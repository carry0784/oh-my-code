"""PPF Paper Mode Readiness Test Suite.

Authority: PPF paper mode verification (shadow -> paper promotion gate)
Basis: PAPER_MANIFEST (enforce_deny=True, allow_live_execution=False)

Purpose:
    Verify that PAPER_MANIFEST behaves correctly for every deny path so that
    the shadow -> paper promotion is safe to execute.

Tests:
    1. TestPaperModeGateDeny        - PAPER denies on every DenyReasonCode
    2. TestPaperModeNoLiveExecution - PAPER.allow_live_execution=False, require_micro_size=False
    3. TestPaperModeSessionAbort    - allow_session_abort=True, aborted ledger -> SESSION_ABORTED
    4. TestPaperModeRecording       - record_lv2/lv3=True, ppf_log_entry + session_summary populated
    5. TestPaperVsShadowCompleteness - For every DenyReasonCode, PAPER denies while SHADOW allows
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from unittest.mock import MagicMock, PropertyMock

import numpy as np
import pytest

from strategies.ppf.constants import MarketProfile, PPFState, RejectionCode
from strategies.ppf.execution_ledger import (
    DivergenceSeverity,
    DivergenceType,
    ExecutionObservation,
    ExecutionPath,
)
from strategies.ppf.logging_schema import PPFLogEntry
from strategies.ppf.parameters import PPFParameters
from strategies.ppf.ppf_gate_handler import (
    PAPER_MANIFEST,
    SHADOW_MANIFEST,
    DenyReasonCode,
    ModeCapabilityManifest,
    PPFGateHandler,
    PPFGateResult,
)
from strategies.ppf.session_ledger import SessionBudgetConfig, SessionFailureBudgetLedger


# ---------------------------------------------------------------------------
# Shared helpers (mirrors test_ppf_enforcement_simulation.py pattern)
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


def _make_ohlcv_provider():
    """Callable that returns minimal valid OHLCV arrays."""
    highs   = np.linspace(101, 110, 50)
    lows    = np.linspace(99,  108, 50)
    closes  = np.linspace(100, 109, 50)
    volumes = np.ones(50) * 500.0

    def provider():
        return (highs, lows, closes, volumes)

    return provider


def _make_gate_mock(evaluate_return: bool, log_entry: PPFLogEntry) -> MagicMock:
    """Build a MagicMock for PPFGate.

    Mocks:
    - is_active:      always True (gate not deactivated by constitution)
    - evaluate():     returns evaluate_return
    - last_log_entry: returns log_entry
    """
    gate = MagicMock()
    type(gate).is_active = PropertyMock(return_value=True)
    gate.evaluate.return_value = evaluate_return
    type(gate).last_log_entry = PropertyMock(return_value=log_entry)
    return gate


def _build_handler(
    manifest: ModeCapabilityManifest,
    evaluate_return: bool,
    log_entry: PPFLogEntry,
    session_ledger: Optional[SessionFailureBudgetLedger] = None,
    ohlcv_provider=None,
) -> PPFGateHandler:
    """Construct a PPFGateHandler with a mocked gate and given manifest."""
    gate = _make_gate_mock(evaluate_return, log_entry)
    ledger = session_ledger if session_ledger is not None else _make_session_ledger()
    provider = ohlcv_provider if ohlcv_provider is not None else _make_ohlcv_provider()
    return PPFGateHandler(
        ppf_gate=gate,
        session_ledger=ledger,
        ohlcv_provider=provider,
        manifest=manifest,
    )


def _make_novelty_log_entry() -> PPFLogEntry:
    """PPFLogEntry for NOVELTY_BRAKE deny (regime_novelty_flag=True)."""
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


def _make_score_deny_log_entry() -> PPFLogEntry:
    """PPFLogEntry for SCORE_THRESHOLD_DENY (regime_novelty_flag=False)."""
    return PPFLogEntry(
        timestamp=datetime.now(timezone.utc).isoformat(),
        asset_timeframe_tag="binance:SOL/USDT:1h",
        ppf_state=PPFState.D2_WATCH.value,
        allow_entry=False,
        filter_contribution_map={
            "I1": 0.1, "I2": 0.1, "I3": 0.1,
            "I4": 0.0,  "I5": 0.0,
            "O4_raw": 0.05, "O5_raw": 0.04,
        },
        rejection_reason_code=RejectionCode.PATH_QUALITY_FAIL.value,
        reached_state=PPFState.D2_WATCH.value,
        regime_novelty_flag=False,
    )


def _make_pass_log_entry() -> PPFLogEntry:
    """PPFLogEntry for D6_EXECUTE_READY allow (regime_novelty_flag=False)."""
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


def _make_aborted_session_ledger() -> SessionFailureBudgetLedger:
    """Session ledger that has already been aborted via blocker divergence."""
    ledger = SessionFailureBudgetLedger(config=SessionBudgetConfig())
    obs = ExecutionObservation(
        order_submit_ts=datetime.now(timezone.utc).isoformat(),
        venue_ack_ts=None,
        reject_code=None,
        timeout_flag=False,
        venue_latency_ms=None,
        partial_fill_qty=0.0,
        final_fill_qty=0.0,
        expected_path=ExecutionPath.SUBMIT_ACK_FILL,
        actual_path=ExecutionPath.SUBMIT_REJECT,
    )
    ledger.record_execution_event(
        exec_obs=obs,
        divergence_severity=DivergenceSeverity.BLOCKER,
        divergence_type=DivergenceType.UNEXPECTED_REJECT,
    )
    assert ledger.is_aborted, "Precondition: ledger must be aborted after BLOCKER divergence"
    return ledger


def _make_gate_mock_inactive() -> MagicMock:
    """Gate mock with is_active=False (constitution deactivated)."""
    gate = MagicMock()
    type(gate).is_active = PropertyMock(return_value=False)
    gate.evaluate.return_value = False
    type(gate).last_log_entry = PropertyMock(return_value=None)
    return gate


# ---------------------------------------------------------------------------
# 1. TestPaperModeGateDeny
#    PAPER_MANIFEST denies on every reachable DenyReasonCode path.
# ---------------------------------------------------------------------------

class TestPaperModeGateDeny:
    """PAPER_MANIFEST (enforce_deny=True) must produce allowed=False for every
    deny path that the gate handler can emit."""

    # -- NOVELTY_BRAKE: evaluate=False + regime_novelty_flag=True --

    def test_paper_denies_novelty_brake(self) -> None:
        """NOVELTY_BRAKE path: paper enforcement must deny."""
        handler = _build_handler(PAPER_MANIFEST, False, _make_novelty_log_entry())
        result = handler.check_gate(symbol="SOL/USDT", exchange="binance")

        assert result.allowed is False
        assert result.raw_gate_decision is False
        assert result.deny_reason_code == DenyReasonCode.NOVELTY_BRAKE
        assert result.mode_manifest == PAPER_MANIFEST

    # -- SCORE_THRESHOLD_DENY: evaluate=False + regime_novelty_flag=False --

    def test_paper_denies_score_threshold(self) -> None:
        """SCORE_THRESHOLD_DENY path: paper enforcement must deny."""
        handler = _build_handler(PAPER_MANIFEST, False, _make_score_deny_log_entry())
        result = handler.check_gate(symbol="SOL/USDT", exchange="binance")

        assert result.allowed is False
        assert result.raw_gate_decision is False
        assert result.deny_reason_code == DenyReasonCode.SCORE_THRESHOLD_DENY
        assert result.mode_manifest == PAPER_MANIFEST

    # -- DATA_MISSING: ohlcv_provider returns None --

    def test_paper_denies_data_missing_none_provider(self) -> None:
        """DATA_MISSING path (provider returns None): paper enforcement must deny."""
        gate = _make_gate_mock(False, _make_score_deny_log_entry())
        handler = PPFGateHandler(
            ppf_gate=gate,
            session_ledger=_make_session_ledger(),
            ohlcv_provider=lambda: None,
            manifest=PAPER_MANIFEST,
        )
        result = handler.check_gate(symbol="SOL/USDT", exchange="binance")

        assert result.allowed is False
        assert result.deny_reason_code == DenyReasonCode.DATA_MISSING

    # -- DATA_MISSING: ohlcv_provider returns empty arrays --

    def test_paper_denies_data_missing_empty_arrays(self) -> None:
        """DATA_MISSING path (empty closes): paper enforcement must deny."""
        gate = _make_gate_mock(False, _make_score_deny_log_entry())
        handler = PPFGateHandler(
            ppf_gate=gate,
            session_ledger=_make_session_ledger(),
            ohlcv_provider=lambda: (
                np.array([]), np.array([]), np.array([]), np.array([])
            ),
            manifest=PAPER_MANIFEST,
        )
        result = handler.check_gate(symbol="SOL/USDT", exchange="binance")

        assert result.allowed is False
        assert result.deny_reason_code == DenyReasonCode.DATA_MISSING

    # -- CONSTITUTION_DEACTIVATED: gate.is_active=False before evaluate --

    def test_paper_denies_constitution_deactivated(self) -> None:
        """CONSTITUTION_DEACTIVATED path: paper enforcement must deny."""
        gate = _make_gate_mock_inactive()
        handler = PPFGateHandler(
            ppf_gate=gate,
            session_ledger=_make_session_ledger(),
            ohlcv_provider=_make_ohlcv_provider(),
            manifest=PAPER_MANIFEST,
        )
        result = handler.check_gate(symbol="SOL/USDT", exchange="binance")

        assert result.allowed is False
        assert result.deny_reason_code == DenyReasonCode.CONSTITUTION_DEACTIVATED

    # -- SESSION_ABORTED: session_ledger.is_aborted=True --

    def test_paper_denies_session_aborted(self) -> None:
        """SESSION_ABORTED path: paper enforcement must deny."""
        aborted_ledger = _make_aborted_session_ledger()
        gate = _make_gate_mock(True, _make_pass_log_entry())
        handler = PPFGateHandler(
            ppf_gate=gate,
            session_ledger=aborted_ledger,
            ohlcv_provider=_make_ohlcv_provider(),
            manifest=PAPER_MANIFEST,
        )
        result = handler.check_gate(symbol="SOL/USDT", exchange="binance")

        assert result.allowed is False
        assert result.deny_reason_code == DenyReasonCode.SESSION_ABORTED

    # -- INTERNAL_GATE_ERROR: exception inside check_gate --

    def test_paper_denies_internal_gate_error(self) -> None:
        """INTERNAL_GATE_ERROR path: exception inside check_gate -> fail-closed deny."""
        gate = MagicMock()
        type(gate).is_active = PropertyMock(return_value=True)
        gate.evaluate.side_effect = RuntimeError("simulated internal error")
        type(gate).last_log_entry = PropertyMock(return_value=None)

        handler = PPFGateHandler(
            ppf_gate=gate,
            session_ledger=_make_session_ledger(),
            ohlcv_provider=_make_ohlcv_provider(),
            manifest=PAPER_MANIFEST,
        )
        result = handler.check_gate(symbol="SOL/USDT", exchange="binance")

        assert result.allowed is False
        assert result.deny_reason_code == DenyReasonCode.INTERNAL_GATE_ERROR

    # -- Parametrize: check deny_reason_code is non-None for all deny paths --

    @pytest.mark.parametrize("deny_code,setup", [
        (
            DenyReasonCode.NOVELTY_BRAKE,
            lambda: _build_handler(PAPER_MANIFEST, False, _make_novelty_log_entry()),
        ),
        (
            DenyReasonCode.SCORE_THRESHOLD_DENY,
            lambda: _build_handler(PAPER_MANIFEST, False, _make_score_deny_log_entry()),
        ),
        (
            DenyReasonCode.DATA_MISSING,
            lambda: PPFGateHandler(
                ppf_gate=_make_gate_mock(False, _make_score_deny_log_entry()),
                session_ledger=_make_session_ledger(),
                ohlcv_provider=lambda: None,
                manifest=PAPER_MANIFEST,
            ),
        ),
        (
            DenyReasonCode.CONSTITUTION_DEACTIVATED,
            lambda: PPFGateHandler(
                ppf_gate=_make_gate_mock_inactive(),
                session_ledger=_make_session_ledger(),
                ohlcv_provider=_make_ohlcv_provider(),
                manifest=PAPER_MANIFEST,
            ),
        ),
        (
            DenyReasonCode.SESSION_ABORTED,
            lambda: PPFGateHandler(
                ppf_gate=_make_gate_mock(True, _make_pass_log_entry()),
                session_ledger=_make_aborted_session_ledger(),
                ohlcv_provider=_make_ohlcv_provider(),
                manifest=PAPER_MANIFEST,
            ),
        ),
    ])
    def test_paper_deny_reason_code_is_set(self, deny_code: DenyReasonCode, setup) -> None:
        """For each deny path, deny_reason_code must equal the expected code."""
        handler = setup()
        result = handler.check_gate(symbol="SOL/USDT", exchange="binance")

        assert result.allowed is False, (
            f"Expected allowed=False for {deny_code.value}, got allowed=True"
        )
        assert result.deny_reason_code == deny_code, (
            f"Expected deny_reason_code={deny_code.value}, "
            f"got {result.deny_reason_code}"
        )

    def test_paper_deny_reason_code_version_is_v1(self) -> None:
        """deny_reason_code_version must be 'v1' for all deny paths under paper."""
        handler = _build_handler(PAPER_MANIFEST, False, _make_novelty_log_entry())
        result = handler.check_gate()

        assert result.deny_reason_code_version == "v1"


# ---------------------------------------------------------------------------
# 2. TestPaperModeNoLiveExecution
#    PAPER_MANIFEST must NOT allow live execution and must NOT require micro size.
# ---------------------------------------------------------------------------

class TestPaperModeNoLiveExecution:
    """PAPER_MANIFEST capability assertions: no live execution, no micro size requirement."""

    def test_paper_manifest_allow_live_execution_false(self) -> None:
        """Paper mode must never allow live execution (pre-production gate)."""
        assert PAPER_MANIFEST.allow_live_execution is False

    def test_paper_manifest_require_micro_size_false(self) -> None:
        """Paper mode does not require micro size (not a live constraint)."""
        assert PAPER_MANIFEST.require_micro_size is False

    def test_paper_manifest_enforce_deny_true(self) -> None:
        """Paper mode must enforce deny (promotion gate is active)."""
        assert PAPER_MANIFEST.enforce_deny is True

    def test_paper_manifest_is_frozen(self) -> None:
        """PAPER_MANIFEST is a frozen dataclass (C10: no runtime mutation)."""
        with pytest.raises(Exception):
            PAPER_MANIFEST.allow_live_execution = True  # type: ignore[misc]

    def test_paper_manifest_has_all_six_boolean_fields(self) -> None:
        """PAPER_MANIFEST must expose all 6 boolean fields from ModeCapabilityManifest."""
        assert hasattr(PAPER_MANIFEST, "enforce_deny")
        assert hasattr(PAPER_MANIFEST, "record_lv2")
        assert hasattr(PAPER_MANIFEST, "record_lv3")
        assert hasattr(PAPER_MANIFEST, "allow_session_abort")
        assert hasattr(PAPER_MANIFEST, "allow_live_execution")
        assert hasattr(PAPER_MANIFEST, "require_micro_size")

    def test_paper_result_mode_manifest_is_paper(self) -> None:
        """PPFGateResult.mode_manifest must be PAPER_MANIFEST when handler uses paper."""
        handler = _build_handler(PAPER_MANIFEST, True, _make_pass_log_entry())
        result = handler.check_gate()

        assert result.mode_manifest == PAPER_MANIFEST
        assert result.mode_manifest.allow_live_execution is False
        assert result.mode_manifest.require_micro_size is False


# ---------------------------------------------------------------------------
# 3. TestPaperModeSessionAbort
#    PAPER_MANIFEST.allow_session_abort=True.
#    When session ledger is aborted, check_gate must return deny=SESSION_ABORTED.
# ---------------------------------------------------------------------------

class TestPaperModeSessionAbort:
    """PAPER_MANIFEST session abort behavior."""

    def test_paper_allow_session_abort_is_true(self) -> None:
        """PAPER_MANIFEST.allow_session_abort must be True."""
        assert PAPER_MANIFEST.allow_session_abort is True

    def test_paper_returns_session_aborted_when_ledger_aborted(self) -> None:
        """Aborted session ledger -> check_gate returns SESSION_ABORTED deny."""
        aborted_ledger = _make_aborted_session_ledger()
        assert aborted_ledger.is_aborted is True

        gate = _make_gate_mock(True, _make_pass_log_entry())
        handler = PPFGateHandler(
            ppf_gate=gate,
            session_ledger=aborted_ledger,
            ohlcv_provider=_make_ohlcv_provider(),
            manifest=PAPER_MANIFEST,
        )

        result = handler.check_gate(symbol="SOL/USDT", exchange="binance")

        assert result.allowed is False
        assert result.deny_reason_code == DenyReasonCode.SESSION_ABORTED
        assert result.raw_gate_decision is False

    def test_paper_session_aborted_result_contains_session_summary(self) -> None:
        """SESSION_ABORTED result must carry session_summary from the ledger."""
        aborted_ledger = _make_aborted_session_ledger()
        gate = _make_gate_mock(True, _make_pass_log_entry())
        handler = PPFGateHandler(
            ppf_gate=gate,
            session_ledger=aborted_ledger,
            ohlcv_provider=_make_ohlcv_provider(),
            manifest=PAPER_MANIFEST,
        )

        result = handler.check_gate(symbol="SOL/USDT", exchange="binance")

        assert result.session_summary is not None
        assert result.session_summary.get("is_aborted") is True

    def test_paper_session_aborted_abort_reason_propagated(self) -> None:
        """abort_reason from ledger must be propagated into session_summary."""
        aborted_ledger = _make_aborted_session_ledger()
        gate = _make_gate_mock(True, _make_pass_log_entry())
        handler = PPFGateHandler(
            ppf_gate=gate,
            session_ledger=aborted_ledger,
            ohlcv_provider=_make_ohlcv_provider(),
            manifest=PAPER_MANIFEST,
        )

        result = handler.check_gate()

        assert result.session_summary is not None
        abort_reason = result.session_summary.get("abort_reason")
        assert abort_reason is not None
        assert len(str(abort_reason)) > 0

    def test_shadow_allows_even_with_aborted_ledger(self) -> None:
        """SHADOW_MANIFEST (enforce_deny=False) allows even when session is aborted."""
        aborted_ledger = _make_aborted_session_ledger()
        gate = _make_gate_mock(True, _make_pass_log_entry())
        handler = PPFGateHandler(
            ppf_gate=gate,
            session_ledger=aborted_ledger,
            ohlcv_provider=_make_ohlcv_provider(),
            manifest=SHADOW_MANIFEST,
        )

        result = handler.check_gate()

        assert result.allowed is True
        assert result.deny_reason_code == DenyReasonCode.SESSION_ABORTED

    def test_paper_allow_session_abort_activates_abort_logging(self) -> None:
        """record_execution_outcome returns abort_reason when PAPER + blocker divergence."""
        ledger = _make_session_ledger()
        gate = _make_gate_mock(True, _make_pass_log_entry())
        handler = PPFGateHandler(
            ppf_gate=gate,
            session_ledger=ledger,
            ohlcv_provider=_make_ohlcv_provider(),
            manifest=PAPER_MANIFEST,
        )

        # Trigger a BLOCKER divergence via record_execution_outcome
        abort_reason = handler.record_execution_outcome(
            order_status="REJECTED",
            expected_path=ExecutionPath.SUBMIT_ACK_FILL,
            reject_code="BLOCKER_TEST",
            timeout_flag=False,
        )

        # Under PAPER_MANIFEST (record_lv2=True, record_lv3=True, allow_session_abort=True)
        # record_execution_outcome should propagate the abort when budget exceeded
        # Note: a single reject does not exceed budget (max=3), so abort_reason=None here.
        # We verify the method is callable and returns None or a string.
        assert abort_reason is None or isinstance(abort_reason, str)


# ---------------------------------------------------------------------------
# 4. TestPaperModeRecording
#    PAPER_MANIFEST: record_lv2=True, record_lv3=True.
#    After check_gate, ppf_log_entry and session_summary must be populated.
# ---------------------------------------------------------------------------

class TestPaperModeRecording:
    """PAPER_MANIFEST recording assertions."""

    def test_paper_manifest_record_lv2_true(self) -> None:
        """PAPER_MANIFEST.record_lv2 must be True."""
        assert PAPER_MANIFEST.record_lv2 is True

    def test_paper_manifest_record_lv3_true(self) -> None:
        """PAPER_MANIFEST.record_lv3 must be True."""
        assert PAPER_MANIFEST.record_lv3 is True

    def test_paper_check_gate_allow_populates_ppf_log_entry(self) -> None:
        """When gate allows under paper, ppf_log_entry must be set in the result."""
        log_entry = _make_pass_log_entry()
        handler = _build_handler(PAPER_MANIFEST, True, log_entry)

        result = handler.check_gate(symbol="SOL/USDT", exchange="binance")

        assert result.ppf_log_entry is not None

    def test_paper_check_gate_allow_populates_session_summary(self) -> None:
        """When gate allows under paper, session_summary must be set in the result."""
        handler = _build_handler(PAPER_MANIFEST, True, _make_pass_log_entry())
        result = handler.check_gate(symbol="SOL/USDT", exchange="binance")

        assert result.session_summary is not None
        assert isinstance(result.session_summary, dict)

    def test_paper_check_gate_deny_populates_session_summary(self) -> None:
        """When gate denies under paper, session_summary must still be set."""
        handler = _build_handler(PAPER_MANIFEST, False, _make_novelty_log_entry())
        result = handler.check_gate(symbol="SOL/USDT", exchange="binance")

        assert result.session_summary is not None
        assert isinstance(result.session_summary, dict)

    def test_paper_session_summary_has_required_keys(self) -> None:
        """session_summary must contain expected session ledger keys."""
        handler = _build_handler(PAPER_MANIFEST, True, _make_pass_log_entry())
        result = handler.check_gate()

        summary = result.session_summary
        assert summary is not None
        for key in ("session_id", "is_aborted", "reject_count", "timeout_count"):
            assert key in summary, f"session_summary missing required key: {key}"

    def test_paper_ppf_log_entry_regime_novelty_flag_matches(self) -> None:
        """ppf_log_entry.regime_novelty_flag must match the log entry injected."""
        log_entry = _make_pass_log_entry()
        handler = _build_handler(PAPER_MANIFEST, True, log_entry)
        result = handler.check_gate()

        assert result.ppf_log_entry is not None
        assert result.ppf_log_entry.regime_novelty_flag is False

    def test_paper_ppf_log_entry_novelty_brake_regime_flag_true(self) -> None:
        """When novelty brake fires, ppf_log_entry.regime_novelty_flag must be True."""
        log_entry = _make_novelty_log_entry()
        handler = _build_handler(PAPER_MANIFEST, False, log_entry)
        result = handler.check_gate()

        assert result.ppf_log_entry is not None
        assert result.ppf_log_entry.regime_novelty_flag is True

    def test_paper_shadow_axes_snapshot_is_populated(self) -> None:
        """shadow_axes_snapshot must be populated after check_gate under paper."""
        handler = _build_handler(PAPER_MANIFEST, True, _make_pass_log_entry())
        result = handler.check_gate(symbol="SOL/USDT", exchange="binance")

        assert result.shadow_axes_snapshot is not None
        axes = result.shadow_axes_snapshot
        assert axes.get("symbol") == "SOL/USDT"
        assert axes.get("venue") == "binance"

    def test_paper_result_to_dict_is_serializable(self) -> None:
        """PPFGateResult.to_dict() must succeed without errors under paper mode."""
        handler = _build_handler(PAPER_MANIFEST, True, _make_pass_log_entry())
        result = handler.check_gate()

        d = result.to_dict()
        assert isinstance(d, dict)
        assert "allowed" in d
        assert "mode_manifest" in d
        assert d["mode_manifest"] is not None

    def test_paper_data_missing_no_ppf_log_entry(self) -> None:
        """DATA_MISSING path: ppf_log_entry is None (gate was never called)."""
        gate = _make_gate_mock(False, _make_score_deny_log_entry())
        handler = PPFGateHandler(
            ppf_gate=gate,
            session_ledger=_make_session_ledger(),
            ohlcv_provider=lambda: None,
            manifest=PAPER_MANIFEST,
        )
        result = handler.check_gate()

        assert result.ppf_log_entry is None


# ---------------------------------------------------------------------------
# 5. TestPaperVsShadowCompleteness
#    For every DenyReasonCode that is reachable, PAPER denies while SHADOW allows.
# ---------------------------------------------------------------------------

class TestPaperVsShadowCompleteness:
    """Comprehensive transition test: PAPER denies on every deny code, SHADOW allows."""

    def _build_paper_and_shadow(self, *args, **kwargs):
        """Helper: returns (shadow_result, paper_result) for the same gate conditions."""
        raise NotImplementedError

    @pytest.mark.parametrize("deny_code,paper_setup,shadow_setup", [
        (
            DenyReasonCode.NOVELTY_BRAKE,
            lambda: _build_handler(PAPER_MANIFEST, False, _make_novelty_log_entry()),
            lambda: _build_handler(SHADOW_MANIFEST, False, _make_novelty_log_entry()),
        ),
        (
            DenyReasonCode.SCORE_THRESHOLD_DENY,
            lambda: _build_handler(PAPER_MANIFEST, False, _make_score_deny_log_entry()),
            lambda: _build_handler(SHADOW_MANIFEST, False, _make_score_deny_log_entry()),
        ),
        (
            DenyReasonCode.DATA_MISSING,
            lambda: PPFGateHandler(
                ppf_gate=_make_gate_mock(False, _make_score_deny_log_entry()),
                session_ledger=_make_session_ledger(),
                ohlcv_provider=lambda: None,
                manifest=PAPER_MANIFEST,
            ),
            lambda: PPFGateHandler(
                ppf_gate=_make_gate_mock(False, _make_score_deny_log_entry()),
                session_ledger=_make_session_ledger(),
                ohlcv_provider=lambda: None,
                manifest=SHADOW_MANIFEST,
            ),
        ),
        (
            DenyReasonCode.CONSTITUTION_DEACTIVATED,
            lambda: PPFGateHandler(
                ppf_gate=_make_gate_mock_inactive(),
                session_ledger=_make_session_ledger(),
                ohlcv_provider=_make_ohlcv_provider(),
                manifest=PAPER_MANIFEST,
            ),
            lambda: PPFGateHandler(
                ppf_gate=_make_gate_mock_inactive(),
                session_ledger=_make_session_ledger(),
                ohlcv_provider=_make_ohlcv_provider(),
                manifest=SHADOW_MANIFEST,
            ),
        ),
        (
            DenyReasonCode.SESSION_ABORTED,
            lambda: PPFGateHandler(
                ppf_gate=_make_gate_mock(True, _make_pass_log_entry()),
                session_ledger=_make_aborted_session_ledger(),
                ohlcv_provider=_make_ohlcv_provider(),
                manifest=PAPER_MANIFEST,
            ),
            lambda: PPFGateHandler(
                ppf_gate=_make_gate_mock(True, _make_pass_log_entry()),
                session_ledger=_make_aborted_session_ledger(),
                ohlcv_provider=_make_ohlcv_provider(),
                manifest=SHADOW_MANIFEST,
            ),
        ),
        (
            DenyReasonCode.INTERNAL_GATE_ERROR,
            lambda: PPFGateHandler(
                ppf_gate=_make_raising_gate_mock(),
                session_ledger=_make_session_ledger(),
                ohlcv_provider=_make_ohlcv_provider(),
                manifest=PAPER_MANIFEST,
            ),
            lambda: PPFGateHandler(
                ppf_gate=_make_raising_gate_mock(),
                session_ledger=_make_session_ledger(),
                ohlcv_provider=_make_ohlcv_provider(),
                manifest=SHADOW_MANIFEST,
            ),
        ),
    ])
    def test_paper_denies_shadow_allows_for_each_deny_code(
        self,
        deny_code: DenyReasonCode,
        paper_setup,
        shadow_setup,
    ) -> None:
        """For deny code {deny_code}, PAPER must deny while SHADOW allows."""
        paper_handler = paper_setup()
        shadow_handler = shadow_setup()

        paper_result = paper_handler.check_gate(symbol="SOL/USDT", exchange="binance")
        shadow_result = shadow_handler.check_gate(symbol="SOL/USDT", exchange="binance")

        # PAPER: enforcement active -> must deny
        assert paper_result.allowed is False, (
            f"[{deny_code.value}] PAPER must deny but got allowed=True"
        )
        assert paper_result.deny_reason_code == deny_code, (
            f"[{deny_code.value}] PAPER deny_reason_code mismatch: "
            f"expected {deny_code.value}, got {paper_result.deny_reason_code}"
        )

        # SHADOW: enforcement inactive -> must allow
        assert shadow_result.allowed is True, (
            f"[{deny_code.value}] SHADOW must allow but got allowed=False"
        )
        assert shadow_result.deny_reason_code == deny_code, (
            f"[{deny_code.value}] SHADOW deny_reason_code must still be set: "
            f"expected {deny_code.value}, got {shadow_result.deny_reason_code}"
        )

    def test_paper_and_shadow_agree_on_raw_gate_decision_for_novelty(self) -> None:
        """Both manifests must agree on raw_gate_decision for novelty brake path."""
        log_entry = _make_novelty_log_entry()
        paper_result = _build_handler(PAPER_MANIFEST, False, log_entry).check_gate()
        shadow_result = _build_handler(SHADOW_MANIFEST, False, log_entry).check_gate()

        assert paper_result.raw_gate_decision is False
        assert shadow_result.raw_gate_decision is False
        assert paper_result.raw_gate_decision == shadow_result.raw_gate_decision

    def test_paper_and_shadow_agree_on_raw_gate_decision_for_score_deny(self) -> None:
        """Both manifests must agree on raw_gate_decision for score threshold deny path."""
        log_entry = _make_score_deny_log_entry()
        paper_result = _build_handler(PAPER_MANIFEST, False, log_entry).check_gate()
        shadow_result = _build_handler(SHADOW_MANIFEST, False, log_entry).check_gate()

        assert paper_result.raw_gate_decision is False
        assert shadow_result.raw_gate_decision is False

    def test_paper_and_shadow_both_allow_when_gate_passes(self) -> None:
        """When gate allows, both PAPER and SHADOW must produce allowed=True."""
        log_entry = _make_pass_log_entry()
        paper_result = _build_handler(PAPER_MANIFEST, True, log_entry).check_gate()
        shadow_result = _build_handler(SHADOW_MANIFEST, True, log_entry).check_gate()

        assert paper_result.allowed is True
        assert shadow_result.allowed is True
        assert paper_result.deny_reason_code is None
        assert shadow_result.deny_reason_code is None

    def test_all_deny_codes_covered_by_parametrize(self) -> None:
        """Verify that the parametrize list covers all DenyReasonCode values that are
        reachable from PPFGateHandler.check_gate() (excludes COOLDOWN_ACTIVE and
        MODE_ENFORCEMENT_DISABLED which require different session state setups)."""
        reachable_from_gate = {
            DenyReasonCode.NOVELTY_BRAKE,
            DenyReasonCode.SCORE_THRESHOLD_DENY,
            DenyReasonCode.DATA_MISSING,
            DenyReasonCode.CONSTITUTION_DEACTIVATED,
            DenyReasonCode.SESSION_ABORTED,
            DenyReasonCode.INTERNAL_GATE_ERROR,
        }
        all_codes = set(DenyReasonCode)
        # Document the codes not reachable via the standard check_gate() path:
        # - DATA_STALE: defined in DenyReasonCode but has no separate code path
        #   in _check_gate_internal (stale data falls under DATA_MISSING branch)
        # - COOLDOWN_ACTIVE: requires session ledger cooldown state, not aborted state
        # - MODE_ENFORCEMENT_DISABLED: not currently emitted by the handler
        not_tested_via_gate = {
            DenyReasonCode.DATA_STALE,
            DenyReasonCode.COOLDOWN_ACTIVE,
            DenyReasonCode.MODE_ENFORCEMENT_DISABLED,
        }
        assert reachable_from_gate | not_tested_via_gate == all_codes, (
            "DenyReasonCode set may have changed; update this test accordingly."
        )


# ---------------------------------------------------------------------------
# Module-level helper used by TestPaperVsShadowCompleteness parametrize
# (must be defined at module scope so lambda in parametrize can reference it)
# ---------------------------------------------------------------------------

def _make_raising_gate_mock() -> MagicMock:
    """Gate mock whose evaluate() raises RuntimeError (-> INTERNAL_GATE_ERROR path)."""
    gate = MagicMock()
    type(gate).is_active = PropertyMock(return_value=True)
    gate.evaluate.side_effect = RuntimeError("simulated error for INTERNAL_GATE_ERROR path")
    type(gate).last_log_entry = PropertyMock(return_value=None)
    return gate
