"""
Multi-Symbol Collection Tasks — Card B-7
Celery tasks for 24-symbol market data collection and historical backfill.

Three tasks:
  1. collect_all_market_data  — OHLCV + funding + OI + orderbook for all 24 symbols
                                Runs every 5 minutes.
  2. collect_extended_sentiment — 4 additional sentiment APIs (CryptoPanic, LunarCrush,
                                  DefiLlama, Messari). Runs every hour.
  3. backfill_history          — One-time backfill of ohlcv_hyper for all 24 symbols.
                                  Triggered manually or via admin endpoint.

All tasks use asyncio.run() pattern since Celery workers are synchronous.
Exchange client is created fresh per task invocation (avoids closed event loop
across asyncio.run() boundaries — see ExchangeFactory.create_fresh docstring).
"""

import asyncio

import ccxt.async_support as ccxt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from workers.celery_app import celery_app
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _create_fresh_db_session_factory() -> tuple:
    """Create a fresh SQLAlchemy async engine + session factory per task.

    The module-level engine (app.core.database.engine) binds its internal
    asyncpg connection pool to the event loop running at import time.
    Celery solo-pool workers call asyncio.run() for each task, which creates
    a NEW event loop — making the module-level pool reference a CLOSED loop.

    This function creates a fresh engine each invocation, ensuring the pool
    is bound to the current (active) event loop.

    Returns:
        (engine, session_factory) — caller must dispose engine after use.
    """
    engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=5,
        pool_timeout=30,
        pool_recycle=1800,
    )
    factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False,
    )
    return engine, factory


def _create_public_binance() -> ccxt.binance:
    """Create a public-only Binance client (mainnet, no testnet).

    Uses real Binance public API for market data collection.
    Testnet is intentionally disabled because:
      - Testnet has limited symbol support (no altcoins)
      - Testnet OHLCV data is sparse/unreliable
      - Public API is read-only → no Gate violation (G2 safe)

    Uses aiohttp.TCPConnector with ThreadedResolver to avoid aiodns
    DNS resolution failures on Windows (aiodns requires c-ares which
    may not be available or may fail to contact DNS servers).
    """
    import aiohttp

    connector = aiohttp.TCPConnector(resolver=aiohttp.resolver.ThreadedResolver())
    session = aiohttp.ClientSession(connector=connector)
    return ccxt.binance({
        "enableRateLimit": True,
        "options": {"defaultType": "spot"},
        "session": session,
    })


# ── Task 1: collect_all_market_data ──────────────────────────────────


@celery_app.task(
    name="workers.tasks.multi_symbol_collection_tasks.collect_all_market_data",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
)
def collect_all_market_data(
    self,
    symbols: list[str] | None = None,
    timeframe: str = "1m",
    exchange_name: str = "binance",
):
    """Collect OHLCV + funding + OI + orderbook for all 24 symbols.

    Designed to run every 5 minutes. Creates a fresh exchange client per
    invocation to avoid event-loop closure issues in Celery workers.

    Args:
        symbols: Override the 24-symbol universe. None → ALL_SYMBOLS.
        timeframe: CCXT timeframe passed to fetch_ohlcv. Default "1m".
        exchange_name: Exchange to collect from. Default "binance".
    """
    try:
        from app.services.multi_symbol_collector import MultiSymbolCollector

        async def _run() -> dict:
            engine, session_factory = _create_fresh_db_session_factory()
            client = _create_public_binance()
            try:
                collector = MultiSymbolCollector(
                    exchange_client=client,
                    db_session_factory=session_factory,
                )
                summary = await collector.collect_all(
                    symbols=symbols,
                    timeframe=timeframe,
                )
                return {
                    "total_symbols": summary.total_symbols,
                    "successful": summary.successful,
                    "failed": summary.failed,
                    "duration_seconds": summary.duration_seconds,
                    "timeframe": timeframe,
                }
            finally:
                await client.close()
                await engine.dispose()

        result = asyncio.run(_run())

        logger.info(
            "collect_all_market_data_complete",
            **result,
        )
        return result

    except Exception as exc:
        logger.error(
            "collect_all_market_data_failed",
            exchange=exchange_name,
            timeframe=timeframe,
            error=str(exc),
        )
        raise self.retry(exc=exc)


