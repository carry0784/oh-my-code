"""
IslandModel — CR-042 Phase 5
Multi-population island topology with migration.

Each island evolves an independent population. Periodically, top genomes
migrate between islands following a configurable topology (ring, star, random).

This prevents premature convergence by maintaining genetic diversity
across isolated sub-populations.

Pure computation — no I/O.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from uuid import uuid4

import numpy as np

from app.core.logging import get_logger
from app.services.backtesting_engine import BacktestConfig, BacktestingEngine
from app.services.performance_metrics import PerformanceReport
from app.services.strategy_genome import GenomeFactory, StrategyGenome
from app.services.strategy_tournament import StrategyTournament

logger = get_logger(__name__)


@dataclass
class Island:
    """Single island with its own population."""
    island_id: str = field(default_factory=lambda: str(uuid4())[:8])
    population: list[StrategyGenome] = field(default_factory=list)
    regime_tag: str = ""
    generation: int = 0
    best_fitness: float = 0.0
    avg_fitness: float = 0.0


@dataclass
class MigrationEvent:
    """Record of a single migration."""
    from_island: str
    to_island: str
    genome_id: str
    fitness: float


@dataclass
class MigrationPolicy:
    """Controls how and when migration occurs."""
    interval: int = 5              # migrate every N generations
    migrant_fraction: float = 0.1  # top 10% migrate
    topology: str = "ring"         # "ring", "star", "random"


@dataclass
class IslandModelConfig:
    """Configuration for the island model."""
    n_islands: int = 5
    population_per_island: int = 10
    migration: MigrationPolicy = field(default_factory=MigrationPolicy)
    backtest_config: BacktestConfig = field(default_factory=BacktestConfig)
    seed: int = 42


class IslandModel:
    """Multi-population evolution with migration between islands."""

    def __init__(self, config: IslandModelConfig | None = None):
        self.config = config or IslandModelConfig()
        self.factory = GenomeFactory(self.config.seed)
        self.rng = np.random.RandomState(self.config.seed)
        self.islands: list[Island] = []
        self.migration_history: list[MigrationEvent] = []
        self._initialize_islands()

    def _initialize_islands(self) -> None:
        """Create initial islands with random populations."""
        for i in range(self.config.n_islands):
            population = self.factory.create_population(self.config.population_per_island)
            island = Island(
                island_id=f"island_{i}",
                population=population,
                regime_tag="",
            )
            self.islands.append(island)
        logger.info("islands_initialized", count=len(self.islands),
                     pop_per_island=self.config.population_per_island)

    def evolve_generation(self, ohlcv: list[list], lookback: int = 50) -> list[Island]:
        """Run one generation of evolution on all islands."""
        from app.services.strategy_runner import StrategyRunner
        
        for island in self.islands:
            if len(island.population) < 4:
                # Replenish if too small
                while len(island.population) < self.config.population_per_island:
                    island.population.append(self.factory.create_random())
            
            # Backtest all genomes on this island
            performances: dict[str, PerformanceReport] = {}
            for genome in island.population:
                strategy = self._genome_to_strategy(genome)
                engine = BacktestingEngine(self.config.backtest_config)
                bt = engine.run(strategy, ohlcv, lookback)
                performances[genome.id] = bt.performance

            # Tournament
            tournament = StrategyTournament(seed=self.config.seed + hash(island.island_id) % 1000)
            t_result = tournament.run_tournament(island.population, performances, island.generation)
            island.population = t_result.survivors
            island.best_fitness = t_result.best_fitness
            island.avg_fitness = t_result.avg_fitness
            island.generation += 1

        # Check if migration should occur
        gen = self.islands[0].generation if self.islands else 0
        if gen > 0 and gen % self.config.migration.interval == 0:
            self.migrate()

        logger.info("island_generation_complete",
                     gen=gen,
                     islands=len(self.islands),
                     best_per_island=[round(i.best_fitness, 4) for i in self.islands])
        return self.islands

    def migrate(self) -> list[MigrationEvent]:
        """Execute migration between islands based on topology."""
        events = []
        n = len(self.islands)
        if n < 2:
            return events

        topology = self.config.migration.topology
        fraction = self.config.migration.migrant_fraction

        if topology == "ring":
            pairs = [(i, (i + 1) % n) for i in range(n)]
        elif topology == "star":
            # Island 0 is hub
            pairs = [(i, 0) for i in range(1, n)] + [(0, i) for i in range(1, n)]
        elif topology == "random":
            pairs = []
            for i in range(n):
                j = self.rng.randint(0, n)
                if j != i:
                    pairs.append((i, j))
        else:
            pairs = [(i, (i + 1) % n) for i in range(n)]

        for src_idx, dst_idx in pairs:
            src = self.islands[src_idx]
            dst = self.islands[dst_idx]

            # Select top migrants from source
            n_migrants = max(1, int(len(src.population) * fraction))
            sorted_pop = sorted(src.population, key=lambda g: g.fitness, reverse=True)
            migrants = sorted_pop[:n_migrants]

            for migrant in migrants:
                clone = copy.deepcopy(migrant)
                clone.id = str(uuid4())[:8]
                dst.population.append(clone)
                event = MigrationEvent(
                    from_island=src.island_id,
                    to_island=dst.island_id,
                    genome_id=migrant.id,
                    fitness=migrant.fitness,
                )
                events.append(event)

        self.migration_history.extend(events)
        logger.info("migration_complete", events=len(events), topology=topology)
        return events

    def get_global_best(self) -> StrategyGenome | None:
        """Get the best genome across all islands."""
        best = None
        for island in self.islands:
            for genome in island.population:
                if best is None or genome.fitness > best.fitness:
                    best = genome
        return best

    def assign_regimes(self, regime_tags: list[str]) -> None:
        """Assign regime specializations to islands."""
        for i, island in enumerate(self.islands):
            if i < len(regime_tags):
                island.regime_tag = regime_tags[i]
            else:
                island.regime_tag = regime_tags[i % len(regime_tags)]

    def _genome_to_strategy(self, genome: StrategyGenome):
        """Convert genome to executable strategy.

        CR-045: Delegates to StrategyRunner._genome_to_strategy for
        consistent SMA/RSI branching based on strategy_type gene.
        """
        from app.services.strategy_runner import StrategyRunner, RunnerConfig
        runner = StrategyRunner(RunnerConfig())
        return runner._genome_to_strategy(genome)
