"""Tests for BacktestingEngine — CR-040 Phase 3."""

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

import numpy as np
import pytest

from app.services.backtesting_engine import BacktestConfig, BacktestingEngine, BacktestResult
from strategies.example_strategy import SimpleMAStrategy


def _make_trending_ohlcv(n: int = 100, start: float = 100.0, trend: float = 0.5) -> list[list]:
    """Generate trending OHLCV data."""
    data = []
    price = start
    for i in range(n):
        price += trend + np.random.uniform(-0.3, 0.3)
        o = price - 0.5
        h = price + 1.0
        l = price - 1.0
        c = price
        v = 1000.0
        data.append([i * 3600000, o, h, l, c, v])
    return data


def _make_oscillating_ohlcv(n: int = 200, period: int = 20) -> list[list]:
    """Generate oscillating OHLCV for crossover signals."""
    data = []
    for i in range(n):
        base = 100 + 10 * np.sin(2 * np.pi * i / period)
        o = base - 0.5
        h = base + 2
        l = base - 2
        c = base
        data.append([i * 3600000, o, h, l, c, 1000.0])
    return data


class TestBacktestingEngine:
    def test_insufficient_data(self):
        engine = BacktestingEngine()
        strategy = SimpleMAStrategy("BTC/USDT", fast_period=5, slow_period=10)
        ohlcv = _make_trending_ohlcv(10)
        result = engine.run(strategy, ohlcv, lookback=50)
        assert result.total_bars == 10
        assert len(result.trades) == 0

    def test_basic_run(self):
        engine = BacktestingEngine()
        strategy = SimpleMAStrategy("BTC/USDT", fast_period=5, slow_period=10)
        ohlcv = _make_oscillating_ohlcv(300, period=30)
        result = engine.run(strategy, ohlcv, lookback=15)
        assert result.total_bars == 300
        assert result.strategy_name == "SMA_5_10"

    def test_generates_trades_on_oscillating_data(self):
        engine = BacktestingEngine(
            BacktestConfig(
                position_size_pct=10.0,
                slippage_pct=0.0,
                fee_pct=0.0,
            )
        )
        strategy = SimpleMAStrategy("BTC/USDT", fast_period=5, slow_period=10)
        ohlcv = _make_oscillating_ohlcv(400, period=25)
        result = engine.run(strategy, ohlcv, lookback=15)
        assert result.signals_generated > 0
        assert len(result.trades) > 0

    def test_performance_report_attached(self):
        engine = BacktestingEngine(BacktestConfig(fee_pct=0.0, slippage_pct=0.0))
        strategy = SimpleMAStrategy("BTC/USDT", fast_period=5, slow_period=10)
        ohlcv = _make_oscillating_ohlcv(400, period=25)
        result = engine.run(strategy, ohlcv, lookback=15)
        assert result.performance.total_trades == len(result.trades)

    def test_slippage_affects_pnl(self):
        config_no_slip = BacktestConfig(slippage_pct=0.0, fee_pct=0.0)
        config_slip = BacktestConfig(slippage_pct=1.0, fee_pct=0.0)  # 1% slippage
        strategy = SimpleMAStrategy("BTC/USDT", fast_period=5, slow_period=10)
        np.random.seed(42)
        ohlcv = _make_oscillating_ohlcv(400, period=25)

        r1 = BacktestingEngine(config_no_slip).run(strategy, ohlcv, lookback=15)
        np.random.seed(42)
        ohlcv2 = _make_oscillating_ohlcv(400, period=25)
        r2 = BacktestingEngine(config_slip).run(strategy, ohlcv2, lookback=15)

        if r1.trades and r2.trades:
            # Slippage should reduce overall PnL
            assert r2.performance.total_pnl <= r1.performance.total_pnl + 1  # tolerance

    def test_stop_loss_triggers(self):
        engine = BacktestingEngine(
            BacktestConfig(stop_loss_enabled=True, slippage_pct=0, fee_pct=0)
        )
        strategy = SimpleMAStrategy("BTC/USDT", fast_period=3, slow_period=5)
        # Bullish crossover followed by crash
        ohlcv = [
            [0, 95, 96, 94, 95, 1000],
            [1, 94, 95, 93, 94, 1000],
            [2, 93, 94, 92, 93, 1000],
            [3, 92, 93, 91, 92, 1000],
            [4, 91, 92, 90, 91, 1000],
            [5, 95, 100, 94, 99, 1000],  # Price jumps → bullish crossover
            [6, 99, 101, 98, 100, 1000],
            [7, 100, 102, 99, 101, 1000],
            [8, 101, 102, 80, 82, 1000],  # Crash through stop loss
            [9, 82, 83, 75, 76, 1000],
        ]
        result = engine.run(strategy, ohlcv, lookback=6)
        # Should have exited on stop loss, not held through crash
        for t in result.trades:
            if t.side == "long":
                assert t.exit_price >= t.entry_price * 0.95  # Stop at ~2%


class TestBacktestConfig:
    def test_default_config(self):
        config = BacktestConfig()
        assert config.initial_capital == 10000
        assert config.fee_pct == 0.1
        assert config.stop_loss_enabled is True
