"""Regime V2 Indicators — alternative regime classification metrics.

Track C-v2: Replaces ADX/BB/ATR (failed in Track C v1 as non-discriminative
in crypto 1H). These indicators measure trending vs. ranging from different
angles:

  1. Choppiness Index (Dreiss): 0-100, high=choppy/ranging, low=trending
  2. Directional Efficiency Ratio: net/gross movement, 0=ranging, 1=trending
  3. Realized Volatility: annualized std of log returns

Pure computation — no I/O, no side effects.
"""

from __future__ import annotations

import numpy as np


def calc_choppiness_index(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    period: int = 14,
) -> np.ndarray:
    """Choppiness Index (Dreiss).

    CI = 100 * LOG10(SUM(ATR, period) / (highest_high - lowest_low)) / LOG10(period)

    Interpretation:
      - CI > 61.8: Market is choppy/ranging (Fibonacci level)
      - CI < 38.2: Market is trending (Fibonacci level)
      - Mid range: transitional

    Args:
        highs: Array of high prices.
        lows: Array of low prices.
        closes: Array of close prices.
        period: Lookback period (default 14).

    Returns:
        Array of choppiness index values (0-100). NaN where insufficient data.
    """
    n = len(closes)
    ci = np.full(n, np.nan)

    if n < period + 1:
        return ci

    # True Range
    tr = np.full(n, np.nan)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )

    log_period = np.log10(period)

    for i in range(period, n):
        atr_sum = np.sum(tr[i - period + 1 : i + 1])
        highest = np.max(highs[i - period + 1 : i + 1])
        lowest = np.min(lows[i - period + 1 : i + 1])

        price_range = highest - lowest
        if price_range <= 0 or atr_sum <= 0:
            ci[i] = 50.0  # neutral if flat
            continue

        ci[i] = 100.0 * np.log10(atr_sum / price_range) / log_period

    return ci


def calc_directional_efficiency(
    closes: np.ndarray,
    period: int = 14,
) -> np.ndarray:
    """Directional Efficiency Ratio (Kaufman-style).

    DER = |net_change| / sum(|bar_changes|)

    Interpretation:
      - DER near 1.0: Strong directional move (trending)
      - DER near 0.0: No net progress despite movement (ranging)
      - DER > 0.5: Generally trending
      - DER < 0.3: Generally ranging

    Args:
        closes: Array of close prices.
        period: Lookback period (default 14).

    Returns:
        Array of directional efficiency values (0.0-1.0). NaN where insufficient.
    """
    n = len(closes)
    der = np.full(n, np.nan)

    if n < period + 1:
        return der

    for i in range(period, n):
        net_change = abs(closes[i] - closes[i - period])
        gross_change = np.sum(np.abs(np.diff(closes[i - period : i + 1])))

        if gross_change <= 0:
            der[i] = 0.0
        else:
            der[i] = net_change / gross_change

    return der


def calc_realized_volatility(
    closes: np.ndarray,
    period: int = 14,
    annualize_factor: float = 365.25 * 24,  # hourly bars → annualized
) -> np.ndarray:
    """Realized Volatility (annualized standard deviation of log returns).

    Interpretation:
      - High RV: Large price swings, could be trending or volatile ranging
      - Low RV: Quiet market, consolidation
      - Useful as a filter complement to CI and DER

    Args:
        closes: Array of close prices.
        period: Lookback period for rolling std (default 14).
        annualize_factor: Bars per year for annualization (default 8766 for 1H).

    Returns:
        Array of annualized realized volatility. NaN where insufficient data.
    """
    n = len(closes)
    rv = np.full(n, np.nan)

    if n < period + 1:
        return rv

    # Log returns
    log_returns = np.full(n, np.nan)
    for i in range(1, n):
        if closes[i - 1] > 0 and closes[i] > 0:
            log_returns[i] = np.log(closes[i] / closes[i - 1])

    sqrt_factor = np.sqrt(annualize_factor)

    for i in range(period, n):
        window = log_returns[i - period + 1 : i + 1]
        valid = window[~np.isnan(window)]
        if len(valid) >= period // 2:
            rv[i] = np.std(valid, ddof=1) * sqrt_factor
        else:
            rv[i] = np.nan

    return rv


def classify_regime_v2(
    choppiness: float,
    directional_eff: float,
    realized_vol: float,
    ci_trending_threshold: float = 38.2,
    ci_ranging_threshold: float = 61.8,
    der_trending_threshold: float = 0.5,
    der_ranging_threshold: float = 0.3,
    rv_high_threshold: float = 0.8,
    rv_crisis_threshold: float = 1.5,
) -> tuple[str, float]:
    """Classify regime from V2 indicator values.

    Returns (regime_label, confidence).

    Regime labels: trending_up, trending_down, ranging, high_volatility, crisis.
    Note: trending direction requires external close comparison.
    This function returns "trending" without direction — caller must resolve.
    """
    if np.isnan(choppiness) or np.isnan(directional_eff) or np.isnan(realized_vol):
        return "unknown", 0.0

    # Crisis override
    if realized_vol > rv_crisis_threshold:
        return "crisis", 0.9

    # High volatility override
    if realized_vol > rv_high_threshold and choppiness > ci_ranging_threshold:
        return "high_volatility", 0.8

    # Trending: low choppiness + high directional efficiency
    if choppiness < ci_trending_threshold and directional_eff > der_trending_threshold:
        confidence = min(
            (ci_trending_threshold - choppiness) / ci_trending_threshold,
            directional_eff,
        )
        return "trending", max(0.6, confidence)

    # Ranging: high choppiness + low directional efficiency
    if choppiness > ci_ranging_threshold and directional_eff < der_ranging_threshold:
        confidence = min(
            (choppiness - ci_ranging_threshold) / (100 - ci_ranging_threshold),
            1 - directional_eff,
        )
        return "ranging", max(0.6, confidence)

    # Transitional: mixed signals
    # Lean toward trending if DER is above threshold
    if directional_eff > der_trending_threshold:
        return "trending", 0.5

    # Lean toward ranging if CI is above threshold
    if choppiness > ci_ranging_threshold:
        return "ranging", 0.5

    return "unknown", 0.3
