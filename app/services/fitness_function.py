"""
FitnessFunction — CR-041 Phase 4
Multi-objective fitness evaluation for strategy genomes.

Fitness = 40% Return + 30% Stability + 20% Consistency + 10% Live Match

Components:
  - Return: risk-adjusted return (Sharpe-based)
  - Stability: inverse of max drawdown
  - Consistency: win rate + profit factor balance
  - Live Match: backtest vs paper trading correlation (future Phase 7)

Pure computation — no I/O.
"""

from dataclasses import dataclass

import numpy as np

from app.core.logging import get_logger
from app.services.performance_metrics import PerformanceReport

logger = get_logger(__name__)

# Fitness weights
W_RETURN = 0.40
W_STABILITY = 0.30
W_CONSISTENCY = 0.20
W_LIVE_MATCH = 0.10


@dataclass
class FitnessBreakdown:
    """Detailed fitness score breakdown."""

    total: float = 0.0  # 0.0 to 1.0
    return_score: float = 0.0  # 0.0 to 1.0
    stability_score: float = 0.0
    consistency_score: float = 0.0
    live_match_score: float = 0.5  # Default 0.5 until paper trading (Phase 7)
    penalties: float = 0.0
    details: dict | None = None


class FitnessFunction:
    """Evaluates strategy fitness from backtest performance."""

    def __init__(
        self,
        min_trades: int = 10,
        max_acceptable_drawdown: float = 30.0,
        target_sharpe: float = 2.0,
        target_win_rate: float = 0.55,
        target_profit_factor: float = 1.5,
    ):
        self.min_trades = min_trades
        self.max_dd = max_acceptable_drawdown
        self.target_sharpe = target_sharpe
        self.target_win_rate = target_win_rate
        self.target_pf = target_profit_factor

    def evaluate(
        self,
        performance: PerformanceReport,
        live_performance: PerformanceReport | None = None,
    ) -> FitnessBreakdown:
        """Calculate multi-objective fitness score."""
        result = FitnessBreakdown()

        # Penalty: insufficient trades
        if performance.total_trades < self.min_trades:
            result.penalties = 0.5
            result.total = 0.0
            result.details = {"penalty": "insufficient_trades", "trades": performance.total_trades}
            return result

        # 1. Return score (40%) — Sharpe-based
        result.return_score = self._return_score(performance)

        # 2. Stability score (30%) — drawdown-based
        result.stability_score = self._stability_score(performance)

        # 3. Consistency score (20%) — win rate + profit factor
        result.consistency_score = self._consistency_score(performance)

        # 4. Live match score (10%) — backtest vs live correlation
        result.live_match_score = self._live_match_score(performance, live_performance)

        # Penalties
        result.penalties = self._calculate_penalties(performance)

        # Weighted total
        raw = (
            result.return_score * W_RETURN
            + result.stability_score * W_STABILITY
            + result.consistency_score * W_CONSISTENCY
            + result.live_match_score * W_LIVE_MATCH
        )
        result.total = max(0.0, min(1.0, raw - result.penalties))

        result.details = {
            "weights": {
                "return": W_RETURN,
                "stability": W_STABILITY,
                "consistency": W_CONSISTENCY,
                "live_match": W_LIVE_MATCH,
            },
            "raw_total": round(raw, 4),
        }

        logger.info(
            "fitness_evaluated",
            total=round(result.total, 4),
            ret=round(result.return_score, 3),
            stab=round(result.stability_score, 3),
            cons=round(result.consistency_score, 3),
            penalty=round(result.penalties, 3),
        )
        return result

    def _return_score(self, perf: PerformanceReport) -> float:
        """Sharpe ratio → 0-1 score. Sharpe >= target = 1.0."""
        if perf.sharpe_ratio <= 0:
            # Negative Sharpe → partial score based on total return
            if perf.total_return_pct > 0:
                return min(perf.total_return_pct / 100, 0.3)
            return 0.0
        return min(perf.sharpe_ratio / self.target_sharpe, 1.0)

    def _stability_score(self, perf: PerformanceReport) -> float:
        """Lower drawdown → higher score."""
        if perf.max_drawdown_pct <= 0:
            return 1.0
        if perf.max_drawdown_pct >= self.max_dd:
            return 0.0
        return 1.0 - (perf.max_drawdown_pct / self.max_dd)

    def _consistency_score(self, perf: PerformanceReport) -> float:
        """Win rate + profit factor balance."""
        wr_score = min(perf.win_rate / self.target_win_rate, 1.0) if perf.win_rate > 0 else 0.0
        pf = perf.profit_factor if perf.profit_factor != float("inf") else self.target_pf * 2
        pf_score = min(pf / self.target_pf, 1.0)

        # Average of win rate and profit factor scores
        return wr_score * 0.5 + pf_score * 0.5

    def _live_match_score(
        self,
        backtest: PerformanceReport,
        live: PerformanceReport | None,
    ) -> float:
        """Compare backtest vs live/paper results. Default 0.5 if no live data."""
        if live is None or live.total_trades < 5:
            return 0.5  # Neutral when no live data available

        # Compare return direction match
        direction_match = (
            1.0
            if (
                (backtest.total_return_pct > 0 and live.total_return_pct > 0)
                or (backtest.total_return_pct <= 0 and live.total_return_pct <= 0)
            )
            else 0.0
        )

        # Compare win rate similarity
        wr_diff = abs(backtest.win_rate - live.win_rate)
        wr_similarity = max(0, 1.0 - wr_diff * 2)

        return direction_match * 0.6 + wr_similarity * 0.4

    def _calculate_penalties(self, perf: PerformanceReport) -> float:
        """Penalty for extreme risk behaviors."""
        penalty = 0.0

        # Excessive consecutive losses
        if perf.max_consecutive_losses > 10:
            penalty += 0.1

        # Extreme drawdown
        if perf.max_drawdown_pct > self.max_dd * 1.5:
            penalty += 0.15

        # Very low trade count
        if perf.total_trades < self.min_trades * 2:
            penalty += 0.05

        return min(penalty, 0.5)
