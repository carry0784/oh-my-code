"""Promotion State model — tracks every state transition in a strategy's lifecycle."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PromotionEvent(Base):
    __tablename__ = "promotion_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    strategy_id: Mapped[str] = mapped_column(String(36), index=True)

    from_status: Mapped[str] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggered_by: Mapped[str] = mapped_column(String(100))  # user or "system"
    approval_level: Mapped[str | None] = mapped_column(String(20), nullable=True)  # LOW/MEDIUM/HIGH

    # CR-048: design card §4.1 — evidence and approval tracking
    evidence: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON: backtest/paper results
    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)  # approver identity

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
