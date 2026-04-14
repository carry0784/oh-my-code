"""Tests for Step 4 — Strategy Expansion.

Covers:
  - Strategy catalog integrity
  - MACD indicator correctness
  - SMC+MACD strategy contract
  - Regime V2 indicators
  - RegimeDetectorV2 batch detection
"""

import numpy as np
import pytest

# ── Catalog Tests ────────────────────────────────────────────────────────


class TestStrategyCatalog:
    def test_catalog_has_all_strategies(self):
        from strategies.catalog import STRATEGY_CATALOG

        assert "SMC_WaveTrend_1H" in STRATEGY_CATALOG
        assert "SMC_MACD_1H" in STRATEGY_CATALOG
        assert "RSI_14_70_30" in STRATEGY_CATALOG

    def test_operational_track_has_smc_wt(self):
        from strategies.catalog import Track, list_by_track

        operational = list_by_track(Track.OPERATIONAL)
        names = [e.name for e in operational]
        assert "SMC_WaveTrend_1H" in names

    def test_experimental_track_entries(self):
        from strategies.catalog import Track, list_by_track

        experimental = list_by_track(Track.EXPERIMENTAL)
        names = [e.name for e in experimental]
        assert "SMC_MACD_1H" in names
        assert "RSI_14_70_30" in names

    def test_regime_affinity_lookup(self):
        from strategies.catalog import list_by_regime

        trending = list_by_regime("trending_up")
        names = [e.name for e in trending]
        assert "SMC_WaveTrend_1H" in names
        assert "SMC_MACD_1H" in names

    def test_symbol_lookup_eth(self):
        from strategies.catalog import list_by_symbol

        eth = list_by_symbol("ETH/USDT")
        names = [e.name for e in eth]
        assert "SMC_MACD_1H" in names
        # RSI has no symbol restriction, so it should also appear
        assert "RSI_14_70_30" in names

    def test_catalog_entry_frozen(self):
        from strategies.catalog import get_entry

        entry = get_entry("SMC_WaveTrend_1H")
        assert entry is not None
        with pytest.raises(AttributeError):
            entry.name = "modified"


# ── MACD Indicator Tests ─────────────────────────────────────────────────


class TestMACDIndicator:
    def _make_closes(self, n=100, trend=0.01):
        """Generate synthetic close prices with slight uptrend."""
        np.random.seed(42)
        noise = np.random.randn(n) * 0.5
        base = 100.0 + np.arange(n) * trend + np.cumsum(noise)
        return base.astype(np.float64)

    def test_macd_output_shape(self):
        from strategies.indicators.macd import calc_macd

        closes = self._make_closes(100)
        macd, signal, hist, signals = calc_macd(closes)
        assert len(macd) == 100
        assert len(signal) == 100
        assert len(hist) == 100
        assert len(signals) == 100

    def test_macd_insufficient_data(self):
        from strategies.indicators.macd import calc_macd

        closes = np.array([100.0, 101.0, 102.0])
        macd, signal, hist, signals = calc_macd(closes)
        assert np.all(np.isnan(macd))
        assert np.all(signals == 0)

    def test_macd_produces_signals(self):
        from strategies.indicators.macd import calc_macd

        closes = self._make_closes(200)
        _, _, _, signals = calc_macd(closes)
        # Should produce at least some crossover signals
        assert np.any(signals != 0)

    def test_macd_signal_values(self):
        from strategies.indicators.macd import calc_macd

        closes = self._make_closes(200)
        _, _, _, signals = calc_macd(closes)
        unique = set(signals.tolist())
        assert unique.issubset({-1, 0, 1})


# ── SMC+MACD Strategy Tests ─────────────────────────────────────────────


class TestSMCMACDStrategy:
    def _make_ohlcv(self, n=100):
        np.random.seed(42)
        closes = 2000.0 + np.cumsum(np.random.randn(n) * 5)
        ohlcv = []
        for i in range(n):
            ts = 1700000000000 + i * 3600000
            c = closes[i]
            h = c + abs(np.random.randn()) * 3
            l = c - abs(np.random.randn()) * 3
            o = c + np.random.randn() * 2
            v = 1000 + np.random.rand() * 5000
            ohlcv.append([ts, o, h, l, c, v])
        return ohlcv

    def test_strategy_name(self):
        from strategies.smc_macd_strategy import SMCMACDStrategy

        s = SMCMACDStrategy()
        assert s.name == "SMC_MACD_1H"

    def test_strategy_min_bars(self):
        from strategies.smc_macd_strategy import SMCMACDStrategy

        s = SMCMACDStrategy()
        assert s.min_bars >= 36  # max(2*5+1, 26+9+1) = max(11, 36)

    def test_strategy_returns_none_on_insufficient_data(self):
        from strategies.smc_macd_strategy import SMCMACDStrategy

        s = SMCMACDStrategy()
        result = s.analyze([[0, 100, 101, 99, 100, 1000]] * 10)
        assert result is None

    def test_strategy_produces_diagnostic(self):
        from strategies.smc_macd_strategy import SMCMACDStrategy

        s = SMCMACDStrategy()
        ohlcv = self._make_ohlcv(100)
        s.analyze(ohlcv)
        diag = s.last_diagnostic()
        assert "smc_signal" in diag
        assert "macd_signal" in diag
        assert "consensus" in diag

    def test_strategy_analyze_contract(self):
        from strategies.smc_macd_strategy import SMCMACDStrategy

        s = SMCMACDStrategy()
        ohlcv = self._make_ohlcv(200)
        # Run through all bars, any signal should follow contract
        for i in range(s.min_bars, len(ohlcv)):
            result = s.analyze(ohlcv[: i + 1])
            if result is not None:
                assert "signal_type" in result
                assert "entry_price" in result
                assert "stop_loss" in result
                assert "take_profit" in result
                assert "confidence" in result
                assert result["metadata"]["track"] == "B"
                break


