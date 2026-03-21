"""
Loop Monitor -- L28 K-Dexter AOS

Purpose: monitor loop health and ceiling usage across all 4 loops.
Reports loop_counts and health status for Gate G-24.

Output: loop_counts (dict) -> EvaluationContext.loop_counts -> Gate G-24 (ceiling check)

Governance: B2 (governance_layer_map.md -- L28)
Gate: G-24 LOOP_CHECK at VALIDATING[9]
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from kdexter.config.thresholds import LOOP_COUNT_CEILINGS, get_loop_ceiling
from kdexter.loops.concurrency import LoopCounter


# ------------------------------------------------------------------ #
# Data models
# ------------------------------------------------------------------ #

class LoopHealthStatus(Enum):
    HEALTHY = "HEALTHY"        # usage well below ceilings
    WARNING = "WARNING"        # usage > 70% of any ceiling
    CRITICAL = "CRITICAL"      # usage > 90% of any ceiling
    EXCEEDED = "EXCEEDED"      # ceiling breached


WARNING_THRESHOLD = 0.70
CRITICAL_THRESHOLD = 0.90


@dataclass
class LoopStatus:
    """Health status for a single loop."""
    loop_name: str
    incident_count: int
    daily_count: int
    weekly_count: int
    incident_ceiling: int
    daily_ceiling: int
    weekly_ceiling: int
    health: LoopHealthStatus
    max_usage_ratio: float     # highest ratio across the 3 windows


@dataclass
class LoopMonitorResult:
    """Result of monitoring all loops."""
    loop_statuses: dict[str, LoopStatus] = field(default_factory=dict)
    overall_health: LoopHealthStatus = LoopHealthStatus.HEALTHY
    any_exceeded: bool = False
    checked_at: datetime = field(default_factory=datetime.utcnow)


# ------------------------------------------------------------------ #
# L28 Loop Monitor
# ------------------------------------------------------------------ #

class LoopMonitor:
    """
    L28 Loop Monitor.

    Reads from LoopCounter to produce health status for each loop.
    The EvaluationContext.loop_counts field is populated from LoopCounter
    directly by the MainLoop -- this engine provides the monitoring overlay.

    Usage:
        counter = LoopCounter()
        monitor = LoopMonitor(counter)
        result = monitor.check("INC-001")
        # result.any_exceeded -> if True, G-24 should fail
    """

    LOOP_NAMES = ["RECOVERY", "MAIN", "SELF_IMPROVEMENT", "EVOLUTION"]

    def __init__(self, counter: LoopCounter) -> None:
        self._counter = counter
        self._last_result: Optional[LoopMonitorResult] = None

    @property
    def last_result(self) -> Optional[LoopMonitorResult]:
        return self._last_result

    def check(self, incident_id: str) -> LoopMonitorResult:
        """
        Check health of all loops for the given incident.

        Args:
            incident_id: current incident/session identifier

        Returns:
            LoopMonitorResult with per-loop health and overall status
        """
        statuses: dict[str, LoopStatus] = {}
        worst_health = LoopHealthStatus.HEALTHY

        for name in self.LOOP_NAMES:
            counts = self._counter.counts(name, incident_id)
            ceiling = get_loop_ceiling(name)

            ratios = []
            if ceiling.per_incident > 0:
                ratios.append(counts["incident"] / ceiling.per_incident)
            if ceiling.per_day > 0:
                ratios.append(counts["daily"] / ceiling.per_day)
            if ceiling.per_week > 0:
                ratios.append(counts["weekly"] / ceiling.per_week)

            max_ratio = max(ratios) if ratios else 0.0

            if max_ratio > 1.0:
                health = LoopHealthStatus.EXCEEDED
            elif max_ratio >= CRITICAL_THRESHOLD:
                health = LoopHealthStatus.CRITICAL
            elif max_ratio >= WARNING_THRESHOLD:
                health = LoopHealthStatus.WARNING
            else:
                health = LoopHealthStatus.HEALTHY

            statuses[name] = LoopStatus(
                loop_name=name,
                incident_count=counts["incident"],
                daily_count=counts["daily"],
                weekly_count=counts["weekly"],
                incident_ceiling=ceiling.per_incident,
                daily_ceiling=ceiling.per_day,
                weekly_ceiling=ceiling.per_week,
                health=health,
                max_usage_ratio=round(max_ratio, 4),
            )

            # Track worst health
            if health.value > worst_health.value or \
               list(LoopHealthStatus).index(health) > list(LoopHealthStatus).index(worst_health):
                worst_health = health

        any_exceeded = any(s.health == LoopHealthStatus.EXCEEDED for s in statuses.values())

        result = LoopMonitorResult(
            loop_statuses=statuses,
            overall_health=worst_health,
            any_exceeded=any_exceeded,
        )
        self._last_result = result
        return result

    def check_single(self, loop_name: str, incident_id: str) -> LoopStatus:
        """Check health of a single loop."""
        counts = self._counter.counts(loop_name, incident_id)
        ceiling = get_loop_ceiling(loop_name)

        ratios = []
        if ceiling.per_incident > 0:
            ratios.append(counts["incident"] / ceiling.per_incident)
        if ceiling.per_day > 0:
            ratios.append(counts["daily"] / ceiling.per_day)
        if ceiling.per_week > 0:
            ratios.append(counts["weekly"] / ceiling.per_week)

        max_ratio = max(ratios) if ratios else 0.0

        if max_ratio > 1.0:
            health = LoopHealthStatus.EXCEEDED
        elif max_ratio >= CRITICAL_THRESHOLD:
            health = LoopHealthStatus.CRITICAL
        elif max_ratio >= WARNING_THRESHOLD:
            health = LoopHealthStatus.WARNING
        else:
            health = LoopHealthStatus.HEALTHY

        return LoopStatus(
            loop_name=loop_name,
            incident_count=counts["incident"],
            daily_count=counts["daily"],
            weekly_count=counts["weekly"],
            incident_ceiling=ceiling.per_incident,
            daily_ceiling=ceiling.per_day,
            weekly_ceiling=ceiling.per_week,
            health=health,
            max_usage_ratio=round(max_ratio, 4),
        )
