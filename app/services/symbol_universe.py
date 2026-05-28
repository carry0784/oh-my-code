"""
Symbol Universe — Card B-1
Canonical 24-symbol trading universe, tiered by liquidity and priority.

Tier 1: Highest liquidity, primary deployment targets (BTC, ETH, SOL, …)
Tier 2: Mid-liquidity established assets
Tier 3: Emerging / lower-cap assets — experimental deployment only

Usage:
    from app.services.symbol_universe import ALL_SYMBOLS, SYMBOL_UNIVERSE, get_tier
"""

from __future__ import annotations

SYMBOL_UNIVERSE: dict[str, list[str]] = {
    "tier1": [
        "BTC/USDT",
        "ETH/USDT",
        "SOL/USDT",
        "BNB/USDT",
        "XRP/USDT",
        "DOGE/USDT",
        "ADA/USDT",
        "AVAX/USDT",
    ],
    "tier2": [
        "TRX/USDT",
        "LINK/USDT",
        "DOT/USDT",
        "POL/USDT",  # Formerly MATIC — rebranded to POL on Binance (2024-09)
        "LTC/USDT",
        "NEAR/USDT",
        "ATOM/USDT",
        "UNI/USDT",
    ],
    "tier3": [
        "APT/USDT",
        "ARB/USDT",
        "OP/USDT",
        "SUI/USDT",
        "TIA/USDT",
        "SEI/USDT",
        "INJ/USDT",
        "FIL/USDT",
    ],
}

# Flat list: tier1 → tier2 → tier3 (24 symbols total)
ALL_SYMBOLS: list[str] = (
    SYMBOL_UNIVERSE["tier1"]
    + SYMBOL_UNIVERSE["tier2"]
    + SYMBOL_UNIVERSE["tier3"]
)

# Reverse lookup: symbol → tier name
_SYMBOL_TO_TIER: dict[str, str] = {
    symbol: tier
    for tier, symbols in SYMBOL_UNIVERSE.items()
    for symbol in symbols
}


def get_tier(symbol: str) -> str | None:
    """Return the tier name for *symbol*, or None if not in the universe.

    Examples:
        >>> get_tier("BTC/USDT")
        'tier1'
        >>> get_tier("ARB/USDT")
        'tier3'
        >>> get_tier("UNKNOWN/USDT")
        None
    """
    return _SYMBOL_TO_TIER.get(symbol)


def get_symbols_by_tier(tier: str) -> list[str]:
    """Return the list of symbols for the given tier name.

    Args:
        tier: One of 'tier1', 'tier2', 'tier3'.

    Returns:
        List of symbols, or empty list for an unknown tier.

    Example:
        >>> get_symbols_by_tier("tier2")
        ['TRX/USDT', 'LINK/USDT', ...]
    """
    return list(SYMBOL_UNIVERSE.get(tier, []))


def is_in_universe(symbol: str) -> bool:
    """Return True if *symbol* is part of the 24-symbol universe."""
    return symbol in _SYMBOL_TO_TIER
