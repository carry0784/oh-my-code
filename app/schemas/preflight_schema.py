"""
I-04: Recovery Preflight / Incident Playback Schema

역참조: Operating Constitution v1.0 제43조~제44조
I-04는 recovery engine이 아니라 recovery preflight / incident review 계층이다.

NOT_READY vs BLOCKED:
  NOT_READY = 복구 전제 조건 부족 (evidence 부족, snapshot stale 등)
  BLOCKED = 운영자 개입 전까지 진행 금지 (lockdown, security restricted 등)

READY means preflight-ready, not execution-authorized.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class PreflightDecision(str, Enum):
    READY = "READY"
    NOT_READY = "NOT_READY"
    BLOCKED = "BLOCKED"


class PreflightReasonCode(str, Enum):
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    LOCKDOWN_ACTIVE = "LOCKDOWN_ACTIVE"
    STALE_SNAPSHOT = "STALE_SNAPSHOT"
    CHECKS_NOT_GREEN = "CHECKS_NOT_GREEN"
    DB_UNAVAILABLE = "DB_UNAVAILABLE"
    FLOW_GAP = "FLOW_GAP"
    SECURITY_RESTRICTED = "SECURITY_RESTRICTED"
    UNRESOLVED_BLOCK = "UNRESOLVED_BLOCK"


class PlaybackConfidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class PreflightCheckItem(BaseModel):
    name: str
    status: str = Field(description="pass/fail/unknown")
    observed: str
    expected: str
    evidence_ref: Optional[str] = None
    message: str = ""
    reason_codes: list[PreflightReasonCode] = Field(default_factory=list)
    basis_refs: list[str] = Field(
        default_factory=list,
        description="Evidence/check/receipt refs supporting this judgment",
    )


class RecoveryPreflightResult(BaseModel):
    """
    제43조: Recovery Preflight 결과.
    READY means preflight-ready, not execution-authorized.
    """

    timestamp: str = Field(description="ISO 8601")
    decision: PreflightDecision
    summary: str
    items: list[PreflightCheckItem] = Field(default_factory=list)
    reason_codes: list[PreflightReasonCode] = Field(default_factory=list)
    basis_refs: list[str] = Field(default_factory=list)
    evidence_id: str = ""
    rule_refs: list[str] = Field(default_factory=list)
    operator_action_required: bool = False
    ready_is_not_execute: str = Field(
        default="READY means preflight-ready, not execution-authorized.",
    )

    @model_validator(mode="after")
    def enforce_blocked_operator(self):
        if self.decision == PreflightDecision.BLOCKED:
            self.operator_action_required = True
        return self


class PlaybackTimelineEntry(BaseModel):
    """제44조: Incident Playback 타임라인 항목."""

    timestamp: str = Field(description="ISO 8601")
    phase: str = Field(description="발생/탐지/자동조치/운영자조치/종료")
    description: str = ""
    source: str = Field(description="evidence_store/receipt_store/flow_log/check_runner")
    evidence_ref: Optional[str] = None


class IncidentPlaybackResult(BaseModel):
    """제44조: Incident Playback 재구성 결과. Review only, no re-execution."""

    incident_id: str
    time_range: dict = Field(description="start/end ISO 8601")
    trigger_source: Optional[str] = None
    summary: str = ""
    timeline: list[PlaybackTimelineEntry] = Field(default_factory=list)
    related_evidence_ids: list[str] = Field(default_factory=list)
    related_receipt_ids: list[str] = Field(default_factory=list)
    related_flow_events: list[str] = Field(default_factory=list)
    related_check_refs: list[str] = Field(default_factory=list)
    confidence: PlaybackConfidence = PlaybackConfidence.LOW
    missing_observations: list[str] = Field(default_factory=list)
    timeline_gap_detected: bool = False
    operator_review_summary: Optional[str] = None
    rule_refs: list[str] = Field(default_factory=list)
