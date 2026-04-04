"""Cycle Receipt model — append-only audit for runner cycles.

Phase 6A+6B-2 of CR-048.  Records each multi-symbol runner cycle:
  - Universe size, strategies evaluated, signal candidates, skips
  - Full entry-level detail in JSON
  - dry_run flag
  - skip_reason_code for whole-cycle skips (market_closed, safe_mode, drift)
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import String, Integer, Float, DateTime, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CycleReceiptRecord(Base):
    """Append-only cycle receipt — records each runner evaluation cycle."""

    __tablename__ = "cycle_receipts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))

    cycle_id: Mapped[str] = mapped_column(String(60), index=True)

    # Summary
    universe_size: Mapped[int] = mapped_column(Integer, default=0)
    strategies_evaluated: Mapped[int] = mapped_column(Integer, default=0)
    signal_candidates: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True)

    # Detail (JSON array of entry records)
    entries_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # System state at cycle time
    safe_mode_active: Mapped[bool] = mapped_column(Boolean, default=False)
    drift_active: Mapped[bool] = mapped_column(Boolean, default=False)

    # Whole-cycle skip reason (none = ran normally)
    skip_reason_code: Mapped[str] = mapped_column(String(40), default="none")

    # Guard state snapshot at cycle time (JSON)
    guard_snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps (timezone-aware for asyncpg compatibility)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
