"""
Remaining Layer Tests -- L22, L27, L18, L23, L24, L25, L30
K-Dexter AOS v4

Run: python -X utf8 tests/test_remaining_layers.py
"""
from __future__ import annotations

import sys

from kdexter.engines.spec_lock import SpecLockEngine, SpecLockResult, BlockedMutation
from kdexter.engines.override_controller import (
    OverrideController, OverrideType, OverrideStatus,
)
from kdexter.engines.budget_evolution import BudgetEvolutionEngine, PerformanceData
from kdexter.engines.research import ResearchEngine
from kdexter.engines.knowledge import KnowledgeEngine
from kdexter.engines.scheduler import SchedulerEngine
from kdexter.engines.progress import ProgressEngine


# ======================================================================== #
# 1. L22 Spec Lock
# ======================================================================== #

def test_spec_lock_initial_unlocked():
    e = SpecLockEngine()
    assert e.is_locked is False
    assert e.mutation_count == 0
    print("  [1] Spec lock initial unlocked  OK")


def test_spec_lock_allows_mutation_when_unlocked():
    e = SpecLockEngine()
    assert e.check_mutation("intent", "old", "new") is True
    assert e.mutation_count == 0
    print("  [2] Spec lock allows mutation when unlocked  OK")


def test_spec_lock_blocks_mutation_when_locked():
    e = SpecLockEngine()
    e.lock()
    assert e.is_locked is True
    assert e.check_mutation("intent", "old", "new") is False
    assert e.mutation_count == 1
    print("  [3] Spec lock blocks mutation when locked  OK")


def test_spec_lock_allows_same_value():
    e = SpecLockEngine()
    e.lock()
    assert e.check_mutation("intent", "same", "same") is True
    assert e.mutation_count == 0
    print("  [4] Spec lock allows same value  OK")


def test_spec_lock_result():
    e = SpecLockEngine()
    e.lock()
    e.check_mutation("field_a", "x", "y")
    e.check_mutation("field_b", "1", "2")
    result = e.get_result()
    assert result.locked is True
    assert result.mutation_count == 2
    assert len(result.mutations_blocked) == 2
    print("  [5] Spec lock result  OK")


def test_spec_lock_unlock_resets():
    e = SpecLockEngine()
    e.lock()
    e.check_mutation("f", "a", "b")
    e.unlock()
    assert e.is_locked is False
    assert e.mutation_count == 0
    print("  [6] Spec lock unlock resets  OK")


# ======================================================================== #
# 2. L27 Override Controller
# ======================================================================== #

def test_override_submit():
    c = OverrideController()
    req = c.submit_request("admin", OverrideType.LOCKDOWN_RELEASE, "Emergency")
    assert req.status == OverrideStatus.PENDING
    assert req.requester == "admin"
    print("  [7] Override submit  OK")


def test_override_approve():
    c = OverrideController()
    req = c.submit_request("admin", OverrideType.LOCKDOWN_RELEASE, "Fix")
    c.approve(req.request_id, "supervisor")
    assert req.status == OverrideStatus.APPROVED
    print("  [8] Override approve  OK")


def test_override_deny():
    c = OverrideController()
    req = c.submit_request("admin", OverrideType.FORCE_STOP, "Stop all")
    c.deny(req.request_id, "supervisor", "Not justified")
    assert req.status == OverrideStatus.DENIED
    print("  [9] Override deny  OK")


def test_override_has_approved():
    c = OverrideController()
    req = c.submit_request("admin", OverrideType.LOCKDOWN_RELEASE, "Fix")
    assert c.has_approved(OverrideType.LOCKDOWN_RELEASE) is False
    c.approve(req.request_id, "supervisor")
    assert c.has_approved(OverrideType.LOCKDOWN_RELEASE) is True
    assert c.has_approved(OverrideType.FORCE_STOP) is False
    print("  [10] Override has_approved  OK")


def test_override_pending_list():
    c = OverrideController()
    c.submit_request("a", OverrideType.LOCKDOWN_RELEASE, "r1")
    c.submit_request("b", OverrideType.FORCE_STOP, "r2")
    pending = c.get_pending()
    assert len(pending) == 2
    print("  [11] Override pending list  OK")


def test_override_double_approve_rejected():
    c = OverrideController()
    req = c.submit_request("admin", OverrideType.LOCKDOWN_RELEASE, "Fix")
    c.approve(req.request_id, "supervisor")
    try:
        c.approve(req.request_id, "supervisor")
        assert False, "Should have raised"
    except ValueError:
        pass
    print("  [12] Override double approve rejected  OK")


# ======================================================================== #
# 3. L18 Budget Evolution Engine
# ======================================================================== #

def test_budget_evolution_propose():
    e = BudgetEvolutionEngine()
    perf = PerformanceData(resource_type="API_CALLS", average_usage=300, peak_usage=500, observation_window=7)
    adj = e.propose_adjustment(1000.0, perf)
    assert adj.resource_type == "API_CALLS"
    assert adj.current_limit == 1000.0
    assert adj.proposed_limit > 0
    print("  [13] Budget evolution propose  OK")


