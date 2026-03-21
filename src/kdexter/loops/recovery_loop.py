"""
Recovery Loop — K-Dexter AOS

Phases: Isolate → Replay → Rollback → Repair → Resume

Triggered by (from failure_taxonomy.md):
  - INFRA failures (all severities except LOW)
  - STRATEGY CRITICAL
  - GOVERNANCE CRITICAL / HIGH

Mandatory items applied (Recovery Loop exempts M-01,02,05,06,11,12,13,15,17,18):
  M-03 risk check, M-04 security check, M-07 evidence (always),
  M-08 budget check, M-09 compliance check, M-10 provenance (always),
  M-14 trust refresh, M-16 completion check

Concurrent Recovery: merge new failures into active recovery scope (no parallel instances).
rollback anchor: last VERIFIED state (OQ-8 — placeholder until v4 confirms).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from kdexter.audit.evidence_store import EvidenceBundle, EvidenceStore
from kdexter.loops.concurrency import LoopPriority, RuleLedgerLock, LoopPriorityQueue
from kdexter.state_machine.security_state import SecurityStateContext, SecurityStateEnum
from kdexter.state_machine.work_state import WorkStateContext, WorkStateEnum


class RecoveryPhase(Enum):
    IDLE = "IDLE"
    ISOLATE = "ISOLATE"
    REPLAY = "REPLAY"
    ROLLBACK = "ROLLBACK"
    REPAIR = "REPAIR"
    RESUME = "RESUME"
    FAILED = "FAILED"       # recovery itself failed — Human Override required


@dataclass
class FailureEvent:
    """A Failure event routed to the Recovery Loop."""
    failure_id: str
    failure_type_id: str        # e.g. F-I-001, F-S-006, F-G-001
    domain: str                 # INFRA / STRATEGY / GOVERNANCE
    severity: str               # CRITICAL / HIGH / MEDIUM / LOW
    recurrence: str             # FIRST / REPEAT / PATTERN
    description: str
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    context: dict = field(default_factory=dict)


@dataclass
class RecoveryScope:
    """
    Tracks all failures being handled in the current recovery session.
    New failures are merged into the active scope (no parallel Recovery instances).
    """
    scope_id: str
    failures: list[FailureEvent] = field(default_factory=list)
    opened_at: datetime = field(default_factory=datetime.utcnow)
    rollback_anchor: Optional[str] = None   # OQ-8: last VERIFIED state id (placeholder)
    repair_notes: list[str] = field(default_factory=list)

    def merge(self, event: FailureEvent) -> None:
        self.failures.append(event)

    @property
    def highest_severity(self) -> str:
        order = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
        for sev in order:
            if any(f.severity == sev for f in self.failures):
                return sev
        return "LOW"


class RecoveryLoop:
    """
    Recovery Loop — handles INFRA/CRITICAL/GOVERNANCE failures.
    Single instance — concurrent failures are merged, not parallelized.
    """

    def __init__(
        self,
        work_state: WorkStateContext,
        security_state: SecurityStateContext,
        evidence_store: EvidenceStore,
        rule_ledger_lock: RuleLedgerLock,
        loop_queue: LoopPriorityQueue,
    ) -> None:
        self._work = work_state
        self._security = security_state
        self._evidence = evidence_store
        self._lock = rule_ledger_lock
        self._queue = loop_queue

        self._phase = RecoveryPhase.IDLE
        self._scope: Optional[RecoveryScope] = None
        self._active = False

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def current_phase(self) -> RecoveryPhase:
        return self._phase

    def accept_failure(self, event: FailureEvent) -> None:
        """
        Accept a new failure event.
        If recovery already active, merge into current scope.
        If not active, open a new scope and start recovery.
        """
        if self._scope is not None:
            # Concurrent failure — merge into active scope (Section 3.2)
            self._scope.merge(event)
            self._emit_evidence("FAILURE_MERGED", {
                "failure_id": event.failure_id,
                "scope_id": self._scope.scope_id,
            })
        else:
            scope_id = f"REC-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
            self._scope = RecoveryScope(
                scope_id=scope_id,
                failures=[event],
                rollback_anchor=self._capture_rollback_anchor(),
            )

    async def run(self) -> None:
        """
        Execute full recovery cycle: Isolate → Replay → Rollback → Repair → Resume.
        Acquires Rule Ledger Write Lock at highest priority (RECOVERY = 0).
        """
        if self._scope is None:
            return

        self._active = True
        self._queue.mark_active(LoopPriority.RECOVERY)

        try:
            await self._phase_isolate()
            await self._phase_replay()
            await self._phase_rollback()
            await self._phase_repair()
            await self._phase_resume()
        except RecoveryFailedError as exc:
            self._phase = RecoveryPhase.FAILED
            self._emit_evidence("RECOVERY_FAILED", {"reason": str(exc)})
            # Human Override required — do not swallow the exception
            raise
        finally:
            self._active = False
            self._queue.mark_inactive(LoopPriority.RECOVERY)
            self._scope = None

    # ------------------------------------------------------------------ #
    # Recovery Phases
    # ------------------------------------------------------------------ #

    async def _phase_isolate(self) -> None:
        """
        Phase 1 — Isolate.
        Transition Work State → ISOLATED.
        Escalate Security State based on highest severity.
        """
        self._phase = RecoveryPhase.ISOLATE
        scope = self._scope

        # Work state transition
        self._work.transition_to(WorkStateEnum.ISOLATED, reason=f"Recovery scope {scope.scope_id}")

        # Security state escalation (failure_taxonomy.md Section 5)
        if scope.highest_severity == "CRITICAL":
            self._security.escalate(SecurityStateEnum.LOCKDOWN, scope.scope_id)
        elif scope.highest_severity == "HIGH":
            self._security.escalate(SecurityStateEnum.QUARANTINED, scope.scope_id)
        else:
            self._security.escalate(SecurityStateEnum.RESTRICTED, scope.scope_id)

        self._emit_evidence("ISOLATE_COMPLETE", {
            "scope_id": scope.scope_id,
            "failure_count": len(scope.failures),
            "highest_severity": scope.highest_severity,
            "work_state": self._work.current.value,
            "security_state": self._security.current.value,
        })

    async def _phase_replay(self) -> None:
        """
        Phase 2 — Replay.
        Transition Work State → REPLAY.
        Reproduce failure conditions for root cause analysis.
        """
        self._phase = RecoveryPhase.REPLAY
        self._work.transition_to(WorkStateEnum.REPLAY)

        # M-07: evidence required
        self._emit_evidence("REPLAY_STARTED", {
            "scope_id": self._scope.scope_id,
            "failure_ids": [f.failure_id for f in self._scope.failures],
        })

        # TODO: implement actual replay logic (connect to ReplayAuditor / SnapshotAuditor)
        await asyncio.sleep(0)  # placeholder for async replay

        self._work.transition_to(WorkStateEnum.ROOT_CAUSE)
        self._emit_evidence("REPLAY_COMPLETE", {"scope_id": self._scope.scope_id})

    async def _phase_rollback(self) -> None:
        """
        Phase 3 — Rollback.
        Roll back to rollback_anchor (OQ-8: last VERIFIED state).
        Acquires Rule Ledger Write Lock.
        """
        self._phase = RecoveryPhase.ROLLBACK

        await self._lock.acquire(LoopPriority.RECOVERY)
        try:
            anchor = self._scope.rollback_anchor
            if anchor is None:
                raise RecoveryFailedError(
                    "rollback_anchor is None — cannot rollback. "
                    "OQ-8: rollback anchor definition required. Human Override needed."
                )

            # TODO: implement actual rollback to anchor state
            self._scope.repair_notes.append(f"Rolled back to anchor: {anchor}")
            self._emit_evidence("ROLLBACK_COMPLETE", {
                "scope_id": self._scope.scope_id,
                "rollback_anchor": anchor,
            })
        finally:
            self._lock.release()

    async def _phase_repair(self) -> None:
        """
        Phase 4 — Repair.
        Apply fixes. M-03 risk check and M-04 security check enforced here.
        M-09 compliance check also enforced.
        """
        self._phase = RecoveryPhase.REPAIR
        self._work.transition_to(WorkStateEnum.REDESIGN)

        # M-03: risk check
        risk_ok = await self._check_risk()
        if not risk_ok:
            raise RecoveryFailedError("Risk check (M-03) failed during Repair phase.")

        # M-04: security check
        security_ok = await self._check_security()
        if not security_ok:
            raise RecoveryFailedError("Security check (M-04) failed during Repair phase.")

        # M-09: compliance check
        compliance_ok = await self._check_compliance()
        if not compliance_ok:
            raise RecoveryFailedError("Compliance check (M-09) failed during Repair phase.")

        # TODO: implement actual repair logic
        self._scope.repair_notes.append("Repair completed (placeholder)")
        self._emit_evidence("REPAIR_COMPLETE", {
            "scope_id": self._scope.scope_id,
            "repair_notes": self._scope.repair_notes,
        })

    async def _phase_resume(self) -> None:
        """
        Phase 5 — Resume.
        M-16 completion check. De-escalate security. Transition Work → RESUME.
        """
        self._phase = RecoveryPhase.RESUME

        # M-16: completion check (OQ-7/OQ-9: score TBD — placeholder: always pass)
        completion_ok = await self._check_completion()
        if not completion_ok:
            raise RecoveryFailedError("Completion check (M-16) failed during Resume phase.")

        # De-escalate security (requires Human Override if LOCKDOWN)
        if self._security.current == SecurityStateEnum.LOCKDOWN:
            # Cannot auto-release LOCKDOWN — emit event and wait
            self._emit_evidence("LOCKDOWN_HUMAN_OVERRIDE_REQUIRED", {
                "scope_id": self._scope.scope_id,
            })
            raise RecoveryFailedError(
                "LOCKDOWN active — Human Override required to de-escalate. "
                "Recovery will resume after L27 Override Controller releases LOCKDOWN."
            )

        self._security.de_escalate(SecurityStateEnum.NORMAL, authorized_by="RECOVERY_LOOP")
        self._work.transition_to(WorkStateEnum.RESUME)

        self._emit_evidence("RECOVERY_COMPLETE", {
            "scope_id": self._scope.scope_id,
            "phases_completed": ["ISOLATE", "REPLAY", "ROLLBACK", "REPAIR", "RESUME"],
        })

    # ------------------------------------------------------------------ #
    # Mandatory Checks (stubs — connect to actual engines in later steps)
    # ------------------------------------------------------------------ #

    async def _check_risk(self) -> bool:
        # TODO: connect to L3 Security & Isolation (G-03)
        return True

    async def _check_security(self) -> bool:
        # TODO: connect to L3 Security & Isolation (G-04)
        return True

    async def _check_compliance(self) -> bool:
        # TODO: connect to L13 Compliance Engine (G-04, G-16)
        return True

    async def _check_completion(self) -> bool:
        # TODO: connect to L21 Completion Engine (G-25); OQ-7/OQ-9 TBD
        return True

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _capture_rollback_anchor(self) -> Optional[str]:
        """
        OQ-8: rollback anchor = last VERIFIED state (placeholder).
        TODO: query actual state snapshot store for last VERIFIED state id.
        """
        return f"ANCHOR-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    def _emit_evidence(self, action: str, artifacts: dict) -> None:
        """M-07: emit EvidenceBundle for every phase transition."""
        bundle = EvidenceBundle(
            trigger=f"RecoveryLoop.{action}",
            actor="RecoveryLoop",
            action=action,
            before_state=self._work.previous.value if self._work.previous else None,
            after_state=self._work.current.value,
            artifacts=[artifacts],
        )
        self._evidence.store(bundle)


class RecoveryFailedError(Exception):
    """Raised when the Recovery Loop itself cannot complete — Human Override required."""
    pass
