# SMC Version B (pure-causal): cr046_smc_pure_causal_design.md
# Canonical core: SMC (pure-causal, Version B) + WaveTrend, 1H timeframe
# 2/2 consensus required for signal generation

from __future__ import annotations

from typing import Any

import numpy as np

from app.models.signal import SignalType
from strategies.base import BaseStrategy


# ---------------------------------------------------------------------------
# Helper functions (ported from scripts/indicator_backtest.py, NOT imported)
# ---------------------------------------------------------------------------


def _sma(data: np.ndarray, period: int) -> np.ndarray:
    """Simple Moving Average."""
    out = np.full(len(data), np.nan)
    if len(data) < period:
        return out
    cumsum = np.cumsum(data)
    cumsum[period:] = cumsum[period:] - cumsum[:-period]
    out[period - 1 :] = cumsum[period - 1 :] / period
    return out


def _ema(data: np.ndarray, period: int) -> np.ndarray:
    """Exponential Moving Average."""
    out = np.full(len(data), np.nan)
    if len(data) < period:
        return out
    k = 2.0 / (period + 1)
    out[period - 1] = np.mean(data[:period])
    for i in range(period, len(data)):
        out[i] = data[i] * k + out[i - 1] * (1 - k)
    return out


# ---------------------------------------------------------------------------
# Indicator implementations (ported from scripts/indicator_backtest.py)
# ---------------------------------------------------------------------------


