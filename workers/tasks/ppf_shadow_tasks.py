"""PPF Shadow Evaluation Task.

Hourly Celery task for PPF novelty brake shadow gate evaluation.
Runs check_gate() with SHADOW_MANIFEST, records gate decisions for FP accumulation.

Contract:
- SHADOW_MANIFEST only (enforce_deny=False)
- No order execution, no state mutation beyond recording
- Fail-closed: all exceptions -> log + return, no side effects
- Redis lock to prevent overlap (TTL=420s)
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# -- Redis lock config --
_LOCK_KEY = "ppf_shadow_eval_running"
_LOCK_TTL = 420  # seconds (> 3600s schedule but prevents stale lock)


def _try_acquire_lock() -> bool:
    """Try to acquire Redis lock. Returns False if lock exists or Redis unavailable."""
    try:
        redis_client = celery_app.backend.client
        acquired = redis_client.set(_LOCK_KEY, "1", nx=True, ex=_LOCK_TTL)
        return bool(acquired)
    except Exception:
        logger.exception("ppf_shadow_eval_lock_acquire_failed")
        return False


def _release_lock() -> None:
    """Release Redis lock. Best-effort."""
    try:
        redis_client = celery_app.backend.client
        redis_client.delete(_LOCK_KEY)
    except Exception:
        logger.warning("ppf_shadow_eval_lock_release_failed")


@celery_app.task(
    name="workers.tasks.ppf_shadow_tasks.run_ppf_shadow_eval",
    max_retries=0,
    expires=3000,
    acks_late=True,
)
def run_ppf_shadow_eval(
    symbol: str = "SOL/USDT",
    exchange_name: str = "binance",
) -> dict:
    """PPF shadow gate evaluation beat task.

    Builds PPFGateHandler with SHADOW_MANIFEST, fetches OHLCV via public API,
    runs check_gate(), and records the result for FP accumulation tracking.

    Fail-closed: all exceptions -> log + return, write=0, state_change=0.
    """
    start_time = time.monotonic()
    now = datetime.now(timezone.utc)

    task_result = {
        "last_run": now.isoformat(),
        "status": "unknown",
        "symbol": symbol,
        "exchange": exchange_name,
        "manifest": "SHADOW_MANIFEST",
        "gate_allowed": None,
        "raw_gate_decision": None,
        "deny_reason_code": None,
        "novelty_detected": False,
        "ohlcv_bars_fetched": 0,
        "duration_ms": 0,
        "lock_acquired": False,
        "error": None,
    }

    try:
        # Step 1: Acquire lock
        if not _try_acquire_lock():
            task_result["status"] = "skipped"
            task_result["error"] = "ALREADY_RUNNING"
            logger.info("ppf_shadow_eval_skipped reason=ALREADY_RUNNING")
            return task_result

        try:
            task_result["lock_acquired"] = True

            # Step 2: Run async core
            result = asyncio.run(
                _run_ppf_shadow_eval_async(symbol, exchange_name, task_result),
            )
            return result

        finally:
            _release_lock()

    except Exception as exc:
        task_result["status"] = "failed"
        task_result["error"] = str(exc)[:200]
        logger.exception(
            "ppf_shadow_eval_failed symbol=%s error=%s",
            symbol,
            str(exc)[:200],
        )
        return task_result

    finally:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        task_result["duration_ms"] = elapsed_ms


async def _run_ppf_shadow_eval_async(
    symbol: str,
    exchange_name: str,
    task_result: dict,
) -> dict:
    """Core async logic for PPF shadow evaluation."""
    import numpy as np

    from exchanges.factory import ExchangeFactory
    from strategies.ppf.constants import MarketProfile
    from strategies.ppf.gate import PPFGate
    from strategies.ppf.parameters import PPFParameters
    from strategies.ppf.ppf_gate_handler import (
        DenyReasonCode,
        PPFGateHandler,
        SHADOW_MANIFEST,
    )
    from strategies.ppf.session_ledger import (
        SessionBudgetConfig,
        SessionFailureBudgetLedger,
    )

    # Step 2a: Fetch OHLCV via public API
    try:
        exchange = ExchangeFactory.create_fresh(exchange_name)
        raw_bars = await exchange.fetch_ohlcv(symbol, timeframe="1h", limit=100)
    except Exception as exc:
        task_result["status"] = "ohlcv_fetch_failed"
        task_result["error"] = f"ohlcv_fetch: {exc!s}"[:200]
        logger.warning(
            "ppf_shadow_eval_ohlcv_failed symbol=%s error=%s",
            symbol,
            str(exc)[:100],
        )
        return task_result

    if not raw_bars or len(raw_bars) == 0:
        task_result["status"] = "ohlcv_fetch_empty"
        task_result["error"] = "ohlcv_fetch returned empty"
        return task_result

    task_result["ohlcv_bars_fetched"] = len(raw_bars)

    # Step 2b: Convert to numpy arrays
    highs = np.array([bar[2] for bar in raw_bars], dtype=np.float64)
    lows = np.array([bar[3] for bar in raw_bars], dtype=np.float64)
    closes = np.array([bar[4] for bar in raw_bars], dtype=np.float64)
    volumes = np.array([bar[5] for bar in raw_bars], dtype=np.float64)

    ohlcv_closure = lambda: (highs, lows, closes, volumes)

    # Step 2c: Build PPFGateHandler (SHADOW_MANIFEST)
    params = PPFParameters(market_profile=MarketProfile.M1_CRYPTO_FUTURES)
    asset_tag = f"{exchange_name}:{symbol}:1h"
    ppf_gate = PPFGate(params=params, asset_timeframe_tag=asset_tag)
    session_ledger = SessionFailureBudgetLedger(config=SessionBudgetConfig())

    handler = PPFGateHandler(
        ppf_gate=ppf_gate,
        session_ledger=session_ledger,
        ohlcv_provider=ohlcv_closure,
        manifest=SHADOW_MANIFEST,
    )

    # Step 2d: Run gate evaluation
    gate_result = handler.check_gate(
        symbol=symbol,
        exchange=exchange_name,
        risk_filter_pass=False,
    )

    # Step 2e: Extract results
    task_result["gate_allowed"] = gate_result.allowed
    task_result["raw_gate_decision"] = gate_result.raw_gate_decision

    deny_code = gate_result.deny_reason_code
    task_result["deny_reason_code"] = deny_code.value if deny_code else None

    # Detect novelty event
    novelty_detected = deny_code == DenyReasonCode.NOVELTY_BRAKE
    task_result["novelty_detected"] = novelty_detected

    # Step 2f: Persist novelty event for FP accumulation (best-effort)
    if novelty_detected:
        try:
            await _persist_novelty_event(
                symbol=symbol,
                exchange=exchange_name,
                deny_reason_code=deny_code.value,
                raw_gate_decision=gate_result.raw_gate_decision,
                gate_allowed=gate_result.allowed,
                close_price=float(closes[-1]) if len(closes) > 0 else None,
                task_result_json=None,
            )
            task_result["novelty_persisted"] = True
        except Exception as persist_exc:
            task_result["novelty_persisted"] = False
            logger.warning(
                "ppf_shadow_eval_novelty_persist_failed error=%s",
                str(persist_exc)[:100],
            )

    # Step 2g: Advance observation windows for existing events (best-effort)
    try:
        window_result = await _advance_observation_windows(
            symbol=symbol,
            close_price=float(closes[-1]) if len(closes) > 0 else None,
        )
        task_result["windows_advanced"] = window_result.get("advanced", 0)
        task_result["windows_closed"] = window_result.get("closed", 0)
    except Exception as win_exc:
        task_result["windows_advanced"] = 0
        task_result["windows_closed"] = 0
        logger.warning(
            "ppf_shadow_eval_window_advance_failed error=%s",
            str(win_exc)[:100],
        )

    task_result["status"] = "completed"

    logger.info(
        "ppf_shadow_eval_completed symbol=%s allowed=%s raw=%s "
        "deny_code=%s novelty=%s bars=%d",
        symbol,
        gate_result.allowed,
        gate_result.raw_gate_decision,
        task_result["deny_reason_code"],
        novelty_detected,
        len(raw_bars),
    )

    return task_result


async def _persist_novelty_event(
    symbol: str,
    exchange: str,
    deny_reason_code: str,
    raw_gate_decision: bool,
    gate_allowed: bool,
    close_price: float | None,
    task_result_json: str | None,
) -> None:
    """Insert a PPFNoveltyEvent row. Best-effort, never raises to caller."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.core.config import settings
    from app.models.ppf_novelty_event import PPFNoveltyEvent

    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
    )
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with factory() as session:
            event = PPFNoveltyEvent(
                symbol=symbol,
                exchange=exchange,
                deny_reason_code=deny_reason_code,
                raw_gate_decision=raw_gate_decision,
                gate_allowed=gate_allowed,
                manifest_name="SHADOW_MANIFEST",
                close_price_at_event=close_price,
                task_result_json=task_result_json,
            )
            session.add(event)
            await session.commit()
            logger.info(
                "ppf_novelty_event_persisted symbol=%s id=%d",
                symbol,
                event.id,
            )
    finally:
        await engine.dispose()


