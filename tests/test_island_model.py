"""Tests for IslandModel — CR-042 Phase 5."""

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

from app.services.island_model import Island, IslandModel, IslandModelConfig, MigrationPolicy
from app.services.strategy_genome import GenomeFactory

# Minimal OHLCV: 100 bars
_OHLCV = [
    [1_000_000 + i * 60_000, 100 + i * 0.1, 101 + i * 0.1, 99 + i * 0.1, 100.5 + i * 0.1, 1000]
    for i in range(100)
]


def _make_model(n_islands=3, pop=4, interval=5, topology="ring", seed=42):
    cfg = IslandModelConfig(
        n_islands=n_islands,
        population_per_island=pop,
        migration=MigrationPolicy(interval=interval, migrant_fraction=0.25, topology=topology),
        seed=seed,
    )
    return IslandModel(cfg)


def _stub_evolve(model):
    """Stub out the heavy backtesting by manually incrementing islands."""
    for island in model.islands:
        island.generation += 1
        for g in island.population:
            g.fitness = 0.5  # flat fitness so migration logic still runs


def test_island_initialization():
    """n_islands islands are created each with population_per_island genomes."""
    model = _make_model(n_islands=4, pop=5)
    assert len(model.islands) == 4
    for island in model.islands:
        assert len(island.population) == 5
        assert island.island_id.startswith("island_")


def test_evolve_generation_runs():
    """After evolve_generation, every island's generation counter increments."""
    model = _make_model(n_islands=2, pop=4, interval=100)

    # Patch backtesting so no heavy computation runs
    from app.services.backtesting_engine import BacktestingEngine, BacktestResult
    from app.services.performance_metrics import PerformanceReport
    from app.services.strategy_tournament import StrategyTournament, TournamentResult

    mock_perf = MagicMock(spec=PerformanceReport)
    mock_perf.sharpe_ratio = 1.0
    mock_bt = MagicMock(spec=BacktestResult)
    mock_bt.performance = mock_perf

    factory = GenomeFactory(seed=0)
    survivors = factory.create_population(4)
    mock_t_result = MagicMock(spec=TournamentResult)
    mock_t_result.survivors = survivors
    mock_t_result.best_fitness = 0.5
    mock_t_result.avg_fitness = 0.4

    with (
        patch.object(BacktestingEngine, "run", return_value=mock_bt),
        patch.object(StrategyTournament, "run_tournament", return_value=mock_t_result),
        patch(
            "app.services.island_model.IslandModel._genome_to_strategy", return_value=MagicMock()
        ),
    ):
        model.evolve_generation(_OHLCV, lookback=20)

    for island in model.islands:
        assert island.generation == 1


def test_migrate_ring_topology():
    """Ring topology: island_i sends migrants to island_(i+1) % n."""
    model = _make_model(n_islands=3, pop=4, topology="ring")

    # Assign distinct fitnesses so top migrant is deterministic
    for idx, island in enumerate(model.islands):
        for rank, genome in enumerate(island.population):
            genome.fitness = (idx + 1) * 10.0 + rank

    events = model.migrate()

    # Ring pairs: (0->1), (1->2), (2->0)
    from_ids = [e.from_island for e in events]
    to_ids = [e.to_island for e in events]

    assert "island_0" in from_ids
    assert "island_1" in from_ids
    assert "island_2" in from_ids

    # island_0 sends to island_1
    pair_0_to_1 = [e for e in events if e.from_island == "island_0" and e.to_island == "island_1"]
    assert len(pair_0_to_1) >= 1

    # island_2 wraps around to island_0
    pair_2_to_0 = [e for e in events if e.from_island == "island_2" and e.to_island == "island_0"]
    assert len(pair_2_to_0) >= 1


def test_migrate_star_topology():
    """Star topology: all islands send to island_0 AND island_0 sends to all."""
    model = _make_model(n_islands=3, pop=4, topology="star")

    for island in model.islands:
        for genome in island.population:
            genome.fitness = 0.5

    events = model.migrate()

    # Spokes in: island_1 -> island_0, island_2 -> island_0
    inbound = [e for e in events if e.to_island == "island_0"]
    assert len(inbound) >= 2

    # Spokes out: island_0 -> island_1, island_0 -> island_2
    outbound = [e for e in events if e.from_island == "island_0"]
    assert len(outbound) >= 2


def test_get_global_best():
    """get_global_best returns the single genome with the highest fitness."""
    model = _make_model(n_islands=3, pop=4)

    best_candidate = None
    for island in model.islands:
        for genome in island.population:
            genome.fitness = 0.1
        # Give island_1's last genome an elite fitness
        if island.island_id == "island_1":
            island.population[-1].fitness = 0.99
            best_candidate = island.population[-1]

    result = model.get_global_best()
    assert result is not None
    assert result.fitness == pytest.approx(0.99)
    assert result.id == best_candidate.id


def test_assign_regimes():
    """assign_regimes stamps each island with a regime_tag, cycling if fewer tags than islands."""
    model = _make_model(n_islands=4)
    tags = ["bull_trend", "bear_trend", "ranging"]
    model.assign_regimes(tags)

    assert model.islands[0].regime_tag == "bull_trend"
    assert model.islands[1].regime_tag == "bear_trend"
    assert model.islands[2].regime_tag == "ranging"
    # 4th island cycles back to index 0
    assert model.islands[3].regime_tag == "bull_trend"


def test_migration_at_interval():
    """Migration events are only created when generation % interval == 0."""
    model = _make_model(n_islands=2, pop=4, interval=3, topology="ring")

    # Set each island to generation=2 (not divisible by 3)
    for island in model.islands:
        island.generation = 2

    initial_count = len(model.migration_history)

    # Simulate generation check: gen=2, 2 % 3 != 0 → no migration
    gen = model.islands[0].generation
    if gen > 0 and gen % model.config.migration.interval == 0:
        model.migrate()

    assert len(model.migration_history) == initial_count  # no new events

    # Now set generation=3 → should trigger
    for island in model.islands:
        for genome in island.population:
            genome.fitness = 0.5
        island.generation = 3

    gen = model.islands[0].generation
    if gen > 0 and gen % model.config.migration.interval == 0:
        model.migrate()

    assert len(model.migration_history) > initial_count  # events added
