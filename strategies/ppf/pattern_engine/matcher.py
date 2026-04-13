"""Pattern matching engine for PPF (O1-O5, O9).

Finds the top-K most similar historical patterns to the current N-bar window
and computes ensemble statistics (majority direction, path projections).

Constitution:
- C6: K >= 2 (single pattern decision prohibited)
- C8: Output is "hypothesis", not "confirmed prediction"
- C10: No runtime parameter adaptation
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np


@dataclass(frozen=True)
class PatternMatch:
    """A single matched historical pattern."""

    start_index: int
    end_index: int
    similarity: float  # [0.0, 1.0]
    projected_direction: int  # -1, 0, +1
    adverse_excursion_pct: float  # % adverse before target
    favorable_excursion_pct: float  # % favorable to target


@dataclass(frozen=True)
class EnsembleResult:
    """Ensemble statistics from top-K matched patterns.

    O1: pattern_similarity_score (mean similarity of top-K)
    O2: projection_direction (+1, 0, -1 by majority vote)
    O3: projection_consensus_ratio (fraction voting for majority)
    O4: expected_adverse_excursion_before_target (median)
    O5: expected_favorable_excursion_to_target (median)
    O9: regime_novelty_flag (True if mean similarity < threshold)
    """

    pattern_similarity_score: float
    projection_direction: int
    projection_consensus_ratio: float
    expected_adverse_excursion_before_target: float
    expected_favorable_excursion_to_target: float
    regime_novelty_flag: bool
    matches: tuple[PatternMatch, ...]


# Minimum overlap guard: pattern window must not overlap with current window
_MIN_GAP_BARS: Final[int] = 1


def _normalize_window(window: np.ndarray) -> np.ndarray:
    """Normalize a price window to percentage returns from first bar.

    This makes pattern comparison scale-invariant.
    """
    if len(window) == 0 or window[0] == 0:
        return np.zeros_like(window)
    return (window - window[0]) / window[0] * 100.0


def _pearson_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Pearson correlation coefficient mapped to [0, 1] similarity.

    correlation in [-1, 1] -> similarity = (correlation + 1) / 2
    Perfect correlation = 1.0, anti-correlation = 0.0, no correlation = 0.5
    """
    if len(a) != len(b) or len(a) < 2:
        return 0.0

    std_a = np.std(a)
    std_b = np.std(b)
    if std_a < 1e-10 or std_b < 1e-10:
        return 0.5  # constant series -> no meaningful correlation

    corr = np.corrcoef(a, b)[0, 1]
    if np.isnan(corr):
        return 0.0
    return float((corr + 1.0) / 2.0)


def _compute_excursions(
    closes: np.ndarray,
    entry_index: int,
    horizon: int,
    direction: int,
) -> tuple[float, float]:
    """Compute adverse and favorable excursions for a projection window.

    Args:
        closes: Full close price array.
        entry_index: Index of the entry point (end of pattern).
        horizon: Number of bars to look ahead.
        direction: +1 for long, -1 for short.

    Returns:
        (adverse_excursion_pct, favorable_excursion_pct)
        Both as positive percentages.
    """
    end = min(entry_index + horizon, len(closes))
    if end <= entry_index or closes[entry_index] == 0:
        return 0.0, 0.0

    entry_price = closes[entry_index]
    future_returns = (closes[entry_index + 1 : end] - entry_price) / entry_price * 100.0

    if len(future_returns) == 0:
        return 0.0, 0.0

    if direction == 1:  # long
        adverse = abs(min(0.0, float(np.min(future_returns))))
        favorable = max(0.0, float(np.max(future_returns)))
    elif direction == -1:  # short
        adverse = max(0.0, float(np.max(future_returns)))
        favorable = abs(min(0.0, float(np.min(future_returns))))
    else:
        adverse = 0.0
        favorable = 0.0

    return adverse, favorable


