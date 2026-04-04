from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import String, Float, DateTime, Text, Enum as SQLEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SignalType(str, Enum):
    LONG = "long"
    SHORT = "short"
    CLOSE = "close"


class SignalStatus(str, Enum):
    PENDING = "pending"
    VALIDATED = "validated"
    REJECTED = "rejected"
    EXECUTED = "executed"
    EXPIRED = "expired"


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source: Mapped[str] = mapped_column(String(100))
    exchange: Mapped[str] = mapped_column(String(50))
    symbol: Mapped[str] = mapped_column(String(20))
    signal_type: Mapped[SignalType] = mapped_column(SQLEnum(SignalType))
    entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[SignalStatus] = mapped_column(SQLEnum(SignalStatus), default=SignalStatus.PENDING)
    metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    agent_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
