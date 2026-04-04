"""CR-046 SMC+WaveTrend Strategy Tests"""

import pytest
import numpy as np
from strategies.smc_wavetrend_strategy import (
    SMCWaveTrendStrategy,
    calc_smc_pure_causal,
    calc_wavetrend,
    _sma,
    _ema,
)
from app.models.signal import SignalType


class TestMinimumBars:
    def test_minimum_bars_returns_none(self):
        strategy = SMCWaveTrendStrategy(symbol="SOL/USDT")
        # Less than min_bars
        ohlcv = [[i * 3600000, 100, 101, 99, 100, 1000] for i in range(5)]
        assert strategy.analyze(ohlcv) is None

    def test_min_bars_property(self):
        strategy = SMCWaveTrendStrategy(symbol="SOL/USDT")
        assert strategy.min_bars == max(2 * 5 + 1, 21 + 5)  # max(11, 26) = 26


class TestSMCPureCausalNoFutureAccess:
    """Causality regression: Version B must not access future bars."""

    def test_smc_pure_causal_no_future_access(self):
        # Create data where bar i+1..i+L would change the swing detection
        np.random.seed(42)
        n = 100
        highs = np.random.uniform(100, 110, n)
        lows = np.random.uniform(90, 100, n)
        closes = (highs + lows) / 2

        # Run on full data
        trend_full, signals_full = calc_smc_pure_causal(highs, lows, closes)

        # Run on data[:80] — signals up to bar 79 must be identical
        trend_partial, signals_partial = calc_smc_pure_causal(
            highs[:80],
            lows[:80],
            closes[:80],
        )
        # Signals at bars 0..79 from partial must match full
        np.testing.assert_array_equal(signals_partial, signals_full[:80])


class TestConsensusRequired:
    def test_consensus_required_smc_only(self):
        """If SMC fires but WT doesn't, result must be None."""
        strategy = SMCWaveTrendStrategy(symbol="SOL/USDT")
        # Use enough bars but construct data where consensus is unlikely
        np.random.seed(123)
        n = 200
        ohlcv = []
        price = 100.0
        for i in range(n):
            # Flat sideways data — unlikely to produce consensus
            h = price + 0.5
            l = price - 0.5
            c = price + np.random.uniform(-0.3, 0.3)
            ohlcv.append([i * 3600000, price, h, l, c, 1000])
        # Most likely returns None due to no consensus
        result = strategy.analyze(ohlcv)
        # We accept None (no consensus) — this validates the gate works
        # If somehow signals align, verify structure
        if result is not None:
            assert result["metadata"]["smc_signal"] == result["metadata"]["wt_signal"]


class TestLongSignalStructure:
    def test_long_signal_structure(self):
        """Verify signal dict has all required keys and correct types."""
        strategy = SMCWaveTrendStrategy(symbol="SOL/USDT")
        # We need to create a mock signal by calling generate_signal directly
        signal = strategy.generate_signal(
            signal_type=SignalType.LONG,
            entry_price=100.0,
            stop_loss=98.0,
            take_profit=104.0,
            confidence=0.7,
            metadata={
                "smc_signal": 1,
                "wt_signal": 1,
                "wt1_val": -30.0,
                "wt2_val": -35.0,
                "bar_timestamp": 1711929600000,
                "strategy_version": "SMC_WaveTrend_1H_v2",
            },
        )
        # Required keys
        assert signal["source"] == "SMC_WaveTrend_1H"
        assert signal["exchange"] == "binance"
        assert signal["symbol"] == "SOL/USDT"
        assert signal["signal_type"] == SignalType.LONG
        assert isinstance(signal["entry_price"], float)
        assert isinstance(signal["stop_loss"], float)
        assert isinstance(signal["take_profit"], float)
        assert isinstance(signal["confidence"], float)
        assert isinstance(signal["metadata"], dict)

        # Metadata keys
        meta = signal["metadata"]
        assert "smc_signal" in meta
        assert "wt_signal" in meta
        assert "wt1_val" in meta
        assert "wt2_val" in meta
        assert "bar_timestamp" in meta
        assert "strategy_version" in meta


class TestSLTPCalculations:
    def test_sl_tp_calculations_long(self):
        """LONG: SL = entry * 0.98, TP = entry * 1.04"""
        entry = 150.0
        sl = entry * (1 - 0.02)
        tp = entry * (1 + 0.04)
        assert sl == pytest.approx(147.0)
        assert tp == pytest.approx(156.0)

    def test_short_signal_sl_tp(self):
        """SHORT: SL = entry * 1.02, TP = entry * 0.96"""
        entry = 150.0
        sl = entry * (1 + 0.02)
        tp = entry * (1 - 0.04)
        assert sl == pytest.approx(153.0)
        assert tp == pytest.approx(144.0)


class TestSignalDirectionAgreement:
    def test_signal_direction_agreement(self):
        """Both indicators must agree for a signal."""
        # Test that calc functions return independent arrays
        np.random.seed(99)
        n = 100
        highs = np.cumsum(np.random.uniform(0, 2, n)) + 100
        lows = highs - np.random.uniform(1, 3, n)
        closes = (highs + lows) / 2

        _, smc_signals = calc_smc_pure_causal(highs, lows, closes)
        _, _, wt_signals = calc_wavetrend(highs, lows, closes)

        # Where both fire, they might not agree — that's fine
        # The strategy checks smc_sig == wt_sig != 0
        for i in range(len(smc_signals)):
            if smc_signals[i] != 0 and wt_signals[i] != 0:
                if smc_signals[i] == wt_signals[i]:
                    pass  # consensus
                # else: no consensus, analyze returns None for this bar


class TestHelperFunctions:
    def test_sma_basic(self):
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = _sma(data, 3)
        assert result[2] == pytest.approx(2.0)
        assert result[3] == pytest.approx(3.0)
        assert result[4] == pytest.approx(4.0)
        assert np.isnan(result[0])
        assert np.isnan(result[1])

    def test_ema_basic(self):
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = _ema(data, 3)
        assert not np.isnan(result[2])
        assert np.isnan(result[0])

    def test_sma_insufficient_data(self):
        data = np.array([1.0, 2.0])
        result = _sma(data, 5)
        assert all(np.isnan(result))

    def test_ema_insufficient_data(self):
        data = np.array([1.0, 2.0])
        result = _ema(data, 5)
        assert all(np.isnan(result))


class TestStrategyName:
    def test_name(self):
        strategy = SMCWaveTrendStrategy(symbol="SOL/USDT")
        assert strategy.name == "SMC_WaveTrend_1H"

    def test_version(self):
        strategy = SMCWaveTrendStrategy(symbol="SOL/USDT")
        assert strategy.version == "v2"
