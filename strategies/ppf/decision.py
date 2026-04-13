"""PPF Decision state machine (D1-D6 + R1).

Authority: PPF-IMPLEMENTATION-001-CORRECTION-R1

State Machine:
    D1 IDLE -> D2 WATCH -> D3 CANDIDATE -> D4 QUALIFIED -> D5 ARMED -> D6 EXECUTE_READY
    D4/D5 failure -> R1 REJECT -> D1 IDLE (next candle)
    D2/D3 timeout -> D1 IDLE

D6 is ephemeral gate-pass: valid only within current candle,
resets to D1 on next candle for re-evaluation.

Transition table (corrected, B1/B2 resolved):
    D1->D2: O1 >= similarity_min
    D2->D3: O2 != 0 (or timeout -> D1)
    D3->D4: abs(I1) >= projection_bias_min AND I2 > 0 AND I3 > 0 (or timeout -> D1)
    D4->D5: I4 > path_quality_min AND I5 >= rr_min (or -> R1)
    D5->D6: risk_filter_pass (or -> R1)
    R1->D1: automatic on next candle
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from strategies.ppf.constants import PPFState, RejectionCode, TransitionOutcome
from strategies.ppf.interpretation import InterpretationScores
from strategies.ppf.observation import ObservationFields
from strategies.ppf.parameters import PPFParameters


@dataclass
class DecisionResult:
    """Result of a single decision evaluation cycle.

    When R1 rejection occurs:
    - state = D1_IDLE (post-rejection reset, B2 compliant)
    - reached_state = the state where rejection occurred (audit trail)
    - rejection = R1_REJECT
    - rejection_code = specific reason
    - allow_entry = False
    """

    state: PPFState
    reached_state: Optional[PPFState] = None
    rejection: Optional[TransitionOutcome] = None
    rejection_code: Optional[RejectionCode] = None
    allow_entry: bool = False


class PPFStateMachine:
    """PPF decision state machine.

    Evaluates one candle at a time. Each candle starts from D1 (IDLE)
    and transitions through states based on observation/interpretation.

    D6 is ephemeral: it does NOT persist across candles. Every candle
    starts fresh from D1.

    Constitution enforced:
        C4: path quality required for D5
        C11: O9=True -> forced D1 (novelty brake)
    """

    def __init__(self, params: PPFParameters) -> None:
        self._params = params
        # Timeout tracking (bars in D2/D3 without transition)
        self._d2_bars: int = 0
        self._d3_bars: int = 0

    def evaluate(
        self,
        obs: ObservationFields,
        scores: InterpretationScores,
        risk_filter_pass: bool = False,
    ) -> DecisionResult:
        """Evaluate one candle through the full state machine.

        Each candle starts from D1 and transitions as far as conditions allow.
        This is a single-pass evaluation, not a persistent state.

        Args:
            obs: Observation fields for this candle.
            scores: Interpretation scores for this candle.
            risk_filter_pass: Whether the external risk filter approves.
                This is provided by the existing engine, NOT by PPF.

        Returns:
            DecisionResult with final state and entry permission.
        """
        # C11: novelty brake - O9=True -> forced IDLE, PPF disabled
        if obs.regime_novelty_flag:
            self._d2_bars = 0
            self._d3_bars = 0
            return DecisionResult(
                state=PPFState.D1_IDLE,
                rejection=TransitionOutcome.R1_REJECT,
                rejection_code=RejectionCode.NOVELTY_BRAKE,
                allow_entry=False,
            )

        # D1 -> D2: O1 >= similarity_min
        if obs.pattern_similarity_score < self._params.similarity_min:
            self._d2_bars = 0
            self._d3_bars = 0
            return DecisionResult(state=PPFState.D1_IDLE)

        # Reached D2 WATCH
        # D2 -> D3: O2 != 0
        if obs.projection_direction == 0:
            self._d2_bars += 1
            self._d3_bars = 0
            # Timeout check
            if self._d2_bars >= self._params.watch_timeout_bars:
                self._d2_bars = 0
                return DecisionResult(state=PPFState.D1_IDLE)
            return DecisionResult(state=PPFState.D2_WATCH)

        # Reached D3 CANDIDATE
        self._d2_bars = 0

        # D3 -> D4: 3-way alignment (corrected: no sign match required)
        # abs(I1) >= projection_bias_min AND I2 > 0 AND I3 > 0
        abs_i1 = abs(scores.projection_bias_score)
        cond_i1 = abs_i1 >= self._params.projection_bias_min
        cond_i2 = scores.trend_alignment_score > 0
        cond_i3 = scores.volume_confirmation_score > 0

        if not (cond_i1 and cond_i2 and cond_i3):
            self._d3_bars += 1
            # Determine specific rejection reason for logging
            rejection_code: Optional[RejectionCode] = None
            if not cond_i1:
                rejection_code = RejectionCode.CONSENSUS_LOW
            elif not cond_i2:
                rejection_code = RejectionCode.TREND_MISALIGN
            elif not cond_i3:
                rejection_code = RejectionCode.VOLUME_WEAK

            # Timeout check
            if self._d3_bars >= self._params.candidate_timeout_bars:
                self._d3_bars = 0
                return DecisionResult(state=PPFState.D1_IDLE)

            return DecisionResult(
                state=PPFState.D3_CANDIDATE,
                rejection_code=rejection_code,
            )

        # Reached D4 QUALIFIED
        self._d3_bars = 0

        # D4 -> D5: I4 > path_quality_min AND I5 >= rr_min
        cond_i4 = scores.path_quality_score > self._params.path_quality_min
        cond_i5 = scores.structure_rr_score >= self._params.rr_min

        if not cond_i4:
            return DecisionResult(
                state=PPFState.D1_IDLE,
                reached_state=PPFState.D4_QUALIFIED,
                rejection=TransitionOutcome.R1_REJECT,
                rejection_code=RejectionCode.PATH_QUALITY_FAIL,
            )

        if not cond_i5:
            return DecisionResult(
                state=PPFState.D1_IDLE,
                reached_state=PPFState.D4_QUALIFIED,
                rejection=TransitionOutcome.R1_REJECT,
                rejection_code=RejectionCode.RR_FAIL,
            )

        # Reached D5 ARMED

        # D5 -> D6: external risk filter pass
        # B2 resolved: failure -> R1 only (no D5 retention)
        if not risk_filter_pass:
            return DecisionResult(
                state=PPFState.D1_IDLE,
                reached_state=PPFState.D5_ARMED,
                rejection=TransitionOutcome.R1_REJECT,
                rejection_code=RejectionCode.RISK_FILTER_FAIL,
            )

        # Reached D6 EXECUTE_READY (ephemeral gate-pass)
        # B1 resolved: D6 is NOT terminal, valid this candle only
        return DecisionResult(
            state=PPFState.D6_EXECUTE_READY,
            allow_entry=True,
        )

    def reset(self) -> None:
        """Reset timeout counters. Called on candle boundaries."""
        self._d2_bars = 0
        self._d3_bars = 0
