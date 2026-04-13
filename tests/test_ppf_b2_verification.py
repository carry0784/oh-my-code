"""PPF B2 Verification Tests.

Authority: PPF-CODE-IMPLEMENTATION-001-CORRECTION-R1

B2 Rule: D4/D5 failure -> R1 REJECT -> state resets to D1_IDLE.
No D4 retention, no D5 retention. reached_state preserves audit trail.

Test coverage:
    1. Current-candle D5 rejection: risk_filter=False -> state=D1_IDLE, reached_state=D5_ARMED
    2. Current-candle D4 rejection: PATH_QUALITY_FAIL -> state=D1_IDLE, reached_state=D4_QUALIFIED
    3. Current-candle D4 rejection: RR_FAIL -> state=D1_IDLE, reached_state=D4_QUALIFIED
    4. Next-candle D1 reset: after R1 outcome, next evaluate() starts from D1
    5. D6 success: confirm allow_entry=True only at D6, reached_state is None
    6. Logging: reached_state appears in log entry for R1 rejections
"""

from __future__ import annotations

import pytest

from strategies.ppf.constants import (
    MarketProfile,
    PPFState,
    RejectionCode,
    TransitionOutcome,
)
from strategies.ppf.decision import DecisionResult, PPFStateMachine
from strategies.ppf.interpretation import InterpretationScores
from strategies.ppf.logging_schema import PPFLogEntry, build_log_entry
from strategies.ppf.observation import ObservationFields
from strategies.ppf.parameters import PPFParameters


# ---------------------------------------------------------------------------
# Fixtures: parameters and observation/scores that reach D4/D5/D6
# ---------------------------------------------------------------------------

def _default_params() -> PPFParameters:
    """Default params for testing. All thresholds at minimum to allow progression."""
    return PPFParameters(
        market_profile=MarketProfile.M1_CRYPTO_FUTURES,
        similarity_min=0.5,
        projection_bias_min=0.1,
        path_quality_min=0.1,
        rr_min=1.5,
    )


def _obs_reaching_d4() -> ObservationFields:
    """Observation fields that pass D1->D2->D3->D4 transitions.

    O1=0.8 >= similarity_min(0.5) -> D2
    O2=+1 != 0 -> D3
    O6=0.5, O7=0.5 -> positive alignment for I2/I3
    """
    return ObservationFields(
        pattern_similarity_score=0.8,
        projection_direction=1,
        projection_consensus_ratio=0.9,
        expected_adverse_excursion_before_target=0.5,
        expected_favorable_excursion_to_target=2.0,
        ssl_trend_strength=0.5,
        volume_force_strength=0.5,
        recent_swing_distance_pct=1.0,
        regime_novelty_flag=False,
    )


def _scores_reaching_d4(*, path_quality: float = 0.5, rr: float = 3.0) -> InterpretationScores:
    """Scores that pass D3->D4 (3-way alignment).

    abs(I1)=0.72 >= projection_bias_min(0.1) -> pass
    I2=0.5 > 0 -> pass
    I3=0.5 > 0 -> pass
    I4/I5 configurable for D4->D5 test.
    """
    return InterpretationScores(
        projection_bias_score=0.72,
        trend_alignment_score=0.5,
        volume_confirmation_score=0.5,
        path_quality_score=path_quality,
        structure_rr_score=rr,
    )


# ---------------------------------------------------------------------------
# Test 1: D5 RISK_FILTER_FAIL -> R1 -> D1_IDLE (B2 core test)
# ---------------------------------------------------------------------------

