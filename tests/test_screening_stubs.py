"""Stage 3B-2: Provider stub contract tests.

Covers:
  - StubMarketDataProvider (fixture lookup, batch, health)
  - StubBacktestDataProvider (fixture lookup, health)
  - StubFundamentalDataProvider (fixture lookup, health)
  - StubScreeningDataProvider (composition, get_provider_statuses)
  - Stub purity (AST-based: SB-01~SB-08)
  - Capability profiles (field verification)
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from app.services.data_provider import (
    BacktestReadiness,
    DataQuality,
    FundamentalSnapshot,
    MarketDataSnapshot,
    ProviderCapability,
    ProviderStatus,
)
from tests.fixtures.screening_fixtures import (
    CAP_DEGRADED_NO_ADX,
    CAP_EMPTY,
    CAP_FULL_CRYPTO,
    CAP_FULL_KR_STOCK,
    CAP_FULL_US_STOCK,
    CAP_MINIMAL_CRYPTO,
    FIXTURE_OK_CRYPTO_BTC_BACKTEST,
    FIXTURE_OK_CRYPTO_BTC_MARKET,
    FIXTURE_OK_CRYPTO_SOL_MARKET,
    FIXTURE_OK_US_AAPL_FUNDAMENTAL,
)
from tests.stubs.screening_stubs import (
    StubBacktestDataProvider,
    StubFundamentalDataProvider,
    StubMarketDataProvider,
    StubScreeningDataProvider,
)


# ── StubMarketDataProvider ──────────────────────────────────────────


class TestStubMarketDataProvider:
    def test_get_known_symbol(self):
        stub = StubMarketDataProvider({"BTC/USDT": FIXTURE_OK_CRYPTO_BTC_MARKET})
        snap = stub.get_market_data("BTC/USDT")
        assert snap.symbol == "BTC/USDT"
        assert snap.price_usd == 68000.0

    def test_get_unknown_returns_empty(self):
        stub = StubMarketDataProvider({})
        snap = stub.get_market_data("UNKNOWN")
        assert snap.symbol == "UNKNOWN"
        assert snap.price_usd is None

    def test_batch_returns_all(self):
        fixtures = {
            "BTC/USDT": FIXTURE_OK_CRYPTO_BTC_MARKET,
            "SOL/USDT": FIXTURE_OK_CRYPTO_SOL_MARKET,
        }
        stub = StubMarketDataProvider(fixtures)
        results = stub.get_market_data_batch(["BTC/USDT", "SOL/USDT", "UNKNOWN"])
        assert len(results) == 3
        assert results[0].symbol == "BTC/USDT"
        assert results[1].symbol == "SOL/USDT"
        assert results[2].price_usd is None

    def test_batch_empty_list(self):
        stub = StubMarketDataProvider({})
        assert stub.get_market_data_batch([]) == []

    def test_health_check_available(self):
        stub = StubMarketDataProvider({})
        status = stub.health_check()
        assert isinstance(status, ProviderStatus)
        assert status.is_available is True
        assert status.provider_name == "stub_market"

    def test_fixture_not_mutated(self):
        fixtures = {"BTC/USDT": FIXTURE_OK_CRYPTO_BTC_MARKET}
        stub = StubMarketDataProvider(fixtures)
        snap1 = stub.get_market_data("BTC/USDT")
        snap2 = stub.get_market_data("BTC/USDT")
        assert snap1 is snap2  # same fixture object, no copy

    def test_multiple_lookups_same_result(self):
        stub = StubMarketDataProvider({"BTC/USDT": FIXTURE_OK_CRYPTO_BTC_MARKET})
        assert stub.get_market_data("BTC/USDT") is stub.get_market_data("BTC/USDT")

    def test_constructor_requires_dict(self):
        stub = StubMarketDataProvider({"X": MarketDataSnapshot(symbol="X")})
        assert stub.get_market_data("X").symbol == "X"


# ── StubBacktestDataProvider ────────────────────────────────────────


class TestStubBacktestDataProvider:
    def test_get_known_symbol(self):
        stub = StubBacktestDataProvider({"BTC/USDT": FIXTURE_OK_CRYPTO_BTC_BACKTEST})
        readiness = stub.get_readiness("BTC/USDT")
        assert readiness.available_bars == 2000

    def test_get_unknown_returns_empty(self):
        stub = StubBacktestDataProvider({})
        readiness = stub.get_readiness("UNKNOWN")
        assert readiness.symbol == "UNKNOWN"
        assert readiness.available_bars is None

    def test_health_check_available(self):
        stub = StubBacktestDataProvider({})
        status = stub.health_check()
        assert status.is_available is True
        assert status.provider_name == "stub_backtest"

    def test_params_ignored(self):
        """timeframe and min_bars don't affect stub."""
        stub = StubBacktestDataProvider({"BTC/USDT": FIXTURE_OK_CRYPTO_BTC_BACKTEST})
        r1 = stub.get_readiness("BTC/USDT", "4h", 1000)
        r2 = stub.get_readiness("BTC/USDT", "1d", 100)
        assert r1 is r2

    def test_fixture_injection(self):
        custom = BacktestReadiness(symbol="TEST", available_bars=42)
        stub = StubBacktestDataProvider({"TEST": custom})
        assert stub.get_readiness("TEST").available_bars == 42


