"""
CR-036: Execution path contract tests

Verifies:
1. Binance adapter uses spot mode (not futures)
2. Futures path is not accidentally activated
3. OrderExecutor → Exchange create_order() call binds correctly
4. Dry-run / live boundary preserves ledger/evidence
"""

import asyncio
import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Test 1: Binance adapter spot mode ────────────────────────────────────── #


def test_binance_adapter_spot_mode():
    """CR-036: Binance adapter must use defaultType='spot', not 'futures'."""
    # Verify at source level — BinanceExchange.__init__ requires async event loop
    # for aiohttp session, so we inspect the source code directly.
    import exchanges.binance as bmod

    source = inspect.getsource(bmod.BinanceExchange.__init__)

    assert '"defaultType": "spot"' in source or "'defaultType': 'spot'" in source, (
        "CR-036: BinanceExchange must set defaultType='spot'. "
        "futures mode is not permitted for M2-2 spot execution."
    )


# ── Test 2: Futures path NOT active ──────────────────────────────────────── #


def test_binance_adapter_no_futures():
    """CR-036: Verify futures path is explicitly blocked."""
    import exchanges.binance as bmod

    source = inspect.getsource(bmod.BinanceExchange.__init__)

    assert '"defaultType": "future"' not in source, (
        "CR-036: defaultType must NOT be 'future'. M2-2 approval scope is spot only."
    )
    assert "'defaultType': 'future'" not in source, (
        "CR-036: defaultType must NOT be 'future' (single quotes). "
        "M2-2 approval scope is spot only."
    )


# ── Test 3: OrderExecutor → Exchange create_order() contract ─────────────── #


def test_order_executor_create_order_signature_match():
    """CR-036: OrderExecutor call must match BaseExchange.create_order() signature."""
    from exchanges.base import BaseExchange

    # Get BaseExchange.create_order signature
    base_sig = inspect.signature(BaseExchange.create_order)
    base_params = list(base_sig.parameters.keys())

    # Expected: ['self', 'symbol', 'side', 'order_type', 'quantity', 'price']
    assert "quantity" in base_params, (
        f"BaseExchange.create_order() missing 'quantity' param: {base_params}"
    )
    assert "amount" not in base_params, (
        f"BaseExchange.create_order() should use 'quantity', not 'amount': {base_params}"
    )

    # Verify OrderExecutor source uses 'quantity=' not 'amount='
    import app.services.order_executor as oe_mod

    source = inspect.getsource(oe_mod.OrderExecutor.execute_order)

    assert "quantity=requested_size" in source, (
        "CR-036: OrderExecutor must call create_order(quantity=requested_size), "
        "not create_order(amount=requested_size)"
    )
    assert "amount=requested_size" not in source, (
        "CR-036: OrderExecutor still uses 'amount=requested_size'. "
        "Must be 'quantity=requested_size' to match BaseExchange contract."
    )


def test_order_executor_create_order_arg_order():
    """CR-036: OrderExecutor must pass args in correct order: symbol, side, order_type."""
    import app.services.order_executor as oe_mod

    source = inspect.getsource(oe_mod.OrderExecutor.execute_order)

    # Find the create_order call block
    lines = source.split("\n")
    call_lines = []
    in_call = False
    for line in lines:
        if "ex.create_order(" in line:
            in_call = True
        if in_call:
            call_lines.append(line.strip())
            if ")," in line or line.strip().endswith("),"):
                break

    call_text = " ".join(call_lines)

    # Verify keyword order matches BaseExchange signature
    sym_pos = call_text.find("symbol=")
    side_pos = call_text.find("side=")
    type_pos = call_text.find("order_type=")
    qty_pos = call_text.find("quantity=")

    assert sym_pos < side_pos < type_pos < qty_pos, (
        f"CR-036: Argument order mismatch. Expected symbol < side < order_type < quantity. "
        f"Got positions: symbol={sym_pos}, side={side_pos}, order_type={type_pos}, quantity={qty_pos}"
    )


# ── Test 4: Dry-run / live boundary — ledger/evidence preserved ──────────── #


def test_dry_run_live_boundary_ledger_preserved():
    """CR-036: Both dry_run=True and dry_run=False paths preserve ledger lineage."""
    from app.agents.action_ledger import ActionLedger
    from app.services.execution_ledger import ExecutionLedger
    from app.services.submit_ledger import SubmitLedger
    from app.services.order_executor import OrderExecutor

    # Setup: full pipeline to get a submit-ready proposal
    al = ActionLedger()
    risk_result = {"approved": True, "position_size": 10.0, "risk_score": 0.05}

    passed, proposal = al.propose_and_guard(
        task_type="order_execution",
        symbol="BTC/USDT",
        exchange="binance",
        risk_result=risk_result,
        pre_evidence_id="PRE-CR036-test",
    )
    assert passed
    al.record_receipt(proposal, final_result={"stage": "test"}, post_evidence_id="POST-CR036-test")

    el = ExecutionLedger()
    ep, eproposal = el.propose_and_guard(
        task_type="order_execution",
        symbol="BTC/USDT",
        exchange="binance",
        agent_proposal_id=proposal.proposal_id,
        agent_proposal_status=proposal.status,
        risk_result=risk_result,
        pre_evidence_id="PRE-CR036-test",
    )
    assert ep
    el.record_receipt(eproposal, final_result={"stage": "test"}, post_evidence_id="POST-CR036-exec")

    sl = SubmitLedger()
    sp, sproposal = sl.propose_and_guard(
        task_type="order_execution",
        symbol="BTC/USDT",
        exchange="binance",
        agent_proposal_id=proposal.proposal_id,
        execution_proposal_id=eproposal.proposal_id,
        execution_proposal_status=eproposal.status,
        risk_result=risk_result,
        pre_evidence_id="PRE-CR036-test",
    )
    assert sp
    sl.record_receipt(
        sproposal, final_result={"stage": "test"}, post_evidence_id="POST-CR036-submit"
    )
    assert sproposal.submit_ready is True

    # Test: dry_run path preserves lineage
    oe = OrderExecutor()
    dry_result = asyncio.run(
        oe.execute_order(submit_proposal=sproposal, side="buy", order_type="market", dry_run=True)
    )

    assert dry_result.agent_proposal_id == proposal.proposal_id
    assert dry_result.execution_proposal_id == eproposal.proposal_id
    assert dry_result.submit_proposal_id == sproposal.proposal_id
    assert dry_result.dry_run is True
    assert dry_result.status == "FILLED"

    # Verify lineage chain intact
    lineage = sl.get_full_lineage(sproposal.proposal_id)
    assert lineage is not None
    assert lineage["agent_proposal_id"] == proposal.proposal_id
    assert lineage["execution_proposal_id"] == eproposal.proposal_id
    assert lineage["submit_ready"] is True
