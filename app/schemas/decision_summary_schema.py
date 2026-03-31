"""
K-Dexter Decision Summary Schema (Typed)

Replaces the untyped dict version of decision_summary in the Board response.
Provides compile-time field guarantees, enum-constrained values, and a
structurally fixed safety sub-model.

Design rules:
  - Posture and RiskLevel are enums — no free-form strings
  - DecisionSafety is a nested model with structurally fixed values
  - action_allowed is ALWAYS False — enforced at schema default level
  - Source/derived relationship:
      decision_summary (this schema) = SOURCE
      decision_card = DERIVED UI view (from decision_card_schema.py)
  - No action verbs, no execution triggers, no write paths
"""
from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


# -- Enums ----------------------------------------------------------------- #

class PostureEnum(str, Enum):
    """Recommended operator posture levels."""
    MONITOR = "MONITOR"
    REVIEW = "REVIEW"
    MANUAL_CHECK = "MANUAL_CHECK"
    URGENT_REVIEW = "URGENT_REVIEW"


class RiskLevelEnum(str, Enum):
    """Risk classification levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class PressureEnum(str, Enum):
    """Cleanup pressure levels (from observation summary)."""
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# -- Safety sub-model ------------------------------------------------------ #

class DecisionSafety(BaseModel):
    """
    Structurally fixed safety labels.

    action_allowed is ALWAYS False. This is not a computed value —
    it is a constitutional constraint. NEVER set to True.
    """
    action_allowed: bool = Field(default=False, description="ALWAYS False. Constitutional constraint.")
    suggestion_only: bool = Field(default=True, description="ALWAYS True. This is guidance, not instruction.")
    read_only: bool = Field(default=True, description="ALWAYS True. No mutations performed.")


# -- Main schema ----------------------------------------------------------- #

class DecisionSummarySchema(BaseModel):
    """
    Typed operator decision summary.

    Source of truth for decision data. DecisionCard is derived from this.
    Read-only, suggestion-only. NEVER executes any action.

    Relationship:
      DecisionSummarySchema (source) → DecisionCard (derived UI view)
    """
    recommended_posture: PostureEnum = PostureEnum.MONITOR
    risk_level: RiskLevelEnum = RiskLevelEnum.LOW
    reason_chain: list[str] = Field(default_factory=list)
    decision_explanation: str = ""
    candidate_total: int = 0
    orphan_total: int = 0
    stale_total: int = 0
    cleanup_pressure: PressureEnum = PressureEnum.LOW
    safety: DecisionSafety = Field(default_factory=DecisionSafety)

    model_config = {"use_enum_values": True}
