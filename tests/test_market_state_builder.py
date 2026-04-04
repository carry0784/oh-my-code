"""Tests for MarketStateBuilder — CR-038 Phase 1."""

import sys
from unittest.mock import MagicMock

# Stub external dependencies before imports
_STUB_MODULES = [
    "ccxt", "ccxt.async_support", "aiohttp",
    "celery", "redis", "sqlalchemy", "sqlalchemy.ext", "sqlalchemy.ext.asyncio",
    "sqlalchemy.orm", "sqlalchemy.pool", "sqlalchemy.engine",
    "app.core.database", "app.core.config",
]
for name in _STUB_MODULES:
    if name not in sys.modules:
        sys.modules[name] = MagicMock()

_fake_base = type("FakeBase", (), {"__tablename__": "", "metadata": MagicMock()})
sys.modules["app.core.database"].Base = _fake_base
sys.modules["app.core.database"].engine = MagicMock()
sys.modules["app.core.database"].async_session_factory = MagicMock()

import pytest

from app.schemas.market_state_schema import (
    IndicatorSet,
    MarketDataCollectionResult,
    OnChainData,
    SentimentCollectionResult,
)
from app.services.market_state_builder import MarketStateBuilder


def _make_market_data(**kwargs) -> MarketDataCollectionResult:
    defaults = {
        "exchange": "binance",
        "symbol": "BTC/USDT",
        "ticker": {
            "last": 65000.0,
            "bid": 64999.0,
            "ask": 65001.0,
            "high": 66000.0,
            "low": 64000.0,
            "quoteVolume": 1_000_000_000,
            "percentage": 2.5,
        },
    }
    defaults.update(kwargs)
    return MarketDataCollectionResult(**defaults)


class TestMarketStateBuilder:
    def setup_method(self):
        self.builder = MarketStateBuilder()

    def test_basic_build(self):
        data = _make_market_data()
        indicators = IndicatorSet()
        result = self.builder.build(data, indicators)

        assert result.exchange == "binance"
        assert result.symbol == "BTC/USDT"
        assert result.price_data.price == 65000.0
        assert result.snapshot_at is not None

    def test_price_extraction(self):
        data = _make_market_data()
        indicators = IndicatorSet()
        result = self.builder.build(data, indicators)

        assert result.price_data.high_24h == 66000.0
        assert result.price_data.low_24h == 64000.0
        assert result.price_data.change_pct_24h == 2.5

    def test_spread_calculation(self):
        data = _make_market_data()
        indicators = IndicatorSet()
        result = self.builder.build(data, indicators)

        expected_spread = ((65001 - 64999) / 64999) * 100
        assert result.microstructure.spread_pct is not None
        assert abs(result.microstructure.spread_pct - expected_spread) < 0.001

    def test_sentiment_integration(self):
        data = _make_market_data()
        indicators = IndicatorSet()
        sentiment = SentimentCollectionResult(
            fear_greed_index=25, fear_greed_label="Extreme Fear"
        )
        result = self.builder.build(data, indicators, sentiment)

        assert result.sentiment.fear_greed_index == 25
        assert result.sentiment.fear_greed_label == "Extreme Fear"

    def test_no_sentiment_defaults(self):
        data = _make_market_data()
        indicators = IndicatorSet()
        result = self.builder.build(data, indicators)

        assert result.sentiment.fear_greed_index is None

    def test_regime_trending_up(self):
        data = _make_market_data()
        indicators = IndicatorSet(
            sma_50=60000.0,  # price > sma_50
            rsi_14=65.0,     # > 50
            macd_histogram=100.0,  # > 0
        )
        result = self.builder.build(data, indicators)
        assert result.regime == "trending_up"

    def test_regime_trending_down(self):
        data = _make_market_data()
        indicators = IndicatorSet(
            sma_50=70000.0,  # price < sma_50
            rsi_14=35.0,     # < 50
            macd_histogram=-100.0,  # < 0
        )
        result = self.builder.build(data, indicators)
        assert result.regime == "trending_down"

    def test_regime_crisis(self):
        data = _make_market_data()
        indicators = IndicatorSet()
        sentiment = SentimentCollectionResult(
            fear_greed_index=5,  # ≤ 10
            fear_greed_label="Extreme Fear",
        )
        result = self.builder.build(data, indicators, sentiment)
        assert result.regime == "crisis"

    def test_regime_high_volatility(self):
        data = _make_market_data()
        indicators = IndicatorSet(
            atr_14=3000.0,  # 3000/65000 = 4.6% > 3%
        )
        result = self.builder.build(data, indicators)
        assert result.regime == "high_volatility"

    def test_regime_ranging(self):
        data = _make_market_data()
        indicators = IndicatorSet(
            rsi_14=50.0,  # Between 40-60
        )
        result = self.builder.build(data, indicators)
        assert result.regime == "ranging"

    def test_regime_unknown_no_data(self):
        data = _make_market_data()
        indicators = IndicatorSet()
        result = self.builder.build(data, indicators)
        assert result.regime == "unknown"

    def test_funding_rate_passthrough(self):
        data = _make_market_data(funding_rate=0.0003)
        indicators = IndicatorSet()
        result = self.builder.build(data, indicators)
        assert result.microstructure.funding_rate == 0.0003

    def test_open_interest_passthrough(self):
        data = _make_market_data(open_interest=50000.0)
        indicators = IndicatorSet()
        result = self.builder.build(data, indicators)
        assert result.microstructure.open_interest == 50000.0

    def test_no_ticker_zero_price(self):
        data = MarketDataCollectionResult(
            exchange="binance", symbol="BTC/USDT", ticker=None
        )
        indicators = IndicatorSet()
        result = self.builder.build(data, indicators)
        assert result.price_data.price == 0.0

    def test_regime_priority_crisis_over_volatility(self):
        """Crisis should take priority over high volatility."""
        data = _make_market_data()
        indicators = IndicatorSet(atr_14=5000.0)  # Would be high_vol
        sentiment = SentimentCollectionResult(
            fear_greed_index=5,  # Crisis level
        )
        result = self.builder.build(data, indicators, sentiment)
        assert result.regime == "crisis"

    def test_regime_priority_volatility_over_trend(self):
        """High volatility should take priority over trending."""
        data = _make_market_data()
        indicators = IndicatorSet(
            sma_50=60000.0,
            rsi_14=65.0,
            macd_histogram=100.0,
            atr_14=5000.0,  # High vol
        )
        result = self.builder.build(data, indicators)
        assert result.regime == "high_volatility"

    def test_on_chain_data_passthrough(self):
        data = _make_market_data()
        indicators = IndicatorSet()
        on_chain = OnChainData(
            hash_rate=500000.0,
            difficulty=83_000_000_000_000,
            tx_count_24h=350000,
            mempool_size=12000,
            mempool_fee_fast=45.0,
            btc_dominance=54.3,
            total_market_cap_usd=2_500_000_000_000,
        )
        sentiment = SentimentCollectionResult(
            fear_greed_index=50, on_chain=on_chain
        )
        result = self.builder.build(data, indicators, sentiment)

        assert result.on_chain.hash_rate == 500000.0
        assert result.on_chain.difficulty == 83_000_000_000_000
        assert result.on_chain.tx_count_24h == 350000
        assert result.on_chain.mempool_fee_fast == 45.0
        assert result.on_chain.btc_dominance == 54.3

    def test_on_chain_defaults_without_sentiment(self):
        data = _make_market_data()
        indicators = IndicatorSet()
        result = self.builder.build(data, indicators)

        assert result.on_chain.hash_rate is None
        assert result.on_chain.btc_dominance is None
