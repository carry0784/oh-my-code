"""
Engine Tests -- L16, L19, L21, L29, L28
K-Dexter AOS v4

Tests for the 5 priority engines:
  1. L16 Rule Conflict Engine
  2. L19 Trust Decay Engine
  3. L21 Completion Engine
  4. L29 Cost Controller
  5. L28 Loop Monitor

Run: python -X utf8 tests/test_engines.py
"""
from __future__ import annotations

import sys

from kdexter.engines.rule_conflict import (
    RuleConflictEngine,
    ConflictCheckResult,
    _actions_contradict,
    _conditions_overlap,
)
from kdexter.engines.trust_decay import TrustDecayEngine, TrustCheckResult
from kdexter.engines.completion import (
    CompletionEngine,
    CompletionCriterion,
    CompletionCheckResult,
)
from kdexter.engines.cost_controller import CostController, CostCheckResult
from kdexter.engines.loop_monitor import (
    LoopMonitor,
    LoopHealthStatus,
    LoopMonitorResult,
)
from kdexter.ledger.rule_ledger import Rule
from kdexter.state_machine.trust_state import TrustStateContext, TrustStateEnum
from kdexter.loops.concurrency import LoopCounter


# ======================================================================== #
# 1. L16 Rule Conflict Engine
# ======================================================================== #

def test_no_conflicts():
    engine = RuleConflictEngine()
    rules = [
        Rule(rule_id="R-001", condition="loss > 0.05", action="BLOCK"),
        Rule(rule_id="R-002", condition="price < 100", action="BUY"),
    ]
    result = engine.check(rules)
    assert result.conflict_count == 0
    assert result.rules_scanned == 2
    print("  [1] No conflicts -- different conditions  OK")


def test_conflicting_rules():
    engine = RuleConflictEngine()
    rules = [
        Rule(rule_id="R-001", condition="price > 100", action="BUY"),
        Rule(rule_id="R-002", condition="price > 100", action="SELL"),
    ]
    result = engine.check(rules)
    assert result.conflict_count == 1
    assert result.conflicts[0].rule_a_id == "R-001"
    assert result.conflicts[0].rule_b_id == "R-002"
    print("  [2] Conflicting rules detected  OK")


def test_actions_contradict_helper():
    assert _actions_contradict("BUY", "SELL")
    assert _actions_contradict("BLOCK", "ALLOW")
    assert _actions_contradict("INCREASE position", "DECREASE position")
    assert not _actions_contradict("BUY", "BUY")
    assert not _actions_contradict("LOG", "ALERT")
    print("  [3] Action contradiction helper  OK")


def test_conditions_overlap_helper():
    assert _conditions_overlap("loss > 0.05", "loss > 0.05")  # exact
    assert _conditions_overlap("loss > 0.05", "loss > 0.10")  # shared tokens
    assert not _conditions_overlap("price > 100", "volume < 50")  # different
    assert not _conditions_overlap("", "loss > 0.05")  # empty
    print("  [4] Condition overlap helper  OK")


def test_empty_rules():
    engine = RuleConflictEngine()
    result = engine.check([])
    assert result.conflict_count == 0
    assert result.rules_scanned == 0
    print("  [5] Empty rules list  OK")


def test_multiple_conflicts():
    engine = RuleConflictEngine()
    rules = [
        Rule(rule_id="R-001", condition="price > 100", action="BUY"),
        Rule(rule_id="R-002", condition="price > 100", action="SELL"),
        Rule(rule_id="R-003", condition="price > 100", action="SELL"),
    ]
    result = engine.check(rules)
    # R-001 vs R-002 (BUY/SELL), R-001 vs R-003 (BUY/SELL)
    # R-002 vs R-003 share same action -- not conflicting
    assert result.conflict_count == 2
    print("  [6] Multiple conflicts detected  OK")


def test_conflict_history():
    engine = RuleConflictEngine()
    engine.check([])
    engine.check([Rule(rule_id="R-001", condition="x > 1", action="BUY")])
    assert len(engine.history()) == 2
    print("  [7] Conflict check history tracked  OK")


# ======================================================================== #
# 2. L19 Trust Decay Engine
# ======================================================================== #

