"""Pydantic schemas for Phase 6A: Universe Manager + Multi-Symbol Runner."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class SymbolSelectionResultRead(BaseModel):
    symbol_id: str
    symbol: str
    outcome: str
    reason_snapshot: dict = {}


class UniverseSnapshotRead(BaseModel):
    selected: list[SymbolSelectionResultRead] = []
    excluded: list[SymbolSelectionResultRead] = []
    total_evaluated: int = 0
    safe_mode_active: bool = False
    drift_active: bool = False
    computed_at: datetime


class CycleReceiptRead(BaseModel):
    id: str
    cycle_id: str
    universe_size: int
    strategies_evaluated: int
    signal_candidates: int
    skipped: int
    dry_run: bool
    safe_mode_active: bool
    drift_active: bool
    skip_reason_code: str = "none"
    started_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}