def calc_wavetrend(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    n1: int = 10,
    n2: int = 21,
    ob1: float = 60,
    os1: float = -60,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Returns (wt1, wt2, signals)."""
    n = len(closes)
    ap = (highs + lows + closes) / 3  # hlc3

    esa_vals = _ema(ap, n1)

    d_vals = np.full(n, np.nan)
    for i in range(n):
        if not np.isnan(esa_vals[i]):
            d_vals[i] = abs(ap[i] - esa_vals[i])
    d_ema = _ema(np.nan_to_num(d_vals), n1)

    ci = np.full(n, np.nan)
    for i in range(n):
        if not np.isnan(esa_vals[i]) and not np.isnan(d_ema[i]) and d_ema[i] != 0:
            ci[i] = (ap[i] - esa_vals[i]) / (0.015 * d_ema[i])

    wt1 = _ema(np.nan_to_num(ci), n2)
    wt2 = _sma(np.nan_to_num(wt1), 4)

    signals = np.zeros(n, dtype=int)
    for i in range(1, n):
        if not np.isnan(wt1[i]) and not np.isnan(wt2[i]):
            if wt1[i] > wt2[i] and wt1[i - 1] <= wt2[i - 1] and wt1[i] < os1:
                signals[i] = 1
            elif wt1[i] < wt2[i] and wt1[i - 1] >= wt2[i - 1] and wt1[i] > ob1:
                signals[i] = -1
            elif wt1[i] > wt2[i] and wt1[i - 1] <= wt2[i - 1]:
                signals[i] = 1
            elif wt1[i] < wt2[i] and wt1[i - 1] >= wt2[i - 1]:
                signals[i] = -1

    return wt1, wt2, signals


def calc_smc_pure_causal(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    swing_length: int = 50,
    internal_length: int = 5,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Pure-causal Smart Money Concepts (Version B).
    Swing detection uses ONLY past/current data -- no future bars.

    At bar i, checks if bar (i - internal_length) was a swing high/low
    by examining the window [i - 2*L .. i] (all past/current).

    Returns (smc_trend, signals).
    """
    n = len(closes)
    L = internal_length
    trend = np.zeros(n, dtype=int)
    signals = np.zeros(n, dtype=int)

    last_swing_high = np.nan
    last_swing_low = np.nan
    current_trend = 0

    for i in range(2 * L, n):
        candidate_idx = i - L
        window_start = max(0, candidate_idx - L)
        window_end = i + 1  # up to current bar (inclusive)

        window_h = highs[window_start:window_end]
        if highs[candidate_idx] == np.max(window_h):
            last_swing_high = highs[candidate_idx]

        window_l = lows[window_start:window_end]
        if lows[candidate_idx] == np.min(window_l):
            last_swing_low = lows[candidate_idx]

        if not np.isnan(last_swing_high) and closes[i] > last_swing_high:
            if current_trend == -1:
                signals[i] = 1  # CHoCH (bullish)
            elif current_trend == 1:
                signals[i] = 1  # BOS (bullish continuation)
            current_trend = 1
            last_swing_high = np.nan

        if not np.isnan(last_swing_low) and closes[i] < last_swing_low:
            if current_trend == 1:
                signals[i] = -1  # CHoCH (bearish)
            elif current_trend == -1:
                signals[i] = -1  # BOS (bearish continuation)
            current_trend = -1
            last_swing_low = np.nan

        trend[i] = current_trend

    return trend, signals


# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------

# Default parameters
DEFAULT_INTERNAL_LENGTH = 5
DEFAULT_N1 = 10
DEFAULT_N2 = 21
SL_PCT = 0.02  # 2% stop-loss
TP_PCT = 0.04  # 4% take-profit


class SMCWaveTrendStrategy(BaseStrategy):
    """
    Canonical core strategy: SMC (pure-causal, Version B) + WaveTrend.
    Requires 2/2 consensus (both indicators must agree on direction in the same bar).
    """

    def __init__(
        self,
        symbol: str,
        exchange: str = "binance",
        internal_length: int = DEFAULT_INTERNAL_LENGTH,
        n1: int = DEFAULT_N1,
        n2: int = DEFAULT_N2,
    ):
        super().__init__(symbol, exchange)
        self.internal_length = internal_length
        self.n1 = n1
        self.n2 = n2

    @property
    def name(self) -> str:
        return "SMC_WaveTrend_1H"

    @property
    def version(self) -> str:
        return "v2"

    @property
    def min_bars(self) -> int:
        return max(2 * self.internal_length + 1, self.n2 + 5)

    # -----------------------------------------------------------------
    # Diagnostic helpers (C1-A)
    # -----------------------------------------------------------------

    @staticmethod
    def _compute_near_miss_type(smc_sig: int, wt_sig: int) -> str | None:
        """Canonical near-miss classification. Inputs: raw signal ints only."""
        if smc_sig != 0 and wt_sig == 0:
            return "SMC_ONLY"
        if smc_sig == 0 and wt_sig != 0:
            return "WT_ONLY"
        if smc_sig != 0 and wt_sig != 0 and smc_sig != wt_sig:
            return "DIR_MISMATCH"
        return None

    @staticmethod
    def _compute_skip_reason_codes(smc_sig: int, wt_sig: int) -> list[str]:
        codes: list[str] = []
        if smc_sig == 0:
            codes.append("SMC_ZERO")
        if wt_sig == 0:
            codes.append("WT_ZERO")
        if smc_sig != 0 and wt_sig != 0 and smc_sig != wt_sig:
            codes.append("DIRECTION_MISMATCH")
        return codes

    def _build_diag(
        self,
        smc_sig: int,
        wt_sig: int,
        smc_trend: int,
        wt1_val: float | None,
        wt2_val: float | None,
        close_price: float,
    ) -> dict:
        wt_cross_dist = (
            abs(wt1_val - wt2_val)
            if wt1_val is not None and wt2_val is not None
            else None
        )
        return {
            "smc_sig_raw": smc_sig,
            "smc_trend_raw": smc_trend,
            "close_price": float(close_price),
            "wt_sig_raw": wt_sig,
            "wt1_val": wt1_val,
            "wt2_val": wt2_val,
            "wt_cross_distance": wt_cross_dist,
            "skip_reason_codes": self._compute_skip_reason_codes(smc_sig, wt_sig),
            "near_miss_type": self._compute_near_miss_type(smc_sig, wt_sig),
            "diagnostic_only": True,
            "diagnostic_version": 1,
            "diagnostic_populated": True,
        }

    # -----------------------------------------------------------------
    # Core analysis
    # -----------------------------------------------------------------

    def analyze(self, ohlcv: list[list], **kwargs) -> dict[str, Any] | None:
        """
        Analyze OHLCV data for 2/2 consensus signal.

        Args:
            ohlcv: List of [timestamp, open, high, low, close, volume]

        Returns:
            Signal dict or None if no signal / insufficient data.
        """
        # Lifecycle: clear previous diagnostic on entry
        self._diag = {}

        if len(ohlcv) < self.min_bars:
            self._diag = {"diagnostic_populated": False}
            return None

        try:
            timestamps = np.array([bar[0] for bar in ohlcv])
            highs = np.array([bar[2] for bar in ohlcv], dtype=float)
            lows = np.array([bar[3] for bar in ohlcv], dtype=float)
            closes = np.array([bar[4] for bar in ohlcv], dtype=float)

            # Compute indicators
            smc_trend_arr, smc_signals = calc_smc_pure_causal(
                highs,
                lows,
                closes,
                internal_length=self.internal_length,
            )
            wt1, wt2, wt_signals = calc_wavetrend(
                highs,
                lows,
                closes,
                n1=self.n1,
                n2=self.n2,
            )

            # Check last bar for consensus
            last_idx = len(ohlcv) - 1
            smc_sig = int(smc_signals[last_idx])
            wt_sig = int(wt_signals[last_idx])
            smc_trend_val = int(smc_trend_arr[last_idx])
            wt1_val = float(wt1[last_idx]) if not np.isnan(wt1[last_idx]) else None
            wt2_val = float(wt2[last_idx]) if not np.isnan(wt2[last_idx]) else None

            # Cache diagnostic (always, regardless of consensus)
            self._diag = self._build_diag(
                smc_sig, wt_sig, smc_trend_val, wt1_val, wt2_val, closes[last_idx]
            )

            # 2/2 consensus: both must agree on direction
            if smc_sig == 0 or wt_sig == 0 or smc_sig != wt_sig:
                return None

            entry_price = closes[last_idx]
            bar_ts = int(timestamps[last_idx])

            if smc_sig == 1:
                # LONG
                signal_type = SignalType.LONG
                stop_loss = entry_price * (1 - SL_PCT)
                take_profit = entry_price * (1 + TP_PCT)
            else:
                # SHORT
                signal_type = SignalType.SHORT
                stop_loss = entry_price * (1 + SL_PCT)
                take_profit = entry_price * (1 - TP_PCT)

            return self.generate_signal(
                signal_type=signal_type,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=0.7,
                metadata={
                    "smc_signal": smc_sig,
                    "wt_signal": wt_sig,
                    "wt1_val": wt1_val,
                    "wt2_val": wt2_val,
                    "bar_timestamp": bar_ts,
                    "strategy_version": f"{self.name}_{self.version}",
                },
            )
        except Exception:
            # Lifecycle: exception → diagnostic_populated=false
            self._diag = {"diagnostic_populated": False}
            raise
