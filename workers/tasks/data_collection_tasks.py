"""
Data Collection Tasks — CR-038 Phase 1
Celery tasks for periodic market data and sentiment collection.
Read-only — never modifies exchange state.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from workers.celery_app import celery_app
from app.core.config import settings
from app.core.logging import get_logger
from app.models.market_state import MarketState
from app.services.market_data_collector import MarketDataCollector
from app.services.sentiment_collector import SentimentCollector
from app.services.indicator_calculator import IndicatorCalculator
from app.services.market_state_builder import MarketStateBuilder
from exchanges.factory import ExchangeFactory

logger = get_logger(__name__)

# Module-level bounded engine: pool_size=1, max_overflow=0
# Prevents per-invocation engine leak (CR-048 DB saturation fix).
# Lazy-initialized on first task call so importing this module does
# not require a valid DATABASE_URL (CI/unit-test isolation).
_sync_engine = None
_SyncSessionFactory = None


def _get_session_factory():
    """
    Return the bounded sync session factory, initializing on first call.

    Moving create_engine() out of module scope prevents import-time DB
    side effects: unit tests that exercise pure helpers (_to_native,
    _classify_failure) can import this module without a valid
    DATABASE_URL. Runtime semantics are preserved — the pool is bounded
    to size=1, max_overflow=0, pre-ping enabled, recycle=1800 — and the
    engine/session factory are created once per process.
    """
    global _sync_engine, _SyncSessionFactory
    if _SyncSessionFactory is None:
        _sync_engine = create_engine(
            settings.database_url_sync,
            pool_pre_ping=True,
            pool_size=1,
            max_overflow=0,
            pool_recycle=1800,
        )
        _SyncSessionFactory = sessionmaker(bind=_sync_engine)
    return _SyncSessionFactory


# CR-NEW Change-1: numpy/pandas scalar → Python native conversion
# Prevents psycopg2 InvalidSchemaName("np") from numpy.float64 leaking
# into SQL parameter binding. Applied defensively to all MarketState
# scalar fields. See docs/operations/evidence/cr_new_p3_window_seal_2026-04-14.md
def _to_native(value: Any) -> Any:
    """
    Convert numpy/pandas scalar to Python native scalar.
    Pass-through for None and already-native types.
    Preserves NaN semantics (numpy.float64('nan').item() == nan).
    """
    if value is None:
        return None
    # numpy scalars and 0-d arrays expose .item() returning Python native
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return item()
        except (ValueError, TypeError):
            return value
    return value


# CR-NEW Change-2: deterministic vs transient failure classifier
# Deterministic failures skip retry to avoid log storms and preserve
# terminal_failure visibility in logs and Celery backend (no success disguise).
_DETERMINISTIC_SCHEMA_MARKERS = (
    'schema "np"',
    'schema "pd"',
    'schema "numpy"',
    'schema "pandas"',
)


def _classify_failure(exc: BaseException) -> tuple[str, bool]:
    """
    Classify exception → (failure_class, retryable).

    Classification strategy:
      - Fast path: exception type-name match
        (InvalidSchemaName, asyncio.TimeoutError, OperationalError)
      - Fallback: schema marker string match in str(exc) for wrapped
        DBAPI errors (e.g. SQLAlchemy-wrapped psycopg2 InvalidSchemaName)

    Returns:
        ("deterministic_type_schema", False)  # no retry, terminal_failure
        ("transient_network", True)            # retry scheduled
        ("transient_db", True)                 # retry scheduled
        ("unknown", True)                      # retry (backward-compat default)
    """
    exc_type_name = type(exc).__name__
    exc_str = str(exc).lower()

    # Deterministic: numpy/pandas scalar leak → psycopg2 InvalidSchemaName
    if exc_type_name == "InvalidSchemaName":
        return ("deterministic_type_schema", False)
    if any(marker in exc_str for marker in _DETERMINISTIC_SCHEMA_MARKERS):
        return ("deterministic_type_schema", False)
    if isinstance(exc, TypeError) and "numpy" in exc_str:
        return ("deterministic_type_schema", False)

    # Transient: network / DB
    if isinstance(exc, asyncio.TimeoutError):
        return ("transient_network", True)
    if isinstance(exc, OperationalError):
        return ("transient_db", True)

    # Default: retry (preserves prior behavior for unknown errors)
    return ("unknown", True)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def collect_market_state(
    self,
    symbol: str = "BTC/USDT",
    exchange_name: str = "binance",
    ohlcv_timeframe: str = "1h",
    ohlcv_limit: int = 200,
):
    """Collect full market state: price + indicators + sentiment → persist snapshot."""
    try:

        async def _collect():
            # Create exchange INSIDE async context so the aiohttp session
            # binds to the *current* event loop created by asyncio.run().
            # Using the singleton here caused "Event loop is closed" on
            # every invocation after the first asyncio.run() in the same
            # Celery solo-pool worker process.
            exchange = ExchangeFactory.create_fresh(exchange_name)
            try:
                collector = MarketDataCollector(exchange.client)
                market_data = await collector.collect(
                    symbol=symbol,
                    ohlcv_timeframe=ohlcv_timeframe,
                    ohlcv_limit=ohlcv_limit,
                )

                sentiment_collector = SentimentCollector()
                sentiment = await sentiment_collector.collect()

                calculator = IndicatorCalculator()
                indicators = calculator.calculate(market_data.ohlcv)

                builder = MarketStateBuilder()
                snapshot = builder.build(market_data, indicators, sentiment)
                return snapshot
            finally:
                await exchange.close()

        snapshot = asyncio.run(_collect())

        # Persist to DB — lazy-init session factory on first call
        sess = _get_session_factory()()
        try:
            # CR-NEW Change-1: defensive _to_native() wrap on all scalar fields
            # Root cause was snapshot.indicators.obv returning numpy.float64;
            # wrapping all indicator/sentiment/on_chain/microstructure scalars
            # prevents future numpy leak regressions.
            state = MarketState(
                exchange=snapshot.exchange,
                symbol=snapshot.symbol,
                price=_to_native(snapshot.price_data.price),
                bid=_to_native(snapshot.microstructure.bid),
                ask=_to_native(snapshot.microstructure.ask),
                spread_pct=_to_native(snapshot.microstructure.spread_pct),
                volume_24h=_to_native(snapshot.price_data.volume_24h),
                rsi_14=_to_native(snapshot.indicators.rsi_14),
                macd_line=_to_native(snapshot.indicators.macd_line),
                macd_signal=_to_native(snapshot.indicators.macd_signal),
                macd_histogram=_to_native(snapshot.indicators.macd_histogram),
                bb_upper=_to_native(snapshot.indicators.bb_upper),
                bb_middle=_to_native(snapshot.indicators.bb_middle),
                bb_lower=_to_native(snapshot.indicators.bb_lower),
                atr_14=_to_native(snapshot.indicators.atr_14),
                adx_14=_to_native(snapshot.indicators.adx_14),
                obv=_to_native(snapshot.indicators.obv),  # <- original leak field
                sma_20=_to_native(snapshot.indicators.sma_20),
                sma_50=_to_native(snapshot.indicators.sma_50),
                sma_200=_to_native(snapshot.indicators.sma_200),
                ema_12=_to_native(snapshot.indicators.ema_12),
                ema_26=_to_native(snapshot.indicators.ema_26),
                fear_greed_index=_to_native(snapshot.sentiment.fear_greed_index),
                fear_greed_label=snapshot.sentiment.fear_greed_label,  # str, no wrap
                hash_rate=_to_native(snapshot.on_chain.hash_rate),
                difficulty=_to_native(snapshot.on_chain.difficulty),
                tx_count_24h=_to_native(snapshot.on_chain.tx_count_24h),
                mempool_size=_to_native(snapshot.on_chain.mempool_size),
                mempool_fee_fast=_to_native(snapshot.on_chain.mempool_fee_fast),
                mempool_fee_medium=_to_native(snapshot.on_chain.mempool_fee_medium),
                btc_dominance=_to_native(snapshot.on_chain.btc_dominance),
                total_market_cap_usd=_to_native(snapshot.on_chain.total_market_cap_usd),
                funding_rate=_to_native(snapshot.microstructure.funding_rate),
                open_interest=_to_native(snapshot.microstructure.open_interest),
                regime=snapshot.regime,  # str, no wrap
                snapshot_at=snapshot.snapshot_at or datetime.now(timezone.utc),
            )
            sess.add(state)
            sess.commit()
        finally:
            sess.close()

        logger.info(
            "market_state_persisted",
            exchange=snapshot.exchange,
            symbol=snapshot.symbol,
            regime=snapshot.regime,
            price=snapshot.price_data.price,
        )
        return {
            "exchange": snapshot.exchange,
            "symbol": snapshot.symbol,
            "regime": snapshot.regime,
            "price": snapshot.price_data.price,
        }

    except Exception as e:
        # CR-NEW Change-2: classify deterministic vs transient failure.
        # Deterministic → no retry, but raise to preserve terminal_failure
        # visibility (Celery records FAILURE; no success disguise).
        # Transient → existing retry path (max_retries=2, default_retry_delay=30).
        failure_class, retryable = _classify_failure(e)
        if not retryable:
            logger.error(
                "collect_market_state_terminal_failure",
                symbol=symbol,
                exchange=exchange_name,
                failure_class=failure_class,
                retryable=False,
                action="no_retry",
                terminal_failure=True,
                error=str(e),
            )
            raise  # preserve Celery FAILURE state, no retry
        logger.error(
            "market_state_collection_failed",
            symbol=symbol,
            exchange=exchange_name,
            failure_class=failure_class,
            retryable=True,
            action="retry_scheduled",
            terminal_failure=False,
            error=str(e),
        )
        raise self.retry(exc=e)


@celery_app.task
def collect_sentiment_only():
    """Lightweight sentiment-only collection (runs less frequently)."""
    try:

        async def _collect():
            collector = SentimentCollector()
            return await collector.collect()

        result = asyncio.run(_collect())
        logger.info(
            "sentiment_collected",
            fear_greed=result.fear_greed_index,
            label=result.fear_greed_label,
        )
        return {
            "fear_greed_index": result.fear_greed_index,
            "fear_greed_label": result.fear_greed_label,
        }
    except Exception as e:
        logger.error("sentiment_collection_failed", error=str(e))
        raise
