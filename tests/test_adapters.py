"""
Exchange Adapter Tests — K-Dexter AOS v4

Tests all 5 adapters: Binance, Bitget, Upbit, KIS, Kiwoom
Each adapter tested for:
  1. exchange_id property
  2. DRY_RUN buy/sell simulation
  3. DRY_RUN balance query
  4. DRY_RUN position query
  5. Risk check pass/fail
  6. verify / cancel (placeholder)

Run: python tests/test_adapters.py
"""
from __future__ import annotations

import asyncio
import sys

from kdexter.tcl.commands import (
    TCLCommand, CommandType, ExecutionMode, OrderType, CommandTranscript,
)
from kdexter.tcl.adapters.binance import BinanceAdapter
from kdexter.tcl.adapters.bitget import BitgetAdapter
from kdexter.tcl.adapters.upbit import UpbitAdapter
from kdexter.tcl.adapters.kis import KISAdapter
from kdexter.tcl.adapters.kiwoom import KiwoomAdapter


# ─────────────────────────────────────────────────────────────────────────── #
# Helpers
# ─────────────────────────────────────────────────────────────────────────── #

def _buy_cmd(exchange: str, symbol: str = "BTC/KRW",
             qty: float = 0.01, price: float = 50_000_000) -> TCLCommand:
    return TCLCommand(
        command_type=CommandType.ORDER_BUY,
        exchange=exchange,
        mode=ExecutionMode.DRY_RUN,
        symbol=symbol,
        quantity=qty,
        price=price,
        order_type=OrderType.LIMIT,
    )


def _sell_cmd(exchange: str, symbol: str = "BTC/KRW",
              qty: float = 0.01, price: float = 51_000_000) -> TCLCommand:
    return TCLCommand(
        command_type=CommandType.ORDER_SELL,
        exchange=exchange,
        mode=ExecutionMode.DRY_RUN,
        symbol=symbol,
        quantity=qty,
        price=price,
        order_type=OrderType.LIMIT,
    )


def _balance_cmd(exchange: str) -> TCLCommand:
    return TCLCommand(
        command_type=CommandType.BALANCE_QUERY,
        exchange=exchange,
        mode=ExecutionMode.DRY_RUN,
    )


def _position_cmd(exchange: str) -> TCLCommand:
    return TCLCommand(
        command_type=CommandType.POSITION_QUERY,
        exchange=exchange,
        mode=ExecutionMode.DRY_RUN,
    )


def _risk_cmd(exchange: str, qty: float = 0.01, price: float = 50_000_000,
              cap_key: str = "order_cap_krw", cap: float = 10_000_000) -> TCLCommand:
    return TCLCommand(
        command_type=CommandType.RISK_CHECK,
        exchange=exchange,
        mode=ExecutionMode.DRY_RUN,
        symbol="BTC/KRW",
        quantity=qty,
        price=price,
        extra={cap_key: cap},
    )


# ─────────────────────────────────────────────────────────────────────────── #
# Test suite for each adapter
# ─────────────────────────────────────────────────────────────────────────── #

def _test_adapter(name: str, adapter, exchange_id: str,
                  risk_cap_key: str = "order_cap_krw",
                  risk_cap: float = 10_000_000,
                  buy_symbol: str = "BTC/KRW",
                  buy_qty: float = 0.01,
                  buy_price: float = 50_000_000):
    """Generic test suite for an adapter."""
    results = []

    # 1. exchange_id
    assert adapter.exchange_id == exchange_id, f"Expected {exchange_id}, got {adapter.exchange_id}"
    results.append(f"  exchange_id = {exchange_id}")

    # 2. DRY_RUN buy
    cmd = _buy_cmd(exchange_id, buy_symbol, buy_qty, buy_price)
    t = asyncio.run(adapter.dry_run(cmd))
    assert t.succeeded, f"DRY_RUN buy failed: {t.error}"
    assert t.exchange_order_id is not None
    assert t.exchange_order_id.startswith("DRY-")
    results.append("  DRY_RUN buy  OK")

    # 3. DRY_RUN sell
    cmd = _sell_cmd(exchange_id, buy_symbol, buy_qty, buy_price)
    t = asyncio.run(adapter.dry_run(cmd))
    assert t.succeeded, f"DRY_RUN sell failed: {t.error}"
    results.append("  DRY_RUN sell  OK")

    # 4. Balance query
    cmd = _balance_cmd(exchange_id)
    t = asyncio.run(adapter.dry_run(cmd))
    assert t.succeeded, f"Balance query failed: {t.error}"
    results.append("  Balance query  OK")

    # 5. Position query
    cmd = _position_cmd(exchange_id)
    t = asyncio.run(adapter.dry_run(cmd))
    assert t.succeeded, f"Position query failed: {t.error}"
    results.append("  Position query  OK")

    # 6. Risk check — PASS (value well within cap and above minimums)
    cmd = _risk_cmd(exchange_id, 1, 10_000, risk_cap_key, risk_cap)
    t = asyncio.run(adapter.dry_run(cmd))
    assert t.succeeded, f"Risk check (pass) failed: {t.error}"
    results.append("  Risk check PASS  OK")

    # 7. Risk check — FAIL (exceed cap)
    cmd = _risk_cmd(exchange_id, 1000, 1_000_000, risk_cap_key, 100)
    t = asyncio.run(adapter.dry_run(cmd))
    assert not t.succeeded, "Risk check should have failed"
    assert "RISK.CHECK failed" in t.error
    results.append("  Risk check FAIL  OK")

    # 8. Verify
    t = asyncio.run(adapter.verify("TEST-ORDER-001"))
    assert t.succeeded, f"Verify failed: {t.error}"
    assert t.verification_result is True
    results.append("  Verify  OK")

    # 9. Cancel
    t = asyncio.run(adapter.cancel("TEST-ORDER-001"))
    assert t.succeeded, f"Cancel failed: {t.error}"
    results.append("  Cancel  OK")

    return results


