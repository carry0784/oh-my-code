"""Market State Observation Receipt — F5c append-only DB persistence.

Persisted form of MarketStateObservationReceipt (F5b schema) for later
consumption by F7 decision-engine validator. Append-only DML contract:
INSERT only; no UPDATE/DELETE.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MarketStateObservationReceiptRecord(Base):
    """Append-only DB record for Market State API observation receipts (F5c).

    Companion to `app/schemas/market_observation_receipt_schema.py`
    (F5b log schema). F5c persists each emitted receipt to DB so that
    a future F7 decision-engine validator can query admissibility.

    Append-only contract: INSERT only. No UPDATE/DELETE.
    """

    __tablename__ = "market_observation_receipts"

    # Identity
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    receipt_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    # Endpoint identity
    endpoint: Mapped[str] = mapped_column(String(16), nullable=False)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)

    # Timestamps
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    audit_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Status fields (mirror F5b schema Literal vocabulary; stored as plain str)
    source_status: Mapped[str] = mapped_column(String(24), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(24), nullable=False)
    freshness_status: Mapped[str] = mapped_column(String(16), nullable=False)
    error_type: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Decision gate input (consumed by future F7 validator)
    response_shape_version: Mapped[str] = mapped_column(String(8), nullable=False, default="v1")
    admissible_for_decision: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Audit / rollback
    rollback_note: Mapped[str] = mapped_column(String(512), nullable=False)
    evidence_bundle_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_market_obs_endpoint", "endpoint"),
        Index("ix_market_obs_symbol", "symbol"),
        Index("ix_market_obs_audit_created_at", "audit_created_at"),
        Index(
            "ix_market_obs_admissible_at",
            "admissible_for_decision",
            "audit_created_at",
        ),
    )
