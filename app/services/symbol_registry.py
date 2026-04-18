"""
Symbol Registry — Card B-8 v1.1

Canonical-to-venue mapping for the 24-symbol universe across Binance + Bitget.

Design:
  - `canonical` = CCXT unified symbol (e.g. "BTC/USDT")
  - Each SymbolEntry tracks per-venue availability, CCXT symbol, and raw
    exchange-native id (e.g. Binance "BTCUSDT", Bitget "BTCUSDT")
  - All 24 current symbols are present on both venues (verified by
    scripts/probe_symbol_mapping.py against live exchange APIs).

  - Loaded from `data/backtest_results/symbol_registry_probe.json` at import,
    with an in-code fallback for offline/test scenarios.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from app.core.logging import get_logger

logger = get_logger(__name__)


Venue = Literal["binance", "bitget"]
SUPPORTED_VENUES: tuple[Venue, ...] = ("binance", "bitget")


@dataclass(frozen=True)
class VenueSymbol:
    """Per-venue symbol details."""

    available: bool
    ccxt_symbol: str | None           # e.g. "BTC/USDT"
    raw_id: str | None                # e.g. "BTCUSDT"
    alias_used: str | None = None     # if a rebrand fallback was used


@dataclass(frozen=True)
class SymbolEntry:
    """Registry entry for one canonical symbol."""

    canonical: str
    tier: str                          # "tier1" | "tier2" | "tier3"
    binance: VenueSymbol
    bitget: VenueSymbol

    def is_available_on(self, venue: Venue) -> bool:
        return getattr(self, venue).available

    def venues_available(self) -> list[Venue]:
        return [v for v in SUPPORTED_VENUES if self.is_available_on(v)]

    def ccxt_symbol_for(self, venue: Venue) -> str | None:
        return getattr(self, venue).ccxt_symbol

    def raw_id_for(self, venue: Venue) -> str | None:
        return getattr(self, venue).raw_id


# ---------------------------------------------------------------------------
# Fallback: 24-symbol Tier1/2/3 universe — both venues confirmed 2026-04-16
# (source: scripts/probe_symbol_mapping.py → 24/24 BOTH, no aliases)
# ---------------------------------------------------------------------------
_TIERS = {
    "tier1": ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX"],
    "tier2": ["TRX", "LINK", "DOT", "POL", "LTC", "NEAR", "ATOM", "UNI"],
    "tier3": ["APT", "ARB", "OP", "SUI", "TIA", "SEI", "INJ", "FIL"],
}


def _build_fallback_entries() -> dict[str, SymbolEntry]:
    """Same format as probe.json. All 24 canonical symbols confirmed BOTH."""
    out: dict[str, SymbolEntry] = {}
    for tier, bases in _TIERS.items():
        for base in bases:
            canonical = f"{base}/USDT"
            raw = f"{base}USDT"
            out[canonical] = SymbolEntry(
                canonical=canonical,
                tier=tier,
                binance=VenueSymbol(True, canonical, raw),
                bitget=VenueSymbol(True, canonical, raw),
            )
    return out


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------
_PROBE_PATH = (
    Path(__file__).resolve().parents[2]
    / "data" / "backtest_results" / "symbol_registry_probe.json"
)


def _load_from_probe(path: Path) -> dict[str, SymbolEntry] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("symbol_registry_probe_parse_error", error=str(exc))
        return None

    out: dict[str, SymbolEntry] = {}
    for canonical, rec in data.get("symbols", {}).items():
        bn = rec.get("binance") or {}
        bg = rec.get("bitget") or {}
        out[canonical] = SymbolEntry(
            canonical=canonical,
            tier=rec.get("tier", "unknown"),
            binance=VenueSymbol(
                bool(bn.get("available", False)),
                bn.get("ccxt_symbol"),
                bn.get("raw_id"),
                bn.get("alias_used"),
            ),
            bitget=VenueSymbol(
                bool(bg.get("available", False)),
                bg.get("ccxt_symbol"),
                bg.get("raw_id"),
                bg.get("alias_used"),
            ),
        )
    return out


# ---------------------------------------------------------------------------
# Public registry
# ---------------------------------------------------------------------------
class SymbolRegistry:
    """Thread-safe lookup registry (entries are frozen dataclasses)."""

    def __init__(self, entries: dict[str, SymbolEntry]):
        self._entries = dict(entries)  # canonical -> SymbolEntry

        # Reverse lookups
        self._by_ccxt: dict[tuple[Venue, str], str] = {}
        self._by_raw: dict[tuple[Venue, str], str] = {}
        for canonical, entry in self._entries.items():
            for venue in SUPPORTED_VENUES:
                vs = getattr(entry, venue)
                if vs.available:
                    if vs.ccxt_symbol:
                        self._by_ccxt[(venue, vs.ccxt_symbol)] = canonical
                    if vs.raw_id:
                        self._by_raw[(venue, vs.raw_id)] = canonical

    # ---- Lookup API ----

    def get(self, canonical: str) -> SymbolEntry | None:
        return self._entries.get(canonical)

    def canonical_from_ccxt(self, venue: Venue, ccxt_symbol: str) -> str | None:
        return self._by_ccxt.get((venue, ccxt_symbol))

    def canonical_from_raw(self, venue: Venue, raw_id: str) -> str | None:
        return self._by_raw.get((venue, raw_id))

    def to_venue_symbol(self, canonical: str, venue: Venue) -> str | None:
        entry = self._entries.get(canonical)
        if entry is None:
            return None
        return entry.ccxt_symbol_for(venue)

    def to_venue_raw(self, canonical: str, venue: Venue) -> str | None:
        entry = self._entries.get(canonical)
        if entry is None:
            return None
        return entry.raw_id_for(venue)

    # ---- Collections ----

    def all_canonicals(self) -> list[str]:
        return list(self._entries.keys())

    def canonicals_on(self, venue: Venue) -> list[str]:
        return [c for c, e in self._entries.items() if e.is_available_on(venue)]

    def canonicals_on_all(self, venues: list[Venue] | None = None) -> list[str]:
        """Return symbols available on every given venue (default: all supported)."""
        venues = venues or list(SUPPORTED_VENUES)
        return [
            c for c, e in self._entries.items()
            if all(e.is_available_on(v) for v in venues)
        ]

    def canonicals_by_tier(self, tier: str) -> list[str]:
        return [c for c, e in self._entries.items() if e.tier == tier]

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, canonical: str) -> bool:
        return canonical in self._entries

    def __iter__(self):
        return iter(self._entries.values())


def build_default_registry() -> SymbolRegistry:
    """Build the default registry used by the app.

    Prefers the probe-generated JSON (canonical source of venue truth).
    Falls back to hard-coded 24-symbol snapshot if the probe file is missing.
    """
    entries = _load_from_probe(_PROBE_PATH)
    if entries is None:
        logger.warning(
            "symbol_registry_using_fallback",
            path=str(_PROBE_PATH),
            note="Run scripts/probe_symbol_mapping.py to regenerate.",
        )
        entries = _build_fallback_entries()
    return SymbolRegistry(entries)


# Module-level singleton — import-time cost is tiny (JSON parse)
REGISTRY = build_default_registry()
