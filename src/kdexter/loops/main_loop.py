"""
Main Loop — K-Dexter AOS

The central execution orchestrator. Drives the 12-step Work State Machine
through one complete governance cycle per invocation.

Normal path:
  DRAFT → CLARIFYING → SPEC_READY → PLANNING → VALIDATING → RUNNING →
  EVALUATING → APPROVAL_PENDING → EXECUTING → VERIFY → MONITOR

On failure at any step: route to Recovery or Self-Improvement/Evolution
via Failure Taxonomy (docs/architecture/failure_taxonomy.md).

Mandatory items enforced per step (mandatory_enforcement_map.md):
  CLARIFYING:  M-01 (intent)
  SPEC_READY:  M-02 (spec_twin)
  PLANNING:    M-03~06, M-18
  VALIDATING:  M-07~17 (10-check checklist)
  All states:  M-07 (evidence — EvidenceBundle on every transition)

Governance: A layer (runtime execution). WorkState transitions require
  B2-approved guard conditions.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Optional, Awaitable

from kdexter.audit.evidence_store import EvidenceBundle, EvidenceStore
from kdexter.loops.concurrency import (
    LoopCounter, LoopCeilingExceededError,
    LoopPriority, LoopPriorityQueue, RuleLedgerLock,
)
from kdexter.state_machine.security_state import SecurityStateContext, SecurityStateEnum
from kdexter.state_machine.trust_state import TrustStateContext
from kdexter.state_machine.work_state import (
    GuardViolationError, InvalidTransitionError,
    ValidatingCheck, ValidationResult,
    WorkStateContext, WorkStateEnum,
)
from kdexter.tcl.commands import TCLDispatcher

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────── #
# Cycle input / output
# ─────────────────────────────────────────────────────────────────────────── #

@dataclass
class CycleInput:
    """
    All data the Main Loop needs to start one execution cycle.
    Provided by the caller (L5 Harness / Scheduler or operator).
    """
    intent: str                             # M-01: user's execution intent
    spec_twin_id: str                       # M-02: pre-generated spec twin ID
    incident_id: str = field(             # loop count tracking key
        default_factory=lambda: f"CYCLE-{uuid.uuid4().hex[:8].upper()}"
    )
    # Optional pre-approvals (set True to skip human gate in automated runs)
    auto_approve: bool = False


@dataclass
class CycleResult:
    """Result of one complete Main Loop cycle."""
    cycle_id: str
    incident_id: str
    outcome: CycleOutcome
    final_state: WorkStateEnum
    evidence_bundles: list[EvidenceBundle] = field(default_factory=list)
    error: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    def finish(self, outcome: "CycleOutcome", state: WorkStateEnum,
               error: Optional[str] = None) -> None:
        self.outcome = outcome
        self.final_state = state
        self.error = error
        self.completed_at = datetime.utcnow()


class CycleOutcome(Enum):
    SUCCESS    = "SUCCESS"          # reached MONITOR
    BLOCKED    = "BLOCKED"          # guard violation — needs review
    FAILED     = "FAILED"           # routed to Recovery/Self-Improvement
    CEILING    = "CEILING"          # loop count ceiling exceeded
    INTERRUPTED = "INTERRUPTED"     # external stop signal


# ─────────────────────────────────────────────────────────────────────────── #
# Hooks (dependency injection for engines not yet implemented)
# ─────────────────────────────────────────────────────────────────────────── #

@dataclass
class MainLoopHooks:
    """
    Injectable callbacks for engines that Main Loop must call.
    Default implementations are stubs that pass all checks.
    Replace with real engines as they are implemented.
    """
    # VALIDATING checklist hooks — each returns (passed: bool, reason: str)
    check_forbidden:   Callable[[WorkStateContext], Awaitable[tuple[bool, str]]] = None
    check_mandatory:   Callable[[WorkStateContext], Awaitable[tuple[bool, str]]] = None
    check_compliance:  Callable[[WorkStateContext], Awaitable[tuple[bool, str]]] = None
    check_drift:       Callable[[WorkStateContext], Awaitable[tuple[bool, str]]] = None
    check_conflict:    Callable[[WorkStateContext], Awaitable[tuple[bool, str]]] = None
    check_pattern:     Callable[[WorkStateContext], Awaitable[tuple[bool, str]]] = None
    check_budget:      Callable[[WorkStateContext], Awaitable[tuple[bool, str]]] = None
    check_trust:       Callable[[WorkStateContext], Awaitable[tuple[bool, str]]] = None
    check_loop:        Callable[[WorkStateContext], Awaitable[tuple[bool, str]]] = None
    check_lock:        Callable[[WorkStateContext], Awaitable[tuple[bool, str]]] = None

    # Execution hook — called at RUNNING state
    run_execution:     Callable[[WorkStateContext, TCLDispatcher],
                                 Awaitable[tuple[bool, str]]] = None

    # Evaluation hook — called at EVALUATING state; returns completion_score
    evaluate:          Callable[[WorkStateContext], Awaitable[float]] = None

    # Approval hook — called at APPROVAL_PENDING; returns approved bool
    request_approval:  Callable[[WorkStateContext], Awaitable[bool]] = None

    def __post_init__(self) -> None:
        """Install stub implementations for any unset hooks."""
        async def _pass(_ctx=None, _d=None) -> tuple[bool, str]:
            return True, ""

        async def _pass_score(_ctx=None) -> float:
            return 1.0

        async def _pass_approve(_ctx=None) -> bool:
            return True

        for attr in [
            "check_forbidden", "check_mandatory", "check_compliance",
            "check_drift", "check_conflict", "check_pattern",
            "check_budget", "check_trust", "check_loop", "check_lock",
        ]:
            if getattr(self, attr) is None:
                setattr(self, attr, _pass)

        if self.run_execution is None:
            self.run_execution = _pass
        if self.evaluate is None:
            self.evaluate = _pass_score
        if self.request_approval is None:
            self.request_approval = _pass_approve


# ─────────────────────────────────────────────────────────────────────────── #
# Main Loop
# ─────────────────────────────────────────────────────────────────────────── #

class MainLoop:
    """
    Central execution orchestrator for K-Dexter AOS.

    One cycle = one traversal of the 12-step normal Work State path.
    Failures at any step are caught, classified, and handed off to the
    appropriate recovery/improvement loop.

    Usage:
        loop = MainLoop(
            work=work_ctx, security=sec_ctx,
            evidence_store=store, tcl=dispatcher,
            loop_counter=counter, loop_queue=queue,
        )
        result = await loop.run_cycle(CycleInput(intent="...", spec_twin_id="..."))
    """

    def __init__(
        self,
        work: WorkStateContext,
        security: SecurityStateContext,
        evidence_store: EvidenceStore,
        tcl: TCLDispatcher,
        loop_counter: LoopCounter,
        loop_queue: LoopPriorityQueue,
        hooks: Optional[MainLoopHooks] = None,
        trust: Optional[TrustStateContext] = None,
    ) -> None:
        self._work = work
        self._security = security
        self._evidence = evidence_store
        self._tcl = tcl
        self._counter = loop_counter
        self._queue = loop_queue
        self._hooks = hooks or MainLoopHooks()
        self._trust = trust
        self._stop_requested = False

    # ── Public API ──────────────────────────────────────────────────────── #

    def request_stop(self) -> None:
        """Signal the loop to stop after the current cycle."""
        self._stop_requested = True

    async def run_cycle(self, cycle_input: CycleInput) -> CycleResult:
        """
        Execute one complete governance cycle (DRAFT → MONITOR).
        Returns CycleResult regardless of outcome — never raises.
        """
        cycle_id = f"MAIN-{uuid.uuid4().hex[:8].upper()}"
        result = CycleResult(
            cycle_id=cycle_id,
            incident_id=cycle_input.incident_id,
            outcome=CycleOutcome.SUCCESS,
            final_state=self._work.current,
        )
        logger.info(f"[{cycle_id}] Cycle start — intent={cycle_input.intent!r}")

        try:
            # Loop count ceiling check (OQ-6 — config/thresholds.py)
            self._counter.check_and_record("MAIN", cycle_input.incident_id)

        except LoopCeilingExceededError as exc:
            logger.warning(f"[{cycle_id}] Loop ceiling: {exc}")
            result.finish(CycleOutcome.CEILING, self._work.current, str(exc))
            return result

        try:
            await self._step_clarifying(cycle_input, result)
            await self._step_spec_ready(cycle_input, result)
            await self._step_planning(cycle_input, result)
            await self._step_validating(result)
            await self._step_running(result)
            await self._step_evaluating(result)
            await self._step_approval(cycle_input, result)
            await self._step_executing(result)
            await self._step_verify(result)
            await self._step_monitor(result)

            result.finish(CycleOutcome.SUCCESS, self._work.current)
            logger.info(f"[{cycle_id}] Cycle complete — SUCCESS")

        except GuardViolationError as exc:
            logger.warning(f"[{cycle_id}] Guard violation: {exc}")
            self._safe_transition(WorkStateEnum.BLOCKED, reason=str(exc))
            result.finish(CycleOutcome.BLOCKED, self._work.current, str(exc))

        except CycleFailureError as exc:
            logger.error(f"[{cycle_id}] Cycle failure: {exc}")
            self._safe_transition(WorkStateEnum.FAILED)
            result.finish(CycleOutcome.FAILED, self._work.current, str(exc))

        except Exception as exc:
            logger.exception(f"[{cycle_id}] Unexpected error")
            self._safe_transition(WorkStateEnum.FAILED)
            result.finish(CycleOutcome.FAILED, self._work.current, str(exc))

        return result

    async def run_continuous(
        self,
        cycle_factory: Callable[[], Awaitable[CycleInput]],
        interval_seconds: float = 60.0,
    ) -> None:
        """
        Run cycles continuously until stop_requested.
        cycle_factory: async callable that produces the next CycleInput.
        """
        while not self._stop_requested:
            if self._security.is_locked_down():
                logger.critical("Security LOCKDOWN active — Main Loop suspended")
                await asyncio.sleep(interval_seconds)
                continue

            cycle_input = await cycle_factory()
            await self.run_cycle(cycle_input)
            await asyncio.sleep(interval_seconds)

    # ── Step implementations ────────────────────────────────────────────── #

    async def _step_clarifying(self, inp: CycleInput, result: CycleResult) -> None:
        """M-01: set intent, transition DRAFT → CLARIFYING → SPEC_READY gate."""
        self._transition(WorkStateEnum.CLARIFYING, result)
        self._work.intent = inp.intent
        # M-01 guard: intent now set — CLARIFYING → SPEC_READY will pass
        logger.debug(f"CLARIFYING: intent={inp.intent!r}")

    async def _step_spec_ready(self, inp: CycleInput, result: CycleResult) -> None:
        """M-02: set spec_twin_id, transition CLARIFYING → SPEC_READY."""
        self._work.spec_twin_id = inp.spec_twin_id
        self._transition(WorkStateEnum.SPEC_READY, result)
        logger.debug(f"SPEC_READY: spec_twin_id={inp.spec_twin_id!r}")

    async def _step_planning(self, inp: CycleInput, result: CycleResult) -> None:
        """M-03~06, M-18: complete planning checks, transition → PLANNING → VALIDATING."""
        self._transition(WorkStateEnum.PLANNING, result)

        # M-03 risk check
        self._work.risk_checked = True           # TODO: call L3 Security engine

        # M-04 security check
        if self._security.is_locked_down():
            raise CycleFailureError("Security LOCKDOWN active — cannot proceed to VALIDATING")
        self._work.security_checked = True

        # M-05 rollback plan
        self._work.rollback_plan_ready = True    # TODO: call L26 Recovery Engine

        # M-06 recovery simulation
        self._work.recovery_simulation_done = True  # TODO: Sandbox simulation

        # M-18 research
        self._work.research_complete = True      # TODO: call L23 Research Engine

        logger.debug("PLANNING: all 5 mandatory checks set")

    async def _step_validating(self, result: CycleResult) -> None:
        """Run 10-check VALIDATING checklist. Transition PLANNING → VALIDATING → RUNNING."""
        self._transition(WorkStateEnum.VALIDATING, result)

        checks: list[tuple[ValidatingCheck, Callable]] = [
            (ValidatingCheck.FORBIDDEN_CHECK,   self._hooks.check_forbidden),
            (ValidatingCheck.MANDATORY_CHECK,   self._hooks.check_mandatory),
            (ValidatingCheck.COMPLIANCE_CHECK,  self._hooks.check_compliance),
            (ValidatingCheck.DRIFT_CHECK,       self._hooks.check_drift),
            (ValidatingCheck.CONFLICT_CHECK,    self._hooks.check_conflict),
            (ValidatingCheck.PATTERN_CHECK,     self._hooks.check_pattern),
            (ValidatingCheck.BUDGET_CHECK,      self._hooks.check_budget),
            (ValidatingCheck.TRUST_CHECK,       self._hooks.check_trust),
            (ValidatingCheck.LOOP_CHECK,        self._hooks.check_loop),
            (ValidatingCheck.LOCK_CHECK,        self._hooks.check_lock),
        ]

        for check_enum, hook_fn in checks:
            passed, reason = await hook_fn(self._work)
            vr = ValidationResult(check=check_enum, passed=passed, reason=reason or None)
            self._work.validation_results.append(vr)

            if not passed:
                self._work.failed_check = check_enum
                raise CycleFailureError(
                    f"VALIDATING [{check_enum.name}] failed: {reason}"
                )
            logger.debug(f"VALIDATING [{check_enum.name}] PASS")

    async def _step_running(self, result: CycleResult) -> None:
        """VALIDATING → RUNNING: execute via TCL."""
        self._transition(WorkStateEnum.RUNNING, result)

        ok, reason = await self._hooks.run_execution(self._work, self._tcl)
        if not ok:
            raise CycleFailureError(f"RUNNING execution failed: {reason}")

        logger.debug("RUNNING: execution complete")

    async def _step_evaluating(self, result: CycleResult) -> None:
        """RUNNING → EVALUATING: score the execution result."""
        self._transition(WorkStateEnum.EVALUATING, result)

        score = await self._hooks.evaluate(self._work)
        self._work.completion_score = score
        logger.debug(f"EVALUATING: completion_score={score:.3f}")

    async def _step_approval(self, inp: CycleInput, result: CycleResult) -> None:
        """EVALUATING → APPROVAL_PENDING: request approval."""
        self._transition(WorkStateEnum.APPROVAL_PENDING, result)

        if inp.auto_approve:
            self._work.approval_granted = True
        else:
            approved = await self._hooks.request_approval(self._work)
            self._work.approval_granted = approved

        if not self._work.approval_granted:
            raise CycleFailureError("Approval denied at APPROVAL_PENDING")

        logger.debug("APPROVAL_PENDING: approval granted")

    async def _step_executing(self, result: CycleResult) -> None:
        """APPROVAL_PENDING → EXECUTING: final execution."""
        self._transition(WorkStateEnum.EXECUTING, result)
        logger.debug("EXECUTING: final execution step")
        # TODO: final order dispatch, fill confirmation

    async def _step_verify(self, result: CycleResult) -> None:
        """EXECUTING → VERIFY: completion check (M-16)."""
        self._transition(WorkStateEnum.VERIFY, result)
        # completion_score already set in EVALUATING — guard will check it
        logger.debug(f"VERIFY: score={self._work.completion_score:.3f}")

    async def _step_monitor(self, result: CycleResult) -> None:
        """VERIFY → MONITOR: cycle complete, return to DRAFT."""
        self._transition(WorkStateEnum.MONITOR, result)
        self._work.system_health_ok = True
        self._transition(WorkStateEnum.DRAFT, result)
        logger.debug("MONITOR → DRAFT: cycle complete")

    # ── Helpers ─────────────────────────────────────────────────────────── #

    def _transition(self, state: WorkStateEnum, result: CycleResult) -> None:
        """Transition + emit EvidenceBundle (M-07)."""
        self._work.transition_to(state)
        bundle = EvidenceBundle(
            trigger="MainLoop.transition",
            actor="MainLoop",
            action=f"→{state.value}",
            before_state=self._work.previous.value if self._work.previous else None,
            after_state=state.value,
        )
        self._evidence.store(bundle)
        result.evidence_bundles.append(bundle)
        logger.debug(
            f"  {self._work.previous.value if self._work.previous else '?'}"
            f" → {state.value}"
        )

    def _safe_transition(
        self, state: WorkStateEnum, reason: Optional[str] = None
    ) -> None:
        """Transition without raising — for error recovery paths."""
        try:
            self._work.transition_to(state, reason=reason)
        except (InvalidTransitionError, GuardViolationError) as exc:
            logger.warning(f"Safe transition to {state.value} failed: {exc}")


class CycleFailureError(Exception):
    """Internal exception that routes the cycle to FAILED state."""
    pass
