"""
K-Dexter Decision Card Service

Transforms DecisionSummary into a structured DecisionCard
for dashboard rendering. Pure presentation logic — no computation,
no mutation, no write, no state transition.

Input:  DecisionSummary (from operator_decision_service)
Output: DecisionCard (structured visualization elements)

Safety:
  - Read-only: transforms existing data, never writes
  - action_allowed always False — structurally enforced
  - No action verbs in labels or descriptions
  - No import of any Ledger or write-capable service
"""
from __future__ import annotations

from app.schemas.decision_card_schema import (
    DecisionCard,
    PostureBadge,
    RiskBadge,
    ReasonCompact,
    SafetyBar,
)
from app.services.operator_decision_service import (
    DecisionSummary,
    POSTURE_MONITOR,
    POSTURE_REVIEW,
    POSTURE_MANUAL_CHECK,
    POSTURE_URGENT_REVIEW,
    POSTURE_DESCRIPTIONS,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_HIGH,
)


# -- Posture → Badge mapping ------------------------------------------------ #

_POSTURE_SEVERITY = {
    POSTURE_MONITOR: "info",
    POSTURE_REVIEW: "warning",
    POSTURE_MANUAL_CHECK: "caution",
    POSTURE_URGENT_REVIEW: "critical",
}

_POSTURE_LABEL = {
    POSTURE_MONITOR: "Monitor",
    POSTURE_REVIEW: "Review",
    POSTURE_MANUAL_CHECK: "Manual Check",
    POSTURE_URGENT_REVIEW: "Urgent Review",
}


# -- Risk → Badge mapping --------------------------------------------------- #

_RISK_SEVERITY = {
    RISK_LOW: "info",
    RISK_MEDIUM: "warning",
    RISK_HIGH: "critical",
}

_RISK_LABEL = {
    RISK_LOW: "Low Risk",
    RISK_MEDIUM: "Medium Risk",
    RISK_HIGH: "High Risk",
}


# -- Reason compact builder ------------------------------------------------- #

_REASON_COMPACT_LIMIT = 3


def _build_reason_compact(reason_chain: list) -> ReasonCompact:
    """
    Compress reason chain to max 3 lines for compact display.

    Prioritizes: pressure first, then candidate/orphan/stale totals,
    then tier-specific details. Truncates with indicator if more.
    """
    total = len(reason_chain)
    lines = reason_chain[:_REASON_COMPACT_LIMIT]
    return ReasonCompact(
        lines=lines,
        total_reasons=total,
        truncated=total > _REASON_COMPACT_LIMIT,
    )


# -- Main builder ----------------------------------------------------------- #

def build_decision_card(decision: DecisionSummary) -> DecisionCard:
    """
    Transform DecisionSummary into a structured DecisionCard.

    Pure transformation — no side effects, no writes, no state changes.
    Safety labels are structurally fixed and cannot be overridden.

    Args:
        decision: DecisionSummary from operator_decision_service

    Returns:
        DecisionCard with posture badge, risk badge, reason compact,
        safety bar, and explanation.
    """
    posture = decision.recommended_posture

    posture_badge = PostureBadge(
        posture=posture,
        severity=_POSTURE_SEVERITY.get(posture, "info"),
        label=_POSTURE_LABEL.get(posture, "Monitor"),
        description=POSTURE_DESCRIPTIONS.get(posture, ""),
    )

    risk = decision.risk_level

    risk_badge = RiskBadge(
        risk_level=risk,
        severity=_RISK_SEVERITY.get(risk, "info"),
        label=_RISK_LABEL.get(risk, "Low Risk"),
    )

    reason_compact = _build_reason_compact(decision.reason_chain)

    # Safety bar — structurally fixed, never derived from input
    safety_bar = SafetyBar(
        action_allowed=False,
        suggestion_only=True,
        read_only=True,
    )

    return DecisionCard(
        posture_badge=posture_badge,
        risk_badge=risk_badge,
        reason_compact=reason_compact,
        safety_bar=safety_bar,
        explanation=decision.decision_explanation,
        candidate_total=decision.candidate_total,
        orphan_total=decision.orphan_total,
        stale_total=decision.stale_total,
    )
