"""Volume Oscillator for PPF volume confirmation (O7).

Computes volume_force_strength as a continuous score in [-1.0, +1.0].
+1.0 = strong buying participation, -1.0 = strong selling participation.

Based on Volume Oscillator:
- Short EMA of volume - Long EMA of volume
- Direction determined by price-volume relationship:
  positive oscillator + up candle = buying, negative + down candle = selling
- Normalized to [-1.0, +1.0]
"""

from __future__ import annotations

import numpy as np


def _ema(data: np.ndarray, period: int) -> np.ndarray:
    """Exponential Moving Average."""
    n = len(data)
    out = np.full(n, np.nan)
    if n < period:
        return out
    k = 2.0 / (period + 1)
    out[period - 1] = np.mean(data[:period])
    for i in range(period, n):
        out[i] = data[i] * k + out[i - 1] * (1 - k)
    return out


def compute_volume_oscillator(
    closes: np.ndarray,
    volumes: np.ndarray,
    short_period: int = 5,
    long_period: int = 10,
) -> np.ndarray:
    """Compute volume force strength as continuous score.

    Args:
        closes: Close prices array.
        volumes: Volume array.
        short_period: Short EMA period for volume oscillator.
        long_period: Long EMA period for volume oscillator.

    Returns:
        Array of volume_force_strength values in [-1.0, +1.0].
        NaN where insufficient data.
    """
    n = len(closes)
    result = np.full(n, np.nan)

    if n < long_period + 1:
        return result

    # Volume oscillator: short EMA - long EMA of volume
    vol_short = _ema(volumes, short_period)
    vol_long = _ema(volumes, long_period)

    start = long_period - 1
    for i in range(start, n):
        if np.isnan(vol_short[i]) or np.isnan(vol_long[i]) or vol_long[i] <= 0:
            continue

        # Oscillator as percentage
        osc_pct = (vol_short[i] - vol_long[i]) / vol_long[i]

        # Direction: use price change to determine buying/selling
        if i > 0:
            price_direction = 1.0 if closes[i] >= closes[i - 1] else -1.0
        else:
            price_direction = 0.0

        # Force = direction * oscillator magnitude
        # Normalize: 50% oscillator deviation = ~0.5 strength
        raw_force = price_direction * abs(osc_pct) / 1.0
        # Clamp to [-1.0, +1.0]
        result[i] = max(-1.0, min(1.0, raw_force))

    return result


def get_volume_force_strength(
    closes: np.ndarray,
    volumes: np.ndarray,
    short_period: int = 5,
    long_period: int = 10,
) -> float:
    """Get the latest volume force strength value.

    Returns:
        Float in [-1.0, +1.0]. Returns 0.0 if insufficient data (fail-closed:
        0.0 means I3 = 0 which blocks D4 entry).
    """
    strengths = compute_volume_oscillator(closes, volumes, short_period, long_period)
    if len(strengths) == 0 or np.isnan(strengths[-1]):
        return 0.0  # fail-closed: neutral = blocks QUALIFIED entry
    return float(strengths[-1])
