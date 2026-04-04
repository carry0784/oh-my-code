"""RI-2A-2b: Shadow Observation Beat Task — dry-schedule mode.

DRY_SCHEDULE=True is HARDCODED. Actual pipeline execution requires
DRY_SCHEDULE=False, which is a separate A approval (not this scope).

Beat entry is COMMENTED in celery_app.py. Dispatch = 0 until uncommented.

Contract:
  - DRY_SCHEDULE=True: log would_run/would_skip/reason_code only, pipeline call 0
  - DRY_SCHEDULE=False: call run_shadow_pipeline + readthrough + observation INSERT
  - business table write: ZERO (regardless of DRY_SCHEDULE)
  - execution path: ZERO
  - gate state change: ZERO
  - fail-closed: all exceptions → log + skip, write=0, state_change=0
  - duplicate dispatch: Redis lock (TTL=300s) + expires=240s + max_retries=0
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# ── RI-2A-2b: FORCED True. False 전환은 별도 A 승인 후에만 허용. ──
DRY_SCHEDULE: bool = True

# ── Retention Planner — definitions only. Purge NOT implemented. ──
# Purge activation requires: simulate → A approve → activate (3 separate gates)
RETENTION_HOT_DAYS: int = 30
RETENTION_WARM_DAYS: int = 90
AUDIT_VERDICTS: frozenset[str] = frozenset(
    {
        "verdict_mismatch",
        "reason_mismatch",
    }
)

# ── Redis lock config ──
_LOCK_KEY = "shadow_observation_running"
_LOCK_TTL = 300  # seconds


class SkipReasonCode(str, Enum):
    """Fixed enum for dry-schedule reason codes. No free-form strings."""

    RUNNABLE = "RUNNABLE"
    NO_MARKET_DATA = "NO_MARKET_DATA"
    NO_BACKTEST_READINESS = "NO_BACKTEST_READINESS"
    STALE_INPUT = "STALE_INPUT"
    DUPLICATE_WINDOW = "DUPLICATE_WINDOW"
    ALREADY_RUNNING = "ALREADY_RUNNING"
    LOCK_FAILED = "LOCK_FAILED"
    NO_INPUT = "NO_INPUT"
    DRY_SCHEDULE_ACTIVE = "DRY_SCHEDULE_ACTIVE"


@dataclass
class DryScheduleResult:
    """Dry-schedule mode output. Required fields for pre-enable verification."""

    would_run: list[str] = field(default_factory=list)
    would_skip: list[str] = field(default_factory=list)
    reason_codes: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_symbols: int = 0
    runnable_count: int = 0
    skip_count: int = 0


def _try_acquire_lock() -> bool:
    """Try to acquire Redis lock. Returns False if lock exists or Redis unavailable."""
    try:
        redis_client = celery_app.backend.client
        acquired = redis_client.set(_LOCK_KEY, "1", nx=True, ex=_LOCK_TTL)
        return bool(acquired)
    except Exception:
        logger.exception("shadow_observation_lock_acquire_failed")
        return False


def _release_lock() -> None:
    """Release Redis lock. Best-effort."""
    try:
        redis_client = celery_app.backend.client
        redis_client.delete(_LOCK_KEY)
    except Exception:
        logger.warning("shadow_observation_lock_release_failed")


def _increment_consecutive_failures() -> int:
    """Increment and return consecutive failure counter in Redis."""
    try:
        redis_client = celery_app.backend.client
        key = "shadow_observation_consecutive_failures"
        count = redis_client.incr(key)
        redis_client.expire(key, 86400)  # TTL 24h
        return int(count)
    except Exception:
        return -1


def _reset_consecutive_failures() -> None:
    """Reset consecutive failure counter."""
    try:
        redis_client = celery_app.backend.client
        redis_client.delete("shadow_observation_consecutive_failures")
    except Exception:
        pass


def _get_symbol_list() -> list[dict]:
    """Get list of symbols to observe. Read-only query."""
    try:
        from app.core.config import settings

        symbols = []
        # Crypto symbols from data collection config
        for sym in ["BTC/USDT", "SOL/USDT"]:
            symbols.append(
                {
                    "symbol": sym,
                    "asset_class": "CRYPTO",
                    "asset_sector": "CRYPTO",
                    "exchange": "binance",
                }
            )
        return symbols
    except Exception:
        logger.exception("shadow_observation_get_symbols_failed")
        return []


def _evaluate_symbol_readiness(symbol_info: dict) -> str:
    """Evaluate if a symbol is ready for observation. Returns SkipReasonCode value."""
    # In dry-schedule mode, we only check basic availability
    # Full readiness check happens only when DRY_SCHEDULE=False
    if not symbol_info.get("symbol"):
        return SkipReasonCode.NO_INPUT.value
    return SkipReasonCode.RUNNABLE.value


def _run_dry_schedule(symbols: list[dict]) -> DryScheduleResult:
    """Execute dry-schedule: evaluate readiness, log would_run/would_skip."""
    result = DryScheduleResult(
        timestamp=datetime.now(timezone.utc),
        total_symbols=len(symbols),
    )

    for sym_info in symbols:
        symbol = sym_info.get("symbol", "unknown")
        reason = _evaluate_symbol_readiness(sym_info)

        result.reason_codes[symbol] = reason

        if reason == SkipReasonCode.RUNNABLE.value:
            result.would_run.append(symbol)
            result.runnable_count += 1
        else:
            result.would_skip.append(symbol)
            result.skip_count += 1

    return result


@celery_app.task(
    name="workers.tasks.shadow_observation_tasks.run_shadow_observation",
    max_retries=0,
    expires=240,
    acks_late=True,
)
def run_shadow_observation() -> dict:
    """Shadow observation beat task.

    DRY_SCHEDULE=True: log would_run/would_skip/reason_code only.
    DRY_SCHEDULE=False: execute full pipeline (requires separate A approval).

    Fail-closed: all exceptions → log + return, write=0, state_change=0.
    """
    start_time = time.monotonic()
    now = datetime.now(timezone.utc)

    task_result = {
        "last_run": now.isoformat(),
        "status": "unknown",
        "skipped_reason": None,
        "failure_reason": None,
        "symbols_processed": 0,
        "symbols_skipped": 0,
        "observations_inserted": 0,
        "observations_failed": 0,
        "duration_ms": 0,
        "consecutive_failures": 0,
        "dry_schedule": DRY_SCHEDULE,
    }

    try:
        # ── Step 1: Acquire lock ──
        if not _try_acquire_lock():
            task_result["status"] = "skipped"
            task_result["skipped_reason"] = SkipReasonCode.ALREADY_RUNNING.value
            logger.info(
                "shadow_observation_skipped reason=%s",
                SkipReasonCode.ALREADY_RUNNING.value,
            )
            return task_result

        try:
            # ── Step 2: Get symbol list ──
            symbols = _get_symbol_list()
            if not symbols:
                task_result["status"] = "skipped"
                task_result["skipped_reason"] = SkipReasonCode.NO_INPUT.value
                logger.info(
                    "shadow_observation_skipped reason=%s",
                    SkipReasonCode.NO_INPUT.value,
                )
                _reset_consecutive_failures()
                return task_result

            # ── Step 3: DRY_SCHEDULE mode ──
            if DRY_SCHEDULE:
                dry_result = _run_dry_schedule(symbols)

                task_result["status"] = "completed"
                task_result["symbols_processed"] = dry_result.runnable_count
                task_result["symbols_skipped"] = dry_result.skip_count

                logger.info(
                    "shadow_observation_dry_schedule_result "
                    "would_run=%s would_skip=%s reason_codes=%s "
                    "total=%d runnable=%d skip=%d",
                    dry_result.would_run,
                    dry_result.would_skip,
                    dry_result.reason_codes,
                    dry_result.total_symbols,
                    dry_result.runnable_count,
                    dry_result.skip_count,
                )

                _reset_consecutive_failures()
                return task_result

            # ── Step 4: Live execution (DRY_SCHEDULE=False) ──
            # NOT IMPLEMENTED in RI-2A-2b scope.
            # Requires: DRY_SCHEDULE=False (separate A approval)
            # When implemented: call run_shadow_pipeline + readthrough + observation INSERT
            task_result["status"] = "skipped"
            task_result["skipped_reason"] = "LIVE_NOT_IMPLEMENTED"
            return task_result

        finally:
            _release_lock()

    except Exception as exc:
        consecutive = _increment_consecutive_failures()
        task_result["status"] = "failed"
        task_result["failure_reason"] = str(exc)[:200]
        task_result["consecutive_failures"] = consecutive

        logger.exception(
            "shadow_observation_task_failed failure_reason=%s consecutive_failures=%d",
            str(exc)[:200],
            consecutive,
        )

        if consecutive >= 10:
            logger.warning(
                "shadow_observation_consecutive_failures count=%d. "
                ">=10 consecutive failures. Manual review recommended.",
                consecutive,
            )

        return task_result

    finally:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        task_result["duration_ms"] = elapsed_ms

        logger.info(
            "shadow_observation_task_completed result=%s",
            task_result,
        )
