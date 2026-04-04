"""Pydantic schemas for Asset Registry (Phase 2, CR-048)."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field

from app.models.asset import (
    AssetSector,
    AssetTheme,
    SymbolStatus,
)
from app.models.strategy_registry import AssetClass
from app.models.qualification import QualificationStatus


# ── Symbol Schemas ───────────────────────────────────────────────────


class SymbolCreate(BaseModel):
    symbol: str = Field(..., max_length=40)
    name: str = Field(..., max_length=200)
    asset_class: AssetClass
    sector: AssetSector
    theme: AssetTheme = AssetTheme.NONE
    exchanges: list[str]
    market_cap_usd: float | None = None
    avg_daily_volume: float | None = None
    status: SymbolStatus = SymbolStatus.WATCH
    status_reason_code: str | None = None
    exclusion_reason: str | None = None
    screening_score: float = 0.0
    regime_allow: list[str] | None = None
    paper_allowed: bool = False
    live_allowed: bool = False
    broker_policy: str | None = None


class SymbolRead(BaseModel):
    id: str
    symbol: str
    name: str
    asset_class: AssetClass
    sector: AssetSector
    theme: AssetTheme
    exchanges: list[str]
    market_cap_usd: float | None
    avg_daily_volume: float | None
    status: SymbolStatus
    status_reason_code: str | None
    exclusion_reason: str | None
    screening_score: float
    qualification_status: str
    promotion_eligibility_status: str
    paper_evaluation_status: str
    paper_pass_at: datetime | None = None
    regime_allow: list[str] | None
    candidate_expire_at: datetime | None
    paper_allowed: bool
    live_allowed: bool
    manual_override: bool
    override_by: str | None
    override_reason: str | None
    override_at: datetime | None
    broker_policy: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SymbolUpdate(BaseModel):
    name: str | None = None
    sector: AssetSector | None = None
    theme: AssetTheme | None = None
    exchanges: list[str] | None = None
    market_cap_usd: float | None = None
    avg_daily_volume: float | None = None
    status: SymbolStatus | None = None
    status_reason_code: str | None = None
    exclusion_reason: str | None = None
    screening_score: float | None = None
    regime_allow: list[str] | None = None
    paper_allowed: bool | None = None
    live_allowed: bool | None = None
    manual_override: bool | None = None
    broker_policy: str | None = None


# ── ScreeningResult Schemas ──────────────────────────────────────────


class ScreeningResultRead(BaseModel):
    id: str
    symbol_id: str
    symbol: str
    stage1_exclusion: bool
    stage2_liquidity: bool
    stage3_technical: bool
    stage4_fundamental: bool
    stage5_backtest: bool
    all_passed: bool
    score: float
    stage_reason_code: str | None
    detail: str | None
    resulting_status: SymbolStatus
    screened_at: datetime

    model_config = {"from_attributes": True}


# ── QualificationResult Schemas ──────────────────────────────────────


class QualificationResultRead(BaseModel):
    id: str
    strategy_id: str
    symbol: str
    timeframe: str
    dataset_fingerprint: str | None
    bars_evaluated: int
    date_range_start: datetime | None
    date_range_end: datetime | None
    check_data_compat: bool
    check_warmup: bool
    check_leakage: bool
    check_data_quality: bool
    check_min_bars: bool
    check_performance: bool
    check_cost_sanity: bool
    all_passed: bool
    qualification_status: QualificationStatus
    disqualify_reason: str | None
    failed_checks: str | None
    metrics_snapshot: str | None
    detail: str | None
    evaluated_at: datetime

    model_config = {"from_attributes": True}


# ── Stage 2A: Validation Response Schemas ───────────────────────────


class BrokerPolicyValidationResponse(BaseModel):
    """Response for broker-policy validation (pure, no DB)."""

    exchanges: list[str]
    asset_class: str
    violations: list[str] = Field(default_factory=list)
    valid: bool = True


class StatusTransitionValidationResponse(BaseModel):
    """Response for status-transition validation (pure, no DB)."""

    current_status: str
    target_status: str
    manual_override: bool = False
    sector: str | None = None
    allowed: bool
    reason: str


class CandidateTTLResponse(BaseModel):
    """Response for candidate TTL computation (pure, no DB)."""

    score: float
    asset_class: str
    ttl_hours: float
    ttl_min_hours: int
    ttl_max_hours: int


class SymbolDataValidationResponse(BaseModel):
    """Response for symbol data pre-validation (pure, no DB)."""

    errors: list[str] = Field(default_factory=list)
    valid: bool = True


class SymbolStatusAuditRead(BaseModel):
    """Read schema for symbol status audit trail (append-only)."""

    id: str
    symbol_id: str
    symbol: str
    from_status: str
    to_status: str
    reason_code: str | None
    reason_detail: str | None
    triggered_by: str
    approval_level: str | None
    context: str | None
    transitioned_at: datetime

    model_config = {"from_attributes": True}
