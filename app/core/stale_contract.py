"""
K-Dexter Stale Contract — Central Stale Judgment Constants & Helpers

This module is the single source of truth for all stale-related constants,
band classifications, and terminal state definitions across the system.

All observation/simulation/decision layers MUST use these constants
instead of local definitions. This prevents drift between layers.

Design rules:
  - Read-only: no mutations, no writes, no state transitions
  - Constants only: threshold defaults, band multipliers, terminal states
  - Helpers only: band classification, terminal state lookup
  - Sealed ledger files (ActionLedger, ExecutionLedger, SubmitLedger)
    are NOT modified — this module mirrors and validates their values

Stale Definition:
  A proposal is "stale" when:
    1. It is NOT in a terminal state (BLOCKED/RECEIPTED/FAILED per tier)
    2. It has a created_at timestamp
    3. Its age exceeds the tier's stale_threshold
    4. It has NOT been receipted

Band Definition (calibrated 2026-03-31):
  - early    : age < 1.5x threshold  (just crossed threshold, may self-resolve)
  - review   : 1.5x <= age < 3.0x   (operator review recommended)
  - prolonged: age >= 3.0x           (extended stale, priority review)

Terminal State Exclusion:
  Proposals in terminal states are excluded from stale detection.
  Each tier has its own terminal state set, mirrored from
  the sealed Proposal._TERMINAL_STATES in each Ledger.

SYNC NOTE:
  If any Ledger's Proposal._TERMINAL_STATES changes,
  TERMINAL_STATES_BY_TIER here must be updated to match.
"""

from __future__ import annotations


# =========================================================================== #
# Stale Threshold Defaults (per tier)                                          #
# =========================================================================== #

# Default stale thresholds in seconds.
# These mirror the defaults in each sealed Ledger's __init__.
# Ledger files are sealed and not modified; these values must stay in sync.
STALE_THRESHOLD_DEFAULTS = {
    "agent": 600.0,  # ActionLedger default
    "execution": 300.0,  # ExecutionLedger default
    "submit": 180.0,  # SubmitLedger default
}


# =========================================================================== #
# Band Multipliers (calibrated 2026-03-31)                                     #
# =========================================================================== #

# Stale age expressed as multiplier of tier's stale_threshold.
#
#   < WATCH_UPPER  → WATCH   (early band, may self-resolve)
#   >= WATCH_UPPER → REVIEW  (review band, operator review needed)
#   >= PROLONGED   → REVIEW  (prolonged band, flagged in explanation)
#
# MANUAL is not age-driven — requires orphan intersection.
THRESHOLD_WATCH_UPPER = 1.5  # age < 1.5x → WATCH
THRESHOLD_PROLONGED = 3.0  # age >= 3.0x → REVIEW (prolonged flag)


# =========================================================================== #
# Terminal States by Tier                                                      #
# =========================================================================== #

# Mirrored from Proposal._TERMINAL_STATES in each sealed Ledger.
# SYNC NOTE: If any Ledger's _TERMINAL_STATES changes, update here.
TERMINAL_STATES_BY_TIER = {
    "agent": frozenset({"BLOCKED", "RECEIPTED", "FAILED"}),
    "execution": frozenset({"EXEC_BLOCKED", "EXEC_RECEIPTED", "EXEC_FAILED"}),
    "submit": frozenset({"SUBMIT_BLOCKED", "SUBMIT_RECEIPTED", "SUBMIT_FAILED"}),
}


# =========================================================================== #
# Helpers                                                                      #
# =========================================================================== #


def classify_stale_band(multiplier: float) -> str:
    """
    Classify stale age multiplier into named band.

    Bands:
      < 1.5x  → "early"     (just crossed threshold)
      1.5~3x  → "review"    (operator review band)
      >= 3x   → "prolonged" (extended stale, priority review)
    """
    if multiplier >= THRESHOLD_PROLONGED:
        return "prolonged"
    if multiplier >= THRESHOLD_WATCH_UPPER:
        return "review"
    return "early"


def is_terminal_state(status: str, tier: str) -> bool:
    """
    Check if a proposal status is terminal for the given tier.

    Terminal proposals are excluded from stale detection.
    """
    terminal_set = TERMINAL_STATES_BY_TIER.get(tier)
    if terminal_set is None:
        return False
    return status in terminal_set


def get_stale_threshold(tier: str) -> float:
    """
    Get default stale threshold for a tier.

    Returns the default threshold in seconds, or 600.0 if tier is unknown.
    """
    return STALE_THRESHOLD_DEFAULTS.get(tier, 600.0)
