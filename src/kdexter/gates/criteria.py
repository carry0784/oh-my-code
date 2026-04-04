"""
Gate Criteria & Verdict — K-Dexter AOS

Data models for quantitative gate evaluation:
  PassCriteria:       threshold definition for a single gate condition
  GateVerdict:        result of evaluating one gate
  GateSuiteResult:    aggregated result of evaluating all gates
  EvaluationContext:  facade over WorkStateContext + runtime engine outputs
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from kdexter.audit.evidence_store import EvidenceBundle


# ─────────────────────────────────────────────────────────────────────────── #
# Pass criteria
# ─────────────────────────────────────────────────────────────────────────── #

@dataclass(frozen=True)
class PassCriteria:
    """
    Quantitative threshold for a gate condition.

    operator semantics:
      "<="  — measured_value <= threshold
      ">="  — measured_value >= threshold
      "=="  — measured_value == threshold
      "!="  — measured_value != threshold
      "is_true"  — measured_value is truthy
      "is_false" — measured_value is falsy
    """
    metric_name: str
    operator: str
    threshold: Any
    unit: str = ""
    description: str = ""

    def evaluate(self, measured: Any) -> bool:
        """Return True if measured value satisfies the criterion."""
        if self.operator == "<=":
            return measured <= self.threshold
        elif self.operator == ">=":
            return measured >= self.threshold
        elif self.operator == "==":
            return measured == self.threshold
        elif self.operator == "!=":
            return measured != self.threshold
        elif self.operator == "is_true":
            return bool(measured)
        elif self.operator == "is_false":
            return not bool(measured)
        raise ValueError(f"Unknown operator: {self.operator!r}")


# ─────────────────────────────────────────────────────────────────────────── #
# Gate verdict
# ─────────────────────────────────────────────────────────────────────────── #

@dataclass
class GateVerdict:
    """Result of evaluating a single gate."""
    gate_id: str
    passed: bool
    measured_value: Any
    criteria: PassCriteria
    evidence: EvidenceBundle
    reason: str = ""
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class GateSuiteResult:
    """Aggregated result from evaluating multiple gates."""
    all_passed: bool
    verdicts: list[GateVerdict] = field(default_factory=list)
    failed_gates: list[GateVerdict] = field(default_factory=list)

    @property
    def failed_gate_ids(self) -> list[str]:
        return [v.gate_id for v in self.failed_gates]


# ─────────────────────────────────────────────────────────────────────────── #
# Evaluation context
# ─────────────────────────────────────────────────────────────────────────── #

@dataclass
class EvaluationContext:
    """
    Facade over WorkStateContext + runtime engine outputs.

    Assembled once at VALIDATING entry and shared across all 10 checks.
    Gate evaluate functions read from this — they never mutate it.
    """
    # Import here to avoid circular import at module level
    from kdexter.state_machine.work_state import WorkStateContext
    work: WorkStateContext

    # L15 Intent Drift Engine output
    drift_score: float = 0.0

    # L19 Trust Decay Engine output
    trust_score: float = 1.0

    # L20 Meta Loop Controller
    loop_counts: dict[str, int] = field(default_factory=dict)

    # L29 Cost Controller
    resource_usage_ratio: float = 0.0

    # L16 Rule Conflict Engine
    conflict_count: int = 0

    # L17 Failure Pattern Memory
    anti_pattern_detected: bool = False

    # L13 Compliance Engine
    constitution_violation_count: int = 0

    # L10 Audit / Evidence Store
    evidence_bundle_count: int = 0
    expected_evidence_count: int = 0

    # L22 Spec Lock System
    spec_mutation_count: int = 0

    # Shadow mode flag — when True, gate failures are logged but not enforced
    shadow_mode: bool = False
