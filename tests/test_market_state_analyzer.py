"""Tests for MarketStateAnalyzer — CR-039 Phase 2."""

import sys
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta

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

from app.services.market_state_analyzer import (
    MarketStateAnalyzer,
    MarketAnalysisResult,
    TrendAnalysis,
)


def _make_snapshots(
    prices: list[float],
    regimes: list[str] | None = None,
    rsis: list[float | None] | None = None,
    volumes: list[float | None] | None = None,
    macds: list[float | None] | None = None,
    obvs: list[float | None] | None = None,
) -> list[dict]:
    n = len(prices)
    regimes = regimes or ["unknown"] * n
    rsis = rsis or [None] * n
    volumes = volumes or [None] * n
    macds = macds or [None] * n
    obvs = obvs or [None] * n
    base = datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc)
    return [
        {
            "price": prices[i],
            "rsi_14": rsis[i],
            "volume_24h": volumes[i],
            "macd_histogram": macds[i],
            "obv": obvs[i],
            "regime": regimes[i],
            "snapshot_at": base + timedelta(hours=i),
        }
        for i in range(n)
    ]


class TestMarketStateAnalyzerTrends:
    def setup_method(self):
        self.analyzer = MarketStateAnalyzer()

    def test_empty_snapshots(self):
        result = self.analyzer.analyze([])
        assert result.snapshot_count == 0
        assert result.price_trend.direction == "flat"

    def test_single_snapshot(self):
        snapshots = _make_snapshots([65000])
        result = self.analyzer.analyze(snapshots)
        assert result.snapshot_count == 1

    def test_uptrend_detection(self):
        prices = [60000 + i * 500 for i in range(20)]
        snapshots = _make_snapshots(prices)
        result = self.analyzer.analyze(snapshots)
        assert result.price_trend.direction == "up"
        assert result.price_trend.slope > 0
        assert result.price_trend.r_squared > 0.9

    def test_downtrend_detection(self):
        prices = [70000 - i * 500 for i in range(20)]
        snapshots = _make_snapshots(prices)
        result = self.analyzer.analyze(snapshots)
        assert result.price_trend.direction == "down"
        assert result.price_trend.slope < 0

    def test_flat_trend(self):
        prices = [65000 + (i % 2 - 0.5) * 10 for i in range(20)]
        snapshots = _make_snapshots(prices)
        result = self.analyzer.analyze(snapshots)
        assert result.price_trend.direction == "flat"

    def test_strong_trend_classification(self):
        prices = [50000 + i * 2000 for i in range(20)]
        snapshots = _make_snapshots(prices)
        result = self.analyzer.analyze(snapshots)
        assert result.price_trend.strength == "strong"

    def test_rsi_trend(self):
        rsis = [30 + i * 2 for i in range(15)]
        prices = [65000] * 15
        snapshots = _make_snapshots(prices, rsis=rsis)
        result = self.analyzer.analyze(snapshots)
        assert result.rsi_trend.direction == "up"

    def test_volume_trend(self):
        volumes = [1e9 + i * 1e8 for i in range(15)]
        prices = [65000] * 15
        snapshots = _make_snapshots(prices, volumes=volumes)
        result = self.analyzer.analyze(snapshots)
        assert result.volume_trend.direction == "up"


