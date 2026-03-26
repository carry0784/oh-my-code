"""
Final Layer Tests -- L1, L4, L5, L6, L7
K-Dexter AOS v4

Run: python -X utf8 tests/test_final_layers.py
"""
from __future__ import annotations

import sys

from kdexter.engines.human_decision import (
    HumanDecisionInterface, DecisionType, DecisionStatus,
)
from kdexter.engines.clarify_spec import (
    ClarifySpecEngine, SpecStatus,
)
from kdexter.engines.harness import HarnessEngine, HarnessStatus
from kdexter.engines.parallel_agent import (
    ParallelAgentManager, AgentStatus,
)
from kdexter.engines.evaluation import (
    EvaluationEngine, EvaluationMetric,
)


# ======================================================================== #
# 1. L1 Human Decision
# ======================================================================== #

def test_human_submit():
    h = HumanDecisionInterface()
    d = h.submit("D-001", DecisionType.APPROVAL, "Approve live trading", "admin")
    assert d.decision_id == "D-001"
    assert d.status == DecisionStatus.PENDING
    print("  [1] Human decision submit  OK")


def test_human_apply():
    h = HumanDecisionInterface()
    h.submit("D-001", DecisionType.APPROVAL, "Approve", "admin")
    assert h.apply("D-001") is True
    d = h.get("D-001")
    assert d.status == DecisionStatus.APPLIED
    assert d.applied_at is not None
    print("  [2] Human decision apply  OK")


def test_human_apply_nonexistent():
    h = HumanDecisionInterface()
    assert h.apply("NONEXIST") is False
    print("  [3] Human decision apply nonexistent  OK")


def test_human_list_pending():
    h = HumanDecisionInterface()
    h.submit("D-001", DecisionType.APPROVAL, "A", "admin")
    h.submit("D-002", DecisionType.DIRECTIVE, "B", "admin")
    h.apply("D-001")
    pending = h.list_pending()
    assert len(pending) == 1
    assert pending[0].decision_id == "D-002"
    print("  [4] Human decision list pending  OK")


# ======================================================================== #
# 2. L4 Clarify & Spec
# ======================================================================== #

def test_spec_create():
    e = ClarifySpecEngine()
    spec = e.create("SPEC-001", "Test intent", ["obj1"], ["constraint1"])
    assert spec.spec_id == "SPEC-001"
    assert spec.status == SpecStatus.DRAFT
    assert len(spec.objectives) == 1
    print("  [5] Spec create  OK")


def test_spec_clarify_approve():
    e = ClarifySpecEngine()
    e.create("SPEC-001", "Test intent")
    assert e.clarify("SPEC-001") is True
    spec = e.get("SPEC-001")
    assert spec.status == SpecStatus.CLARIFIED
    assert e.approve("SPEC-001") is True
    assert spec.status == SpecStatus.APPROVED
    print("  [6] Spec clarify -> approve  OK")


def test_spec_approve_without_clarify_fails():
    e = ClarifySpecEngine()
    e.create("SPEC-001", "Test")
    assert e.approve("SPEC-001") is False
    print("  [7] Spec approve without clarify fails  OK")


def test_spec_list_all():
    e = ClarifySpecEngine()
    e.create("S1", "A")
    e.create("S2", "B")
    assert len(e.list_all()) == 2
    print("  [8] Spec list all  OK")


# ======================================================================== #
# 3. L5 Harness
# ======================================================================== #

def test_harness_lifecycle():
    e = HarnessEngine()
    run = e.create("RUN-001", "strat_1")
    assert run.status == HarnessStatus.CREATED
    assert e.start("RUN-001") is True
    assert run.status == HarnessStatus.RUNNING
    assert e.complete("RUN-001", {"pnl": 100}) is True
    assert run.status == HarnessStatus.COMPLETED
    assert run.result["pnl"] == 100
    print("  [9] Harness lifecycle  OK")


def test_harness_fail():
    e = HarnessEngine()
    e.create("RUN-001", "strat_1")
    e.start("RUN-001")
    assert e.fail("RUN-001", "timeout") is True
    run = e.get("RUN-001")
    assert run.status == HarnessStatus.FAILED
    assert run.error == "timeout"
    print("  [10] Harness fail  OK")


def test_harness_list_running():
    e = HarnessEngine()
    e.create("R1", "s1")
    e.create("R2", "s2")
    e.start("R1")
    assert len(e.list_running()) == 1
    print("  [11] Harness list running  OK")


# ======================================================================== #
# 4. L6 Parallel Agent
# ======================================================================== #

