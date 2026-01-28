from datetime import datetime
from pydantic import BaseModel

from app.models.position import PositionSide


class PositionResponse(BaseModel):
    id: str
    exchange: str
    symbol: str
    side: PositionSide
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    leverage: float
    liquidation_price: float | None
    opened_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PositionList(BaseModel):
    positions: list[PositionResponse]
    total: int
