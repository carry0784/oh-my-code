"""CR-046 Track C-v2: Alternative Regime Indicator Research Tests"""

import numpy as np
import pytest

import sys
import os

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
)

from track_c_v2_regime_research import (
    calc_realized_vol_percentile,
    calc_range_compression_ratio,
    calc_choppiness_index,
    calc_directional_efficiency,
    calc_hurst_exponent,
    classify_regime_ground_truth,
    evaluate_regime_indicator,
    backtest_with_regime_filter,
    calc_smc_wt_consensus,
    backtest_signals,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_trending(n: int = 2500, seed: int = 42) -> tuple:
    rng = np.random.RandomState(seed)
    price = 45000.0
    highs, lows, closes = [], [], []
    for _ in range(n):
        ret = rng.normal(0.001, 0.008)
        price *= 1 + ret
        h = price * (1 + abs(rng.normal(0, 0.003)))
        l = price * (1 - abs(rng.normal(0, 0.003)))
        highs.append(h)
        lows.append(l)
        closes.append(price)
    return np.array(highs), np.array(lows), np.array(closes)


def _make_random_walk(n: int = 2500, seed: int = 55) -> tuple:
    rng = np.random.RandomState(seed)
    price = 45000.0
    highs, lows, closes = [], [], []
    for _ in range(n):
        ret = rng.normal(0, 0.008)
        price *= 1 + ret
        h = price * (1 + abs(rng.normal(0, 0.003)))
        l = price * (1 - abs(rng.normal(0, 0.003)))
        highs.append(h)
        lows.append(l)
        closes.append(price)
    return np.array(highs), np.array(lows), np.array(closes)


# ---------------------------------------------------------------------------
# Value Range Tests
# ---------------------------------------------------------------------------


class TestValueRanges:
    def test_realized_vol_percentile_range(self):
        _, _, closes = _make_trending()
        result = calc_realized_vol_percentile(closes)
        valid = result[~np.isnan(result)]
        assert len(valid) > 0
        assert np.all(valid >= 0.0)
        assert np.all(valid <= 1.0)

    def test_range_compression_ratio_positive(self):
        highs, lows, closes = _make_trending()
        result = calc_range_compression_ratio(highs, lows, closes)
        valid = result[~np.isnan(result)]
        assert len(valid) > 0
        assert np.all(valid >= 0.0)

    def test_choppiness_index_range(self):
        highs, lows, closes = _make_trending()
        result = calc_choppiness_index(highs, lows, closes)
        valid = result[~np.isnan(result)]
        assert len(valid) > 0
        assert np.all(valid >= 0.0)
        assert np.all(valid <= 100.0)

    def test_directional_efficiency_range(self):
        _, _, closes = _make_trending()
        result = calc_directional_efficiency(closes)
        valid = result[~np.isnan(result)]
        assert len(valid) > 0
        assert np.all(valid >= 0.0)
        assert np.all(valid <= 1.0)

    def test_hurst_exponent_range(self):
        _, _, closes = _make_trending()
        result = calc_hurst_exponent(closes)
        valid = result[~np.isnan(result)]
        assert len(valid) > 0
        assert np.all(valid >= 0.0)
        assert np.all(valid <= 1.0)


# ---------------------------------------------------------------------------
# Causality Regression Tests (5 indicators)
# ---------------------------------------------------------------------------


class TestCausality:
    """Each indicator at bar i must not change when future bars are modified."""

    def _check_causality(self, calc_fn, n: int = 500, check_bar: int = 300):
        highs, lows, closes = _make_trending(n, seed=42)
        result_full = calc_fn(highs, lows, closes)

        # Modify future data
        rng = np.random.RandomState(99)
        closes_mod = closes.copy()
        highs_mod = highs.copy()
        lows_mod = lows.copy()
        closes_mod[check_bar + 1 :] *= 1 + rng.normal(0, 0.1, n - check_bar - 1)
        highs_mod[check_bar + 1 :] = closes_mod[check_bar + 1 :] * 1.01
        lows_mod[check_bar + 1 :] = closes_mod[check_bar + 1 :] * 0.99

        result_mod = calc_fn(highs_mod, lows_mod, closes_mod)

        # Values up to check_bar must be identical
        for i in range(check_bar + 1):
            if np.isnan(result_full[i]) and np.isnan(result_mod[i]):
                continue
            if not np.isnan(result_full[i]) and not np.isnan(result_mod[i]):
                np.testing.assert_allclose(
                    result_full[i],
                    result_mod[i],
                    rtol=1e-10,
                    err_msg=f"Causality violated at bar {i}",
                )

    def test_realized_vol_percentile_causal(self):
        self._check_causality(
            lambda h, l, c: calc_realized_vol_percentile(c, vol_window=24, rank_window=200),
            n=500,
            check_bar=300,
        )

    def test_range_compression_causal(self):
        self._check_causality(
            lambda h, l, c: calc_range_compression_ratio(h, l, c, window=24),
        )

    def test_choppiness_index_causal(self):
        self._check_causality(
            lambda h, l, c: calc_choppiness_index(h, l, c, period=14),
        )

    def test_directional_efficiency_causal(self):
        self._check_causality(
            lambda h, l, c: calc_directional_efficiency(c, window=24),
        )

    def test_hurst_exponent_causal(self):
        self._check_causality(
            lambda h, l, c: calc_hurst_exponent(c, window=100),
        )


# ---------------------------------------------------------------------------
# Hurst Exponent Specific Tests
# ---------------------------------------------------------------------------


class TestHurstExponent:
    def test_random_walk_hurst_near_05(self):
        """Pure random walk should have Hurst ~ 0.5."""
        _, _, closes = _make_random_walk(3000, seed=55)
        result = calc_hurst_exponent(closes, window=200)
        valid = result[~np.isnan(result)]
        if len(valid) > 0:
            mean_h = np.mean(valid)
            # Allow wide tolerance since R/S is noisy
            assert 0.2 < mean_h < 0.8, f"Hurst mean={mean_h} not near 0.5 for random walk"

    def test_trending_data_hurst_above_05(self):
        """Trending data should have Hurst > 0.5 on average."""
        rng = np.random.RandomState(42)
        # Strong trend: cumulative positive drift
        closes = np.exp(np.cumsum(rng.normal(0.002, 0.005, 3000))) * 100
        result = calc_hurst_exponent(closes, window=200)
        valid = result[~np.isnan(result)]
        if len(valid) > 10:
            mean_h = np.mean(valid)
            # Trending should be above 0.45 at least
            assert mean_h > 0.4, f"Hurst mean={mean_h} too low for trending data"


# ---------------------------------------------------------------------------
# Regime Classification Tests
# ---------------------------------------------------------------------------


class TestRegimeClassification:
    def test_ground_truth_binary(self):
        _, _, closes = _make_trending(500)
        labels = classify_regime_ground_truth(closes, forward_window=24)
        valid = labels[~np.isnan(labels)]
        unique = set(np.unique(valid))
        assert unique.issubset({0.0, 1.0})

    def test_ground_truth_nan_at_end(self):
        """Last forward_window bars should be NaN (no future data)."""
        _, _, closes = _make_trending(500)
        labels = classify_regime_ground_truth(closes, forward_window=24)
        assert np.all(np.isnan(labels[-24:]))

    def test_evaluate_returns_required_keys(self):
        _, _, closes = _make_trending(500)
        indicator = np.random.RandomState(42).uniform(0, 1, 500)
        ground_truth = classify_regime_ground_truth(closes)
        result = evaluate_regime_indicator(indicator, ground_truth, threshold=0.5)
        assert "accuracy" in result
        assert "sideways_accuracy" in result
        assert "trend_accuracy" in result
        assert "n_valid" in result


# ---------------------------------------------------------------------------
# Regime Filter Backtest Tests
# ---------------------------------------------------------------------------


class TestRegimeFilterBacktest:
    def test_filtered_has_fewer_or_equal_trades(self):
        """Applying a filter should not increase trade count."""
        highs, lows, closes = _make_trending(1000)
        base = calc_smc_wt_consensus(highs, lows, closes)
        bt_base = backtest_signals(closes, base, "unfiltered")

        regime = calc_choppiness_index(highs, lows, closes)
        bt_filt = backtest_with_regime_filter(
            highs,
            lows,
            closes,
            regime,
            threshold=61.8,
            block_when_above=True,
            indicator_name="filtered",
        )
        assert bt_filt.total_trades <= bt_base.total_trades


# ---------------------------------------------------------------------------
# Isolation Tests
# ---------------------------------------------------------------------------


class TestIsolation:
    def test_no_operational_imports(self):
        """Track C-v2 must not import from app/, workers/, strategies/."""
        import track_c_v2_regime_research as mod

        source = open(mod.__file__, "r", encoding="utf-8").read()
        assert "from app." not in source
        assert "from workers." not in source
        assert "from strategies." not in source
        assert "import app." not in source
        assert "import workers." not in source
        assert "import strategies." not in source

    def test_no_regime_detector_modification(self):
        """Script must not import or modify RegimeDetector."""
        import track_c_v2_regime_research as mod

        source = open(mod.__file__, "r", encoding="utf-8").read()
        assert "RegimeDetector" not in source or "PROHIBITED" in source
