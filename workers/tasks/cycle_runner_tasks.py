"""Celery tasks for periodic multi-symbol runner cycles.

Phase 6B-2 activation of CR-048.  Provides:
  - Periodic run_cycle() invocation with trading hours guard
  - Pre-cycle guards: trading hours, safe mode (DB), drift (DB), duplicate
  - Guard snapshot persistence for audit
  - Receipt persistence after each cycle (including skipped cycles)
  - Idempotency via cycle_id = market:YYYYMMDD-HHMM
  - Task-level exception isolation (never crashes the worker)
  - DB session wiring: async_session_factory → guarded_cycle_with_state
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _make_cycle_id(market: str, now: datetime) -> str:
    """Generate idempotent cycle_id: market:YYYYMMDD-HHMM."""
    return f"{market}:{now.strftime('%Y%m%d-%H%M')}"


async def _run_cycle_with_db(
    *,
    market: str,
    cycle_id: str,
    now: datetime,
    dry_run: bool,
    symbols: list[dict],
    strategies: list[dict],
) -> dict:
    """Async helper: open DB session, run guarded cycle, persist receipt.

    Creates a per-call async engine + session factory to avoid event loop
    mismatch when asyncio.run() creates a new loop each invocation.
    """
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )
    from app.core.config import settings
    from app.services.cycle_receipt_service import CycleReceiptService
    from app.services.multi_symbol_runner import CycleReceipt

    # Per-call engine: avoids asyncpg connection pool being bound to a
    # previous event loop (asyncio.run() creates a new loop each time).
    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
    )
    factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with factory() as session:
        try:
            result = await guarded_cycle_with_state(
                market=market,
                cycle_id=cycle_id,
                now=now,
                dry_run=dry_run,
                symbols=symbols,
                strategies=strategies,
                db=session,
            )

            # Persist receipt (skip or normal)
            receipt_svc = CycleReceiptService(session)
            receipt = CycleReceipt(
                cycle_id=result.get("cycle_id", cycle_id),
                dry_run=result.get("dry_run", dry_run),
                skip_reason_code=result.get("skip_reason_code", "none"),
            )
            receipt.universe_size = result.get("universe_size", 0)
            receipt.strategies_evaluated = result.get("strategies_evaluated", 0)
            receipt.signal_candidates = result.get("signal_candidates", 0)
            receipt.skipped = result.get("skipped", 0)
            receipt.started_at = now
            receipt.finalize()

            guard_snapshot = result.get("guard_snapshot")
            await receipt_svc.persist_receipt(
                receipt,
                safe_mode_active=bool(guard_snapshot and guard_snapshot.get("safe_mode_active")),
                drift_active=bool(guard_snapshot and guard_snapshot.get("drift_active")),
                guard_snapshot=guard_snapshot,
            )

            await session.commit()
            return result
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
            await engine.dispose()


@celery_app.task(
    name="workers.tasks.cycle_runner_tasks.run_strategy_cycle",
    bind=True,
    max_retries=0,
    soft_time_limit=120,
    time_limit=150,
    acks_late=True,
)
def run_strategy_cycle(
    self,
    *,
    market: str = "CRYPTO",
    dry_run: bool = True,
    symbols: list[dict] | None = None,
    strategies: list[dict] | None = None,
):
    """Run one multi-symbol strategy evaluation cycle.

    Pre-cycle guards (in order):
    1. Trading hours check
    2. Safe mode check (DB query)
    3. Drift check (DB query)
    4. Duplicate cycle check (DB query)

    If any guard triggers, a skip receipt is persisted and the task returns.
    All receipts (skip + normal) are persisted to DB via async session.
    """
    now = datetime.now(timezone.utc)
    cycle_id = _make_cycle_id(market, now)
    symbols = symbols or []
    strategies = strategies or []

    try:
        result = asyncio.run(
            _run_cycle_with_db(
                market=market,
                cycle_id=cycle_id,
                now=now,
                dry_run=dry_run,
                symbols=symbols,
                strategies=strategies,
            )
        )
        return result
    except Exception:
        logger.exception(
            "Unhandled error in strategy cycle %s",
            cycle_id,
        )
        return {
            "cycle_id": cycle_id,
            "market": market,
            "skip_reason_code": "task_error",
            "error": True,
        }


# ── Stateless guarded cycle (no DB) ─────────────────────────────────
# Used by tests and when DB is not available.


def _guarded_cycle(
    *,
    market: str,
    cycle_id: str,
    now: datetime,
    dry_run: bool,
    symbols: list[dict],
    strategies: list[dict],
    safe_mode_active: bool = False,
    drift_active: bool = False,
    is_duplicate: bool = False,
) -> dict:
    """Execute the guarded cycle pipeline (stateless version).

    For DB-backed state queries, use guarded_cycle_with_state() instead.
    This version accepts guard states as explicit parameters for testability.
    """
    from app.services.trading_hours import TradingHoursGuard
    from app.services.multi_symbol_runner import (
        MultiSymbolRunner,
        CycleReceipt,
        CycleSkipReason,
    )

    guard = TradingHoursGuard()

    # ── Guard 1: Trading hours ───────────────────────────────────
    hours_result = guard.check(market, now=now)
    if not hours_result.is_open:
        return _build_skip_receipt(
            cycle_id=cycle_id,
            reason=CycleSkipReason.MARKET_CLOSED,
            now=now,
            dry_run=dry_run,
            guard_snapshot={
                "market": hours_result.market,
                "is_open": False,
                "market_reason_code": hours_result.reason_code,
                "safe_mode_active": safe_mode_active,
                "drift_active": drift_active,
            },
        )

    # ── Guard 2: Safe mode ───────────────────────────────────────
    if safe_mode_active:
        return _build_skip_receipt(
            cycle_id=cycle_id,
            reason=CycleSkipReason.SAFE_MODE_ACTIVE,
            now=now,
            dry_run=dry_run,
            guard_snapshot={
                "market": hours_result.market,
                "is_open": True,
                "market_reason_code": hours_result.reason_code,
                "safe_mode_active": True,
                "drift_active": drift_active,
            },
        )

    # ── Guard 3: Drift ───────────────────────────────────────────
    if drift_active:
        return _build_skip_receipt(
            cycle_id=cycle_id,
            reason=CycleSkipReason.DRIFT_ACTIVE,
            now=now,
            dry_run=dry_run,
            guard_snapshot={
                "market": hours_result.market,
                "is_open": True,
                "market_reason_code": hours_result.reason_code,
                "safe_mode_active": False,
                "drift_active": True,
            },
        )

    # ── Guard 4: Duplicate cycle ─────────────────────────────────
    if is_duplicate:
        return _build_skip_receipt(
            cycle_id=cycle_id,
            reason=CycleSkipReason.DUPLICATE_CYCLE,
            now=now,
            dry_run=dry_run,
            guard_snapshot={
                "market": hours_result.market,
                "is_open": True,
                "market_reason_code": hours_result.reason_code,
                "safe_mode_active": False,
                "drift_active": False,
                "is_duplicate": True,
            },
        )

    # ── All guards passed — run cycle ────────────────────────────
    runner = MultiSymbolRunner()
    receipt = runner.run_cycle(
        cycle_id=cycle_id,
        symbols=symbols,
        strategies=strategies,
        safe_mode_active=safe_mode_active,
        drift_active=drift_active,
        bar_ts=now.isoformat(),
        dry_run=dry_run,
    )

    logger.info(
        "Cycle %s complete: universe=%d, evaluated=%d, signals=%d, skipped=%d",
        cycle_id,
        receipt.universe_size,
        receipt.strategies_evaluated,
        receipt.signals_generated,
        receipt.skipped,
    )

    return receipt.to_dict()


# ── DB-backed guarded cycle (async) ─────────────────────────────────
# Used by the actual Celery task when DB session is available.


async def guarded_cycle_with_state(
    *,
    market: str,
    cycle_id: str,
    now: datetime,
    dry_run: bool,
    symbols: list[dict],
    strategies: list[dict],
    db,  # AsyncSession
) -> dict:
    """Execute guarded cycle with real DB state queries.

    Reads safe_mode and drift state from the database via CycleStateService.
    This is the production-path function.
    """
    from app.services.cycle_state_service import CycleStateService
    from app.services.trading_hours import TradingHoursGuard
    from app.services.multi_symbol_runner import CycleSkipReason

    state_svc = CycleStateService(db)
    guard = TradingHoursGuard()

    # ── Guard 1: Trading hours ───────────────────────────────────
    hours_result = guard.check(market, now=now)

    # ── Read DB state ────────────────────────────────────────────
    safe_mode_active = await state_svc.is_safe_mode_active()
    drift_active = await state_svc.has_unprocessed_drift()
    is_duplicate = await state_svc.is_duplicate_cycle(cycle_id)

    # ── Build guard snapshot ─────────────────────────────────────
    snapshot = {
        "cycle_id": cycle_id,
        "market": hours_result.market,
        "is_open": hours_result.is_open,
        "market_reason_code": hours_result.reason_code,
        "safe_mode_active": safe_mode_active,
        "drift_active": drift_active,
        "is_duplicate": is_duplicate,
        "checked_at": now.isoformat(),
    }

    # ── Delegate to stateless pipeline with real state ───────────
    result = _guarded_cycle(
        market=market,
        cycle_id=cycle_id,
        now=now,
        dry_run=dry_run,
        symbols=symbols,
        strategies=strategies,
        safe_mode_active=safe_mode_active,
        drift_active=drift_active,
        is_duplicate=is_duplicate,
    )

    # Enrich result with guard snapshot
    result["guard_snapshot"] = snapshot

    return result


def _build_skip_receipt(
    *,
    cycle_id: str,
    reason,
    now: datetime,
    dry_run: bool,
    guard_snapshot: dict | None = None,
) -> dict:
    """Build a skip receipt dict for a guarded-out cycle."""
    from app.services.multi_symbol_runner import CycleReceipt

    receipt = CycleReceipt(
        cycle_id=cycle_id,
        dry_run=dry_run,
        skip_reason_code=reason.value,
    )
    receipt.started_at = now
    receipt.finalize()

    result = receipt.to_dict()
    if guard_snapshot:
        result["guard_snapshot"] = guard_snapshot

    logger.info(
        "Cycle %s skipped: reason=%s",
        cycle_id,
        reason.value,
    )

    return result
