"""Comprehensive tests for PPF governance modules (S1-S5).

Covers:
  S1  — OhlcvPreflightValidator  (TestOhlcvPreflightValidator)
  S3/S4 — PPFGovernanceEngine    (TestPPFGovernanceEngine + TestPPFGovernanceTierComputation)
  S5  — ValPDC002Judge           (TestValPDC002Judge)
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ohlcv_preflight_validator import OhlcvPreflightValidator
from app.services.ppf_governance_engine import (
    ALLOWED_TRANSITIONS,
    MIN_BARS_FOR_VALIDATION,
    MIN_NOVELTY_EVENTS,
    PPFBlockLevel,
    PPFGovernanceEngine,
    PPFGovernanceState,
    PPFGovernanceTier,
)
from app.services.ppf_val_pdc_002 import ValPDC002Judge, ValPDC002Verdict


# ---------------------------------------------------------------------------
# Helpers / factories
# ---------------------------------------------------------------------------


def _make_comparison_report(
    *,
    metrics: list | None = None,
    insufficiency_reasons: list[str] | None = None,
    baseline_id: str = "baseline-test-001",
    live_bars_evaluated: int = 400,
    live_novelty_count: int = 12,
    all_within_tolerance: bool = True,
) -> SimpleNamespace:
    """Return a minimal duck-typed PPFComparisonReport substitute."""
    return SimpleNamespace(
        baseline_id=baseline_id,
        live_bars_evaluated=live_bars_evaluated,
        live_novelty_count=live_novelty_count,
        all_within_tolerance=all_within_tolerance,
        metrics=metrics or [],
        insufficiency_reasons=insufficiency_reasons or [],
    )


def _make_metric(
    metric_name: str,
    *,
    within_tolerance: bool = True,
    delta_abs: float = 0.01,
    backtest_value: float = 0.10,
    live_value: float = 0.11,
) -> SimpleNamespace:
    """Return a minimal duck-typed ComparisonMetric substitute."""
    return SimpleNamespace(
        metric_name=metric_name,
        within_tolerance=within_tolerance,
        delta_abs=delta_abs,
        backtest_value=backtest_value,
        live_value=live_value,
    )


def _full_passing_metrics() -> list:
    """Return metric list that satisfies C2 (deny_rate), C3 (fpr), C4 (js)."""
    return [
        _make_metric("deny_rate", within_tolerance=True),
        _make_metric("fpr", within_tolerance=True),
        _make_metric(
            "deny_reason_distribution_js",
            within_tolerance=True,
            delta_abs=0.05,
            backtest_value=0.0,
            live_value=0.05,
        ),
    ]


# ---------------------------------------------------------------------------
# Helper: advance engine through the full pipeline
# ---------------------------------------------------------------------------

_FULL_CHAIN = [
    PPFGovernanceState.DATA_READY,
    PPFGovernanceState.PHASE_A_RUNNING,
    PPFGovernanceState.BASELINE_FROZEN,
    PPFGovernanceState.PHASE_B_COLLECTING,
    PPFGovernanceState.VALIDATION_READY,
    PPFGovernanceState.VAL_PDC_002_ISSUED,
]


def _advance_to_terminal(engine: PPFGovernanceEngine) -> None:
    for state in _FULL_CHAIN:
        engine.transition(state)


# ---------------------------------------------------------------------------
# Class 1: TestOhlcvPreflightValidator
# ---------------------------------------------------------------------------


class TestOhlcvPreflightValidator:
    """Unit tests for OhlcvPreflightValidator.

    DB-requiring methods use mocked async sessions.
    Pure helpers (_compute_data_hash, _check_symbol_lock) are called directly.
    """

    def setup_method(self):
        self.validator = OhlcvPreflightValidator()

    # --- Symbol lock ---

    @pytest.mark.asyncio
    async def test_symbol_lock_rejects_non_sol_usdt(self):
        """Non-SOL/USDT symbol must return (False, reason containing 'symbol_lock')."""
        ok, reason = await self.validator._check_symbol_lock("BTC/USDT", "1h")
        assert ok is False
        assert reason is not None
        assert "symbol_lock" in reason
        assert "BTC/USDT" in reason

    @pytest.mark.asyncio
    async def test_symbol_lock_accepts_sol_usdt_1h(self):
        """SOL/USDT with 1h must return (True, None)."""
        ok, reason = await self.validator._check_symbol_lock("SOL/USDT", "1h")
        assert ok is True
        assert reason is None

    # --- Timeframe lock ---

    @pytest.mark.asyncio
    async def test_timeframe_lock_rejects_non_1h(self):
        """Non-1h timeframe must return (False, reason containing 'timeframe_lock')."""
        ok, reason = await self.validator._check_symbol_lock("SOL/USDT", "4h")
        assert ok is False
        assert reason is not None
        assert "timeframe_lock" in reason
        assert "4h" in reason

    @pytest.mark.asyncio
    async def test_both_symbol_and_timeframe_wrong_reason_contains_both(self):
        """Wrong symbol AND wrong timeframe: both offences appear in failure reason."""
        ok, reason = await self.validator._check_symbol_lock("ETH/USDT", "15m")
        assert ok is False
        assert reason is not None
        assert "symbol_lock" in reason
        assert "timeframe_lock" in reason

    # --- _compute_data_hash determinism ---

    def test_compute_data_hash_determinism_same_inputs_same_hash(self):
        """Same (first_ts, last_ts, candle_count) must always produce identical hash."""
        h1 = self.validator._compute_data_hash(1_000_000, 9_999_999, 9600)
        h2 = self.validator._compute_data_hash(1_000_000, 9_999_999, 9600)
        assert h1 == h2

    def test_compute_data_hash_different_inputs_produce_different_hash(self):
        """Changing any single input must change the resulting hash."""
        base = self.validator._compute_data_hash(1_000_000, 9_999_999, 9600)
        diff_first = self.validator._compute_data_hash(1_000_001, 9_999_999, 9600)
        diff_last = self.validator._compute_data_hash(1_000_000, 9_999_998, 9600)
        diff_count = self.validator._compute_data_hash(1_000_000, 9_999_999, 9601)
        assert base != diff_first
        assert base != diff_last
        assert base != diff_count

    def test_compute_data_hash_returns_64_char_hex_string(self):
        """Digest must be exactly 64 lowercase hex characters (SHA-256)."""
        h = self.validator._compute_data_hash(0, 0, 0)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_compute_data_hash_matches_manual_sha256(self):
        """Hash must equal a manually computed SHA-256 of the canonical payload."""
        first_ts, last_ts, count = 1_600_000_000_000, 1_634_400_000_000, 9600
        expected = hashlib.sha256(f"{first_ts}:{last_ts}:{count}".encode("utf-8")).hexdigest()
        assert self.validator._compute_data_hash(first_ts, last_ts, count) == expected

    # --- run() with mocked DB session ---

    def _build_mock_session(self, scalar_return: int = 0) -> AsyncMock:
        """Build an AsyncMock session whose execute() returns a scalar of scalar_return."""
        session = AsyncMock()
        scalar_result = MagicMock()
        scalar_result.scalar_one.return_value = scalar_return
        session.execute = AsyncMock(return_value=scalar_result)
        return session

    def _build_coverage_report(
        self,
        *,
        total_candles: int = 9600,
        coverage_pct: float = 97.0,
        gap_count: int = 10,
        first_ts: int = 1_600_000_000_000,
        last_ts: int = 1_634_400_000_000,
        days_covered: float = 400.0,
    ) -> SimpleNamespace:
        return SimpleNamespace(
            total_candles=total_candles,
            coverage_pct=coverage_pct,
            gap_count=gap_count,
            first_ts=first_ts,
            last_ts=last_ts,
            days_covered=days_covered,
        )

    @pytest.mark.asyncio
    async def test_run_populates_all_required_checks_dict_keys(self):
        """run() must populate all 5 expected check keys regardless of outcome."""
        session = self._build_mock_session()
        cov = self._build_coverage_report()

        with patch(
            "app.services.history_data_manager.HistoryDataManager.check_coverage",
            new_callable=AsyncMock,
            return_value=cov,
        ):
            result = await self.validator.run(
                session, exchange="binance", symbol="SOL/USDT", timeframe="1h"
            )

        expected_keys = {
            "symbol_lock",
            "coverage",
            "gap_count",
            "no_duplicates",
            "timestamp_alignment",
        }
        assert expected_keys.issubset(result.checks.keys())

    @pytest.mark.asyncio
    async def test_run_failure_reasons_populated_on_wrong_symbol(self):
        """run() must add a failure_reason entry when symbol_lock check fails."""
        session = self._build_mock_session()
        cov = self._build_coverage_report()

        with patch(
            "app.services.history_data_manager.HistoryDataManager.check_coverage",
            new_callable=AsyncMock,
            return_value=cov,
        ):
            result = await self.validator.run(
                session, exchange="binance", symbol="BTC/USDT", timeframe="1h"
            )

        assert result.passed is False
        assert len(result.failure_reasons) >= 1
        assert any("symbol_lock" in r for r in result.failure_reasons)

    @pytest.mark.asyncio
    async def test_run_failure_reasons_populated_on_excessive_gap_count(self):
        """run() must report gap_count failure when gap_count > MAX_GAP_COUNT (48)."""
        session = self._build_mock_session()
        cov = self._build_coverage_report(gap_count=100)  # exceeds 48

        with patch(
            "app.services.history_data_manager.HistoryDataManager.check_coverage",
            new_callable=AsyncMock,
            return_value=cov,
        ):
            result = await self.validator.run(
                session, exchange="binance", symbol="SOL/USDT", timeframe="1h"
            )

        assert result.passed is False
        assert any("gap_count" in r for r in result.failure_reasons)

    @pytest.mark.asyncio
    async def test_run_passed_true_when_all_checks_succeed(self):
        """run() must return passed=True when all checks produce no failures."""
        session = self._build_mock_session(scalar_return=0)
        cov = self._build_coverage_report()

        with patch(
            "app.services.history_data_manager.HistoryDataManager.check_coverage",
            new_callable=AsyncMock,
            return_value=cov,
        ):
            result = await self.validator.run(
                session, exchange="binance", symbol="SOL/USDT", timeframe="1h"
            )

        assert result.passed is True
        assert result.failure_reasons == []

    @pytest.mark.asyncio
    async def test_run_data_hash_always_populated_even_on_failure(self):
        """data_hash must be a 64-char hex string even when the run fails."""
        session = self._build_mock_session(scalar_return=0)
        cov = self._build_coverage_report()

        with patch(
            "app.services.history_data_manager.HistoryDataManager.check_coverage",
            new_callable=AsyncMock,
            return_value=cov,
        ):
            result = await self.validator.run(
                session,
                exchange="binance",
                symbol="BTC/USDT",  # wrong symbol forces failure
                timeframe="1h",
            )

        assert result.passed is False
        assert len(result.data_hash) == 64
        assert all(c in "0123456789abcdef" for c in result.data_hash)


# ---------------------------------------------------------------------------
# Class 2: TestPPFGovernanceEngine
# ---------------------------------------------------------------------------


class TestPPFGovernanceEngine:
    """Unit tests for PPFGovernanceEngine state machine and FC-0x rules."""

    def setup_method(self):
        self.engine = PPFGovernanceEngine()

    # --- Initial state ---

    def test_initial_state_is_not_initialized(self):
        """A freshly constructed engine must start in NOT_INITIALIZED."""
        assert self.engine.state == PPFGovernanceState.NOT_INITIALIZED

    # --- Valid transition chain ---

    def test_full_valid_transition_chain_succeeds(self):
        """All 6 pipeline transitions must succeed when executed in order."""
        for state in _FULL_CHAIN:
            result = self.engine.transition(state, reason="unit-test")
            assert result is True
        assert self.engine.state == PPFGovernanceState.VAL_PDC_002_ISSUED

    def test_transition_not_initialized_to_data_ready(self):
        assert self.engine.transition(PPFGovernanceState.DATA_READY) is True
        assert self.engine.state == PPFGovernanceState.DATA_READY

    def test_transition_data_ready_to_phase_a_running(self):
        self.engine.transition(PPFGovernanceState.DATA_READY)
        assert self.engine.transition(PPFGovernanceState.PHASE_A_RUNNING) is True

    def test_transition_phase_a_running_to_baseline_frozen(self):
        self.engine.transition(PPFGovernanceState.DATA_READY)
        self.engine.transition(PPFGovernanceState.PHASE_A_RUNNING)
        assert self.engine.transition(PPFGovernanceState.BASELINE_FROZEN) is True

    def test_transition_baseline_frozen_to_phase_b_collecting(self):
        self.engine.transition(PPFGovernanceState.DATA_READY)
        self.engine.transition(PPFGovernanceState.PHASE_A_RUNNING)
        self.engine.transition(PPFGovernanceState.BASELINE_FROZEN)
        assert self.engine.transition(PPFGovernanceState.PHASE_B_COLLECTING) is True

    def test_transition_phase_b_collecting_to_validation_ready(self):
        self.engine.transition(PPFGovernanceState.DATA_READY)
        self.engine.transition(PPFGovernanceState.PHASE_A_RUNNING)
        self.engine.transition(PPFGovernanceState.BASELINE_FROZEN)
        self.engine.transition(PPFGovernanceState.PHASE_B_COLLECTING)
        assert self.engine.transition(PPFGovernanceState.VALIDATION_READY) is True

    def test_transition_validation_ready_to_val_pdc_002_issued(self):
        self.engine.transition(PPFGovernanceState.DATA_READY)
        self.engine.transition(PPFGovernanceState.PHASE_A_RUNNING)
        self.engine.transition(PPFGovernanceState.BASELINE_FROZEN)
        self.engine.transition(PPFGovernanceState.PHASE_B_COLLECTING)
        self.engine.transition(PPFGovernanceState.VALIDATION_READY)
        assert self.engine.transition(PPFGovernanceState.VAL_PDC_002_ISSUED) is True

    # --- Invalid transitions ---

    def test_invalid_transition_raises_value_error(self):
        """Skipping states (NOT_INITIALIZED → BASELINE_FROZEN) must raise ValueError."""
        with pytest.raises(ValueError, match="INVALID_TRANSITION"):
            self.engine.transition(PPFGovernanceState.BASELINE_FROZEN)

    def test_invalid_transition_not_initialized_to_phase_a_running(self):
        with pytest.raises(ValueError):
            self.engine.transition(PPFGovernanceState.PHASE_A_RUNNING)

    def test_invalid_transition_data_ready_to_val_pdc_002_issued(self):
        self.engine.transition(PPFGovernanceState.DATA_READY)
        with pytest.raises(ValueError):
            self.engine.transition(PPFGovernanceState.VAL_PDC_002_ISSUED)

    # --- Terminal state ---

    def test_terminal_state_has_empty_allowed_transitions_list(self):
        """ALLOWED_TRANSITIONS[VAL_PDC_002_ISSUED] must be an empty list."""
        assert ALLOWED_TRANSITIONS[PPFGovernanceState.VAL_PDC_002_ISSUED] == []

    def test_terminal_state_transition_raises_terminal_state_error(self):
        """Attempting any transition from terminal state must raise ValueError with TERMINAL_STATE."""
        _advance_to_terminal(self.engine)
        with pytest.raises(ValueError, match="TERMINAL_STATE"):
            self.engine.transition(PPFGovernanceState.DATA_READY)

    # --- can_transition ---

    def test_can_transition_returns_true_none_for_valid_target(self):
        """can_transition to a permitted next state must return (True, None)."""
        ok, reason = self.engine.can_transition(PPFGovernanceState.DATA_READY)
        assert ok is True
        assert reason is None

    def test_can_transition_returns_false_with_reason_for_invalid_target(self):
        """can_transition to an invalid target must return (False, non-empty str)."""
        ok, reason = self.engine.can_transition(PPFGovernanceState.BASELINE_FROZEN)
        assert ok is False
        assert isinstance(reason, str)
        assert len(reason) > 0

    def test_can_transition_from_terminal_state_returns_false(self):
        """can_transition from terminal state must return (False, TERMINAL_STATE reason)."""
        _advance_to_terminal(self.engine)
        ok, reason = self.engine.can_transition(PPFGovernanceState.DATA_READY)
        assert ok is False
        assert reason is not None
        assert "TERMINAL_STATE" in reason

    # --- Transition log ---

    def test_transition_log_records_one_entry_per_transition(self):
        """Each successful transition must append exactly one entry to the log."""
        self.engine.transition(PPFGovernanceState.DATA_READY, reason="step1")
        self.engine.transition(PPFGovernanceState.PHASE_A_RUNNING, reason="step2")
        log = self.engine.get_transition_log()
        assert len(log) == 2

    def test_transition_log_entry_has_all_required_keys(self):
        """Each log entry must contain timestamp, from_state, to_state, reason."""
        self.engine.transition(PPFGovernanceState.DATA_READY, reason="check")
        entry = self.engine.get_transition_log()[0]
        for key in ("timestamp", "from_state", "to_state", "reason"):
            assert key in entry

    def test_transition_log_values_are_correct(self):
        """Log entry values must match the actual transition that was executed."""
        self.engine.transition(PPFGovernanceState.DATA_READY, reason="my-reason")
        entry = self.engine.get_transition_log()[0]
        assert entry["from_state"] == "NOT_INITIALIZED"
        assert entry["to_state"] == "DATA_READY"
        assert entry["reason"] == "my-reason"

    def test_transition_log_returns_shallow_copy(self):
        """Mutating the returned log list must not affect the engine's internal state."""
        self.engine.transition(PPFGovernanceState.DATA_READY)
        log = self.engine.get_transition_log()
        log.clear()
        # Engine still has the one entry
        assert len(self.engine.get_transition_log()) == 1

    # --- FC-01 ---

    def test_fc01_preflight_false_returns_soft_block(self):
        """FC-01: preflight_passed=False must return SOFT_BLOCK."""
        level, msg = self.engine.check_phase_a_ready(False)
        assert level == PPFBlockLevel.SOFT_BLOCK
        assert "FC-01" in msg

    def test_fc01_preflight_true_returns_clear(self):
        """FC-01: preflight_passed=True must return CLEAR."""
        level, msg = self.engine.check_phase_a_ready(True)
        assert level == PPFBlockLevel.CLEAR
        assert "FC-01" in msg

    # --- FC-02 ---

    def test_fc02_unresolved_rate_006_returns_soft_block(self):
        """FC-02: unresolved_rate=0.06 exceeds 5% ceiling → SOFT_BLOCK."""
        level, msg = self.engine.check_baseline_freeze_ready(0.06)
        assert level == PPFBlockLevel.SOFT_BLOCK
        assert "FC-02" in msg

    def test_fc02_unresolved_rate_003_returns_clear(self):
        """FC-02: unresolved_rate=0.03 is within limit → CLEAR."""
        level, msg = self.engine.check_baseline_freeze_ready(0.03)
        assert level == PPFBlockLevel.CLEAR
        assert "FC-02" in msg

    def test_fc02_unresolved_rate_exactly_005_returns_clear(self):
        """FC-02: unresolved_rate=0.05 is at the boundary (inclusive) → CLEAR."""
        level, _ = self.engine.check_baseline_freeze_ready(0.05)
        assert level == PPFBlockLevel.CLEAR

    def test_fc02_unresolved_rate_zero_returns_clear(self):
        """FC-02: unresolved_rate=0.0 (fully resolved) → CLEAR."""
        level, _ = self.engine.check_baseline_freeze_ready(0.0)
        assert level == PPFBlockLevel.CLEAR

    def test_fc02_unresolved_rate_above_1_returns_soft_block(self):
        """FC-02: unresolved_rate > 1.0 is invalid input → SOFT_BLOCK."""
        level, msg = self.engine.check_baseline_freeze_ready(1.5)
        assert level == PPFBlockLevel.SOFT_BLOCK

    # --- FC-03 ---

    def test_fc03_baseline_not_frozen_returns_soft_block(self):
        """FC-03: baseline_frozen=False → SOFT_BLOCK."""
        level, msg = self.engine.check_phase_b_ready(False)
        assert level == PPFBlockLevel.SOFT_BLOCK
        assert "FC-03" in msg

    def test_fc03_baseline_frozen_but_wrong_state_returns_soft_block(self):
        """FC-03: baseline_frozen=True but engine in NOT_INITIALIZED → SOFT_BLOCK."""
        level, msg = self.engine.check_phase_b_ready(True)
        assert level == PPFBlockLevel.SOFT_BLOCK

    def test_fc03_baseline_frozen_with_correct_state_returns_clear(self):
        """FC-03: baseline_frozen=True and state is BASELINE_FROZEN → CLEAR."""
        self.engine.transition(PPFGovernanceState.DATA_READY)
        self.engine.transition(PPFGovernanceState.PHASE_A_RUNNING)
        self.engine.transition(PPFGovernanceState.BASELINE_FROZEN)

        level, msg = self.engine.check_phase_b_ready(True)
        assert level == PPFBlockLevel.CLEAR
        assert "FC-03" in msg

    # --- FC-04 + FC-05 ---

    def test_fc04_fc05_both_fail_returns_evidence_insufficient(self):
        """FC-04+FC-05: bars=100 and events=5 → EVIDENCE_INSUFFICIENT."""
        level, msg = self.engine.check_validation_ready(100, 5)
        assert level == PPFBlockLevel.EVIDENCE_INSUFFICIENT

    def test_fc04_only_bars_insufficient_returns_evidence_insufficient(self):
        """FC-04: bars=100 < 336, events=15 >= 10 → EVIDENCE_INSUFFICIENT with FC-04 in message."""
        level, msg = self.engine.check_validation_ready(100, 15)
        assert level == PPFBlockLevel.EVIDENCE_INSUFFICIENT
        assert "FC-04" in msg

    def test_fc05_only_events_insufficient_returns_evidence_insufficient(self):
        """FC-05: bars=400 >= 336, events=5 < 10 → EVIDENCE_INSUFFICIENT with FC-05 in message."""
        level, msg = self.engine.check_validation_ready(400, 5)
        assert level == PPFBlockLevel.EVIDENCE_INSUFFICIENT
        assert "FC-05" in msg

    def test_fc04_fc05_both_at_exact_minimum_returns_clear(self):
        """FC-04+FC-05: bars=336 (exact min), events=10 (exact min) → CLEAR."""
        level, _ = self.engine.check_validation_ready(336, 10)
        assert level == PPFBlockLevel.CLEAR

    def test_fc04_fc05_well_above_minimum_returns_clear(self):
        """FC-04+FC-05: bars=500, events=20 → CLEAR."""
        level, _ = self.engine.check_validation_ready(500, 20)
        assert level == PPFBlockLevel.CLEAR

    # --- FC-07 ---

    def test_fc07_check_live_entry_always_hard_block(self):
        """FC-07: check_live_entry() must always return HARD_BLOCK."""
        level, msg = self.engine.check_live_entry()
        assert level == PPFBlockLevel.HARD_BLOCK
        assert len(msg) > 0

    def test_fc07_hard_block_persists_at_terminal_state(self):
        """FC-07: HARD_BLOCK must remain even when state is VAL_PDC_002_ISSUED."""
        _advance_to_terminal(self.engine)
        level, _ = self.engine.check_live_entry()
        assert level == PPFBlockLevel.HARD_BLOCK

    # --- FC-08 ---

    def test_fc08_wrong_state_green_tier_returns_hard_block(self):
        """FC-08: state=NOT_INITIALIZED (wrong) + tier=GREEN → HARD_BLOCK."""
        level, msg = self.engine.check_paper_entry(PPFGovernanceTier.GREEN)
        assert level == PPFBlockLevel.HARD_BLOCK
        assert "FC-08" in msg

    def test_fc08_correct_state_yellow_tier_returns_hard_block(self):
        """FC-08: state=VAL_PDC_002_ISSUED + tier=YELLOW → HARD_BLOCK."""
        _advance_to_terminal(self.engine)
        level, msg = self.engine.check_paper_entry(PPFGovernanceTier.YELLOW)
        assert level == PPFBlockLevel.HARD_BLOCK
        assert "FC-08" in msg

    def test_fc08_correct_state_green_tier_returns_clear(self):
        """FC-08: state=VAL_PDC_002_ISSUED + tier=GREEN → CLEAR."""
        _advance_to_terminal(self.engine)
        level, msg = self.engine.check_paper_entry(PPFGovernanceTier.GREEN)
        assert level == PPFBlockLevel.CLEAR
        assert "FC-08" in msg

    def test_fc08_correct_state_red_tier_returns_hard_block(self):
        """FC-08: state=VAL_PDC_002_ISSUED + tier=RED → HARD_BLOCK."""
        _advance_to_terminal(self.engine)
        level, _ = self.engine.check_paper_entry(PPFGovernanceTier.RED)
        assert level == PPFBlockLevel.HARD_BLOCK

    # --- compute_tier ---

    def test_compute_tier_below_5_events_returns_red(self):
        """compute_tier: events=4, all_checks_passed=True → RED."""
        tier = self.engine.compute_tier(4, True)
        assert tier == PPFGovernanceTier.RED

    def test_compute_tier_7_events_all_pass_returns_yellow(self):
        """compute_tier: events=7, all_checks_passed=True → YELLOW."""
        tier = self.engine.compute_tier(7, True)
        assert tier == PPFGovernanceTier.YELLOW

    def test_compute_tier_10_events_all_pass_returns_green(self):
        """compute_tier: events=10, all_checks_passed=True → GREEN."""
        tier = self.engine.compute_tier(10, True)
        assert tier == PPFGovernanceTier.GREEN

    def test_compute_tier_10_events_not_all_pass_returns_red(self):
        """compute_tier: events=10, all_checks_passed=False → RED (critical failure overrides)."""
        tier = self.engine.compute_tier(10, False)
        assert tier == PPFGovernanceTier.RED

    # --- get_status_summary ---

    def test_get_status_summary_returns_expected_keys(self):
        """get_status_summary() must return all 7 documented keys."""
        summary = self.engine.get_status_summary()
        required_keys = {
            "state",
            "transition_count",
            "terminal",
            "allowed_next",
            "live_entry_block",
            "live_entry_block_msg",
            "paper_entry_note",
        }
        assert required_keys.issubset(summary.keys())

    def test_get_status_summary_state_matches_engine_state(self):
        """get_status_summary().state must equal engine.state.value."""
        assert self.engine.get_status_summary()["state"] == self.engine.state.value

    def test_get_status_summary_terminal_false_initially(self):
        assert self.engine.get_status_summary()["terminal"] is False

    def test_get_status_summary_terminal_true_at_terminal_state(self):
        _advance_to_terminal(self.engine)
        assert self.engine.get_status_summary()["terminal"] is True

    def test_get_status_summary_live_entry_block_always_hard_block(self):
        """live_entry_block in summary must always be HARD_BLOCK value."""
        assert (
            self.engine.get_status_summary()["live_entry_block"] == PPFBlockLevel.HARD_BLOCK.value
        )

    def test_get_status_summary_transition_count_increments(self):
        """transition_count in summary must grow by 1 for each transition."""
        self.engine.transition(PPFGovernanceState.DATA_READY)
        assert self.engine.get_status_summary()["transition_count"] == 1
        self.engine.transition(PPFGovernanceState.PHASE_A_RUNNING)
        assert self.engine.get_status_summary()["transition_count"] == 2


