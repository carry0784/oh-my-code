"""
Tier 2 Tests — Governance (Doctrine + B1 Constitution + B2 Orchestration)
K-Dexter AOS v4

Tests:
  1. DoctrineRegistry: core doctrines, ratification, compliance, violations
  2. B1Constitution: enforce, forbidden bridge, LOCKDOWN, invariants
  3. B2Orchestration: attribution, change approval, pipeline, authority

Run: python tests/test_tier2.py
"""
from __future__ import annotations

import sys

from kdexter.audit.evidence_store import EvidenceStore
from kdexter.governance.doctrine import (
    DoctrineArticle,
    DoctrineRatificationError,
    DoctrineRegistry,
    DoctrineSeverity,
    DoctrineStatus,
    GovernanceTier,
)
from kdexter.governance.b1_constitution import (
    B1Constitution,
    ConstitutionalViolationError,
)
from kdexter.governance.b2_orchestration import (
    ApprovalStatus,
    B2Orchestration,
    ChangeRequest,
    PipelineStage,
    PipelineValidationError,
)
from kdexter.ledger.forbidden_ledger import ForbiddenAction, ForbiddenLedger
from kdexter.state_machine.security_state import SecurityStateContext, SecurityStateEnum


# ======================================================================== #
# 1. DoctrineRegistry
# ======================================================================== #

def test_core_doctrines_loaded():
    reg = DoctrineRegistry()
    assert reg.count() == 10
    for i in range(1, 11):
        d_id = f"D-{str(i).zfill(3)}"
        assert reg.is_ratified(d_id), f"{d_id} should be ratified"
    print("  [1] Core 10 doctrines loaded  OK")


def test_doctrine_get():
    reg = DoctrineRegistry()
    d001 = reg.get("D-001")
    assert d001 is not None
    assert d001.name == "TCL-only execution"
    assert d001.severity == DoctrineSeverity.CONSTITUTIONAL
    print("  [2] Doctrine get  OK")


def test_doctrine_list_by_severity():
    reg = DoctrineRegistry()
    constitutional = reg.list_by_severity(DoctrineSeverity.CONSTITUTIONAL)
    assert len(constitutional) >= 5  # D-001~D-005, D-009
    critical = reg.list_by_severity(DoctrineSeverity.CRITICAL)
    assert len(critical) >= 3  # D-006~D-008, D-010
    print("  [3] Doctrine list_by_severity  OK")


def test_doctrine_ratify_b1():
    reg = DoctrineRegistry()
    new_article = DoctrineArticle(
        doctrine_id="D-100",
        name="custom rule",
        description="test custom doctrine",
        severity=DoctrineSeverity.ADVISORY,
        constraint="custom_field == True",
    )
    d_id = reg.ratify(new_article, ratified_by="L1")
    assert d_id == "D-100"
    assert reg.count() == 11
    assert reg.is_ratified("D-100")
    print("  [4] Doctrine ratify (B1)  OK")


def test_doctrine_ratify_unauthorized():
    reg = DoctrineRegistry()
    new_article = DoctrineArticle(
        doctrine_id="D-200",
        name="bad",
        description="unauthorized",
        severity=DoctrineSeverity.ADVISORY,
        constraint="x == True",
    )
    try:
        reg.ratify(new_article, ratified_by="A_RUNTIME")
        assert False, "Should have raised DoctrineRatificationError"
    except DoctrineRatificationError:
        pass
    print("  [5] Doctrine ratify unauthorized rejected  OK")


def test_doctrine_compliance_pass():
    reg = DoctrineRegistry()
    context = {
        "actor": "MainLoop",
        "via_tcl": True,
        "evidence_bundle_count": 5,
        "expected_evidence_count": 5,
        "provenance": True,
        "intent": "test intent",
        "risk_checked": True,
        "lock_held": True,
    }
    violations = reg.check_compliance(context)
    assert len(violations) == 0
    print("  [6] Doctrine compliance pass  OK")


