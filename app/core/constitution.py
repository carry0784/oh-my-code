"""Constitution — single source of truth for forbidden/excluded definitions.

Phase 0 rules enforced across Gateway, Asset Registry, Screener, and
Qualification layers.  All other modules import from here.

This file is the shared source that prevents drift between
FORBIDDEN_SECTORS (Injection Gateway) and EXCLUDED_SECTORS (Asset Registry).
"""

from __future__ import annotations

# ── Forbidden Brokers (registration-level block) ─────────────────────

FORBIDDEN_BROKERS: frozenset[str] = frozenset({"ALPACA", "KIWOOM_US"})

# ── Allowed Brokers per Asset Class ──────────────────────────────────

ALLOWED_BROKERS: dict[str, frozenset[str]] = {
    "crypto": frozenset({"BINANCE", "BITGET", "UPBIT"}),
    "us_stock": frozenset({"KIS_US"}),
    "kr_stock": frozenset({"KIS_KR", "KIWOOM_KR"}),
}

# ── Forbidden Sectors (single canonical set) ─────────────────────────
# Used by both Injection Gateway (uppercase string keys) and
# Asset Registry (AssetSector enum values).  The string values here
# must match AssetSector enum .value exactly.

FORBIDDEN_SECTOR_VALUES: frozenset[str] = frozenset(
    {
        "meme",
        "gamefi",
        "low_liquidity_new_token",
        "high_valuation_pure_sw",
        "weak_consumer_beta",
        "oil_sensitive",
        "low_liquidity_theme",
    }
)

# ── Exposure Limits ──────────────────────────────────────────────────

# ── Broker Policy Rules (asset-class → allowed brokers) ─────────────
# Validation-only reference.  Used by asset_validators.py (pure function).
# This duplicates ALLOWED_BROKERS intentionally as a cross-check anchor.

BROKER_POLICY_RULES: dict[str, dict] = {
    "crypto": {
        "allowed": frozenset({"BINANCE", "BITGET", "UPBIT"}),
        "forbidden": FORBIDDEN_BROKERS,
    },
    "us_stock": {
        "allowed": frozenset({"KIS_US"}),
        "forbidden": FORBIDDEN_BROKERS,
    },
    "kr_stock": {
        "allowed": frozenset({"KIS_KR", "KIWOOM_KR"}),
        "forbidden": FORBIDDEN_BROKERS,
    },
}

# ── TTL Defaults (candidate TTL hours by asset class) ───────────────
# Policy definition only.  Actual TTL expiry execution is Stage 2B.

TTL_DEFAULTS: dict[str, int] = {
    "crypto": 48,  # 48 hours — 24/7 market
    "us_stock": 72,  # 72 hours — weekday-only market
    "kr_stock": 72,  # 72 hours — weekday-only market
}

TTL_MIN_HOURS: int = 12
TTL_MAX_HOURS: int = 168  # 7 days

# ── Status Transition Rules ─────────────────────────────────────────
# Defines which status transitions are allowed and under what conditions.
# Key: (from_status, to_status) → condition string.
# Execution of transitions is Stage 2B.  This is policy definition only.

STATUS_TRANSITION_RULES: dict[tuple[str, str], str] = {
    # From CORE
    ("core", "watch"): "ttl_expired|regime_change|screening_fail",
    ("core", "excluded"): "manual_exclusion|exclusion_baseline",
    # From WATCH
    ("watch", "core"): "screening_full_pass",
    ("watch", "excluded"): "manual_exclusion|exclusion_baseline",
    # From EXCLUDED
    ("excluded", "watch"): "manual_override_required",
    ("excluded", "core"): "forbidden",  # EXCLUDED→CORE direct transition is always forbidden
}

# ── Exposure Limits ──────────────────────────────────────────────────

EXPOSURE_LIMITS: dict[str, int] = {
    "max_strategies_per_market": 5,
    "max_strategies_per_symbol": 3,
    "max_concurrent_strategy_symbol": 30,
    "max_symbols_per_market": 20,
    "max_symbols_per_theme": 5,
    "max_single_symbol_capital_pct": 10,
    "max_single_theme_capital_pct": 25,
    "max_single_market_capital_pct": 50,
}
