"""Tests for StrategyRegistry — CR-042 Phase 5."""

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

import pytest

from app.services.strategy_genome import GenomeFactory
from app.services.strategy_registry import RegistryEntry, StrategyRegistry


def _make_registry(max_entries=20, threshold=0.95):
    return StrategyRegistry(max_entries=max_entries, similarity_threshold=threshold)


def _genome(seed, fitness=0.5, regime="bull_trend"):
    factory = GenomeFactory(seed=seed)
    g = factory.create_random()
    g.fitness = fitness
    g.regime_tag = regime
    return g


def test_register_adds_entry():
    """register() adds the genome and returns a RegistryEntry."""
    reg = _make_registry()
    g = _genome(seed=1, fitness=0.6)

    entry = reg.register(g)

    assert entry is not None
    assert isinstance(entry, RegistryEntry)
    assert reg.size == 1
    assert entry.genome.id == g.id


def test_register_assigns_rank():
    """Entries are ranked 1..N by descending fitness after each registration."""
    reg = _make_registry()
    low = _genome(seed=10, fitness=0.3)
    high = _genome(seed=20, fitness=0.9)

    # Register lower fitness first, then higher
    reg.register(low)
    reg.register(high)

    assert reg.size == 2
    # Rank 1 should be the highest fitness genome
    assert reg.entries[0].rank == 1
    assert reg.entries[0].lifetime_fitness == pytest.approx(0.9)
    assert reg.entries[1].rank == 2
    assert reg.entries[1].lifetime_fitness == pytest.approx(0.3)


def test_register_duplicate_rejected():
    """A genome identical to an existing entry is rejected (returns None)."""
    # Use a very low similarity_threshold so near-identical params are caught
    reg = _make_registry(threshold=0.5)
    factory = GenomeFactory(seed=5)
    g = factory.create_default()
    g.fitness = 0.7

    first = reg.register(g)
    assert first is not None

    # Clone with same params — should be detected as duplicate
    import copy
    clone = copy.deepcopy(g)
    clone.id = "different-id"  # different id but same parameters

    second = reg.register(clone)
    assert second is None
    assert reg.size == 1  # still only one entry


def test_get_top_n():
    """get_top_n(n) returns the n highest-fitness entries in descending order."""
    reg = _make_registry()
    for i, fitness in enumerate([0.4, 0.9, 0.7, 0.2, 0.8]):
        reg.register(_genome(seed=i + 1, fitness=fitness))

    top3 = reg.get_top_n(3)
    assert len(top3) == 3
    fitnesses = [e.lifetime_fitness for e in top3]
    assert fitnesses == sorted(fitnesses, reverse=True)
    assert fitnesses[0] == pytest.approx(0.9)


def test_get_top_n_regime_filter():
    """get_top_n with regime= parameter returns only entries matching that regime."""
    reg = _make_registry()
    reg.register(_genome(seed=1, fitness=0.8, regime="bull_trend"))
    reg.register(_genome(seed=2, fitness=0.7, regime="bear_trend"))
    reg.register(_genome(seed=3, fitness=0.6, regime="bull_trend"))

    bull_top = reg.get_top_n(10, regime="bull_trend")
    assert all(e.regime_tag == "bull_trend" for e in bull_top)
    assert len(bull_top) == 2

    bear_top = reg.get_top_n(10, regime="bear_trend")
    assert len(bear_top) == 1


def test_retire_removes_entry():
    """retire(genome_id) removes the entry and re-ranks the remaining ones."""
    reg = _make_registry()
    g1 = _genome(seed=1, fitness=0.9)
    g2 = _genome(seed=2, fitness=0.5)
    g3 = _genome(seed=3, fitness=0.7)

    reg.register(g1)
    reg.register(g2)
    reg.register(g3)
    assert reg.size == 3

    removed = reg.retire(g2.id)
    assert removed is True
    assert reg.size == 2

    # Remaining IDs must not include g2
    remaining_ids = {e.genome.id for e in reg.entries}
    assert g2.id not in remaining_ids

    # Ranks must be contiguous from 1
    ranks = [e.rank for e in reg.entries]
    assert sorted(ranks) == list(range(1, reg.size + 1))


def test_max_entries_cap():
    """Registering beyond max_entries silently trims the lowest-ranked entries."""
    reg = _make_registry(max_entries=3, threshold=1.01)  # threshold>1.0 disables dedup

    for i in range(5):
        g = _genome(seed=i + 1, fitness=0.1 * (i + 1))
        reg.register(g)

    assert reg.size == 3
    # The lowest fitness (0.1, 0.2) should have been trimmed
    fitnesses = [e.lifetime_fitness for e in reg.entries]
    assert min(fitnesses) > 0.2


def test_export_format():
    """export() returns a list of dicts each containing the required keys."""
    reg = _make_registry()
    reg.register(_genome(seed=1, fitness=0.6))
    reg.register(_genome(seed=2, fitness=0.4))

    exported = reg.export()

    assert isinstance(exported, list)
    assert len(exported) == 2

    required_keys = {"rank", "genome_id", "fitness", "regime_tag",
                     "validation_status", "registered_at", "params"}
    for item in exported:
        assert required_keys.issubset(item.keys()), (
            f"Missing keys: {required_keys - item.keys()}"
        )
        assert isinstance(item["params"], dict)
        assert isinstance(item["rank"], int)
        assert isinstance(item["fitness"], float)
