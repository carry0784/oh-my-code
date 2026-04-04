"""Tests for Stage 3A: DataProvider — ABC/Protocol interface contracts.

Covers:
  - All ABC classes are truly abstract (cannot instantiate)
  - Data contracts (frozen dataclasses, correct fields)
  - DataQuality enum completeness
  - Interface Purity Proof (no implementation, no external calls)
"""

from __future__ import annotations

import ast
import pathlib
from datetime import datetime, timezone

import pytest

from app.services.data_provider import (
    DataQuality,
    MarketDataSnapshot,
    FundamentalSnapshot,
    BacktestReadiness,
    ProviderStatus,
    MarketDataProvider,
    FundamentalDataProvider,
    BacktestDataProvider,
    ScreeningDataProvider,
)


# ── DataQuality Enum ────────────────────────────────────────────────


class TestDataQuality:
    def test_all_quality_levels(self):
        expected = {"high", "degraded", "stale", "unavailable"}
        actual = {q.value for q in DataQuality}
        assert expected == actual

    def test_is_str_enum(self):
        assert isinstance(DataQuality.HIGH, str)


# ── Data Contracts ──────────────────────────────────────────────────


class TestMarketDataSnapshot:
    def test_default_quality_is_unavailable(self):
        snap = MarketDataSnapshot(symbol="BTC/USDT")
        assert snap.quality == DataQuality.UNAVAILABLE

    def test_all_fields_optional_except_symbol(self):
        snap = MarketDataSnapshot(symbol="SOL/USDT")
        assert snap.price_usd is None
        assert snap.market_cap_usd is None
        assert snap.avg_daily_volume_usd is None
        assert snap.spread_pct is None
        assert snap.atr_pct is None
        assert snap.adx is None
        assert snap.price_vs_200ma is None

    def test_frozen(self):
        snap = MarketDataSnapshot(symbol="BTC/USDT", price_usd=50000.0)
        with pytest.raises(AttributeError):
            snap.price_usd = 60000.0  # type: ignore

    def test_with_full_data(self):
        now = datetime.now(timezone.utc)
        snap = MarketDataSnapshot(
            symbol="BTC/USDT",
            timestamp=now,
            price_usd=50000.0,
            market_cap_usd=1_000_000_000_000,
            avg_daily_volume_usd=30_000_000_000,
            spread_pct=0.01,
            atr_pct=3.5,
            adx=25.0,
            price_vs_200ma=1.1,
            quality=DataQuality.HIGH,
        )
        assert snap.quality == DataQuality.HIGH
        assert snap.atr_pct == 3.5


class TestFundamentalSnapshot:
    def test_default_quality_is_unavailable(self):
        snap = FundamentalSnapshot(symbol="AAPL")
        assert snap.quality == DataQuality.UNAVAILABLE

    def test_frozen(self):
        snap = FundamentalSnapshot(symbol="AAPL", per=25.0)
        with pytest.raises(AttributeError):
            snap.per = 30.0  # type: ignore

    def test_defi_fields(self):
        snap = FundamentalSnapshot(
            symbol="UNI/USDT",
            tvl_usd=500_000_000,
            active_addresses_trend=0.05,
            quality=DataQuality.HIGH,
        )
        assert snap.tvl_usd == 500_000_000

    def test_stock_fields(self):
        snap = FundamentalSnapshot(
            symbol="AAPL",
            per=28.5,
            roe=45.0,
            revenue_growth_pct=8.2,
            operating_margin_pct=30.0,
            quality=DataQuality.HIGH,
        )
        assert snap.roe == 45.0


class TestBacktestReadiness:
    def test_default_quality_is_unavailable(self):
        snap = BacktestReadiness(symbol="SOL/USDT")
        assert snap.quality == DataQuality.UNAVAILABLE

    def test_frozen(self):
        snap = BacktestReadiness(symbol="SOL/USDT", available_bars=1000)
        with pytest.raises(AttributeError):
            snap.available_bars = 2000  # type: ignore

    def test_with_full_data(self):
        snap = BacktestReadiness(
            symbol="SOL/USDT",
            available_bars=1500,
            sharpe_ratio=1.2,
            missing_data_pct=0.5,
            quality=DataQuality.HIGH,
        )
        assert snap.sharpe_ratio == 1.2


class TestProviderStatus:
    def test_default_unavailable(self):
        status = ProviderStatus(provider_name="coingecko")
        assert status.is_available is False

    def test_frozen(self):
        status = ProviderStatus(provider_name="coingecko", is_available=True)
        with pytest.raises(AttributeError):
            status.is_available = False  # type: ignore


# ── ABC Instantiation Tests ─────────────────────────────────────────


