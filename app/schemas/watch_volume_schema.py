"""
K-Dexter WATCH Volume Schema (Typed)

Read-only observation card for WATCH action class volume and distribution.
Provides operator with factual count/ratio/distribution data only.

Design rules:
  - No prediction, recommendation, or auto-judgment
  - No action verbs, no execution triggers, no write paths
  - Count/ratio/window definitions must be explicit
  - Density signal is descriptive, not prescriptive
  - Safety labels are structurally fixed (always True)

Data source:
  CleanupSimulationReport.candidates where action_class == WATCH
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# -- Nested models --------------------------------------------------------- #


class WatchTierDistribution(BaseModel):
    """WATCH candidate count per tier."""

    agent: int = 0
    execution: int = 0
    submit: int = 0


class WatchReasonDistribution(BaseModel):
    """WATCH candidate count per reason code."""

    stale_agent: int = 0
    stale_execution: int = 0
    stale_submit: int = 0
    orphan_exec_parent: int = 0
    orphan_submit_parent: int = 0
    stale_and_orphan: int = 0


class WatchBandDistribution(BaseModel):
    """WATCH candidate count per stale band (early/review/prolonged)."""

    early: int = 0
    review: int = 0
    prolonged: int = 0


class WatchDensitySignal(BaseModel):
    """
    Descriptive density signal for operator awareness.

    NOT prescriptive. Describes observable patterns only.
    """

    is_concentrated: bool = False  # >66% in single tier
    dominant_tier: str = ""  # tier with most WATCH candidates
    dominant_ratio: float = 0.0  # ratio of dominant tier
    has_prolonged: bool = False  # any candidate in prolonged band
    prolonged_count: int = 0  # count of prolonged candidates
    description: str = ""  # human-readable summary


class WatchVolumeSafety(BaseModel):
    """Structurally fixed safety labels. All ALWAYS True."""

    read_only: bool = Field(default=True, description="ALWAYS True.")
    simulation_only: bool = Field(default=True, description="ALWAYS True.")
    no_action_executed: bool = Field(default=True, description="ALWAYS True.")
    no_prediction: bool = Field(default=True, description="ALWAYS True. No forecasting.")


# -- Main schema ----------------------------------------------------------- #


class WatchVolumeSchema(BaseModel):
    """
    WATCH volume observation card.

    Factual summary of WATCH-class cleanup candidates.
    Read-only, no prediction, no recommendation.

    Relationship:
      CleanupSimulationReport -> WatchVolumeSchema (observation)
      ObservationSummarySchema (Layer 4) contains candidate totals
      This card drills down into the WATCH subset specifically
    """

    watch_total: int = 0
    candidate_total: int = 0  # total across all action classes
    watch_ratio: float = 0.0  # watch_total / candidate_total (0 if no candidates)
    by_tier: WatchTierDistribution = Field(default_factory=WatchTierDistribution)
    by_reason: WatchReasonDistribution = Field(default_factory=WatchReasonDistribution)
    by_band: WatchBandDistribution = Field(default_factory=WatchBandDistribution)
    density: WatchDensitySignal = Field(default_factory=WatchDensitySignal)
    safety: WatchVolumeSafety = Field(default_factory=WatchVolumeSafety)

    model_config = {"use_enum_values": True}
