"""
Evaluation Engine — L7
K-Dexter AOS v4

Evaluates strategy performance after execution cycles.
Feeds results into the Self-Improvement (L9) and Evolution (L14) loops.

A (Runtime Execution) layer, B2-approved.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class EvaluationMetric:
    name: str
    value: float
    benchmark: float = 0.0
    passed: bool = True


@dataclass
class EvaluationResult:
    eval_id: str
    strategy_id: str
    cycle_id: str
    metrics: list[EvaluationMetric] = field(default_factory=list)
    overall_score: float = 0.0
    passed: bool = True
    evaluated_at: datetime = field(default_factory=datetime.utcnow)


class EvaluationEngine:
    """
    L7 Evaluation Engine.

    Scores strategy performance and determines whether cycles met objectives.
    """

    def __init__(self) -> None:
        self._results: dict[str, EvaluationResult] = {}

    def evaluate(
        self,
        eval_id: str,
        strategy_id: str,
        cycle_id: str,
        metrics: Optional[list[EvaluationMetric]] = None,
    ) -> EvaluationResult:
        metrics = metrics or []
        overall = 0.0
        if metrics:
            overall = sum(m.value for m in metrics) / len(metrics)
        passed = all(m.passed for m in metrics) if metrics else True
        result = EvaluationResult(
            eval_id=eval_id,
            strategy_id=strategy_id,
            cycle_id=cycle_id,
            metrics=metrics,
            overall_score=round(overall, 4),
            passed=passed,
        )
        self._results[eval_id] = result
        return result

    def get(self, eval_id: str) -> Optional[EvaluationResult]:
        return self._results.get(eval_id)

    def list_for_strategy(self, strategy_id: str) -> list[EvaluationResult]:
        return [r for r in self._results.values()
                if r.strategy_id == strategy_id]

    def average_score(self, strategy_id: str) -> float:
        results = self.list_for_strategy(strategy_id)
        if not results:
            return 0.0
        return sum(r.overall_score for r in results) / len(results)

    def list_all(self) -> list[EvaluationResult]:
        return list(self._results.values())
