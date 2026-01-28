from datetime import datetime
from pydantic import BaseModel, Field

from app.models.signal import SignalType, SignalStatus


class SignalCreate(BaseModel):
    source: str = Field(..., description="Signal source identifier")
    exchange: str
    symbol: str
    signal_type: SignalType
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    metadata: dict = Field(default_factory=dict)


class SignalResponse(BaseModel):
    id: str
    source: str
    exchange: str
    symbol: str
    signal_type: SignalType
    entry_price: float | None
    stop_loss: float | None
    take_profit: float | None
    confidence: float
    status: SignalStatus
    metadata: dict
    agent_analysis: str | None
    created_at: datetime
    expires_at: datetime | None

    model_config = {"from_attributes": True}


class SignalList(BaseModel):
    signals: list[SignalResponse]
    total: int
