"""
PortfolioMetrics — CR-043 Phase 6
Portfolio-level performance metrics and attribution.

Calculates portfolio Sharpe, Sortino, max drawdown, component attribution,
diversification benefit, and effective number of strategies.

Pure computation — no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.core.logging import get_logger

logger = get_logger(__name__)

ANNUAL_FACTOR = 365
RISK_FREE_RATE = 0.04


@dataclass
class PortfolioPerformanceReport:
    """Portfolio-level performance metrics."""
    portfolio_sharpe: float = 0.0
    portfolio_sortino: float = 0.0
    portfolio_max_drawdown_pct: float = 0.0
    portfolio_return_pct: float = 0.0
    portfolio_volatility_pct: float = 0.0
    component_attribution: dict[str, float] = field(default_factory=dict)
    diversification_benefit_pct: float = 0.0
    effective_n_strategies: float = 0.0


class PortfolioMetricsCalculator:
    """Calculates portfolio-level performance metrics."""

    def calculate_portfolio_equity(
        self,
        weights: dict[str, float],
        equity_curves: dict[str, list[float]],
        initial_capital: float = 10000.0,
    ) -> list[float]:
        """
        Compute combined portfolio equity curve from component curves.
        Each component curve is normalized and weighted.
        """
        if not weights or not equity_curves:
            return [initial_capital]

        ids = [gid for gid in weights if gid in equity_curves]
        if not ids:
            return [initial_capital]

        # Normalize each curve to start at 1.0
        min_len = min(len(equity_curves[gid]) for gid in ids)
        if min_len < 2:
            return [initial_capital]

        portfolio = np.zeros(min_len)
        for gid in ids:
            curve = np.array(equity_curves[gid][:min_len])
            normalized = curve / curve[0] if curve[0] != 0 else np.ones(min_len)
            portfolio += weights[gid] * normalized

        return [float(initial_capital * v) for v in portfolio]

    def calculate(
        self,
        weights: dict[str, float],
        equity_curves: dict[str, list[float]],
        initial_capital: float = 10000.0,
    ) -> PortfolioPerformanceReport:
        """Calculate complete portfolio performance metrics."""
        report = PortfolioPerformanceReport()

        portfolio_equity = self.calculate_portfolio_equity(
            weights, equity_curves, initial_capital
        )

        if len(portfolio_equity) < 2:
            return report

        # Portfolio returns
        equity = np.array(portfolio_equity)
        returns = np.diff(equity) / equity[:-1]
        returns = np.nan_to_num(returns, nan=0.0)

        # Basic metrics
        report.portfolio_return_pct = float(
            (equity[-1] - equity[0]) / equity[0] * 100
        )
        report.portfolio_volatility_pct = float(np.std(returns) * np.sqrt(ANNUAL_FACTOR) * 100)

        # Sharpe
        daily_rf = RISK_FREE_RATE / ANNUAL_FACTOR
        excess = returns - daily_rf
        std = float(np.std(excess))
        if std > 0:
            report.portfolio_sharpe = float(
                np.mean(excess) / std * np.sqrt(ANNUAL_FACTOR)
            )

        # Sortino
        downside = returns[returns < daily_rf] - daily_rf
        downside_std = float(np.std(downside)) if len(downside) > 0 else 0.0
        if downside_std > 0:
            report.portfolio_sortino = float(
                np.mean(excess) / downside_std * np.sqrt(ANNUAL_FACTOR)
            )

        # Max drawdown
        peak = np.maximum.accumulate(equity)
        drawdowns = (peak - equity) / peak * 100
        report.portfolio_max_drawdown_pct = float(np.max(drawdowns))

        # Component attribution
        ids = [gid for gid in weights if gid in equity_curves]
        for gid in ids:
            curve = equity_curves[gid]
            if len(curve) >= 2:
                comp_return = (curve[-1] - curve[0]) / curve[0]
                report.component_attribution[gid] = float(
                    weights[gid] * comp_return * 100
                )

        # Diversification benefit
        if len(ids) >= 2:
            weighted_vol_sum = 0.0
            min_len = min(len(equity_curves[gid]) for gid in ids)
            for gid in ids:
                curve = np.array(equity_curves[gid][:min_len])
                comp_rets = np.diff(curve) / curve[:-1]
                comp_rets = np.nan_to_num(comp_rets, nan=0.0)
                weighted_vol_sum += weights[gid] * float(np.std(comp_rets))
            
            port_vol = float(np.std(returns))
            if port_vol > 0:
                report.diversification_benefit_pct = float(
                    (1.0 - port_vol / weighted_vol_sum) * 100
                ) if weighted_vol_sum > 0 else 0.0

        # Effective N (Herfindahl-based)
        w_values = list(weights.values())
        hhi = sum(w ** 2 for w in w_values)
        report.effective_n_strategies = 1.0 / hhi if hhi > 0 else 0.0

        logger.info("portfolio_metrics_calculated",
                     sharpe=round(report.portfolio_sharpe, 4),
                     return_pct=round(report.portfolio_return_pct, 2),
                     max_dd=round(report.portfolio_max_drawdown_pct, 2))
        return report