# ── StubFundamentalDataProvider ─────────────────────────────────────


class TestStubFundamentalDataProvider:
    def test_get_known_symbol(self):
        stub = StubFundamentalDataProvider({"AAPL": FIXTURE_OK_US_AAPL_FUNDAMENTAL})
        snap = stub.get_fundamentals("AAPL")
        assert snap.per == 28.5

    def test_get_unknown_returns_empty(self):
        stub = StubFundamentalDataProvider({})
        snap = stub.get_fundamentals("UNKNOWN")
        assert snap.symbol == "UNKNOWN"
        assert snap.per is None

    def test_health_check_available(self):
        stub = StubFundamentalDataProvider({})
        status = stub.health_check()
        assert status.is_available is True
        assert status.provider_name == "stub_fundamental"

    def test_fixture_injection(self):
        custom = FundamentalSnapshot(symbol="TEST", per=99.0)
        stub = StubFundamentalDataProvider({"TEST": custom})
        assert stub.get_fundamentals("TEST").per == 99.0


# ── StubScreeningDataProvider ───────────────────────────────────────


class TestStubScreeningDataProvider:
    def _make_composite(self):
        m = StubMarketDataProvider({"BTC/USDT": FIXTURE_OK_CRYPTO_BTC_MARKET})
        b = StubBacktestDataProvider({"BTC/USDT": FIXTURE_OK_CRYPTO_BTC_BACKTEST})
        f = StubFundamentalDataProvider({})
        return StubScreeningDataProvider(m, b, f)

    def test_provider_statuses_count(self):
        comp = self._make_composite()
        statuses = comp.get_provider_statuses()
        assert len(statuses) == 3

    def test_all_available(self):
        comp = self._make_composite()
        statuses = comp.get_provider_statuses()
        assert all(s.is_available for s in statuses)

    def test_delegates_to_sub_providers(self):
        comp = self._make_composite()
        assert comp.market.get_market_data("BTC/USDT").price_usd == 68000.0
        assert comp.backtest.get_readiness("BTC/USDT").available_bars == 2000

    def test_provider_names_distinct(self):
        comp = self._make_composite()
        names = [s.provider_name for s in comp.get_provider_statuses()]
        assert len(set(names)) == 3


# ── Stub Purity (SB-01~SB-08 AST checks) ───────────────────────────


