"""
HistoryDataManager — Phase A (400-Day Backtest Data Plane)

Responsibilities:
  - Bulk-ingest OHLCV candles from exchange API into ohlcv_history table
  - Query stored candles for deterministic backtest replay
  - Validate data completeness (gap detection, coverage stats)
  - Normalize symbol/exchange/timeframe identifiers

Design constraints:
  - Backtest data plane ONLY — no runtime/execution coupling
  - Read interface returns raw OHLCV lists compatible with BacktestingEngine.run()
  - Write path: bulk historical ingestion only (no live-stream writes)
  - Idempotent upsert: duplicate (exchange, symbol, timeframe, open_time) ignored
  - Event metadata tagging via separate update path
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select, func, text, delete, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.ohlcv_history import OhlcvHistory

logger = get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────────

# 400 days * 24 hours = 9,600 candles for 1h timeframe
TARGET_DAYS = 400
HOURS_PER_DAY = 24
TARGET_CANDLES_1H = TARGET_DAYS * HOURS_PER_DAY  # 9,600

# CCXT fetch_ohlcv max per request (Binance default)
CCXT_BATCH_LIMIT = 1000

# Supported timeframes with their millisecond durations
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
class IngestionResult:
    """Result of a bulk ingestion operation."""

    exchange: str = ""
    symbol: str = ""
    timeframe: str = "1h"
    candles_fetched: int = 0
    candles_inserted: int = 0
    candles_skipped: int = 0  # duplicates ignored
    first_ts: int = 0
    last_ts: int = 0
    gaps_detected: int = 0
    coverage_pct: float = 0.0


@dataclass
class CoverageReport:
    """Data coverage statistics for a symbol."""

    exchange: str = ""
    symbol: str = ""
    timeframe: str = "1h"
    total_candles: int = 0
    expected_candles: int = 0
    coverage_pct: float = 0.0
    first_ts: int = 0
    last_ts: int = 0
    gap_count: int = 0
    gap_timestamps: list[int] = field(default_factory=list)
    days_covered: float = 0.0


# ── Manager ──────────────────────────────────────────────────────────


class HistoryDataManager:
    """Manages OHLCV history for backtest replay.

    All methods require an AsyncSession (injected, not created).
    Pure data operations — no exchange API calls.
    Exchange data fetching is handled by the caller.
    """

    # ── Ingestion ────────────────────────────────────────────────────

    async def ingest_candles(
        self,
        session: AsyncSession,
        exchange: str,
        symbol: str,
        timeframe: str,
        candles: list[list[Any]],
    ) -> IngestionResult:
        """Bulk-insert OHLCV candles with idempotent upsert.

        Args:
            session: Async DB session (caller manages transaction).
            exchange: Exchange identifier (e.g. "binance").
            symbol: Trading pair (e.g. "SOL/USDT").
            timeframe: Candle timeframe (e.g. "1h").
            candles: List of [timestamp_ms, open, high, low, close, volume].

        Returns:
            IngestionResult with insert/skip counts.
        """
        result = IngestionResult(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            candles_fetched=len(candles),
        )

        if not candles:
            return result

        now = datetime.utcnow()  # naive UTC — required by asyncpg TIMESTAMP WITHOUT TIME ZONE
        rows = []
        for c in candles:
            if len(c) < 6:
                continue
            rows.append(
                {
                    "id": str(uuid4()),
                    "exchange": exchange,
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "open_time": int(c[0]),
                    "open": float(c[1]),
                    "high": float(c[2]),
                    "low": float(c[3]),
                    "close": float(c[4]),
                    "volume": float(c[5]),
                    "event_week_flag": False,
                    "macro_event_type": None,
                    "high_volatility_flag": False,
                    "ingested_at": now,
                }
            )

        if not rows:
            return result

        # PostgreSQL ON CONFLICT DO NOTHING for idempotent ingestion
        stmt = pg_insert(OhlcvHistory).values(rows)
        stmt = stmt.on_conflict_do_nothing(constraint="uq_ohlcv_canonical_slot")
        db_result = await session.execute(stmt)
        await session.flush()

        inserted: int = db_result.rowcount or 0
        result.candles_inserted = inserted
        result.candles_skipped = len(rows) - inserted
        result.first_ts = int(rows[0]["open_time"])  # type: ignore[call-overload]
        result.last_ts = int(rows[-1]["open_time"])  # type: ignore[call-overload]

        logger.info(
            "ohlcv_ingested",
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            fetched=len(candles),
            inserted=inserted,
            skipped=result.candles_skipped,
        )
        return result

    # ── Query (Read-Only Replay Interface) ───────────────────────────

    async def get_replay_candles(
        self,
        session: AsyncSession,
        exchange: str,
        symbol: str,
        timeframe: str = "1h",
        start_ts: int | None = None,
        end_ts: int | None = None,
        limit: int | None = None,
    ) -> list[list[Any]]:
        """Retrieve candles in BacktestingEngine-compatible format.

        Returns:
            List of [timestamp_ms, open, high, low, close, volume]
            sorted by open_time ASC (deterministic replay order).
        """
        stmt = (
            select(
                OhlcvHistory.open_time,
                OhlcvHistory.open,
                OhlcvHistory.high,
                OhlcvHistory.low,
                OhlcvHistory.close,
                OhlcvHistory.volume,
            )
            .where(OhlcvHistory.exchange == exchange)
            .where(OhlcvHistory.symbol == symbol)
            .where(OhlcvHistory.timeframe == timeframe)
            .order_by(OhlcvHistory.open_time.asc())
        )

        if start_ts is not None:
            stmt = stmt.where(OhlcvHistory.open_time >= start_ts)
        if end_ts is not None:
            stmt = stmt.where(OhlcvHistory.open_time <= end_ts)
        if limit is not None:
            stmt = stmt.limit(limit)

        rows = (await session.execute(stmt)).all()
        return [[r[0], r[1], r[2], r[3], r[4], r[5]] for r in rows]

    async def get_candle_count(
        self,
        session: AsyncSession,
        exchange: str,
        symbol: str,
        timeframe: str = "1h",
    ) -> int:
        """Count stored candles for a symbol."""
        stmt = (
            select(func.count())
            .select_from(OhlcvHistory)
            .where(OhlcvHistory.exchange == exchange)
            .where(OhlcvHistory.symbol == symbol)
            .where(OhlcvHistory.timeframe == timeframe)
        )
        result = await session.execute(stmt)
        count: int = result.scalar_one()
        return count

    # ── Coverage Analysis ────────────────────────────────────────────

    async def check_coverage(
        self,
        session: AsyncSession,
        exchange: str,
        symbol: str,
        timeframe: str = "1h",
    ) -> CoverageReport:
        """Analyze data coverage and detect gaps.

        Returns:
            CoverageReport with gap analysis.
        """
        report = CoverageReport(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
        )

        # Get all stored timestamps in order
        stmt = (
            select(OhlcvHistory.open_time)
            .where(OhlcvHistory.exchange == exchange)
            .where(OhlcvHistory.symbol == symbol)
            .where(OhlcvHistory.timeframe == timeframe)
            .order_by(OhlcvHistory.open_time.asc())
        )
        rows = (await session.execute(stmt)).scalars().all()

        if not rows:
            return report

        timestamps = [int(ts) for ts in rows]
        report.total_candles = len(timestamps)
        report.first_ts = timestamps[0]
        report.last_ts = timestamps[-1]

        # Calculate expected candles
        tf_ms = TIMEFRAME_MS.get(timeframe, 3_600_000)
        expected = ((timestamps[-1] - timestamps[0]) // tf_ms) + 1
        report.expected_candles = expected
        report.coverage_pct = round(len(timestamps) / expected * 100, 2) if expected > 0 else 0.0
        report.days_covered = round((timestamps[-1] - timestamps[0]) / 86_400_000, 1)

        # Detect gaps
        gaps = []
        for i in range(1, len(timestamps)):
            delta = timestamps[i] - timestamps[i - 1]
            if delta > tf_ms * 1.5:  # Allow small tolerance
                missing_count = (delta // tf_ms) - 1
                for j in range(1, int(missing_count) + 1):
                    gaps.append(timestamps[i - 1] + tf_ms * j)

        report.gap_count = len(gaps)
        report.gap_timestamps = gaps[:100]  # Cap at 100 for reporting

        logger.info(
            "coverage_checked",
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            total=report.total_candles,
            expected=report.expected_candles,
            coverage_pct=report.coverage_pct,
            gaps=report.gap_count,
            days=report.days_covered,
        )
        return report

    # ── Event Metadata Tagging ───────────────────────────────────────

    async def tag_event_week(
        self,
        session: AsyncSession,
        exchange: str,
        symbol: str,
        timeframe: str,
        start_ts: int,
        end_ts: int,
        macro_event_type: str,
    ) -> int:
        """Tag candles in a time range as event-week candles.

        Args:
            start_ts: Start of event window (Unix ms).
            end_ts: End of event window (Unix ms).
            macro_event_type: Event type (FOMC, CPI, NFP, HALVING, etc.)

        Returns:
            Number of rows updated.
        """
        stmt = (
            update(OhlcvHistory)
            .where(OhlcvHistory.exchange == exchange)
            .where(OhlcvHistory.symbol == symbol)
            .where(OhlcvHistory.timeframe == timeframe)
            .where(OhlcvHistory.open_time >= start_ts)
            .where(OhlcvHistory.open_time <= end_ts)
            .values(
                event_week_flag=True,
                macro_event_type=macro_event_type,
            )
        )
        result = await session.execute(stmt)
        await session.flush()

        updated: int = result.rowcount or 0
        logger.info(
            "event_week_tagged",
            exchange=exchange,
            symbol=symbol,
            event_type=macro_event_type,
            candles_tagged=updated,
        )
        return updated

    async def tag_high_volatility(
        self,
        session: AsyncSession,
        exchange: str,
        symbol: str,
        timeframe: str,
        timestamps: list[int],
    ) -> int:
        """Tag specific candles as high-volatility.

        Args:
            timestamps: List of open_time values to tag.

        Returns:
            Number of rows updated.
        """
        if not timestamps:
            return 0

        stmt = (
            update(OhlcvHistory)
            .where(OhlcvHistory.exchange == exchange)
            .where(OhlcvHistory.symbol == symbol)
            .where(OhlcvHistory.timeframe == timeframe)
            .where(OhlcvHistory.open_time.in_(timestamps))
            .values(high_volatility_flag=True)
        )
        result = await session.execute(stmt)
        await session.flush()

        updated: int = result.rowcount or 0
        logger.info(
            "high_volatility_tagged",
            exchange=exchange,
            symbol=symbol,
            candles_tagged=updated,
        )
        return updated

    # ── Utility ──────────────────────────────────────────────────────

    async def list_symbols(
        self,
        session: AsyncSession,
        exchange: str | None = None,
    ) -> list[dict[str, Any]]:
        """List all stored (exchange, symbol, timeframe) combinations with counts.

        Returns:
            List of {"exchange", "symbol", "timeframe", "count", "first_ts", "last_ts"}.
        """
        stmt = select(
            OhlcvHistory.exchange,
            OhlcvHistory.symbol,
            OhlcvHistory.timeframe,
            func.count().label("count"),
            func.min(OhlcvHistory.open_time).label("first_ts"),
            func.max(OhlcvHistory.open_time).label("last_ts"),
        ).group_by(
            OhlcvHistory.exchange,
            OhlcvHistory.symbol,
            OhlcvHistory.timeframe,
        )
        if exchange is not None:
            stmt = stmt.where(OhlcvHistory.exchange == exchange)

        rows = (await session.execute(stmt)).all()
        return [
            {
                "exchange": r[0],
                "symbol": r[1],
                "timeframe": r[2],
                "count": r[3],
                "first_ts": r[4],
                "last_ts": r[5],
            }
            for r in rows
        ]

    async def delete_symbol_data(
        self,
        session: AsyncSession,
        exchange: str,
        symbol: str,
        timeframe: str | None = None,
    ) -> int:
        """Delete all stored candles for a symbol (cleanup/re-ingestion).

        Returns:
            Number of rows deleted.
        """
        stmt = (
            delete(OhlcvHistory)
            .where(OhlcvHistory.exchange == exchange)
            .where(OhlcvHistory.symbol == symbol)
        )
        if timeframe is not None:
            stmt = stmt.where(OhlcvHistory.timeframe == timeframe)

        result = await session.execute(stmt)
        await session.flush()

        deleted: int = result.rowcount or 0
        logger.info(
            "symbol_data_deleted",
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe or "all",
            rows_deleted=deleted,
        )
        return deleted
