"""
K-Dexter Pipeline Blockage Summary Schema (Typed)

Read-only observation card for pipeline blockage distribution across tiers.
Provides operator with factual blockage rate/reason/distribution data only.

Design rules:
  - No prediction, recommendation, or auto-judgment
  - No action verbs, no execution triggers, no write paths
  - Blockage rate is a factual ratio, not a risk score
  - Description templates are pattern-based, not free-form
  - Safety labels are structurally fixed (always True)

Data source:
  TierSummary.blocked_count / TierSummary.total per tier
  TierSummary.guard_reason_top per tier
"""
from __future__ import annotations

from pydantic import BaseModel, Field


# -- Nested models --------------------------------------------------------- #

class TierBlockage(BaseModel):
    """Blockage counts and rate for a single tier."""
    tier_name: str = ""
    blocked_count: int = 0
    total_count: int = 0
    blockage_rate: float = 0.0      # blocked / total (0 if no proposals)


class ReasonAggregation(BaseModel):
    """Top blocking reasons aggregated across all tiers."""
    reason: str = ""
    count: int = 0


class BlockageDensitySignal(BaseModel):
    """
    Descriptive blockage concentration signal for operator awareness.

    NOT prescriptive. Describes observable patterns only.
    """
    is_concentrated: bool = False       # >66% of blocks in single tier
    dominant_tier: str = ""             # tier with most blocks
    dominant_ratio: float = 0.0         # ratio of dominant tier blocks
    has_high_blockage: bool = False     # any tier with blockage_rate > 50%
    high_blockage_tier: str = ""        # tier with highest blockage rate
    description: str = ""               # human-readable summary


class BlockageSafety(BaseModel):
    """Structurally fixed safety labels. All ALWAYS True."""
    read_only: bool = Field(default=True, description="ALWAYS True.")
    simulation_only: bool = Field(default=True, description="ALWAYS True.")
    no_action_executed: bool = Field(default=True, description="ALWAYS True.")
    no_prediction: bool = Field(default=True, description="ALWAYS True. No forecasting.")


# -- Main schema ----------------------------------------------------------- #

class BlockageSummarySchema(BaseModel):
    """
    Pipeline Blockage Summary observation card.

    Factual summary of blocked proposals across all tiers.
    Read-only, no prediction, no recommendation.

    Relationship:
      TierSummary (per-tier counts) -> BlockageSummarySchema (cross-tier aggregation)
      This card aggregates blockage from Agent, Execution, and Submit tiers.
    """
    total_blocked: int = 0
    total_proposals: int = 0
    overall_blockage_rate: float = 0.0      # total_blocked / total_proposals
    by_tier: list[TierBlockage] = Field(default_factory=list)
    top_reasons: list[ReasonAggregation] = Field(default_factory=list, max_length=10)
    density: BlockageDensitySignal = Field(default_factory=BlockageDensitySignal)
    safety: BlockageSafety = Field(default_factory=BlockageSafety)

    model_config = {"use_enum_values": True}
