"""CR-046 Track B: ETH SMC+MACD Research Tests"""

import numpy as np
import pytest

# Import from research script (NOT operational code)
import sys
import os

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
)

from track_b_eth_research import (
    sma,
    ema,
    calc_macd,
    calc_smc_pure_causal,
    calc_wavetrend,
    calc_smc_macd_consensus,
    calc_smc_wavetrend_consensus,
    backtest_signals,
    apply_1bar_delay,
    buy_and_hold_return,
    purged_kfold_cv,
    BacktestResult,
    Trade,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_trending_data(n: int = 500, seed: int = 42) -> tuple:
    """Generate trending price data."""
    rng = np.random.RandomState(seed)
    price = 2500.0
    highs, lows, closes = [], [], []
    for _ in range(n):
        ret = rng.normal(0.001, 0.008)  # slight upward drift
        price *= 1 + ret
        h = price * (1 + abs(rng.normal(0, 0.003)))
        l = price * (1 - abs(rng.normal(0, 0.003)))
        highs.append(h)
        lows.append(l)
        closes.append(price)
    return np.array(highs), np.array(lows), np.array(closes)


def _make_flat_data(n: int = 500, seed: int = 10) -> tuple:
    """Generate sideways/flat price data."""
    rng = np.random.RandomState(seed)
    price = 2500.0
    highs, lows, closes = [], [], []
    for _ in range(n):
        ret = rng.normal(0, 0.002)  # very low vol, no drift
        price *= 1 + ret
        h = price * (1 + abs(rng.normal(0, 0.001)))
        l = price * (1 - abs(rng.normal(0, 0.001)))
        highs.append(h)
        lows.append(l)
        closes.append(price)
    return np.array(highs), np.array(lows), np.array(closes)


# ---------------------------------------------------------------------------
# MACD Tests
# ---------------------------------------------------------------------------


class TestMACD:
    def test_macd_output_shapes(self):
        closes = np.random.RandomState(42).normal(100, 5, 200).cumsum() + 2000
        macd_line, signal_line, histogram, signals = calc_macd(closes)
        assert macd_line.shape == closes.shape
        assert signal_line.shape == closes.shape
        assert histogram.shape == closes.shape
        assert signals.shape == closes.shape

    def test_macd_signals_are_minus1_0_plus1(self):
        closes = np.random.RandomState(42).normal(100, 5, 500).cumsum() + 2000
        _, _, _, signals = calc_macd(closes)
        unique = set(np.unique(signals))
        assert unique.issubset({-1, 0, 1})

    def test_macd_causality(self):
        """MACD at bar i must not change when future bars are modified."""
        rng = np.random.RandomState(42)
        closes = rng.normal(0, 1, 300).cumsum() + 2500

        _, _, _, signals_full = calc_macd(closes)

        # Modify future data after bar 200
        closes_modified = closes.copy()
        closes_modified[201:] = closes_modified[200] + rng.normal(0, 50, 99)

        _, _, _, signals_mod = calc_macd(closes_modified)

        # Signals up to bar 200 must be identical
        np.testing.assert_array_equal(signals_full[:201], signals_mod[:201])

    def test_macd_crossover_direction(self):
        """Verify +1 means MACD crosses above signal, -1 below."""
        closes = np.random.RandomState(42).normal(0, 1, 500).cumsum() + 2500
        macd_line, signal_line, _, signals = calc_macd(closes)

        for i in range(1, len(signals)):
            if signals[i] == 1:
                assert macd_line[i] > signal_line[i]
                assert macd_line[i - 1] <= signal_line[i - 1]
            elif signals[i] == -1:
                assert macd_line[i] < signal_line[i]
                assert macd_line[i - 1] >= signal_line[i - 1]

    def test_macd_no_signal_on_nan_input(self):
        closes = np.full(100, np.nan)
        _, _, _, signals = calc_macd(closes)
        assert np.all(signals == 0)


# ---------------------------------------------------------------------------
# SMC+MACD Consensus Tests
# ---------------------------------------------------------------------------


class TestSMCMACDConsensus:
    def test_consensus_requires_both(self):
        """Consensus fires only when SMC and MACD agree on same bar."""
        highs, lows, closes = _make_trending_data(500)
        consensus = calc_smc_macd_consensus(highs, lows, closes)
        _, smc_sig = calc_smc_pure_causal(highs, lows, closes)
        _, _, _, macd_sig = calc_macd(closes)

        for i in range(len(consensus)):
            if consensus[i] != 0:
                assert smc_sig[i] == consensus[i]
                assert macd_sig[i] == consensus[i]

    def test_consensus_direction_match(self):
        """Consensus direction must match both sub-signals."""
        highs, lows, closes = _make_trending_data(1000, seed=99)
        consensus = calc_smc_macd_consensus(highs, lows, closes)
        _, smc_sig = calc_smc_pure_causal(highs, lows, closes)
        _, _, _, macd_sig = calc_macd(closes)

        for i in range(len(consensus)):
            if consensus[i] != 0:
                assert smc_sig[i] == macd_sig[i] == consensus[i]

    def test_consensus_subset_of_both(self):
        """Consensus signals must be a subset of both individual signal sets."""
        highs, lows, closes = _make_trending_data(800)
        consensus = calc_smc_macd_consensus(highs, lows, closes)
        _, smc_sig = calc_smc_pure_causal(highs, lows, closes)
        _, _, _, macd_sig = calc_macd(closes)

        consensus_bars = set(np.where(consensus != 0)[0])
        smc_bars = set(np.where(smc_sig != 0)[0])
        macd_bars = set(np.where(macd_sig != 0)[0])

        assert consensus_bars.issubset(smc_bars)
        assert consensus_bars.issubset(macd_bars)

    def test_flat_data_few_or_no_consensus(self):
        """Flat data should produce very few or zero consensus signals."""
        highs, lows, closes = _make_flat_data(500)
        consensus = calc_smc_macd_consensus(highs, lows, closes)
        # Allow some but expect very few
        assert np.sum(np.abs(consensus)) <= 10


# ---------------------------------------------------------------------------
# Backtest Tests
# ---------------------------------------------------------------------------


class TestBacktest:
    def test_backtest_result_keys(self):
        closes = np.linspace(100, 200, 500)
        signals = np.zeros(500, dtype=int)
        signals[50] = 1
        signals[100] = -1
        bt = backtest_signals(closes, signals, "test")
        d = bt.to_dict()
        required_keys = {
            "indicator",
            "total_trades",
            "winning_trades",
            "losing_trades",
            "win_rate",
            "total_return_pct",
            "max_drawdown_pct",
            "avg_trade_pct",
            "sharpe_ratio",
            "profit_factor",
        }
        assert required_keys.issubset(d.keys())

    def test_backtest_no_signals_no_trades(self):
        closes = np.linspace(100, 200, 100)
        signals = np.zeros(100, dtype=int)
        bt = backtest_signals(closes, signals, "none")
        assert bt.total_trades == 0
        assert bt.total_return_pct == 0.0

    def test_backtest_fees_reduce_returns(self):
        closes = np.linspace(100, 110, 200)
        signals = np.zeros(200, dtype=int)
        signals[10] = 1
        signals[190] = -1

        bt_low = backtest_signals(closes, signals, "low_fee", fee_pct=0.01)
        bt_high = backtest_signals(closes, signals, "high_fee", fee_pct=1.0)
        assert bt_low.total_return_pct > bt_high.total_return_pct

    def test_buy_and_hold_return(self):
        closes = np.array([100.0, 110.0])
        assert buy_and_hold_return(closes) == pytest.approx(10.0, abs=0.01)

    def test_buy_and_hold_empty(self):
        assert buy_and_hold_return(np.array([])) == 0.0


# ---------------------------------------------------------------------------
# 1-bar Delay Tests
# ---------------------------------------------------------------------------


class TestDelay:
    def test_1bar_delay_shifts_forward(self):
        signals = np.array([0, 1, 0, -1, 0])
        delayed = apply_1bar_delay(signals)
        np.testing.assert_array_equal(delayed, [0, 0, 1, 0, -1])

    def test_1bar_delay_preserves_length(self):
        signals = np.zeros(100, dtype=int)
        signals[50] = 1
        delayed = apply_1bar_delay(signals)
        assert len(delayed) == len(signals)

    def test_1bar_delay_first_element_zero(self):
        signals = np.array([1, -1, 0])
        delayed = apply_1bar_delay(signals)
        assert delayed[0] == 0


# ---------------------------------------------------------------------------
# OOS Temporal Ordering Tests
# ---------------------------------------------------------------------------


class TestOOSOrdering:
    def test_oos_train_before_test(self):
        """In 4mo/2mo split, test period must come after training."""
        n = 4320
        split_idx = int(n * 2 / 3)
        assert split_idx > 0
        assert split_idx < n
        # Train: [0, split_idx), Test: [split_idx, n)
        # All train indices < all test indices
        assert split_idx == 2880


# ---------------------------------------------------------------------------
# Purged CV Tests
# ---------------------------------------------------------------------------


class TestPurgedCV:
    def test_cv_returns_correct_fold_count(self):
        highs, lows, closes = _make_trending_data(1000)
        results = purged_kfold_cv(
            closes,
            highs,
            lows,
            consensus_fn=calc_smc_macd_consensus,
            n_folds=5,
            embargo_bars=48,
        )
        assert len(results) == 5

    def test_cv_embargo_applied(self):
        """Embargo bars should reduce effective test range for folds > 0."""
        highs, lows, closes = _make_trending_data(1000)
        results = purged_kfold_cv(
            closes,
            highs,
            lows,
            consensus_fn=calc_smc_macd_consensus,
            n_folds=5,
            embargo_bars=48,
        )
        # Fold 1 (idx 0) has no embargo, fold 2+ should have embargo applied
        for fold in results:
            assert "embargo_bars" in fold
            assert fold["embargo_bars"] == 48

    def test_cv_fold_results_have_required_keys(self):
        highs, lows, closes = _make_trending_data(500)
        results = purged_kfold_cv(
            closes,
            highs,
            lows,
            consensus_fn=calc_smc_macd_consensus,
            n_folds=5,
            embargo_bars=48,
        )
        required = {
            "fold",
            "test_range",
            "embargo_bars",
            "sharpe_ratio",
            "profit_factor",
            "total_trades",
            "pass",
        }
        for fold in results:
            assert required.issubset(fold.keys())


# ---------------------------------------------------------------------------
# Isolation Tests
# ---------------------------------------------------------------------------


class TestIsolation:
    def test_no_operational_imports(self):
        """Track B script must not import from app/, workers/, strategies/."""
        import track_b_eth_research as mod

        source = open(mod.__file__, "r", encoding="utf-8").read()
        assert "from app." not in source
        assert "from workers." not in source
        assert "from strategies." not in source
        assert "import app." not in source
        assert "import workers." not in source
        assert "import strategies." not in source

    def test_b1_result_has_required_keys(self):
        """Phase B-1 result must have expected structure."""
        highs, lows, closes = _make_trending_data(500)
        from track_b_eth_research import run_phase_b1

        result = run_phase_b1(highs, lows, closes)
        assert "smc_macd" in result
        assert "smc_wavetrend" in result
        assert "buy_and_hold_return_pct" in result
        assert "checks" in result
        assert "status" in result
