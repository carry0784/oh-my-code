"""RI-2B-1: Shadow Write Receipt — append-only dry-run evidence.

Records write INTENT only. No business table state change.
dry_run=True, executed=False, business_write_count=0 — always.

This table is NOT a business decision source.
DML contract: INSERT only (UPDATE/DELETE prohibited).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ShadowWriteReceipt(Base):
    __tablename__ = "shadow_write_receipt"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Identity
    receipt_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    dedupe_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)

    # Target
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    target_table: Mapped[str] = mapped_column(String(48), nullable=False)
    target_field: Mapped[str] = mapped_column(String(48), nullable=False)
    current_value: Mapped[str | None] = mapped_column(String(128), nullable=True)
    intended_value: Mapped[str] = mapped_column(String(128), nullable=False)
    would_change_summary: Mapped[str] = mapped_column(String(256), nullable=False)

    # Reason
    transition_reason: Mapped[str] = mapped_column(String(128), nullable=False)
    block_reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Linkage (reference only, no FK)
    shadow_observation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

    # Proof fields (RI-2B-1: always fixed)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    executed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    business_write_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Verdict
    verdict: Mapped[str] = mapped_column(String(32), nullable=False)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_swr_symbol", "symbol"),
        Index("ix_swr_created_at", "created_at"),
    )
