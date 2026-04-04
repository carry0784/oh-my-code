"""Feature Pack model — a bundle of indicators used by a strategy.

CR-048 Phase 1: design_feature_pack.md v1.0
"""

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import String, Integer, DateTime, Text, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FeaturePackStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CHALLENGER = "CHALLENGER"
    DEPRECATED = "DEPRECATED"
    BLOCKED = "BLOCKED"


class FeaturePack(Base):
    __tablename__ = "feature_packs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(100), unique=True)
    version: Mapped[str] = mapped_column(String(20))  # semver
    description: Mapped[str | None] = mapped_column(Text, nullable=True)  # CR-048

    # Indicator composition — JSON list of indicator IDs
    indicator_ids: Mapped[str] = mapped_column(Text)  # JSON: ["ind-uuid-1", "ind-uuid-2"]
    weights: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: {"ind-uuid-1": 1.0}

    # CR-048: asset class, timeframe, warmup (design card §4.1)
    asset_classes: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: ["CRYPTO"]
    timeframes: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: ["1h", "4h"]
    warmup_bars: Mapped[int] = mapped_column(Integer, default=0)  # max(indicator warmup_bars)

    # CR-048: Champion/Challenger (design card §4.1)
    champion_of: Mapped[str | None] = mapped_column(String(36), nullable=True)  # strategy_id

    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)  # SHA-256

    status: Mapped[str] = mapped_column(
        SQLEnum(FeaturePackStatus, values_callable=lambda e: [x.value for x in e]),
        default=FeaturePackStatus.ACTIVE,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
