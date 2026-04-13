"""PPF Observation module (O1-O9 field computation).

Authority: PPF-IMPLEMENTATION-001-CORRECTION-R1
Missing data principle: fail-closed to most conservative path.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from strategies.ppf.constants import EPSILON_PCT
from strategies.ppf.indicators.ssl_hybrid import get_ssl_trend_strength
from strategies.ppf.indicators.volume_osc import get_volume_force_strength
from strategies.ppf.parameters import PPFParameters
from strategies.ppf.pattern_engine.matcher import EnsembleResult, find_similar_patterns


@dataclass(frozen=True)
class ObservationFields:
    """All 9 observation fields computed for a single candle.

    Frozen to prevent runtime mutation.
    """

    # O1: pattern similarity score [0.0, 1.0]
    pattern_similarity_score: float

    # O2: projection direction {-1, 0, +1}
    projection_direction: int

    # O3: projection consensus ratio [0.0, 1.0]
    projection_consensus_ratio: float

    # O4: expected adverse excursion before target (%)
    expected_adverse_excursion_before_target: float

    # O5: expected favorable excursion to target (%)
    expected_favorable_excursion_to_target: float

    # O6: SSL trend strength [-1.0, +1.0]
    ssl_trend_strength: float

    # O7: volume force strength [-1.0, +1.0]
    volume_force_strength: float

    # O8: recent swing distance (%)
    recent_swing_distance_pct: float

    # O9: regime novelty flag (True = PPF disabled, fail-closed)
    regime_novelty_flag: bool


def _compute_swing_distance(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    lookback: int = 20,
) -> float:
    """Compute distance from current price to recent swing high/low.

    Returns percentage distance. 0.0 if insufficient data.
    """
    if len(closes) < lookback or closes[-1] == 0:
        return 0.0

    recent_high = float(np.max(highs[-lookback:]))
    recent_low = float(np.min(lows[-lookback:]))
    current = closes[-1]

    dist_high = abs(recent_high - current) / current * 100.0
    dist_low = abs(current - recent_low) / current * 100.0

    return min(dist_high, dist_low)


def compute_observation(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    volumes: np.ndarray,
    params: PPFParameters,
    ssl_period: int = 10,
    ssl_atr_period: int = 14,
    vol_short_period: int = 5,
    vol_long_period: int = 10,
) -> ObservationFields:
    """Compute all 9 observation fields for the current candle.

    Args:
        highs: Full historical high prices.
        lows: Full historical low prices.
        closes: Full historical close prices.
        volumes: Full historical volumes.
        params: PPF parameters (frozen).
        ssl_period: SSL Hybrid SMA period.
        ssl_atr_period: SSL Hybrid ATR normalization period.
        vol_short_period: Volume Oscillator short EMA period.
        vol_long_period: Volume Oscillator long EMA period.

    Returns:
        ObservationFields with all 9 fields.
        Missing data -> fail-closed defaults.
    """
    # O1-O5, O9: Pattern matching engine
    ensemble: EnsembleResult = find_similar_patterns(
        closes=closes,
        correlation_length=params.correlation_length,
        projection_horizon=params.projection_horizon,
        k=params.k,
        novelty_threshold=params.novelty_threshold,
    )

    # O6: SSL Hybrid trend strength
    ssl_strength = get_ssl_trend_strength(
        highs, lows, closes, ssl_period, ssl_atr_period
    )

    # O7: Volume Oscillator force strength
    vol_strength = get_volume_force_strength(
        closes, volumes, vol_short_period, vol_long_period
    )

    # O8: Recent swing distance
    swing_dist = _compute_swing_distance(highs, lows, closes)

    return ObservationFields(
        pattern_similarity_score=ensemble.pattern_similarity_score,
        projection_direction=ensemble.projection_direction,
        projection_consensus_ratio=ensemble.projection_consensus_ratio,
        expected_adverse_excursion_before_target=(
            ensemble.expected_adverse_excursion_before_target
        ),
        expected_favorable_excursion_to_target=(
            ensemble.expected_favorable_excursion_to_target
        ),
        ssl_trend_strength=ssl_strength,
        volume_force_strength=vol_strength,
        recent_swing_distance_pct=swing_dist,
        regime_novelty_flag=ensemble.regime_novelty_flag,
    )
