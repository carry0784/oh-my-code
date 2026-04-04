"""
Failure Router Tests + Pattern Memory
K-Dexter AOS v4

Tests the routing decision table from failure_taxonomy.md Section 2.

Run: python tests/test_failure_router.py
"""
from __future__ import annotations

import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from kdexter.engines.failure_router import (
    FailurePatternMemory,
    FailureRouter,
    Recurrence,
    RoutingDecision,
    TargetLoop,
)
from kdexter.state_machine.security_state import SecurityStateEnum


# ======================================================================== #
# 1. FailurePatternMemory
# ======================================================================== #

def test_memory_first():
    mem = FailurePatternMemory()
    assert mem.classify_recurrence("F-I-001") == Recurrence.FIRST
    print("  [1] Pattern memory FIRST  OK")


def test_memory_repeat():
    mem = FailurePatternMemory()
    # Record 1 occurrence far in the past
    mem.record("F-I-001", datetime(2020, 1, 1))
    assert mem.classify_recurrence("F-I-001") == Recurrence.REPEAT
    print("  [2] Pattern memory REPEAT  OK")


def test_memory_pattern_by_count():
    mem = FailurePatternMemory()
    mem.record("F-I-001", datetime(2020, 1, 1))
    mem.record("F-I-001", datetime(2020, 6, 1))
    mem.record("F-I-001", datetime(2021, 1, 1))
    # 3 prior occurrences → PATTERN
    assert mem.classify_recurrence("F-I-001") == Recurrence.PATTERN
    print("  [3] Pattern memory PATTERN by count (3+)  OK")


def test_memory_pattern_by_window():
    mem = FailurePatternMemory()
    # 2 within last 7 days
    mem.record("F-S-001", datetime.utcnow() - timedelta(days=3))
    mem.record("F-S-001", datetime.utcnow() - timedelta(days=1))
    assert mem.classify_recurrence("F-S-001") == Recurrence.PATTERN
    print("  [4] Pattern memory PATTERN by window (2 in 7d)  OK")


def test_memory_count():
    mem = FailurePatternMemory()
    mem.record("F-I-001")
    mem.record("F-I-001")
    mem.record("F-S-001")
    assert mem.count() == 3
    assert mem.count("F-I-001") == 2
    assert mem.count("F-S-001") == 1
    assert mem.count("F-X-999") == 0
    print("  [5] Pattern memory count  OK")


def test_memory_clear():
    mem = FailurePatternMemory()
    mem.record("F-I-001")
    mem.clear()
    assert mem.count() == 0
    print("  [6] Pattern memory clear  OK")


# ======================================================================== #
# 2. INFRA Routing
# ======================================================================== #

def test_infra_critical():
    mem = FailurePatternMemory()
    router = FailureRouter(mem)
    d = router.route("INFRA", "CRITICAL", "F-I-007")
    assert d.target_loop == TargetLoop.RECOVERY
    assert d.security_target == SecurityStateEnum.LOCKDOWN
    assert d.work_state_action == "ISOLATED"
    print("  [7] INFRA CRITICAL → Recovery + LOCKDOWN  OK")


def test_infra_high():
    mem = FailurePatternMemory()
    router = FailureRouter(mem)
    d = router.route("INFRA", "HIGH", "F-I-001")
    assert d.target_loop == TargetLoop.RECOVERY
    assert d.security_target == SecurityStateEnum.QUARANTINED
    assert d.work_state_action == "FAILED"
    print("  [8] INFRA HIGH → Recovery + QUARANTINED  OK")


def test_infra_medium_first():
    mem = FailurePatternMemory()
    router = FailureRouter(mem)
    d = router.route("INFRA", "MEDIUM", "F-I-003")
    assert d.target_loop == TargetLoop.RECOVERY
    assert d.security_target == SecurityStateEnum.RESTRICTED
    assert not d.schedule_evolution
    print("  [9] INFRA MEDIUM FIRST → Recovery  OK")


