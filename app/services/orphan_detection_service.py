"""
K-Dexter Orphan Detection Service

Read-only cross-tier lineage verification for orphan proposal detection.
Sits OUTSIDE all Ledgers — never writes to any Ledger.

Orphan definition:
  - Execution orphan: agent_proposal_id not found in ActionLedger
  - Submit orphan: execution_proposal_id not found in ExecutionLedger
  - ActionLedger has no parent tier, so no cross-tier orphans

Data access:
  - ActionLedger.get_proposals()   → list[dict]
  - ExecutionLedger.get_proposals() → list[dict]
  - SubmitLedger.get_proposals()   → list[dict]
  Only public read APIs. Never accesses _proposals directly.

Safety:
  - Read-only: never calls propose_and_guard, record_receipt, transition_to
  - No deletion, no state mutation, no side-effects
  - Missing/None Ledger → skip that tier (fail-safe)
  - Sentinel values ("NONE", "UNKNOWN", "") treated as missing parent
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.agents.action_ledger import ActionLedger
    from app.services.execution_ledger import ExecutionLedger
    from app.services.submit_ledger import SubmitLedger


# Sentinel values treated as "no parent" (lineage missing)
_SENTINEL_IDS = frozenset({"", "NONE", "UNKNOWN", None})


@dataclass
class OrphanEntry:
    """Single orphan proposal record."""
    proposal_id: str
    tier: str                          # "execution" | "submit"
    missing_parent_type: str           # "agent_proposal_id" | "execution_proposal_id"
    missing_parent_id: Optional[str]   # the ID that was not found
    current_status: str
    created_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class OrphanReport:
    """Cross-tier orphan detection result."""
    execution_orphan_count: int = 0
    submit_orphan_count: int = 0
    total_cross_tier_orphan_count: int = 0
    execution_orphans: list[dict] = field(default_factory=list)
    submit_orphans: list[dict] = field(default_factory=list)
    tiers_checked: list[str] = field(default_factory=list)
    skipped_tiers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    partial_observation: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def detect_orphans(
    action_ledger: Optional[ActionLedger] = None,
    execution_ledger: Optional[ExecutionLedger] = None,
    submit_ledger: Optional[SubmitLedger] = None,
) -> OrphanReport:
    """
    Detect cross-tier orphan proposals by verifying lineage IDs.

    Read-only: only calls get_proposals() on each Ledger.
    Missing Ledger → skip that tier's verification.

    Returns OrphanReport with orphan counts and details.
    """
    report = OrphanReport()

    # -- Build parent ID sets from upstream Ledgers ---------------------- #
    action_ids: Optional[set[str]] = None
    if action_ledger is not None:
        try:
            action_proposals = action_ledger.get_proposals()
            action_ids = {p.get("proposal_id", "") for p in action_proposals}
            action_ids.discard("")
        except Exception:
            action_ids = None
            report.skipped_tiers.append("action")
            report.warnings.append("action ledger get_proposals() failed")
    else:
        report.skipped_tiers.append("action")

    execution_ids: Optional[set[str]] = None
    if execution_ledger is not None:
        try:
            exec_proposals = execution_ledger.get_proposals()
            execution_ids = {p.get("proposal_id", "") for p in exec_proposals}
            execution_ids.discard("")
        except Exception:
            execution_ids = None
            report.warnings.append("execution ledger get_proposals() failed")

    # -- Check Execution orphans (parent = ActionLedger) ----------------- #
    if execution_ledger is not None and action_ids is not None:
        report.tiers_checked.append("execution")
        try:
            exec_proposals = execution_ledger.get_proposals()
            for p in exec_proposals:
                parent_id = p.get("agent_proposal_id")
                if parent_id in _SENTINEL_IDS or parent_id not in action_ids:
                    entry = OrphanEntry(
                        proposal_id=p.get("proposal_id", ""),
                        tier="execution",
                        missing_parent_type="agent_proposal_id",
                        missing_parent_id=parent_id,
                        current_status=p.get("status", ""),
                        created_at=p.get("created_at", ""),
                    )
                    report.execution_orphans.append(entry.to_dict())
        except Exception:
            report.skipped_tiers.append("execution")
            report.warnings.append("execution orphan scan failed")
    elif execution_ledger is not None and action_ids is None:
        report.skipped_tiers.append("execution")
        report.warnings.append("execution orphan check skipped: action ledger unavailable")

    # -- Check Submit orphans (parent = ExecutionLedger) ------------------ #
    if submit_ledger is not None and execution_ids is not None:
        report.tiers_checked.append("submit")
        try:
            submit_proposals = submit_ledger.get_proposals()
            for p in submit_proposals:
                parent_id = p.get("execution_proposal_id")
                if parent_id in _SENTINEL_IDS or parent_id not in execution_ids:
                    entry = OrphanEntry(
                        proposal_id=p.get("proposal_id", ""),
                        tier="submit",
                        missing_parent_type="execution_proposal_id",
                        missing_parent_id=parent_id,
                        current_status=p.get("status", ""),
                        created_at=p.get("created_at", ""),
                    )
                    report.submit_orphans.append(entry.to_dict())
        except Exception:
            report.skipped_tiers.append("submit")
            report.warnings.append("submit orphan scan failed")
    elif submit_ledger is not None and execution_ids is None:
        report.skipped_tiers.append("submit")
        report.warnings.append("submit orphan check skipped: execution ledger unavailable")

    # -- Aggregate counts ------------------------------------------------ #
    report.execution_orphan_count = len(report.execution_orphans)
    report.submit_orphan_count = len(report.submit_orphans)
    report.total_cross_tier_orphan_count = (
        report.execution_orphan_count + report.submit_orphan_count
    )
    report.partial_observation = len(report.skipped_tiers) > 0

    return report
