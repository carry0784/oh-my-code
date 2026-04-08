"""
CR-046 C1-A: Diagnostic Receipt Extension tests.

Verifies:
  1. last_diagnostic() lifecycle (init, cache, copy, exception)
  2. skip_reason_codes canonical values
  3. near_miss_type canonical rule
  4. Receipt fallback (diagnostic failure never blocks receipt)
  5. diagnostic_version / diagnostic_populated fields
"""

from __future__ import annotations

import numpy as np
import pytest

from strategies.base import BaseStrategy
from strategies.smc_wavetrend_strategy import SMCWaveTrendStrategy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_flat_ohlcv(n: int = 100, base: float = 100.0) -> list[list]:
    """Generate flat OHLCV data (no trend change → SMC=0, WT=0)."""
    return [
        [1_700_000_000_000 + i * 3_600_000, base, base + 0.1, base - 0.1, base, 1000.0]
        for i in range(n)
    ]


def _make_trending_ohlcv(n: int = 100, start: float = 100.0) -> list[list]:
    """Generate uptrending OHLCV data to potentially trigger signals."""
    bars = []
    for i in range(n):
        price = start + i * 0.5
        bars.append([
            1_700_000_000_000 + i * 3_600_000,
            price,            # open
            price + 1.0,      # high
            price - 0.5,      # low
            price + 0.3,      # close
            1000.0,           # volume
        ])
    return bars


# ---------------------------------------------------------------------------
# 1. last_diagnostic() lifecycle
# ---------------------------------------------------------------------------

class TestLastDiagnosticLifecycle:

    def test_empty_before_analyze(self):
        """Before analyze(), last_diagnostic() returns empty dict."""
        s = SMCWaveTrendStrategy(symbol="TEST/USDT")
        diag = s.last_diagnostic()
        assert diag == {}

    def test_populated_after_analyze_none(self):
        """After analyze() → None, diagnostic is populated."""
        s = SMCWaveTrendStrategy(symbol="TEST/USDT")
        result = s.analyze(_make_flat_ohlcv(100))
        assert result is None
        diag = s.last_diagnostic()
        assert diag.get("diagnostic_populated") is True
        assert "smc_sig_raw" in diag
        assert "wt_sig_raw" in diag

    def test_returns_copy_not_reference(self):
        """last_diagnostic() returns a copy — mutation doesn't affect internal state."""
        s = SMCWaveTrendStrategy(symbol="TEST/USDT")
        s.analyze(_make_flat_ohlcv(100))
        d1 = s.last_diagnostic()
        d1["injected"] = True
        d2 = s.last_diagnostic()
        assert "injected" not in d2

    def test_reset_on_new_analyze(self):
        """Each analyze() call resets diagnostic from previous call."""
        s = SMCWaveTrendStrategy(symbol="TEST/USDT")
        s.analyze(_make_flat_ohlcv(100))
        d1 = s.last_diagnostic()
        assert d1.get("diagnostic_populated") is True

        # Second call with different data
        s.analyze(_make_flat_ohlcv(50, base=200.0))
        d2 = s.last_diagnostic()
        assert d2.get("diagnostic_populated") is True
        # Close price should differ
        assert d2["close_price"] != d1["close_price"]

    def test_insufficient_data(self):
        """When data is insufficient, diagnostic_populated=False."""
        s = SMCWaveTrendStrategy(symbol="TEST/USDT")
        result = s.analyze(_make_flat_ohlcv(5))  # Less than min_bars
        assert result is None
        diag = s.last_diagnostic()
        assert diag.get("diagnostic_populated") is False

    def test_base_strategy_default(self):
        """BaseStrategy.last_diagnostic() returns empty dict by default."""

        class DummyStrategy(BaseStrategy):
            @property
            def name(self):
                return "dummy"

            def analyze(self, ohlcv, **kwargs):
                return None

        s = DummyStrategy(symbol="TEST/USDT")
        assert s.last_diagnostic() == {}


# ---------------------------------------------------------------------------
# 2. skip_reason_codes
# ---------------------------------------------------------------------------

class TestSkipReasonCodes:

    def test_both_zero(self):
        """Flat data → both SMC and WT are 0 → [SMC_ZERO, WT_ZERO]."""
        s = SMCWaveTrendStrategy(symbol="TEST/USDT")
        s.analyze(_make_flat_ohlcv(100))
        diag = s.last_diagnostic()
        codes = diag.get("skip_reason_codes", [])
        assert "SMC_ZERO" in codes
        assert "WT_ZERO" in codes

    def test_no_both_zero_code(self):
        """BOTH_ZERO should never appear as a code."""
        s = SMCWaveTrendStrategy(symbol="TEST/USDT")
        s.analyze(_make_flat_ohlcv(100))
        diag = s.last_diagnostic()
        codes = diag.get("skip_reason_codes", [])
        assert "BOTH_ZERO" not in codes

    def test_codes_is_list(self):
        """skip_reason_codes must always be a list."""
        s = SMCWaveTrendStrategy(symbol="TEST/USDT")
        s.analyze(_make_flat_ohlcv(100))
        diag = s.last_diagnostic()
        assert isinstance(diag["skip_reason_codes"], list)

    def test_valid_code_values_only(self):
        """Only canonical code values are permitted."""
        valid_codes = {"SMC_ZERO", "WT_ZERO", "DIRECTION_MISMATCH", "DATA_INSUFFICIENT"}
        s = SMCWaveTrendStrategy(symbol="TEST/USDT")
        s.analyze(_make_flat_ohlcv(100))
        codes = s.last_diagnostic()["skip_reason_codes"]
        for code in codes:
            assert code in valid_codes, f"Unexpected code: {code}"


