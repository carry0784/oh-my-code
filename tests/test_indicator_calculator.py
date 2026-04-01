"""Tests for IndicatorCalculator — CR-038 Phase 1."""

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

# Patch DeclarativeBase so models can define __tablename__
_fake_base = type("FakeBase", (), {"__tablename__": "", "metadata": MagicMock()})
sys.modules["app.core.database"].Base = _fake_base
sys.modules["app.core.database"].engine = MagicMock()
sys.modules["app.core.database"].async_session_factory = MagicMock()

import numpy as np
import pytest

from app.schemas.market_state_schema import OHLCVBar
from app.services.indicator_calculator import IndicatorCalculator


def _make_bars(closes: list[float], volume: float = 1000.0) -> list[OHLCVBar]:
    """Generate OHLCVBars from close prices with synthetic OHLV."""
    bars = []
    for i, c in enumerate(closes):
        bars.append(OHLCVBar(
            timestamp=1000000 + i * 3600,
            open=c * 0.999,
            high=c * 1.005,
            low=c * 0.995,
            close=c,
            volume=volume,
        ))
    return bars


class TestIndicatorCalculator:
    def setup_method(self):
        self.calc = IndicatorCalculator()

    def test_empty_bars_returns_empty_indicators(self):
        result = self.calc.calculate([])
        assert result.rsi_14 is None
        assert result.macd_line is None

    def test_single_bar_returns_empty_indicators(self):
        bars = _make_bars([100.0])
        result = self.calc.calculate(bars)
        assert result.rsi_14 is None

    def test_rsi_all_gains(self):
        # Monotonically increasing prices → RSI near 100
        closes = [100 + i for i in range(20)]
        bars = _make_bars(closes)
        result = self.calc.calculate(bars)
        assert result.rsi_14 is not None
        assert result.rsi_14 > 90.0

    def test_rsi_all_losses(self):
        # Monotonically decreasing prices → RSI near 0
        closes = [120 - i for i in range(20)]
        bars = _make_bars(closes)
        result = self.calc.calculate(bars)
        assert result.rsi_14 is not None
        assert result.rsi_14 < 10.0

    def test_rsi_range(self):
        # Mixed → RSI between 0 and 100
        closes = [100 + (i % 3 - 1) * 2 for i in range(20)]
        bars = _make_bars(closes)
        result = self.calc.calculate(bars)
        assert result.rsi_14 is not None
        assert 0 <= result.rsi_14 <= 100

    def test_sma_20_calculation(self):
        closes = list(range(100, 125))  # 25 values
        bars = _make_bars(closes)
        result = self.calc.calculate(bars)
        expected_sma20 = np.mean(closes[-20:])
        assert result.sma_20 is not None
        assert abs(result.sma_20 - expected_sma20) < 0.01

    def test_sma_50_needs_50_bars(self):
        bars = _make_bars([100.0] * 30)
        result = self.calc.calculate(bars)
        assert result.sma_50 is None  # Not enough data

    def test_sma_50_with_enough_data(self):
        bars = _make_bars([100.0 + i * 0.1 for i in range(55)])
        result = self.calc.calculate(bars)
        assert result.sma_50 is not None

    def test_ema_12_calculation(self):
        closes = [100.0 + i for i in range(15)]
        bars = _make_bars(closes)
        result = self.calc.calculate(bars)
        assert result.ema_12 is not None
        # EMA should be close to recent prices
        assert abs(result.ema_12 - closes[-1]) < 10

    def test_macd_needs_35_bars(self):
        bars = _make_bars([100.0] * 30)
        result = self.calc.calculate(bars)
        assert result.macd_line is None

    def test_macd_with_enough_data(self):
        closes = [100.0 + i * 0.5 for i in range(40)]
        bars = _make_bars(closes)
        result = self.calc.calculate(bars)
        assert result.macd_line is not None
        assert result.macd_signal is not None
        assert result.macd_histogram is not None

    def test_macd_trending_up_positive(self):
        # Strong uptrend → MACD line should be positive
        closes = [100.0 + i * 2 for i in range(40)]
        bars = _make_bars(closes)
        result = self.calc.calculate(bars)
        assert result.macd_line > 0

    def test_bollinger_bands_calculation(self):
        closes = [100.0 + (i % 5 - 2) for i in range(25)]
        bars = _make_bars(closes)
        result = self.calc.calculate(bars)
        assert result.bb_upper is not None
        assert result.bb_middle is not None
        assert result.bb_lower is not None
        assert result.bb_upper > result.bb_middle > result.bb_lower

    def test_atr_calculation(self):
        closes = [100.0 + (i % 3 - 1) * 3 for i in range(20)]
        bars = _make_bars(closes)
        result = self.calc.calculate(bars)
        assert result.atr_14 is not None
        assert result.atr_14 > 0

    def test_obv_up_trend(self):
        # All closes increasing → OBV should be positive
        closes = [100.0 + i for i in range(10)]
        bars = _make_bars(closes, volume=1000.0)
        result = self.calc.calculate(bars)
        assert result.obv is not None
        assert result.obv > 0

    def test_obv_down_trend(self):
        # All closes decreasing → OBV should be negative
        closes = [110.0 - i for i in range(10)]
        bars = _make_bars(closes, volume=1000.0)
        result = self.calc.calculate(bars)
        assert result.obv is not None
        assert result.obv < 0

    def test_full_calculation_200_bars(self):
        # Full realistic dataset
        np.random.seed(42)
        base = 50000.0
        returns = np.random.normal(0.0001, 0.02, 200)
        closes = [base]
        for r in returns:
            closes.append(closes[-1] * (1 + r))
        bars = _make_bars(closes)
        result = self.calc.calculate(bars)

        # All indicators should be populated
        assert result.rsi_14 is not None
        assert result.macd_line is not None
        assert result.bb_upper is not None
        assert result.atr_14 is not None
        assert result.obv is not None
        assert result.sma_20 is not None
        assert result.sma_50 is not None
        assert result.sma_200 is not None
        assert result.ema_12 is not None
        assert result.ema_26 is not None
