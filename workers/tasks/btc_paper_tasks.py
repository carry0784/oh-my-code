"""CR-048 Phase 5a-C -- BTC Guarded Paper Trading Task (BTC-only).

Hourly Celery task for BTC/USDT guarded paper trading.
dry_run=True hardcoded, never configurable.

7-point latency guard required before every trade decision.
All missing latency/spread metrics resolve to SKIP_LATENCY_GUARD (fail-closed).

State machine: fail-closed. All exceptions -> ERROR_FAIL_CLOSED.

BTC lane adds guarded paper capability only; it does not expand
runtime activation capability.

Phase 5a-C allows append-only receipts/evaluation records and
paper-session state persistence only. It does not allow live exchange
writes or business-state activation writes.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from uuid import uuid4

from workers.celery_app import celery_app
from app.core.config import settings
from app.core.logging import get_logger
from app.services.paper_trading_session_cr046 import (
    BarAction,
    CR046PaperSession,
    CR046PaperTradingManager,
    PaperTradingReceipt,
    SL_PCT,
    TP_PCT,
)
from app.services.btc_latency_guard import (
    evaluate_btc_guard,
    update_high_latency_counter,
)
from strategies.smc_wavetrend_strategy import SMCWaveTrendStrategy
from exchanges.factory import ExchangeFactory

logger = get_logger(__name__)

SESSION_ID = "cr046_btc_guarded_v1"
STRATEGY_VERSION = "SMC_WaveTrend_1H_v2"

# Synthetic slippage model: max(spread/2, 0.05%)
SLIPPAGE_FLOOR = 0.0005


def _synthetic_slippage(spread_pct: float | None) -> float:
    if spread_pct is None:
        return SLIPPAGE_FLOOR
    return max(spread_pct / 2, SLIPPAGE_FLOOR)


@celery_app.task(bind=True, max_retries=0)
def run_btc_paper_bar(
    self,
    symbol: str = "BTC/USDT",
    exchange_name: str = "binance",
):
    """Execute one bar of BTC guarded paper trading. dry_run=True always."""
    receipt = PaperTradingReceipt(
        receipt_id=str(uuid4()),
        session_id=SESSION_ID,
        symbol=symbol,
        strategy_version=STRATEGY_VERSION,
        dry_run=True,
    )

    try:
        # Always use asyncio.run() to guarantee a fresh event loop per task.
        # Previous pattern reused a closed loop, causing 'NoneType' object
        # has no attribute 'send' in solo-pool workers after the first
        # async task completed.  (Same fix as sol_paper_tasks PR #89.)
        result = asyncio.run(
            _run_btc_paper_bar_async(symbol, exchange_name, receipt),
        )
        return result
    except Exception as e:
        receipt.action = BarAction.ERROR_FAIL_CLOSED
        receipt.decision_source = "error"
        receipt.block_reason = str(e)
        receipt.halt_state = True
        logger.error(
            "btc_paper_error_fail_closed",
            error=str(e),
            receipt_id=receipt.receipt_id,
        )
        return {"action": BarAction.ERROR_FAIL_CLOSED, "error": str(e)}


async def _run_btc_paper_bar_async(
    symbol: str,
    exchange_name: str,
    receipt: PaperTradingReceipt,
) -> dict:
    """Core async logic for BTC guarded paper bar."""
    from app.core.database import async_session_factory
    from app.services.session_store_cr046 import (
        SessionStore,
        ReceiptStore,
        DuplicateBarError,
    )

    manager = CR046PaperTradingManager()
    now_utc = datetime.now(timezone.utc)

    async with async_session_factory() as db:
        try:
            store = SessionStore(db)
            receipt_store = ReceiptStore(db)

            # 1. Load or create session
            session = await store.load(SESSION_ID)
            if session is None:
                session = CR046PaperSession(
                    session_id=SESSION_ID,
                    symbol=symbol,
                    started_at=now_utc.isoformat(),
                    last_daily_reset_utc=now_utc.replace(hour=0, minute=0, second=0, microsecond=0),
                    last_weekly_reset_utc=now_utc.replace(
                        hour=0, minute=0, second=0, microsecond=0
                    ),
                )
                await store.create(session)

            # 2. Daily/weekly resets
            session = manager.check_and_reset_daily(session, now_utc)
            session = manager.check_and_reset_weekly(session, now_utc)

            # 3. Kill-switch check (pre-guard)
            should_halt, halt_reason = manager.apply_kill_switches(session)
            if should_halt:
                session.is_halted = True
                session.halt_reason = halt_reason
                receipt.action = BarAction.HALTED_KILL_SWITCH
                receipt.decision_source = "kill_switch"
                receipt.halt_state = True
                receipt.block_reason = halt_reason
                await _commit_all(db, store, receipt_store, session, receipt)
                return _receipt_to_dict(receipt)

            # 4. Fetch OHLCV data with API latency measurement
            api_start = time.monotonic()
            # Fresh instance per asyncio.run() — prevents stale
            # aiohttp session from closed event loop.
            exchange = ExchangeFactory.create_fresh(exchange_name)
            async with exchange.connect():
                collector_module = __import__(
                    "app.services.market_data_collector",
                    fromlist=["MarketDataCollector"],
                )
                collector = collector_module.MarketDataCollector(exchange.client)
                ohlcv_raw = await collector._fetch_ohlcv(symbol, "1h", 200)
            api_elapsed_ms = (time.monotonic() - api_start) * 1000
            receipt.api_latency_ms = api_elapsed_ms

            if not ohlcv_raw:
                receipt.action = BarAction.ERROR_FAIL_CLOSED
                receipt.decision_source = "error"
                receipt.block_reason = "ohlcv_fetch_empty"
                await _commit_all(db, store, receipt_store, session, receipt)
                return _receipt_to_dict(receipt)

            # Convert OHLCVBar objects to lists
            ohlcv_list = [
                [bar.timestamp, bar.open, bar.high, bar.low, bar.close, bar.volume]
                for bar in ohlcv_raw
            ]

            # 5. Strategy analysis with execution latency measurement
            exec_start = time.monotonic()
            strategy = SMCWaveTrendStrategy(symbol=symbol, exchange=exchange_name)
            signal_result = strategy.analyze(ohlcv_list)
            exec_elapsed_ms = (time.monotonic() - exec_start) * 1000
            receipt.execution_latency_ms = api_elapsed_ms + exec_elapsed_ms

            # 5a. Collect diagnostic snapshot (best-effort, never blocks receipt)
            try:
                diag = strategy.last_diagnostic()
            except Exception:
                diag = {"diagnostic_populated": False}
            receipt.diagnostic = diag

            if signal_result is None:
                receipt.action = BarAction.SKIP_SIGNAL_NONE
                receipt.decision_source = "signal"
                receipt.bar_ts = int(ohlcv_list[-1][0]) if ohlcv_list else 0
                # Still update high-latency counter on skip
                session, _ = update_high_latency_counter(session, receipt.execution_latency_ms)
                await _commit_all(db, store, receipt_store, session, receipt)
                return _receipt_to_dict(receipt)

            # 6. Extract signal info
            signal_type = signal_result["signal_type"].value.upper()
            entry_price = signal_result["entry_price"]
            bar_ts = signal_result["metadata"].get("bar_timestamp", 0)
            receipt.bar_ts = bar_ts
            receipt.signal = signal_type
            receipt.consensus_pass = True

            # 7. Spread measurement (synthetic for paper mode)
            # In paper simulation, spread is synthetic from recent volatility
            spread_pct = _estimate_spread(ohlcv_list)
            receipt.spread_pct = spread_pct

            # 8. 7-POINT LATENCY GUARD (BTC-specific)
            guard_result = evaluate_btc_guard(
                bar_ts_ms=bar_ts,
                now_utc=now_utc,
                execution_latency_ms=receipt.execution_latency_ms,
                api_latency_ms=receipt.api_latency_ms,
                spread_pct=spread_pct,
                session=session,
            )
            receipt.guard_pass = guard_result.passed
            receipt.guard_details = guard_result.details

            if not guard_result.passed:
                receipt.action = BarAction.SKIP_LATENCY_GUARD
                receipt.decision_source = "guard"
                receipt.block_reason = guard_result.fail_reason

                # Update high-latency counter
                session, should_pause = update_high_latency_counter(
                    session, receipt.execution_latency_ms
                )
                if should_pause and not session.is_halted:
                    session.is_halted = True
                    session.halt_reason = "K_LATENCY:3_consecutive_high_latency"
                    receipt.action = BarAction.HALTED_KILL_SWITCH
                    receipt.halt_state = True
                    receipt.block_reason = "K_LATENCY:3_consecutive_high_latency"

                await _commit_all(db, store, receipt_store, session, receipt)
                return _receipt_to_dict(receipt)

            # 9. Update high-latency counter (guard passed, latency was OK)
            session, should_pause = update_high_latency_counter(
                session, receipt.execution_latency_ms
            )
            if should_pause and not session.is_halted:
                session.is_halted = True
                session.halt_reason = "K_LATENCY:3_consecutive_high_latency"
                receipt.action = BarAction.HALTED_KILL_SWITCH
                receipt.decision_source = "guard"
                receipt.halt_state = True
                receipt.block_reason = "K_LATENCY:3_consecutive_high_latency"
                await _commit_all(db, store, receipt_store, session, receipt)
                return _receipt_to_dict(receipt)

            # 10. Check for open position exit
            if session.open_position is not None:
                current_price = entry_price
                should_exit, exit_reason = manager.check_exit(
                    session,
                    current_price,
                    bar_ts,
                    reverse_signal=signal_type,
                )
                if should_exit:
                    slippage = _synthetic_slippage(spread_pct)
                    direction = session.open_position["direction"]
                    if direction == "LONG":
                        exit_price = current_price * (1 - slippage)
                    else:
                        exit_price = current_price * (1 + slippage)

                    close_result = manager.compute_close(session, exit_price, exit_reason)
                    session.daily_pnl = close_result["updated_fields"]["daily_pnl"]
                    session.open_position = None

                    if exit_reason == "stop_loss":
                        receipt.action = BarAction.EXIT_SL
                    elif exit_reason == "take_profit":
                        receipt.action = BarAction.EXIT_TP
                    else:
                        receipt.action = BarAction.EXIT_REVERSE
                    receipt.decision_source = "signal"
                    await _commit_all(db, store, receipt_store, session, receipt)
                    return _receipt_to_dict(receipt)

            # 11. Can enter? (session-level check)
            can_enter, reason = manager.can_enter(session, signal_type)
            receipt.session_can_enter = can_enter

            if not can_enter:
                receipt.action = BarAction.SKIP_SESSION_BLOCK
                receipt.decision_source = "session_block"
                receipt.block_reason = reason
                await _commit_all(db, store, receipt_store, session, receipt)
                return _receipt_to_dict(receipt)

            # 12. Enter position (dry_run=True always)
            slippage = _synthetic_slippage(spread_pct)
            if signal_type == "LONG":
                fill_price = entry_price * (1 + slippage)
                sl_price = fill_price * (1 - SL_PCT)
                tp_price = fill_price * (1 + TP_PCT)
            else:
                fill_price = entry_price * (1 - slippage)
                sl_price = fill_price * (1 + SL_PCT)
                tp_price = fill_price * (1 - TP_PCT)

            session.open_position = {
                "direction": signal_type,
                "entry_price": fill_price,
                "entry_bar_ts": bar_ts,
                "sl_price": sl_price,
                "tp_price": tp_price,
            }
            session.weekly_trades += 1

            receipt.action = BarAction.ENTER_DRY_RUN
            receipt.decision_source = "signal"
            receipt.entry_price = fill_price
            receipt.expected_sl = sl_price
            receipt.expected_tp = tp_price

            # 13. Commit all in single transaction
            await _commit_all(db, store, receipt_store, session, receipt)

            logger.info(
                "btc_paper_entry",
                action=receipt.action,
                signal=signal_type,
                entry_price=fill_price,
                receipt_id=receipt.receipt_id,
                session_id=SESSION_ID,
                guard_pass=True,
            )
            return _receipt_to_dict(receipt)

        except DuplicateBarError:
            await db.rollback()
            logger.info(
                "btc_paper_duplicate_bar",
                action=BarAction.SKIP_DUPLICATE_BAR,
                session_id=SESSION_ID,
                bar_ts=receipt.bar_ts,
            )
            return {
                "action": BarAction.SKIP_DUPLICATE_BAR,
                "decision_source": "idempotency_skip",
            }

        except Exception as e:
            await db.rollback()
            logger.error(
                "btc_paper_error_fail_closed",
                error=str(e),
                receipt_id=receipt.receipt_id,
            )
            return {"action": BarAction.ERROR_FAIL_CLOSED, "error": str(e)}


def _estimate_spread(ohlcv_list: list[list]) -> float | None:
    """Estimate spread from recent OHLCV data (synthetic for paper mode).

    Uses (high - low) / close of the last bar as a proxy.
    Real spread would come from order book snapshot.
    """
    if not ohlcv_list:
        return None
    last = ohlcv_list[-1]
    high, low, close = last[2], last[3], last[4]
    if close <= 0:
        return None
    # Typical spread is a fraction of the bar range
    bar_range_pct = (high - low) / close
    # Estimate spread as ~10% of bar range (conservative)
    return bar_range_pct * 0.1


async def _commit_all(db, store, receipt_store, session, receipt):
    """Single transaction: session UPDATE + receipt INSERT."""
    try:
        await store.save(session)
        await receipt_store.create(receipt)
        await db.commit()
    except Exception:
        await db.rollback()
        raise


def _receipt_to_dict(receipt: PaperTradingReceipt) -> dict:
    import dataclasses

    return dataclasses.asdict(receipt)
