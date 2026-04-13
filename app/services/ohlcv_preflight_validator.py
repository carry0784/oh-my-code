"""
OhlcvPreflightValidator — Phase A (400-Day Backtest Data Plane)

Preflight data quality gate that runs BEFORE Phase A backtest execution.
Enforces symbol lock, timeframe lock, coverage threshold, duplicate detection,
gap tolerance, and hourly timestamp alignment.

Design constraints:
  - Fail-closed: any single check failure results in passed=False
  - All checks always run (no short-circuit on first failure — collect all reasons)
  - Read-only: no writes to DB; pure validation
  - HistoryDataManager imported lazily inside methods to avoid circular imports
  - Reproducibility: SHA-256 hash of (first_ts, last_ts, candle_count) recorded
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.ohlcv_history import OhlcvHistory

logger = get_logger(__name__)


# ── Data Contract ─────────────────────────────────────────────────────────────


@dataclass
class PreflightResult:
    """Result of a full OHLCV preflight validation run."""

    passed: bool = False
    symbol: str = ""
    exchange: str = ""
    timeframe: str = ""
    candle_count: int = 0
    coverage_pct: float = 0.0
    gap_count: int = 0
    duplicate_count: int = 0
    misaligned_count: int = 0  # timestamps not on exact hourly boundary
    first_ts: int = 0
    last_ts: int = 0
    days_covered: float = 0.0
    data_hash: str = ""
    checks: dict[str, bool] = field(default_factory=dict)   # per-check pass/fail
    failure_reasons: list[str] = field(default_factory=list)


# ── Validator ─────────────────────────────────────────────────────────────────


class OhlcvPreflightValidator:
    """Run all Phase A preflight checks against the ohlcv_history table.

    Usage::

        validator = OhlcvPreflightValidator()
        result = await validator.run(session, exchange="binance",
                                     symbol="SOL/USDT", timeframe="1h")
        if not result.passed:
            raise RuntimeError(result.failure_reasons)
    """

    # ── Constants ─────────────────────────────────────────────────────
    ALLOWED_SYMBOL = "SOL/USDT"
    ALLOWED_TIMEFRAME = "1h"
    MIN_COVERAGE_PCT = 95.0
    MIN_CANDLES = 9600        # 400 days × 24 hours
    MAX_GAP_COUNT = 48        # 2 days' worth of 1h gaps max
    HOURLY_MS = 3_600_000     # milliseconds per hour — alignment divisor

    # ── Public Entry Point ────────────────────────────────────────────

    async def run(
        self,
        session: AsyncSession,
        exchange: str = "binance",
        symbol: str = "SOL/USDT",
        timeframe: str = "1h",
    ) -> PreflightResult:
        """Run all preflight checks.

        All checks execute regardless of earlier failures so that every
        defect is surfaced in a single pass.  ``passed`` is True only when
        every individual check passes.

        Args:
            session:   Async DB session (caller manages transaction scope).
            exchange:  Exchange identifier (e.g. "binance").
            symbol:    Trading pair to validate.
            timeframe: Candle timeframe to validate.

        Returns:
            PreflightResult with per-check breakdown and failure reasons.
        """
        result = PreflightResult(
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
        )

        # ── Check 1: Symbol & timeframe lock ──────────────────────────
        sym_ok, sym_reason = await self._check_symbol_lock(symbol, timeframe)
        result.checks["symbol_lock"] = sym_ok
        if not sym_ok and sym_reason:
            result.failure_reasons.append(sym_reason)

        # ── Check 2: Coverage (candle count + coverage_pct + days) ────
        cov_ok, coverage_report, cov_reason = await self._check_coverage(
            session, exchange, symbol, timeframe
        )
        result.checks["coverage"] = cov_ok
        if coverage_report is not None:
            result.candle_count = coverage_report.total_candles
            result.coverage_pct = coverage_report.coverage_pct
            result.gap_count = coverage_report.gap_count
            result.first_ts = coverage_report.first_ts
            result.last_ts = coverage_report.last_ts
            result.days_covered = coverage_report.days_covered
        if not cov_ok and cov_reason:
            result.failure_reasons.append(cov_reason)

        # ── Check 3: Gap count ────────────────────────────────────────
        # gap_count is populated by check_coverage above; evaluate threshold here
        gap_ok = result.gap_count <= self.MAX_GAP_COUNT
        result.checks["gap_count"] = gap_ok
        if not gap_ok:
            result.failure_reasons.append(
                f"gap_count {result.gap_count} exceeds MAX_GAP_COUNT {self.MAX_GAP_COUNT}"
            )

        # ── Check 4: Duplicate open_time detection ────────────────────
        dup_ok, dup_count, dup_reason = await self._check_duplicates(
            session, exchange, symbol, timeframe
        )
        result.checks["no_duplicates"] = dup_ok
        result.duplicate_count = dup_count
        if not dup_ok and dup_reason:
            result.failure_reasons.append(dup_reason)

        # ── Check 5: Hourly timestamp alignment ───────────────────────
        align_ok, misaligned_count, align_reason = await self._check_timestamp_alignment(
            session, exchange, symbol, timeframe
        )
        result.checks["timestamp_alignment"] = align_ok
        result.misaligned_count = misaligned_count
        if not align_ok and align_reason:
            result.failure_reasons.append(align_reason)

        # ── Compute reproducibility hash (always, even on failure) ────
        result.data_hash = self._compute_data_hash(
            result.first_ts, result.last_ts, result.candle_count
        )

        # ── Final gate: all checks must pass ──────────────────────────
        result.passed = all(result.checks.values())

        # ── Structured summary log ────────────────────────────────────
        logger.info(
            "ohlcv_preflight_complete",
            passed=result.passed,
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            candle_count=result.candle_count,
            coverage_pct=result.coverage_pct,
            days_covered=result.days_covered,
            gap_count=result.gap_count,
            duplicate_count=result.duplicate_count,
            misaligned_count=result.misaligned_count,
            first_ts=result.first_ts,
            last_ts=result.last_ts,
            data_hash=result.data_hash,
            checks=result.checks,
            failure_reasons=result.failure_reasons,
        )

        return result

    # ── Individual Checks ─────────────────────────────────────────────

    async def _check_symbol_lock(
        self,
        symbol: str,
        timeframe: str,
    ) -> tuple[bool, str | None]:
        """Reject any symbol or timeframe other than the locked values.

        Returns:
            (passed, failure_reason_or_None)
        """
        reasons: list[str] = []

        if symbol != self.ALLOWED_SYMBOL:
            reasons.append(
                f"symbol_lock: got '{symbol}', only '{self.ALLOWED_SYMBOL}' allowed"
            )
        if timeframe != self.ALLOWED_TIMEFRAME:
            reasons.append(
                f"timeframe_lock: got '{timeframe}', only '{self.ALLOWED_TIMEFRAME}' allowed"
            )

        if reasons:
            return False, "; ".join(reasons)
        return True, None

    async def _check_coverage(
        self,
        session: AsyncSession,
        exchange: str,
        symbol: str,
        timeframe: str,
    ) -> tuple[bool, object | None, str | None]:
        """Verify minimum candle count and coverage percentage.

        Delegates gap detection to HistoryDataManager.check_coverage().

        Returns:
            (passed, CoverageReport_or_None, failure_reason_or_None)
        """
        # Lazy import to avoid circular dependency
        from app.services.history_data_manager import HistoryDataManager  # noqa: PLC0415

        manager = HistoryDataManager()
        report = await manager.check_coverage(session, exchange, symbol, timeframe)

        reasons: list[str] = []

        if report.total_candles < self.MIN_CANDLES:
            reasons.append(
                f"candle_count {report.total_candles} < MIN_CANDLES {self.MIN_CANDLES}"
            )

        if report.coverage_pct < self.MIN_COVERAGE_PCT:
            reasons.append(
                f"coverage_pct {report.coverage_pct:.2f}% < MIN_COVERAGE_PCT "
                f"{self.MIN_COVERAGE_PCT:.1f}%"
            )

        if reasons:
            return False, report, "; ".join(reasons)
        return True, report, None

    async def _check_duplicates(
        self,
        session: AsyncSession,
        exchange: str,
        symbol: str,
        timeframe: str,
    ) -> tuple[bool, int, str | None]:
        """Detect duplicate open_time values for the same (exchange, symbol, timeframe).

        SQL: SELECT open_time, COUNT(*) FROM ohlcv_history
             WHERE exchange=... AND symbol=... AND timeframe=...
             GROUP BY open_time HAVING COUNT(*) > 1

        Returns:
            (passed, duplicate_row_count, failure_reason_or_None)
        """
        stmt = (
            select(func.count())
            .select_from(
                select(OhlcvHistory.open_time)
                .where(OhlcvHistory.exchange == exchange)
                .where(OhlcvHistory.symbol == symbol)
                .where(OhlcvHistory.timeframe == timeframe)
                .group_by(OhlcvHistory.open_time)
                .having(func.count() > 1)
                .subquery()
            )
        )
        duplicate_group_count: int = (await session.execute(stmt)).scalar_one() or 0

        if duplicate_group_count > 0:
            return (
                False,
                duplicate_group_count,
                f"duplicate_open_time: {duplicate_group_count} open_time value(s) "
                f"appear more than once",
            )
        return True, 0, None

    async def _check_timestamp_alignment(
        self,
        session: AsyncSession,
        exchange: str,
        symbol: str,
        timeframe: str,
    ) -> tuple[bool, int, str | None]:
        """Verify all open_time values are on exact hourly boundaries (ms % 3600000 == 0).

        Any candle whose open_time is not evenly divisible by HOURLY_MS indicates
        timezone skew, data corruption, or a wrong-timeframe ingest.

        Returns:
            (passed, misaligned_count, failure_reason_or_None)
        """
        stmt = (
            select(func.count())
            .select_from(OhlcvHistory)
            .where(OhlcvHistory.exchange == exchange)
            .where(OhlcvHistory.symbol == symbol)
            .where(OhlcvHistory.timeframe == timeframe)
            .where((OhlcvHistory.open_time % self.HOURLY_MS) != 0)
        )
        misaligned_count: int = (await session.execute(stmt)).scalar_one() or 0

        if misaligned_count > 0:
            return (
                False,
                misaligned_count,
                f"timestamp_alignment: {misaligned_count} candle(s) have open_time "
                f"not divisible by {self.HOURLY_MS}ms (not on hourly boundary)",
            )
        return True, 0, None

    # ── Utility ───────────────────────────────────────────────────────

    def _compute_data_hash(
        self,
        first_ts: int,
        last_ts: int,
        candle_count: int,
    ) -> str:
        """SHA-256 hash of (first_ts, last_ts, candle_count) for reproducibility.

        The hash encodes the exact boundaries and size of the dataset so that
        two backtest runs using identical data produce identical hashes.

        Returns:
            Hex-encoded 64-character SHA-256 digest.
        """
        payload = f"{first_ts}:{last_ts}:{candle_count}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
