"""
Failure Router — K-Dexter AOS v4

Implements the routing decision table from failure_taxonomy.md Section 2.
Given a failure event (domain, severity, recurrence), determines:
  1. Which loop handles it (Recovery / Self-Improvement / Evolution / MainLoop)
  2. Target SecurityState escalation
  3. Target WorkState transition
  4. Whether B1 notification is required

Also integrates Failure Pattern Memory (L17) for recurrence classification:
  FIRST:   no prior occurrence in memory
  REPEAT:  1+ prior, below PATTERN threshold
  PATTERN: 3+ total OR 2 within 7 days

Governance: B2 (L17 Failure Pattern Memory)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from kdexter.state_machine.security_state import SecurityStateEnum


# ─────────────────────────────────────────────────────────────────────────── #
# Routing targets
# ─────────────────────────────────────────────────────────────────────────── #

class TargetLoop(Enum):
    RECOVERY = "RECOVERY"
    SELF_IMPROVEMENT = "SELF_IMPROVEMENT"
    EVOLUTION = "EVOLUTION"
    MAIN_LOOP = "MAIN_LOOP"        # handled within MainLoop (LOW severity)
    AUDIT_ONLY = "AUDIT_ONLY"      # just log (GOVERNANCE LOW)


class Recurrence(Enum):
    FIRST = "FIRST"
    REPEAT = "REPEAT"
    PATTERN = "PATTERN"


@dataclass
class RoutingDecision:
    """Result of the failure routing decision."""
    target_loop: TargetLoop
    security_target: SecurityStateEnum
    work_state_action: str              # "ISOLATED", "FAILED", "BLOCKED", "MONITOR", "RUNNING"
    b1_notify: bool = False             # whether B1 must be notified
    schedule_evolution: bool = False    # INFRA MEDIUM PATTERN: Recovery + Evolution scheduled
    reason: str = ""


# ─────────────────────────────────────────────────────────────────────────── #
# Failure Pattern Memory (L17)
# ─────────────────────────────────────────────────────────────────────────── #

# OQ-1 placeholder: PATTERN threshold
PATTERN_COUNT_THRESHOLD: int = 3        # 3+ total occurrences
PATTERN_WINDOW_DAYS: int = 7            # OR 2 within 7 days
PATTERN_WINDOW_COUNT: int = 2


@dataclass
class FailureRecord:
    """A single recorded failure occurrence."""
    failure_type_id: str
    occurred_at: datetime = field(default_factory=datetime.utcnow)


class FailurePatternMemory:
    """
    L17 Failure Pattern Memory.
    Tracks failure occurrences and classifies recurrence.
    """

    def __init__(self) -> None:
        self._records: list[FailureRecord] = []

    def record(self, failure_type_id: str, occurred_at: Optional[datetime] = None) -> None:
        self._records.append(FailureRecord(
            failure_type_id=failure_type_id,
            occurred_at=occurred_at or datetime.utcnow(),
        ))

    def classify_recurrence(self, failure_type_id: str) -> Recurrence:
        """
        Classify recurrence for a failure type.
        Must be called BEFORE recording the new occurrence.
        """
        matching = [r for r in self._records if r.failure_type_id == failure_type_id]
        total = len(matching)

        if total == 0:
            return Recurrence.FIRST

        # Check PATTERN: 3+ total OR 2 within window
        if total >= PATTERN_COUNT_THRESHOLD:
            return Recurrence.PATTERN

        now = datetime.utcnow()
        window_start = now - timedelta(days=PATTERN_WINDOW_DAYS)
        recent = sum(1 for r in matching if r.occurred_at >= window_start)
        if recent >= PATTERN_WINDOW_COUNT:
            return Recurrence.PATTERN

        return Recurrence.REPEAT

    def count(self, failure_type_id: Optional[str] = None) -> int:
        if failure_type_id is None:
            return len(self._records)
        return sum(1 for r in self._records if r.failure_type_id == failure_type_id)

    def clear(self) -> None:
        self._records.clear()


# ─────────────────────────────────────────────────────────────────────────── #
# Failure Router
# ─────────────────────────────────────────────────────────────────────────── #

class FailureRouter:
    """
    Routes failures to the correct loop based on failure_taxonomy.md Section 2.

    Usage:
        memory = FailurePatternMemory()
        router = FailureRouter(memory)

        decision = router.route("INFRA", "CRITICAL", "F-I-007")
        # decision.target_loop == TargetLoop.RECOVERY
        # decision.security_target == SecurityStateEnum.LOCKDOWN
    """

    def __init__(self, pattern_memory: FailurePatternMemory) -> None:
        self._memory = pattern_memory

    def route(
        self,
        domain: str,
        severity: str,
        failure_type_id: str,
        recurrence_override: Optional[Recurrence] = None,
    ) -> RoutingDecision:
        """
        Determine routing for a failure.

        Args:
            domain:     "INFRA" | "STRATEGY" | "GOVERNANCE"
            severity:   "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
            failure_type_id: e.g. "F-I-001", "F-S-006"
            recurrence_override: if provided, skip pattern memory lookup

        Returns:
            RoutingDecision with target loop, security/work state targets.

        Side effect: records failure in pattern memory.
        """
        # Classify recurrence
        if recurrence_override is not None:
            recurrence = recurrence_override
        else:
            recurrence = self._memory.classify_recurrence(failure_type_id)

        # Record in memory
        self._memory.record(failure_type_id)

        # Route based on domain
        if domain == "INFRA":
            return self._route_infra(severity, recurrence, failure_type_id)
        elif domain == "STRATEGY":
            return self._route_strategy(severity, recurrence, failure_type_id)
        elif domain == "GOVERNANCE":
            return self._route_governance(severity, recurrence, failure_type_id)
        else:
            return RoutingDecision(
                target_loop=TargetLoop.AUDIT_ONLY,
                security_target=SecurityStateEnum.NORMAL,
                work_state_action="RUNNING",
                reason=f"Unknown domain: {domain}",
            )

    # ── INFRA routing ────────────────────────────────────────────────────── #

    def _route_infra(
        self, severity: str, recurrence: Recurrence, fid: str,
    ) -> RoutingDecision:
        if severity == "CRITICAL":
            return RoutingDecision(
                target_loop=TargetLoop.RECOVERY,
                security_target=SecurityStateEnum.LOCKDOWN,
                work_state_action="ISOLATED",
                reason=f"INFRA CRITICAL {fid} → Recovery + LOCKDOWN",
            )
        if severity == "HIGH":
            return RoutingDecision(
                target_loop=TargetLoop.RECOVERY,
                security_target=SecurityStateEnum.QUARANTINED,
                work_state_action="FAILED",
                reason=f"INFRA HIGH {fid} → Recovery + QUARANTINED",
            )
        if severity == "MEDIUM":
            schedule_evo = recurrence == Recurrence.PATTERN
            return RoutingDecision(
                target_loop=TargetLoop.RECOVERY,
                security_target=SecurityStateEnum.RESTRICTED,
                work_state_action="FAILED",
                schedule_evolution=schedule_evo,
                reason=f"INFRA MEDIUM {fid} ({recurrence.value}) → Recovery"
                       + (" + Evolution scheduled" if schedule_evo else ""),
            )
        # LOW
        return RoutingDecision(
            target_loop=TargetLoop.MAIN_LOOP,
            security_target=SecurityStateEnum.NORMAL,
            work_state_action="MONITOR",
            reason=f"INFRA LOW {fid} → MainLoop internal handling",
        )

    # ── STRATEGY routing ─────────────────────────────────────────────────── #

    def _route_strategy(
        self, severity: str, recurrence: Recurrence, fid: str,
    ) -> RoutingDecision:
        if severity == "CRITICAL":
            return RoutingDecision(
                target_loop=TargetLoop.RECOVERY,
                security_target=SecurityStateEnum.QUARANTINED,
                work_state_action="ISOLATED",
                reason=f"STRATEGY CRITICAL {fid} → Recovery + QUARANTINED",
            )
        if severity == "HIGH":
            if recurrence == Recurrence.PATTERN:
                return RoutingDecision(
                    target_loop=TargetLoop.EVOLUTION,
                    security_target=SecurityStateEnum.RESTRICTED,
                    work_state_action="FAILED",
                    reason=f"STRATEGY HIGH PATTERN {fid} → Evolution",
                )
            return RoutingDecision(
                target_loop=TargetLoop.SELF_IMPROVEMENT,
                security_target=SecurityStateEnum.RESTRICTED,
                work_state_action="FAILED",
                reason=f"STRATEGY HIGH {recurrence.value} {fid} → Self-Improvement",
            )
        if severity == "MEDIUM":
            if recurrence == Recurrence.PATTERN:
                return RoutingDecision(
                    target_loop=TargetLoop.EVOLUTION,
                    security_target=SecurityStateEnum.RESTRICTED,
                    work_state_action="FAILED",
                    reason=f"STRATEGY MEDIUM PATTERN {fid} → Evolution",
                )
            return RoutingDecision(
                target_loop=TargetLoop.SELF_IMPROVEMENT,
                security_target=SecurityStateEnum.NORMAL,
                work_state_action="FAILED",
                reason=f"STRATEGY MEDIUM {recurrence.value} {fid} → Self-Improvement",
            )
        # LOW
        return RoutingDecision(
            target_loop=TargetLoop.MAIN_LOOP,
            security_target=SecurityStateEnum.NORMAL,
            work_state_action="MONITOR",
            reason=f"STRATEGY LOW {fid} → MainLoop internal handling",
        )

    # ── GOVERNANCE routing ───────────────────────────────────────────────── #

    def _route_governance(
        self, severity: str, recurrence: Recurrence, fid: str,
    ) -> RoutingDecision:
        if severity == "CRITICAL":
            return RoutingDecision(
                target_loop=TargetLoop.RECOVERY,
                security_target=SecurityStateEnum.LOCKDOWN,
                work_state_action="ISOLATED",
                b1_notify=True,
                reason=f"GOVERNANCE CRITICAL {fid} → Recovery + B1 Human Override",
            )
        if severity == "HIGH":
            return RoutingDecision(
                target_loop=TargetLoop.RECOVERY,
                security_target=SecurityStateEnum.QUARANTINED,
                work_state_action="BLOCKED",
                b1_notify=True,
                reason=f"GOVERNANCE HIGH {fid} → Recovery + B1 notification",
            )
        if severity == "MEDIUM":
            if recurrence == Recurrence.PATTERN:
                return RoutingDecision(
                    target_loop=TargetLoop.EVOLUTION,
                    security_target=SecurityStateEnum.RESTRICTED,
                    work_state_action="BLOCKED",
                    b1_notify=True,
                    reason=f"GOVERNANCE MEDIUM PATTERN {fid} → Evolution + B1 notification",
                )
            return RoutingDecision(
                target_loop=TargetLoop.SELF_IMPROVEMENT,
                security_target=SecurityStateEnum.RESTRICTED,
                work_state_action="BLOCKED",
                reason=f"GOVERNANCE MEDIUM {recurrence.value} {fid} → Self-Improvement",
            )
        # LOW
        return RoutingDecision(
            target_loop=TargetLoop.AUDIT_ONLY,
            security_target=SecurityStateEnum.NORMAL,
            work_state_action="RUNNING",
            reason=f"GOVERNANCE LOW {fid} → Audit record only",
        )
