"""
Budget Evolution Engine -- L18 K-Dexter AOS

Purpose: adjust cost budgets based on performance history.
Proposes limit changes for downstream approval without executing them directly.

Governance: B2 (governance_layer_map.md -- L18)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# ------------------------------------------------------------------ #
# Data models
# ------------------------------------------------------------------ #


@dataclass
class BudgetAdjustment:
    """Proposed adjustment to a single resource budget."""

    resource_type: str  # e.g. "API_CALLS", "USD_COST"
    current_limit: float
    proposed_limit: float
    reason: str
    confidence: float  # 0.0 ~ 1.0


@dataclass
class PerformanceData:
    """Snapshot of recent performance used to drive adjustment proposals."""

    resource_type: str
    average_usage: float  # average usage over the observation window
    peak_usage: float  # highest observed usage
    observation_window: int  # number of periods observed


# ------------------------------------------------------------------ #
# L18 Budget Evolution Engine
# ------------------------------------------------------------------ #


class BudgetEvolutionEngine:
    """
    L18 Budget Evolution Engine.

    Analyses performance history and proposes budget limit adjustments.
    Proposals are returned as BudgetAdjustment dataclasses and must be
    reviewed and applied externally -- this engine never mutates live budgets.

    Usage:
        engine = BudgetEvolutionEngine()
        perf = PerformanceData("API_CALLS", average_usage=750, peak_usage=950,
                               observation_window=7)
        adjustment = engine.propose_adjustment(current_budget=1000, performance_data=perf)
        # adjustment.proposed_limit -> submit for approval
    """

    # If peak/limit ratio exceeds this, propose an increase.
    HEADROOM_THRESHOLD = 0.90
    # If average/limit ratio is below this, propose a decrease.
    SLACK_THRESHOLD = 0.30
    # Default confidence for stub proposals.
    DEFAULT_CONFIDENCE = 0.70

    def __init__(self) -> None:
        self._history: list[BudgetAdjustment] = []

    def propose_adjustment(
        self,
        current_budget: float,
        performance_data: PerformanceData,
    ) -> BudgetAdjustment:
        """
        Propose a budget adjustment based on performance data.

        Logic (stub):
        - Peak >= 90% of current_budget  -> propose 20% increase
        - Average <= 30% of current_budget -> propose 20% decrease
        - Otherwise                        -> no change proposed

        Args:
            current_budget: current limit for the resource type
            performance_data: recent usage statistics

        Returns:
            BudgetAdjustment with proposed_limit and reason
        """
        pd = performance_data
        proposed = current_budget
        reason = "no adjustment needed"
        confidence = self.DEFAULT_CONFIDENCE

        if current_budget > 0:
            peak_ratio = pd.peak_usage / current_budget
            avg_ratio = pd.average_usage / current_budget

            if peak_ratio >= self.HEADROOM_THRESHOLD:
                proposed = round(current_budget * 1.20, 4)
                reason = (
                    f"peak usage {peak_ratio:.0%} of limit over "
                    f"{pd.observation_window} periods; increasing headroom"
                )
                confidence = min(0.90, 0.50 + peak_ratio * 0.40)
            elif avg_ratio <= self.SLACK_THRESHOLD:
                proposed = round(current_budget * 0.80, 4)
                reason = (
                    f"average usage only {avg_ratio:.0%} of limit over "
                    f"{pd.observation_window} periods; reclaiming slack"
                )
                confidence = min(0.85, 0.50 + (1.0 - avg_ratio) * 0.35)

        adjustment = BudgetAdjustment(
            resource_type=pd.resource_type,
            current_limit=current_budget,
            proposed_limit=proposed,
            reason=reason,
            confidence=round(confidence, 4),
        )
        self._history.append(adjustment)
        return adjustment

    def history(self) -> list[BudgetAdjustment]:
        """Return all past proposals (most recent last)."""
        return list(self._history)

    def clear_history(self) -> None:
        """Clear proposal history."""
        self._history.clear()
