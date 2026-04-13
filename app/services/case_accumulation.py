"""Case Accumulation Rules — structured event-to-case conversion.

Defines rules for when observations become tracked cases:
  - What constitutes a case (trigger conditions)
  - How cases accumulate evidence (observation windows)
  - When cases close (resolution conditions)
  - How cases feed back into learning (judgment pipeline)

Case types:
  1. NOVELTY_CASE: PPF novelty brake activation → observation window → TP/FP judgment
  2. REGIME_SHIFT_CASE: Regime transition detected → stability window → confirmed/reverted
  3. SIGNAL_CLUSTER_CASE: Multiple signals in short period → outcome tracking → quality score
  4. ANOMALY_CASE: Anomaly flag raised → investigation window → classified/dismissed

Design:
  - Cases are independent of the observation chain (different table)
  - Cases reference observation chain entries by ID for provenance
  - Cases have a lifecycle: OPEN → ACCUMULATING → RESOLVED → CLOSED
  - Resolution is either automated (window expiry) or manual (operator judgment)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Case Types ───────────────────────────────────────────────────────


class CaseType(str, Enum):
    NOVELTY = "NOVELTY"
    REGIME_SHIFT = "REGIME_SHIFT"
    SIGNAL_CLUSTER = "SIGNAL_CLUSTER"
    ANOMALY = "ANOMALY"


class CaseStatus(str, Enum):
    OPEN = "OPEN"
    ACCUMULATING = "ACCUMULATING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class CaseResolution(str, Enum):
    TRUE_POSITIVE = "TP"
    FALSE_POSITIVE = "FP"
    CONFIRMED = "CONFIRMED"
    REVERTED = "REVERTED"
    DISMISSED = "DISMISSED"
    UNRESOLVED = "UNRESOLVED"


# ── Accumulation Rules ───────────────────────────────────────────────


@dataclass(frozen=True)
class AccumulationRule:
    """Defines how a case type accumulates evidence and resolves."""

    case_type: CaseType
    observation_window_bars: int  # bars to observe before resolution
    auto_resolve: bool  # True = resolve automatically at window end
    min_evidence_count: int  # minimum observations needed
    resolution_method: str  # "window_expiry", "threshold", "manual"
    description: str = ""


# Registry of all accumulation rules
ACCUMULATION_RULES: dict[CaseType, AccumulationRule] = {
    CaseType.NOVELTY: AccumulationRule(
        case_type=CaseType.NOVELTY,
        observation_window_bars=20,
        auto_resolve=True,
        min_evidence_count=1,
        resolution_method="window_expiry",
        description=(
            "PPF novelty brake event. Opens on O9=True detection. "
            "Accumulates price observations for 20 bars. "
            "Auto-resolves as TP (price moved >3%) or FP (price reverted)."
        ),
    ),
    CaseType.REGIME_SHIFT: AccumulationRule(
        case_type=CaseType.REGIME_SHIFT,
        observation_window_bars=48,
        auto_resolve=True,
        min_evidence_count=3,
        resolution_method="window_expiry",
        description=(
            "Regime transition detected by V1 or V2 detector. "
            "Accumulates regime observations for 48 bars. "
            "Auto-resolves as CONFIRMED (regime persisted) or REVERTED."
        ),
    ),
    CaseType.SIGNAL_CLUSTER: AccumulationRule(
        case_type=CaseType.SIGNAL_CLUSTER,
        observation_window_bars=24,
        auto_resolve=True,
        min_evidence_count=2,
        resolution_method="threshold",
        description=(
            "Multiple strategy signals within 24 bars. "
            "Accumulates signal outcomes. "
            "Resolves based on net P&L of clustered signals."
        ),
    ),
    CaseType.ANOMALY: AccumulationRule(
        case_type=CaseType.ANOMALY,
        observation_window_bars=72,
        auto_resolve=False,
        min_evidence_count=1,
        resolution_method="manual",
        description=(
            "Anomaly flag (price spike, volume surge, etc.). "
            "Accumulates for 72 bars. "
            "Requires manual operator classification."
        ),
    ),
}


# ── Case Data Contracts ──────────────────────────────────────────────


@dataclass
class CaseRecord:
    """In-memory case record for processing.

    Not a DB model — cases can be persisted via observation_chain
    or a dedicated case table (future extension).
    """

    case_id: str = ""
    case_type: CaseType = CaseType.NOVELTY
    status: CaseStatus = CaseStatus.OPEN
    symbol: str = ""
    exchange: str = "binance"

    # Trigger
    trigger_ts: datetime | None = None
    trigger_price: float | None = None
    trigger_reason: str = ""

    # Accumulation
    observation_window_bars: int = 20
    bars_elapsed: int = 0
    evidence: list[dict] = field(default_factory=list)

    # Resolution
    resolution: CaseResolution | None = None
    resolution_ts: datetime | None = None
    resolution_price: float | None = None
    resolution_reason: str = ""

    def is_window_complete(self) -> bool:
        return self.bars_elapsed >= self.observation_window_bars

    def can_auto_resolve(self) -> bool:
        rule = ACCUMULATION_RULES.get(self.case_type)
        if rule is None:
            return False
        return rule.auto_resolve and self.is_window_complete()


# ── Case Evaluation Engine ───────────────────────────────────────────


class CaseEvaluator:
    """Evaluates cases for resolution based on accumulation rules."""

    @staticmethod
    def evaluate_novelty(case: CaseRecord) -> tuple[CaseResolution, str]:
        """Evaluate a novelty case based on price movement.

        TP: price moved > 3% from trigger (novelty was real)
        FP: price stayed within 3% (novelty was false alarm)
        """
        if case.trigger_price is None or case.resolution_price is None:
            return CaseResolution.UNRESOLVED, "missing_price_data"

        pct_change = abs((case.resolution_price - case.trigger_price) / case.trigger_price)

        if pct_change > 0.03:
            return CaseResolution.TRUE_POSITIVE, f"price_moved_{pct_change:.2%}"
        return CaseResolution.FALSE_POSITIVE, f"price_stable_{pct_change:.2%}"

    @staticmethod
    def evaluate_regime_shift(case: CaseRecord) -> tuple[CaseResolution, str]:
        """Evaluate a regime shift case based on regime persistence.

        CONFIRMED: regime persisted through observation window
        REVERTED: regime changed back within window
        """
        if len(case.evidence) < 3:
            return CaseResolution.UNRESOLVED, "insufficient_evidence"

        # Count how many observations match the trigger regime
        trigger_regime = case.trigger_reason
        matching = sum(1 for e in case.evidence if e.get("regime") == trigger_regime)
        ratio = matching / len(case.evidence)

        if ratio >= 0.6:
            return CaseResolution.CONFIRMED, f"regime_persisted_{ratio:.0%}"
        return CaseResolution.REVERTED, f"regime_reverted_{ratio:.0%}"

    @staticmethod
    def evaluate_signal_cluster(case: CaseRecord) -> tuple[CaseResolution, str]:
        """Evaluate a signal cluster based on net outcome.

        TP: net positive outcome from clustered signals
        FP: net negative outcome
        """
        if not case.evidence:
            return CaseResolution.UNRESOLVED, "no_signal_outcomes"

        net_pnl = sum(e.get("pnl", 0.0) for e in case.evidence)

        if net_pnl > 0:
            return CaseResolution.TRUE_POSITIVE, f"net_positive_{net_pnl:.4f}"
        return CaseResolution.FALSE_POSITIVE, f"net_negative_{net_pnl:.4f}"

    def resolve(self, case: CaseRecord) -> CaseRecord:
        """Attempt to resolve a case based on its type and accumulated evidence."""
        if not case.can_auto_resolve():
            return case

        evaluators = {
            CaseType.NOVELTY: self.evaluate_novelty,
            CaseType.REGIME_SHIFT: self.evaluate_regime_shift,
            CaseType.SIGNAL_CLUSTER: self.evaluate_signal_cluster,
        }

        evaluator = evaluators.get(case.case_type)
        if evaluator is None:
            return case

        resolution, reason = evaluator(case)
        case.resolution = resolution
        case.resolution_reason = reason
        case.resolution_ts = datetime.utcnow()
        case.status = CaseStatus.RESOLVED

        logger.info(
            "case_resolved",
            case_id=case.case_id,
            type=case.case_type.value,
            resolution=resolution.value,
            reason=reason,
        )

        return case


def get_rule(case_type: CaseType) -> AccumulationRule:
    """Look up accumulation rule for a case type."""
    rule = ACCUMULATION_RULES.get(case_type)
    if rule is None:
        raise ValueError(f"No accumulation rule defined for {case_type}")
    return rule
