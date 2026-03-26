"""
B-09: Market Feed Schema — read-only best bid/ask/spread 정규화

4개 거래소 (Binance, OKX, UpBit, Bitget) best bid/ask/spread/trust/staleness.
KIS/Kiwoom 제외 (bid/ask 미지원). full orderbook/execution/strategy 범위 밖.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class QuoteEntry(BaseModel):
    """단일 심볼 quote."""

    exchange: str = ""
    symbol: str = ""
    bid: Optional[float] = None
    ask: Optional[float] = None
    spread: Optional[float] = None
    last: Optional[float] = None
    as_of: Optional[str] = Field(default=None, description="ISO 8601")
    age_seconds: Optional[float] = None
    trust_state: str = Field(
        default="UNKNOWN",
        description="LIVE/STALE/NOT_AVAILABLE/UNAVAILABLE/DISCONNECTED/NOT_QUERIED",
    )
    is_stale: bool = Field(default=False, description="age > threshold")


class VenueFeedSummary(BaseModel):
    """거래소별 feed 요약."""

    exchange: str = ""
    trust_state: str = "UNKNOWN"
    live_count: int = 0
    stale_count: int = 0
    total_symbols: int = 0
    supported: bool = True


class MarketFeedSummary(BaseModel):
    """AI Assist 친화적 market feed 요약."""

    venues_connected: int = Field(default=0)
    venues_total: int = Field(default=4, description="bid/ask 지원 거래소 수")
    total_live: int = 0
    total_stale: int = 0
    worst_trust: str = "UNKNOWN"
    stale_threshold_seconds: int = Field(default=120)


class MarketFeedResponse(BaseModel):
    """
    B-09: Market Feed 응답.
    Read-only. No execution. No recommendation.
    """

    summary: MarketFeedSummary = Field(default_factory=MarketFeedSummary)
    venues: list[VenueFeedSummary] = Field(default_factory=list)
    quotes: list[QuoteEntry] = Field(default_factory=list)
    feed_note: str = Field(
        default="Read-only best bid/ask/spread feed. No execution path.",
    )