# ---------------------------------------------------------------------------
# Class 3: TestValPDC002Judge
# ---------------------------------------------------------------------------


class TestValPDC002Judge:
    """Unit tests for ValPDC002Judge verdict logic."""

    def setup_method(self):
        self.judge = ValPDC002Judge()

    # --- GO verdict ---

    def test_go_verdict_when_all_7_criteria_pass_and_green_tier(self):
        """All criteria pass + events=10 (GREEN) → GO verdict."""
        report = _make_comparison_report(metrics=_full_passing_metrics())
        result = self.judge.judge(
            comparison_report=report,
            seal_valid=True,
            governance_has_hard_block=False,
            novelty_events=10,
            bars_collected=400,
        )
        assert result.verdict == ValPDC002Verdict.GO
        assert result.tier == "GREEN"
        assert result.live_authorized is False

    def test_go_verdict_report_has_exactly_7_criteria(self):
        """A GO-path report must contain exactly 7 criteria (C1-C7)."""
        report = _make_comparison_report(metrics=_full_passing_metrics())
        result = self.judge.judge(
            comparison_report=report,
            seal_valid=True,
            governance_has_hard_block=False,
            novelty_events=15,
            bars_collected=500,
        )
        assert len(result.criteria) == 7

    # --- BLOCK from hard block ---

    def test_block_verdict_when_governance_has_hard_block(self):
        """governance_has_hard_block=True → BLOCK (C7 fails)."""
        report = _make_comparison_report(metrics=_full_passing_metrics())
        result = self.judge.judge(
            comparison_report=report,
            seal_valid=True,
            governance_has_hard_block=True,
            novelty_events=15,
            bars_collected=500,
        )
        assert result.verdict == ValPDC002Verdict.BLOCK
        assert any("C7" in r for r in result.failure_reasons)

    # --- BLOCK from insufficient bars ---

    def test_block_verdict_when_bars_below_336(self):
        """bars_collected=100 < 336 → BLOCK (C1 fails)."""
        report = _make_comparison_report(metrics=_full_passing_metrics())
        result = self.judge.judge(
            comparison_report=report,
            seal_valid=True,
            governance_has_hard_block=False,
            novelty_events=15,
            bars_collected=100,
        )
        assert result.verdict == ValPDC002Verdict.BLOCK
        assert any("C1" in r for r in result.failure_reasons)

    # --- BLOCK from novelty events below RED threshold ---

    def test_block_verdict_when_novelty_events_below_5_red_tier(self):
        """novelty_events=3 → RED tier → BLOCK."""
        report = _make_comparison_report(metrics=_full_passing_metrics())
        result = self.judge.judge(
            comparison_report=report,
            seal_valid=True,
            governance_has_hard_block=False,
            novelty_events=3,
            bars_collected=400,
        )
        assert result.verdict == ValPDC002Verdict.BLOCK
        assert result.tier == "RED"

    # --- HOLD from YELLOW tier ---

    def test_block_verdict_when_yellow_tier_5_to_9_events(self):
        """novelty_events=7 → YELLOW tier but C5 (>=10) fails → BLOCK.

        HOLD via YELLOW is impossible because C5 requires >=10 events
        while YELLOW is 5-9 events — a structural contradiction. The
        correct verdict for 7 events is BLOCK (C5 failure).
        """
        report = _make_comparison_report(metrics=_full_passing_metrics())
        result = self.judge.judge(
            comparison_report=report,
            seal_valid=True,
            governance_has_hard_block=False,
            novelty_events=7,
            bars_collected=400,
        )
        assert result.verdict == ValPDC002Verdict.BLOCK
        assert result.tier == "YELLOW"

    # --- HOLD from seal failure ---

    def test_hold_verdict_when_seal_invalid_c1_c5_c7_all_pass(self):
        """seal_valid=False + events=10 + C1-C5+C7 pass → HOLD (C6 seal re-verify needed)."""
        report = _make_comparison_report(metrics=_full_passing_metrics())
        result = self.judge.judge(
            comparison_report=report,
            seal_valid=False,
            governance_has_hard_block=False,
            novelty_events=10,
            bars_collected=400,
        )
        assert result.verdict == ValPDC002Verdict.HOLD
        assert any("C6" in r for r in result.failure_reasons)

    # --- check_live_authorized always False ---

    def test_check_live_authorized_always_returns_false(self):
        """check_live_authorized() must return (False, non-empty reason) always."""
        authorized, reason = self.judge.check_live_authorized()
        assert authorized is False
        assert isinstance(reason, str)
        assert len(reason) > 0

    def test_check_live_authorized_idempotent_across_multiple_calls(self):
        """check_live_authorized() must return False on repeated calls."""
        for _ in range(5):
            authorized, _ = self.judge.check_live_authorized()
            assert authorized is False

    # --- Criteria list has exactly 7 items ---

    def test_criteria_list_has_exactly_7_items_on_block_path(self):
        """judge() must always produce exactly 7 criteria even on a BLOCK path."""
        report = _make_comparison_report()  # no metrics, will fail C3/C4
        result = self.judge.judge(
            comparison_report=report,
            seal_valid=False,
            governance_has_hard_block=False,
            novelty_events=3,
            bars_collected=100,
        )
        assert len(result.criteria) == 7

    # --- failure_reasons populated correctly ---

    def test_failure_reasons_populated_for_c1_c5_c6_when_all_fail(self):
        """failure_reasons must include C1, C5, C6 entries when those criteria fail."""
        report = _make_comparison_report(metrics=[])  # no metrics → C3/C4 fail too
        result = self.judge.judge(
            comparison_report=report,
            seal_valid=False,
            governance_has_hard_block=False,
            novelty_events=3,
            bars_collected=50,
        )
        reason_text = " ".join(result.failure_reasons)
        assert "C1" in reason_text
        assert "C5" in reason_text
        assert "C6" in reason_text

    def test_failure_reasons_empty_on_go_path(self):
        """failure_reasons must be empty when all criteria pass (GO verdict)."""
        report = _make_comparison_report(metrics=_full_passing_metrics())
        result = self.judge.judge(
            comparison_report=report,
            seal_valid=True,
            governance_has_hard_block=False,
            novelty_events=10,
            bars_collected=400,
        )
        assert result.verdict == ValPDC002Verdict.GO
        assert result.failure_reasons == []

    # --- live_authorized always False in report ---

    def test_live_authorized_always_false_on_go_path(self):
        """live_authorized in ValPDC002Report must be False even on GO verdict."""
        report = _make_comparison_report(metrics=_full_passing_metrics())
        result = self.judge.judge(
            comparison_report=report,
            seal_valid=True,
            governance_has_hard_block=False,
            novelty_events=10,
            bars_collected=400,
        )
        assert result.verdict == ValPDC002Verdict.GO
        assert result.live_authorized is False

    def test_live_authorized_always_false_on_block_path(self):
        """live_authorized must be False even on BLOCK verdict."""
        result = self.judge.judge(
            comparison_report=_make_comparison_report(),
            seal_valid=False,
            governance_has_hard_block=True,
            novelty_events=0,
            bars_collected=0,
        )
        assert result.live_authorized is False

    # --- issued_at populated ---

    def test_issued_at_is_parseable_iso_datetime_string(self):
        """issued_at must be a non-empty, parseable ISO-8601 UTC timestamp."""
        report = _make_comparison_report()
        result = self.judge.judge(
            comparison_report=report,
            seal_valid=False,
            governance_has_hard_block=False,
            novelty_events=3,
            bars_collected=100,
        )
        assert isinstance(result.issued_at, str)
        assert len(result.issued_at) > 0
        # Must not raise
        datetime.fromisoformat(result.issued_at)

    # --- criteria names ---

    def test_criteria_names_include_all_7_canonical_identifiers(self):
        """All 7 canonical criterion names (C1-C7) must appear in the report."""
        report = _make_comparison_report(metrics=_full_passing_metrics())
        result = self.judge.judge(
            comparison_report=report,
            seal_valid=True,
            governance_has_hard_block=False,
            novelty_events=10,
            bars_collected=400,
        )
        names = {c.name for c in result.criteria}
        expected = {
            "C1_MIN_BARS",
            "C2_DENY_RATE_DELTA",
            "C3_FPR_DELTA",
            "C4_STATE_JS_DIVERGENCE",
            "C5_MIN_NOVELTY_EVENTS",
            "C6_SEAL_INTEGRITY",
            "C7_NO_HARD_BLOCK",
        }
        assert expected == names


