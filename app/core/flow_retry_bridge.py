"""
Card C-34: Flow Conditional Wiring — Retry Plan Enqueue Bridge

Purpose:
  After notification send completes, conditionally enqueue failed
  channel results into the retry plan store for later manual retry.

Design:
  - Called explicitly after send step, NOT automatically
  - Evaluates each channel result via C-29 retry policy
  - Enqueues retryable failures into C-30 plan store
  - Does NOT execute retries (that's C-31/C-32/C-33)
  - Fail-closed: bridge errors → no enqueue, no raise
  - No daemon, scheduler, background worker
  - No modification of existing send path behavior
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


@dataclass
class BridgeResult:
    """Result of conditional retry enqueue after send."""
    checked: int = 0
    enqueued: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def bridge_failed_to_retry_store(
    send_receipt: Any,
    plan_store: Any,
    retry_policy: Any = None,
    incident: str = "",
    severity_tier: str = "",
    snapshot_summary: str = "",
) -> BridgeResult:
    """
    Evaluate send receipt and enqueue retryable failures into plan store.

    This bridge is called EXPLICITLY after send. It is never called
    automatically by the notification flow pipeline.

    Args:
        send_receipt: NotificationReceipt from C-15 sender
        plan_store: RetryPlanStore instance (C-30)
        retry_policy: DeliveryRetryPolicy instance (C-29), or None
        incident: Incident identifier for dedup
        severity_tier: Severity for plan metadata
        snapshot_summary: Summary for plan metadata

    Returns:
        BridgeResult with enqueue counts.

    Fail-closed: errors captured, never propagated.
    """
    result = BridgeResult()

    try:
        return _bridge_impl(
            send_receipt, plan_store, retry_policy,
            incident, severity_tier, snapshot_summary, result,
        )
    except Exception as e:
        result.errors.append(f"bridge_error: {str(e)[:100]}")
        return result


def _bridge_impl(
    send_receipt: Any,
    plan_store: Any,
    retry_policy: Any,
    incident: str,
    severity_tier: str,
    snapshot_summary: str,
    result: BridgeResult,
) -> BridgeResult:
    """Internal bridge implementation."""

    # Get channel results from receipt
    results_list = getattr(send_receipt, "results", [])
    if not results_list:
        return result

    for ch_result in results_list:
        result.checked += 1

        channel = getattr(ch_result, "channel", "")
        delivered = getattr(ch_result, "delivered", True)
        detail = getattr(ch_result, "detail", "")

        # Already delivered → skip
        if delivered:
            result.skipped += 1
            continue

        # Check retry eligibility if policy provided
        retryable = True
        retry_reason = detail
        retry_after = 60

        if retry_policy is not None:
            try:
                eligibility = retry_policy.check_eligibility(
                    channel=channel,
                    delivered=delivered,
                    detail=detail,
                )
                retryable = eligibility.eligible
                retry_reason = eligibility.reason
            except Exception:
                retryable = False
                retry_reason = "policy_check_error"

        if not retryable:
            result.skipped += 1
            continue

        # Enqueue into plan store
        try:
            enqueue_result = plan_store.enqueue(
                channel=channel,
                reason=retry_reason,
                reliability_tier="transient_failure",
                retryable=True,
                retry_after_seconds=retry_after,
                incident=incident,
                severity_tier=severity_tier,
                snapshot_summary=snapshot_summary,
            )
            if enqueue_result.enqueued:
                result.enqueued += 1
            else:
                result.skipped += 1
        except Exception as e:
            result.errors.append(f"enqueue_error:{channel}: {str(e)[:60]}")
            result.skipped += 1

    return result
