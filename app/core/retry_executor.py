"""
Card C-31: Retry Executor / Wiring

Purpose:
  Execute pending retry plans from the RetryPlanStore (C-30)
  using the existing notification sender (C-15) in a bounded,
  single-pass, fail-closed manner.

Design:
  - Single-pass: process eligible pending plans once, then return
  - Bounded: configurable max_executions per pass (default 5)
  - Fail-closed: individual retry failures mark plan as failed, never raise
  - Reuses existing sender infrastructure (C-15)
  - Updates plan state via RetryPlanStore transitions
  - No background daemon, no infinite loop, no auto-scheduling
  - No engine logic, no sealed layer modification

Flow:
  1. Query pending plans from store
  2. Filter to eligible (eligible_at <= now)
  3. For each eligible plan (up to max_executions):
     a. Retrieve sender for channel
     b. Execute send
     c. On success: mark_executed + record receipt
     d. On failure: increment attempt, re-enqueue or mark_expired
  4. Return execution summary
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_MAX_EXECUTIONS = 5


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class RetryAttemptResult:
    """Result of a single retry attempt."""
    retry_id: str
    channel: str
    success: bool
    detail: str = ""
    new_status: str = ""


@dataclass
class RetryPassResult:
    """Result of a complete retry execution pass."""
    executed_at: str = ""
    plans_checked: int = 0
    plans_eligible: int = 0
    plans_attempted: int = 0
    plans_succeeded: int = 0
    plans_failed: int = 0
    plans_skipped: int = 0
    results: list[RetryAttemptResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Retry Executor
# ---------------------------------------------------------------------------

def execute_retry_pass(
    plan_store: Any,
    snapshot: Optional[dict[str, Any]] = None,
    max_executions: int = DEFAULT_MAX_EXECUTIONS,
) -> RetryPassResult:
    """
    Execute a single bounded pass over pending retry plans.

    Args:
        plan_store: RetryPlanStore instance (C-30)
        snapshot: Optional snapshot dict for sender context.
                  If None, a minimal stub snapshot is used.
        max_executions: Maximum plans to attempt in this pass.

    Returns:
        RetryPassResult with per-plan outcomes.

    Fail-closed: errors captured in result, never propagated.
    """
    now = datetime.now(timezone.utc)
    result = RetryPassResult(executed_at=now.isoformat())

    try:
        return _execute_pass_impl(plan_store, snapshot, max_executions, now, result)
    except Exception as e:
        result.errors.append(f"pass_error: {str(e)[:100]}")
        return result


def _execute_pass_impl(
    plan_store: Any,
    snapshot: Optional[dict[str, Any]],
    max_executions: int,
    now: datetime,
    result: RetryPassResult,
) -> RetryPassResult:
    """Internal implementation of retry pass."""

    # Step 1: Get pending plans
    pending_plans = plan_store.list_plans(status="pending")
    result.plans_checked = len(pending_plans)

    if not pending_plans:
        return result

    # Step 2: Filter eligible (eligible_at <= now)
    eligible_plans = []
    for plan in pending_plans:
        try:
            eligible_at_str = plan.get("eligible_at", "")
            if not eligible_at_str:
                eligible_plans.append(plan)
                continue
            eligible_at = datetime.fromisoformat(eligible_at_str)
            # Handle timezone-aware comparison
            if eligible_at.tzinfo is None:
                eligible_at = eligible_at.replace(tzinfo=timezone.utc)
            if eligible_at <= now:
                eligible_plans.append(plan)
        except (ValueError, TypeError):
            # Parse error → skip this plan
            result.plans_skipped += 1

    result.plans_eligible = len(eligible_plans)

    if not eligible_plans:
        return result

    # Step 3: Execute up to max_executions
    attempted = 0
    for plan in eligible_plans:
        if attempted >= max_executions:
            break

        retry_id = plan.get("retry_id", "")
        channel = plan.get("channel", "")

        if not retry_id or not channel:
            result.plans_skipped += 1
            continue

        attempted += 1
        attempt_result = execute_single_plan(
            plan_store=plan_store,
            plan=plan,
            snapshot=snapshot,
            retry_id=retry_id,
            channel=channel,
            reason_prefix="retry",
        )

        result.results.append(attempt_result)
        if attempt_result.success:
            result.plans_succeeded += 1
        else:
            result.plans_failed += 1

    result.plans_attempted = attempted
    return result


def execute_single_plan(
    plan_store: Any,
    plan: dict,
    snapshot: Optional[dict[str, Any]],
    retry_id: str,
    channel: str,
    reason_prefix: str = "retry",
) -> RetryAttemptResult:
    """
    Execute a single retry attempt for one plan.

    This is the canonical single-plan execution helper shared by
    C-31 (execute_retry_pass) and C-38 (auto_retry_orchestrator).

    Args:
        plan_store: RetryPlanStore instance
        plan: Plan dict from store
        snapshot: Optional snapshot for sender context
        retry_id: Plan ID
        channel: Target channel
        reason_prefix: Prefix for routing reason (default "retry")

    Returns:
        RetryAttemptResult with outcome.

    Fail-closed: errors → mark failed, never raise.
    """
    try:
        # Get sender from registry
        from app.core.notification_sender import get_sender
        sender = get_sender(channel)

        if sender is None:
            # No sender → permanent failure, expire the plan
            plan_store.mark_expired(retry_id)
            return RetryAttemptResult(
                retry_id=retry_id,
                channel=channel,
                success=False,
                detail=f"no sender registered for channel: {channel}",
                new_status="expired",
            )

        # Build minimal routing context
        routing = {
            "channels": [channel],
            "severity_tier": plan.get("severity_tier", "unknown"),
            "reason": f"{reason_prefix}:{plan.get('reason', 'unknown')}",
        }

        # Use provided snapshot or minimal stub
        send_snapshot = snapshot if snapshot else {
            "overall_status": "RETRY",
            "highest_incident": plan.get("incident", "UNKNOWN"),
            "snapshot_version": "retry",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Execute send
        channel_result = sender(send_snapshot, routing)

        if channel_result.delivered:
            # Success → mark executed
            plan_store.mark_executed(retry_id)
            return RetryAttemptResult(
                retry_id=retry_id,
                channel=channel,
                success=True,
                detail=channel_result.detail,
                new_status="executed",
            )
        else:
            # Failed again → mark expired (exhausted this pass)
            plan_store.mark_expired(retry_id)
            return RetryAttemptResult(
                retry_id=retry_id,
                channel=channel,
                success=False,
                detail=channel_result.detail,
                new_status="expired",
            )

    except Exception as e:
        # Fail-closed: mark expired on error
        try:
            plan_store.mark_expired(retry_id)
        except Exception:
            pass
        return RetryAttemptResult(
            retry_id=retry_id,
            channel=channel,
            success=False,
            detail=f"retry_error: {str(e)[:80]}",
            new_status="expired",
        )


def get_retry_summary(plan_store: Any) -> dict[str, Any]:
    """
    Get a compact summary of current retry state.

    Fail-closed: errors → safe empty summary.
    """
    try:
        return plan_store.summary()
    except Exception:
        return {"total": 0, "pending": 0, "error": True}
