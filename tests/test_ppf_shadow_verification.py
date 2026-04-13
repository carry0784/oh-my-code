"""PPF Shadow Verification Test Suite.

Authority: PPF-SHADOW-VERIFICATION-001
Basis: PPF-CODE-IMPLEMENTATION-001 + CORRECTION-R1

Shadow-only verification of the full PPF implementation.
No paper/live promotion. No order submission. No engine modification.

Verification Scope:
    - Observation O1~O9 shadow outputs
    - Interpretation I1~I5 formulas and fail-closed behavior
    - Decision D1~D6 + R1 transition consistency
    - D6 = ephemeral gate-pass
    - D4/D5 failure => R1 only (B2)
    - state / reached_state / rejection / rejection_code separation
    - next-candle reset to D1 after R1
    - PPFGate allow_entry behavior
    - external orchestration wrapper only
    - O4_raw / O5_raw logging in L2
    - L1~L6 logging completeness
    - EV1~EV10 parameter load and frozen behavior
    - C1~C11 invariants under shadow conditions
    - novelty brake => D1 + allow_entry=False
    - watch_timeout_bars = 3, candidate_timeout_bars = 5
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import FrozenInstanceError
from typing import Optional
from unittest.mock import patch

import numpy as np
import pytest

from strategies.ppf.constants import (
    DEFAULT_CANDIDATE_TIMEOUT_BARS,
    DEFAULT_CORRELATION_LENGTH,
    DEFAULT_K,
    DEFAULT_NOVELTY_THRESHOLD,
    DEFAULT_PATH_QUALITY_MIN,
    DEFAULT_PROJECTION_BIAS_MIN,
    DEFAULT_PROJECTION_HORIZON,
    DEFAULT_RR_MIN,
    DEFAULT_SIMILARITY_MIN,
    DEFAULT_WATCH_TIMEOUT_BARS,
    EPSILON_PCT,
    MIN_K,
    MarketProfile,
    PPFState,
    RejectionCode,
    TransitionOutcome,
)
from strategies.ppf.constitution import (
    ConstitutionCheckResult,
    check_c10_runtime_immutability,
    check_c11_novelty_brake,
    check_c6_k_minimum,
    check_c7_engine_diff,
    run_all_checks,
)
from strategies.ppf.decision import DecisionResult, PPFStateMachine
from strategies.ppf.gate import PPFGate, PPFOrchestrationWrapper
from strategies.ppf.indicators.ssl_hybrid import compute_ssl_hybrid, get_ssl_trend_strength
from strategies.ppf.indicators.volume_osc import (
    compute_volume_oscillator,
    get_volume_force_strength,
)
from strategies.ppf.interpretation import InterpretationScores, compute_scores
from strategies.ppf.logging_schema import PPFLogEntry, build_log_entry, emit_log
from strategies.ppf.observation import ObservationFields, compute_observation
from strategies.ppf.parameters import (
    PPFParameters,
    load_parameters_from_dict,
    load_parameters_from_env,
)
from strategies.ppf.pattern_engine.matcher import (
    EnsembleResult,
    PatternMatch,
    _normalize_window,
    _pearson_similarity,
    find_similar_patterns,
)


# ===========================================================================
# Shared Fixtures
# ===========================================================================


def _params(**overrides) -> PPFParameters:
    defaults = dict(
        market_profile=MarketProfile.M1_CRYPTO_FUTURES,
        similarity_min=0.5,
        projection_bias_min=0.1,
        path_quality_min=0.1,
        rr_min=1.5,
        k=3,
        correlation_length=10,
        projection_horizon=5,
        novelty_threshold=0.4,
        watch_timeout_bars=3,
        candidate_timeout_bars=5,
    )
    defaults.update(overrides)
    return PPFParameters(**defaults)


def _obs(**overrides) -> ObservationFields:
    defaults = dict(
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
    defaults.update(overrides)
    return ObservationFields(**defaults)


def _scores(**overrides) -> InterpretationScores:
    defaults = dict(
        projection_bias_score=0.72,
        trend_alignment_score=0.5,
        volume_confirmation_score=0.5,
        path_quality_score=0.5,
        structure_rr_score=3.0,
    )
    defaults.update(overrides)
    return InterpretationScores(**defaults)


def _synthetic_prices(n: int = 200, seed: int = 42) -> tuple[np.ndarray, ...]:
    """Generate synthetic OHLCV data for integration tests."""
    rng = np.random.RandomState(seed)
    base = 100.0
    returns = rng.randn(n) * 0.02
    closes = base * np.cumprod(1 + returns)
    highs = closes * (1 + rng.uniform(0.001, 0.01, n))
    lows = closes * (1 - rng.uniform(0.001, 0.01, n))
    volumes = rng.uniform(100, 1000, n)
    return highs, lows, closes, volumes


# ===========================================================================
# SECTION 1: Observation O1~O9 Shadow Outputs
# ===========================================================================


class TestObservationFields:
    """Verify O1~O9 field computation and fail-closed behavior."""

    def test_obs_fields_frozen(self) -> None:
        """ObservationFields is frozen (no runtime mutation)."""
        obs = _obs()
        with pytest.raises(FrozenInstanceError):
            obs.pattern_similarity_score = 0.5  # type: ignore[misc]

    def test_obs_all_9_fields_present(self) -> None:
        """ObservationFields has exactly 9 fields."""
        obs = _obs()
        field_names = [
            "pattern_similarity_score",
            "projection_direction",
            "projection_consensus_ratio",
            "expected_adverse_excursion_before_target",
            "expected_favorable_excursion_to_target",
            "ssl_trend_strength",
            "volume_force_strength",
            "recent_swing_distance_pct",
            "regime_novelty_flag",
        ]
        for name in field_names:
            assert hasattr(obs, name), f"Missing field: {name}"

    def test_ssl_fail_closed_returns_zero(self) -> None:
        """O6: SSL returns 0.0 on insufficient data (blocks D4)."""
        # Insufficient data: only 2 bars
        val = get_ssl_trend_strength(
            np.array([100.0, 101.0]),
            np.array([99.0, 100.0]),
            np.array([100.0, 100.5]),
            period=10,
            atr_period=14,
        )
        assert val == 0.0

    def test_volume_fail_closed_returns_zero(self) -> None:
        """O7: Volume returns 0.0 on insufficient data (blocks D4)."""
        val = get_volume_force_strength(
            np.array([100.0, 101.0]),
            np.array([500.0, 600.0]),
            short_period=5,
            long_period=10,
        )
        assert val == 0.0

    def test_pattern_engine_fail_closed_insufficient_data(self) -> None:
        """O9: Pattern engine returns regime_novelty_flag=True on insufficient data."""
        closes = np.array([100.0, 101.0, 102.0])
        result = find_similar_patterns(
            closes=closes,
            correlation_length=10,
            projection_horizon=5,
            k=3,
            novelty_threshold=0.4,
        )
        assert result.regime_novelty_flag is True
        assert result.projection_direction == 0
        assert result.pattern_similarity_score == 0.0

    def test_normalize_window_scale_invariant(self) -> None:
        """Pattern normalization makes comparison scale-invariant."""
        w1 = _normalize_window(np.array([100.0, 102.0, 104.0]))
        w2 = _normalize_window(np.array([200.0, 204.0, 208.0]))
        np.testing.assert_array_almost_equal(w1, w2)

    def test_pearson_similarity_range(self) -> None:
        """Similarity is in [0, 1]."""
        a = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        b = np.array([5.0, 4.0, 3.0, 2.0, 1.0])
        sim = _pearson_similarity(a, b)
        assert 0.0 <= sim <= 1.0
        # Anti-correlated -> low similarity
        assert sim < 0.1

    def test_pearson_similarity_perfect(self) -> None:
        """Perfect correlation -> similarity = 1.0."""
        a = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        sim = _pearson_similarity(a, a)
        assert abs(sim - 1.0) < 1e-6

    def test_compute_observation_integration(self) -> None:
        """Full observation pipeline produces valid ObservationFields."""
        highs, lows, closes, volumes = _synthetic_prices(200, seed=42)
        params = _params()
        obs = compute_observation(
            highs=highs,
            lows=lows,
            closes=closes,
            volumes=volumes,
            params=params,
        )
        assert isinstance(obs, ObservationFields)
        assert 0.0 <= obs.pattern_similarity_score <= 1.0
        assert obs.projection_direction in (-1, 0, 1)
        assert 0.0 <= obs.projection_consensus_ratio <= 1.0
        assert -1.0 <= obs.ssl_trend_strength <= 1.0
        assert -1.0 <= obs.volume_force_strength <= 1.0
        assert isinstance(obs.regime_novelty_flag, bool)

    def test_ssl_hybrid_range(self) -> None:
        """SSL strength values are clamped to [-1, 1]."""
        highs, lows, closes, _ = _synthetic_prices(100)
        result = compute_ssl_hybrid(highs, lows, closes, period=10, atr_period=14)
        valid = result[~np.isnan(result)]
        assert np.all(valid >= -1.0)
        assert np.all(valid <= 1.0)

    def test_volume_oscillator_range(self) -> None:
        """Volume force values are clamped to [-1, 1]."""
        _, _, closes, volumes = _synthetic_prices(100)
        result = compute_volume_oscillator(closes, volumes, short_period=5, long_period=10)
        valid = result[~np.isnan(result)]
        assert np.all(valid >= -1.0)
        assert np.all(valid <= 1.0)


# ===========================================================================
# SECTION 2: Interpretation I1~I5 Formulas & Fail-Closed
# ===========================================================================


class TestInterpretationScores:
    """Verify I1~I5 formulas and fail-closed behavior."""

    def test_scores_frozen(self) -> None:
        """InterpretationScores is frozen."""
        s = _scores()
        with pytest.raises(FrozenInstanceError):
            s.projection_bias_score = 0.0  # type: ignore[misc]

    def test_i1_formula_bullish(self) -> None:
        """I1 = O2 * O3 * O1 for bullish direction."""
        obs = _obs(
            projection_direction=1, projection_consensus_ratio=0.8, pattern_similarity_score=0.9
        )
        scores = compute_scores(obs)
        expected = 1 * 0.8 * 0.9
        assert abs(scores.projection_bias_score - expected) < 1e-9

    def test_i1_formula_bearish(self) -> None:
        """I1 = O2 * O3 * O1 for bearish direction — sign is negative."""
        obs = _obs(
            projection_direction=-1, projection_consensus_ratio=0.8, pattern_similarity_score=0.9
        )
        scores = compute_scores(obs)
        expected = -1 * 0.8 * 0.9
        assert abs(scores.projection_bias_score - expected) < 1e-9
        assert scores.projection_bias_score < 0

    def test_i2_alignment_bullish(self) -> None:
        """I2 = sign(O2) * O6. Bullish + positive SSL -> I2 > 0."""
        obs = _obs(projection_direction=1, ssl_trend_strength=0.7)
        scores = compute_scores(obs)
        assert abs(scores.trend_alignment_score - 0.7) < 1e-9

    def test_i2_alignment_bearish(self) -> None:
        """I2 = sign(O2) * O6. Bearish + negative SSL -> I2 > 0 (aligned)."""
        obs = _obs(projection_direction=-1, ssl_trend_strength=-0.6)
        scores = compute_scores(obs)
        # sign(-1) * (-0.6) = (-1) * (-0.6) = +0.6
        assert abs(scores.trend_alignment_score - 0.6) < 1e-9
        assert scores.trend_alignment_score > 0

    def test_i3_alignment_bearish(self) -> None:
        """I3 = sign(O2) * O7. Bearish + negative volume -> I3 > 0 (aligned)."""
        obs = _obs(projection_direction=-1, volume_force_strength=-0.4)
        scores = compute_scores(obs)
        # sign(-1) * (-0.4) = +0.4
        assert abs(scores.volume_confirmation_score - 0.4) < 1e-9
        assert scores.volume_confirmation_score > 0

    def test_i2_i3_zero_when_o2_zero(self) -> None:
        """I2=0 and I3=0 when O2=0 (blocks D4 entry)."""
        obs = _obs(projection_direction=0, ssl_trend_strength=0.9, volume_force_strength=0.8)
        scores = compute_scores(obs)
        assert scores.trend_alignment_score == 0.0
        assert scores.volume_confirmation_score == 0.0

    def test_i4_path_quality_formula(self) -> None:
        """I4 = (O5 - O4) / O5."""
        obs = _obs(
            expected_adverse_excursion_before_target=0.5, expected_favorable_excursion_to_target=2.0
        )
        scores = compute_scores(obs)
        expected = (2.0 - 0.5) / 2.0  # = 0.75
        assert abs(scores.path_quality_score - expected) < 1e-9

    def test_i4_fail_closed_when_o5_zero(self) -> None:
        """I4 = -1.0 when O5 <= EPSILON (fail-closed)."""
        obs = _obs(expected_favorable_excursion_to_target=0.0)
        scores = compute_scores(obs)
        assert scores.path_quality_score == -1.0

    def test_i4_fail_closed_when_o5_epsilon(self) -> None:
        """I4 = -1.0 when O5 = EPSILON_PCT."""
        obs = _obs(expected_favorable_excursion_to_target=EPSILON_PCT)
        scores = compute_scores(obs)
        assert scores.path_quality_score == -1.0

    def test_i5_structure_rr_formula(self) -> None:
        """I5 = O5 / max(O4, EPSILON)."""
        obs = _obs(
            expected_adverse_excursion_before_target=0.5, expected_favorable_excursion_to_target=2.0
        )
        scores = compute_scores(obs)
        expected = 2.0 / max(0.5, EPSILON_PCT)  # = 4.0
        assert abs(scores.structure_rr_score - expected) < 1e-9

    def test_i5_zero_adverse_uses_epsilon(self) -> None:
        """I5 denominator uses EPSILON when O4=0."""
        obs = _obs(
            expected_adverse_excursion_before_target=0.0, expected_favorable_excursion_to_target=2.0
        )
        scores = compute_scores(obs)
        expected = 2.0 / EPSILON_PCT
        assert abs(scores.structure_rr_score - expected) < 1e-9


# ===========================================================================
# SECTION 3: Decision D1~D6 + R1 Transition Consistency
# ===========================================================================


class TestDecisionTransitions:
    """Verify complete D1~D6 + R1 state machine transitions."""

    def test_d1_idle_low_similarity(self) -> None:
        """D1: O1 < similarity_min -> stays D1_IDLE."""
        sm = PPFStateMachine(_params(similarity_min=0.6))
        result = sm.evaluate(
            obs=_obs(pattern_similarity_score=0.3),
            scores=_scores(),
        )
        assert result.state == PPFState.D1_IDLE
        assert result.allow_entry is False

    def test_d2_watch_o2_zero(self) -> None:
        """D2: O1 passes, O2=0 -> D2_WATCH."""
        sm = PPFStateMachine(_params())
        result = sm.evaluate(
            obs=_obs(projection_direction=0),
            scores=_scores(),
        )
        assert result.state == PPFState.D2_WATCH

    def test_d2_watch_timeout_3_bars(self) -> None:
        """D2: watch_timeout_bars=3 -> 3 bars in D2 -> D1_IDLE."""
        sm = PPFStateMachine(_params(watch_timeout_bars=3))
        obs = _obs(projection_direction=0)
        scores = _scores()
        # Bar 1, 2: stay in D2
        r1 = sm.evaluate(obs=obs, scores=scores)
        assert r1.state == PPFState.D2_WATCH
        r2 = sm.evaluate(obs=obs, scores=scores)
        assert r2.state == PPFState.D2_WATCH
        # Bar 3: timeout -> D1
        r3 = sm.evaluate(obs=obs, scores=scores)
        assert r3.state == PPFState.D1_IDLE

    def test_d3_candidate_alignment_fail(self) -> None:
        """D3: 3-way alignment fails -> D3_CANDIDATE."""
        sm = PPFStateMachine(_params())
        result = sm.evaluate(
            obs=_obs(),
            scores=_scores(trend_alignment_score=-0.3),  # I2 < 0 fails
        )
        assert result.state == PPFState.D3_CANDIDATE
        assert result.rejection_code == RejectionCode.TREND_MISALIGN

    def test_d3_candidate_timeout_5_bars(self) -> None:
        """D3: candidate_timeout_bars=5 -> 5 bars in D3 -> D1_IDLE."""
        sm = PPFStateMachine(_params(candidate_timeout_bars=5))
        obs = _obs()
        scores_fail = _scores(trend_alignment_score=-0.3)
        for i in range(4):
            r = sm.evaluate(obs=obs, scores=scores_fail)
            assert r.state == PPFState.D3_CANDIDATE, f"Bar {i + 1} should be D3"
        # Bar 5: timeout -> D1
        r5 = sm.evaluate(obs=obs, scores=scores_fail)
        assert r5.state == PPFState.D1_IDLE

    def test_d4_qualified_path_quality_fail(self) -> None:
        """D4: I4 <= path_quality_min -> R1 -> D1_IDLE (B2)."""
        sm = PPFStateMachine(_params(path_quality_min=0.3))
        result = sm.evaluate(
            obs=_obs(),
            scores=_scores(path_quality_score=0.1),
        )
        assert result.state == PPFState.D1_IDLE
        assert result.reached_state == PPFState.D4_QUALIFIED
        assert result.rejection == TransitionOutcome.R1_REJECT
        assert result.rejection_code == RejectionCode.PATH_QUALITY_FAIL

    def test_d4_qualified_rr_fail(self) -> None:
        """D4: I5 < rr_min -> R1 -> D1_IDLE (B2)."""
        sm = PPFStateMachine(_params(rr_min=2.0))
        result = sm.evaluate(
            obs=_obs(),
            scores=_scores(structure_rr_score=1.5),
        )
        assert result.state == PPFState.D1_IDLE
        assert result.reached_state == PPFState.D4_QUALIFIED
        assert result.rejection == TransitionOutcome.R1_REJECT
        assert result.rejection_code == RejectionCode.RR_FAIL

    def test_d5_armed_risk_filter_fail(self) -> None:
        """D5: risk_filter=False -> R1 -> D1_IDLE (B2)."""
        sm = PPFStateMachine(_params())
        result = sm.evaluate(
            obs=_obs(),
            scores=_scores(),
            risk_filter_pass=False,
        )
        assert result.state == PPFState.D1_IDLE
        assert result.reached_state == PPFState.D5_ARMED
        assert result.rejection == TransitionOutcome.R1_REJECT
        assert result.rejection_code == RejectionCode.RISK_FILTER_FAIL

    def test_d6_execute_ready_full_pass(self) -> None:
        """D6: all conditions pass + risk_filter=True -> D6_EXECUTE_READY."""
        sm = PPFStateMachine(_params())
        result = sm.evaluate(
            obs=_obs(),
            scores=_scores(),
            risk_filter_pass=True,
        )
        assert result.state == PPFState.D6_EXECUTE_READY
        assert result.allow_entry is True
        assert result.reached_state is None
        assert result.rejection is None

    def test_d6_ephemeral_not_persistent(self) -> None:
        """D6 is ephemeral: each candle starts from D1, not D6."""
        sm = PPFStateMachine(_params())
        # Candle 1: reach D6
        r1 = sm.evaluate(obs=_obs(), scores=_scores(), risk_filter_pass=True)
        assert r1.state == PPFState.D6_EXECUTE_READY
        # Candle 2: low similarity -> back to D1 (D6 not retained)
        r2 = sm.evaluate(
            obs=_obs(pattern_similarity_score=0.1),
            scores=_scores(),
        )
        assert r2.state == PPFState.D1_IDLE

    def test_next_candle_d1_reset_after_r1(self) -> None:
        """After R1 on candle N, candle N+1 starts from D1."""
        sm = PPFStateMachine(_params())
        # Candle 1: R1 at D5
        r1 = sm.evaluate(obs=_obs(), scores=_scores(), risk_filter_pass=False)
        assert r1.state == PPFState.D1_IDLE
        assert r1.rejection == TransitionOutcome.R1_REJECT
        # Candle 2: full pass -> D6 (no R1 carry-over)
        r2 = sm.evaluate(obs=_obs(), scores=_scores(), risk_filter_pass=True)
        assert r2.state == PPFState.D6_EXECUTE_READY
        assert r2.allow_entry is True

    def test_no_entry_outside_d6(self) -> None:
        """allow_entry=False for all states except D6."""
        sm = PPFStateMachine(_params())
        # D1: low similarity
        r = sm.evaluate(obs=_obs(pattern_similarity_score=0.1), scores=_scores())
        assert r.allow_entry is False
        # D2: O2=0
        r = sm.evaluate(obs=_obs(projection_direction=0), scores=_scores())
        assert r.allow_entry is False
        # D3: alignment fail
        r = sm.evaluate(obs=_obs(), scores=_scores(trend_alignment_score=-0.5))
        assert r.allow_entry is False
        # D4: path quality fail (now R1 -> D1)
        r = sm.evaluate(obs=_obs(), scores=_scores(path_quality_score=-0.5))
        assert r.allow_entry is False
        # D5: risk filter fail (now R1 -> D1)
        r = sm.evaluate(obs=_obs(), scores=_scores(), risk_filter_pass=False)
        assert r.allow_entry is False


# ===========================================================================
# SECTION 4: Novelty Brake
# ===========================================================================


class TestNoveltyBrake:
    """Verify C11 novelty brake disables PPF."""

    def test_novelty_brake_forces_d1(self) -> None:
        sm = PPFStateMachine(_params())
        result = sm.evaluate(
            obs=_obs(regime_novelty_flag=True),
            scores=_scores(),
            risk_filter_pass=True,
        )
        assert result.state == PPFState.D1_IDLE
        assert result.allow_entry is False
        assert result.rejection == TransitionOutcome.R1_REJECT
        assert result.rejection_code == RejectionCode.NOVELTY_BRAKE

    def test_novelty_brake_no_reached_state(self) -> None:
        """Novelty fires before reaching any state -> reached_state is None."""
        sm = PPFStateMachine(_params())
        result = sm.evaluate(
            obs=_obs(regime_novelty_flag=True),
            scores=_scores(),
        )
        assert result.reached_state is None

    def test_novelty_brake_resets_timeouts(self) -> None:
        """Novelty brake resets D2/D3 timeout counters."""
        sm = PPFStateMachine(_params(watch_timeout_bars=3))
        # Build up D2 counter
        sm.evaluate(obs=_obs(projection_direction=0), scores=_scores())
        sm.evaluate(obs=_obs(projection_direction=0), scores=_scores())
        # Novelty brake resets counters
        sm.evaluate(obs=_obs(regime_novelty_flag=True), scores=_scores())
        # Next D2 should be bar 1 again (not bar 3)
        r = sm.evaluate(obs=_obs(projection_direction=0), scores=_scores())
        assert r.state == PPFState.D2_WATCH  # not D1 from timeout


# ===========================================================================
# SECTION 5: Bullish Worked Example
# ===========================================================================


class TestBullishWorkedExample:
    """Full bullish path: D1->D2->D3->D4->D5->D6."""

    def test_bullish_full_pass(self) -> None:
        params = _params()
        sm = PPFStateMachine(params)
        obs = _obs(
            pattern_similarity_score=0.85,
            projection_direction=1,
            projection_consensus_ratio=0.9,
            expected_adverse_excursion_before_target=0.3,
            expected_favorable_excursion_to_target=2.5,
            ssl_trend_strength=0.6,
            volume_force_strength=0.4,
            regime_novelty_flag=False,
        )
        scores = compute_scores(obs)
        # Verify I1 is positive (bullish)
        assert scores.projection_bias_score > 0
        # Verify I2 > 0 (aligned)
        assert scores.trend_alignment_score > 0
        # Verify I3 > 0 (aligned)
        assert scores.volume_confirmation_score > 0

        result = sm.evaluate(obs=obs, scores=scores, risk_filter_pass=True)
        assert result.state == PPFState.D6_EXECUTE_READY
        assert result.allow_entry is True


# ===========================================================================
# SECTION 6: Bearish Worked Example
# ===========================================================================


class TestBearishWorkedExample:
    """Full bearish path: D1->D6 with negative direction."""

    def test_bearish_full_pass(self) -> None:
        params = _params()
        sm = PPFStateMachine(params)
        obs = _obs(
            pattern_similarity_score=0.85,
            projection_direction=-1,
            projection_consensus_ratio=0.9,
            expected_adverse_excursion_before_target=0.3,
            expected_favorable_excursion_to_target=2.5,
            ssl_trend_strength=-0.6,  # bearish SSL
            volume_force_strength=-0.4,  # bearish volume
            regime_novelty_flag=False,
        )
        scores = compute_scores(obs)
        # Verify I1 is negative (bearish direction)
        assert scores.projection_bias_score < 0
        # Verify I2 > 0 (aligned: sign(-1) * (-0.6) = +0.6)
        assert scores.trend_alignment_score > 0
        # Verify I3 > 0 (aligned: sign(-1) * (-0.4) = +0.4)
        assert scores.volume_confirmation_score > 0

        result = sm.evaluate(obs=obs, scores=scores, risk_filter_pass=True)
        assert result.state == PPFState.D6_EXECUTE_READY
        assert result.allow_entry is True

    def test_bearish_misaligned_blocked(self) -> None:
        """Bearish direction but positive SSL -> I2 < 0 -> blocked at D3."""
        params = _params()
        sm = PPFStateMachine(params)
        obs = _obs(
            projection_direction=-1,
            ssl_trend_strength=0.6,  # bullish SSL != bearish direction -> misalign
            volume_force_strength=-0.4,
        )
        scores = compute_scores(obs)
        # I2 = sign(-1) * 0.6 = -0.6 -> fails I2 > 0
        assert scores.trend_alignment_score < 0

        result = sm.evaluate(obs=obs, scores=scores, risk_filter_pass=True)
        assert result.state == PPFState.D3_CANDIDATE
        assert result.rejection_code == RejectionCode.TREND_MISALIGN


# ===========================================================================
# SECTION 7: PPFGate & Orchestration Wrapper
# ===========================================================================


class TestPPFGate:
    """Verify PPFGate entry point and wrapper behavior."""

    def test_gate_returns_false_on_deactivation(self) -> None:
        """Deactivated gate always returns False."""
        params = _params()
        gate = PPFGate(params, "test:SOL/USDT:1h")
        gate._active = False
        h, l, c, v = _synthetic_prices(200)
        assert gate.evaluate(h, l, c, v, risk_filter_pass=True) is False

    def test_gate_returns_bool(self) -> None:
        """Gate always returns bool."""
        params = _params()
        gate = PPFGate(params, "test:SOL/USDT:1h")
        h, l, c, v = _synthetic_prices(200)
        result = gate.evaluate(h, l, c, v, risk_filter_pass=True)
        assert isinstance(result, bool)

    def test_gate_fail_closed_on_exception(self) -> None:
        """Gate returns False on internal exception."""
        params = _params()
        gate = PPFGate(params, "test:SOL/USDT:1h")
        # Pass invalid data to trigger exception
        result = gate.evaluate(
            np.array([]),
            np.array([]),
            np.array([]),
            np.array([]),
            risk_filter_pass=True,
        )
        assert result is False

    def test_gate_logs_every_evaluation(self) -> None:
        """Every evaluation produces a log entry (audit principle)."""
        params = _params()
        gate = PPFGate(params, "test:SOL/USDT:1h")
        h, l, c, v = _synthetic_prices(200)
        gate.evaluate(h, l, c, v, risk_filter_pass=False)
        assert gate.last_log_entry is not None

    def test_gate_d6_check(self) -> None:
        """Gate only returns True if state is D6_EXECUTE_READY."""
        params = _params()
        gate = PPFGate(params, "test:SOL/USDT:1h")
        h, l, c, v = _synthetic_prices(200)
        # With risk_filter_pass=False, can't reach D6
        assert gate.evaluate(h, l, c, v, risk_filter_pass=False) is False

    def test_wrapper_no_candidate_returns_none(self) -> None:
        """Wrapper returns None when engine produces no candidate."""
        params = _params()
        gate = PPFGate(params, "test:SOL/USDT:1h")
        wrapper = PPFOrchestrationWrapper(
            ppf_gate=gate,
            generate_candidate_fn=lambda: None,
            execute_order_fn=lambda x: x,
            risk_filter_fn=lambda: True,
        )
        h, l, c, v = _synthetic_prices(200)
        assert wrapper.process_candle(h, l, c, v) is None

    def test_wrapper_denied_discards_candidate(self) -> None:
        """Wrapper discards candidate when PPF denies."""
        params = _params()
        gate = PPFGate(params, "test:SOL/USDT:1h")
        candidate = {"side": "buy", "amount": 1.0}
        wrapper = PPFOrchestrationWrapper(
            ppf_gate=gate,
            generate_candidate_fn=lambda: candidate,
            execute_order_fn=lambda x: x,
            risk_filter_fn=lambda: False,  # risk filter fails -> PPF denies
        )
        h, l, c, v = _synthetic_prices(200)
        assert wrapper.process_candle(h, l, c, v) is None


# ===========================================================================
# SECTION 8: Logging L1~L6 Completeness + O4_raw/O5_raw
# ===========================================================================


class TestLogging:
    """Verify L1~L6 logging fields and O4_raw/O5_raw."""

    def test_log_entry_has_l5_asset_tag(self) -> None:
        """L5: asset_timeframe_tag present."""
        entry = build_log_entry(
            obs=_obs(),
            scores=_scores(),
            result=DecisionResult(state=PPFState.D6_EXECUTE_READY, allow_entry=True),
            asset_timeframe_tag="binance:SOL/USDT:1h",
        )
        assert entry.asset_timeframe_tag == "binance:SOL/USDT:1h"

    def test_log_entry_has_l6_novelty_flag(self) -> None:
        """L6: regime_novelty_flag present."""
        entry = build_log_entry(
            obs=_obs(regime_novelty_flag=True),
            scores=_scores(),
            result=DecisionResult(state=PPFState.D1_IDLE),
            asset_timeframe_tag="test",
        )
        assert entry.regime_novelty_flag is True

    def test_log_entry_l1_initially_none(self) -> None:
        """L1: projection_actual_error is None at judgment time (post-hoc)."""
        entry = build_log_entry(
            obs=_obs(),
            scores=_scores(),
            result=DecisionResult(state=PPFState.D6_EXECUTE_READY, allow_entry=True),
            asset_timeframe_tag="test",
        )
        assert entry.projection_actual_error is None

    def test_log_entry_l3_initially_none(self) -> None:
        """L3: false_positive_flag is None at judgment time (post-hoc)."""
        entry = build_log_entry(
            obs=_obs(),
            scores=_scores(),
            result=DecisionResult(state=PPFState.D6_EXECUTE_READY, allow_entry=True),
            asset_timeframe_tag="test",
        )
        assert entry.false_positive_flag is None

    def test_log_entry_l2_contains_o4_raw_o5_raw(self) -> None:
        """L2: filter_contribution_map includes O4_raw and O5_raw."""
        obs = _obs(
            expected_adverse_excursion_before_target=1.5,
            expected_favorable_excursion_to_target=3.0,
        )
        entry = build_log_entry(
            obs=obs,
            scores=_scores(),
            result=DecisionResult(state=PPFState.D6_EXECUTE_READY, allow_entry=True),
            asset_timeframe_tag="test",
        )
        fcm = entry.filter_contribution_map
        assert "O4_raw" in fcm
        assert "O5_raw" in fcm
        assert fcm["O4_raw"] == 1.5
        assert fcm["O5_raw"] == 3.0

    def test_log_entry_l2_contains_i1_to_i5(self) -> None:
        """L2: filter_contribution_map includes I1-I5."""
        scores = _scores(
            projection_bias_score=0.5,
            trend_alignment_score=0.3,
            volume_confirmation_score=0.2,
            path_quality_score=0.7,
            structure_rr_score=4.0,
        )
        entry = build_log_entry(
            obs=_obs(),
            scores=scores,
            result=DecisionResult(state=PPFState.D6_EXECUTE_READY, allow_entry=True),
            asset_timeframe_tag="test",
        )
        fcm = entry.filter_contribution_map
        assert fcm["I1"] == 0.5
        assert fcm["I2"] == 0.3
        assert fcm["I3"] == 0.2
        assert fcm["I4"] == 0.7
        assert fcm["I5"] == 4.0

    def test_log_entry_l4_rejection_code(self) -> None:
        """L4: rejection_reason_code present on R1."""
        entry = build_log_entry(
            obs=_obs(),
            scores=_scores(),
            result=DecisionResult(
                state=PPFState.D1_IDLE,
                reached_state=PPFState.D5_ARMED,
                rejection=TransitionOutcome.R1_REJECT,
                rejection_code=RejectionCode.RISK_FILTER_FAIL,
            ),
            asset_timeframe_tag="test",
        )
        assert entry.rejection_reason_code == "RISK_FILTER_FAIL"

    def test_log_entry_reached_state_on_rejection(self) -> None:
        """reached_state is logged for R1 rejections."""
        entry = build_log_entry(
            obs=_obs(),
            scores=_scores(),
            result=DecisionResult(
                state=PPFState.D1_IDLE,
                reached_state=PPFState.D5_ARMED,
                rejection=TransitionOutcome.R1_REJECT,
                rejection_code=RejectionCode.RISK_FILTER_FAIL,
            ),
            asset_timeframe_tag="test",
        )
        assert entry.reached_state == "ARMED"

    def test_log_entry_reached_state_none_on_success(self) -> None:
        """reached_state is None on D6 success."""
        entry = build_log_entry(
            obs=_obs(),
            scores=_scores(),
            result=DecisionResult(state=PPFState.D6_EXECUTE_READY, allow_entry=True),
            asset_timeframe_tag="test",
        )
        assert entry.reached_state is None

    def test_emit_log_json_valid(self) -> None:
        """emit_log produces valid JSON."""
        entry = build_log_entry(
            obs=_obs(),
            scores=_scores(),
            result=DecisionResult(state=PPFState.D6_EXECUTE_READY, allow_entry=True),
            asset_timeframe_tag="test:SOL/USDT:1h",
        )
        with patch.object(logging.getLogger("ppf.audit"), "info") as mock_info:
            emit_log(entry)
            assert mock_info.called
            logged_json = mock_info.call_args[0][0]
            parsed = json.loads(logged_json)
            assert parsed["ppf_state"] == "EXECUTE_READY"
            assert parsed["allow_entry"] is True
            assert parsed["asset_timeframe_tag"] == "test:SOL/USDT:1h"
            assert "reached_state" in parsed


# ===========================================================================
# SECTION 9: EV1~EV10 Parameter Load & Frozen Behavior
# ===========================================================================


class TestParameters:
    """Verify EV1~EV10 parameters and C10 frozen behavior."""

    def test_default_values(self) -> None:
        """Default EV1~EV10 values match constants."""
        p = PPFParameters(market_profile=MarketProfile.M1_CRYPTO_FUTURES)
        assert p.correlation_length == DEFAULT_CORRELATION_LENGTH  # EV1=50
        assert p.projection_horizon == DEFAULT_PROJECTION_HORIZON  # EV2=10
        assert p.k == DEFAULT_K  # EV3=10
        assert p.path_quality_min == DEFAULT_PATH_QUALITY_MIN  # EV4=0.2
        assert p.rr_min == DEFAULT_RR_MIN  # EV5=2.0
        assert p.similarity_min == DEFAULT_SIMILARITY_MIN  # EV6=0.6
        assert p.novelty_threshold == DEFAULT_NOVELTY_THRESHOLD  # EV7=0.4
        assert p.projection_bias_min == DEFAULT_PROJECTION_BIAS_MIN  # EV8=0.2
        assert p.watch_timeout_bars == DEFAULT_WATCH_TIMEOUT_BARS  # EV9=3
        assert p.candidate_timeout_bars == DEFAULT_CANDIDATE_TIMEOUT_BARS  # EV10=5

    def test_ev9_watch_timeout_default_3(self) -> None:
        """EV9: watch_timeout_bars default = 3."""
        assert DEFAULT_WATCH_TIMEOUT_BARS == 3

    def test_ev10_candidate_timeout_default_5(self) -> None:
        """EV10: candidate_timeout_bars default = 5."""
        assert DEFAULT_CANDIDATE_TIMEOUT_BARS == 5

    def test_frozen_immutability(self) -> None:
        """C10: PPFParameters is frozen (no runtime mutation)."""
        p = _params()
        with pytest.raises(FrozenInstanceError):
            p.k = 5  # type: ignore[misc]

    def test_c6_k_minimum_validation(self) -> None:
        """C6: K=1 raises ValueError at construction."""
        with pytest.raises(ValueError, match="C6"):
            PPFParameters(
                market_profile=MarketProfile.M1_CRYPTO_FUTURES,
                k=1,
            )

    def test_c6_k2_passes(self) -> None:
        """C6: K=2 is minimum valid."""
        p = PPFParameters(
            market_profile=MarketProfile.M1_CRYPTO_FUTURES,
            k=2,
        )
        assert p.k == 2

    def test_load_from_dict(self) -> None:
        """load_parameters_from_dict produces frozen instance."""
        p = load_parameters_from_dict(
            MarketProfile.M1_CRYPTO_FUTURES,
            {"k": 5, "similarity_min": 0.7},
        )
        assert p.k == 5
        assert p.similarity_min == 0.7
        with pytest.raises(FrozenInstanceError):
            p.k = 10  # type: ignore[misc]

    def test_invalid_similarity_min(self) -> None:
        """similarity_min <= 0 raises ValueError."""
        with pytest.raises(ValueError):
            PPFParameters(
                market_profile=MarketProfile.M1_CRYPTO_FUTURES,
                similarity_min=0.0,
            )

    def test_invalid_rr_min(self) -> None:
        """rr_min <= 0 raises ValueError."""
        with pytest.raises(ValueError):
            PPFParameters(
                market_profile=MarketProfile.M1_CRYPTO_FUTURES,
                rr_min=0.0,
            )


# ===========================================================================
# SECTION 10: C1~C11 Constitution Invariants
# ===========================================================================


class TestConstitution:
    """Verify C1~C11 invariant checks."""

    def test_c6_check_passes(self) -> None:
        assert check_c6_k_minimum(_params(k=2)) is True

    def test_c6_check_fails(self) -> None:
        # Bypass validation to test the check function directly
        p = _params(k=3)
        object.__setattr__(p, "k", 1)
        assert check_c6_k_minimum(p) is False

    def test_c7_no_dir_passes(self) -> None:
        """C7: non-existent engine dir -> passes (acceptable)."""
        result = check_c7_engine_diff("/nonexistent/path")
        assert result.passed is True

    def test_c7_no_checksums_passes(self) -> None:
        """C7: no checksums -> passes (warning mode)."""
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as d:
            result = check_c7_engine_diff(d, None)
            assert result.passed is True

    def test_c10_frozen_passes(self) -> None:
        """C10: frozen dataclass passes immutability check."""
        p = _params()
        assert check_c10_runtime_immutability(p) is True

    def test_c11_novelty_idle_passes(self) -> None:
        """C11: novelty=True + D1_IDLE -> passes."""
        assert check_c11_novelty_brake(True, PPFState.D1_IDLE) is True

    def test_c11_novelty_non_idle_fails(self) -> None:
        """C11: novelty=True + non-IDLE -> fails."""
        assert check_c11_novelty_brake(True, PPFState.D5_ARMED) is False

    def test_c11_no_novelty_any_state_passes(self) -> None:
        """C11: novelty=False -> always passes."""
        for state in PPFState:
            assert check_c11_novelty_brake(False, state) is True

    def test_run_all_checks_passes(self) -> None:
        """All checks pass with valid params and no novelty."""
        result = run_all_checks(
            params=_params(),
            regime_novelty_flag=False,
            current_state=PPFState.D6_EXECUTE_READY,
        )
        assert result.passed is True
        assert result.violated_articles == ()

    def test_run_all_checks_c6_violation(self) -> None:
        """C6 violation detected by run_all_checks."""
        p = _params(k=3)
        object.__setattr__(p, "k", 1)
        result = run_all_checks(
            params=p,
            regime_novelty_flag=False,
            current_state=PPFState.D1_IDLE,
        )
        assert result.passed is False
        assert "C6" in result.violated_articles

    def test_run_all_checks_c11_violation(self) -> None:
        """C11 violation detected by run_all_checks."""
        result = run_all_checks(
            params=_params(),
            regime_novelty_flag=True,
            current_state=PPFState.D5_ARMED,  # should be IDLE
        )
        assert result.passed is False
        assert "C11" in result.violated_articles


# ===========================================================================
# SECTION 11: Engine diff=0 Verification
# ===========================================================================


class TestEngineDiffZero:
    """Verify execution engine files are not modified by PPF."""

    def test_c7_with_matching_checksums(self) -> None:
        """C7: matching checksums -> passes."""
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as d:
            fpath = os.path.join(d, "engine.py")
            content = b"# engine code unchanged"
            with open(fpath, "wb") as f:
                f.write(content)
            import hashlib

            expected = hashlib.sha256(content).hexdigest()
            result = check_c7_engine_diff(d, {"engine.py": expected})
            assert result.passed is True

    def test_c7_with_mismatched_checksums(self) -> None:
        """C7: mismatched checksum -> fails."""
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as d:
            fpath = os.path.join(d, "engine.py")
            with open(fpath, "wb") as f:
                f.write(b"# modified engine code")
            result = check_c7_engine_diff(d, {"engine.py": "0" * 64})
            assert result.passed is False
            assert "C7" in result.violated_articles

    def test_c7_missing_file(self) -> None:
        """C7: expected file missing -> fails."""
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            result = check_c7_engine_diff(d, {"missing.py": "0" * 64})
            assert result.passed is False


# ===========================================================================
# SECTION 12: Shadow Log Completeness
# ===========================================================================


class TestShadowLogCompleteness:
    """Verify that shadow mode captures all mandatory log fields."""

    def test_emit_log_includes_reached_state(self) -> None:
        """emit_log includes reached_state in JSON output."""
        entry = build_log_entry(
            obs=_obs(),
            scores=_scores(),
            result=DecisionResult(
                state=PPFState.D1_IDLE,
                reached_state=PPFState.D4_QUALIFIED,
                rejection=TransitionOutcome.R1_REJECT,
                rejection_code=RejectionCode.PATH_QUALITY_FAIL,
            ),
            asset_timeframe_tag="test:SOL/USDT:1h",
        )
        with patch.object(logging.getLogger("ppf.audit"), "info") as mock_info:
            emit_log(entry)
            parsed = json.loads(mock_info.call_args[0][0])
            assert parsed["reached_state"] == "QUALIFIED"
            assert parsed["rejection_reason_code"] == "PATH_QUALITY_FAIL"
            assert parsed["ppf_state"] == "IDLE"

    def test_all_rejection_codes_loggable(self) -> None:
        """Every RejectionCode value can be logged."""
        for code in RejectionCode:
            entry = build_log_entry(
                obs=_obs(),
                scores=_scores(),
                result=DecisionResult(
                    state=PPFState.D1_IDLE,
                    rejection=TransitionOutcome.R1_REJECT,
                    rejection_code=code,
                ),
                asset_timeframe_tag="test",
            )
            assert entry.rejection_reason_code == code.value

    def test_all_states_loggable(self) -> None:
        """Every PPFState value can appear in log entry."""
        for state in PPFState:
            entry = build_log_entry(
                obs=_obs(),
                scores=_scores(),
                result=DecisionResult(state=state),
                asset_timeframe_tag="test",
            )
            assert entry.ppf_state == state.value
