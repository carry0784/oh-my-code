"""
K-Dexter Observation Summary Service

Aggregates stale/orphan/cleanup simulation results into a single
operator-readable summary with pressure levels and priority ranking.

Read-only observation layer. NEVER writes to any Ledger.
NEVER deletes, transitions, or executes any cleanup action.
All output is advisory — simulation only.

Safety labels (always True):
  read_only          — no write operations
  simulation_only    — no cleanup executed
  no_action_executed — no state transitions triggered

Data sources:
  - simulate_cleanup() → CleanupSimulationReport
  - detect_orphans()   → OrphanReport
  - Ledger.get_board() → stale_count per tier
  Only public read APIs. Never accesses _proposals directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional, TYPE_CHECKING

from app.services.cleanup_simulation_service import (
    simulate_cleanup,
    CleanupSimulationReport,
    ACTION_MANUAL,
    ACTION_REVIEW,
    ACTION_WATCH,
)
from app.services.orphan_detection_service import detect_orphans

if TYPE_CHECKING:
    from app.agents.action_ledger import ActionLedger
    from app.services.execution_ledger import ExecutionLedger
    from app.services.submit_ledger import SubmitLedger


# -- Constants -------------------------------------------------------------- #

PRESSURE_LOW = "LOW"
PRESSURE_MODERATE = "MODERATE"
PRESSURE_HIGH = "HIGH"
PRESSURE_CRITICAL = "CRITICAL"


# -- Data classes ----------------------------------------------------------- #


@dataclass
class ObservationSummary:
    """
    Aggregated observation summary for operator dashboard.

    Read-only observation. Simulation only. No action executed.
    """

    # -- Pressure --
    cleanup_pressure: str = PRESSURE_LOW

    # -- Counts --
    stale_total: int = 0
    orphan_total: int = 0
    candidate_total: int = 0

    # -- By-tier stale distribution --
    stale_by_tier: dict = field(default_factory=dict)

    # -- By-reason x by-action cross table --
    reason_action_matrix: list = field(default_factory=list)

    # -- Top priority items (max 5) --
    top_priority_candidates: list = field(default_factory=list)

    # -- Safety labels (always True — read-only observation) --
    read_only: bool = True
    simulation_only: bool = True
    no_action_executed: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    def to_schema(self):
        """Convert to typed Pydantic schema (ObservationSummarySchema)."""
        from app.schemas.observation_summary_schema import (
            ObservationSummarySchema,
            ObservationSafety,
            ReasonActionEntry,
            TopPriorityCandidate,
        )

        return ObservationSummarySchema(
            cleanup_pressure=self.cleanup_pressure,
            stale_total=self.stale_total,
            orphan_total=self.orphan_total,
            candidate_total=self.candidate_total,
            stale_by_tier=dict(self.stale_by_tier),
            reason_action_matrix=[
                ReasonActionEntry(**entry) for entry in self.reason_action_matrix
            ],
            top_priority_candidates=[
                TopPriorityCandidate(**entry) for entry in self.top_priority_candidates
            ],
            safety=ObservationSafety(
                read_only=True,
                simulation_only=True,
                no_action_executed=True,
            ),
        )


# -- Core logic ------------------------------------------------------------- #


def _determine_pressure(
    cleanup_report: CleanupSimulationReport,
) -> str:
    """
    Determine cleanup pressure level from simulation results.

    Rules:
      LOW      — candidates == 0 or all WATCH
      MODERATE — REVIEW exists, no MANUAL
      HIGH     — MANUAL exists, ratio < 50%
      CRITICAL — MANUAL ratio >= 50% or total_candidates >= 10
    """
    total = cleanup_report.total_candidates
    if total == 0:
        return PRESSURE_LOW

    manual_count = cleanup_report.by_action_class.get(ACTION_MANUAL, 0)
    review_count = cleanup_report.by_action_class.get(ACTION_REVIEW, 0)

    # CRITICAL: MANUAL >= 50% of total, or total >= 10
    if total >= 10:
        return PRESSURE_CRITICAL
    if manual_count > 0 and (manual_count / total) >= 0.5:
        return PRESSURE_CRITICAL

    # HIGH: MANUAL exists but < 50%
    if manual_count > 0:
        return PRESSURE_HIGH

    # MODERATE: REVIEW exists, no MANUAL
    if review_count > 0:
        return PRESSURE_MODERATE

    # LOW: only WATCH or INFO
    return PRESSURE_LOW


def _build_reason_action_matrix(
    cleanup_report: CleanupSimulationReport,
) -> list[dict]:
    """
    Build reason × action cross table from candidates.

    Returns list of {"reason": str, "action": str, "count": int}.
    """
    cross: dict[tuple[str, str], int] = {}
    for c in cleanup_report.candidates:
        key = (c.get("reason_code", ""), c.get("action_class", ""))
        cross[key] = cross.get(key, 0) + 1

    return [
        {"reason": reason, "action": action, "count": count}
        for (reason, action), count in sorted(cross.items())
    ]


def _select_top_priority(
    cleanup_report: CleanupSimulationReport,
    limit: int = 5,
) -> list[dict]:
    """
    Select top priority candidates for operator attention.

    Sort order:
      1. MANUAL_CLEANUP_CANDIDATE first
      2. REVIEW second
      3. Within same class: higher stale_age_seconds first
    Max 5 items.
    """
    _ACTION_PRIORITY = {ACTION_MANUAL: 0, ACTION_REVIEW: 1, ACTION_WATCH: 2}

    candidates = list(cleanup_report.candidates)
    candidates.sort(
        key=lambda c: (
            _ACTION_PRIORITY.get(c.get("action_class", ""), 99),
            -c.get("stale_age_seconds", 0),
        )
    )
    return candidates[:limit]


def _collect_stale_by_tier(
    action_ledger,
    execution_ledger,
    submit_ledger,
) -> dict[str, int]:
    """Collect stale_count from each tier's get_board()."""
    result: dict[str, int] = {}
    for ledger, tier_name in [
        (action_ledger, "agent"),
        (execution_ledger, "execution"),
        (submit_ledger, "submit"),
    ]:
        if ledger is not None:
            try:
                board = ledger.get_board()
                result[tier_name] = board.get("stale_count", 0)
            except Exception:
                result[tier_name] = 0
        else:
            result[tier_name] = 0
    return result


