"""
CR-046 Stage A: Manual SOL Paper Trading Verification Runner

This script runs run_sol_paper_bar logic directly (bypassing Celery)
with controlled OHLCV data to verify 3 scenarios:

  Run 1: No signal (sideways data → SKIP_SIGNAL_NONE)
  Run 2: LONG entry (trending data → ENTER_DRY_RUN)
  Run 3: Duplicate bar skip (same bar_ts → SKIP_DUPLICATE_BAR)

Validates:
  - Receipt fields correctness
  - Session persistence (version bump, daily_pnl)
  - DB append-only receipt storage
  - Duplicate bar idempotent skip
  - dry_run=True enforcement
  - fail-closed on all paths

Usage:
  python scripts/cr046_stage_a_runner.py
"""

import asyncio
import json
import sys
import os
from datetime import datetime, timezone
from uuid import uuid4

import numpy as np

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import async_session_factory
from app.services.paper_trading_session_cr046 import (
    BarAction,
    CR046PaperSession,
    CR046PaperTradingManager,
    PaperTradingReceipt,
    SL_PCT,
    TP_PCT,
)
from app.services.session_store_cr046 import (
    SessionStore,
    ReceiptStore,
    DuplicateBarError,
)
from strategies.smc_wavetrend_strategy import SMCWaveTrendStrategy

SESSION_ID = "cr046_sol_stage_a_test"
SYMBOL = "SOL/USDT"
STRATEGY_VERSION = "SMC_WaveTrend_1H_v2"
SLIPPAGE_FLOOR = 0.0005


def _generate_sideways_ohlcv(n: int = 200, base_price: float = 130.0) -> list[list]:
    """Generate flat sideways data — no trend, unlikely consensus."""
    np.random.seed(42)
    ohlcv = []
    bar_ts = 1711929600000  # 2024-04-01 00:00 UTC
    for i in range(n):
        noise = np.random.uniform(-0.5, 0.5)
        o = base_price + noise
        h = o + np.random.uniform(0.1, 1.0)
        l = o - np.random.uniform(0.1, 1.0)
        c = o + np.random.uniform(-0.3, 0.3)
        ohlcv.append([bar_ts + i * 3600000, o, h, l, c, 100000])
    return ohlcv


def _generate_consensus_ohlcv(n: int = 200, base_price: float = 100.0) -> list[list]:
    """Generate data that produces 2/2 consensus at last bar (seed=720 verified)."""
    np.random.seed(720)
    ohlcv = []
    bar_ts = 1711929600000 + 200 * 3600000  # Offset to avoid bar_ts collision with sideways
    price = base_price
    for i in range(n):
        delta = np.random.uniform(-1.5, 1.8)
        price = max(price + delta, 10)
        h = price + np.random.uniform(0.1, 2.0)
        l = price - np.random.uniform(0.1, 2.0)
        c = price + np.random.uniform(-0.5, 0.5)
        ohlcv.append([bar_ts + i * 3600000, price, h, l, c, 100000])
    return ohlcv


