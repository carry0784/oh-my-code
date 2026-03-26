from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import String, Float, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    exchange: Mapped[str] = mapped_column(String(50))
    symbol: Mapped[str] = mapped_column(String(20))
    order_id: Mapped[str] = mapped_column(String(36))
    exchange_trade_id: Mapped[str] = mapped_column(String(100))
    side: Mapped[str] = mapped_column(String(10))
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    fee: Mapped[float] = mapped_column(Float, default=0.0)
    fee_currency: Mapped[str] = mapped_column(String(10), default="USDT")
    executed_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
