"""
HyperHistoryManager — Card B-6 (400-Day Hyper Backfill)

Responsibilities:
  - Bulk-ingest OHLCV candles from exchange API into ohlcv_hyper TimescaleDB table
  - Supports multi-symbol batch operations across the 24-symbol universe
  - Idempotent: ON CONFLICT DO NOTHING prevents duplicate rows
  - Coverage check reports last record time and gap from now

Design constraints:
  - Targets ohlcv_hyper ONLY — never touches ohlcv_history (backtest plane)
  - Fetch loop respects CCXT batch limit (1000 candles per request)
  - Sequential symbol iteration preserves exchange rate limits
  - No runtime/execution coupling; data ingestion only
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.timescale_hypertables import OhlcvHyper
from app.services.symbol_universe import ALL_SYMBOLS

logger = get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────────

# CCXT fetch_ohlcv max per request (Binance default)
CCXT_BATCH_LIMIT = 1000

# Supported timeframes with millisecond durations
TIMEFRAME_MS: dict[str, int] = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
}


# ── Data Contracts ───────────────────────────────────────────────────


@dataclass
class BackfillResult:
    """Result of a single-symbol backfill operation into ohlcv_hyper."""

    exchange: str = ""
    symbol: str = ""
    timeframe: str = "1h"
    days_requested: int = 400
    candles_fetched: int = 0
    candles_inserted: int = 0
    candles_skipped: int = 0  # ON CONFLICT DO NOTHING count
    first_candle_time: datetime | None = None
    last_candle_time: datetime | None = None
    batches_fetched: int = 0
    success: bool = True
    error: str | None = None


@dataclass
class HyperCoverageReport:
    """Coverage statistics for ohlcv_hyper for a single symbol."""

    exchange: str = ""
    symbol: str = ""
    timeframe: str = "1h"
    total_candles: int = 0
    first_candle_time: datetime | None = None
    last_candle_time: datetime | None = None
    gap_from_now_minutes: float | None = None  # minutes since last record
    is_stale: bool = False  # True if gap_from_now_minutes > staleness_threshold


# ── Manager ──────────────────────────────────────────────────────────


class HyperHistoryManager:
    """Manages historical data backfill into TimescaleDB hypertables.

    Similar to HistoryDataManager but targets ohlcv_hyper table
    and supports multi-symbol batch operations.

    All methods require an AsyncSession (injected, not created).
    Exchange API calls are made via the provided exchange_client.
    """

    # ── Single-Symbol Backfill ───────────────────────────────────────

    async def backfill_symbol(
        self,
        session: AsyncSession,
        exchange: str,
        symbol: str,
        timeframe: str,
        days: int = 400,
        exchange_client: Any = None,
    ) -> BackfillResult:
        """Backfill one symbol's OHLCV history into ohlcv_hyper.

        Fetches from exchange API in batches of 1000 candles.
        Uses pg_insert ON CONFLICT DO NOTHING for idempotency.
        Unix ms timestamps are converted to timezone-aware datetime
        for the `time` column (TimescaleDB partition key).

        Args:
            session: Async DB session (caller manages transaction scope).
            exchange: Exchange identifier (e.g. "binance").
            symbol: Trading pair (e.g. "SOL/USDT").
            timeframe: Candle timeframe (e.g. "1h").
            days: How many days of history to fetch (default 400).
            exchange_client: CCXT async exchange instance. If None, a
                placeholder empty list is used (useful for unit tests).

        Returns:
            BackfillResult with insert/skip counts and time coverage.
        """
        result = BackfillResult(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            days_requested=days,
        )

        tf_ms = TIMEFRAME_MS.get(timeframe, 3_600_000)
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        start_ms = now_ms - (days * 24 * 3_600_000)

        total_fetched = 0
        total_inserted = 0
        total_skipped = 0
        batch_count = 0
        first_dt: datetime | None = None
        last_dt: datetime | None = None

        current_since = start_ms

        try:
            while current_since < now_ms:
                # Fetch one batch from exchange
                if exchange_client is not None:
                    try:
                        candles: list[list[Any]] = await exchange_client.fetch_ohlcv(
                            symbol,
                            timeframe=timeframe,
                            since=current_since,
                            limit=CCXT_BATCH_LIMIT,
                        )
                    except Exception as exc:
                        logger.warning(
                            "hyper_backfill_fetch_error",
                            exchange=exchange,
                            symbol=symbol,
                            timeframe=timeframe,
                            since=current_since,
                            error=str(exc),
                        )
                        result.success = False
                        result.error = str(exc)
                        break
                else:
                    candles = []

                if not candles:
                    # No more data available at this point
                    break

                batch_count += 1
                rows = []
                for c in candles:
                    if len(c) < 6:
                        continue
                    ts_ms = int(c[0])
                    candle_dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
                    rows.append(
                        {
                            "time": candle_dt,
                            "symbol": symbol,
                            "exchange": exchange,
                            "timeframe": timeframe,
                            "open": float(c[1]),
                            "high": float(c[2]),
                            "low": float(c[3]),
                            "close": float(c[4]),
                            "volume": float(c[5]),
                        }
                    )

                if rows:
                    stmt = pg_insert(OhlcvHyper).values(rows).on_conflict_do_nothing(
                        index_elements=["time", "symbol"]
                    )
                    db_result = await session.execute(stmt)
                    await session.flush()

                    inserted = db_result.rowcount or 0
                    skipped = len(rows) - inserted
                    total_inserted += inserted
                    total_skipped += skipped
                    total_fetched += len(rows)

                    if first_dt is None:
                        first_dt = rows[0]["time"]
                    last_dt = rows[-1]["time"]

                # Advance cursor past the last candle timestamp
                last_ts_ms = int(candles[-1][0])
                next_since = last_ts_ms + tf_ms

                # Guard: if exchange returns candles at or before our cursor,
                # advance by one batch worth to prevent infinite loop.
                if next_since <= current_since:
                    next_since = current_since + (CCXT_BATCH_LIMIT * tf_ms)

                current_since = next_since

                # If fewer candles than limit, we've reached the end
                if len(candles) < CCXT_BATCH_LIMIT:
                    break

        except Exception as exc:
            logger.error(
                "hyper_backfill_error",
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
                error=str(exc),
            )
            result.success = False
            result.error = str(exc)

        result.candles_fetched = total_fetched
        result.candles_inserted = total_inserted
        result.candles_skipped = total_skipped
        result.batches_fetched = batch_count
        result.first_candle_time = first_dt
        result.last_candle_time = last_dt

        logger.info(
            "hyper_backfill_complete",
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            days=days,
            batches=batch_count,
            fetched=total_fetched,
            inserted=total_inserted,
            skipped=total_skipped,
            success=result.success,
        )
        return result

    # ── Multi-Symbol Backfill ────────────────────────────────────────

    async def backfill_all(
        self,
        session: AsyncSession,
        exchange: str,
        symbols: list[str] | None = None,
        timeframe: str = "1h",
        days: int = 400,
        exchange_client: Any = None,
        max_concurrent: int = 3,
    ) -> list[BackfillResult]:
        """Backfill all 24 symbols sequentially to respect exchange rate limits.

        Despite the max_concurrent parameter (kept for API compatibility and
        potential future use), symbols are processed one at a time by default
        to be conservative with rate limits. Set max_concurrent > 1 only when
        the exchange tier allows it and you have confirmed rate limit headroom.

        Args:
            session: Async DB session (shared across all symbols).
            exchange: Exchange identifier.
            symbols: Override the default 24-symbol universe. None → ALL_SYMBOLS.
            timeframe: Candle timeframe for all symbols.
            days: Days of history to backfill for each symbol.
            exchange_client: CCXT async exchange instance.
            max_concurrent: Concurrency cap (default 3; use 1 for strict sequential).

        Returns:
            List of BackfillResult, one per symbol, in input order.
        """
        target_symbols = symbols if symbols is not None else ALL_SYMBOLS
        results: list[BackfillResult] = []

        logger.info(
            "hyper_backfill_all_start",
            exchange=exchange,
            symbol_count=len(target_symbols),
            timeframe=timeframe,
            days=days,
            max_concurrent=max_concurrent,
        )

        if max_concurrent <= 1:
            # Strict sequential — safest for rate limits
            for idx, symbol in enumerate(target_symbols):
                logger.info(
                    "hyper_backfill_symbol_progress",
                    symbol=symbol,
                    index=idx + 1,
                    total=len(target_symbols),
                )
                res = await self.backfill_symbol(
                    session=session,
                    exchange=exchange,
                    symbol=symbol,
                    timeframe=timeframe,
                    days=days,
                    exchange_client=exchange_client,
                )
                results.append(res)
        else:
            # Bounded concurrency via semaphore
            semaphore = asyncio.Semaphore(max_concurrent)

            async def _bounded(sym: str) -> BackfillResult:
                async with semaphore:
                    return await self.backfill_symbol(
                        session=session,
                        exchange=exchange,
                        symbol=sym,
                        timeframe=timeframe,
                        days=days,
                        exchange_client=exchange_client,
                    )

            tasks = [_bounded(sym) for sym in target_symbols]
            results = list(await asyncio.gather(*tasks))

        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        total_inserted = sum(r.candles_inserted for r in results)

        logger.info(
            "hyper_backfill_all_complete",
            exchange=exchange,
            symbol_count=len(target_symbols),
            successful=successful,
            failed=failed,
            total_inserted=total_inserted,
        )
        return results

    # ── Coverage Check ───────────────────────────────────────────────

    async def check_hyper_coverage(
        self,
        session: AsyncSession,
        exchange: str,
        symbol: str,
        timeframe: str,
        staleness_threshold_minutes: float = 65.0,
    ) -> HyperCoverageReport:
        """Check coverage in ohlcv_hyper table for a symbol.

        Queries for total row count, first/last candle time, and computes
        how many minutes have elapsed since the most recent record.

        Args:
            session: Async DB session.
            exchange: Exchange identifier.
            symbol: Trading pair.
            timeframe: Candle timeframe.
            staleness_threshold_minutes: Flag as stale if gap exceeds this.
                Default 65 minutes (1h + 5-minute grace for 1h candles).

        Returns:
            HyperCoverageReport with coverage statistics.
        """
        report = HyperCoverageReport(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
        )

        try:
            stmt = text(
                """
                SELECT
                    COUNT(*) AS total_candles,
                    MIN(time) AS first_time,
                    MAX(time) AS last_time
                FROM ohlcv_hyper
                WHERE exchange = :exchange
                  AND symbol = :symbol
                  AND timeframe = :timeframe
                """
            )
            row = (
                await session.execute(
                    stmt,
                    {"exchange": exchange, "symbol": symbol, "timeframe": timeframe},
                )
            ).one_or_none()

            if row is None or row[0] == 0:
                return report

            report.total_candles = int(row[0])
            report.first_candle_time = row[1]
            report.last_candle_time = row[2]

            if report.last_candle_time is not None:
                now_utc = datetime.now(timezone.utc)
                last_aware = report.last_candle_time
                if last_aware.tzinfo is None:
                    last_aware = last_aware.replace(tzinfo=timezone.utc)
                gap_minutes = (now_utc - last_aware).total_seconds() / 60.0
                report.gap_from_now_minutes = round(gap_minutes, 1)
                report.is_stale = gap_minutes > staleness_threshold_minutes

        except Exception as exc:
            logger.warning(
                "hyper_coverage_check_error",
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
                error=str(exc),
            )

        logger.debug(
            "hyper_coverage_checked",
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            total_candles=report.total_candles,
            gap_minutes=report.gap_from_now_minutes,
            is_stale=report.is_stale,
        )
        return report