def test_infra_medium_pattern():
    mem = FailurePatternMemory()
    router = FailureRouter(mem)
    d = router.route("INFRA", "MEDIUM", "F-I-003",
                     recurrence_override=Recurrence.PATTERN)
    assert d.target_loop == TargetLoop.RECOVERY
    assert d.schedule_evolution is True
    print("  [10] INFRA MEDIUM PATTERN → Recovery + Evolution scheduled  OK")


def test_infra_low():
    mem = FailurePatternMemory()
    router = FailureRouter(mem)
    d = router.route("INFRA", "LOW", "F-I-099")
    assert d.target_loop == TargetLoop.MAIN_LOOP
    assert d.security_target == SecurityStateEnum.NORMAL
    print("  [11] INFRA LOW → MainLoop  OK")


# ======================================================================== #
# 3. STRATEGY Routing
# ======================================================================== #

def test_strategy_critical():
    mem = FailurePatternMemory()
    router = FailureRouter(mem)
    d = router.route("STRATEGY", "CRITICAL", "F-S-006")
    assert d.target_loop == TargetLoop.RECOVERY
    assert d.security_target == SecurityStateEnum.QUARANTINED
    assert d.work_state_action == "ISOLATED"
    print("  [12] STRATEGY CRITICAL → Recovery  OK")


def test_strategy_high_first():
    mem = FailurePatternMemory()
    router = FailureRouter(mem)
    d = router.route("STRATEGY", "HIGH", "F-S-001")
    assert d.target_loop == TargetLoop.SELF_IMPROVEMENT
    assert d.security_target == SecurityStateEnum.RESTRICTED
    print("  [13] STRATEGY HIGH FIRST → Self-Improvement  OK")


def test_strategy_high_pattern():
    mem = FailurePatternMemory()
    router = FailureRouter(mem)
    d = router.route("STRATEGY", "HIGH", "F-S-001",
                     recurrence_override=Recurrence.PATTERN)
    assert d.target_loop == TargetLoop.EVOLUTION
    assert d.security_target == SecurityStateEnum.RESTRICTED
    print("  [14] STRATEGY HIGH PATTERN → Evolution  OK")


def test_strategy_medium_first():
    mem = FailurePatternMemory()
    router = FailureRouter(mem)
    d = router.route("STRATEGY", "MEDIUM", "F-S-002")
    assert d.target_loop == TargetLoop.SELF_IMPROVEMENT
    assert d.security_target == SecurityStateEnum.NORMAL
    print("  [15] STRATEGY MEDIUM FIRST → Self-Improvement  OK")


def test_strategy_medium_pattern():
    mem = FailurePatternMemory()
    router = FailureRouter(mem)
    d = router.route("STRATEGY", "MEDIUM", "F-S-002",
                     recurrence_override=Recurrence.PATTERN)
    assert d.target_loop == TargetLoop.EVOLUTION
    assert d.security_target == SecurityStateEnum.RESTRICTED
    print("  [16] STRATEGY MEDIUM PATTERN → Evolution  OK")


def test_strategy_low():
    mem = FailurePatternMemory()
    router = FailureRouter(mem)
    d = router.route("STRATEGY", "LOW", "F-S-099")
    assert d.target_loop == TargetLoop.MAIN_LOOP
    assert d.security_target == SecurityStateEnum.NORMAL
    print("  [17] STRATEGY LOW → MainLoop  OK")


# ======================================================================== #
# 4. GOVERNANCE Routing
# ======================================================================== #

def test_governance_critical():
    mem = FailurePatternMemory()
    router = FailureRouter(mem)
    d = router.route("GOVERNANCE", "CRITICAL", "F-G-001")
    assert d.target_loop == TargetLoop.RECOVERY
    assert d.security_target == SecurityStateEnum.LOCKDOWN
    assert d.b1_notify is True
    print("  [18] GOVERNANCE CRITICAL → Recovery + B1  OK")


def test_governance_high():
    mem = FailurePatternMemory()
    router = FailureRouter(mem)
    d = router.route("GOVERNANCE", "HIGH", "F-G-002")
    assert d.target_loop == TargetLoop.RECOVERY
    assert d.security_target == SecurityStateEnum.QUARANTINED
    assert d.b1_notify is True
    assert d.work_state_action == "BLOCKED"
    print("  [19] GOVERNANCE HIGH → Recovery + B1  OK")


