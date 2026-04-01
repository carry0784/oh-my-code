"""
MarketStateBuilder — CR-038 Phase 1
Assembles a unified MarketStateSnapshot from collected data components.
Pure transformation — no I/O, no side effects.
"""

from datetime import datetime, timezone

from app.core.logging import get_logger
from app.schemas.market_state_schema import (
    IndicatorSet,
    MarketDataCollectionResult,
    MarketMicrostructure,
    MarketStateSnapshot,
    OnChainData,
    PriceData,
    SentimentCollectionResult,
    SentimentData,
)

logger = get_logger(__name__)

# Regime detection thresholds
RSI_OVERBOUGHT = 70.0
RSI_OVERSOLD = 30.0
ATR_HIGH_VOL_MULTIPLIER = 2.0  # ATR > 2x SMA_20 spread → high volatility


class MarketStateBuilder:
    """Builds unified MarketStateSnapshot from raw collected data."""

    def build(
        self,
        market_data: MarketDataCollectionResult,
        indicators: IndicatorSet,
        sentiment: SentimentCollectionResult | None = None,
    ) -> MarketStateSnapshot:
        """Assemble all components into a single market state snapshot."""
        price_data = self._extract_price_data(market_data)
        microstructure = self._extract_microstructure(market_data)
        sentiment_data = self._extract_sentiment(sentiment)
        on_chain = self._extract_on_chain(sentiment)
        regime = self._detect_regime(price_data, indicators, sentiment_data)

        snapshot = MarketStateSnapshot(
            exchange=market_data.exchange,
            symbol=market_data.symbol,
            price_data=price_data,
            indicators=indicators,
            sentiment=sentiment_data,
            on_chain=on_chain,
            microstructure=microstructure,
            regime=regime,
            snapshot_at=datetime.now(timezone.utc),
        )

        logger.info(
            "market_state_built",
            exchange=snapshot.exchange,
            symbol=snapshot.symbol,
            regime=regime,
            price=price_data.price,
        )
        return snapshot

    def _extract_price_data(self, data: MarketDataCollectionResult) -> PriceData:
        ticker = data.ticker or {}
        return PriceData(
            price=ticker.get("last", 0.0),
            volume_24h=ticker.get("quoteVolume") or ticker.get("baseVolume"),
            high_24h=ticker.get("high"),
            low_24h=ticker.get("low"),
            change_pct_24h=ticker.get("percentage"),
        )

    def _extract_microstructure(
        self, data: MarketDataCollectionResult
    ) -> MarketMicrostructure:
        ticker = data.ticker or {}
        bid = ticker.get("bid")
        ask = ticker.get("ask")
        spread_pct = None
        if bid and ask and bid > 0:
            spread_pct = ((ask - bid) / bid) * 100

        return MarketMicrostructure(
            funding_rate=data.funding_rate,
            open_interest=data.open_interest,
            bid=bid,
            ask=ask,
            spread_pct=spread_pct,
        )

    def _extract_sentiment(
        self, sentiment: SentimentCollectionResult | None
    ) -> SentimentData:
        if not sentiment:
            return SentimentData()
        return SentimentData(
            fear_greed_index=sentiment.fear_greed_index,
            fear_greed_label=sentiment.fear_greed_label,
        )

    def _extract_on_chain(
        self, sentiment: SentimentCollectionResult | None
    ) -> OnChainData:
        if not sentiment:
            return OnChainData()
        return sentiment.on_chain

    def _detect_regime(
        self,
        price: PriceData,
        indicators: IndicatorSet,
        sentiment: SentimentData,
    ) -> str:
        """Simple rule-based regime detection. Phase 2 will add ML-based detection."""
        # Crisis: Fear & Greed ≤ 10 or extreme RSI oversold with high volatility
        if sentiment.fear_greed_index is not None and sentiment.fear_greed_index <= 10:
            return "crisis"

        # High volatility: large ATR relative to price, or large 24h range
        if indicators.atr_14 and price.price > 0:
            atr_pct = (indicators.atr_14 / price.price) * 100
            if atr_pct > 3.0:  # ATR > 3% of price
                return "high_volatility"

        # Trending up: price > SMA_50, RSI > 50, MACD histogram > 0
        if (
            indicators.sma_50
            and price.price > indicators.sma_50
            and indicators.rsi_14
            and indicators.rsi_14 > 50
            and indicators.macd_histogram
            and indicators.macd_histogram > 0
        ):
            return "trending_up"

        # Trending down: price < SMA_50, RSI < 50, MACD histogram < 0
        if (
            indicators.sma_50
            and price.price < indicators.sma_50
            and indicators.rsi_14
            and indicators.rsi_14 < 50
            and indicators.macd_histogram
            and indicators.macd_histogram < 0
        ):
            return "trending_down"

        # Ranging: RSI between 40-60, price near SMA_20
        if indicators.rsi_14 and 40 <= indicators.rsi_14 <= 60:
            return "ranging"

        return "unknown"
