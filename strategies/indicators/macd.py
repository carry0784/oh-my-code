"""MACD (Moving Average Convergence Divergence) indicator.

Standard MACD with configurable fast/slow/signal periods.
Pure computation — no I/O, no side effects.

Usage:
    macd_line, signal_line, histogram, signals = calc_macd(closes)
    # signals: +1 = bullish crossover, -1 = bearish crossover, 0 = no signal
"""

from __future__ import annotations

import numpy as np


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


def calc_macd(
    closes: np.ndarray,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Compute MACD line, signal line, histogram, and crossover signals.

    Args:
        closes: Array of close prices.
        fast_period: Fast EMA period (default 12).
        slow_period: Slow EMA period (default 26).
        signal_period: Signal line EMA period (default 9).

    Returns:
        Tuple of (macd_line, signal_line, histogram, signals).
        signals: +1 = bullish crossover (MACD crosses above signal),
                 -1 = bearish crossover (MACD crosses below signal),
                  0 = no signal.
    """
    n = len(closes)
    macd_line = np.full(n, np.nan)
    signal_line = np.full(n, np.nan)
    histogram = np.full(n, np.nan)
    signals = np.zeros(n, dtype=np.int32)

    if n < slow_period + signal_period:
        return macd_line, signal_line, histogram, signals

    # MACD line = Fast EMA - Slow EMA
    fast_ema = _ema(closes, fast_period)
    slow_ema = _ema(closes, slow_period)

    for i in range(slow_period - 1, n):
        if not np.isnan(fast_ema[i]) and not np.isnan(slow_ema[i]):
            macd_line[i] = fast_ema[i] - slow_ema[i]

    # Signal line = EMA of MACD line (only over valid MACD values)
    valid_start = slow_period - 1
    macd_valid = macd_line[valid_start:]
    signal_valid = _ema(macd_valid, signal_period)
    signal_line[valid_start:] = signal_valid

    # Histogram = MACD - Signal
    for i in range(n):
        if not np.isnan(macd_line[i]) and not np.isnan(signal_line[i]):
            histogram[i] = macd_line[i] - signal_line[i]

    # Crossover signals
    for i in range(1, n):
        if np.isnan(histogram[i]) or np.isnan(histogram[i - 1]):
            continue
        # Bullish: histogram crosses from negative to positive
        if histogram[i - 1] <= 0 and histogram[i] > 0:
            signals[i] = 1
        # Bearish: histogram crosses from positive to negative
        elif histogram[i - 1] >= 0 and histogram[i] < 0:
            signals[i] = -1

    return macd_line, signal_line, histogram, signals
