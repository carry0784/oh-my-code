"""
RiskBudgetAllocator — CR-043 Phase 6
Risk budget allocation across strategies.

Distributes a total risk budget (max portfolio drawdown %) across
strategies based on their weights and volatility contributions.

Pure computation — no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RiskBudget:
    """Risk budget allocation result."""
    total_risk_pct: float = 20.0
    strategy_budgets: dict[str, float] = field(default_factory=dict)
    regime_budgets: dict[str, float] = field(default_factory=dict)


class RiskBudgetAllocator:
    """Allocates risk budget across strategies."""

    def __init__(self, total_risk_pct: float = 20.0):
        self.total_risk_pct = total_risk_pct

    def allocate(
        self,
        weights: dict[str, float],
        volatilities: dict[str, float] | None = None,
    ) -> RiskBudget:
        """
        Allocate risk budget proportional to portfolio weights.
        
        If volatilities provided, risk budget is weight-adjusted by vol
        so higher-vol strategies get proportionally less risk budget.
        """
        budget = RiskBudget(total_risk_pct=self.total_risk_pct)

        if not weights:
            return budget

        if volatilities:
            # Vol-adjusted allocation: lower vol -> more budget per unit weight
            inv_vols = {}
            for gid, w in weights.items():
                vol = volatilities.get(gid, 1.0)
                inv_vols[gid] = w / vol if vol > 1e-10 else w

            total_inv = sum(inv_vols.values())
            for gid in weights:
                budget.strategy_budgets[gid] = (
                    self.total_risk_pct * inv_vols[gid] / total_inv
                ) if total_inv > 0 else 0.0
        else:
            # Simple proportional allocation
            for gid, w in weights.items():
                budget.strategy_budgets[gid] = self.total_risk_pct * w

        logger.info("risk_budget_allocated",
                     total=self.total_risk_pct,
                     strategies=len(budget.strategy_budgets))
        return budget

    def check_breach(
        self,
        budget: RiskBudget,
        current_drawdowns: dict[str, float],
    ) -> list[str]:
        """
        Check which strategies have breached their risk budget.
        
        Args:
            budget: Allocated risk budgets
            current_drawdowns: genome_id -> current drawdown %
            
        Returns:
            List of genome_ids that have breached their budget
        """
        breached = []
        for gid, dd in current_drawdowns.items():
            allowed = budget.strategy_budgets.get(gid, 0.0)
            if dd > allowed:
                breached.append(gid)
                logger.warning("risk_budget_breach",
                             genome_id=gid,
                             drawdown=round(dd, 2),
                             budget=round(allowed, 2))
        return breached

    def allocate_by_regime(
        self,
        regime_weights: dict[str, float],
    ) -> RiskBudget:
        """Allocate risk budget across market regimes."""
        budget = RiskBudget(total_risk_pct=self.total_risk_pct)
        
        total_w = sum(regime_weights.values())
        if total_w > 0:
            for regime, w in regime_weights.items():
                budget.regime_budgets[regime] = self.total_risk_pct * w / total_w

        return budget
