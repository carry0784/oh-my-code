"""RI-2A-2b + P3-A: Shadow Observation Beat Task — dry-schedule mode.

DRY_SCHEDULE=True is HARDCODED. Actual pipeline execution requires
DRY_SCHEDULE=False, which is a separate P4 approval (not this scope).

Beat entry is COMMENTED in celery_app.py. Dispatch = 0 until uncommented (P3-B).

P3-A addition: When DRY_SCHEDULE=True, RUNNABLE symbols are now passed
through ShadowPipelineOrchestrator.run_single() to produce dry-run
observations and receipts. execute_bounded_write is NEVER called.

Contract:
  - DRY_SCHEDULE=True: orchestrator dry-run per RUNNABLE symbol
  - DRY_SCHEDULE=False: BLOCKED (not implemented, requires P4 approval)
  - business table write: ZERO (regardless of DRY_SCHEDULE)
  - execution path: ZERO (execute_bounded_write NOT imported)
  - rollback path: ZERO (rollback_bounded_write NOT imported)
  - gate state change: ZERO
  - fail-closed: all exceptions → log + skip, write=0, state_change=0
  - duplicate dispatch: Redis lock (TTL=420s) + expires=240s + max_retries=0
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
# P3-A: TTL must exceed schedule interval (300s) to prevent overlap.
_LOCK_KEY = "shadow_observation_running"
_LOCK_TTL = 420  # seconds (> 300s schedule interval)


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


def _run_orchestrator_for_symbols(
    runnable_symbols: list[str],
    now_utc: datetime,
) -> list:
    """Run ShadowPipelineOrchestrator.run_single() per RUNNABLE symbol.

    P3-A: task-level per-symbol loop (not run_batch).
    Uses per-call async engine to avoid event loop binding issues.
    Fail-closed: individual symbol errors are caught inside orchestrator.

    Returns list of OrchestrationResult.
    """
    import asyncio

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.core.config import settings
    from app.services.shadow_pipeline_orchestrator import ShadowPipelineOrchestrator

    async def _run():
        engine = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=1,
            max_overflow=0,
        )
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        orch = ShadowPipelineOrchestrator()
        results = []
        try:
            async with factory() as session:
                for symbol in runnable_symbols:
                    result = await orch.run_single(session, symbol, now_utc)
                    results.append(result)
                    logger.info(
                        "shadow_observation_orchestrator_result "
                        "symbol=%s outcome=%s receipt_id=%s obs_id=%s",
                        result.symbol,
                        result.outcome.value,
                        result.receipt_id,
                        result.observation_id,
                    )
                # Commit observation/receipt INSERTs
                await session.commit()
        finally:
            await engine.dispose()
        return results

    return asyncio.run(_run())


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
        "receipts_created": 0,
        "orchestrator_outcomes": {},
        "lock_acquired": False,
        "lock_ttl_sec": _LOCK_TTL,
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

            # ── Step 3: DRY_SCHEDULE guard ──
            # P3-A runtime guard: DRY_SCHEDULE must be True.
            # False transition requires P4 approval.
            assert DRY_SCHEDULE is True, (
                "DRY_SCHEDULE=False requires P4 approval. "
                "This task must not run with DRY_SCHEDULE=False."
            )

            # ── Step 4: Dry-schedule evaluation ──
            dry_result = _run_dry_schedule(symbols)

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

            # ── Step 5: P3-A orchestrator dry-run for RUNNABLE symbols ──
            orchestrator_outcomes: dict[str, dict[str, str]] = {}
            observations_inserted = 0
            receipts_created = 0

            if dry_result.would_run:
                orch_results = _run_orchestrator_for_symbols(dry_result.would_run, now)
                for orch_res in orch_results:
                    orchestrator_outcomes[orch_res.symbol] = {
                        "outcome": orch_res.outcome.value,
                        "reason_code": dry_result.reason_codes.get(orch_res.symbol, ""),
                    }
                    if orch_res.observation_id is not None:
                        observations_inserted += 1
                    if orch_res.receipt_id is not None:
                        receipts_created += 1

            task_result["status"] = "completed"
            task_result["symbols_processed"] = dry_result.runnable_count
            task_result["observations_inserted"] = observations_inserted
            task_result["receipts_created"] = receipts_created
            task_result["orchestrator_outcomes"] = orchestrator_outcomes
            task_result["lock_acquired"] = True
            task_result["lock_ttl_sec"] = _LOCK_TTL

            _reset_consecutive_failures()
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
