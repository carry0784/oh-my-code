"""Tests for FitnessFunction — CR-041 Phase 4."""

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

from app.services.fitness_function import FitnessFunction, FitnessBreakdown
from app.services.performance_metrics import PerformanceReport


def _make_report(**kwargs) -> PerformanceReport:
    """Build a PerformanceReport with sane defaults, overriding with kwargs."""
    defaults = dict(
        total_trades=20,
        winning_trades=12,
        losing_trades=8,
        win_rate=0.6,
        total_pnl=500.0,
        profit_factor=1.8,
        max_drawdown_pct=10.0,
        max_consecutive_losses=3,
        sharpe_ratio=1.5,
        total_return_pct=5.0,
    )
    defaults.update(kwargs)
    return PerformanceReport(**defaults)


def test_fitness_insufficient_trades_penalty():
    fn = FitnessFunction(min_trades=10)
    perf = _make_report(total_trades=5)
    result = fn.evaluate(perf)
    assert result.total == 0.0
    assert result.penalties == 0.5
    assert result.details["penalty"] == "insufficient_trades"


def test_fitness_positive_sharpe_return_score():
    fn = FitnessFunction(target_sharpe=2.0)
    # Sharpe = 1.0 → return_score = 0.5
    perf = _make_report(sharpe_ratio=1.0)
    result = fn.evaluate(perf)
    assert abs(result.return_score - 0.5) < 0.001


def test_fitness_negative_sharpe_partial_score():
    fn = FitnessFunction()
    # Negative Sharpe but positive return → small partial score
    perf = _make_report(sharpe_ratio=-0.5, total_return_pct=10.0)
    result = fn.evaluate(perf)
    assert 0.0 < result.return_score <= 0.3


def test_fitness_zero_drawdown_perfect_stability():
    fn = FitnessFunction()
    perf = _make_report(max_drawdown_pct=0.0)
    result = fn.evaluate(perf)
    assert result.stability_score == 1.0


def test_fitness_max_drawdown_zero_stability():
    fn = FitnessFunction(max_acceptable_drawdown=30.0)
    perf = _make_report(max_drawdown_pct=30.0)
    result = fn.evaluate(perf)
    assert result.stability_score == 0.0


def test_fitness_consistency_score_components():
    fn = FitnessFunction(target_win_rate=0.55, target_profit_factor=1.5)
    # win_rate = 0.55 (at target), profit_factor = 1.5 (at target) → score = 1.0
    perf = _make_report(win_rate=0.55, profit_factor=1.5)
    result = fn.evaluate(perf)
    assert abs(result.consistency_score - 1.0) < 0.001


def test_fitness_live_match_no_live_data_neutral():
    fn = FitnessFunction()
    perf = _make_report()
    result = fn.evaluate(perf, live_performance=None)
    assert result.live_match_score == 0.5


def test_fitness_live_match_with_live_data():
    fn = FitnessFunction()
    backtest = _make_report(total_return_pct=5.0, win_rate=0.6)
    live = _make_report(total_trades=10, total_return_pct=3.0, win_rate=0.58)
    result = fn.evaluate(backtest, live_performance=live)
    # Both positive returns → direction match; similar win rates → high similarity
    assert result.live_match_score > 0.5


def test_fitness_penalty_excessive_losses():
    fn = FitnessFunction(min_trades=10)
    perf = _make_report(max_consecutive_losses=12, max_drawdown_pct=5.0)
    result = fn.evaluate(perf)
    # max_consecutive_losses > 10 triggers penalty
    assert result.penalties >= 0.1


def test_fitness_total_weighted_sum():
    fn = FitnessFunction(
        target_sharpe=2.0,
        max_acceptable_drawdown=30.0,
        target_win_rate=0.55,
        target_profit_factor=1.5,
    )
    # Construct a report that should yield a high fitness
    perf = _make_report(
        total_trades=30,
        sharpe_ratio=2.0,  # return_score = 1.0
        max_drawdown_pct=0.0,  # stability_score = 1.0
        win_rate=0.55,  # wr_score = 1.0
        profit_factor=1.5,  # pf_score = 1.0 → consistency_score = 1.0
        max_consecutive_losses=2,
    )
    result = fn.evaluate(perf)
    # Expected raw: 1.0*0.4 + 1.0*0.3 + 1.0*0.2 + 0.5*0.1 = 0.95 (live_match neutral)
    assert result.total > 0.85
    assert 0.0 <= result.total <= 1.0
