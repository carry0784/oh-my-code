"""CR-048 Follow-Up 2A P1: Adapter layer tests.

Tests MarketStateAdapter, BacktestReadinessStub, and ADX indicator.
No FROZEN file dependencies. CI-safe (no ORM mapper initialization issues).
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import numpy as np
import pytest

from app.services.data_provider import BacktestReadiness, DataQuality, MarketDataSnapshot
from app.services.adapters.backtest_readiness_stub import BacktestReadinessStub
from app.services.indicator_calculator import IndicatorCalculator
from app.schemas.market_state_schema import OHLCVBar


# ── BacktestReadinessStub tests ──────────────────────────────────


class TestBacktestReadinessStub:
    def test_sol_usdt_returns_sealed_values(self):
        stub = BacktestReadinessStub()
        result = stub.get_readiness("SOL/USDT")
        assert result.symbol == "SOL/USDT"
        assert result.available_bars == 1500
        assert result.sharpe_ratio == 1.0
        assert result.missing_data_pct == 1.0
        assert result.quality == DataQuality.HIGH

    def test_btc_usdt_returns_sealed_values(self):
        stub = BacktestReadinessStub()
        result = stub.get_readiness("BTC/USDT")
        assert result.symbol == "BTC/USDT"
        assert result.available_bars == 2000
        assert result.sharpe_ratio == 1.2
        assert result.missing_data_pct == 0.5
        assert result.quality == DataQuality.HIGH

    def test_unknown_symbol_returns_unavailable(self):
        stub = BacktestReadinessStub()
        result = stub.get_readiness("ETH/USDT")
        assert result.symbol == "ETH/USDT"
        assert result.quality == DataQuality.UNAVAILABLE
        assert result.available_bars is None

    def test_empty_string_returns_unavailable(self):
        stub = BacktestReadinessStub()
        result = stub.get_readiness("")
        assert result.quality == DataQuality.UNAVAILABLE

    def test_supported_symbols(self):
        stub = BacktestReadinessStub()
        symbols = stub.get_supported_symbols()
        assert "SOL/USDT" in symbols
        assert "BTC/USDT" in symbols
        assert len(symbols) == 2

    def test_stub_version_exists(self):
        stub = BacktestReadinessStub()
        assert stub.STUB_VERSION == "cr046-sealed-v1"

    def test_deterministic_output(self):
        """Same input always produces same output."""
        stub = BacktestReadinessStub()
        r1 = stub.get_readiness("SOL/USDT")
        r2 = stub.get_readiness("SOL/USDT")
        assert r1 == r2

    def test_immutable_output(self):
        """Output is frozen dataclass — cannot be modified."""
        stub = BacktestReadinessStub()
        result = stub.get_readiness("SOL/USDT")
        with pytest.raises(AttributeError):
            result.available_bars = 9999


# ── IndicatorCalculator ADX tests ────────────────────────────────


def _make_trending_bars(n: int = 50) -> list[OHLCVBar]:
    """Generate synthetic bars with an upward trend (ADX should be > 0)."""
    bars = []
    base = 100.0
    for i in range(n):
        price = base + i * 0.5  # uptrend
        bars.append(
            OHLCVBar(
                timestamp=1000000 + i * 60000,
                open=price,
                high=price + 2.0,
                low=price - 1.0,
                close=price + 1.0,
                volume=1000.0,
            )
        )
    return bars


def _make_flat_bars(n: int = 50) -> list[OHLCVBar]:
    """Generate synthetic flat bars (ADX should be low)."""
    bars = []
    for i in range(n):
        bars.append(
            OHLCVBar(
                timestamp=1000000 + i * 60000,
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.0,
                volume=1000.0,
            )
        )
    return bars


class TestADXCalculation:
    def test_adx_calculated_with_enough_bars(self):
        """ADX is computed when >= 28 bars."""
        calc = IndicatorCalculator()
        bars = _make_trending_bars(50)
        result = calc.calculate(bars)
        assert result.adx_14 is not None
        assert isinstance(result.adx_14, float)

    def test_adx_none_with_insufficient_bars(self):
        """ADX is None when < 28 bars."""
        calc = IndicatorCalculator()
        bars = _make_trending_bars(20)
        result = calc.calculate(bars)
        assert result.adx_14 is None

    def test_adx_is_positive(self):
        """ADX should always be non-negative."""
        calc = IndicatorCalculator()
        bars = _make_trending_bars(100)
        result = calc.calculate(bars)
        assert result.adx_14 >= 0

    def test_adx_range(self):
        """ADX should be in [0, 100]."""
        calc = IndicatorCalculator()
        bars = _make_trending_bars(100)
        result = calc.calculate(bars)
        assert 0 <= result.adx_14 <= 100

    def test_adx_trending_higher_than_flat(self):
        """Trending market should have higher ADX than flat market."""
        calc = IndicatorCalculator()
        trending = calc.calculate(_make_trending_bars(100))
        flat = calc.calculate(_make_flat_bars(100))
        assert trending.adx_14 is not None
        assert flat.adx_14 is not None
        assert trending.adx_14 > flat.adx_14

    def test_adx_deterministic(self):
        """Same input always produces same ADX."""
        calc = IndicatorCalculator()
        bars = _make_trending_bars(60)
        r1 = calc.calculate(bars)
        r2 = calc.calculate(bars)
        assert r1.adx_14 == r2.adx_14

    def test_adx_existing_indicators_preserved(self):
        """Adding ADX doesn't break existing indicators."""
        calc = IndicatorCalculator()
        bars = _make_trending_bars(200)
        result = calc.calculate(bars)
        # Existing indicators still computed
        assert result.rsi_14 is not None
        assert result.atr_14 is not None
        assert result.sma_200 is not None
        assert result.adx_14 is not None


