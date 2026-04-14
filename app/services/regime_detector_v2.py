"""RegimeDetectorV2 — Track C-v2 alternative regime classification.

Replaces ADX/BB/ATR (Track C v1 FAIL: non-discriminative in crypto 1H)
with Choppiness Index, Directional Efficiency Ratio, and Realized Volatility.

Design goals:
  - Better trending/ranging discrimination for crypto 1H timeframe
  - Composable with existing RegimeDetector as a parallel detector
  - Pure computation — no I/O, no side effects
  - Batch mode for historical replay

Integration:
  - Used by RegimeEvolutionManager as alternative/parallel regime source
  - Strategy catalog entries reference regime labels from this detector
  - Separate from V1 — no mutation of existing regime pipeline
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from app.core.logging import get_logger
from strategies.indicators.regime_v2 import (
    calc_choppiness_index,
    calc_directional_efficiency,
    calc_realized_volatility,
    classify_regime_v2,
)

logger = get_logger(__name__)

# Regime labels
TRENDING_UP = "trending_up"
TRENDING_DOWN = "trending_down"
RANGING = "ranging"
HIGH_VOLATILITY = "high_volatility"
CRISIS = "crisis"
UNKNOWN = "unknown"


@dataclass
class RegimeV2Result:
    """Single-bar regime classification result from V2 detector."""

    regime: str = UNKNOWN
    confidence: float = 0.0
    choppiness_index: float = 0.0
    directional_efficiency: float = 0.0
    realized_volatility: float = 0.0
    method: str = "regime_v2"


@dataclass
class RegimeV2Config:
    """Configuration for V2 regime detection thresholds."""

    ci_period: int = 14
    der_period: int = 14
    rv_period: int = 14
    ci_trending_threshold: float = 38.2
    ci_ranging_threshold: float = 61.8
    der_trending_threshold: float = 0.5
    der_ranging_threshold: float = 0.3
    rv_high_threshold: float = 0.8
    rv_crisis_threshold: float = 1.5
    direction_lookback: int = 5  # bars to determine trend direction


class RegimeDetectorV2:
    """V2 regime detector using Choppiness, Directional Efficiency, Realized Vol.

    Parallel to V1 RegimeDetector — does not replace it.
    Can be used standalone or as a comparison detector for validation.
    """

    def __init__(self, config: RegimeV2Config | None = None):
        self.config = config or RegimeV2Config()

    def detect(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
    ) -> RegimeV2Result:
        """Classify current regime from the latest bar.

        Requires enough history for all indicator periods.
        """
        min_bars = (
            max(
                self.config.ci_period,
                self.config.der_period,
                self.config.rv_period,
            )
            + 1
        )

        if len(closes) < min_bars:
            return RegimeV2Result()

        ci_arr = calc_choppiness_index(
            highs,
            lows,
            closes,
            period=self.config.ci_period,
        )
        der_arr = calc_directional_efficiency(
            closes,
            period=self.config.der_period,
        )
        rv_arr = calc_realized_volatility(
            closes,
            period=self.config.rv_period,
        )

        ci_val = ci_arr[-1] if not np.isnan(ci_arr[-1]) else 50.0
        der_val = der_arr[-1] if not np.isnan(der_arr[-1]) else 0.0
        rv_val = rv_arr[-1] if not np.isnan(rv_arr[-1]) else 0.0

        raw_regime, confidence = classify_regime_v2(
            choppiness=ci_val,
            directional_eff=der_val,
            realized_vol=rv_val,
            ci_trending_threshold=self.config.ci_trending_threshold,
            ci_ranging_threshold=self.config.ci_ranging_threshold,
            der_trending_threshold=self.config.der_trending_threshold,
            der_ranging_threshold=self.config.der_ranging_threshold,
            rv_high_threshold=self.config.rv_high_threshold,
            rv_crisis_threshold=self.config.rv_crisis_threshold,
        )

        # Resolve trending direction
        regime = self._resolve_direction(raw_regime, closes)

        return RegimeV2Result(
            regime=regime,
            confidence=confidence,
            choppiness_index=ci_val,
            directional_efficiency=der_val,
            realized_volatility=rv_val,
        )

    def detect_batch(
        self,
        ohlcv: list[list],
    ) -> list[RegimeV2Result]:
        """Classify regime for each bar in a historical OHLCV series.

        Returns list of RegimeV2Result, one per bar. Early bars
        with insufficient data get regime=UNKNOWN.
        """
        n = len(ohlcv)
        if n == 0:
            return []

        highs = np.array([bar[2] for bar in ohlcv], dtype=np.float64)
        lows = np.array([bar[3] for bar in ohlcv], dtype=np.float64)
        closes = np.array([bar[4] for bar in ohlcv], dtype=np.float64)

        ci_arr = calc_choppiness_index(
            highs,
            lows,
            closes,
            period=self.config.ci_period,
        )
        der_arr = calc_directional_efficiency(
            closes,
            period=self.config.der_period,
        )
        rv_arr = calc_realized_volatility(
            closes,
            period=self.config.rv_period,
        )

        results = []
        for i in range(n):
            ci_val = ci_arr[i]
            der_val = der_arr[i]
            rv_val = rv_arr[i]

            if np.isnan(ci_val) or np.isnan(der_val) or np.isnan(rv_val):
                results.append(RegimeV2Result())
                continue

            raw_regime, confidence = classify_regime_v2(
                choppiness=ci_val,
                directional_eff=der_val,
                realized_vol=rv_val,
                ci_trending_threshold=self.config.ci_trending_threshold,
                ci_ranging_threshold=self.config.ci_ranging_threshold,
                der_trending_threshold=self.config.der_trending_threshold,
                der_ranging_threshold=self.config.der_ranging_threshold,
                rv_high_threshold=self.config.rv_high_threshold,
                rv_crisis_threshold=self.config.rv_crisis_threshold,
            )

            # Resolve trending direction using local close comparison
            regime = self._resolve_direction_at(raw_regime, closes, i)

            results.append(
                RegimeV2Result(
                    regime=regime,
                    confidence=confidence,
                    choppiness_index=ci_val,
                    directional_efficiency=der_val,
                    realized_volatility=rv_val,
                )
            )

        return results

    def _resolve_direction(self, raw_regime: str, closes: np.ndarray) -> str:
        """Resolve 'trending' into 'trending_up' or 'trending_down'."""
        if raw_regime != "trending":
            return raw_regime
        return self._resolve_direction_at(raw_regime, closes, len(closes) - 1)

    def _resolve_direction_at(self, raw_regime: str, closes: np.ndarray, idx: int) -> str:
        """Resolve trending direction at a specific index."""
        if raw_regime != "trending":
            return raw_regime

        lookback = self.config.direction_lookback
        start = max(0, idx - lookback)
        if closes[idx] > closes[start]:
            return TRENDING_UP
        elif closes[idx] < closes[start]:
            return TRENDING_DOWN
        return RANGING  # flat = treat as ranging
