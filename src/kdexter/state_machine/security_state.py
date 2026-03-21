"""
Security State Machine — K-Dexter AOS

States:
  NORMAL      → all operations allowed
  RESTRICTED  → approval required for execution
  QUARANTINED → sandbox only
  LOCKDOWN    → Human Override only (no automated actions)

Transitions are triggered by Failure Severity (from failure_taxonomy.md).
LOCKDOWN can only be released by Human (L27 Override Controller).
"""
from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


class SecurityStateEnum(Enum):
    NORMAL = "NORMAL"
    RESTRICTED = "RESTRICTED"
    QUARANTINED = "QUARANTINED"
    LOCKDOWN = "LOCKDOWN"


# Explicit severity ordering — string enum values cannot be compared with <=
_SECURITY_SEVERITY: dict[str, int] = {
    "NORMAL": 0,
    "RESTRICTED": 1,
    "QUARANTINED": 2,
    "LOCKDOWN": 3,
}


@dataclass
class SecurityStateContext:
    current: SecurityStateEnum = SecurityStateEnum.NORMAL
    previous: Optional[SecurityStateEnum] = None
    trigger_failure_id: Optional[str] = None
    locked_at: Optional[datetime] = None
    last_transition: datetime = field(default_factory=datetime.utcnow)

    def escalate(self, target: SecurityStateEnum, trigger_failure_id: Optional[str] = None) -> None:
        """Escalate to a more restrictive security state."""
        if _SECURITY_SEVERITY[target.value] <= _SECURITY_SEVERITY[self.current.value]:
            return  # already at same or higher restriction — no-op
        self._do_transition(target, trigger_failure_id)

    def de_escalate(self, target: SecurityStateEnum, authorized_by: str) -> None:
        """
        De-escalate to a less restrictive state.
        LOCKDOWN → any requires Human Override (L27).
        """
        if self.current == SecurityStateEnum.LOCKDOWN and authorized_by != "HUMAN_OVERRIDE":
            raise UnauthorizedDeEscalationError(
                "LOCKDOWN can only be released by HUMAN_OVERRIDE (L27 Override Controller)"
            )
        self._do_transition(target, authorized_by)

    def _do_transition(self, target: SecurityStateEnum, context: Optional[str]) -> None:
        self.previous = self.current
        self.current = target
        self.last_transition = datetime.utcnow()
        self.trigger_failure_id = context
        if target == SecurityStateEnum.LOCKDOWN:
            self.locked_at = datetime.utcnow()

    def allows_execution(self) -> bool:
        return self.current == SecurityStateEnum.NORMAL

    def requires_approval(self) -> bool:
        return self.current == SecurityStateEnum.RESTRICTED

    def sandbox_only(self) -> bool:
        return self.current == SecurityStateEnum.QUARANTINED

    def is_locked_down(self) -> bool:
        return self.current == SecurityStateEnum.LOCKDOWN


class UnauthorizedDeEscalationError(Exception):
    pass
