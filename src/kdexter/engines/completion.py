"""
Completion Engine -- L21 K-Dexter AOS

Purpose: track and evaluate completion of work items against defined criteria.
Computes completion_score that feeds into Gate G-25 and satisfies M-16.

Output: completion_score (float) -> WorkStateContext.completion_score -> Gate G-25

Governance: B2 (governance_layer_map.md -- L21)
Gate: G-25 COMPLETION_CHECK at VERIFY state
Mandatory: M-16 (completion criteria must be met before promotion)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ------------------------------------------------------------------ #
# Data models
# ------------------------------------------------------------------ #


@dataclass
class CompletionCriterion:
    """A single criterion that must be satisfied for completion."""

    criterion_id: str
    description: str
    weight: float = 1.0  # relative weight in score calculation
    satisfied: bool = False
    evidence: str = ""  # what proved this criterion was met

    def satisfy(self, evidence: str = "") -> None:
        self.satisfied = True
        self.evidence = evidence


@dataclass
class CompletionCheckResult:
    """Result of a completion evaluation."""

    completion_score: float  # 0.0 ~ 1.0 weighted score
    total_criteria: int
    satisfied_criteria: int
    unsatisfied: list[str]  # IDs of unsatisfied criteria
    passed_gate: bool  # score >= threshold
    threshold: float
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ------------------------------------------------------------------ #
# L21 Completion Engine
# ------------------------------------------------------------------ #


class CompletionEngine:
    """
    L21 Completion Engine.

    Manages completion criteria for a work item and evaluates
    the weighted completion score against a configurable threshold.

    M-16: All defined criteria must be checked before work can proceed
    past VERIFY state. Gate G-25 enforces completion_score >= threshold.

    Usage:
        engine = CompletionEngine(threshold=0.8)
        engine.add_criterion(CompletionCriterion("C-1", "Tests pass"))
        engine.add_criterion(CompletionCriterion("C-2", "Risk check OK"))
        engine.satisfy("C-1", evidence="24/24 tests passed")
        result = engine.check()
        # result.completion_score -> feed into WorkStateContext
    """

    def __init__(self, threshold: float = 0.8) -> None:
        self._criteria: dict[str, CompletionCriterion] = {}
        self._threshold = threshold
        self._last_result: Optional[CompletionCheckResult] = None

    @property
    def threshold(self) -> float:
        return self._threshold

    @threshold.setter
    def threshold(self, value: float) -> None:
        self._threshold = max(0.0, min(1.0, value))

    @property
    def last_result(self) -> Optional[CompletionCheckResult]:
        return self._last_result

    def add_criterion(self, criterion: CompletionCriterion) -> None:
        """Add a completion criterion."""
        self._criteria[criterion.criterion_id] = criterion

    def remove_criterion(self, criterion_id: str) -> None:
        """Remove a completion criterion."""
        self._criteria.pop(criterion_id, None)

    def satisfy(self, criterion_id: str, evidence: str = "") -> None:
        """
        Mark a criterion as satisfied.

        Raises:
            KeyError: if criterion_id not found
        """
        self._criteria[criterion_id].satisfy(evidence)

    def reset(self, criterion_id: str) -> None:
        """Reset a criterion to unsatisfied."""
        if criterion_id in self._criteria:
            self._criteria[criterion_id].satisfied = False
            self._criteria[criterion_id].evidence = ""

    def reset_all(self) -> None:
        """Reset all criteria to unsatisfied."""
        for c in self._criteria.values():
            c.satisfied = False
            c.evidence = ""

    def check(self) -> CompletionCheckResult:
        """
        Evaluate completion score against threshold.

        Score = sum(satisfied weights) / sum(all weights)
        If no criteria defined, score = 1.0 (vacuously complete).

        Returns:
            CompletionCheckResult with completion_score for G-25
        """
        if not self._criteria:
            result = CompletionCheckResult(
                completion_score=1.0,
                total_criteria=0,
                satisfied_criteria=0,
                unsatisfied=[],
                passed_gate=True,
                threshold=self._threshold,
            )
            self._last_result = result
            return result

        total_weight = sum(c.weight for c in self._criteria.values())
        satisfied_weight = sum(c.weight for c in self._criteria.values() if c.satisfied)

        score = satisfied_weight / total_weight if total_weight > 0 else 0.0
        unsatisfied = [c.criterion_id for c in self._criteria.values() if not c.satisfied]

        result = CompletionCheckResult(
            completion_score=round(score, 4),
            total_criteria=len(self._criteria),
            satisfied_criteria=len(self._criteria) - len(unsatisfied),
            unsatisfied=unsatisfied,
            passed_gate=score >= self._threshold,
            threshold=self._threshold,
        )
        self._last_result = result
        return result

    def criteria_list(self) -> list[CompletionCriterion]:
        """Return all criteria."""
        return list(self._criteria.values())