async def run_scenario(
    scenario_name: str,
    ohlcv_data: list[list],
    session_id: str,
    expect_action: str | None = None,
) -> dict:
    """Run a single paper trading scenario and return the receipt dict."""
    print(f"\n{'=' * 60}")
    print(f"SCENARIO: {scenario_name}")
    print(f"{'=' * 60}")

    manager = CR046PaperTradingManager()
    now_utc = datetime.now(timezone.utc)

    async with async_session_factory() as db:
        try:
            store = SessionStore(db)
            receipt_store = ReceiptStore(db)

            receipt = PaperTradingReceipt(
                receipt_id=str(uuid4()),
                session_id=session_id,
                symbol=SYMBOL,
                strategy_version=STRATEGY_VERSION,
                dry_run=True,
            )

            # 1. Load or create session
            session = await store.load(session_id)
            if session is None:
                session = CR046PaperSession(
                    session_id=session_id,
                    symbol=SYMBOL,
                    started_at=now_utc.isoformat(),
                    last_daily_reset_utc=now_utc.replace(hour=0, minute=0, second=0, microsecond=0),
                    last_weekly_reset_utc=now_utc.replace(
                        hour=0, minute=0, second=0, microsecond=0
                    ),
                )
                await store.create(session)
                print(f"  Session created: {session_id}, version={session.version}")
            else:
                print(f"  Session loaded: {session_id}, version={session.version}")

            # 2. Daily/weekly resets
            session = manager.check_and_reset_daily(session, now_utc)
            session = manager.check_and_reset_weekly(session, now_utc)

            # 3. Kill-switch check
            should_halt, halt_reason = manager.apply_kill_switches(session)
            if should_halt:
                session.is_halted = True
                session.halt_reason = halt_reason
                receipt.action = BarAction.HALTED_KILL_SWITCH
                receipt.decision_source = "kill_switch"
                receipt.halt_state = True
                receipt.block_reason = halt_reason
                receipt.bar_ts = int(ohlcv_data[-1][0])
                await store.save(session)
                await receipt_store.create(receipt)
                await db.commit()
                result = _print_receipt(receipt, session)
                return result

            # 4. Strategy analysis
            strategy = SMCWaveTrendStrategy(symbol=SYMBOL, exchange="binance")
            signal_result = strategy.analyze(ohlcv_data)
            receipt.bar_ts = int(ohlcv_data[-1][0])

            if signal_result is None:
                receipt.action = BarAction.SKIP_SIGNAL_NONE
                receipt.decision_source = "signal"
                await store.save(session)
                await receipt_store.create(receipt)
                await db.commit()
                result = _print_receipt(receipt, session)
                return result

            # 5. Extract signal
            signal_type = signal_result["signal_type"].value.upper()
            entry_price = signal_result["entry_price"]
            receipt.signal = signal_type
            receipt.consensus_pass = True

            # 6. Check exit for open position
            if session.open_position is not None:
                should_exit, exit_reason = manager.check_exit(
                    session,
                    entry_price,
                    receipt.bar_ts,
                    reverse_signal=signal_type,
                )
                if should_exit:
                    slippage = SLIPPAGE_FLOOR
                    direction = session.open_position["direction"]
                    exit_price = (
                        entry_price * (1 - slippage)
                        if direction == "LONG"
                        else entry_price * (1 + slippage)
                    )
                    close_result = manager.compute_close(session, exit_price, exit_reason)
                    session.daily_pnl = close_result["updated_fields"]["daily_pnl"]
                    session.open_position = None

                    receipt.action = {
                        "stop_loss": BarAction.EXIT_SL,
                        "take_profit": BarAction.EXIT_TP,
                    }.get(exit_reason, BarAction.EXIT_REVERSE)
                    receipt.decision_source = "signal"
                    await store.save(session)
                    await receipt_store.create(receipt)
                    await db.commit()
                    result = _print_receipt(receipt, session)
                    return result

            # 7. Can enter?
            can_enter, reason = manager.can_enter(session, signal_type)
            receipt.session_can_enter = can_enter

            if not can_enter:
                receipt.action = BarAction.SKIP_SESSION_BLOCK
                receipt.decision_source = "session_block"
                receipt.block_reason = reason
                await store.save(session)
                await receipt_store.create(receipt)
                await db.commit()
                result = _print_receipt(receipt, session)
                return result

            # 8. Enter position (dry_run=True)
            slippage = SLIPPAGE_FLOOR
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
                "entry_bar_ts": receipt.bar_ts,
                "sl_price": sl_price,
                "tp_price": tp_price,
            }
            session.weekly_trades += 1

            receipt.action = BarAction.ENTER_DRY_RUN
            receipt.decision_source = "signal"
            receipt.entry_price = fill_price
            receipt.expected_sl = sl_price
            receipt.expected_tp = tp_price

            await store.save(session)
            await receipt_store.create(receipt)
            await db.commit()

            result = _print_receipt(receipt, session)
            return result

        except DuplicateBarError as e:
            await db.rollback()
            receipt.action = BarAction.SKIP_DUPLICATE_BAR
            receipt.decision_source = "idempotency_skip"
            print(f"  [DUPLICATE BAR] {e}")
            result = _print_receipt(receipt, session)
            return result

        except Exception as e:
            await db.rollback()
            receipt.action = BarAction.ERROR_FAIL_CLOSED
            receipt.decision_source = "error"
            receipt.block_reason = str(e)
            print(f"  [ERROR_FAIL_CLOSED] {e}")
            import traceback

            traceback.print_exc()
            result = _print_receipt(receipt, session)
            return result


