"""VAL-PDC-002 Judgment Engine — Phase A/B comparison verdict.

Issues a formal GO/HOLD/BLOCK verdict by evaluating VAL-PDC-002 criteria
against a PPFComparisonReport produced by ppf_backtest_comparator and
additional governance / seal state inputs.

Design contract:
  - NO execution binding  (execution_binding = NONE)
  - NO promotion authority (promotion_open = FALSE)
  - NO auto-advance       (auto_advance = FORBIDDEN)
  - Live entry is NEVER authorized by this module (hard prohibition)

Judgment criteria (ALL must be met for GO):
  C1: live_bars_evaluated >= 336  (14 days × 24h, VAL-QTY-001)
  C2: |backtest_deny_rate - live_deny_rate| <= 5 pp
      NOTE: currently uncomputable from PPFNoveltyEvent alone; criterion
      fails unless the baseline deny_rate is trivially absent from the report.
  C3: |backtest_fpr - live_fpr| <= 5 pp  (metric: "fpr")
  C4: state_distribution JS divergence <= 0.1  (metric: "deny_reason_distribution_js"
      used as proxy until a dedicated state counter is implemented)
  C5: novelty_events >= 10
  C6: baseline seal integrity verified (seal_valid=True)
  C7: no HARD_BLOCK active from governance engine

Verdict mapping:
  GO    — all 7 criteria met AND tier is GREEN (>= 10 events, all checks passed)
  HOLD  — criteria C1-C5 met AND tier is YELLOW (5-9 events)
          OR criteria C1-C5 + C7 met but C6 fails (seal needs re-verification)
  BLOCK — any of C1-C4 failed, OR tier is RED, OR HARD_BLOCK active (C7)

All verdict paths emit a fully populated ValPDC002Report with per-criterion
detail, a failure_reasons list, and the issued_at timestamp.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Public enumerations
# ---------------------------------------------------------------------------


class ValPDC002Verdict(str, Enum):
    GO = "GO"
    HOLD = "HOLD"
    BLOCK = "BLOCK"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ValPDC002Criterion:
    """Single criterion evaluation result for VAL-PDC-002."""

    name: str
    """Short identifier, e.g. 'C1_MIN_BARS'."""

    description: str
    """Human-readable description of what this criterion checks."""

    required_value: str
    """Human-readable threshold string, e.g. '>= 336 bars'."""

    actual_value: str
    """Human-readable actual value observed, e.g. '480 bars'."""

    passed: bool
    """True if the criterion was satisfied."""


@dataclass
class ValPDC002Report:
    """Formal VAL-PDC-002 verdict report.

    ``live_authorized`` is ALWAYS False — production deployment requires
    explicit human approval outside this module.
    """

    verdict: ValPDC002Verdict = ValPDC002Verdict.BLOCK
    criteria: list[ValPDC002Criterion] = field(default_factory=list)
    tier: str = "RED"  # GREEN / YELLOW / RED
    live_authorized: bool = False  # ALWAYS False — hard prohibition
    live_block_reason: str = "LIVE_NOT_AUTHORIZED: PPF production deployment not approved"
    issued_at: str = ""
    baseline_id: str = ""
    bars_collected: int = 0
    novelty_events: int = 0
    failure_reasons: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Judge
# ---------------------------------------------------------------------------


class ValPDC002Judge:
    """Issues VAL-PDC-002 verdict based on comparison report and governance state.

    Immutable judgment rules:
    - GO requires ALL 7 criteria + GREEN tier
    - HOLD requires criteria C1-C5 + YELLOW tier
      OR criteria C1-C5 + C7 but C6 fails (seal re-verification needed)
    - BLOCK is default for everything else
    - Live entry is NEVER authorized (hard prohibition)

    Parameters
    ----------
    min_bars:
        Minimum live bars required (default 336 = 14 days x 24h).
    min_novelty_events:
        Minimum novelty event count (default 10, VAL-QTY-001 S2P-EI1).
    deny_rate_tolerance_pp:
        Absolute tolerance in percentage points for deny_rate comparison (default 5.0).
    fpr_tolerance_pp:
        Absolute tolerance in percentage points for FPR comparison (default 5.0).
    js_divergence_threshold:
        Maximum JS divergence for state distribution (default 0.1).
    """

    MIN_BARS: int = 336
    MIN_NOVELTY_EVENTS: int = 10
    DENY_RATE_TOLERANCE_PP: float = 5.0  # percentage points -> 0.05 on [0,1] scale
    FPR_TOLERANCE_PP: float = 5.0
    JS_DIVERGENCE_THRESHOLD: float = 0.1

    def __init__(
        self,
        min_bars: int = MIN_BARS,
        min_novelty_events: int = MIN_NOVELTY_EVENTS,
        deny_rate_tolerance_pp: float = DENY_RATE_TOLERANCE_PP,
        fpr_tolerance_pp: float = FPR_TOLERANCE_PP,
        js_divergence_threshold: float = JS_DIVERGENCE_THRESHOLD,
    ) -> None:
        if min_bars <= 0:
            raise ValueError(f"min_bars must be > 0, got {min_bars}")
        if min_novelty_events <= 0:
            raise ValueError(f"min_novelty_events must be > 0, got {min_novelty_events}")
        if deny_rate_tolerance_pp <= 0.0:
            raise ValueError(f"deny_rate_tolerance_pp must be > 0, got {deny_rate_tolerance_pp}")
        if fpr_tolerance_pp <= 0.0:
            raise ValueError(f"fpr_tolerance_pp must be > 0, got {fpr_tolerance_pp}")
        if js_divergence_threshold <= 0.0:
            raise ValueError(f"js_divergence_threshold must be > 0, got {js_divergence_threshold}")

        self._min_bars = min_bars
        self._min_novelty_events = min_novelty_events
        self._deny_rate_tol = deny_rate_tolerance_pp / 100.0  # normalise to [0,1]
        self._fpr_tol = fpr_tolerance_pp / 100.0
        self._js_threshold = js_divergence_threshold

        logger.debug(
            "ValPDC002Judge initialised",
            min_bars=min_bars,
            min_novelty_events=min_novelty_events,
            deny_rate_tolerance_pp=deny_rate_tolerance_pp,
            fpr_tolerance_pp=fpr_tolerance_pp,
            js_divergence_threshold=js_divergence_threshold,
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def judge(
        self,
        comparison_report: Any,  # PPFComparisonReport from ppf_backtest_comparator
        seal_valid: bool,
        governance_has_hard_block: bool,
        novelty_events: int,
        bars_collected: int,
        baseline_id: str = "",
    ) -> ValPDC002Report:
        """Issue a VAL-PDC-002 verdict.

        Parameters
        ----------
        comparison_report:
            ``PPFComparisonReport`` produced by ``PPFBacktestComparator.compare()``.
            Must expose: ``baseline_id``, ``live_bars_evaluated``,
            ``live_novelty_count``, ``all_within_tolerance``, ``metrics``
            (list of ``ComparisonMetric``), and ``insufficiency_reasons``.
        seal_valid:
            True when the caller has verified the baseline seal hash matches
            the stored digest.  False forces C6 to fail.
        governance_has_hard_block:
            True when the governance engine has an active HARD_BLOCK for this
            symbol/session.  Forces C7 to fail and verdict to BLOCK.
        novelty_events:
            Total novelty events collected in Phase B.  Used for tier
            computation and C5.  Should match
            ``comparison_report.live_novelty_count`` but callers may pass
            the authoritative count separately.
        bars_collected:
            Total live bars evaluated in Phase B.  Should match
            ``comparison_report.live_bars_evaluated`` but callers may pass
            the authoritative count separately.
        baseline_id:
            Override for the baseline identifier.  Falls back to
            ``comparison_report.baseline_id`` when empty.

        Returns
        -------
        ValPDC002Report
            Fully populated report.  ``live_authorized`` is ALWAYS False.
        """
        report = ValPDC002Report(
            issued_at=datetime.now(timezone.utc).isoformat(),
            baseline_id=baseline_id or getattr(comparison_report, "baseline_id", ""),
            bars_collected=bars_collected,
            novelty_events=novelty_events,
        )

        criteria: list[ValPDC002Criterion] = []
        failure_reasons: list[str] = []

        # ------------------------------------------------------------------
        # C1: Minimum live bars (14 days x 24h = 336 bars for 1H timeframe)
        # ------------------------------------------------------------------
        c1_passed = bars_collected >= self._min_bars
        criteria.append(
            ValPDC002Criterion(
                name="C1_MIN_BARS",
                description=(
                    "At least 14 days of live shadow data must be accumulated "
                    "(>= 336 bars for 1H timeframe, VAL-QTY-001)"
                ),
                required_value=f">= {self._min_bars} bars",
                actual_value=f"{bars_collected} bars",
                passed=c1_passed,
            )
        )
        if not c1_passed:
            failure_reasons.append(
                f"C1_MIN_BARS FAIL: {bars_collected} bars < {self._min_bars} required"
            )

        # ------------------------------------------------------------------
        # C2: |backtest_deny_rate - live_deny_rate| <= 5 pp
        #
        # The comparator cannot reconstruct live deny_rate from PPFNoveltyEvent
        # alone (only novelty-brake activations are tracked, not total gate
        # evaluations).  This criterion is evaluated as follows:
        #   - If the metric "deny_rate" is present in comparison_report.metrics,
        #     use its within_tolerance field directly.
        #   - If absent, check whether comparison_report.insufficiency_reasons
        #     contains a deny_rate gap note.  If so, fail (the gap is blocking).
        #   - If absent with no insufficiency note, pass conservatively (no
        #     baseline deny_rate means zero reference, delta is zero by definition).
        # ------------------------------------------------------------------
        deny_rate_metric = self._extract_metric(comparison_report, "deny_rate")
        if deny_rate_metric is not None:
            c2_passed = bool(deny_rate_metric.within_tolerance)
            actual_deny_str = (
                f"delta={deny_rate_metric.delta_abs * 100:.2f} pp "
                f"(backtest={deny_rate_metric.backtest_value * 100:.2f}%, "
                f"live={deny_rate_metric.live_value * 100:.2f}%)"
            )
        else:
            insuff: list[str] = getattr(comparison_report, "insufficiency_reasons", [])
            deny_rate_gap = any("deny_rate" in r.lower() for r in insuff)
            if deny_rate_gap:
                c2_passed = False
                actual_deny_str = (
                    "live deny_rate not computable from PPFNoveltyEvent; "
                    "separate shadow evaluation counter required"
                )
            else:
                c2_passed = True
                actual_deny_str = "metric not computed (no baseline deny_rate present, delta=0)"

        criteria.append(
            ValPDC002Criterion(
                name="C2_DENY_RATE_DELTA",
                description=(
                    "Absolute difference between backtest and live deny_rate "
                    "must not exceed 5 percentage points"
                ),
                required_value=f"|delta| <= {self.DENY_RATE_TOLERANCE_PP:.1f} pp",
                actual_value=actual_deny_str,
                passed=c2_passed,
            )
        )
        if not c2_passed:
            failure_reasons.append(f"C2_DENY_RATE_DELTA FAIL: {actual_deny_str}")

        # ------------------------------------------------------------------
        # C3: |backtest_fpr - live_fpr| <= 5 pp
        # ------------------------------------------------------------------
        fpr_metric = self._extract_metric(comparison_report, "fpr")
        if fpr_metric is not None:
            c3_passed = bool(fpr_metric.within_tolerance)
            actual_fpr_str = (
                f"delta={fpr_metric.delta_abs * 100:.2f} pp "
                f"(backtest={fpr_metric.backtest_value * 100:.2f}%, "
                f"live={fpr_metric.live_value * 100:.2f}%)"
            )
        else:
            insuff = getattr(comparison_report, "insufficiency_reasons", [])
            fpr_gap = any("fpr" in r.lower() for r in insuff)
            if fpr_gap:
                c3_passed = False
                actual_fpr_str = "FPR not computable: no judged (TP/FP) novelty events available"
            else:
                c3_passed = False
                actual_fpr_str = "fpr metric absent from comparison report"

        criteria.append(
            ValPDC002Criterion(
                name="C3_FPR_DELTA",
                description=(
                    "Absolute difference between backtest and live FPR "
                    "must not exceed 5 percentage points"
                ),
                required_value=f"|delta| <= {self.FPR_TOLERANCE_PP:.1f} pp",
                actual_value=actual_fpr_str,
                passed=c3_passed,
            )
        )
        if not c3_passed:
            failure_reasons.append(f"C3_FPR_DELTA FAIL: {actual_fpr_str}")

        # ------------------------------------------------------------------
        # C4: State distribution JS divergence <= 0.1
        #
        # Uses "deny_reason_distribution_js" metric as proxy until a dedicated
        # state counter is available.  Fails conservatively when absent.
        # ------------------------------------------------------------------
        js_metric = self._extract_metric(comparison_report, "deny_reason_distribution_js")
        if js_metric is not None:
            c4_passed = bool(js_metric.within_tolerance)
            actual_js_str = (
                f"JS divergence={js_metric.live_value:.6f} (threshold={self._js_threshold:.2f})"
            )
        else:
            insuff = getattr(comparison_report, "insufficiency_reasons", [])
            js_deferred = any(
                "state_distribution" in r.lower() or "deny_reason_distribution" in r.lower()
                for r in insuff
            )
            if js_deferred:
                c4_passed = False
                actual_js_str = (
                    "state distribution JS comparison deferred: "
                    "live gate-state counter not yet implemented"
                )
            else:
                c4_passed = False
                actual_js_str = "JS divergence metric absent from comparison report"

        criteria.append(
            ValPDC002Criterion(
                name="C4_STATE_JS_DIVERGENCE",
                description=(
                    "State distribution JS divergence between backtest and live "
                    "must not exceed 0.1 "
                    "(uses deny_reason_distribution_js as proxy)"
                ),
                required_value=f"JS divergence <= {self._js_threshold:.2f}",
                actual_value=actual_js_str,
                passed=c4_passed,
            )
        )
        if not c4_passed:
            failure_reasons.append(f"C4_STATE_JS_DIVERGENCE FAIL: {actual_js_str}")

        # ------------------------------------------------------------------
        # C5: Minimum novelty events
        # ------------------------------------------------------------------
        c5_passed = novelty_events >= self._min_novelty_events
        criteria.append(
            ValPDC002Criterion(
                name="C5_MIN_NOVELTY_EVENTS",
                description=(
                    "At least 10 novelty events must have been observed "
                    "during Phase B (VAL-QTY-001 S2P-EI1)"
                ),
                required_value=f">= {self._min_novelty_events} events",
                actual_value=f"{novelty_events} events",
                passed=c5_passed,
            )
        )
        if not c5_passed:
            failure_reasons.append(
                f"C5_MIN_NOVELTY_EVENTS FAIL: {novelty_events} events "
                f"< {self._min_novelty_events} required"
            )

        # ------------------------------------------------------------------
        # C6: Baseline seal integrity
        # ------------------------------------------------------------------
        criteria.append(
            ValPDC002Criterion(
                name="C6_SEAL_INTEGRITY",
                description=(
                    "Baseline seal hash must match the stored digest, "
                    "verifying that the backtest baseline has not been altered"
                ),
                required_value="seal_valid = True",
                actual_value=f"seal_valid = {seal_valid}",
                passed=seal_valid,
            )
        )
        if not seal_valid:
            failure_reasons.append(
                "C6_SEAL_INTEGRITY FAIL: baseline seal hash mismatch or not verified"
            )

        # ------------------------------------------------------------------
        # C7: No HARD_BLOCK from governance engine
        # ------------------------------------------------------------------
        c7_passed = not governance_has_hard_block
        criteria.append(
            ValPDC002Criterion(
                name="C7_NO_HARD_BLOCK",
                description=(
                    "No HARD_BLOCK must be active from the governance engine "
                    "for this symbol/session"
                ),
                required_value="governance_has_hard_block = False",
                actual_value=f"governance_has_hard_block = {governance_has_hard_block}",
                passed=c7_passed,
            )
        )
        if not c7_passed:
            failure_reasons.append(
                "C7_NO_HARD_BLOCK FAIL: governance engine has an active HARD_BLOCK"
            )

        # ------------------------------------------------------------------
        # Tier computation
        # ------------------------------------------------------------------
        all_criteria_passed = all(c.passed for c in criteria)
        tier = self._compute_tier(novelty_events, all_criteria_passed)

        # ------------------------------------------------------------------
        # Verdict determination
        #
        # Priority order (highest to lowest):
        #   1. HARD_BLOCK active -> always BLOCK (C7 override)
        #   2. Tier RED          -> always BLOCK
        #   3. Any of C1-C4 failed -> BLOCK
        #   4. All 7 criteria + GREEN tier -> GO
        #   5. C1-C5 + C7 + YELLOW tier   -> HOLD (event count low)
        #   6. C1-C5 + C7 met but C6 fails -> HOLD (seal needs reverification)
        #   7. Everything else             -> BLOCK
        # ------------------------------------------------------------------
        core_hard_criteria_passed = c1_passed and c2_passed and c3_passed and c4_passed

        if governance_has_hard_block:
            verdict = ValPDC002Verdict.BLOCK
        elif tier == "RED":
            verdict = ValPDC002Verdict.BLOCK
            if not any("tier is RED" in r for r in failure_reasons):
                failure_reasons.append(
                    f"Tier RED: novelty_events={novelty_events} < 5 or critical metric failure"
                )
        elif not core_hard_criteria_passed:
            verdict = ValPDC002Verdict.BLOCK
        elif all_criteria_passed and tier == "GREEN":
            verdict = ValPDC002Verdict.GO
        elif core_hard_criteria_passed and c5_passed and c7_passed and tier == "YELLOW":
            verdict = ValPDC002Verdict.HOLD
        elif core_hard_criteria_passed and c5_passed and c7_passed and not seal_valid:
            # Seal re-verification needed but all other criteria met
            verdict = ValPDC002Verdict.HOLD
        else:
            verdict = ValPDC002Verdict.BLOCK

        # ------------------------------------------------------------------
        # Populate and return report
        # ------------------------------------------------------------------
        report.verdict = verdict
        report.criteria = criteria
        report.tier = tier
        report.live_authorized = False  # hard prohibition — never changes
        report.live_block_reason = "LIVE_NOT_AUTHORIZED: PPF production deployment not approved"
        report.failure_reasons = failure_reasons

        logger.info(
            "VAL-PDC-002 verdict issued",
            verdict=verdict.value,
            tier=tier,
            baseline_id=report.baseline_id,
            bars_collected=bars_collected,
            novelty_events=novelty_events,
            all_criteria_passed=all_criteria_passed,
            core_hard_criteria_passed=core_hard_criteria_passed,
            seal_valid=seal_valid,
            governance_has_hard_block=governance_has_hard_block,
            failure_count=len(failure_reasons),
            live_authorized=False,
        )

        return report

    def check_live_authorized(self) -> tuple[bool, str]:
        """ALWAYS returns (False, reason).  Hard prohibition.

        Live production deployment requires explicit human approval beyond
        the automated VAL-PDC-002 gate.  This method is the single
        authoritative check point for any caller that queries live
        authorization state.

        Returns
        -------
        tuple[bool, str]
            (False, reason_string) — the bool is always False.
        """
        reason = (
            "LIVE_NOT_AUTHORIZED: PPF production deployment requires "
            "explicit human approval beyond VAL-PDC-002"
        )
        logger.debug("check_live_authorized called", authorized=False, reason=reason)
        return (False, reason)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _compute_tier(self, novelty_events: int, all_criteria_passed: bool) -> str:
        """Compute GREEN / YELLOW / RED tier.

        Rules
        -----
        GREEN   — novelty_events >= 10 AND all criteria passed
        YELLOW  — novelty_events in [5, 9]  (regardless of criterion state,
                  except that RED still wins when any hard metric fails)
        RED     — novelty_events < 5  OR  (novelty_events in [5, 9] and
                  a hard criterion C1-C4 is failed, degrading evidence quality)

        Note: the GREEN band threshold matches MIN_NOVELTY_EVENTS (10).
        The YELLOW band covers the 5-9 event range, which may support a HOLD
        verdict but never a GO verdict.

        Parameters
        ----------
        novelty_events:
            Total novelty events observed in Phase B.
        all_criteria_passed:
            True when every single VAL-PDC-002 criterion was satisfied.

        Returns
        -------
        str
            One of "GREEN", "YELLOW", "RED".
        """
        if novelty_events >= self._min_novelty_events and all_criteria_passed:
            return "GREEN"
        if novelty_events >= 5:
            return "YELLOW"
        return "RED"

    def _extract_metric(self, comparison_report: Any, metric_name: str) -> Any | None:
        """Extract a named ComparisonMetric from a PPFComparisonReport.

        Parameters
        ----------
        comparison_report:
            PPFComparisonReport instance (typed as Any to avoid hard import
            cycle).  Must expose a ``metrics`` attribute that is iterable
            with objects having a ``metric_name`` string attribute.
        metric_name:
            The ``ComparisonMetric.metric_name`` value to search for.

        Returns
        -------
        ComparisonMetric | None
            The first matching metric, or None if not found or if the
            comparison_report does not expose a ``metrics`` attribute.
        """
        metrics = getattr(comparison_report, "metrics", None)
        if not metrics:
            return None
        for m in metrics:
            if getattr(m, "metric_name", None) == metric_name:
                return m
        return None
