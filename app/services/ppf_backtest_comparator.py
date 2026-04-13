"""PPF Backtest Comparator — Phase B live vs backtest comparison engine.

Compares accumulated live shadow results against Phase A backtest baseline
to determine if PPF behavior in production matches backtested expectations.

Used for VAL-PDC-002 promotion decision.

Design contract:
  - NO execution binding  (execution_binding = NONE)
  - NO promotion authority (promotion_open = FALSE)
  - NO auto-advance       (auto_advance = FORBIDDEN)
  - Read-only with respect to DB; callers own persistence

Metric coverage:
  1. novelty_rate       — live novelty events / estimated total evals
  2. fpr                — FP / (TP + FP) from judged live events
  3. deny_reason_dist   — JS divergence between baseline deny_reason_distribution
                          and live deny_reason_code distribution (novelty events only)
  4. state_distribution — JS divergence between baseline state_distribution and live
                          (skipped when baseline field is absent; noted in report)

NOTE on deny_rate:
  PPFNoveltyEvent only records O9=True activations, not all gate evaluations.
  Therefore live deny_rate (deny_count / evaluated_bars) cannot be reconstructed
  from this table alone.  deny_rate comparison is explicitly omitted and its
  absence is recorded in insufficiency_reasons when the baseline deny_rate is
  non-trivial (> 0.01).

Minimum data requirements for VAL-PDC-002 eligibility:
  - live_bars_evaluated >= 336  (14 days × 24 hours, VAL-QTY-001)
  - live_novelty_count  >= 10   (VAL-QTY-001 S2P-EI1)
  - All computed metrics within tolerance
  - No unresolvable insufficiency reasons
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ComparisonMetric:
    """Single metric comparison result."""

    metric_name: str
    backtest_value: float
    live_value: float
    delta_abs: float
    """Absolute difference: |live - backtest|."""
    delta_pct: float
    """|live - backtest| / max(|backtest|, epsilon) * 100 — for display only."""
    within_tolerance: bool
    tolerance_pct: float
    """Configured tolerance as a percentage (e.g. 5.0 means ±5 pp for rates)."""


@dataclass
class PPFComparisonReport:
    """Phase B comparison report.

    val_pdc_002_eligible is True only when:
      - all computed metrics are within tolerance, AND
      - minimum data requirements are satisfied, AND
      - insufficiency_reasons is empty.
    """

    baseline_id: str = ""
    comparison_ts: str = ""
    live_bars_evaluated: int = 0
    live_novelty_count: int = 0
    live_days_elapsed: int = 0
    metrics: list[ComparisonMetric] = field(default_factory=list)
    all_within_tolerance: bool = False
    val_pdc_002_eligible: bool = False
    insufficiency_reasons: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Comparator
# ---------------------------------------------------------------------------


class PPFBacktestComparator:
    """Compares PPF backtest baseline against live shadow accumulation.

    Comparison metrics:
      1. novelty_rate: |backtest - live| <= tolerance_pct (as pp, not %)
      2. fpr:          |backtest - live| <= tolerance_pct (only if judged events exist)
      3. deny_reason_distribution JS divergence <= js_threshold
         (computed from novelty events' deny_reason_code vs baseline distribution)
      4. state_distribution JS divergence <= js_threshold
         (skipped with a note when baseline.state_distribution is absent)

    deny_rate is intentionally not compared — see module docstring for rationale.

    Minimum data requirements for comparison:
      - live_bars_evaluated >= 336 (14 days × 24h, VAL-QTY-001)
      - live_novelty_count >= 10 (VAL-QTY-001 S2P-EI1)

    All metrics must pass for val_pdc_002_eligible = True.

    Parameters
    ----------
    tolerance_pct:
        Absolute tolerance in percentage points for rate metrics.
        Default 5.0 means live rate must be within ±0.05 of backtest rate.
    js_threshold:
        Maximum allowable Jensen–Shannon divergence for distribution metrics.
        Default 0.1 (range 0–1, where 0 = identical distributions).
    """

    DEFAULT_TOLERANCE_PCT: float = 5.0
    DEFAULT_JS_THRESHOLD: float = 0.1
    MIN_LIVE_BARS: int = 336       # 14 days × 24h
    MIN_NOVELTY_EVENTS: int = 10   # VAL-QTY-001 S2P-EI1

    def __init__(
        self,
        tolerance_pct: float = DEFAULT_TOLERANCE_PCT,
        js_threshold: float = DEFAULT_JS_THRESHOLD,
    ) -> None:
        if tolerance_pct <= 0.0:
            raise ValueError(f"tolerance_pct must be > 0, got {tolerance_pct}")
        if js_threshold <= 0.0:
            raise ValueError(f"js_threshold must be > 0, got {js_threshold}")

        self._tolerance_pct = tolerance_pct
        self._js_threshold = js_threshold

        logger.debug(
            "PPFBacktestComparator initialised: tolerance_pct=%.2f, js_threshold=%.4f",
            self._tolerance_pct,
            self._js_threshold,
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def compare(
        self,
        session,  # AsyncSession — typed as Any to avoid hard import
        baseline_id: str,
    ) -> PPFComparisonReport:
        """Compare backtest baseline against accumulated live shadow results.

        Steps:
          1. Load PPFBacktestBaseline by baseline_id — bail if absent.
          2. Query PPFNoveltyEvent for the same symbol/exchange.
          3. Compute live metrics (novelty_rate, fpr, deny_reason distribution).
          4. Compare each metric against baseline using tolerance rules.
          5. Compare distribution fields via JS divergence where available.
          6. Evaluate minimum data requirements.
          7. Return fully populated PPFComparisonReport.

        Parameters
        ----------
        session:
            Active SQLAlchemy AsyncSession.  The caller owns transaction scope.
        baseline_id:
            UUID string (primary key) of the PPFBacktestBaseline row to compare
            against.

        Returns
        -------
        PPFComparisonReport
            val_pdc_002_eligible=True only when all conditions are satisfied.
        """
        from sqlalchemy import select  # local import — avoids circular at module load
        from app.models.ppf_backtest_baseline import PPFBacktestBaseline
        from app.models.ppf_novelty_event import PPFNoveltyEvent

        report = PPFComparisonReport(
            baseline_id=baseline_id,
            comparison_ts=datetime.now(timezone.utc).isoformat(),
        )

        # ------------------------------------------------------------------
        # Step 1 — Load baseline
        # ------------------------------------------------------------------
        baseline: Optional[PPFBacktestBaseline] = await session.get(
            PPFBacktestBaseline, baseline_id
        )
        if baseline is None:
            logger.warning(
                "compare: baseline_id=%r not found in ppf_backtest_baselines",
                baseline_id,
            )
            report.insufficiency_reasons.append(
                f"baseline {baseline_id!r} not found in ppf_backtest_baselines"
            )
            return report

        logger.info(
            "compare: loaded baseline id=%s symbol=%s exchange=%s "
            "evaluated_bars=%d novelty_rate=%.6f fpr=%.6f",
            baseline_id,
            baseline.symbol,
            baseline.exchange,
            baseline.evaluated_bars,
            baseline.novelty_rate,
            baseline.fpr,
        )

        # ------------------------------------------------------------------
        # Step 2 — Load live novelty events
        # ------------------------------------------------------------------
        stmt = (
            select(PPFNoveltyEvent)
            .where(
                PPFNoveltyEvent.symbol == baseline.symbol,
                PPFNoveltyEvent.exchange == baseline.exchange,
            )
            .order_by(PPFNoveltyEvent.event_ts)
        )
        result = await session.execute(stmt)
        events: list[PPFNoveltyEvent] = list(result.scalars().all())

        report.live_novelty_count = len(events)

        logger.info(
            "compare: found %d live novelty events for symbol=%s exchange=%s",
            len(events),
            baseline.symbol,
            baseline.exchange,
        )

        # ------------------------------------------------------------------
        # Step 3 — Derive live time window and bar estimate
        # ------------------------------------------------------------------
        if events:
            first_ts: datetime = min(e.event_ts for e in events)
            last_ts: datetime = max(e.event_ts for e in events)
            elapsed_days = max(1, (last_ts - first_ts).days)
        else:
            elapsed_days = 0

        report.live_days_elapsed = elapsed_days

        # Estimated total hourly evaluations; floored at 1 to avoid ZeroDivision.
        estimated_total_evals: int = max(elapsed_days * 24, 1)
        report.live_bars_evaluated = estimated_total_evals

        # ------------------------------------------------------------------
        # Step 4 — Compute live rates
        # ------------------------------------------------------------------
        live_novelty_rate: float = len(events) / estimated_total_evals

        judged = [e for e in events if e.judgment is not None]
        tp_count = sum(1 for e in judged if e.judgment == "TP")
        fp_count = sum(1 for e in judged if e.judgment == "FP")
        resolved_count = tp_count + fp_count

        live_fpr: float = fp_count / resolved_count if resolved_count > 0 else 0.0

        logger.debug(
            "compare: live_novelty_rate=%.6f live_fpr=%.6f "
            "tp=%d fp=%d resolved=%d",
            live_novelty_rate,
            live_fpr,
            tp_count,
            fp_count,
            resolved_count,
        )

        # ------------------------------------------------------------------
        # Step 5 — Metric comparisons
        # ------------------------------------------------------------------
        metrics: list[ComparisonMetric] = []

        # 5a. novelty_rate
        metrics.append(
            self._compare_metric("novelty_rate", baseline.novelty_rate, live_novelty_rate)
        )

        # 5b. fpr — only when we have judged events (avoid comparing against 0.0 default)
        if resolved_count > 0:
            metrics.append(self._compare_metric("fpr", baseline.fpr, live_fpr))
        else:
            report.insufficiency_reasons.append(
                "no judged (TP/FP) novelty events available for FPR comparison"
            )
            logger.info("compare: skipping fpr — no judged events")

        # 5c. deny_rate omission notice (non-blocking)
        # PPFNoveltyEvent only records novelty-brake activations, not all gate
        # evaluations.  Live deny_rate cannot be reconstructed.  Flag only if
        # the baseline deny_rate is material (> 1 %) so low-novelty baselines
        # do not generate spurious noise.
        if baseline.deny_rate > 0.01:
            report.insufficiency_reasons.append(
                f"deny_rate comparison unavailable: live deny_count not tracked in "
                f"PPFNoveltyEvent (baseline deny_rate={baseline.deny_rate:.4f}); "
                "requires a separate shadow evaluation counter"
            )
            logger.info(
                "compare: deny_rate omitted — baseline=%.4f, live source absent",
                baseline.deny_rate,
            )

        # 5d. deny_reason_distribution JS divergence
        if baseline.deny_reason_distribution:
            try:
                backtest_deny_dist: dict[str, float] = json.loads(
                    baseline.deny_reason_distribution
                )
                live_deny_dist = self._build_deny_reason_dist(events)
                js = self._js_divergence(backtest_deny_dist, live_deny_dist)
                within_js = js <= self._js_threshold
                metrics.append(
                    ComparisonMetric(
                        metric_name="deny_reason_distribution_js",
                        backtest_value=0.0,          # reference = 0 divergence
                        live_value=js,
                        delta_abs=js,
                        delta_pct=js * 100.0,
                        within_tolerance=within_js,
                        tolerance_pct=self._js_threshold * 100.0,
                    )
                )
                logger.debug(
                    "compare: deny_reason_distribution JS=%.6f within=%s",
                    js,
                    within_js,
                )
            except (json.JSONDecodeError, ValueError) as exc:
                logger.warning(
                    "compare: could not parse baseline.deny_reason_distribution: %s",
                    exc,
                )
                report.insufficiency_reasons.append(
                    f"baseline deny_reason_distribution JSON parse error: {exc}"
                )
        else:
            logger.debug(
                "compare: baseline deny_reason_distribution absent — skipping JS comparison"
            )

        # 5e. state_distribution JS divergence
        # Live state distribution is not available from PPFNoveltyEvent alone
        # (events only capture novelty-brake states, not full gate state counts).
        # This comparison is deferred; its absence is informational, not blocking.
        if baseline.state_distribution:
            report.insufficiency_reasons.append(
                "state_distribution JS comparison not available: "
                "live gate-state distribution requires a separate shadow state counter "
                "(PPFNoveltyEvent captures novelty-brake states only)"
            )
            logger.info(
                "compare: state_distribution comparison deferred — "
                "live state counter not yet implemented"
            )

        # ------------------------------------------------------------------
        # Step 6 — Minimum data requirements
        # ------------------------------------------------------------------
        if estimated_total_evals < self.MIN_LIVE_BARS:
            report.insufficiency_reasons.append(
                f"live_bars_evaluated={estimated_total_evals} < "
                f"minimum={self.MIN_LIVE_BARS} (14 days × 24h)"
            )
        if len(events) < self.MIN_NOVELTY_EVENTS:
            report.insufficiency_reasons.append(
                f"live_novelty_count={len(events)} < "
                f"minimum={self.MIN_NOVELTY_EVENTS} (VAL-QTY-001 S2P-EI1)"
            )

        # ------------------------------------------------------------------
        # Step 7 — Aggregate and return
        # ------------------------------------------------------------------
        report.metrics = metrics
        report.all_within_tolerance = bool(metrics) and all(
            m.within_tolerance for m in metrics
        )

        # val_pdc_002_eligible requires:
        #   - at least one metric computed
        #   - all computed metrics within tolerance
        #   - no unresolvable insufficiency reasons
        #
        # NOTE: deny_rate and state_distribution absence entries are recorded in
        #   insufficiency_reasons, so val_pdc_002_eligible will be False until those
        #   tracking gaps are closed.  This is intentional — the gate must be strict.
        report.val_pdc_002_eligible = (
            report.all_within_tolerance
            and len(report.insufficiency_reasons) == 0
        )

        logger.info(
            "compare: DONE baseline_id=%s live_bars=%d novelty=%d "
            "all_within_tolerance=%s eligible=%s reasons=%d",
            baseline_id,
            report.live_bars_evaluated,
            report.live_novelty_count,
            report.all_within_tolerance,
            report.val_pdc_002_eligible,
            len(report.insufficiency_reasons),
        )

        return report

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _compare_metric(
        self, name: str, backtest: float, live: float
    ) -> ComparisonMetric:
        """Compare a single rate metric against the configured tolerance.

        Tolerance is applied as an absolute threshold on the rate scale [0, 1].
        A tolerance_pct of 5.0 means |live - backtest| must be <= 0.05.

        Parameters
        ----------
        name:
            Human-readable metric identifier (used in ComparisonMetric.metric_name).
        backtest:
            Rate value from the sealed backtest baseline.
        live:
            Rate value computed from live shadow data.

        Returns
        -------
        ComparisonMetric
            Immutable result record.
        """
        delta_abs = abs(live - backtest)
        epsilon = 1e-9
        delta_pct = delta_abs / max(abs(backtest), epsilon) * 100.0
        # Absolute tolerance: tolerance_pct is in percentage points (e.g. 5.0 → 0.05)
        within = delta_abs <= (self._tolerance_pct / 100.0)

        logger.debug(
            "_compare_metric: %s backtest=%.6f live=%.6f delta_abs=%.6f "
            "delta_pct=%.2f%% within=%s",
            name,
            backtest,
            live,
            delta_abs,
            delta_pct,
            within,
        )

        return ComparisonMetric(
            metric_name=name,
            backtest_value=backtest,
            live_value=live,
            delta_abs=delta_abs,
            delta_pct=delta_pct,
            within_tolerance=within,
            tolerance_pct=self._tolerance_pct,
        )

    @staticmethod
    def _build_deny_reason_dist(events: list) -> dict[str, float]:
        """Build a deny_reason_code frequency map from live novelty events.

        Parameters
        ----------
        events:
            List of PPFNoveltyEvent ORM objects.  Each must expose a
            ``deny_reason_code`` string attribute.

        Returns
        -------
        dict[str, float]
            Raw counts per deny_reason_code.  Returns empty dict when events
            is empty (JS divergence will handle gracefully).
        """
        dist: dict[str, float] = {}
        for ev in events:
            code: str = getattr(ev, "deny_reason_code", "UNKNOWN") or "UNKNOWN"
            dist[code] = dist.get(code, 0.0) + 1.0
        return dist

    @staticmethod
    def _js_divergence(
        dist_a: dict[str, float], dist_b: dict[str, float]
    ) -> float:
        """Jensen–Shannon divergence between two categorical distributions.

        JS divergence is symmetric, bounded [0, ln(2)] in nats (or [0, 1]
        when using log base 2).  This implementation uses natural logarithm
        to match the statistical convention; values closer to 0 indicate
        more similar distributions.

        Returns 0.0 when either distribution is empty (considered identical
        for eligibility purposes — no data means no evidence of divergence).

        Parameters
        ----------
        dist_a:
            First distribution as raw counts or probabilities (unnormalized).
        dist_b:
            Second distribution as raw counts or probabilities (unnormalized).

        Returns
        -------
        float
            JS divergence in [0, ln(2)].  Compare against js_threshold which
            defaults to 0.1 (well below ln(2) ≈ 0.693).
        """
        if not dist_a or not dist_b:
            logger.debug("_js_divergence: one or both distributions empty — returning 0.0")
            return 0.0

        all_keys: set[str] = set(dist_a.keys()) | set(dist_b.keys())

        # Normalize to probability distributions
        total_a: float = sum(dist_a.values()) or 1.0
        total_b: float = sum(dist_b.values()) or 1.0

        p: dict[str, float] = {k: dist_a.get(k, 0.0) / total_a for k in all_keys}
        q: dict[str, float] = {k: dist_b.get(k, 0.0) / total_b for k in all_keys}

        # Mixture distribution M = (P + Q) / 2
        m: dict[str, float] = {k: (p[k] + q[k]) / 2.0 for k in all_keys}

        def _kl(a_dist: dict[str, float], m_dist: dict[str, float]) -> float:
            """KL(a_dist || m_dist) using natural logarithm."""
            result = 0.0
            for k in all_keys:
                p_k = a_dist[k]
                m_k = m_dist[k]
                if p_k > 0.0 and m_k > 0.0:
                    result += p_k * math.log(p_k / m_k)
            return result

        js = (_kl(p, m) + _kl(q, m)) / 2.0

        # Clamp to [0, ln(2)] to guard against float precision drift
        js = max(0.0, min(js, math.log(2)))

        logger.debug(
            "_js_divergence: keys=%d js=%.6f threshold=N/A",
            len(all_keys),
            js,
        )
        return js