# ── Regime V2 Indicator Tests ────────────────────────────────────────────


class TestRegimeV2Indicators:
    def _make_trending_data(self, n=100):
        """Strong uptrend — low choppiness, high directional efficiency."""
        closes = 100.0 + np.arange(n) * 0.5
        highs = closes + 0.3
        lows = closes - 0.3
        return highs, lows, closes

    def _make_ranging_data(self, n=200):
        """Oscillating — high choppiness, low directional efficiency.

        Uses short-period oscillation with large amplitude and wide H-L spread
        to ensure choppiness stays high over 14-bar windows.
        """
        np.random.seed(99)
        # Short-period zigzag: up/down every 3-4 bars with noise
        closes = 100.0 + np.sin(np.linspace(0, 30 * np.pi, n)) * 8 + np.random.randn(n) * 2
        highs = closes + 3.0 + np.abs(np.random.randn(n)) * 1.5
        lows = closes - 3.0 - np.abs(np.random.randn(n)) * 1.5
        return highs, lows, closes

    def test_choppiness_trending(self):
        from strategies.indicators.regime_v2 import calc_choppiness_index

        h, l, c = self._make_trending_data()
        ci = calc_choppiness_index(h, l, c, period=14)
        valid = ci[~np.isnan(ci)]
        assert len(valid) > 0
        assert np.mean(valid) < 50  # trending should have lower CI

    def test_choppiness_ranging(self):
        from strategies.indicators.regime_v2 import calc_choppiness_index

        h, l, c = self._make_ranging_data()
        ci = calc_choppiness_index(h, l, c, period=14)
        valid = ci[~np.isnan(ci)]
        assert len(valid) > 0
        assert np.mean(valid) > 50  # ranging should have higher CI

    def test_directional_efficiency_trending(self):
        from strategies.indicators.regime_v2 import calc_directional_efficiency

        _, _, c = self._make_trending_data()
        der = calc_directional_efficiency(c, period=14)
        valid = der[~np.isnan(der)]
        assert len(valid) > 0
        assert np.mean(valid) > 0.5  # trending = high efficiency

    def test_directional_efficiency_ranging(self):
        from strategies.indicators.regime_v2 import calc_directional_efficiency

        _, _, c = self._make_ranging_data()
        der = calc_directional_efficiency(c, period=14)
        valid = der[~np.isnan(der)]
        assert len(valid) > 0
        assert np.mean(valid) < 0.5  # ranging = low efficiency

    def test_realized_volatility_positive(self):
        from strategies.indicators.regime_v2 import calc_realized_volatility

        _, _, c = self._make_trending_data()
        rv = calc_realized_volatility(c, period=14)
        valid = rv[~np.isnan(rv)]
        assert len(valid) > 0
        assert np.all(valid >= 0)

    def test_classify_regime_trending(self):
        from strategies.indicators.regime_v2 import classify_regime_v2

        regime, conf = classify_regime_v2(
            choppiness=30.0,
            directional_eff=0.7,
            realized_vol=0.3,
        )
        assert regime == "trending"
        assert conf >= 0.5

    def test_classify_regime_ranging(self):
        from strategies.indicators.regime_v2 import classify_regime_v2

        regime, conf = classify_regime_v2(
            choppiness=70.0,
            directional_eff=0.1,
            realized_vol=0.3,
        )
        assert regime == "ranging"
        assert conf >= 0.5

    def test_classify_regime_crisis(self):
        from strategies.indicators.regime_v2 import classify_regime_v2

        regime, conf = classify_regime_v2(
            choppiness=50.0,
            directional_eff=0.5,
            realized_vol=2.0,
        )
        assert regime == "crisis"


# ── RegimeDetectorV2 Tests ───────────────────────────────────────────────


class TestRegimeDetectorV2:
    def _make_ohlcv(self, n=100, trend=0.5):
        closes = 100.0 + np.arange(n) * trend
        ohlcv = []
        for i in range(n):
            c = closes[i]
            ohlcv.append([i * 3600000, c - 0.1, c + 0.3, c - 0.3, c, 1000.0])
        return ohlcv

    def test_detect_returns_result(self):
        from app.services.regime_detector_v2 import RegimeDetectorV2

        detector = RegimeDetectorV2()
        ohlcv = self._make_ohlcv(50)
        h = np.array([b[2] for b in ohlcv])
        l = np.array([b[3] for b in ohlcv])
        c = np.array([b[4] for b in ohlcv])
        result = detector.detect(h, l, c)
        assert result.method == "regime_v2"
        assert result.regime in (
            "trending_up",
            "trending_down",
            "ranging",
            "high_volatility",
            "crisis",
            "unknown",
        )

    def test_detect_batch_length(self):
        from app.services.regime_detector_v2 import RegimeDetectorV2

        detector = RegimeDetectorV2()
        ohlcv = self._make_ohlcv(50)
        results = detector.detect_batch(ohlcv)
        assert len(results) == 50

    def test_trending_data_classified_as_trending(self):
        from app.services.regime_detector_v2 import RegimeDetectorV2

        detector = RegimeDetectorV2()
        ohlcv = self._make_ohlcv(100, trend=1.0)  # strong uptrend
        results = detector.detect_batch(ohlcv)
        # Check later bars (after warmup)
        later_results = results[30:]
        trending_count = sum(
            1 for r in later_results if r.regime in ("trending_up", "trending_down")
        )
        total_valid = sum(1 for r in later_results if r.regime != "unknown")
        if total_valid > 0:
            assert trending_count / total_valid > 0.3  # at least 30% trending
