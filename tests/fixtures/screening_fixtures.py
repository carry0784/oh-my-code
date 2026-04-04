"""Stage 3B-2: Golden set fixtures for screening transform + stub tests.

Categories:
  - Normal: market-specific healthy data (4 symbols)
  - Failure: F1-F9 failure mode reproduction (9 scenarios)
  - Edge: boundary values (4 scenarios)
  - Capability: provider capability profiles (3 profiles)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.data_provider import (
    BacktestReadiness,
    DataQuality,
    FundamentalSnapshot,
    MarketDataSnapshot,
    ProviderCapability,
    SymbolMetadata,
)


# ══════════════════════════════════════════════════════════════════════
# Reference timestamp for all fixtures
# ══════════════════════════════════════════════════════════════════════

NOW_UTC = datetime(2026, 4, 3, 12, 0, 0, tzinfo=timezone.utc)


# ══════════════════════════════════════════════════════════════════════
# Normal Fixtures (canonical / 4 markets)
# ══════════════════════════════════════════════════════════════════════


# ── BTC/USDT (CRYPTO, LAYER1) ────────────────────────────────────────

FIXTURE_OK_CRYPTO_BTC_MARKET = MarketDataSnapshot(
    symbol="BTC/USDT",
    timestamp=NOW_UTC - timedelta(minutes=15),
    price_usd=68000.0,
    market_cap_usd=1_340_000_000_000,
    avg_daily_volume_usd=35_000_000_000,
    spread_pct=0.01,
    atr_pct=3.2,
    adx=28.0,
    price_vs_200ma=1.08,
    quality=DataQuality.HIGH,
)

FIXTURE_OK_CRYPTO_BTC_BACKTEST = BacktestReadiness(
    symbol="BTC/USDT",
    available_bars=2000,
    sharpe_ratio=0.85,
    missing_data_pct=0.3,
    quality=DataQuality.HIGH,
)

FIXTURE_OK_CRYPTO_BTC_METADATA = SymbolMetadata(
    symbol="BTC/USDT",
    market="crypto",
    listing_age_days=5000,
    is_active=True,
    as_of=NOW_UTC,
    metadata_origin="coingecko",
)


# ── SOL/USDT (CRYPTO, LAYER1) ────────────────────────────────────────

FIXTURE_OK_CRYPTO_SOL_MARKET = MarketDataSnapshot(
    symbol="SOL/USDT",
    timestamp=NOW_UTC - timedelta(minutes=10),
    price_usd=145.0,
    market_cap_usd=65_000_000_000,
    avg_daily_volume_usd=3_500_000_000,
    spread_pct=0.03,
    atr_pct=5.5,
    adx=22.0,
    price_vs_200ma=1.15,
    quality=DataQuality.HIGH,
)

FIXTURE_OK_CRYPTO_SOL_BACKTEST = BacktestReadiness(
    symbol="SOL/USDT",
    available_bars=1500,
    sharpe_ratio=0.65,
    missing_data_pct=0.5,
    quality=DataQuality.HIGH,
)

FIXTURE_OK_CRYPTO_SOL_METADATA = SymbolMetadata(
    symbol="SOL/USDT",
    market="crypto",
    listing_age_days=1800,
    is_active=True,
    metadata_origin="coingecko",
)


# ── AAPL (US_STOCK, TECH) ────────────────────────────────────────────

FIXTURE_OK_US_AAPL_MARKET = MarketDataSnapshot(
    symbol="AAPL",
    timestamp=NOW_UTC - timedelta(hours=1),
    price_usd=195.0,
    market_cap_usd=3_000_000_000_000,
    avg_daily_volume_usd=8_000_000_000,
    spread_pct=0.005,
    atr_pct=1.8,
    adx=20.0,
    price_vs_200ma=1.02,
    quality=DataQuality.HIGH,
)

FIXTURE_OK_US_AAPL_BACKTEST = BacktestReadiness(
    symbol="AAPL",
    available_bars=3000,
    sharpe_ratio=1.1,
    missing_data_pct=0.1,
    quality=DataQuality.HIGH,
)

FIXTURE_OK_US_AAPL_FUNDAMENTAL = FundamentalSnapshot(
    symbol="AAPL",
    per=28.5,
    roe=45.0,
    revenue_growth_pct=8.2,
    operating_margin_pct=30.0,
    quality=DataQuality.HIGH,
)

FIXTURE_OK_US_AAPL_METADATA = SymbolMetadata(
    symbol="AAPL",
    market="us_stock",
    listing_age_days=15000,
    is_active=True,
    metadata_origin="sec",
)


# ── 005930 (KR_STOCK, SEMICONDUCTOR) ─────────────────────────────────

FIXTURE_OK_KR_005930_MARKET = MarketDataSnapshot(
    symbol="005930",
    timestamp=NOW_UTC - timedelta(hours=2),
    price_usd=55.0,
    market_cap_usd=330_000_000_000,
    avg_daily_volume_usd=1_500_000_000,
    spread_pct=0.02,
    atr_pct=2.0,
    adx=18.0,
    price_vs_200ma=0.95,
    quality=DataQuality.HIGH,
)

FIXTURE_OK_KR_005930_BACKTEST = BacktestReadiness(
    symbol="005930",
    available_bars=2500,
    sharpe_ratio=0.7,
    missing_data_pct=0.2,
    quality=DataQuality.HIGH,
)

FIXTURE_OK_KR_005930_METADATA = SymbolMetadata(
    symbol="005930",
    market="kr_stock",
    listing_age_days=10000,
    is_active=True,
    metadata_origin="krx",
)


# ══════════════════════════════════════════════════════════════════════
# Failure Fixtures (F1-F9)
# ══════════════════════════════════════════════════════════════════════


# F1: Empty response — all fields None
FIXTURE_REJECT_F1_EMPTY_MARKET = MarketDataSnapshot(symbol="BTC/USDT")
FIXTURE_REJECT_F1_EMPTY_BACKTEST = BacktestReadiness(symbol="BTC/USDT")

# F2: Partial mandatory — volume present but atr/adx/bars missing
FIXTURE_REJECT_F2_PARTIAL_MARKET = MarketDataSnapshot(
    symbol="BTC/USDT",
    timestamp=NOW_UTC - timedelta(minutes=10),
    avg_daily_volume_usd=35_000_000_000,
    quality=DataQuality.DEGRADED,
)
FIXTURE_REJECT_F2_PARTIAL_BACKTEST = BacktestReadiness(symbol="BTC/USDT")

# F3: Partial optional — mandatory present, optional missing → PARTIAL_USABLE
FIXTURE_OK_F3_PARTIAL_OPTIONAL_MARKET = MarketDataSnapshot(
    symbol="BTC/USDT",
    timestamp=NOW_UTC - timedelta(minutes=10),
    avg_daily_volume_usd=35_000_000_000,
    atr_pct=3.2,
    adx=28.0,
    quality=DataQuality.HIGH,
    # market_cap, spread, price_vs_200ma all None
)
FIXTURE_OK_F3_PARTIAL_OPTIONAL_BACKTEST = BacktestReadiness(
    symbol="BTC/USDT",
    available_bars=2000,
    quality=DataQuality.HIGH,
)

# F4: Stale data — timestamp 3 hours old (CRYPTO limit is 1h)
FIXTURE_REJECT_F4_STALE_MARKET = MarketDataSnapshot(
    symbol="BTC/USDT",
    timestamp=NOW_UTC - timedelta(hours=3),
    avg_daily_volume_usd=35_000_000_000,
    atr_pct=3.2,
    adx=28.0,
    quality=DataQuality.STALE,
)
FIXTURE_REJECT_F4_STALE_BACKTEST = BacktestReadiness(
    symbol="BTC/USDT",
    available_bars=2000,
    quality=DataQuality.HIGH,
)

# F5: Insufficient bars — bars=100 (< 500 threshold)
# NOTE: validate passes, stage 5 handles rejection
FIXTURE_OK_F5_INSUFFICIENT_BARS_MARKET = MarketDataSnapshot(
    symbol="BTC/USDT",
    timestamp=NOW_UTC - timedelta(minutes=10),
    avg_daily_volume_usd=35_000_000_000,
    atr_pct=3.2,
    adx=28.0,
    market_cap_usd=1_340_000_000_000,
    spread_pct=0.01,
    price_vs_200ma=1.08,
    quality=DataQuality.HIGH,
)
FIXTURE_OK_F5_INSUFFICIENT_BARS_BACKTEST = BacktestReadiness(
    symbol="BTC/USDT",
    available_bars=100,
    quality=DataQuality.HIGH,
)

# F6: Missing listing age — metadata=None
# NOTE: validate passes (F6 exception), listing_age_days=None
FIXTURE_OK_F6_NO_LISTING_AGE_MARKET = MarketDataSnapshot(
    symbol="BTC/USDT",
    timestamp=NOW_UTC - timedelta(minutes=10),
    avg_daily_volume_usd=35_000_000_000,
    atr_pct=3.2,
    adx=28.0,
    market_cap_usd=1_340_000_000_000,
    spread_pct=0.01,
    price_vs_200ma=1.08,
    quality=DataQuality.HIGH,
)
FIXTURE_OK_F6_NO_LISTING_AGE_BACKTEST = BacktestReadiness(
    symbol="BTC/USDT",
    available_bars=2000,
    quality=DataQuality.HIGH,
)

# F7: Namespace error — no slash in CRYPTO symbol
FIXTURE_REJECT_F7_NAMESPACE_MARKET = MarketDataSnapshot(
    symbol="BTCUSDT",
    timestamp=NOW_UTC - timedelta(minutes=10),
    avg_daily_volume_usd=35_000_000_000,
    atr_pct=3.2,
    adx=28.0,
    quality=DataQuality.HIGH,
)
FIXTURE_REJECT_F7_NAMESPACE_BACKTEST = BacktestReadiness(
    symbol="BTCUSDT",
    available_bars=2000,
    quality=DataQuality.HIGH,
)

# F8: Provider timeout — simulated via empty snapshot (unknown symbol)
FIXTURE_REJECT_F8_TIMEOUT_MARKET = MarketDataSnapshot(symbol="UNKNOWN/TOKEN")
FIXTURE_REJECT_F8_TIMEOUT_BACKTEST = BacktestReadiness(symbol="UNKNOWN/TOKEN")

# F9: Quality conflict — degraded quality, partial optional data
FIXTURE_OK_F9_DEGRADED_MARKET = MarketDataSnapshot(
    symbol="BTC/USDT",
    timestamp=NOW_UTC - timedelta(minutes=30),
    avg_daily_volume_usd=35_000_000_000,
    atr_pct=3.2,
    adx=28.0,
    quality=DataQuality.DEGRADED,
    # optional fields missing
)
FIXTURE_OK_F9_DEGRADED_BACKTEST = BacktestReadiness(
    symbol="BTC/USDT",
    available_bars=2000,
    quality=DataQuality.DEGRADED,
)


# ══════════════════════════════════════════════════════════════════════
# Edge Fixtures (boundary values)
# ══════════════════════════════════════════════════════════════════════


# Stale boundary: exactly at limit (CRYPTO price = 1h) → OK (<=)
FIXTURE_EDGE_STALE_BOUNDARY_MARKET = MarketDataSnapshot(
    symbol="BTC/USDT",
    timestamp=NOW_UTC - timedelta(hours=1),
    avg_daily_volume_usd=35_000_000_000,
    atr_pct=3.2,
    adx=28.0,
    market_cap_usd=1_340_000_000_000,
    spread_pct=0.01,
    price_vs_200ma=1.08,
    quality=DataQuality.HIGH,
)

# Stale usable: 50 minutes (under 1h limit)
FIXTURE_EDGE_STALE_USABLE_MARKET = MarketDataSnapshot(
    symbol="BTC/USDT",
    timestamp=NOW_UTC - timedelta(minutes=50),
    avg_daily_volume_usd=35_000_000_000,
    atr_pct=3.2,
    adx=28.0,
    market_cap_usd=1_340_000_000_000,
    spread_pct=0.01,
    price_vs_200ma=1.08,
    quality=DataQuality.HIGH,
)

FIXTURE_EDGE_BACKTEST = BacktestReadiness(
    symbol="BTC/USDT",
    available_bars=2000,
    sharpe_ratio=0.5,
    missing_data_pct=1.0,
    quality=DataQuality.HIGH,
)


# ══════════════════════════════════════════════════════════════════════
# Capability Profiles
# ══════════════════════════════════════════════════════════════════════


CAP_FULL_CRYPTO = ProviderCapability(
    provider_name="full_crypto",
    supported_asset_classes=frozenset({"CRYPTO"}),
    supports_volume=True,
    supports_spread=True,
    supports_atr=True,
    supports_adx=True,
    supports_price_vs_ma=True,
    supports_market_cap=True,
    supports_tvl=True,
    supports_available_bars=True,
    supports_sharpe=True,
    supports_missing_pct=True,
    supports_listing_age=True,
    freshness_granularity="1m",
    symbol_namespace="ccxt",
    max_batch_size=50,
)

CAP_FULL_US_STOCK = ProviderCapability(
    provider_name="full_us_stock",
    supported_asset_classes=frozenset({"US_STOCK"}),
    supports_volume=True,
    supports_spread=True,
    supports_atr=True,
    supports_adx=True,
    supports_price_vs_ma=True,
    supports_market_cap=True,
    supports_per=True,
    supports_roe=True,
    supports_available_bars=True,
    supports_sharpe=True,
    supports_missing_pct=True,
    supports_listing_age=True,
    freshness_granularity="15m",
    symbol_namespace="ticker",
    max_batch_size=20,
)

CAP_FULL_KR_STOCK = ProviderCapability(
    provider_name="full_kr_stock",
    supported_asset_classes=frozenset({"KR_STOCK"}),
    supports_volume=True,
    supports_spread=True,
    supports_atr=True,
    supports_adx=True,
    supports_price_vs_ma=True,
    supports_market_cap=True,
    supports_available_bars=True,
    supports_sharpe=True,
    supports_missing_pct=True,
    supports_listing_age=True,
    freshness_granularity="15m",
    symbol_namespace="krx_code",
    max_batch_size=30,
)

CAP_MINIMAL_CRYPTO = ProviderCapability(
    provider_name="minimal_crypto",
    supported_asset_classes=frozenset({"CRYPTO"}),
    supports_volume=True,
    supports_atr=True,
    supports_adx=True,
    supports_available_bars=True,
)

CAP_DEGRADED_NO_ADX = ProviderCapability(
    provider_name="degraded_no_adx",
    supported_asset_classes=frozenset({"CRYPTO"}),
    supports_volume=True,
    supports_atr=True,
    supports_adx=False,
    supports_available_bars=False,
)

CAP_EMPTY = ProviderCapability(provider_name="empty")


# ══════════════════════════════════════════════════════════════════════
# Golden Set Symbols
# ══════════════════════════════════════════════════════════════════════


GOLDEN_SYMBOLS_CANONICAL = {
    "CRYPTO": ["BTC/USDT", "SOL/USDT"],
    "US_STOCK": ["AAPL", "NVDA"],
    "KR_STOCK": ["005930", "000660"],
}

GOLDEN_SYMBOLS_FORBIDDEN = {
    "CRYPTO": ["BTCUSDT", "KRW-BTC", "", "btc_usdt"],
    "US_STOCK": ["BRK.B", "005930", "AAPL1"],
    "KR_STOCK": ["12345", "00593A", "005930.KS"],
}
