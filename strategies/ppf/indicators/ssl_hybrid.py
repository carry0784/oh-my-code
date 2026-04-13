"""SSL Hybrid indicator for PPF trend alignment (O6).

Computes ssl_trend_strength as a continuous score in [-1.0, +1.0].
+1.0 = strong bullish trend, -1.0 = strong bearish trend.

Based on Semaphore Signal Level (SSL) channel:
- SSL_up = SMA(highs, period)
- SSL_down = SMA(lows, period)
- Baseline = (SSL_up + SSL_down) / 2
- Trend direction: close > baseline = bullish, close < baseline = bearish
- Strength: normalized distance from baseline
"""

from __future__ import annotations

import numpy as np


def _sma(data: np.ndarray, period: int) -> np.ndarray:
    """Simple Moving Average."""
    n = len(data)
    out = np.full(n, np.nan)
    if n < period:
        return out
    cumsum = np.cumsum(data)
    cumsum[period:] = cumsum[period:] - cumsum[:-period]
    out[period - 1 :] = cumsum[period - 1 :] / period
    return out


def compute_ssl_hybrid(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    period: int = 10,
    atr_period: int = 14,
) -> np.ndarray:
    """Compute SSL Hybrid trend strength as continuous score.

    Args:
        highs: High prices array.
        lows: Low prices array.
        closes: Close prices array.
        period: SMA period for SSL channel.
        atr_period: ATR period for normalization.

    Returns:
        Array of ssl_trend_strength values in [-1.0, +1.0].
        NaN where insufficient data.
    """
    n = len(closes)
    result = np.full(n, np.nan)

    if n < max(period, atr_period):
        return result

    # SSL channel
    ssl_up = _sma(highs, period)
    ssl_down = _sma(lows, period)
    baseline = (ssl_up + ssl_down) / 2.0

    # ATR for normalization
    tr = np.maximum(
        highs[1:] - lows[1:],
        np.maximum(
            np.abs(highs[1:] - closes[:-1]),
            np.abs(lows[1:] - closes[:-1]),
        ),
    )
    tr = np.concatenate([[highs[0] - lows[0]], tr])
    atr = _sma(tr, atr_period)

    # Compute strength: distance from baseline normalized by ATR
    start = max(period, atr_period) - 1
    for i in range(start, n):
        if np.isnan(baseline[i]) or np.isnan(atr[i]) or atr[i] <= 0:
            continue

        distance = closes[i] - baseline[i]
        # Normalize: 1 ATR distance = ~0.5 strength
        raw_strength = distance / (2.0 * atr[i])
        # Clamp to [-1.0, +1.0]
        result[i] = max(-1.0, min(1.0, raw_strength))

    return result


def get_ssl_trend_strength(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    period: int = 10,
    atr_period: int = 14,
) -> float:
    """Get the latest SSL trend strength value.

    Returns:
        Float in [-1.0, +1.0]. Returns 0.0 if insufficient data (fail-closed:
        0.0 means I2 = 0 which blocks D4 entry).
    """
    strengths = compute_ssl_hybrid(highs, lows, closes, period, atr_period)
    if len(strengths) == 0 or np.isnan(strengths[-1]):
        return 0.0  # fail-closed: neutral = blocks QUALIFIED entry
    return float(strengths[-1])
