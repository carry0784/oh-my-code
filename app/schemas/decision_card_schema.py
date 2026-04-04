"""
K-Dexter Decision Card Schema

Structured visualization elements for operator decision guidance.
Transforms raw decision_summary into badge/card/compact-view format
that a frontend or dashboard can render immediately.

Design rules:
  - Read-only: no action buttons, no execution triggers
  - SafetyBar always visible: action_allowed=False, suggestion_only, read_only
  - ReasonCompact max 3 lines (truncated indicator if more)
  - Severity hints for posture/risk badges (info/warning/caution/critical)
  - No action verbs in any label or description
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class PostureBadge(BaseModel):
    """Operator posture badge with severity hint for UI rendering."""
    posture: str = "MONITOR"
    severity: str = "info"          # info | warning | caution | critical
    label: str = "Monitor"
    description: str = ""


class RiskBadge(BaseModel):
    """Risk level badge with severity hint for UI rendering."""
    risk_level: str = "LOW"
    severity: str = "info"          # info | warning | critical
    label: str = "Low Risk"


class ReasonCompact(BaseModel):
    """Compact reason view — max 3 lines for dashboard display."""
    lines: list[str] = Field(default_factory=list, max_length=3)
    total_reasons: int = 0
    truncated: bool = False


class SafetyBar(BaseModel):
    """
    Fixed safety labels — always visible on dashboard.

    action_allowed is structurally False. Never True.
    """
    action_allowed: bool = False        # NEVER True
    suggestion_only: bool = True        # Always True
    read_only: bool = True              # Always True
    labels: list[str] = Field(default_factory=lambda: [
        "No action executed",
        "Suggestion only",
        "Read-only observation",
    ])


class DecisionCard(BaseModel):
    """
    Unified decision card for dashboard display.

    Combines posture badge, risk badge, reason compact view,
    and safety bar into a single renderable card.

    This is a presentation-only model. No computation, no mutation.
    """
    posture_badge: PostureBadge
    risk_badge: RiskBadge
    reason_compact: ReasonCompact
    safety_bar: SafetyBar
    explanation: str = ""
    candidate_total: int = 0
    orphan_total: int = 0
    stale_total: int = 0
