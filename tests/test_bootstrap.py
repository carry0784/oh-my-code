"""
Bootstrap Tests -- System Wiring & Lifecycle
K-Dexter AOS v4

Tests the SystemBootstrap wiring, layer binding, hook connection,
and end-to-end cycle execution.

Run: python -X utf8 tests/test_bootstrap.py
"""

from __future__ import annotations

import asyncio
import sys

from kdexter.bootstrap import SystemBootstrap
from kdexter.layers.registry import LayerStatus, HealthStatus
from kdexter.loops.main_loop import CycleInput, CycleOutcome
from kdexter.state_machine.work_state import WorkStateEnum
from kdexter.state_machine.security_state import SecurityStateEnum


def run(coro):
    """Helper to run async code in tests."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# ======================================================================== #
# 1. Wiring
# ======================================================================== #


def test_wire_creates_all_components():
    sys_ = SystemBootstrap()
    sys_.wire()
    assert sys_.work_state is not None
    assert sys_.trust_state is not None
    assert sys_.security_state is not None
    assert sys_.doctrine is not None
    assert sys_.b1 is not None
    assert sys_.b2 is not None
    assert sys_.rule_ledger is not None
    assert sys_.forbidden_ledger is not None
    assert sys_.mandatory_ledger is not None
    assert sys_.evidence_store is not None
    assert sys_.main_loop is not None
    assert sys_.recovery_loop is not None
    assert sys_.si_loop is not None
    assert sys_.evolution_loop is not None
    assert sys_.tcl is not None
    assert sys_.registry is not None
    print("  [1] Wire creates all components  OK")


def test_wire_binds_layers():
    sys_ = SystemBootstrap()
    sys_.wire()
    bound = sys_.registry.bound_count()
    # All 30 layers now bound
    assert bound == 30, f"Expected 30 bound layers, got {bound}"
    print(f"  [2] Wire binds {bound} layers  OK")


def test_wire_registry_summary():
    sys_ = SystemBootstrap()
    sys_.wire()
    summary = sys_.registry.summary()
    assert summary["total"] == 30
    assert summary["bound"] == 30
    assert summary["unbound"] == 30 - summary["bound"]
    print(f"  [3] Registry summary: {summary['bound']}/30 bound  OK")


def test_wire_sets_flag():
    sys_ = SystemBootstrap()
    assert sys_._wired is False
    sys_.wire()
    assert sys_._wired is True
    print("  [4] Wire sets _wired flag  OK")


# ======================================================================== #
# 2. Engine wiring verification
# ======================================================================== #


def test_engines_wired():
    sys_ = SystemBootstrap()
    sys_.wire()
    assert sys_.drift_engine is not None
    assert sys_.conflict_engine is not None
    assert sys_.trust_engine is not None
    assert sys_.completion_engine is not None
    assert sys_.cost_controller is not None
    assert sys_.loop_monitor is not None
    assert sys_.pattern_memory is not None
    assert sys_.failure_router is not None
    assert sys_.spec_lock is not None
    assert sys_.override_controller is not None
    assert sys_.budget_evolution is not None
    assert sys_.research_engine is not None
    assert sys_.knowledge_engine is not None
    assert sys_.scheduler_engine is not None
    assert sys_.progress_engine is not None
    print("  [5] All engines wired  OK")


def test_trust_engine_has_system_component():
    sys_ = SystemBootstrap()
    sys_.wire()
    ctx = sys_.trust_engine.get_context("system")
    assert ctx is not None
    assert ctx.score == 1.0
    print("  [6] Trust engine has 'system' component  OK")


def test_conflict_engine_checks_rule_ledger():
    sys_ = SystemBootstrap()
    sys_.wire()
    # Empty rule ledger -- no conflicts
    result = sys_.conflict_engine.check(sys_.rule_ledger.list_all())
    assert result.conflict_count == 0
    print("  [7] Conflict engine reads from rule ledger  OK")


def test_cost_controller_starts_empty():
    sys_ = SystemBootstrap()
    sys_.wire()
    result = sys_.cost_controller.check()
    assert result.resource_usage_ratio == 0.0
    assert result.passed_gate is True
    print("  [8] Cost controller starts with zero usage  OK")


# ======================================================================== #
# 3. Layer registry bindings
# ======================================================================== #


def test_layer_l15_is_drift_engine():
    sys_ = SystemBootstrap()
    sys_.wire()
    instance = sys_.registry.get_instance("L15")
    assert instance is sys_.drift_engine
    print("  [9] L15 bound to IntentDriftEngine  OK")


def test_layer_l16_is_conflict_engine():
    sys_ = SystemBootstrap()
    sys_.wire()
    instance = sys_.registry.get_instance("L16")
    assert instance is sys_.conflict_engine
    print("  [10] L16 bound to RuleConflictEngine  OK")


def test_layer_l19_is_trust_engine():
    sys_ = SystemBootstrap()
    sys_.wire()
    instance = sys_.registry.get_instance("L19")
    assert instance is sys_.trust_engine
    print("  [11] L19 bound to TrustDecayEngine  OK")


def test_layer_l21_is_completion_engine():
    sys_ = SystemBootstrap()
    sys_.wire()
    instance = sys_.registry.get_instance("L21")
    assert instance is sys_.completion_engine
    print("  [12] L21 bound to CompletionEngine  OK")


def test_layer_l29_is_cost_controller():
    sys_ = SystemBootstrap()
    sys_.wire()
    instance = sys_.registry.get_instance("L29")
    assert instance is sys_.cost_controller
    print("  [13] L29 bound to CostController  OK")


def test_layer_l28_is_loop_monitor():
    sys_ = SystemBootstrap()
    sys_.wire()
    instance = sys_.registry.get_instance("L28")
    assert instance is sys_.loop_monitor
    print("  [14] L28 bound to LoopMonitor  OK")


# ======================================================================== #
# 4. End-to-end cycle
# ======================================================================== #


def test_cycle_success():
    """Full MainLoop cycle through bootstrap with real hooks."""
    sys_ = SystemBootstrap()
    sys_.wire()

    inp = CycleInput(
        intent="Test bootstrap cycle",
        spec_twin_id="SPEC-BOOT-001",
        auto_approve=True,
    )
    result = run(sys_.run_cycle(inp))
    assert result.outcome == CycleOutcome.SUCCESS, (
        f"Expected SUCCESS, got {result.outcome}: {result.error}"
    )
    assert result.final_state == WorkStateEnum.DRAFT  # returned to DRAFT
    print("  [15] Full cycle SUCCESS through bootstrap  OK")


def test_cycle_produces_evidence():
    sys_ = SystemBootstrap()
    sys_.wire()

    inp = CycleInput(
        intent="Evidence test cycle",
        spec_twin_id="SPEC-BOOT-002",
        auto_approve=True,
    )
    result = run(sys_.run_cycle(inp))
    assert result.outcome == CycleOutcome.SUCCESS
    assert len(result.evidence_bundles) > 0
    assert sys_.evidence_store.count() > 0
    print(f"  [16] Cycle produced {len(result.evidence_bundles)} evidence bundles  OK")


def test_cycle_updates_trust():
    sys_ = SystemBootstrap()
    sys_.wire()

    # Trust should still be high after successful cycle
    inp = CycleInput(
        intent="Trust test",
        spec_twin_id="SPEC-BOOT-003",
        auto_approve=True,
    )
    run(sys_.run_cycle(inp))
    assert sys_.trust_state.score > 0.5
    print(f"  [17] Trust score after cycle: {sys_.trust_state.score:.2f}  OK")


def test_summary():
    sys_ = SystemBootstrap()
    sys_.wire()
    summary = sys_.summary()
    assert summary["wired"] is True
    assert summary["work_state"] == "DRAFT"
    assert summary["security_state"] == "NORMAL"
    assert summary["trust_score"] == 1.0
    print("  [18] System summary  OK")


def test_cycle_blocked_by_security_lockdown():
    """Cycle should fail when security is in LOCKDOWN."""
    sys_ = SystemBootstrap()
    sys_.wire()

    # Escalate to LOCKDOWN
    sys_.security_state.escalate(SecurityStateEnum.LOCKDOWN, "TEST-LOCKDOWN")

    inp = CycleInput(
        intent="Should be blocked",
        spec_twin_id="SPEC-BLOCK-001",
        auto_approve=True,
    )
    result = run(sys_.run_cycle(inp))
    # Should fail at PLANNING (security check)
    assert result.outcome == CycleOutcome.FAILED
    print("  [19] Cycle blocked by LOCKDOWN  OK")


def test_multiple_cycles():
    """Run 3 cycles sequentially."""
    sys_ = SystemBootstrap()
    sys_.wire()

    for i in range(3):
        inp = CycleInput(
            intent=f"Multi-cycle test {i + 1}",
            spec_twin_id=f"SPEC-MULTI-{i + 1:03d}",
            auto_approve=True,
        )
        result = run(sys_.run_cycle(inp))
        assert result.outcome == CycleOutcome.SUCCESS, f"Cycle {i + 1} failed: {result.error}"
    print("  [20] 3 sequential cycles all SUCCESS  OK")


# ======================================================================== #
# 5. Hooks verification
# ======================================================================== #


def test_hook_conflict_check_with_conflicting_rules():
    """Conflict hook should detect rule conflicts."""
    import asyncio
    from kdexter.ledger.rule_ledger import Rule, RuleProvenance
    from kdexter.loops.concurrency import LoopPriority

    sys_ = SystemBootstrap()
    sys_.wire()

    # Add conflicting rules
    r1 = Rule(name="buy_signal", condition="price > 100", action="BUY")
    r1.provenance = RuleProvenance(source_incident="TEST", author_layer="L9")
    r2 = Rule(name="sell_signal", condition="price > 100", action="SELL")
    r2.provenance = RuleProvenance(source_incident="TEST", author_layer="L9")

    async def add_rules():
        await sys_.rule_ledger.create(r1, LoopPriority.MAIN)
        await sys_.rule_ledger.create(r2, LoopPriority.MAIN)

    run(add_rules())

    # Now conflict engine should detect
    result = sys_.conflict_engine.check(sys_.rule_ledger.list_all())
    assert result.conflict_count == 1
    print("  [21] Hook detects conflicting rules  OK")


def test_hook_budget_exceeded():
    """Budget hook should fail when cost exceeds limit."""
    sys_ = SystemBootstrap()
    sys_.wire()

    sys_.cost_controller.set_budget("API_CALLS", limit=100)
    sys_.cost_controller.record_usage("API_CALLS", 150)

    inp = CycleInput(
        intent="Budget test",
        spec_twin_id="SPEC-BUDGET-001",
        auto_approve=True,
    )
    result = run(sys_.run_cycle(inp))
    # Should fail at VALIDATING BUDGET_CHECK
    assert result.outcome == CycleOutcome.FAILED
    assert "Budget exceeded" in (result.error or "")
    print("  [22] Cycle fails on budget exceeded  OK")


# ======================================================================== #
# 6. New layer bindings (L22, L27, L18, L23, L24, L25, L30, L8)
# ======================================================================== #


def test_layer_l22_is_spec_lock():
    sys_ = SystemBootstrap()
    sys_.wire()
    assert sys_.registry.get_instance("L22") is sys_.spec_lock
    print("  [23] L22 bound to SpecLockEngine  OK")


def test_layer_l27_is_override_controller():
    sys_ = SystemBootstrap()
    sys_.wire()
    assert sys_.registry.get_instance("L27") is sys_.override_controller
    print("  [24] L27 bound to OverrideController  OK")


def test_layer_l18_is_budget_evolution():
    sys_ = SystemBootstrap()
    sys_.wire()
    assert sys_.registry.get_instance("L18") is sys_.budget_evolution
    print("  [25] L18 bound to BudgetEvolutionEngine  OK")


def test_layer_l23_is_research_engine():
    sys_ = SystemBootstrap()
    sys_.wire()
    assert sys_.registry.get_instance("L23") is sys_.research_engine
    print("  [26] L23 bound to ResearchEngine  OK")


def test_layer_l24_is_knowledge_engine():
    sys_ = SystemBootstrap()
    sys_.wire()
    assert sys_.registry.get_instance("L24") is sys_.knowledge_engine
    print("  [27] L24 bound to KnowledgeEngine  OK")


def test_layer_l25_is_scheduler_engine():
    sys_ = SystemBootstrap()
    sys_.wire()
    assert sys_.registry.get_instance("L25") is sys_.scheduler_engine
    print("  [28] L25 bound to SchedulerEngine  OK")


def test_layer_l30_is_progress_engine():
    sys_ = SystemBootstrap()
    sys_.wire()
    assert sys_.registry.get_instance("L30") is sys_.progress_engine
    print("  [29] L30 bound to ProgressEngine  OK")


def test_layer_l8_is_execution_cell():
    sys_ = SystemBootstrap()
    sys_.wire()
    assert sys_.registry.get_instance("L8") is sys_.execution_cell
    print("  [30] L8 bound to ExecutionCell  OK")


# ======================================================================== #
# 7. Strategy pipeline wiring
# ======================================================================== #


def test_strategy_pipeline_wired():
    sys_ = SystemBootstrap()
    sys_.wire()
    assert sys_.risk_filter is not None
    assert sys_.position_sizer is not None
    assert sys_.execution_cell is not None
    assert sys_.strategy_pipeline is not None
    print("  [31] Strategy pipeline wired  OK")


def test_signal_queue_exists():
    sys_ = SystemBootstrap()
    sys_.wire()
    assert isinstance(sys_.signal_queue, list)
    assert len(sys_.signal_queue) == 0
    print("  [32] Signal queue initialized empty  OK")


def test_cycle_with_spec_lock():
    """Cycle should pass with spec lock unlocked (default)."""
    sys_ = SystemBootstrap()
    sys_.wire()
    # Lock is unlocked by default -> check_lock should pass
    inp = CycleInput(
        intent="Spec lock test",
        spec_twin_id="SPEC-LOCK-001",
        auto_approve=True,
    )
    result = run(sys_.run_cycle(inp))
    assert result.outcome == CycleOutcome.SUCCESS
    print("  [33] Cycle with spec lock unlocked passes  OK")


# ======================================================================== #
# Runner
# ======================================================================== #

if __name__ == "__main__":
    print("\nBootstrap Tests (System Wiring & Lifecycle)")
    print("=" * 60)

    tests = [
        (
            "Wiring",
            [
                test_wire_creates_all_components,
                test_wire_binds_layers,
                test_wire_registry_summary,
                test_wire_sets_flag,
            ],
        ),
        (
            "Engine Wiring",
            [
                test_engines_wired,
                test_trust_engine_has_system_component,
                test_conflict_engine_checks_rule_ledger,
                test_cost_controller_starts_empty,
            ],
        ),
        (
            "Layer Bindings",
            [
                test_layer_l15_is_drift_engine,
                test_layer_l16_is_conflict_engine,
                test_layer_l19_is_trust_engine,
                test_layer_l21_is_completion_engine,
                test_layer_l29_is_cost_controller,
                test_layer_l28_is_loop_monitor,
            ],
        ),
        (
            "End-to-End Cycles",
            [
                test_cycle_success,
                test_cycle_produces_evidence,
                test_cycle_updates_trust,
                test_summary,
                test_cycle_blocked_by_security_lockdown,
                test_multiple_cycles,
            ],
        ),
        (
            "Hook Verification",
            [
                test_hook_conflict_check_with_conflicting_rules,
                test_hook_budget_exceeded,
            ],
        ),
        (
            "New Layer Bindings",
            [
                test_layer_l22_is_spec_lock,
                test_layer_l27_is_override_controller,
                test_layer_l18_is_budget_evolution,
                test_layer_l23_is_research_engine,
                test_layer_l24_is_knowledge_engine,
                test_layer_l25_is_scheduler_engine,
                test_layer_l30_is_progress_engine,
                test_layer_l8_is_execution_cell,
            ],
        ),
        (
            "Strategy Pipeline",
            [
                test_strategy_pipeline_wired,
                test_signal_queue_exists,
                test_cycle_with_spec_lock,
            ],
        ),
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
