"""RI-2A-2b + P3-A + P4-impl: Shadow Observation Beat Task.

DRY_SCHEDULE=True is HARDCODED. P4-canary GO required to flip to False.

P4-impl addition: wet-run code path implemented but gated behind:
  Gate 0: DRY_SCHEDULE constant (True = dry, False = wet-capable)
  Gate 1: _check_activation_gate() — ops_state.json machine-readable check
  Gate 1.5: per-symbol allowed_symbols filter
  Gate 2: execute_bounded_write internal 10-step CAS verification

When DRY_SCHEDULE=True, behavior is 100% identical to P3-A (dry-run).
When DRY_SCHEDULE=False (P4-canary), Phase A (observation) runs first,
then Phase B (execution) runs per-symbol in isolated sessions.

Contract:
  - DRY_SCHEDULE=True: orchestrator dry-run per RUNNABLE symbol (P3-A path)
  - DRY_SCHEDULE=False: wet-run via execute_bounded_write (P4-impl path)
  - Phase A: observation INSERT (append-only, 1 session, N symbols)
  - Phase B: execute per-symbol (1 session per symbol, isolated commit)
  - Gate 1: activation_gate.status == UNLOCKED + receipt_signed + budget
  - Gate 1.5: symbol in activation_gate.allowed_symbols
  - fail-closed: all exceptions → log + skip, write=0, state_change=0
  - duplicate dispatch: Redis lock (TTL=420s) + expires=240s + max_retries=0
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
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


# ── P4-impl: Activation gate + wet execution ──────────────────

_OPS_STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "ops_state.json")


def _load_ops_state_for_gate() -> dict:
    """Load ops_state.json for activation gate check. Returns empty dict on failure."""
    try:
        with open(_OPS_STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _check_activation_gate() -> tuple[bool, dict]:
    """Machine-readable activation gate check.

    Returns (allowed: bool, gate_config: dict).
    Source of truth: ops_state.json ONLY.
    Markdown receipts are evidence documents — never read at runtime.

    Gate passes when ALL conditions are met:
      - activation_gate.status == "UNLOCKED"
      - activation_gate.receipt_signed == True
      - activation_gate.write_budget > activation_gate.writes_consumed
    """
    state = _load_ops_state_for_gate()
    gate = state.get("activation_gate", {})

    if gate.get("status") != "UNLOCKED":
        return False, gate
    if not gate.get("receipt_signed"):
        return False, gate
    if gate.get("write_budget", 0) <= gate.get("writes_consumed", 0):
        return False, gate

    return True, gate


def _log_activation_snapshot(gate_config: dict, symbols: list[str]) -> str:
    """Log pre-execution snapshot for audit trail. Returns snapshot_id."""
    snapshot_id = str(uuid.uuid4())[:8]
    state = _load_ops_state_for_gate()
    logger.info(
        "activation_snapshot",
        extra={
            "snapshot_id": snapshot_id,
            "exchange_mode": state.get("baseline_values", {}).get("exchange_mode", "UNKNOWN"),
            "gate_status": gate_config.get("status"),
            "gate_mode": gate_config.get("mode"),
            "allowed_symbols": gate_config.get("allowed_symbols", []),
            "write_budget": gate_config.get("write_budget", 0),
            "writes_consumed": gate_config.get("writes_consumed", 0),
            "target_symbols": symbols,
        },
    )
    return snapshot_id


def _run_wet_execution(
    orch_results: list,
    gate_config: dict,
    reason_codes: dict[str, str],
) -> dict:
    """Phase B: Execute bounded writes for allowed symbols in isolated sessions.

    1 write = 1 isolated session. RollbackFailedError breaks the loop.

    Returns dict with per-write outcome counters and write_outcomes list.
    """
    import asyncio

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.core.config import settings
    from app.services.shadow_write_service import (
        ExecutionVerdict,
        RollbackFailedError,
        execute_bounded_write,
        rollback_bounded_write,
    )

    allowed_symbols = set(gate_config.get("allowed_symbols", []))
    write_budget = gate_config.get("write_budget", 0)

    result = {
        "writes_executed": 0,
        "writes_failed_no_write": 0,
        "writes_failed_after_write": 0,
        "writes_rolled_back": 0,
        "writes_rollback_failed": 0,
        "writes_skipped_not_in_scope": 0,
        "writes_skipped_no_verdict": 0,
        "write_outcomes": [],
        "parity_check": True,
        "manual_intervention_required": False,
    }
    writes_consumed_this_run = 0

    async def _execute():
        nonlocal writes_consumed_this_run

        engine = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=1,
            max_overflow=0,
        )
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        try:
            for orch_res in orch_results:
                # Gate 1.5: per-symbol activation filter
                if orch_res.symbol not in allowed_symbols:
                    result["writes_skipped_not_in_scope"] += 1
                    result["write_outcomes"].append(
                        {
                            "symbol": orch_res.symbol,
                            "outcome": "SKIPPED_NOT_IN_SCOPE",
                            "reason": "symbol not in allowed_symbols",
                        }
                    )
                    continue

                # Only execute for WOULD_WRITE verdicts
                write_verdict = getattr(orch_res, "write_verdict", None)
                if write_verdict is None or write_verdict.value != "would_write":
                    result["writes_skipped_no_verdict"] += 1
                    result["write_outcomes"].append(
                        {
                            "symbol": orch_res.symbol,
                            "outcome": "SKIPPED_NO_VERDICT",
                            "reason": f"write_verdict={write_verdict}",
                        }
                    )
                    continue

                # Budget check
                if writes_consumed_this_run >= write_budget:
                    result["writes_skipped_no_verdict"] += 1
                    result["write_outcomes"].append(
                        {
                            "symbol": orch_res.symbol,
                            "outcome": "SKIPPED_BUDGET_EXHAUSTED",
                            "reason": f"budget={write_budget}, consumed={writes_consumed_this_run}",
                        }
                    )
                    continue

                # Parity check: only WOULD_WRITE results should reach here
                if orch_res.receipt_id is None:
                    result["parity_check"] = False
                    result["write_outcomes"].append(
                        {
                            "symbol": orch_res.symbol,
                            "outcome": "SKIPPED_NO_VERDICT",
                            "reason": "no receipt_id from orchestrator",
                        }
                    )
                    continue

                # Phase B: isolated session per write
                new_receipt_id = f"exec-{uuid.uuid4()}"
                async with factory() as exec_session:
                    try:
                        write_receipt = await execute_bounded_write(
                            db=exec_session,
                            receipt_id=new_receipt_id,
                            shadow_receipt_id=orch_res.receipt_id,
                            symbol=orch_res.symbol,
                        )
                        await exec_session.commit()

                        if (
                            write_receipt
                            and write_receipt.verdict == ExecutionVerdict.EXECUTED.value
                        ):
                            result["writes_executed"] += 1
                            writes_consumed_this_run += 1
                            result["write_outcomes"].append(
                                {
                                    "symbol": orch_res.symbol,
                                    "outcome": "EXECUTED",
                                    "receipt_id": new_receipt_id,
                                }
                            )
                            logger.info(
                                "wet_execution_success symbol=%s receipt=%s",
                                orch_res.symbol,
                                new_receipt_id,
                            )
                        elif (
                            write_receipt
                            and write_receipt.verdict == ExecutionVerdict.EXECUTION_FAILED.value
                        ):
                            result["writes_failed_after_write"] += 1
                            result["write_outcomes"].append(
                                {
                                    "symbol": orch_res.symbol,
                                    "outcome": "FAILED_AFTER_WRITE",
                                    "receipt_id": new_receipt_id,
                                }
                            )
                            logger.warning(
                                "wet_execution_failed_after_write symbol=%s",
                                orch_res.symbol,
                            )
                        else:
                            # BLOCKED or other non-write verdict
                            result["writes_failed_no_write"] += 1
                            verdict_val = write_receipt.verdict if write_receipt else "none"
                            result["write_outcomes"].append(
                                {
                                    "symbol": orch_res.symbol,
                                    "outcome": "FAILED_NO_WRITE",
                                    "receipt_id": new_receipt_id,
                                    "verdict": verdict_val,
                                }
                            )

                    except RollbackFailedError as rfe:
                        result["writes_rollback_failed"] += 1
                        result["manual_intervention_required"] = True
                        result["write_outcomes"].append(
                            {
                                "symbol": orch_res.symbol,
                                "outcome": "ROLLBACK_FAILED",
                                "error": str(rfe)[:200],
                            }
                        )
                        logger.critical(
                            "wet_execution_rollback_failed symbol=%s error=%s",
                            orch_res.symbol,
                            str(rfe)[:200],
                        )
                        break  # Stop processing further symbols

                    except Exception as exc:
                        await exec_session.rollback()
                        result["writes_failed_no_write"] += 1
                        result["write_outcomes"].append(
                            {
                                "symbol": orch_res.symbol,
                                "outcome": "FAILED_NO_WRITE",
                                "error": str(exc)[:200],
                            }
                        )
                        logger.exception("wet_execution_exception symbol=%s", orch_res.symbol)
        finally:
            await engine.dispose()

    asyncio.run(_execute())
    return result


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
        # P4-impl: wet-run counters (always present, 0 when dry)
        "writes_executed": 0,
        "writes_failed_no_write": 0,
        "writes_failed_after_write": 0,
        "writes_rolled_back": 0,
        "writes_rollback_failed": 0,
        "writes_skipped_not_in_scope": 0,
        "writes_skipped_no_verdict": 0,
        "write_outcomes": [],
        "parity_check": True,
        "manual_intervention_required": False,
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

            # ── Step 3: DRY/WET path branch (P4-impl) ──
            # Gate 0: DRY_SCHEDULE determines path capability.
            # DRY_SCHEDULE=True → P3-A dry path (100% identical to before)
            # DRY_SCHEDULE=False → P4-impl wet-capable path (gated by Gate 1+1.5+2)

            # ── Step 4: Dry-schedule evaluation (both paths) ──
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

            # ── Step 5: Phase A — orchestrator observation (both paths) ──
            orchestrator_outcomes: dict[str, dict[str, str]] = {}
            observations_inserted = 0
            receipts_created = 0
            orch_results = []

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

            task_result["symbols_processed"] = dry_result.runnable_count
            task_result["observations_inserted"] = observations_inserted
            task_result["receipts_created"] = receipts_created
            task_result["orchestrator_outcomes"] = orchestrator_outcomes
            task_result["lock_acquired"] = True
            task_result["lock_ttl_sec"] = _LOCK_TTL

            # ── Step 6: Path divergence — dry vs wet ──
            if DRY_SCHEDULE:
                # P3-A dry path — no writes, observation only
                task_result["status"] = "completed"
            else:
                # P4-impl wet path — gated execution
                # Gate 1: activation gate check
                gate_allowed, gate_config = _check_activation_gate()

                if not gate_allowed:
                    task_result["status"] = "gate_blocked"
                    task_result["skipped_reason"] = "ACTIVATION_GATE_LOCKED"
                    logger.info(
                        "shadow_observation_gate_blocked gate_status=%s",
                        gate_config.get("status", "MISSING"),
                    )
                else:
                    # Log activation snapshot for audit trail
                    _log_activation_snapshot(gate_config, dry_result.would_run)

                    # Phase B: wet execution (1 write = 1 isolated session)
                    wet_result = _run_wet_execution(
                        orch_results, gate_config, dry_result.reason_codes
                    )

                    # Merge wet-run counters into task result
                    for key in (
                        "writes_executed",
                        "writes_failed_no_write",
                        "writes_failed_after_write",
                        "writes_rolled_back",
                        "writes_rollback_failed",
                        "writes_skipped_not_in_scope",
                        "writes_skipped_no_verdict",
                        "write_outcomes",
                        "parity_check",
                        "manual_intervention_required",
                    ):
                        task_result[key] = wet_result[key]

                    task_result["status"] = "wet_completed"

                    logger.info(
                        "shadow_observation_wet_completed "
                        "executed=%d failed_no_write=%d failed_after_write=%d "
                        "rolled_back=%d rollback_failed=%d "
                        "skipped_scope=%d skipped_verdict=%d parity=%s",
                        wet_result["writes_executed"],
                        wet_result["writes_failed_no_write"],
                        wet_result["writes_failed_after_write"],
                        wet_result["writes_rolled_back"],
                        wet_result["writes_rollback_failed"],
                        wet_result["writes_skipped_not_in_scope"],
                        wet_result["writes_skipped_no_verdict"],
                        wet_result["parity_check"],
                    )

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