def test_trust_register_and_check():
    engine = TrustDecayEngine()
    ctx = TrustStateContext(component_id="strat_1")
    engine.register("strat_1", ctx)
    result = engine.check("strat_1")
    assert result.trust_score == 1.0
    assert result.passed_gate is True
    print("  [8] Trust register and check  OK")


def test_trust_failure_decay():
    engine = TrustDecayEngine()
    ctx = TrustStateContext(component_id="strat_1")
    engine.register("strat_1", ctx)
    engine.on_failure("strat_1", "CRITICAL")
    result = engine.check("strat_1")
    assert result.trust_score < 1.0
    # CRITICAL decay = -0.40, so score ~0.60
    assert result.trust_score <= 0.61
    print("  [9] Trust failure decay  OK")


def test_trust_gate_fail():
    engine = TrustDecayEngine()
    ctx = TrustStateContext(component_id="strat_1")
    engine.register("strat_1", ctx)
    engine.on_failure("strat_1", "CRITICAL")
    engine.on_failure("strat_1", "MEDIUM")
    result = engine.check("strat_1")
    # 1.0 - 0.40 - 0.05 = 0.55 < 0.60
    assert result.trust_score < 0.60
    assert result.passed_gate is False
    print("  [10] Trust gate fail below 0.60  OK")


def test_trust_success_recovery():
    engine = TrustDecayEngine()
    ctx = TrustStateContext(component_id="strat_1")
    engine.register("strat_1", ctx)
    engine.on_failure("strat_1", "HIGH")
    engine.on_success("strat_1")
    result = engine.check("strat_1")
    # 1.0 - 0.20 + 0.10 = 0.90
    assert 0.89 <= result.trust_score <= 0.91
    assert result.passed_gate is True
    print("  [11] Trust success recovery  OK")


def test_trust_check_all():
    engine = TrustDecayEngine()
    engine.register("a", TrustStateContext(component_id="a"))
    engine.register("b", TrustStateContext(component_id="b"))
    results = engine.check_all()
    assert len(results) == 2
    assert "a" in results and "b" in results
    print("  [12] Trust check all  OK")


def test_trust_lowest():
    engine = TrustDecayEngine()
    engine.register("a", TrustStateContext(component_id="a"))
    engine.register("b", TrustStateContext(component_id="b"))
    engine.on_failure("b", "HIGH")
    lowest = engine.lowest_trust()
    assert lowest is not None
    assert lowest.component_id == "b"
    print("  [13] Trust lowest component  OK")


def test_trust_unregister():
    engine = TrustDecayEngine()
    engine.register("x", TrustStateContext(component_id="x"))
    engine.unregister("x")
    assert engine.get_context("x") is None
    print("  [14] Trust unregister  OK")


# ======================================================================== #
# 3. L21 Completion Engine
# ======================================================================== #

def test_completion_no_criteria():
    engine = CompletionEngine(threshold=0.8)
    result = engine.check()
    assert result.completion_score == 1.0
    assert result.passed_gate is True
    print("  [15] Completion no criteria (vacuous)  OK")


def test_completion_all_satisfied():
    engine = CompletionEngine(threshold=0.8)
    engine.add_criterion(CompletionCriterion("C-1", "Tests pass"))
    engine.add_criterion(CompletionCriterion("C-2", "Risk OK"))
    engine.satisfy("C-1", "24/24")
    engine.satisfy("C-2", "green")
    result = engine.check()
    assert result.completion_score == 1.0
    assert result.passed_gate is True
    assert result.satisfied_criteria == 2
    print("  [16] Completion all satisfied  OK")


def test_completion_partial():
    engine = CompletionEngine(threshold=0.8)
    engine.add_criterion(CompletionCriterion("C-1", "Tests", weight=3.0))
    engine.add_criterion(CompletionCriterion("C-2", "Risk", weight=1.0))
    engine.satisfy("C-1")
    result = engine.check()
    # 3.0 / 4.0 = 0.75 < 0.80
    assert result.completion_score == 0.75
    assert result.passed_gate is False
    assert result.unsatisfied == ["C-2"]
    print("  [17] Completion partial -- below threshold  OK")


def test_completion_weighted():
    engine = CompletionEngine(threshold=0.5)
    engine.add_criterion(CompletionCriterion("C-1", "Heavy", weight=9.0))
    engine.add_criterion(CompletionCriterion("C-2", "Light", weight=1.0))
    engine.satisfy("C-2")
    result = engine.check()
    # 1.0 / 10.0 = 0.10
    assert result.completion_score == 0.1
    assert result.passed_gate is False
    print("  [18] Completion weighted scoring  OK")


