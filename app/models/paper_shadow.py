"""Paper Shadow + Promotion Gate models — Phase 4B of CR-048.

Provides:
  - ObservationStatus: status of a paper observation record
  - PromotionEligibility: promotion eligibility lifecycle states
  - PaperObservation: append-only observation record
  - PromotionDecision: append-only promotion decision record

The paper shadow layer sits between qualification (Phase 4A) and
live execution.  It records simulated observations without any
broker or order execution.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import String, Float, Integer, DateTime, Text, Boolean, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# ── Enums ────────────────────────────────────────────────────────────


class ObservationStatus(str, Enum):
    """Status of a paper shadow observation record."""

    RECORDED = "recorded"
    SKIPPED_SAFE_MODE = "skipped_safe_mode"
    SKIPPED_DRIFT = "skipped_drift"


class PromotionEligibility(str, Enum):
    """Promotion eligibility lifecycle — independent of screening + qualification.

    Deliberately separate from QualificationStatus to keep
    qualification (backtest fitness) and promotion (operational readiness)
    concerns distinct.
    """

    UNCHECKED = "unchecked"
    ELIGIBLE_FOR_PAPER = "eligible_for_paper"
    PAPER_HOLD = "paper_hold"
    PAPER_PASS = "paper_pass"
    PAPER_FAIL = "paper_fail"
    QUARANTINE_CANDIDATE = "quarantine_candidate"


class EligibilityBlockReason(str, Enum):
    """Reason codes for promotion eligibility failure."""

    SCREENING_NOT_CORE = "screening_not_core"
    QUALIFICATION_NOT_PASS = "qualification_not_pass"
    SYMBOL_EXCLUDED = "symbol_excluded"
    SAFE_MODE_ACTIVE = "safe_mode_active"
    RUNTIME_DRIFT_ACTIVE = "runtime_drift_active"


# ── PaperObservation Model ──────────────────────────────────────────


class PaperObservation(Base):
    """Append-only paper shadow observation record.

    One record per observation event for a (strategy, symbol, timeframe).
    No actual broker/order execution — metrics are supplied or simulated.
    """

    __tablename__ = "paper_observations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # What was observed
    strategy_id: Mapped[str] = mapped_column(String(36), index=True)
    symbol: Mapped[str] = mapped_column(String(40), index=True)
    timeframe: Mapped[str] = mapped_column(String(10))

    # Observation data
    metrics_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    observation_status: Mapped[ObservationStatus] = mapped_column(
        SQLEnum(ObservationStatus, values_callable=lambda e: [x.value for x in e]),
        default=ObservationStatus.RECORDED,
    )

    # Linkage to qualification
    source_qualification_result_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Evaluation window identity
    observation_window_fingerprint: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # SHA-256 of eval window (threshold set + period + qualification result)

    # Detail (JSON)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps — append-only, no updated_at
    observed_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


# ── PromotionDecision Model ─────────────────────────────────────────


class PromotionDecision(Base):
    """Append-only promotion decision audit record.

    Records every eligibility evaluation result, including
    suppressed duplicates (for audit completeness).
    """

    __tablename__ = "promotion_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # What was evaluated
    strategy_id: Mapped[str] = mapped_column(String(36), index=True)
    symbol: Mapped[str] = mapped_column(String(40), index=True)
    timeframe: Mapped[str] = mapped_column(String(10))

    # Decision
    decision: Mapped[PromotionEligibility] = mapped_column(
        SQLEnum(PromotionEligibility, values_callable=lambda e: [x.value for x in e]),
        default=PromotionEligibility.UNCHECKED,
    )
    previous_decision: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Eligibility check detail (JSON — each of the 5 checks pass/fail)
    eligibility_checks: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Linkage
    source_observation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Blocked checks detail (JSON array of all failed check names)
    blocked_checks: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Duplicate suppression
    suppressed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Audit
    decided_by: Mapped[str] = mapped_column(String(100), default="system")

    # Timestamps — append-only, no updated_at
    decided_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


# ── PaperEvaluationRecord Model ────────────────────────────────────


class PaperEvaluationRecord(Base):
    """Append-only paper evaluation result.

    Records the result of evaluating a window of paper observations
    against the paper pass criteria.  Separate from PromotionDecision
    to keep eligibility (gate) and evaluation (observation quality) distinct.
    """

    __tablename__ = "paper_evaluation_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # What was evaluated
    strategy_id: Mapped[str] = mapped_column(String(36), index=True)
    symbol: Mapped[str] = mapped_column(String(40), index=True)
    timeframe: Mapped[str] = mapped_column(String(10))

    # Observation window
    observation_count: Mapped[int] = mapped_column(Integer, default=0)
    valid_observation_count: Mapped[int] = mapped_column(Integer, default=0)
    expected_observation_count: Mapped[int] = mapped_column(Integer, default=0)
    observation_window_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Aggregated metrics
    cumulative_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_turnover_annual: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_slippage_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    # 6-rule results
    rule_min_observations: Mapped[bool] = mapped_column(Boolean, default=False)
    rule_cumulative_performance: Mapped[bool] = mapped_column(Boolean, default=False)
    rule_max_drawdown: Mapped[bool] = mapped_column(Boolean, default=False)
    rule_turnover: Mapped[bool] = mapped_column(Boolean, default=False)
    rule_slippage: Mapped[bool] = mapped_column(Boolean, default=False)
    rule_completeness: Mapped[bool] = mapped_column(Boolean, default=False)

    # Aggregate
    all_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    decision: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending / hold / pass / fail / quarantine
    primary_reason: Mapped[str | None] = mapped_column(String(60), nullable=True)
    failed_rules: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON array of failed rule names

    # Metrics summary (JSON)
    metrics_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Linkage
    source_qualification_result_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Timestamps — append-only
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
