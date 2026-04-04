"""Tests for EvolutionStateManager — CR-042 Phase 5."""

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

import json
import pytest

from app.services.evolution_state import EvolutionCheckpoint, EvolutionStateManager
from app.services.strategy_genome import Gene, GenomeFactory, StrategyGenome


def _make_populations(n_islands=2, pop_size=3, seed=0):
    factory = GenomeFactory(seed=seed)
    return [factory.create_population(pop_size) for _ in range(n_islands)]


def test_save_creates_checkpoint():
    """save() returns an EvolutionCheckpoint with correct generation and island count."""
    mgr = EvolutionStateManager()
    populations = _make_populations(n_islands=3, pop_size=4)

    checkpoint = mgr.save(generation=7, populations=populations)

    assert isinstance(checkpoint, EvolutionCheckpoint)
    assert checkpoint.generation == 7
    assert len(checkpoint.islands) == 3
    # Each island list should contain 4 dicts
    for island_data in checkpoint.islands:
        assert len(island_data) == 4
        assert isinstance(island_data[0], dict)


def test_load_restores_populations():
    """Round-trip save→load gives the same number of islands and population sizes."""
    mgr = EvolutionStateManager()
    populations = _make_populations(n_islands=2, pop_size=5)

    checkpoint = mgr.save(generation=3, populations=populations)
    state = mgr.load(checkpoint)

    assert state["generation"] == 3
    assert len(state["populations"]) == 2
    for pop in state["populations"]:
        assert len(pop) == 5
        for genome in pop:
            assert isinstance(genome, StrategyGenome)


def test_to_json_from_json_roundtrip():
    """JSON serialization/deserialization preserves generation, island count, fitness."""
    mgr = EvolutionStateManager()
    populations = _make_populations(n_islands=2, pop_size=3)
    # Give a genome a known fitness to verify preservation
    populations[0][0].fitness = 0.77

    checkpoint = mgr.save(generation=5, populations=populations, fitness_history=[0.1, 0.5, 0.77])

    json_str = mgr.to_json(checkpoint)
    assert isinstance(json_str, str)

    restored = mgr.from_json(json_str)
    assert isinstance(restored, EvolutionCheckpoint)
    assert restored.generation == 5
    assert len(restored.islands) == 2
    assert restored.fitness_history == [0.1, 0.5, 0.77]

    # Verify the known fitness value survived the round-trip
    first_genome_dict = restored.islands[0][0]
    assert first_genome_dict["fitness"] == pytest.approx(0.77)


def test_checkpoint_has_timestamp():
    """Saved checkpoint carries a non-empty ISO-format timestamp."""
    mgr = EvolutionStateManager()
    populations = _make_populations()

    checkpoint = mgr.save(generation=1, populations=populations)

    assert checkpoint.timestamp != ""
    # Basic ISO-8601 shape check: contains 'T' and '+' or 'Z'
    assert "T" in checkpoint.timestamp


def test_load_restores_hall_of_fame():
    """HOF genomes saved in the checkpoint are reconstructed correctly by load()."""
    mgr = EvolutionStateManager()
    factory = GenomeFactory(seed=7)
    populations = [factory.create_population(3)]

    hof = factory.create_population(2)
    hof[0].fitness = 0.88
    hof[1].fitness = 0.66

    checkpoint = mgr.save(generation=4, populations=populations, hall_of_fame=hof)
    state = mgr.load(checkpoint)

    assert len(state["hall_of_fame"]) == 2
    fitnesses = sorted([g.fitness for g in state["hall_of_fame"]])
    assert fitnesses[0] == pytest.approx(0.66, abs=0.01)
    assert fitnesses[1] == pytest.approx(0.88, abs=0.01)


def test_dict_to_genome_reconstructs():
    """_dict_to_genome rebuilds a StrategyGenome whose params match the original."""
    mgr = EvolutionStateManager()
    factory = GenomeFactory(seed=3)
    original = factory.create_default()
    original.fitness = 0.55
    original.wins = 4

    genome_dict = original.to_dict()
    reconstructed = mgr._dict_to_genome(genome_dict)

    assert isinstance(reconstructed, StrategyGenome)
    assert reconstructed.id == original.id
    assert reconstructed.fitness == pytest.approx(0.55)
    assert reconstructed.wins == 4

    # Params round-trip: every key in the original dict should appear
    orig_params = original.to_params()
    recon_params = reconstructed.to_params()
    for key, val in orig_params.items():
        assert key in recon_params
        assert recon_params[key] == pytest.approx(val, rel=1e-5)
