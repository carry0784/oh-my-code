"""
K-Dexter WATCH Volume Service

Read-only observation service that extracts WATCH-class cleanup candidates
and computes factual volume/distribution/density metrics.

NEVER writes to any Ledger. NEVER deletes or transitions proposals.
Output is factual observation — no future estimation or auto-judgment.
All output is factual observation only.

Data source:
  CleanupSimulationReport from simulate_cleanup()
  Only WATCH-class candidates are counted.

Safety:
  - Read-only: no write operations
  - Simulation-only: no cleanup executed
  - No future estimation or scoring
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from app.services.cleanup_simulation_service import (
    simulate_cleanup,
    ACTION_WATCH,
)
from app.core.stale_contract import classify_stale_band
from app.schemas.watch_volume_schema import (
    WatchVolumeSchema,
    WatchTierDistribution,
    WatchReasonDistribution,
    WatchBandDistribution,
    WatchDensitySignal,
    WatchVolumeSafety,
)

if TYPE_CHECKING:
    from app.agents.action_ledger import ActionLedger
    from app.services.execution_ledger import ExecutionLedger
    from app.services.submit_ledger import SubmitLedger


# -- Reason code mapping --------------------------------------------------- #

_REASON_TO_FIELD = {
    "STALE_AGENT": "stale_agent",
    "STALE_EXECUTION": "stale_execution",
    "STALE_SUBMIT": "stale_submit",
    "ORPHAN_EXEC_PARENT": "orphan_exec_parent",
    "ORPHAN_SUBMIT_PARENT": "orphan_submit_parent",
    "STALE_AND_ORPHAN": "stale_and_orphan",
}

# Default stale thresholds per tier (from stale_contract)
_TIER_THRESHOLDS = {"agent": 600.0, "execution": 300.0, "submit": 180.0}

# Concentration threshold — >66% in a single tier
_CONCENTRATION_THRESHOLD = 2 / 3


def build_watch_volume(
    action_ledger: Optional["ActionLedger"] = None,
    execution_ledger: Optional["ExecutionLedger"] = None,
    submit_ledger: Optional["SubmitLedger"] = None,
) -> WatchVolumeSchema:
    """
    Build WATCH volume observation from cleanup simulation.

    Read-only: only calls simulate_cleanup().
    Never writes, deletes, or transitions any proposal.

    Returns WatchVolumeSchema with volume, distribution, and density.
    """
    report = simulate_cleanup(action_ledger, execution_ledger, submit_ledger)

    # -- Extract WATCH candidates ----------------------------------------- #
    watch_candidates = [c for c in report.candidates if c.get("action_class") == ACTION_WATCH]

    watch_total = len(watch_candidates)
    candidate_total = report.total_candidates
    watch_ratio = (watch_total / candidate_total) if candidate_total > 0 else 0.0

    # -- By tier ---------------------------------------------------------- #
    tier_counts = {"agent": 0, "execution": 0, "submit": 0}
    for c in watch_candidates:
        tier = c.get("tier", "")
        if tier in tier_counts:
            tier_counts[tier] += 1

    by_tier = WatchTierDistribution(**tier_counts)

    # -- By reason -------------------------------------------------------- #
    reason_counts = {field: 0 for field in _REASON_TO_FIELD.values()}
    for c in watch_candidates:
        reason_code = c.get("reason_code", "")
        field_name = _REASON_TO_FIELD.get(reason_code, "")
        if field_name:
            reason_counts[field_name] += 1

    by_reason = WatchReasonDistribution(**reason_counts)

    # -- By band ---------------------------------------------------------- #
    band_counts = {"early": 0, "review": 0, "prolonged": 0}
    for c in watch_candidates:
        tier = c.get("tier", "agent")
        threshold = _TIER_THRESHOLDS.get(tier, 600.0)
        age = c.get("stale_age_seconds", 0.0)
        if age > 0 and threshold > 0:
            multiplier = age / threshold
            band = classify_stale_band(multiplier)
            if band in band_counts:
                band_counts[band] += 1

    by_band = WatchBandDistribution(**band_counts)

    # -- Density signal --------------------------------------------------- #
    density = _build_density_signal(watch_total, tier_counts, band_counts)

    return WatchVolumeSchema(
        watch_total=watch_total,
        candidate_total=candidate_total,
        watch_ratio=round(watch_ratio, 3),
        by_tier=by_tier,
        by_reason=by_reason,
        by_band=by_band,
        density=density,
        safety=WatchVolumeSafety(),
    )


def _build_density_signal(
    watch_total: int,
    tier_counts: dict[str, int],
    band_counts: dict[str, int],
) -> WatchDensitySignal:
    """
    Build descriptive density signal from WATCH distribution.

    NOT prescriptive. Describes observable patterns only.
    """
    if watch_total == 0:
        return WatchDensitySignal(description="No WATCH candidates.")

    # Find dominant tier
    dominant_tier = max(tier_counts, key=tier_counts.get)
    dominant_count = tier_counts[dominant_tier]
    dominant_ratio = dominant_count / watch_total if watch_total > 0 else 0.0
    is_concentrated = dominant_ratio > _CONCENTRATION_THRESHOLD

    # Prolonged check
    prolonged_count = band_counts.get("prolonged", 0)
    has_prolonged = prolonged_count > 0

    # Build description
    parts = [f"{watch_total} WATCH candidate(s)."]
    if is_concentrated:
        parts.append(
            f"Concentrated in {dominant_tier} tier "
            f"({dominant_count}/{watch_total}, {dominant_ratio:.0%})."
        )
    if has_prolonged:
        parts.append(f"{prolonged_count} in prolonged band (>=3x threshold).")

    return WatchDensitySignal(
        is_concentrated=is_concentrated,
        dominant_tier=dominant_tier,
        dominant_ratio=round(dominant_ratio, 3),
        has_prolonged=has_prolonged,
        prolonged_count=prolonged_count,
        description=" ".join(parts),
    )
