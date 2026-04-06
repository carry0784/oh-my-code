"""
CR-046 Paper Trading DB Models

Tables:
  - paper_trading_sessions: Session state persistence (optimistic lock)
  - paper_trading_receipts: Append-only bar receipts
  - promotion_receipts: Append-only promotion audit trail

All tables are append-only or version-locked. No casual UPDATE/DELETE.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Float,
    Integer,
    Boolean,
    Text,
    BigInteger,
    DateTime,
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PaperTradingSessionModel(Base):
    __tablename__ = "paper_trading_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    daily_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    weekly_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consecutive_losing_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_halted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    halt_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    open_position: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    consecutive_high_latency: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    last_daily_reset_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_weekly_reset_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class PaperTradingReceiptModel(Base):
    __tablename__ = "paper_trading_receipts"
    __table_args__ = (UniqueConstraint("session_id", "bar_ts", name="uq_session_bar"),)

    receipt_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    bar_ts: Mapped[int] = mapped_column(BigInteger, nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    decision_source: Mapped[str] = mapped_column(String(50), nullable=False)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class PromotionReceiptModel(Base):
    __tablename__ = "promotion_receipts"
    __table_args__ = (CheckConstraint("approved_by != ''", name="ck_approved_by_not_empty"),)

    receipt_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    promotion_target: Mapped[str] = mapped_column(String(50), nullable=False)
    promotion_basis: Mapped[str] = mapped_column(Text, nullable=False)
    approved_by: Mapped[str] = mapped_column(String(50), nullable=False)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    linked_receipt_ids: Mapped[list] = mapped_column(JSONB, nullable=False)
    risk_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
