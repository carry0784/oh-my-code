"""
Concurrency Control — K-Dexter AOS

Priority Queue for 4 loops:
  Recovery(0) > Main(1) > Self-Improvement(2) > Evolution(3)

Rule Ledger Write Lock:
  Only one loop may write to Rule Ledger at a time.
  Higher-priority loops preempt by waiting with priority ordering.

Deadlock Detection:
  If Recovery holds Write Lock AND Main is waiting AND elapsed > timeout_deadlock
  → emit DeadlockDetectedEvent → Human Override required.

LoopOrchestrator:
  Manages execution of all 4 loops:
  - Recovery activation suspends Main; Main resumes after Recovery.RESUME
  - Evolution deferred while Recovery active; EvolutionDeferGuard enforces timeout
  - Background watchdog polls DeadlockDetector every second
  - on_human_override_required callback called when Human intervention needed

Open Questions:
  OQ-2: timeout_deadlock (seconds) — placeholder: 30s
  OQ-3: timeout_evolution_defer (seconds) — placeholder: 300s
"""
from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Optional, Callable, Awaitable, Protocol

logger = logging.getLogger(__name__)


class LoopPriority(IntEnum):
    RECOVERY = 0
    MAIN = 1
    SELF_IMPROVEMENT = 2
    EVOLUTION = 3


# OQ-2 placeholder — 30 seconds until confirmed
TIMEOUT_DEADLOCK_SECONDS: float = 30.0

# OQ-3 placeholder — 5 minutes until confirmed
TIMEOUT_EVOLUTION_DEFER_SECONDS: float = 300.0


@dataclass(order=True)
class LoopTask:
    priority: LoopPriority
    created_at: datetime = field(default_factory=datetime.utcnow, compare=False)
    task_id: str = field(default="", compare=False)
    coro: Optional[Callable[[], Awaitable[None]]] = field(default=None, compare=False)


class LoopPriorityQueue:
    """
    Priority queue for cross-loop task scheduling.
    Higher-priority loops (lower LoopPriority value) are dequeued first.
    """

    def __init__(self) -> None:
        self._queue: asyncio.PriorityQueue[LoopTask] = asyncio.PriorityQueue()
        self._active_loops: dict[LoopPriority, bool] = {p: False for p in LoopPriority}

    async def enqueue(self, task: LoopTask) -> None:
        await self._queue.put(task)

    async def dequeue(self) -> LoopTask:
        return await self._queue.get()

    def mark_active(self, priority: LoopPriority) -> None:
        self._active_loops[priority] = True

    def mark_inactive(self, priority: LoopPriority) -> None:
        self._active_loops[priority] = False

    def is_active(self, priority: LoopPriority) -> bool:
        return self._active_loops[priority]

    def recovery_active(self) -> bool:
        return self._active_loops[LoopPriority.RECOVERY]


