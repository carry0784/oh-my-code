"""
K-Dexter 4-Tier Board Service

Aggregates all 4 tiers + OrderExecutor into a single read-only dashboard view.
No mutations, no side-effects. Reads only from in-memory ledgers.

Data sources:
  Tier 1 (Agent):     ActionLedger.get_board()
  Tier 2 (Execution): ExecutionLedger.get_board()
  Tier 3 (Submit):    SubmitLedger.get_board()
  Tier 4 (Orders):    OrderExecutor.get_history()

Safety:
  - Read-only: never writes to any ledger
  - Fail-closed: missing tier → connected=False, zero counts
  - No raw reasoning/prompt/error_class exposure
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from app.schemas.four_tier_board_schema import (
    FourTierBoardResponse,
    TierSummary,
    OrderTierSummary,
    DerivedFlags,
    LineageEntry,
    OrphanDetail,
    CleanupActionSummary,
)
from app.services.orphan_detection_service import detect_orphans
from app.services.cleanup_simulation_service import simulate_cleanup
from app.services.observation_summary_service import build_observation_summary
from app.services.operator_decision_service import build_decision_summary
from app.services.decision_card_service import build_decision_card
from app.services.review_volume_service import build_review_volume
from app.services.watch_volume_service import build_watch_volume
from app.services.blockage_summary_service import build_blockage_summary
from app.services.retry_pressure_service import build_retry_pressure
from app.services.latency_observation_service import build_latency_observation
from app.services.trend_observation_service import build_trend_observation

if TYPE_CHECKING:
    from app.agents.action_ledger import ActionLedger
    from app.services.execution_ledger import ExecutionLedger
    from app.services.submit_ledger import SubmitLedger
    from app.services.order_executor import OrderExecutor
    from app.core.retry_plan_store import RetryPlanStore
    from app.core.metric_snapshot_buffer import MetricSnapshotBuffer


def build_four_tier_board(
    action_ledger: Optional[ActionLedger] = None,
    execution_ledger: Optional[ExecutionLedger] = None,
    submit_ledger: Optional[SubmitLedger] = None,
    order_executor: Optional[OrderExecutor] = None,
    retry_store: Optional[RetryPlanStore] = None,
    snapshot_buffer: Optional[MetricSnapshotBuffer] = None,
) -> FourTierBoardResponse:
    """
    Build unified 4-tier board from live ledger/executor instances.

    All parameters are optional. Missing tier → connected=False, zero counts.
    This function is pure read-only — it never calls propose_and_guard,
    record_receipt, or any mutating method.
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    # -- Tier 1: Agent ---------------------------------------------------- #
    agent_tier = _build_agent_tier(action_ledger)

    # -- Tier 2: Execution ------------------------------------------------ #
    execution_tier = _build_execution_tier(execution_ledger)

    # -- Tier 3: Submit --------------------------------------------------- #
    submit_tier = _build_submit_tier(submit_ledger)

    # -- Tier 4: Orders --------------------------------------------------- #
    order_tier = _build_order_tier(order_executor)

    # -- Derived flags ---------------------------------------------------- #
    derived_flags = _build_derived_flags(execution_ledger, submit_ledger)

    # -- Aggregated top block reasons ------------------------------------- #
    all_reasons = Counter()
    for tier in [agent_tier, execution_tier, submit_tier]:
        for reason_str in tier.guard_reason_top:
            # Format: "CHECK_NAME: count"
            parts = reason_str.rsplit(": ", 1)
            if len(parts) == 2:
                try:
                    all_reasons[parts[0]] += int(parts[1])
                except ValueError:
                    all_reasons[reason_str] += 1
            else:
                all_reasons[reason_str] += 1

    top_all = [f"{name}: {count}" for name, count in all_reasons.most_common(10)]

    # -- Recent lineage --------------------------------------------------- #
    recent_lineage = _build_recent_lineage(submit_ledger, order_executor)

    # -- Cross-tier orphan detection --------------------------------------- #
    orphan_report = detect_orphans(action_ledger, execution_ledger, submit_ledger)

    # -- Cleanup simulation ------------------------------------------------ #
    cleanup_report = simulate_cleanup(action_ledger, execution_ledger, submit_ledger)

    # -- Observation summary ----------------------------------------------- #
    obs_summary = build_observation_summary(
        action_ledger, execution_ledger, submit_ledger,
    )

    # -- Decision summary -------------------------------------------------- #
    decision = build_decision_summary(
        action_ledger, execution_ledger, submit_ledger,
    )

    # -- Decision card (visualization) ------------------------------------- #
    decision_card = build_decision_card(decision)

    # -- REVIEW volume observation ----------------------------------------- #
    review_volume = build_review_volume(
        action_ledger, execution_ledger, submit_ledger,
    )

    # -- WATCH volume observation ----------------------------------------- #
    watch_volume = build_watch_volume(
        action_ledger, execution_ledger, submit_ledger,
    )

    # -- Pipeline blockage summary ---------------------------------------- #
    blockage_summary = build_blockage_summary(agent_tier, execution_tier, submit_tier)

    # -- Retry pressure observation --------------------------------------- #
    retry_pressure = build_retry_pressure(retry_store)

    # -- Latency observation (v1: per-tier only) ------------------------- #
    latency_observation = build_latency_observation(
        action_ledger, execution_ledger, submit_ledger, order_executor,
    )

    # -- Trend observation (v1: two-window count comparison) ------------- #
    trend_observation = build_trend_observation(snapshot_buffer)

    return FourTierBoardResponse(
        agent_tier=agent_tier,
        execution_tier=execution_tier,
        submit_tier=submit_tier,
        order_tier=order_tier,
        derived_flags=derived_flags,
        top_block_reasons_all=top_all,
        recent_lineage=recent_lineage,
        cross_tier_orphan_count=orphan_report.total_cross_tier_orphan_count,
        cross_tier_orphan_detail=[
            OrphanDetail(**o) for o in
            (orphan_report.execution_orphans + orphan_report.submit_orphans)
        ],
        cleanup_candidate_count=cleanup_report.total_candidates,
        cleanup_action_summary=CleanupActionSummary(**{
            k: v for k, v in cleanup_report.by_action_class.items()
            if k in CleanupActionSummary.model_fields
        }),
        observation_summary=obs_summary.to_schema(),
        decision_summary=decision.to_schema(),
        decision_card=decision_card,
        review_volume=review_volume,
        watch_volume=watch_volume,
        blockage_summary=blockage_summary,
        retry_pressure=retry_pressure,
        latency_observation=latency_observation,
        trend_observation=trend_observation,
        total_guard_checks=25,
        seal_chain_complete=True,
        generated_at=now_iso,
    )


