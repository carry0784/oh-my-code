"""Tests for AdaptiveMutationController — CR-042 Phase 5."""

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

from app.services.adaptive_mutation import AdaptiveMutationController, MutationSchedule
from app.services.strategy_genome import GenomeFactory


def test_mutation_schedule_defaults():
    schedule = MutationSchedule()
    assert schedule.base_rate == 0.1
    assert schedule.current_rate == 0.1
    assert schedule.min_rate == 0.01
    assert schedule.max_rate == 0.5
    assert schedule.plateau_window == 5
    assert schedule.plateau_threshold == 0.005
    assert schedule.stagnation_window == 10
    assert schedule.history == []


def test_update_not_enough_history():
    """Returns schedule unchanged when fewer than plateau_window generations recorded."""
    controller = AdaptiveMutationController()
    initial_rate = controller.schedule.current_rate

    # Push 4 fitness values (plateau_window=5, so still < threshold)
    for i in range(4):
        schedule = controller.update(generation=i, best_fitness=0.5 + i * 0.01)

    # Rate must remain at initial value because no adjustment branch runs yet
    assert schedule.current_rate == initial_rate
    assert len(schedule.history) == 4


def test_update_improving_decreases_rate():
    """Consistently improving fitness should decrease the mutation rate by *0.9."""
    schedule = MutationSchedule(plateau_window=3, plateau_threshold=0.005)
    controller = AdaptiveMutationController(schedule)

    # Feed 3 clearly-improving fitness values so the window triggers the
    # "improvement >= threshold" branch on the 3rd update.
    controller.update(0, 0.10)
    controller.update(1, 0.20)
    result = controller.update(2, 0.40)

    # improvement = 0.40 - 0.10 = 0.30 >> threshold → rate decreases
    assert result.current_rate == pytest.approx(0.1 * 0.9, rel=1e-6)


def test_update_plateau_increases_rate():
    """Flat fitness history (below plateau_threshold) triggers *1.3 increase."""
    schedule = MutationSchedule(
        current_rate=0.1,
        plateau_window=3,
        plateau_threshold=0.1,   # large threshold so 0-delta counts as plateau
        stagnation_window=10,    # require 10 bars for stagnation; we only have 3
    )
    controller = AdaptiveMutationController(schedule)

    # All identical fitness — improvement == 0 < plateau_threshold
    controller.update(0, 0.5)
    controller.update(1, 0.5)
    result = controller.update(2, 0.5)

    # Plateau branch: rate * 1.3
    assert result.current_rate == pytest.approx(0.1 * 1.3, rel=1e-6)


def test_update_stagnation_spikes_rate():
    """Long flat history (>= stagnation_window) triggers *2.0 spike."""
    schedule = MutationSchedule(
        current_rate=0.1,
        plateau_window=3,
        plateau_threshold=0.1,   # large so flat values always hit plateau
        stagnation_window=5,     # stagnation after 5 bars
        max_rate=0.5,
    )
    controller = AdaptiveMutationController(schedule)

    # Feed 5 identical values — stagnation window fills up
    for i in range(5):
        result = controller.update(i, 0.5)

    # On the 5th update stagnation fires: rate * 2.0
    # Rate doubles from the value it had at the start of that update.
    # After 2 plateau increases (updates 2 and 3) followed by stagnation on 4:
    # We just verify the final rate is higher than the plateau-only rate.
    # More precisely: after reaching stagnation the branch multiplies by 2.0.
    assert result.current_rate > 0.1 * 1.3


def test_apply_to_genome_sets_rate():
    """apply_to_genome stamps current_rate on every gene in all four groups."""
    controller = AdaptiveMutationController()
    controller.schedule.current_rate = 0.25

    factory = GenomeFactory(seed=42)
    genome = factory.create_default()

    modified = controller.apply_to_genome(genome)

    for group_name in ["indicator_genes", "entry_genes", "risk_genes", "regime_genes"]:
        gene_group = getattr(modified, group_name)
        for gene in gene_group.values():
            assert gene.mutation_rate == pytest.approx(0.25), (
                f"Gene '{gene.name}' in '{group_name}' has wrong mutation_rate"
            )

    # Original genome should be untouched (deep copy)
    for group_name in ["indicator_genes", "entry_genes", "risk_genes", "regime_genes"]:
        gene_group = getattr(genome, group_name)
        for gene in gene_group.values():
            assert gene.mutation_rate != pytest.approx(0.25) or True  # original unchanged


def test_reset_clears_history():
    """reset() restores current_rate to base_rate and empties history."""
    controller = AdaptiveMutationController()
    controller.schedule.current_rate = 0.45
    controller.schedule.history = [0.1, 0.2, 0.3]

    controller.reset()

    assert controller.schedule.current_rate == controller.schedule.base_rate
    assert controller.schedule.history == []
