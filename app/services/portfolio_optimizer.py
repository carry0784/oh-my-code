"""
PortfolioOptimizer — CR-043 Phase 6
Portfolio weight optimization using risk-parity, min-variance, and max-Sharpe.

Computes optimal weight allocations for a set of strategies given
their historical return series and constraints.

Pure computation — no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class OptimizationConstraints:
    """Constraints for portfolio optimization."""
    max_weight: float = 0.4
    min_weight: float = 0.02
    max_strategies: int = 10
    target_volatility: float | None = None


class PortfolioOptimizer:
    """Computes optimal portfolio weights."""

    def optimize_equal_weight(
        self,
        returns: dict[str, list[float]],
        constraints: OptimizationConstraints | None = None,
    ) -> dict[str, float]:
        """Equal weight allocation (1/N portfolio)."""
        n = len(returns)
        if n == 0:
            return {}
        weight = 1.0 / n
        return {gid: weight for gid in returns}

    def optimize_risk_parity(
        self,
        returns: dict[str, list[float]],
        constraints: OptimizationConstraints | None = None,
    ) -> dict[str, float]:
        """
        Risk parity: weight inversely proportional to volatility.
        Each strategy contributes equal risk to the portfolio.
        """
        constraints = constraints or OptimizationConstraints()
        
        if len(returns) == 0:
            return {}
        if len(returns) == 1:
            gid = list(returns.keys())[0]
            return {gid: 1.0}

        ids = list(returns.keys())
        min_len = min(len(returns[gid]) for gid in ids)
        if min_len < 2:
            return self.optimize_equal_weight(returns)

        # Calculate volatilities
        vols = {}
        for gid in ids:
            vols[gid] = float(np.std(returns[gid][:min_len]))

        # Inverse volatility weighting
        inv_vols = {}
        for gid in ids:
            inv_vols[gid] = 1.0 / vols[gid] if vols[gid] > 1e-10 else 1.0

        total_inv = sum(inv_vols.values())
        weights = {gid: inv_vols[gid] / total_inv for gid in ids}

        # Apply constraints
        weights = self._apply_constraints(weights, constraints)

        logger.info("risk_parity_optimized",
                     n_strategies=len(weights),
                     max_w=round(max(weights.values()), 4),
                     min_w=round(min(weights.values()), 4))
        return weights

    def optimize_min_variance(
        self,
        returns: dict[str, list[float]],
        constraints: OptimizationConstraints | None = None,
    ) -> dict[str, float]:
        """
        Minimum variance portfolio using analytical solution.
        For simplicity, uses inverse-variance weighting (diagonal covariance).
        """
        constraints = constraints or OptimizationConstraints()

        if len(returns) == 0:
            return {}
        if len(returns) == 1:
            gid = list(returns.keys())[0]
            return {gid: 1.0}

        ids = list(returns.keys())
        min_len = min(len(returns[gid]) for gid in ids)
        if min_len < 2:
            return self.optimize_equal_weight(returns)

        # Inverse variance weighting
        inv_vars = {}
        for gid in ids:
            var = float(np.var(returns[gid][:min_len]))
            inv_vars[gid] = 1.0 / var if var > 1e-10 else 1.0

        total = sum(inv_vars.values())
        weights = {gid: inv_vars[gid] / total for gid in ids}

        weights = self._apply_constraints(weights, constraints)

        logger.info("min_variance_optimized", n_strategies=len(weights))
        return weights

    def optimize_max_sharpe(
        self,
        returns: dict[str, list[float]],
        constraints: OptimizationConstraints | None = None,
        risk_free_rate: float = 0.04,
    ) -> dict[str, float]:
        """
        Max Sharpe ratio portfolio.
        Uses return/vol ratio weighting as an approximation.
        """
        constraints = constraints or OptimizationConstraints()

        if len(returns) == 0:
            return {}
        if len(returns) == 1:
            gid = list(returns.keys())[0]
            return {gid: 1.0}

        ids = list(returns.keys())
        min_len = min(len(returns[gid]) for gid in ids)
        if min_len < 2:
            return self.optimize_equal_weight(returns)

        daily_rf = risk_free_rate / 365

        # Sharpe-like ratio for each strategy
        ratios = {}
        for gid in ids:
            rets = returns[gid][:min_len]
            mean_ret = float(np.mean(rets))
            vol = float(np.std(rets))
            excess = mean_ret - daily_rf
            ratios[gid] = max(excess / vol, 0.0) if vol > 1e-10 else 0.0

        total = sum(ratios.values())
        if total <= 0:
            return self.optimize_equal_weight(returns)

        weights = {gid: ratios[gid] / total for gid in ids}

        weights = self._apply_constraints(weights, constraints)

        logger.info("max_sharpe_optimized", n_strategies=len(weights))
        return weights

    def _apply_constraints(
        self,
        weights: dict[str, float],
        constraints: OptimizationConstraints,
    ) -> dict[str, float]:
        """Apply weight constraints and re-normalize iteratively."""
        # Iterative capping: cap, re-normalize uncapped, repeat until stable
        for _ in range(10):
            capped = {}
            uncapped = {}
            capped_total = 0.0
            for gid, w in weights.items():
                if w > constraints.max_weight:
                    capped[gid] = constraints.max_weight
                    capped_total += constraints.max_weight
                else:
                    uncapped[gid] = w

            if not capped:
                break  # No caps needed

            remaining = 1.0 - capped_total
            uncapped_total = sum(uncapped.values())
            if uncapped_total > 0 and remaining > 0:
                for gid in uncapped:
                    uncapped[gid] = uncapped[gid] / uncapped_total * remaining
            weights = {**capped, **uncapped}

        # Floor min weight — drop if below
        filtered = {gid: w for gid, w in weights.items() if w >= constraints.min_weight}
        if not filtered:
            filtered = weights  # Keep all if none pass min

        # Final re-normalize to sum to 1.0
        total = sum(filtered.values())
        if total > 0:
            filtered = {gid: w / total for gid, w in filtered.items()}

        return filtered
