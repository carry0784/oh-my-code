"""
AdvancedRunner — CR-042 Phase 5
Extended strategy runner with island model, adaptive mutation,
regime-aware evolution, and state persistence.

Orchestrates all Phase 5 components into a unified evolution pipeline.

Pipeline: Initialize Islands → For each generation:
  Adaptive Mutation → Island Evolution → Migration → Registry Update
  → Checkpoint Save

Pure computation — no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.services.adaptive_mutation import AdaptiveMutationController, MutationSchedule
from app.services.backtesting_engine import BacktestConfig
from app.services.evolution_state import EvolutionCheckpoint, EvolutionStateManager
from app.services.island_model import IslandModel, IslandModelConfig, MigrationPolicy
from app.services.strategy_genome import StrategyGenome
from app.services.strategy_registry import StrategyRegistry
from app.services.strategy_runner import RunnerConfig, RunnerResult, EvolutionRecord
from app.services.validation_pipeline import ValidationThresholds

logger = get_logger(__name__)


@dataclass
class AdvancedRunnerConfig:
    """Configuration for the advanced evolution runner."""

    # Island model
    n_islands: int = 5
    population_per_island: int = 10
    migration_interval: int = 5
    migration_topology: str = "ring"

    # Evolution
    max_generations: int = 20
    seed: int = 42

    # Adaptive mutation
    adaptive_mutation: bool = True

    # Backtest
    backtest_config: BacktestConfig = field(default_factory=BacktestConfig)

    # Validation
    validation_thresholds: ValidationThresholds = field(default_factory=ValidationThresholds)
    mc_simulations: int = 200
    wf_windows: int = 3

    # Registry
    registry_max_entries: int = 50

    # State persistence
    persist_state: bool = True


@dataclass
class AdvancedRunnerResult:
    """Result of advanced evolution run."""

    generations_run: int = 0
    evolution_history: list[EvolutionRecord] = field(default_factory=list)
    best_genome: StrategyGenome | None = None
    best_fitness: float = 0.0
    island_count: int = 0
    total_migrations: int = 0
    registry_size: int = 0
    final_mutation_rate: float = 0.1
    checkpoint: EvolutionCheckpoint | None = None


class AdvancedStrategyRunner:
    """Extended runner with island model and adaptive mutation."""

    def __init__(self, config: AdvancedRunnerConfig | None = None):
        self.config = config or AdvancedRunnerConfig()

        # Initialize components
        island_config = IslandModelConfig(
            n_islands=self.config.n_islands,
            population_per_island=self.config.population_per_island,
            migration=MigrationPolicy(
                interval=self.config.migration_interval,
                topology=self.config.migration_topology,
            ),
            backtest_config=self.config.backtest_config,
            seed=self.config.seed,
        )
        self.island_model = IslandModel(island_config)
        self.mutation_controller = (
            AdaptiveMutationController() if self.config.adaptive_mutation else None
        )
        self.registry = StrategyRegistry(max_entries=self.config.registry_max_entries)
        self.state_manager = EvolutionStateManager()

    def run_evolution(self, ohlcv: list[list], lookback: int = 50) -> AdvancedRunnerResult:
        """
        Run advanced evolution with island model.

        1. For each generation: evolve all islands
        2. Apply adaptive mutation rates
        3. Register best genomes
        4. Save checkpoint
        """
        result = AdvancedRunnerResult()

        for gen in range(self.config.max_generations):
            # Apply adaptive mutation to all island populations
            if self.mutation_controller:
                for island in self.island_model.islands:
                    island.population = [
                        self.mutation_controller.apply_to_genome(g) for g in island.population
                    ]

            # Evolve all islands (includes migration)
            self.island_model.evolve_generation(ohlcv, lookback)

            # Get global best
            global_best = self.island_model.get_global_best()
            best_fitness = global_best.fitness if global_best else 0.0

            # Update adaptive mutation
            if self.mutation_controller:
                self.mutation_controller.update(gen, best_fitness)

            # Register best from each island
            for island in self.island_model.islands:
                if island.population:
                    island_best = max(island.population, key=lambda g: g.fitness)
                    if island_best.fitness > 0:
                        self.registry.register(island_best)

            # Calculate average fitness
            all_fitnesses = []
            for island in self.island_model.islands:
                for genome in island.population:
                    all_fitnesses.append(genome.fitness)
            avg_fitness = sum(all_fitnesses) / len(all_fitnesses) if all_fitnesses else 0.0

            # Record
            record = EvolutionRecord(
                generation=gen,
                best_fitness=best_fitness,
                avg_fitness=avg_fitness,
                population_size=sum(len(i.population) for i in self.island_model.islands),
                best_genome_id=global_best.id if global_best else "",
            )
            result.evolution_history.append(record)

            logger.info(
                "advanced_evolution_gen",
                gen=gen,
                best=round(best_fitness, 4),
                avg=round(avg_fitness, 4),
                mutation_rate=round(self.mutation_controller.get_rate(), 4)
                if self.mutation_controller
                else 0.1,
                registry=self.registry.size,
            )

        # Finalize result
        result.generations_run = self.config.max_generations
        result.best_genome = self.island_model.get_global_best()
        result.best_fitness = result.best_genome.fitness if result.best_genome else 0.0
        result.island_count = len(self.island_model.islands)
        result.total_migrations = len(self.island_model.migration_history)
        result.registry_size = self.registry.size
        result.final_mutation_rate = (
            self.mutation_controller.get_rate() if self.mutation_controller else 0.1
        )

        # Save checkpoint
        if self.config.persist_state:
            populations = [i.population for i in self.island_model.islands]
            hof = [e.genome for e in self.registry.get_top_n(10)]
            mut_state = (
                {
                    "current_rate": self.mutation_controller.schedule.current_rate,
                    "history": self.mutation_controller.schedule.history,
                }
                if self.mutation_controller
                else {}
            )

            fitness_hist = [r.best_fitness for r in result.evolution_history]
            result.checkpoint = self.state_manager.save(
                self.config.max_generations,
                populations,
                hof,
                mut_state,
                fitness_hist,
            )

        logger.info(
            "advanced_evolution_complete",
            generations=result.generations_run,
            best=round(result.best_fitness, 4),
            registry=result.registry_size,
            migrations=result.total_migrations,
        )
        return result

    def resume_evolution(
        self,
        checkpoint: EvolutionCheckpoint,
        ohlcv: list[list],
        additional_generations: int = 10,
        lookback: int = 50,
    ) -> AdvancedRunnerResult:
        """Resume evolution from a saved checkpoint."""
        state = self.state_manager.load(checkpoint)

        # Restore island populations
        for i, pop in enumerate(state["populations"]):
            if i < len(self.island_model.islands):
                self.island_model.islands[i].population = pop
                self.island_model.islands[i].generation = state["generation"]

        # Restore mutation state
        if self.mutation_controller and state["mutation_schedule"]:
            self.mutation_controller.schedule.current_rate = state["mutation_schedule"].get(
                "current_rate", 0.1
            )
            self.mutation_controller.schedule.history = state["mutation_schedule"].get(
                "history", []
            )

        # Restore hall of fame
        for genome in state["hall_of_fame"]:
            self.registry.register(genome)

        # Update config and run
        self.config.max_generations = additional_generations
        return self.run_evolution(ohlcv, lookback)