def build_observation_summary(
    action_ledger: Optional[ActionLedger] = None,
    execution_ledger: Optional[ExecutionLedger] = None,
    submit_ledger: Optional[SubmitLedger] = None,
) -> ObservationSummary:
    """
    Build unified observation summary from all observation layers.

    Read-only: only calls get_board(), simulate_cleanup(), detect_orphans().
    Never writes, deletes, or transitions any proposal.

    Returns ObservationSummary with pressure, distributions, and top priorities.
    """
    # -- Collect data from observation layers ------------------------------ #
    cleanup_report = simulate_cleanup(action_ledger, execution_ledger, submit_ledger)
    orphan_report = detect_orphans(action_ledger, execution_ledger, submit_ledger)
    stale_by_tier = _collect_stale_by_tier(
        action_ledger,
        execution_ledger,
        submit_ledger,
    )

    # -- Build summary ----------------------------------------------------- #
    pressure = _determine_pressure(cleanup_report)
    matrix = _build_reason_action_matrix(cleanup_report)
    top_priority = _select_top_priority(cleanup_report)

    return ObservationSummary(
        cleanup_pressure=pressure,
        stale_total=sum(stale_by_tier.values()),
        orphan_total=orphan_report.total_cross_tier_orphan_count,
        candidate_total=cleanup_report.total_candidates,
        stale_by_tier=stale_by_tier,
        reason_action_matrix=matrix,
        top_priority_candidates=top_priority,
        # Safety labels — always enforced
        read_only=True,
        simulation_only=True,
        no_action_executed=True,
    )
