"""
Cost Controller -- L29 K-Dexter AOS

Purpose: track resource usage (API calls, compute, budget) and enforce budget limits.
Computes resource_usage_ratio that feeds into Gate G-22.

Output: resource_usage_ratio (float) -> EvaluationContext.resource_usage_ratio -> Gate G-22 (<= 1.0)

Governance: B2 (governance_layer_map.md -- L29)
Gate: G-22 BUDGET_CHECK at VALIDATING[7]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ------------------------------------------------------------------ #
# Data models
# ------------------------------------------------------------------ #


@dataclass
class ResourceBudget:
    """Budget definition for a single resource type."""

    resource_type: str  # "API_CALLS", "COMPUTE_SECONDS", "USD_COST", etc.
    limit: float  # max allowed
    current: float = 0.0  # current usage

    @property
    def usage_ratio(self) -> float:
        if self.limit <= 0:
            return 0.0 if self.current <= 0 else float("inf")
        return self.current / self.limit

    @property
    def remaining(self) -> float:
        return max(0.0, self.limit - self.current)

    @property
    def exceeded(self) -> bool:
        return self.current > self.limit


@dataclass
class CostCheckResult:
    """Result of a budget check."""

    resource_usage_ratio: float  # max ratio across all resources
    budgets: dict[str, float]  # resource_type -> usage_ratio
    exceeded: list[str]  # resource types over budget
    passed_gate: bool  # max ratio <= 1.0
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ------------------------------------------------------------------ #
# L29 Cost Controller
# ------------------------------------------------------------------ #


class CostController:
    """
    L29 Cost Controller.

    Tracks multiple resource budgets and computes the overall
    resource_usage_ratio (max across all resources) for G-22.

    Usage:
        cc = CostController()
        cc.set_budget("API_CALLS", limit=1000)
        cc.set_budget("USD_COST", limit=10.0)
        cc.record_usage("API_CALLS", 50)
        cc.record_usage("USD_COST", 2.5)
        result = cc.check()
        # result.resource_usage_ratio -> feed into EvaluationContext
    """

    def __init__(self) -> None:
        self._budgets: dict[str, ResourceBudget] = {}
        self._last_result: Optional[CostCheckResult] = None

    @property
    def last_result(self) -> Optional[CostCheckResult]:
        return self._last_result

    def set_budget(self, resource_type: str, limit: float) -> None:
        """Set or update budget for a resource type."""
        if resource_type in self._budgets:
            self._budgets[resource_type].limit = limit
        else:
            self._budgets[resource_type] = ResourceBudget(
                resource_type=resource_type,
                limit=limit,
            )

    def record_usage(self, resource_type: str, amount: float) -> None:
        """
        Record resource usage (additive).

        Raises:
            KeyError: if resource_type has no budget set
        """
        self._budgets[resource_type].current += amount

    def reset_usage(self, resource_type: str) -> None:
        """Reset usage counter for a resource type."""
        if resource_type in self._budgets:
            self._budgets[resource_type].current = 0.0

    def reset_all(self) -> None:
        """Reset all usage counters."""
        for b in self._budgets.values():
            b.current = 0.0

    def get_budget(self, resource_type: str) -> Optional[ResourceBudget]:
        """Get budget info for a resource type."""
        return self._budgets.get(resource_type)

    def check(self) -> CostCheckResult:
        """
        Evaluate all budgets and compute resource_usage_ratio.

        The ratio is the MAX across all resource types -- if any
        single resource exceeds its budget, the gate fails.

        Returns:
            CostCheckResult with resource_usage_ratio for G-22
        """
        if not self._budgets:
            result = CostCheckResult(
                resource_usage_ratio=0.0,
                budgets={},
                exceeded=[],
                passed_gate=True,
            )
            self._last_result = result
            return result

        ratios = {rt: b.usage_ratio for rt, b in self._budgets.items()}
        exceeded = [rt for rt, b in self._budgets.items() if b.exceeded]
        max_ratio = max(ratios.values()) if ratios else 0.0

        result = CostCheckResult(
            resource_usage_ratio=round(max_ratio, 4),
            budgets={rt: round(r, 4) for rt, r in ratios.items()},
            exceeded=exceeded,
            passed_gate=max_ratio <= 1.0,
        )
        self._last_result = result
        return result
