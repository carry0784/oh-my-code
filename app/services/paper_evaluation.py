"""Paper Evaluation Policy Engine — observation-based paper pass/fail.

Phase 4C of CR-048.

Evaluates whether a strategy×symbol×timeframe combination's paper
observations meet the criteria for PAPER_PASS.  Six evaluation rules:

  1. Minimum Observation Count — enough observations recorded
  2. Cumulative Performance — aggregate return sanity
  3. Maximum Drawdown — drawdown within ceiling
  4. Turnover Ceiling — not over-trading
  5. Slippage Sensitivity — execution quality acceptable
  6. Observation Completeness — missing/invalid observations within tolerance

Each rule returns pass/fail + a reason code.
Stateless — all state is in input/output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# ── Evaluation Reason Codes ─────────────────────────────────────────


class PaperEvalReason(str, Enum):
    """Reason codes for paper evaluation failure.

    Separate from EligibilityBlockReason (Phase 4B) to keep
    eligibility (gate preconditions) and evaluation (observation quality)
    concerns distinct.
    """

    INSUFFICIENT_OBSERVATIONS = "insufficient_observations"
    NEGATIVE_CUMULATIVE_RETURN = "negative_cumulative_return"
    EXCESSIVE_DRAWDOWN = "excessive_drawdown"
    EXCESSIVE_TURNOVER = "excessive_turnover"
    EXCESSIVE_SLIPPAGE = "excessive_slippage"
    OBSERVATION_INCOMPLETE = "observation_incomplete"


class PaperEvalDecision(str, Enum):
    """Paper evaluation decision — separate from PromotionEligibility."""

    PENDING = "pending"  # not yet evaluated
    HOLD = "hold"  # observations insufficient or system guard
    PASS = "pass"
    FAIL = "fail"
    QUARANTINE = "quarantine"  # anomaly detected during evaluation


# ── Evaluation Thresholds ───────────────────────────────────────────


@dataclass(frozen=True)
class PaperEvalThresholds:
    """Configurable thresholds for paper evaluation rules."""

    # Rule 1: Minimum observations
    min_observation_count: int = 50

    # Rule 2: Cumulative performance
    min_cumulative_return_pct: float = -10.0  # allow small negative

    # Rule 3: Drawdown ceiling
    max_drawdown_pct: float = 30.0

    # Rule 4: Turnover ceiling
    max_turnover_annual: float = 365.0  # max ~1 trade/day

    # Rule 5: Slippage sensitivity
    max_slippage_pct: float = 2.0  # max 2% avg slippage

    # Rule 6: Observation completeness
    max_missing_observation_pct: float = 10.0  # max 10% missing


# ── Evaluation Input Contract ───────────────────────────────────────


@dataclass
class PaperEvalInput:
    """Input contract for the 6-rule paper evaluation engine.

    Represents aggregated metrics from observation history.
    """

    strategy_id: str = ""
    symbol: str = ""
    timeframe: str = ""

    # Observation stats
    total_observations: int = 0
    valid_observations: int = 0  # excluding skipped/invalid
    expected_observations: int = 0  # how many should have been recorded
    observation_window_fingerprint: str | None = None  # hash of eval window

    # Aggregated metrics from observations
    cumulative_return_pct: float | None = None
    max_drawdown_pct: float | None = None
    avg_turnover_annual: float | None = None
    avg_slippage_pct: float | None = None

    # System guards (now read from DB, not caller-injected)
    safe_mode_active: bool = False
    drift_active: bool = False

    # Source linkage
    source_qualification_result_id: str | None = None


# ── Rule Result ─────────────────────────────────────────────────────


@dataclass
class EvalRuleResult:
    """Result of a single evaluation rule."""

    rule_name: str
    passed: bool
    reason: PaperEvalReason | None = None


# ── Evaluation Output ───────────────────────────────────────────────


@dataclass
class PaperEvalOutput:
    """Complete evaluation result for one strategy×symbol paper window."""

    strategy_id: str = ""
    symbol: str = ""
    timeframe: str = ""
    rules: list[EvalRuleResult] = field(default_factory=list)
    all_passed: bool = False
    decision: PaperEvalDecision = PaperEvalDecision.FAIL
    failed_rules: list[str] = field(default_factory=list)
    primary_reason: PaperEvalReason | None = None
    observation_window_fingerprint: str | None = None
    metrics_summary: dict | None = None


# ── Paper Evaluation Engine ─────────────────────────────────────────


class PaperEvaluator:
    """6-rule paper evaluation engine.

    Stateless — all state is in input/output.
    Each rule is a separate method for testability.
    """

    def __init__(
        self,
        thresholds: PaperEvalThresholds | None = None,
    ) -> None:
        self.t = thresholds or PaperEvalThresholds()

    def evaluate(self, inp: PaperEvalInput) -> PaperEvalOutput:
        """Run all 6 rules plus system guards. Return aggregate result."""

        output = PaperEvalOutput(
            strategy_id=inp.strategy_id,
            symbol=inp.symbol,
            timeframe=inp.timeframe,
            observation_window_fingerprint=inp.observation_window_fingerprint,
        )

        # System guards first — if active, short-circuit to HOLD/QUARANTINE
        if inp.drift_active:
            output.decision = PaperEvalDecision.QUARANTINE
            output.primary_reason = None
            output.rules = []
            return output

        if inp.safe_mode_active:
            output.decision = PaperEvalDecision.HOLD
            output.primary_reason = None
            output.rules = []
            return output

        # Run 6 evaluation rules
        rules = [
            self._rule1_min_observations(inp),
            self._rule2_cumulative_performance(inp),
            self._rule3_max_drawdown(inp),
            self._rule4_turnover(inp),
            self._rule5_slippage(inp),
            self._rule6_completeness(inp),
        ]
        output.rules = rules

        # Build metrics summary
        output.metrics_summary = {
            "total_observations": inp.total_observations,
            "valid_observations": inp.valid_observations,
            "expected_observations": inp.expected_observations,
            "cumulative_return_pct": inp.cumulative_return_pct,
            "max_drawdown_pct": inp.max_drawdown_pct,
            "avg_turnover_annual": inp.avg_turnover_annual,
            "avg_slippage_pct": inp.avg_slippage_pct,
        }

        # Collect failed rules
        failed = [r for r in rules if not r.passed]
        output.failed_rules = [r.rule_name for r in failed]

        if not failed:
            output.all_passed = True
            output.decision = PaperEvalDecision.PASS
        elif rules[0].passed is False:
            # Insufficient observations → HOLD (not enough data yet)
            output.decision = PaperEvalDecision.HOLD
            output.primary_reason = failed[0].reason
        else:
            output.decision = PaperEvalDecision.FAIL
            output.primary_reason = failed[0].reason

        return output

    # ── Individual Rules ─────────────────────────────────────────────

    def _rule1_min_observations(self, inp: PaperEvalInput) -> EvalRuleResult:
        """Rule 1: Minimum observation count."""
        if inp.valid_observations < self.t.min_observation_count:
            return EvalRuleResult(
                "min_observations",
                False,
                PaperEvalReason.INSUFFICIENT_OBSERVATIONS,
            )
        return EvalRuleResult("min_observations", True)

    def _rule2_cumulative_performance(self, inp: PaperEvalInput) -> EvalRuleResult:
        """Rule 2: Cumulative return sanity."""
        if inp.cumulative_return_pct is None:
            return EvalRuleResult(
                "cumulative_performance",
                False,
                PaperEvalReason.NEGATIVE_CUMULATIVE_RETURN,
            )
        if inp.cumulative_return_pct < self.t.min_cumulative_return_pct:
            return EvalRuleResult(
                "cumulative_performance",
                False,
                PaperEvalReason.NEGATIVE_CUMULATIVE_RETURN,
            )
        return EvalRuleResult("cumulative_performance", True)

    def _rule3_max_drawdown(self, inp: PaperEvalInput) -> EvalRuleResult:
        """Rule 3: Max drawdown ceiling."""
        if inp.max_drawdown_pct is not None and inp.max_drawdown_pct > self.t.max_drawdown_pct:
            return EvalRuleResult(
                "max_drawdown",
                False,
                PaperEvalReason.EXCESSIVE_DRAWDOWN,
            )
        return EvalRuleResult("max_drawdown", True)

    def _rule4_turnover(self, inp: PaperEvalInput) -> EvalRuleResult:
        """Rule 4: Turnover ceiling."""
        if (
            inp.avg_turnover_annual is not None
            and inp.avg_turnover_annual > self.t.max_turnover_annual
        ):
            return EvalRuleResult(
                "turnover",
                False,
                PaperEvalReason.EXCESSIVE_TURNOVER,
            )
        return EvalRuleResult("turnover", True)

    def _rule5_slippage(self, inp: PaperEvalInput) -> EvalRuleResult:
        """Rule 5: Slippage sensitivity ceiling."""
        if inp.avg_slippage_pct is not None and inp.avg_slippage_pct > self.t.max_slippage_pct:
            return EvalRuleResult(
                "slippage",
                False,
                PaperEvalReason.EXCESSIVE_SLIPPAGE,
            )
        return EvalRuleResult("slippage", True)

    def _rule6_completeness(self, inp: PaperEvalInput) -> EvalRuleResult:
        """Rule 6: Observation completeness."""
        if inp.expected_observations > 0:
            missing_pct = (
                (inp.expected_observations - inp.valid_observations) / inp.expected_observations
            ) * 100.0
            if missing_pct > self.t.max_missing_observation_pct:
                return EvalRuleResult(
                    "completeness",
                    False,
                    PaperEvalReason.OBSERVATION_INCOMPLETE,
                )
        return EvalRuleResult("completeness", True)