# ── MarketStateAdapter unit tests (no DB) ────────────────────────


class TestMarketStateAdapterFreshness:
    """Test freshness policy without DB."""

    def test_freshness_policy_constants(self):
        from app.services.adapters.market_state_adapter import MarketStateAdapter

        adapter = MarketStateAdapter()
        assert adapter.FRESHNESS_HIGH_SECONDS == 3600
        assert adapter.FRESHNESS_STALE_SECONDS == 14400

    def test_freshness_high(self):
        from app.services.adapters.market_state_adapter import MarketStateAdapter

        adapter = MarketStateAdapter()
        now = datetime(2026, 4, 6, 12, 0, 0, tzinfo=timezone.utc)
        ts = now - timedelta(minutes=30)
        quality = adapter._determine_quality(ts, now)
        assert quality == DataQuality.HIGH

    def test_freshness_stale(self):
        from app.services.adapters.market_state_adapter import MarketStateAdapter

        adapter = MarketStateAdapter()
        now = datetime(2026, 4, 6, 12, 0, 0, tzinfo=timezone.utc)
        ts = now - timedelta(hours=2)
        quality = adapter._determine_quality(ts, now)
        assert quality == DataQuality.STALE

    def test_freshness_unavailable(self):
        from app.services.adapters.market_state_adapter import MarketStateAdapter

        adapter = MarketStateAdapter()
        now = datetime(2026, 4, 6, 12, 0, 0, tzinfo=timezone.utc)
        ts = now - timedelta(hours=5)
        quality = adapter._determine_quality(ts, now)
        assert quality == DataQuality.UNAVAILABLE

    def test_freshness_none_timestamp(self):
        from app.services.adapters.market_state_adapter import MarketStateAdapter

        adapter = MarketStateAdapter()
        now = datetime(2026, 4, 6, 12, 0, 0, tzinfo=timezone.utc)
        quality = adapter._determine_quality(None, now)
        assert quality == DataQuality.UNAVAILABLE

    def test_freshness_naive_timestamp_treated_as_utc(self):
        from app.services.adapters.market_state_adapter import MarketStateAdapter

        adapter = MarketStateAdapter()
        now = datetime(2026, 4, 6, 12, 0, 0, tzinfo=timezone.utc)
        ts = datetime(2026, 4, 6, 11, 50, 0)  # naive, 10 min ago
        quality = adapter._determine_quality(ts, now)
        assert quality == DataQuality.HIGH

    def test_freshness_boundary_exact_1h(self):
        """Exactly 1 hour is still HIGH (<=)."""
        from app.services.adapters.market_state_adapter import MarketStateAdapter

        adapter = MarketStateAdapter()
        now = datetime(2026, 4, 6, 12, 0, 0, tzinfo=timezone.utc)
        ts = now - timedelta(hours=1)
        quality = adapter._determine_quality(ts, now)
        assert quality == DataQuality.HIGH

    def test_freshness_boundary_just_over_1h(self):
        """1 hour + 1 second is STALE."""
        from app.services.adapters.market_state_adapter import MarketStateAdapter

        adapter = MarketStateAdapter()
        now = datetime(2026, 4, 6, 12, 0, 0, tzinfo=timezone.utc)
        ts = now - timedelta(hours=1, seconds=1)
        quality = adapter._determine_quality(ts, now)
        assert quality == DataQuality.STALE
