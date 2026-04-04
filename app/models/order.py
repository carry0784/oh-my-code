from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import String, Float, DateTime, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


class OrderStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    exchange: Mapped[str] = mapped_column(String(50))
    symbol: Mapped[str] = mapped_column(String(20))
    # BL-ENUM01: values_callable ensures .value (lowercase) is sent to DB,
    # matching PostgreSQL enum definitions. Without this, SQLAlchemy sends
    # .name (UPPERCASE) which causes "invalid input value for enum" errors.
    side: Mapped[OrderSide] = mapped_column(
        SQLEnum(OrderSide, values_callable=lambda e: [x.value for x in e]),
    )
    order_type: Mapped[OrderType] = mapped_column(
        SQLEnum(OrderType, values_callable=lambda e: [x.value for x in e]),
    )
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[OrderStatus] = mapped_column(
        SQLEnum(OrderStatus, values_callable=lambda e: [x.value for x in e]),
        default=OrderStatus.PENDING,
    )
    exchange_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    filled_quantity: Mapped[float] = mapped_column(Float, default=0.0)
    average_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    signal_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