def test_completion_reset():
    engine = CompletionEngine(threshold=0.5)
    engine.add_criterion(CompletionCriterion("C-1", "Test"))
    engine.satisfy("C-1")
    engine.reset("C-1")
    result = engine.check()
    assert result.completion_score == 0.0
    print("  [19] Completion reset criterion  OK")


def test_completion_reset_all():
    engine = CompletionEngine()
    engine.add_criterion(CompletionCriterion("C-1", "A"))
    engine.add_criterion(CompletionCriterion("C-2", "B"))
    engine.satisfy("C-1")
    engine.satisfy("C-2")
    engine.reset_all()
    result = engine.check()
    assert result.completion_score == 0.0
    assert len(result.unsatisfied) == 2
    print("  [20] Completion reset all  OK")


def test_completion_remove_criterion():
    engine = CompletionEngine()
    engine.add_criterion(CompletionCriterion("C-1", "A"))
    engine.add_criterion(CompletionCriterion("C-2", "B"))
    engine.satisfy("C-1")
    engine.remove_criterion("C-2")
    result = engine.check()
    assert result.completion_score == 1.0
    print("  [21] Completion remove criterion  OK")


# ======================================================================== #
# 4. L29 Cost Controller
# ======================================================================== #

def test_cost_no_budgets():
    cc = CostController()
    result = cc.check()
    assert result.resource_usage_ratio == 0.0
    assert result.passed_gate is True
    print("  [22] Cost no budgets  OK")


def test_cost_within_budget():
    cc = CostController()
    cc.set_budget("API_CALLS", limit=1000)
    cc.record_usage("API_CALLS", 500)
    result = cc.check()
    assert result.resource_usage_ratio == 0.5
    assert result.passed_gate is True
    assert len(result.exceeded) == 0
    print("  [23] Cost within budget  OK")


def test_cost_exceeded():
    cc = CostController()
    cc.set_budget("USD_COST", limit=10.0)
    cc.record_usage("USD_COST", 15.0)
    result = cc.check()
    assert result.resource_usage_ratio == 1.5
    assert result.passed_gate is False
    assert "USD_COST" in result.exceeded
    print("  [24] Cost exceeded  OK")


def test_cost_multiple_resources():
    cc = CostController()
    cc.set_budget("API_CALLS", limit=1000)
    cc.set_budget("USD_COST", limit=10.0)
    cc.record_usage("API_CALLS", 500)   # 0.5
    cc.record_usage("USD_COST", 8.0)    # 0.8
    result = cc.check()
    assert result.resource_usage_ratio == 0.8  # max of the two
    assert result.passed_gate is True
    print("  [25] Cost multiple resources -- max ratio  OK")


def test_cost_reset_usage():
    cc = CostController()
    cc.set_budget("API_CALLS", limit=100)
    cc.record_usage("API_CALLS", 50)
    cc.reset_usage("API_CALLS")
    result = cc.check()
    assert result.resource_usage_ratio == 0.0
    print("  [26] Cost reset usage  OK")


def test_cost_reset_all():
    cc = CostController()
    cc.set_budget("A", limit=100)
    cc.set_budget("B", limit=100)
    cc.record_usage("A", 50)
    cc.record_usage("B", 80)
    cc.reset_all()
    result = cc.check()
    assert result.resource_usage_ratio == 0.0
    print("  [27] Cost reset all  OK")


def test_cost_additive_usage():
    cc = CostController()
    cc.set_budget("API_CALLS", limit=100)
    cc.record_usage("API_CALLS", 30)
    cc.record_usage("API_CALLS", 40)
    result = cc.check()
    assert result.resource_usage_ratio == 0.7
    print("  [28] Cost additive usage  OK")


# ======================================================================== #
# 5. L28 Loop Monitor
# ======================================================================== #

def test_monitor_healthy():
    counter = LoopCounter()
    monitor = LoopMonitor(counter)
    result = monitor.check("INC-001")
    assert result.overall_health == LoopHealthStatus.HEALTHY
    assert result.any_exceeded is False
    assert len(result.loop_statuses) == 4
    print("  [29] Loop monitor healthy  OK")


