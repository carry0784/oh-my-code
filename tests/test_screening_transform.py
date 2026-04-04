"""Stage 3B-2: ScreeningInput transformation contract tests.

Covers:
  - validate_screening_preconditions (namespace, stale, partial)
  - build_screening_input (field mapping)
  - transform_provider_to_screening (full pipeline)
  - ScreeningInputSource (audit-only frozen dataclass)
  - TransformResult (invariants)
  - Failure mode integration (F1-F9)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models.asset import AssetClass, AssetSector
from app.services.data_provider import (
    BacktestReadiness,
    DataQuality,
    DataQualityDecision,
    FundamentalSnapshot,
    MarketDataSnapshot,
    SymbolMetadata,
)
from app.services.screening_transform import (
    ScreeningInputSource,
    TransformResult,
    _REJECT_DECISIONS,
    build_screening_input,
    transform_provider_to_screening,
    validate_screening_preconditions,
)
from tests.fixtures.screening_fixtures import (
    FIXTURE_EDGE_BACKTEST,
    FIXTURE_EDGE_STALE_BOUNDARY_MARKET,
    FIXTURE_EDGE_STALE_USABLE_MARKET,
    FIXTURE_OK_CRYPTO_BTC_BACKTEST,
    FIXTURE_OK_CRYPTO_BTC_MARKET,
    FIXTURE_OK_CRYPTO_BTC_METADATA,
    FIXTURE_OK_CRYPTO_SOL_BACKTEST,
    FIXTURE_OK_CRYPTO_SOL_MARKET,
    FIXTURE_OK_CRYPTO_SOL_METADATA,
    FIXTURE_OK_F3_PARTIAL_OPTIONAL_BACKTEST,
    FIXTURE_OK_F3_PARTIAL_OPTIONAL_MARKET,
    FIXTURE_OK_F5_INSUFFICIENT_BARS_BACKTEST,
    FIXTURE_OK_F5_INSUFFICIENT_BARS_MARKET,
    FIXTURE_OK_F6_NO_LISTING_AGE_BACKTEST,
    FIXTURE_OK_F6_NO_LISTING_AGE_MARKET,
    FIXTURE_OK_F9_DEGRADED_BACKTEST,
    FIXTURE_OK_F9_DEGRADED_MARKET,
    FIXTURE_OK_KR_005930_BACKTEST,
    FIXTURE_OK_KR_005930_MARKET,
    FIXTURE_OK_KR_005930_METADATA,
    FIXTURE_OK_US_AAPL_BACKTEST,
    FIXTURE_OK_US_AAPL_FUNDAMENTAL,
    FIXTURE_OK_US_AAPL_MARKET,
    FIXTURE_OK_US_AAPL_METADATA,
    FIXTURE_REJECT_F1_EMPTY_BACKTEST,
    FIXTURE_REJECT_F1_EMPTY_MARKET,
    FIXTURE_REJECT_F2_PARTIAL_BACKTEST,
    FIXTURE_REJECT_F2_PARTIAL_MARKET,
    FIXTURE_REJECT_F4_STALE_BACKTEST,
    FIXTURE_REJECT_F4_STALE_MARKET,
    FIXTURE_REJECT_F7_NAMESPACE_BACKTEST,
    FIXTURE_REJECT_F7_NAMESPACE_MARKET,
    FIXTURE_REJECT_F8_TIMEOUT_BACKTEST,
    FIXTURE_REJECT_F8_TIMEOUT_MARKET,
    NOW_UTC,
)


# ── validate_screening_preconditions ─────────────────────────────────


class TestValidateScreeningPreconditions:
    def test_valid_btc_ok(self):
        result = validate_screening_preconditions(
            FIXTURE_OK_CRYPTO_BTC_MARKET,
            FIXTURE_OK_CRYPTO_BTC_BACKTEST,
            FIXTURE_OK_CRYPTO_BTC_METADATA,
            "CRYPTO",
            NOW_UTC,
        )
        assert result == DataQualityDecision.OK

    def test_valid_sol_ok(self):
        result = validate_screening_preconditions(
            FIXTURE_OK_CRYPTO_SOL_MARKET,
            FIXTURE_OK_CRYPTO_SOL_BACKTEST,
            FIXTURE_OK_CRYPTO_SOL_METADATA,
            "CRYPTO",
            NOW_UTC,
        )
        assert result == DataQualityDecision.OK

    def test_valid_aapl_ok(self):
        result = validate_screening_preconditions(
            FIXTURE_OK_US_AAPL_MARKET,
            FIXTURE_OK_US_AAPL_BACKTEST,
            FIXTURE_OK_US_AAPL_METADATA,
            "US_STOCK",
            NOW_UTC,
        )
        assert result == DataQualityDecision.OK

    def test_valid_kr_stock_ok(self):
        result = validate_screening_preconditions(
            FIXTURE_OK_KR_005930_MARKET,
            FIXTURE_OK_KR_005930_BACKTEST,
            FIXTURE_OK_KR_005930_METADATA,
            "KR_STOCK",
            NOW_UTC,
        )
        assert result == DataQualityDecision.OK

    def test_namespace_error_no_slash(self):
        result = validate_screening_preconditions(
            FIXTURE_REJECT_F7_NAMESPACE_MARKET,
            FIXTURE_REJECT_F7_NAMESPACE_BACKTEST,
            None,
            "CRYPTO",
            NOW_UTC,
        )
        assert result == DataQualityDecision.SYMBOL_NAMESPACE_ERROR

    def test_namespace_error_empty(self):
        market = MarketDataSnapshot(symbol="")
        bt = BacktestReadiness(symbol="")
        result = validate_screening_preconditions(market, bt, None, "CRYPTO", NOW_UTC)
        assert result == DataQualityDecision.SYMBOL_NAMESPACE_ERROR

    def test_namespace_error_kr_5digit(self):
        market = MarketDataSnapshot(
            symbol="12345",
            timestamp=NOW_UTC - timedelta(minutes=10),
            avg_daily_volume_usd=1e9,
            atr_pct=2.0,
            adx=18.0,
        )
        bt = BacktestReadiness(symbol="12345", available_bars=2000)
        result = validate_screening_preconditions(market, bt, None, "KR_STOCK", NOW_UTC)
        assert result == DataQualityDecision.SYMBOL_NAMESPACE_ERROR

    def test_stale_crypto_reject(self):
        result = validate_screening_preconditions(
            FIXTURE_REJECT_F4_STALE_MARKET,
            FIXTURE_REJECT_F4_STALE_BACKTEST,
            None,
            "CRYPTO",
            NOW_UTC,
        )
        assert result == DataQualityDecision.STALE_REJECT

    def test_stale_us_stock_reject(self):
        market = MarketDataSnapshot(
            symbol="AAPL",
            timestamp=NOW_UTC - timedelta(hours=6),
            avg_daily_volume_usd=8e9,
            atr_pct=1.8,
            adx=20.0,
        )
        bt = BacktestReadiness(symbol="AAPL", available_bars=3000)
        result = validate_screening_preconditions(market, bt, None, "US_STOCK", NOW_UTC)
        assert result == DataQualityDecision.STALE_REJECT

    def test_partial_reject_no_volume(self):
        market = MarketDataSnapshot(
            symbol="BTC/USDT",
            timestamp=NOW_UTC - timedelta(minutes=10),
            atr_pct=3.2,
            adx=28.0,
        )
        bt = BacktestReadiness(symbol="BTC/USDT", available_bars=2000)
        result = validate_screening_preconditions(market, bt, None, "CRYPTO", NOW_UTC)
        assert result == DataQualityDecision.PARTIAL_REJECT

    def test_partial_reject_no_atr(self):
        market = MarketDataSnapshot(
            symbol="BTC/USDT",
            timestamp=NOW_UTC - timedelta(minutes=10),
            avg_daily_volume_usd=35e9,
            adx=28.0,
        )
        bt = BacktestReadiness(symbol="BTC/USDT", available_bars=2000)
        result = validate_screening_preconditions(market, bt, None, "CRYPTO", NOW_UTC)
        assert result == DataQualityDecision.PARTIAL_REJECT

    def test_partial_reject_no_adx(self):
        market = MarketDataSnapshot(
            symbol="BTC/USDT",
            timestamp=NOW_UTC - timedelta(minutes=10),
            avg_daily_volume_usd=35e9,
            atr_pct=3.2,
        )
        bt = BacktestReadiness(symbol="BTC/USDT", available_bars=2000)
        result = validate_screening_preconditions(market, bt, None, "CRYPTO", NOW_UTC)
        assert result == DataQualityDecision.PARTIAL_REJECT

    def test_partial_reject_no_bars(self):
        market = MarketDataSnapshot(
            symbol="BTC/USDT",
            timestamp=NOW_UTC - timedelta(minutes=10),
            avg_daily_volume_usd=35e9,
            atr_pct=3.2,
            adx=28.0,
        )
        bt = BacktestReadiness(symbol="BTC/USDT")
        result = validate_screening_preconditions(market, bt, None, "CRYPTO", NOW_UTC)
        assert result == DataQualityDecision.PARTIAL_REJECT

    def test_partial_usable_optional_missing(self):
        result = validate_screening_preconditions(
            FIXTURE_OK_F3_PARTIAL_OPTIONAL_MARKET,
            FIXTURE_OK_F3_PARTIAL_OPTIONAL_BACKTEST,
            None,
            "CRYPTO",
            NOW_UTC,
        )
        assert result == DataQualityDecision.PARTIAL_USABLE

    def test_fail_fast_namespace_before_stale(self):
        """Bad symbol + stale → NAMESPACE (step 1 runs first)."""
        market = MarketDataSnapshot(
            symbol="BTCUSDT",
            timestamp=NOW_UTC - timedelta(hours=3),
            avg_daily_volume_usd=35e9,
            atr_pct=3.2,
            adx=28.0,
        )
        bt = BacktestReadiness(symbol="BTCUSDT", available_bars=2000)
        result = validate_screening_preconditions(market, bt, None, "CRYPTO", NOW_UTC)
        assert result == DataQualityDecision.SYMBOL_NAMESPACE_ERROR

    def test_fail_fast_stale_before_partial(self):
        """Stale + partial reject → STALE (step 2 runs before step 3)."""
        market = MarketDataSnapshot(
            symbol="BTC/USDT",
            timestamp=NOW_UTC - timedelta(hours=3),
        )
        bt = BacktestReadiness(symbol="BTC/USDT")
        result = validate_screening_preconditions(market, bt, None, "CRYPTO", NOW_UTC)
        assert result == DataQualityDecision.STALE_REJECT

    def test_edge_stale_boundary_ok(self):
        """Exactly at 1h limit → OK (<=)."""
        result = validate_screening_preconditions(
            FIXTURE_EDGE_STALE_BOUNDARY_MARKET,
            FIXTURE_EDGE_BACKTEST,
            None,
            "CRYPTO",
            NOW_UTC,
        )
        assert result == DataQualityDecision.OK

    def test_edge_stale_usable_ok(self):
        """50 minutes old (under 1h limit) → OK."""
        result = validate_screening_preconditions(
            FIXTURE_EDGE_STALE_USABLE_MARKET,
            FIXTURE_EDGE_BACKTEST,
            None,
            "CRYPTO",
            NOW_UTC,
        )
        assert result == DataQualityDecision.OK


# ── build_screening_input ────────────────────────────────────────────


class TestBuildScreeningInput:
    def test_full_btc_mapping(self):
        inp = build_screening_input(
            FIXTURE_OK_CRYPTO_BTC_MARKET,
            FIXTURE_OK_CRYPTO_BTC_BACKTEST,
            None,
            FIXTURE_OK_CRYPTO_BTC_METADATA,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        assert inp.symbol == "BTC/USDT"
        assert inp.asset_class == AssetClass.CRYPTO
        assert inp.sector == AssetSector.LAYER1
        assert inp.avg_daily_volume_usd == 35_000_000_000
        assert inp.atr_pct == 3.2
        assert inp.adx == 28.0
        assert inp.available_bars == 2000
        assert inp.listing_age_days == 5000

    def test_full_aapl_with_fundamental(self):
        inp = build_screening_input(
            FIXTURE_OK_US_AAPL_MARKET,
            FIXTURE_OK_US_AAPL_BACKTEST,
            FIXTURE_OK_US_AAPL_FUNDAMENTAL,
            FIXTURE_OK_US_AAPL_METADATA,
            AssetClass.US_STOCK,
            AssetSector.TECH,
        )
        assert inp.per == 28.5
        assert inp.roe == 45.0
        assert inp.tvl_usd is None  # FundamentalSnapshot has tvl_usd=None for stocks

    def test_no_fundamental_none_fields(self):
        inp = build_screening_input(
            FIXTURE_OK_CRYPTO_BTC_MARKET,
            FIXTURE_OK_CRYPTO_BTC_BACKTEST,
            None,
            FIXTURE_OK_CRYPTO_BTC_METADATA,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        assert inp.per is None
        assert inp.roe is None
        assert inp.tvl_usd is None

    def test_no_metadata_none_listing_age(self):
        inp = build_screening_input(
            FIXTURE_OK_CRYPTO_BTC_MARKET,
            FIXTURE_OK_CRYPTO_BTC_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        assert inp.listing_age_days is None

    def test_metadata_listing_age_copied(self):
        inp = build_screening_input(
            FIXTURE_OK_CRYPTO_BTC_MARKET,
            FIXTURE_OK_CRYPTO_BTC_BACKTEST,
            None,
            FIXTURE_OK_CRYPTO_BTC_METADATA,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        assert inp.listing_age_days == 5000

    def test_asset_class_from_parameter(self):
        inp = build_screening_input(
            FIXTURE_OK_US_AAPL_MARKET,
            FIXTURE_OK_US_AAPL_BACKTEST,
            None,
            None,
            AssetClass.US_STOCK,
            AssetSector.TECH,
        )
        assert inp.asset_class == AssetClass.US_STOCK

    def test_sector_from_parameter(self):
        inp = build_screening_input(
            FIXTURE_OK_KR_005930_MARKET,
            FIXTURE_OK_KR_005930_BACKTEST,
            None,
            None,
            AssetClass.KR_STOCK,
            AssetSector.SEMICONDUCTOR,
        )
        assert inp.sector == AssetSector.SEMICONDUCTOR

    def test_symbol_from_market(self):
        inp = build_screening_input(
            FIXTURE_OK_CRYPTO_SOL_MARKET,
            FIXTURE_OK_CRYPTO_SOL_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        assert inp.symbol == "SOL/USDT"

    def test_optional_none_passthrough(self):
        """market_cap=None in source → market_cap_usd=None in input."""
        inp = build_screening_input(
            FIXTURE_OK_F3_PARTIAL_OPTIONAL_MARKET,
            FIXTURE_OK_F3_PARTIAL_OPTIONAL_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        assert inp.market_cap_usd is None
        assert inp.spread_pct is None
        assert inp.price_vs_200ma is None

    def test_mandatory_present(self):
        inp = build_screening_input(
            FIXTURE_OK_CRYPTO_BTC_MARKET,
            FIXTURE_OK_CRYPTO_BTC_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        assert inp.avg_daily_volume_usd is not None
        assert inp.atr_pct is not None
        assert inp.adx is not None
        assert inp.available_bars is not None

    def test_sharpe_and_missing_data_mapped(self):
        inp = build_screening_input(
            FIXTURE_OK_CRYPTO_BTC_MARKET,
            FIXTURE_OK_CRYPTO_BTC_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        assert inp.sharpe_ratio == 0.85
        assert inp.missing_data_pct == 0.3

    def test_kr_stock_no_fundamental(self):
        inp = build_screening_input(
            FIXTURE_OK_KR_005930_MARKET,
            FIXTURE_OK_KR_005930_BACKTEST,
            None,
            FIXTURE_OK_KR_005930_METADATA,
            AssetClass.KR_STOCK,
            AssetSector.SEMICONDUCTOR,
        )
        assert inp.per is None
        assert inp.roe is None
        assert inp.listing_age_days == 10000


# ── transform_provider_to_screening ──────────────────────────────────


class TestTransformProviderToScreening:
    def test_normal_btc_returns_ok(self):
        result = transform_provider_to_screening(
            FIXTURE_OK_CRYPTO_BTC_MARKET,
            FIXTURE_OK_CRYPTO_BTC_BACKTEST,
            None,
            FIXTURE_OK_CRYPTO_BTC_METADATA,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            NOW_UTC,
        )
        assert result.decision == DataQualityDecision.OK
        assert result.screening_input is not None
        assert result.source is not None

    def test_normal_sol_returns_ok(self):
        result = transform_provider_to_screening(
            FIXTURE_OK_CRYPTO_SOL_MARKET,
            FIXTURE_OK_CRYPTO_SOL_BACKTEST,
            None,
            FIXTURE_OK_CRYPTO_SOL_METADATA,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            NOW_UTC,
        )
        assert result.decision == DataQualityDecision.OK

    def test_normal_aapl_returns_ok(self):
        result = transform_provider_to_screening(
            FIXTURE_OK_US_AAPL_MARKET,
            FIXTURE_OK_US_AAPL_BACKTEST,
            FIXTURE_OK_US_AAPL_FUNDAMENTAL,
            FIXTURE_OK_US_AAPL_METADATA,
            AssetClass.US_STOCK,
            AssetSector.TECH,
            NOW_UTC,
        )
        assert result.decision == DataQualityDecision.OK

    def test_normal_kr_returns_ok(self):
        result = transform_provider_to_screening(
            FIXTURE_OK_KR_005930_MARKET,
            FIXTURE_OK_KR_005930_BACKTEST,
            None,
            FIXTURE_OK_KR_005930_METADATA,
            AssetClass.KR_STOCK,
            AssetSector.SEMICONDUCTOR,
            NOW_UTC,
        )
        assert result.decision == DataQualityDecision.OK

    def test_reject_returns_none_input(self):
        result = transform_provider_to_screening(
            FIXTURE_REJECT_F7_NAMESPACE_MARKET,
            FIXTURE_REJECT_F7_NAMESPACE_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            NOW_UTC,
        )
        assert result.screening_input is None

    def test_reject_returns_none_source(self):
        result = transform_provider_to_screening(
            FIXTURE_REJECT_F7_NAMESPACE_MARKET,
            FIXTURE_REJECT_F7_NAMESPACE_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            NOW_UTC,
        )
        assert result.source is None

    def test_namespace_error_returns_none(self):
        result = transform_provider_to_screening(
            FIXTURE_REJECT_F7_NAMESPACE_MARKET,
            FIXTURE_REJECT_F7_NAMESPACE_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            NOW_UTC,
        )
        assert result.decision == DataQualityDecision.SYMBOL_NAMESPACE_ERROR

    def test_stale_reject_returns_none(self):
        result = transform_provider_to_screening(
            FIXTURE_REJECT_F4_STALE_MARKET,
            FIXTURE_REJECT_F4_STALE_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            NOW_UTC,
        )
        assert result.decision == DataQualityDecision.STALE_REJECT
        assert result.screening_input is None

    def test_partial_usable_returns_input(self):
        result = transform_provider_to_screening(
            FIXTURE_OK_F3_PARTIAL_OPTIONAL_MARKET,
            FIXTURE_OK_F3_PARTIAL_OPTIONAL_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            NOW_UTC,
        )
        assert result.decision == DataQualityDecision.PARTIAL_USABLE
        assert result.screening_input is not None

    def test_source_records_provider_names(self):
        result = transform_provider_to_screening(
            FIXTURE_OK_CRYPTO_BTC_MARKET,
            FIXTURE_OK_CRYPTO_BTC_BACKTEST,
            None,
            FIXTURE_OK_CRYPTO_BTC_METADATA,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            NOW_UTC,
            market_provider="binance_ccxt",
            backtest_provider="local_db",
        )
        assert result.source.market_provider == "binance_ccxt"
        assert result.source.backtest_provider == "local_db"

    def test_source_records_timestamp(self):
        result = transform_provider_to_screening(
            FIXTURE_OK_CRYPTO_BTC_MARKET,
            FIXTURE_OK_CRYPTO_BTC_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            NOW_UTC,
        )
        assert result.source.build_timestamp == NOW_UTC

    def test_source_records_stale_decision(self):
        result = transform_provider_to_screening(
            FIXTURE_OK_CRYPTO_BTC_MARKET,
            FIXTURE_OK_CRYPTO_BTC_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            NOW_UTC,
        )
        assert result.source.stale_decision == DataQualityDecision.OK

    def test_f6_missing_listing_age_ok(self):
        result = transform_provider_to_screening(
            FIXTURE_OK_F6_NO_LISTING_AGE_MARKET,
            FIXTURE_OK_F6_NO_LISTING_AGE_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            NOW_UTC,
        )
        assert result.decision == DataQualityDecision.OK
        assert result.screening_input is not None
        assert result.screening_input.listing_age_days is None

    def test_f5_insufficient_bars_passes_validate(self):
        result = transform_provider_to_screening(
            FIXTURE_OK_F5_INSUFFICIENT_BARS_MARKET,
            FIXTURE_OK_F5_INSUFFICIENT_BARS_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            NOW_UTC,
        )
        assert result.decision == DataQualityDecision.OK
        assert result.screening_input is not None
        assert result.screening_input.available_bars == 100

    def test_reject_decisions_constant(self):
        assert len(_REJECT_DECISIONS) == 4
        assert DataQualityDecision.PARTIAL_REJECT in _REJECT_DECISIONS
        assert DataQualityDecision.STALE_REJECT in _REJECT_DECISIONS
        assert DataQualityDecision.SYMBOL_NAMESPACE_ERROR in _REJECT_DECISIONS
        assert DataQualityDecision.PROVIDER_UNAVAILABLE in _REJECT_DECISIONS


# ── ScreeningInputSource ─────────────────────────────────────────────


class TestScreeningInputSource:
    def test_frozen(self):
        src = ScreeningInputSource(symbol="BTC/USDT")
        with pytest.raises(AttributeError):
            src.market_provider = "changed"  # type: ignore

    def test_default_values(self):
        src = ScreeningInputSource(symbol="TEST")
        assert src.market_provider == "unknown"
        assert src.backtest_provider == "unknown"
        assert src.fundamental_provider == "unknown"
        assert src.metadata_provider == "unknown"
        assert src.market_timestamp is None
        assert src.build_timestamp is None
        assert src.stale_decision == DataQualityDecision.OK

    def test_full_construction(self):
        src = ScreeningInputSource(
            symbol="BTC/USDT",
            market_provider="binance",
            backtest_provider="local_db",
            fundamental_provider="coingecko",
            metadata_provider="registry",
            market_timestamp=NOW_UTC,
            build_timestamp=NOW_UTC,
            stale_decision=DataQualityDecision.OK,
            partial_decision=DataQualityDecision.PARTIAL_USABLE,
        )
        assert src.symbol == "BTC/USDT"
        assert src.partial_decision == DataQualityDecision.PARTIAL_USABLE

    def test_audit_only_no_screener_impact(self):
        """Source existence should not change screening result."""
        result_with_source = transform_provider_to_screening(
            FIXTURE_OK_CRYPTO_BTC_MARKET,
            FIXTURE_OK_CRYPTO_BTC_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            NOW_UTC,
            market_provider="provider_a",
        )
        result_diff_source = transform_provider_to_screening(
            FIXTURE_OK_CRYPTO_BTC_MARKET,
            FIXTURE_OK_CRYPTO_BTC_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            NOW_UTC,
            market_provider="provider_b",
        )
        # Same screening input despite different source
        assert (
            result_with_source.screening_input.symbol == result_diff_source.screening_input.symbol
        )
        assert (
            result_with_source.screening_input.atr_pct == result_diff_source.screening_input.atr_pct
        )

    def test_paired_with_screening_input(self):
        result = transform_provider_to_screening(
            FIXTURE_OK_CRYPTO_BTC_MARKET,
            FIXTURE_OK_CRYPTO_BTC_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            NOW_UTC,
        )
        assert result.screening_input is not None
        assert result.source is not None
        assert result.source.symbol == result.screening_input.symbol


# ── TransformResult ──────────────────────────────────────────────────


class TestTransformResult:
    def test_frozen(self):
        tr = TransformResult(decision=DataQualityDecision.OK)
        with pytest.raises(AttributeError):
            tr.decision = DataQualityDecision.STALE_REJECT  # type: ignore

    def test_reject_invariant(self):
        tr = TransformResult(decision=DataQualityDecision.PARTIAL_REJECT)
        assert tr.screening_input is None
        assert tr.source is None

    def test_ok_invariant(self):
        result = transform_provider_to_screening(
            FIXTURE_OK_CRYPTO_BTC_MARKET,
            FIXTURE_OK_CRYPTO_BTC_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            NOW_UTC,
        )
        assert result.decision == DataQualityDecision.OK
        assert result.screening_input is not None
        assert result.source is not None

    def test_partial_usable_has_input(self):
        result = transform_provider_to_screening(
            FIXTURE_OK_F3_PARTIAL_OPTIONAL_MARKET,
            FIXTURE_OK_F3_PARTIAL_OPTIONAL_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            NOW_UTC,
        )
        assert result.decision == DataQualityDecision.PARTIAL_USABLE
        assert result.screening_input is not None

    def test_decision_preserved(self):
        result = transform_provider_to_screening(
            FIXTURE_REJECT_F4_STALE_MARKET,
            FIXTURE_REJECT_F4_STALE_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            NOW_UTC,
        )
        assert result.decision == DataQualityDecision.STALE_REJECT


# ── Failure Mode Integration ─────────────────────────────────────────


class TestFailureModeIntegration:
    def test_f1_empty_to_reject(self):
        result = transform_provider_to_screening(
            FIXTURE_REJECT_F1_EMPTY_MARKET,
            FIXTURE_REJECT_F1_EMPTY_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            NOW_UTC,
        )
        assert result.decision in _REJECT_DECISIONS
        assert result.screening_input is None

    def test_f2_partial_mandatory_to_reject(self):
        result = transform_provider_to_screening(
            FIXTURE_REJECT_F2_PARTIAL_MARKET,
            FIXTURE_REJECT_F2_PARTIAL_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            NOW_UTC,
        )
        assert result.decision == DataQualityDecision.PARTIAL_REJECT

    def test_f3_partial_optional_usable(self):
        result = transform_provider_to_screening(
            FIXTURE_OK_F3_PARTIAL_OPTIONAL_MARKET,
            FIXTURE_OK_F3_PARTIAL_OPTIONAL_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            NOW_UTC,
        )
        assert result.decision == DataQualityDecision.PARTIAL_USABLE
        assert result.screening_input is not None

    def test_f4_stale_to_reject(self):
        result = transform_provider_to_screening(
            FIXTURE_REJECT_F4_STALE_MARKET,
            FIXTURE_REJECT_F4_STALE_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            NOW_UTC,
        )
        assert result.decision == DataQualityDecision.STALE_REJECT

    def test_f5_insufficient_bars_passes(self):
        result = transform_provider_to_screening(
            FIXTURE_OK_F5_INSUFFICIENT_BARS_MARKET,
            FIXTURE_OK_F5_INSUFFICIENT_BARS_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            NOW_UTC,
        )
        assert result.screening_input is not None
        assert result.screening_input.available_bars == 100

    def test_f6_no_listing_age_passes(self):
        result = transform_provider_to_screening(
            FIXTURE_OK_F6_NO_LISTING_AGE_MARKET,
            FIXTURE_OK_F6_NO_LISTING_AGE_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            NOW_UTC,
        )
        assert result.screening_input is not None
        assert result.screening_input.listing_age_days is None

    def test_f7_namespace_to_reject(self):
        result = transform_provider_to_screening(
            FIXTURE_REJECT_F7_NAMESPACE_MARKET,
            FIXTURE_REJECT_F7_NAMESPACE_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            NOW_UTC,
        )
        assert result.decision == DataQualityDecision.SYMBOL_NAMESPACE_ERROR

    def test_f8_timeout_empty_to_reject(self):
        result = transform_provider_to_screening(
            FIXTURE_REJECT_F8_TIMEOUT_MARKET,
            FIXTURE_REJECT_F8_TIMEOUT_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            NOW_UTC,
        )
        assert result.decision in _REJECT_DECISIONS

    def test_f9_degraded_usable(self):
        result = transform_provider_to_screening(
            FIXTURE_OK_F9_DEGRADED_MARKET,
            FIXTURE_OK_F9_DEGRADED_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            NOW_UTC,
        )
        assert result.screening_input is not None
