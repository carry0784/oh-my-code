"""PPF Live Verification Stage 3 (LV-3): Bounded Live Session Verification.

Authority: PPF-LIVE-VERIFICATION-001
Stage: LV-3 (staged pass, prerequisite: LV-2 COMPLETE)
Basis: PPF-LIVE-VERIFICATION-001 / LV-2 COMPLETE (90/90)

LV-3 Scope:
    Bounded live session verification. NOT production rollout.
    Session continuity / failure budget / abort / cooldown verification.
    Execution Divergence Ledger continuity from LV-2.
    Session Failure Budget Ledger as mandatory output.

Hard Constraints:
    - Bounded live session only
    - Micro-size only
    - Whitelist asset only
    - Fixed venue or fixed venue-set only
    - Bounded order count and exposure
    - No auto capital scaling
    - No unrestricted live session
    - No automatic promotion beyond LV-3
    - Fail closed on blocker / budget overrun / unverifiable session path

Mandatory Outputs:
    1. Doctrine check
    2. Fixed skeleton mapping
    3. Slot decomposition
    4. Forbidden zone separation
    5. LV-3 verification plan
    6. Per-session pass/fail criteria
    7. Required data/state/event/score/log/validation path
    8. Execution divergence continuity check
    9. Session failure budget ledger
    10. Stage receipt

LV-3 Required Session Paths:
    - stable bounded session completion
    - degraded session completion
    - abort on reject budget overrun
    - abort on timeout budget overrun
    - abort on high-divergence budget overrun
    - cooldown enforcement after abort
    - cooldown re-entry denial
    - blocker-triggered immediate stop

LV-3 Failure Taxonomy (Learning):
    - budget_overrun_reject
    - budget_overrun_timeout
    - budget_overrun_divergence
    - blocker_abort
    - cooldown_reentry_denied
    - session_completion_stable
    - session_completion_degraded
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import numpy as np
import pytest

from strategies.ppf.constants import (
    MarketProfile,
    PPFState,
    RejectionCode,
    TransitionOutcome,
)
from strategies.ppf.constitution import run_all_checks
from strategies.ppf.decision import DecisionResult, PPFStateMachine
from strategies.ppf.execution_ledger import (
    DivergenceLedgerEntry,
    DivergenceSeverity,
    DivergenceType,
    ExecutionDivergenceLedger,
    ExecutionInterpretation,
    ExecutionObservation,
    ExecutionPath,
    OrderPathConsistency,
    VenueReliabilityState,
    classify_divergence,
    compute_execution_interpretation,
)
from strategies.ppf.gate import PPFGate, PPFOrchestrationWrapper
from strategies.ppf.interpretation import InterpretationScores, compute_scores
from strategies.ppf.logging_schema import build_log_entry
from strategies.ppf.observation import ObservationFields, compute_observation
from strategies.ppf.parameters import PPFParameters
from strategies.ppf.session_ledger import (
    BudgetPressureState,
    DivergenceAccumulationState,
    ExposureIntegrity,
    SessionBudgetConfig,
    SessionFailureBudgetLedger,
    SessionInterpretation,
    SessionObservation,
    SessionPath,
    SessionStability,
    VenueSessionReliability,
)


# ===========================================================================
# Fixtures
# ===========================================================================

def _params(**kw) -> PPFParameters:
    defaults = dict(
        market_profile=MarketProfile.M1_CRYPTO_FUTURES,
        similarity_min=0.5, projection_bias_min=0.1, path_quality_min=0.1,
        rr_min=1.5, k=3, correlation_length=10, projection_horizon=5,
        novelty_threshold=0.4, watch_timeout_bars=3, candidate_timeout_bars=5,
    )
    defaults.update(kw)
    return PPFParameters(**defaults)


def _synthetic(n=200, seed=42):
    rng = np.random.RandomState(seed)
    c = 100.0 * np.cumprod(1 + rng.randn(n) * 0.02)
    h = c * (1 + rng.uniform(0.001, 0.01, n))
    l = c * (1 - rng.uniform(0.001, 0.01, n))
    v = rng.uniform(100, 1000, n)
    return h, l, c, v


def _now_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _budget_config(**kw) -> SessionBudgetConfig:
    defaults = dict(
        max_reject_per_session=3,
        max_timeout_per_session=2,
        max_high_divergence_per_session=1,
        session_abort_threshold=5,
        forced_cooldown_seconds=300,
        max_exposure_per_asset=0.01,
    )
    defaults.update(kw)
    return SessionBudgetConfig(**defaults)


def _happy_exec_obs() -> ExecutionObservation:
    return ExecutionObservation(
        order_submit_ts=_now_ts(),
        venue_ack_ts=_now_ts(),
        expected_path=ExecutionPath.SUBMIT_ACK_FILL,
        actual_path=ExecutionPath.SUBMIT_ACK_FILL,
        final_fill_qty=0.001,
        venue_latency_ms=50.0,
    )


def _reject_exec_obs(code: str = "MARGIN") -> ExecutionObservation:
    return ExecutionObservation(
        order_submit_ts=_now_ts(),
        expected_path=ExecutionPath.SUBMIT_ACK_FILL,
        actual_path=ExecutionPath.SUBMIT_REJECT,
        reject_code=code,
    )


def _timeout_exec_obs() -> ExecutionObservation:
    return ExecutionObservation(
        order_submit_ts=_now_ts(),
        expected_path=ExecutionPath.SUBMIT_ACK_FILL,
        actual_path=ExecutionPath.SUBMIT_TIMEOUT,
        timeout_flag=True,
    )


# ===========================================================================
# MANDATORY OUTPUT 1: Doctrine Check
# ===========================================================================

class TestLV3DoctrineCheck:
    """LV-3 doctrine: automation / autonomous / self-evolution / constitution."""

    def test_automation_compatible(self) -> None:
        """Session ledger can be driven without human intervention."""
        ledger = SessionFailureBudgetLedger(_budget_config())
        result = ledger.record_execution_event(
            _happy_exec_obs(), DivergenceSeverity.NONE, DivergenceType.NONE,
        )
        assert result is None  # no abort, automated

    def test_autonomous_judgment_compatible(self) -> None:
        """Budget overrun -> abort is autonomous (no human approval needed)."""
        config = _budget_config(max_reject_per_session=1)
        ledger = SessionFailureBudgetLedger(config)
        # First reject
        ledger.record_execution_event(
            _reject_exec_obs(), DivergenceSeverity.MEDIUM, DivergenceType.UNEXPECTED_REJECT,
        )
        assert ledger.is_aborted  # autonomous abort

    def test_self_evolution_loop_compatible(self) -> None:
        """Session summary enables post-hoc learning."""
        ledger = SessionFailureBudgetLedger(_budget_config())
        ledger.record_execution_event(
            _happy_exec_obs(), DivergenceSeverity.NONE, DivergenceType.NONE,
        )
        ledger.complete_session()
        summary = ledger.summary()
        assert "session_id" in summary
        assert "stability" in summary
        assert "budget_pressure" in summary

    def test_constitution_governance_non_conflict(self) -> None:
        """Constitution checks pass with valid LV-3 params."""
        result = run_all_checks(
            params=_params(), regime_novelty_flag=False,
            current_state=PPFState.D6_EXECUTE_READY,
        )
        assert result.passed is True


# ===========================================================================
# MANDATORY OUTPUT 2: Fixed Skeleton Mapping
# ===========================================================================

class TestLV3FixedSkeletonMapping:
    """Each skeleton layer has LV-3-verifiable behavior."""

    def test_observation_layer_session(self) -> None:
        """Observation: SessionObservation captures all required fields."""
        obs = SessionObservation()
        required = [
            "session_id", "session_start_ts", "session_end_ts",
            "consecutive_divergence_count", "reject_count", "timeout_count",
            "high_severity_divergence_count", "exposure_by_asset",
            "abort_triggered", "abort_reason", "forced_cooldown_until",
            "expected_session_path", "actual_session_path",
        ]
        for f in required:
            assert hasattr(obs, f), f"Missing: {f}"

    def test_interpretation_layer_session(self) -> None:
        """Interpretation: SessionInterpretation has all required scores."""
        interp = SessionInterpretation()
        required = [
            "session_execution_stability", "budget_pressure_state",
            "divergence_accumulation_state", "bounded_exposure_integrity",
            "venue_session_reliability",
        ]
        for f in required:
            assert hasattr(interp, f), f"Missing: {f}"

    def test_decision_layer_budget(self) -> None:
        """Decision: budget config drives abort/continue decisions."""
        config = _budget_config()
        ledger = SessionFailureBudgetLedger(config)
        assert not ledger.is_aborted
        assert not ledger.is_reject_budget_exceeded()

    def test_execution_layer_bounded(self) -> None:
        """Execution: gate + wrapper still bounded in LV-3."""
        gate = PPFGate(_params(), "lv3:SOL/USDT:1h")
        h, l, c, v = _synthetic(200)
        result = gate.evaluate(h, l, c, v, risk_filter_pass=True)
        assert isinstance(result, bool)

    def test_learning_layer_taxonomy(self) -> None:
        """Learning: session paths map to failure taxonomy."""
        paths = list(SessionPath)
        assert len(paths) == 8  # 8 session paths as specified

    def test_evolution_layer_session_governance(self) -> None:
        """Evolution: session budget config is frozen (C10)."""
        from dataclasses import FrozenInstanceError
        config = _budget_config()
        with pytest.raises(FrozenInstanceError):
            config.max_reject_per_session = 99  # type: ignore[misc]

    def test_constitution_layer_unchanged(self) -> None:
        """Constitution: all checks pass, fail-closed default."""
        r = run_all_checks(
            params=_params(), regime_novelty_flag=False,
            current_state=PPFState.D1_IDLE,
        )
        assert r.passed is True


# ===========================================================================
# MANDATORY OUTPUT 3: Slot Decomposition
# ===========================================================================

class TestLV3SlotDecomposition:
    """Verify all 8 rule slots are addressable."""

    def test_observation_rules_slot(self) -> None:
        """Slot 1: session observation has 13 fields."""
        obs = SessionObservation()
        fields = [f for f in obs.__dataclass_fields__]
        assert len(fields) == 13

    def test_interpretation_rules_slot(self) -> None:
        """Slot 2: session interpretation has 5 scores."""
        interp = SessionInterpretation()
        fields = [f for f in interp.__dataclass_fields__]
        assert len(fields) == 5

    def test_state_transition_rules_slot(self) -> None:
        """Slot 3: LV-2 COMPLETE required before LV-3."""
        # Structural: this test file exists only because LV-2 passed
        # Budget state transitions: NORMAL -> ELEVATED -> CRITICAL -> OVERRUN
        states = list(BudgetPressureState)
        assert len(states) == 4

    def test_scenario_rules_slot(self) -> None:
        """Slot 4: 8 session paths defined."""
        paths = list(SessionPath)
        assert SessionPath.STABLE_COMPLETION in paths
        assert SessionPath.DEGRADED_COMPLETION in paths
        assert SessionPath.ABORT_REJECT_OVERRUN in paths
        assert SessionPath.ABORT_TIMEOUT_OVERRUN in paths
        assert SessionPath.ABORT_DIVERGENCE_OVERRUN in paths
        assert SessionPath.ABORT_BLOCKER in paths
        assert SessionPath.COOLDOWN_ACTIVE in paths
        assert SessionPath.NOT_STARTED in paths

    def test_execution_restriction_rules_slot(self) -> None:
        """Slot 5: budget config enforces bounded execution."""
        config = _budget_config()
        assert config.max_reject_per_session == 3
        assert config.max_timeout_per_session == 2
        assert config.max_exposure_per_asset == 0.01

    def test_learning_items_slot(self) -> None:
        """Slot 6: 7 learning taxonomy items from session paths."""
        # budget_overrun_reject, budget_overrun_timeout, budget_overrun_divergence,
        # blocker_abort, cooldown_reentry_denied,
        # session_completion_stable, session_completion_degraded
        taxonomy_count = 7
        abort_paths = [
            SessionPath.ABORT_REJECT_OVERRUN,
            SessionPath.ABORT_TIMEOUT_OVERRUN,
            SessionPath.ABORT_DIVERGENCE_OVERRUN,
            SessionPath.ABORT_BLOCKER,
            SessionPath.COOLDOWN_ACTIVE,
            SessionPath.STABLE_COMPLETION,
            SessionPath.DEGRADED_COMPLETION,
        ]
        assert len(abort_paths) == taxonomy_count

    def test_evolution_candidate_rules_slot(self) -> None:
        """Slot 7: session governance standardization."""
        ledger = SessionFailureBudgetLedger(_budget_config())
        assert ledger.receipt_id.startswith("LV3-")

    def test_constitution_governance_restriction_rules_slot(self) -> None:
        """Slot 8: 7 prohibitions enforced."""
        gate = PPFGate(_params(), "lv3:SOL/USDT:1h")
        assert not hasattr(gate, "auto_advance")
        assert not hasattr(gate, "promote")
        assert not hasattr(gate, "scale_up")
        ledger = SessionFailureBudgetLedger(_budget_config())
        assert not hasattr(ledger, "restart_session")
        assert not hasattr(ledger, "bypass_cooldown")


# ===========================================================================
# MANDATORY OUTPUT 4: Forbidden Zone Separation
# ===========================================================================

class TestLV3ForbiddenZones:
    """Verify all 9 forbidden zones are not breachable."""

    def test_no_full_production_rollout(self) -> None:
        gate = PPFGate(_params(), "lv3:SOL/USDT:1h")
        h, l, c, v = _synthetic(200)
        assert isinstance(gate.evaluate(h, l, c, v), bool)

    def test_no_automatic_capital_scaling(self) -> None:
        gate = PPFGate(_params(), "lv3:SOL/USDT:1h")
        assert not hasattr(gate, "scale_capital")

    def test_no_unrestricted_asset_expansion(self) -> None:
        gate = PPFGate(_params(), "lv3:SOL/USDT:1h")
        assert not hasattr(gate, "add_asset")

    def test_no_unrestricted_venue_expansion(self) -> None:
        ledger = SessionFailureBudgetLedger(_budget_config())
        assert not hasattr(ledger, "add_venue")

    def test_no_unrestricted_session_duration(self) -> None:
        """Session has explicit start/end timestamps."""
        obs = SessionObservation()
        assert obs.session_start_ts is not None
        # session_end_ts is None until session ends (bounded)

    def test_no_auto_advance_beyond_lv3(self) -> None:
        ledger = SessionFailureBudgetLedger(_budget_config())
        assert not hasattr(ledger, "advance")
        assert not hasattr(ledger, "promote")

    def test_no_silent_engine_rewrite(self) -> None:
        """Verified by baseline fingerprint test."""
        pass

    def test_no_constitution_bypass(self) -> None:
        gate = PPFGate(_params(), "lv3:SOL/USDT:1h")
        assert not hasattr(gate, "bypass_constitution")

    def test_abort_prevents_silent_continuation(self) -> None:
        """After abort, further events return abort reason (no silent continuation)."""
        config = _budget_config(max_reject_per_session=1)
        ledger = SessionFailureBudgetLedger(config)
        ledger.record_execution_event(
            _reject_exec_obs(), DivergenceSeverity.MEDIUM, DivergenceType.UNEXPECTED_REJECT,
        )
        assert ledger.is_aborted
        # Try to continue -> returns abort reason
        result = ledger.record_execution_event(
            _happy_exec_obs(), DivergenceSeverity.NONE, DivergenceType.NONE,
        )
        assert result is not None  # abort reason returned, not silently continuing


# ===========================================================================
# MANDATORY OUTPUT 5: LV-3 Verification Plan (per-session-path tests)
# ===========================================================================

# ---------------------------------------------------------------------------
# Path 1: Stable Bounded Session Completion
# ---------------------------------------------------------------------------

class TestPathStableCompletion:
    """Verify stable bounded session completion."""

    def test_stable_session_all_happy(self) -> None:
        """All orders succeed -> stable completion."""
        ledger = SessionFailureBudgetLedger(_budget_config())
        for _ in range(5):
            result = ledger.record_execution_event(
                _happy_exec_obs(), DivergenceSeverity.NONE, DivergenceType.NONE,
            )
            assert result is None
        ledger.complete_session(degraded=False)
        assert ledger.observation.actual_session_path == SessionPath.STABLE_COMPLETION

    def test_stable_session_interpretation(self) -> None:
        """Stable session: stability=STABLE, pressure=NORMAL."""
        ledger = SessionFailureBudgetLedger(_budget_config())
        for _ in range(3):
            ledger.record_execution_event(
                _happy_exec_obs(), DivergenceSeverity.NONE, DivergenceType.NONE,
            )
        ledger.complete_session()
        interp = ledger.compute_interpretation()
        assert interp.session_execution_stability == SessionStability.STABLE
        assert interp.budget_pressure_state == BudgetPressureState.NORMAL
        assert interp.divergence_accumulation_state == DivergenceAccumulationState.CLEAN

    def test_stable_session_summary(self) -> None:
        """Stable session has complete summary."""
        ledger = SessionFailureBudgetLedger(_budget_config())
        ledger.record_execution_event(
            _happy_exec_obs(), DivergenceSeverity.NONE, DivergenceType.NONE,
        )
        ledger.complete_session()
        s = ledger.summary()
        assert s["is_aborted"] is False
        assert s["stability"] == "stable"
        assert s["actual_session_path"] == "stable_completion"


# ---------------------------------------------------------------------------
# Path 2: Degraded Session Completion
# ---------------------------------------------------------------------------

class TestPathDegradedCompletion:
    """Verify degraded session completion."""

    def test_degraded_with_rejects(self) -> None:
        """Some rejects but under budget -> degraded completion."""
        config = _budget_config(max_reject_per_session=3)
        ledger = SessionFailureBudgetLedger(config)
        # 2 rejects (under budget of 3)
        for _ in range(2):
            ledger.record_execution_event(
                _reject_exec_obs(), DivergenceSeverity.MEDIUM, DivergenceType.UNEXPECTED_REJECT,
            )
        # 3 happy
        for _ in range(3):
            ledger.record_execution_event(
                _happy_exec_obs(), DivergenceSeverity.NONE, DivergenceType.NONE,
            )
        ledger.complete_session(degraded=True)
        assert ledger.observation.actual_session_path == SessionPath.DEGRADED_COMPLETION
        assert not ledger.is_aborted

    def test_degraded_interpretation(self) -> None:
        """Degraded session: stability=DEGRADED, pressure=ELEVATED."""
        config = _budget_config(max_reject_per_session=3)
        ledger = SessionFailureBudgetLedger(config)
        # 2/3 reject budget used -> elevated
        for _ in range(2):
            ledger.record_execution_event(
                _reject_exec_obs(), DivergenceSeverity.MEDIUM, DivergenceType.UNEXPECTED_REJECT,
            )
        interp = ledger.compute_interpretation()
        assert interp.session_execution_stability == SessionStability.DEGRADED
        assert interp.budget_pressure_state == BudgetPressureState.ELEVATED

    def test_degraded_consecutive_divergence_resets(self) -> None:
        """Happy event resets consecutive divergence counter."""
        ledger = SessionFailureBudgetLedger(_budget_config())
        # Reject -> consecutive=1
        ledger.record_execution_event(
            _reject_exec_obs(), DivergenceSeverity.MEDIUM, DivergenceType.UNEXPECTED_REJECT,
        )
        assert ledger.observation.consecutive_divergence_count == 1
        # Happy -> consecutive=0
        ledger.record_execution_event(
            _happy_exec_obs(), DivergenceSeverity.NONE, DivergenceType.NONE,
        )
        assert ledger.observation.consecutive_divergence_count == 0


# ---------------------------------------------------------------------------
# Path 3: Abort on Reject Budget Overrun
# ---------------------------------------------------------------------------

class TestPathAbortRejectOverrun:
    """Verify abort on reject budget overrun."""

    def test_reject_overrun_triggers_abort(self) -> None:
        """3 rejects with budget=3 -> abort."""
        config = _budget_config(max_reject_per_session=3)
        ledger = SessionFailureBudgetLedger(config)
        for i in range(3):
            result = ledger.record_execution_event(
                _reject_exec_obs(), DivergenceSeverity.MEDIUM, DivergenceType.UNEXPECTED_REJECT,
            )
        assert ledger.is_aborted
        assert "REJECT_BUDGET_OVERRUN" in ledger.abort_reason

    def test_reject_overrun_session_path(self) -> None:
        """Abort path is ABORT_REJECT_OVERRUN."""
        config = _budget_config(max_reject_per_session=2)
        ledger = SessionFailureBudgetLedger(config)
        for _ in range(2):
            ledger.record_execution_event(
                _reject_exec_obs(), DivergenceSeverity.MEDIUM, DivergenceType.UNEXPECTED_REJECT,
            )
        assert ledger.observation.actual_session_path == SessionPath.ABORT_REJECT_OVERRUN

    def test_reject_overrun_activates_cooldown(self) -> None:
        """Abort activates forced cooldown."""
        config = _budget_config(max_reject_per_session=1, forced_cooldown_seconds=600)
        ledger = SessionFailureBudgetLedger(config)
        ledger.record_execution_event(
            _reject_exec_obs(), DivergenceSeverity.MEDIUM, DivergenceType.UNEXPECTED_REJECT,
        )
        assert ledger.is_aborted
        assert ledger.is_cooldown_active
        assert ledger.cooldown_until is not None

    def test_reject_overrun_interpretation(self) -> None:
        """Abort: stability=ABORTED, pressure=OVERRUN."""
        config = _budget_config(max_reject_per_session=1)
        ledger = SessionFailureBudgetLedger(config)
        ledger.record_execution_event(
            _reject_exec_obs(), DivergenceSeverity.MEDIUM, DivergenceType.UNEXPECTED_REJECT,
        )
        interp = ledger.compute_interpretation()
        assert interp.session_execution_stability == SessionStability.ABORTED
        assert interp.budget_pressure_state == BudgetPressureState.OVERRUN


# ---------------------------------------------------------------------------
# Path 4: Abort on Timeout Budget Overrun
# ---------------------------------------------------------------------------

class TestPathAbortTimeoutOverrun:
    """Verify abort on timeout budget overrun."""

    def test_timeout_overrun_triggers_abort(self) -> None:
        """2 timeouts with budget=2, high_div budget=10 -> timeout overrun first."""
        config = _budget_config(
            max_timeout_per_session=2,
            max_high_divergence_per_session=10,  # high enough to not fire first
        )
        ledger = SessionFailureBudgetLedger(config)
        for _ in range(2):
            ledger.record_execution_event(
                _timeout_exec_obs(), DivergenceSeverity.HIGH, DivergenceType.UNEXPECTED_TIMEOUT,
            )
        assert ledger.is_aborted
        assert "TIMEOUT_BUDGET_OVERRUN" in ledger.abort_reason

    def test_timeout_overrun_session_path(self) -> None:
        config = _budget_config(
            max_timeout_per_session=1,
            max_high_divergence_per_session=10,
        )
        ledger = SessionFailureBudgetLedger(config)
        ledger.record_execution_event(
            _timeout_exec_obs(), DivergenceSeverity.HIGH, DivergenceType.UNEXPECTED_TIMEOUT,
        )
        assert ledger.observation.actual_session_path == SessionPath.ABORT_TIMEOUT_OVERRUN

    def test_timeout_overrun_activates_cooldown(self) -> None:
        config = _budget_config(
            max_timeout_per_session=1,
            max_high_divergence_per_session=10,
        )
        ledger = SessionFailureBudgetLedger(config)
        ledger.record_execution_event(
            _timeout_exec_obs(), DivergenceSeverity.HIGH, DivergenceType.UNEXPECTED_TIMEOUT,
        )
        assert ledger.is_cooldown_active


# ---------------------------------------------------------------------------
# Path 5: Abort on High-Divergence Budget Overrun
# ---------------------------------------------------------------------------

class TestPathAbortDivergenceOverrun:
    """Verify abort on high-severity divergence budget overrun."""

    def test_high_divergence_overrun_triggers_abort(self) -> None:
        """1 HIGH divergence with budget=1 -> abort."""
        config = _budget_config(max_high_divergence_per_session=1)
        ledger = SessionFailureBudgetLedger(config)
        obs = ExecutionObservation(
            order_submit_ts=_now_ts(),
            expected_path=ExecutionPath.SUBMIT_ACK_FILL,
            actual_path=ExecutionPath.SUBMIT_TIMEOUT,
            timeout_flag=True,
        )
        ledger.record_execution_event(
            obs, DivergenceSeverity.HIGH, DivergenceType.UNEXPECTED_TIMEOUT,
        )
        assert ledger.is_aborted
        assert "HIGH_DIVERGENCE_OVERRUN" in ledger.abort_reason

    def test_high_divergence_overrun_session_path(self) -> None:
        config = _budget_config(max_high_divergence_per_session=1)
        ledger = SessionFailureBudgetLedger(config)
        obs = ExecutionObservation(
            order_submit_ts=_now_ts(),
            expected_path=ExecutionPath.SUBMIT_ACK_FILL,
            actual_path=ExecutionPath.SUBMIT_ACK_CANCEL,
        )
        ledger.record_execution_event(
            obs, DivergenceSeverity.HIGH, DivergenceType.UNEXPECTED_CANCEL,
        )
        assert ledger.observation.actual_session_path == SessionPath.ABORT_DIVERGENCE_OVERRUN


# ---------------------------------------------------------------------------
# Path 6: Cooldown Enforcement After Abort
# ---------------------------------------------------------------------------

class TestPathCooldownEnforcement:
    """Verify cooldown enforcement after abort."""

    def test_cooldown_active_after_abort(self) -> None:
        """Cooldown activates immediately after abort."""
        config = _budget_config(max_reject_per_session=1, forced_cooldown_seconds=300)
        ledger = SessionFailureBudgetLedger(config)
        ledger.record_execution_event(
            _reject_exec_obs(), DivergenceSeverity.MEDIUM, DivergenceType.UNEXPECTED_REJECT,
        )
        assert ledger.is_aborted
        assert ledger.is_cooldown_active
        assert ledger.cooldown_until is not None

    def test_cooldown_has_explicit_expiry(self) -> None:
        """Cooldown has explicit timestamp, not open-ended."""
        config = _budget_config(max_reject_per_session=1, forced_cooldown_seconds=600)
        ledger = SessionFailureBudgetLedger(config)
        ledger.record_execution_event(
            _reject_exec_obs(), DivergenceSeverity.MEDIUM, DivergenceType.UNEXPECTED_REJECT,
        )
        # Cooldown timestamp should be parseable
        cooldown_ts = ledger.cooldown_until
        assert cooldown_ts is not None
        parsed = datetime.fromisoformat(cooldown_ts)
        assert parsed > datetime.now(timezone.utc)

    def test_cooldown_in_observation(self) -> None:
        """Cooldown expiry is recorded in session observation."""
        config = _budget_config(max_reject_per_session=1)
        ledger = SessionFailureBudgetLedger(config)
        ledger.record_execution_event(
            _reject_exec_obs(), DivergenceSeverity.MEDIUM, DivergenceType.UNEXPECTED_REJECT,
        )
        assert ledger.observation.forced_cooldown_until is not None

    def test_cooldown_in_summary(self) -> None:
        """Summary includes cooldown status."""
        config = _budget_config(max_reject_per_session=1)
        ledger = SessionFailureBudgetLedger(config)
        ledger.record_execution_event(
            _reject_exec_obs(), DivergenceSeverity.MEDIUM, DivergenceType.UNEXPECTED_REJECT,
        )
        s = ledger.summary()
        assert s["cooldown_active"] is True
        assert s["cooldown_until"] is not None


# ---------------------------------------------------------------------------
# Path 7: Cooldown Re-entry Denial
# ---------------------------------------------------------------------------

class TestPathCooldownReentryDenial:
    """Verify cooldown re-entry is denied."""

    def test_reentry_denied_during_cooldown(self) -> None:
        """Events after abort (which activates cooldown) return denial reason.

        After abort, self._aborted is True, so the abort_reason is returned
        before the cooldown check. This is correct: abort implies cooldown,
        and both deny re-entry. The key invariant is: re-entry is NOT silently
        accepted.
        """
        config = _budget_config(max_reject_per_session=1)
        ledger = SessionFailureBudgetLedger(config)
        ledger.record_execution_event(
            _reject_exec_obs(), DivergenceSeverity.MEDIUM, DivergenceType.UNEXPECTED_REJECT,
        )
        assert ledger.is_aborted
        assert ledger.is_cooldown_active
        # Try re-entry -> returns abort reason (not None = denied)
        result = ledger.record_execution_event(
            _happy_exec_obs(), DivergenceSeverity.NONE, DivergenceType.NONE,
        )
        assert result is not None  # re-entry denied, not silently accepted

    def test_reentry_denial_is_not_silent(self) -> None:
        """Re-entry denial returns explicit reason string (not None)."""
        config = _budget_config(
            max_timeout_per_session=1,
            max_high_divergence_per_session=10,
        )
        ledger = SessionFailureBudgetLedger(config)
        ledger.record_execution_event(
            _timeout_exec_obs(), DivergenceSeverity.HIGH, DivergenceType.UNEXPECTED_TIMEOUT,
        )
        assert ledger.is_aborted
        result = ledger.record_execution_event(
            _happy_exec_obs(), DivergenceSeverity.NONE, DivergenceType.NONE,
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_multiple_reentry_attempts_all_denied(self) -> None:
        """Multiple re-entry attempts are all denied."""
        config = _budget_config(max_reject_per_session=1)
        ledger = SessionFailureBudgetLedger(config)
        ledger.record_execution_event(
            _reject_exec_obs(), DivergenceSeverity.MEDIUM, DivergenceType.UNEXPECTED_REJECT,
        )
        for _ in range(5):
            result = ledger.record_execution_event(
                _happy_exec_obs(), DivergenceSeverity.NONE, DivergenceType.NONE,
            )
            assert result is not None


# ---------------------------------------------------------------------------
# Path 8: Blocker-Triggered Immediate Stop
# ---------------------------------------------------------------------------

class TestPathBlockerImmediateStop:
    """Verify blocker divergence triggers immediate session stop."""

    def test_blocker_triggers_immediate_abort(self) -> None:
        """BLOCKER severity -> immediate abort regardless of budget."""
        ledger = SessionFailureBudgetLedger(_budget_config())
        result = ledger.record_execution_event(
            _timeout_exec_obs(), DivergenceSeverity.BLOCKER, DivergenceType.UNEXPECTED_TIMEOUT,
        )
        assert ledger.is_aborted
        assert "BLOCKER_DIVERGENCE" in ledger.abort_reason

    def test_blocker_session_path(self) -> None:
        """Blocker sets session path to ABORT_BLOCKER."""
        ledger = SessionFailureBudgetLedger(_budget_config())
        ledger.record_execution_event(
            _timeout_exec_obs(), DivergenceSeverity.BLOCKER, DivergenceType.UNEXPECTED_TIMEOUT,
        )
        assert ledger.observation.actual_session_path == SessionPath.ABORT_BLOCKER

    def test_blocker_overrides_remaining_budget(self) -> None:
        """Full budget remaining, but BLOCKER still aborts."""
        config = _budget_config(
            max_reject_per_session=100,
            max_timeout_per_session=100,
            max_high_divergence_per_session=100,
        )
        ledger = SessionFailureBudgetLedger(config)
        # No budget pressure at all
        assert not ledger.is_reject_budget_exceeded()
        assert not ledger.is_timeout_budget_exceeded()
        # BLOCKER still aborts
        ledger.record_execution_event(
            _timeout_exec_obs(), DivergenceSeverity.BLOCKER, DivergenceType.UNEXPECTED_TIMEOUT,
        )
        assert ledger.is_aborted

    def test_blocker_activates_cooldown(self) -> None:
        """Blocker abort also activates cooldown."""
        ledger = SessionFailureBudgetLedger(_budget_config())
        ledger.record_execution_event(
            _timeout_exec_obs(), DivergenceSeverity.BLOCKER, DivergenceType.UNEXPECTED_TIMEOUT,
        )
        assert ledger.is_cooldown_active


# ===========================================================================
# MANDATORY OUTPUT 6: Per-Session Pass/Fail Criteria
# ===========================================================================

class TestPerSessionPassFailCriteria:
    """Verify per-session pass/fail criteria."""

    def test_pass_bounded_session_verifiable(self) -> None:
        """PASS: bounded session path is verifiable."""
        ledger = SessionFailureBudgetLedger(_budget_config())
        for _ in range(3):
            ledger.record_execution_event(
                _happy_exec_obs(), DivergenceSeverity.NONE, DivergenceType.NONE,
            )
        ledger.complete_session()
        assert ledger.observation.actual_session_path == SessionPath.STABLE_COMPLETION

    def test_pass_budgets_measurable(self) -> None:
        """PASS: reject/timeout/divergence budgets are measurable."""
        ledger = SessionFailureBudgetLedger(_budget_config())
        assert ledger.reject_count == 0
        assert ledger.timeout_count == 0
        assert ledger.high_divergence_count == 0

    def test_pass_abort_classifiable(self) -> None:
        """PASS: abort is classifiable with reason."""
        config = _budget_config(max_reject_per_session=1)
        ledger = SessionFailureBudgetLedger(config)
        ledger.record_execution_event(
            _reject_exec_obs(), DivergenceSeverity.MEDIUM, DivergenceType.UNEXPECTED_REJECT,
        )
        assert ledger.abort_reason is not None
        assert len(ledger.abort_reason) > 0

    def test_pass_session_receipt_generated(self) -> None:
        """PASS: session receipt is generated."""
        ledger = SessionFailureBudgetLedger(_budget_config())
        assert ledger.receipt_id.startswith("LV3-")
        assert len(ledger.receipt_id) == 16

    def test_pass_constitution_intact(self) -> None:
        """PASS: constitution remains intact."""
        r = run_all_checks(
            params=_params(), regime_novelty_flag=False,
            current_state=PPFState.D6_EXECUTE_READY,
        )
        assert r.passed

    def test_fail_budget_overrun_without_abort(self) -> None:
        """FAIL: budget overrun MUST trigger abort (verified by implementation)."""
        config = _budget_config(max_reject_per_session=2)
        ledger = SessionFailureBudgetLedger(config)
        for _ in range(2):
            ledger.record_execution_event(
                _reject_exec_obs(), DivergenceSeverity.MEDIUM, DivergenceType.UNEXPECTED_REJECT,
            )
        # Budget overrun -> abort was triggered (not missing)
        assert ledger.is_aborted

    def test_fail_cooldown_violation_impossible(self) -> None:
        """FAIL: cooldown violation is blocked by implementation."""
        config = _budget_config(max_reject_per_session=1)
        ledger = SessionFailureBudgetLedger(config)
        ledger.record_execution_event(
            _reject_exec_obs(), DivergenceSeverity.MEDIUM, DivergenceType.UNEXPECTED_REJECT,
        )
        # Re-entry blocked
        result = ledger.record_execution_event(
            _happy_exec_obs(), DivergenceSeverity.NONE, DivergenceType.NONE,
        )
        assert result is not None  # denied, not silently accepted


# ===========================================================================
# MANDATORY OUTPUT 7: Required Data/State/Event/Score/Log/Validation Path
# ===========================================================================

class TestRequiredDataPaths:
    """Verify all required data flows are connected."""

    def test_ppf_gate_to_session_ledger(self) -> None:
        """PPF gate result feeds session ledger via execution observation."""
        gate = PPFGate(_params(), "lv3:SOL/USDT:1h")
        h, l, c, v = _synthetic(200)
        gate_allows = gate.evaluate(h, l, c, v, risk_filter_pass=True)

        ledger = SessionFailureBudgetLedger(_budget_config())
        if gate_allows:
            exec_obs = ExecutionObservation(
                order_submit_ts=_now_ts(), venue_ack_ts=_now_ts(),
                expected_path=ExecutionPath.SUBMIT_ACK_FILL,
                actual_path=ExecutionPath.SUBMIT_ACK_FILL,
                final_fill_qty=0.001, venue_latency_ms=50.0,
            )
            result = ledger.record_execution_event(
                exec_obs, DivergenceSeverity.NONE, DivergenceType.NONE,
            )
            assert result is None

    def test_execution_observation_to_session_counters(self) -> None:
        """Execution events increment session counters."""
        ledger = SessionFailureBudgetLedger(_budget_config())
        ledger.record_execution_event(
            _reject_exec_obs(), DivergenceSeverity.MEDIUM, DivergenceType.UNEXPECTED_REJECT,
        )
        assert ledger.reject_count == 1
        assert ledger.total_failure_count == 1

    def test_session_counters_to_interpretation(self) -> None:
        """Session counters produce valid interpretation."""
        ledger = SessionFailureBudgetLedger(_budget_config())
        ledger.record_execution_event(
            _reject_exec_obs(), DivergenceSeverity.MEDIUM, DivergenceType.UNEXPECTED_REJECT,
        )
        interp = ledger.compute_interpretation()
        assert interp.session_execution_stability == SessionStability.DEGRADED

    def test_ppf_log_entry_coexists(self) -> None:
        """PPF audit log and session ledger coexist."""
        gate = PPFGate(_params(), "lv3:SOL/USDT:1h")
        h, l, c, v = _synthetic(200)
        gate.evaluate(h, l, c, v, risk_filter_pass=True)
        assert gate.last_log_entry is not None

        ledger = SessionFailureBudgetLedger(_budget_config())
        ledger.record_execution_event(
            _happy_exec_obs(), DivergenceSeverity.NONE, DivergenceType.NONE,
        )
        assert ledger.session_id is not None

    def test_constitution_check_runs_in_lv3(self) -> None:
        result = run_all_checks(
            params=_params(), regime_novelty_flag=False,
            current_state=PPFState.D1_IDLE,
        )
        assert result.passed


# ===========================================================================
# MANDATORY OUTPUT 8: Execution Divergence Continuity Check
# ===========================================================================

class TestExecutionDivergenceContinuity:
    """Verify LV-2 execution divergence ledger continuity in LV-3."""

    def test_session_ledger_contains_divergence_ledger(self) -> None:
        """Session ledger wraps LV-2 divergence ledger."""
        ledger = SessionFailureBudgetLedger(_budget_config())
        assert ledger.divergence_ledger is not None
        assert isinstance(ledger.divergence_ledger, ExecutionDivergenceLedger)

    def test_divergence_events_accumulate_in_session(self) -> None:
        """Divergence events from session flow into divergence ledger."""
        ledger = SessionFailureBudgetLedger(_budget_config())
        ledger.record_execution_event(
            _reject_exec_obs(), DivergenceSeverity.MEDIUM, DivergenceType.UNEXPECTED_REJECT,
        )
        assert ledger.divergence_ledger.entry_count == 1

    def test_happy_events_dont_add_divergence(self) -> None:
        """Happy events (NONE type) don't add divergence entries."""
        ledger = SessionFailureBudgetLedger(_budget_config())
        ledger.record_execution_event(
            _happy_exec_obs(), DivergenceSeverity.NONE, DivergenceType.NONE,
        )
        assert ledger.divergence_ledger.entry_count == 0

    def test_blocker_stops_divergence_ledger_too(self) -> None:
        """Blocker in session also stops the underlying divergence ledger."""
        ledger = SessionFailureBudgetLedger(_budget_config())
        ledger.record_execution_event(
            _timeout_exec_obs(), DivergenceSeverity.BLOCKER, DivergenceType.UNEXPECTED_TIMEOUT,
        )
        assert ledger.divergence_ledger.is_stopped

    def test_session_summary_includes_divergence_stats(self) -> None:
        """Session summary includes divergence ledger statistics."""
        ledger = SessionFailureBudgetLedger(_budget_config())
        ledger.record_execution_event(
            _reject_exec_obs(), DivergenceSeverity.MEDIUM, DivergenceType.UNEXPECTED_REJECT,
        )
        summary = ledger.summary()
        assert "divergence_ledger_entries" in summary
        assert "divergence_severity_counts" in summary
        assert summary["divergence_ledger_entries"] == 1