class TestMarketStateAnalyzerRegimeTransitions:
    def setup_method(self):
        self.analyzer = MarketStateAnalyzer()

    def test_no_transitions(self):
        regimes = ["trending_up"] * 10
        snapshots = _make_snapshots([65000] * 10, regimes=regimes)
        result = self.analyzer.analyze(snapshots)
        assert len(result.regime_transitions) == 0
        assert result.regime_stability == 1.0

    def test_single_transition(self):
        regimes = ["trending_up"] * 5 + ["ranging"] * 5
        snapshots = _make_snapshots([65000] * 10, regimes=regimes)
        result = self.analyzer.analyze(snapshots)
        assert len(result.regime_transitions) == 1
        assert result.regime_transitions[0].from_regime == "trending_up"
        assert result.regime_transitions[0].to_regime == "ranging"

    def test_multiple_transitions(self):
        regimes = ["ranging", "trending_up", "trending_up", "high_volatility", "crisis"]
        snapshots = _make_snapshots([65000] * 5, regimes=regimes)
        result = self.analyzer.analyze(snapshots)
        assert len(result.regime_transitions) == 3

    def test_stability_calculation(self):
        regimes = ["trending_up", "ranging", "trending_up", "ranging"]
        snapshots = _make_snapshots([65000] * 4, regimes=regimes)
        result = self.analyzer.analyze(snapshots)
        # 3 transitions out of 3 intervals = 0% stability
        assert result.regime_stability == 0.0

    def test_transition_has_timestamp(self):
        regimes = ["trending_up", "crisis"]
        snapshots = _make_snapshots([65000] * 2, regimes=regimes)
        result = self.analyzer.analyze(snapshots)
        assert result.regime_transitions[0].timestamp is not None


class TestMarketStateAnalyzerDivergences:
    def setup_method(self):
        self.analyzer = MarketStateAnalyzer()

    def test_bullish_rsi_divergence(self):
        # Price down, RSI up → bullish divergence
        prices = [70000, 69000, 68000, 67000, 66000, 65000, 64000, 63000, 62000, 61000]
        rsis = [30, 32, 34, 36, 38, 40, 42, 44, 46, 48]
        snapshots = _make_snapshots(prices, rsis=rsis)
        result = self.analyzer.analyze(snapshots)
        rsi_divs = [d for d in result.divergences if d.indicator == "rsi"]
        assert len(rsi_divs) == 1
        assert rsi_divs[0].divergence_type == "bullish"

    def test_bearish_rsi_divergence(self):
        # Price up, RSI down → bearish divergence
        prices = [60000, 61000, 62000, 63000, 64000, 65000, 66000, 67000, 68000, 69000]
        rsis = [70, 68, 66, 64, 62, 60, 58, 56, 54, 52]
        snapshots = _make_snapshots(prices, rsis=rsis)
        result = self.analyzer.analyze(snapshots)
        rsi_divs = [d for d in result.divergences if d.indicator == "rsi"]
        assert len(rsi_divs) == 1
        assert rsi_divs[0].divergence_type == "bearish"

    def test_no_divergence_aligned(self):
        # Price up, RSI up → aligned, no divergence
        prices = [60000 + i * 1000 for i in range(10)]
        rsis = [40 + i * 3 for i in range(10)]
        snapshots = _make_snapshots(prices, rsis=rsis)
        result = self.analyzer.analyze(snapshots)
        rsi_divs = [d for d in result.divergences if d.indicator == "rsi"]
        assert len(rsi_divs) == 0

    def test_obv_divergence(self):
        # Price up, OBV down → bearish OBV divergence
        prices = [60000 + i * 500 for i in range(10)]
        obvs = [1e6 - i * 50000 for i in range(10)]
        snapshots = _make_snapshots(prices, obvs=obvs)
        result = self.analyzer.analyze(snapshots)
        obv_divs = [d for d in result.divergences if d.indicator == "obv"]
        assert len(obv_divs) == 1
        assert obv_divs[0].divergence_type == "bearish"

    def test_insufficient_data_no_divergence(self):
        snapshots = _make_snapshots([65000, 66000])
        result = self.analyzer.analyze(snapshots)
        assert len(result.divergences) == 0

    def test_divergence_strength_range(self):
        prices = [70000 - i * 1000 for i in range(10)]
        rsis = [30 + i * 5 for i in range(10)]
        snapshots = _make_snapshots(prices, rsis=rsis)
        result = self.analyzer.analyze(snapshots)
        for d in result.divergences:
            assert 0 <= d.strength <= 1.0