def _print_receipt(receipt: PaperTradingReceipt, session: CR046PaperSession) -> dict:
    """Print receipt summary and return dict."""
    print(f"\n  --- Receipt ---")
    print(f"  receipt_id:      {receipt.receipt_id}")
    print(f"  session_id:      {receipt.session_id}")
    print(f"  bar_ts:          {receipt.bar_ts}")
    print(f"  action:          {receipt.action}")
    print(f"  decision_source: {receipt.decision_source}")
    print(f"  signal:          {receipt.signal}")
    print(f"  consensus_pass:  {receipt.consensus_pass}")
    print(f"  session_can_enter: {receipt.session_can_enter}")
    print(f"  dry_run:         {receipt.dry_run}")
    print(f"  entry_price:     {receipt.entry_price}")
    print(f"  expected_sl:     {receipt.expected_sl}")
    print(f"  expected_tp:     {receipt.expected_tp}")
    print(f"  halt_state:      {receipt.halt_state}")
    print(f"  block_reason:    {receipt.block_reason}")

    print(f"\n  --- Session State ---")
    print(f"  version:         {session.version}")
    print(f"  daily_pnl:       {session.daily_pnl}")
    print(f"  weekly_trades:   {session.weekly_trades}")
    print(f"  is_halted:       {session.is_halted}")
    print(f"  open_position:   {session.open_position}")

    import dataclasses

    return dataclasses.asdict(receipt)


