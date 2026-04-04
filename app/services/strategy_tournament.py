"""
StrategyTournament — CR-041 Phase 4
Natural selection system for strategy genomes.

Tournament process:
  1. Evaluate fitness of all genomes
  2. Rank by fitness score
  3. Top 25% → promoted (kept as-is)
  4. Middle 50% → crossover + mutation (breed new variants)
  5. Bottom 25% → mutated heavily (last chance)
  6. Bottom 3 → eliminated (extinction)

Pure computation — no I/O.
"""

from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.services.fitness_function import FitnessFunction, FitnessBreakdown
from app.services.performance_metrics import PerformanceReport
from app.services.strategy_genome import GenomeFactory, StrategyGenome

logger = get_logger(__name__)


@dataclass
class TournamentEntry:
    """Single entry in a tournament."""
    genome: StrategyGenome
    fitness: FitnessBreakdown = field(default_factory=FitnessBreakdown)
    rank: int = 0
    action: str = ""  # "promoted", "bred", "mutated", "eliminated"


@dataclass
class TournamentResult:
    """Result of a tournament round."""
    generation: int = 0
    entries: list[TournamentEntry] = field(default_factory=list)
    survivors: list[StrategyGenome] = field(default_factory=list)
    eliminated: list[str] = field(default_factory=list)  # IDs
    new_genomes: list[StrategyGenome] = field(default_factory=list)

    # Stats
    best_fitness: float = 0.0
    avg_fitness: float = 0.0
    worst_fitness: float = 0.0
    population_size: int = 0


class StrategyTournament:
    """Runs evolutionary tournaments on strategy populations."""

    def __init__(
        self,
        promote_ratio: float = 0.25,    # Top 25% kept
        mutate_ratio: float = 0.25,     # Bottom 25% mutated
        eliminate_count: int = 3,        # Bottom 3 removed
        seed: int | None = None,
    ):
        self.promote_ratio = promote_ratio
        self.mutate_ratio = mutate_ratio
        self.eliminate_count = eliminate_count
        self.factory = GenomeFactory(seed)
        self.fitness_fn = FitnessFunction()

    def run_tournament(
        self,
        population: list[StrategyGenome],
        performances: dict[str, PerformanceReport],
        generation: int = 0,
    ) -> TournamentResult:
        """
        Execute one tournament round.

        Args:
            population: Current genome population.
            performances: Genome ID → backtest PerformanceReport.
            generation: Current generation number.
        """
        result = TournamentResult(generation=generation)

        if len(population) < 4:
            logger.warning("population_too_small", size=len(population))
            result.survivors = list(population)
            result.population_size = len(population)
            return result

        # 1. Evaluate fitness
        entries = []
        for genome in population:
            perf = performances.get(genome.id, PerformanceReport())
            fitness = self.fitness_fn.evaluate(perf)
            genome.fitness = fitness.total
            entries.append(TournamentEntry(genome=genome, fitness=fitness))

        # 2. Rank by fitness (descending)
        entries.sort(key=lambda e: e.fitness.total, reverse=True)
        for i, entry in enumerate(entries):
            entry.rank = i + 1

        # 3. Partition
        n = len(entries)
        n_promote = max(1, int(n * self.promote_ratio))
        n_mutate = max(1, int(n * self.mutate_ratio))
        n_eliminate = min(self.eliminate_count, n // 4)  # Never eliminate > 25%

        promoted = entries[:n_promote]
        middle = entries[n_promote:n - n_mutate]
        bottom = entries[n - n_mutate:]
        eliminated = entries[n - n_eliminate:] if n_eliminate > 0 else []

        # 4. Apply actions
        survivors = []

        # Promoted: keep as-is, increment age
        for entry in promoted:
            entry.action = "promoted"
            entry.genome.age += 1
            entry.genome.wins += 1
            survivors.append(entry.genome)

        # Middle: crossover + mutation
        bred = []
        for i in range(len(middle)):
            entry = middle[i]
            entry.action = "bred"
            # Cross with a random promoted genome
            partner_idx = self.factory.rng.randint(0, len(promoted))
            child = self.factory.crossover(entry.genome, promoted[partner_idx].genome)
            child = self.factory.mutate(child)
            child.generation = generation + 1
            bred.append(child)
            survivors.append(child)

        # Bottom (non-eliminated): heavy mutation
        eliminated_ids = {e.genome.id for e in eliminated}
        for entry in bottom:
            if entry.genome.id in eliminated_ids:
                entry.action = "eliminated"
            else:
                entry.action = "mutated"
                mutated = self.factory.mutate(entry.genome)
                # Double mutation for bottom tier
                mutated = self.factory.mutate(mutated)
                mutated.generation = generation + 1
                mutated.age = 0
                survivors.append(mutated)

        # Fill eliminated slots with fresh random genomes
        for _ in range(len(eliminated)):
            fresh = self.factory.create_random()
            fresh.generation = generation + 1
            survivors.append(fresh)

        # Collect results
        result.entries = entries
        result.survivors = survivors
        result.eliminated = [e.genome.id for e in eliminated]
        result.new_genomes = bred + [s for s in survivors if s.generation == generation + 1]
        result.population_size = len(survivors)

        fitnesses = [e.fitness.total for e in entries]
        result.best_fitness = max(fitnesses)
        result.avg_fitness = sum(fitnesses) / len(fitnesses)
        result.worst_fitness = min(fitnesses)

        logger.info(
            "tournament_complete",
            generation=generation,
            population=len(survivors),
            promoted=len(promoted),
            bred=len(bred),
            eliminated=len(eliminated),
            best=round(result.best_fitness, 4),
            avg=round(result.avg_fitness, 4),
        )
        return result
