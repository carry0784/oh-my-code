"""
E-01: Executor Schema — 제한적 실행 계층 설계

이 파일은 E-01의 **설계 계약(schema + contract)만** 정의한다.
실행 로직, 거래소 호출, 주문 전송, 자동 실행, unlock/resume은 포함하지 않는다.

E-01 활성화는 별도 승인 전까지 금지다.

역참조: Operating Constitution v1.0 제36조~제38조

실행 전제 조건 체인:
  I-03 check_id        → 점검 결과 고정
  I-04 preflight_id    → 복구 적합성 고정
  I-05 gate_snapshot_id → 4조건 판정 고정
  I-06 approval_id     → 승인 증거 고정 (7필드 + scope + expiry)
  I-07 policy_id       → 승인 유효성 고정 (MATCH 필수)
  E-01 execution_id    → 실행 근거 고정

전제 조건 (모두 AND):
  1. I-06 APPROVED receipt 존재 + 미만료
  2. I-07 decision == MATCH
  3. execution_scope ⊆ approval_scope
  4. Fail-closed: 어떤 조건이든 실패하면 실행 불가

Scope 일치 규칙:
  execution_scope ⊆ approval_scope
  MICRO_LIVE_ONLY ⊆ MICRO_LIVE_ONLY
  PAPER_ONLY ⊆ PAPER_ONLY, MICRO_LIVE_ONLY
  SPECIFIC_SYMBOL_ONLY ⊆ SPECIFIC_SYMBOL_ONLY (target_symbol 일치 필수)
  NO_EXECUTION ⊆ 모든 scope (실행 불가이므로 항상 안전)
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Execution State
# ---------------------------------------------------------------------------
class ExecutionState(str, Enum):
    """E-01 실행 상태. 설계 계약만 정의."""

    PENDING = "PENDING"  # 실행 요청 생성됨, 아직 미실행
    PRECONDITION_FAILED = "PRECONDITION_FAILED"  # 전제 조건 미충족
    SCOPE_MISMATCH = "SCOPE_MISMATCH"  # scope 불일치
    READY_TO_EXECUTE = "READY_TO_EXECUTE"  # 전제 충족, 실행 대기 (활성화 금지)
    # 아래 상태는 E-01 활성화 후에만 사용 가능 (현재 금지)
    # EXECUTING = "EXECUTING"
    # COMPLETED = "COMPLETED"
    # FAILED = "FAILED"
    # ROLLED_BACK = "ROLLED_BACK"


class ExecutionScope(str, Enum):
    """실행 범위. I-06 ApprovalScope와 동일 체계."""

    MICRO_LIVE_ONLY = "MICRO_LIVE_ONLY"
    PAPER_ONLY = "PAPER_ONLY"
    NO_EXECUTION = "NO_EXECUTION"
    SPECIFIC_SYMBOL_ONLY = "SPECIFIC_SYMBOL_ONLY"


class ExecutionFailReason(str, Enum):
    """Fail-closed 실패 사유."""

    MISSING_APPROVAL = "MISSING_APPROVAL"
    APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
    APPROVAL_NOT_APPROVED = "APPROVAL_NOT_APPROVED"
    MISSING_POLICY_MATCH = "MISSING_POLICY_MATCH"
    POLICY_DRIFT = "POLICY_DRIFT"
    POLICY_EXPIRED = "POLICY_EXPIRED"
    SCOPE_MISMATCH = "SCOPE_MISMATCH"
    SYMBOL_MISMATCH = "SYMBOL_MISMATCH"
    EXECUTOR_NOT_ACTIVATED = "EXECUTOR_NOT_ACTIVATED"
    EVIDENCE_CHAIN_BROKEN = "EVIDENCE_CHAIN_BROKEN"


# ---------------------------------------------------------------------------
# Evidence Chain Reference
# ---------------------------------------------------------------------------
class EvidenceChainRef(BaseModel):
    """I-03 ~ I-07 → E-01 증거 체인 참조 계약."""

    check_id: str = Field(description="I-03 점검 결과 ID")
    preflight_id: str = Field(description="I-04 Recovery Preflight ID")
    gate_snapshot_id: str = Field(description="I-05 Execution Gate ID")
    approval_id: str = Field(description="I-06 Operator Approval ID")
    approval_receipt_hash: str = Field(description="I-06 영수증 SHA-256 해시")
    policy_snapshot_id: str = Field(description="I-07 Execution Policy ID")
    policy_decision: str = Field(description="I-07 판정 (MATCH 필수)")


# ---------------------------------------------------------------------------
# Execution Receipt (설계 계약)
# ---------------------------------------------------------------------------
class ExecutionReceipt(BaseModel):
    """
    E-01: Execution Receipt — 실행 근거 고정 설계.

    이 스키마는 설계 계약이다. 실행 로직은 포함하지 않는다.
    E-01 활성화는 별도 승인 전까지 금지다.

    Fail-closed 규칙:
      - 전제 조건 하나라도 실패 → 실행 불가
      - evidence_chain 하나라도 누락 → 실행 불가
      - scope 불일치 → 실행 불가
      - 활성화 전 → EXECUTOR_NOT_ACTIVATED
    """

    execution_id: str = Field(description="실행 근거 고유 ID")
    state: ExecutionState
    execution_scope: ExecutionScope
    target_symbol: Optional[str] = Field(
        default=None,
        description="SPECIFIC_SYMBOL_ONLY 일 때 필수",
    )
    evidence_chain: EvidenceChainRef = Field(
        description="I-03~I-07 증거 체인 참조",
    )
    fail_reasons: list[ExecutionFailReason] = Field(default_factory=list)
    timestamp: str = Field(description="ISO 8601")
    summary: str = ""
    evidence_id: str = Field(default="", description="E-01 자체 evidence bundle ID")
    rule_refs: list[str] = Field(default_factory=list)
    operator_action_required: bool = False
    executor_activated: bool = Field(
        default=False,
        description="E-01 활성화 여부. 현재 항상 False.",
    )
    receipt_note: str = Field(
        default="E-01은 설계 계약이다. 실행 로직은 활성화 전까지 포함하지 않는다.",
    )

    @model_validator(mode="after")
    def enforce_not_activated(self):
        """E-01 미활성화 상태에서 READY_TO_EXECUTE 이상 진행 금지."""
        if not self.executor_activated and self.state == ExecutionState.READY_TO_EXECUTE:
            if ExecutionFailReason.EXECUTOR_NOT_ACTIVATED not in self.fail_reasons:
                self.fail_reasons.append(ExecutionFailReason.EXECUTOR_NOT_ACTIVATED)
            self.operator_action_required = True
        return self

    @model_validator(mode="after")
    def enforce_scope_symbol(self):
        """SPECIFIC_SYMBOL_ONLY인데 target_symbol 없으면 SCOPE_MISMATCH."""
        if self.execution_scope == ExecutionScope.SPECIFIC_SYMBOL_ONLY and not self.target_symbol:
            self.state = ExecutionState.SCOPE_MISMATCH
            if ExecutionFailReason.SYMBOL_MISMATCH not in self.fail_reasons:
                self.fail_reasons.append(ExecutionFailReason.SYMBOL_MISMATCH)
        return self

    @model_validator(mode="after")
    def enforce_failed_operator(self):
        """PRECONDITION_FAILED / SCOPE_MISMATCH면 operator_action_required 강제."""
        if self.state in (
            ExecutionState.PRECONDITION_FAILED,
            ExecutionState.SCOPE_MISMATCH,
        ):
            self.operator_action_required = True
        return self


# ---------------------------------------------------------------------------
# Scope 일치 규칙
# ---------------------------------------------------------------------------
_SCOPE_HIERARCHY = {
    ExecutionScope.NO_EXECUTION: {
        ExecutionScope.NO_EXECUTION,
        ExecutionScope.PAPER_ONLY,
        ExecutionScope.MICRO_LIVE_ONLY,
        ExecutionScope.SPECIFIC_SYMBOL_ONLY,
    },
    ExecutionScope.PAPER_ONLY: {
        ExecutionScope.PAPER_ONLY,
        ExecutionScope.MICRO_LIVE_ONLY,
    },
    ExecutionScope.MICRO_LIVE_ONLY: {
        ExecutionScope.MICRO_LIVE_ONLY,
    },
    ExecutionScope.SPECIFIC_SYMBOL_ONLY: {
        ExecutionScope.SPECIFIC_SYMBOL_ONLY,
    },
}


def is_scope_compatible(
    execution_scope: ExecutionScope,
    approval_scope: ExecutionScope,
    execution_symbol: str | None = None,
    approval_symbol: str | None = None,
) -> bool:
    """
    execution_scope ⊆ approval_scope 검증.
    SPECIFIC_SYMBOL_ONLY면 symbol 일치도 필수.
    """
    allowed = _SCOPE_HIERARCHY.get(execution_scope, set())
    if approval_scope not in allowed:
        return False
    if (
        execution_scope == ExecutionScope.SPECIFIC_SYMBOL_ONLY
        and approval_scope == ExecutionScope.SPECIFIC_SYMBOL_ONLY
    ):
        if not execution_symbol or not approval_symbol:
            return False
        if execution_symbol != approval_symbol:
            return False
    return True
