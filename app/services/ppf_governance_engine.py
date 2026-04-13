"""PPF Governance Engine — Phase B fail-closed rules (S3) + operational state machine (S4).

Combines:
  S3: Fail-closed rule set — each FC-0x check gates a specific pipeline step.
  S4: Operational state transition machine — enforces shadow→validation→paper ordering.

Design contract:
  - NO execution binding  (execution_binding = NONE)
  - NO promotion authority (promotion_open = FALSE)
  - NO auto-advance       (auto_advance = FORBIDDEN)
  - FC-07: LIVE mode PROHIBITED unconditionally (HARD_BLOCK, no override path)
  - FC-08: Paper requires VAL_PDC_002_ISSUED state AND GREEN tier
  - FC-10: Baseline immutable after freeze — tracked via state; no field updates allowed
           once state >= BASELINE_FROZEN

State pipeline (ordered):
  NOT_INITIALIZED → DATA_READY → PHASE_A_RUNNING → BASELINE_FROZEN
  → PHASE_B_COLLECTING → VALIDATION_READY → VAL_PDC_002_ISSUED

Minimum data thresholds (VAL-QTY-001):
  - MIN_BARS_FOR_VALIDATION = 336  (14 days × 24 hourly bars)
  - MIN_NOVELTY_EVENTS      = 10   (S2P-EI1)

Promotion tier traffic light:
  RED    — <5 novelty events or any critical failure
  YELLOW — 5-9 novelty events, no critical failure
  GREEN  — ≥10 novelty events, all checks passed
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class PPFGovernanceState(str, Enum):
    """PPF validation pipeline states."""

    NOT_INITIALIZED = "NOT_INITIALIZED"
    DATA_READY = "DATA_READY"              # OHLCV preflight passed
    PHASE_A_RUNNING = "PHASE_A_RUNNING"    # Backtest in progress
    BASELINE_FROZEN = "BASELINE_FROZEN"    # Baseline sealed
    PHASE_B_COLLECTING = "PHASE_B_COLLECTING"  # Live shadow accumulation
    VALIDATION_READY = "VALIDATION_READY"  # Minimum events + bars met
    VAL_PDC_002_ISSUED = "VAL_PDC_002_ISSUED"  # Comparator report issued


class PPFGovernanceTier(str, Enum):
    """Promotion tier (traffic light)."""

    RED = "RED"        # <5 events or critical failure
    YELLOW = "YELLOW"  # 5-9 events, partial evidence
    GREEN = "GREEN"    # ≥10 events, all checks passed


class PPFBlockLevel(str, Enum):
    """Block severity."""

    HARD_BLOCK = "HARD_BLOCK"                    # Cannot proceed under any circumstance
    SOFT_BLOCK = "SOFT_BLOCK"                    # Needs manual override
    EVIDENCE_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"  # Needs more data
    CLEAR = "CLEAR"                              # No block


# ---------------------------------------------------------------------------
# State transition table
# ---------------------------------------------------------------------------

# ALLOWED_TRANSITIONS[from_state] = [to_state, ...]
ALLOWED_TRANSITIONS: dict[PPFGovernanceState, list[PPFGovernanceState]] = {
    PPFGovernanceState.NOT_INITIALIZED: [
        PPFGovernanceState.DATA_READY,
    ],
    PPFGovernanceState.DATA_READY: [
        PPFGovernanceState.PHASE_A_RUNNING,
    ],
    PPFGovernanceState.PHASE_A_RUNNING: [
        PPFGovernanceState.BASELINE_FROZEN,
        PPFGovernanceState.DATA_READY,   # reset on failure
    ],
    PPFGovernanceState.BASELINE_FROZEN: [
        PPFGovernanceState.PHASE_B_COLLECTING,
    ],
    PPFGovernanceState.PHASE_B_COLLECTING: [
        PPFGovernanceState.VALIDATION_READY,
        PPFGovernanceState.BASELINE_FROZEN,  # reset
    ],
    PPFGovernanceState.VALIDATION_READY: [
        PPFGovernanceState.VAL_PDC_002_ISSUED,
    ],
    PPFGovernanceState.VAL_PDC_002_ISSUED: [],  # terminal
}

# Minimum data thresholds (VAL-QTY-001)
MIN_BARS_FOR_VALIDATION: int = 336   # 14 days × 24 hourly bars
MIN_NOVELTY_EVENTS: int = 10         # VAL-QTY-001 S2P-EI1

# Tier event thresholds
TIER_GREEN_MIN_EVENTS: int = 10
TIER_YELLOW_MIN_EVENTS: int = 5

# Unresolved rate ceiling before baseline freeze is blocked (FC-02)
MAX_UNRESOLVED_RATE_FOR_FREEZE: float = 0.05   # 5 %


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class PPFGovernanceEngine:
    """Enforces PPF validation pipeline state transitions and fail-closed rules.

    Fail-closed rules:
    - FC-01: Phase A cannot start without preflight PASS
    - FC-02: Baseline cannot freeze with unresolved_rate > 5%
    - FC-03: Phase B cannot start without frozen baseline
    - FC-04: Validation cannot proceed with < 336 bars (14 days)
    - FC-05: Validation cannot proceed with < 10 novelty events
    - FC-06: VAL-PDC-002 cannot issue if any metric out of tolerance
    - FC-07: LIVE mode PROHIBITED (HARD_BLOCK always)
    - FC-08: Paper mode requires VAL_PDC_002_ISSUED + GREEN tier
    - FC-09: Shadow must precede validation (ordering enforced by state machine)
    - FC-10: Baseline immutable after freeze (no field updates)

    Thread safety: this class is NOT thread-safe. Callers must synchronize
    access when shared across async tasks.
    """

    def __init__(self) -> None:
        self._state: PPFGovernanceState = PPFGovernanceState.NOT_INITIALIZED
        self._transition_log: list[dict] = []

    # ------------------------------------------------------------------
    # State accessors
    # ------------------------------------------------------------------

    @property
    def state(self) -> PPFGovernanceState:
        """Current pipeline state (read-only)."""
        return self._state

    # ------------------------------------------------------------------
    # Transition management
    # ------------------------------------------------------------------

    def can_transition(
        self, target: PPFGovernanceState
    ) -> tuple[bool, str | None]:
        """Check if a transition from current state to *target* is allowed.

        Returns
        -------
        (True, None)
            Transition is permitted by the transition table.
        (False, reason)
            Transition is not permitted; *reason* explains the block.
        """
        allowed_targets = ALLOWED_TRANSITIONS.get(self._state, [])

        if target not in allowed_targets:
            if self._state == PPFGovernanceState.VAL_PDC_002_ISSUED:
                reason = (
                    f"TERMINAL_STATE: current state {self._state.value} has no "
                    "allowed outgoing transitions"
                )
            else:
                allowed_names = [s.value for s in allowed_targets]
                reason = (
                    f"INVALID_TRANSITION: {self._state.value} → {target.value} "
                    f"is not in allowed transitions {allowed_names}"
                )
            return (False, reason)

        return (True, None)

    def transition(
        self, target: PPFGovernanceState, reason: str = ""
    ) -> bool:
        """Execute a state transition.

        Validates the transition against the allowed transition table, logs
        the event with a UTC timestamp, then updates internal state.

        Parameters
        ----------
        target:
            The target state to transition to.
        reason:
            Optional human-readable explanation for the transition (e.g.,
            "preflight passed", "baseline frozen with unresolved_rate=0.02").

        Returns
        -------
        bool
            True on success.

        Raises
        ------
        ValueError
            If the transition is not permitted by the state machine table.
        """
        allowed, block_reason = self.can_transition(target)
        if not allowed:
            logger.error(
                "ppf_governance_transition_blocked",
                from_state=self._state.value,
                to_state=target.value,
                block_reason=block_reason,
            )
            raise ValueError(
                f"PPFGovernanceEngine: transition blocked — {block_reason}"
            )

        from_state = self._state
        self._state = target

        entry: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "from_state": from_state.value,
            "to_state": target.value,
            "reason": reason,
        }
        self._transition_log.append(entry)

        logger.info(
            "ppf_governance_transition",
            from_state=from_state.value,
            to_state=target.value,
            reason=reason,
        )
        return True

    # ------------------------------------------------------------------
    # FC-0x check methods
    # ------------------------------------------------------------------

    def check_phase_a_ready(
        self, preflight_passed: bool
    ) -> tuple[PPFBlockLevel, str]:
        """FC-01: Check if Phase A backtest can start.

        Condition: OHLCV preflight must have passed.

        Parameters
        ----------
        preflight_passed:
            True if the OHLCV preflight check completed without errors
            (sufficient candle coverage, no gaps exceeding threshold).

        Returns
        -------
        (PPFBlockLevel, message)
        """
        if not preflight_passed:
            msg = (
                "FC-01_BLOCK: Phase A cannot start — OHLCV preflight has not "
                "passed. Run HistoryDataManager.preflight() and confirm "
                "coverage before proceeding."
            )
            logger.warning("ppf_governance_fc01_block")
            return (PPFBlockLevel.SOFT_BLOCK, msg)

        msg = "FC-01_CLEAR: OHLCV preflight passed — Phase A may start."
        return (PPFBlockLevel.CLEAR, msg)

    def check_baseline_freeze_ready(
        self, unresolved_rate: float
    ) -> tuple[PPFBlockLevel, str]:
        """FC-02: Check if baseline can be frozen.

        Condition: unresolved novelty event rate must be <= 5%.

        Parameters
        ----------
        unresolved_rate:
            Fraction of novelty events that are UNRESOLVED
            (unresolved_count / total_novelty_count).
            Must be in [0.0, 1.0].

        Returns
        -------
        (PPFBlockLevel, message)
        """
        if unresolved_rate < 0.0 or unresolved_rate > 1.0:
            msg = (
                f"FC-02_BLOCK: unresolved_rate={unresolved_rate:.4f} is outside "
                "the valid range [0.0, 1.0]. Cannot freeze baseline with "
                "invalid input."
            )
            logger.error("ppf_governance_fc02_invalid_rate", rate=unresolved_rate)
            return (PPFBlockLevel.SOFT_BLOCK, msg)

        if unresolved_rate > MAX_UNRESOLVED_RATE_FOR_FREEZE:
            msg = (
                f"FC-02_BLOCK: baseline cannot freeze — "
                f"unresolved_rate={unresolved_rate:.4f} exceeds maximum "
                f"{MAX_UNRESOLVED_RATE_FOR_FREEZE:.4f} (5%). Resolve outstanding "
                "novelty events before freezing."
            )
            logger.warning(
                "ppf_governance_fc02_block", unresolved_rate=unresolved_rate
            )
            return (PPFBlockLevel.SOFT_BLOCK, msg)

        msg = (
            f"FC-02_CLEAR: unresolved_rate={unresolved_rate:.4f} within limit — "
            "baseline may be frozen."
        )
        return (PPFBlockLevel.CLEAR, msg)

    def check_phase_b_ready(
        self, baseline_frozen: bool
    ) -> tuple[PPFBlockLevel, str]:
        """FC-03: Check if Phase B live shadow accumulation can start.

        Condition: a frozen baseline must exist. This is also enforced
        structurally by the state machine (BASELINE_FROZEN → PHASE_B_COLLECTING),
        but this method provides an explicit runtime guard for callers that
        bypass state machine transitions.

        Parameters
        ----------
        baseline_frozen:
            True if a PPFBacktestBaseline row has been persisted and the
            current governance state is at least BASELINE_FROZEN.

        Returns
        -------
        (PPFBlockLevel, message)
        """
        if not baseline_frozen:
            msg = (
                "FC-03_BLOCK: Phase B cannot start — no frozen baseline exists. "
                "Complete Phase A (PPFIntegratedBacktester.run()) and freeze the "
                "baseline before starting live shadow collection."
            )
            logger.warning("ppf_governance_fc03_block")
            return (PPFBlockLevel.SOFT_BLOCK, msg)

        # Also enforce state machine ordering (FC-09 shadow precedes validation)
        frozen_states = {
            PPFGovernanceState.BASELINE_FROZEN,
            PPFGovernanceState.PHASE_B_COLLECTING,
            PPFGovernanceState.VALIDATION_READY,
            PPFGovernanceState.VAL_PDC_002_ISSUED,
        }
        if self._state not in frozen_states:
            msg = (
                f"FC-03_BLOCK: Phase B cannot start — current state is "
                f"{self._state.value}, which precedes BASELINE_FROZEN. "
                "State machine ordering violated."
            )
            logger.warning(
                "ppf_governance_fc03_state_order_block", state=self._state.value
            )
            return (PPFBlockLevel.SOFT_BLOCK, msg)

        msg = "FC-03_CLEAR: frozen baseline confirmed — Phase B may start."
        return (PPFBlockLevel.CLEAR, msg)

    def check_validation_ready(
        self, bars_collected: int, novelty_events: int
    ) -> tuple[PPFBlockLevel, str]:
        """FC-04, FC-05: Check if validation can proceed.

        FC-04: bars_collected >= MIN_BARS_FOR_VALIDATION (336)
        FC-05: novelty_events >= MIN_NOVELTY_EVENTS (10)

        Both conditions must be satisfied simultaneously.

        Parameters
        ----------
        bars_collected:
            Number of hourly bars evaluated during Phase B live shadow.
        novelty_events:
            Number of novelty brake events recorded during Phase B.

        Returns
        -------
        (PPFBlockLevel, message)
            EVIDENCE_INSUFFICIENT when thresholds are not yet met.
            CLEAR when both thresholds are satisfied.
        """
        bars_ok = bars_collected >= MIN_BARS_FOR_VALIDATION
        events_ok = novelty_events >= MIN_NOVELTY_EVENTS

        if not bars_ok and not events_ok:
            msg = (
                f"FC-04+FC-05_BLOCK: validation cannot proceed — "
                f"bars_collected={bars_collected} < {MIN_BARS_FOR_VALIDATION} (FC-04) "
                f"AND novelty_events={novelty_events} < {MIN_NOVELTY_EVENTS} (FC-05). "
                "Continue Phase B shadow accumulation."
            )
            logger.info(
                "ppf_governance_validation_insufficient",
                bars_collected=bars_collected,
                novelty_events=novelty_events,
            )
            return (PPFBlockLevel.EVIDENCE_INSUFFICIENT, msg)

        if not bars_ok:
            msg = (
                f"FC-04_BLOCK: validation cannot proceed — "
                f"bars_collected={bars_collected} < {MIN_BARS_FOR_VALIDATION} "
                f"(need {MIN_BARS_FOR_VALIDATION - bars_collected} more bars, "
                f"~{(MIN_BARS_FOR_VALIDATION - bars_collected) / 24:.1f} days)."
            )
            logger.info(
                "ppf_governance_fc04_block",
                bars_collected=bars_collected,
                deficit=MIN_BARS_FOR_VALIDATION - bars_collected,
            )
            return (PPFBlockLevel.EVIDENCE_INSUFFICIENT, msg)

        if not events_ok:
            msg = (
                f"FC-05_BLOCK: validation cannot proceed — "
                f"novelty_events={novelty_events} < {MIN_NOVELTY_EVENTS} "
                f"(need {MIN_NOVELTY_EVENTS - novelty_events} more events)."
            )
            logger.info(
                "ppf_governance_fc05_block",
                novelty_events=novelty_events,
                deficit=MIN_NOVELTY_EVENTS - novelty_events,
            )
            return (PPFBlockLevel.EVIDENCE_INSUFFICIENT, msg)

        msg = (
            f"FC-04+FC-05_CLEAR: bars_collected={bars_collected} >= "
            f"{MIN_BARS_FOR_VALIDATION} AND novelty_events={novelty_events} >= "
            f"{MIN_NOVELTY_EVENTS} — validation may proceed."
        )
        return (PPFBlockLevel.CLEAR, msg)

    def check_val_pdc_002_ready(
        self, all_metrics_in_tolerance: bool
    ) -> tuple[PPFBlockLevel, str]:
        """FC-06: Check if VAL-PDC-002 report can be issued.

        Condition: all comparison metrics from PPFBacktestComparator must
        be within configured tolerance bands. A single out-of-tolerance
        metric is sufficient to block issuance.

        Parameters
        ----------
        all_metrics_in_tolerance:
            True if PPFComparisonReport.all_within_tolerance is True.
            This value comes directly from PPFBacktestComparator.compare().

        Returns
        -------
        (PPFBlockLevel, message)
        """
        if not all_metrics_in_tolerance:
            msg = (
                "FC-06_BLOCK: VAL-PDC-002 cannot issue — one or more comparison "
                "metrics are outside tolerance. Review PPFComparisonReport.metrics "
                "for details and address out-of-tolerance deviations."
            )
            logger.warning("ppf_governance_fc06_block")
            return (PPFBlockLevel.SOFT_BLOCK, msg)

        # State check: must be in VALIDATION_READY or later to issue report
        valid_states = {
            PPFGovernanceState.VALIDATION_READY,
            PPFGovernanceState.VAL_PDC_002_ISSUED,
        }
        if self._state not in valid_states:
            msg = (
                f"FC-06_BLOCK: VAL-PDC-002 cannot issue — current state is "
                f"{self._state.value}, which has not reached VALIDATION_READY. "
                "Minimum data requirements (FC-04, FC-05) must be satisfied first."
            )
            logger.warning(
                "ppf_governance_fc06_state_block", state=self._state.value
            )
            return (PPFBlockLevel.SOFT_BLOCK, msg)

        msg = (
            "FC-06_CLEAR: all metrics within tolerance and state is "
            f"{self._state.value} — VAL-PDC-002 may be issued."
        )
        return (PPFBlockLevel.CLEAR, msg)

    def check_live_entry(self) -> tuple[PPFBlockLevel, str]:
        """FC-07: LIVE entry is ALWAYS prohibited.

        This block is unconditional — no override path exists.
        PPF production authorization requires a separate governance change
        request and is NOT enabled in this codebase.

        Returns
        -------
        (HARD_BLOCK, reason)
            Always returns HARD_BLOCK. No conditions can clear this check.
        """
        return (
            PPFBlockLevel.HARD_BLOCK,
            "LIVE_ENTRY_PROHIBITED: PPF live mode not authorized",
        )

    def check_paper_entry(
        self, tier: PPFGovernanceTier
    ) -> tuple[PPFBlockLevel, str]:
        """FC-08: Paper mode entry check.

        Both conditions must hold simultaneously:
          1. Current state must be VAL_PDC_002_ISSUED
          2. Tier must be GREEN

        Parameters
        ----------
        tier:
            Promotion tier as computed by compute_tier().

        Returns
        -------
        (PPFBlockLevel, message)
        """
        state_ok = self._state == PPFGovernanceState.VAL_PDC_002_ISSUED
        tier_ok = tier == PPFGovernanceTier.GREEN

        if not state_ok and not tier_ok:
            msg = (
                f"FC-08_BLOCK: paper entry denied — state={self._state.value} "
                f"(need VAL_PDC_002_ISSUED) AND tier={tier.value} (need GREEN). "
                "Both conditions must be satisfied."
            )
            logger.warning(
                "ppf_governance_fc08_block_both",
                state=self._state.value,
                tier=tier.value,
            )
            return (PPFBlockLevel.HARD_BLOCK, msg)

        if not state_ok:
            msg = (
                f"FC-08_BLOCK: paper entry denied — state={self._state.value} "
                f"(need VAL_PDC_002_ISSUED). VAL-PDC-002 report must be issued "
                "before paper trading is authorized."
            )
            logger.warning(
                "ppf_governance_fc08_block_state", state=self._state.value
            )
            return (PPFBlockLevel.HARD_BLOCK, msg)

        if not tier_ok:
            msg = (
                f"FC-08_BLOCK: paper entry denied — tier={tier.value} "
                "(need GREEN). Minimum 10 novelty events with all checks passed "
                "is required for paper authorization."
            )
            logger.warning(
                "ppf_governance_fc08_block_tier", tier=tier.value
            )
            return (PPFBlockLevel.HARD_BLOCK, msg)

        msg = (
            f"FC-08_CLEAR: paper entry authorized — state={self._state.value}, "
            f"tier={tier.value}."
        )
        logger.info("ppf_governance_fc08_clear", tier=tier.value)
        return (PPFBlockLevel.CLEAR, msg)

    # ------------------------------------------------------------------
    # Tier computation
    # ------------------------------------------------------------------

    def compute_tier(
        self, novelty_events: int, all_checks_passed: bool
    ) -> PPFGovernanceTier:
        """Compute promotion tier based on evidence volume and check outcomes.

        Traffic-light logic:
          RED    — novelty_events < 5  OR  not all_checks_passed (critical failure)
          YELLOW — 5 <= novelty_events < 10  AND  all_checks_passed (partial evidence)
          GREEN  — novelty_events >= 10  AND  all_checks_passed (full evidence)

        Parameters
        ----------
        novelty_events:
            Number of novelty brake events accumulated during Phase B.
        all_checks_passed:
            True if all comparison metrics are within tolerance and no
            insufficiency reasons block promotion.

        Returns
        -------
        PPFGovernanceTier
        """
        if novelty_events < TIER_YELLOW_MIN_EVENTS or not all_checks_passed:
            # RED: insufficient evidence or critical failure
            tier = PPFGovernanceTier.RED
        elif novelty_events < TIER_GREEN_MIN_EVENTS:
            # YELLOW: 5-9 events, no critical failure
            tier = PPFGovernanceTier.YELLOW
        else:
            # GREEN: ≥10 events and all checks passed
            tier = PPFGovernanceTier.GREEN

        logger.debug(
            "ppf_governance_compute_tier",
            novelty_events=novelty_events,
            all_checks_passed=all_checks_passed,
            tier=tier.value,
        )
        return tier

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_transition_log(self) -> list[dict]:
        """Return full transition history as a list of immutable snapshots.

        Each entry contains:
          - timestamp (ISO-8601 UTC)
          - from_state
          - to_state
          - reason
        """
        # Return a shallow copy to prevent external mutation of internal log
        return list(self._transition_log)

    def get_status_summary(self) -> dict:
        """Return current state, active blocks, and summary metrics.

        Performs a lightweight scan of block conditions based on current state.
        Does NOT perform full FC-0x checks (those require caller-supplied inputs).

        Returns
        -------
        dict with keys:
          state            — current PPFGovernanceState value string
          transition_count — number of completed transitions
          terminal         — True if state is VAL_PDC_002_ISSUED
          allowed_next     — list of allowed next state value strings
          live_entry_block — always HARD_BLOCK (FC-07)
          paper_entry_note — note about paper entry requirements
        """
        allowed_next = [
            s.value for s in ALLOWED_TRANSITIONS.get(self._state, [])
        ]
        is_terminal = self._state == PPFGovernanceState.VAL_PDC_002_ISSUED

        # FC-07 is always active
        live_block_level, live_block_msg = self.check_live_entry()

        paper_note: str
        if self._state == PPFGovernanceState.VAL_PDC_002_ISSUED:
            paper_note = (
                "State is VAL_PDC_002_ISSUED — paper entry depends on tier. "
                "Call check_paper_entry(tier) with compute_tier() result."
            )
        else:
            paper_note = (
                f"Paper entry requires VAL_PDC_002_ISSUED state (current: "
                f"{self._state.value}). FC-08 will HARD_BLOCK until report is issued."
            )

        return {
            "state": self._state.value,
            "transition_count": len(self._transition_log),
            "terminal": is_terminal,
            "allowed_next": allowed_next,
            "live_entry_block": live_block_level.value,
            "live_entry_block_msg": live_block_msg,
            "paper_entry_note": paper_note,
        }
