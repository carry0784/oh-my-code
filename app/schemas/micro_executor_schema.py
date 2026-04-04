"""
E-03: Micro Executor Schema — Activation-Consumed Dispatch Guard

E-03는 full executor가 아니라 activation-consumed dispatch guard 계층이다.
DISPATCH_ALLOWED means dispatch-eligible only, not order-sent.
DISPATCH_CONSUMED means activation already consumed, not execution-success.

핵심 규칙:
  - activation_consumed_at: 소비 시점
  - consumed_by_execution_id: 소비한 실행 ID
  - 동일 activation_id / intent_hash 재사용 금지
  - dispatch_window_expires_at: 짧은 실행 가능 시간창
  - paper/micro scope만 허용, live unlock 금지

No Evidence, No Dispatch.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class DispatchDecision(str, Enum):
    DISPATCH_ALLOWED = "DISPATCH_ALLOWED"
    DISPATCH_DENIED = "DISPATCH_DENIED"
    DISPATCH_BLOCKED = "DISPATCH_BLOCKED"
    DISPATCH_CONSUMED = "DISPATCH_CONSUMED"


class DispatchReason(str, Enum):
    ACTIVATION_MISSING = "ACTIVATION_MISSING"
    ACTIVATION_NOT_ALLOWED = "ACTIVATION_NOT_ALLOWED"
    ACTIVATION_ALREADY_CONSUMED = "ACTIVATION_ALREADY_CONSUMED"
    INTENT_HASH_ALREADY_USED = "INTENT_HASH_ALREADY_USED"
    DISPATCH_WINDOW_EXPIRED = "DISPATCH_WINDOW_EXPIRED"
    APPROVAL_SCOPE_MISMATCH = "APPROVAL_SCOPE_MISMATCH"
    TARGET_SYMBOL_MISMATCH = "TARGET_SYMBOL_MISMATCH"
    NO_EXECUTION_SCOPE = "NO_EXECUTION_SCOPE"
    POLICY_NOT_MATCH = "POLICY_NOT_MATCH"
    APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
    ACTIVATION_APPROVAL_MISSING = "ACTIVATION_APPROVAL_MISSING"
    LOCKDOWN_ACTIVE = "LOCKDOWN_ACTIVE"
    CRITICAL_ALERT_DETECTED = "CRITICAL_ALERT_DETECTED"
    EXECUTOR_NOT_ACTIVATED = "EXECUTOR_NOT_ACTIVATED"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    LIVE_SCOPE_FORBIDDEN = "LIVE_SCOPE_FORBIDDEN"


_BLOCKED_REASONS = frozenset(
    {
        DispatchReason.LOCKDOWN_ACTIVE,
        DispatchReason.CRITICAL_ALERT_DETECTED,
        DispatchReason.POLICY_NOT_MATCH,
    }
)


class DispatchEvidenceChain(BaseModel):
    """Full evidence chain from I-03 through E-02."""

    check_id: str = ""
    preflight_id: str = ""
    gate_snapshot_id: str = ""
    approval_id: str = ""
    approval_receipt_hash: str = ""
    policy_snapshot_id: str = ""
    activation_id: str = ""
    execution_intent_hash: str = ""


class DispatchCheckItem(BaseModel):
    name: str
    passed: bool
    observed: str = ""
    expected: str = ""
    message: str = ""
    rule_refs: list[str] = Field(default_factory=list)


class DispatchReceipt(BaseModel):
    """
    E-03: Dispatch Receipt.
    DISPATCH_ALLOWED means dispatch-eligible only, not order-sent.
    """

    execution_id: str
    decision: DispatchDecision
    timestamp: str = Field(description="ISO 8601")
    activation_id: str = ""
    execution_intent_hash: str = ""
    execution_scope: str = ""
    requested_action: str = ""
    target_symbol: Optional[str] = None
    activation_consumed_at: Optional[str] = Field(
        default=None,
        description="소비 시점 (ISO 8601). None=미소비.",
    )
    consumed_by_execution_id: Optional[str] = Field(
        default=None,
        description="소비한 execution_id. None=미소비.",
    )
    dispatch_window_expires_at: Optional[str] = Field(
        default=None,
        description="dispatch 가능 시간창 만료 (ISO 8601)",
    )
    evidence_chain: DispatchEvidenceChain = Field(default_factory=DispatchEvidenceChain)
    items: list[DispatchCheckItem] = Field(default_factory=list)
    reasons: list[DispatchReason] = Field(default_factory=list)
    rule_refs: list[str] = Field(default_factory=list)
    operator_action_required: bool = False
    dispatch_note: str = Field(
        default="DISPATCH_ALLOWED means dispatch-eligible only, not order-sent.",
    )
    reapproval_required: bool = False
    evidence_id: str = ""

    @model_validator(mode="after")
    def enforce_blocked_operator(self):
        if self.decision == DispatchDecision.DISPATCH_BLOCKED:
            self.operator_action_required = True
        return self

    @model_validator(mode="after")
    def enforce_consumed_denied(self):
        if self.decision in (DispatchDecision.DISPATCH_DENIED, DispatchDecision.DISPATCH_CONSUMED):
            self.reapproval_required = True
        return self
