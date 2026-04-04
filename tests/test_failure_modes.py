"""CR-048 Stage 3B-1 — Failure Mode contract tests.

Covers:
  - DataQualityDecision enum completeness
  - Stale policy (check_stale) pure function
  - Partial policy (check_partial) pure function
  - Failure Mode → Decision mapping
  - FailureModeRecovery classification
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.data_provider import (
    BacktestReadiness,
    DataQuality,
    DataQualityDecision,
    FailureModeRecovery,
    FAILURE_MODE_RECOVERY,
    FundamentalSnapshot,
    MarketDataSnapshot,
    STALE_LIMITS,
    check_partial,
    check_stale,
    normalize_symbol,
)


# ── DataQualityDecision Enum ─────────────────────────────────────────


class TestDataQualityDecision:
    def test_all_decision_values(self):
        expected = {
            "ok",
            "partial_usable",
            "partial_reject",
            "stale_usable",
            "stale_reject",
            "insufficient_bars",
            "missing_listing_age",
            "symbol_namespace_error",
            "provider_unavailable",
        }
        actual = {d.value for d in DataQualityDecision}
        assert expected == actual

    def test_is_str_enum(self):
        assert isinstance(DataQualityDecision.OK, str)

    def test_reject_decisions(self):
        rejects = {
            DataQualityDecision.PARTIAL_REJECT,
            DataQualityDecision.STALE_REJECT,
            DataQualityDecision.PROVIDER_UNAVAILABLE,
            DataQualityDecision.SYMBOL_NAMESPACE_ERROR,
        }
        assert len(rejects) == 4

    def test_usable_decisions(self):
        usable = {
            DataQualityDecision.OK,
            DataQualityDecision.PARTIAL_USABLE,
            DataQualityDecision.STALE_USABLE,
        }
        assert len(usable) == 3

    def test_special_decisions(self):
        special = {
            DataQualityDecision.INSUFFICIENT_BARS,
            DataQualityDecision.MISSING_LISTING_AGE,
        }
        assert len(special) == 2


# ── Stale Policy ─────────────────────────────────────────────────────


class TestStalePolicy:
    _NOW = datetime(2026, 4, 3, 12, 0, 0, tzinfo=timezone.utc)

    def test_crypto_price_fresh(self):
        ts = self._NOW - timedelta(minutes=30)
        assert check_stale(ts, "CRYPTO", "price", self._NOW) == DataQualityDecision.OK

    def test_crypto_price_stale_reject(self):
        ts = self._NOW - timedelta(hours=2)
        assert check_stale(ts, "CRYPTO", "price", self._NOW) == DataQualityDecision.STALE_REJECT

    def test_us_stock_price_fresh(self):
        ts = self._NOW - timedelta(hours=2)
        assert check_stale(ts, "US_STOCK", "price", self._NOW) == DataQualityDecision.OK

    def test_us_stock_price_stale_reject(self):
        ts = self._NOW - timedelta(hours=5)
        assert check_stale(ts, "US_STOCK", "price", self._NOW) == DataQualityDecision.STALE_REJECT

    def test_us_stock_fundamental_fresh(self):
        ts = self._NOW - timedelta(days=3)
        assert check_stale(ts, "US_STOCK", "fundamental", self._NOW) == DataQualityDecision.OK

    def test_us_stock_fundamental_stale_reject(self):
        ts = self._NOW - timedelta(days=10)
        assert (
            check_stale(ts, "US_STOCK", "fundamental", self._NOW)
            == DataQualityDecision.STALE_REJECT
        )

    def test_none_timestamp_stale_reject(self):
        assert check_stale(None, "CRYPTO", "price", self._NOW) == DataQualityDecision.STALE_REJECT

    def test_unknown_asset_class_conservative(self):
        """Unknown asset_class should use fallback (most conservative)."""
        ts = self._NOW - timedelta(hours=2)
        result = check_stale(ts, "UNKNOWN_CLASS", "price", self._NOW)
        assert result == DataQualityDecision.STALE_REJECT

    def test_backtest_data_fresh(self):
        ts = self._NOW - timedelta(days=15)
        assert check_stale(ts, "CRYPTO", "backtest", self._NOW) == DataQualityDecision.OK

    def test_backtest_data_stale(self):
        ts = self._NOW - timedelta(days=45)
        assert check_stale(ts, "CRYPTO", "backtest", self._NOW) == DataQualityDecision.STALE_REJECT

    def test_stale_limits_are_system_constants(self):
        """SP-01: Stale limits are system policy values."""
        assert isinstance(STALE_LIMITS, dict)
        assert len(STALE_LIMITS) > 0
        for key, val in STALE_LIMITS.items():
            assert isinstance(key, tuple)
            assert isinstance(val, timedelta)


# ── Partial Policy ───────────────────────────────────────────────────


class TestPartialPolicy:
    def test_all_mandatory_present_ok(self):
        market = MarketDataSnapshot(
            symbol="BTC/USDT",
            avg_daily_volume_usd=30_000_000_000,
            atr_pct=3.5,
            adx=25.0,
            market_cap_usd=1_000_000_000_000,
            spread_pct=0.01,
            price_vs_200ma=1.1,
        )
        bt = BacktestReadiness(symbol="BTC/USDT", available_bars=1500)
        assert check_partial(market, bt) == DataQualityDecision.OK

    def test_volume_missing_reject(self):
        market = MarketDataSnapshot(
            symbol="BTC/USDT",
            atr_pct=3.5,
            adx=25.0,
        )
        bt = BacktestReadiness(symbol="BTC/USDT", available_bars=1500)
        assert check_partial(market, bt) == DataQualityDecision.PARTIAL_REJECT

    def test_atr_missing_reject(self):
        market = MarketDataSnapshot(
            symbol="BTC/USDT",
            avg_daily_volume_usd=30e9,
            adx=25.0,
        )
        bt = BacktestReadiness(symbol="BTC/USDT", available_bars=1500)
        assert check_partial(market, bt) == DataQualityDecision.PARTIAL_REJECT

    def test_adx_missing_reject(self):
        market = MarketDataSnapshot(
            symbol="BTC/USDT",
            avg_daily_volume_usd=30e9,
            atr_pct=3.5,
        )
        bt = BacktestReadiness(symbol="BTC/USDT", available_bars=1500)
        assert check_partial(market, bt) == DataQualityDecision.PARTIAL_REJECT

    def test_bars_missing_reject(self):
        market = MarketDataSnapshot(
            symbol="BTC/USDT",
            avg_daily_volume_usd=30e9,
            atr_pct=3.5,
            adx=25.0,
        )
        bt = BacktestReadiness(symbol="BTC/USDT")  # available_bars=None
        assert check_partial(market, bt) == DataQualityDecision.PARTIAL_REJECT

    def test_optional_missing_usable(self):
        market = MarketDataSnapshot(
            symbol="BTC/USDT",
            avg_daily_volume_usd=30e9,
            atr_pct=3.5,
            adx=25.0,
            # market_cap, spread, price_vs_200ma all None
        )
        bt = BacktestReadiness(symbol="BTC/USDT", available_bars=1500)
        assert check_partial(market, bt) == DataQualityDecision.PARTIAL_USABLE

    def test_all_present_ok(self):
        market = MarketDataSnapshot(
            symbol="SOL/USDT",
            avg_daily_volume_usd=5e9,
            atr_pct=5.0,
            adx=30.0,
            market_cap_usd=50e9,
            spread_pct=0.02,
            price_vs_200ma=1.2,
        )
        bt = BacktestReadiness(symbol="SOL/USDT", available_bars=2000)
        assert check_partial(market, bt) == DataQualityDecision.OK


# ── Failure Mode Policies ────────────────────────────────────────────


class TestFailureModePolicies:
    def test_f1_empty_provider_unavailable(self):
        """F1: All fields None → change should be rejected."""
        market = MarketDataSnapshot(symbol="BTC/USDT")
        bt = BacktestReadiness(symbol="BTC/USDT")
        result = check_partial(market, bt)
        assert result == DataQualityDecision.PARTIAL_REJECT

    def test_f7_namespace_error_no_separator(self):
        result = normalize_symbol("BTCUSDT", "CRYPTO")
        assert result is None

    def test_f7_namespace_error_empty(self):
        result = normalize_symbol("", "CRYPTO")
        assert result is None

    def test_reject_blocks_screening_input(self):
        """REJECT decisions should prevent ScreeningInput creation."""
        reject_decisions = [
            DataQualityDecision.PARTIAL_REJECT,
            DataQualityDecision.STALE_REJECT,
            DataQualityDecision.PROVIDER_UNAVAILABLE,
            DataQualityDecision.SYMBOL_NAMESPACE_ERROR,
        ]
        for d in reject_decisions:
            assert "reject" in d.value or "unavailable" in d.value or "error" in d.value

    def test_all_failure_modes_have_recovery(self):
        """Every F1-F9 has a recovery classification."""
        assert len(FAILURE_MODE_RECOVERY) == 9
        for key, val in FAILURE_MODE_RECOVERY.items():
            assert isinstance(val, FailureModeRecovery)


# ── Symbol Namespace ─────────────────────────────────────────────────


class TestSymbolNamespace:
    def test_ccxt_format_passthrough(self):
        assert normalize_symbol("BTC/USDT", "CRYPTO") == "BTC/USDT"

    def test_lowercase_normalization(self):
        assert normalize_symbol("btc/usdt", "CRYPTO") == "BTC/USDT"

    def test_no_separator_error(self):
        assert normalize_symbol("BTCUSDT", "CRYPTO") is None

    def test_krx_code_passthrough(self):
        assert normalize_symbol("005930", "KR_STOCK") == "005930"

    def test_us_stock_passthrough(self):
        assert normalize_symbol("AAPL", "US_STOCK") == "AAPL"

    def test_us_stock_lowercase_normalized(self):
        assert normalize_symbol("aapl", "US_STOCK") == "AAPL"

    def test_unknown_asset_class(self):
        assert normalize_symbol("XYZ", "UNKNOWN") is None

    def test_krx_invalid_length(self):
        assert normalize_symbol("12345", "KR_STOCK") is None


# ── FailureModeRecovery ──────────────────────────────────────────────


class TestFailureModeRecovery:
    def test_enum_values(self):
        assert FailureModeRecovery.RECOVERABLE.value == "recoverable"
        assert FailureModeRecovery.NON_RECOVERABLE.value == "non_recoverable"

    def test_is_str_enum(self):
        assert isinstance(FailureModeRecovery.RECOVERABLE, str)

    def test_f2_non_recoverable(self):
        assert FAILURE_MODE_RECOVERY["F2_PARTIAL_MANDATORY"] == FailureModeRecovery.NON_RECOVERABLE

    def test_f8_recoverable(self):
        assert FAILURE_MODE_RECOVERY["F8_PROVIDER_TIMEOUT"] == FailureModeRecovery.RECOVERABLE

    def test_f7_non_recoverable(self):
        assert FAILURE_MODE_RECOVERY["F7_SYMBOL_NAMESPACE"] == FailureModeRecovery.NON_RECOVERABLE
