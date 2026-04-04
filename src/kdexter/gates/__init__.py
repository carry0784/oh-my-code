"""
Gates module — K-Dexter AOS v4

G-01~G-08 (Phase 4 Shadow Validation) and G-16~G-27 (v4 quantitative criteria).
G-09~G-15 reserved for Phase 4 expansion. G-28~G-30 reserved.
"""

from kdexter.gates.criteria import (
    EvaluationContext,
    GateSuiteResult,
    GateVerdict,
    PassCriteria,
)
from kdexter.gates.gate_evaluator import GateEvaluator
from kdexter.gates.gate_hooks import build_evaluation_context, create_gate_hooks
from kdexter.gates.gate_registry import (
    ALL_GATES,
    GATE_MAP,
    GATES_BY_CHECK,
    Gate,
    GatePhase,
    GateStatus,
)

__all__ = [
    "ALL_GATES",
    "EvaluationContext",
    "GATE_MAP",
    "GATES_BY_CHECK",
    "Gate",
    "GateEvaluator",
    "GatePhase",
    "GateStatus",
    "GateSuiteResult",
    "GateVerdict",
    "PassCriteria",
    "build_evaluation_context",
    "create_gate_hooks",
]