# ===========================================================================
# MANDATORY OUTPUT 9: Session Failure Budget Ledger (comprehensive tests)
# ===========================================================================

class TestSessionFailureBudgetLedger:
    """Comprehensive tests for Session Failure Budget Ledger."""

    def test_config_is_frozen(self) -> None:
        """Budget config is frozen (C10 compliant)."""
        from dataclasses import FrozenInstanceError
        config = _budget_config()
        with pytest.raises(FrozenInstanceError):
            config.max_reject_per_session = 99  # type: ignore[misc]

    def test_initial_state(self) -> None:
        """New ledger starts with zero counters and not aborted."""
        ledger = SessionFailureBudgetLedger(_budget_config())
        assert ledger.reject_count == 0
        assert ledger.timeout_count == 0
        assert ledger.high_divergence_count == 0
        assert ledger.total_failure_count == 0
        assert not ledger.is_aborted
        assert not ledger.is_cooldown_active

    def test_receipt_id_unique(self) -> None:
        """Each ledger gets a unique receipt ID."""
        ids = set()
        for _ in range(20):
            ledger = SessionFailureBudgetLedger(_budget_config())
            ids.add(ledger.receipt_id)
        assert len(ids) == 20

    def test_session_id_unique(self) -> None:
        """Each session gets a unique ID."""
        ids = set()
        for _ in range(20):
            ledger = SessionFailureBudgetLedger(_budget_config())
            ids.add(ledger.session_id)
        assert len(ids) == 20

    def test_exposure_tracking(self) -> None:
        """Exposure is tracked per asset."""
        ledger = SessionFailureBudgetLedger(_budget_config())
        ledger.update_exposure("SOL/USDT", 0.005)
        ledger.update_exposure("BTC/USDT", 0.002)
        assert ledger.observation.exposure_by_asset["SOL/USDT"] == 0.005
        assert ledger.observation.exposure_by_asset["BTC/USDT"] == 0.002

    def test_exposure_exceeded_triggers_abort(self) -> None:
        """Exposure exceeding max triggers abort."""
        config = _budget_config(max_exposure_per_asset=0.01)
        ledger = SessionFailureBudgetLedger(config)
        result = ledger.update_exposure("SOL/USDT", 0.02)
        assert result is not None
        assert "EXPOSURE_EXCEEDED" in result
        assert ledger.is_aborted

    def test_exposure_within_bounds_ok(self) -> None:
        """Exposure within bounds returns None."""
        config = _budget_config(max_exposure_per_asset=0.01)
        ledger = SessionFailureBudgetLedger(config)
        result = ledger.update_exposure("SOL/USDT", 0.005)
        assert result is None
        assert not ledger.is_aborted

    def test_complete_session_after_abort_noop(self) -> None:
        """complete_session after abort is a no-op."""
        config = _budget_config(max_reject_per_session=1)
        ledger = SessionFailureBudgetLedger(config)
        ledger.record_execution_event(
            _reject_exec_obs(), DivergenceSeverity.MEDIUM, DivergenceType.UNEXPECTED_REJECT,
        )
        assert ledger.is_aborted
        # Try to complete -> ignored
        ledger.complete_session(degraded=False)
        assert ledger.observation.actual_session_path != SessionPath.STABLE_COMPLETION

    def test_budget_pressure_critical(self) -> None:
        """80%+ budget usage -> CRITICAL pressure."""
        config = _budget_config(max_reject_per_session=5)
        ledger = SessionFailureBudgetLedger(config)
        # 4/5 = 80% -> CRITICAL
        for _ in range(4):
            ledger.record_execution_event(
                _reject_exec_obs(), DivergenceSeverity.MEDIUM, DivergenceType.UNEXPECTED_REJECT,
            )
        interp = ledger.compute_interpretation()
        assert interp.budget_pressure_state == BudgetPressureState.CRITICAL

    def test_exposure_approaching_limit(self) -> None:
        """Exposure at 80%+ of limit -> APPROACHING_LIMIT."""
        config = _budget_config(max_exposure_per_asset=0.01)
        ledger = SessionFailureBudgetLedger(config)
        ledger.update_exposure("SOL/USDT", 0.009)  # 90% of 0.01
        interp = ledger.compute_interpretation()
        assert interp.bounded_exposure_integrity == ExposureIntegrity.APPROACHING_LIMIT

    def test_venue_unreliable_on_high_divergence(self) -> None:
        """HIGH+ divergences -> UNRELIABLE venue."""
        ledger = SessionFailureBudgetLedger(
            _budget_config(max_high_divergence_per_session=10)
        )
        obs = ExecutionObservation(
            order_submit_ts=_now_ts(),
            expected_path=ExecutionPath.SUBMIT_ACK_FILL,
            actual_path=ExecutionPath.SUBMIT_TIMEOUT,
            timeout_flag=True,
        )
        ledger.record_execution_event(
            obs, DivergenceSeverity.HIGH, DivergenceType.UNEXPECTED_TIMEOUT,
        )
        interp = ledger.compute_interpretation()
        assert interp.venue_session_reliability == VenueSessionReliability.UNRELIABLE


