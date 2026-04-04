"""
Card C-33: Operator Retry Trigger Endpoint

Purpose:
  Expose a POST endpoint that allows operators to explicitly trigger
  a bounded single-pass retry of pending notification plans.

Design:
  - POST /api/operator/retry-pass → manual trigger
  - GET  /api/operator/retry-status → current retry queue summary
  - Operator-facing explicit action only
  - Automatic retry is forbidden in this card
  - Fail-closed: errors return safe JSON, never raise
  - Reuses C-32 manual entrypoint and C-30 store
  - No daemon, scheduler, background worker, startup hook
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/api/operator", tags=["operator"])


# ---------------------------------------------------------------------------
# Singleton-safe store access (lazy, fail-closed)
# ---------------------------------------------------------------------------

def _get_plan_store() -> Any:
    """Get or create the global RetryPlanStore. Fail-closed."""
    try:
        from app.core.retry_plan_store import RetryPlanStore
        if not hasattr(_get_plan_store, "_instance"):
            _get_plan_store._instance = RetryPlanStore()
        return _get_plan_store._instance
    except Exception:
        return None


# ---------------------------------------------------------------------------
# POST /api/operator/retry-pass — Manual retry trigger
# ---------------------------------------------------------------------------

@router.post("/retry-pass", include_in_schema=False)
async def operator_retry_pass(max_executions: int = 5) -> dict[str, Any]:
    """
    Trigger a bounded single-pass retry of pending notification plans.

    This is an operator-facing explicit action only.
    Automatic retry is forbidden. Each call executes at most
    `max_executions` eligible pending plans.

    Returns:
        dict with retry pass results.
    """
    now = datetime.now(timezone.utc)
    store = _get_plan_store()

    if store is None:
        return {
            "triggered_at": now.isoformat(),
            "success": False,
            "error": "retry_plan_store_unavailable",
            "plans_attempted": 0,
        }

    try:
        from app.core.notification_flow import run_manual_retry_pass
        result = run_manual_retry_pass(
            plan_store=store,
            max_executions=max_executions,
        )
        return {
            "triggered_at": now.isoformat(),
            "success": True,
            **result,
        }
    except Exception as e:
        return {
            "triggered_at": now.isoformat(),
            "success": False,
            "error": f"retry_pass_error: {str(e)[:100]}",
            "plans_attempted": 0,
        }


# ---------------------------------------------------------------------------
# GET /api/operator/retry-status — Retry queue summary
# ---------------------------------------------------------------------------

@router.get("/retry-status", include_in_schema=False)
async def operator_retry_status() -> dict[str, Any]:
    """
    Get current retry queue summary.

    Returns pending/executed/expired/cancelled counts
    and recent pending plans.
    """
    store = _get_plan_store()

    if store is None:
        return {
            "available": False,
            "error": "retry_plan_store_unavailable",
        }

    try:
        summary = store.summary()
        pending = store.list_plans(status="pending", limit=5)
        return {
            "available": True,
            **summary,
            "recent_pending": pending,
        }
    except Exception as e:
        return {
            "available": False,
            "error": f"status_error: {str(e)[:100]}",
        }
