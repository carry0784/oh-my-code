"""
K-Dexter Retry Pressure Service

Read-only observation service that reads retry plan queue state
and computes factual backlog/distribution/density metrics.

NEVER writes to any store. NEVER executes retries or transitions plans.
Output is factual observation — no future estimation or auto-judgment.
All output is factual observation only.

Data source:
  RetryPlanStore.list_plans() and count methods.
  Reads plan status, channel, and severity distributions.

Safety:
  - Read-only: no write operations
  - Simulation-only: no retry execution
  - No future estimation or scoring
"""

from __future__ import annotations

from collections import Counter
from typing import Optional, TYPE_CHECKING

from app.schemas.retry_pressure_schema import (
    RetryPressureSchema,
    RetryStatusDistribution,
    RetryChannelDistribution,
    RetrySeverityDistribution,
    RetryDensitySignal,
    RetryPressureSafety,
)

if TYPE_CHECKING:
    from app.core.retry_plan_store import RetryPlanStore


# Concentration threshold — >66% in a single channel
_CONCENTRATION_THRESHOLD = 2 / 3

# Description templates (OC-08 pattern-based)
_TEMPLATE_NONE = "No retry plans."
_TEMPLATE_NO_PENDING = "{total} retry plan(s), {pending} pending."
_TEMPLATE_BASIC = "{total} retry plan(s), {pending} pending."
_TEMPLATE_CONCENTRATED = (
    "{total} retry plan(s), {pending} pending. "
    "Concentrated in {channel} channel ({count}/{pending}, {ratio})."
)


def build_retry_pressure(
    retry_store: Optional["RetryPlanStore"] = None,
) -> RetryPressureSchema:
    """
    Build retry pressure observation from retry plan store.

    Read-only: only calls list_plans() and count().
    Never enqueues, executes, cancels, or transitions any plan.

    Returns RetryPressureSchema with backlog, distribution, and density.
    """
    if retry_store is None:
        return RetryPressureSchema(
            density=RetryDensitySignal(description=_TEMPLATE_NONE),
            safety=RetryPressureSafety(),
        )

    # -- Read plans (read-only) ------------------------------------------- #
    all_plans = retry_store.list_plans(limit=200)
    total_plans = len(all_plans)

    if total_plans == 0:
        return RetryPressureSchema(
            density=RetryDensitySignal(description=_TEMPLATE_NONE),
            safety=RetryPressureSafety(),
        )

    # -- By status -------------------------------------------------------- #
    status_counts = Counter()
    for plan in all_plans:
        status_counts[plan.get("status", "unknown")] += 1

    by_status = RetryStatusDistribution(
        pending=status_counts.get("pending", 0),
        cancelled=status_counts.get("cancelled", 0),
        executed=status_counts.get("executed", 0),
        expired=status_counts.get("expired", 0),
    )

    pending_count = by_status.pending
    backlog_ratio = (pending_count / total_plans) if total_plans > 0 else 0.0

    # -- By channel (pending only) ---------------------------------------- #
    channel_counts = Counter()
    for plan in all_plans:
        if plan.get("status") == "pending":
            channel_counts[plan.get("channel", "unknown")] += 1

    by_channel = [
        RetryChannelDistribution(channel=ch, count=cnt)
        for ch, cnt in channel_counts.most_common(10)
    ]

    # -- By severity (pending only) --------------------------------------- #
    severity_counts = Counter()
    for plan in all_plans:
        if plan.get("status") == "pending":
            sev = plan.get("severity_tier", "unknown")
            if sev:
                severity_counts[sev] += 1

    by_severity = [
        RetrySeverityDistribution(severity=sev, count=cnt)
        for sev, cnt in severity_counts.most_common(10)
    ]

    # -- Density signal --------------------------------------------------- #
    density = _build_density_signal(total_plans, pending_count, channel_counts)

    return RetryPressureSchema(
        total_plans=total_plans,
        pending_count=pending_count,
        backlog_ratio=round(backlog_ratio, 3),
        by_status=by_status,
        by_channel=by_channel,
        by_severity=by_severity,
        density=density,
        safety=RetryPressureSafety(),
    )


def _build_density_signal(
    total_plans: int,
    pending_count: int,
    channel_counts: Counter,
) -> RetryDensitySignal:
    """
    Build descriptive retry density signal.

    NOT prescriptive. Describes observable patterns only.
    """
    if total_plans == 0 or pending_count == 0:
        return RetryDensitySignal(
            description=_TEMPLATE_NO_PENDING.format(total=total_plans, pending=0),
        )

    has_pending = pending_count > 0
    pending_ratio = pending_count / total_plans if total_plans > 0 else 0.0

    # Channel concentration
    dominant_channel = channel_counts.most_common(1)[0][0] if channel_counts else ""
    dominant_count = channel_counts.get(dominant_channel, 0)
    dominant_ratio = dominant_count / pending_count if pending_count > 0 else 0.0
    is_concentrated = dominant_ratio > _CONCENTRATION_THRESHOLD

    # Build description
    if is_concentrated:
        description = _TEMPLATE_CONCENTRATED.format(
            total=total_plans,
            pending=pending_count,
            channel=dominant_channel,
            count=dominant_count,
            ratio=f"{dominant_ratio:.0%}",
        )
    else:
        description = _TEMPLATE_BASIC.format(
            total=total_plans,
            pending=pending_count,
        )

    return RetryDensitySignal(
        has_pending=has_pending,
        pending_ratio=round(pending_ratio, 3),
        is_channel_concentrated=is_concentrated,
        dominant_channel=dominant_channel,
        dominant_channel_ratio=round(dominant_ratio, 3),
        description=description,
    )
