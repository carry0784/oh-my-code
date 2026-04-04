"""
StrategyRunner — CR-041 Phase 4
Automated strategy execution pipeline connecting all Phase 1-4 components.

Pipeline: Data Collection → Regime Detection → Strategy Selection →
          Backtesting → Validation → Tournament → Evolution

Read-only in Mode 1. Execution gated by governance pipeline.
"""

from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.services.backtesting_engine import BacktestConfig, BacktestingEngine, BacktestResult
from app.services.fitness_function import FitnessFunction
from app.services.performance_metrics import PerformanceCalculator, PerformanceReport
from app.services.strategy_genome import GenomeFactory, StrategyGenome
from app.services.strategy_tournament import StrategyTournament, TournamentResult
from app.services.validation_pipeline import (
    ValidationPipeline,
    ValidationResult,
    ValidationThresholds,
)
from strategies.base import BaseStrategy
from strategies.example_strategy import SimpleMAStrategy
from strategies.rsi_strategy import RSICrossStrategy

logger = get_logger(__name__)


@dataclass
class RunnerConfig:
    """Configuration for the strategy runner."""

    population_size: int = 20
    max_generations: int = 10
    tournament_seed: int = 42
    backtest_config: BacktestConfig = field(default_factory=BacktestConfig)
    validation_thresholds: ValidationThresholds = field(default_factory=ValidationThresholds)
    mc_simulations: int = 200  # Lower for speed during evolution
    wf_windows: int = 3


@dataclass
class EvolutionRecord:
    """Record of a single generation in the evolution."""

    generation: int = 0
    best_fitness: float = 0.0
    avg_fitness: float = 0.0
    population_size: int = 0
    best_genome_id: str = ""
    eliminated_count: int = 0


@dataclass
class RunnerResult:
    """Complete strategy runner result."""

    generations_run: int = 0
    evolution_history: list[EvolutionRecord] = field(default_factory=list)
    best_genome: StrategyGenome | None = None
    best_fitness: float = 0.0
    best_backtest: BacktestResult | None = None
    validation_result: ValidationResult | None = None
    final_population: list[StrategyGenome] = field(default_factory=list)


class StrategyRunner:
    """
    Automated strategy evolution pipeline.
    Connects genome creation → backtesting → fitness → tournament → validation.
    """

    def __init__(self, config: RunnerConfig | None = None):
        self.config = config or RunnerConfig()
        self.factory = GenomeFactory(self.config.tournament_seed)

    def run_evolution(
        self,
        ohlcv: list[list],
        lookback: int = 50,
    ) -> RunnerResult:
        """
        Run full evolution loop:
        1. Create initial population
        2. For each generation: backtest all → evaluate fitness → tournament
        3. Validate the best genome through 5-stage pipeline
        """
        result = RunnerResult()

        # 1. Initialize population
        population = self.factory.create_population(self.config.population_size)
        tournament = StrategyTournament(seed=self.config.tournament_seed)

        # 2. Evolution loop
        for gen in range(self.config.max_generations):
            # Backtest each genome
            performances: dict[str, PerformanceReport] = {}
            for genome in population:
                strategy = self._genome_to_strategy(genome)
                engine = BacktestingEngine(self.config.backtest_config)
                bt = engine.run(strategy, ohlcv, lookback)
                performances[genome.id] = bt.performance

            # Tournament
            t_result = tournament.run_tournament(population, performances, gen)
            population = t_result.survivors

            # Record history
            record = EvolutionRecord(
                generation=gen,
                best_fitness=t_result.best_fitness,
                avg_fitness=t_result.avg_fitness,
                population_size=t_result.population_size,
                best_genome_id=t_result.entries[0].genome.id if t_result.entries else "",
                eliminated_count=len(t_result.eliminated),
            )
            result.evolution_history.append(record)

            logger.info(
                "evolution_generation",
                gen=gen,
                best=round(t_result.best_fitness, 4),
                avg=round(t_result.avg_fitness, 4),
                pop=t_result.population_size,
            )

        result.generations_run = self.config.max_generations
        result.final_population = population

        # 3. Find best genome
        if population:
            best = max(population, key=lambda g: g.fitness)
            result.best_genome = best
            result.best_fitness = best.fitness

            # Run final backtest for the best
            best_strategy = self._genome_to_strategy(best)
            engine = BacktestingEngine(self.config.backtest_config)
            result.best_backtest = engine.run(best_strategy, ohlcv, lookback)

            # 4. Validate best through full pipeline
            pipeline = ValidationPipeline(
                thresholds=self.config.validation_thresholds,
                backtest_config=self.config.backtest_config,
                mc_simulations=self.config.mc_simulations,
                wf_windows=self.config.wf_windows,
            )
            result.validation_result = pipeline.validate(best_strategy, ohlcv, lookback)

        logger.info(
            "evolution_complete",
            generations=result.generations_run,
            best_fitness=round(result.best_fitness, 4),
            validated=result.validation_result.overall_status.value
            if result.validation_result
            else "N/A",
        )
        return result

    def _genome_to_strategy(self, genome: StrategyGenome) -> BaseStrategy:
        """Convert a genome to an executable strategy.

        CR-045: Routes to SMA or RSI strategy based on strategy_type gene.
        strategy_type=0 → SimpleMAStrategy, strategy_type=1 → RSICrossStrategy.
        """
        params = genome.to_params()
        strategy_type = int(params.get("ind.strategy_type", 0))

        if strategy_type == 1:
            # RSI Cross Strategy
            rsi_period = int(params.get("ind.rsi_period", 14))
            rsi_overbought = float(params.get("ind.rsi_overbought", 70))
            rsi_oversold = float(params.get("ind.rsi_oversold", 30))

            # Ensure overbought > oversold
            if rsi_overbought <= rsi_oversold:
                rsi_overbought = rsi_oversold + 20

            return RSICrossStrategy(
                "BTC/USDT",
                rsi_period=rsi_period,
                rsi_overbought=rsi_overbought,
                rsi_oversold=rsi_oversold,
            )
        else:
            # SMA Crossover Strategy (default)
            fast = int(params.get("ind.fast_period", 10))
            slow = int(params.get("ind.slow_period", 20))

            # Ensure fast < slow
            if fast >= slow:
                slow = fast + 5

            return SimpleMAStrategy(
                "BTC/USDT",
                fast_period=fast,
                slow_period=slow,
            )