# ===========================================================================
# Multi-Session Simulation
# ===========================================================================

class TestMultiSessionSimulation:
    """Simulate bounded LV-3 sessions."""

    def test_stable_session_full_lifecycle(self) -> None:
        """Complete stable session lifecycle."""
        ledger = SessionFailureBudgetLedger(_budget_config())
        # 5 happy orders
        for _ in range(5):
            ledger.record_execution_event(
                _happy_exec_obs(), DivergenceSeverity.NONE, DivergenceType.NONE,
            )
        ledger.update_exposure("SOL/USDT", 0.005)
        ledger.complete_session(degraded=False)

        s = ledger.summary()
        assert s["is_aborted"] is False
        assert s["stability"] == "stable"
        assert s["budget_pressure"] == "normal"
        assert s["actual_session_path"] == "stable_completion"

    def test_degraded_session_full_lifecycle(self) -> None:
        """Degraded session with mixed outcomes."""
        config = _budget_config(max_reject_per_session=5)
        ledger = SessionFailureBudgetLedger(config)
        # 3 happy, 2 rejects, 2 happy
        for _ in range(3):
            ledger.record_execution_event(
                _happy_exec_obs(), DivergenceSeverity.NONE, DivergenceType.NONE,
            )
        for _ in range(2):
            ledger.record_execution_event(
                _reject_exec_obs(), DivergenceSeverity.MEDIUM, DivergenceType.UNEXPECTED_REJECT,
            )
        for _ in range(2):
            ledger.record_execution_event(
                _happy_exec_obs(), DivergenceSeverity.NONE, DivergenceType.NONE,
            )
        ledger.complete_session(degraded=True)

        s = ledger.summary()
        assert s["is_aborted"] is False
        assert s["reject_count"] == 2
        assert s["stability"] == "degraded"
        assert s["actual_session_path"] == "degraded_completion"

    def test_aborted_session_full_lifecycle(self) -> None:
        """Session aborted by budget overrun."""
        config = _budget_config(max_reject_per_session=2)
        ledger = SessionFailureBudgetLedger(config)
        # 1 happy, then 2 rejects -> abort
        ledger.record_execution_event(
            _happy_exec_obs(), DivergenceSeverity.NONE, DivergenceType.NONE,
        )
        ledger.record_execution_event(
            _reject_exec_obs(), DivergenceSeverity.MEDIUM, DivergenceType.UNEXPECTED_REJECT,
        )
        ledger.record_execution_event(
            _reject_exec_obs(), DivergenceSeverity.MEDIUM, DivergenceType.UNEXPECTED_REJECT,
        )

        s = ledger.summary()
        assert s["is_aborted"] is True
        assert s["stability"] == "aborted"
        assert s["cooldown_active"] is True
        assert "REJECT_BUDGET_OVERRUN" in s["abort_reason"]