def test_doctrine_compliance_violation():
    reg = DoctrineRegistry()
    # Missing intent → D-007 violated
    context = {
        "actor": "BadActor",
        "via_tcl": True,
        "provenance": True,
        "intent": "",           # empty intent
        "risk_checked": True,
        "lock_held": True,
        "evidence_bundle_count": 1,
        "expected_evidence_count": 1,
    }
    violations = reg.check_compliance(context)
    violated_ids = {v.doctrine_id for v in violations}
    assert "D-007" in violated_ids
    print("  [7] Doctrine compliance violation detected  OK")


def test_doctrine_violation_recording():
    reg = DoctrineRegistry()
    context = {"actor": "test", "via_tcl": False}  # D-001 violation
    violations = reg.check_compliance(context)
    assert len(violations) >= 1
    assert reg.violation_count() >= 1
    all_v = reg.list_violations("D-001")
    assert len(all_v) >= 1
    print("  [8] Doctrine violation recording  OK")


# ======================================================================== #
# 2. B1Constitution
# ======================================================================== #

def test_b1_enforce_clean():
    doctrine = DoctrineRegistry()
    forbidden = ForbiddenLedger()
    security = SecurityStateContext()
    evidence = EvidenceStore()
    b1 = B1Constitution(doctrine, forbidden, security, evidence)

    context = {
        "actor": "MainLoop",
        "via_tcl": True,
        "evidence_bundle_count": 5,
        "expected_evidence_count": 5,
        "provenance": True,
        "intent": "test",
        "risk_checked": True,
        "lock_held": True,
    }
    violations = b1.enforce(context)
    assert len(violations) == 0
    assert security.current == SecurityStateEnum.NORMAL
    print("  [9] B1 enforce clean  OK")


def test_b1_enforce_constitutional_violation():
    doctrine = DoctrineRegistry()
    forbidden = ForbiddenLedger()
    security = SecurityStateContext()
    evidence = EvidenceStore()
    b1 = B1Constitution(doctrine, forbidden, security, evidence)

    # D-001: via_tcl=False → CONSTITUTIONAL violation → LOCKDOWN
    context = {
        "actor": "BadLayer",
        "via_tcl": False,
        "provenance": True,
        "intent": "test",
        "risk_checked": True,
        "lock_held": True,
        "evidence_bundle_count": 1,
        "expected_evidence_count": 1,
    }
    violations = b1.enforce(context)
    assert len(violations) >= 1
    assert security.current == SecurityStateEnum.LOCKDOWN
    assert evidence.count() >= 1
    print("  [10] B1 enforce CONSTITUTIONAL → LOCKDOWN  OK")


def test_b1_forbidden_bridge():
    doctrine = DoctrineRegistry()
    forbidden = ForbiddenLedger()
    forbidden.register(ForbiddenAction(
        action_id="FA-TEST",
        description="test forbidden",
        severity="BLOCKED",
        pattern="TEST_FORBIDDEN",
        registered_by="B1",
    ))
    security = SecurityStateContext()
    evidence = EvidenceStore()
    b1 = B1Constitution(doctrine, forbidden, security, evidence)

    passed, reason = b1.check_forbidden_action("TEST_FORBIDDEN", {})
    assert not passed
    assert "FA-TEST" in reason
    assert security.current == SecurityStateEnum.QUARANTINED
    print("  [11] B1 forbidden bridge  OK")


def test_b1_lockdown_release():
    doctrine = DoctrineRegistry()
    forbidden = ForbiddenLedger()
    security = SecurityStateContext()
    evidence = EvidenceStore()
    b1 = B1Constitution(doctrine, forbidden, security, evidence)

    # Put into LOCKDOWN
    security.escalate(SecurityStateEnum.LOCKDOWN, "test")
    assert b1.is_locked_down()

    # Unauthorized release
    try:
        b1.release_lockdown("B2", "want to release")
        assert False, "Should have raised ConstitutionalViolationError"
    except ConstitutionalViolationError:
        pass

    # Authorized release
    ok = b1.release_lockdown("L27_HUMAN", "operator override")
    assert ok
    assert security.current == SecurityStateEnum.NORMAL
    print("  [12] B1 LOCKDOWN release (Human only)  OK")


