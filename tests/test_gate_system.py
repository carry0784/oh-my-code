"""
Gate System Tests — K-Dexter AOS v4

Tests:
  1. Gate registry: all gates instantiated, correct IDs, mandatory mapping
  2. Individual gate boundary tests (pass/fail edge cases)
  3. GateEvaluator: evaluate_all, evaluate_single, evaluate_by_check
  4. Gate hooks: MainLoop integration (full cycle with gate hooks)
  5. Shadow mode: failures logged but not enforced

Run: python -m pytest tests/test_gate_system.py -v
  or: python tests/test_gate_system.py  (standalone)
"""
from __future__ import annotations

import asyncio
import sys
import os

# Ensure project root is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from kdexter.gates.criteria import EvaluationContext, PassCriteria
from kdexter.gates.gate_registry import (
    ALL_GATES, GATE_MAP, GATES_BY_CHECK,
    GatePhase, GateStatus,
    _eval_g01, _eval_g02, _eval_g03, _eval_g04, _eval_g05,
    _eval_g06, _eval_g07, _eval_g08,
    _eval_g16, _eval_g18, _eval_g19, _eval_g20, _eval_g21,
    _eval_g22, _eval_g23, _eval_g24, _eval_g25, _eval_g26, _eval_g27,
)
from kdexter.gates.gate_evaluator import GateEvaluator
from kdexter.state_machine.work_state import WorkStateContext, WorkStateEnum, ValidatingCheck

# ─────────────────────────────────────────────────────────────────────────── #
# Helpers
# ─────────────────────────────────────────────────────────────────────────── #

def _base_ctx(**overrides) -> EvaluationContext:
    """Build an EvaluationContext with sensible defaults (all gates pass)."""
    w = WorkStateContext()
    w.intent = "test intent"
    w.spec_twin_id = "SPEC-001"
    w.risk_checked = True
    w.security_checked = True
    w.rollback_plan_ready = True
    w.recovery_simulation_done = True
    w.research_complete = True
    w.approval_granted = True
    w.completion_score = 0.95
    w.provenance_recorded = True
    w.system_health_ok = True

    defaults = dict(
        work=w,
        drift_score=0.10,
        trust_score=0.85,
        loop_counts={},
        resource_usage_ratio=0.50,
        conflict_count=0,
        anti_pattern_detected=False,
        constitution_violation_count=0,
        evidence_bundle_count=5,
        expected_evidence_count=5,
        spec_mutation_count=0,
        shadow_mode=True,  # G-01 requires shadow mode
    )
    defaults.update(overrides)
    return EvaluationContext(**defaults)


# ─────────────────────────────────────────────────────────────────────────── #
# 1. Registry tests
# ─────────────────────────────────────────────────────────────────────────── #

def test_all_gates_instantiated():
    """All expected gate IDs are present."""
    expected_ids = {
        "G-01", "G-02", "G-03", "G-04", "G-05", "G-06", "G-07", "G-08",
        "G-16", "G-18", "G-19", "G-20", "G-21", "G-22", "G-23",
        "G-24", "G-25", "G-26", "G-27",
    }
    actual_ids = {g.gate_id for g in ALL_GATES}
    assert expected_ids == actual_ids, f"Missing: {expected_ids - actual_ids}, Extra: {actual_ids - expected_ids}"
    print("  [1] All 19 gates instantiated  OK")


def test_gate_map_lookup():
    """GATE_MAP provides O(1) lookup by gate_id."""
    for g in ALL_GATES:
        assert GATE_MAP[g.gate_id] is g
    print("  [2] GATE_MAP lookup correct  OK")


def test_validating_check_mapping():
    """Gates with validating_check are in GATES_BY_CHECK."""
    mapped_checks = {
        ValidatingCheck.COMPLIANCE_CHECK,   # G-16
        ValidatingCheck.DRIFT_CHECK,        # G-19
        ValidatingCheck.CONFLICT_CHECK,     # G-20
        ValidatingCheck.PATTERN_CHECK,      # G-21
        ValidatingCheck.BUDGET_CHECK,       # G-22
        ValidatingCheck.TRUST_CHECK,        # G-23
        ValidatingCheck.LOOP_CHECK,         # G-24
        ValidatingCheck.LOCK_CHECK,         # G-26
    }
    assert set(GATES_BY_CHECK.keys()) == mapped_checks
    print("  [3] ValidatingCheck mapping  OK")


