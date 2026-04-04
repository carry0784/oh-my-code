"""Tests for AdvancedStrategyRunner — CR-042 Phase 5."""

import sys
from unittest.mock import MagicMock, patch

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

from app.services.advanced_runner import (
    AdvancedRunnerConfig,
    AdvancedRunnerResult,
    AdvancedStrategyRunner,
)
from app.services.backtesting_engine import BacktestResult
from app.services.evolution_state import EvolutionCheckpoint
from app.services.performance_metrics import PerformanceReport
from app.services.strategy_genome import GenomeFactory
from app.services.strategy_runner import EvolutionRecord
from app.services.strategy_tournament import TournamentResult

# Small deterministic OHLCV dataset
_OHLCV = [
    [1_000_000 + i * 60_000, 100 + i * 0.1, 101 + i * 0.1, 99 + i * 0.1, 100.5 + i * 0.1, 1000]
    for i in range(100)
]

_SMALL_CFG = AdvancedRunnerConfig(
    n_islands=2,
    population_per_island=5,
    max_generations=2,
    seed=42,
    migration_interval=10,  # far enough that migration never fires in 2 gens
    adaptive_mutation=True,
    persist_state=False,  # default off; individual tests opt-in
    registry_max_entries=20,
)


def _patched_runner(cfg=None):
    """Return an AdvancedStrategyRunner whose heavy internals are stubbed."""
    runner = AdvancedStrategyRunner(cfg or _SMALL_CFG)

    factory = GenomeFactory(seed=42)
    survivors = factory.create_population(5)

    mock_perf = MagicMock(spec=PerformanceReport)
    mock_perf.sharpe_ratio = 1.0
    mock_bt = MagicMock(spec=BacktestResult)
    mock_bt.performance = mock_perf

    mock_t_result = MagicMock(spec=TournamentResult)
    mock_t_result.survivors = survivors
    mock_t_result.best_fitness = 0.5
    mock_t_result.avg_fitness = 0.4

    from app.services.backtesting_engine import BacktestingEngine
    from app.services.strategy_tournament import StrategyTournament

    runner._bt_patch = patch.object(BacktestingEngine, "run", return_value=mock_bt)
    runner._tour_patch = patch.object(
        StrategyTournament, "run_tournament", return_value=mock_t_result
    )
    runner._strat_patch = patch(
        "app.services.island_model.IslandModel._genome_to_strategy",
        return_value=MagicMock(),
    )
    return runner


def test_advanced_config_defaults():
    """AdvancedRunnerConfig carries expected default field values."""
    cfg = AdvancedRunnerConfig()
    assert cfg.n_islands == 5
    assert cfg.population_per_island == 10
    assert cfg.max_generations == 20
    assert cfg.migration_interval == 5
    assert cfg.migration_topology == "ring"
    assert cfg.seed == 42
    assert cfg.adaptive_mutation is True
    assert cfg.persist_state is True
    assert cfg.registry_max_entries == 50


def test_advanced_runner_creates_islands():
    """AdvancedStrategyRunner initialises the correct number of islands."""
    runner = AdvancedStrategyRunner(_SMALL_CFG)
    assert len(runner.island_model.islands) == _SMALL_CFG.n_islands
    for island in runner.island_model.islands:
        assert len(island.population) == _SMALL_CFG.population_per_island


def test_advanced_evolution_returns_result():
    """run_evolution() returns an AdvancedRunnerResult with the expected fields."""
    runner = _patched_runner()

    with runner._bt_patch, runner._tour_patch, runner._strat_patch:
        result = runner.run_evolution(_OHLCV, lookback=20)

    assert isinstance(result, AdvancedRunnerResult)
    assert result.generations_run == _SMALL_CFG.max_generations
    assert result.island_count == _SMALL_CFG.n_islands
    assert isinstance(result.best_fitness, float)
    assert isinstance(result.final_mutation_rate, float)
    assert result.registry_size >= 0


def test_advanced_evolution_has_history():
    """evolution_history contains exactly max_generations EvolutionRecord entries."""
    runner = _patched_runner()

    with runner._bt_patch, runner._tour_patch, runner._strat_patch:
        result = runner.run_evolution(_OHLCV, lookback=20)

    assert len(result.evolution_history) == _SMALL_CFG.max_generations
    for record in result.evolution_history:
        assert isinstance(record, EvolutionRecord)
        assert record.generation >= 0


def test_advanced_evolution_saves_checkpoint():
    """When persist_state=True, checkpoint field is a non-None EvolutionCheckpoint."""
    cfg = AdvancedRunnerConfig(
        n_islands=2,
        population_per_island=5,
        max_generations=2,
        seed=42,
        migration_interval=10,
        adaptive_mutation=True,
        persist_state=True,
    )
    runner = _patched_runner(cfg)

    with runner._bt_patch, runner._tour_patch, runner._strat_patch:
        result = runner.run_evolution(_OHLCV, lookback=20)

    assert result.checkpoint is not None
    assert isinstance(result.checkpoint, EvolutionCheckpoint)
    assert result.checkpoint.generation == cfg.max_generations