# ---------------------------------------------------------------------------
# Class 4: TestPPFGovernanceTierComputation
# ---------------------------------------------------------------------------


class TestPPFGovernanceTierComputation:
    """Parametrized boundary tests for PPFGovernanceEngine.compute_tier()."""

    def setup_method(self):
        self.engine = PPFGovernanceEngine()

    @pytest.mark.parametrize(
        "novelty_events, all_checks_passed, expected_tier",
        [
            # RED: 0 events
            (0, True, PPFGovernanceTier.RED),
            # RED: 4 events (one below YELLOW threshold of 5)
            (4, True, PPFGovernanceTier.RED),
            # YELLOW: exactly 5 events, all checks pass
            (5, True, PPFGovernanceTier.YELLOW),
            # YELLOW: 7 events, all checks pass
            (7, True, PPFGovernanceTier.YELLOW),
            # YELLOW: 9 events (one below GREEN), all checks pass
            (9, True, PPFGovernanceTier.YELLOW),
            # GREEN: exactly 10 events, all checks pass
            (10, True, PPFGovernanceTier.GREEN),
            # GREEN: more than 10 events, all checks pass
            (20, True, PPFGovernanceTier.GREEN),
        ],
    )
    def test_tier_boundaries(
        self,
        novelty_events: int,
        all_checks_passed: bool,
        expected_tier: PPFGovernanceTier,
    ):
        """compute_tier() must return the correct tier at each event-count boundary."""
        tier = self.engine.compute_tier(novelty_events, all_checks_passed)
        assert tier == expected_tier, (
            f"Expected {expected_tier.value} for events={novelty_events}, "
            f"all_checks_passed={all_checks_passed}; got {tier.value}"
        )

    def test_red_override_10_events_checks_not_all_passed(self):
        """10 events with all_checks_passed=False → RED (critical failure wins over GREEN)."""
        tier = self.engine.compute_tier(10, False)
        assert tier == PPFGovernanceTier.RED

    def test_red_override_20_events_checks_not_all_passed(self):
        """20 events with all_checks_passed=False → RED."""
        tier = self.engine.compute_tier(20, False)
        assert tier == PPFGovernanceTier.RED

    def test_red_override_5_events_at_yellow_boundary_checks_not_all_passed(self):
        """5 events (YELLOW boundary) with all_checks_passed=False → RED."""
        tier = self.engine.compute_tier(5, False)
        assert tier == PPFGovernanceTier.RED

    def test_tier_green_requires_exactly_min_novelty_events(self):
        """GREEN threshold matches MIN_NOVELTY_EVENTS (10); one below gives YELLOW."""
        assert self.engine.compute_tier(MIN_NOVELTY_EVENTS, True) == PPFGovernanceTier.GREEN
        assert self.engine.compute_tier(MIN_NOVELTY_EVENTS - 1, True) == PPFGovernanceTier.YELLOW

    def test_compute_tier_always_returns_enum_instance(self):
        """compute_tier() must always return a PPFGovernanceTier enum member."""
        for events in range(0, 15):
            for passed in (True, False):
                tier = self.engine.compute_tier(events, passed)
                assert isinstance(tier, PPFGovernanceTier)
