"""
K-Dexter Retry Pressure Schema (Typed)

Read-only observation card for retry queue pressure and distribution.
Provides operator with factual retry backlog/status/channel data only.

Design rules:
  - No prediction, recommendation, or auto-judgment
  - No action verbs, no execution triggers, no write paths
  - Backlog count is a factual total, not a risk score
  - Description templates are pattern-based, not free-form
  - Safety labels are structurally fixed (always True)

Data source:
  RetryPlanStore plan list (pending/cancelled/executed/expired counts)
"""
from __future__ import annotations

from pydantic import BaseModel, Field


# -- Nested models --------------------------------------------------------- #

class RetryStatusDistribution(BaseModel):
    """Retry plan count per status."""
    pending: int = 0
    cancelled: int = 0
    executed: int = 0
    expired: int = 0


class RetryChannelDistribution(BaseModel):
    """Retry plan count per notification channel."""
    channel: str = ""
    count: int = 0


class RetrySeverityDistribution(BaseModel):
    """Retry plan count per severity tier."""
    severity: str = ""
    count: int = 0


class RetryDensitySignal(BaseModel):
    """
    Descriptive retry backlog signal for operator awareness.

    NOT prescriptive. Describes observable patterns only.
    """
    has_pending: bool = False           # any pending plans exist
    pending_ratio: float = 0.0          # pending / total (0 if no plans)
    is_channel_concentrated: bool = False  # >66% in single channel
    dominant_channel: str = ""          # channel with most pending plans
    dominant_channel_ratio: float = 0.0 # ratio of dominant channel
    description: str = ""               # human-readable summary


class RetryPressureSafety(BaseModel):
    """Structurally fixed safety labels. All ALWAYS True."""
    read_only: bool = Field(default=True, description="ALWAYS True.")
    simulation_only: bool = Field(default=True, description="ALWAYS True.")
    no_action_executed: bool = Field(default=True, description="ALWAYS True.")
    no_prediction: bool = Field(default=True, description="ALWAYS True. No forecasting.")


# -- Main schema ----------------------------------------------------------- #

class RetryPressureSchema(BaseModel):
    """
    Retry Pressure observation card.

    Factual summary of retry queue backlog and distribution.
    Read-only, no prediction, no recommendation.

    Relationship:
      RetryPlanStore -> RetryPressureSchema (observation)
      Notification flow produces retry plans; this card observes them.
    """
    total_plans: int = 0
    pending_count: int = 0
    backlog_ratio: float = 0.0          # pending / total (0 if no plans)
    by_status: RetryStatusDistribution = Field(default_factory=RetryStatusDistribution)
    by_channel: list[RetryChannelDistribution] = Field(default_factory=list, max_length=10)
    by_severity: list[RetrySeverityDistribution] = Field(default_factory=list, max_length=10)
    density: RetryDensitySignal = Field(default_factory=RetryDensitySignal)
    safety: RetryPressureSafety = Field(default_factory=RetryPressureSafety)

    model_config = {"use_enum_values": True}
