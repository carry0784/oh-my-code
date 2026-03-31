"""
K-Dexter Trend Observation Schema (v1)

Two-window comparative observation: current 60m vs. previous 60m.
Count-based metrics only. No rates, no percentiles, no mean.

This is a volatile observation — data comes from an in-memory ring buffer
that is cleared on process restart.

Safety:
  - Read-only: no writes, no mutations
  - Simulation-only: no execution triggered
  - No prediction: no extrapolation, no forecasting
  - No recommendation: no action trigger
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class WindowSnapshot(BaseModel):
    """Aggregated counts for a single time window."""
    window_label: str = ""           # "current" | "previous"
    window_start: str = ""           # ISO timestamp
    window_end: str = ""             # ISO timestamp
    sample_count: int = 0            # number of snapshots in window
    value: int = 0                   # aggregated count (last snapshot in window)


class MetricComparison(BaseModel):
    """Two-window comparison for a single count-based metric."""
    metric_name: str = ""
    current_window: WindowSnapshot = Field(default_factory=lambda: WindowSnapshot(window_label="current"))
    previous_window: WindowSnapshot = Field(default_factory=lambda: WindowSnapshot(window_label="previous"))
    delta: int = 0                   # current - previous (absolute count difference)
    direction: str = "stable"        # "increasing" | "decreasing" | "stable"
    insufficient_data: bool = True
    description: str = ""            # template-locked (OC-08)


class TrendDensitySignal(BaseModel):
    """Descriptive density signal for trend observation."""
    trend_available: bool = False
    metrics_tracked: int = 0
    metrics_with_change: int = 0
    since_startup: str = ""          # ISO timestamp — when buffer started
    volatile: bool = True            # always True — in-memory only
    description: str = ""


class TrendSafety(BaseModel):
    """Safety invariant — observation layer standard (4 fields)."""
    read_only: bool = True
    simulation_only: bool = True
    no_action_executed: bool = True
    no_prediction: bool = True


class TrendObservationSchema(BaseModel):
    """
    Trend Observation v1 — two-window comparative observation.

    Compares count-based metrics between current 60m window and previous 60m window.
    No rates, no percentiles, no forecasting. Volatile (in-memory buffer).
    """
    blocked_trend: MetricComparison = Field(default_factory=lambda: MetricComparison(metric_name="blocked_total"))
    pending_retry_trend: MetricComparison = Field(default_factory=lambda: MetricComparison(metric_name="pending_retry_total"))
    review_trend: MetricComparison = Field(default_factory=lambda: MetricComparison(metric_name="review_total"))
    watch_trend: MetricComparison = Field(default_factory=lambda: MetricComparison(metric_name="watch_total"))
    window_minutes: int = 60
    density: TrendDensitySignal = Field(default_factory=TrendDensitySignal)
    safety: TrendSafety = Field(default_factory=TrendSafety)
