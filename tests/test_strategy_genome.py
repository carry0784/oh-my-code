"""Tests for StrategyGenome — CR-041 Phase 4."""

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

from app.services.strategy_genome import Gene, GenomeFactory, StrategyGenome


def test_gene_creation_defaults():
    gene = Gene(name="fast_period", value=10.0, min_val=3.0, max_val=50.0)
    assert gene.name == "fast_period"
    assert gene.value == 10.0
    assert gene.min_val == 3.0
    assert gene.max_val == 50.0
    assert gene.mutation_rate == 0.1
    assert gene.mutation_scale == 0.2
    assert gene.is_integer is False


def test_gene_mutation_within_bounds():
    gene = Gene(name="test", value=25.0, min_val=0.0, max_val=50.0, mutation_rate=1.0)
    rng = np.random.RandomState(0)
    for _ in range(50):
        mutated = gene.mutate(rng)
        assert mutated.min_val <= mutated.value <= mutated.max_val


def test_gene_integer_mutation_rounds():
    gene = Gene(
        name="period", value=10.0, min_val=3.0, max_val=50.0, mutation_rate=1.0, is_integer=True
    )
    rng = np.random.RandomState(7)
    for _ in range(30):
        mutated = gene.mutate(rng)
        assert mutated.value == float(round(mutated.value))


def test_gene_no_mutation_when_rate_zero():
    gene = Gene(name="x", value=15.0, min_val=0.0, max_val=100.0, mutation_rate=0.0)
    rng = np.random.RandomState(42)
    for _ in range(20):
        mutated = gene.mutate(rng)
        assert mutated.value == 15.0


def test_genome_default_creation():
    factory = GenomeFactory(seed=0)
    genome = factory.create_default()
    assert isinstance(genome, StrategyGenome)
    assert "fast_period" in genome.indicator_genes
    assert "slow_period" in genome.indicator_genes
    assert "stop_loss_pct" in genome.risk_genes
    assert "confidence_threshold" in genome.entry_genes
    assert "trend_sensitivity" in genome.regime_genes
    assert genome.fitness == 0.0
    assert genome.generation == 0


def test_genome_to_params_flat_dict():
    factory = GenomeFactory(seed=0)
    genome = factory.create_default()
    params = genome.to_params()
    # Keys should be prefixed with group names
    assert "ind.fast_period" in params
    assert "ind.slow_period" in params
    assert "risk.stop_loss_pct" in params
    assert "entry.confidence_threshold" in params
    assert "regime.trend_sensitivity" in params
    # All values should be numeric (float or int for integer genes)
    for v in params.values():
        assert isinstance(v, (int, float))


def test_genome_to_dict_serialization():
    factory = GenomeFactory(seed=0)
    genome = factory.create_default()
    genome.fitness = 0.75
    genome.wins = 3
    d = genome.to_dict()
    assert d["id"] == genome.id
    assert d["generation"] == 0
    assert d["fitness"] == 0.75
    assert d["wins"] == 3
    assert "params" in d
    assert isinstance(d["params"], dict)
    assert len(d["params"]) > 0


def test_factory_create_random_varies():
    factory = GenomeFactory(seed=1)
    g1 = factory.create_random()
    g2 = factory.create_random()
    # Different random draws should produce different parameter values
    p1 = g1.to_params()
    p2 = g2.to_params()
    assert p1 != p2


def test_factory_crossover_has_parent_ids():
    factory = GenomeFactory(seed=2)
    parent_a = factory.create_random()
    parent_b = factory.create_random()
    child = factory.crossover(parent_a, parent_b)
    assert parent_a.id in child.parent_ids
    assert parent_b.id in child.parent_ids
    assert len(child.parent_ids) == 2


def test_factory_crossover_inherits_genes():
    factory = GenomeFactory(seed=3)
    parent_a = factory.create_default()
    parent_b = factory.create_default()
    # Give parents distinct values
    parent_a.indicator_genes["fast_period"].value = 5.0
    parent_b.indicator_genes["fast_period"].value = 40.0
    child = factory.crossover(parent_a, parent_b)
    fast_val = child.indicator_genes["fast_period"].value
    # Child must have inherited one of the parent values
    assert fast_val in (5.0, 40.0)


def test_factory_mutate_enforces_fast_lt_slow():
    factory = GenomeFactory(seed=99)
    genome = factory.create_default()
    # Artificially set fast >= slow
    genome.indicator_genes["fast_period"].value = 30.0
    genome.indicator_genes["slow_period"].value = 20.0
    mutated = factory.mutate(genome)
    fast = mutated.indicator_genes["fast_period"].value
    slow = mutated.indicator_genes["slow_period"].value
    assert fast < slow


def test_factory_create_population_size():
    factory = GenomeFactory(seed=5)
    pop = factory.create_population(8)
    assert len(pop) == 8
    ids = [g.id for g in pop]
    # All IDs should be unique
    assert len(set(ids)) == 8


# ── CR-045: strategy_type gene tests ──


def test_genome_has_strategy_type_gene():
    """CR-045: strategy_type gene must exist in indicator_genes."""
    factory = GenomeFactory(seed=0)
    genome = factory.create_default()
    assert "strategy_type" in genome.indicator_genes
    gene = genome.indicator_genes["strategy_type"]
    assert gene.min_val == 0
    assert gene.max_val == 1
    assert gene.is_integer is True


def test_genome_strategy_type_in_params():
    """CR-045: strategy_type appears in flat params as ind.strategy_type."""
    factory = GenomeFactory(seed=0)
    genome = factory.create_default()
    params = genome.to_params()
    assert "ind.strategy_type" in params
    assert params["ind.strategy_type"] in (0.0, 1.0)


def test_genome_strategy_type_mutation_stays_binary():
    """CR-045: strategy_type gene stays 0 or 1 after mutation."""
    factory = GenomeFactory(seed=10)
    genome = factory.create_default()
    for _ in range(50):
        mutated = factory.mutate(genome)
        val = mutated.indicator_genes["strategy_type"].value
        assert val in (0.0, 1.0), f"strategy_type must be 0 or 1, got {val}"


def test_genome_crossover_preserves_strategy_type():
    """CR-045: crossover preserves strategy_type gene."""
    factory = GenomeFactory(seed=20)
    parent_a = factory.create_default()
    parent_b = factory.create_default()
    parent_a.indicator_genes["strategy_type"].value = 0.0
    parent_b.indicator_genes["strategy_type"].value = 1.0
    child = factory.crossover(parent_a, parent_b)
    val = child.indicator_genes["strategy_type"].value
    assert val in (0.0, 1.0)