class TestB2D5RiskFilterReject:
    """B2: D5 -> D6 failure must produce R1 -> D1_IDLE, not ARMED retention."""

    def test_risk_filter_fail_returns_d1_idle(self) -> None:
        """state=D1_IDLE when risk_filter=False at D5."""
        params = _default_params()
        sm = PPFStateMachine(params)
        obs = _obs_reaching_d4()
        scores = _scores_reaching_d4(path_quality=0.5, rr=3.0)

        result = sm.evaluate(obs=obs, scores=scores, risk_filter_pass=False)

        assert result.state == PPFState.D1_IDLE, (
            f"B2 violation: expected D1_IDLE, got {result.state}"
        )

    def test_risk_filter_fail_reached_state_is_armed(self) -> None:
        """reached_state=D5_ARMED preserves audit trail."""
        params = _default_params()
        sm = PPFStateMachine(params)
        obs = _obs_reaching_d4()
        scores = _scores_reaching_d4(path_quality=0.5, rr=3.0)

        result = sm.evaluate(obs=obs, scores=scores, risk_filter_pass=False)

        assert result.reached_state == PPFState.D5_ARMED, (
            f"Audit trail lost: expected D5_ARMED, got {result.reached_state}"
        )

    def test_risk_filter_fail_rejection_outcome(self) -> None:
        """rejection=R1_REJECT and rejection_code=RISK_FILTER_FAIL."""
        params = _default_params()
        sm = PPFStateMachine(params)
        obs = _obs_reaching_d4()
        scores = _scores_reaching_d4(path_quality=0.5, rr=3.0)

        result = sm.evaluate(obs=obs, scores=scores, risk_filter_pass=False)

        assert result.rejection == TransitionOutcome.R1_REJECT
        assert result.rejection_code == RejectionCode.RISK_FILTER_FAIL

    def test_risk_filter_fail_denies_entry(self) -> None:
        """allow_entry=False on RISK_FILTER_FAIL."""
        params = _default_params()
        sm = PPFStateMachine(params)
        obs = _obs_reaching_d4()
        scores = _scores_reaching_d4(path_quality=0.5, rr=3.0)

        result = sm.evaluate(obs=obs, scores=scores, risk_filter_pass=False)

        assert result.allow_entry is False


# ---------------------------------------------------------------------------
# Test 2: D4 PATH_QUALITY_FAIL -> R1 -> D1_IDLE
# ---------------------------------------------------------------------------

class TestB2D4PathQualityReject:
    """B2: D4 -> D5 failure (path quality) must produce R1 -> D1_IDLE."""

    def test_path_quality_fail_returns_d1_idle(self) -> None:
        params = _default_params()
        sm = PPFStateMachine(params)
        obs = _obs_reaching_d4()
        # I4 = -0.1 <= path_quality_min(0.1) -> fail
        scores = _scores_reaching_d4(path_quality=-0.1, rr=3.0)

        result = sm.evaluate(obs=obs, scores=scores, risk_filter_pass=True)

        assert result.state == PPFState.D1_IDLE, (
            f"B2 violation: expected D1_IDLE, got {result.state}"
        )

    def test_path_quality_fail_reached_state_is_qualified(self) -> None:
        params = _default_params()
        sm = PPFStateMachine(params)
        obs = _obs_reaching_d4()
        scores = _scores_reaching_d4(path_quality=-0.1, rr=3.0)

        result = sm.evaluate(obs=obs, scores=scores, risk_filter_pass=True)

        assert result.reached_state == PPFState.D4_QUALIFIED

    def test_path_quality_fail_rejection_code(self) -> None:
        params = _default_params()
        sm = PPFStateMachine(params)
        obs = _obs_reaching_d4()
        scores = _scores_reaching_d4(path_quality=-0.1, rr=3.0)

        result = sm.evaluate(obs=obs, scores=scores, risk_filter_pass=True)

        assert result.rejection == TransitionOutcome.R1_REJECT
        assert result.rejection_code == RejectionCode.PATH_QUALITY_FAIL


# ---------------------------------------------------------------------------
# Test 3: D4 RR_FAIL -> R1 -> D1_IDLE
# ---------------------------------------------------------------------------

