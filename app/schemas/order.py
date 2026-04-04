from datetime import datetime
from pydantic import BaseModel, Field

from app.models.order import OrderSide, OrderType, OrderStatus


class OrderCreate(BaseModel):
    exchange: str = Field(..., description="Exchange identifier (binance, okx)")
    symbol: str = Field(..., description="Trading pair (e.g., BTC/USDT)")
    side: OrderSide
    order_type: OrderType
    quantity: float = Field(..., gt=0)
    price: float | None = Field(None, gt=0)
    signal_id: str | None = None


class OrderResponse(BaseModel):
    id: str
    exchange: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: float | None
    status: OrderStatus
    exchange_order_id: str | None
    filled_quantity: float
    average_price: float | None
    signal_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrderList(BaseModel):
    orders: list[OrderResponse]
    total: int
