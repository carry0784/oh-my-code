"""Unit tests for app/services/symbol_registry.py (Card B-8 v1.1)."""
from __future__ import annotations

import pytest

from app.services.symbol_registry import (
    REGISTRY,
    SUPPORTED_VENUES,
    SymbolEntry,
    SymbolRegistry,
    VenueSymbol,
    _build_fallback_entries,
    build_default_registry,
)


# ---------------------------------------------------------------------------
# Default registry sanity
# ---------------------------------------------------------------------------
class TestDefaultRegistry:
    def test_registry_has_24_symbols(self):
        assert len(REGISTRY) == 24

    def test_all_24_available_on_both_venues(self):
        """Per probe 2026-04-16: 24/24 BOTH."""
        on_both = REGISTRY.canonicals_on_all(["binance", "bitget"])
        assert len(on_both) == 24

    def test_tier_distribution(self):
        assert len(REGISTRY.canonicals_by_tier("tier1")) == 8
        assert len(REGISTRY.canonicals_by_tier("tier2")) == 8
        assert len(REGISTRY.canonicals_by_tier("tier3")) == 8

    def test_supported_venues_constant(self):
        assert set(SUPPORTED_VENUES) == {"binance", "bitget"}


# ---------------------------------------------------------------------------
# Canonical ↔ venue mapping
# ---------------------------------------------------------------------------
class TestCanonicalMapping:
    def test_canonical_contains_known_symbol(self):
        assert "BTC/USDT" in REGISTRY
        assert "SEI/USDT" in REGISTRY

    def test_unknown_canonical_returns_none(self):
        assert REGISTRY.get("FAKECOIN/USDT") is None
        assert REGISTRY.to_venue_symbol("FAKECOIN/USDT", "binance") is None
        assert REGISTRY.to_venue_raw("FAKECOIN/USDT", "bitget") is None

    def test_to_venue_symbol_roundtrip(self):
        """canonical → venue_ccxt_symbol → canonical should round-trip."""
        for canonical in REGISTRY.all_canonicals():
            for venue in SUPPORTED_VENUES:
                venue_sym = REGISTRY.to_venue_symbol(canonical, venue)
                assert venue_sym is not None, f"{canonical}/{venue}"
                back = REGISTRY.canonical_from_ccxt(venue, venue_sym)
                assert back == canonical, f"{canonical}/{venue}: {venue_sym} → {back}"

    def test_to_venue_raw_roundtrip(self):
        """canonical → venue_raw_id → canonical should round-trip."""
        for canonical in REGISTRY.all_canonicals():
            for venue in SUPPORTED_VENUES:
                raw = REGISTRY.to_venue_raw(canonical, venue)
                assert raw is not None
                back = REGISTRY.canonical_from_raw(venue, raw)
                assert back == canonical

    def test_raw_id_format_no_slash(self):
        """Exchange-native IDs have no slash (e.g. BTCUSDT, not BTC/USDT)."""
        for canonical in REGISTRY.all_canonicals():
            for venue in SUPPORTED_VENUES:
                raw = REGISTRY.to_venue_raw(canonical, venue)
                assert "/" not in raw, f"{venue}/{canonical}: {raw!r}"

    def test_ccxt_symbol_has_slash(self):
        """CCXT unified symbols always use `/`."""
        for canonical in REGISTRY.all_canonicals():
            for venue in SUPPORTED_VENUES:
                sym = REGISTRY.to_venue_symbol(canonical, venue)
                assert "/" in sym


# ---------------------------------------------------------------------------
# Collection queries
# ---------------------------------------------------------------------------
class TestCollections:
    def test_canonicals_on_binance_equals_bitget(self):
        """All 24 available on both."""
        bn = set(REGISTRY.canonicals_on("binance"))
        bg = set(REGISTRY.canonicals_on("bitget"))
        assert bn == bg
        assert len(bn) == 24

    def test_iter_returns_entries(self):
        entries = list(REGISTRY)
        assert all(isinstance(e, SymbolEntry) for e in entries)
        assert len(entries) == 24


# ---------------------------------------------------------------------------
# Fallback + missing-venue handling (exercise code paths even if not hit now)
# ---------------------------------------------------------------------------
class TestEdgeCases:
    def test_fallback_equivalent_to_probe(self):
        """The hard-coded fallback matches probe snapshot in size & canonicals."""
        fallback = SymbolRegistry(_build_fallback_entries())
        assert len(fallback) == 24
        assert set(fallback.all_canonicals()) == set(REGISTRY.all_canonicals())

    def test_symbol_entry_is_available_on_when_missing(self):
        entry = SymbolEntry(
            canonical="FAKE/USDT",
            tier="test",
            binance=VenueSymbol(False, None, None),
            bitget=VenueSymbol(True, "FAKE/USDT", "FAKEUSDT"),
        )
        assert entry.is_available_on("bitget") is True
        assert entry.is_available_on("binance") is False
        assert entry.venues_available() == ["bitget"]

    def test_canonicals_on_all_with_one_venue_missing(self):
        """A symbol listed on only one venue should NOT appear in canonicals_on_all."""
        entries = _build_fallback_entries()
        # Mutate a copy: mark BTC unavailable on bitget
        entries["BTC/USDT"] = SymbolEntry(
            canonical="BTC/USDT",
            tier="tier1",
            binance=entries["BTC/USDT"].binance,
            bitget=VenueSymbol(False, None, None),
        )
        reg = SymbolRegistry(entries)
        both = reg.canonicals_on_all(["binance", "bitget"])
        assert "BTC/USDT" not in both
        assert len(both) == 23
        # But still listed on binance alone
        assert "BTC/USDT" in reg.canonicals_on("binance")

    def test_build_default_registry_produces_registry(self):
        r = build_default_registry()
        assert isinstance(r, SymbolRegistry)
        assert len(r) == 24


# ---------------------------------------------------------------------------
# Specific symbol spot checks (catches regressions in probe data)
# ---------------------------------------------------------------------------
class TestSpecificSymbols:
    @pytest.mark.parametrize(
        "canonical,tier",
        [
            ("BTC/USDT", "tier1"),
            ("ETH/USDT", "tier1"),
            ("SOL/USDT", "tier1"),
            ("POL/USDT", "tier2"),  # was MATIC — verify rebrand resolved
            ("SEI/USDT", "tier3"),
            ("FIL/USDT", "tier3"),
        ],
    )
    def test_known_symbol_metadata(self, canonical, tier):
        entry = REGISTRY.get(canonical)
        assert entry is not None
        assert entry.tier == tier
        assert entry.is_available_on("binance")
        assert entry.is_available_on("bitget")

    def test_pol_is_not_matic(self):
        """POL rebrand must be resolved — canonical stays POL, not MATIC."""
        assert REGISTRY.get("POL/USDT") is not None
        # MATIC/USDT should NOT be a canonical in our registry
        assert REGISTRY.get("MATIC/USDT") is None