class TestB2D4RRReject:
    """B2: D4 -> D5 failure (RR too low) must produce R1 -> D1_IDLE."""

    def test_rr_fail_returns_d1_idle(self) -> None:
        params = _default_params()
        sm = PPFStateMachine(params)
        obs = _obs_reaching_d4()
        # I5 = 1.0 < rr_min(1.5) -> fail
        scores = _scores_reaching_d4(path_quality=0.5, rr=1.0)

        result = sm.evaluate(obs=obs, scores=scores, risk_filter_pass=True)

        assert result.state == PPFState.D1_IDLE, (
            f"B2 violation: expected D1_IDLE, got {result.state}"
        )

    def test_rr_fail_reached_state_is_qualified(self) -> None:
        params = _default_params()
        sm = PPFStateMachine(params)
        obs = _obs_reaching_d4()
        scores = _scores_reaching_d4(path_quality=0.5, rr=1.0)

        result = sm.evaluate(obs=obs, scores=scores, risk_filter_pass=True)

        assert result.reached_state == PPFState.D4_QUALIFIED

    def test_rr_fail_rejection_code(self) -> None:
        params = _default_params()
        sm = PPFStateMachine(params)
        obs = _obs_reaching_d4()
        scores = _scores_reaching_d4(path_quality=0.5, rr=1.0)

        result = sm.evaluate(obs=obs, scores=scores, risk_filter_pass=True)

        assert result.rejection == TransitionOutcome.R1_REJECT
        assert result.rejection_code == RejectionCode.RR_FAIL


# ---------------------------------------------------------------------------
# Test 4: Next-candle D1 reset after R1
# ---------------------------------------------------------------------------

class TestB2NextCandleReset:
    """After R1 outcome on candle N, candle N+1 starts from D1."""

    def test_next_candle_starts_d1_after_risk_filter_reject(self) -> None:
        """Candle 1: R1 (risk filter). Candle 2: low similarity -> D1_IDLE."""
        params = _default_params()
        sm = PPFStateMachine(params)
        obs_d5 = _obs_reaching_d4()
        scores_d5 = _scores_reaching_d4(path_quality=0.5, rr=3.0)

        # Candle 1: R1 rejection at D5
        result_1 = sm.evaluate(obs=obs_d5, scores=scores_d5, risk_filter_pass=False)
        assert result_1.state == PPFState.D1_IDLE
        assert result_1.rejection == TransitionOutcome.R1_REJECT

        # Candle 2: low similarity -> should stop at D1, not persist any D5 state
        obs_low = ObservationFields(
            pattern_similarity_score=0.1,  # below similarity_min(0.5)
            projection_direction=0,
            projection_consensus_ratio=0.0,
            expected_adverse_excursion_before_target=0.0,
            expected_favorable_excursion_to_target=0.0,
            ssl_trend_strength=0.0,
            volume_force_strength=0.0,
            recent_swing_distance_pct=0.0,
            regime_novelty_flag=False,
        )
        scores_low = InterpretationScores(
            projection_bias_score=0.0,
            trend_alignment_score=0.0,
            volume_confirmation_score=0.0,
            path_quality_score=0.0,
            structure_rr_score=0.0,
        )

        result_2 = sm.evaluate(obs=obs_low, scores=scores_low, risk_filter_pass=False)
        assert result_2.state == PPFState.D1_IDLE
        assert result_2.rejection is None  # no R1, just normal D1 stop
        assert result_2.reached_state is None

    def test_next_candle_can_reach_d6_after_prior_reject(self) -> None:
        """Candle 1: R1. Candle 2: full pass -> D6 (no R1 carry-over)."""
        params = _default_params()
        sm = PPFStateMachine(params)
        obs = _obs_reaching_d4()
        scores = _scores_reaching_d4(path_quality=0.5, rr=3.0)

        # Candle 1: reject
        result_1 = sm.evaluate(obs=obs, scores=scores, risk_filter_pass=False)
        assert result_1.state == PPFState.D1_IDLE

        # Candle 2: same conditions but risk_filter=True -> D6
        result_2 = sm.evaluate(obs=obs, scores=scores, risk_filter_pass=True)
        assert result_2.state == PPFState.D6_EXECUTE_READY
        assert result_2.allow_entry is True
        assert result_2.reached_state is None


# ---------------------------------------------------------------------------
# Test 5: D6 success path (positive control)
# ---------------------------------------------------------------------------