# ─────────────────────────────────────────────────────────────────────────── #
# Individual adapter tests
# ─────────────────────────────────────────────────────────────────────────── #

def test_binance():
    adapter = BinanceAdapter()
    _test_adapter("Binance", adapter, "binance")

def test_bitget():
    adapter = BitgetAdapter()
    _test_adapter("Bitget", adapter, "bitget",
                  risk_cap_key="order_cap_usdt", risk_cap=10_000,
                  buy_symbol="BTC/USDT", buy_qty=0.001, buy_price=60_000)

def test_upbit():
    adapter = UpbitAdapter()
    _test_adapter("Upbit", adapter, "upbit")

def test_kis():
    adapter = KISAdapter(account_no="50123456-01")
    _test_adapter("KIS", adapter, "kis",
                  risk_cap_key="order_cap_krw", risk_cap=50_000_000,
                  buy_symbol="005930/KRW", buy_qty=10, buy_price=70_000)

def test_kiwoom():
    adapter = KiwoomAdapter(account_no="1234567890")
    _test_adapter("Kiwoom", adapter, "kiwoom",
                  risk_cap_key="order_cap_krw", risk_cap=50_000_000,
                  buy_symbol="005930/KRW", buy_qty=10, buy_price=70_000)


# ─────────────────────────────────────────────────────────────────────────── #
# TCLDispatcher integration test
# ─────────────────────────────────────────────────────────────────────────── #

def test_dispatcher_all_adapters():
    """Register all 5 adapters and dispatch DRY_RUN commands."""
    from kdexter.tcl.commands import TCLDispatcher

    dispatcher = TCLDispatcher()
    dispatcher.register("binance", BinanceAdapter())
    dispatcher.register("bitget", BitgetAdapter())
    dispatcher.register("upbit", UpbitAdapter())
    dispatcher.register("kis", KISAdapter(account_no="50123456-01"))
    dispatcher.register("kiwoom", KiwoomAdapter(account_no="1234567890"))

    results = []
    for exch in ["binance", "bitget", "upbit", "kis", "kiwoom"]:
        cmd = TCLCommand(
            command_type=CommandType.BALANCE_QUERY,
            exchange=exch,
            mode=ExecutionMode.DRY_RUN,
        )
        t = asyncio.run(dispatcher.dispatch(cmd))
        assert t.succeeded, f"Dispatcher {exch} failed: {t.error}"
        results.append(f"  {exch} dispatch  OK")


def test_upbit_symbol_conversion():
    """Upbit symbol conversion: BTC/KRW ↔ KRW-BTC."""
    assert UpbitAdapter._to_upbit_symbol("BTC/KRW") == "KRW-BTC"
    assert UpbitAdapter._to_upbit_symbol("ETH/KRW") == "KRW-ETH"
    assert UpbitAdapter._from_upbit_symbol("KRW-BTC") == "BTC/KRW"


def test_kis_code_conversion():
    """KIS code conversion: 005930/KRW → 005930."""
    assert KISAdapter._to_kis_code("005930/KRW") == "005930"
    assert KISAdapter._to_kis_code("005930") == "005930"


def test_kiwoom_code_conversion():
    """Kiwoom code conversion: 005930/KRW → 005930."""
    assert KiwoomAdapter._to_kiwoom_code("005930/KRW") == "005930"
    assert KiwoomAdapter._to_kiwoom_code("005930") == "005930"


# ─────────────────────────────────────────────────────────────────────────── #
# Runner
# ─────────────────────────────────────────────────────────────────────────── #

if __name__ == "__main__":
    print("\nExchange Adapter Tests")
    print("=" * 60)

    tests = [
        ("Binance", test_binance),
        ("Bitget", test_bitget),
        ("Upbit", test_upbit),
        ("KIS (한국투자증권)", test_kis),
        ("Kiwoom (키움증권)", test_kiwoom),
        ("TCLDispatcher (all 5)", test_dispatcher_all_adapters),
        ("Upbit Symbol Conv", test_upbit_symbol_conversion),
        ("KIS Code Conv", test_kis_code_conversion),
        ("Kiwoom Code Conv", test_kiwoom_code_conversion),
    ]

    total = 0
    passed = 0
    failed_tests = []

    for name, fn in tests:
        total += 1
        print(f"\n--- {name} ---")
        try:
            results = fn()
            for r in results:
                print(r)
            passed += 1
        except Exception as e:
            failed_tests.append((name, str(e)))
            print(f"  FAILED: {e}")

    print(f"\n{'=' * 60}")
    print(f"Results: {passed}/{total} test groups passed")
    if failed_tests:
        print("FAILED:")
        for name, err in failed_tests:
            print(f"  - {name}: {err}")
        sys.exit(1)
    else:
        print("All tests PASSED")
