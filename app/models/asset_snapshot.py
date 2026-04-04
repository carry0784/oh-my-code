"""
Asset Snapshot Model — I-05 총 자산 시계열
Periodic snapshots of aggregated portfolio value for time-window statistics.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import String, Float, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AssetSnapshot(Base):
    __tablename__ = "asset_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    total_value: Mapped[float] = mapped_column(Float, default=0.0)
    trade_count: Mapped[int] = mapped_column(Integer, default=0)
    total_balance: Mapped[float] = mapped_column(Float, default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )
