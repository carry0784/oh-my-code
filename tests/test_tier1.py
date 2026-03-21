"""
Tier 1 Tests — Ledger 3종 + EvidenceStore
K-Dexter AOS v4

Tests:
  1. EvidenceStore: store/get/count/list
  2. MandatoryLedger: 18 items, exemptions, satisfaction checks
  3. ForbiddenLedger: register, check, enforce + escalate
  4. RuleLedger: CRUD, provenance enforcement, change count, lock

Run: python tests/test_tier1.py
"""
from __future__ import annotations

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from kdexter.audit.evidence_store import EvidenceBundle, EvidenceStore
from kdexter.ledger.mandatory_ledger import MandatoryLedger, MandatoryItem, LoopType
from kdexter.ledger.forbidden_ledger import ForbiddenLedger, ForbiddenAction
from kdexter.ledger.rule_ledger import (
    RuleLedger, Rule, RuleProvenance,
    ProvenanceRequiredError, RuleNotFoundError,
)
from kdexter.loops.concurrency import RuleLedgerLock, LoopPriority
from kdexter.state_machine.work_state import WorkStateContext
from kdexter.state_machine.security_state import SecurityStateContext, SecurityStateEnum


# ═══════════════════════════════════════════════════════════════════════════ #
# 1. EvidenceStore
# ═══════════════════════════════════════════════════════════════════════════ #

def test_evidence_store_basic():
    store = EvidenceStore()
    assert store.count() == 0

    b1 = EvidenceBundle(trigger="test", actor="TestRunner", action="CREATE")
    bid = store.store(b1)
    assert bid == b1.bundle_id
    assert store.count() == 1
    assert store.get(bid) is b1
    print("  [1] EvidenceStore basic  OK")


def test_evidence_store_count_cycle():
    store = EvidenceStore()
    store.store(EvidenceBundle(actor="A", cycle_id="C-001"))
    store.store(EvidenceBundle(actor="A", cycle_id="C-001"))
    store.store(EvidenceBundle(actor="B", cycle_id="C-002"))

    assert store.count() == 3
    assert store.count_for_cycle("C-001") == 2
    assert store.count_for_cycle("C-002") == 1
    assert store.count_for_cycle("C-999") == 0
    print("  [2] EvidenceStore count_for_cycle  OK")


def test_evidence_store_list_by_trigger():
    store = EvidenceStore()
    store.store(EvidenceBundle(trigger="Gate.G-01", actor="GE"))
    store.store(EvidenceBundle(trigger="Gate.G-02", actor="GE"))
    store.store(EvidenceBundle(trigger="MainLoop.transition", actor="ML"))

    assert len(store.list_by_trigger("Gate.")) == 2
    assert len(store.list_by_trigger("MainLoop.")) == 1
    print("  [3] EvidenceStore list_by_trigger  OK")


def test_evidence_store_clear():
    store = EvidenceStore()
    store.store(EvidenceBundle())
    store.store(EvidenceBundle())
    assert store.count() == 2
    store.clear()
    assert store.count() == 0
    print("  [4] EvidenceStore clear  OK")


# ═══════════════════════════════════════════════════════════════════════════ #
# 2. MandatoryLedger
# ═══════════════════════════════════════════════════════════════════════════ #

def test_mandatory_18_items():
    ledger = MandatoryLedger()
    items = ledger.get_all()
    assert len(items) == 18
    ids = {i.item_id for i in items}
    expected = {f"M-{str(n).zfill(2)}" for n in range(1, 19)}
    assert ids == expected
    print("  [5] MandatoryLedger 18 items  OK")


def test_mandatory_get_item():
    ledger = MandatoryLedger()
    m01 = ledger.get_item("M-01")
    assert m01.name == "clarify"
    assert m01.enforcement_state == "CLARIFYING"
    print("  [6] MandatoryLedger get_item  OK")


def test_mandatory_recovery_exemptions():
    ledger = MandatoryLedger()
    required = ledger.get_required_items(LoopType.RECOVERY)
    required_ids = {i.item_id for i in required}

    # Recovery exempts 10 items, so 8 remain required
    assert len(required) == 8
    # M-03, M-04, M-07, M-08, M-09, M-10, M-14, M-16 should be required
    expected_required = {"M-03", "M-04", "M-07", "M-08", "M-09", "M-10", "M-14", "M-16"}
    assert required_ids == expected_required

    # Main loop: all 18 required
    assert len(ledger.get_required_items(LoopType.MAIN)) == 18
    print("  [7] MandatoryLedger Recovery exemptions (10)  OK")


def test_mandatory_check_satisfied():
    ledger = MandatoryLedger()
    ctx = WorkStateContext()

    # M-01: intent not set → unsatisfied
    assert not ledger.check_satisfied("M-01", ctx)

    ctx.intent = "test intent"
    assert ledger.check_satisfied("M-01", ctx)

    # M-03: risk_checked
    assert not ledger.check_satisfied("M-03", ctx)
    ctx.risk_checked = True
    assert ledger.check_satisfied("M-03", ctx)
    print("  [8] MandatoryLedger check_satisfied  OK")


def test_mandatory_list_unsatisfied():
    ledger = MandatoryLedger()
    ctx = WorkStateContext()

    # Fresh context: M-01, M-02, M-03, M-04, M-05, M-06, M-10, M-16, M-18 unsatisfied
    unsatisfied = ledger.list_unsatisfied(LoopType.MAIN, ctx)
    unsatisfied_ids = {i.item_id for i in unsatisfied}
    assert "M-01" in unsatisfied_ids
    assert "M-03" in unsatisfied_ids

    # Fill all fields
    ctx.intent = "test"
    ctx.spec_twin_id = "SPEC-001"
    ctx.risk_checked = True
    ctx.security_checked = True
    ctx.rollback_plan_ready = True
    ctx.recovery_simulation_done = True
    ctx.provenance_recorded = True
    ctx.completion_score = 0.95
    ctx.research_complete = True

    assert ledger.all_satisfied(LoopType.MAIN, ctx)
    print("  [9] MandatoryLedger list_unsatisfied  OK")


def test_mandatory_is_exempt():
    ledger = MandatoryLedger()
    assert ledger.is_exempt("M-01", LoopType.RECOVERY)
    assert not ledger.is_exempt("M-01", LoopType.MAIN)
    assert ledger.is_exempt("M-18", LoopType.RECOVERY)
    assert not ledger.is_exempt("M-07", LoopType.RECOVERY)  # M-07 always required
    print("  [10] MandatoryLedger is_exempt  OK")


# ═══════════════════════════════════════════════════════════════════════════ #
# 3. ForbiddenLedger
# ═══════════════════════════════════════════════════════════════════════════ #

def test_forbidden_register_and_check():
    ledger = ForbiddenLedger()
    fa = ForbiddenAction(
        action_id="FA-001",
        description="Direct API call",
        severity="LOCKDOWN",
        pattern="DIRECT_API_CALL",
        registered_by="B1",
    )
    ledger.register(fa)
    assert len(ledger.list_actions()) == 1

    # No match
    assert ledger.check("NORMAL_ACTION") is None

    # Exact match
    matched = ledger.check("DIRECT_API_CALL")
    assert matched is not None
    assert matched.action_id == "FA-001"
    print("  [11] ForbiddenLedger register + check  OK")


def test_forbidden_wildcard_match():
    ledger = ForbiddenLedger()
    ledger.register(ForbiddenAction(
        action_id="FA-002",
        description="Any bypass attempt",
        severity="BLOCKED",
        pattern="BYPASS_*",
        registered_by="B1",
    ))

    assert ledger.check("BYPASS_GATE") is not None
    assert ledger.check("BYPASS_AUTH") is not None
    assert ledger.check("NORMAL") is None
    print("  [12] ForbiddenLedger wildcard match  OK")


def test_forbidden_enforce_lockdown():
    ledger = ForbiddenLedger()
    ledger.register(ForbiddenAction(
        action_id="FA-001",
        description="Direct API call",
        severity="LOCKDOWN",
        pattern="DIRECT_API_CALL",
        registered_by="B1",
    ))

    sec = SecurityStateContext()
    store = EvidenceStore()

    passed, reason = ledger.check_and_enforce(
        "DIRECT_API_CALL", {"target": "binance"},
        sec, store,
    )

    assert not passed
    assert "FA-001" in reason
    assert sec.current == SecurityStateEnum.LOCKDOWN
    assert store.count() == 1
    assert ledger.violation_count() == 1
    print("  [13] ForbiddenLedger enforce LOCKDOWN  OK")


def test_forbidden_enforce_blocked():
    ledger = ForbiddenLedger()
    ledger.register(ForbiddenAction(
        action_id="FA-003",
        description="Unsafe operation",
        severity="BLOCKED",
        pattern="UNSAFE_OP",
        registered_by="B1",
    ))

    sec = SecurityStateContext()
    store = EvidenceStore()

    passed, reason = ledger.check_and_enforce("UNSAFE_OP", {}, sec, store)
    assert not passed
    assert sec.current == SecurityStateEnum.QUARANTINED
    print("  [14] ForbiddenLedger enforce BLOCKED  OK")


def test_forbidden_no_violation():
    ledger = ForbiddenLedger()
    sec = SecurityStateContext()
    store = EvidenceStore()

    passed, reason = ledger.check_and_enforce("NORMAL_ACTION", {}, sec, store)
    assert passed
    assert reason == ""
    assert sec.current == SecurityStateEnum.NORMAL
    assert store.count() == 0
    print("  [15] ForbiddenLedger no violation  OK")


# ═══════════════════════════════════════════════════════════════════════════ #
# 4. RuleLedger
# ═══════════════════════════════════════════════════════════════════════════ #

def _prov(incident: str = "INC-001") -> RuleProvenance:
    return RuleProvenance(
        source_incident=incident,
        author_layer="L5",
        rationale="test rule",
    )


def test_rule_create():
    lock = RuleLedgerLock()
    ledger = RuleLedger(lock)

    rule = Rule(name="max_loss", condition="loss > 0.05", action="BLOCK",
                provenance=_prov())
    rid = asyncio.run(ledger.create(rule, LoopPriority.MAIN))

    assert ledger.read(rid) is rule
    assert len(ledger.list_all()) == 1
    assert ledger.rule_change_count() == 1
    print("  [16] RuleLedger create  OK")


def test_rule_provenance_required():
    lock = RuleLedgerLock()
    ledger = RuleLedger(lock)

    rule = Rule(name="no_prov")  # no provenance
    try:
        asyncio.run(ledger.create(rule, LoopPriority.MAIN))
        assert False, "Should have raised ProvenanceRequiredError"
    except ProvenanceRequiredError:
        pass
    print("  [17] RuleLedger provenance enforcement  OK")


def test_rule_update():
    lock = RuleLedgerLock()
    ledger = RuleLedger(lock)

    rule = Rule(name="test", condition="a > b", action="WARN",
                provenance=_prov())
    rid = asyncio.run(ledger.create(rule, LoopPriority.MAIN))

    updated = asyncio.run(ledger.update(
        rid, {"condition": "a > c"}, _prov("INC-002"), LoopPriority.MAIN,
    ))
    assert updated.condition == "a > c"
    assert updated.version == 2
    assert ledger.rule_change_count() == 2  # 1 create + 1 update
    print("  [18] RuleLedger update  OK")


def test_rule_delete():
    lock = RuleLedgerLock()
    ledger = RuleLedger(lock)

    rule = Rule(name="to_delete", provenance=_prov())
    rid = asyncio.run(ledger.create(rule, LoopPriority.MAIN))

    asyncio.run(ledger.delete(rid, _prov("INC-003"), LoopPriority.MAIN))
    assert ledger.read(rid).enabled is False  # soft delete
    assert len(ledger.list_all(enabled_only=True)) == 0
    assert len(ledger.list_all(enabled_only=False)) == 1
    print("  [19] RuleLedger delete (soft)  OK")


def test_rule_change_count_since():
    from datetime import timedelta
    lock = RuleLedgerLock()
    ledger = RuleLedger(lock)

    rule = Rule(name="r1", provenance=_prov())
    asyncio.run(ledger.create(rule, LoopPriority.MAIN))

    # All changes since epoch
    from datetime import datetime
    assert ledger.rule_change_count(since=datetime(2000, 1, 1)) == 1
    # No changes in the future
    assert ledger.rule_change_count(since=datetime(2099, 1, 1)) == 0
    print("  [20] RuleLedger change_count since  OK")


def test_rule_change_history():
    lock = RuleLedgerLock()
    ledger = RuleLedger(lock)

    rule = Rule(name="hist", provenance=_prov())
    rid = asyncio.run(ledger.create(rule, LoopPriority.MAIN))
    asyncio.run(ledger.update(rid, {"name": "hist2"}, _prov(), LoopPriority.MAIN))

    history = ledger.change_history(rid)
    assert len(history) == 2
    assert history[0].change_type == "CREATE"
    assert history[1].change_type == "UPDATE"
    assert history[1].before_snapshot["name"] == "hist"
    assert history[1].after_snapshot["name"] == "hist2"
    print("  [21] RuleLedger change_history  OK")


def test_rule_not_found():
    lock = RuleLedgerLock()
    ledger = RuleLedger(lock)

    assert ledger.read("NONEXISTENT") is None
    try:
        asyncio.run(ledger.update("NONEXISTENT", {}, _prov(), LoopPriority.MAIN))
        assert False, "Should have raised RuleNotFoundError"
    except RuleNotFoundError:
        pass
    print("  [22] RuleLedger not found  OK")


# ═══════════════════════════════════════════════════════════════════════════ #
# Runner
# ═══════════════════════════════════════════════════════════════════════════ #

if __name__ == "__main__":
    print("\nTier 1 Tests — Ledger 3종 + EvidenceStore")
    print("=" * 60)

    tests = [
        ("EvidenceStore", [
            test_evidence_store_basic,
            test_evidence_store_count_cycle,
            test_evidence_store_list_by_trigger,
            test_evidence_store_clear,
        ]),
        ("MandatoryLedger", [
            test_mandatory_18_items,
            test_mandatory_get_item,
            test_mandatory_recovery_exemptions,
            test_mandatory_check_satisfied,
            test_mandatory_list_unsatisfied,
            test_mandatory_is_exempt,
        ]),
        ("ForbiddenLedger", [
            test_forbidden_register_and_check,
            test_forbidden_wildcard_match,
            test_forbidden_enforce_lockdown,
            test_forbidden_enforce_blocked,
            test_forbidden_no_violation,
        ]),
        ("RuleLedger", [
            test_rule_create,
            test_rule_provenance_required,
            test_rule_update,
            test_rule_delete,
            test_rule_change_count_since,
            test_rule_change_history,
            test_rule_not_found,
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
