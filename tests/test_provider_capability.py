"""CR-048 Stage 3B-1 — ProviderCapability + SymbolMetadata contract tests.

Covers:
  - ProviderCapability frozen dataclass
  - is_screening_capable() pure function
  - SymbolMetadata frozen dataclass
  - compute_listing_age() pure function
  - Capability × Failure Mode cross-reference
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.services.data_provider import (
    ProviderCapability,
    SymbolMetadata,
    compute_listing_age,
    is_screening_capable,
)


# ── ProviderCapability ───────────────────────────────────────────────


class TestProviderCapability:
    def test_frozen(self):
        cap = ProviderCapability(provider_name="test")
        with pytest.raises(AttributeError):
            cap.supports_volume = True  # type: ignore

    def test_default_values(self):
        cap = ProviderCapability(provider_name="test")
        assert cap.supports_volume is False
        assert cap.supports_spread is False
        assert cap.supports_atr is False
        assert cap.supports_adx is False
        assert cap.supports_price_vs_ma is False
        assert cap.supports_market_cap is False
        assert cap.supports_per is False
        assert cap.supports_roe is False
        assert cap.supports_tvl is False
        assert cap.supports_available_bars is False
        assert cap.supports_sharpe is False
        assert cap.supports_missing_pct is False
        assert cap.supports_listing_age is False
        assert cap.freshness_granularity == "unknown"
        assert cap.partial_data_policy == "reject"
        assert cap.stale_data_policy == "reject"
        assert cap.symbol_namespace == "unknown"
        assert cap.max_batch_size == 1

    def test_all_fields_present(self):
        """ProviderCapability has exactly 20 fields."""
        import dataclasses

        fields = dataclasses.fields(ProviderCapability)
        assert len(fields) == 20

    def test_custom_values(self):
        cap = ProviderCapability(
            provider_name="binance_ccxt",
            supported_asset_classes=frozenset(["CRYPTO"]),
            supports_volume=True,
            supports_atr=True,
            supports_adx=True,
            supports_available_bars=True,
            freshness_granularity="1m",
            symbol_namespace="ccxt",
            max_batch_size=50,
        )
        assert cap.provider_name == "binance_ccxt"
        assert "CRYPTO" in cap.supported_asset_classes
        assert cap.freshness_granularity == "1m"
        assert cap.max_batch_size == 50

    def test_supported_asset_classes_is_frozenset(self):
        cap = ProviderCapability(
            provider_name="test",
            supported_asset_classes=frozenset(["CRYPTO", "US_STOCK"]),
        )
        assert isinstance(cap.supported_asset_classes, frozenset)


# ── is_screening_capable ─────────────────────────────────────────────


class TestIsScreeningCapable:
    def test_all_true_capable(self):
        cap = ProviderCapability(
            provider_name="full",
            supports_volume=True,
            supports_atr=True,
            supports_adx=True,
            supports_available_bars=True,
        )
        assert is_screening_capable(cap) is True

    def test_missing_volume_not_capable(self):
        cap = ProviderCapability(
            provider_name="no_vol",
            supports_atr=True,
            supports_adx=True,
            supports_available_bars=True,
        )
        assert is_screening_capable(cap) is False

    def test_missing_atr_not_capable(self):
        cap = ProviderCapability(
            provider_name="no_atr",
            supports_volume=True,
            supports_adx=True,
            supports_available_bars=True,
        )
        assert is_screening_capable(cap) is False

    def test_missing_adx_not_capable(self):
        cap = ProviderCapability(
            provider_name="no_adx",
            supports_volume=True,
            supports_atr=True,
            supports_available_bars=True,
        )
        assert is_screening_capable(cap) is False

    def test_missing_bars_not_capable(self):
        cap = ProviderCapability(
            provider_name="no_bars",
            supports_volume=True,
            supports_atr=True,
            supports_adx=True,
        )
        assert is_screening_capable(cap) is False

    def test_default_not_capable(self):
        cap = ProviderCapability(provider_name="default")
        assert is_screening_capable(cap) is False

    def test_extra_capabilities_still_capable(self):
        """Having extra capabilities doesn't break screening check."""
        cap = ProviderCapability(
            provider_name="rich",
            supports_volume=True,
            supports_atr=True,
            supports_adx=True,
            supports_available_bars=True,
            supports_per=True,
            supports_roe=True,
            supports_tvl=True,
        )
        assert is_screening_capable(cap) is True


# ── SymbolMetadata ───────────────────────────────────────────────────


class TestSymbolMetadata:
    def test_frozen(self):
        meta = SymbolMetadata(symbol="BTC/USDT", market="crypto")
        with pytest.raises(AttributeError):
            meta.is_active = False  # type: ignore

    def test_default_values(self):
        meta = SymbolMetadata(symbol="AAPL", market="us_stock")
        assert meta.listing_age_days is None
        assert meta.is_active is True
        assert meta.as_of is None
        assert meta.metadata_origin == "unknown"

    def test_full_construction(self):
        now = datetime.now(timezone.utc)
        meta = SymbolMetadata(
            symbol="005930",
            market="kr_stock",
            listing_age_days=10000,
            is_active=True,
            as_of=now,
            metadata_origin="krx",
        )
        assert meta.symbol == "005930"
        assert meta.listing_age_days == 10000
        assert meta.metadata_origin == "krx"

    def test_required_fields(self):
        """symbol and market are required."""
        with pytest.raises(TypeError):
            SymbolMetadata()  # type: ignore

    def test_inactive_symbol(self):
        meta = SymbolMetadata(
            symbol="DELISTED",
            market="us_stock",
            is_active=False,
        )
        assert meta.is_active is False


# ── compute_listing_age ──────────────────────────────────────────────


class TestComputeListingAge:
    def test_known_date(self):
        listing = date(2020, 1, 1)
        as_of = date(2026, 4, 3)
        age = compute_listing_age(listing, as_of)
        assert age is not None
        assert age > 2000

    def test_unknown_date(self):
        assert compute_listing_age(None, date(2026, 4, 3)) is None

    def test_same_day(self):
        d = date(2026, 4, 3)
        assert compute_listing_age(d, d) == 0

    def test_one_year(self):
        listing = date(2025, 4, 3)
        as_of = date(2026, 4, 3)
        age = compute_listing_age(listing, as_of)
        assert age == 365 or age == 366  # leap year tolerance

    def test_is_pure_function(self):
        """compute_listing_age has no I/O — just date arithmetic."""
        import inspect

        src = inspect.getsource(compute_listing_age)
        assert "open(" not in src
        assert "os." not in src
        assert "await" not in src


# ── Capability × Failure Mode Cross-reference ────────────────────────


class TestCapabilityCrossModes:
    def test_missing_volume_maps_to_partial_reject(self):
        """supports_volume=False → ScreeningInput will have volume=None → F2."""
        cap = ProviderCapability(
            provider_name="no_vol",
            supports_atr=True,
            supports_adx=True,
            supports_available_bars=True,
        )
        assert not cap.supports_volume
        assert not is_screening_capable(cap)

    def test_missing_listing_age_is_known_gap(self):
        """supports_listing_age=False → F6 MISSING_LISTING_AGE."""
        cap = ProviderCapability(provider_name="no_listing")
        assert not cap.supports_listing_age

    def test_all_mandatory_capable(self):
        cap = ProviderCapability(
            provider_name="full",
            supports_volume=True,
            supports_atr=True,
            supports_adx=True,
            supports_available_bars=True,
        )
        assert is_screening_capable(cap)
