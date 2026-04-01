"""Tests for StrategyRunner — CR-041 Phase 4."""

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
from app.services.strategy_genome import GenomeFactory, StrategyGenome
from app.services.strategy_runner import RunnerConfig, RunnerResult, StrategyRunner
from app.services.validation_pipeline import ValidationThresholds
from strategies.example_strategy import SimpleMAStrategy
from strategies.rsi_strategy import RSICrossStrategy


def _make_oscillating_ohlcv(n: int = 150, period: int = 20) -> list[list]:
    """Generate oscillating OHLCV with enough bars for lookback + crossover signals."""
    data = []
    for i in range(n):
        base = 100.0 + 10.0 * np.sin(2 * np.pi * i / period)
        o = base - 0.5
        h = base + 2.0
        l = base - 2.0
        c = base
        data.append([i * 3600000, o, h, l, c, 1000.0])
    return data


def _fast_config() -> RunnerConfig:
    """Minimal config to keep tests fast."""
    return RunnerConfig(
        population_size=6,
        max_generations=2,
        tournament_seed=42,
        backtest_config=BacktestConfig(fee_pct=0.0, slippage_pct=0.0),
        mc_simulations=10,
        wf_windows=2,
    )


def test_runner_config_defaults():
    config = RunnerConfig()
    assert config.population_size == 20
    assert config.max_generations == 10
    assert config.mc_simulations == 200
    assert config.wf_windows == 3
    assert config.tournament_seed == 42


def test_runner_genome_to_strategy_valid():
    runner = StrategyRunner(_fast_config())
    factory = GenomeFactory(seed=0)
    genome = factory.create_default()
    strategy = runner._genome_to_strategy(genome)
    assert isinstance(strategy, SimpleMAStrategy)
    assert strategy.fast_period < strategy.slow_period


def test_runner_genome_to_strategy_fast_gte_slow():
    runner = StrategyRunner(_fast_config())
    factory = GenomeFactory(seed=0)
    genome = factory.create_default()
    # Force invalid condition: fast >= slow
    genome.indicator_genes["fast_period"].value = 30.0
    genome.indicator_genes["slow_period"].value = 15.0
    strategy = runner._genome_to_strategy(genome)
    # Runner must correct the constraint
    assert strategy.fast_period < strategy.slow_period


def test_runner_evolution_returns_result():
    ohlcv = _make_oscillating_ohlcv(150, period=20)
    runner = StrategyRunner(_fast_config())
    result = runner.run_evolution(ohlcv, lookback=15)
    assert isinstance(result, RunnerResult)
    assert result.generations_run == 2


def test_runner_evolution_history_length():
    ohlcv = _make_oscillating_ohlcv(150, period=20)
    runner = StrategyRunner(_fast_config())
    result = runner.run_evolution(ohlcv, lookback=15)
    assert len(result.evolution_history) == 2
    for i, record in enumerate(result.evolution_history):
        assert record.generation == i


def test_runner_evolution_best_genome_set():
    ohlcv = _make_oscillating_ohlcv(150, period=20)
    runner = StrategyRunner(_fast_config())
    result = runner.run_evolution(ohlcv, lookback=15)
    assert result.best_genome is not None
    assert isinstance(result.best_genome, StrategyGenome)
    assert result.best_fitness >= 0.0


def test_runner_evolution_final_population():
    config = _fast_config()
    ohlcv = _make_oscillating_ohlcv(150, period=20)
    runner = StrategyRunner(config)
    result = runner.run_evolution(ohlcv, lookback=15)
    assert len(result.final_population) == config.population_size


def test_runner_evolution_validation_runs():
    ohlcv = _make_oscillating_ohlcv(150, period=20)
    runner = StrategyRunner(_fast_config())
    result = runner.run_evolution(ohlcv, lookback=15)
    # Validation pipeline must have been called and returned a result
    assert result.validation_result is not None
    assert result.validation_result.total_stages == 5


# ── CR-045: RSI strategy branch tests ──

def test_runner_genome_to_strategy_sma_default():
    """CR-045: strategy_type=0 returns SimpleMAStrategy."""
    runner = StrategyRunner(_fast_config())
    factory = GenomeFactory(seed=0)
    genome = factory.create_default()
    genome.indicator_genes["strategy_type"].value = 0.0
    strategy = runner._genome_to_strategy(genome)
    assert isinstance(strategy, SimpleMAStrategy)


def test_runner_genome_to_strategy_rsi_branch():
    """CR-045: strategy_type=1 returns RSICrossStrategy."""
    runner = StrategyRunner(_fast_config())
    factory = GenomeFactory(seed=0)
    genome = factory.create_default()
    genome.indicator_genes["strategy_type"].value = 1.0
    strategy = runner._genome_to_strategy(genome)
    assert isinstance(strategy, RSICrossStrategy)
    assert strategy.rsi_period == 14
    assert strategy.rsi_overbought == 70.0
    assert strategy.rsi_oversold == 30.0


def test_runner_genome_to_strategy_rsi_custom_params():
    """CR-045: RSI strategy picks up genome RSI params."""
    runner = StrategyRunner(_fast_config())
    factory = GenomeFactory(seed=0)
    genome = factory.create_default()
    genome.indicator_genes["strategy_type"].value = 1.0
    genome.indicator_genes["rsi_period"].value = 21.0
    genome.indicator_genes["rsi_overbought"].value = 80.0
    genome.indicator_genes["rsi_oversold"].value = 20.0
    strategy = runner._genome_to_strategy(genome)
    assert isinstance(strategy, RSICrossStrategy)
    assert strategy.rsi_period == 21
    assert strategy.rsi_overbought == 80.0
    assert strategy.rsi_oversold == 20.0


def test_runner_genome_to_strategy_rsi_overbought_lte_oversold():
    """CR-045: overbought <= oversold is corrected."""
    runner = StrategyRunner(_fast_config())
    factory = GenomeFactory(seed=0)
    genome = factory.create_default()
    genome.indicator_genes["strategy_type"].value = 1.0
    genome.indicator_genes["rsi_overbought"].value = 25.0
    genome.indicator_genes["rsi_oversold"].value = 30.0
    strategy = runner._genome_to_strategy(genome)
    assert isinstance(strategy, RSICrossStrategy)
    assert strategy.rsi_overbought > strategy.rsi_oversold


def test_rsi_strategy_analyze_returns_signal():
    """CR-045: RSICrossStrategy produces signals on oscillating data."""
    # Create data that oscillates enough to trigger RSI crossovers
    data = []
    for i in range(200):
        # Alternate between up and down moves to create RSI oscillation
        if (i // 10) % 2 == 0:
            base = 100.0 + (i % 10) * 2
        else:
            base = 120.0 - (i % 10) * 2
        data.append([i * 300000, base - 1, base + 1, base - 2, base, 1000.0])

    strategy = RSICrossStrategy("BTC/USDT", rsi_period=7, rsi_overbought=65, rsi_oversold=35)
    signals = []
    for end in range(20, len(data)):
        result = strategy.analyze(data[:end])
        if result is not None:
            signals.append(result)

    # RSI strategy should generate at least some signals on oscillating data
    assert len(signals) > 0, "RSI strategy should generate signals on oscillating data"


def test_rsi_strategy_name_format():
    """CR-045: RSI strategy name contains period and thresholds."""
    strategy = RSICrossStrategy("BTC/USDT", rsi_period=14, rsi_overbought=70, rsi_oversold=30)
    assert strategy.name == "RSI_14_70_30"
