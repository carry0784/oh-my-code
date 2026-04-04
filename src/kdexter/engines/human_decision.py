"""
Human Decision Interface — L1
K-Dexter AOS v4

B1 Constitutional layer. Human-only decisions that the machine
cannot override. Provides an interface for human operators to
submit decisions, approvals, and overrides.

Machine code MUST NOT modify decisions stored here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class DecisionType(Enum):
    APPROVAL = "APPROVAL"
    REJECTION = "REJECTION"
    OVERRIDE = "OVERRIDE"
    DIRECTIVE = "DIRECTIVE"


class DecisionStatus(Enum):
    PENDING = "PENDING"
    APPLIED = "APPLIED"
    EXPIRED = "EXPIRED"


@dataclass
class HumanDecision:
    decision_id: str
    decision_type: DecisionType
    description: str
    operator: str
    status: DecisionStatus = DecisionStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    applied_at: Optional[datetime] = None


class HumanDecisionInterface:
    """
    L1 Human Decision layer.

    Records human decisions and makes them available to the system.
    Machine code can read but NEVER modify stored decisions.
    """

    def __init__(self) -> None:
        self._decisions: dict[str, HumanDecision] = {}

    def submit(
        self,
        decision_id: str,
        decision_type: DecisionType,
        description: str,
        operator: str,
    ) -> HumanDecision:
        d = HumanDecision(
            decision_id=decision_id,
            decision_type=decision_type,
            description=description,
            operator=operator,
        )
        self._decisions[decision_id] = d
        return d

    def apply(self, decision_id: str) -> bool:
        d = self._decisions.get(decision_id)
        if d is None or d.status != DecisionStatus.PENDING:
            return False
        d.status = DecisionStatus.APPLIED
        d.applied_at = datetime.utcnow()
        return True

    def get(self, decision_id: str) -> Optional[HumanDecision]:
        return self._decisions.get(decision_id)

    def list_pending(self) -> list[HumanDecision]:
        return [d for d in self._decisions.values()
                if d.status == DecisionStatus.PENDING]

    def list_all(self) -> list[HumanDecision]:
        return list(self._decisions.values())
