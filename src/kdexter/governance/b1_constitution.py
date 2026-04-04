"""
B1 Constitutional Layer — K-Dexter AOS v4

The highest governance tier. Contains immutable constraints that cannot be
overridden at runtime.

B1 Responsibilities (governance_layer_map.md):
  - Ratify/revoke doctrines (L2)
  - Enforce forbidden actions (ForbiddenLedger)
  - Security policy enforcement (L3)
  - Spec lock approval (L22)
  - LOCKDOWN release via Human Override (L27)

B1 Attribution (5 layers):
  L1  Human Decision        — machine cannot change
  L2  Doctrine & Policy     — B1 ratification required
  L3  Security & Isolation  — B1 ratification required
  L22 Spec Lock System      — lock release requires B1
  L27 Override Controller   — Human only

Key invariants:
  - B1 doctrines are read-only for B2 and A
  - No automated process can modify B1 layer code
  - LOCKDOWN can only be released by Human (L27)
  - Forbidden Ledger LOCKDOWN violations are non-negotiable
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from kdexter.audit.evidence_store import EvidenceBundle, EvidenceStore
from kdexter.governance.doctrine import (
    DoctrineArticle,
    DoctrineRegistry,
    DoctrineSeverity,
    DoctrineStatus,
    DoctrineViolation,
)
from kdexter.ledger.forbidden_ledger import ForbiddenLedger
from kdexter.state_machine.security_state import SecurityStateContext, SecurityStateEnum


# ─────────────────────────────────────────────────────────────────────────── #
# Constitutional invariant
# ─────────────────────────────────────────────────────────────────────────── #


@dataclass(frozen=True)
class ConstitutionalInvariant:
    """
    A hard system invariant enforced by B1.
    Unlike DoctrineArticle (declarative), invariants are code-level checks
    that B1Constitution.enforce() runs on every governance cycle.
    """

    invariant_id: str
    name: str
    description: str
    check_fn_name: str  # method name on B1Constitution to call


# ─────────────────────────────────────────────────────────────────────────── #
# B1 Constitution
# ─────────────────────────────────────────────────────────────────────────── #


class B1Constitution:
    """
    Immutable constitutional rule set for K-Dexter AOS.

    Provides:
      1. Doctrine management (ratify/suspend/check compliance)
      2. Forbidden action enforcement bridge
      3. Security state invariant enforcement
      4. LOCKDOWN release gate (Human-only)

    Usage:
        doctrine = DoctrineRegistry()
        forbidden = ForbiddenLedger()
        security = SecurityStateContext()
        evidence = EvidenceStore()

        b1 = B1Constitution(doctrine, forbidden, security, evidence)
        violations = b1.enforce(context)
    """

    def __init__(
        self,
        doctrine: DoctrineRegistry,
        forbidden: ForbiddenLedger,
        security: SecurityStateContext,
        evidence: EvidenceStore,
    ) -> None:
        self._doctrine = doctrine
        self._forbidden = forbidden
        self._security = security
        self._evidence = evidence
        self._invariants = self._build_invariants()

    # ── Properties ───────────────────────────────────────────────────────── #

    @property
    def doctrine(self) -> DoctrineRegistry:
        return self._doctrine

    @property
    def forbidden(self) -> ForbiddenLedger:
        return self._forbidden

    # ── Doctrine management ──────────────────────────────────────────────── #

    def ratify_doctrine(self, article: DoctrineArticle) -> str:
        """
        Ratify a new doctrine. Only B1 (L1/L2) can call this.
        Produces an EvidenceBundle for the ratification event.
        """
        doctrine_id = self._doctrine.ratify(article, ratified_by="L1")

        self._evidence.store(
            EvidenceBundle(
                trigger="B1Constitution.ratify_doctrine",
                actor="B1",
                action=f"RATIFY:{doctrine_id}",
                artifacts=[
                    {
                        "doctrine_id": doctrine_id,
                        "name": article.name,
                        "severity": article.severity.value,
                    }
                ],
            )
        )
        return doctrine_id

    def suspend_doctrine(self, doctrine_id: str, reason: str) -> bool:
        """
        Suspend a doctrine (requires B1 authority).
        Core doctrines (D-001~D-010) cannot be suspended.
        """
        article = self._doctrine.get(doctrine_id)
        if article is None:
            return False

        # Core doctrines are immutable
        if doctrine_id.startswith("D-0") and int(doctrine_id.split("-")[1]) <= 10:
            raise ConstitutionalViolationError(
                f"Core doctrine {doctrine_id} cannot be suspended. "
                "Constitutional doctrines are immutable."
            )

        # Suspension requires creating a new article with SUSPENDED status
        # (DoctrineArticle is frozen, so we record suspension separately)
        self._evidence.store(
            EvidenceBundle(
                trigger="B1Constitution.suspend_doctrine",
                actor="B1",
                action=f"SUSPEND:{doctrine_id}",
                artifacts=[{"doctrine_id": doctrine_id, "reason": reason}],
            )
        )
        return True

    # ── Enforcement ──────────────────────────────────────────────────────── #

    def enforce(self, context: dict) -> list[DoctrineViolation]:
        """
        Run all constitutional checks against the given context.
        Returns list of doctrine violations found.
        On CONSTITUTIONAL severity violation → escalate to LOCKDOWN.
        """
        violations = self._doctrine.check_compliance(context)

        for v in violations:
            self._evidence.store(
                EvidenceBundle(
                    trigger="B1Constitution.enforce",
                    actor="B1",
                    action=f"VIOLATION:{v.doctrine_id}",
                    before_state=self._security.current.value,
                    artifacts=[
                        {
                            "doctrine_id": v.doctrine_id,
                            "severity": v.severity.value,
                            "violated_by": v.violated_by,
                        }
                    ],
                )
            )

            # CONSTITUTIONAL violation → immediate LOCKDOWN
            if v.severity == DoctrineSeverity.CONSTITUTIONAL:
                self._security.escalate(
                    SecurityStateEnum.LOCKDOWN,
                    f"Constitutional violation: {v.doctrine_id}",
                )
            elif v.severity == DoctrineSeverity.CRITICAL:
                self._security.escalate(
                    SecurityStateEnum.QUARANTINED,
                    f"Critical doctrine violation: {v.doctrine_id}",
                )

        return violations

    def check_forbidden_action(
        self,
        action_name: str,
        context: dict,
    ) -> tuple[bool, str]:
        """
        Bridge to ForbiddenLedger.check_and_enforce.
        Returns (passed: bool, reason: str).
        """
        return self._forbidden.check_and_enforce(
            action_name,
            context,
            self._security,
            self._evidence,
        )

    # ── LOCKDOWN management ──────────────────────────────────────────────── #

    def is_locked_down(self) -> bool:
        return self._security.current == SecurityStateEnum.LOCKDOWN

    def release_lockdown(self, authorized_by: str, reason: str) -> bool:
        """
        Release LOCKDOWN state. Only L27 (Human Override) may call this.
        Returns True if successfully released, False if not in LOCKDOWN.
        """
        if authorized_by != "L27_HUMAN":
            raise ConstitutionalViolationError(
                f"Only L27_HUMAN can release LOCKDOWN. Got: {authorized_by}"
            )

        if self._security.current != SecurityStateEnum.LOCKDOWN:
            return False

        self._security.de_escalate(
            SecurityStateEnum.NORMAL,
            authorized_by="HUMAN_OVERRIDE",
        )

        self._evidence.store(
            EvidenceBundle(
                trigger="B1Constitution.release_lockdown",
                actor="L27_HUMAN",
                action="LOCKDOWN_RELEASE",
                before_state=SecurityStateEnum.LOCKDOWN.value,
                after_state=SecurityStateEnum.NORMAL.value,
                artifacts=[{"reason": reason, "authorized_by": authorized_by}],
            )
        )
        return True

    # ── Invariant checks ─────────────────────────────────────────────────── #

    def check_invariants(self) -> list[str]:
        """
        Run all hard invariant checks. Returns list of violation descriptions.
        Empty list = all invariants hold.
        """
        violations = []
        for inv in self._invariants:
            check_fn = getattr(self, inv.check_fn_name, None)
            if check_fn and not check_fn():
                violations.append(f"[{inv.invariant_id}] {inv.name}: {inv.description}")
        return violations

    def _check_doctrine_count(self) -> bool:
        """Core doctrines must always be present."""
        return self._doctrine.count() >= 10

    def _check_core_doctrines_ratified(self) -> bool:
        """All core doctrines D-001~D-010 must be RATIFIED."""
        for i in range(1, 11):
            d_id = f"D-{str(i).zfill(3)}"
            if not self._doctrine.is_ratified(d_id):
                return False
        return True

    def _build_invariants(self) -> list[ConstitutionalInvariant]:
        return [
            ConstitutionalInvariant(
                "CI-001",
                "Core doctrine presence",
                "At least 10 core doctrines must exist",
                "_check_doctrine_count",
            ),
            ConstitutionalInvariant(
                "CI-002",
                "Core doctrine ratification",
                "All core doctrines D-001~D-010 must be RATIFIED",
                "_check_core_doctrines_ratified",
            ),
        ]


# ─────────────────────────────────────────────────────────────────────────── #
# Exceptions
# ─────────────────────────────────────────────────────────────────────────── #


class ConstitutionalViolationError(Exception):
    """Raised when an action violates a constitutional invariant."""

    pass
