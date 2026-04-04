"""
ValidationPipeline — CR-040 Phase 3
5-stage strategy validation pipeline:
  Stage 1: In-Sample backtest
  Stage 2: Out-of-Sample backtest
  Stage 3: Walk-Forward analysis
  Stage 4: Monte Carlo simulation
  Stage 5: Paper trading readiness check

Each stage must PASS to proceed. Fail-fast on any stage.
Pure computation (Stages 1-4). Stage 5 is a readiness gate only.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.core.logging import get_logger
from app.services.backtesting_engine import BacktestConfig, BacktestingEngine, BacktestResult
from app.services.monte_carlo_simulator import MonteCarloSimulator, MonteCarloResult
from app.services.performance_metrics import PerformanceReport
from app.services.walk_forward_validator import WalkForwardValidator, WalkForwardResult
from strategies.base import BaseStrategy

logger = get_logger(__name__)


class StageStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"
    NOT_RUN = "NOT_RUN"


@dataclass
class StageResult:
    """Result of a single validation stage."""

    stage: int
    name: str
    status: StageStatus = StageStatus.NOT_RUN
    reason: str = ""
    metrics: dict = field(default_factory=dict)


@dataclass
class ValidationThresholds:
    """Minimum thresholds to pass each stage."""

    # Stage 1 & 2: Backtest
    min_trades: int = 10
    min_win_rate: float = 0.35
    max_drawdown_pct: float = 30.0
    min_profit_factor: float = 1.1

    # Stage 3: Walk-Forward
    min_efficiency_ratio: float = 0.3
    min_consistency: float = 0.4

    # Stage 4: Monte Carlo
    max_ruin_probability: float = 0.10
    min_profitable_probability: float = 0.55
    max_dd_95th_pct: float = 40.0


@dataclass
class ValidationResult:
    """Complete 5-stage validation result."""

    strategy_name: str = ""
    overall_status: StageStatus = StageStatus.NOT_RUN
    stages: list[StageResult] = field(default_factory=list)
    passed_stages: int = 0
    total_stages: int = 5

    # Detailed results
    in_sample: BacktestResult | None = None
    out_sample: BacktestResult | None = None
    walk_forward: WalkForwardResult | None = None
    monte_carlo: MonteCarloResult | None = None


class ValidationPipeline:
    """Orchestrates the 5-stage validation pipeline."""

    def __init__(
        self,
        thresholds: ValidationThresholds | None = None,
        backtest_config: BacktestConfig | None = None,
        mc_simulations: int = 1000,
        wf_windows: int = 5,
    ):
        self.thresholds = thresholds or ValidationThresholds()
        self.bt_config = backtest_config or BacktestConfig()
        self.mc_simulations = mc_simulations
        self.wf_windows = wf_windows

    def validate(
        self,
        strategy: BaseStrategy,
        ohlcv: list[list],
        lookback: int = 50,
    ) -> ValidationResult:
        """
        Run full 5-stage validation pipeline.
        Fail-fast: stops at first FAIL.
        """
        result = ValidationResult(strategy_name=strategy.name)

        # Split data: 70% in-sample, 30% out-of-sample
        split_idx = int(len(ohlcv) * 0.7)
        in_sample_data = ohlcv[:split_idx]
        out_sample_data = ohlcv[split_idx:]

        engine = BacktestingEngine(self.bt_config)

        # Stage 1: In-Sample Backtest
        stage1 = self._stage1_in_sample(engine, strategy, in_sample_data, lookback)
        result.stages.append(stage1)
        if stage1.status == StageStatus.PASS:
            result.in_sample = engine.run(strategy, in_sample_data, lookback)
            result.passed_stages += 1
        else:
            result.overall_status = StageStatus.FAIL
            self._fill_remaining(result, 2)
            return result

        # Stage 2: Out-of-Sample Backtest
        stage2 = self._stage2_out_sample(engine, strategy, out_sample_data, lookback)
        result.stages.append(stage2)
        if stage2.status == StageStatus.PASS:
            result.out_sample = engine.run(strategy, out_sample_data, lookback)
            result.passed_stages += 1
        else:
            result.overall_status = StageStatus.FAIL
            self._fill_remaining(result, 3)
            return result

        # Stage 3: Walk-Forward
        stage3 = self._stage3_walk_forward(strategy, ohlcv, lookback)
        result.stages.append(stage3)
        if stage3.status == StageStatus.PASS:
            result.passed_stages += 1
        else:
            result.overall_status = StageStatus.FAIL
            self._fill_remaining(result, 4)
            return result

        # Stage 4: Monte Carlo
        all_trades = (result.in_sample.trades if result.in_sample else []) + (
            result.out_sample.trades if result.out_sample else []
        )
        stage4 = self._stage4_monte_carlo(all_trades)
        result.stages.append(stage4)
        if stage4.status == StageStatus.PASS:
            result.passed_stages += 1
        else:
            result.overall_status = StageStatus.FAIL
            self._fill_remaining(result, 5)
            return result

        # Stage 5: Paper Trading Readiness
        stage5 = self._stage5_paper_ready(result)
        result.stages.append(stage5)
        if stage5.status == StageStatus.PASS:
            result.passed_stages += 1
            result.overall_status = StageStatus.PASS
        else:
            result.overall_status = StageStatus.FAIL

        logger.info(
            "validation_complete",
            strategy=strategy.name,
            status=result.overall_status.value,
            passed=result.passed_stages,
            total=result.total_stages,
        )
        return result

    def _stage1_in_sample(
        self,
        engine: BacktestingEngine,
        strategy: BaseStrategy,
        data: list[list],
        lookback: int,
    ) -> StageResult:
        """Stage 1: In-sample backtest must meet minimum performance."""
        bt = engine.run(strategy, data, lookback)
        perf = bt.performance
        return self._check_backtest_thresholds(1, "In-Sample Backtest", perf)

    def _stage2_out_sample(
        self,
        engine: BacktestingEngine,
        strategy: BaseStrategy,
        data: list[list],
        lookback: int,
    ) -> StageResult:
        """Stage 2: Out-of-sample must show the strategy generalizes."""
        bt = engine.run(strategy, data, lookback)
        perf = bt.performance
        return self._check_backtest_thresholds(2, "Out-of-Sample Backtest", perf)

    def _check_backtest_thresholds(
        self, stage: int, name: str, perf: PerformanceReport
    ) -> StageResult:
        """Check backtest performance against thresholds."""
        t = self.thresholds
        metrics = {
            "trades": perf.total_trades,
            "win_rate": round(perf.win_rate, 3),
            "max_drawdown": round(perf.max_drawdown_pct, 2),
            "profit_factor": round(perf.profit_factor, 3),
            "total_return": round(perf.total_return_pct, 2),
        }

        if perf.total_trades < t.min_trades:
            return StageResult(
                stage,
                name,
                StageStatus.FAIL,
                f"Insufficient trades: {perf.total_trades} < {t.min_trades}",
                metrics,
            )
        if perf.win_rate < t.min_win_rate:
            return StageResult(
                stage,
                name,
                StageStatus.FAIL,
                f"Win rate too low: {perf.win_rate:.1%} < {t.min_win_rate:.1%}",
                metrics,
            )
        if perf.max_drawdown_pct > t.max_drawdown_pct:
            return StageResult(
                stage,
                name,
                StageStatus.FAIL,
                f"Drawdown too high: {perf.max_drawdown_pct:.1f}% > {t.max_drawdown_pct}%",
                metrics,
            )
        if perf.profit_factor < t.min_profit_factor and perf.total_trades >= t.min_trades:
            return StageResult(
                stage,
                name,
                StageStatus.FAIL,
                f"Profit factor too low: {perf.profit_factor:.2f} < {t.min_profit_factor}",
                metrics,
            )

        return StageResult(stage, name, StageStatus.PASS, "All thresholds met", metrics)

    def _stage3_walk_forward(
        self, strategy: BaseStrategy, ohlcv: list[list], lookback: int
    ) -> StageResult:
        """Stage 3: Walk-forward analysis."""
        validator = WalkForwardValidator(n_windows=self.wf_windows, config=self.bt_config)
        wf = validator.validate(strategy, ohlcv, lookback)
        self._last_wf = wf

        metrics = {
            "windows": wf.total_windows,
            "efficiency_ratio": round(wf.efficiency_ratio, 3),
            "consistency": round(wf.consistency, 3),
            "is_overfit": wf.is_overfit,
        }

        t = self.thresholds
        if wf.is_overfit:
            return StageResult(
                3, "Walk-Forward Analysis", StageStatus.FAIL, "Strategy is overfit", metrics
            )
        if wf.total_windows == 0:
            return StageResult(
                3,
                "Walk-Forward Analysis",
                StageStatus.FAIL,
                "Insufficient data for walk-forward",
                metrics,
            )
        if wf.consistency < t.min_consistency:
            return StageResult(
                3,
                "Walk-Forward Analysis",
                StageStatus.FAIL,
                f"Consistency too low: {wf.consistency:.1%} < {t.min_consistency:.1%}",
                metrics,
            )

        return StageResult(
            3, "Walk-Forward Analysis", StageStatus.PASS, "Walk-forward validation passed", metrics
        )

    def _stage4_monte_carlo(self, trades: list) -> StageResult:
        """Stage 4: Monte Carlo simulation."""
        simulator = MonteCarloSimulator(n_simulations=self.mc_simulations, seed=42)
        mc = simulator.simulate(trades)
        self._last_mc = mc

        metrics = {
            "return_median": round(mc.return_median, 2),
            "return_5th": round(mc.return_5th, 2),
            "max_dd_95th": round(mc.max_dd_95th, 2),
            "ruin_probability": round(mc.ruin_probability, 3),
            "profitable_probability": round(mc.profitable_probability, 3),
        }

        t = self.thresholds
        if mc.ruin_probability > t.max_ruin_probability:
            return StageResult(
                4,
                "Monte Carlo Simulation",
                StageStatus.FAIL,
                f"Ruin probability too high: {mc.ruin_probability:.1%} > {t.max_ruin_probability:.1%}",
                metrics,
            )
        if mc.profitable_probability < t.min_profitable_probability:
            return StageResult(
                4,
                "Monte Carlo Simulation",
                StageStatus.FAIL,
                f"Profit probability too low: {mc.profitable_probability:.1%}",
                metrics,
            )
        if mc.max_dd_95th > t.max_dd_95th_pct:
            return StageResult(
                4,
                "Monte Carlo Simulation",
                StageStatus.FAIL,
                f"95th percentile drawdown too high: {mc.max_dd_95th:.1f}%",
                metrics,
            )

        return StageResult(
            4,
            "Monte Carlo Simulation",
            StageStatus.PASS,
            "Monte Carlo within acceptable bounds",
            metrics,
        )

    def _stage5_paper_ready(self, result: ValidationResult) -> StageResult:
        """Stage 5: Paper trading readiness gate."""
        metrics = {
            "stages_passed": result.passed_stages,
            "has_in_sample": result.in_sample is not None,
            "has_out_sample": result.out_sample is not None,
        }

        if result.passed_stages < 4:
            return StageResult(
                5,
                "Paper Trading Readiness",
                StageStatus.FAIL,
                f"Only {result.passed_stages}/4 stages passed",
                metrics,
            )

        return StageResult(
            5,
            "Paper Trading Readiness",
            StageStatus.PASS,
            "Strategy approved for paper trading",
            metrics,
        )

    def _fill_remaining(self, result: ValidationResult, from_stage: int) -> None:
        """Fill remaining stages as NOT_RUN after a failure."""
        stage_names = {
            2: "Out-of-Sample Backtest",
            3: "Walk-Forward Analysis",
            4: "Monte Carlo Simulation",
            5: "Paper Trading Readiness",
        }
        for s in range(from_stage, 6):
            if s in stage_names:
                result.stages.append(
                    StageResult(
                        s, stage_names[s], StageStatus.NOT_RUN, "Skipped due to prior failure"
                    )
                )
