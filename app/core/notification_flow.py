"""
Card C-22: Notification Execution Flow — Fail-closed orchestration.

Purpose:
  Wire routing → policy → sender → receipt into a single execution flow.
  This is the top-level entry point for the notification pipeline.

Flow:
  snapshot → route_snapshot() → policy.evaluate() → send_notifications() → store.store()

Design:
  - Fail-closed at every step: individual step failure does not block others
  - Each step's result is captured in the flow receipt
  - No state mutation beyond receipt persistence
  - No hidden reasoning, no debug traces

Usage:
  from app.core.notification_flow import execute_notification_flow
  result = execute_notification_flow(snapshot, policy, store)
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class FlowResult:
    """Result of a complete notification flow execution."""
    executed_at: str = ""
    # Step results
    routing_ok: bool = False
    routing: dict = field(default_factory=dict)
    policy_ok: bool = False
    policy_action: str = ""
    policy_suppressed: bool = False
    policy_urgent: bool = False
    send_ok: bool = False
    channels_attempted: int = 0
    channels_delivered: int = 0
    receipt_id: str = ""
    # Error tracking
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def execute_notification_flow(
    snapshot: dict[str, Any],
    policy: Any = None,
    store: Any = None,
) -> FlowResult:
    """
    Execute the full notification pipeline:
      1. Route snapshot (C-14)
      2. Apply policy (C-21)
      3. Send notifications (C-15)
      4. Persist receipt (C-16)

    Args:
        snapshot: Output of _build_incident_snapshot() (C-13)
        policy:   AlertPolicy instance (C-21), or None to skip policy
        store:    ReceiptStore instance (C-16), or None to skip persistence

    Returns:
        FlowResult with per-step outcomes.

    Fail-closed: each step is independently try/excepted.
    """
    now = datetime.now(timezone.utc)
    result = FlowResult(executed_at=now.isoformat())

    # Step 1: Route
    routing = {"channels": [], "severity_tier": "unknown", "reason": "routing_failed"}
    try:
        from app.core.alert_router import route_snapshot
        routing = route_snapshot(snapshot)
        result.routing_ok = True
        result.routing = routing
    except Exception as e:
        result.errors.append(f"routing: {str(e)[:80]}")

    # Step 2: Policy evaluation
    effective_channels = list(routing.get("channels", []))
    effective_severity = routing.get("severity_tier", "unknown")

    if policy is not None:
        try:
            decision = policy.evaluate(routing, snapshot)
            result.policy_ok = True
            result.policy_action = decision.action
            result.policy_suppressed = decision.suppressed
            result.policy_urgent = decision.urgent

            # Apply policy decision
            if decision.action == "suppress":
                effective_channels = []
            elif decision.action in ("escalate", "resolve", "send"):
                effective_channels = list(decision.channels)
                effective_severity = decision.severity_tier
        except Exception as e:
            result.errors.append(f"policy: {str(e)[:80]}")
            # Fail-closed: use original routing
    else:
        result.policy_ok = True
        result.policy_action = "passthrough"

    # Step 3: Send (skip if suppressed)
    receipt = None
    if effective_channels and not result.policy_suppressed:
        try:
            from app.core.notification_sender import send_notifications
            send_routing = {
                "channels": effective_channels,
                "severity_tier": effective_severity,
                "reason": routing.get("reason", ""),
            }
            receipt = send_notifications(snapshot, send_routing)
            result.send_ok = True
            result.channels_attempted = receipt.channels_attempted
            result.channels_delivered = receipt.channels_delivered
        except Exception as e:
            result.errors.append(f"send: {str(e)[:80]}")
    else:
        result.send_ok = True  # suppressed = intentional skip, not failure

    # Step 4: Persist receipt
    if store is not None and receipt is not None:
        try:
            result.receipt_id = store.store(receipt, snapshot)
        except Exception as e:
            result.errors.append(f"persist: {str(e)[:80]}")

    return result


# ---------------------------------------------------------------------------
# Card C-32: Manual Retry Pass Entrypoint
# ---------------------------------------------------------------------------

def run_manual_retry_pass(
    plan_store: Any,
    snapshot: Optional[dict[str, Any]] = None,
    max_executions: int = 5,
) -> dict[str, Any]:
    """
    Execute a single bounded retry pass over pending retry plans.

    This is a MANUAL-ONLY entrypoint. Automatic retry is forbidden
    in this card. The caller must explicitly invoke this function;
    it is never called automatically by the notification flow,
    startup hooks, schedulers, or background workers.

    Args:
        plan_store: RetryPlanStore instance (C-30)
        snapshot:   Optional snapshot dict for sender context.
                    If None, executor uses a minimal stub.
        max_executions: Maximum plans to attempt (default 5, bounded by C-31).

    Returns:
        dict with retry pass results (RetryPassResult.to_dict()).

    Fail-closed: errors captured in result, never propagated.
    """
    try:
        from app.core.retry_executor import execute_retry_pass
        result = execute_retry_pass(
            plan_store=plan_store,
            snapshot=snapshot,
            max_executions=max_executions,
        )
        return result.to_dict()
    except Exception as e:
        return {
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "plans_checked": 0,
            "plans_attempted": 0,
            "plans_succeeded": 0,
            "plans_failed": 0,
            "errors": [f"manual_retry_pass_error: {str(e)[:100]}"],
        }
