"""Tests for ValidationPipeline — CR-040 Phase 3."""

import sys
from unittest.mock import MagicMock

_STUB_MODULES = [
    "ccxt", "ccxt.async_support", "aiohttp", "celery", "redis",
    "sqlalchemy", "sqlalchemy.ext", "sqlalchemy.ext.asyncio",
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

import numpy as np
import pytest

from app.services.backtesting_engine import BacktestConfig
from app.services.validation_pipeline import (
    ValidationPipeline,
    ValidationResult,
    ValidationThresholds,
    StageStatus,
)
from strategies.example_strategy import SimpleMAStrategy


def _make_oscillating_ohlcv(n: int = 500, period: int = 25) -> list[list]:
    data = []
    for i in range(n):
        base = 100 + 10 * np.sin(2 * np.pi * i / period)
        data.append([i * 3600000, base - 0.5, base + 2, base - 2, base, 1000.0])
    return data


def _make_flat_ohlcv(n: int = 500) -> list[list]:
    return [[i * 3600000, 100, 100.1, 99.9, 100, 1000.0] for i in range(n)]


class TestValidationPipeline:
    def test_insufficient_data_fails(self):
        pipeline = ValidationPipeline()
        strategy = SimpleMAStrategy("BTC/USDT", fast_period=5, slow_period=10)
        ohlcv = _make_flat_ohlcv(20)  # Too few bars
        result = pipeline.validate(strategy, ohlcv, lookback=50)
        assert result.overall_status == StageStatus.FAIL
        assert result.passed_stages < 5

    def test_flat_market_fails_stage1(self):
        """Flat market should produce no signals → fail min_trades."""
        pipeline = ValidationPipeline(
            thresholds=ValidationThresholds(min_trades=5),
            backtest_config=BacktestConfig(fee_pct=0, slippage_pct=0),
        )
        strategy = SimpleMAStrategy("BTC/USDT", fast_period=5, slow_period=10)
        ohlcv = _make_flat_ohlcv(500)
        result = pipeline.validate(strategy, ohlcv, lookback=15)
        assert result.stages[0].status == StageStatus.FAIL
        assert "Insufficient trades" in result.stages[0].reason

    def test_fail_fast_skips_remaining(self):
        pipeline = ValidationPipeline(
            thresholds=ValidationThresholds(min_trades=5),
        )
        strategy = SimpleMAStrategy("BTC/USDT", fast_period=5, slow_period=10)
        ohlcv = _make_flat_ohlcv(500)
        result = pipeline.validate(strategy, ohlcv, lookback=15)
        # Stage 1 fails → stages 2-5 should be NOT_RUN
        not_run = [s for s in result.stages if s.status == StageStatus.NOT_RUN]
        assert len(not_run) >= 3  # At least stages 2,3,4,5 skipped

    def test_all_stages_have_results(self):
        pipeline = ValidationPipeline(
            thresholds=ValidationThresholds(min_trades=1, min_win_rate=0.0, max_drawdown_pct=100, min_profit_factor=0.0, min_consistency=0.0, max_ruin_probability=1.0, min_profitable_probability=0.0, max_dd_95th_pct=100),
            backtest_config=BacktestConfig(fee_pct=0, slippage_pct=0),
            mc_simulations=50,
            wf_windows=3,
        )
        strategy = SimpleMAStrategy("BTC/USDT", fast_period=5, slow_period=10)
        ohlcv = _make_oscillating_ohlcv(600, period=25)
        result = pipeline.validate(strategy, ohlcv, lookback=15)
        assert len(result.stages) == 5
        assert result.total_stages == 5

    def test_lenient_thresholds_pass(self):
        """With very lenient thresholds, oscillating data should pass all stages."""
        pipeline = ValidationPipeline(
            thresholds=ValidationThresholds(
                min_trades=1, min_win_rate=0.0, max_drawdown_pct=100,
                min_profit_factor=0.0, min_consistency=0.0, min_efficiency_ratio=0.0,
                max_ruin_probability=1.0, min_profitable_probability=0.0,
                max_dd_95th_pct=100,
            ),
            backtest_config=BacktestConfig(fee_pct=0, slippage_pct=0),
            mc_simulations=50,
            wf_windows=3,
        )
        strategy = SimpleMAStrategy("BTC/USDT", fast_period=5, slow_period=10)
        ohlcv = _make_oscillating_ohlcv(800, period=25)
        result = pipeline.validate(strategy, ohlcv, lookback=15)
        assert result.passed_stages == 5
        assert result.overall_status == StageStatus.PASS

    def test_strategy_name_propagated(self):
        pipeline = ValidationPipeline()
        strategy = SimpleMAStrategy("BTC/USDT", fast_period=7, slow_period=14)
        ohlcv = _make_flat_ohlcv(200)
        result = pipeline.validate(strategy, ohlcv, lookback=20)
        assert result.strategy_name == "SMA_7_14"

    def test_strict_thresholds_fail(self):
        """Strict thresholds should make it harder to pass."""
        pipeline = ValidationPipeline(
            thresholds=ValidationThresholds(
                min_trades=50, min_win_rate=0.7, max_drawdown_pct=5,
                min_profit_factor=3.0,
            ),
            backtest_config=BacktestConfig(fee_pct=0, slippage_pct=0),
        )
        strategy = SimpleMAStrategy("BTC/USDT", fast_period=5, slow_period=10)
        ohlcv = _make_oscillating_ohlcv(500)
        result = pipeline.validate(strategy, ohlcv, lookback=15)
        assert result.overall_status == StageStatus.FAIL

    def test_stage_metrics_populated(self):
        pipeline = ValidationPipeline(
            thresholds=ValidationThresholds(min_trades=1),
            backtest_config=BacktestConfig(fee_pct=0, slippage_pct=0),
        )
        strategy = SimpleMAStrategy("BTC/USDT", fast_period=5, slow_period=10)
        ohlcv = _make_oscillating_ohlcv(500, period=25)
        result = pipeline.validate(strategy, ohlcv, lookback=15)
        for stage in result.stages:
            if stage.status != StageStatus.NOT_RUN:
                assert isinstance(stage.metrics, dict)
