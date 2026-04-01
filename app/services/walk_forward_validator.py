"""
WalkForwardValidator — CR-040 Phase 3
Walk-forward analysis: split data into rolling in-sample/out-of-sample windows,
run backtest on each, then aggregate results.
Detects overfitting by comparing in-sample vs out-of-sample performance.
Pure computation — no I/O.
"""

from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.services.backtesting_engine import BacktestConfig, BacktestingEngine, BacktestResult
from strategies.base import BaseStrategy

logger = get_logger(__name__)


@dataclass
class WalkForwardWindow:
    """Single walk-forward window result."""
    window_index: int
    in_sample_bars: int
    out_sample_bars: int
    in_sample_return: float = 0.0
    out_sample_return: float = 0.0
    in_sample_sharpe: float = 0.0
    out_sample_sharpe: float = 0.0
    in_sample_trades: int = 0
    out_sample_trades: int = 0


@dataclass
class WalkForwardResult:
    """Aggregated walk-forward analysis result."""
    strategy_name: str = ""
    total_windows: int = 0
    windows: list[WalkForwardWindow] = field(default_factory=list)

    # Aggregates
    avg_in_sample_return: float = 0.0
    avg_out_sample_return: float = 0.0
    avg_in_sample_sharpe: float = 0.0
    avg_out_sample_sharpe: float = 0.0

    # Overfitting detection
    efficiency_ratio: float = 0.0   # OOS return / IS return (>0.5 = good)
    consistency: float = 0.0        # % of windows where OOS is profitable
    is_overfit: bool = False


class WalkForwardValidator:
    """Performs walk-forward analysis on a strategy."""

    def __init__(
        self,
        in_sample_ratio: float = 0.7,
        n_windows: int = 5,
        config: BacktestConfig | None = None,
    ):
        self.in_sample_ratio = in_sample_ratio
        self.n_windows = n_windows
        self.config = config or BacktestConfig()

    def validate(
        self,
        strategy: BaseStrategy,
        ohlcv: list[list],
        lookback: int = 50,
    ) -> WalkForwardResult:
        """
        Run walk-forward validation.

        Splits data into n_windows rolling segments, each with
        in_sample_ratio for training and (1 - in_sample_ratio) for testing.
        """
        result = WalkForwardResult(strategy_name=strategy.name)

        total_bars = len(ohlcv)
        window_size = total_bars // self.n_windows
        if window_size < lookback * 2:
            logger.warning("insufficient_data_for_walk_forward",
                           bars=total_bars, windows=self.n_windows)
            return result

        engine = BacktestingEngine(self.config)
        windows: list[WalkForwardWindow] = []

        for i in range(self.n_windows):
            start = i * window_size
            end = min(start + window_size, total_bars)
            segment = ohlcv[start:end]

            split_idx = int(len(segment) * self.in_sample_ratio)
            in_sample = segment[:split_idx]
            out_sample = segment[split_idx:]

            # Run in-sample backtest
            is_result = engine.run(strategy, in_sample, lookback)
            # Run out-of-sample backtest
            oos_result = engine.run(strategy, out_sample, lookback)

            wfw = WalkForwardWindow(
                window_index=i,
                in_sample_bars=len(in_sample),
                out_sample_bars=len(out_sample),
                in_sample_return=is_result.performance.total_return_pct,
                out_sample_return=oos_result.performance.total_return_pct,
                in_sample_sharpe=is_result.performance.sharpe_ratio,
                out_sample_sharpe=oos_result.performance.sharpe_ratio,
                in_sample_trades=len(is_result.trades),
                out_sample_trades=len(oos_result.trades),
            )
            windows.append(wfw)

        result.windows = windows
        result.total_windows = len(windows)
        self._aggregate(result)

        logger.info(
            "walk_forward_complete",
            strategy=strategy.name,
            windows=result.total_windows,
            efficiency=round(result.efficiency_ratio, 3),
            consistency=round(result.consistency, 3),
            overfit=result.is_overfit,
        )
        return result

    def _aggregate(self, result: WalkForwardResult) -> None:
        """Calculate aggregate metrics from window results."""
        if not result.windows:
            return

        n = len(result.windows)
        result.avg_in_sample_return = sum(w.in_sample_return for w in result.windows) / n
        result.avg_out_sample_return = sum(w.out_sample_return for w in result.windows) / n
        result.avg_in_sample_sharpe = sum(w.in_sample_sharpe for w in result.windows) / n
        result.avg_out_sample_sharpe = sum(w.out_sample_sharpe for w in result.windows) / n

        # Efficiency: how much of IS performance carries to OOS
        if result.avg_in_sample_return != 0:
            result.efficiency_ratio = result.avg_out_sample_return / abs(result.avg_in_sample_return)
        else:
            result.efficiency_ratio = 0.0

        # Consistency: % of OOS windows that are profitable
        profitable = sum(1 for w in result.windows if w.out_sample_return > 0)
        result.consistency = profitable / n

        # Overfitting: IS good but OOS bad, or efficiency < 0.3
        result.is_overfit = (
            result.avg_in_sample_return > 0
            and result.avg_out_sample_return <= 0
        ) or (
            result.efficiency_ratio < 0.3
            and result.avg_in_sample_return > 5.0  # IS showed decent return
        )
