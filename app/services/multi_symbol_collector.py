"""
MultiSymbolCollector — Card B (B-2 / B-3 / B-4)
Parallel data collection across the 24-symbol universe with TimescaleDB persistence.

Design:
  - Wraps MarketDataCollector (single-symbol) with asyncio.Semaphore rate limiting.
  - Collects OHLCV, funding rate, open interest, and orderbook snapshots concurrently.
  - Persists to TimescaleDB hypertables via ON CONFLICT DO NOTHING (idempotent).
  - One symbol failure is isolated — it never aborts the rest of the gather.

Typical usage (from a Celery task or FastAPI background task):
    collector = MultiSymbolCollector(exchange_client, async_session_factory)
    summary = await collector.collect_all(timeframe="1m")
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.logging import get_logger
from app.models.timescale_hypertables import (
    FundingRateHyper,
    OhlcvHyper,
    OpenInterestHyper,
    OrderbookSnapshotHyper,
)
from app.services.market_data_collector import MarketDataCollector
from app.services.symbol_universe import ALL_SYMBOLS

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Public data contracts
# ---------------------------------------------------------------------------


@dataclass
class SymbolCollectionResult:
    """Per-symbol outcome returned by :meth:`MultiSymbolCollector._collect_symbol`."""

    symbol: str
    success: bool
    ohlcv_count: int = 0
    has_funding: bool = False
    has_oi: bool = False
    has_orderbook: bool = False
    error: str | None = None
    collected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CollectionSummary:
    """Aggregate outcome returned by :meth:`MultiSymbolCollector.collect_all`."""

    total_symbols: int
    successful: int
    failed: int
    results: list[SymbolCollectionResult]
    duration_seconds: float
    collected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class MultiSymbolCollector:
    """Collect market data for the full 24-symbol universe in parallel.

    Args:
        exchange_client: An async CCXT exchange instance (e.g. ccxt.pro.binance).
        db_session_factory: An ``async_sessionmaker`` (or any callable that returns
            an ``AsyncSession`` context manager).
        max_concurrent: Maximum number of symbols collected at the same time.
            Default 6 — conservative enough for most exchange rate-limit tiers.
    """

    def __init__(
        self,
        exchange_client: Any,
        db_session_factory: Any,
        max_concurrent: int = 6,
    ) -> None:
        self.exchange_client = exchange_client
        self.db_session_factory = db_session_factory
        self.max_concurrent = max_concurrent

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def collect_all(
        self,
        symbols: list[str] | None = None,
        timeframe: str = "1m",
    ) -> CollectionSummary:
        """Collect OHLCV + funding + OI + orderbook for all symbols.

        Args:
            symbols: Override the default universe. ``None`` → :data:`ALL_SYMBOLS`.
            timeframe: CCXT timeframe string passed to ``fetch_ohlcv``.

        Returns:
            :class:`CollectionSummary` with per-symbol detail.
        """
        target_symbols = symbols if symbols is not None else ALL_SYMBOLS
        semaphore = asyncio.Semaphore(self.max_concurrent)
        started_at = time.monotonic()

        tasks = [
            self._collect_symbol(symbol, timeframe, semaphore)
            for symbol in target_symbols
        ]
        results: list[SymbolCollectionResult] = await asyncio.gather(*tasks)

        duration = time.monotonic() - started_at
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful

        summary = CollectionSummary(
            total_symbols=len(results),
            successful=successful,
            failed=failed,
            results=list(results),
            duration_seconds=round(duration, 3),
        )

        logger.info(
            "multi_symbol_collection_complete",
            total=summary.total_symbols,
            successful=summary.successful,
            failed=summary.failed,
            duration_seconds=summary.duration_seconds,
            timeframe=timeframe,
        )
        return summary

    # ------------------------------------------------------------------
    # Per-symbol worker
    # ------------------------------------------------------------------

    async def _collect_symbol(
        self,
        symbol: str,
        timeframe: str,
        semaphore: asyncio.Semaphore,
    ) -> SymbolCollectionResult:
        """Collect all data types for *symbol* and persist to DB.

        The semaphore limits concurrency so exchange rate limits are respected.
        Any exception is caught and reflected in the returned result — it does
        NOT propagate to the outer gather.
        """
        async with semaphore:
            try:
                collector = MarketDataCollector(self.exchange_client)
                result = await collector.collect(symbol, ohlcv_timeframe=timeframe)

                ohlcv_count = await self._persist_ohlcv(result)
                has_funding = await self._persist_funding(symbol, result)
                has_oi = await self._persist_oi(symbol, result)
                has_orderbook = await self._persist_orderbook(symbol, result)

                logger.debug(
                    "symbol_collected",
                    symbol=symbol,
                    ohlcv_count=ohlcv_count,
                    has_funding=has_funding,
                    has_oi=has_oi,
                    has_orderbook=has_orderbook,
                )
                return SymbolCollectionResult(
                    symbol=symbol,
                    success=True,
                    ohlcv_count=ohlcv_count,
                    has_funding=has_funding,
                    has_oi=has_oi,
                    has_orderbook=has_orderbook,
                )

            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "symbol_collection_failed",
                    symbol=symbol,
                    error=str(exc),
                )
                return SymbolCollectionResult(
                    symbol=symbol,
                    success=False,
                    error=str(exc),
                )

    # ------------------------------------------------------------------
    # Persist helpers
    # ------------------------------------------------------------------

    async def _persist_ohlcv(self, result: Any) -> int:
        """Write OHLCV bars to ``ohlcv_hyper``.

        Returns:
            Number of rows inserted (conflicts silently skipped).
        """
        if not result.ohlcv:
            return 0

        exchange = result.exchange
        symbol = result.symbol
        rows = [
            {
                "time": datetime.fromtimestamp(bar.timestamp / 1000, tz=timezone.utc),
                "symbol": symbol,
                "exchange": exchange,
                "timeframe": "1m",  # collector default; caller can override if needed
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
            }
            for bar in result.ohlcv
        ]

        stmt = pg_insert(OhlcvHyper).values(rows).on_conflict_do_nothing(
            index_elements=["time", "symbol"]
        )

        async with self.db_session_factory() as session:
            await session.execute(stmt)
            await session.commit()

        return len(rows)

    async def _persist_funding(self, symbol: str, result: Any) -> bool:
        """Write funding rate to ``funding_rate_hyper``.

        Returns:
            True if a row was attempted (data was present), False otherwise.
        """
        if result.funding_rate is None:
            return False

        collected_at = result.collected_at or datetime.now(timezone.utc)

        stmt = (
            pg_insert(FundingRateHyper)
            .values(
                time=collected_at,
                symbol=symbol,
                exchange=result.exchange,
                funding_rate=result.funding_rate,
                mark_price=None,
                index_price=None,
                next_funding_time=None,
            )
            .on_conflict_do_nothing(index_elements=["time", "symbol"])
        )

        async with self.db_session_factory() as session:
            await session.execute(stmt)
            await session.commit()

        return True

    async def _persist_oi(self, symbol: str, result: Any) -> bool:
        """Write open interest to ``open_interest_hyper``.

        Returns:
            True if a row was attempted (data was present), False otherwise.
        """
        if result.open_interest is None:
            return False

        collected_at = result.collected_at or datetime.now(timezone.utc)

        stmt = (
            pg_insert(OpenInterestHyper)
            .values(
                time=collected_at,
                symbol=symbol,
                exchange=result.exchange,
                open_interest=result.open_interest,
                open_interest_value=None,
            )
            .on_conflict_do_nothing(index_elements=["time", "symbol"])
        )

        async with self.db_session_factory() as session:
            await session.execute(stmt)
            await session.commit()

        return True

    async def _persist_orderbook(self, symbol: str, result: Any) -> bool:
        """Write top-20 orderbook snapshot to ``orderbook_snapshot_hyper``.

        Extracts up to 20 bid/ask levels, computes spread and mid_price.

        Returns:
            True if a row was attempted (data was present), False otherwise.
        """
        ob = result.order_book
        if ob is None:
            return False

        bids: list[list[float]] = ob.get("bids", [])[:20]
        asks: list[list[float]] = ob.get("asks", [])[:20]

        if not bids or not asks:
            return False

        bid_prices = [level[0] for level in bids]
        bid_volumes = [level[1] for level in bids]
        ask_prices = [level[0] for level in asks]
        ask_volumes = [level[1] for level in asks]

        best_bid = bid_prices[0]
        best_ask = ask_prices[0]
        spread = best_ask - best_bid
        mid_price = (best_ask + best_bid) / 2

        collected_at = result.collected_at or datetime.now(timezone.utc)

        stmt = (
            pg_insert(OrderbookSnapshotHyper)
            .values(
                time=collected_at,
                symbol=symbol,
                exchange=result.exchange,
                bid_prices=bid_prices,
                bid_volumes=bid_volumes,
                ask_prices=ask_prices,
                ask_volumes=ask_volumes,
                spread=spread,
                mid_price=mid_price,
            )
            .on_conflict_do_nothing(index_elements=["time", "symbol"])
        )

        async with self.db_session_factory() as session:
            await session.execute(stmt)
            await session.commit()

        return True
