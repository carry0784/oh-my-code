"""
PortfolioConstructor — CR-043 Phase 6
Orchestrates portfolio construction from strategy candidates.

Combines correlation analysis, weight optimization, risk budget allocation,
and performance calculation into a single construction pipeline.

Pure computation — no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.services.correlation_analyzer import CorrelationAnalyzer, CorrelationMatrix
from app.services.portfolio_metrics import PortfolioMetricsCalculator, PortfolioPerformanceReport
from app.services.portfolio_optimizer import PortfolioOptimizer, OptimizationConstraints
from app.services.risk_budget_allocator import RiskBudgetAllocator, RiskBudget

logger = get_logger(__name__)


@dataclass
class StrategyAllocation:
    """Single strategy allocation in the portfolio."""

    genome_id: str = ""
    weight: float = 0.0
    risk_budget_pct: float = 0.0
    regime_tag: str = ""


@dataclass
class PortfolioConstructionResult:
    """Complete portfolio construction result."""

    allocations: list[StrategyAllocation] = field(default_factory=list)
    correlation: CorrelationMatrix | None = None
    risk_budget: RiskBudget | None = None
    performance: PortfolioPerformanceReport | None = None
    optimization_method: str = ""
    total_capital: float = 0.0
    strategy_count: int = 0


class PortfolioConstructor:
    """Builds optimized multi-strategy portfolios."""

    def __init__(
        self,
        optimizer: PortfolioOptimizer | None = None,
        correlator: CorrelationAnalyzer | None = None,
        risk_allocator: RiskBudgetAllocator | None = None,
        metrics_calc: PortfolioMetricsCalculator | None = None,
    ):
        self.optimizer = optimizer or PortfolioOptimizer()
        self.correlator = correlator or CorrelationAnalyzer()
        self.risk_allocator = risk_allocator or RiskBudgetAllocator()
        self.metrics_calc = metrics_calc or PortfolioMetricsCalculator()

    def construct(
        self,
        equity_curves: dict[str, list[float]],
        capital: float = 10000.0,
        method: str = "risk_parity",
        constraints: OptimizationConstraints | None = None,
        regime_tags: dict[str, str] | None = None,
    ) -> PortfolioConstructionResult:
        """
        Full portfolio construction pipeline:
        1. Compute correlation matrix
        2. Optimize weights
        3. Allocate risk budgets
        4. Calculate portfolio performance
        """
        result = PortfolioConstructionResult(
            optimization_method=method,
            total_capital=capital,
        )

        if not equity_curves:
            return result

        # 1. Correlation analysis
        result.correlation = self.correlator.compute_from_equity(equity_curves)

        # 2. Convert equity to returns for optimizer
        returns = {}
        for gid, curve in equity_curves.items():
            if len(curve) >= 2:
                rets = []
                for i in range(1, len(curve)):
                    if curve[i - 1] != 0:
                        rets.append((curve[i] - curve[i - 1]) / curve[i - 1])
                    else:
                        rets.append(0.0)
                returns[gid] = rets

        # 3. Optimize weights
        constraints = constraints or OptimizationConstraints()
        if method == "risk_parity":
            weights = self.optimizer.optimize_risk_parity(returns, constraints)
        elif method == "min_variance":
            weights = self.optimizer.optimize_min_variance(returns, constraints)
        elif method == "max_sharpe":
            weights = self.optimizer.optimize_max_sharpe(returns, constraints)
        else:
            weights = self.optimizer.optimize_equal_weight(returns, constraints)

        # 4. Risk budget
        vols = {}
        for gid, rets in returns.items():
            vols[gid] = float(max(abs(r) for r in rets)) if rets else 0.0
        result.risk_budget = self.risk_allocator.allocate(weights, vols)

        # 5. Build allocations
        regime_tags = regime_tags or {}
        for gid, w in weights.items():
            alloc = StrategyAllocation(
                genome_id=gid,
                weight=w,
                risk_budget_pct=result.risk_budget.strategy_budgets.get(gid, 0.0),
                regime_tag=regime_tags.get(gid, ""),
            )
            result.allocations.append(alloc)
        result.strategy_count = len(result.allocations)

        # 6. Portfolio performance
        result.performance = self.metrics_calc.calculate(weights, equity_curves, capital)

        logger.info(
            "portfolio_constructed",
            method=method,
            strategies=result.strategy_count,
            sharpe=round(result.performance.portfolio_sharpe, 4) if result.performance else 0.0,
        )
        return result

    def rebalance_check(
        self,
        target_weights: dict[str, float],
        current_weights: dict[str, float],
        threshold_pct: float = 5.0,
    ) -> bool:
        """Check if rebalancing is needed based on weight drift."""
        for gid in target_weights:
            target = target_weights[gid]
            current = current_weights.get(gid, 0.0)
            drift = abs(target - current) * 100
            if drift > threshold_pct:
                logger.info("rebalance_triggered", genome_id=gid, drift=round(drift, 2))
                return True
        return False
