"""
Forbidden Ledger — K-Dexter AOS v4

Actions that are never permitted regardless of state.
Violation triggers immediate LOCKDOWN or BLOCKED.

Used by VALIDATING [1] FORBIDDEN_CHECK in the Main Loop.
Violations produce EvidenceBundles for audit trail.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from kdexter.audit.evidence_store import EvidenceBundle, EvidenceStore
from kdexter.state_machine.security_state import SecurityStateContext, SecurityStateEnum


# ─────────────────────────────────────────────────────────────────────────── #
# Data models
# ─────────────────────────────────────────────────────────────────────────── #


@dataclass(frozen=True)
class ForbiddenAction:
    """A registered forbidden action."""

    action_id: str  # "FA-001", "FA-002", ...
    description: str  # what is forbidden
    severity: str  # "LOCKDOWN" | "BLOCKED"
    pattern: str  # action name pattern to match
    registered_by: str  # author layer (e.g. "B1", "L3")
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ForbiddenViolation:
    """Record of a detected forbidden action violation."""

    violation_id: str = field(default_factory=lambda: f"FV-{uuid.uuid4().hex[:8].upper()}")
    action_id: str = ""  # which ForbiddenAction was violated
    action_pattern: str = ""
    detected_action: str = ""  # what the system tried to do
    severity: str = ""
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    context: dict = field(default_factory=dict)
    evidence_bundle_id: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────── #
# Forbidden Ledger
# ─────────────────────────────────────────────────────────────────────────── #


class ForbiddenLedger:
    """
    Registry of forbidden actions + violation detection.

    Usage:
        ledger = ForbiddenLedger()
        ledger.register(ForbiddenAction(
            action_id="FA-001",
            description="Direct exchange API call from upper layer",
            severity="LOCKDOWN",
            pattern="DIRECT_API_CALL",
            registered_by="B1",
        ))

        # VALIDATING [1] check:
        passed, reason = ledger.check_and_enforce(
            action_name="DIRECT_API_CALL",
            context={...},
            security_ctx=security_state,
            evidence_store=store,
        )
    """

    def __init__(self) -> None:
        self._actions: dict[str, ForbiddenAction] = {}
        self._violations: list[ForbiddenViolation] = []

    # ── Registration ──────────────────────────────────────────────────── #

    def register(self, action: ForbiddenAction) -> None:
        """Register a forbidden action.

        Idempotent by key overwrite: repeated registration with the same
        action_id converges to one final mapping. Safe to call multiple times.
        """
        self._actions[action.action_id] = action

    def unregister(self, action_id: str) -> None:
        """
        Remove a forbidden action. Requires B1 approval.
        Caller is responsible for verifying B1 authorization.
        """
        self._actions.pop(action_id, None)

    def list_actions(self) -> list[ForbiddenAction]:
        """List all registered forbidden actions."""
        return list(self._actions.values())

    # ── Violation detection ───────────────────────────────────────────── #

    def check(self, action_name: str) -> Optional[ForbiddenAction]:
        """
        Check if action_name matches any forbidden action pattern.
        Returns the matched ForbiddenAction, or None if no violation.
        """
        for fa in self._actions.values():
            if self._matches(fa.pattern, action_name):
                return fa
        return None

    def check_and_enforce(
        self,
        action_name: str,
        context: dict,
        security_ctx: SecurityStateContext,
        evidence_store: EvidenceStore,
    ) -> tuple[bool, str]:
        """
        VALIDATING [1] FORBIDDEN_CHECK interface.
        Returns (passed: bool, reason: str).

        On violation:
          - Records violation
          - Produces EvidenceBundle
          - Escalates SecurityState (LOCKDOWN or QUARANTINED)
        """
        matched = self.check(action_name)
        if matched is None:
            return True, ""

        # Record violation
        bundle = EvidenceBundle(
            trigger=f"ForbiddenLedger.violation",
            actor="ForbiddenLedger",
            action=f"VIOLATION:{matched.action_id}",
            before_state=security_ctx.current.value,
            artifacts=[
                {
                    "action_id": matched.action_id,
                    "pattern": matched.pattern,
                    "detected_action": action_name,
                    "severity": matched.severity,
                    "context": context,
                }
            ],
        )
        bundle_id = evidence_store.store(bundle)

        violation = ForbiddenViolation(
            action_id=matched.action_id,
            action_pattern=matched.pattern,
            detected_action=action_name,
            severity=matched.severity,
            context=context,
            evidence_bundle_id=bundle_id,
        )
        self._violations.append(violation)

        # Escalate security state
        if matched.severity == "LOCKDOWN":
            security_ctx.escalate(SecurityStateEnum.LOCKDOWN, matched.action_id)
        else:
            security_ctx.escalate(SecurityStateEnum.QUARANTINED, matched.action_id)

        bundle.after_state = security_ctx.current.value

        return False, (
            f"Forbidden action [{matched.action_id}] detected: "
            f"{matched.description} (severity={matched.severity})"
        )

    # ── Violation history ─────────────────────────────────────────────── #

    def list_violations(self) -> list[ForbiddenViolation]:
        """List all recorded violations."""
        return list(self._violations)

    def violation_count(self) -> int:
        """Total violation count."""
        return len(self._violations)

    # ── Internal ──────────────────────────────────────────────────────── #

    @staticmethod
    def _matches(pattern: str, action_name: str) -> bool:
        """
        Simple pattern matching.
        Exact match or prefix match with wildcard (*).
        """
        if pattern == action_name:
            return True
        if pattern.endswith("*") and action_name.startswith(pattern[:-1]):
            return True
        return False
