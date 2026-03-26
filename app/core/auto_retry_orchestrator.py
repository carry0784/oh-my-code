"""
Card C-38: Auto Retry Orchestrator (Conditional)

Purpose:
  Orchestrate a gated, budgeted, metriced retry pass that combines
  C-35 gate, C-36 budget, C-31 executor, and C-37 metrics into
  a single conditional execution flow.

Design:
  - Gate check first: if gate denies → no execution
  - Budget check per plan: if budget denies → skip plan
  - Executor runs bounded pass on allowed plans
  - Metrics recorded for all outcomes
  - Single-pass, bounded, fail-closed
  - Can be triggered manually (C-33) or conditionally by caller
  - No infinite loop, no daemon, no background worker
  - The "auto" means: caller decides when to call, orchestrator
    decides whether to proceed based on gate/budget

Flow:
  caller → gate.evaluate() → budget.check() → executor → metrics → result
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional


DEFAULT_MAX_EXECUTIONS = 5


@dataclass
class AutoRetryResult:
    """Result of a gated auto-retry pass."""
    executed_at: str = ""
    gate_allowed: bool = False
    gate_reason: str = ""
    plans_checked: int = 0
    plans_budget_allowed: int = 0
    plans_budget_denied: int = 0
    plans_attempted: int = 0
    plans_succeeded: int = 0
    plans_failed: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_auto_retry(
    plan_store: Any,
    gate: Any = None,
    budget: Any = None,
    metrics: Any = None,
    snapshot: Optional[dict[str, Any]] = None,
    max_executions: int = DEFAULT_MAX_EXECUTIONS,
) -> AutoRetryResult:
    """
    Run a gated, budgeted, metriced retry pass.

    Args:
        plan_store: RetryPlanStore (C-30)
        gate: RetryPolicyGate (C-35), or None to skip gate
        budget: RetryBudget (C-36), or None to skip budget
        metrics: RetryMetrics (C-37), or None to skip metrics
        snapshot: Optional snapshot for sender context
        max_executions: Bounded max per pass

    Returns:
        AutoRetryResult with full outcome.

    Fail-closed: errors captured, never propagated.
    """
    now = datetime.now(timezone.utc)
    result = AutoRetryResult(executed_at=now.isoformat())

    try:
        return _run_impl(plan_store, gate, budget, metrics,
                         snapshot, max_executions, now, result)
    except Exception as e:
        result.errors.append(f"orchestrator_error: {str(e)[:100]}")
        return result


def _run_impl(
    plan_store: Any,
    gate: Any,
    budget: Any,
    metrics: Any,
    snapshot: Optional[dict[str, Any]],
    max_executions: int,
    now: datetime,
    result: AutoRetryResult,
) -> AutoRetryResult:
    """Internal orchestrator implementation."""

    # Step 1: Gate check
    if gate is not None:
        try:
            decision = gate.evaluate(plan_store)
            result.gate_allowed = decision.allowed
            result.gate_reason = decision.reason

            if not decision.allowed:
                if metrics:
                    try:
                        metrics.record_gate_denied()
                    except Exception:
                        pass
                return result
        except Exception as e:
            result.gate_allowed = False
            result.gate_reason = f"gate_error: {str(e)[:80]}"
            return result
    else:
        result.gate_allowed = True
        result.gate_reason = "no_gate"

    # Step 2: Acquire pass lock if gate supports it
    if gate is not None and hasattr(gate, "acquire_pass"):
        if not gate.acquire_pass():
            result.gate_allowed = False
            result.gate_reason = "could_not_acquire_pass_lock"
            return result

    try:
        # Step 3: Get pending plans
        pending = plan_store.list_plans(status="pending")
        result.plans_checked = len(pending)

        if not pending:
            return result

        # Step 4: Filter by eligibility time
        eligible = []
        for plan in pending:
            try:
                eligible_at_str = plan.get("eligible_at", "")
                if not eligible_at_str:
                    eligible.append(plan)
                    continue
                eligible_at = datetime.fromisoformat(eligible_at_str)
                if eligible_at.tzinfo is None:
                    eligible_at = eligible_at.replace(tzinfo=timezone.utc)
                if eligible_at <= now:
                    eligible.append(plan)
            except (ValueError, TypeError):
                pass

        # Step 5: Budget filter + execute
        attempted = 0
        for plan in eligible:
            if attempted >= max_executions:
                break

            channel = plan.get("channel", "")
            retry_id = plan.get("retry_id", "")

            if not channel or not retry_id:
                continue

            # Budget check
            if budget is not None:
                try:
                    budget_check = budget.check(channel)
                    if not budget_check.allowed:
                        result.plans_budget_denied += 1
                        if metrics:
                            try:
                                metrics.record_budget_denied()
                            except Exception:
                                pass
                        continue
                except Exception:
                    result.plans_budget_denied += 1
                    continue

            result.plans_budget_allowed += 1

            # Execute single retry via C-31 shared helper
            from app.core.retry_executor import execute_single_plan
            attempt = execute_single_plan(
                plan_store=plan_store,
                plan=plan,
                snapshot=snapshot,
                retry_id=retry_id,
                channel=channel,
                reason_prefix="auto_retry",
            )
            success = attempt.success
            attempted += 1

            if success:
                result.plans_succeeded += 1
            else:
                result.plans_failed += 1

            # Record metrics
            if metrics:
                try:
                    metrics.record_attempt(channel, success)
                except Exception:
                    pass

            # Record budget
            if budget:
                try:
                    budget.record(channel)
                except Exception:
                    pass

        result.plans_attempted = attempted

        # Record pass
        if metrics:
            try:
                metrics.record_pass()
            except Exception:
                pass

    finally:
        # Release pass lock
        if gate is not None and hasattr(gate, "release_pass"):
            try:
                gate.release_pass()
            except Exception:
                pass

    return result


# C-39: _execute_single removed.
# All execution paths now use C-31 execute_single_plan().
