"""
K-Dexter Latency Observation Service (v1)

Read-only observation service that computes per-tier elapsed time
from proposal creation to receipt milestone.

NEVER writes to any ledger. NEVER triggers actions or transitions.
Output is factual observation — no future estimation or auto-judgment.

Scope (v1):
  - Per-tier only (no end-to-end cross-tier latency)
  - Median, min, max only (no mean, no percentiles)
  - Template-locked descriptions (OC-08)

Data sources:
  Tier 1: ActionLedger.get_proposals() → receipt.created_at
  Tier 2: ExecutionLedger.get_proposals() → receipt.execution_ready_at
  Tier 3: SubmitLedger.get_proposals() → receipt.submit_ready_at
  Tier 4: OrderExecutor.get_history() → executed_at

Safety:
  - Read-only: no write operations
  - Simulation-only: no execution triggered
  - No contractual targets, no scoring, no judgment
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from app.schemas.latency_observation_schema import (
    LatencyObservationSchema,
    TierLatency,
    LatencyDensitySignal,
    LatencySafety,
)

if TYPE_CHECKING:
    from app.agents.action_ledger import ActionLedger
    from app.services.execution_ledger import ExecutionLedger
    from app.services.submit_ledger import SubmitLedger
    from app.services.order_executor import OrderExecutor


# -- Constants ---------------------------------------------------------------- #

_SAMPLE_LIMIT = 200

# Description templates (OC-08 pattern-based)
_TEMPLATE_NONE = "No latency measurements available."
_TEMPLATE_SINGLE = "{count} tier(s) measured. Median elapsed: {median:.1f}s ({tier})."
_TEMPLATE_MULTI = "{count} tier(s) measured. Slowest median: {median:.1f}s ({tier})."


# -- Public API --------------------------------------------------------------- #

def build_latency_observation(
    action_ledger: Optional["ActionLedger"] = None,
    execution_ledger: Optional["ExecutionLedger"] = None,
    submit_ledger: Optional["SubmitLedger"] = None,
    order_executor: Optional["OrderExecutor"] = None,
) -> LatencyObservationSchema:
    """
    Build per-tier latency observation from live ledger instances.

    Read-only: only calls get_proposals() and get_history().
    Never writes, never transitions, never triggers actions.

    Returns LatencyObservationSchema with per-tier elapsed summary.
    """
    # -- Tier 1: Agent ---------------------------------------------------- #
    agent_lat = _measure_tier(
        tier_name="Agent",
        tier_number=1,
        ledger=action_ledger,
        receipt_timestamp_key="created_at",
    )

    # -- Tier 2: Execution ------------------------------------------------ #
    exec_lat = _measure_tier(
        tier_name="Execution",
        tier_number=2,
        ledger=execution_ledger,
        receipt_timestamp_key="execution_ready_at",
    )

    # -- Tier 3: Submit --------------------------------------------------- #
    submit_lat = _measure_tier(
        tier_name="Submit",
        tier_number=3,
        ledger=submit_ledger,
        receipt_timestamp_key="submit_ready_at",
    )

    # -- Tier 4: Orders --------------------------------------------------- #
    order_lat = _measure_order_tier(order_executor)

    # -- Density signal --------------------------------------------------- #
    density = _build_density_signal(agent_lat, exec_lat, submit_lat, order_lat)

    return LatencyObservationSchema(
        agent_latency=agent_lat,
        execution_latency=exec_lat,
        submit_latency=submit_lat,
        order_latency=order_lat,
        density=density,
        safety=LatencySafety(),
    )


# -- Tier measurement -------------------------------------------------------- #

def _measure_tier(
    tier_name: str,
    tier_number: int,
    ledger: object,
    receipt_timestamp_key: str,
) -> TierLatency:
    """Measure elapsed time for a proposal-based tier."""
    base = TierLatency(tier_name=tier_name, tier_number=tier_number)

    if ledger is None:
        return base

    proposals = ledger.get_proposals()
    if not proposals:
        return base

    # Apply sample limit
    sample_limited = len(proposals) > _SAMPLE_LIMIT
    proposals = proposals[-_SAMPLE_LIMIT:]  # most recent

    elapsed_values = []
    excluded = 0

    for p in proposals:
        receipt = p.get("receipt")
        if receipt is None:
            continue  # no receipt yet — not measured, not excluded

        start_str = p.get("created_at")
        end_str = receipt.get(receipt_timestamp_key)

        if not start_str or not end_str:
            excluded += 1
            continue

        start_dt = _parse_iso(start_str)
        end_dt = _parse_iso(end_str)

        if start_dt is None or end_dt is None:
            excluded += 1
            continue

        elapsed = (end_dt - start_dt).total_seconds()
        if elapsed < 0:
            excluded += 1
            continue

        elapsed_values.append(elapsed)

    if not elapsed_values:
        return TierLatency(
            tier_name=tier_name,
            tier_number=tier_number,
            excluded_count=excluded,
            sample_limited=sample_limited,
        )

    elapsed_values.sort()
    return TierLatency(
        tier_name=tier_name,
        tier_number=tier_number,
        measured=True,
        sample_size=len(elapsed_values),
        excluded_count=excluded,
        sample_limited=sample_limited,
        min_seconds=round(elapsed_values[0], 3),
        max_seconds=round(elapsed_values[-1], 3),
        median_seconds=round(_median(elapsed_values), 3),
    )


def _measure_order_tier(executor: Optional["OrderExecutor"]) -> TierLatency:
    """Measure elapsed time for the order executor tier."""
    base = TierLatency(tier_name="Orders", tier_number=4)

    if executor is None:
        return base

    history = executor.get_history()
    if not history:
        return base

    sample_limited = len(history) > _SAMPLE_LIMIT
    history = history[-_SAMPLE_LIMIT:]

    elapsed_values = []
    excluded = 0

    for order in history:
        start_str = order.get("created_at")
        end_str = order.get("executed_at")

        if not start_str or not end_str:
            excluded += 1
            continue

        start_dt = _parse_iso(start_str)
        end_dt = _parse_iso(end_str)

        if start_dt is None or end_dt is None:
            excluded += 1
            continue

        elapsed = (end_dt - start_dt).total_seconds()
        if elapsed < 0:
            excluded += 1
            continue

        elapsed_values.append(elapsed)

    if not elapsed_values:
        return TierLatency(
            tier_name="Orders",
            tier_number=4,
            excluded_count=excluded,
            sample_limited=sample_limited,
        )

    elapsed_values.sort()
    return TierLatency(
        tier_name="Orders",
        tier_number=4,
        measured=True,
        sample_size=len(elapsed_values),
        excluded_count=excluded,
        sample_limited=sample_limited,
        min_seconds=round(elapsed_values[0], 3),
        max_seconds=round(elapsed_values[-1], 3),
        median_seconds=round(_median(elapsed_values), 3),
    )


# -- Density signal ---------------------------------------------------------- #

def _build_density_signal(*tiers: TierLatency) -> LatencyDensitySignal:
    """Build descriptive density signal from tier measurements."""
    measured = [t for t in tiers if t.measured]

    if not measured:
        return LatencyDensitySignal(description=_TEMPLATE_NONE)

    slowest = max(measured, key=lambda t: t.median_seconds)

    if len(measured) == 1:
        description = _TEMPLATE_SINGLE.format(
            count=1,
            median=slowest.median_seconds,
            tier=slowest.tier_name,
        )
    else:
        description = _TEMPLATE_MULTI.format(
            count=len(measured),
            median=slowest.median_seconds,
            tier=slowest.tier_name,
        )

    return LatencyDensitySignal(
        has_measurements=True,
        tiers_measured=len(measured),
        slowest_tier=slowest.tier_name,
        slowest_median=round(slowest.median_seconds, 3),
        description=description,
    )


# -- Helpers ----------------------------------------------------------------- #

def _parse_iso(value: str) -> Optional[datetime]:
    """Parse ISO datetime string safely. Returns None on failure."""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        return None


def _median(values: list[float]) -> float:
    """Compute median of a sorted list."""
    n = len(values)
    if n == 0:
        return 0.0
    mid = n // 2
    if n % 2 == 0:
        return (values[mid - 1] + values[mid]) / 2.0
    return values[mid]