# -- Tier builders --------------------------------------------------------- #

def _build_agent_tier(ledger: Optional[ActionLedger]) -> TierSummary:
    if ledger is None:
        return TierSummary(tier_name="Agent", tier_number=1, connected=False)

    board = ledger.get_board()
    return TierSummary(
        tier_name="Agent",
        tier_number=1,
        total=board.get("total", 0),
        receipted_count=board.get("receipted_count", 0),
        blocked_count=board.get("blocked_count", 0),
        failed_count=board.get("failed_count", 0),
        orphan_count=board.get("orphan_count", 0),
        stale_count=board.get("stale_count", 0),
        stale_threshold_seconds=board.get("stale_threshold_seconds", 0.0),
        guard_reason_top=board.get("guard_reason_top", []),
        connected=True,
    )


def _build_execution_tier(ledger: Optional[ExecutionLedger]) -> TierSummary:
    if ledger is None:
        return TierSummary(tier_name="Execution", tier_number=2, connected=False)

    board = ledger.get_board()
    return TierSummary(
        tier_name="Execution",
        tier_number=2,
        total=board.get("total", 0),
        receipted_count=board.get("receipted_count", 0),
        blocked_count=board.get("blocked_count", 0),
        failed_count=board.get("failed_count", 0),
        orphan_count=board.get("orphan_count", 0),
        stale_count=board.get("stale_count", 0),
        stale_threshold_seconds=board.get("stale_threshold_seconds", 0.0),
        guard_reason_top=board.get("guard_reason_top", []),
        connected=True,
    )


