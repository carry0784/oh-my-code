"""Tests for MonteCarloSimulator — CR-040 Phase 3."""

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

from app.services.monte_carlo_simulator import MonteCarloSimulator, MonteCarloResult
from app.services.performance_metrics import TradeRecord


def _profitable_trades(n: int = 20) -> list[TradeRecord]:
    return [
        TradeRecord(entry_price=100, exit_price=105, side="long", fee_pct=0.001) for _ in range(n)
    ]


def _losing_trades(n: int = 20) -> list[TradeRecord]:
    return [
        TradeRecord(entry_price=100, exit_price=90, side="long", fee_pct=0.001) for _ in range(n)
    ]


def _mixed_trades() -> list[TradeRecord]:
    return [
        TradeRecord(entry_price=100, exit_price=108, side="long", fee_pct=0.001),
        TradeRecord(entry_price=100, exit_price=103, side="long", fee_pct=0.001),
        TradeRecord(entry_price=100, exit_price=95, side="long", fee_pct=0.001),
        TradeRecord(entry_price=100, exit_price=110, side="long", fee_pct=0.001),
        TradeRecord(entry_price=100, exit_price=92, side="long", fee_pct=0.001),
        TradeRecord(entry_price=100, exit_price=106, side="long", fee_pct=0.001),
        TradeRecord(entry_price=100, exit_price=98, side="long", fee_pct=0.001),
        TradeRecord(entry_price=100, exit_price=104, side="long", fee_pct=0.001),
        TradeRecord(entry_price=100, exit_price=96, side="long", fee_pct=0.001),
        TradeRecord(entry_price=100, exit_price=107, side="long", fee_pct=0.001),
    ]


class TestMonteCarloSimulator:
    def test_insufficient_trades(self):
        sim = MonteCarloSimulator(n_simulations=100, seed=42)
        result = sim.simulate([])
        assert result.n_trades == 0
        assert result.return_mean == 0.0

    def test_two_trades_returns_empty(self):
        trades = _profitable_trades(2)
        sim = MonteCarloSimulator(n_simulations=100, seed=42)
        result = sim.simulate(trades)
        assert result.n_trades == 2
        assert result.return_mean == 0.0

    def test_profitable_trades_positive_return(self):
        trades = _profitable_trades(20)
        sim = MonteCarloSimulator(n_simulations=500, seed=42)
        result = sim.simulate(trades)
        assert result.return_mean > 0
        assert result.return_median > 0
        assert result.profitable_probability > 0.9

    def test_losing_trades_negative_return(self):
        trades = _losing_trades(20)
        sim = MonteCarloSimulator(n_simulations=500, seed=42)
        result = sim.simulate(trades)
        assert result.return_mean < 0
        assert result.profitable_probability < 0.1

    def test_percentile_ordering(self):
        trades = _mixed_trades()
        sim = MonteCarloSimulator(n_simulations=1000, seed=42)
        result = sim.simulate(trades)
        assert result.return_5th <= result.return_25th
        assert result.return_25th <= result.return_median
        assert result.return_median <= result.return_75th
        assert result.return_75th <= result.return_95th

    def test_drawdown_positive(self):
        trades = _mixed_trades()
        sim = MonteCarloSimulator(n_simulations=500, seed=42)
        result = sim.simulate(trades)
        assert result.max_dd_mean >= 0
        assert result.max_dd_95th >= result.max_dd_mean

    def test_ruin_probability_range(self):
        trades = _mixed_trades()
        sim = MonteCarloSimulator(n_simulations=500, seed=42)
        result = sim.simulate(trades)
        assert 0 <= result.ruin_probability <= 1.0

    def test_seed_reproducibility(self):
        trades = _mixed_trades()
        r1 = MonteCarloSimulator(n_simulations=100, seed=123).simulate(trades)
        r2 = MonteCarloSimulator(n_simulations=100, seed=123).simulate(trades)
        assert r1.return_mean == r2.return_mean
        assert r1.max_dd_95th == r2.max_dd_95th

    def test_different_seeds_different_results(self):
        trades = _mixed_trades()
        r1 = MonteCarloSimulator(n_simulations=100, seed=1).simulate(trades)
        r2 = MonteCarloSimulator(n_simulations=100, seed=999).simulate(trades)
        # With enough simulations, means should be similar but not identical
        assert r1.return_mean != r2.return_mean