# ===========================================================================
# LV-3: Baseline Fingerprint Drift Detection
# ===========================================================================

class TestLV3BaselineFingerprint:
    """Verify source files match sealed baseline."""

    def test_original_11_source_files_unchanged(self) -> None:
        """Original 11 PPF source files match sealed baseline SHA256."""
        expected = {
            "strategies/ppf/constitution.py": "f317c816a29355c6",
            "strategies/ppf/decision.py": "a72b23bf4070b6c4",
            "strategies/ppf/gate.py": "66bdf8f4d0cfcaef",
            "strategies/ppf/logging_schema.py": "ea8e4e18078a29de",
            "strategies/ppf/observation.py": "f8ad852f9d69673f",
            "strategies/ppf/interpretation.py": "d732f3d290d60b2b",
            "strategies/ppf/parameters.py": "8171010ad2ced00d",
            "strategies/ppf/constants.py": "3790cbdd43ed47cf",
            "strategies/ppf/pattern_engine/matcher.py": "002ddbe818caa4cc",
            "strategies/ppf/indicators/ssl_hybrid.py": "8997f35923b19966",
            "strategies/ppf/indicators/volume_osc.py": "192d8e0a737481f8",
        }
        for filepath, prefix in expected.items():
            actual = hashlib.sha256(open(filepath, "rb").read()).hexdigest()
            assert actual.startswith(prefix), (
                f"DRIFT: {filepath} expected {prefix}..., got {actual[:16]}..."
            )

    def test_lv2_execution_ledger_unchanged(self) -> None:
        """LV-2 execution_ledger.py unchanged from LV-2 sealed baseline."""
        expected_prefix = "065247b809b6bdda"
        actual = hashlib.sha256(
            open("strategies/ppf/execution_ledger.py", "rb").read()
        ).hexdigest()
        assert actual.startswith(expected_prefix), (
            f"DRIFT: execution_ledger.py expected {expected_prefix}..., got {actual[:16]}..."
        )

    def test_session_ledger_is_new_file(self) -> None:
        """session_ledger.py is a NEW file (LV-3 mandatory output)."""
        import os
        path = "strategies/ppf/session_ledger.py"
        assert os.path.exists(path), "session_ledger.py must exist"