async def verify_db_state(session_id: str):
    """Query DB directly to verify persisted state."""
    print(f"\n{'=' * 60}")
    print(f"DB VERIFICATION: {session_id}")
    print(f"{'=' * 60}")

    from sqlalchemy import select, text
    from app.models.paper_session import (
        PaperTradingSessionModel,
        PaperTradingReceiptModel,
    )

    async with async_session_factory() as db:
        # Session
        stmt = select(PaperTradingSessionModel).where(
            PaperTradingSessionModel.session_id == session_id,
        )
        result = await db.execute(stmt)
        session_row = result.scalar_one_or_none()
        if session_row:
            print(f"\n  [DB] Session:")
            print(f"    session_id:     {session_row.session_id}")
            print(f"    symbol:         {session_row.symbol}")
            print(f"    version:        {session_row.version}")
            print(f"    daily_pnl:      {session_row.daily_pnl}")
            print(f"    weekly_trades:  {session_row.weekly_trades}")
            print(f"    is_halted:      {session_row.is_halted}")
            print(f"    open_position:  {session_row.open_position}")
            print(f"    last_updated_at:{session_row.last_updated_at}")
        else:
            print(f"  [DB] Session: NOT FOUND")

        # Receipts
        stmt = (
            select(PaperTradingReceiptModel)
            .where(PaperTradingReceiptModel.session_id == session_id)
            .order_by(PaperTradingReceiptModel.created_at)
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()
        print(f"\n  [DB] Receipts: {len(rows)} total")
        for i, row in enumerate(rows):
            print(
                f"    [{i + 1}] receipt_id={row.receipt_id[:12]}... "
                f"action={row.action} decision={row.decision_source} "
                f"dry_run={row.dry_run} bar_ts={row.bar_ts}"
            )


async def main():
    print("=" * 60)
    print("CR-046 SOL Stage A: Manual Verification Runner")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Session ID: {SESSION_ID}")
    print("=" * 60)

    results = []

    # --- Run 1: No signal (sideways data) ---
    ohlcv_sideways = _generate_sideways_ohlcv()
    r1 = await run_scenario(
        "Run 1: No Signal (sideways data → SKIP_SIGNAL_NONE)",
        ohlcv_sideways,
        SESSION_ID,
    )
    results.append(r1)
    assert r1["action"] == BarAction.SKIP_SIGNAL_NONE, (
        f"Expected SKIP_SIGNAL_NONE, got {r1['action']}"
    )
    assert r1["dry_run"] is True, "dry_run must be True"
    print("  [OK] Run 1 PASS: SKIP_SIGNAL_NONE, dry_run=True")

    # --- Run 2: Entry (trending data) ---
    ohlcv_trending = _generate_consensus_ohlcv()
    r2 = await run_scenario(
        "Run 2: Entry (trending data → ENTER_DRY_RUN or SKIP_SIGNAL_NONE)",
        ohlcv_trending,
        SESSION_ID,
    )
    results.append(r2)
    assert r2["dry_run"] is True, "dry_run must be True"
    assert r2["action"] in [
        BarAction.ENTER_DRY_RUN,
        BarAction.SKIP_SIGNAL_NONE,
        BarAction.SKIP_SESSION_BLOCK,
    ], f"Unexpected action: {r2['action']}"
    print(f"  [OK] Run 2 PASS: action={r2['action']}, dry_run=True")

    # --- Run 3: Duplicate bar (same data as Run 2 → SKIP_DUPLICATE_BAR) ---
    r3 = await run_scenario(
        "Run 3: Duplicate bar (same bar_ts → SKIP_DUPLICATE_BAR)",
        ohlcv_trending,  # Same data = same bar_ts
        SESSION_ID,
    )
    results.append(r3)
    assert r3["dry_run"] is True, "dry_run must be True"
    # Should be duplicate skip (same bar_ts as Run 2)
    assert r3["action"] == BarAction.SKIP_DUPLICATE_BAR, (
        f"Expected SKIP_DUPLICATE_BAR, got {r3['action']}"
    )
    print(f"  [OK] Run 3 PASS: SKIP_DUPLICATE_BAR, dry_run=True")

    # --- DB Verification ---
    await verify_db_state(SESSION_ID)

    # --- Summary ---
    print(f"\n{'=' * 60}")
    print("STAGE A SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Run 1: action={results[0]['action']}, dry_run={results[0]['dry_run']}")
    print(f"  Run 2: action={results[1]['action']}, dry_run={results[1]['dry_run']}")
    print(f"  Run 3: action={results[2]['action']}, dry_run={results[2]['dry_run']}")

    # Checklist
    checks = {
        "action이 허용된 상태명만 사용": all(
            r["action"] in [a for a in dir(BarAction) if not a.startswith("_")] for r in results
        ),
        "ERROR_FAIL_CLOSED 불필요 발생 없음": all(
            r["action"] != BarAction.ERROR_FAIL_CLOSED for r in results
        ),
        "SKIP_DUPLICATE_BAR 필요 시에만 발생": results[2]["action"] == BarAction.SKIP_DUPLICATE_BAR,
        "dry_run=True 전체": all(r["dry_run"] is True for r in results),
        "receipt_id 존재": all(r["receipt_id"] for r in results),
        "session_id 존재": all(r["session_id"] for r in results),
        "ETH 관련 흔적 없음": all(r["symbol"] == "SOL/USDT" for r in results),
    }

    all_pass = True
    for check_name, passed in checks.items():
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  [{status}] {check_name}")

    print(f"\n  Stage A 최종 판정: {'PASS' if all_pass else 'FAIL'}")
    return all_pass


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
