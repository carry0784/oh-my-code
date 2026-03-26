"""
Rule Ledger — K-Dexter AOS v4

Single source of truth for all active rules.
CRITICAL: Concurrent writes from 4 loops must be serialized via RuleLedgerLock.

Features:
  - Rule CRUD with async write locking
  - M-10 provenance enforcement (no provenance → ProvenanceRequiredError)
  - Rule change count tracking (for IntentDriftEngine.rule_change_count)
  - Full change history with before/after snapshots
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

from kdexter.loops.concurrency import LoopPriority, RuleLedgerLock


# ─────────────────────────────────────────────────────────────────────────── #
# Data models
# ─────────────────────────────────────────────────────────────────────────── #

@dataclass
class RuleProvenance:
    """
    M-10: provenance record for a rule change.
    Required for every create/update/delete operation.
    """
    source_incident: str        # incident ID that caused this rule
    author_layer: str           # "L5", "L13", "RecoveryLoop", etc.
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    rationale: str = ""         # why this rule was created/changed


@dataclass
class Rule:
    """A single rule in the Rule Ledger."""
    rule_id: str = field(default_factory=lambda: f"R-{uuid.uuid4().hex[:8].upper()}")
    name: str = ""
    condition: str = ""         # rule condition (DSL or text)
    action: str = ""            # rule action
    priority: int = 0
    enabled: bool = True
    provenance: Optional[RuleProvenance] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1

    def to_snapshot(self) -> dict:
        """Produce a serializable snapshot for change history."""
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "condition": self.condition,
            "action": self.action,
            "priority": self.priority,
            "enabled": self.enabled,
            "version": self.version,
        }


@dataclass
class RuleChangeRecord:
    """Audit record for a single rule change."""
    change_id: str = field(default_factory=lambda: f"RC-{uuid.uuid4().hex[:8].upper()}")
    rule_id: str = ""
    change_type: str = ""       # "CREATE" | "UPDATE" | "DELETE"
    provenance: Optional[RuleProvenance] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    before_snapshot: Optional[dict] = None
    after_snapshot: Optional[dict] = None


# ─────────────────────────────────────────────────────────────────────────── #
# Exceptions
# ─────────────────────────────────────────────────────────────────────────── #

class ProvenanceRequiredError(Exception):
    """M-10: provenance is required for all Rule Ledger writes."""
    pass


class RuleNotFoundError(Exception):
    """Rule not found in the ledger."""
    pass


# ─────────────────────────────────────────────────────────────────────────── #
# Rule Ledger
# ─────────────────────────────────────────────────────────────────────────── #

class RuleLedger:
    """
    Single source of truth for all active rules.

    All write operations (create/update/delete) require:
      1. RuleLedgerLock acquisition (via LoopPriority)
      2. Valid RuleProvenance (M-10)

    Read operations do not require the lock.

    Usage:
        lock = RuleLedgerLock()
        ledger = RuleLedger(lock)

        rule = Rule(name="max_loss", condition="loss > 0.05", action="BLOCK")
        rule.provenance = RuleProvenance(
            source_incident="INC-001",
            author_layer="L5",
            rationale="Max loss threshold rule",
        )
        rule_id = await ledger.create(rule, LoopPriority.MAIN)
    """

    def __init__(self, lock: RuleLedgerLock) -> None:
        self._lock = lock
        self._rules: dict[str, Rule] = {}
        self._changes: list[RuleChangeRecord] = []

    # ── Read operations (no lock required) ────────────────────────────── #

    def read(self, rule_id: str) -> Optional[Rule]:
        """Get a single rule by ID. Returns None if not found."""
        return self._rules.get(rule_id)

    def list_all(self, enabled_only: bool = True) -> list[Rule]:
        """List all rules, optionally filtering by enabled status."""
        if enabled_only:
            return [r for r in self._rules.values() if r.enabled]
        return list(self._rules.values())

    def rule_change_count(self, since: Optional[datetime] = None) -> int:
        """
        Count rule changes since a given timestamp.
        Used by IntentDriftEngine to measure rule drift.
        """
        if since is None:
            return len(self._changes)
        return sum(1 for c in self._changes if c.timestamp >= since)

    def change_history(self, rule_id: Optional[str] = None) -> list[RuleChangeRecord]:
        """Get change history, optionally filtered by rule_id."""
        if rule_id is None:
            return list(self._changes)
        return [c for c in self._changes if c.rule_id == rule_id]

    # ── Write operations (lock required + provenance required) ────────── #

    async def create(self, rule: Rule, requester: LoopPriority) -> str:
        """
        Create a new rule. Acquires lock, enforces M-10 provenance.
        Returns rule_id.
        """
        self._enforce_provenance(rule.provenance)

        await self._lock.acquire(requester)
        try:
            self._rules[rule.rule_id] = rule
            self._record_change(
                rule_id=rule.rule_id,
                change_type="CREATE",
                provenance=rule.provenance,
                after_snapshot=rule.to_snapshot(),
            )
        finally:
            self._lock.release()

        return rule.rule_id

    async def update(
        self,
        rule_id: str,
        updates: dict,
        provenance: RuleProvenance,
        requester: LoopPriority,
    ) -> Rule:
        """
        Update an existing rule. Acquires lock, enforces M-10 provenance.
        Returns updated Rule.
        """
        self._enforce_provenance(provenance)

        await self._lock.acquire(requester)
        try:
            rule = self._rules.get(rule_id)
            if rule is None:
                raise RuleNotFoundError(f"Rule {rule_id} not found")

            before = rule.to_snapshot()

            for key, value in updates.items():
                if hasattr(rule, key) and key not in ("rule_id", "created_at"):
                    setattr(rule, key, value)

            rule.provenance = provenance
            rule.updated_at = datetime.now(timezone.utc)
            rule.version += 1

            self._record_change(
                rule_id=rule_id,
                change_type="UPDATE",
                provenance=provenance,
                before_snapshot=before,
                after_snapshot=rule.to_snapshot(),
            )
        finally:
            self._lock.release()

        return rule

    async def delete(
        self,
        rule_id: str,
        provenance: RuleProvenance,
        requester: LoopPriority,
    ) -> None:
        """
        Soft-delete a rule (disable it). Acquires lock, enforces M-10 provenance.
        """
        self._enforce_provenance(provenance)

        await self._lock.acquire(requester)
        try:
            rule = self._rules.get(rule_id)
            if rule is None:
                raise RuleNotFoundError(f"Rule {rule_id} not found")

            before = rule.to_snapshot()
            rule.enabled = False
            rule.updated_at = datetime.now(timezone.utc)
            rule.version += 1

            self._record_change(
                rule_id=rule_id,
                change_type="DELETE",
                provenance=provenance,
                before_snapshot=before,
                after_snapshot=rule.to_snapshot(),
            )
        finally:
            self._lock.release()

    # ── Internal ──────────────────────────────────────────────────────── #

    @staticmethod
    def _enforce_provenance(provenance: Optional[RuleProvenance]) -> None:
        """M-10: reject writes without provenance."""
        if provenance is None:
            raise ProvenanceRequiredError(
                "M-10: RuleProvenance is required for all Rule Ledger writes. "
                "Provide source_incident, author_layer, and rationale."
            )

    def _record_change(
        self,
        rule_id: str,
        change_type: str,
        provenance: Optional[RuleProvenance],
        before_snapshot: Optional[dict] = None,
        after_snapshot: Optional[dict] = None,
    ) -> None:
        """Record a change in the change history."""
        self._changes.append(RuleChangeRecord(
            rule_id=rule_id,
            change_type=change_type,
            provenance=provenance,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
        ))
