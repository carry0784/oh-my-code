"""
I-07: Execution Policy Schema — 승인-실행 상태 일치 검증

역참조: Operating Constitution v1.0 제33조, 제39조, 제43조
I-07은 실행 계층이 아니라 승인-실행 일치 검증 계층이다.
MATCH means policy-match only, not execution-performed.
I-06 APPROVED receipt는 실행 허가가 아니다.
I-07 MATCH 없이는 어떤 실행도 허용되지 않는다.

판정:
  MATCH: 6조건 모두 일치 (E-01 진입 가능 조건일 뿐, 실행 자체 아님)
  DRIFT: 1개 이상 불일치 (재승인 필요)
  EXPIRED: 만료 (재승인 필요)
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class PolicyDecision(str, Enum):
    MATCH = "MATCH"
    DRIFT = "DRIFT"
    EXPIRED = "EXPIRED"


class PolicyDriftReason(str, Enum):
    APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
    GATE_CLOSED = "GATE_CLOSED"
    PREFLIGHT_NOT_READY = "PREFLIGHT_NOT_READY"
    OPS_SCORE_LOW = "OPS_SCORE_LOW"
    LOCKDOWN_ACTIVE = "LOCKDOWN_ACTIVE"
    CRITICAL_ALERT_DETECTED = "CRITICAL_ALERT_DETECTED"
    APPROVAL_HASH_MISMATCH = "APPROVAL_HASH_MISMATCH"
    MISSING_APPROVAL_RECEIPT = "MISSING_APPROVAL_RECEIPT"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"


class PolicyCheckItem(BaseModel):
    """개별 검증 항목."""

    name: str
    matched: bool
    approval_value: str = Field(description="승인 시점 값")
    current_value: str = Field(description="현재 값")
    message: str = ""
    rule_refs: list[str] = Field(default_factory=list)


class ExecutionPolicyResult(BaseModel):
    """
    I-07: Execution Policy 결과.
    MATCH means policy-match only, not execution-performed.
    """

    policy_id: str = Field(description="검증 고유 ID")
    approval_id: str = Field(description="대상 I-06 승인 영수증 ID")
    decision: PolicyDecision
    timestamp: str = Field(description="검증 시각 (ISO 8601)")
    summary: str
    items: list[PolicyCheckItem] = Field(default_factory=list)
    drift_reasons: list[PolicyDriftReason] = Field(default_factory=list)
    approval_receipt_hash: str = Field(
        default="", description="SHA-256 of approval receipt fields"
    )
    current_hash: str = Field(
        default="", description="SHA-256 of current state fields"
    )
    evidence_id: str = ""
    rule_refs: list[str] = Field(default_factory=list)
    operator_action_required: bool = False
    reapproval_required: bool = False
    receipt_note: str = Field(
        default="MATCH means policy-match only, not execution-performed.",
    )

    @model_validator(mode="after")
    def enforce_drift_operator(self):
        """DRIFT/EXPIRED면 operator_action_required + reapproval_required 강제."""
        if self.decision in (PolicyDecision.DRIFT, PolicyDecision.EXPIRED):
            self.operator_action_required = True
            self.reapproval_required = True
        return self