def test_budget_evolution_high_usage():
    e = BudgetEvolutionEngine()
    perf = PerformanceData(resource_type="USD_COST", average_usage=8.0, peak_usage=9.5, observation_window=7)
    adj = e.propose_adjustment(10.0, perf)
    # Peak 9.5/10 = 95% -> should propose increase
    assert adj.proposed_limit >= 10.0
    print("  [14] Budget evolution high usage -> increase  OK")


def test_budget_evolution_low_usage():
    e = BudgetEvolutionEngine()
    perf = PerformanceData(resource_type="USD_COST", average_usage=1.0, peak_usage=2.0, observation_window=7)
    adj = e.propose_adjustment(10.0, perf)
    # Average 1/10=10%, peak 2/10=20% -> should propose decrease
    assert adj.proposed_limit <= 10.0
    print("  [15] Budget evolution low usage -> decrease  OK")


# ======================================================================== #
# 4. L23 Research Engine
# ======================================================================== #

def test_research_conduct():
    e = ResearchEngine()
    result = e.conduct("market conditions")
    assert result.research_complete is True
    assert result.topic == "market conditions"
    print("  [16] Research conduct  OK")


def test_research_multiple():
    e = ResearchEngine()
    r1 = e.conduct("topic1")
    r2 = e.conduct("topic2")
    assert r1.topic == "topic1"
    assert r2.topic == "topic2"
    assert r1.research_complete is True
    assert r2.research_complete is True
    print("  [17] Research multiple conducts  OK")


# ======================================================================== #
# 5. L24 Knowledge Engine
# ======================================================================== #

def test_knowledge_store_retrieve():
    e = KnowledgeEngine()
    e.store("btc_trend", "bullish", "analysis_v1")
    entry = e.retrieve("btc_trend")
    assert entry is not None
    assert entry.value == "bullish"
    print("  [18] Knowledge store/retrieve  OK")


def test_knowledge_missing_key():
    e = KnowledgeEngine()
    assert e.retrieve("nonexistent") is None
    print("  [19] Knowledge missing key  OK")


def test_knowledge_update():
    e = KnowledgeEngine()
    e.store("key1", "v1", "src")
    e.store("key1", "v2", "src2")
    entry = e.retrieve("key1")
    assert entry.value == "v2"
    print("  [20] Knowledge update  OK")


# ======================================================================== #
# 6. L25 Scheduler Engine
# ======================================================================== #

def test_scheduler_schedule():
    e = SchedulerEngine()
    task = e.schedule("health_check", 60, "check_health")
    assert task.task_id == "health_check"
    assert task.active is True
    print("  [21] Scheduler schedule  OK")


def test_scheduler_cancel():
    e = SchedulerEngine()
    e.schedule("t1", 60, "cb1")
    e.cancel("t1")
    tasks = e.list_tasks()
    active = [t for t in tasks if t.active]
    assert len(active) == 0
    print("  [22] Scheduler cancel  OK")


def test_scheduler_list():
    e = SchedulerEngine()
    e.schedule("t1", 60, "cb1")
    e.schedule("t2", 120, "cb2")
    assert len(e.list_tasks()) == 2
    print("  [23] Scheduler list  OK")


# ======================================================================== #
# 7. L30 Progress Engine
# ======================================================================== #

def test_progress_record_get():
    e = ProgressEngine()
    e.record("cycles_completed", 42.0)
    assert e.get("cycles_completed") == 42.0
    print("  [24] Progress record/get  OK")


def test_progress_missing():
    e = ProgressEngine()
    assert e.get("nonexistent") is None
    print("  [25] Progress missing metric  OK")


def test_progress_summary():
    e = ProgressEngine()
    e.record("a", 1.0)
    e.record("b", 2.0)
    s = e.summary()
    assert s["a"] == 1.0
    assert s["b"] == 2.0
    print("  [26] Progress summary  OK")


# ======================================================================== #
# Runner
# ======================================================================== #

if __name__ == "__main__":
    print("\nRemaining Layer Tests (L22, L27, L18, L23, L24, L25, L30)")
    print("=" * 60)

    tests = [
        ("L22 Spec Lock", [
            test_spec_lock_initial_unlocked,
            test_spec_lock_allows_mutation_when_unlocked,
            test_spec_lock_blocks_mutation_when_locked,
            test_spec_lock_allows_same_value,
            test_spec_lock_result,
            test_spec_lock_unlock_resets,
        ]),
        ("L27 Override Controller", [
            test_override_submit,
            test_override_approve,
            test_override_deny,
            test_override_has_approved,
            test_override_pending_list,
            test_override_double_approve_rejected,
        ]),
        ("L18 Budget Evolution", [
            test_budget_evolution_propose,
            test_budget_evolution_high_usage,
            test_budget_evolution_low_usage,
        ]),
        ("L23 Research Engine", [
            test_research_conduct,
            test_research_multiple,
        ]),
        ("L24 Knowledge Engine", [
            test_knowledge_store_retrieve,
            test_knowledge_missing_key,
            test_knowledge_update,
        ]),
        ("L25 Scheduler Engine", [
            test_scheduler_schedule,
            test_scheduler_cancel,
            test_scheduler_list,
        ]),
        ("L30 Progress Engine", [
            test_progress_record_get,
            test_progress_missing,
            test_progress_summary,
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