def test_b1_invariants():
    doctrine = DoctrineRegistry()
    forbidden = ForbiddenLedger()
    security = SecurityStateContext()
    evidence = EvidenceStore()
    b1 = B1Constitution(doctrine, forbidden, security, evidence)

    violations = b1.check_invariants()
    assert len(violations) == 0  # all core doctrines present and ratified
    print("  [13] B1 invariants hold  OK")


def test_b1_core_doctrine_suspension_blocked():
    doctrine = DoctrineRegistry()
    forbidden = ForbiddenLedger()
    security = SecurityStateContext()
    evidence = EvidenceStore()
    b1 = B1Constitution(doctrine, forbidden, security, evidence)

    try:
        b1.suspend_doctrine("D-001", "want to suspend")
        assert False, "Should have raised ConstitutionalViolationError"
    except ConstitutionalViolationError:
        pass
    print("  [14] B1 core doctrine suspension blocked  OK")


def test_b1_ratify_new_doctrine():
    doctrine = DoctrineRegistry()
    forbidden = ForbiddenLedger()
    security = SecurityStateContext()
    evidence = EvidenceStore()
    b1 = B1Constitution(doctrine, forbidden, security, evidence)

    new = DoctrineArticle(
        doctrine_id="D-050",
        name="custom",
        description="test",
        severity=DoctrineSeverity.ADVISORY,
        constraint="x == True",
    )
    d_id = b1.ratify_doctrine(new)
    assert d_id == "D-050"
    assert doctrine.is_ratified("D-050")
    assert evidence.count() >= 1  # ratification evidence
    print("  [15] B1 ratify new doctrine  OK")


# ======================================================================== #
# 3. B2Orchestration
# ======================================================================== #

def test_b2_attribution():
    assert B2Orchestration.get_attribution("L1").tier == GovernanceTier.B1
    assert B2Orchestration.get_attribution("L11").tier == GovernanceTier.B2
    assert B2Orchestration.get_attribution("L6").tier == GovernanceTier.A
    assert B2Orchestration.get_attribution("L99") is None
    print("  [16] B2 attribution lookup  OK")


def test_b2_tier_layers():
    b1_layers = B2Orchestration.get_tier_layers(GovernanceTier.B1)
    b2_layers = B2Orchestration.get_tier_layers(GovernanceTier.B2)
    a_layers = B2Orchestration.get_tier_layers(GovernanceTier.A)
    assert len(b1_layers) == 5
    assert len(a_layers) == 5
    assert len(b2_layers) == 20  # 21 minus L22 which is B1
    print("  [17] B2 tier layer counts  OK")


def test_b2_can_modify():
    # B2 can modify B2 and A layers
    assert B2Orchestration.can_modify("L11", "B2")
    assert B2Orchestration.can_modify("L6", "B2")
    # B2 cannot modify B1 layers
    assert not B2Orchestration.can_modify("L1", "B2")
    assert not B2Orchestration.can_modify("L3", "B2")
    # Human can modify anything
    assert B2Orchestration.can_modify("L1", "HUMAN")
    assert B2Orchestration.can_modify("L27", "HUMAN")
    # A cannot modify anything
    assert not B2Orchestration.can_modify("L11", "A")
    print("  [18] B2 can_modify authority check  OK")


def test_b2_approve_change():
    doctrine = DoctrineRegistry()
    evidence = EvidenceStore()
    b2 = B2Orchestration(doctrine, evidence)

    cr = ChangeRequest(
        target_layer="L11",
        change_type="RULE",
        description="add new rule",
        requester="B2",
    )
    approved = b2.approve_change(cr)
    assert approved
    assert cr.status == ApprovalStatus.APPROVED
    assert cr.doctrine_compliant
    assert b2.change_count() == 1
    print("  [19] B2 approve change  OK")


def test_b2_deny_unauthorized():
    doctrine = DoctrineRegistry()
    evidence = EvidenceStore()
    b2 = B2Orchestration(doctrine, evidence)

    cr = ChangeRequest(
        target_layer="L1",      # B1/Human-only layer
        change_type="CODE",
        description="modify L1",
        requester="B2",         # B2 cannot modify L1
    )
    approved = b2.approve_change(cr)
    assert not approved
    assert cr.status == ApprovalStatus.DENIED
    assert "lacks authority" in cr.denial_reason
    print("  [20] B2 deny unauthorized change  OK")


