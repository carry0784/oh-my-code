"""
Scheduler Engine -- L25 K-Dexter AOS

Purpose: schedule and manage recurring tasks by name.
Maintains task registry; execution dispatch is handled externally.

Governance: B2 (governance_layer_map.md -- L25)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional


# ------------------------------------------------------------------ #
# Data models
# ------------------------------------------------------------------ #

@dataclass
class ScheduledTask:
    """Descriptor for a single scheduled recurring task."""
    task_id: str
    interval: float           # recurrence interval in seconds
    callback_name: str        # dotted name of the callable to invoke
    active: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None


# ------------------------------------------------------------------ #
# L25 Scheduler Engine
# ------------------------------------------------------------------ #

class SchedulerEngine:
    """
    L25 Scheduler Engine.

    Maintains a registry of recurring tasks. Scheduling a task records
    the desired interval and callback; actual invocation is the caller's
    responsibility (this engine does not spawn threads or event loops).

    next_run is calculated at schedule time as now + interval.
    Callers should update last_run / next_run after each execution via
    mark_ran().

    Usage:
        engine = SchedulerEngine()
        task = engine.schedule("heartbeat", interval_seconds=60,
                               callback_name="kdexter.health.heartbeat")
        # ... after execution:
        engine.mark_ran("heartbeat")
        engine.cancel("heartbeat")
    """

    def __init__(self) -> None:
        self._tasks: dict[str, ScheduledTask] = {}

    # ---------------------------------------------------------------- #
    # Registration
    # ---------------------------------------------------------------- #

    def schedule(
        self,
        task_id: str,
        interval_seconds: float,
        callback_name: str,
    ) -> ScheduledTask:
        """
        Register (or replace) a recurring task.

        Args:
            task_id: unique identifier for the task
            interval_seconds: how often the task should run
            callback_name: dotted-path name of the callable

        Returns:
            The registered ScheduledTask
        """
        now = datetime.utcnow()
        task = ScheduledTask(
            task_id=task_id,
            interval=interval_seconds,
            callback_name=callback_name,
            active=True,
            last_run=None,
            next_run=now + timedelta(seconds=interval_seconds),
        )
        self._tasks[task_id] = task
        return task

    def cancel(self, task_id: str) -> bool:
        """
        Deactivate a task without removing it from the registry.

        Returns:
            True if the task existed, False otherwise
        """
        task = self._tasks.get(task_id)
        if task is None:
            return False
        task.active = False
        return True

    def remove(self, task_id: str) -> bool:
        """
        Remove a task from the registry entirely.

        Returns:
            True if the task existed and was removed, False otherwise
        """
        if task_id in self._tasks:
            del self._tasks[task_id]
            return True
        return False

    # ---------------------------------------------------------------- #
    # Lifecycle helpers
    # ---------------------------------------------------------------- #

    def mark_ran(self, task_id: str) -> None:
        """
        Record that a task has just executed.

        Updates last_run to now and advances next_run by interval.

        Raises:
            KeyError: if task_id is not in the registry
        """
        task = self._tasks[task_id]
        now = datetime.utcnow()
        task.last_run = now
        task.next_run = now + timedelta(seconds=task.interval)

    # ---------------------------------------------------------------- #
    # Queries
    # ---------------------------------------------------------------- #

    def get(self, task_id: str) -> Optional[ScheduledTask]:
        """Return a task by ID, or None if not found."""
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[ScheduledTask]:
        """Return all registered tasks (active and inactive)."""
        return list(self._tasks.values())

    def active_tasks(self) -> list[ScheduledTask]:
        """Return only active tasks."""
        return [t for t in self._tasks.values() if t.active]

    def due_tasks(self) -> list[ScheduledTask]:
        """
        Return active tasks whose next_run is at or before now.

        Useful for polling loops that need to dispatch overdue tasks.
        """
        now = datetime.utcnow()
        return [
            t for t in self._tasks.values()
            if t.active and t.next_run is not None and t.next_run <= now
        ]