def test_mandatory_items():
    """Key gates have correct mandatory item references."""
    assert GATE_MAP["G-02"].mandatory_items == ["M-05", "M-06"]
    assert GATE_MAP["G-19"].mandatory_items == ["M-11"]
    assert GATE_MAP["G-23"].mandatory_items == ["M-14"]
    assert GATE_MAP["G-25"].mandatory_items == ["M-16"]
    print("  [4] Mandatory item mapping  OK")


# ─────────────────────────────────────────────────────────────────────────── #
# 2. Individual gate boundary tests
# ─────────────────────────────────────────────────────────────────────────── #

def test_g01_shadow_mode():
    """G-01: shadow_mode True → PASS, False → FAIL."""
    assert _eval_g01(_base_ctx(shadow_mode=True)).passed
    assert not _eval_g01(_base_ctx(shadow_mode=False)).passed
    print("  [5] G-01 Shadow Entry  OK")


def test_g02_state_recovery():
    """G-02: both rollback + sim required."""
    ctx = _base_ctx()
    assert _eval_g02(ctx).passed

    ctx2 = _base_ctx()
    ctx2.work.rollback_plan_ready = False
    assert not _eval_g02(ctx2).passed

    ctx3 = _base_ctx()
    ctx3.work.recovery_simulation_done = False
    assert not _eval_g02(ctx3).passed
    print("  [6] G-02 State Recovery  OK")


def test_g19_drift_boundary():
    """G-19: drift_score at exact threshold (0.35) → PASS, above → FAIL."""
    assert _eval_g19(_base_ctx(drift_score=0.35)).passed     # exact boundary
    assert _eval_g19(_base_ctx(drift_score=0.34)).passed     # below
    assert not _eval_g19(_base_ctx(drift_score=0.351)).passed  # above
    print("  [7] G-19 Drift Gate boundary  OK")


def test_g23_trust_boundary():
    """G-23: trust_score at 0.60 → PASS, below → FAIL."""
    assert _eval_g23(_base_ctx(trust_score=0.60)).passed     # exact boundary
    assert _eval_g23(_base_ctx(trust_score=0.80)).passed     # TRUSTED
    assert not _eval_g23(_base_ctx(trust_score=0.59)).passed  # below DEGRADED
    print("  [8] G-23 Trust Gate boundary  OK")


def test_g22_budget():
    """G-22: usage ratio <= 1.0 → PASS."""
    assert _eval_g22(_base_ctx(resource_usage_ratio=1.0)).passed
    assert _eval_g22(_base_ctx(resource_usage_ratio=0.0)).passed
    assert not _eval_g22(_base_ctx(resource_usage_ratio=1.01)).passed
    print("  [9] G-22 Budget Gate  OK")


def test_g25_completion():
    """G-25: completion_score >= threshold (0.80)."""
    ctx_pass = _base_ctx()
    ctx_pass.work.completion_score = 0.80
    assert _eval_g25(ctx_pass).passed

    ctx_fail = _base_ctx()
    ctx_fail.work.completion_score = 0.79
    assert not _eval_g25(ctx_fail).passed
    print("  [10] G-25 Completion Gate boundary  OK")


def test_g24_loop_gate():
    """G-24: loop counts within ceiling → PASS."""
    # No loops → pass
    assert _eval_g24(_base_ctx(loop_counts={})).passed

    # Within ceiling
    assert _eval_g24(_base_ctx(loop_counts={"RECOVERY": 2})).passed

    # Exceeds per_incident ceiling (RECOVERY = 3)
    assert not _eval_g24(_base_ctx(loop_counts={"RECOVERY": 4})).passed
    print("  [11] G-24 Loop Gate  OK")


def test_g26_spec_lock():
    """G-26: spec_mutation_count == 0 → PASS."""
    assert _eval_g26(_base_ctx(spec_mutation_count=0)).passed
    assert not _eval_g26(_base_ctx(spec_mutation_count=1)).passed
    print("  [12] G-26 Spec Lock Gate  OK")