def test_agent_spawn_start():
    m = ParallelAgentManager(max_agents=5)
    agent = m.spawn("A-001", "strat_1", "binance")
    assert agent is not None
    assert agent.status == AgentStatus.IDLE
    assert m.start("A-001") is True
    assert agent.status == AgentStatus.RUNNING
    print("  [12] Agent spawn and start  OK")


def test_agent_max_limit():
    m = ParallelAgentManager(max_agents=2)
    m.spawn("A1", "s1", "binance")
    m.spawn("A2", "s2", "upbit")
    assert m.spawn("A3", "s3", "bitget") is None
    print("  [13] Agent max limit  OK")


def test_agent_pause_resume():
    m = ParallelAgentManager()
    m.spawn("A-001", "s1", "binance")
    m.start("A-001")
    assert m.pause("A-001") is True
    assert m.get("A-001").status == AgentStatus.PAUSED
    assert m.start("A-001") is True
    assert m.get("A-001").status == AgentStatus.RUNNING
    print("  [14] Agent pause/resume  OK")


def test_agent_record_cycle():
    m = ParallelAgentManager()
    m.spawn("A-001", "s1", "binance")
    m.start("A-001")
    m.record_cycle("A-001")
    m.record_cycle("A-001")
    assert m.get("A-001").cycles_completed == 2
    print("  [15] Agent record cycle  OK")


def test_agent_active_count():
    m = ParallelAgentManager()
    m.spawn("A1", "s1", "binance")
    m.spawn("A2", "s2", "upbit")
    m.start("A1")
    assert m.active_count() == 1
    m.start("A2")
    assert m.active_count() == 2
    m.stop("A1")
    assert m.active_count() == 1
    print("  [16] Agent active count  OK")


# ======================================================================== #
# 5. L7 Evaluation
# ======================================================================== #

def test_eval_basic():
    e = EvaluationEngine()
    metrics = [
        EvaluationMetric(name="pnl", value=0.8, benchmark=0.5, passed=True),
        EvaluationMetric(name="sharpe", value=1.2, benchmark=1.0, passed=True),
    ]
    result = e.evaluate("E-001", "strat_1", "CYC-001", metrics)
    assert result.passed is True
    assert result.overall_score == 1.0  # (0.8 + 1.2) / 2
    print("  [17] Evaluation basic  OK")


def test_eval_failed_metric():
    e = EvaluationEngine()
    metrics = [
        EvaluationMetric(name="pnl", value=-0.5, benchmark=0.0, passed=False),
        EvaluationMetric(name="sharpe", value=1.0, benchmark=1.0, passed=True),
    ]
    result = e.evaluate("E-001", "strat_1", "CYC-001", metrics)
    assert result.passed is False
    print("  [18] Evaluation failed metric  OK")


def test_eval_average_score():
    e = EvaluationEngine()
    e.evaluate("E-001", "s1", "C1", [EvaluationMetric("a", 0.8)])
    e.evaluate("E-002", "s1", "C2", [EvaluationMetric("a", 0.6)])
    avg = e.average_score("s1")
    assert abs(avg - 0.7) < 0.001
    print("  [19] Evaluation average score  OK")


def test_eval_list_for_strategy():
    e = EvaluationEngine()
    e.evaluate("E-001", "s1", "C1")
    e.evaluate("E-002", "s2", "C2")
    e.evaluate("E-003", "s1", "C3")
    assert len(e.list_for_strategy("s1")) == 2
    assert len(e.list_for_strategy("s2")) == 1
    print("  [20] Evaluation list for strategy  OK")


# ======================================================================== #
# Runner
# ======================================================================== #

if __name__ == "__main__":
    print("\nFinal Layer Tests (L1, L4, L5, L6, L7)")
    print("=" * 60)

    tests = [
        ("L1 Human Decision", [
            test_human_submit,
            test_human_apply,
            test_human_apply_nonexistent,
            test_human_list_pending,
        ]),
        ("L4 Clarify & Spec", [
            test_spec_create,
            test_spec_clarify_approve,
            test_spec_approve_without_clarify_fails,
            test_spec_list_all,
        ]),
        ("L5 Harness", [
            test_harness_lifecycle,
            test_harness_fail,
            test_harness_list_running,
        ]),
        ("L6 Parallel Agent", [
            test_agent_spawn_start,
            test_agent_max_limit,
            test_agent_pause_resume,
            test_agent_record_cycle,
            test_agent_active_count,
        ]),
        ("L7 Evaluation", [
            test_eval_basic,
            test_eval_failed_metric,
            test_eval_average_score,
            test_eval_list_for_strategy,
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
