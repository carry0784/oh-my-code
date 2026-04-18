"""
IngestionHealthChecker — Card B-8
Health check and gap detection service for the 24-symbol ingestion pipeline.

Responsibilities:
  - Check last-record recency for each symbol across all 5 hypertables
  - Detect candle gaps in ohlcv_hyper for any symbol/timeframe
  - Provide aggregate collection statistics for dashboards and ops checks

Design constraints:
  - Read-only — no writes to any table
  - Uses raw SQL with text() for TimescaleDB-aware queries (time_bucket, etc.)
  - Single symbol failure in check_all() never aborts the rest
  - All async; AsyncSession injected by caller
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.services.symbol_universe import ALL_SYMBOLS

logger = get_logger(__name__)

# ── Staleness thresholds (minutes) ──────────────────────────────────

STALE_OHLCV_MINUTES = 10          # 1m candle — stale after 10 min gap
STALE_FUNDING_MINUTES = 480       # funding updates ~every 8h
STALE_OI_MINUTES = 60             # OI updates ~hourly
STALE_ORDERBOOK_MINUTES = 10      # orderbook snapshots ~5-min
STALE_SENTIMENT_MINUTES = 120     # sentiment updated ~hourly


# ── Data Contracts ───────────────────────────────────────────────────


@dataclass
class GapInfo:
    """One detected gap in OHLCV candle series."""

    symbol: str
    timeframe: str
    gap_start: datetime        # timestamp of last candle before the gap
    gap_end: datetime          # timestamp of first candle after the gap
    missing_candles: int       # estimated number of missing candles in gap


@dataclass
class SymbolHealth:
    """Health snapshot for one symbol across all 5 hypertables."""

    symbol: str

    # ohlcv_hyper
    ohlcv_last_time: datetime | None = None
    ohlcv_gap_minutes: float | None = None
    ohlcv_stale: bool = False

    # funding_rate_hyper
    funding_last_time: datetime | None = None
    funding_gap_minutes: float | None = None
    funding_stale: bool = False

    # open_interest_hyper
    oi_last_time: datetime | None = None
    oi_gap_minutes: float | None = None
    oi_stale: bool = False

    # orderbook_snapshot_hyper
    orderbook_last_time: datetime | None = None
    orderbook_gap_minutes: float | None = None
    orderbook_stale: bool = False

    # sentiment_hyper
    sentiment_last_time: datetime | None = None
    sentiment_gap_minutes: float | None = None
    sentiment_stale: bool = False

    # Overall flag: any table is stale
    any_stale: bool = False

    # Error message if the health check itself failed for this symbol
    check_error: str | None = None


@dataclass
class IngestionHealthReport:
    """Aggregate health report for all 24 symbols."""

    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    symbol_count: int = 0
    healthy_count: int = 0     # no stale tables
    stale_count: int = 0       # at least one stale table
    error_count: int = 0       # check itself errored
    symbols: list[SymbolHealth] = field(default_factory=list)

    # Convenience: stale symbols by table
    stale_ohlcv: list[str] = field(default_factory=list)
    stale_funding: list[str] = field(default_factory=list)
    stale_oi: list[str] = field(default_factory=list)
    stale_orderbook: list[str] = field(default_factory=list)
    stale_sentiment: list[str] = field(default_factory=list)


# ── Health Checker ───────────────────────────────────────────────────


class IngestionHealthChecker:
    """Monitors data collection health across all 24 symbols.

    All methods require an AsyncSession (injected, not created).
    All queries are read-only.
    """

    # ── Public API ────────────────────────────────────────────────────

    async def check_all(
        self,
        session: AsyncSession,
        symbols: list[str] | None = None,
    ) -> IngestionHealthReport:
        """Check health of all symbols across all 5 hypertables.

        For each symbol, queries the most recent row in each of:
          - ohlcv_hyper
          - funding_rate_hyper
          - open_interest_hyper
          - orderbook_snapshot_hyper
          - sentiment_hyper

        Flags symbols whose most recent record exceeds the per-table
        staleness threshold.

        Args:
            session: Async DB session.
            symbols: Override the symbol list. None → ALL_SYMBOLS.

        Returns:
            IngestionHealthReport with per-symbol SymbolHealth records.
        """
        target_symbols = symbols if symbols is not None else ALL_SYMBOLS
        report = IngestionHealthReport(symbol_count=len(target_symbols))

        for symbol in target_symbols:
            health = await self._check_symbol(session, symbol)
            report.symbols.append(health)

            if health.check_error:
                report.error_count += 1
            elif health.any_stale:
                report.stale_count += 1
                if health.ohlcv_stale:
                    report.stale_ohlcv.append(symbol)
                if health.funding_stale:
                    report.stale_funding.append(symbol)
                if health.oi_stale:
                    report.stale_oi.append(symbol)
                if health.orderbook_stale:
                    report.stale_orderbook.append(symbol)
                if health.sentiment_stale:
                    report.stale_sentiment.append(symbol)
            else:
                report.healthy_count += 1

        logger.info(
            "ingestion_health_check_complete",
            symbol_count=report.symbol_count,
            healthy=report.healthy_count,
            stale=report.stale_count,
            errors=report.error_count,
            stale_ohlcv_count=len(report.stale_ohlcv),
            stale_funding_count=len(report.stale_funding),
        )
        return report

    async def detect_gaps(
        self,
        session: AsyncSession,
        symbol: str,
        timeframe: str = "1m",
        lookback_hours: int = 24,
    ) -> list[GapInfo]:
        """Detect gaps in ohlcv_hyper OHLCV data for a symbol.

        A gap is defined as a missing candle within the expected cadence.
        Uses a lead/lag approach via SQL window functions to find consecutive
        pairs where the interval exceeds the timeframe period.

        Args:
            session: Async DB session.
            symbol: Trading pair to check.
            timeframe: Candle timeframe key (e.g. "1m", "1h").
            lookback_hours: How many hours of history to scan. Default 24.

        Returns:
            List of GapInfo, sorted by gap_start ascending.
            Empty list if no gaps found or symbol has no data.
        """
        from app.services.hyper_history_manager import TIMEFRAME_MS

        tf_ms = TIMEFRAME_MS.get(timeframe, 60_000)
        tf_seconds = tf_ms / 1000.0
        # Allow 50% slack to avoid false positives from fractional delays
        gap_threshold_seconds = tf_seconds * 1.5

        gaps: list[GapInfo] = []

        try:
            # Compute lookback bound as a concrete timestamp to avoid
            # PostgreSQL INTERVAL parameterization pitfalls.
            now_utc = datetime.now(timezone.utc)
            from datetime import timedelta
            since_dt = now_utc - timedelta(hours=lookback_hours)

            stmt = text(
                """
                WITH ordered AS (
                    SELECT
                        time,
                        LEAD(time) OVER (ORDER BY time) AS next_time
                    FROM ohlcv_hyper
                    WHERE symbol = :symbol
                      AND timeframe = :timeframe
                      AND time >= :since_dt
                    ORDER BY time
                )
                SELECT
                    time AS gap_start,
                    next_time AS gap_end,
                    EXTRACT(EPOCH FROM (next_time - time)) AS interval_seconds
                FROM ordered
                WHERE next_time IS NOT NULL
                  AND EXTRACT(EPOCH FROM (next_time - time)) > :threshold_seconds
                ORDER BY time
                """
            )

            rows = (
                await session.execute(
                    stmt,
                    {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "since_dt": since_dt,
                        "threshold_seconds": gap_threshold_seconds,
                    },
                )
            ).all()

            for row in rows:
                gap_start: datetime = row[0]
                gap_end: datetime = row[1]
                interval_sec: float = float(row[2])
                # Estimate missing candles: subtract the expected 1 candle
                missing = max(0, int(interval_sec / tf_seconds) - 1)
                gaps.append(
                    GapInfo(
                        symbol=symbol,
                        timeframe=timeframe,
                        gap_start=gap_start,
                        gap_end=gap_end,
                        missing_candles=missing,
                    )
                )

        except Exception as exc:
            logger.warning(
                "detect_gaps_error",
                symbol=symbol,
                timeframe=timeframe,
                lookback_hours=lookback_hours,
                error=str(exc),
            )

        logger.debug(
            "gaps_detected",
            symbol=symbol,
            timeframe=timeframe,
            lookback_hours=lookback_hours,
            gap_count=len(gaps),
        )
        return gaps

    async def get_collection_stats(self, session: AsyncSession) -> dict[str, Any]:
        """Get aggregate collection statistics across all hypertables.

        Returns counts, time ranges, and approximate row totals per table.
        Useful for dashboards and operational health reports.

        Args:
            session: Async DB session.

        Returns:
            Dict with per-table stats and a summary section.
        """
        stats: dict[str, Any] = {}

        tables = [
            ("ohlcv_hyper", True),            # has symbol column
            ("funding_rate_hyper", True),
            ("open_interest_hyper", True),
            ("orderbook_snapshot_hyper", True),
            ("sentiment_hyper", True),
        ]

        for table_name, has_symbol in tables:
            try:
                row_stmt = text(
                    f"""
                    SELECT
                        COUNT(*) AS total_rows,
                        MIN(time) AS first_time,
                        MAX(time) AS last_time,
                        COUNT(DISTINCT symbol) AS symbol_count
                    FROM {table_name}
                    """  # noqa: S608 — table names are hardcoded constants, not user input
                )
                row = (await session.execute(row_stmt)).one_or_none()

                if row:
                    last_time = row[2]
                    gap_minutes: float | None = None
                    if last_time is not None:
                        now_utc = datetime.now(timezone.utc)
                        last_aware = last_time
                        if last_aware.tzinfo is None:
                            last_aware = last_aware.replace(tzinfo=timezone.utc)
                        gap_minutes = round(
                            (now_utc - last_aware).total_seconds() / 60.0, 1
                        )

                    stats[table_name] = {
                        "total_rows": int(row[0]) if row[0] else 0,
                        "first_time": row[1].isoformat() if row[1] else None,
                        "last_time": row[2].isoformat() if row[2] else None,
                        "symbol_count": int(row[3]) if row[3] else 0,
                        "gap_from_now_minutes": gap_minutes,
                    }
                else:
                    stats[table_name] = {
                        "total_rows": 0,
                        "first_time": None,
                        "last_time": None,
                        "symbol_count": 0,
                        "gap_from_now_minutes": None,
                    }

            except Exception as exc:
                logger.warning(
                    "collection_stats_table_error",
                    table=table_name,
                    error=str(exc),
                )
                stats[table_name] = {"error": str(exc)}

        # Summary across all tables
        stats["summary"] = {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "universe_size": len(ALL_SYMBOLS),
            "tables_checked": len(tables),
            "tables_ok": sum(1 for v in stats.values() if "error" not in v),
        }

        logger.info(
            "collection_stats_complete",
            tables_checked=len(tables),
            ohlcv_rows=stats.get("ohlcv_hyper", {}).get("total_rows"),
        )
        return stats

    # ── Private helpers ───────────────────────────────────────────────

    async def _check_symbol(
        self,
        session: AsyncSession,
        symbol: str,
    ) -> SymbolHealth:
        """Check health of one symbol across all 5 hypertables."""
        health = SymbolHealth(symbol=symbol)

        try:
            now_utc = datetime.now(timezone.utc)

            # ohlcv_hyper — last row for this symbol
            ohlcv_time = await self._last_time(
                session, "ohlcv_hyper", symbol=symbol
            )
            health.ohlcv_last_time = ohlcv_time
            health.ohlcv_gap_minutes = _gap_minutes(ohlcv_time, now_utc)
            health.ohlcv_stale = _is_stale(
                health.ohlcv_gap_minutes, STALE_OHLCV_MINUTES
            )

            # funding_rate_hyper
            funding_time = await self._last_time(
                session, "funding_rate_hyper", symbol=symbol
            )
            health.funding_last_time = funding_time
            health.funding_gap_minutes = _gap_minutes(funding_time, now_utc)
            health.funding_stale = _is_stale(
                health.funding_gap_minutes, STALE_FUNDING_MINUTES
            )

            # open_interest_hyper
            oi_time = await self._last_time(
                session, "open_interest_hyper", symbol=symbol
            )
            health.oi_last_time = oi_time
            health.oi_gap_minutes = _gap_minutes(oi_time, now_utc)
            health.oi_stale = _is_stale(
                health.oi_gap_minutes, STALE_OI_MINUTES
            )

            # orderbook_snapshot_hyper
            ob_time = await self._last_time(
                session, "orderbook_snapshot_hyper", symbol=symbol
            )
            health.orderbook_last_time = ob_time
            health.orderbook_gap_minutes = _gap_minutes(ob_time, now_utc)
            health.orderbook_stale = _is_stale(
                health.orderbook_gap_minutes, STALE_ORDERBOOK_MINUTES
            )

            # sentiment_hyper — symbol may be NULL for global metrics;
            # we look for any row matching this symbol OR NULL
            sentiment_time = await self._last_time_sentiment(session, symbol)
            health.sentiment_last_time = sentiment_time
            health.sentiment_gap_minutes = _gap_minutes(sentiment_time, now_utc)
            health.sentiment_stale = _is_stale(
                health.sentiment_gap_minutes, STALE_SENTIMENT_MINUTES
            )

            health.any_stale = any(
                [
                    health.ohlcv_stale,
                    health.funding_stale,
                    health.oi_stale,
                    health.orderbook_stale,
                    health.sentiment_stale,
                ]
            )

        except Exception as exc:
            logger.warning(
                "symbol_health_check_error",
                symbol=symbol,
                error=str(exc),
            )
            health.check_error = str(exc)
            health.any_stale = False  # don't flag as stale when check itself failed

        return health

    async def _last_time(
        self,
        session: AsyncSession,
        table_name: str,
        symbol: str,
    ) -> datetime | None:
        """Return MAX(time) for a symbol from any hypertable."""
        try:
            stmt = text(
                f"SELECT MAX(time) FROM {table_name} WHERE symbol = :symbol"
                # noqa: S608 — table names are hardcoded constants, not user input
            )
            result = await session.execute(stmt, {"symbol": symbol})
            row = result.scalar_one_or_none()
            return row  # may be None if no rows
        except Exception as exc:
            logger.debug(
                "last_time_query_error",
                table=table_name,
                symbol=symbol,
                error=str(exc),
            )
            return None

    async def _last_time_sentiment(
        self,
        session: AsyncSession,
        symbol: str,
    ) -> datetime | None:
        """Return MAX(time) from sentiment_hyper for a symbol or global rows."""
        # Extract base asset from "BTC/USDT" → "BTC"
        base = symbol.split("/")[0] if "/" in symbol else symbol
        try:
            stmt = text(
                """
                SELECT MAX(time) FROM sentiment_hyper
                WHERE symbol = :symbol
                   OR symbol = :base
                   OR symbol IS NULL
                """
            )
            result = await session.execute(
                stmt, {"symbol": symbol, "base": base}
            )
            row = result.scalar_one_or_none()
            return row
        except Exception as exc:
            logger.debug(
                "last_time_sentiment_error",
                symbol=symbol,
                error=str(exc),
            )
            return None


# ── Module-level helpers ─────────────────────────────────────────────


def _gap_minutes(
    last_time: datetime | None,
    now_utc: datetime,
) -> float | None:
    """Compute minutes elapsed since last_time. Returns None if last_time is None."""
    if last_time is None:
        return None
    aware = last_time
    if aware.tzinfo is None:
        aware = aware.replace(tzinfo=timezone.utc)
    return round((now_utc - aware).total_seconds() / 60.0, 1)


def _is_stale(
    gap_minutes: float | None,
    threshold_minutes: float,
) -> bool:
    """Return True if gap_minutes exceeds threshold, or if there is no data (None)."""
    if gap_minutes is None:
        return True  # no data at all is considered stale
    return gap_minutes > threshold_minutes
