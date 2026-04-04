"""
Adapter Connection Tests — Rate Limiter, CcxtMixin, KIS Token, Kiwoom COM
K-Dexter AOS v4

Tests that work WITHOUT external dependencies (ccxt, pykiwoom, etc.).
Run: python -X utf8 tests/test_adapter_connections.py
"""
from __future__ import annotations

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from kdexter.tcl.adapters.rate_limiter import AsyncRateLimiter


def run(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# ======================================================================== #
# 1. Rate Limiter
# ======================================================================== #

def test_rate_limiter_init():
    rl = AsyncRateLimiter(max_calls=10, period=1.0)
    assert rl.max_calls == 10
    assert rl.period == 1.0
    print("  [1] Rate limiter init  OK")


def test_rate_limiter_invalid_args():
    try:
        AsyncRateLimiter(max_calls=0)
        assert False, "Should raise ValueError"
    except ValueError:
        pass
    try:
        AsyncRateLimiter(max_calls=5, period=0)
        assert False, "Should raise ValueError"
    except ValueError:
        pass
    print("  [2] Rate limiter invalid args  OK")


def test_rate_limiter_acquire():
    rl = AsyncRateLimiter(max_calls=5, period=1.0)

    async def acquire_n(n):
        for _ in range(n):
            await rl.acquire()

    # Should not block for burst within limit
    run(acquire_n(5))
    print("  [3] Rate limiter acquire burst  OK")


def test_rate_limiter_multiple():
    rl = AsyncRateLimiter(max_calls=100, period=1.0)

    async def acquire_many():
        for _ in range(50):
            await rl.acquire()

    run(acquire_many())
    print("  [4] Rate limiter 50 acquires  OK")


# ======================================================================== #
# 2. CcxtMixin — import guard
# ======================================================================== #

def test_ccxt_binance_no_ccxt():
    """Binance live order should fail gracefully without ccxt."""
    from kdexter.tcl.adapters.binance import BinanceAdapter
    adapter = BinanceAdapter(api_key="test", api_secret="test")
    # _get_client should raise RuntimeError if ccxt not installed
    # (or succeed if ccxt IS installed — either way, adapter works)
    try:
        adapter._get_client()
        # ccxt is installed — that's fine
        print("  [5] Binance ccxt available (live capable)  OK")
    except RuntimeError as e:
        assert "ccxt" in str(e).lower()
        print("  [5] Binance ccxt not installed (graceful fail)  OK")


def test_ccxt_bitget_no_ccxt():
    from kdexter.tcl.adapters.bitget import BitgetAdapter
    adapter = BitgetAdapter(api_key="test", api_secret="test")
    try:
        adapter._get_client()
        print("  [6] Bitget ccxt available  OK")
    except RuntimeError as e:
        assert "ccxt" in str(e).lower()
        print("  [6] Bitget ccxt not installed (graceful fail)  OK")


def test_ccxt_upbit_no_ccxt():
    from kdexter.tcl.adapters.upbit import UpbitAdapter
    adapter = UpbitAdapter(access_key="test", secret_key="test")
    try:
        adapter._get_client()
        print("  [7] Upbit ccxt available  OK")
    except RuntimeError as e:
        assert "ccxt" in str(e).lower()
        print("  [7] Upbit ccxt not installed (graceful fail)  OK")


# ======================================================================== #
# 3. KIS Token logic
# ======================================================================== #

def test_kis_token_validity():
    from kdexter.tcl.adapters.kis import KISAdapter
    from datetime import datetime, timedelta
    adapter = KISAdapter(appkey="test", appsecret="test")
    assert adapter._is_token_valid() is False
    # Simulate valid token
    adapter._access_token = "FAKE"
    adapter._token_expires = datetime.utcnow() + timedelta(hours=1)
    assert adapter._is_token_valid() is True
    # Simulate expired
    adapter._token_expires = datetime.utcnow() - timedelta(hours=1)
    assert adapter._is_token_valid() is False
    print("  [8] KIS token validity  OK")


def test_kis_token_no_key():
    from kdexter.tcl.adapters.kis import KISAdapter
    adapter = KISAdapter()  # no appkey/appsecret

    async def try_token():
        try:
            await adapter._ensure_token()
            assert False, "Should raise"
        except RuntimeError as e:
            assert "appkey" in str(e).lower()

    run(try_token())
    print("  [9] KIS token requires credentials  OK")


def test_kis_code_conversion():
    from kdexter.tcl.adapters.kis import KISAdapter
    assert KISAdapter._to_kis_code("005930/KRW") == "005930"
    assert KISAdapter._to_kis_code("005930") == "005930"
    assert KISAdapter._to_kis_code(None) == ""
    print("  [10] KIS code conversion  OK")


def test_kis_tr_id_mapping():
    from kdexter.tcl.adapters.kis import KISAdapter
    assert KISAdapter._get_tr_id("buy", True) == "VTTC0802U"
    assert KISAdapter._get_tr_id("sell", True) == "VTTC0801U"
    assert KISAdapter._get_tr_id("buy", False) == "TTTC0802U"
    assert KISAdapter._get_tr_id("sell", False) == "TTTC0801U"
    print("  [11] KIS TR ID mapping  OK")


def test_kis_headers():
    from kdexter.tcl.adapters.kis import KISAdapter
    adapter = KISAdapter(appkey="AK", appsecret="AS")
    adapter._access_token = "TOKEN"
    h = adapter._build_headers("VTTC0802U")
    assert h["authorization"] == "Bearer TOKEN"
    assert h["appkey"] == "AK"
    assert h["tr_id"] == "VTTC0802U"
    print("  [12] KIS headers  OK")


# ======================================================================== #
# 4. Kiwoom COM guard
# ======================================================================== #

def test_kiwoom_no_pykiwoom():
    from kdexter.tcl.adapters.kiwoom import KiwoomAdapter
    adapter = KiwoomAdapter(account_no="1234567890")
    try:
        adapter._get_api()
        print("  [13] Kiwoom pykiwoom available  OK")
    except RuntimeError as e:
        assert "pykiwoom" in str(e).lower() or "kiwoom" in str(e).lower()
        print("  [13] Kiwoom pykiwoom not installed (graceful fail)  OK")


def test_kiwoom_code_conversion():
    from kdexter.tcl.adapters.kiwoom import KiwoomAdapter
    assert KiwoomAdapter._to_kiwoom_code("005930/KRW") == "005930"
    assert KiwoomAdapter._to_kiwoom_code("005930") == "005930"
    assert KiwoomAdapter._to_kiwoom_code(None) == ""
    print("  [14] Kiwoom code conversion  OK")


def test_kiwoom_rate_limiter():
    from kdexter.tcl.adapters.kiwoom import KiwoomAdapter
    adapter = KiwoomAdapter()
    assert adapter._rate_limiter.max_calls == 5
    print("  [15] Kiwoom rate limiter configured  OK")


# ======================================================================== #
# 5. Dry run backward compatibility
# ======================================================================== #

def test_all_adapters_dry_run():
    """All 5 adapters' dry_run still works after refactoring."""
    from kdexter.tcl.adapters.binance import BinanceAdapter
    from kdexter.tcl.adapters.bitget import BitgetAdapter
    from kdexter.tcl.adapters.upbit import UpbitAdapter
    from kdexter.tcl.adapters.kis import KISAdapter
    from kdexter.tcl.adapters.kiwoom import KiwoomAdapter
    from kdexter.tcl.commands import TCLCommand, CommandType, OrderType

    adapters = [
        BinanceAdapter(),
        BitgetAdapter(),
        UpbitAdapter(),
        KISAdapter(),
        KiwoomAdapter(),
    ]

    async def run_dry_runs():
        for adapter in adapters:
            cmd = TCLCommand(
                command_type=CommandType.ORDER_BUY,
                exchange=adapter.exchange_id,
                symbol="BTC/KRW",
                quantity=0.1,
                price=50000000.0,
                order_type=OrderType.LIMIT,
            )
            t = await adapter.dry_run(cmd)
            assert t.succeeded, f"{adapter.exchange_id} dry_run failed: {t.error}"

    run(run_dry_runs())
    print("  [16] All 5 adapters dry_run OK")


# ======================================================================== #
# Runner
# ======================================================================== #

if __name__ == "__main__":
    print("\nAdapter Connection Tests")
    print("=" * 60)

    tests = [
        ("Rate Limiter", [
            test_rate_limiter_init,
            test_rate_limiter_invalid_args,
            test_rate_limiter_acquire,
            test_rate_limiter_multiple,
        ]),
        ("CcxtMixin Guard", [
            test_ccxt_binance_no_ccxt,
            test_ccxt_bitget_no_ccxt,
            test_ccxt_upbit_no_ccxt,
        ]),
        ("KIS Token & Config", [
            test_kis_token_validity,
            test_kis_token_no_key,
            test_kis_code_conversion,
            test_kis_tr_id_mapping,
            test_kis_headers,
        ]),
        ("Kiwoom COM Guard", [
            test_kiwoom_no_pykiwoom,
            test_kiwoom_code_conversion,
            test_kiwoom_rate_limiter,
        ]),
        ("Dry Run Compat", [
            test_all_adapters_dry_run,
        ]),
    ]

    total = 0
    passed = 0
    failed_tests = []

    for section, fns in tests:
        print(f"\n--- {section} ---")
        for fn in fns:
            total += 1
            try:
                fn()
                passed += 1
            except Exception as e:
                failed_tests.append((fn.__name__, str(e)))
                print(f"  FAILED: {fn.__name__}: {e}")

    print(f"\n{'=' * 60}")
    print(f"Results: {passed}/{total} passed")
    if failed_tests:
        print("FAILED:")
        for name, err in failed_tests:
            print(f"  - {name}: {err}")
        sys.exit(1)
    else:
        print("All tests PASSED")
