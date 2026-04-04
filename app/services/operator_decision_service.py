"""
K-Dexter Operator Decision Service

Generates structured operator decision guidance from observation summary.
Read-only, suggestion-only. NEVER executes any action.

Posture levels:
  MONITOR       — Normal or minor. Wait for auto-resolution.
  REVIEW        — Operator review needed. Manual judgment pending.
  MANUAL_CHECK  — Manual check needed. Cleanup candidates present.
  URGENT_REVIEW — Urgent review. High pressure + multiple MANUAL items.

Risk levels:
  LOW    — Pressure LOW/MODERATE, orphan 0, candidate <= 2
  MEDIUM — Pressure HIGH or orphan > 0 or candidate 3-9
  HIGH   — Pressure CRITICAL or candidate >= 10

Safety:
  - action_allowed always False — NEVER True
  - suggestion_only always True
  - read_only always True
  - No write, no delete, no transition, no execution
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional, TYPE_CHECKING

from app.services.observation_summary_service import (
    build_observation_summary,
    ObservationSummary,
    PRESSURE_LOW,
    PRESSURE_MODERATE,
    PRESSURE_HIGH,
    PRESSURE_CRITICAL,
)

if TYPE_CHECKING:
    from app.agents.action_ledger import ActionLedger
    from app.services.execution_ledger import ExecutionLedger
    from app.services.submit_ledger import SubmitLedger


# -- Constants -------------------------------------------------------------- #

POSTURE_MONITOR = "MONITOR"
POSTURE_REVIEW = "REVIEW"
POSTURE_MANUAL_CHECK = "MANUAL_CHECK"
POSTURE_URGENT_REVIEW = "URGENT_REVIEW"

RISK_LOW = "LOW"
RISK_MEDIUM = "MEDIUM"
RISK_HIGH = "HIGH"

# Posture descriptions — suggestion only, no action verbs
POSTURE_DESCRIPTIONS = {
    POSTURE_MONITOR: "Normal operating state. No operator intervention needed at this time.",
    POSTURE_REVIEW: "Operator review recommended. Some observations warrant attention.",
    POSTURE_MANUAL_CHECK: "Manual check recommended. Cleanup candidates identified for review.",
    POSTURE_URGENT_REVIEW: "Urgent operator review recommended. Elevated pressure with multiple items requiring attention.",
}


# -- Data classes ----------------------------------------------------------- #

@dataclass
class DecisionSummary:
    """
    Structured operator decision guidance.

    Suggestion only. No action executed. action_allowed is ALWAYS False.
    """
    recommended_posture: str = POSTURE_MONITOR
    risk_level: str = RISK_LOW
    reason_chain: list = field(default_factory=list)
    decision_explanation: str = ""
    candidate_total: int = 0
    orphan_total: int = 0
    stale_total: int = 0
    cleanup_pressure: str = PRESSURE_LOW

    # Safety labels — ALWAYS fixed, NEVER changed
    action_allowed: bool = False     # NEVER True
    suggestion_only: bool = True     # Always True
    read_only: bool = True           # Always True

    def to_dict(self) -> dict:
        return asdict(self)

    def to_schema(self):
        """Convert to typed Pydantic schema (DecisionSummarySchema)."""
        from app.schemas.decision_summary_schema import (
            DecisionSummarySchema, DecisionSafety,
        )
        return DecisionSummarySchema(
            recommended_posture=self.recommended_posture,
            risk_level=self.risk_level,
            reason_chain=list(self.reason_chain),
            decision_explanation=self.decision_explanation,
            candidate_total=self.candidate_total,
            orphan_total=self.orphan_total,
            stale_total=self.stale_total,
            cleanup_pressure=self.cleanup_pressure,
            safety=DecisionSafety(
                action_allowed=False,   # Structurally fixed
                suggestion_only=True,
                read_only=True,
            ),
        )


# -- Core logic ------------------------------------------------------------- #

def _determine_posture(pressure: str) -> str:
    """
    Map cleanup pressure to recommended operator posture.

    Rules:
      LOW      → MONITOR
      MODERATE → REVIEW
      HIGH     → MANUAL_CHECK
      CRITICAL → URGENT_REVIEW
    """
    mapping = {
        PRESSURE_LOW: POSTURE_MONITOR,
        PRESSURE_MODERATE: POSTURE_REVIEW,
        PRESSURE_HIGH: POSTURE_MANUAL_CHECK,
        PRESSURE_CRITICAL: POSTURE_URGENT_REVIEW,
    }
    return mapping.get(pressure, POSTURE_MONITOR)


def _determine_risk_level(
    pressure: str,
    orphan_total: int,
    candidate_total: int,
) -> str:
    """
    Determine risk level from pressure + orphan + candidate counts.

    Rules:
      HIGH   — pressure CRITICAL or candidate >= 10
      MEDIUM — pressure HIGH or orphan > 0 or candidate 3-9
      LOW    — otherwise
    """
    if pressure == PRESSURE_CRITICAL or candidate_total >= 10:
        return RISK_HIGH
    if pressure == PRESSURE_HIGH or orphan_total > 0 or candidate_total >= 3:
        return RISK_MEDIUM
    return RISK_LOW


def _build_reason_chain(obs: ObservationSummary) -> list[str]:
    """Build traceable reason chain from observation data."""
    chain = []
    chain.append(f"pressure={obs.cleanup_pressure}")
    chain.append(f"candidate_total={obs.candidate_total}")
    chain.append(f"orphan_total={obs.orphan_total}")
    chain.append(f"stale_total={obs.stale_total}")

    # Add tier-specific stale info if non-zero
    for tier, count in obs.stale_by_tier.items():
        if count > 0:
            chain.append(f"stale_{tier}={count}")

    # Add action class distribution from matrix if available
    action_counts: dict[str, int] = {}
    for entry in obs.reason_action_matrix:
        action = entry.get("action", "")
        count = entry.get("count", 0)
        if action and count > 0:
            action_counts[action] = action_counts.get(action, 0) + count
    for action, count in sorted(action_counts.items()):
        chain.append(f"action_{action}={count}")

    return chain


def _build_explanation(
    posture: str,
    risk_level: str,
    obs: ObservationSummary,
) -> str:
    """Build human-readable decision explanation. No action verbs."""
    parts = []

    # Base posture description
    desc = POSTURE_DESCRIPTIONS.get(posture, "")
    if desc:
        parts.append(desc)

    # Risk context
    parts.append(f"Risk level: {risk_level}.")

    # Key numbers
    if obs.candidate_total > 0:
        parts.append(
            f"Observation: {obs.candidate_total} cleanup candidate(s), "
            f"{obs.orphan_total} orphan(s), {obs.stale_total} stale."
        )
    else:
        parts.append("No cleanup candidates identified.")

    return " ".join(parts)


def build_decision_summary(
    action_ledger: Optional[ActionLedger] = None,
    execution_ledger: Optional[ExecutionLedger] = None,
    submit_ledger: Optional[SubmitLedger] = None,
) -> DecisionSummary:
    """
    Build operator decision guidance from observation layers.

    Read-only: delegates to build_observation_summary().
    Suggestion only: action_allowed is ALWAYS False.
    Never writes, deletes, or transitions any proposal.

    Returns DecisionSummary with posture, risk level, and reason chain.
    """
    obs = build_observation_summary(action_ledger, execution_ledger, submit_ledger)

    posture = _determine_posture(obs.cleanup_pressure)
    risk_level = _determine_risk_level(
        obs.cleanup_pressure, obs.orphan_total, obs.candidate_total,
    )
    reason_chain = _build_reason_chain(obs)
    explanation = _build_explanation(posture, risk_level, obs)

    return DecisionSummary(
        recommended_posture=posture,
        risk_level=risk_level,
        reason_chain=reason_chain,
        decision_explanation=explanation,
        candidate_total=obs.candidate_total,
        orphan_total=obs.orphan_total,
        stale_total=obs.stale_total,
        cleanup_pressure=obs.cleanup_pressure,
        # Safety labels — ALWAYS enforced
        action_allowed=False,
        suggestion_only=True,
        read_only=True,
    )
