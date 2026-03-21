"""
Gate Hooks — K-Dexter AOS v4

Bridge between GateEvaluator and MainLoopHooks.
Converts gate evaluations into the (passed, reason) tuple interface
that MainLoop's VALIDATING step expects.

Usage:
    from kdexter.gates.gate_hooks import create_gate_hooks

    evaluator = GateEvaluator(ALL_GATES)
    hooks = create_gate_hooks(evaluator)
    loop = MainLoop(..., hooks=hooks)
"""
from __future__ import annotations

from typing import Optional

from kdexter.gates.criteria import EvaluationContext
from kdexter.gates.gate_evaluator import GateEvaluator
from kdexter.loops.main_loop import MainLoopHooks
from kdexter.state_machine.work_state import ValidatingCheck, WorkStateContext


def build_evaluation_context(
    work: WorkStateContext,
    *,
    drift_score: float = 0.0,
    trust_score: float = 1.0,
    loop_counts: Optional[dict[str, int]] = None,
    resource_usage_ratio: float = 0.0,
    conflict_count: int = 0,
    anti_pattern_detected: bool = False,
    constitution_violation_count: int = 0,
    evidence_bundle_count: int = 0,
    expected_evidence_count: int = 0,
    spec_mutation_count: int = 0,
    shadow_mode: bool = False,
) -> EvaluationContext:
    """
    Factory: build EvaluationContext from WorkStateContext + engine outputs.

    Called once at VALIDATING entry. The returned context is shared across
    all 10 VALIDATING checks within a single cycle — it is a snapshot.
    """
    return EvaluationContext(
        work=work,
        drift_score=drift_score,
        trust_score=trust_score,
        loop_counts=loop_counts or {},
        resource_usage_ratio=resource_usage_ratio,
        conflict_count=conflict_count,
        anti_pattern_detected=anti_pattern_detected,
        constitution_violation_count=constitution_violation_count,
        evidence_bundle_count=evidence_bundle_count,
        expected_evidence_count=expected_evidence_count,
        spec_mutation_count=spec_mutation_count,
        shadow_mode=shadow_mode,
    )


def create_gate_hooks(
    evaluator: GateEvaluator,
    *,
    drift_score: float = 0.0,
    trust_score: float = 1.0,
    loop_counts: Optional[dict[str, int]] = None,
    resource_usage_ratio: float = 0.0,
    conflict_count: int = 0,
    anti_pattern_detected: bool = False,
    constitution_violation_count: int = 0,
    evidence_bundle_count: int = 0,
    expected_evidence_count: int = 0,
    spec_mutation_count: int = 0,
    shadow_mode: bool = False,
) -> MainLoopHooks:
    """
    Create MainLoopHooks wired to a GateEvaluator.

    Engine output values are captured at creation time and used for all
    subsequent VALIDATING checks within the cycle. For dynamic values,
    use create_gate_hooks_dynamic() with engine references instead.
    """

    def _make_check(check: ValidatingCheck):
        async def _check(ctx: WorkStateContext) -> tuple[bool, str]:
            eval_ctx = build_evaluation_context(
                ctx,
                drift_score=drift_score,
                trust_score=trust_score,
                loop_counts=loop_counts,
                resource_usage_ratio=resource_usage_ratio,
                conflict_count=conflict_count,
                anti_pattern_detected=anti_pattern_detected,
                constitution_violation_count=constitution_violation_count,
                evidence_bundle_count=evidence_bundle_count,
                expected_evidence_count=expected_evidence_count,
                spec_mutation_count=spec_mutation_count,
                shadow_mode=shadow_mode,
            )
            return evaluator.evaluate_by_check(check, eval_ctx)
        return _check

    return MainLoopHooks(
        check_forbidden=_make_check(ValidatingCheck.FORBIDDEN_CHECK),
        check_mandatory=_make_check(ValidatingCheck.MANDATORY_CHECK),
        check_compliance=_make_check(ValidatingCheck.COMPLIANCE_CHECK),
        check_drift=_make_check(ValidatingCheck.DRIFT_CHECK),
        check_conflict=_make_check(ValidatingCheck.CONFLICT_CHECK),
        check_pattern=_make_check(ValidatingCheck.PATTERN_CHECK),
        check_budget=_make_check(ValidatingCheck.BUDGET_CHECK),
        check_trust=_make_check(ValidatingCheck.TRUST_CHECK),
        check_loop=_make_check(ValidatingCheck.LOOP_CHECK),
        check_lock=_make_check(ValidatingCheck.LOCK_CHECK),
    )