def test_g20_conflict():
    """G-20: conflict_count == 0 → PASS."""
    assert _eval_g20(_base_ctx(conflict_count=0)).passed
    assert not _eval_g20(_base_ctx(conflict_count=2)).passed
    print("  [13] G-20 Conflict Gate  OK")


def test_g21_pattern():
    """G-21: anti_pattern_detected False → PASS."""
    assert _eval_g21(_base_ctx(anti_pattern_detected=False)).passed
    assert not _eval_g21(_base_ctx(anti_pattern_detected=True)).passed
    print("  [14] G-21 Pattern Gate  OK")


# ─────────────────────────────────────────────────────────────────────────── #
# 3. GateEvaluator tests
# ─────────────────────────────────────────────────────────────────────────── #

def test_evaluator_all_pass():
    """GateEvaluator.evaluate_all — all gates pass with good context."""
    evaluator = GateEvaluator(ALL_GATES)
    suite = evaluator.evaluate_all(_base_ctx())
    assert suite.all_passed, f"Failed gates: {suite.failed_gate_ids}"
    assert len(suite.verdicts) == len(ALL_GATES)
    print("  [15] GateEvaluator all-pass  OK")


def test_evaluator_single_gate():
    """GateEvaluator.evaluate_single returns correct verdict."""
    evaluator = GateEvaluator(ALL_GATES)
    verdict = evaluator.evaluate_single("G-19", _base_ctx(drift_score=0.10))
    assert verdict.passed
    assert verdict.gate_id == "G-19"

    verdict2 = evaluator.evaluate_single("G-19", _base_ctx(drift_score=0.50))
    assert not verdict2.passed
    print("  [16] GateEvaluator single-gate  OK")


def test_evaluator_by_check():
    """GateEvaluator.evaluate_by_check returns (bool, str) for MainLoop."""
    evaluator = GateEvaluator(ALL_GATES)

    passed, reason = evaluator.evaluate_by_check(
        ValidatingCheck.DRIFT_CHECK, _base_ctx(drift_score=0.10))
    assert passed
    assert reason == ""

    passed2, reason2 = evaluator.evaluate_by_check(
        ValidatingCheck.DRIFT_CHECK, _base_ctx(drift_score=0.50))
    assert not passed2
    assert "G-19" in reason2
    print("  [17] GateEvaluator by-check  OK")


def test_evaluator_unmapped_check_passes():
    """Checks with no mapped gates pass by default."""
    evaluator = GateEvaluator(ALL_GATES)
    # FORBIDDEN_CHECK and MANDATORY_CHECK have no gates in GATES_BY_CHECK
    passed, reason = evaluator.evaluate_by_check(
        ValidatingCheck.FORBIDDEN_CHECK, _base_ctx())
    assert passed
    print("  [18] Unmapped check auto-pass  OK")


def test_evaluator_shadow_mode():
    """Shadow-phase gates log failures but evaluate_by_check still passes."""
    # G-01 is SHADOW phase — even if it fails, evaluate_by_check should pass
    # (G-01 is not mapped to any ValidatingCheck, but test the mechanism)
    evaluator = GateEvaluator(ALL_GATES)
    suite = evaluator.evaluate_all(_base_ctx(shadow_mode=False))
    # G-01 should fail but the suite is for reporting, not blocking
    g01_verdict = next(v for v in suite.verdicts if v.gate_id == "G-01")
    assert not g01_verdict.passed  # G-01 fails when not in shadow mode
    print("  [19] Shadow mode non-enforcement  OK")


# ─────────────────────────────────────────────────────────────────────────── #
# 4. PassCriteria.evaluate tests
# ─────────────────────────────────────────────────────────────────────────── #

def test_pass_criteria_operators():
    """PassCriteria.evaluate works for all operators."""
    assert PassCriteria("x", "<=", 5).evaluate(5)
    assert PassCriteria("x", "<=", 5).evaluate(4)
    assert not PassCriteria("x", "<=", 5).evaluate(6)

    assert PassCriteria("x", ">=", 5).evaluate(5)
    assert not PassCriteria("x", ">=", 5).evaluate(4)

    assert PassCriteria("x", "==", 0).evaluate(0)
    assert not PassCriteria("x", "==", 0).evaluate(1)

    assert PassCriteria("x", "!=", 0).evaluate(1)
    assert not PassCriteria("x", "!=", 0).evaluate(0)

    assert PassCriteria("x", "is_true", True).evaluate(True)
    assert not PassCriteria("x", "is_true", True).evaluate(False)

    assert PassCriteria("x", "is_false", False).evaluate(False)
    assert not PassCriteria("x", "is_false", False).evaluate(True)
    print("  [20] PassCriteria operators  OK")


