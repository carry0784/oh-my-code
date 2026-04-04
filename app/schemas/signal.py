from datetime import datetime
from pydantic import BaseModel, Field

from app.models.signal import SignalType, SignalStatus


class SignalCreate(BaseModel):
    model_config = {"populate_by_name": True}

    source: str = Field(..., description="Signal source identifier")
    exchange: str
    symbol: str
    signal_type: SignalType
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    signal_metadata: dict = Field(default_factory=dict, alias="metadata", serialization_alias="metadata")


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
    signal_metadata: dict = Field(alias="metadata", serialization_alias="metadata")
    agent_analysis: str | None
    created_at: datetime
    expires_at: datetime | None

    model_config = {"from_attributes": True, "populate_by_name": True}


class SignalList(BaseModel):
    signals: list[SignalResponse]
    total: int