# ── Task 2: collect_extended_sentiment ───────────────────────────────


@celery_app.task(
    name="workers.tasks.multi_symbol_collection_tasks.collect_extended_sentiment",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
)
def collect_extended_sentiment(self, symbols: list[str] | None = None):
    """Collect extended sentiment data from 4 additional public APIs.

    Sources: CryptoPanic, LunarCrush, DefiLlama, Messari.
    Designed to run every hour. Each source failure is isolated.

    Args:
        symbols: Override the symbol list for per-symbol metrics.
            None → defaults to full 24-symbol universe.
    """
    try:
        from app.services.extended_sentiment_collector import ExtendedSentimentCollector

        async def _run() -> dict:
            collector = ExtendedSentimentCollector()
            result = await collector.collect_all(symbols=symbols)
            return {
                "sources_ok": result.sources_ok,
                "sources_failed": result.sources_failed,
                "has_cryptopanic": result.cryptopanic is not None,
                "has_lunarcrush": result.lunarcrush is not None,
                "has_defillama": result.defillama is not None,
                "has_messari": result.messari is not None,
            }

        result = asyncio.run(_run())

        logger.info(
            "collect_extended_sentiment_complete",
            **result,
        )
        return result

    except Exception as exc:
        logger.error(
            "collect_extended_sentiment_failed",
            error=str(exc),
        )
        raise self.retry(exc=exc)


# ── Task 3: backfill_history ─────────────────────────────────────────


@celery_app.task(
    name="workers.tasks.multi_symbol_collection_tasks.backfill_history",
    bind=True,
    max_retries=0,  # One-time operation; manual retry if needed
    time_limit=7200,  # 2-hour hard limit (400 days × 24 symbols is slow)
    soft_time_limit=6600,
)
def backfill_history(
    self,
    symbols: list[str] | None = None,
    timeframe: str = "1h",
    days: int = 400,
    exchange_name: str = "binance",
    max_concurrent: int = 1,
):
    """One-time backfill of historical OHLCV data for all 24 symbols.

    Persists candles into ohlcv_hyper (NOT ohlcv_history).
    Sequential by default (max_concurrent=1) to respect exchange rate limits.
    This task is intended to be triggered manually via Celery CLI or admin
    endpoint — not added to beat_schedule.

    Args:
        symbols: Override the 24-symbol universe. None → ALL_SYMBOLS.
        timeframe: Candle timeframe (default "1h").
        days: Days of history to fetch per symbol (default 400).
        exchange_name: Exchange to fetch from (default "binance").
        max_concurrent: Concurrency cap. Default 1 (sequential).
    """
    try:
        from app.services.hyper_history_manager import HyperHistoryManager

        async def _run() -> dict:
            engine, session_factory = _create_fresh_db_session_factory()
            client = _create_public_binance()
            try:
                manager = HyperHistoryManager()
                async with session_factory() as session:
                    results = await manager.backfill_all(
                        session=session,
                        exchange=exchange_name,
                        symbols=symbols,
                        timeframe=timeframe,
                        days=days,
                        exchange_client=client,
                        max_concurrent=max_concurrent,
                    )
                    await session.commit()

                successful = sum(1 for r in results if r.success)
                failed = len(results) - successful
                total_inserted = sum(r.candles_inserted for r in results)
                total_fetched = sum(r.candles_fetched for r in results)

                return {
                    "symbol_count": len(results),
                    "successful": successful,
                    "failed": failed,
                    "total_fetched": total_fetched,
                    "total_inserted": total_inserted,
                    "timeframe": timeframe,
                    "days": days,
                }
            finally:
                await client.close()
                await engine.dispose()

        result = asyncio.run(_run())

        logger.info(
            "backfill_history_complete",
            **result,
        )
        return result

    except Exception as exc:
        logger.error(
            "backfill_history_failed",
            exchange=exchange_name,
            timeframe=timeframe,
            days=days,
            error=str(exc),
        )
        # No retry for backfill — surface the error for manual investigation
        raise