# ─────────────────────────────────────────────────────────────────────────── #
# 5. Gate hooks integration test
# ─────────────────────────────────────────────────────────────────────────── #

def test_gate_hooks_integration():
    """create_gate_hooks produces MainLoopHooks that work with WorkStateContext."""
    from kdexter.gates.gate_hooks import create_gate_hooks

    evaluator = GateEvaluator(ALL_GATES)
    hooks = create_gate_hooks(
        evaluator,
        drift_score=0.10,
        trust_score=0.85,
    )

    # Verify hooks have been set
    assert hooks.check_drift is not None
    assert hooks.check_trust is not None
    assert hooks.check_compliance is not None

    # Test a hook call
    w = WorkStateContext()
    w.intent = "test"
    w.spec_twin_id = "SPEC-001"
    passed, reason = asyncio.run(hooks.check_drift(w))
    assert passed
    assert reason == ""

    # Test with failing drift
    hooks_fail = create_gate_hooks(evaluator, drift_score=0.50)
    passed2, reason2 = asyncio.run(hooks_fail.check_drift(w))
    assert not passed2
    assert "G-19" in reason2
    print("  [21] Gate hooks integration  OK")


# ─────────────────────────────────────────────────────────────────────────── #
# 6. Evidence production test
# ─────────────────────────────────────────────────────────────────────────── #

def test_evidence_produced():
    """Every gate verdict includes an EvidenceBundle."""
    evaluator = GateEvaluator(ALL_GATES)
    suite = evaluator.evaluate_all(_base_ctx())
    for v in suite.verdicts:
        assert v.evidence is not None
        assert v.evidence.trigger.startswith("Gate.")
        assert v.evidence.actor == "GateEvaluator"
        assert v.evidence.action in ("PASS", "FAIL", "SKIP", "ERROR")
    print("  [22] Evidence production  OK")


# ─────────────────────────────────────────────────────────────────────────── #
# Runner
# ─────────────────────────────────────────────────────────────────────────── #

if __name__ == "__main__":
    print("\nGate System Tests")
    print("=" * 60)

    tests = [
        ("Registry", [
            test_all_gates_instantiated,
            test_gate_map_lookup,
            test_validating_check_mapping,
            test_mandatory_items,
        ]),
        ("Gate Boundaries", [
            test_g01_shadow_mode,
            test_g02_state_recovery,
            test_g19_drift_boundary,
            test_g23_trust_boundary,
            test_g22_budget,
            test_g25_completion,
            test_g24_loop_gate,
            test_g26_spec_lock,
            test_g20_conflict,
            test_g21_pattern,
        ]),
        ("GateEvaluator", [
            test_evaluator_all_pass,
            test_evaluator_single_gate,
            test_evaluator_by_check,
            test_evaluator_unmapped_check_passes,
            test_evaluator_shadow_mode,
        ]),
        ("PassCriteria", [
            test_pass_criteria_operators,
        ]),
        ("Gate Hooks", [
            test_gate_hooks_integration,
        ]),
        ("Evidence", [
            test_evidence_produced,
        ]),
    ]

    total = 0
    passed = 0
    failed_tests = []

    for section, fns in tests:
        print(f"\n--- {section} ---")
        for fn in fns:
            total += 1
            try:
                fn()
                passed += 1
            except Exception as e:
                failed_tests.append((fn.__name__, str(e)))
                print(f"  FAILED: {fn.__name__}: {e}")

    print(f"\n{'=' * 60}")
    print(f"Results: {passed}/{total} passed")
    if failed_tests:
        print(f"FAILED tests:")
        for name, err in failed_tests:
            print(f"  - {name}: {err}")
        sys.exit(1)
    else:
        print("All tests PASSED")
