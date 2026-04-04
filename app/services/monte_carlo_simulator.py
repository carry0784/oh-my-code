"""
MonteCarloSimulator — CR-040 Phase 3
Monte Carlo simulation: resample trade returns to estimate
confidence intervals for performance metrics.
Pure computation — no I/O.
"""

from dataclasses import dataclass, field

import numpy as np

from app.core.logging import get_logger
from app.services.performance_metrics import PerformanceCalculator, TradeRecord

logger = get_logger(__name__)


@dataclass
class MonteCarloResult:
    """Monte Carlo simulation result with confidence intervals."""
    n_simulations: int = 0
    n_trades: int = 0

    # Return distribution
    return_mean: float = 0.0
    return_median: float = 0.0
    return_std: float = 0.0
    return_5th: float = 0.0     # 5th percentile (worst case)
    return_25th: float = 0.0
    return_75th: float = 0.0
    return_95th: float = 0.0    # 95th percentile (best case)

    # Drawdown distribution
    max_dd_mean: float = 0.0
    max_dd_median: float = 0.0
    max_dd_95th: float = 0.0    # 95th percentile worst drawdown

    # Sharpe distribution
    sharpe_mean: float = 0.0
    sharpe_median: float = 0.0
    sharpe_5th: float = 0.0

    # Risk of ruin: % of simulations with > X% drawdown
    ruin_probability: float = 0.0  # P(drawdown > 50%)

    # Confidence
    profitable_probability: float = 0.0  # P(return > 0)


class MonteCarloSimulator:
    """Runs Monte Carlo simulations on trade results."""

    def __init__(
        self,
        n_simulations: int = 1000,
        ruin_threshold_pct: float = 50.0,
        seed: int | None = None,
    ):
        self.n_simulations = n_simulations
        self.ruin_threshold = ruin_threshold_pct
        self.rng = np.random.RandomState(seed)

    def simulate(
        self,
        trades: list[TradeRecord],
        initial_capital: float = 10000.0,
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation by resampling trade sequence.
        Each simulation shuffles the order of trades and computes metrics.
        """
        result = MonteCarloResult(
            n_simulations=self.n_simulations,
            n_trades=len(trades),
        )

        if len(trades) < 3:
            return result

        pnls = np.array([t.pnl for t in trades])
        returns_pct = np.array([t.return_pct for t in trades])
        calculator = PerformanceCalculator()

        sim_returns = []
        sim_drawdowns = []
        sim_sharpes = []

        for _ in range(self.n_simulations):
            # Resample with replacement
            indices = self.rng.choice(len(trades), size=len(trades), replace=True)
            sampled_pnls = pnls[indices]

            # Equity curve
            equity = [initial_capital]
            for pnl in sampled_pnls:
                equity.append(equity[-1] + pnl)

            total_return = ((equity[-1] - initial_capital) / initial_capital) * 100
            sim_returns.append(total_return)

            # Max drawdown
            peak = initial_capital
            max_dd = 0.0
            for val in equity[1:]:
                if val > peak:
                    peak = val
                dd = (peak - val) / peak * 100 if peak > 0 else 0
                max_dd = max(max_dd, dd)
            sim_drawdowns.append(max_dd)

            # Sharpe (simplified)
            sampled_rets = returns_pct[indices] / 100
            if np.std(sampled_rets) > 0:
                sharpe = float(np.mean(sampled_rets) / np.std(sampled_rets) * np.sqrt(252))
            else:
                sharpe = 0.0
            sim_sharpes.append(sharpe)

        # Compute statistics
        sim_returns = np.array(sim_returns)
        sim_drawdowns = np.array(sim_drawdowns)
        sim_sharpes = np.array(sim_sharpes)

        result.return_mean = float(np.mean(sim_returns))
        result.return_median = float(np.median(sim_returns))
        result.return_std = float(np.std(sim_returns))
        result.return_5th = float(np.percentile(sim_returns, 5))
        result.return_25th = float(np.percentile(sim_returns, 25))
        result.return_75th = float(np.percentile(sim_returns, 75))
        result.return_95th = float(np.percentile(sim_returns, 95))

        result.max_dd_mean = float(np.mean(sim_drawdowns))
        result.max_dd_median = float(np.median(sim_drawdowns))
        result.max_dd_95th = float(np.percentile(sim_drawdowns, 95))

        result.sharpe_mean = float(np.mean(sim_sharpes))
        result.sharpe_median = float(np.median(sim_sharpes))
        result.sharpe_5th = float(np.percentile(sim_sharpes, 5))

        result.ruin_probability = float(np.mean(sim_drawdowns > self.ruin_threshold))
        result.profitable_probability = float(np.mean(sim_returns > 0))

        logger.info(
            "monte_carlo_complete",
            sims=self.n_simulations,
            trades=len(trades),
            return_median=round(result.return_median, 2),
            dd_95th=round(result.max_dd_95th, 2),
            profitable_prob=round(result.profitable_probability, 3),
        )
        return result
