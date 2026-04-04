"""Indicator Registry model — single technical indicator metadata.

CR-048 Phase 1: design_indicator_registry.md v1.0
"""

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import String, Integer, DateTime, Text, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class IndicatorCategory(str, Enum):
    """CR-048 design card: 5 indicator categories."""

    MOMENTUM = "MOMENTUM"
    TREND = "TREND"
    VOLATILITY = "VOLATILITY"
    VOLUME = "VOLUME"
    OSCILLATOR = "OSCILLATOR"


class IndicatorStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    BLOCKED = "BLOCKED"


class Indicator(Base):
    __tablename__ = "indicators"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(100), unique=True)
    version: Mapped[str] = mapped_column(String(20))  # semver: "1.0.0"
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # CR-048: indicator category (design card §4.1)
    category: Mapped[str | None] = mapped_column(
        SQLEnum(IndicatorCategory, values_callable=lambda e: [x.value for x in e]),
        nullable=True,
    )

    # I/O schema
    input_params: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: {"period": 14}
    output_fields: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: ["rsi_value"]

    # CR-048: asset class & timeframe applicability (design card §4.1)
    asset_classes: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON: ["CRYPTO", "US_STOCK"]
    timeframes: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: ["1h", "4h", "1d"]

    # Compute metadata
    warmup_bars: Mapped[int] = mapped_column(Integer, default=0)
    compute_module: Mapped[str] = mapped_column(String(200))  # e.g. "app.indicators.rsi"
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)  # SHA-256

    status: Mapped[str] = mapped_column(
        SQLEnum(IndicatorStatus, values_callable=lambda e: [x.value for x in e]),
        default=IndicatorStatus.ACTIVE,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
