"""
K-Dexter Trend Observation Service (v1)

Two-window comparative observation service. Reads from MetricSnapshotBuffer
and computes count-based deltas between current 60m and previous 60m windows.

NEVER writes to any ledger. NEVER triggers actions or transitions.
Output is factual observation — no future estimation or auto-judgment.

Scope (v1):
  - 2 equal windows (current 60m vs. previous 60m)
  - Count-based metrics only (no rates, no percentiles)
  - In-memory ring buffer only (volatile, restart clears)
  - Template-locked descriptions (OC-08)

Safety:
  - Read-only: no write operations
  - Simulation-only: no execution triggered
  - No future estimation or extrapolation
  - No judgment language
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from app.schemas.trend_observation_schema import (
    TrendObservationSchema,
    MetricComparison,
    WindowSnapshot,
    TrendDensitySignal,
    TrendSafety,
)

if TYPE_CHECKING:
    from app.core.metric_snapshot_buffer import MetricSnapshotBuffer, MetricSnapshot


# -- Constants ---------------------------------------------------------------- #

_WINDOW_MINUTES = 60
_MIN_SAMPLES = 5  # minimum snapshots per window for valid comparison

# Description templates (OC-08 pattern-based)
_TEMPLATE_NO_BUFFER = "No snapshot buffer available."
_TEMPLATE_INSUFFICIENT = "Insufficient history for comparison."
_TEMPLATE_WAITING = "Waiting for comparison window ({samples} snapshot(s) available)."
_TEMPLATE_STABLE = "{name}: {current} (stable vs. previous window)."
_TEMPLATE_CHANGE = "{name}: {previous} in previous window, {current} in current window (delta: {delta:+d})."

# Density templates
_DENSITY_NONE = "No trend data available."
_DENSITY_INSUFFICIENT = "Insufficient history. Buffer started {since}."
_DENSITY_AVAILABLE = "{tracked} metric(s) compared. {changed} changed vs. previous window."


# -- Public API --------------------------------------------------------------- #

def build_trend_observation(
    snapshot_buffer: Optional["MetricSnapshotBuffer"] = None,
) -> TrendObservationSchema:
    """
    Build two-window comparative observation from snapshot buffer.

    Read-only: only calls get_windows() and list_snapshots().
    Never writes, never transitions, never triggers actions.

    Returns TrendObservationSchema with count-based metric comparisons.
    """
    if snapshot_buffer is None:
        return TrendObservationSchema(
            density=TrendDensitySignal(description=_TEMPLATE_NO_BUFFER),
            safety=TrendSafety(),
        )

    now = datetime.now(timezone.utc)
    current_snaps, previous_snaps = snapshot_buffer.get_windows(
        window_minutes=_WINDOW_MINUTES, now=now,
    )

    since_startup = snapshot_buffer.started_at.isoformat()

    # Check sufficiency
    current_sufficient = len(current_snaps) >= _MIN_SAMPLES
    previous_sufficient = len(previous_snaps) >= _MIN_SAMPLES
    both_sufficient = current_sufficient and previous_sufficient

    # -- Build metric comparisons ----------------------------------------- #
    blocked = _build_comparison(
        "blocked_total", current_snaps, previous_snaps,
        both_sufficient, now,
    )
    pending_retry = _build_comparison(
        "pending_retry_total", current_snaps, previous_snaps,
        both_sufficient, now,
    )
    review = _build_comparison(
        "review_total", current_snaps, previous_snaps,
        both_sufficient, now,
    )
    watch = _build_comparison(
        "watch_total", current_snaps, previous_snaps,
        both_sufficient, now,
    )

    # -- Density signal --------------------------------------------------- #
    all_comparisons = [blocked, pending_retry, review, watch]
    density = _build_density_signal(
        all_comparisons, both_sufficient, since_startup, snapshot_buffer.count,
    )

    return TrendObservationSchema(
        blocked_trend=blocked,
        pending_retry_trend=pending_retry,
        review_trend=review,
        watch_trend=watch,
        window_minutes=_WINDOW_MINUTES,
        density=density,
        safety=TrendSafety(),
    )


# -- Comparison builder ------------------------------------------------------- #

def _build_comparison(
    metric_name: str,
    current_snaps: list,
    previous_snaps: list,
    both_sufficient: bool,
    now: datetime,
) -> MetricComparison:
    """Build a single metric comparison between two windows."""
    from datetime import timedelta

    window = timedelta(minutes=_WINDOW_MINUTES)
    current_start = now - window
    previous_start = now - (2 * window)

    current_window = WindowSnapshot(
        window_label="current",
        window_start=current_start.isoformat(),
        window_end=now.isoformat(),
        sample_count=len(current_snaps),
        value=_last_value(current_snaps, metric_name),
    )

    previous_window = WindowSnapshot(
        window_label="previous",
        window_start=previous_start.isoformat(),
        window_end=current_start.isoformat(),
        sample_count=len(previous_snaps),
        value=_last_value(previous_snaps, metric_name),
    )

    if not both_sufficient:
        total_samples = len(current_snaps) + len(previous_snaps)
        return MetricComparison(
            metric_name=metric_name,
            current_window=current_window,
            previous_window=previous_window,
            insufficient_data=True,
            description=_TEMPLATE_WAITING.format(samples=total_samples)
            if total_samples > 0 else _TEMPLATE_INSUFFICIENT,
        )

    current_val = current_window.value
    previous_val = previous_window.value
    delta = current_val - previous_val
    direction = _classify_direction(delta)

    if direction == "stable":
        description = _TEMPLATE_STABLE.format(
            name=metric_name, current=current_val,
        )
    else:
        description = _TEMPLATE_CHANGE.format(
            name=metric_name,
            previous=previous_val,
            current=current_val,
            delta=delta,
        )

    return MetricComparison(
        metric_name=metric_name,
        current_window=current_window,
        previous_window=previous_window,
        delta=delta,
        direction=direction,
        insufficient_data=False,
        description=description,
    )


# -- Density signal ---------------------------------------------------------- #

def _build_density_signal(
    comparisons: list[MetricComparison],
    both_sufficient: bool,
    since_startup: str,
    buffer_count: int,
) -> TrendDensitySignal:
    """Build descriptive density signal."""
    if not both_sufficient:
        if buffer_count == 0:
            desc = _DENSITY_NONE
        else:
            desc = _DENSITY_INSUFFICIENT.format(since=since_startup)

        return TrendDensitySignal(
            trend_available=False,
            metrics_tracked=len(comparisons),
            since_startup=since_startup,
            description=desc,
        )

    changed = sum(1 for c in comparisons if not c.insufficient_data and c.direction != "stable")

    return TrendDensitySignal(
        trend_available=True,
        metrics_tracked=len(comparisons),
        metrics_with_change=changed,
        since_startup=since_startup,
        description=_DENSITY_AVAILABLE.format(
            tracked=len(comparisons), changed=changed,
        ),
    )


# -- Helpers ----------------------------------------------------------------- #

def _last_value(snapshots: list, metric_name: str) -> int:
    """Get the last (most recent) snapshot value for a metric."""
    if not snapshots:
        return 0
    last = snapshots[-1]
    return getattr(last, metric_name, 0)


def _classify_direction(delta: int) -> str:
    """Classify delta as increasing, decreasing, or stable."""
    if delta > 0:
        return "increasing"
    elif delta < 0:
        return "decreasing"
    return "stable"
