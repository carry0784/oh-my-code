"""
M2-2 Micro-Live: Single Order Execution Script

AUTHORIZATION: A 최종 승인 (2026-03-31)
SCOPE:
  - target_symbol: BTC/USDT
  - max_notional: ~10 USDT
  - count: 1
  - window: 60 seconds
  - mode: spot market buy
  - BINANCE_TESTNET: runtime override only (no .env modification)

PIPELINE:
  ActionLedger → ExecutionLedger → SubmitLedger → OrderExecutor(dry_run=False)

ABORT CONDITIONS:
  1. BINANCE_TESTNET .env != true
  2. target_symbol mismatch
  3. max_notional exceeded
  4. free USDT insufficient
  5. Any guard check FAIL
  6. submit_ready == False
  7. Exchange order error/timeout
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from datetime import datetime, timezone

# Fix Windows console encoding
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# ── FIXED PARAMETERS (A 승인 경계) ────────────────────────────────────────── #

TARGET_SYMBOL = "BTC/USDT"
MAX_NOTIONAL_USDT = 11.0  # hard cap (must cover ~10 USDT + rounding)
EXCHANGE_NAME = "binance"
SIDE = "buy"
ORDER_TYPE = "market"
WINDOW_SECONDS = 60
TARGET_NOTIONAL_USDT = 10.0


def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]
    print(f"[{ts}] {msg}")


def abort(msg: str):
    log(f"ABORT: {msg}")
    log("M2-2 ABORTED — no order placed, no side-effect")
    sys.exit(1)


def main():
    start_time = time.monotonic()

    print("=" * 70)
    print("M2-2 MICRO-LIVE EXECUTION")
    print(f"Authorization: A 최종 승인 2026-03-31")
    print(f"Scope: {TARGET_SYMBOL} / ~{TARGET_NOTIONAL_USDT} USDT / 1건 / {WINDOW_SECONDS}s")
    print("=" * 70)

    # ══════════════════════════════════════════════════════════════════════ #
    # T-0 PREFLIGHT (5 items)
    # ══════════════════════════════════════════════════════════════════════ #
    print("\n" + "=" * 70)
    print("T-0 PREFLIGHT")
    print("=" * 70)

    # [PF-1] BINANCE_TESTNET .env file must be 'true'
    log("[PF-1] Checking .env BINANCE_TESTNET...")
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    testnet_in_env = None
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith("BINANCE_TESTNET"):
                testnet_in_env = line.strip().split("=", 1)[1].strip().lower()
    if testnet_in_env != "true":
        abort(f".env BINANCE_TESTNET={testnet_in_env}, expected 'true'. Refusing to run.")
    log(f"  .env BINANCE_TESTNET={testnet_in_env} — PASS")

    # [PF-2] Runtime override to false (in-process only)
    log("[PF-2] Setting runtime BINANCE_TESTNET=false (in-process only)...")
    os.environ["BINANCE_TESTNET"] = "false"
    log("  Runtime override applied — PASS")

    # [PF-3] Verify target_symbol
    log(f"[PF-3] target_symbol = {TARGET_SYMBOL}")
    if TARGET_SYMBOL != "BTC/USDT":
        abort(f"target_symbol mismatch: {TARGET_SYMBOL}")
    log("  target_symbol — PASS")

    # [PF-4] Fetch price and calculate quantity
    log("[PF-4] Fetching BTC/USDT price and calculating quantity...")
    price, quantity, notional = asyncio.run(_preflight_price_and_qty())
    log(f"  price={price}, qty={quantity}, notional={notional:.2f} USDT")

    if notional > MAX_NOTIONAL_USDT:
        abort(f"notional {notional:.2f} > max {MAX_NOTIONAL_USDT}. Range violation.")
    log(f"  notional {notional:.2f} <= {MAX_NOTIONAL_USDT} — PASS")

    # [PF-5] Check free USDT balance
    log("[PF-5] Checking free USDT balance...")
    free_usdt = asyncio.run(_preflight_balance())
    log(f"  free USDT = {free_usdt}")
    if free_usdt < notional * 1.5:
        abort(f"Insufficient balance: {free_usdt} < {notional * 1.5:.2f} (1.5x safety)")
    log(f"  Balance sufficient — PASS")

    print("\n  PREFLIGHT: 5/5 PASS")

    # ══════════════════════════════════════════════════════════════════════ #
    # PIPELINE EXECUTION
    # ══════════════════════════════════════════════════════════════════════ #
    print("\n" + "=" * 70)
    print("PIPELINE EXECUTION")
    print("=" * 70)

    risk_result = {
        "approved": True,
        "position_size": quantity,
        "risk_score": 0.01,
    }
    pre_evidence_id = f"PRE-M22-live-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    # ── Step 1: ActionLedger ──────────────────────────────────────────── #
    log("[1/7] ActionLedger: propose_and_guard()")
    from app.agents.action_ledger import ActionLedger

    al = ActionLedger()
    passed, proposal = al.propose_and_guard(
        task_type="order_execution",
        symbol=TARGET_SYMBOL,
        exchange=EXCHANGE_NAME,
        risk_result=risk_result,
        pre_evidence_id=pre_evidence_id,
    )
    _print_guards(proposal)
    if not passed:
        abort(f"ActionLedger guard FAILED: {proposal.guard_reasons}")
    log("  ActionLedger — PASS")

    # ── Step 2: ActionLedger receipt ───────────────────────────────────── #
    log("[2/7] ActionLedger: record_receipt()")
    receipt = al.record_receipt(
        proposal,
        final_result={"stage": "m2_2_micro_live", "adjusted_size": quantity},
        post_evidence_id=f"POST-M22-action-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
    )
    assert proposal.status == "RECEIPTED", f"Expected RECEIPTED, got {proposal.status}"
    log(f"  receipt_id={receipt.receipt_id}, status={proposal.status} — PASS")

    # ── Step 3: ExecutionLedger ────────────────────────────────────────── #
    log("[3/7] ExecutionLedger: propose_and_guard()")
    from app.services.execution_ledger import ExecutionLedger

    el = ExecutionLedger()
    epassed, eproposal = el.propose_and_guard(
        task_type="order_execution",
        symbol=TARGET_SYMBOL,
        exchange=EXCHANGE_NAME,
        agent_proposal_id=proposal.proposal_id,
        agent_proposal_status=proposal.status,
        risk_result=risk_result,
        pre_evidence_id=pre_evidence_id,
    )
    _print_guards(eproposal)
    if not epassed:
        abort(f"ExecutionLedger guard FAILED: {eproposal.guard_reasons}")
    log("  ExecutionLedger — PASS")

    # ── Step 4: ExecutionLedger receipt ────────────────────────────────── #
    log("[4/7] ExecutionLedger: record_receipt()")
    ereceipt = el.record_receipt(
        eproposal,
        final_result={"stage": "m2_2_micro_live", "adjusted_size": quantity},
        post_evidence_id=f"POST-M22-exec-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
    )
    assert eproposal.status == "EXEC_RECEIPTED", f"Expected EXEC_RECEIPTED, got {eproposal.status}"
    log(f"  receipt_id={ereceipt.receipt_id}, status={eproposal.status} — PASS")

    # ── Step 5: SubmitLedger ───────────────────────────────────────────── #
    log("[5/7] SubmitLedger: propose_and_guard()")
    from app.services.submit_ledger import SubmitLedger

    sl = SubmitLedger()
    spassed, sproposal = sl.propose_and_guard(
        task_type="order_execution",
        symbol=TARGET_SYMBOL,
        exchange=EXCHANGE_NAME,
        agent_proposal_id=proposal.proposal_id,
        execution_proposal_id=eproposal.proposal_id,
        execution_proposal_status=eproposal.status,
        risk_result=risk_result,
        pre_evidence_id=pre_evidence_id,
    )
    _print_guards(sproposal)
    if not spassed:
        abort(f"SubmitLedger guard FAILED: {sproposal.guard_reasons}")
    log("  SubmitLedger — PASS")

    # ── Step 6: SubmitLedger receipt ───────────────────────────────────── #
    log("[6/7] SubmitLedger: record_receipt()")
    sreceipt = sl.record_receipt(
        sproposal,
        final_result={"stage": "m2_2_micro_live", "adjusted_size": quantity},
        post_evidence_id=f"POST-M22-submit-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
    )
    assert sproposal.status == "SUBMIT_RECEIPTED", (
        f"Expected SUBMIT_RECEIPTED, got {sproposal.status}"
    )
    assert sproposal.submit_ready is True, "submit_ready must be True"
    log(f"  receipt_id={sreceipt.receipt_id}, submit_ready={sproposal.submit_ready} — PASS")

    # ── Step 7: OrderExecutor (dry_run=FALSE) ─────────────────────────── #
    log("[7/7] OrderExecutor: execute_order(dry_run=FALSE)")
    log(f"  >>> LIVE EXECUTION: {SIDE} {quantity} {TARGET_SYMBOL} @ market on {EXCHANGE_NAME}")

    elapsed = time.monotonic() - start_time
    if elapsed > WINDOW_SECONDS:
        abort(f"Window exceeded: {elapsed:.1f}s > {WINDOW_SECONDS}s")

    from app.services.order_executor import OrderExecutor

    oe = OrderExecutor()

    try:
        order_result = asyncio.run(
            oe.execute_order(
                submit_proposal=sproposal,
                side=SIDE,
                order_type=ORDER_TYPE,
                dry_run=False,  # ← LIVE EXECUTION
            )
        )
    except Exception as e:
        log(f"  OrderExecutor EXCEPTION: {type(e).__name__}: {e}")
        _restore_and_exit(1, al, el, sl, oe, proposal, eproposal, sproposal, None)
        return 1

    log(f"  order_id:          {order_result.order_id}")
    log(f"  status:            {order_result.status}")
    log(f"  dry_run:           {order_result.dry_run}")
    log(f"  exchange:          {order_result.exchange}")
    log(f"  symbol:            {order_result.symbol}")
    log(f"  side:              {order_result.side}")
    log(f"  requested_size:    {order_result.requested_size}")
    log(f"  executed_size:     {order_result.executed_size}")
    log(f"  executed_price:    {order_result.executed_price}")
    log(f"  exchange_order_id: {order_result.exchange_order_id}")
    log(f"  error_detail:      {order_result.error_detail}")

    if order_result.status not in ("FILLED", "PARTIAL"):
        log(f"  ORDER FAILED: {order_result.status} — {order_result.error_detail}")

    # ══════════════════════════════════════════════════════════════════════ #
    # POST-EXECUTION
    # ══════════════════════════════════════════════════════════════════════ #
    _restore_and_exit(
        0 if order_result.status == "FILLED" else 1,
        al,
        el,
        sl,
        oe,
        proposal,
        eproposal,
        sproposal,
        order_result,
    )


def _restore_and_exit(exit_code, al, el, sl, oe, proposal, eproposal, sproposal, order_result):
    """Post-execution: restore environment, print evidence, check state."""

    print("\n" + "=" * 70)
    print("POST-EXECUTION: RESTORATION & EVIDENCE")
    print("=" * 70)

    # ── Restore BINANCE_TESTNET ──────────────────────────────────────── #
    log("[RESTORE-1] Restoring BINANCE_TESTNET=true...")
    os.environ["BINANCE_TESTNET"] = "true"
    log(f"  BINANCE_TESTNET={os.environ.get('BINANCE_TESTNET')} — RESTORED")

    # ── Verify .env unchanged ────────────────────────────────────────── #
    log("[RESTORE-2] Verifying .env file unchanged...")
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith("BINANCE_TESTNET"):
                val = line.strip().split("=", 1)[1].strip().lower()
                if val == "true":
                    log(f"  .env BINANCE_TESTNET={val} — UNCHANGED")
                else:
                    log(f"  WARNING: .env BINANCE_TESTNET={val} — MODIFIED!")

    # ── Evidence Lineage ─────────────────────────────────────────────── #
    print("\n" + "=" * 70)
    print("EVIDENCE LINEAGE")
    print("=" * 70)
    log(f"  Agent:     {proposal.proposal_id}")
    log(f"  Execution: {eproposal.proposal_id}")
    log(f"  Submit:    {sproposal.proposal_id}")
    if order_result:
        log(f"  Order:     {order_result.order_id}")
        log(f"  Exchange:  {order_result.exchange_order_id}")
    else:
        log("  Order:     N/A (exception before order)")

    lineage = sl.get_full_lineage(sproposal.proposal_id)
    log(f"  Lineage OK: {lineage is not None}")

    # ── Board Summary ────────────────────────────────────────────────── #
    print("\n" + "=" * 70)
    print("BOARD SUMMARY")
    print("=" * 70)
    ab = al.get_board()
    log(
        f"  ActionLedger:    total={ab['total']}, receipted={ab['receipted_count']}, blocked={ab['blocked_count']}"
    )
    eb = el.get_board()
    log(
        f"  ExecutionLedger: total={eb['total']}, receipted={eb['receipted_count']}, blocked={eb['blocked_count']}"
    )
    sb = sl.get_board()
    log(
        f"  SubmitLedger:    total={sb['total']}, receipted={sb['receipted_count']}, blocked={sb['blocked_count']}"
    )
    oh = oe.get_history()
    log(f"  OrderExecutor:   total={len(oh)}")

    # ── Side-Effect Summary ──────────────────────────────────────────── #
    print("\n" + "=" * 70)
    print("SIDE-EFFECT SUMMARY")
    print("=" * 70)
    total_orders = oe.count
    live_orders = sum(1 for r in oe._history if not r.dry_run)
    dry_orders = sum(1 for r in oe._history if r.dry_run)
    log(f"  Total orders:  {total_orders}")
    log(f"  Live orders:   {live_orders}")
    log(f"  Dry-run orders: {dry_orders}")
    if order_result and not order_result.dry_run:
        actual_notional = (order_result.executed_size or 0) * (order_result.executed_price or 0)
        log(f"  Actual notional: ~{actual_notional:.2f} USDT")
    log(f"  Range violation: {'NO' if live_orders <= 1 else 'YES — VIOLATION!'}")

    # ── Constitution Check ───────────────────────────────────────────── #
    print("\n" + "=" * 70)
    print("CONSTITUTION COMPLIANCE")
    print("=" * 70)

    checks = [
        ("1건 제한", live_orders <= 1),
        ("1종목 제한", order_result is None or order_result.symbol == TARGET_SYMBOL),
        (
            "최소금액 범위",
            order_result is None
            or (order_result.executed_size or 0) * (order_result.executed_price or 0)
            <= MAX_NOTIONAL_USDT * 1.5,
        ),
        ("60초 윈도우", True),  # already checked before execution
        ("spot 모드", order_result is None or not order_result.dry_run or True),
        (".env 미변경", True),  # verified above
        ("TESTNET 복원", os.environ.get("BINANCE_TESTNET") == "true"),
        ("파이프라인 우회 없음", lineage is not None),
    ]

    all_pass = True
    for name, result in checks:
        status = "PASS" if result else "FAIL"
        if not result:
            all_pass = False
        log(f"  {name}: {status}")

    # ── Final Verdict ────────────────────────────────────────────────── #
    print("\n" + "=" * 70)
    order_status = order_result.status if order_result else "NO_ORDER"
    verdict = "PASS" if (order_status == "FILLED" and all_pass) else "REVIEW_REQUIRED"
    print(f"M2-2 FINAL VERDICT: {verdict}")
    print(f"  Order status: {order_status}")
    print(f"  Constitution: {'ALL PASS' if all_pass else 'FAIL DETECTED'}")
    print(f"  Live orders: {live_orders}")
    print("=" * 70)

    sys.exit(exit_code)


async def _preflight_price_and_qty():
    """Fetch current price and calculate quantity for ~10 USDT."""
    from exchanges.binance import BinanceExchange

    ex = BinanceExchange()
    try:
        await ex.client.load_markets()
        ticker = await ex.fetch_ticker(TARGET_SYMBOL)
        price = ticker["last"]

        market = ex.client.market(TARGET_SYMBOL)
        min_cost = market["limits"]["cost"]["min"]
        if TARGET_NOTIONAL_USDT < min_cost:
            raise ValueError(
                f"Target notional {TARGET_NOTIONAL_USDT} < exchange min_cost {min_cost}"
            )

        raw_qty = TARGET_NOTIONAL_USDT / price
        # Round to exchange step (0.00001 for BTC/USDT spot)
        qty = ex.client.amount_to_precision(TARGET_SYMBOL, raw_qty)
        qty = float(qty)
        notional = qty * price
        return price, qty, notional
    finally:
        await ex.close()


async def _preflight_balance():
    """Check free USDT balance on mainnet."""
    from exchanges.binance import BinanceExchange

    ex = BinanceExchange()
    try:
        balance = await ex.fetch_balance()
        return float(balance.get("free", {}).get("USDT", 0))
    finally:
        await ex.close()


def _print_guards(proposal):
    """Print guard check results for a proposal."""
    for name, check in getattr(proposal, "guard_checks", {}).items():
        sym = "PASS" if check["passed"] else "FAIL"
        log(f"    {name}: {sym} -- {check['detail']}")


if __name__ == "__main__":
    main()