def find_similar_patterns(
    closes: np.ndarray,
    correlation_length: int,
    projection_horizon: int,
    k: int,
    novelty_threshold: float,
) -> EnsembleResult:
    """Find top-K similar historical patterns and compute ensemble result.

    Args:
        closes: Full historical close prices (including current bar at end).
        correlation_length: Window size for pattern matching (EV1).
        projection_horizon: How many bars ahead to project (EV2).
        k: Number of similar patterns to use (EV3, must be >= 2 per C6).
        novelty_threshold: Regime safety brake threshold (EV7).

    Returns:
        EnsembleResult with O1-O5, O9 fields computed.
        If insufficient data, returns fail-closed result (O9=True).
    """
    n = len(closes)
    min_required = correlation_length + projection_horizon + _MIN_GAP_BARS

    # Fail-closed: insufficient data
    if n < min_required + correlation_length:
        return EnsembleResult(
            pattern_similarity_score=0.0,
            projection_direction=0,
            projection_consensus_ratio=0.0,
            expected_adverse_excursion_before_target=0.0,
            expected_favorable_excursion_to_target=0.0,
            regime_novelty_flag=True,  # fail-closed
            matches=(),
        )

    # Current pattern: last correlation_length bars
    current_window = _normalize_window(closes[-correlation_length:])

    # Search historical data for similar patterns
    # Search range: from correlation_length to (n - correlation_length - gap)
    # Each candidate ends at least (correlation_length + gap) before current
    search_end = n - correlation_length - _MIN_GAP_BARS
    candidates: list[tuple[float, int]] = []  # (similarity, end_index)

    for end_idx in range(
        correlation_length, min(search_end, n - projection_horizon)
    ):
        start_idx = end_idx - correlation_length
        hist_window = _normalize_window(closes[start_idx:end_idx])

        if len(hist_window) != correlation_length:
            continue

        sim = _pearson_similarity(current_window, hist_window)
        candidates.append((sim, end_idx))

    # Sort by similarity descending, take top-K
    candidates.sort(key=lambda x: x[0], reverse=True)
    top_k = candidates[:k]

    if len(top_k) < k:
        # Not enough candidates found - fail-closed
        return EnsembleResult(
            pattern_similarity_score=0.0,
            projection_direction=0,
            projection_consensus_ratio=0.0,
            expected_adverse_excursion_before_target=0.0,
            expected_favorable_excursion_to_target=0.0,
            regime_novelty_flag=True,
            matches=(),
        )

    # Compute per-match statistics
    matches: list[PatternMatch] = []
    for sim, end_idx in top_k:
        # Determine direction from what happened after the pattern
        future_end = min(end_idx + projection_horizon, n)
        if future_end > end_idx and closes[end_idx] != 0:
            total_return = (
                (closes[future_end - 1] - closes[end_idx]) / closes[end_idx]
            )
            direction = 1 if total_return > 0 else (-1 if total_return < 0 else 0)
        else:
            direction = 0

        adverse, favorable = _compute_excursions(
            closes, end_idx, projection_horizon, direction
        )

        matches.append(
            PatternMatch(
                start_index=end_idx - correlation_length,
                end_index=end_idx,
                similarity=sim,
                projected_direction=direction,
                adverse_excursion_pct=adverse,
                favorable_excursion_pct=favorable,
            )
        )

    # Ensemble statistics
    similarities = [m.similarity for m in matches]
    mean_similarity = float(np.mean(similarities))

    # O9: regime novelty flag
    regime_novelty = mean_similarity < novelty_threshold

    # O2: majority vote direction
    directions = [m.projected_direction for m in matches if m.projected_direction != 0]
    if len(directions) == 0:
        majority_direction = 0
        consensus_ratio = 0.0
    else:
        up_count = sum(1 for d in directions if d == 1)
        down_count = sum(1 for d in directions if d == -1)
        total_directional = up_count + down_count

        if up_count > down_count:
            majority_direction = 1
            consensus_ratio = up_count / total_directional if total_directional > 0 else 0.0
        elif down_count > up_count:
            majority_direction = -1
            consensus_ratio = down_count / total_directional if total_directional > 0 else 0.0
        else:
            majority_direction = 0  # tie -> no direction
            consensus_ratio = 0.5

    # O4/O5: median excursions (only from matches with majority direction)
    aligned_matches = [
        m for m in matches if m.projected_direction == majority_direction
    ]
    if aligned_matches and majority_direction != 0:
        adverse_values = [m.adverse_excursion_pct for m in aligned_matches]
        favorable_values = [m.favorable_excursion_pct for m in aligned_matches]
        median_adverse = float(np.median(adverse_values))
        median_favorable = float(np.median(favorable_values))
    else:
        median_adverse = 0.0
        median_favorable = 0.0

    return EnsembleResult(
        pattern_similarity_score=mean_similarity,
        projection_direction=majority_direction,
        projection_consensus_ratio=consensus_ratio,
        expected_adverse_excursion_before_target=median_adverse,
        expected_favorable_excursion_to_target=median_favorable,
        regime_novelty_flag=regime_novelty,
        matches=tuple(matches),
    )