# ---------------------------------------------------------------------------
# 3. near_miss_type canonical rule
# ---------------------------------------------------------------------------

class TestNearMissType:

    def test_canonical_smc_only(self):
        assert SMCWaveTrendStrategy._compute_near_miss_type(1, 0) == "SMC_ONLY"
        assert SMCWaveTrendStrategy._compute_near_miss_type(-1, 0) == "SMC_ONLY"

    def test_canonical_wt_only(self):
        assert SMCWaveTrendStrategy._compute_near_miss_type(0, 1) == "WT_ONLY"
        assert SMCWaveTrendStrategy._compute_near_miss_type(0, -1) == "WT_ONLY"

    def test_canonical_dir_mismatch(self):
        assert SMCWaveTrendStrategy._compute_near_miss_type(1, -1) == "DIR_MISMATCH"
        assert SMCWaveTrendStrategy._compute_near_miss_type(-1, 1) == "DIR_MISMATCH"

    def test_canonical_null(self):
        assert SMCWaveTrendStrategy._compute_near_miss_type(0, 0) is None
        assert SMCWaveTrendStrategy._compute_near_miss_type(1, 1) is None
        assert SMCWaveTrendStrategy._compute_near_miss_type(-1, -1) is None

    def test_flat_data_is_null(self):
        """Flat data → both zero → near_miss_type is None."""
        s = SMCWaveTrendStrategy(symbol="TEST/USDT")
        s.analyze(_make_flat_ohlcv(100))
        assert s.last_diagnostic()["near_miss_type"] is None


# ---------------------------------------------------------------------------
# 4. Receipt fallback
# ---------------------------------------------------------------------------

class TestReceiptFallback:

    def test_diagnostic_field_is_optional(self):
        """PaperTradingReceipt.diagnostic defaults to None."""
        from app.services.paper_trading_session_cr046 import PaperTradingReceipt
        r = PaperTradingReceipt()
        assert r.diagnostic is None

    def test_receipt_serializable_with_diagnostic(self):
        """Receipt with diagnostic can be serialized via dataclasses.asdict."""
        import dataclasses
        from app.services.paper_trading_session_cr046 import PaperTradingReceipt

        r = PaperTradingReceipt(
            diagnostic={
                "smc_sig_raw": 0,
                "wt_sig_raw": 0,
                "diagnostic_populated": True,
                "diagnostic_version": 1,
            }
        )
        d = dataclasses.asdict(r)
        assert d["diagnostic"]["smc_sig_raw"] == 0
        assert d["diagnostic"]["diagnostic_version"] == 1

    def test_receipt_serializable_without_diagnostic(self):
        """Receipt without diagnostic (None) can be serialized."""
        import dataclasses
        from app.services.paper_trading_session_cr046 import PaperTradingReceipt

        r = PaperTradingReceipt()
        d = dataclasses.asdict(r)
        assert d["diagnostic"] is None


# ---------------------------------------------------------------------------
# 5. diagnostic_version / diagnostic_populated
# ---------------------------------------------------------------------------

class TestDiagnosticMeta:

    def test_version_is_1(self):
        s = SMCWaveTrendStrategy(symbol="TEST/USDT")
        s.analyze(_make_flat_ohlcv(100))
        assert s.last_diagnostic()["diagnostic_version"] == 1

    def test_diagnostic_only_is_true(self):
        s = SMCWaveTrendStrategy(symbol="TEST/USDT")
        s.analyze(_make_flat_ohlcv(100))
        assert s.last_diagnostic()["diagnostic_only"] is True

    def test_populated_true_on_success(self):
        s = SMCWaveTrendStrategy(symbol="TEST/USDT")
        s.analyze(_make_flat_ohlcv(100))
        assert s.last_diagnostic()["diagnostic_populated"] is True

    def test_populated_false_on_insufficient(self):
        s = SMCWaveTrendStrategy(symbol="TEST/USDT")
        s.analyze(_make_flat_ohlcv(5))
        assert s.last_diagnostic()["diagnostic_populated"] is False


# ---------------------------------------------------------------------------
# 6. P1/P2 field presence
# ---------------------------------------------------------------------------

class TestFieldPresence:

    def test_p1_fields_present(self):
        """P1 fields: smc_sig_raw, smc_trend_raw, close_price."""
        s = SMCWaveTrendStrategy(symbol="TEST/USDT")
        s.analyze(_make_flat_ohlcv(100))
        diag = s.last_diagnostic()
        assert "smc_sig_raw" in diag
        assert "smc_trend_raw" in diag
        assert "close_price" in diag

    def test_p2_fields_present(self):
        """P2 fields: wt_sig_raw, wt1_val, wt2_val, wt_cross_distance."""
        s = SMCWaveTrendStrategy(symbol="TEST/USDT")
        s.analyze(_make_flat_ohlcv(100))
        diag = s.last_diagnostic()
        assert "wt_sig_raw" in diag
        assert "wt1_val" in diag
        assert "wt2_val" in diag
        assert "wt_cross_distance" in diag

    def test_p3_fields_present(self):
        """P3 fields: skip_reason_codes, near_miss_type, diagnostic_only, diagnostic_version, diagnostic_populated."""
        s = SMCWaveTrendStrategy(symbol="TEST/USDT")
        s.analyze(_make_flat_ohlcv(100))
        diag = s.last_diagnostic()
        assert "skip_reason_codes" in diag
        assert "near_miss_type" in diag
        assert "diagnostic_only" in diag
        assert "diagnostic_version" in diag
        assert "diagnostic_populated" in diag
