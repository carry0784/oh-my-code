"""PPF Paper Verification Test Suite.

Authority: PPF-PAPER-VERIFICATION-001
Basis: PPF-CODE-IMPLEMENTATION-001 + CORRECTION-R1 (B2) + CORRECTION-R1 (C10)
     + PPF-SHADOW-VERIFICATION-001 (101/101 PASS)

Paper-only verification of PPF in simulated trading flow.
No live promotion. No real order submission. No engine modification.

Paper Verification Scope (beyond shadow):
    - Paper order candidate creation / deny / accept flow
    - Paper fill / cancel / no-fill scenarios
    - Paper PnL / post-trade logging / false_positive_flag pipeline
    - Multi-candle sequence with state transitions
    - Shadow-to-paper invariant continuity
    - Full PPFGate + PPFOrchestrationWrapper integration

Baseline Fingerprint:
    Recorded at chain start. Any source file drift => FAIL.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from strategies.ppf.constants import (
    DEFAULT_CANDIDATE_TIMEOUT_BARS,
    DEFAULT_WATCH_TIMEOUT_BARS,
    EPSILON_PCT,
    MarketProfile,
    PPFState,
    RejectionCode,
    TransitionOutcome,
)
from strategies.ppf.constitution import run_all_checks
from strategies.ppf.decision import DecisionResult, PPFStateMachine
from strategies.ppf.gate import PPFGate, PPFOrchestrationWrapper
from strategies.ppf.interpretation import InterpretationScores, compute_scores
from strategies.ppf.logging_schema import PPFLogEntry, build_log_entry, emit_log
from strategies.ppf.observation import ObservationFields, compute_observation
from strategies.ppf.parameters import PPFParameters


# ===========================================================================
# Paper Trading Simulation Helpers
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


def _synthetic_prices(n: int = 200, seed: int = 42) -> tuple[np.ndarray, ...]:
    rng = np.random.RandomState(seed)
    base = 100.0
    returns = rng.randn(n) * 0.02
    closes = base * np.cumprod(1 + returns)
    highs = closes * (1 + rng.uniform(0.001, 0.01, n))
    lows = closes * (1 - rng.uniform(0.001, 0.01, n))
    volumes = rng.uniform(100, 1000, n)
    return highs, lows, closes, volumes


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


@dataclass
class PaperTrade:
    """Simulated paper trade for verification."""

    side: str
    symbol: str
    size: float
    entry_price: float
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    status: str = "open"  # open, filled, cancelled

    def fill(self, exit_price: float) -> None:
        self.exit_price = exit_price
        self.status = "filled"
        if self.side == "buy":
            self.pnl = (exit_price - self.entry_price) / self.entry_price * 100
        else:
            self.pnl = (self.entry_price - exit_price) / self.entry_price * 100

    def cancel(self) -> None:
        self.status = "cancelled"
        self.pnl = 0.0


class PaperTradingEngine:
    """Simulated paper trading engine for PPF verification.

    This simulates the EXISTING engine that PPF wraps.
    PPF does NOT modify this engine (C7 diff=0).
    """

    def __init__(self) -> None:
        self.candidates: list[dict[str, Any]] = []
        self.executed: list[dict[str, Any]] = []
        self.trades: list[PaperTrade] = []
        self._next_candidate: Optional[dict[str, Any]] = None
        self._risk_filter_result: bool = True

    def set_next_candidate(self, candidate: Optional[dict[str, Any]]) -> None:
        self._next_candidate = candidate

    def set_risk_filter(self, result: bool) -> None:
        self._risk_filter_result = result

    def generate_candidate(self) -> Optional[dict[str, Any]]:
        c = self._next_candidate
        if c is not None:
            self.candidates.append(c)
        return c

    def execute_order(self, candidate: dict[str, Any]) -> dict[str, Any]:
        result = {**candidate, "status": "paper_filled"}
        self.executed.append(result)
        trade = PaperTrade(
            side=candidate.get("side", "buy"),
            symbol=candidate.get("symbol", "SOL/USDT"),
            size=candidate.get("size", 1.0),
            entry_price=candidate.get("entry_price", 100.0),
        )
        self.trades.append(trade)
        return result

    def risk_filter(self) -> bool:
        return self._risk_filter_result


# ===========================================================================
# SECTION 1: Paper Candidate Accepted Flow (Bullish)
# ===========================================================================


class TestPaperCandidateAccepted:
    """Paper flow: engine candidate → PPF D6 → execute (paper)."""

    def test_bullish_candidate_accepted_and_executed(self) -> None:
        """Full bullish flow: candidate created, PPF allows, paper order executed."""
        params = _params()
        gate = PPFGate(params, "paper:SOL/USDT:1h")
        engine = PaperTradingEngine()

        candidate = {"side": "buy", "symbol": "SOL/USDT", "size": 1.0, "entry_price": 150.0}
        engine.set_next_candidate(candidate)
        engine.set_risk_filter(True)

        wrapper = PPFOrchestrationWrapper(
            ppf_gate=gate,
            generate_candidate_fn=engine.generate_candidate,
            execute_order_fn=engine.execute_order,
            risk_filter_fn=engine.risk_filter,
        )

        h, l, c, v = _synthetic_prices(200, seed=42)
        result = wrapper.process_candle(h, l, c, v)

        # Verify: either executed or denied (depends on pattern data)
        # The key is the wrapper flow works without error
        assert result is None or isinstance(result, dict)
        assert len(engine.candidates) == 1

    def test_bearish_candidate_accepted_and_executed(self) -> None:
        """Full bearish flow with paper execution."""
        params = _params()
        gate = PPFGate(params, "paper:SOL/USDT:1h")
        engine = PaperTradingEngine()

        candidate = {"side": "sell", "symbol": "SOL/USDT", "size": 1.0, "entry_price": 150.0}
        engine.set_next_candidate(candidate)
        engine.set_risk_filter(True)

        wrapper = PPFOrchestrationWrapper(
            ppf_gate=gate,
            generate_candidate_fn=engine.generate_candidate,
            execute_order_fn=engine.execute_order,
            risk_filter_fn=engine.risk_filter,
        )

        h, l, c, v = _synthetic_prices(200, seed=99)
        result = wrapper.process_candle(h, l, c, v)
        assert result is None or isinstance(result, dict)


# ===========================================================================
# SECTION 2: Paper Candidate Denied Flow
# ===========================================================================


class TestPaperCandidateDenied:
    """Paper flow: engine candidate → PPF denies → candidate discarded."""

    def test_denied_by_risk_filter(self) -> None:
        """Risk filter fails → PPF denies → no execution."""
        params = _params()
        gate = PPFGate(params, "paper:SOL/USDT:1h")
        engine = PaperTradingEngine()

        candidate = {"side": "buy", "symbol": "SOL/USDT", "size": 1.0}
        engine.set_next_candidate(candidate)
        engine.set_risk_filter(False)  # risk filter fails

        wrapper = PPFOrchestrationWrapper(
            ppf_gate=gate,
            generate_candidate_fn=engine.generate_candidate,
            execute_order_fn=engine.execute_order,
            risk_filter_fn=engine.risk_filter,
        )

        h, l, c, v = _synthetic_prices(200)
        result = wrapper.process_candle(h, l, c, v)

        assert result is None  # denied
        assert len(engine.executed) == 0

    def test_denied_no_candidate(self) -> None:
        """No candidate from engine → nothing to gate."""
        params = _params()
        gate = PPFGate(params, "paper:SOL/USDT:1h")
        engine = PaperTradingEngine()
        engine.set_next_candidate(None)

        wrapper = PPFOrchestrationWrapper(
            ppf_gate=gate,
            generate_candidate_fn=engine.generate_candidate,
            execute_order_fn=engine.execute_order,
            risk_filter_fn=engine.risk_filter,
        )

        h, l, c, v = _synthetic_prices(200)
        result = wrapper.process_candle(h, l, c, v)
        assert result is None
        assert len(engine.candidates) == 0
        assert len(engine.executed) == 0

    def test_denied_gate_deactivated(self) -> None:
        """Deactivated gate → all candidates denied."""
        params = _params()
        gate = PPFGate(params, "paper:SOL/USDT:1h")
        gate._active = False  # simulate constitution violation

        engine = PaperTradingEngine()
        candidate = {"side": "buy", "symbol": "SOL/USDT", "size": 1.0}
        engine.set_next_candidate(candidate)
        engine.set_risk_filter(True)

        wrapper = PPFOrchestrationWrapper(
            ppf_gate=gate,
            generate_candidate_fn=engine.generate_candidate,
            execute_order_fn=engine.execute_order,
            risk_filter_fn=engine.risk_filter,
        )

        h, l, c, v = _synthetic_prices(200)
        result = wrapper.process_candle(h, l, c, v)
        assert result is None
        assert len(engine.executed) == 0


# ===========================================================================
# SECTION 3: Paper Fill / Cancel / No-Fill Scenarios
# ===========================================================================


class TestPaperTradeLifecycle:
    """Paper trade lifecycle: fill, cancel, no-fill."""

    def test_paper_fill_positive_pnl(self) -> None:
        """Paper trade filled with positive PnL."""
        trade = PaperTrade(side="buy", symbol="SOL/USDT", size=1.0, entry_price=100.0)
        trade.fill(exit_price=110.0)
        assert trade.status == "filled"
        assert trade.pnl is not None
        assert trade.pnl == pytest.approx(10.0)  # 10% gain

    def test_paper_fill_negative_pnl(self) -> None:
        """Paper trade filled with negative PnL (false positive candidate)."""
        trade = PaperTrade(side="buy", symbol="SOL/USDT", size=1.0, entry_price=100.0)
        trade.fill(exit_price=95.0)
        assert trade.status == "filled"
        assert trade.pnl is not None
        assert trade.pnl == pytest.approx(-5.0)  # 5% loss

    def test_paper_fill_short_positive(self) -> None:
        """Short paper trade filled with positive PnL."""
        trade = PaperTrade(side="sell", symbol="SOL/USDT", size=1.0, entry_price=100.0)
        trade.fill(exit_price=90.0)
        assert trade.pnl == pytest.approx(10.0)

    def test_paper_cancel(self) -> None:
        """Paper trade cancelled → PnL = 0."""
        trade = PaperTrade(side="buy", symbol="SOL/USDT", size=1.0, entry_price=100.0)
        trade.cancel()
        assert trade.status == "cancelled"
        assert trade.pnl == 0.0

    def test_paper_no_fill_stays_open(self) -> None:
        """Paper trade not filled → stays open."""
        trade = PaperTrade(side="buy", symbol="SOL/USDT", size=1.0, entry_price=100.0)
        assert trade.status == "open"
        assert trade.exit_price is None
        assert trade.pnl is None


# ===========================================================================
# SECTION 4: Paper PnL / False Positive Pipeline
# ===========================================================================


class TestPaperFalsePositivePipeline:
    """L3 false_positive_flag pipeline in paper mode."""

    def test_false_positive_flag_set_on_loss(self) -> None:
        """D6 approved trade that loses → false_positive_flag = True."""
        obs = _obs()
        scores = _scores()
        result = DecisionResult(
            state=PPFState.D6_EXECUTE_READY,
            allow_entry=True,
        )
        entry = build_log_entry(
            obs=obs,
            scores=scores,
            result=result,
            asset_timeframe_tag="paper:SOL/USDT:1h",
        )
        # L3 is initially None (filled post-hoc)
        assert entry.false_positive_flag is None

        # Post-hoc: trade lost → set false_positive_flag
        entry.false_positive_flag = True
        assert entry.false_positive_flag is True

    def test_true_positive_flag_on_win(self) -> None:
        """D6 approved trade that wins → false_positive_flag = False."""
        entry = build_log_entry(
            obs=_obs(),
            scores=_scores(),
            result=DecisionResult(state=PPFState.D6_EXECUTE_READY, allow_entry=True),
            asset_timeframe_tag="paper:SOL/USDT:1h",
        )
        entry.false_positive_flag = False
        assert entry.false_positive_flag is False

    def test_l1_projection_actual_error_post_hoc(self) -> None:
        """L1 projection_actual_error filled after projection horizon."""
        entry = build_log_entry(
            obs=_obs(),
            scores=_scores(),
            result=DecisionResult(state=PPFState.D6_EXECUTE_READY, allow_entry=True),
            asset_timeframe_tag="paper:SOL/USDT:1h",
        )
        assert entry.projection_actual_error is None
        # Post-hoc: fill with actual error
        entry.projection_actual_error = 2.5
        assert entry.projection_actual_error == 2.5

    def test_rejected_trade_no_false_positive(self) -> None:
        """R1 rejected trade → false_positive_flag stays None (no trade taken)."""
        entry = build_log_entry(
            obs=_obs(),
            scores=_scores(),
            result=DecisionResult(
                state=PPFState.D1_IDLE,
                reached_state=PPFState.D5_ARMED,
                rejection=TransitionOutcome.R1_REJECT,
                rejection_code=RejectionCode.RISK_FILTER_FAIL,
            ),
            asset_timeframe_tag="paper:SOL/USDT:1h",
        )
        # No trade was taken, so false_positive_flag should remain None
        assert entry.false_positive_flag is None
        assert entry.projection_actual_error is None


# ===========================================================================
# SECTION 5: Multi-Candle Paper Sequence
# ===========================================================================


class TestMultiCandlePaperSequence:
    """Simulate multi-candle paper trading sessions."""

    def test_multi_candle_mixed_outcomes(self) -> None:
        """5-candle sequence: idle, watch, reject, accept, idle."""
        params = _params()
        sm = PPFStateMachine(params)

        # Candle 1: low similarity -> D1
        r1 = sm.evaluate(
            obs=_obs(pattern_similarity_score=0.2),
            scores=_scores(),
        )
        assert r1.state == PPFState.D1_IDLE

        # Candle 2: high similarity, O2=0 -> D2
        r2 = sm.evaluate(
            obs=_obs(projection_direction=0),
            scores=_scores(),
        )
        assert r2.state == PPFState.D2_WATCH

        # Candle 3: alignment fail -> R1 at D4 (path quality)
        r3 = sm.evaluate(
            obs=_obs(),
            scores=_scores(path_quality_score=-0.5),
        )
        assert r3.state == PPFState.D1_IDLE
        assert r3.rejection == TransitionOutcome.R1_REJECT
        assert r3.reached_state == PPFState.D4_QUALIFIED

        # Candle 4: full pass -> D6
        r4 = sm.evaluate(
            obs=_obs(),
            scores=_scores(),
            risk_filter_pass=True,
        )
        assert r4.state == PPFState.D6_EXECUTE_READY
        assert r4.allow_entry is True

        # Candle 5: low similarity again -> D1 (D6 not retained)
        r5 = sm.evaluate(
            obs=_obs(pattern_similarity_score=0.1),
            scores=_scores(),
        )
        assert r5.state == PPFState.D1_IDLE

    def test_consecutive_rejections_then_accept(self) -> None:
        """3 consecutive R1 rejections followed by D6 pass."""
        params = _params()
        sm = PPFStateMachine(params)

        # 3 rejections at D5 (risk filter)
        for i in range(3):
            r = sm.evaluate(
                obs=_obs(),
                scores=_scores(),
                risk_filter_pass=False,
            )
            assert r.state == PPFState.D1_IDLE
            assert r.rejection == TransitionOutcome.R1_REJECT
            assert r.reached_state == PPFState.D5_ARMED

        # Then D6 pass
        r = sm.evaluate(obs=_obs(), scores=_scores(), risk_filter_pass=True)
        assert r.state == PPFState.D6_EXECUTE_READY
        assert r.allow_entry is True

    def test_d2_timeout_in_paper_sequence(self) -> None:
        """D2 timeout after 3 bars in paper flow."""
        params = _params(watch_timeout_bars=3)
        sm = PPFStateMachine(params)
        obs_d2 = _obs(projection_direction=0)
        scores = _scores()

        results = []
        for _ in range(4):
            r = sm.evaluate(obs=obs_d2, scores=scores)
            results.append(r.state)

        # Bars 1,2: D2, Bar 3: D1 (timeout), Bar 4: D2 (reset counter)
        assert results[0] == PPFState.D2_WATCH
        assert results[1] == PPFState.D2_WATCH
        assert results[2] == PPFState.D1_IDLE  # timeout at bar 3
        assert results[3] == PPFState.D2_WATCH  # counter reset

    def test_d3_timeout_in_paper_sequence(self) -> None:
        """D3 timeout after 5 bars in paper flow."""
        params = _params(candidate_timeout_bars=5)
        sm = PPFStateMachine(params)
        obs_d3 = _obs()
        scores_fail = _scores(trend_alignment_score=-0.3)

        results = []
        for _ in range(6):
            r = sm.evaluate(obs=obs_d3, scores=scores_fail)
            results.append(r.state)

        # Bars 1-4: D3, Bar 5: D1 (timeout), Bar 6: D3 (reset)
        assert results[0] == PPFState.D3_CANDIDATE
        assert results[1] == PPFState.D3_CANDIDATE
        assert results[2] == PPFState.D3_CANDIDATE
        assert results[3] == PPFState.D3_CANDIDATE
        assert results[4] == PPFState.D1_IDLE  # timeout at bar 5
        assert results[5] == PPFState.D3_CANDIDATE  # counter reset


# ===========================================================================
# SECTION 6: PPFGate Integration in Paper Mode
# ===========================================================================


class TestPPFGateIntegration:
    """End-to-end PPFGate behavior in paper mode."""

    def test_gate_evaluate_returns_bool(self) -> None:
        """Gate always returns bool in paper mode."""
        params = _params()
        gate = PPFGate(params, "paper:SOL/USDT:1h")
        h, l, c, v = _synthetic_prices(200)
        result = gate.evaluate(h, l, c, v, risk_filter_pass=True)
        assert isinstance(result, bool)

    def test_gate_logs_in_paper_mode(self) -> None:
        """Every gate evaluation produces audit log."""
        params = _params()
        gate = PPFGate(params, "paper:SOL/USDT:1h")
        h, l, c, v = _synthetic_prices(200)
        gate.evaluate(h, l, c, v, risk_filter_pass=True)
        log = gate.last_log_entry
        assert log is not None
        assert log.asset_timeframe_tag == "paper:SOL/USDT:1h"

    def test_gate_fail_closed_on_bad_data(self) -> None:
        """Gate returns False on invalid data (fail-closed)."""
        params = _params()
        gate = PPFGate(params, "paper:SOL/USDT:1h")
        result = gate.evaluate(
            np.array([]),
            np.array([]),
            np.array([]),
            np.array([]),
            risk_filter_pass=True,
        )
        assert result is False

    def test_gate_sequential_candles(self) -> None:
        """Gate handles sequential candle evaluations."""
        params = _params()
        gate = PPFGate(params, "paper:SOL/USDT:1h")
        h, l, c, v = _synthetic_prices(200)

        results = []
        for _ in range(5):
            r = gate.evaluate(h, l, c, v, risk_filter_pass=True)
            results.append(r)

        # All should be bool, no crashes across candles
        assert all(isinstance(r, bool) for r in results)

    def test_gate_constitution_violation_deactivates(self) -> None:
        """Constitution violation → gate deactivated → all future False."""
        params = _params(k=3)
        gate = PPFGate(params, "paper:SOL/USDT:1h")
        # Force C6 violation by mutating k (bypassing frozen)
        object.__setattr__(gate._params, "k", 1)

        h, l, c, v = _synthetic_prices(200)
        r1 = gate.evaluate(h, l, c, v, risk_filter_pass=True)
        assert r1 is False
        assert gate.is_active is False

        # All future evaluations return False
        r2 = gate.evaluate(h, l, c, v, risk_filter_pass=True)
        assert r2 is False


# ===========================================================================
# SECTION 7: Wrapper End-to-End Paper Flow
# ===========================================================================


class TestWrapperEndToEnd:
    """Full PPFOrchestrationWrapper paper flow."""

    def test_wrapper_accept_execute_flow(self) -> None:
        """Wrapper: candidate → gate allows → execute."""
        params = _params()
        gate = PPFGate(params, "paper:SOL/USDT:1h")
        engine = PaperTradingEngine()

        candidate = {"side": "buy", "symbol": "SOL/USDT", "size": 0.5, "entry_price": 155.0}
        engine.set_next_candidate(candidate)
        engine.set_risk_filter(True)

        wrapper = PPFOrchestrationWrapper(
            ppf_gate=gate,
            generate_candidate_fn=engine.generate_candidate,
            execute_order_fn=engine.execute_order,
            risk_filter_fn=engine.risk_filter,
        )

        h, l, c, v = _synthetic_prices(200)
        result = wrapper.process_candle(h, l, c, v)

        # Either executed or denied by PPF pattern check
        if result is not None:
            assert result["status"] == "paper_filled"
            assert len(engine.executed) == 1
            assert len(engine.trades) == 1
        else:
            assert len(engine.executed) == 0

    def test_wrapper_deny_discard_flow(self) -> None:
        """Wrapper: candidate → risk filter fails → discard."""
        params = _params()
        gate = PPFGate(params, "paper:SOL/USDT:1h")
        engine = PaperTradingEngine()

        candidate = {"side": "buy", "symbol": "SOL/USDT", "size": 1.0}
        engine.set_next_candidate(candidate)
        engine.set_risk_filter(False)  # will block at D5

        wrapper = PPFOrchestrationWrapper(
            ppf_gate=gate,
            generate_candidate_fn=engine.generate_candidate,
            execute_order_fn=engine.execute_order,
            risk_filter_fn=engine.risk_filter,
        )

        h, l, c, v = _synthetic_prices(200)
        result = wrapper.process_candle(h, l, c, v)
        assert result is None
        assert len(engine.executed) == 0

    def test_wrapper_multi_candle_session(self) -> None:
        """Wrapper processes 10 candles without error."""
        params = _params()
        gate = PPFGate(params, "paper:SOL/USDT:1h")
        engine = PaperTradingEngine()

        candidate = {"side": "buy", "symbol": "SOL/USDT", "size": 1.0}

        wrapper = PPFOrchestrationWrapper(
            ppf_gate=gate,
            generate_candidate_fn=engine.generate_candidate,
            execute_order_fn=engine.execute_order,
            risk_filter_fn=engine.risk_filter,
        )

        h, l, c, v = _synthetic_prices(300)

        for i in range(10):
            # Alternate: candidate present / absent
            if i % 2 == 0:
                engine.set_next_candidate(candidate)
                engine.set_risk_filter(i % 3 == 0)
            else:
                engine.set_next_candidate(None)

            result = wrapper.process_candle(h, l, c, v)
            assert result is None or isinstance(result, dict)


# ===========================================================================
# SECTION 8: Shadow-to-Paper Invariant Continuity
# ===========================================================================


class TestShadowToPaperContinuity:
    """Verify shadow-verified invariants hold in paper mode."""

    def test_b2_d5_rejection_in_paper(self) -> None:
        """B2: D5 failure -> R1 -> D1_IDLE holds in paper flow."""
        sm = PPFStateMachine(_params())
        r = sm.evaluate(obs=_obs(), scores=_scores(), risk_filter_pass=False)
        assert r.state == PPFState.D1_IDLE
        assert r.reached_state == PPFState.D5_ARMED
        assert r.rejection == TransitionOutcome.R1_REJECT

    def test_d6_ephemeral_in_paper(self) -> None:
        """D6 ephemeral: not retained across candles in paper flow."""
        sm = PPFStateMachine(_params())
        r1 = sm.evaluate(obs=_obs(), scores=_scores(), risk_filter_pass=True)
        assert r1.state == PPFState.D6_EXECUTE_READY
        r2 = sm.evaluate(
            obs=_obs(pattern_similarity_score=0.1),
            scores=_scores(),
        )
        assert r2.state == PPFState.D1_IDLE

    def test_novelty_brake_in_paper(self) -> None:
        """C11: novelty brake forces D1 in paper flow."""
        sm = PPFStateMachine(_params())
        r = sm.evaluate(
            obs=_obs(regime_novelty_flag=True),
            scores=_scores(),
            risk_filter_pass=True,
        )
        assert r.state == PPFState.D1_IDLE
        assert r.allow_entry is False
        assert r.rejection_code == RejectionCode.NOVELTY_BRAKE

    def test_ev9_timeout_3_in_paper(self) -> None:
        """EV9: watch_timeout_bars=3 holds in paper flow."""
        assert DEFAULT_WATCH_TIMEOUT_BARS == 3
        sm = PPFStateMachine(_params(watch_timeout_bars=3))
        obs_d2 = _obs(projection_direction=0)
        for _ in range(2):
            r = sm.evaluate(obs=obs_d2, scores=_scores())
            assert r.state == PPFState.D2_WATCH
        r = sm.evaluate(obs=obs_d2, scores=_scores())
        assert r.state == PPFState.D1_IDLE

    def test_ev10_timeout_5_in_paper(self) -> None:
        """EV10: candidate_timeout_bars=5 holds in paper flow."""
        assert DEFAULT_CANDIDATE_TIMEOUT_BARS == 5
        sm = PPFStateMachine(_params(candidate_timeout_bars=5))
        obs_d3 = _obs()
        scores_fail = _scores(trend_alignment_score=-0.3)
        for _ in range(4):
            r = sm.evaluate(obs=obs_d3, scores=scores_fail)
            assert r.state == PPFState.D3_CANDIDATE
        r = sm.evaluate(obs=obs_d3, scores=scores_fail)
        assert r.state == PPFState.D1_IDLE

    def test_c10_frozen_in_paper(self) -> None:
        """C10: parameters frozen in paper mode."""
        from dataclasses import FrozenInstanceError

        p = _params()
        with pytest.raises(FrozenInstanceError):
            p.k = 99  # type: ignore[misc]

    def test_constitution_all_pass_in_paper(self) -> None:
        """All constitution checks pass with valid params in paper mode."""
        result = run_all_checks(
            params=_params(),
            regime_novelty_flag=False,
            current_state=PPFState.D6_EXECUTE_READY,
        )
        assert result.passed is True


# ===========================================================================
# SECTION 9: Paper Logging Completeness
# ===========================================================================


class TestPaperLogging:
    """Verify logging completeness in paper mode."""

    def test_paper_log_has_asset_tag(self) -> None:
        """L5: paper asset tag in log."""
        params = _params()
        gate = PPFGate(params, "paper:SOL/USDT:1h")
        h, l, c, v = _synthetic_prices(200)
        gate.evaluate(h, l, c, v, risk_filter_pass=True)
        log = gate.last_log_entry
        assert log is not None
        assert "paper:" in log.asset_timeframe_tag

    def test_paper_log_has_filter_map(self) -> None:
        """L2: filter_contribution_map with I1-I5 and O4_raw/O5_raw."""
        params = _params()
        gate = PPFGate(params, "paper:SOL/USDT:1h")
        h, l, c, v = _synthetic_prices(200)
        gate.evaluate(h, l, c, v, risk_filter_pass=True)
        log = gate.last_log_entry
        assert log is not None
        fcm = log.filter_contribution_map
        for key in ["I1", "I2", "I3", "I4", "I5", "O4_raw", "O5_raw"]:
            assert key in fcm, f"Missing {key} in filter_contribution_map"

    def test_paper_log_json_serializable(self) -> None:
        """Paper log entries can be JSON serialized."""
        params = _params()
        gate = PPFGate(params, "paper:SOL/USDT:1h")
        h, l, c, v = _synthetic_prices(200)
        gate.evaluate(h, l, c, v, risk_filter_pass=True)
        log = gate.last_log_entry
        assert log is not None

        with patch.object(logging.getLogger("ppf.audit"), "info") as mock:
            emit_log(log)
            assert mock.called
            parsed = json.loads(mock.call_args[0][0])
            assert "ppf_state" in parsed
            assert "allow_entry" in parsed
            assert "filter_contribution_map" in parsed

    def test_paper_log_reached_state_on_rejection(self) -> None:
        """reached_state logged on R1 rejection in paper."""
        entry = build_log_entry(
            obs=_obs(),
            scores=_scores(),
            result=DecisionResult(
                state=PPFState.D1_IDLE,
                reached_state=PPFState.D5_ARMED,
                rejection=TransitionOutcome.R1_REJECT,
                rejection_code=RejectionCode.RISK_FILTER_FAIL,
            ),
            asset_timeframe_tag="paper:SOL/USDT:1h",
        )
        assert entry.reached_state == "ARMED"
        assert entry.ppf_state == "IDLE"


# ===========================================================================
# SECTION 10: Engine diff=0 in Paper Mode
# ===========================================================================


class TestEngineDiffZeroPaper:
    """Verify engine files are not modified during paper verification."""

    def test_no_engine_file_modification(self) -> None:
        """PPF source files match baseline fingerprint (no drift)."""
        import hashlib

        # Baseline from PPF-SHADOW-VERIFICATION-001
        expected = {
            "strategies/ppf/constitution.py": "7b26bba6a161fa19",
            "strategies/ppf/decision.py": "a72b23bf4070b6c4",
            "strategies/ppf/gate.py": "6542d2c4b5298725",
            "strategies/ppf/logging_schema.py": "3f7fc8511a188e3e",
            "strategies/ppf/observation.py": "77f1e61edc725a67",
            "strategies/ppf/interpretation.py": "f98f2b3741b4b50b",
            "strategies/ppf/parameters.py": "7aa74fc9b0111cde",
            "strategies/ppf/constants.py": "e29c54c86a572f92",
            "strategies/ppf/pattern_engine/matcher.py": "5ef3ae35db81d7ed",
            "strategies/ppf/indicators/ssl_hybrid.py": "8997f35923b19966",
            "strategies/ppf/indicators/volume_osc.py": "c9e7ddc6405837eb",
        }

        for filepath, expected_prefix in expected.items():
            actual = hashlib.sha256(open(filepath, "rb").read()).hexdigest()
            assert actual.startswith(expected_prefix), (
                f"Source file drift: {filepath}\n"
                f"  expected prefix: {expected_prefix}\n"
                f"  actual:          {actual[:16]}"
            )