def test_governance_medium_first():
    mem = FailurePatternMemory()
    router = FailureRouter(mem)
    d = router.route("GOVERNANCE", "MEDIUM", "F-G-004")
    assert d.target_loop == TargetLoop.SELF_IMPROVEMENT
    assert d.security_target == SecurityStateEnum.RESTRICTED
    assert not d.b1_notify
    print("  [20] GOVERNANCE MEDIUM FIRST → Self-Improvement  OK")


def test_governance_medium_pattern():
    mem = FailurePatternMemory()
    router = FailureRouter(mem)
    d = router.route("GOVERNANCE", "MEDIUM", "F-G-004",
                     recurrence_override=Recurrence.PATTERN)
    assert d.target_loop == TargetLoop.EVOLUTION
    assert d.b1_notify is True
    print("  [21] GOVERNANCE MEDIUM PATTERN → Evolution + B1  OK")


def test_governance_low():
    mem = FailurePatternMemory()
    router = FailureRouter(mem)
    d = router.route("GOVERNANCE", "LOW", "F-G-099")
    assert d.target_loop == TargetLoop.AUDIT_ONLY
    assert d.security_target == SecurityStateEnum.NORMAL
    print("  [22] GOVERNANCE LOW → Audit only  OK")


# ======================================================================== #
# 5. Integration: recurrence auto-classification
# ======================================================================== #

def test_auto_recurrence_escalation():
    """Route same failure 3x → auto-escalates from FIRST to PATTERN."""
    mem = FailurePatternMemory()
    router = FailureRouter(mem)

    # 1st: FIRST → Self-Improvement
    d1 = router.route("STRATEGY", "HIGH", "F-S-001")
    assert d1.target_loop == TargetLoop.SELF_IMPROVEMENT

    # 2nd: REPEAT → Self-Improvement
    d2 = router.route("STRATEGY", "HIGH", "F-S-001")
    assert d2.target_loop == TargetLoop.SELF_IMPROVEMENT

    # 3rd: now 2 prior records, but check window (both recent)
    # classify sees 2 records, both within 7 days → PATTERN
    d3 = router.route("STRATEGY", "HIGH", "F-S-001")
    assert d3.target_loop == TargetLoop.EVOLUTION
    print("  [23] Auto recurrence escalation FIRST→REPEAT→PATTERN  OK")


def test_router_records_to_memory():
    """Router auto-records failures to pattern memory."""
    mem = FailurePatternMemory()
    router = FailureRouter(mem)
    router.route("INFRA", "HIGH", "F-I-001")
    router.route("INFRA", "HIGH", "F-I-001")
    assert mem.count("F-I-001") == 2
    print("  [24] Router records to memory  OK")


# ======================================================================== #
# Runner
# ======================================================================== #

if __name__ == "__main__":
    print("\nFailure Router + Pattern Memory Tests")
    print("=" * 60)

    tests = [
        ("FailurePatternMemory", [
            test_memory_first,
            test_memory_repeat,
            test_memory_pattern_by_count,
            test_memory_pattern_by_window,
            test_memory_count,
            test_memory_clear,
        ]),
        ("INFRA Routing", [
            test_infra_critical,
            test_infra_high,
            test_infra_medium_first,
            test_infra_medium_pattern,
            test_infra_low,
        ]),
        ("STRATEGY Routing", [
            test_strategy_critical,
            test_strategy_high_first,
            test_strategy_high_pattern,
            test_strategy_medium_first,
            test_strategy_medium_pattern,
            test_strategy_low,
        ]),
        ("GOVERNANCE Routing", [
            test_governance_critical,
            test_governance_high,
            test_governance_medium_first,
            test_governance_medium_pattern,
            test_governance_low,
        ]),
        ("Integration", [
            test_auto_recurrence_escalation,
            test_router_records_to_memory,
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
