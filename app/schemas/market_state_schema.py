"""
MarketState Schemas — CR-038 Phase 1
Pydantic schemas for market state data transfer.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IndicatorSet(BaseModel):
    rsi_14: float | None = None
    macd_line: float | None = None
    macd_signal: float | None = None
    macd_histogram: float | None = None
    bb_upper: float | None = None
    bb_middle: float | None = None
    bb_lower: float | None = None
    atr_14: float | None = None
    obv: float | None = None
    sma_20: float | None = None
    sma_50: float | None = None
    sma_200: float | None = None
    ema_12: float | None = None
    ema_26: float | None = None


class OnChainData(BaseModel):
    """Free on-chain indicators from Blockchain.com + Mempool.space."""
    # Blockchain.com (free, no key)
    hash_rate: float | None = None          # TH/s — miner confidence
    difficulty: float | None = None          # network difficulty
    tx_count_24h: int | None = None          # daily transaction count
    mempool_size: int | None = None          # unconfirmed tx count
    avg_block_size: float | None = None      # bytes — network load

    # Mempool.space (free, no key)
    mempool_fee_fast: float | None = None    # sat/vB — fastest confirm
    mempool_fee_medium: float | None = None  # sat/vB — ~30min confirm
    mempool_fee_slow: float | None = None    # sat/vB — ~1h confirm
    mempool_vsize: float | None = None       # MB — mempool total vsize

    # CoinGecko (free, no key)
    btc_dominance: float | None = None       # % — BTC market dominance
    total_market_cap_usd: float | None = None
    total_volume_24h_usd: float | None = None


class SentimentData(BaseModel):
    fear_greed_index: int | None = None
    fear_greed_label: str | None = None


class MarketMicrostructure(BaseModel):
    funding_rate: float | None = None
    open_interest: float | None = None
    bid: float | None = None
    ask: float | None = None
    spread_pct: float | None = None


class PriceData(BaseModel):
    price: float
    volume_24h: float | None = None
    high_24h: float | None = None
    low_24h: float | None = None
    change_pct_24h: float | None = None


class OHLCVBar(BaseModel):
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketStateSnapshot(BaseModel):
    exchange: str
    symbol: str
    price_data: PriceData
    indicators: IndicatorSet = Field(default_factory=IndicatorSet)
    sentiment: SentimentData = Field(default_factory=SentimentData)
    on_chain: OnChainData = Field(default_factory=OnChainData)
    microstructure: MarketMicrostructure = Field(default_factory=MarketMicrostructure)
    regime: str = "unknown"
    snapshot_at: datetime | None = None
    raw_data: dict[str, Any] | None = None


class MarketDataCollectionResult(BaseModel):
    exchange: str
    symbol: str
    ticker: dict[str, Any] | None = None
    ohlcv: list[OHLCVBar] = Field(default_factory=list)
    order_book: dict[str, Any] | None = None
    recent_trades: list[dict[str, Any]] = Field(default_factory=list)
    funding_rate: float | None = None
    open_interest: float | None = None
    collected_at: datetime | None = None


class SentimentCollectionResult(BaseModel):
    fear_greed_index: int | None = None
    fear_greed_label: str | None = None
    on_chain: OnChainData = Field(default_factory=OnChainData)
    source: str = "unknown"
    collected_at: datetime | None = None
