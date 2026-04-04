"""
Tests for Phase 9 minimal — Recovery Policy Engine, Safe Mode state machine,
and drift event consumer.

Coverage:
  - drift event → NORMAL → SM3 entry
  - duplicate drift → suppression
  - SM3 state → additional drift → no re-entry
  - manual downward transition without approval → rejected
  - manual approval → SM3 → SM2 → SM1 → NORMAL step recovery
  - transition audit records
  - unregistered/skip warning → no Safe Mode entry
  - idempotent consumer re-execution
  - reason code standardization
  - SafeModeStatus/SafeModeTransition model instantiation
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from app.services.runtime_bundle import BundleType, DriftSeverity
from app.services.runtime_verifier import DriftEvent, DriftAction
from app.services.recovery_policy_engine import (
    RecoveryPolicyEngine,
    PolicyDecision,
    SafeModeStateMachine,
    SafeModeError,
    DriftEventConsumer,
    TransitionRecord,
    BUNDLE_TO_REASON,
)
from app.models.safe_mode import (
    SafeModeState,
    SafeModeReasonCode,
    SafeModeStatus,
    SafeModeTransition,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _drift_event(
    bundle_type: BundleType = BundleType.STRATEGY,
    action: DriftAction = DriftAction.REFUSE_LOAD,
    sm3_candidate: bool = True,
    severity: DriftSeverity = DriftSeverity.HIGH,
    expected_hash: str = "a" * 64,
    observed_hash: str = "b" * 64,
    event_id: str | None = None,
) -> DriftEvent:
    e = DriftEvent(
        bundle_type=bundle_type,
        expected_hash=expected_hash,
        observed_hash=observed_hash,
        action=action,
        sm3_candidate=sm3_candidate,
        severity=severity,
    )
    if event_id is not None:
        e.id = event_id
    return e


# ── Recovery Policy Engine ───────────────────────────────────────────


class TestRecoveryPolicyEngine:
    def test_qualifying_event_returns_enter_sm3(self):
        engine = RecoveryPolicyEngine()
        event = _drift_event()
        assert engine.evaluate(event) == PolicyDecision.ENTER_SM3

    def test_runtime_drift_also_qualifies(self):
        engine = RecoveryPolicyEngine()
        event = _drift_event(action=DriftAction.RUNTIME_DRIFT_DETECTED)
        assert engine.evaluate(event) == PolicyDecision.ENTER_SM3

    def test_non_candidate_returns_noop(self):
        engine = RecoveryPolicyEngine()
        event = _drift_event(sm3_candidate=False)
        assert engine.evaluate(event) == PolicyDecision.NOOP

    def test_non_qualifying_action_returns_noop(self):
        engine = RecoveryPolicyEngine()
        event = _drift_event(action=DriftAction.QUARANTINE_CANDIDATE, sm3_candidate=True)
        assert engine.evaluate(event) == PolicyDecision.NOOP

    def test_duplicate_within_cooldown_suppressed(self):
        engine = RecoveryPolicyEngine(cooldown_seconds=300)
        event = _drift_event()
        assert engine.evaluate(event) == PolicyDecision.ENTER_SM3
        # Same fingerprint again
        event2 = _drift_event()
        assert engine.evaluate(event2) == PolicyDecision.DUPLICATE_SUPPRESSED
        assert engine.suppression_count == 1

    def test_different_fingerprint_not_suppressed(self):
        engine = RecoveryPolicyEngine(cooldown_seconds=300)
        event1 = _drift_event(bundle_type=BundleType.STRATEGY)
        event2 = _drift_event(bundle_type=BundleType.RISK_LIMIT)
        assert engine.evaluate(event1) == PolicyDecision.ENTER_SM3
        assert engine.evaluate(event2) == PolicyDecision.ENTER_SM3

    def test_different_hashes_not_suppressed(self):
        engine = RecoveryPolicyEngine(cooldown_seconds=300)
        event1 = _drift_event(expected_hash="a" * 64, observed_hash="b" * 64)
        event2 = _drift_event(expected_hash="a" * 64, observed_hash="c" * 64)
        assert engine.evaluate(event1) == PolicyDecision.ENTER_SM3
        assert engine.evaluate(event2) == PolicyDecision.ENTER_SM3

    def test_reset_clears_state(self):
        engine = RecoveryPolicyEngine()
        engine.evaluate(_drift_event())
        engine.reset()
        assert engine.suppression_count == 0
        # Same event should not be suppressed after reset
        assert engine.evaluate(_drift_event()) == PolicyDecision.ENTER_SM3


# ── Safe Mode State Machine ─────────────────────────────────────────


class TestSafeModeStateMachine:
    def test_initial_state_is_normal(self):
        sm = SafeModeStateMachine()
        assert sm.state == SafeModeState.NORMAL
        assert sm.is_normal is True

    def test_enter_sm3_from_normal(self):
        sm = SafeModeStateMachine()
        record = sm.enter_sm3(
            reason_code="drift_strategy_bundle",
            source_event_id="evt-001",
        )
        assert record is not None
        assert sm.state == SafeModeState.SM3_RECOVERY_ONLY
        assert sm.is_normal is False
        assert sm.entered_reason_code == "drift_strategy_bundle"
        assert sm.source_event_id == "evt-001"

    def test_enter_sm3_when_already_sm3_suppressed(self):
        sm = SafeModeStateMachine()
        sm.enter_sm3(reason_code="drift_strategy_bundle")
        result = sm.enter_sm3(reason_code="drift_feature_pack_bundle")
        assert result is None  # Suppressed
        assert sm.state == SafeModeState.SM3_RECOVERY_ONLY

    def test_enter_sm3_when_in_sm2_suppressed(self):
        sm = SafeModeStateMachine()
        # Get to SM2 via SM3 + manual
        sm.enter_sm3(reason_code="drift_strategy_bundle")
        sm.manual_transition(
            to_state=SafeModeState.SM2_EXIT_ONLY,
            reason_code="stability_confirmed",
            approved_by="operator",
        )
        # Try auto SM3 from SM2
        result = sm.enter_sm3(reason_code="drift_risk_limit_bundle")
        assert result is None
        assert sm.state == SafeModeState.SM2_EXIT_ONLY

    def test_enter_sm3_when_in_sm1_suppressed(self):
        sm = SafeModeStateMachine()
        sm.enter_sm3(reason_code="drift_strategy_bundle")
        sm.manual_transition(
            to_state=SafeModeState.SM1_OBSERVE_ONLY,
            reason_code="escalation",
            approved_by="approver",
        )
        result = sm.enter_sm3(reason_code="drift_risk_limit_bundle")
        assert result is None
        assert sm.state == SafeModeState.SM1_OBSERVE_ONLY

    def test_transition_record_fields(self):
        sm = SafeModeStateMachine()
        record = sm.enter_sm3(
            reason_code="drift_strategy_bundle",
            source_event_id="evt-001",
            detail="severity=high action=refuse_load",
        )
        assert record.from_state == SafeModeState.NORMAL
        assert record.to_state == SafeModeState.SM3_RECOVERY_ONLY
        assert record.reason_code == "drift_strategy_bundle"
        assert record.source_event_id == "evt-001"
        assert record.detail == "severity=high action=refuse_load"
        assert record.approved_by is None

    def test_cooldown_set_on_sm3_entry(self):
        sm = SafeModeStateMachine()
        sm.enter_sm3(reason_code="drift_strategy_bundle", cooldown_seconds=600)
        assert sm.cooldown_until is not None

    def test_transitions_list_grows(self):
        sm = SafeModeStateMachine()
        sm.enter_sm3(reason_code="drift_strategy_bundle")
        assert len(sm.transitions) == 1
        sm.manual_transition(
            to_state=SafeModeState.SM2_EXIT_ONLY,
            reason_code="stability_confirmed",
            approved_by="operator",
        )
        assert len(sm.transitions) == 2


# ── Manual Transition Rules ──────────────────────────────────────────


class TestManualTransitions:
    def test_sm3_to_sm2_with_approval(self):
        sm = SafeModeStateMachine()
        sm.enter_sm3(reason_code="drift_strategy_bundle")
        record = sm.manual_transition(
            to_state=SafeModeState.SM2_EXIT_ONLY,
            reason_code="stability_confirmed",
            approved_by="operator_a",
        )
        assert sm.state == SafeModeState.SM2_EXIT_ONLY
        assert record.approved_by == "operator_a"

    def test_sm2_to_sm1_with_approval(self):
        sm = SafeModeStateMachine()
        sm.enter_sm3(reason_code="drift_strategy_bundle")
        sm.manual_transition(
            to_state=SafeModeState.SM2_EXIT_ONLY,
            reason_code="stability_confirmed",
            approved_by="operator",
        )
        record = sm.manual_transition(
            to_state=SafeModeState.SM1_OBSERVE_ONLY,
            reason_code="further_escalation",
            approved_by="approver",
        )
        assert sm.state == SafeModeState.SM1_OBSERVE_ONLY

    def test_sm1_to_normal_with_approval(self):
        sm = SafeModeStateMachine()
        sm.enter_sm3(reason_code="drift_strategy_bundle")
        sm.manual_transition(
            to_state=SafeModeState.SM2_EXIT_ONLY,
            reason_code="x",
            approved_by="op",
        )
        sm.manual_transition(
            to_state=SafeModeState.SM1_OBSERVE_ONLY,
            reason_code="x",
            approved_by="op",
        )
        sm.manual_transition(
            to_state=SafeModeState.NORMAL,
            reason_code="stability_confirmed",
            approved_by="approver_a",
        )
        assert sm.state == SafeModeState.NORMAL
        assert sm.is_normal is True
        assert sm.entered_at is None  # cleared on return to NORMAL

    def test_full_step_recovery_sm3_sm2_sm1_normal(self):
        """Full recovery path: SM3 → SM2 → SM1 → NORMAL."""
        sm = SafeModeStateMachine()
        sm.enter_sm3(reason_code="drift_risk_limit_bundle")
        sm.manual_transition(
            to_state=SafeModeState.SM2_EXIT_ONLY,
            reason_code="stability_confirmed",
            approved_by="operator",
        )
        sm.manual_transition(
            to_state=SafeModeState.SM1_OBSERVE_ONLY,
            reason_code="stability_confirmed",
            approved_by="approver",
        )
        sm.manual_transition(
            to_state=SafeModeState.NORMAL,
            reason_code="manual_release",
            approved_by="approver_a",
        )
        assert sm.state == SafeModeState.NORMAL
        assert len(sm.transitions) == 4  # SM3 entry + 3 manual steps

    def test_manual_without_approval_raises(self):
        sm = SafeModeStateMachine()
        sm.enter_sm3(reason_code="drift_strategy_bundle")
        with pytest.raises(SafeModeError, match="requires approved_by"):
            sm.manual_transition(
                to_state=SafeModeState.SM2_EXIT_ONLY,
                reason_code="stability_confirmed",
                approved_by="",  # empty
            )

    def test_auto_downward_transition_not_possible(self):
        """Auto entry only targets SM3; already in SM3+ is suppressed, not errored."""
        sm = SafeModeStateMachine()
        sm.enter_sm3(reason_code="drift_strategy_bundle")
        # enter_sm3 from SM3 is suppressed (returns None), NOT a downward transition
        result = sm.enter_sm3(reason_code="another_drift")
        assert result is None
        assert sm.state == SafeModeState.SM3_RECOVERY_ONLY

    def test_invalid_manual_transition_raises(self):
        """Cannot go from SM3 directly to NORMAL (must step through)."""
        sm = SafeModeStateMachine()
        sm.enter_sm3(reason_code="drift_strategy_bundle")
        with pytest.raises(SafeModeError, match="not allowed"):
            sm.manual_transition(
                to_state=SafeModeState.NORMAL,
                reason_code="x",
                approved_by="op",
            )

    def test_cannot_skip_sm2_to_normal(self):
        """From SM2, cannot go directly to NORMAL (must go through SM1)."""
        sm = SafeModeStateMachine()
        sm.enter_sm3(reason_code="drift_strategy_bundle")
        sm.manual_transition(
            to_state=SafeModeState.SM2_EXIT_ONLY,
            reason_code="x",
            approved_by="op",
        )
        with pytest.raises(SafeModeError, match="not allowed"):
            sm.manual_transition(
                to_state=SafeModeState.NORMAL,
                reason_code="x",
                approved_by="op",
            )


# ── Drift Event Consumer ────────────────────────────────────────────


class TestDriftEventConsumer:
    def test_drift_triggers_sm3(self):
        policy = RecoveryPolicyEngine()
        sm = SafeModeStateMachine()
        consumer = DriftEventConsumer(policy, sm)

        event = _drift_event(event_id="evt-001")
        decision = consumer.consume(event)

        assert decision == PolicyDecision.ENTER_SM3
        assert sm.state == SafeModeState.SM3_RECOVERY_ONLY

    def test_same_event_id_idempotent(self):
        policy = RecoveryPolicyEngine()
        sm = SafeModeStateMachine()
        consumer = DriftEventConsumer(policy, sm)

        event = _drift_event(event_id="evt-001")
        consumer.consume(event)
        decision = consumer.consume(event)  # re-consume same

        assert decision == PolicyDecision.DUPLICATE_SUPPRESSED
        assert consumer.processed_count == 1  # only counted once

    def test_second_drift_while_sm3_suppressed(self):
        policy = RecoveryPolicyEngine()
        sm = SafeModeStateMachine()
        consumer = DriftEventConsumer(policy, sm)

        event1 = _drift_event(event_id="evt-001", bundle_type=BundleType.STRATEGY)
        event2 = _drift_event(event_id="evt-002", bundle_type=BundleType.RISK_LIMIT)

        d1 = consumer.consume(event1)
        d2 = consumer.consume(event2)

        assert d1 == PolicyDecision.ENTER_SM3
        assert d2 == PolicyDecision.DUPLICATE_SUPPRESSED  # SM already in SM3
        assert sm.state == SafeModeState.SM3_RECOVERY_ONLY

    def test_non_candidate_event_noop(self):
        policy = RecoveryPolicyEngine()
        sm = SafeModeStateMachine()
        consumer = DriftEventConsumer(policy, sm)

        event = _drift_event(sm3_candidate=False, event_id="evt-noop")
        decision = consumer.consume(event)

        assert decision == PolicyDecision.NOOP
        assert sm.state == SafeModeState.NORMAL

    def test_consume_batch(self):
        policy = RecoveryPolicyEngine()
        sm = SafeModeStateMachine()
        consumer = DriftEventConsumer(policy, sm)

        events = [
            _drift_event(event_id="evt-001", bundle_type=BundleType.STRATEGY),
            _drift_event(event_id="evt-002", bundle_type=BundleType.RISK_LIMIT),
            _drift_event(event_id="evt-003", bundle_type=BundleType.BROKER_POLICY),
        ]
        decisions = consumer.consume_batch(events)

        assert decisions[0] == PolicyDecision.ENTER_SM3
        assert decisions[1] == PolicyDecision.DUPLICATE_SUPPRESSED  # already SM3
        assert decisions[2] == PolicyDecision.DUPLICATE_SUPPRESSED  # still SM3
        assert consumer.processed_count == 3

    def test_reason_code_mapped_correctly(self):
        policy = RecoveryPolicyEngine()
        sm = SafeModeStateMachine()
        consumer = DriftEventConsumer(policy, sm)

        event = _drift_event(event_id="evt-001", bundle_type=BundleType.RISK_LIMIT)
        consumer.consume(event)

        assert sm.entered_reason_code == SafeModeReasonCode.DRIFT_RISK_LIMIT_BUNDLE.value

    def test_feature_pack_reason_code(self):
        policy = RecoveryPolicyEngine()
        sm = SafeModeStateMachine()
        consumer = DriftEventConsumer(policy, sm)

        event = _drift_event(event_id="evt-fp", bundle_type=BundleType.FEATURE_PACK)
        consumer.consume(event)

        assert sm.entered_reason_code == SafeModeReasonCode.DRIFT_FEATURE_PACK_BUNDLE.value

    def test_broker_policy_reason_code(self):
        policy = RecoveryPolicyEngine()
        sm = SafeModeStateMachine()
        consumer = DriftEventConsumer(policy, sm)

        event = _drift_event(event_id="evt-bp", bundle_type=BundleType.BROKER_POLICY)
        consumer.consume(event)

        assert sm.entered_reason_code == SafeModeReasonCode.DRIFT_BROKER_POLICY_BUNDLE.value

    def test_consumer_reset(self):
        policy = RecoveryPolicyEngine()
        sm = SafeModeStateMachine()
        consumer = DriftEventConsumer(policy, sm)

        event = _drift_event(event_id="evt-001")
        consumer.consume(event)
        consumer.reset()
        assert consumer.processed_count == 0


# ── Reason Code Completeness ────────────────────────────────────────


class TestReasonCodes:
    def test_all_bundle_types_have_reason_codes(self):
        for bt in BundleType:
            assert bt in BUNDLE_TO_REASON

    def test_reason_code_enum_values(self):
        assert SafeModeReasonCode.DRIFT_STRATEGY_BUNDLE.value == "drift_strategy_bundle"
        assert SafeModeReasonCode.DRIFT_FEATURE_PACK_BUNDLE.value == "drift_feature_pack_bundle"
        assert SafeModeReasonCode.DRIFT_BROKER_POLICY_BUNDLE.value == "drift_broker_policy_bundle"
        assert SafeModeReasonCode.DRIFT_RISK_LIMIT_BUNDLE.value == "drift_risk_limit_bundle"
        assert SafeModeReasonCode.DUPLICATE_DRIFT_SUPPRESSED.value == "duplicate_drift_suppressed"

    def test_safe_mode_state_enum_values(self):
        assert SafeModeState.NORMAL.value == "normal"
        assert SafeModeState.SM3_RECOVERY_ONLY.value == "sm3_recovery_only"
        assert SafeModeState.SM2_EXIT_ONLY.value == "sm2_exit_only"
        assert SafeModeState.SM1_OBSERVE_ONLY.value == "sm1_observe_only"


# ── Audit Trail Completeness ────────────────────────────────────────


class TestAuditTrail:
    def test_sm3_entry_creates_audit_record(self):
        sm = SafeModeStateMachine()
        sm.enter_sm3(reason_code="drift_strategy_bundle", source_event_id="evt-001")
        records = sm.transitions
        assert len(records) == 1
        r = records[0]
        assert r.from_state == SafeModeState.NORMAL
        assert r.to_state == SafeModeState.SM3_RECOVERY_ONLY
        assert r.source_event_id == "evt-001"

    def test_full_recovery_creates_4_audit_records(self):
        sm = SafeModeStateMachine()
        sm.enter_sm3(reason_code="drift_risk_limit_bundle")
        sm.manual_transition(
            to_state=SafeModeState.SM2_EXIT_ONLY,
            reason_code="stability_confirmed",
            approved_by="operator",
        )
        sm.manual_transition(
            to_state=SafeModeState.SM1_OBSERVE_ONLY,
            reason_code="stability_confirmed",
            approved_by="approver",
        )
        sm.manual_transition(
            to_state=SafeModeState.NORMAL,
            reason_code="manual_release",
            approved_by="approver_a",
        )
        records = sm.transitions
        assert len(records) == 4

        # Verify chain
        assert records[0].from_state == SafeModeState.NORMAL
        assert records[0].to_state == SafeModeState.SM3_RECOVERY_ONLY
        assert records[1].from_state == SafeModeState.SM3_RECOVERY_ONLY
        assert records[1].to_state == SafeModeState.SM2_EXIT_ONLY
        assert records[2].from_state == SafeModeState.SM2_EXIT_ONLY
        assert records[2].to_state == SafeModeState.SM1_OBSERVE_ONLY
        assert records[3].from_state == SafeModeState.SM1_OBSERVE_ONLY
        assert records[3].to_state == SafeModeState.NORMAL

    def test_suppressed_sm3_no_audit_record(self):
        sm = SafeModeStateMachine()
        sm.enter_sm3(reason_code="drift_strategy_bundle")
        sm.enter_sm3(reason_code="drift_risk_limit_bundle")  # suppressed
        assert len(sm.transitions) == 1  # only the first entry


# ── DB Model Instantiation ──────────────────────────────────────────


class TestSafeModeModels:
    def test_safe_mode_status_model(self):
        status = SafeModeStatus(
            current_state=SafeModeState.SM3_RECOVERY_ONLY,
            previous_state=SafeModeState.NORMAL,
            entered_reason_code="drift_strategy_bundle",
            source_event_id="evt-001",
        )
        assert status.current_state == SafeModeState.SM3_RECOVERY_ONLY
        assert status.previous_state == SafeModeState.NORMAL

    def test_safe_mode_transition_model(self):
        t = SafeModeTransition(
            from_state="normal",
            to_state="sm3_recovery_only",
            reason_code="drift_strategy_bundle",
            source_event_id="evt-001",
            approved_by=None,
            detail="auto entry from drift",
        )
        assert t.from_state == "normal"
        assert t.to_state == "sm3_recovery_only"
        assert t.approved_by is None