class TestABCCannotInstantiate:
    def test_market_data_provider_is_abstract(self):
        with pytest.raises(TypeError, match="abstract"):
            MarketDataProvider()  # type: ignore

    def test_fundamental_data_provider_is_abstract(self):
        with pytest.raises(TypeError, match="abstract"):
            FundamentalDataProvider()  # type: ignore

    def test_backtest_data_provider_is_abstract(self):
        with pytest.raises(TypeError, match="abstract"):
            BacktestDataProvider()  # type: ignore

    def test_screening_data_provider_is_abstract(self):
        with pytest.raises(TypeError, match="abstract"):
            ScreeningDataProvider()  # type: ignore


# ── ABC Method Contracts ────────────────────────────────────────────


class TestABCMethodContracts:
    def test_market_data_provider_has_get_market_data(self):
        assert hasattr(MarketDataProvider, "get_market_data")

    def test_market_data_provider_has_get_market_data_batch(self):
        assert hasattr(MarketDataProvider, "get_market_data_batch")

    def test_market_data_provider_has_health_check(self):
        assert hasattr(MarketDataProvider, "health_check")

    def test_fundamental_data_provider_has_get_fundamentals(self):
        assert hasattr(FundamentalDataProvider, "get_fundamentals")

    def test_fundamental_data_provider_has_health_check(self):
        assert hasattr(FundamentalDataProvider, "health_check")

    def test_backtest_data_provider_has_get_readiness(self):
        assert hasattr(BacktestDataProvider, "get_readiness")

    def test_backtest_data_provider_has_health_check(self):
        assert hasattr(BacktestDataProvider, "health_check")

    def test_screening_data_provider_has_get_screening_data(self):
        assert hasattr(ScreeningDataProvider, "get_screening_data")

    def test_screening_data_provider_has_get_provider_statuses(self):
        assert hasattr(ScreeningDataProvider, "get_provider_statuses")


# ── Interface Purity Proof ──────────────────────────────────────────


class TestInterfacePurityProof:
    """Verify data_provider.py is interface-only: no implementation."""

    _SOURCE_PATH = pathlib.Path("app/services/data_provider.py")

    def _get_source(self) -> str:
        return self._SOURCE_PATH.read_text(encoding="utf-8")

    def test_no_httpx_or_requests(self):
        src = self._get_source()
        assert "httpx" not in src
        assert "import requests" not in src

    def test_no_aiohttp(self):
        src = self._get_source()
        assert "aiohttp" not in src

    def test_no_sqlalchemy(self):
        src = self._get_source()
        assert "sqlalchemy" not in src

    def test_no_celery(self):
        src = self._get_source()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "celery" not in node.module.lower()

    def test_no_concrete_implementation(self):
        """No method body beyond `...` or `pass` or docstrings in ABC methods."""
        src = self._get_source()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                body = node.body
                for stmt in body:
                    if isinstance(stmt, ast.Expr):
                        # docstring (str Constant) or Ellipsis (... Constant)
                        if isinstance(stmt.value, ast.Constant):
                            continue
                    elif isinstance(stmt, ast.Pass):
                        continue
                    else:
                        pytest.fail(f"Method {node.name} has implementation code: {ast.dump(stmt)}")

    def test_no_os_or_env_access(self):
        src = self._get_source()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module not in ("os", "os.path", "dotenv")

    def test_no_json_file_operations(self):
        """No file read/write operations."""
        src = self._get_source()
        assert "open(" not in src
        assert "Path(" not in src or "pathlib" not in src


# ── Stage 3B-1: ProviderCapability Purity ─────────────────────────────


class TestProviderCapabilityPurity:
    """Verify Stage 3B-1 additions maintain data_provider purity."""

    def test_capability_in_data_provider_module(self):
        from app.services.data_provider import ProviderCapability

        assert ProviderCapability is not None

    def test_capability_is_frozen(self):
        from app.services.data_provider import ProviderCapability

        cap = ProviderCapability(provider_name="test")
        with pytest.raises(AttributeError):
            cap.supports_volume = True  # type: ignore

    def test_symbol_metadata_in_module(self):
        from app.services.data_provider import SymbolMetadata

        assert SymbolMetadata is not None

    def test_symbol_metadata_is_frozen(self):
        from app.services.data_provider import SymbolMetadata

        meta = SymbolMetadata(symbol="X", market="crypto")
        with pytest.raises(AttributeError):
            meta.is_active = False  # type: ignore

    def test_data_provider_purity_maintained(self):
        """data_provider.py still has no forbidden imports after 3B-1."""
        src = pathlib.Path("app/services/data_provider.py").read_text(encoding="utf-8")
        for forbidden in ["httpx", "import requests", "aiohttp", "sqlalchemy"]:
            assert forbidden not in src