def _build_submit_tier(ledger: Optional[SubmitLedger]) -> TierSummary:
    if ledger is None:
        return TierSummary(tier_name="Submit", tier_number=3, connected=False)

    board = ledger.get_board()
    return TierSummary(
        tier_name="Submit",
        tier_number=3,
        total=board.get("total", 0),
        receipted_count=board.get("receipted_count", 0),
        blocked_count=board.get("blocked_count", 0),
        failed_count=board.get("failed_count", 0),
        orphan_count=board.get("orphan_count", 0),
        stale_count=board.get("stale_count", 0),
        stale_threshold_seconds=board.get("stale_threshold_seconds", 0.0),
        guard_reason_top=board.get("guard_reason_top", []),
        connected=True,
    )


def _build_order_tier(executor: Optional[OrderExecutor]) -> OrderTierSummary:
    if executor is None:
        return OrderTierSummary(connected=False)

    history = executor.get_history()
    filled = partial = rejected = timeout = error = pending = dry_run = 0

    for order in history:
        status = order.get("status", "")
        if status == "FILLED":
            filled += 1
        elif status == "PARTIAL":
            partial += 1
        elif status == "REJECTED":
            rejected += 1
        elif status == "TIMEOUT":
            timeout += 1
        elif status == "ERROR":
            error += 1
        elif status == "PENDING":
            pending += 1

        if order.get("dry_run", False):
            dry_run += 1

    return OrderTierSummary(
        total=len(history),
        filled_count=filled,
        partial_count=partial,
        rejected_count=rejected,
        timeout_count=timeout,
        error_count=error,
        pending_count=pending,
        dry_run_count=dry_run,
        connected=True,
    )


def _build_derived_flags(
    execution_ledger: Optional[ExecutionLedger],
    submit_ledger: Optional[SubmitLedger],
) -> DerivedFlags:
    exec_ready_pending = 0
    exec_ready_true = 0
    submit_ready_pending = 0
    submit_ready_true = 0

    if execution_ledger is not None:
        board = execution_ledger.get_board()
        exec_ready_true = board.get("receipted_count", 0)
        exec_ready_pending = board.get("orphan_count", 0)

    if submit_ledger is not None:
        board = submit_ledger.get_board()
        submit_ready_true = board.get("receipted_count", 0)
        submit_ready_pending = board.get("orphan_count", 0)

    return DerivedFlags(
        execution_ready_pending=exec_ready_pending,
        submit_ready_pending=submit_ready_pending,
        execution_ready_true=exec_ready_true,
        submit_ready_true=submit_ready_true,
    )


def _build_recent_lineage(
    submit_ledger: Optional[SubmitLedger],
    order_executor: Optional[OrderExecutor],
    limit: int = 10,
) -> list[LineageEntry]:
    """Build recent lineage from submit proposals + order results."""
    if submit_ledger is None:
        return []

    proposals = submit_ledger.get_proposals()
    # Most recent first
    recent = list(reversed(proposals[-limit:]))

    entries = []
    for p in recent:
        sp_id = p.get("proposal_id", "")
        order_id = None
        if order_executor is not None:
            order = order_executor.get_order_by_proposal(sp_id)
            if order is not None:
                order_id = order.order_id

        entries.append(LineageEntry(
            agent_proposal_id=p.get("agent_proposal_id"),
            execution_proposal_id=p.get("execution_proposal_id"),
            submit_proposal_id=sp_id,
            order_id=order_id,
            status=p.get("status"),
            submit_ready=p.get("submit_ready"),
            execution_ready=None,  # would need cross-ledger lookup
        ))

    return entries
