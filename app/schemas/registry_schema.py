"""Pydantic schemas for Control Plane registry endpoints."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


# ── Indicator ─────────────────────────────────────────────────────────


class IndicatorCreate(BaseModel):
    name: str
    version: str
    description: str | None = None
    input_params: str | None = None  # JSON string
    output_fields: str | None = None  # JSON string
    warmup_bars: int = 0
    compute_module: str
    checksum: str | None = None


class IndicatorResponse(BaseModel):
    id: str
    name: str
    version: str
    description: str | None
    warmup_bars: int
    compute_module: str
    checksum: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Feature Pack ──────────────────────────────────────────────────────


class FeaturePackCreate(BaseModel):
    name: str
    version: str
    indicator_ids: str  # JSON list
    weights: str | None = None  # JSON dict
    checksum: str | None = None


class FeaturePackResponse(BaseModel):
    id: str
    name: str
    version: str
    indicator_ids: str
    checksum: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Strategy ──────────────────────────────────────────────────────────


class StrategyCreate(BaseModel):
    name: str
    version: str
    description: str | None = None
    feature_pack_id: str
    compute_module: str
    checksum: str | None = None
    asset_classes: str  # JSON list
    exchanges: str  # JSON list
    sectors: str | None = None  # JSON list
    timeframes: str  # JSON list
    regimes: str | None = None  # JSON list
    max_symbols: int = 20


class StrategyResponse(BaseModel):
    id: str
    name: str
    version: str
    description: str | None
    feature_pack_id: str
    compute_module: str
    checksum: str | None
    asset_classes: str
    exchanges: str
    sectors: str | None
    timeframes: str
    regimes: str | None
    max_symbols: int
    status: str
    is_champion: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Gateway ───────────────────────────────────────────────────────────

# ── Promotion Event ──────────────────────────────────────────────────


class PromotionEventResponse(BaseModel):
    id: str
    strategy_id: str
    from_status: str
    to_status: str
    reason: str | None
    triggered_by: str
    approval_level: str | None
    evidence: str | None
    approved_by: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Retire Request ───────────────────────────────────────────────────


class RetireRequest(BaseModel):
    reason: str = ""
    retired_by: str = "operator"


# ── Registry Stats ───────────────────────────────────────────────────


class RegistryStatsResponse(BaseModel):
    indicators: int = 0
    feature_packs: int = 0
    strategies: int = 0
    promotion_events: int = 0


# ── Gateway ──────────────────────────────────────────────────────────


class GatewayResultResponse(BaseModel):
    verdict: str
    violations: list[str] = Field(default_factory=list)
    blocked_code: str | None = None
