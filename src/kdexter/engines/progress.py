"""
Progress Engine -- L30 K-Dexter AOS

Purpose: track overall system progress metrics as named float values.
Provides a lightweight metric store for other engines and gates to query.

Governance: B2 (governance_layer_map.md -- L30)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ------------------------------------------------------------------ #
# Data models
# ------------------------------------------------------------------ #


@dataclass
class MetricRecord:
    """Internal record for a single tracked metric."""

    name: str
    value: float
    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    update_count: int = 0


# ------------------------------------------------------------------ #
# L30 Progress Engine
# ------------------------------------------------------------------ #


class ProgressEngine:
    """
    L30 Progress Engine.

    Maintains a dict-based store of named float metrics. Callers record
    values over time; the engine exposes the most-recent value per metric
    and a full snapshot via summary().

    Usage:
        engine = ProgressEngine()
        engine.record("tasks_completed", 5.0)
        engine.record("tasks_total", 10.0)
        val = engine.get("tasks_completed")   # 5.0
        snap = engine.summary()               # {"tasks_completed": 5.0, ...}
    """

    def __init__(self) -> None:
        self._metrics: dict[str, MetricRecord] = {}

    # ---------------------------------------------------------------- #
    # Mutation
    # ---------------------------------------------------------------- #

    def record(self, metric_name: str, value: float) -> None:
        """
        Record (overwrite) the current value of a metric.

        Args:
            metric_name: unique name for the metric
            value: current float value to store
        """
        existing = self._metrics.get(metric_name)
        if existing is not None:
            existing.value = value
            existing.recorded_at = datetime.now(timezone.utc)
            existing.update_count += 1
        else:
            self._metrics[metric_name] = MetricRecord(
                name=metric_name,
                value=value,
            )

    def increment(self, metric_name: str, delta: float = 1.0) -> float:
        """
        Increment a metric by delta (creates it at 0 if absent).

        Returns:
            New value after increment
        """
        current = self.get(metric_name) or 0.0
        new_value = current + delta
        self.record(metric_name, new_value)
        return new_value

    def reset(self, metric_name: str) -> None:
        """Reset a single metric to 0.0 (does nothing if absent)."""
        if metric_name in self._metrics:
            self.record(metric_name, 0.0)

    def clear(self) -> None:
        """Remove all metrics."""
        self._metrics.clear()

    # ---------------------------------------------------------------- #
    # Queries
    # ---------------------------------------------------------------- #

    def get(self, metric_name: str) -> Optional[float]:
        """
        Return the current value of a metric.

        Returns:
            float value if the metric exists, None otherwise
        """
        record = self._metrics.get(metric_name)
        return record.value if record is not None else None

    def summary(self) -> dict[str, float]:
        """
        Return a snapshot dict of all current metric values.

        Returns:
            {metric_name: value} for all tracked metrics
        """
        return {name: rec.value for name, rec in self._metrics.items()}

    def metric_names(self) -> list[str]:
        """Return all tracked metric names."""
        return list(self._metrics.keys())

    def __len__(self) -> int:
        return len(self._metrics)
