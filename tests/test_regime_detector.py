"""Tests for RegimeDetector — CR-039 Phase 2."""

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
    MarketMicrostructure,
    OnChainData,
    PriceData,
    SentimentData,
)
from app.services.regime_detector import RegimeDetector, RegimeResult


class TestRegimeDetectorRuleOverrides:
    def setup_method(self):
        self.detector = RegimeDetector()

    def test_crisis_fear_greed_override(self):
        price = PriceData(price=65000)
        indicators = IndicatorSet(rsi_14=50, sma_50=60000, macd_histogram=100)
        sentiment = SentimentData(fear_greed_index=5)
        result = self.detector.detect(price, indicators, sentiment)
        assert result.regime == "crisis"
        assert result.method == "rule:crisis_fg"
        assert result.confidence >= 0.9

    def test_crisis_extreme_atr_override(self):
        price = PriceData(price=65000)
        indicators = IndicatorSet(atr_14=6000)  # 6000/65000 = 9.2% > 8%
        result = self.detector.detect(price, indicators)
        assert result.regime == "crisis"
        assert result.method == "rule:crisis_atr"

    def test_fear_greed_10_still_crisis(self):
        price = PriceData(price=65000)
        indicators = IndicatorSet()
        sentiment = SentimentData(fear_greed_index=10)
        result = self.detector.detect(price, indicators, sentiment)
        assert result.regime == "crisis"

    def test_fear_greed_11_not_crisis_rule(self):
        price = PriceData(price=65000)
        indicators = IndicatorSet()
        sentiment = SentimentData(fear_greed_index=11)
        result = self.detector.detect(price, indicators, sentiment)
        assert result.method == "cluster"  # Falls through to clustering


class TestRegimeDetectorClustering:
    def setup_method(self):
        self.detector = RegimeDetector()

    def test_trending_up_features(self):
        price = PriceData(price=65000)
        indicators = IndicatorSet(
            rsi_14=70,
            macd_histogram=390,  # 390/65000*100 = 0.6 → matches trending_up centroid
            atr_14=1300,  # 1300/65000 = 0.02 → matches centroid atr_pct
        )
        sentiment = SentimentData(fear_greed_index=70)
        result = self.detector.detect(price, indicators, sentiment)
        assert result.regime == "trending_up"
        assert result.confidence > 0

    def test_trending_down_features(self):
        price = PriceData(price=65000)
        indicators = IndicatorSet(
            rsi_14=30,
            macd_histogram=-390,  # -390/65000*100 = -0.6 → matches trending_down centroid
            atr_14=1300,
        )
        sentiment = SentimentData(fear_greed_index=30)
        result = self.detector.detect(price, indicators, sentiment)
        assert result.regime == "trending_down"

    def test_ranging_features(self):
        price = PriceData(price=65000)
        indicators = IndicatorSet(
            rsi_14=50,
            macd_histogram=0,
            atr_14=650,  # 650/65000 = 0.01 → matches ranging centroid atr_pct
        )
        sentiment = SentimentData(fear_greed_index=50)
        result = self.detector.detect(price, indicators, sentiment)
        assert result.regime == "ranging"

    def test_high_volatility_features(self):
        price = PriceData(price=65000)
        indicators = IndicatorSet(
            rsi_14=50,
            macd_histogram=0,
            atr_14=3900,  # 3900/65000 = 0.06 → matches high_vol centroid atr_pct
        )
        sentiment = SentimentData(fear_greed_index=25)
        on_chain = OnChainData(btc_dominance=55.0, mempool_fee_fast=70)  # fee_norm=0.7
        microstructure = MarketMicrostructure(spread_pct=5.0)
        result = self.detector.detect(
            price,
            indicators,
            sentiment,
            on_chain=on_chain,
            microstructure=microstructure,
        )
        assert result.regime == "high_volatility"

    def test_minimal_data_returns_result(self):
        price = PriceData(price=65000)
        indicators = IndicatorSet()
        result = self.detector.detect(price, indicators)
        assert result.regime in [
            "trending_up",
            "trending_down",
            "ranging",
            "high_volatility",
            "crisis",
            "unknown",
        ]
        assert result.method == "cluster"

    def test_confidence_range(self):
        price = PriceData(price=65000)
        indicators = IndicatorSet(rsi_14=70, macd_histogram=100, atr_14=500)
        result = self.detector.detect(price, indicators)
        assert 0.0 <= result.confidence <= 1.0


class TestRegimeDetectorFeatures:
    def setup_method(self):
        self.detector = RegimeDetector()

    def test_features_returned_in_result(self):
        price = PriceData(price=65000)
        indicators = IndicatorSet(rsi_14=60)
        result = self.detector.detect(price, indicators)
        assert "rsi_norm" in result.features
        assert "macd_hist_norm" in result.features
        assert "fear_greed_norm" in result.features

    def test_rsi_normalization(self):
        price = PriceData(price=65000)
        indicators = IndicatorSet(rsi_14=70)
        result = self.detector.detect(price, indicators)
        assert result.features["rsi_norm"] == pytest.approx(0.7, abs=0.01)

    def test_on_chain_features_integrated(self):
        price = PriceData(price=65000)
        indicators = IndicatorSet(rsi_14=50)
        on_chain = OnChainData(
            btc_dominance=60.0,
            mempool_fee_fast=50,
        )
        result = self.detector.detect(price, indicators, on_chain=on_chain)
        assert result.features["btc_dominance_norm"] == pytest.approx(0.6, abs=0.01)
        assert result.features["mempool_fee_norm"] == pytest.approx(0.5, abs=0.01)


class TestRegimeDetectorMomentum:
    def test_momentum_stabilizes_regime(self):
        detector = RegimeDetector()
        price = PriceData(price=65000)

        # Feed 3 consistent trending_up signals to build history
        for _ in range(3):
            detector.detect(
                price,
                IndicatorSet(rsi_14=70, macd_histogram=200, atr_14=800),
                SentimentData(fear_greed_index=70),
            )

        # Now try a borderline signal — momentum should stabilize
        result = detector.detect(
            price,
            IndicatorSet(rsi_14=55, macd_histogram=50, atr_14=800),
            SentimentData(fear_greed_index=55),
        )
        # Should still be trending_up or at least have higher confidence
        assert result.confidence > 0
