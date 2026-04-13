"""PPF Interpretation module (I1-I5 score calculation).

Authority: PPF-IMPLEMENTATION-001-CORRECTION-R1

Score Role Separation:
    I1 projection_bias_score:      direction + strength (sign = bullish/bearish)
    I2 trend_alignment_score:      alignment strength (positive = aligned)
    I3 volume_confirmation_score:  alignment strength (positive = aligned)
    I4 path_quality_score:         path quality (higher = better)
    I5 structure_rr_score:         structural R:R (higher = better)

Key: I2/I3 are alignment-strength scores, NOT direction scores.
     In a bearish scenario with proper alignment, I2 > 0 and I3 > 0.
     sign(I1) == sign(I2) == sign(I3) is NOT required (removed in R2).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from strategies.ppf.constants import EPSILON_PCT
from strategies.ppf.observation import ObservationFields


@dataclass(frozen=True)
class InterpretationScores:
    """All 5 interpretation scores computed for a single candle.

    Frozen to prevent runtime mutation.
    """

    # I1: direction + strength [-1.0, +1.0]
    projection_bias_score: float

    # I2: trend alignment strength [-1.0, +1.0]
    #     positive = aligned (regardless of direction)
    trend_alignment_score: float

    # I3: volume alignment strength [-1.0, +1.0]
    #     positive = aligned (regardless of direction)
    volume_confirmation_score: float

    # I4: path quality (-inf, 1.0]
    #     fail-closed: -1.0 when O5 <= epsilon
    path_quality_score: float

    # I5: structural R:R [0, inf)
    structure_rr_score: float


def compute_scores(obs: ObservationFields) -> InterpretationScores:
    """Compute all 5 interpretation scores from observation fields.

    Args:
        obs: ObservationFields for the current candle.

    Returns:
        InterpretationScores with I1-I5.

    Formulas (from design spec):
        I1 = O2 * O3 * O1
        I2 = sign(O2) * O6
        I3 = sign(O2) * O7
        I4 = (O5 - O4) / max(O5, eps)  [fail-closed if O5 <= eps]
        I5 = O5 / max(O4, eps)
    """
    # I1: projection_bias_score = direction * consensus * similarity
    i1 = (
        obs.projection_direction
        * obs.projection_consensus_ratio
        * obs.pattern_similarity_score
    )

    # I2: trend_alignment_score = sign(projection_direction) * ssl_strength
    # When O2=0, sign=0, so I2=0 (blocks D4 entry - correct fail-closed)
    if obs.projection_direction > 0:
        sign_dir = 1.0
    elif obs.projection_direction < 0:
        sign_dir = -1.0
    else:
        sign_dir = 0.0

    i2 = sign_dir * obs.ssl_trend_strength
    i3 = sign_dir * obs.volume_force_strength

    # I4: path_quality_score
    # fail-closed: if O5 <= epsilon, I4 = -1.0 (auto REJECT)
    o5 = obs.expected_favorable_excursion_to_target
    o4 = obs.expected_adverse_excursion_before_target

    if o5 <= EPSILON_PCT:
        i4 = -1.0  # fail-closed: no favorable excursion measurable
    else:
        i4 = (o5 - o4) / o5

    # I5: structure_rr_score
    i5 = o5 / max(o4, EPSILON_PCT)

    return InterpretationScores(
        projection_bias_score=i1,
        trend_alignment_score=i2,
        volume_confirmation_score=i3,
        path_quality_score=i4,
        structure_rr_score=i5,
    )
