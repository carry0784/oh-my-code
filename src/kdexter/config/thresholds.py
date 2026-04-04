"""
Threshold Registry — K-Dexter AOS v4

Central definition of the 3 quantitative thresholds required for v4.
Previously Open Questions OQ-4, OQ-5, OQ-6 in governance_layer_map.md.

All values carry:
  - Rationale: why this number
  - Source: how it was derived
  - Review trigger: condition that should prompt re-evaluation
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Final


# ─────────────────────────────────────────────────────────────────────────── #
# OQ-4 resolved: drift_high_threshold
# ─────────────────────────────────────────────────────────────────────────── #

DRIFT_HIGH_THRESHOLD: Final[float] = 0.35
"""
Intent drift score above which execution is BLOCKED (L15 Intent Drift Engine).

Scale:  0.0 = current behavior identical to original intent
        1.0 = completely diverged from original intent

Value:  0.35 (35% divergence threshold)

Rationale:
  - Below 0.15: normal strategy micro-adjustments, no action needed
  - 0.15~0.35:  noticeable drift, warn but allow execution (DEGRADED trust zone)
  - Above 0.35: material divergence from user intent — block until reviewed
  - Above 0.60: would be considered CRITICAL drift, but 0.35 chosen conservatively
    to catch problems early before they compound

Source:
  Conservative first-pass value. Chosen to minimize false negatives (missed real
  drift) at the cost of some false positives (minor drift flagged). Tune upward
  if operational data shows excessive BLOCKED events.

Review trigger:
  > 3 BLOCKED events per week due to DRIFT → consider raising to 0.40
  Any live-trading loss attributable to undetected drift → lower to 0.25
"""

DRIFT_WARN_THRESHOLD: Final[float] = 0.15
"""
Drift score above which a warning is logged but execution is not blocked.
Between DRIFT_WARN_THRESHOLD and DRIFT_HIGH_THRESHOLD: monitor only.
"""


# ─────────────────────────────────────────────────────────────────────────── #
# OQ-5 resolved: trust_decay_function
# ─────────────────────────────────────────────────────────────────────────── #

# Decision: EVENT-BASED decay with slow linear background
# Rationale: Time-only decay punishes reliable but infrequently-used components.
#            Event-based decay is proportional to actual failure history.
#            Linear background prevents permanently-trusted stale components.

TRUST_DECAY_BACKGROUND_RATE: Final[float] = 0.002
"""
Background linear decay rate: score units per hour.
Applied continuously regardless of events.

Value: 0.002/hour = 4.8% per 100 hours ≈ ~2% per day
A perfectly healthy component stays TRUSTED (≥0.8) for ~100 hours without
any success events — appropriate for daily-active trading systems.
"""

TRUST_DECAY_ON_CRITICAL: Final[float] = 0.40
"""Step-down applied to trust score on CRITICAL failure event."""

TRUST_DECAY_ON_HIGH: Final[float] = 0.20
"""Step-down applied to trust score on HIGH failure event."""

TRUST_DECAY_ON_MEDIUM: Final[float] = 0.05
"""Step-down applied to trust score on MEDIUM failure event."""

TRUST_RECOVERY_ON_SUCCESS: Final[float] = 0.10
"""Step-up applied to trust score on successful execution."""

TRUST_RECOVERY_ON_RECOVERY_COMPLETE: Final[float] = 0.25
"""Step-up applied after Recovery Loop successfully completes for this component."""

# Trust score → TrustStateEnum boundary mapping
# Must be consistent with trust_state.py _update_state_from_score()
TRUST_BOUNDARY_TRUSTED: Final[float] = 0.80
TRUST_BOUNDARY_DEGRADED: Final[float] = 0.60
TRUST_BOUNDARY_UNRELIABLE: Final[float] = 0.40
TRUST_BOUNDARY_DECAYING: Final[float] = 0.20
TRUST_BOUNDARY_STALE: Final[float] = 0.01  # > 0.0 but below DECAYING

"""
Trust decay function summary:

  score(t+Δt) = score(t)
                - TRUST_DECAY_BACKGROUND_RATE * Δt_hours
                - Σ failure_step_downs(events in Δt)
                + Σ success_step_ups(events in Δt)
                clamped to [0.0, 1.0]

Review trigger:
  > 5 components hit ISOLATED within 30 days → background rate too aggressive,
    consider lowering TRUST_DECAY_BACKGROUND_RATE to 0.001
  Strategy runs with UNRELIABLE components allowed → review boundaries
"""


# ─────────────────────────────────────────────────────────────────────────── #
# OQ-6 resolved: loop_count ceilings
# ─────────────────────────────────────────────────────────────────────────── #


@dataclass(frozen=True)
class LoopCountCeiling:
    """Max allowed loop activations within the specified window."""

    per_incident: int  # max runs per single failure incident / session
    per_day: int  # max runs per calendar day
    per_week: int  # max runs per calendar week


LOOP_COUNT_CEILINGS: Final[dict[str, LoopCountCeiling]] = {
    "RECOVERY": LoopCountCeiling(
        per_incident=3,
        per_day=10,
        per_week=30,
    ),
    "MAIN": LoopCountCeiling(
        per_incident=10_000,  # effectively unlimited — it's the heartbeat
        per_day=10_000,
        per_week=70_000,
    ),
    "SELF_IMPROVEMENT": LoopCountCeiling(
        per_incident=3,
        per_day=5,
        per_week=15,
    ),
    "EVOLUTION": LoopCountCeiling(
        per_incident=1,
        per_day=2,
        per_week=3,
    ),
}
"""
Loop count ceiling rationale:

RECOVERY  per_incident=3:
  If 3 recovery attempts on the same incident all fail → Human Override required.
  3 attempts covers: (1) transient fix, (2) rollback, (3) emergency patch.
  4th attempt without Human review would be irrational repetition (Forbidden: repeat failure).

SELF_IMPROVEMENT  per_day=5:
  Each cycle costs 6~10 LLM calls × $0.01~0.05 = ~$0.50 per run.
  5/day = max ~$2.50/day improvement cost.
  More than 5 self-improvement runs in a day suggests the system is thrashing.

EVOLUTION  per_week=3:
  Evolution changes rule structure — high risk of compounding errors.
  3/week = one major structural evolution every ~2.3 days maximum.
  Fewer than 3/week is expected in stable operation.

Review trigger:
  Recovery per_incident ceiling hit > 2x/week → investigate root cause depth
  Evolution ceiling hit → review if Merge Gate criteria are too permissive
"""


# ─────────────────────────────────────────────────────────────────────────── #
# Convenience accessor
# ─────────────────────────────────────────────────────────────────────────── #


def get_loop_ceiling(loop_name: str) -> LoopCountCeiling:
    """
    Returns LoopCountCeiling for a given loop name.
    Raises KeyError if loop_name not registered.
    """
    return LOOP_COUNT_CEILINGS[loop_name.upper()]