class RuleLedgerLock:
    """
    Async write lock for Rule Ledger.
    Prevents concurrent writes from multiple loops.
    See failure_taxonomy.md Section 6: loop concurrency rules.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._holder: Optional[LoopPriority] = None
        self._acquired_at: Optional[datetime] = None

    async def acquire(self, requester: LoopPriority) -> None:
        await self._lock.acquire()
        self._holder = requester
        self._acquired_at = datetime.utcnow()

    def release(self) -> None:
        self._holder = None
        self._acquired_at = None
        self._lock.release()

    @property
    def holder(self) -> Optional[LoopPriority]:
        return self._holder

    @property
    def held_duration_seconds(self) -> float:
        if self._acquired_at is None:
            return 0.0
        return (datetime.utcnow() - self._acquired_at).total_seconds()

    def is_held(self) -> bool:
        return self._lock.locked()


class DeadlockDetector:
    """
    Detects deadlock condition:
      Recovery holds RuleLedgerLock AND Main is waiting AND elapsed > timeout_deadlock.

    OQ-2: timeout_deadlock = 30s (placeholder).
    On detection: emits DeadlockDetectedEvent — caller must request Human Override.
    """

    def __init__(
        self,
        rule_ledger_lock: RuleLedgerLock,
        loop_queue: LoopPriorityQueue,
        timeout_seconds: float = TIMEOUT_DEADLOCK_SECONDS,
    ) -> None:
        self._lock = rule_ledger_lock
        self._queue = loop_queue
        self._timeout = timeout_seconds
        self._main_waiting_since: Optional[datetime] = None

    def notify_main_waiting(self) -> None:
        if self._main_waiting_since is None:
            self._main_waiting_since = datetime.utcnow()

    def notify_main_acquired(self) -> None:
        self._main_waiting_since = None

    def check(self) -> bool:
        """
        Returns True if deadlock condition is met.
        Caller should request Human Override immediately.
        """
        if not self._lock.is_held():
            return False
        if self._lock.holder != LoopPriority.RECOVERY:
            return False
        if self._main_waiting_since is None:
            return False
        elapsed = (datetime.utcnow() - self._main_waiting_since).total_seconds()
        return elapsed > self._timeout


class EvolutionDeferGuard:
    """
    Guards against infinite Evolution Loop deferral when Recovery is active.
    OQ-3: timeout_evolution_defer = 300s (placeholder).
    """

    def __init__(self, timeout_seconds: float = TIMEOUT_EVOLUTION_DEFER_SECONDS) -> None:
        self._timeout = timeout_seconds
        self._deferred_since: Optional[datetime] = None

    def start_deferral(self) -> None:
        if self._deferred_since is None:
            self._deferred_since = datetime.utcnow()

    def clear_deferral(self) -> None:
        self._deferred_since = None

    def is_exceeded(self) -> bool:
        if self._deferred_since is None:
            return False
        elapsed = (datetime.utcnow() - self._deferred_since).total_seconds()
        return elapsed > self._timeout


# ─────────────────────────────────────────────────────────────────────────── #
# Loop protocol — each loop must implement this interface
# ─────────────────────────────────────────────────────────────────────────── #

class LoopProtocol(Protocol):
    """Interface all 4 loops must satisfy to plug into LoopOrchestrator."""
    @property
    def is_active(self) -> bool: ...
    async def run(self) -> None: ...


# ─────────────────────────────────────────────────────────────────────────── #
# Orchestrator events
# ─────────────────────────────────────────────────────────────────────────── #

@dataclass
class OrchestratorEvent:
    kind: str                               # e.g. "DEADLOCK", "EVOLUTION_DEFER_EXCEEDED"
    loop: Optional[LoopPriority]
    message: str
    occurred_at: datetime = field(default_factory=datetime.utcnow)


HumanOverrideCallback = Callable[[OrchestratorEvent], Awaitable[None]]


# ─────────────────────────────────────────────────────────────────────────── #
# LoopOrchestrator
# ─────────────────────────────────────────────────────────────────────────── #

class LoopOrchestrator:
    """
    Central coordinator for all 4 K-Dexter loops.

    Responsibilities:
    1. Maintain priority order: Recovery > Main > Self-Improvement > Evolution
    2. Suspend Main when Recovery activates; resume after Recovery.RESUME
    3. Defer Evolution while Recovery active; raise alert if OQ-3 exceeded
    4. Background watchdog detects deadlocks; calls on_human_override_required
    5. Dequeue and dispatch tasks from LoopPriorityQueue

    Usage:
        orch = LoopOrchestrator(
            recovery_loop=..., main_loop=...,
            rule_ledger_lock=..., loop_queue=...,
            on_human_override_required=my_alert_handler,
        )
        await orch.start()           # starts watchdog + dispatch loop
        await orch.stop()            # graceful shutdown
    """

    WATCHDOG_INTERVAL: float = 1.0   # seconds between deadlock checks

    def __init__(
        self,
        recovery_loop: LoopProtocol,
        main_loop: LoopProtocol,
        rule_ledger_lock: RuleLedgerLock,
        loop_queue: LoopPriorityQueue,
        on_human_override_required: Optional[HumanOverrideCallback] = None,
        self_improvement_loop: Optional[LoopProtocol] = None,
        evolution_loop: Optional[LoopProtocol] = None,
    ) -> None:
        self._recovery = recovery_loop
        self._main = main_loop
        self._self_improvement = self_improvement_loop
        self._evolution = evolution_loop
        self._lock = rule_ledger_lock
        self._queue = loop_queue
        self._on_override = on_human_override_required

        self._deadlock_detector = DeadlockDetector(rule_ledger_lock, loop_queue)
        self._evolution_guard = EvolutionDeferGuard()

        self._main_suspended: bool = False
        self._main_resume_event: asyncio.Event = asyncio.Event()
        self._main_resume_event.set()   # initially not suspended

        self._running: bool = False
        self._watchdog_task: Optional[asyncio.Task] = None
        self._dispatch_task: Optional[asyncio.Task] = None

    # ── Public API ──────────────────────────────────────────────────────── #

    async def start(self) -> None:
        """Start the orchestrator: launch watchdog and dispatch loop."""
        self._running = True
        self._watchdog_task = asyncio.create_task(
            self._watchdog_loop(), name="orchestrator-watchdog"
        )
        self._dispatch_task = asyncio.create_task(
            self._dispatch_loop(), name="orchestrator-dispatch"
        )
        logger.info("LoopOrchestrator started")

    async def stop(self) -> None:
        """Graceful shutdown — cancel background tasks."""
        self._running = False
        if self._watchdog_task:
            self._watchdog_task.cancel()
        if self._dispatch_task:
            self._dispatch_task.cancel()
        await asyncio.gather(
            self._watchdog_task or asyncio.sleep(0),
            self._dispatch_task or asyncio.sleep(0),
            return_exceptions=True,
        )
        logger.info("LoopOrchestrator stopped")

    async def trigger_recovery(self, loop_task: LoopTask) -> None:
        """
        Enqueue a Recovery task at highest priority.
        Suspends Main loop until Recovery completes.
        Starts Evolution deferral timer if Evolution was active.
        """
        self._suspend_main()
        if self._evolution and self._queue.is_active(LoopPriority.EVOLUTION):
            self._evolution_guard.start_deferral()
        await self._queue.enqueue(loop_task)
        logger.info(f"Recovery task {loop_task.task_id!r} enqueued — Main suspended")

    async def trigger_loop(self, loop_task: LoopTask) -> None:
        """Enqueue any loop task at its natural priority."""
        await self._queue.enqueue(loop_task)

    # ── Internal: suspend / resume Main ─────────────────────────────────── #

    def _suspend_main(self) -> None:
        if not self._main_suspended:
            self._main_suspended = True
            self._main_resume_event.clear()
            self._deadlock_detector.notify_main_waiting()
            logger.debug("Main loop suspended — waiting for Recovery to complete")

    def _resume_main(self) -> None:
        if self._main_suspended:
            self._main_suspended = False
            self._main_resume_event.set()
            self._deadlock_detector.notify_main_acquired()
            self._evolution_guard.clear_deferral()
            logger.debug("Main loop resumed")

    # ── Internal: dispatch loop ──────────────────────────────────────────── #

    async def _dispatch_loop(self) -> None:
        """
        Continuously dequeue tasks and dispatch to the appropriate loop.
        Main loop waits on _main_resume_event when suspended.
        """
        while self._running:
            try:
                task: LoopTask = await asyncio.wait_for(
                    self._queue.dequeue(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue

            if task.priority == LoopPriority.MAIN:
                # Wait until Main is no longer suspended
                await self._main_resume_event.wait()

            if task.coro is not None:
                try:
                    self._queue.mark_active(task.priority)
                    await task.coro()
                except Exception as exc:
                    logger.error(
                        f"Loop {task.priority.name} task {task.task_id!r} raised: {exc}"
                    )
                finally:
                    self._queue.mark_inactive(task.priority)
                    # If Recovery just finished, resume Main
                    if task.priority == LoopPriority.RECOVERY:
                        self._resume_main()

            self._queue._queue.task_done()

    # ── Internal: watchdog ───────────────────────────────────────────────── #

    async def _watchdog_loop(self) -> None:
        """
        Background watchdog — polls every WATCHDOG_INTERVAL seconds.
        Checks:
          1. Deadlock condition (OQ-2)
          2. Evolution deferral timeout (OQ-3)
        """
        while self._running:
            await asyncio.sleep(self.WATCHDOG_INTERVAL)

            # Check deadlock
            if self._deadlock_detector.check():
                event = OrchestratorEvent(
                    kind="DEADLOCK",
                    loop=LoopPriority.RECOVERY,
                    message=(
                        f"Deadlock detected: Recovery holds RuleLedgerLock, "
                        f"Main waiting > {TIMEOUT_DEADLOCK_SECONDS}s. "
                        "Human Override required."
                    ),
                )
                logger.critical(event.message)
                await self._notify_override(event)

            # Check Evolution deferral timeout
            if self._evolution_guard.is_exceeded():
                event = OrchestratorEvent(
                    kind="EVOLUTION_DEFER_EXCEEDED",
                    loop=LoopPriority.EVOLUTION,
                    message=(
                        f"Evolution Loop deferred > {TIMEOUT_EVOLUTION_DEFER_SECONDS}s "
                        "while Recovery active. Human Override required."
                    ),
                )
                logger.warning(event.message)
                await self._notify_override(event)

    async def _notify_override(self, event: OrchestratorEvent) -> None:
        if self._on_override is not None:
            try:
                await self._on_override(event)
            except Exception as exc:
                logger.error(f"on_human_override_required callback raised: {exc}")


class ConcurrencyError(Exception):
    """Raised when a concurrency violation is detected."""
    pass


# ─────────────────────────────────────────────────────────────────────────── #
# Loop Count Ceiling Enforcement (OQ-6 resolved)
# ─────────────────────────────────────────────────────────────────────────── #

from collections import defaultdict
from kdexter.config.thresholds import get_loop_ceiling


class LoopCounter:
    """
    Enforces per-loop activation ceilings (OQ-6 resolved — config/thresholds.py).

    Tracks:
      - per_incident: activations within a single incident/session ID
      - per_day:      activations within the current UTC calendar day
      - per_week:     activations within the current UTC ISO week

    Raises LoopCeilingExceededError before activation if any ceiling would be breached.
    The Meta Loop Controller (L20) should call check_and_record() before launching a loop.
    """

    def __init__(self) -> None:
        # incident_id → {loop_name → count}
        self._incident_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        # (date_str, loop_name) → count
        self._daily_counts: dict[tuple[str, str], int] = defaultdict(int)
        # (week_str, loop_name) → count
        self._weekly_counts: dict[tuple[str, str], int] = defaultdict(int)

    def check_and_record(self, loop_name: str, incident_id: str) -> None:
        """
        Check ceiling for loop_name under incident_id, then record the activation.
        Raises LoopCeilingExceededError if any ceiling would be breached.

        Args:
            loop_name:   "RECOVERY" | "MAIN" | "SELF_IMPROVEMENT" | "EVOLUTION"
            incident_id: unique ID for the current incident/session
        """
        ceiling = get_loop_ceiling(loop_name)
        now = datetime.utcnow()
        day_key = (now.strftime("%Y-%m-%d"), loop_name)
        week_key = (now.strftime("%Y-W%W"), loop_name)

        current_incident = self._incident_counts[incident_id][loop_name]
        current_daily   = self._daily_counts[day_key]
        current_weekly  = self._weekly_counts[week_key]

        if current_incident >= ceiling.per_incident:
            raise LoopCeilingExceededError(
                f"{loop_name} per_incident ceiling ({ceiling.per_incident}) reached "
                f"for incident '{incident_id}'. Human Override required."
            )
        if current_daily >= ceiling.per_day:
            raise LoopCeilingExceededError(
                f"{loop_name} per_day ceiling ({ceiling.per_day}) reached "
                f"for {day_key[0]}."
            )
        if current_weekly >= ceiling.per_week:
            raise LoopCeilingExceededError(
                f"{loop_name} per_week ceiling ({ceiling.per_week}) reached "
                f"for week {week_key[0]}."
            )

        # Record activation
        self._incident_counts[incident_id][loop_name] += 1
        self._daily_counts[day_key] += 1
        self._weekly_counts[week_key] += 1

    def counts(self, loop_name: str, incident_id: str) -> dict[str, int]:
        """Return current activation counts for a given loop and incident."""
        now = datetime.utcnow()
        day_key = (now.strftime("%Y-%m-%d"), loop_name)
        week_key = (now.strftime("%Y-W%W"), loop_name)
        return {
            "incident": self._incident_counts[incident_id][loop_name],
            "daily":    self._daily_counts[day_key],
            "weekly":   self._weekly_counts[week_key],
        }


class LoopCeilingExceededError(Exception):
    """Raised when a loop activation would exceed its configured ceiling."""
    pass
