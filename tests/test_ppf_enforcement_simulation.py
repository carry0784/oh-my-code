"""PPF Enforcement Mode Transition Test Suite.

Authority: PPF-ENFORCEMENT-SIMULATION-001
Basis: PPFGateHandler shadow/paper manifest behavior
       enforce_deny logic: effective = raw OR NOT enforce_deny

Purpose:
    Simulate the promotion transition from SHADOW_MANIFEST to PAPER_MANIFEST
    and verify that the novelty brake changes behavior from "allow everything"
    to "actually deny when novelty brake fires".

Critical invariant under test (ppf_gate_handler.py ~line 491):
    effective_allowed = raw_gate_allows or not self._manifest.enforce_deny

    SHADOW (enforce_deny=False): effective = raw OR True  = always True
    PAPER  (enforce_deny=True):  effective = raw OR False = raw (actual gate decision)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from unittest.mock import MagicMock, PropertyMock

import numpy as np
import pytest

from strategies.ppf.constants import MarketProfile, PPFState, RejectionCode
from strategies.ppf.logging_schema import PPFLogEntry
from strategies.ppf.parameters import PPFParameters
from strategies.ppf.ppf_gate_handler import (
    GUARDED_MANIFEST,
    LIVE_MANIFEST,
    PAPER_MANIFEST,
    SHADOW_MANIFEST,
    DenyReasonCode,
    ModeCapabilityManifest,
    PPFGateHandler,
    PPFGateResult,
)
from strategies.ppf.session_ledger import SessionBudgetConfig, SessionFailureBudgetLedger


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_params() -> PPFParameters:
    """Minimal valid PPFParameters for testing."""
    return PPFParameters(
        market_profile=MarketProfile.M1_CRYPTO_FUTURES,
        correlation_length=20,
        projection_horizon=5,
        k=3,
        path_quality_min=0.1,
        rr_min=1.5,
        similarity_min=0.5,
        novelty_threshold=0.4,
        projection_bias_min=0.1,
        watch_timeout_bars=2,
        candidate_timeout_bars=3,
    )


def _make_session_ledger() -> SessionFailureBudgetLedger:
    """Fresh session ledger (non-aborted, no cooldown)."""
    return SessionFailureBudgetLedger(config=SessionBudgetConfig())


def _make_ohlcv_provider() -> object:
    """Callable that returns minimal valid OHLCV arrays."""
    highs  = np.linspace(101, 110, 50)
    lows   = np.linspace(99,  108, 50)
    closes = np.linspace(100, 109, 50)
    volumes = np.ones(50) * 500.0

    def provider():
        return (highs, lows, closes, volumes)

    return provider


def _make_novelty_log_entry() -> PPFLogEntry:
    """PPFLogEntry representing a NOVELTY_BRAKE deny (regime_novelty_flag=True)."""
    return PPFLogEntry(
        timestamp=datetime.now(timezone.utc).isoformat(),
        asset_timeframe_tag="binance:SOL/USDT:1h",
        ppf_state=PPFState.D1_IDLE.value,
        allow_entry=False,
        filter_contribution_map={
            "I1": -0.5, "I2": 0.1, "I3": 0.1,
            "I4": 0.0,  "I5": 0.0,
            "O4_raw": 0.05, "O5_raw": 0.04,
        },
        rejection_reason_code=RejectionCode.NOVELTY_BRAKE.value,
        reached_state=PPFState.D1_IDLE.value,
        regime_novelty_flag=True,
    )


def _make_pass_log_entry() -> PPFLogEntry:
    """PPFLogEntry representing a D6_EXECUTE_READY allow (regime_novelty_flag=False)."""
    return PPFLogEntry(
        timestamp=datetime.now(timezone.utc).isoformat(),
        asset_timeframe_tag="binance:SOL/USDT:1h",
        ppf_state=PPFState.D6_EXECUTE_READY.value,
        allow_entry=True,
        filter_contribution_map={
            "I1": 0.8, "I2": 0.7, "I3": 0.6,
            "I4": 0.5, "I5": 0.4,
            "O4_raw": 0.02, "O5_raw": 0.06,
        },
        rejection_reason_code=None,
        reached_state=PPFState.D6_EXECUTE_READY.value,
        regime_novelty_flag=False,
    )


def _make_gate_mock(evaluate_return: bool, log_entry: PPFLogEntry) -> MagicMock:
    """Build a MagicMock for PPFGate that returns a fixed evaluate result.

    Mocks:
    - is_active property: always True (gate not deactivated)
    - evaluate():         returns evaluate_return
    - last_log_entry:     returns log_entry
    """
    gate = MagicMock()

    # is_active must be a property; configure on the mock type
    type(gate).is_active = PropertyMock(return_value=True)

    gate.evaluate.return_value = evaluate_return
    type(gate).last_log_entry = PropertyMock(return_value=log_entry)

    return gate


def _build_handler(
    manifest: ModeCapabilityManifest,
    evaluate_return: bool,
    log_entry: PPFLogEntry,
) -> PPFGateHandler:
    """Construct a PPFGateHandler with a mocked gate and the given manifest."""
    gate = _make_gate_mock(evaluate_return, log_entry)
    session_ledger = _make_session_ledger()
    ohlcv_provider = _make_ohlcv_provider()
    return PPFGateHandler(
        ppf_gate=gate,
        session_ledger=session_ledger,
        ohlcv_provider=ohlcv_provider,
        manifest=manifest,
    )


# ---------------------------------------------------------------------------
# Test 1: shadow manifest allows even when novelty brake fires
# ---------------------------------------------------------------------------

class TestShadowManifestAllowsOnNoveltyBrake:
    """SHADOW_MANIFEST: enforce_deny=False means deny is overridden to allow."""

    def test_shadow_manifest_allows_on_novelty_brake(self) -> None:
        """Gate denies (novelty brake) but shadow override makes result allowed=True."""
        log_entry = _make_novelty_log_entry()
        handler = _build_handler(
            manifest=SHADOW_MANIFEST,
            evaluate_return=False,   # gate denies
            log_entry=log_entry,
        )

        result = handler.check_gate(
            symbol="SOL/USDT",
            exchange="binance",
            risk_filter_pass=True,
        )

        # Shadow must override: allowed=True regardless of raw deny
        assert result.allowed is True, (
            "SHADOW_MANIFEST must override gate deny to allowed=True"
        )

        # Raw gate decision must reflect the actual gate deny
        assert result.raw_gate_decision is False, (
            "raw_gate_decision must capture the true gate evaluation (False)"
        )

        # Deny reason code must map to NOVELTY_BRAKE because regime_novelty_flag=True
        assert result.deny_reason_code == DenyReasonCode.NOVELTY_BRAKE, (
            f"deny_reason_code expected NOVELTY_BRAKE, got {result.deny_reason_code}"
        )

        # Mode manifest must be SHADOW
        assert result.mode_manifest == SHADOW_MANIFEST

    def test_shadow_manifest_deny_reason_code_version_present(self) -> None:
        """deny_reason_code_version must be populated in the result."""
        log_entry = _make_novelty_log_entry()
        handler = _build_handler(SHADOW_MANIFEST, False, log_entry)

        result = handler.check_gate()

        assert result.deny_reason_code_version is not None
        assert len(result.deny_reason_code_version) > 0


# ---------------------------------------------------------------------------
# Test 2: paper manifest denies on novelty brake
# ---------------------------------------------------------------------------

class TestPaperManifestDeniesOnNoveltyBrake:
    """PAPER_MANIFEST: enforce_deny=True means raw gate deny is effective deny."""

    def test_paper_manifest_denies_on_novelty_brake(self) -> None:
        """Gate denies (novelty brake) and paper enforcement makes result allowed=False."""
        log_entry = _make_novelty_log_entry()
        handler = _build_handler(
            manifest=PAPER_MANIFEST,
            evaluate_return=False,   # gate denies
            log_entry=log_entry,
        )

        result = handler.check_gate(
            symbol="SOL/USDT",
            exchange="binance",
            risk_filter_pass=True,
        )

        # Paper enforcement must propagate deny
        assert result.allowed is False, (
            "PAPER_MANIFEST must enforce deny: allowed=False when gate denies"
        )

        # Raw gate decision must also be False
        assert result.raw_gate_decision is False, (
            "raw_gate_decision must reflect true gate evaluation (False)"
        )

        # Deny reason code must be NOVELTY_BRAKE
        assert result.deny_reason_code == DenyReasonCode.NOVELTY_BRAKE, (
            f"deny_reason_code expected NOVELTY_BRAKE, got {result.deny_reason_code}"
        )

        # Mode manifest must be PAPER
        assert result.mode_manifest == PAPER_MANIFEST

    def test_paper_manifest_deny_code_not_none(self) -> None:
        """deny_reason_code must be non-None when gate denies under paper manifest."""
        log_entry = _make_novelty_log_entry()
        handler = _build_handler(PAPER_MANIFEST, False, log_entry)

        result = handler.check_gate()

        assert result.deny_reason_code is not None


# ---------------------------------------------------------------------------
# Test 3: shadow-to-paper transition changes behavior
# ---------------------------------------------------------------------------

class TestShadowToPaperTransitionChangesBehavior:
    """Simulates the promotion transition: same gate state, different manifest."""

    def test_shadow_to_paper_transition_changes_behavior(self) -> None:
        """Two handlers with same gate deny: shadow allows, paper denies.

        This test directly simulates the promotion transition scenario.
        The gate state is identical (novelty brake active), but the manifest
        change from SHADOW to PAPER causes the behavioral difference.
        """
        log_entry = _make_novelty_log_entry()

        # Before promotion: shadow mode
        shadow_handler = _build_handler(SHADOW_MANIFEST, False, log_entry)
        shadow_result = shadow_handler.check_gate(
            symbol="SOL/USDT",
            exchange="binance",
            risk_filter_pass=True,
        )

        # After promotion: paper mode (same gate conditions)
        paper_handler = _build_handler(PAPER_MANIFEST, False, log_entry)
        paper_result = paper_handler.check_gate(
            symbol="SOL/USDT",
            exchange="binance",
            risk_filter_pass=True,
        )

        # Shadow: allowed despite deny
        assert shadow_result.allowed is True, (
            "Pre-promotion (shadow): must be allowed=True even when gate denies"
        )

        # Paper: denied because enforcement is active
        assert paper_result.allowed is False, (
            "Post-promotion (paper): must be allowed=False when gate denies"
        )

        # Both must agree on raw gate decision
        assert shadow_result.raw_gate_decision is False
        assert paper_result.raw_gate_decision is False

        # Both must agree on deny reason code
        assert shadow_result.deny_reason_code == DenyReasonCode.NOVELTY_BRAKE
        assert paper_result.deny_reason_code == DenyReasonCode.NOVELTY_BRAKE

    def test_transition_only_differs_in_allowed_field(self) -> None:
        """The transition changes allowed but not raw_gate_decision or deny_reason_code."""
        log_entry = _make_novelty_log_entry()

        shadow_handler = _build_handler(SHADOW_MANIFEST, False, log_entry)
        paper_handler = _build_handler(PAPER_MANIFEST, False, log_entry)

        shadow_result = shadow_handler.check_gate()
        paper_result = paper_handler.check_gate()

        # Structural: only allowed differs between shadow and paper on deny
        assert shadow_result.allowed != paper_result.allowed
        assert shadow_result.raw_gate_decision == paper_result.raw_gate_decision
        assert shadow_result.deny_reason_code == paper_result.deny_reason_code


# ---------------------------------------------------------------------------
# Test 4: paper manifest allows when gate passes
# ---------------------------------------------------------------------------

class TestPaperManifestAllowsWhenGatePasses:
    """PAPER_MANIFEST: when gate passes (D6_EXECUTE_READY), result is allowed=True."""

    def test_paper_manifest_allows_when_gate_passes(self) -> None:
        """Gate passes (D6_EXECUTE_READY) and paper enforcement preserves allow."""
        log_entry = _make_pass_log_entry()
        handler = _build_handler(
            manifest=PAPER_MANIFEST,
            evaluate_return=True,   # gate allows
            log_entry=log_entry,
        )

        result = handler.check_gate(
            symbol="SOL/USDT",
            exchange="binance",
            risk_filter_pass=True,
        )

        # Gate passes; paper enforcement must preserve allow
        assert result.allowed is True, (
            "PAPER_MANIFEST must allow execution when gate passes"
        )

        # Raw gate decision must also be True
        assert result.raw_gate_decision is True, (
            "raw_gate_decision must reflect true gate allow (True)"
        )

        # No deny reason code when gate passes
        assert result.deny_reason_code is None, (
            "deny_reason_code must be None when gate passes"
        )

        # Mode manifest must be PAPER
        assert result.mode_manifest == PAPER_MANIFEST

    def test_paper_manifest_gate_pass_no_deny_in_shadow_axes(self) -> None:
        """shadow_axes_snapshot denial_reason is None when gate passes."""
        log_entry = _make_pass_log_entry()
        handler = _build_handler(PAPER_MANIFEST, True, log_entry)

        result = handler.check_gate(symbol="SOL/USDT", exchange="binance")

        assert result.shadow_axes_snapshot is not None
        assert result.shadow_axes_snapshot.get("denial_reason") is None

    def test_shadow_manifest_also_allows_when_gate_passes(self) -> None:
        """Both shadow and paper manifests allow when the gate passes."""
        log_entry = _make_pass_log_entry()

        shadow_result = _build_handler(SHADOW_MANIFEST, True, log_entry).check_gate()
        paper_result  = _build_handler(PAPER_MANIFEST,  True, log_entry).check_gate()

        assert shadow_result.allowed is True
        assert paper_result.allowed is True
        assert shadow_result.raw_gate_decision is True
        assert paper_result.raw_gate_decision is True


# ---------------------------------------------------------------------------
# Test 5: all manifests enforce_deny flag assertions
# ---------------------------------------------------------------------------

class TestAllManifestsEnforceDenyFlag:
    """Static assertions on the 4 predefined ModeCapabilityManifest instances."""

    def test_shadow_manifest_enforce_deny_false(self) -> None:
        assert SHADOW_MANIFEST.enforce_deny is False

    def test_paper_manifest_enforce_deny_true(self) -> None:
        assert PAPER_MANIFEST.enforce_deny is True

    def test_guarded_manifest_enforce_deny_true(self) -> None:
        assert GUARDED_MANIFEST.enforce_deny is True

    def test_live_manifest_enforce_deny_true(self) -> None:
        assert LIVE_MANIFEST.enforce_deny is True

    def test_all_manifests_enforce_deny_combined(self) -> None:
        """Consolidated single-assert version of all four manifest checks."""
        assert SHADOW_MANIFEST.enforce_deny is False
        assert PAPER_MANIFEST.enforce_deny is True
        assert GUARDED_MANIFEST.enforce_deny is True
        assert LIVE_MANIFEST.enforce_deny is True

    def test_shadow_manifest_allow_live_execution_false(self) -> None:
        """Shadow must not allow live execution."""
        assert SHADOW_MANIFEST.allow_live_execution is False

    def test_paper_manifest_allow_live_execution_false(self) -> None:
        """Paper must not allow live execution."""
        assert PAPER_MANIFEST.allow_live_execution is False

    def test_guarded_manifest_require_micro_size_true(self) -> None:
        """Guarded must require micro size."""
        assert GUARDED_MANIFEST.require_micro_size is True

    def test_live_manifest_require_micro_size_false(self) -> None:
        """Live must not require micro size (full sizing allowed)."""
        assert LIVE_MANIFEST.require_micro_size is False

    def test_all_manifests_are_frozen(self) -> None:
        """All manifests are frozen dataclasses (C10: no runtime mutation)."""
        for manifest in (SHADOW_MANIFEST, PAPER_MANIFEST, GUARDED_MANIFEST, LIVE_MANIFEST):
            original = manifest.enforce_deny
            with pytest.raises(Exception):
                manifest.enforce_deny = not original  # type: ignore[misc]

    def test_all_manifests_record_lv2_true(self) -> None:
        """All manifests must record LV-2 (execution divergence logging)."""
        for manifest in (SHADOW_MANIFEST, PAPER_MANIFEST, GUARDED_MANIFEST, LIVE_MANIFEST):
            assert manifest.record_lv2 is True, (
                f"{manifest} must have record_lv2=True"
            )

    def test_all_manifests_record_lv3_true(self) -> None:
        """All manifests must record LV-3 (session ledger logging)."""
        for manifest in (SHADOW_MANIFEST, PAPER_MANIFEST, GUARDED_MANIFEST, LIVE_MANIFEST):
            assert manifest.record_lv3 is True, (
                f"{manifest} must have record_lv3=True"
            )


# ---------------------------------------------------------------------------
# Test 6: enforcement logic formula verification
# ---------------------------------------------------------------------------

class TestEnforcementLogicFormula:
    """Direct verification of the enforce_deny formula from the source.

    Checks the 4 combinations of (raw_gate_allows, enforce_deny) against
    the formula: effective = raw OR NOT enforce_deny.
    """

    @pytest.mark.parametrize("raw,enforce_deny,expected_effective", [
        (False, False, True),   # SHADOW + deny -> allow (shadow override)
        (False, True,  False),  # PAPER  + deny -> deny  (enforcement)
        (True,  False, True),   # SHADOW + allow -> allow
        (True,  True,  True),   # PAPER  + allow -> allow
    ])
    def test_formula(
        self,
        raw: bool,
        enforce_deny: bool,
        expected_effective: bool,
    ) -> None:
        """Verify: effective_allowed = raw_gate_allows or not enforce_deny."""
        effective = raw or not enforce_deny
        assert effective is expected_effective, (
            f"Formula check failed: raw={raw}, enforce_deny={enforce_deny} "
            f"-> effective={effective}, expected={expected_effective}"
        )

    @pytest.mark.parametrize("raw,manifest,expected_allowed", [
        (False, SHADOW_MANIFEST, True),
        (False, PAPER_MANIFEST,  False),
        (True,  SHADOW_MANIFEST, True),
        (True,  PAPER_MANIFEST,  True),
    ])
    def test_handler_respects_formula(
        self,
        raw: bool,
        manifest: ModeCapabilityManifest,
        expected_allowed: bool,
    ) -> None:
        """PPFGateHandler.check_gate() respects the enforce_deny formula end-to-end."""
        if raw:
            log_entry = _make_pass_log_entry()
        else:
            log_entry = _make_novelty_log_entry()

        handler = _build_handler(manifest, raw, log_entry)
        result = handler.check_gate(symbol="SOL/USDT", exchange="binance")

        assert result.allowed is expected_allowed, (
            f"Handler formula mismatch: raw={raw}, manifest.enforce_deny="
            f"{manifest.enforce_deny} -> allowed={result.allowed}, "
            f"expected={expected_allowed}"
        )
        assert result.raw_gate_decision is raw


# ---------------------------------------------------------------------------
# Test 7: score threshold deny (non-novelty deny path)
# ---------------------------------------------------------------------------

class TestScoreThresholdDenyCode:
    """Verify SCORE_THRESHOLD_DENY is used when gate denies without novelty flag."""

    def _make_non_novelty_deny_log(self) -> PPFLogEntry:
        """PPFLogEntry for a score-based deny (regime_novelty_flag=False)."""
        return PPFLogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            asset_timeframe_tag="binance:SOL/USDT:1h",
            ppf_state=PPFState.D1_IDLE.value,
            allow_entry=False,
            filter_contribution_map={
                "I1": 0.1, "I2": 0.1, "I3": 0.1,
                "I4": 0.0,  "I5": 0.0,
                "O4_raw": 0.05, "O5_raw": 0.04,
            },
            rejection_reason_code=RejectionCode.SCORE_THRESHOLD_DENY.value
            if hasattr(RejectionCode, "SCORE_THRESHOLD_DENY")
            else RejectionCode.PATH_QUALITY_FAIL.value,
            reached_state=PPFState.D2_WATCH.value,
            regime_novelty_flag=False,   # novelty flag NOT set
        )

    def test_shadow_score_threshold_deny_uses_correct_code(self) -> None:
        """Shadow: score deny -> deny_reason_code=SCORE_THRESHOLD_DENY, allowed=True."""
        log_entry = self._make_non_novelty_deny_log()
        handler = _build_handler(SHADOW_MANIFEST, False, log_entry)

        result = handler.check_gate()

        assert result.allowed is True   # shadow override
        assert result.raw_gate_decision is False
        assert result.deny_reason_code == DenyReasonCode.SCORE_THRESHOLD_DENY

    def test_paper_score_threshold_deny_uses_correct_code(self) -> None:
        """Paper: score deny -> deny_reason_code=SCORE_THRESHOLD_DENY, allowed=False."""
        log_entry = self._make_non_novelty_deny_log()
        handler = _build_handler(PAPER_MANIFEST, False, log_entry)

        result = handler.check_gate()

        assert result.allowed is False   # paper enforcement
        assert result.raw_gate_decision is False
        assert result.deny_reason_code == DenyReasonCode.SCORE_THRESHOLD_DENY
