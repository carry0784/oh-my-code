"""
B-13: Alert Priority / Escalation Summary Schema — read-only

priority_level: P1 / P2 / P3 / INFO
escalation_state: none / watch / escalated / critical

No ack/write/mute/retry/notification. Read-only summary only.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class PriorityLevel(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    INFO = "INFO"


class EscalationState(str, Enum):
    NONE = "none"
    WATCH = "watch"
    ESCALATED = "escalated"
    CRITICAL = "critical"


class PriorityBreakdown(BaseModel):
    p1_count: int = 0
    p2_count: int = 0
    p3_count: int = 0
    info_count: int = 0


class AlertHealth(BaseModel):
    """v2 경량 요약. 5필드만."""

    top_priority: PriorityLevel = PriorityLevel.INFO
    escalation_state: EscalationState = EscalationState.NONE
    top_reason: str = ""
    alert_count: int = 0
    updated_at: str = ""


class AlertSummaryDetailResponse(BaseModel):
    """
    B-13: Alert Summary (상세).
    /api/alert-summary 전용.
    """

    top_priority: PriorityLevel = PriorityLevel.INFO
    escalation_state: EscalationState = EscalationState.NONE
    top_reason: str = ""
    alert_count: int = 0
    updated_at: str = ""
    breakdown: PriorityBreakdown = Field(default_factory=PriorityBreakdown)
    ops_status: str = "UNKNOWN"
    governance_status: str = "UNKNOWN"
    execution_state: str = "UNKNOWN"
    market_worst_trust: str = "UNKNOWN"
    active_constraints: int = 0
    stale_sources: int = 0
    unavailable_sources: int = 0
    summary_note: str = Field(
        default="Read-only alert priority summary. No ack/write/mute/retry.",
    )