def test_b2_pipeline():
    doctrine = DoctrineRegistry()
    evidence = EvidenceStore()
    b2 = B2Orchestration(doctrine, evidence)

    stages = [
        PipelineStage("S1", "L4", "G-01", 1, "Clarify"),
        PipelineStage("S2", "L11", "G-18", 2, "Rule Ledger"),
        PipelineStage("S3", "L8", "G-05", 3, "Execute"),
    ]
    b2.register_pipeline("MAIN_PIPELINE", stages)
    assert "MAIN_PIPELINE" in b2.list_pipelines()

    pipeline = b2.get_pipeline("MAIN_PIPELINE")
    assert len(pipeline) == 3
    assert pipeline[0].stage_id == "S1"  # sorted by order
    print("  [21] B2 pipeline registration  OK")


def test_b2_pipeline_validation():
    doctrine = DoctrineRegistry()
    evidence = EvidenceStore()
    b2 = B2Orchestration(doctrine, evidence)

    # Stage with A-layer and no gate
    stages = [
        PipelineStage("S1", "L6", None, 1, "Agent without gate"),
    ]
    b2.register_pipeline("TEST_PIPE", stages)
    issues = b2.validate_pipeline("TEST_PIPE")
    assert len(issues) >= 1
    assert "no gate" in issues[0].lower()
    print("  [22] B2 pipeline validation  OK")


def test_b2_pipeline_invalid_layer():
    doctrine = DoctrineRegistry()
    evidence = EvidenceStore()
    b2 = B2Orchestration(doctrine, evidence)

    stages = [
        PipelineStage("S1", "L99", None, 1, "Unknown layer"),
    ]
    try:
        b2.register_pipeline("BAD_PIPE", stages)
        assert False, "Should have raised PipelineValidationError"
    except PipelineValidationError:
        pass
    print("  [23] B2 pipeline invalid layer rejected  OK")


def test_b2_change_log():
    doctrine = DoctrineRegistry()
    evidence = EvidenceStore()
    b2 = B2Orchestration(doctrine, evidence)

    cr1 = ChangeRequest(target_layer="L11", change_type="RULE", requester="B2")
    cr2 = ChangeRequest(target_layer="L1", change_type="CODE", requester="B2")
    b2.approve_change(cr1)
    b2.approve_change(cr2)

    approved = b2.list_changes(ApprovalStatus.APPROVED)
    denied = b2.list_changes(ApprovalStatus.DENIED)
    assert len(approved) == 1
    assert len(denied) == 1
    assert b2.change_count() == 2
    print("  [24] B2 change log  OK")


# ======================================================================== #
# Runner
# ======================================================================== #

if __name__ == "__main__":
    print("\nTier 2 Tests -- Governance (Doctrine + B1 + B2)")
    print("=" * 60)

    tests = [
        ("DoctrineRegistry", [
            test_core_doctrines_loaded,
            test_doctrine_get,
            test_doctrine_list_by_severity,
            test_doctrine_ratify_b1,
            test_doctrine_ratify_unauthorized,
            test_doctrine_compliance_pass,
            test_doctrine_compliance_violation,
            test_doctrine_violation_recording,
        ]),
        ("B1Constitution", [
            test_b1_enforce_clean,
            test_b1_enforce_constitutional_violation,
            test_b1_forbidden_bridge,
            test_b1_lockdown_release,
            test_b1_invariants,
            test_b1_core_doctrine_suspension_blocked,
            test_b1_ratify_new_doctrine,
        ]),
        ("B2Orchestration", [
            test_b2_attribution,
            test_b2_tier_layers,
            test_b2_can_modify,
            test_b2_approve_change,
            test_b2_deny_unauthorized,
            test_b2_pipeline,
            test_b2_pipeline_validation,
            test_b2_pipeline_invalid_layer,
            test_b2_change_log,
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
