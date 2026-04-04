"""Pydantic schemas for Paper Shadow + Promotion Gate + Evaluation (Phase 4B+4C, CR-048)."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel

from app.models.paper_shadow import (
    ObservationStatus,
    PromotionEligibility,
    EligibilityBlockReason,
)
from app.services.paper_evaluation import PaperEvalDecision


# ── PaperObservation Schemas ────────────────────────────────────────


class PaperObservationRead(BaseModel):
    id: str
    strategy_id: str
    symbol: str
    timeframe: str
    metrics_snapshot: str | None
    observation_status: ObservationStatus
    source_qualification_result_id: str | None
    observation_window_fingerprint: str | None
    detail: str | None
    observed_at: datetime

    model_config = {"from_attributes": True}


# ── PromotionDecision Schemas ───────────────────────────────────────


class PromotionDecisionRead(BaseModel):
    id: str
    strategy_id: str
    symbol: str
    timeframe: str
    decision: PromotionEligibility
    previous_decision: str | None
    reason: str | None
    eligibility_checks: str | None
    blocked_checks: str | None
    source_observation_id: str | None
    suppressed: bool
    decided_by: str
    decided_at: datetime

    model_config = {"from_attributes": True}


# ── EligibilityCheck Schemas ────────────────────────────────────────


class EligibilityCheckRead(BaseModel):
    check_name: str
    passed: bool
    reason: str | None = None


class EligibilityResultRead(BaseModel):
    strategy_id: str
    symbol: str
    timeframe: str
    checks: list[EligibilityCheckRead]
    all_passed: bool
    decision: PromotionEligibility
    block_reason: str | None = None


# ── PaperEvaluationRecord Schemas ───────────────────────────────────


class PaperEvaluationRecordRead(BaseModel):
    id: str
    strategy_id: str
    symbol: str
    timeframe: str
    observation_count: int
    valid_observation_count: int
    expected_observation_count: int
    observation_window_fingerprint: str | None
    cumulative_return_pct: float | None
    max_drawdown_pct: float | None
    avg_turnover_annual: float | None
    avg_slippage_pct: float | None
    rule_min_observations: bool
    rule_cumulative_performance: bool
    rule_max_drawdown: bool
    rule_turnover: bool
    rule_slippage: bool
    rule_completeness: bool
    all_passed: bool
    decision: str
    primary_reason: str | None
    failed_rules: str | None
    metrics_summary: str | None
    source_qualification_result_id: str | None
    evaluated_at: datetime

    model_config = {"from_attributes": True}
