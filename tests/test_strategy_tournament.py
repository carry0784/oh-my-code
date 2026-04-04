"""Tests for StrategyTournament — CR-041 Phase 4."""

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

from app.services.performance_metrics import PerformanceReport
from app.services.strategy_genome import GenomeFactory, StrategyGenome
from app.services.strategy_tournament import StrategyTournament, TournamentResult


def _make_population(n: int, seed: int = 0) -> list[StrategyGenome]:
    factory = GenomeFactory(seed=seed)
    return factory.create_population(n)


def _make_performances(
    population: list[StrategyGenome],
    fitness_values: list[float],
) -> dict[str, PerformanceReport]:
    """
    Map genomes to PerformanceReports that will produce the requested fitness ordering.
    A higher sharpe_ratio drives a higher fitness return score.
    """
    assert len(population) == len(fitness_values)
    performances = {}
    for genome, target in zip(population, fitness_values):
        # Use sharpe and win_rate to approximate desired fitness tier.
        # High target → high sharpe; enough trades to avoid penalty.
        sharpe = target * 4.0          # target=1.0 → sharpe=4.0
        win = 0.35 + target * 0.25    # range ~[0.35, 0.60]
        performances[genome.id] = PerformanceReport(
            total_trades=20,
            winning_trades=int(20 * win),
            losing_trades=int(20 * (1 - win)),
            win_rate=win,
            sharpe_ratio=sharpe,
            profit_factor=1.2 + target,
            max_drawdown_pct=10.0 * (1 - target),
            max_consecutive_losses=2,
            total_return_pct=target * 10,
        )
    return performances


def test_tournament_small_population_passthrough():
    pop = _make_population(3, seed=0)
    tournament = StrategyTournament(seed=0)
    performances = _make_performances(pop, [0.5, 0.4, 0.3])
    result = tournament.run_tournament(pop, performances, generation=0)
    # Population < 4 → pass-through without ranking
    assert result.population_size == 3
    assert len(result.eliminated) == 0


def test_tournament_entries_ranked_by_fitness():
    pop = _make_population(8, seed=1)
    tournament = StrategyTournament(seed=1)
    # Provide descending fitness values
    fitnesses = [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2]
    performances = _make_performances(pop, fitnesses)
    result = tournament.run_tournament(pop, performances, generation=0)
    ranks = [e.rank for e in result.entries]
    assert ranks == sorted(ranks)
    # Best entry has rank 1 and highest fitness
    assert result.entries[0].rank == 1
    assert result.entries[0].fitness.total >= result.entries[-1].fitness.total


def test_tournament_promoted_get_wins():
    pop = _make_population(8, seed=2)
    tournament = StrategyTournament(promote_ratio=0.25, seed=2)
    fitnesses = [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2]
    performances = _make_performances(pop, fitnesses)
    result = tournament.run_tournament(pop, performances, generation=0)
    promoted = [e for e in result.entries if e.action == "promoted"]
    for entry in promoted:
        assert entry.genome.wins >= 1


def test_tournament_eliminated_replaced_by_fresh():
    pop = _make_population(12, seed=3)
    tournament = StrategyTournament(eliminate_count=3, seed=3)
    fitnesses = [0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.5, 0.4, 0.3, 0.2, 0.1, 0.05]
    performances = _make_performances(pop, fitnesses)
    result = tournament.run_tournament(pop, performances, generation=1)
    assert len(result.eliminated) > 0
    # Survivors count should equal original population (eliminated slots refilled)
    assert result.population_size == len(pop)


def test_tournament_population_size_maintained():
    pop = _make_population(10, seed=4)
    tournament = StrategyTournament(seed=4)
    fitnesses = [float(i) / 10 for i in range(10, 0, -1)]
    performances = _make_performances(pop, fitnesses)
    result = tournament.run_tournament(pop, performances, generation=0)
    assert result.population_size == len(pop)


def test_tournament_result_stats_correct():
    pop = _make_population(8, seed=5)
    tournament = StrategyTournament(seed=5)
    fitnesses = [0.9, 0.7, 0.5, 0.5, 0.4, 0.3, 0.2, 0.1]
    performances = _make_performances(pop, fitnesses)
    result = tournament.run_tournament(pop, performances, generation=2)
    assert result.best_fitness >= result.avg_fitness >= result.worst_fitness
    assert result.generation == 2


def test_tournament_middle_bred_with_promoted():
    pop = _make_population(8, seed=6)
    tournament = StrategyTournament(promote_ratio=0.25, seed=6)
    fitnesses = [0.9, 0.8, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]
    performances = _make_performances(pop, fitnesses)
    result = tournament.run_tournament(pop, performances, generation=0)
    bred_entries = [e for e in result.entries if e.action == "bred"]
    assert len(bred_entries) > 0
    # All bred children should have parent_ids populated (from crossover)
    for child in result.new_genomes:
        # new_genomes includes bred children; crossover children have parent_ids
        if child.parent_ids:
            assert len(child.parent_ids) == 2


def test_tournament_bottom_double_mutated():
    pop = _make_population(8, seed=7)
    original_ids = {g.id for g in pop}
    tournament = StrategyTournament(promote_ratio=0.25, mutate_ratio=0.25, eliminate_count=1, seed=7)
    fitnesses = [0.9, 0.8, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]
    performances = _make_performances(pop, fitnesses)
    result = tournament.run_tournament(pop, performances, generation=0)
    mutated_entries = [e for e in result.entries if e.action == "mutated"]
    assert len(mutated_entries) > 0
    # Mutated genomes must have new IDs (deep-copied + re-id'd in mutate)
    survivor_ids = {g.id for g in result.survivors}
    assert not survivor_ids.issubset(original_ids)


def test_tournament_generation_incremented():
    pop = _make_population(8, seed=8)
    tournament = StrategyTournament(seed=8)
    fitnesses = [0.9, 0.8, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]
    performances = _make_performances(pop, fitnesses)
    result = tournament.run_tournament(pop, performances, generation=5)
    # New genomes bred/mutated in generation 5 → assigned generation 6
    for genome in result.new_genomes:
        assert genome.generation == 6


def test_tournament_deterministic_with_seed():
    pop_a = _make_population(8, seed=10)
    pop_b = _make_population(8, seed=10)
    fitnesses = [0.9, 0.8, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]

    t1 = StrategyTournament(seed=42)
    t2 = StrategyTournament(seed=42)

    perf_a = _make_performances(pop_a, fitnesses)
    perf_b = _make_performances(pop_b, fitnesses)

    r1 = t1.run_tournament(pop_a, perf_a, generation=0)
    r2 = t2.run_tournament(pop_b, perf_b, generation=0)

    assert r1.best_fitness == r2.best_fitness
    assert r1.avg_fitness == r2.avg_fitness
    assert len(r1.survivors) == len(r2.survivors)
