"""
E-02: Executor Activation Rule Schema — 활성화 조건 헌법

E-02는 실행 계층이 아니라 activation rule 계층이다.
ACTIVATION_ALLOWED means activation-eligible only, not execution-performed.
I-06 APPROVED + I-07 MATCH가 모두 있어도 activation approval 없으면 활성화 불가.

ACTIVATION_DENIED: 조건 부족, scope/hash mismatch, expiry, missing approval
ACTIVATION_BLOCKED: LOCKDOWN, CRITICAL alert, GATE CLOSED, PREFLIGHT NOT READY
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class ActivationDecision(str, Enum):
    ACTIVATION_ALLOWED = "ACTIVATION_ALLOWED"
    ACTIVATION_DENIED = "ACTIVATION_DENIED"
    ACTIVATION_BLOCKED = "ACTIVATION_BLOCKED"


class ActivationReason(str, Enum):
    MISSING_POLICY_SNAPSHOT = "MISSING_POLICY_SNAPSHOT"
    POLICY_NOT_MATCH = "POLICY_NOT_MATCH"
    APPROVAL_MISSING = "APPROVAL_MISSING"
    APPROVAL_SCOPE_MISMATCH = "APPROVAL_SCOPE_MISMATCH"
    TARGET_SYMBOL_MISMATCH = "TARGET_SYMBOL_MISMATCH"
    NO_EXECUTION_SCOPE = "NO_EXECUTION_SCOPE"
    ACTIVATION_APPROVAL_MISSING = "ACTIVATION_APPROVAL_MISSING"
    INTENT_HASH_MISMATCH = "INTENT_HASH_MISMATCH"
    APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
    LOCKDOWN_ACTIVE = "LOCKDOWN_ACTIVE"
    GATE_CLOSED = "GATE_CLOSED"
    PREFLIGHT_NOT_READY = "PREFLIGHT_NOT_READY"
    OPS_SCORE_LOW = "OPS_SCORE_LOW"
    CRITICAL_ALERT_DETECTED = "CRITICAL_ALERT_DETECTED"
    EXECUTOR_NOT_ACTIVATED = "EXECUTOR_NOT_ACTIVATED"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"


# Blocked-class reasons (operator intervention required)
_BLOCKED_REASONS = frozenset({
    ActivationReason.LOCKDOWN_ACTIVE,
    ActivationReason.CRITICAL_ALERT_DETECTED,
    ActivationReason.GATE_CLOSED,
    ActivationReason.PREFLIGHT_NOT_READY,
})


class ActivationCheckItem(BaseModel):
    name: str
    passed: bool
    observed: str = ""
    expected: str = ""
    message: str = ""
    rule_refs: list[str] = Field(default_factory=list)
    source_ref: Optional[str] = None


class ActivationApprovalReceipt(BaseModel):
    """Activation 전용 승인 영수증. I-06 operator approval과 별도 계층."""
    activation_approval_id: str
    approved_by: str = "operator"
    timestamp: str = Field(description="ISO 8601")
    expiry_at: str = Field(description="ISO 8601")
    allowed_scope: str = ""
    rule_refs: list[str] = Field(default_factory=list)
    activation_reason: str = ""
    note: str = ""


class ActivationReceipt(BaseModel):
    """
    E-02: Activation Receipt.
    ACTIVATION_ALLOWED means activation-eligible only, not execution-performed.
    """
    activation_id: str
    decision: ActivationDecision
    timestamp: str = Field(description="ISO 8601")
    policy_snapshot_id: str = ""
    approval_id: str = ""
    approval_receipt_hash: str = ""
    execution_intent_hash: str = ""
    execution_scope: str = ""
    requested_action: str = ""
    target_symbol: Optional[str] = None
    items: list[ActivationCheckItem] = Field(default_factory=list)
    reasons: list[ActivationReason] = Field(default_factory=list)
    rule_refs: list[str] = Field(default_factory=list)
    operator_action_required: bool = False
    activation_approval_id: Optional[str] = None
    activation_bucket: str = ""
    activation_note: str = Field(
        default="ACTIVATION_ALLOWED means activation-eligible only, not execution-performed.",
    )
    reapproval_required: bool = False
    evidence_id: str = ""

    @model_validator(mode="after")
    def enforce_blocked_operator(self):
        if self.decision == ActivationDecision.ACTIVATION_BLOCKED:
            self.operator_action_required = True
        return self

    @model_validator(mode="after")
    def enforce_denied_reapproval(self):
        if self.decision in (ActivationDecision.ACTIVATION_DENIED, ActivationDecision.ACTIVATION_BLOCKED):
            self.reapproval_required = True
        return self
