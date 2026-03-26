"""
I-06: Operator Approval Receipt Schema — 승인 영수증 계층

역참조: Operating Constitution v1.0 제43조, 제45조
I-06은 승인 영수증 계층이지 실행 계층이 아니다.
APPROVED means operator-approved receipt only, not execution-authorized.
No Evidence, No Power.

필수 7필드:
  gate_snapshot_id, preflight_id, check_id, ops_score,
  security_state, timestamp, approval_expiry_at

approval_scope: 승인이 어떤 범위까지 유효한지 제한.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class ApprovalDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ApprovalScope(str, Enum):
    MICRO_LIVE_ONLY = "MICRO_LIVE_ONLY"
    PAPER_ONLY = "PAPER_ONLY"
    NO_EXECUTION = "NO_EXECUTION"
    SPECIFIC_SYMBOL_ONLY = "SPECIFIC_SYMBOL_ONLY"


class ApprovalRejectionReason(str, Enum):
    MISSING_GATE = "MISSING_GATE"
    GATE_NOT_OPEN = "GATE_NOT_OPEN"
    MISSING_PREFLIGHT = "MISSING_PREFLIGHT"
    PREFLIGHT_NOT_READY = "PREFLIGHT_NOT_READY"
    MISSING_CHECK = "MISSING_CHECK"
    CHECK_BLOCKED = "CHECK_BLOCKED"
    OPS_SCORE_LOW = "OPS_SCORE_LOW"
    LOCKDOWN_ACTIVE = "LOCKDOWN_ACTIVE"
    INVALID_TIMESTAMP = "INVALID_TIMESTAMP"
    APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    MISSING_APPROVAL_SCOPE = "MISSING_APPROVAL_SCOPE"
    MISSING_TARGET_SYMBOL = "MISSING_TARGET_SYMBOL"


class OperatorApprovalReceipt(BaseModel):
    """
    I-06: Operator Approval Receipt.
    APPROVED means operator-approved receipt only, not execution-authorized.
    No Evidence, No Power — 7필드 하나라도 누락 시 승인 불가.
    """

    approval_id: str = Field(description="승인 영수증 고유 ID")
    decision: ApprovalDecision
    gate_snapshot_id: str = Field(description="I-05 Execution Gate 결과 ID")
    preflight_id: str = Field(description="I-04 Recovery Preflight 결과 ID")
    check_id: str = Field(description="I-03 최근 점검 결과 ID")
    ops_score: float = Field(description="I-01 Ops Score 4축 평균")
    security_state: str = Field(description="I-01 enforcement state")
    timestamp: str = Field(description="승인 시각 (ISO 8601)")
    approval_expiry_at: str = Field(description="승인 만료 시각 (ISO 8601)")
    approval_scope: ApprovalScope = Field(description="승인 범위")
    approved_by: str = Field(default="operator", description="승인자")
    approval_reason: str = Field(default="", description="승인 사유")
    rule_refs: list[str] = Field(default_factory=list)
    rejection_reasons: list[ApprovalRejectionReason] = Field(default_factory=list)
    target_symbol: Optional[str] = Field(
        default=None,
        description="SPECIFIC_SYMBOL_ONLY 일 때 필수",
    )
    receipt_note: str = Field(
        default="APPROVED means operator-approved receipt only, not execution-authorized.",
    )
    operator_action_required: bool = Field(default=False)

    @model_validator(mode="after")
    def enforce_specific_symbol(self):
        """SPECIFIC_SYMBOL_ONLY scope에서 target_symbol 필수."""
        if (
            self.approval_scope == ApprovalScope.SPECIFIC_SYMBOL_ONLY
            and not self.target_symbol
            and self.decision == ApprovalDecision.APPROVED
        ):
            self.decision = ApprovalDecision.REJECTED
            if ApprovalRejectionReason.MISSING_TARGET_SYMBOL not in self.rejection_reasons:
                self.rejection_reasons.append(ApprovalRejectionReason.MISSING_TARGET_SYMBOL)
        return self

    @model_validator(mode="after")
    def enforce_rejected_action(self):
        """REJECTED면 operator_action_required 강제."""
        if self.decision == ApprovalDecision.REJECTED:
            self.operator_action_required = True
        return self
