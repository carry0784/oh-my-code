"""
B-09: Market Feed Service — read-only best bid/ask/spread

기존 `_get_quote_data()` 기능을 독립 서비스 계층으로 제공한다.
4개 거래소 (Binance, OKX, UpBit, Bitget). KIS/Kiwoom 제외.
full orderbook/execution/strategy 범위 밖.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.logging import get_logger
from app.schemas.market_feed_schema import (
    MarketFeedResponse,
    MarketFeedSummary,
    QuoteEntry,
    VenueFeedSummary,
)

logger = get_logger(__name__)

_SUPPORTED_EXCHANGES = ["binance", "okx", "upbit", "bitget"]
_BID_ASK_NOT_SUPPORTED = {"kis", "kiwoom"}
_STALE_THRESHOLD_S = 120

# Trust state priority (worst wins)
_TRUST_PRIORITY = {
    "LIVE": 0,
    "STALE": 1,
    "NOT_AVAILABLE": 2,
    "UNAVAILABLE": 3,
    "DISCONNECTED": 4,
    "NOT_QUERIED": 5,
    "UNKNOWN": 6,
}


def build_market_feed_from_quote_data(quote_data: dict | None) -> MarketFeedResponse:
    """
    기존 v2 quote_data dict를 정규화된 MarketFeedResponse로 변환.
    read-only 변환만. 신규 외부 호출 없음.
    """
    if not quote_data:
        return MarketFeedResponse()

    venues: list[VenueFeedSummary] = []
    quotes: list[QuoteEntry] = []
    total_live = 0
    total_stale = 0
    worst_trust = "LIVE"
    venues_connected = 0

    for exchange in _SUPPORTED_EXCHANGES:
        venue_data = quote_data.get(exchange)
        if not venue_data:
            venues.append(VenueFeedSummary(
                exchange=exchange, trust_state="NOT_QUERIED", supported=True,
            ))
            continue

        venue_summary = venue_data.get("_venue_summary", {})
        v_trust = venue_summary.get("trust_state", "UNKNOWN")
        v_live = venue_summary.get("live_count", 0)
        v_stale = venue_summary.get("stale_count", 0)

        symbols = venue_data.get("symbols", {})
        sym_count = len(symbols)

        for symbol, q in symbols.items():
            bid = q.get("bid")
            ask = q.get("ask")
            spread = q.get("spread")
            last = q.get("last")
            as_of = q.get("as_of")
            age = q.get("age_seconds")
            trust = q.get("trust_state", "UNKNOWN")
            is_stale = age is not None and age > _STALE_THRESHOLD_S

            quotes.append(QuoteEntry(
                exchange=exchange,
                symbol=symbol,
                bid=bid,
                ask=ask,
                spread=spread,
                last=last,
                as_of=as_of,
                age_seconds=age,
                trust_state=trust,
                is_stale=is_stale,
            ))

        venues.append(VenueFeedSummary(
            exchange=exchange,
            trust_state=v_trust,
            live_count=v_live,
            stale_count=v_stale,
            total_symbols=sym_count,
            supported=True,
        ))

        total_live += v_live
        total_stale += v_stale
        if sym_count > 0:
            venues_connected += 1

        if _TRUST_PRIORITY.get(v_trust, 99) > _TRUST_PRIORITY.get(worst_trust, 0):
            worst_trust = v_trust

    return MarketFeedResponse(
        summary=MarketFeedSummary(
            venues_connected=venues_connected,
            venues_total=len(_SUPPORTED_EXCHANGES),
            total_live=total_live,
            total_stale=total_stale,
            worst_trust=worst_trust,
            stale_threshold_seconds=_STALE_THRESHOLD_S,
        ),
        venues=venues,
        quotes=quotes,
    )


def build_empty_market_feed() -> MarketFeedResponse:
    """Fail-closed: 데이터 없을 때 안전한 빈 응답."""
    return MarketFeedResponse(
        venues=[
            VenueFeedSummary(exchange=ex, trust_state="NOT_QUERIED", supported=True)
            for ex in _SUPPORTED_EXCHANGES
        ],
    )
