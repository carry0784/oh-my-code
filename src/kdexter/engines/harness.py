"""
Execution Harness — L5
K-Dexter AOS v4

Manages execution harnesses: sandboxed environments where strategies
are tested before live deployment. Coordinates with L25 SchedulerEngine
for timed execution.

B2 Orchestration layer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class HarnessStatus(Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class HarnessRun:
    run_id: str
    strategy_id: str
    status: HarnessStatus = HarnessStatus.CREATED
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[dict] = None
    error: Optional[str] = None


class HarnessEngine:
    """
    L5 Execution Harness.

    Manages sandboxed test runs for strategies before live deployment.
    """

    def __init__(self) -> None:
        self._runs: dict[str, HarnessRun] = {}

    def create(self, run_id: str, strategy_id: str) -> HarnessRun:
        run = HarnessRun(run_id=run_id, strategy_id=strategy_id)
        self._runs[run_id] = run
        return run

    def start(self, run_id: str) -> bool:
        run = self._runs.get(run_id)
        if run is None or run.status != HarnessStatus.CREATED:
            return False
        run.status = HarnessStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)
        return True

    def complete(self, run_id: str, result: Optional[dict] = None) -> bool:
        run = self._runs.get(run_id)
        if run is None or run.status != HarnessStatus.RUNNING:
            return False
        run.status = HarnessStatus.COMPLETED
        run.completed_at = datetime.now(timezone.utc)
        run.result = result or {}
        return True

    def fail(self, run_id: str, error: str) -> bool:
        run = self._runs.get(run_id)
        if run is None or run.status != HarnessStatus.RUNNING:
            return False
        run.status = HarnessStatus.FAILED
        run.completed_at = datetime.now(timezone.utc)
        run.error = error
        return True

    def get(self, run_id: str) -> Optional[HarnessRun]:
        return self._runs.get(run_id)

    def list_all(self) -> list[HarnessRun]:
        return list(self._runs.values())

    def list_running(self) -> list[HarnessRun]:
        return [r for r in self._runs.values()
                if r.status == HarnessStatus.RUNNING]
