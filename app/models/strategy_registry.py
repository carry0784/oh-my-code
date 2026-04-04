"""Strategy Registry model — strategy metadata, market matrix, and promotion state."""

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import String, Float, Integer, DateTime, Text, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AssetClass(str, Enum):
    CRYPTO = "CRYPTO"
    US_STOCK = "US_STOCK"
    KR_STOCK = "KR_STOCK"


class PromotionStatus(str, Enum):
    DRAFT = "DRAFT"
    REGISTERED = "REGISTERED"
    BACKTEST_PASS = "BACKTEST_PASS"
    BACKTEST_FAIL = "BACKTEST_FAIL"  # CR-048: design card §4.1
    PAPER_PASS = "PAPER_PASS"
    QUARANTINE = "QUARANTINE"
    GUARDED_LIVE = "GUARDED_LIVE"
    LIVE = "LIVE"
    RETIRED = "RETIRED"
    BLOCKED = "BLOCKED"


class Strategy(Base):
    __tablename__ = "strategies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(100))
    version: Mapped[str] = mapped_column(String(20))  # semver: "2.1.4"
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Dependencies
    feature_pack_id: Mapped[str] = mapped_column(String(36))  # FK to feature_packs.id
    compute_module: Mapped[str] = mapped_column(String(200))  # e.g. "strategies.smc_wavetrend"
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)  # SHA-256

    # Market matrix (JSON)
    asset_classes: Mapped[str] = mapped_column(Text)  # JSON: ["crypto"]
    exchanges: Mapped[str] = mapped_column(Text)  # JSON: ["BINANCE", "UPBIT"]
    sectors: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: ["LAYER1", "DEFI"]
    timeframes: Mapped[str] = mapped_column(Text)  # JSON: ["1h", "4h"]
    regimes: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: ["trending_up"]
    max_symbols: Mapped[int] = mapped_column(Integer, default=20)

    # Promotion
    status: Mapped[str] = mapped_column(
        SQLEnum(PromotionStatus, values_callable=lambda e: [x.value for x in e]),
        default=PromotionStatus.DRAFT,
    )
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    promoted_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Champion/Challenger
    is_champion: Mapped[bool] = mapped_column(default=False)
    champion_since: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
