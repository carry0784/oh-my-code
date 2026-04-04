"""
B-11: Governance Summary Schema — read-only 통제 상태 요약

overall_status:
  HEALTHY: NORMAL + enabled + no orphans + evidence exists
  DEGRADED: RESTRICTED / orphans / evidence missing / enabled=false
  BLOCKED: QUARANTINED / LOCKDOWN (최우선)

execution_state:
  ALLOWED: NORMAL
  GUARDED: RESTRICTED
  BLOCKED: QUARANTINED / LOCKDOWN

dominant_reason 우선순위:
  lockdown > quarantined > restricted > orphan > evidence_missing > governance_disabled

No enforcement change. No guard change. No raw text. Read-only summary only.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class GovOverallStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"


class GovExecutionState(str, Enum):
    ALLOWED = "ALLOWED"
    GUARDED = "GUARDED"
    BLOCKED = "BLOCKED"


class GovernanceHealth(BaseModel):
    """v2 경량 요약. 5필드만."""

    overall_status: GovOverallStatus = GovOverallStatus.DEGRADED
    execution_state: GovExecutionState = GovExecutionState.GUARDED
    dominant_reason: str = ""
    active_constraints_count: int = 0
    updated_at: str = ""


class GovernanceSummaryResponse(BaseModel):
    """
    B-11: Governance Summary (상세).
    /api/governance-summary 전용.
    """

    overall_status: GovOverallStatus = GovOverallStatus.DEGRADED
    execution_state: GovExecutionState = GovExecutionState.GUARDED
    dominant_reason: str = ""
    active_constraints_count: int = 0
    updated_at: str = ""
    security_state: str = "UNKNOWN"
    governance_enabled: bool = False
    orphan_detected: bool = False
    evidence_exists: bool = False
    evidence_total: int = 0
    summary_note: str = Field(
        default="Read-only governance summary. No enforcement change.",
    )
