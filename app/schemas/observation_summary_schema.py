"""
K-Dexter Observation Summary Schema (Typed)

Replaces the untyped dict version of observation_summary in the Board response.
Provides compile-time field guarantees, enum-constrained pressure values, and
structurally fixed safety labels.

Design rules:
  - PressureEnum constrains cleanup_pressure to LOW/MODERATE/HIGH/CRITICAL
  - ObservationSafety is a nested model with structurally fixed values
  - read_only, simulation_only, no_action_executed are ALWAYS True
  - ReasonActionEntry is a typed cross-table row (reason × action × count)
  - No action verbs, no execution triggers, no write paths

Source/Derived relationship:
  observation_summary (this schema) = SOURCE (Layer 4)
  decision_summary = DERIVED from observation (Layer 5)
  decision_card = DERIVED UI view from decision (Layer 6)
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.decision_summary_schema import PressureEnum


# -- Safety sub-model ------------------------------------------------------ #


class ObservationSafety(BaseModel):
    """
    Structurally fixed safety labels for observation layer.

    All four fields are ALWAYS True. These are constitutional constraints,
    not computed values. NEVER set to False.
    """

    read_only: bool = Field(default=True, description="ALWAYS True. No mutations performed.")
    simulation_only: bool = Field(default=True, description="ALWAYS True. No cleanup executed.")
    no_action_executed: bool = Field(
        default=True, description="ALWAYS True. No state transitions triggered."
    )
    no_prediction: bool = Field(default=True, description="ALWAYS True. No forecasting.")


# -- Nested models --------------------------------------------------------- #


class ReasonActionEntry(BaseModel):
    """Single row of reason × action cross table."""

    reason: str = ""
    action: str = ""
    count: int = 0


class TopPriorityCandidate(BaseModel):
    """Top priority cleanup candidate for operator attention."""

    proposal_id: str = ""
    tier: str = ""
    action_class: str = ""
    reason_code: str = ""
    is_stale: bool = False
    is_orphan: bool = False
    stale_age_seconds: float = 0.0
    current_status: str = ""
    explanation: str = ""


# -- Main schema ----------------------------------------------------------- #


class ObservationSummarySchema(BaseModel):
    """
    Typed observation summary for operator dashboard.

    Source of truth for Layer 4 observation data.
    Read-only, simulation-only. NEVER executes any action.

    Relationship:
      ObservationSummarySchema (source, Layer 4)
        → DecisionSummarySchema (derived, Layer 5)
        → DecisionCard (derived UI view, Layer 6)
    """

    cleanup_pressure: PressureEnum = PressureEnum.LOW
    stale_total: int = 0
    orphan_total: int = 0
    candidate_total: int = 0
    stale_by_tier: dict[str, int] = Field(default_factory=dict)
    reason_action_matrix: list[ReasonActionEntry] = Field(default_factory=list)
    top_priority_candidates: list[TopPriorityCandidate] = Field(default_factory=list)
    safety: ObservationSafety = Field(default_factory=ObservationSafety)

    model_config = {"use_enum_values": True}
