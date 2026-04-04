"""
Card C-30: Retry Queue / Deferred Retry Plan Ledger

Purpose:
  Store retryable notification failures as deferred retry plans
  for later execution. This card does NOT execute retries.

Design:
  retry policy (C-29) classifies → retryable items enqueued here
  → future executor card (C-31) will consume these plans

  - Append-only plan ledger
  - In-memory ring buffer (configurable max_size)
  - Duplicate suppression by channel+incident key
  - retryable=false items are rejected at enqueue time
  - Fail-closed: errors → plan not enqueued (safe default)
  - No retry execution, no workers, no task runners
  - Read-only review: list, filter, get by ID

Plan states:
  pending   → awaiting execution
  cancelled → manually cancelled or superseded
  executed  → consumed by future executor
  expired   → TTL exceeded without execution
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional
import uuid


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_MAX_PLANS = 200
DEFAULT_TTL_SECONDS = 3600  # 1 hour default expiry


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class RetryPlan:
    """A single deferred retry plan entry."""

    retry_id: str = ""
    created_at: str = ""
    incident: str = ""
    channel: str = ""
    reason: str = ""
    reliability_tier: str = ""
    retry_after_seconds: Optional[int] = None
    eligible_at: str = ""
    status: str = "pending"  # pending | cancelled | executed | expired
    attempt_count: int = 0
    severity_tier: str = ""
    snapshot_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EnqueueResult:
    """Result of a plan enqueue attempt."""

    enqueued: bool
    retry_id: str = ""
    reason: str = ""


# ---------------------------------------------------------------------------
# Retry Plan Store
# ---------------------------------------------------------------------------


class RetryPlanStore:
    """
    Append-only deferred retry plan ledger.

    Stores retryable notification failures for future execution.
    Does NOT execute retries. Classify-only store.
    """

    def __init__(
        self,
        max_plans: int = DEFAULT_MAX_PLANS,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        self._max_plans = max_plans
        self._ttl_seconds = ttl_seconds
        self._plans: list[RetryPlan] = []
        self._dedup_keys: set[str] = set()

    # -- Enqueue ---------------------------------------------------------------

    def enqueue(
        self,
        channel: str,
        reason: str,
        reliability_tier: str,
        retryable: bool,
        retry_after_seconds: Optional[int] = None,
        incident: str = "",
        severity_tier: str = "",
        snapshot_summary: str = "",
    ) -> EnqueueResult:
        """
        Enqueue a retryable failure as a deferred plan.

        Fail-closed: errors → not enqueued.
        Rejects retryable=false items.
        Suppresses duplicates by channel+incident key.
        """
        try:
            return self._enqueue_impl(
                channel=channel,
                reason=reason,
                reliability_tier=reliability_tier,
                retryable=retryable,
                retry_after_seconds=retry_after_seconds,
                incident=incident,
                severity_tier=severity_tier,
                snapshot_summary=snapshot_summary,
            )
        except Exception:
            return EnqueueResult(enqueued=False, reason="enqueue_error")

    def _enqueue_impl(
        self,
        channel: str,
        reason: str,
        reliability_tier: str,
        retryable: bool,
        retry_after_seconds: Optional[int],
        incident: str,
        severity_tier: str,
        snapshot_summary: str,
    ) -> EnqueueResult:
        now = datetime.now(timezone.utc)

        # Rule: reject non-retryable
        if not retryable:
            return EnqueueResult(
                enqueued=False,
                reason="not_retryable",
            )

        # Rule: duplicate suppression
        dedup_key = f"{channel}:{incident}"
        if dedup_key in self._dedup_keys:
            return EnqueueResult(
                enqueued=False,
                reason="duplicate_suppressed",
            )

        # Rule: capacity check
        self._expire_old_plans(now)
        if len(self._plans) >= self._max_plans:
            # Evict oldest pending
            self._evict_oldest_pending()

        # Build plan
        retry_id = uuid.uuid4().hex[:12]
        eligible_seconds = retry_after_seconds if retry_after_seconds is not None else 60

        from datetime import timedelta

        eligible_at = now + timedelta(seconds=eligible_seconds)

        plan = RetryPlan(
            retry_id=retry_id,
            created_at=now.isoformat(),
            incident=incident,
            channel=channel,
            reason=reason,
            reliability_tier=reliability_tier,
            retry_after_seconds=retry_after_seconds,
            eligible_at=eligible_at.isoformat(),
            status="pending",
            attempt_count=0,
            severity_tier=severity_tier,
            snapshot_summary=snapshot_summary,
        )

        self._plans.append(plan)
        self._dedup_keys.add(dedup_key)

        return EnqueueResult(
            enqueued=True,
            retry_id=retry_id,
            reason="plan_created",
        )

    # -- Query -----------------------------------------------------------------

    def list_plans(
        self,
        status: Optional[str] = None,
        channel: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List plans, newest-first. Optional filters by status/channel."""
        try:
            plans = list(reversed(self._plans))
            if status:
                plans = [p for p in plans if p.status == status]
            if channel:
                plans = [p for p in plans if p.channel == channel]
            return [p.to_dict() for p in plans[:limit]]
        except Exception:
            return []

    def get_plan(self, retry_id: str) -> Optional[dict[str, Any]]:
        """Get a single plan by ID."""
        try:
            for p in self._plans:
                if p.retry_id == retry_id:
                    return p.to_dict()
            return None
        except Exception:
            return None

    def count(self, status: Optional[str] = None) -> int:
        """Count plans, optionally filtered by status."""
        try:
            if not isinstance(self._plans, list):
                return 0
            if status:
                return sum(1 for p in self._plans if p.status == status)
            return len(self._plans)
        except Exception:
            return 0

    def pending_count(self) -> int:
        """Count pending plans."""
        return self.count(status="pending")

    # -- State transitions -----------------------------------------------------

    def mark_cancelled(self, retry_id: str) -> bool:
        """Cancel a pending plan."""
        return self._transition(retry_id, from_status="pending", to_status="cancelled")

    def mark_executed(self, retry_id: str) -> bool:
        """Mark a plan as executed (called by future executor)."""
        return self._transition(retry_id, from_status="pending", to_status="executed")

    def mark_expired(self, retry_id: str) -> bool:
        """Mark a plan as expired."""
        return self._transition(retry_id, from_status="pending", to_status="expired")

    def _transition(self, retry_id: str, from_status: str, to_status: str) -> bool:
        """Transition plan state. Returns True if successful."""
        try:
            for p in self._plans:
                if p.retry_id == retry_id and p.status == from_status:
                    p.status = to_status
                    # Release dedup key on terminal states
                    if to_status in ("cancelled", "executed", "expired"):
                        dedup_key = f"{p.channel}:{p.incident}"
                        self._dedup_keys.discard(dedup_key)
                    return True
            return False
        except Exception:
            return False

    # -- Maintenance -----------------------------------------------------------

    def _expire_old_plans(self, now: datetime) -> None:
        """Auto-expire plans past TTL."""
        from datetime import timedelta

        cutoff = now - timedelta(seconds=self._ttl_seconds)
        for p in self._plans:
            if p.status == "pending":
                try:
                    created = datetime.fromisoformat(p.created_at)
                    if created < cutoff:
                        p.status = "expired"
                        dedup_key = f"{p.channel}:{p.incident}"
                        self._dedup_keys.discard(dedup_key)
                except (ValueError, TypeError):
                    pass

    def _evict_oldest_pending(self) -> None:
        """Evict the oldest pending plan to make room."""
        for p in self._plans:
            if p.status == "pending":
                p.status = "expired"
                dedup_key = f"{p.channel}:{p.incident}"
                self._dedup_keys.discard(dedup_key)
                return

    def clear(self) -> None:
        """Clear all plans and dedup keys."""
        self._plans.clear()
        self._dedup_keys.clear()

    def summary(self) -> dict[str, Any]:
        """Return a compact summary of the store."""
        try:
            if not isinstance(self._plans, list):
                return {"total": 0, "pending": 0, "error": True}
            return {
                "total": len(self._plans),
                "pending": self.count("pending"),
                "cancelled": self.count("cancelled"),
                "executed": self.count("executed"),
                "expired": self.count("expired"),
                "max_plans": self._max_plans,
                "ttl_seconds": self._ttl_seconds,
            }
        except Exception:
            return {"total": 0, "pending": 0, "error": True}
