"""PPF Gate interface and orchestration wrapper.

Authority: PPF-IMPLEMENTATION-001-CORRECTION-R1

Architecture (B3 resolved):
    PPF Gate sits OUTSIDE the execution engine as an orchestration wrapper.
    Execution engine files diff = 0 (C7).

    ┌─────────────────────────────────────────────┐
    │         Orchestration Wrapper (this file)    │
    │                                              │
    │  1. Existing engine -> entry candidate       │
    │  2. PPFGate.allow_entry(ppf_state) check     │
    │  3-a. True  -> engine.execute_order()        │
    │  3-b. False -> discard + L4 log              │
    │                                              │
    └─────────────────────────────────────────────┘
           │                        │
      Existing Engine (diff=0)  PPF Module (new)

Constitution enforced:
    E1: PPF is gate-only, never generates orders
    E2: Only EXECUTE_READY allows entry
    E3: No engine modification
    E4: No standalone entry
    E7: Novelty -> blocked
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

import numpy as np

from strategies.ppf.constants import PPFState, RejectionCode
from strategies.ppf.constitution import ConstitutionCheckResult, run_all_checks
from strategies.ppf.decision import DecisionResult, PPFStateMachine
from strategies.ppf.interpretation import InterpretationScores, compute_scores
from strategies.ppf.logging_schema import PPFLogEntry, build_log_entry, emit_log
from strategies.ppf.observation import ObservationFields, compute_observation
from strategies.ppf.parameters import PPFParameters

logger = logging.getLogger("ppf.gate")


class PPFGate:
    """PPF Gate - supplementary filter gate for the existing execution engine.

    This class is the ONLY entry point for PPF functionality. It:
    1. Computes observation fields (O1-O9)
    2. Computes interpretation scores (I1-I5)
    3. Evaluates the decision state machine (D1-D6, R1)
    4. Returns allow_entry (bool) to the orchestration wrapper
    5. Logs every evaluation (audit principle)

    PPF does NOT:
    - Generate orders (E1, C1)
    - Modify the execution engine (E3, C7)
    - Operate standalone (E4, C9)
    - Adapt parameters at runtime (C10)

    Fail-closed behavior:
    - Any error -> allow_entry = False
    - Missing data -> allow_entry = False
    - Constitution violation -> allow_entry = False
    - Novelty flag -> allow_entry = False
    """

    def __init__(
        self,
        params: PPFParameters,
        asset_timeframe_tag: str,
        engine_dir: Optional[str] = None,
        engine_checksums: Optional[dict[str, str]] = None,
    ) -> None:
        """Initialize PPF Gate.

        Args:
            params: Frozen PPF parameters for this market profile.
            asset_timeframe_tag: L5 tag, e.g. "binance:SOL/USDT:1h".
            engine_dir: Path to execution engine directory for C7 check.
            engine_checksums: Expected SHA256 checksums for C7 check.
        """
        self._params = params
        self._asset_tag = asset_timeframe_tag
        self._engine_dir = engine_dir
        self._engine_checksums = engine_checksums
        self._state_machine = PPFStateMachine(params)
        self._last_log: Optional[PPFLogEntry] = None
        self._active = True  # False if constitution violation detected

    @property
    def is_active(self) -> bool:
        """Whether PPF is active. False after constitution violation."""
        return self._active

    @property
    def last_log_entry(self) -> Optional[PPFLogEntry]:
        """Last emitted log entry (for testing/inspection)."""
        return self._last_log

    def evaluate(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        volumes: np.ndarray,
        risk_filter_pass: bool = False,
    ) -> bool:
        """Evaluate PPF gate for the current candle.

        This is the main entry point called by the orchestration wrapper.

        Args:
            highs: Full historical high prices (current bar at end).
            lows: Full historical low prices.
            closes: Full historical close prices.
            volumes: Full historical volumes.
            risk_filter_pass: Whether the external engine's risk filter
                approves this entry. Provided by existing engine, NOT PPF.

        Returns:
            True if entry is allowed (D6 EXECUTE_READY reached).
            False otherwise (fail-closed).
        """
        # Fail-closed: PPF deactivated by constitution violation
        if not self._active:
            logger.warning("PPF deactivated due to prior constitution violation")
            return False

        try:
            return self._evaluate_internal(highs, lows, closes, volumes, risk_filter_pass)
        except Exception as exc:
            # Fail-closed: any error -> deny entry
            logger.error(f"PPF evaluation error (fail-closed): {exc!r}")
            return False

    def _evaluate_internal(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        volumes: np.ndarray,
        risk_filter_pass: bool,
    ) -> bool:
        """Internal evaluation logic. Exceptions propagate to caller."""
        # Step 1: Compute observation fields (O1-O9)
        obs: ObservationFields = compute_observation(
            highs=highs,
            lows=lows,
            closes=closes,
            volumes=volumes,
            params=self._params,
        )

        # Step 2: Compute interpretation scores (I1-I5)
        scores: InterpretationScores = compute_scores(obs)

        # Step 3: Evaluate decision state machine
        result: DecisionResult = self._state_machine.evaluate(
            obs=obs,
            scores=scores,
            risk_filter_pass=risk_filter_pass,
        )

        # Step 4: Constitution check
        const_result: ConstitutionCheckResult = run_all_checks(
            params=self._params,
            regime_novelty_flag=obs.regime_novelty_flag,
            current_state=result.state,
            engine_dir=self._engine_dir,
            engine_checksums=self._engine_checksums,
        )

        if not const_result.passed:
            logger.error(
                f"Constitution violation detected: {const_result.details}. "
                f"PPF deactivated (fail-closed)."
            )
            self._active = False
            result = DecisionResult(
                state=PPFState.D1_IDLE,
                allow_entry=False,
            )

        # Step 5: Log (audit principle: every evaluation is logged)
        log_entry = build_log_entry(
            obs=obs,
            scores=scores,
            result=result,
            asset_timeframe_tag=self._asset_tag,
        )
        emit_log(log_entry)
        self._last_log = log_entry

        # Step 6: Return gate decision
        # E2: only EXECUTE_READY allows entry
        return result.allow_entry and result.state == PPFState.D6_EXECUTE_READY


class PPFOrchestrationWrapper:
    """Orchestration wrapper that connects PPF gate to existing engine.

    B3 resolved: This wrapper sits OUTSIDE the engine. The engine code
    is never modified (C7 diff=0). The wrapper:
    1. Asks the engine to generate an entry candidate
    2. Checks the PPF gate
    3. If approved, tells the engine to execute
    4. If denied, discards the candidate and logs

    This class is a template/reference implementation. Actual integration
    depends on the specific engine interface.
    """

    def __init__(
        self,
        ppf_gate: PPFGate,
        generate_candidate_fn: Callable[[], Optional[dict[str, Any]]],
        execute_order_fn: Callable[[dict[str, Any]], Any],
        risk_filter_fn: Callable[[], bool],
    ) -> None:
        """Initialize orchestration wrapper.

        Args:
            ppf_gate: The PPF gate instance.
            generate_candidate_fn: Function that asks the existing engine
                to generate an entry candidate. Returns dict or None.
            execute_order_fn: Function that tells the existing engine
                to execute an order. Takes the candidate dict.
            risk_filter_fn: Function that queries the existing engine's
                risk filter. Returns True if risk check passes.
        """
        self._gate = ppf_gate
        self._generate_candidate = generate_candidate_fn
        self._execute_order = execute_order_fn
        self._risk_filter = risk_filter_fn

    def process_candle(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        volumes: np.ndarray,
    ) -> Optional[dict[str, Any]]:
        """Process a single candle through the orchestration pipeline.

        Returns:
            The executed order dict if entry was allowed, None otherwise.
        """
        # Step 1: Ask existing engine for entry candidate
        candidate = self._generate_candidate()
        if candidate is None:
            return None  # No candidate from engine, nothing to gate

        # Step 2: Check risk filter (from existing engine, not PPF)
        risk_pass = self._risk_filter()

        # Step 3: Check PPF gate
        ppf_allows = self._gate.evaluate(
            highs=highs,
            lows=lows,
            closes=closes,
            volumes=volumes,
            risk_filter_pass=risk_pass,
        )

        # Step 4: Execute or discard
        if ppf_allows:
            logger.info("PPF gate: ALLOW - executing order")
            return self._execute_order(candidate)
        else:
            logger.info("PPF gate: DENY - discarding candidate")
            return None
