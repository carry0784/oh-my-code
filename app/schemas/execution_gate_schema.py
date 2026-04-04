"""
I-05: Execution Gate Schema — 4조건 통합 판정 스키마

역참조: Operating Constitution v1.0 제7조, 제41조, 제42조, 제43조

Execution Gate 4조건 (AND 결합):
  1. preflight.decision == READY  (제43조)
  2. ops_score >= threshold        (제41조)
  3. trading_authorized == true    (제42조)
  4. lockdown == false             (제7조)

OPEN = 4조건 모두 충족. 실행 전제 조건 OK.
CLOSED = 1개 이상 미충족. 실행 불가.

OPEN이어도 자동 실행하지 않는다. 표시/기록 전용.
OPEN means gate-open, not execution-authorized.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class GateDecision(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class GateCondition(BaseModel):
    """Execution Gate 개별 조건 판정."""

    name: str = Field(description="조건명")
    met: bool = Field(description="충족 여부")
    observed: str = Field(description="관찰값")
    required: str = Field(description="요구값")
    source: str = Field(description="출처 카드 (I-01/I-04)")
    rule_ref: str = Field(description="헌법 역참조")


class ExecutionGateResult(BaseModel):
    """
    I-05: Execution Gate 4조건 통합 판정 결과.
    OPEN means gate-open, not execution-authorized.
    자동 거래 실행/재개/승격/자본 확대 금지.
    """

    timestamp: str = Field(description="ISO 8601")
    decision: GateDecision
    summary: str
    conditions: list[GateCondition] = Field(default_factory=list)
    conditions_met: int = Field(default=0)
    conditions_total: int = Field(default=4)
    ops_score_average: float = Field(default=0.0, description="Ops Score 4축 평균")
    ops_score_threshold: float = Field(default=0.7, description="Ops Score 임계값")
    evidence_id: str = ""
    rule_refs: list[str] = Field(default_factory=list)
    operator_action_required: bool = False
    gate_is_not_execute: str = Field(
        default="OPEN means gate-open, not execution-authorized.",
    )

    @model_validator(mode="after")
    def enforce_closed_operator(self):
        """CLOSED면 operator_action_required 강제."""
        if self.decision == GateDecision.CLOSED:
            self.operator_action_required = True
        return self