async def _advance_observation_windows(
    symbol: str,
    close_price: float | None,
) -> dict:
    """Increment bars_elapsed for open observation windows. Close windows at threshold.

    Returns {"advanced": N, "closed": N}.
    """
    from sqlalchemy import select, update
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.core.config import settings
    from app.models.ppf_novelty_event import PPFNoveltyEvent

    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
    )
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    result = {"advanced": 0, "closed": 0}

    try:
        async with factory() as session:
            # Find open observation windows for this symbol
            stmt = select(PPFNoveltyEvent).where(
                PPFNoveltyEvent.symbol == symbol,
                PPFNoveltyEvent.observation_window_closed == False,
            )
            rows = (await session.execute(stmt)).scalars().all()

            for event in rows:
                event.bars_elapsed += 1

                if event.bars_elapsed >= event.observation_window_bars:
                    event.observation_window_closed = True
                    event.close_price_at_window_end = close_price

                    # Auto-judge using shared NoveltyJudgmentEngine
                    try:
                        from app.services.ppf_novelty_judgment import NoveltyJudgmentEngine
                        judge = NoveltyJudgmentEngine()
                        judgment, reason = judge.judge_single(
                            close_at_event=event.close_price_at_event,
                            close_at_window_end=close_price,
                            window_complete=True,
                        )
                        event.judgment = judgment
                        event.judgment_reason = reason
                        event.judgment_ts = datetime.utcnow()
                    except Exception as judge_exc:
                        logger.warning(
                            "ppf_novelty_judgment_failed event_id=%s error=%s",
                            event.id,
                            str(judge_exc)[:100],
                        )

                    result["closed"] += 1

                result["advanced"] += 1

            if rows:
                await session.commit()
                logger.info(
                    "ppf_observation_windows_advanced symbol=%s advanced=%d closed=%d",
                    symbol,
                    result["advanced"],
                    result["closed"],
                )
    finally:
        await engine.dispose()

    return result
