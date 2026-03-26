"""
Doctrine — K-Dexter AOS v4

Shared doctrine definitions used by both B1 (Constitutional) and B2
(Orchestration) governance layers.

Doctrine = the set of immutable principles that all layers must obey.
Doctrines are:
  - Created by L2 (Doctrine & Policy)
  - Ratified by B1 (requires Human approval via L1)
  - Read-only for B2 and A layers
  - Cannot be modified at runtime — only via B1 ratification process

Each Doctrine has:
  - A unique ID (D-xxx)
  - A severity (CONSTITUTIONAL / CRITICAL / ADVISORY)
  - A constraint expression (machine-checkable condition)
  - A human-readable description
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────── #
# Enums
# ─────────────────────────────────────────────────────────────────────────── #

class DoctrineSeverity(Enum):
    """How strictly this doctrine must be enforced."""
    CONSTITUTIONAL = "CONSTITUTIONAL"  # Violation → immediate LOCKDOWN
    CRITICAL = "CRITICAL"              # Violation → QUARANTINED + block
    ADVISORY = "ADVISORY"              # Violation → warning + log


class DoctrineStatus(Enum):
    """Lifecycle status of a doctrine."""
    DRAFT = "DRAFT"           # Proposed, not yet ratified
    RATIFIED = "RATIFIED"     # Active and enforceable
    SUSPENDED = "SUSPENDED"   # Temporarily disabled (requires B1 approval)
    RETIRED = "RETIRED"       # Permanently deactivated


class GovernanceTier(Enum):
    """Governance attribution tiers."""
    B1 = "B1"   # Constitutional Foundry
    B2 = "B2"   # Build Orchestration
    A = "A"      # Runtime Execution


class ChangeAuthority(Enum):
    """Who can authorize a change."""
    HUMAN_ONLY = "HUMAN_ONLY"   # L1 — machine cannot change
    B1_RATIFY = "B1_RATIFY"     # Requires B1 ratification
    B2_APPROVE = "B2_APPROVE"   # B2 approval sufficient
    A_RUNTIME = "A_RUNTIME"     # A layer can change (evidence required)


# ─────────────────────────────────────────────────────────────────────────── #
# Data models
# ─────────────────────────────────────────────────────────────────────────── #

@dataclass(frozen=True)
class DoctrineArticle:
    """A single doctrine article — one enforceable principle."""
    doctrine_id: str                          # "D-001", "D-002", ...
    name: str                                 # short name
    description: str                          # what it enforces
    severity: DoctrineSeverity
    constraint: str                           # machine-checkable expression
    ratified_by: str = "L1"                   # who ratified (always L1/Human)
    ratified_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: DoctrineStatus = DoctrineStatus.RATIFIED
    related_mandatory: list[str] = field(default_factory=list)  # M-xx refs


@dataclass
class DoctrineViolation:
    """Record of a doctrine violation."""
    violation_id: str = field(default_factory=lambda: f"DV-{uuid.uuid4().hex[:8].upper()}")
    doctrine_id: str = ""
    violated_by: str = ""           # layer or actor that violated
    severity: DoctrineSeverity = DoctrineSeverity.ADVISORY
    description: str = ""
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    context: dict = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────── #
# Built-in Doctrines (Constitutional — cannot be changed at runtime)
# ─────────────────────────────────────────────────────────────────────────── #

_CORE_DOCTRINES: list[DoctrineArticle] = [
    DoctrineArticle(
        doctrine_id="D-001",
        name="TCL-only execution",
        description="All exchange interactions must go through TCL. "
                    "No layer may call exchange APIs directly.",
        severity=DoctrineSeverity.CONSTITUTIONAL,
        constraint="exchange_call.via_tcl == True",
        related_mandatory=["M-07"],
    ),
    DoctrineArticle(
        doctrine_id="D-002",
        name="Evidence on every change",
        description="Every state transition, gate evaluation, and TCL command "
                    "must produce an EvidenceBundle (M-07).",
        severity=DoctrineSeverity.CONSTITUTIONAL,
        constraint="evidence_bundle_count >= expected_evidence_count",
        related_mandatory=["M-07"],
    ),
    DoctrineArticle(
        doctrine_id="D-003",
        name="Provenance required",
        description="Every Rule Ledger write must include RuleProvenance (M-10). "
                    "No anonymous rule changes permitted.",
        severity=DoctrineSeverity.CONSTITUTIONAL,
        constraint="rule_change.provenance is not None",
        related_mandatory=["M-10"],
    ),
    DoctrineArticle(
        doctrine_id="D-004",
        name="Human-only LOCKDOWN release",
        description="Only L27 Override Controller (Human) can de-escalate LOCKDOWN. "
                    "No automated process may release LOCKDOWN state.",
        severity=DoctrineSeverity.CONSTITUTIONAL,
        constraint="lockdown_release.authorized_by == 'L27_HUMAN'",
    ),
    DoctrineArticle(
        doctrine_id="D-005",
        name="B1 immutability",
        description="B1 layer code and doctrines cannot be modified by B2 or A. "
                    "Only Human (L1) can ratify changes to B1.",
        severity=DoctrineSeverity.CONSTITUTIONAL,
        constraint="b1_modification.requester == 'L1'",
    ),
    DoctrineArticle(
        doctrine_id="D-006",
        name="Recovery loop ceiling",
        description="Recovery Loop may attempt at most 3 recoveries per incident. "
                    "Exceeding requires Human Override.",
        severity=DoctrineSeverity.CRITICAL,
        constraint="recovery_attempts_per_incident <= 3",
        related_mandatory=["M-14"],
    ),
    DoctrineArticle(
        doctrine_id="D-007",
        name="Intent clarification mandatory",
        description="No execution may begin without explicit intent clarification (M-01). "
                    "CLARIFYING state must set intent before proceeding.",
        severity=DoctrineSeverity.CRITICAL,
        constraint="work_state.intent != ''",
        related_mandatory=["M-01"],
    ),
    DoctrineArticle(
        doctrine_id="D-008",
        name="Risk check before execution",
        description="Risk assessment (M-03) must complete before VALIDATING state. "
                    "No execution without risk clearance.",
        severity=DoctrineSeverity.CRITICAL,
        constraint="work_state.risk_checked == True",
        related_mandatory=["M-03"],
    ),
    DoctrineArticle(
        doctrine_id="D-009",
        name="Forbidden action zero tolerance",
        description="Forbidden Ledger violations with LOCKDOWN severity trigger "
                    "immediate system lockdown. No exceptions.",
        severity=DoctrineSeverity.CONSTITUTIONAL,
        constraint="forbidden_violation.severity != 'LOCKDOWN' or "
                   "security_state == 'LOCKDOWN'",
    ),
    DoctrineArticle(
        doctrine_id="D-010",
        name="Concurrent write serialization",
        description="All Rule Ledger writes must be serialized via RuleLedgerLock. "
                    "No concurrent writes from multiple loops.",
        severity=DoctrineSeverity.CRITICAL,
        constraint="rule_ledger_lock.held_by is not None",
        related_mandatory=["M-10"],
    ),
]


# ─────────────────────────────────────────────────────────────────────────── #
# Doctrine Registry
# ─────────────────────────────────────────────────────────────────────────── #

class DoctrineRegistry:
    """
    Immutable registry of all active doctrines.

    Core doctrines (D-001~D-010) are loaded at init and cannot be removed.
    Additional doctrines can be ratified through B1 ratification process.
    """

    def __init__(self) -> None:
        self._doctrines: dict[str, DoctrineArticle] = {}
        self._violations: list[DoctrineViolation] = []

        # Load core doctrines
        for d in _CORE_DOCTRINES:
            self._doctrines[d.doctrine_id] = d

    # ── Read operations ──────────────────────────────────────────────────── #

    def get(self, doctrine_id: str) -> Optional[DoctrineArticle]:
        return self._doctrines.get(doctrine_id)

    def list_all(self, status: Optional[DoctrineStatus] = None) -> list[DoctrineArticle]:
        if status is None:
            return list(self._doctrines.values())
        return [d for d in self._doctrines.values() if d.status == status]

    def list_by_severity(self, severity: DoctrineSeverity) -> list[DoctrineArticle]:
        return [d for d in self._doctrines.values()
                if d.severity == severity and d.status == DoctrineStatus.RATIFIED]

    def count(self) -> int:
        return len(self._doctrines)

    def is_ratified(self, doctrine_id: str) -> bool:
        d = self._doctrines.get(doctrine_id)
        return d is not None and d.status == DoctrineStatus.RATIFIED

    # ── Ratification (B1 only) ───────────────────────────────────────────── #

    def ratify(self, article: DoctrineArticle, ratified_by: str = "L1") -> str:
        """
        Ratify a new doctrine. Only callable by B1 (L1/L2).
        Raises ValueError if ratified_by is not B1 authority.
        """
        if ratified_by not in ("L1", "L2", "B1"):
            raise DoctrineRatificationError(
                f"Only B1 authority (L1/L2) can ratify doctrines. Got: {ratified_by}"
            )
        self._doctrines[article.doctrine_id] = article
        return article.doctrine_id

    # ── Violation recording ──────────────────────────────────────────────── #

    def record_violation(self, violation: DoctrineViolation) -> str:
        self._violations.append(violation)
        return violation.violation_id

    def list_violations(self, doctrine_id: Optional[str] = None) -> list[DoctrineViolation]:
        if doctrine_id is None:
            return list(self._violations)
        return [v for v in self._violations if v.doctrine_id == doctrine_id]

    def violation_count(self) -> int:
        return len(self._violations)

    # ── Compliance check ─────────────────────────────────────────────────── #

    def check_compliance(self, context: dict) -> list[DoctrineViolation]:
        """
        Check a context dict against all ratified doctrines.
        Returns list of violations found (empty = compliant).

        NOTE: constraint evaluation is currently pattern-based.
        Full expression evaluation will be implemented with Rule Engine.
        """
        violations = []
        for d in self._doctrines.values():
            if d.status != DoctrineStatus.RATIFIED:
                continue
            if not self._evaluate_constraint(d, context):
                v = DoctrineViolation(
                    doctrine_id=d.doctrine_id,
                    violated_by=context.get("actor", "UNKNOWN"),
                    severity=d.severity,
                    description=f"Violated: {d.name} — {d.description}",
                    context=context,
                )
                violations.append(v)
                self._violations.append(v)
        return violations

    @staticmethod
    def _evaluate_constraint(doctrine: DoctrineArticle, context: dict) -> bool:
        """
        Evaluate a doctrine constraint against context.
        Returns True if constraint is satisfied (no violation).

        Current implementation: key-based checks for known constraints.
        Future: DSL expression evaluator.
        """
        c = doctrine.constraint

        # D-001: TCL-only
        if "exchange_call.via_tcl" in c:
            return context.get("via_tcl", True)

        # D-002: evidence count
        if "evidence_bundle_count" in c:
            actual = context.get("evidence_bundle_count", 0)
            expected = context.get("expected_evidence_count", 0)
            return actual >= expected

        # D-003: provenance
        if "rule_change.provenance" in c:
            return context.get("provenance") is not None

        # D-004: lockdown release
        if "lockdown_release.authorized_by" in c:
            return context.get("lockdown_release_by", "L27_HUMAN") == "L27_HUMAN"

        # D-005: B1 immutability
        if "b1_modification.requester" in c:
            return context.get("modification_requester", "L1") == "L1"

        # D-006: recovery ceiling
        if "recovery_attempts_per_incident" in c:
            return context.get("recovery_attempts", 0) <= 3

        # D-007: intent
        if "work_state.intent" in c:
            return bool(context.get("intent", ""))

        # D-008: risk check
        if "work_state.risk_checked" in c:
            return context.get("risk_checked", False)

        # D-009: forbidden violation
        if "forbidden_violation.severity" in c:
            sev = context.get("forbidden_severity")
            sec = context.get("security_state", "NORMAL")
            if sev == "LOCKDOWN":
                return sec == "LOCKDOWN"
            return True

        # D-010: concurrent write lock
        if "rule_ledger_lock.held_by" in c:
            return context.get("lock_held", True)

        # Unknown constraint — pass by default (fail-open for unknown)
        return True


# ─────────────────────────────────────────────────────────────────────────── #
# Exceptions
# ─────────────────────────────────────────────────────────────────────────── #

class DoctrineRatificationError(Exception):
    """Raised when an unauthorized entity attempts to ratify a doctrine."""
    pass