def test_monitor_warning():
    counter = LoopCounter()
    monitor = LoopMonitor(counter)
    # Recovery ceiling = 3 per incident, record 2 (66%) -> still HEALTHY
    counter.check_and_record("RECOVERY", "INC-001")
    counter.check_and_record("RECOVERY", "INC-001")
    result = monitor.check("INC-001")
    status = result.loop_statuses["RECOVERY"]
    assert status.incident_count == 2
    # 2/3 = 0.667 < 0.70 -> HEALTHY
    assert status.health == LoopHealthStatus.HEALTHY
    print("  [30] Loop monitor below warning  OK")


def test_monitor_warning_threshold():
    counter = LoopCounter()
    monitor = LoopMonitor(counter)
    # Evolution ceiling = 1 per incident. Record 1 -> 1/1 = 1.0 >= 0.90 -> CRITICAL
    counter.check_and_record("EVOLUTION", "INC-001")
    result = monitor.check("INC-001")
    status = result.loop_statuses["EVOLUTION"]
    assert status.max_usage_ratio == 1.0
    assert status.health == LoopHealthStatus.CRITICAL
    print("  [31] Loop monitor at evolution ceiling -> CRITICAL  OK")


def test_monitor_any_exceeded():
    counter = LoopCounter()
    monitor = LoopMonitor(counter)
    counter.check_and_record("RECOVERY", "INC-001")
    counter.check_and_record("RECOVERY", "INC-001")
    counter.check_and_record("RECOVERY", "INC-001")
    # Now at ceiling (3/3), next would fail. But check doesn't record.
    result = monitor.check("INC-001")
    status = result.loop_statuses["RECOVERY"]
    # 3/3 = 1.0 -> EXCEEDED (> 1.0 boundary is >, but 1.0 == ceiling means at limit)
    # Our check: max_ratio > 1.0 -> EXCEEDED, else >= 0.90 -> CRITICAL
    # 3/3 = 1.0 -- this is exactly at ceiling, not exceeded yet
    assert status.max_usage_ratio == 1.0
    assert status.health == LoopHealthStatus.CRITICAL  # 1.0 >= 0.90
    print("  [32] Loop monitor at ceiling -> CRITICAL  OK")


def test_monitor_single():
    counter = LoopCounter()
    monitor = LoopMonitor(counter)
    status = monitor.check_single("MAIN", "INC-001")
    assert status.loop_name == "MAIN"
    assert status.incident_count == 0
    assert status.health == LoopHealthStatus.HEALTHY
    print("  [33] Loop monitor single check  OK")


# ======================================================================== #
# Runner
# ======================================================================== #

if __name__ == "__main__":
    print("\nEngine Tests (L16, L19, L21, L29, L28)")
    print("=" * 60)

    tests = [
        ("L16 Rule Conflict Engine", [
            test_no_conflicts,
            test_conflicting_rules,
            test_actions_contradict_helper,
            test_conditions_overlap_helper,
            test_empty_rules,
            test_multiple_conflicts,
            test_conflict_history,
        ]),
        ("L19 Trust Decay Engine", [
            test_trust_register_and_check,
            test_trust_failure_decay,
            test_trust_gate_fail,
            test_trust_success_recovery,
            test_trust_check_all,
            test_trust_lowest,
            test_trust_unregister,
        ]),
        ("L21 Completion Engine", [
            test_completion_no_criteria,
            test_completion_all_satisfied,
            test_completion_partial,
            test_completion_weighted,
            test_completion_reset,
            test_completion_reset_all,
            test_completion_remove_criterion,
        ]),
        ("L29 Cost Controller", [
            test_cost_no_budgets,
            test_cost_within_budget,
            test_cost_exceeded,
            test_cost_multiple_resources,
            test_cost_reset_usage,
            test_cost_reset_all,
            test_cost_additive_usage,
        ]),
        ("L28 Loop Monitor", [
            test_monitor_healthy,
            test_monitor_warning,
            test_monitor_warning_threshold,
            test_monitor_any_exceeded,
            test_monitor_single,
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
        print("FAILED:")
        for name, err in failed_tests:
            print(f"  - {name}: {err}")
        sys.exit(1)
    else:
        print("All tests PASSED")