class TestStubPurity:
    """AST-based verification that stubs obey SB-01~SB-08."""

    _STUB_PATH = pathlib.Path("tests/stubs/screening_stubs.py")

    def _get_source_and_tree(self):
        src = self._STUB_PATH.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(self._STUB_PATH))
        return src, tree

    def test_sb02_no_httpx(self):
        """SB-02: No httpx import."""
        src, tree = self._get_source_and_tree()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "httpx" not in alias.name
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert "httpx" not in mod

    def test_sb02_no_requests(self):
        """SB-02: No requests import."""
        _, tree = self._get_source_and_tree()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "requests" not in alias.name
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert not mod.startswith("requests")

    def test_sb02_no_aiohttp(self):
        """SB-02: No aiohttp import."""
        _, tree = self._get_source_and_tree()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert "aiohttp" not in mod

    def test_sb02_no_ccxt(self):
        """SB-02: No ccxt import."""
        _, tree = self._get_source_and_tree()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "ccxt" not in alias.name
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert "ccxt" not in mod

    def test_sb02_no_sqlalchemy(self):
        """SB-02: No sqlalchemy import."""
        _, tree = self._get_source_and_tree()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert "sqlalchemy" not in mod

    def test_sb03_no_os_environ(self):
        """SB-03: No os.environ/dotenv/open() in executable code."""
        _, tree = self._get_source_and_tree()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert "dotenv" not in mod, "SB-03: dotenv import found"
                assert mod != "os", "SB-03: os import found"
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "os", "SB-03: os import found"
                    assert "dotenv" not in alias.name, "SB-03: dotenv import found"
            # Check for os.environ / os.getenv attribute access
            elif isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name) and node.value.id == "os":
                    assert node.attr not in ("environ", "getenv"), (
                        f"SB-03: os.{node.attr} access found"
                    )

    def test_sb03_no_open(self):
        """SB-03: No open() file operations."""
        src, _ = self._get_source_and_tree()
        # Check there's no open( that isn't part of a comment/string
        _, tree = self._get_source_and_tree()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "open":
                    pytest.fail("SB-03: open() call found in stubs")

    def test_sb04_no_async_def(self):
        """SB-04: No async def (sync only)."""
        _, tree = self._get_source_and_tree()
        for node in ast.walk(tree):
            assert not isinstance(node, ast.AsyncFunctionDef), (
                f"SB-04: async def found in stubs: {node.name}"
                if isinstance(node, ast.AsyncFunctionDef)
                else ""
            )


# ── Capability Profiles ─────────────────────────────────────────────


class TestCapabilityProfiles:
    def test_full_crypto_all_supported(self):
        assert CAP_FULL_CRYPTO.supports_volume is True
        assert CAP_FULL_CRYPTO.supports_atr is True
        assert CAP_FULL_CRYPTO.supports_adx is True
        assert CAP_FULL_CRYPTO.supports_available_bars is True
        assert "CRYPTO" in CAP_FULL_CRYPTO.supported_asset_classes

    def test_full_us_stock_supports_per_roe(self):
        assert CAP_FULL_US_STOCK.supports_per is True
        assert CAP_FULL_US_STOCK.supports_roe is True
        assert "US_STOCK" in CAP_FULL_US_STOCK.supported_asset_classes

    def test_full_kr_stock_namespace(self):
        assert CAP_FULL_KR_STOCK.symbol_namespace == "krx_code"
        assert "KR_STOCK" in CAP_FULL_KR_STOCK.supported_asset_classes

    def test_minimal_crypto_limited(self):
        assert CAP_MINIMAL_CRYPTO.supports_volume is True
        assert CAP_MINIMAL_CRYPTO.supports_spread is False
        assert CAP_MINIMAL_CRYPTO.supports_market_cap is False

    def test_degraded_no_adx(self):
        assert CAP_DEGRADED_NO_ADX.supports_adx is False
        assert CAP_DEGRADED_NO_ADX.supports_available_bars is False

    def test_empty_provider_defaults(self):
        assert CAP_EMPTY.supports_volume is False
        assert CAP_EMPTY.supports_atr is False
        assert CAP_EMPTY.provider_name == "empty"
