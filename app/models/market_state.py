"""
MarketState Model — CR-038 Phase 1
Persistent market state snapshots combining price, volume, indicators, and sentiment.
"""

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import String, Float, Integer, DateTime, JSON, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MarketRegime(str, Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    CRISIS = "crisis"
    UNKNOWN = "unknown"


class MarketState(Base):
    __tablename__ = "market_states"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    exchange: Mapped[str] = mapped_column(String(50), index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)

    # Price data
    price: Mapped[float] = mapped_column(Float)
    bid: Mapped[float | None] = mapped_column(Float, nullable=True)
    ask: Mapped[float | None] = mapped_column(Float, nullable=True)
    spread_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_24h: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Technical indicators
    rsi_14: Mapped[float | None] = mapped_column(Float, nullable=True)
    macd_line: Mapped[float | None] = mapped_column(Float, nullable=True)
    macd_signal: Mapped[float | None] = mapped_column(Float, nullable=True)
    macd_histogram: Mapped[float | None] = mapped_column(Float, nullable=True)
    bb_upper: Mapped[float | None] = mapped_column(Float, nullable=True)
    bb_middle: Mapped[float | None] = mapped_column(Float, nullable=True)
    bb_lower: Mapped[float | None] = mapped_column(Float, nullable=True)
    atr_14: Mapped[float | None] = mapped_column(Float, nullable=True)
    obv: Mapped[float | None] = mapped_column(Float, nullable=True)
    sma_20: Mapped[float | None] = mapped_column(Float, nullable=True)
    sma_50: Mapped[float | None] = mapped_column(Float, nullable=True)
    sma_200: Mapped[float | None] = mapped_column(Float, nullable=True)
    ema_12: Mapped[float | None] = mapped_column(Float, nullable=True)
    ema_26: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Sentiment
    fear_greed_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fear_greed_label: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # On-chain indicators (free APIs: Blockchain.com, Mempool.space, CoinGecko)
    hash_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    difficulty: Mapped[float | None] = mapped_column(Float, nullable=True)
    tx_count_24h: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mempool_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mempool_fee_fast: Mapped[float | None] = mapped_column(Float, nullable=True)
    mempool_fee_medium: Mapped[float | None] = mapped_column(Float, nullable=True)
    btc_dominance: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_market_cap_usd: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Market microstructure
    funding_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    open_interest: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Regime
    regime: Mapped[MarketRegime] = mapped_column(
        SQLEnum(MarketRegime), default=MarketRegime.UNKNOWN
    )

    # Raw data storage
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )
