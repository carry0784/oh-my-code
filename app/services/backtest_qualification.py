"""Backtest Qualification Engine — 7-check minimal qualification.

Phase 4A of CR-048.

Evaluates a strategy×symbol×timeframe combination through 7 sequential checks:
  1. Data Compatibility — asset class and timeframe match
  2. Warmup Sufficiency — enough warmup bars for indicators
  3. Leakage / Causality Guard — no future data contamination
  4. Data Quality — missing data, timestamp order, duplicates
  5. Minimum Bars — enough data for meaningful evaluation
  6. Basic Performance — Sharpe >= 0, drawdown within bounds
  7. Cost-Adjusted Sanity — still profitable after fees/slippage

Each check returns pass/fail + a disqualify reason.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.models.qualification import (
    QualificationStatus,
    DisqualifyReason,
)

logger = logging.getLogger(__name__)


# ── Qualification Input Contract ─────────────────────────────────────


@dataclass
class QualificationInput:
    """Input contract for the 7-check qualification engine.

    Represents the dataset and metrics from a completed backtest run.
    """

    # Identity
    strategy_id: str = ""
    symbol: str = ""
    timeframe: str = "1h"

    # Strategy metadata
    strategy_asset_classes: list[str] | None = None  # allowed asset classes
    strategy_timeframes: list[str] | None = None  # allowed timeframes
    symbol_asset_class: str = "crypto"

    # Dataset
    dataset_fingerprint: str | None = None
    total_bars: int = 0
    warmup_bars_required: int = 200  # typical for 200MA
    warmup_bars_available: int = 0
    date_range_start: datetime | None = None
    date_range_end: datetime | None = None

    # Data quality
    missing_data_pct: float = 0.0
    has_timestamp_disorder: bool = False
    duplicate_bar_count: int = 0

    # Leakage indicators
    has_future_data_leak: bool = False
    has_lookahead_bias: bool = False

    # Performance metrics (from backtest)
    sharpe_ratio: float | None = None
    max_drawdown_pct: float | None = None  # as positive pct, e.g. 15.0 = 15% DD
    total_return_pct: float | None = None

    # Cost-adjusted metrics
    sharpe_after_costs: float | None = None
    return_after_costs_pct: float | None = None
    turnover_annual: float | None = None  # annualized turnover ratio


# ── Qualification Thresholds ─────────────────────────────────────────


@dataclass(frozen=True)
class QualificationThresholds:
    """Configurable thresholds for qualification checks."""

    # Check 4: Data quality
    max_missing_data_pct: float = 5.0
    max_duplicate_bars: int = 0

    # Check 5: Min bars
    min_bars: int = 500

    # Check 6: Performance
    min_sharpe: float = 0.0
    max_drawdown_pct: float = 50.0  # 50% max DD

    # Check 7: Cost sanity
    min_sharpe_after_costs: float = -0.5  # lenient — just checking not destroyed
    max_turnover_annual: float = 365.0  # max 1 trade/day equivalent


# ── Check Results ────────────────────────────────────────────────────


@dataclass
class CheckResult:
    """Result of a single qualification check."""

    check_name: str
    passed: bool
    reason: DisqualifyReason | None = None


@dataclass
class QualificationOutput:
    """Complete qualification result for one strategy×symbol evaluation."""

    strategy_id: str = ""
    symbol: str = ""
    timeframe: str = ""
    checks: list[CheckResult] = field(default_factory=list)
    all_passed: bool = False
    qualification_status: QualificationStatus = QualificationStatus.FAIL
    disqualify_reason: DisqualifyReason | None = None
    metrics_snapshot: dict | None = None


# ── Qualification Engine ─────────────────────────────────────────────


class BacktestQualifier:
    """7-check qualification engine.

    Stateless — all state is in input/output.
    Each check is a separate method for testability.
    """

    def __init__(
        self,
        thresholds: QualificationThresholds | None = None,
    ) -> None:
        self.t = thresholds or QualificationThresholds()

    def qualify(self, inp: QualificationInput) -> QualificationOutput:
        """Run all 7 checks. Return aggregate result."""

        output = QualificationOutput(
            strategy_id=inp.strategy_id,
            symbol=inp.symbol,
            timeframe=inp.timeframe,
        )

        checks = [
            self._check1_data_compat(inp),
            self._check2_warmup(inp),
            self._check3_leakage(inp),
            self._check4_data_quality(inp),
            self._check5_min_bars(inp),
            self._check6_performance(inp),
            self._check7_cost_sanity(inp),
        ]
        output.checks = checks

        # Build metrics snapshot
        output.metrics_snapshot = {
            "total_bars": inp.total_bars,
            "missing_data_pct": inp.missing_data_pct,
            "sharpe_ratio": inp.sharpe_ratio,
            "max_drawdown_pct": inp.max_drawdown_pct,
            "total_return_pct": inp.total_return_pct,
            "sharpe_after_costs": inp.sharpe_after_costs,
            "return_after_costs_pct": inp.return_after_costs_pct,
            "turnover_annual": inp.turnover_annual,
        }

        if all(c.passed for c in checks):
            output.all_passed = True
            output.qualification_status = QualificationStatus.PASS
        else:
            first_fail = next(c for c in checks if not c.passed)
            output.qualification_status = QualificationStatus.FAIL
            output.disqualify_reason = first_fail.reason

        return output

    # ── Individual Checks ────────────────────────────────────────────

    def _check1_data_compat(self, inp: QualificationInput) -> CheckResult:
        """Check 1: Data compatibility — asset class + timeframe match."""

        # Asset class compatibility
        if inp.strategy_asset_classes is not None:
            if inp.symbol_asset_class not in inp.strategy_asset_classes:
                return CheckResult(
                    "data_compat",
                    False,
                    DisqualifyReason.INCOMPATIBLE_ASSET_CLASS,
                )

        # Timeframe compatibility
        if inp.strategy_timeframes is not None:
            if inp.timeframe not in inp.strategy_timeframes:
                return CheckResult(
                    "data_compat",
                    False,
                    DisqualifyReason.INCOMPATIBLE_TIMEFRAME,
                )

        return CheckResult("data_compat", True)

    def _check2_warmup(self, inp: QualificationInput) -> CheckResult:
        """Check 2: Warmup sufficiency."""

        if inp.warmup_bars_available < inp.warmup_bars_required:
            return CheckResult(
                "warmup",
                False,
                DisqualifyReason.INSUFFICIENT_WARMUP,
            )

        return CheckResult("warmup", True)

    def _check3_leakage(self, inp: QualificationInput) -> CheckResult:
        """Check 3: Causality / leakage guard."""

        if inp.has_future_data_leak:
            return CheckResult(
                "leakage",
                False,
                DisqualifyReason.FUTURE_DATA_LEAK,
            )

        if inp.has_lookahead_bias:
            return CheckResult(
                "leakage",
                False,
                DisqualifyReason.LOOKAHEAD_BIAS,
            )

        return CheckResult("leakage", True)

    def _check4_data_quality(self, inp: QualificationInput) -> CheckResult:
        """Check 4: Data quality — missing data, ordering, duplicates."""

        if inp.missing_data_pct > self.t.max_missing_data_pct:
            return CheckResult(
                "data_quality",
                False,
                DisqualifyReason.MISSING_DATA_EXCESS,
            )

        if inp.has_timestamp_disorder:
            return CheckResult(
                "data_quality",
                False,
                DisqualifyReason.TIMESTAMP_DISORDER,
            )

        if inp.duplicate_bar_count > self.t.max_duplicate_bars:
            return CheckResult(
                "data_quality",
                False,
                DisqualifyReason.DUPLICATE_BARS,
            )

        return CheckResult("data_quality", True)

    def _check5_min_bars(self, inp: QualificationInput) -> CheckResult:
        """Check 5: Minimum bars requirement."""

        if inp.total_bars < self.t.min_bars:
            return CheckResult(
                "min_bars",
                False,
                DisqualifyReason.INSUFFICIENT_BARS,
            )

        return CheckResult("min_bars", True)

    def _check6_performance(self, inp: QualificationInput) -> CheckResult:
        """Check 6: Basic performance — Sharpe and drawdown."""

        if inp.sharpe_ratio is None:
            return CheckResult(
                "performance",
                False,
                DisqualifyReason.NEGATIVE_SHARPE,
            )

        if inp.sharpe_ratio < self.t.min_sharpe:
            return CheckResult(
                "performance",
                False,
                DisqualifyReason.NEGATIVE_SHARPE,
            )

        if inp.max_drawdown_pct is not None and inp.max_drawdown_pct > self.t.max_drawdown_pct:
            return CheckResult(
                "performance",
                False,
                DisqualifyReason.EXCESSIVE_DRAWDOWN,
            )

        return CheckResult("performance", True)

    def _check7_cost_sanity(self, inp: QualificationInput) -> CheckResult:
        """Check 7: Cost-adjusted sanity — still viable after fees."""

        if inp.sharpe_after_costs is not None:
            if inp.sharpe_after_costs < self.t.min_sharpe_after_costs:
                return CheckResult(
                    "cost_sanity",
                    False,
                    DisqualifyReason.NEGATIVE_AFTER_COSTS,
                )

        if inp.turnover_annual is not None:
            if inp.turnover_annual > self.t.max_turnover_annual:
                return CheckResult(
                    "cost_sanity",
                    False,
                    DisqualifyReason.EXCESSIVE_TURNOVER,
                )

        return CheckResult("cost_sanity", True)
