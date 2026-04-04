"""Tests for MarketScorer — CR-039 Phase 2."""

import sys
from unittest.mock import MagicMock

_STUB_MODULES = [
    "ccxt",
    "ccxt.async_support",
    "aiohttp",
    "celery",
    "redis",
    "sqlalchemy",
    "sqlalchemy.ext",
    "sqlalchemy.ext.asyncio",
    "sqlalchemy.orm",
    "sqlalchemy.pool",
    "sqlalchemy.engine",
    "app.core.database",
    "app.core.config",
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
    OnChainData,
    PriceData,
    SentimentData,
)
from app.services.market_scorer import MarketScorer, ScoreBreakdown


class TestMarketScorerGrades:
    def setup_method(self):
        self.scorer = MarketScorer()

    def test_strong_bull(self):
        price = PriceData(price=65000)
        indicators = IndicatorSet(
            rsi_14=75,
            macd_histogram=500,
            sma_20=60000,
            sma_50=58000,
            sma_200=50000,
            ema_12=64000,
            ema_26=62000,
            bb_upper=68000,
            bb_lower=60000,
        )
        sentiment = SentimentData(fear_greed_index=80)
        on_chain = OnChainData(hash_rate=500000, btc_dominance=55)
        result = self.scorer.score(price, indicators, sentiment, on_chain=on_chain)
        assert result.grade == "STRONG_BULL"
        assert result.total >= 50

    def test_strong_bear(self):
        price = PriceData(price=55000)
        indicators = IndicatorSet(
            rsi_14=20,
            macd_histogram=-500,
            sma_20=60000,
            sma_50=62000,
            sma_200=65000,
            ema_12=56000,
            ema_26=58000,
            bb_upper=62000,
            bb_lower=54000,
        )
        sentiment = SentimentData(fear_greed_index=10)
        result = self.scorer.score(price, indicators, sentiment)
        assert result.grade == "STRONG_BEAR"
        assert result.total <= -50

    def test_neutral(self):
        price = PriceData(price=65000)
        indicators = IndicatorSet(rsi_14=50, macd_histogram=0)
        sentiment = SentimentData(fear_greed_index=50)
        result = self.scorer.score(price, indicators, sentiment)
        assert result.grade == "NEUTRAL"
        assert -20 <= result.total <= 20

    def test_bull(self):
        price = PriceData(price=65000)
        indicators = IndicatorSet(
            rsi_14=60,
            macd_histogram=100,
            sma_50=62000,
            ema_12=64500,
            ema_26=63000,
        )
        sentiment = SentimentData(fear_greed_index=65)
        result = self.scorer.score(price, indicators, sentiment)
        assert result.grade in ("BULL", "STRONG_BULL")
        assert result.total >= 20

    def test_bear(self):
        price = PriceData(price=55000)
        indicators = IndicatorSet(
            rsi_14=35,
            macd_histogram=-100,
            sma_50=60000,
            ema_12=56000,
            ema_26=58000,
        )
        sentiment = SentimentData(fear_greed_index=30)
        result = self.scorer.score(price, indicators, sentiment)
        assert result.grade in ("BEAR", "STRONG_BEAR")
        assert result.total <= -20


class TestMarketScorerComponents:
    def setup_method(self):
        self.scorer = MarketScorer()

    def test_technical_only(self):
        price = PriceData(price=65000)
        indicators = IndicatorSet(rsi_14=70, macd_histogram=200)
        result = self.scorer.score(price, indicators)
        assert result.technical > 0
        assert result.sentiment == 0.0  # No sentiment data

    def test_sentiment_only(self):
        price = PriceData(price=65000)
        indicators = IndicatorSet()  # No tech data
        sentiment = SentimentData(fear_greed_index=80)
        result = self.scorer.score(price, indicators, sentiment)
        assert result.sentiment > 0
        assert result.technical == 0.0

    def test_on_chain_component(self):
        price = PriceData(price=65000)
        indicators = IndicatorSet()
        on_chain = OnChainData(
            mempool_fee_fast=50,
            btc_dominance=55,
            hash_rate=500000,
        )
        result = self.scorer.score(price, indicators, on_chain=on_chain)
        assert result.on_chain != 0.0  # Should have some on-chain signal

    def test_high_fee_negative_on_chain(self):
        price = PriceData(price=65000)
        indicators = IndicatorSet()
        on_chain = OnChainData(mempool_fee_fast=250)  # Panic-level fees
        result = self.scorer.score(price, indicators, on_chain=on_chain)
        assert result.on_chain < 0  # Should be negative

    def test_no_data_returns_neutral(self):
        price = PriceData(price=65000)
        indicators = IndicatorSet()
        result = self.scorer.score(price, indicators)
        assert result.total == 0.0
        assert result.grade == "NEUTRAL"


class TestMarketScorerRange:
    def setup_method(self):
        self.scorer = MarketScorer()

    def test_score_bounded(self):
        """Score should always be in [-100, +100]."""
        price = PriceData(price=65000)
        indicators = IndicatorSet(
            rsi_14=99,
            macd_histogram=10000,
            sma_20=10000,
            sma_50=10000,
            sma_200=10000,
            ema_12=64000,
            ema_26=60000,
            bb_upper=70000,
            bb_lower=60000,
        )
        sentiment = SentimentData(fear_greed_index=100)
        result = self.scorer.score(price, indicators, sentiment)
        assert -100 <= result.total <= 100

    def test_extreme_bear_bounded(self):
        price = PriceData(price=65000)
        indicators = IndicatorSet(
            rsi_14=1,
            macd_histogram=-10000,
            sma_20=90000,
            sma_50=95000,
            sma_200=100000,
            ema_12=66000,
            ema_26=68000,
        )
        sentiment = SentimentData(fear_greed_index=0)
        result = self.scorer.score(price, indicators, sentiment)
        assert -100 <= result.total <= 100

    def test_signal_strength_range(self):
        price = PriceData(price=65000)
        indicators = IndicatorSet(rsi_14=50)
        result = self.scorer.score(price, indicators)
        assert 0 <= result.signal_strength <= 1.0

    def test_bollinger_position_scoring(self):
        """Price at upper BB should score bullish."""
        price = PriceData(price=69000)
        indicators = IndicatorSet(
            bb_upper=70000,
            bb_lower=60000,
        )
        result = self.scorer.score(price, indicators)
        assert result.technical > 0  # Near top of BB range

    def test_bollinger_lower_scoring(self):
        """Price at lower BB should score bearish."""
        price = PriceData(price=61000)
        indicators = IndicatorSet(
            bb_upper=70000,
            bb_lower=60000,
        )
        result = self.scorer.score(price, indicators)
        assert result.technical < 0  # Near bottom of BB range