class TestB2D6SuccessPath:
    """Positive control: D6 success has allow_entry=True, no reached_state."""

    def test_d6_allow_entry(self) -> None:
        params = _default_params()
        sm = PPFStateMachine(params)
        obs = _obs_reaching_d4()
        scores = _scores_reaching_d4(path_quality=0.5, rr=3.0)

        result = sm.evaluate(obs=obs, scores=scores, risk_filter_pass=True)

        assert result.state == PPFState.D6_EXECUTE_READY
        assert result.allow_entry is True
        assert result.reached_state is None
        assert result.rejection is None
        assert result.rejection_code is None


# ---------------------------------------------------------------------------
# Test 6: Logging includes reached_state for R1 rejections
# ---------------------------------------------------------------------------

class TestB2LoggingReachedState:
    """Log entry must include reached_state for audit trail."""

    def test_log_entry_contains_reached_state_on_rejection(self) -> None:
        obs = _obs_reaching_d4()
        scores = _scores_reaching_d4(path_quality=0.5, rr=3.0)
        result = DecisionResult(
            state=PPFState.D1_IDLE,
            reached_state=PPFState.D5_ARMED,
            rejection=TransitionOutcome.R1_REJECT,
            rejection_code=RejectionCode.RISK_FILTER_FAIL,
            allow_entry=False,
        )

        log_entry = build_log_entry(
            obs=obs,
            scores=scores,
            result=result,
            asset_timeframe_tag="test:SOL/USDT:1h",
        )

        assert log_entry.reached_state == "ARMED"
        assert log_entry.ppf_state == "IDLE"
        assert log_entry.rejection_reason_code == "RISK_FILTER_FAIL"

    def test_log_entry_reached_state_none_on_success(self) -> None:
        obs = _obs_reaching_d4()
        scores = _scores_reaching_d4(path_quality=0.5, rr=3.0)
        result = DecisionResult(
            state=PPFState.D6_EXECUTE_READY,
            allow_entry=True,
        )

        log_entry = build_log_entry(
            obs=obs,
            scores=scores,
            result=result,
            asset_timeframe_tag="test:SOL/USDT:1h",
        )

        assert log_entry.reached_state is None
        assert log_entry.ppf_state == "EXECUTE_READY"
        assert log_entry.rejection_reason_code is None

    def test_log_entry_reached_state_d4_on_path_quality_fail(self) -> None:
        obs = _obs_reaching_d4()
        scores = _scores_reaching_d4(path_quality=-0.1, rr=3.0)
        result = DecisionResult(
            state=PPFState.D1_IDLE,
            reached_state=PPFState.D4_QUALIFIED,
            rejection=TransitionOutcome.R1_REJECT,
            rejection_code=RejectionCode.PATH_QUALITY_FAIL,
            allow_entry=False,
        )

        log_entry = build_log_entry(
            obs=obs,
            scores=scores,
            result=result,
            asset_timeframe_tag="test:SOL/USDT:1h",
        )

        assert log_entry.reached_state == "QUALIFIED"
        assert log_entry.ppf_state == "IDLE"


# ---------------------------------------------------------------------------
# Test 7: Novelty brake (C11) - reached_state not applicable
# ---------------------------------------------------------------------------

class TestB2NoveltyBrake:
    """C11 novelty brake is a separate path, not B2 R1. No reached_state."""

    def test_novelty_brake_no_reached_state(self) -> None:
        params = _default_params()
        sm = PPFStateMachine(params)
        obs = ObservationFields(
            pattern_similarity_score=0.8,
            projection_direction=1,
            projection_consensus_ratio=0.9,
            expected_adverse_excursion_before_target=0.5,
            expected_favorable_excursion_to_target=2.0,
            ssl_trend_strength=0.5,
            volume_force_strength=0.5,
            recent_swing_distance_pct=1.0,
            regime_novelty_flag=True,  # novelty brake active
        )
        scores = _scores_reaching_d4()

        result = sm.evaluate(obs=obs, scores=scores, risk_filter_pass=True)

        assert result.state == PPFState.D1_IDLE
        assert result.rejection == TransitionOutcome.R1_REJECT
        assert result.rejection_code == RejectionCode.NOVELTY_BRAKE
        # Novelty brake fires before reaching any state, so reached_state is None
        assert result.reached_state is None
