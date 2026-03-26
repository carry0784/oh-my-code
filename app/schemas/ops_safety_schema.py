"""
B-14A: Operator Safety Summary Schema — 3계층 read-only safety state

Preflight (I-04) + Gate (I-05) + Approval (I-06) 집계.
Read-only. No execution authority.

역참조: Operating Constitution v1.0 제43조, 제45조
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class OpsSafetySummary(BaseModel):
    """
    B-14A: Operator Safety Summary.
    3계층 집계 결과. Read-only. Not execution-authorized.
    """

    timestamp: str = Field(description="ISO 8601")

    # 3-layer decisions
    preflight_decision: str = Field(
        default="NOT_READY",
        description="READY | NOT_READY | BLOCKED",
    )
    gate_decision: str = Field(
        default="CLOSED",
        description="OPEN | CLOSED",
    )
    approval_decision: str = Field(
        default="REJECTED",
        description="APPROVED | REJECTED",
    )

    # All-clear: preflight=READY + gate=OPEN + approval=APPROVED + blocked_reasons=[]
    all_clear: bool = Field(
        default=False,
        description="True only when all 3 layers clear AND blocked_reasons empty",
    )

    # Blocked reasons (표준 코드, 중복 제거, 순서: Preflight → Gate → Approval → System)
    blocked_reasons: list[str] = Field(
        default_factory=list,
        description="Aggregated blocking reason codes from all 3 layers",
    )

    # Next safe steps (고정 매핑만, 자유 생성 금지)
    next_safe_steps: list[str] = Field(
        default_factory=list,
        description="Operator guidance from fixed reason-code mapping",
    )

    # STEP 1: Extended fields (기존 값 읽기만, 새 계산 금지)
    pipeline_state: str = Field(
        default="UNKNOWN",
        description="첫 번째 차단 단계 또는 ALL_CLEAR",
    )
    ops_score: Optional[float] = Field(
        default=None,
        description="ops_score_average (기존 값, 재계산 금지)",
    )
    policy_decision: str = Field(
        default="UNKNOWN",
        description="MATCH | DRIFT | UNKNOWN",
    )
    lockdown_state: str = Field(
        default="UNKNOWN",
        description="security_state (기존 값)",
    )
    trading_authorized: Optional[bool] = Field(
        default=None,
        description="dual lock trading_authorized (기존 값)",
    )
    check_grade: str = Field(
        default="UNKNOWN",
        description="latest_check_grade (기존 값)",
    )
    conditions_met: Optional[int] = Field(
        default=None,
        description="gate_conditions_met (기존 값, 0~4)",
    )

    # Evidence references
    preflight_evidence_id: Optional[str] = None
    gate_evidence_id: Optional[str] = None
    approval_id: Optional[str] = None

    # Disclaimer
    safety_note: str = Field(
        default="Read-only. No execution authority.",
    )
