"""PPF Novelty Event Log — append-only record for FP accumulation.

Tracks each PPF novelty brake activation (O9=True) with observation window
metadata for post-hoc TP/FP/UNRESOLVED judgment.

DML contract:
  INSERT: allowed (ppf_shadow_tasks only)
  SELECT: allowed (read-only queries)
  UPDATE: allowed (judgment fields only, after observation window closes)
  DELETE: PROHIBITED

FK: ZERO (independent of all existing tables)
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PPFNoveltyEvent(Base):
    """PPF novelty brake event record for FP accumulation tracking."""

    __tablename__ = "ppf_novelty_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # -- Event identification --
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    event_ts: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # -- Gate evaluation snapshot --
    deny_reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_gate_decision: Mapped[bool] = mapped_column(Boolean, nullable=False)
    gate_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    manifest_name: Mapped[str] = mapped_column(String(32), nullable=False)

    # -- Observation window tracking --
    observation_window_bars: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    observation_window_closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    bars_elapsed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # -- Post-hoc judgment (filled after observation window) --
    judgment: Mapped[str | None] = mapped_column(String(16), nullable=True)  # TP / FP / UNRESOLVED
    judgment_ts: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    judgment_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # -- Market context at event time --
    close_price_at_event: Mapped[float | None] = mapped_column(Float, nullable=True)
    close_price_at_window_end: Mapped[float | None] = mapped_column(Float, nullable=True)

    # -- Metadata --
    task_result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_ppf_novelty_symbol_ts", "symbol", "event_ts"),
        Index("ix_ppf_novelty_judgment", "judgment"),
        Index("ix_ppf_novelty_window_closed", "observation_window_closed"),
    )
