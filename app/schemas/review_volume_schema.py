"""
K-Dexter REVIEW Volume Schema (Typed)

Read-only observation card for REVIEW action class volume and distribution.
Provides operator with factual count/ratio/distribution data only.

Design rules:
  - No prediction, recommendation, or auto-judgment
  - No action verbs, no execution triggers, no write paths
  - Count/ratio/window definitions must be explicit
  - Overcrowding signal is descriptive, not prescriptive
  - Safety labels are structurally fixed (always True)

Data source:
  CleanupSimulationReport.candidates where action_class == REVIEW
"""
from __future__ import annotations

from pydantic import BaseModel, Field


# -- Nested models --------------------------------------------------------- #

class TierDistribution(BaseModel):
    """REVIEW candidate count per tier."""
    agent: int = 0
    execution: int = 0
    submit: int = 0


class ReasonDistribution(BaseModel):
    """REVIEW candidate count per reason code."""
    stale_agent: int = 0
    stale_execution: int = 0
    stale_submit: int = 0
    orphan_exec_parent: int = 0
    orphan_submit_parent: int = 0
    stale_and_orphan: int = 0


class BandDistribution(BaseModel):
    """REVIEW candidate count per stale band (early/review/prolonged)."""
    early: int = 0
    review: int = 0
    prolonged: int = 0


class DensitySignal(BaseModel):
    """
    Descriptive density/overcrowding signal for operator awareness.

    NOT prescriptive. Describes observable patterns only.
    """
    is_concentrated: bool = False       # >66% in single tier
    dominant_tier: str = ""             # tier with most REVIEW candidates
    dominant_ratio: float = 0.0         # ratio of dominant tier
    has_prolonged: bool = False         # any candidate in prolonged band
    prolonged_count: int = 0            # count of prolonged candidates
    description: str = ""               # human-readable summary


class ReviewVolumeSafety(BaseModel):
    """Structurally fixed safety labels. All ALWAYS True."""
    read_only: bool = Field(default=True, description="ALWAYS True.")
    simulation_only: bool = Field(default=True, description="ALWAYS True.")
    no_action_executed: bool = Field(default=True, description="ALWAYS True.")
    no_prediction: bool = Field(default=True, description="ALWAYS True. No forecasting.")


# -- Main schema ----------------------------------------------------------- #

class ReviewVolumeSchema(BaseModel):
    """
    REVIEW volume observation card.

    Factual summary of REVIEW-class cleanup candidates.
    Read-only, no prediction, no recommendation.

    Relationship:
      CleanupSimulationReport → ReviewVolumeSchema (observation)
      ObservationSummarySchema (Layer 4) contains candidate totals
      This card drills down into the REVIEW subset specifically
    """
    review_total: int = 0
    candidate_total: int = 0                # total across all action classes
    review_ratio: float = 0.0               # review_total / candidate_total (0 if no candidates)
    by_tier: TierDistribution = Field(default_factory=TierDistribution)
    by_reason: ReasonDistribution = Field(default_factory=ReasonDistribution)
    by_band: BandDistribution = Field(default_factory=BandDistribution)
    density: DensitySignal = Field(default_factory=DensitySignal)
    safety: ReviewVolumeSafety = Field(default_factory=ReviewVolumeSafety)

    model_config = {"use_enum_values": True}
