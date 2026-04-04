"""
K-Dexter Cleanup Simulation Service

Read-only simulation layer that classifies stale/orphan proposals as cleanup
candidates and assigns operator action recommendations.

NEVER writes to any Ledger. NEVER deletes or transitions proposals.
Simulation only — all output is advisory.

Operator Action Classes:
  INFO                     — Normal, no action needed
  WATCH                    — Observe, may self-resolve
  REVIEW                   — Operator confirmation needed
  MANUAL_CLEANUP_CANDIDATE — Manual cleanup candidate, operator decides

Reason Codes:
  STALE_AGENT              — Agent tier stale proposal
  STALE_EXECUTION          — Execution tier stale proposal
  STALE_SUBMIT             — Submit tier stale proposal
  ORPHAN_EXEC_PARENT       — Execution: agent_proposal_id missing
  ORPHAN_SUBMIT_PARENT     — Submit: execution_proposal_id missing
  STALE_AND_ORPHAN         — Both stale and orphan

Data access:
  - Ledger.get_proposals() + Proposal.is_stale() for stale detection
  - detect_orphans() for orphan detection
  Only public read APIs. Never accesses _proposals directly.

Safety:
  - Read-only: never calls propose_and_guard, record_receipt, transition_to
  - No deletion, no state mutation, no side-effects
  - write_impact always 0, terminal_impact always 0
  - simulation_only always True
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from app.services.orphan_detection_service import detect_orphans
from app.core.stale_contract import (
    THRESHOLD_WATCH_UPPER,
    THRESHOLD_PROLONGED,
    TERMINAL_STATES_BY_TIER,
    classify_stale_band as _classify_stale_band,
)

if TYPE_CHECKING:
    from app.agents.action_ledger import ActionLedger
    from app.services.execution_ledger import ExecutionLedger
    from app.services.submit_ledger import SubmitLedger


# -- Constants -------------------------------------------------------------- #

# Standard Operator Action Classes
ACTION_INFO = "INFO"
ACTION_WATCH = "WATCH"
ACTION_REVIEW = "REVIEW"
ACTION_MANUAL = "MANUAL_CLEANUP_CANDIDATE"

# Operator posture descriptions (simulation only — not execution commands)
ACTION_POSTURE = {
    ACTION_INFO: "No action needed. Normal state.",
    ACTION_WATCH: "Observe at next review cycle. May self-resolve.",
    ACTION_REVIEW: "Operator review needed. Manual judgment required.",
    ACTION_MANUAL: "Manual cleanup candidate. Operator decides whether to act.",
}

# Alias for internal use — canonical source is stale_contract
_TERMINAL_STATES_BY_TIER = TERMINAL_STATES_BY_TIER

# Standard Reason Codes (6 types)
REASON_STALE_AGENT = "STALE_AGENT"
REASON_STALE_EXECUTION = "STALE_EXECUTION"
REASON_STALE_SUBMIT = "STALE_SUBMIT"
REASON_ORPHAN_EXEC_PARENT = "ORPHAN_EXEC_PARENT"
REASON_ORPHAN_SUBMIT_PARENT = "ORPHAN_SUBMIT_PARENT"
REASON_STALE_AND_ORPHAN = "STALE_AND_ORPHAN"

_VALID_REASON_CODES = frozenset({
    REASON_STALE_AGENT,
    REASON_STALE_EXECUTION,
    REASON_STALE_SUBMIT,
    REASON_ORPHAN_EXEC_PARENT,
    REASON_ORPHAN_SUBMIT_PARENT,
    REASON_STALE_AND_ORPHAN,
})


# -- Data classes ----------------------------------------------------------- #

@dataclass
class CleanupCandidate:
    """Single cleanup candidate with action recommendation (simulation only)."""
    proposal_id: str
    tier: str                          # "agent" | "execution" | "submit"
    action_class: str                  # ACTION_WATCH | ACTION_REVIEW | ACTION_MANUAL
    reason_code: str                   # one of _VALID_REASON_CODES
    is_stale: bool
    is_orphan: bool
    stale_age_seconds: float = 0.0     # 0.0 if not stale
    current_status: str = ""
    explanation: str = ""              # Human-readable reason for this classification

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CleanupSimulationReport:
    """Cleanup simulation result — advisory only, never executed."""
    total_candidates: int = 0
    by_tier: dict = field(default_factory=dict)
    by_action_class: dict = field(default_factory=dict)
    by_reason: dict = field(default_factory=dict)
    candidates: list[dict] = field(default_factory=list)
    write_impact: int = 0              # Always 0 — write forbidden
    terminal_impact: int = 0           # Always 0 — terminal change forbidden
    simulation_only: bool = True       # Always True

    def to_dict(self) -> dict:
        return asdict(self)


# -- Core logic ------------------------------------------------------------- #

def _determine_action_class(
    is_stale: bool,
    is_orphan: bool,
    stale_age_seconds: float,
    stale_threshold: float,
) -> str:
    """
    Determine operator action class based on stale/orphan status.

    Rules (calibrated 2026-03-31):
      stale only (age < 1.5x threshold)  → WATCH
      stale only (age >= 1.5x threshold) → REVIEW
      orphan only                        → REVIEW
      stale + orphan                     → MANUAL_CLEANUP_CANDIDATE

    Band boundaries defined by THRESHOLD_WATCH_UPPER (1.5x).
    """
    if is_stale and is_orphan:
        return ACTION_MANUAL
    if is_orphan:
        return ACTION_REVIEW
    if is_stale:
        if stale_age_seconds >= THRESHOLD_WATCH_UPPER * stale_threshold:
            return ACTION_REVIEW
        return ACTION_WATCH
    return ACTION_INFO


def _determine_reason_code(
    tier: str,
    is_stale: bool,
    is_orphan: bool,
) -> str:
    """Determine standard reason code."""
    if is_stale and is_orphan:
        return REASON_STALE_AND_ORPHAN
    if is_orphan:
        if tier == "execution":
            return REASON_ORPHAN_EXEC_PARENT
        return REASON_ORPHAN_SUBMIT_PARENT
    if is_stale:
        if tier == "agent":
            return REASON_STALE_AGENT
        if tier == "execution":
            return REASON_STALE_EXECUTION
        return REASON_STALE_SUBMIT
    return REASON_STALE_AGENT  # fallback, should not reach


def _collect_stale_candidates(
    ledger,
    tier_name: str,
    threshold: float,
) -> list[dict]:
    """
    Collect stale proposals from a single ledger.

    Mirrors Proposal.is_stale() logic exactly:
      1. Skip terminal states (BLOCKED/RECEIPTED/FAILED per tier)
      2. Skip proposals with receipt
      3. Skip proposals without created_at
      4. Only include if age > threshold

    SYNC NOTE: This logic must stay aligned with Proposal.is_stale().
    If is_stale() criteria change, update this function accordingly.
    """
    results = []
    terminal_states = _TERMINAL_STATES_BY_TIER.get(tier_name, frozenset())
    try:
        now = datetime.now(timezone.utc)
        proposals = ledger.get_proposals()
        for p in proposals:
            proposal_id = p.get("proposal_id", "")
            status = p.get("status", "")
            created_at_str = p.get("created_at", "")

            # Mirror is_stale() rule 1: terminal states are never stale
            if status in terminal_states:
                continue

            # Mirror is_stale() rule 2: receipted proposals are never stale
            if p.get("receipt") is not None:
                continue

            # Mirror is_stale() rule 3: no created_at → cannot determine age
            if not created_at_str:
                continue

            try:
                created = datetime.fromisoformat(created_at_str)
                age = (now - created).total_seconds()
            except (ValueError, TypeError):
                continue

            # Mirror is_stale() rule 4: age > threshold
            if age > threshold:
                results.append({
                    "proposal_id": proposal_id,
                    "tier": tier_name,
                    "stale_age_seconds": age,
                    "status": status,
                    "threshold": threshold,
                })
    except Exception:
        pass
    return results


def _build_explanation(
    action_class: str,
    reason_code: str,
    is_stale: bool,
    is_orphan: bool,
    stale_age_seconds: float,
    threshold: float,
    tier: str,
) -> str:
    """Build human-readable explanation for operator (simulation only)."""
    parts = []
    if is_stale and is_orphan:
        multiplier = f"{stale_age_seconds / threshold:.1f}x" if threshold > 0 else "N/A"
        parts.append(
            f"Stale ({multiplier} threshold) and orphan (missing parent) "
            f"in {tier} tier."
        )
    elif is_stale:
        multiplier_val = stale_age_seconds / threshold if threshold > 0 else 0
        multiplier = f"{multiplier_val:.1f}x" if threshold > 0 else "N/A"
        band = _classify_stale_band(multiplier_val)
        parts.append(
            f"Stale for {int(stale_age_seconds)}s ({multiplier} threshold, "
            f"band={band}) in {tier} tier."
        )
    elif is_orphan:
        parts.append(f"Orphan in {tier} tier: parent reference not found in upstream ledger.")

    posture = ACTION_POSTURE.get(action_class, "")
    if posture:
        parts.append(f"Posture: {posture}")

    return " ".join(parts)


def simulate_cleanup(
    action_ledger: Optional[ActionLedger] = None,
    execution_ledger: Optional[ExecutionLedger] = None,
    submit_ledger: Optional[SubmitLedger] = None,
    agent_stale_threshold: float = 600.0,
    execution_stale_threshold: float = 300.0,
    submit_stale_threshold: float = 180.0,
) -> CleanupSimulationReport:
    """
    Simulate cleanup by classifying stale/orphan proposals as candidates.

    Read-only: only calls get_proposals() and detect_orphans().
    Never writes, deletes, or transitions any proposal.

    Returns CleanupSimulationReport with candidates and aggregated stats.
    """
    report = CleanupSimulationReport()

    # -- Step 1: Collect stale proposals ----------------------------------- #
    stale_map: dict[str, dict] = {}  # proposal_id -> stale info

    if action_ledger is not None:
        for item in _collect_stale_candidates(action_ledger, "agent", agent_stale_threshold):
            stale_map[item["proposal_id"]] = item

    if execution_ledger is not None:
        for item in _collect_stale_candidates(execution_ledger, "execution", execution_stale_threshold):
            stale_map[item["proposal_id"]] = item

    if submit_ledger is not None:
        for item in _collect_stale_candidates(submit_ledger, "submit", submit_stale_threshold):
            stale_map[item["proposal_id"]] = item

    # -- Step 2: Collect orphan proposals ---------------------------------- #
    orphan_report = detect_orphans(action_ledger, execution_ledger, submit_ledger)
    orphan_map: dict[str, dict] = {}  # proposal_id -> orphan info

    for o in orphan_report.execution_orphans:
        orphan_map[o["proposal_id"]] = {
            "tier": "execution",
            "status": o.get("current_status", ""),
        }

    for o in orphan_report.submit_orphans:
        orphan_map[o["proposal_id"]] = {
            "tier": "submit",
            "status": o.get("current_status", ""),
        }

    # -- Step 3: Union stale + orphan → candidates ------------------------- #
    all_candidate_ids = set(stale_map.keys()) | set(orphan_map.keys())

    tier_counts: dict[str, int] = {}
    action_counts: dict[str, int] = {}
    reason_counts: dict[str, int] = {}

    for pid in sorted(all_candidate_ids):
        is_stale = pid in stale_map
        is_orphan = pid in orphan_map

        # Determine tier
        if pid in stale_map:
            tier = stale_map[pid]["tier"]
            stale_age = stale_map[pid]["stale_age_seconds"]
            threshold = stale_map[pid]["threshold"]
            status = stale_map[pid]["status"]
        else:
            tier = orphan_map[pid]["tier"]
            stale_age = 0.0
            threshold = 0.0
            status = orphan_map[pid]["status"]

        action_class = _determine_action_class(is_stale, is_orphan, stale_age, threshold)
        reason_code = _determine_reason_code(tier, is_stale, is_orphan)
        explanation = _build_explanation(
            action_class, reason_code, is_stale, is_orphan,
            stale_age, threshold, tier,
        )

        candidate = CleanupCandidate(
            proposal_id=pid,
            tier=tier,
            action_class=action_class,
            reason_code=reason_code,
            is_stale=is_stale,
            is_orphan=is_orphan,
            stale_age_seconds=round(stale_age, 1),
            current_status=status,
            explanation=explanation,
        )
        report.candidates.append(candidate.to_dict())

        # Aggregate
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        action_counts[action_class] = action_counts.get(action_class, 0) + 1
        reason_counts[reason_code] = reason_counts.get(reason_code, 0) + 1

    # -- Step 4: Finalize report ------------------------------------------- #
    report.total_candidates = len(report.candidates)
    report.by_tier = tier_counts
    report.by_action_class = action_counts
    report.by_reason = reason_counts
    # Safety invariants — always enforced
    report.write_impact = 0
    report.terminal_impact = 0
    report.simulation_only = True

    return report
