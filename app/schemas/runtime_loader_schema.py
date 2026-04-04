"""Pydantic schemas for Phase 5A: Runtime Loader + Strategy Router + Feature Cache."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


# ── Load Decision Receipt ──────────────────────────────────────────────


class LoadDecisionReceiptRead(BaseModel):
    id: str
    strategy_id: str
    symbol_id: str
    timeframe: str
    decision: str
    primary_reason: str | None = None
    failed_checks: str | None = None
    status_snapshot: str | None = None
    strategy_fingerprint: str | None = None
    fp_fingerprint: str | None = None
    decided_at: datetime

    model_config = {"from_attributes": True}


# ── Routing Result ─────────────────────────────────────────────────────


class RoutingCheckRead(BaseModel):
    check_name: str
    passed: bool
    detail: str | None = None


class RoutingResultRead(BaseModel):
    strategy_id: str
    symbol: str
    timeframe: str
    routable: bool
    checks: list[RoutingCheckRead] = []
    failed_checks: list[str] = []


# ── Feature Cache Stats ───────────────────────────────────────────────


class FeatureCacheStatsRead(BaseModel):
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    invalidations: int = 0
    current_size: int = 0
    hit_rate: float = 0.0
