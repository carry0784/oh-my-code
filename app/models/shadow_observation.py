"""RI-2A-2a: Shadow Observation Log — append-only observation record.

This table is NOT a business decision source.
business_impact = false.

DML contract:
  INSERT: allowed (record_shadow_observation only)
  SELECT: allowed (read-only queries)
  UPDATE: PROHIBITED (permanent)
  DELETE: PROHIBITED (retention purge deferred to RI-2A-2b)

FK: ZERO (independent of all existing tables)
UNIQUE: ZERO (append-only, duplicates allowed, dedup at query time)
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, String, Text, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ShadowObservationLog(Base):
    """Shadow observation record. Append-only. Not a business decision source."""

    __tablename__ = "shadow_observation_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ── 관찰 대상 ──
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(16), nullable=False)
    asset_sector: Mapped[str] = mapped_column(String(32), nullable=False)

    # ── Shadow 결과 ──
    shadow_verdict: Mapped[str] = mapped_column(String(32), nullable=False)
    shadow_screening_passed: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )
    shadow_qualification_passed: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    # ── 비교 결과 ──
    comparison_verdict: Mapped[str] = mapped_column(String(32), nullable=False)
    existing_screening_passed: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )
    existing_qualification_passed: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    # ── Reason-level ──
    reason_comparison_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ── Read-through metadata ──
    readthrough_failure_code: Mapped[str | None] = mapped_column(
        String(48),
        nullable=True,
    )
    existing_screening_result_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    existing_qualification_result_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    # ── 재현성 ──
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

    # ── 시각 ──
    shadow_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # ── RI-2A-2b: Retention support ──
    # Soft-delete marker for retention policy. Default False.
    # Purge execution is NOT implemented (RI-2A-2b planner only).
    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    __table_args__ = (
        Index("ix_shadow_obs_symbol", "symbol"),
        Index("ix_shadow_obs_created_at", "created_at"),
        Index("ix_shadow_obs_verdict", "comparison_verdict", "created_at"),
    )
