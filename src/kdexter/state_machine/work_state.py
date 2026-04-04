"""
Work State Machine — K-Dexter AOS

Normal execution path (12 steps):
  DRAFT → CLARIFYING → SPEC_READY → PLANNING → VALIDATING → RUNNING →
  EVALUATING → APPROVAL_PENDING → EXECUTING → VERIFY → MONITOR

Failure recovery path:
  FAILED → REPLAY → ROOT_CAUSE → REDESIGN → RULE_UPDATE → SANDBOX →
  IMPROVEMENT → RESUME

Block states: BLOCKED / ISOLATED / CLOSED

VALIDATING state contains 10 internal checks (run as checklist, not separate states):
  [1] FORBIDDEN_CHECK  [2] MANDATORY_CHECK  [3] COMPLIANCE_CHECK
  [4] DRIFT_CHECK      [5] CONFLICT_CHECK   [6] PATTERN_CHECK
  [7] BUDGET_CHECK     [8] TRUST_CHECK      [9] LOOP_CHECK
  [10] LOCK_CHECK

v4 Priority 4: each transition now carries Guard conditions.
Guard failure raises GuardViolationError with the specific unmet condition.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Optional


# ─────────────────────────────────────────────────────────────────────────── #
# State enum
# ─────────────────────────────────────────────────────────────────────────── #


class WorkStateEnum(Enum):
    # Normal execution path
    DRAFT = "DRAFT"
    CLARIFYING = "CLARIFYING"
    SPEC_READY = "SPEC_READY"
    PLANNING = "PLANNING"
    VALIDATING = "VALIDATING"
    RUNNING = "RUNNING"
    EVALUATING = "EVALUATING"
    APPROVAL_PENDING = "APPROVAL_PENDING"
    EXECUTING = "EXECUTING"
    VERIFY = "VERIFY"
    MONITOR = "MONITOR"

    # Failure recovery path
    FAILED = "FAILED"
    REPLAY = "REPLAY"
    ROOT_CAUSE = "ROOT_CAUSE"
    REDESIGN = "REDESIGN"
    RULE_UPDATE = "RULE_UPDATE"
    SANDBOX = "SANDBOX"
    IMPROVEMENT = "IMPROVEMENT"
    RESUME = "RESUME"

    # Block states
    BLOCKED = "BLOCKED"
    ISOLATED = "ISOLATED"
    CLOSED = "CLOSED"


class ValidatingCheck(Enum):
    """10 internal checks within VALIDATING state (ordered)."""

    FORBIDDEN_CHECK = 1
    MANDATORY_CHECK = 2
    COMPLIANCE_CHECK = 3
    DRIFT_CHECK = 4
    CONFLICT_CHECK = 5
    PATTERN_CHECK = 6
    BUDGET_CHECK = 7
    TRUST_CHECK = 8
    LOOP_CHECK = 9
    LOCK_CHECK = 10


# ─────────────────────────────────────────────────────────────────────────── #
# Guard system
# ─────────────────────────────────────────────────────────────────────────── #


@dataclass
class GuardResult:
    passed: bool
    condition_id: str  # e.g. "INTENT_SET", "SPEC_TWIN_EXISTS"
    message: str

    @classmethod
    def ok(cls, condition_id: str) -> "GuardResult":
        return cls(passed=True, condition_id=condition_id, message="")

    @classmethod
    def fail(cls, condition_id: str, message: str) -> "GuardResult":
        return cls(passed=False, condition_id=condition_id, message=message)


# Guard function type: takes WorkStateContext, returns GuardResult
GuardFn = Callable[["WorkStateContext"], GuardResult]


@dataclass
class TransitionGuard:
    """
    Named guard attached to a specific (from_state → to_state) transition.
    condition_id: short identifier used in error messages and audit logs.
    check:        function that validates the WorkStateContext.
    """

    condition_id: str
    description: str
    check: GuardFn


# ─────────────────────────────────────────────────────────────────────────── #
# Context
# ─────────────────────────────────────────────────────────────────────────── #


@dataclass
class ValidationResult:
    check: ValidatingCheck
    passed: bool
    reason: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class WorkStateContext:
    """
    Runtime context attached to a Work State instance.

    Fields are set by the calling layer (Main Loop, Recovery Loop, etc.)
    before requesting a transition. Guards read these fields to decide
    whether the transition is permitted.
    """

    # Core state
    current: WorkStateEnum = WorkStateEnum.DRAFT
    previous: Optional[WorkStateEnum] = None
    last_transition: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # CLARIFYING guard fields
    intent: Optional[str] = None  # M-01: must be non-empty

    # SPEC_READY guard fields
    spec_twin_id: Optional[str] = None  # M-02: execution + verification spec pair ID

    # PLANNING guard fields
    risk_checked: bool = False  # M-03
    security_checked: bool = False  # M-04
    rollback_plan_ready: bool = False  # M-05
    recovery_simulation_done: bool = False  # M-06
    research_complete: bool = False  # M-18

    # VALIDATING guard fields
    validation_results: list[ValidationResult] = field(default_factory=list)
    failed_check: Optional[ValidatingCheck] = None

    # APPROVAL_PENDING guard fields
    approval_granted: bool = False

    # VERIFY guard fields
    completion_score: float = 0.0
    # OQ-9: completion_threshold TBD — using 0.80 as v4 placeholder
    completion_threshold: float = 0.80

    # FAILED → REPLAY guard fields
    failure_event_id: Optional[str] = None

    # Recovery path guard fields
    replay_complete: bool = False
    root_cause_identified: bool = False
    redesign_approved: bool = False
    repair_complete: bool = False  # fast path: REDESIGN → RESUME
    provenance_recorded: bool = False  # M-10 for RULE_UPDATE
    sandbox_passed: bool = False
    improvement_approved: bool = False
    system_health_ok: bool = False

    # BLOCKED state
    blocked_reason: Optional[str] = None
    blocked_reason_resolved: bool = False

    def transition_to(
        self,
        new_state: WorkStateEnum,
        reason: Optional[str] = None,
        skip_guards: bool = False,
    ) -> None:
        """
        Transition to new_state after validating:
          1. Transition is in the allowed map
          2. All guards for (current → new_state) pass

        skip_guards=True is ONLY for Recovery Loop emergency fast-path.
        Caller is always responsible for emitting an EvidenceBundle (M-07).
        """
        if not self._is_allowed(new_state):
            raise InvalidTransitionError(
                f"{self.current.value} → {new_state.value} not in transition map. reason={reason}"
            )

        if not skip_guards:
            violations = self._check_guards(new_state)
            if violations:
                raise GuardViolationError(
                    from_state=self.current,
                    to_state=new_state,
                    violations=violations,
                )

        self.previous = self.current
        self.current = new_state
        self.last_transition = datetime.now(timezone.utc)

        if new_state == WorkStateEnum.BLOCKED:
            self.blocked_reason = reason
        if new_state == WorkStateEnum.DRAFT:
            self._reset_cycle_flags()

    def all_validating_checks_passed(self) -> bool:
        """True if all 10 VALIDATING checks have a passed=True result."""
        passed_ids = {r.check for r in self.validation_results if r.passed}
        return all(c in passed_ids for c in ValidatingCheck)

    def _is_allowed(self, target: WorkStateEnum) -> bool:
        return target in _TRANSITION_MAP.get(self.current, set())

    def _check_guards(self, target: WorkStateEnum) -> list[GuardResult]:
        """Return list of failed GuardResults for (current → target)."""
        guards = _TRANSITION_GUARDS.get((self.current, target), [])
        return [r for g in guards if not (r := g.check(self)).passed]

    def _reset_cycle_flags(self) -> None:
        """Reset per-cycle fields when returning to DRAFT."""
        self.intent = None
        self.spec_twin_id = None
        self.risk_checked = False
        self.security_checked = False
        self.rollback_plan_ready = False
        self.recovery_simulation_done = False
        self.research_complete = False
        self.validation_results = []
        self.failed_check = None
        self.approval_granted = False
        self.completion_score = 0.0
        self.failure_event_id = None
        self.replay_complete = False
        self.root_cause_identified = False
        self.redesign_approved = False
        self.repair_complete = False
        self.provenance_recorded = False
        self.sandbox_passed = False
        self.improvement_approved = False
        self.system_health_ok = False
        self.blocked_reason = None
        self.blocked_reason_resolved = False


# ─────────────────────────────────────────────────────────────────────────── #
# Exceptions
# ─────────────────────────────────────────────────────────────────────────── #


class InvalidTransitionError(Exception):
    pass


@dataclass
class GuardViolationError(Exception):
    from_state: WorkStateEnum
    to_state: WorkStateEnum
    violations: list[GuardResult]

    def __str__(self) -> str:
        details = "; ".join(f"[{v.condition_id}] {v.message}" for v in self.violations)
        return f"Guard violation: {self.from_state.value} → {self.to_state.value} — {details}"


# ─────────────────────────────────────────────────────────────────────────── #
# Transition map (allowed edges)
# ─────────────────────────────────────────────────────────────────────────── #

_TRANSITION_MAP: dict[WorkStateEnum, set[WorkStateEnum]] = {
    WorkStateEnum.DRAFT: {WorkStateEnum.CLARIFYING, WorkStateEnum.CLOSED},
    WorkStateEnum.CLARIFYING: {WorkStateEnum.SPEC_READY, WorkStateEnum.BLOCKED},
    WorkStateEnum.SPEC_READY: {WorkStateEnum.PLANNING, WorkStateEnum.BLOCKED},
    WorkStateEnum.PLANNING: {WorkStateEnum.VALIDATING, WorkStateEnum.BLOCKED, WorkStateEnum.FAILED},
    WorkStateEnum.VALIDATING: {WorkStateEnum.RUNNING, WorkStateEnum.BLOCKED, WorkStateEnum.FAILED},
    WorkStateEnum.RUNNING: {WorkStateEnum.EVALUATING, WorkStateEnum.FAILED, WorkStateEnum.ISOLATED},
    WorkStateEnum.EVALUATING: {WorkStateEnum.APPROVAL_PENDING, WorkStateEnum.FAILED},
    WorkStateEnum.APPROVAL_PENDING: {
        WorkStateEnum.EXECUTING,
        WorkStateEnum.BLOCKED,
        WorkStateEnum.FAILED,
    },
    WorkStateEnum.EXECUTING: {WorkStateEnum.VERIFY, WorkStateEnum.FAILED, WorkStateEnum.ISOLATED},
    WorkStateEnum.VERIFY: {WorkStateEnum.MONITOR, WorkStateEnum.FAILED, WorkStateEnum.BLOCKED},
    WorkStateEnum.MONITOR: {WorkStateEnum.DRAFT, WorkStateEnum.FAILED},
    # Failure recovery path
    WorkStateEnum.FAILED: {WorkStateEnum.REPLAY, WorkStateEnum.ISOLATED, WorkStateEnum.CLOSED},
    WorkStateEnum.REPLAY: {WorkStateEnum.ROOT_CAUSE, WorkStateEnum.ISOLATED},
    WorkStateEnum.ROOT_CAUSE: {WorkStateEnum.REDESIGN, WorkStateEnum.ISOLATED},
    WorkStateEnum.REDESIGN: {
        WorkStateEnum.RULE_UPDATE,
        WorkStateEnum.RESUME,
        WorkStateEnum.BLOCKED,
    },
    WorkStateEnum.RULE_UPDATE: {WorkStateEnum.SANDBOX, WorkStateEnum.BLOCKED},
    WorkStateEnum.SANDBOX: {WorkStateEnum.IMPROVEMENT, WorkStateEnum.BLOCKED},
    WorkStateEnum.IMPROVEMENT: {WorkStateEnum.RESUME, WorkStateEnum.BLOCKED},
    WorkStateEnum.RESUME: {WorkStateEnum.DRAFT},
    # Block states
    WorkStateEnum.BLOCKED: {WorkStateEnum.DRAFT, WorkStateEnum.CLOSED},
    WorkStateEnum.ISOLATED: {WorkStateEnum.REPLAY, WorkStateEnum.CLOSED},
    WorkStateEnum.CLOSED: set(),  # terminal
}


# ─────────────────────────────────────────────────────────────────────────── #
# Guard definitions
# Key: (from_state, to_state)
# Value: list of TransitionGuard — ALL must pass
# ─────────────────────────────────────────────────────────────────────────── #


def _g(cid: str, desc: str, fn: GuardFn) -> TransitionGuard:
    return TransitionGuard(condition_id=cid, description=desc, check=fn)


_TRANSITION_GUARDS: dict[tuple[WorkStateEnum, WorkStateEnum], list[TransitionGuard]] = {
    # ── Normal path ──────────────────────────────────────────────────── #
    (WorkStateEnum.CLARIFYING, WorkStateEnum.SPEC_READY): [
        _g(
            "INTENT_SET",
            "M-01: intent must be non-empty string",
            lambda ctx: (
                GuardResult.ok("INTENT_SET")
                if ctx.intent
                else GuardResult.fail("INTENT_SET", "ctx.intent is None or empty")
            ),
        ),
    ],
    (WorkStateEnum.SPEC_READY, WorkStateEnum.PLANNING): [
        _g(
            "SPEC_TWIN_EXISTS",
            "M-02: spec_twin_id must be set",
            lambda ctx: (
                GuardResult.ok("SPEC_TWIN_EXISTS")
                if ctx.spec_twin_id
                else GuardResult.fail("SPEC_TWIN_EXISTS", "ctx.spec_twin_id is None")
            ),
        ),
    ],
    (WorkStateEnum.PLANNING, WorkStateEnum.VALIDATING): [
        _g(
            "RISK_CHECKED",
            "M-03: risk check must be complete",
            lambda ctx: (
                GuardResult.ok("RISK_CHECKED")
                if ctx.risk_checked
                else GuardResult.fail("RISK_CHECKED", "ctx.risk_checked is False")
            ),
        ),
        _g(
            "SECURITY_CHECKED",
            "M-04: security check must be complete",
            lambda ctx: (
                GuardResult.ok("SECURITY_CHECKED")
                if ctx.security_checked
                else GuardResult.fail("SECURITY_CHECKED", "ctx.security_checked is False")
            ),
        ),
        _g(
            "ROLLBACK_PLAN_READY",
            "M-05: rollback plan must exist",
            lambda ctx: (
                GuardResult.ok("ROLLBACK_PLAN_READY")
                if ctx.rollback_plan_ready
                else GuardResult.fail("ROLLBACK_PLAN_READY", "ctx.rollback_plan_ready is False")
            ),
        ),
        _g(
            "RECOVERY_SIM_DONE",
            "M-06: recovery simulation must be run",
            lambda ctx: (
                GuardResult.ok("RECOVERY_SIM_DONE")
                if ctx.recovery_simulation_done
                else GuardResult.fail("RECOVERY_SIM_DONE", "ctx.recovery_simulation_done is False")
            ),
        ),
        _g(
            "RESEARCH_COMPLETE",
            "M-18: research must be complete before execution",
            lambda ctx: (
                GuardResult.ok("RESEARCH_COMPLETE")
                if ctx.research_complete
                else GuardResult.fail("RESEARCH_COMPLETE", "ctx.research_complete is False")
            ),
        ),
    ],
    (WorkStateEnum.VALIDATING, WorkStateEnum.RUNNING): [
        _g(
            "ALL_CHECKS_PASSED",
            "All 10 VALIDATING checks must pass",
            lambda ctx: (
                GuardResult.ok("ALL_CHECKS_PASSED")
                if ctx.all_validating_checks_passed()
                else GuardResult.fail(
                    "ALL_CHECKS_PASSED",
                    f"Failed check: {ctx.failed_check.name if ctx.failed_check else 'unknown'}",
                )
            ),
        ),
    ],
    (WorkStateEnum.APPROVAL_PENDING, WorkStateEnum.EXECUTING): [
        _g(
            "APPROVAL_GRANTED",
            "Approval must be granted before executing",
            lambda ctx: (
                GuardResult.ok("APPROVAL_GRANTED")
                if ctx.approval_granted
                else GuardResult.fail("APPROVAL_GRANTED", "ctx.approval_granted is False")
            ),
        ),
    ],
    (WorkStateEnum.VERIFY, WorkStateEnum.MONITOR): [
        _g(
            "COMPLETION_SCORE",
            "M-16: completion_score must meet threshold",
            lambda ctx: (
                GuardResult.ok("COMPLETION_SCORE")
                if ctx.completion_score >= ctx.completion_threshold
                else GuardResult.fail(
                    "COMPLETION_SCORE",
                    f"score={ctx.completion_score:.3f} < threshold={ctx.completion_threshold:.3f}",
                )
            ),
        ),
    ],
    # ── Failure recovery path ─────────────────────────────────────────── #
    (WorkStateEnum.FAILED, WorkStateEnum.REPLAY): [
        _g(
            "FAILURE_EVENT_RECORDED",
            "failure_event_id must be set before replay",
            lambda ctx: (
                GuardResult.ok("FAILURE_EVENT_RECORDED")
                if ctx.failure_event_id
                else GuardResult.fail("FAILURE_EVENT_RECORDED", "ctx.failure_event_id is None")
            ),
        ),
    ],
    (WorkStateEnum.REPLAY, WorkStateEnum.ROOT_CAUSE): [
        _g(
            "REPLAY_COMPLETE",
            "Replay must complete before root cause analysis",
            lambda ctx: (
                GuardResult.ok("REPLAY_COMPLETE")
                if ctx.replay_complete
                else GuardResult.fail("REPLAY_COMPLETE", "ctx.replay_complete is False")
            ),
        ),
    ],
    (WorkStateEnum.ROOT_CAUSE, WorkStateEnum.REDESIGN): [
        _g(
            "ROOT_CAUSE_IDENTIFIED",
            "Root cause must be identified",
            lambda ctx: (
                GuardResult.ok("ROOT_CAUSE_IDENTIFIED")
                if ctx.root_cause_identified
                else GuardResult.fail("ROOT_CAUSE_IDENTIFIED", "ctx.root_cause_identified is False")
            ),
        ),
    ],
    (WorkStateEnum.REDESIGN, WorkStateEnum.RULE_UPDATE): [
        _g(
            "REDESIGN_APPROVED",
            "Redesign must be approved before rule update",
            lambda ctx: (
                GuardResult.ok("REDESIGN_APPROVED")
                if ctx.redesign_approved
                else GuardResult.fail("REDESIGN_APPROVED", "ctx.redesign_approved is False")
            ),
        ),
    ],
    (WorkStateEnum.REDESIGN, WorkStateEnum.RESUME): [
        # Recovery fast path: skip RULE_UPDATE→SANDBOX→IMPROVEMENT
        _g(
            "REPAIR_COMPLETE",
            "Repair must be complete for fast-path resume",
            lambda ctx: (
                GuardResult.ok("REPAIR_COMPLETE")
                if ctx.repair_complete
                else GuardResult.fail("REPAIR_COMPLETE", "ctx.repair_complete is False")
            ),
        ),
    ],
    (WorkStateEnum.RULE_UPDATE, WorkStateEnum.SANDBOX): [
        _g(
            "PROVENANCE_RECORDED",
            "M-10: rule provenance must be recorded",
            lambda ctx: (
                GuardResult.ok("PROVENANCE_RECORDED")
                if ctx.provenance_recorded
                else GuardResult.fail("PROVENANCE_RECORDED", "ctx.provenance_recorded is False")
            ),
        ),
    ],
    (WorkStateEnum.SANDBOX, WorkStateEnum.IMPROVEMENT): [
        _g(
            "SANDBOX_PASSED",
            "Sandbox test must pass before improvement",
            lambda ctx: (
                GuardResult.ok("SANDBOX_PASSED")
                if ctx.sandbox_passed
                else GuardResult.fail("SANDBOX_PASSED", "ctx.sandbox_passed is False")
            ),
        ),
    ],
    (WorkStateEnum.IMPROVEMENT, WorkStateEnum.RESUME): [
        _g(
            "IMPROVEMENT_APPROVED",
            "Improvement must be approved",
            lambda ctx: (
                GuardResult.ok("IMPROVEMENT_APPROVED")
                if ctx.improvement_approved
                else GuardResult.fail("IMPROVEMENT_APPROVED", "ctx.improvement_approved is False")
            ),
        ),
    ],
    (WorkStateEnum.RESUME, WorkStateEnum.DRAFT): [
        _g(
            "SYSTEM_HEALTH_OK",
            "System health must be confirmed before re-entering DRAFT",
            lambda ctx: (
                GuardResult.ok("SYSTEM_HEALTH_OK")
                if ctx.system_health_ok
                else GuardResult.fail("SYSTEM_HEALTH_OK", "ctx.system_health_ok is False")
            ),
        ),
    ],
    (WorkStateEnum.BLOCKED, WorkStateEnum.DRAFT): [
        _g(
            "BLOCKED_REASON_RESOLVED",
            "Blocking issue must be resolved before returning to DRAFT",
            lambda ctx: (
                GuardResult.ok("BLOCKED_REASON_RESOLVED")
                if ctx.blocked_reason_resolved
                else GuardResult.fail(
                    "BLOCKED_REASON_RESOLVED",
                    f"Unresolved block: {ctx.blocked_reason or 'no reason recorded'}",
                )
            ),
        ),
    ],
    (WorkStateEnum.ISOLATED, WorkStateEnum.REPLAY): [
        _g(
            "FAILURE_EVENT_RECORDED",
            "failure_event_id must be set to begin replay from ISOLATED",
            lambda ctx: (
                GuardResult.ok("FAILURE_EVENT_RECORDED")
                if ctx.failure_event_id
                else GuardResult.fail("FAILURE_EVENT_RECORDED", "ctx.failure_event_id is None")
            ),
        ),
    ],
}
