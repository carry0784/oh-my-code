"""PPF parameter loading module (EV1-EV10).

Authority: PPF-IMPLEMENTATION-001-CORRECTION-R1
Constitution: C3 (no universal parameters), C10 (no runtime adaptation)

Parameters are loaded at initialization time from environment variables or
a configuration dict. Runtime mutation is prohibited (C10). Each market
profile (M1-M3) must have independent parameter sets (C3).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Final

from strategies.ppf.constants import (
    DEFAULT_CANDIDATE_TIMEOUT_BARS,
    DEFAULT_CORRELATION_LENGTH,
    DEFAULT_K,
    DEFAULT_NOVELTY_THRESHOLD,
    DEFAULT_PATH_QUALITY_MIN,
    DEFAULT_PROJECTION_BIAS_MIN,
    DEFAULT_PROJECTION_HORIZON,
    DEFAULT_RR_MIN,
    DEFAULT_SIMILARITY_MIN,
    DEFAULT_WATCH_TIMEOUT_BARS,
    MIN_K,
    MarketProfile,
)

# Environment variable prefix for PPF parameters
_ENV_PREFIX: Final[str] = "PPF_"


@dataclass(frozen=True)
class PPFParameters:
    """Immutable PPF parameter set for a single market profile.

    frozen=True enforces C10 (no runtime adaptation). Once constructed,
    parameters cannot be modified. Changes require offline Evolution
    evaluation and a separate RAW_GO.

    All parameters must satisfy:
    - K >= MIN_K (C6: K=1 prohibited)
    - similarity_min in (0, 1]
    - path_quality_min in (-inf, 1)
    - rr_min > 0
    - projection_bias_min in (0, 1]
    - novelty_threshold in (0, 1]
    - correlation_length > 0
    - projection_horizon > 0
    - watch_timeout_bars > 0
    - candidate_timeout_bars > 0
    """

    # Market profile this parameter set belongs to
    market_profile: MarketProfile

    # EV1: pattern matching window (bars)
    correlation_length: int = DEFAULT_CORRELATION_LENGTH

    # EV2: projection length (bars)
    projection_horizon: int = DEFAULT_PROJECTION_HORIZON

    # EV3: ensemble similar pattern count
    k: int = DEFAULT_K

    # EV4: path quality threshold for ARMED entry
    path_quality_min: float = DEFAULT_PATH_QUALITY_MIN

    # EV5: minimum risk-reward ratio for ARMED entry
    rr_min: float = DEFAULT_RR_MIN

    # EV6: minimum similarity for WATCH entry
    similarity_min: float = DEFAULT_SIMILARITY_MIN

    # EV7: regime safety brake threshold
    novelty_threshold: float = DEFAULT_NOVELTY_THRESHOLD

    # EV8: minimum projection bias for QUALIFIED entry
    projection_bias_min: float = DEFAULT_PROJECTION_BIAS_MIN

    # EV9: D2 WATCH timeout before D1 reset (bars)
    watch_timeout_bars: int = DEFAULT_WATCH_TIMEOUT_BARS

    # EV10: D3 CANDIDATE timeout before D1 reset (bars)
    candidate_timeout_bars: int = DEFAULT_CANDIDATE_TIMEOUT_BARS

    def __post_init__(self) -> None:
        """Validate parameter constraints. Raises ValueError on violation."""
        violations: list[str] = []

        # C6: K=1 prohibited
        if self.k < MIN_K:
            violations.append(
                f"C6 violation: k={self.k} < MIN_K={MIN_K}. "
                f"Single pattern (K=1) decision prohibited."
            )

        if self.correlation_length <= 0:
            violations.append(
                f"correlation_length={self.correlation_length} must be > 0"
            )

        if self.projection_horizon <= 0:
            violations.append(
                f"projection_horizon={self.projection_horizon} must be > 0"
            )

        if not (0 < self.similarity_min <= 1.0):
            violations.append(
                f"similarity_min={self.similarity_min} must be in (0, 1]"
            )

        if self.rr_min <= 0:
            violations.append(f"rr_min={self.rr_min} must be > 0")

        if not (0 < self.projection_bias_min <= 1.0):
            violations.append(
                f"projection_bias_min={self.projection_bias_min} "
                f"must be in (0, 1]"
            )

        if not (0 < self.novelty_threshold <= 1.0):
            violations.append(
                f"novelty_threshold={self.novelty_threshold} "
                f"must be in (0, 1]"
            )

        if self.watch_timeout_bars <= 0:
            violations.append(
                f"watch_timeout_bars={self.watch_timeout_bars} must be > 0"
            )

        if self.candidate_timeout_bars <= 0:
            violations.append(
                f"candidate_timeout_bars={self.candidate_timeout_bars} "
                f"must be > 0"
            )

        if violations:
            raise ValueError(
                f"PPFParameters validation failed for "
                f"{self.market_profile.value}:\n"
                + "\n".join(f"  - {v}" for v in violations)
            )


def load_parameters_from_env(
    market_profile: MarketProfile,
) -> PPFParameters:
    """Load PPF parameters from environment variables.

    Environment variable naming convention:
        PPF_{MARKET}_{PARAM} = value

    Example:
        PPF_CRYPTO_FUTURES_K = 10
        PPF_CRYPTO_FUTURES_SIMILARITY_MIN = 0.6

    Falls back to defaults if env var is not set.
    C3: Each market profile loads independently.
    C10: Parameters are frozen after construction.
    """
    prefix = f"{_ENV_PREFIX}{market_profile.value.upper()}_"

    def _get_int(name: str, default: int) -> int:
        raw = os.environ.get(f"{prefix}{name}", "")
        if raw.strip().isdigit():
            return int(raw.strip())
        return default

    def _get_float(name: str, default: float) -> float:
        raw = os.environ.get(f"{prefix}{name}", "")
        try:
            return float(raw.strip()) if raw.strip() else default
        except ValueError:
            return default

    return PPFParameters(
        market_profile=market_profile,
        correlation_length=_get_int("CORRELATION_LENGTH", DEFAULT_CORRELATION_LENGTH),
        projection_horizon=_get_int("PROJECTION_HORIZON", DEFAULT_PROJECTION_HORIZON),
        k=_get_int("K", DEFAULT_K),
        path_quality_min=_get_float("PATH_QUALITY_MIN", DEFAULT_PATH_QUALITY_MIN),
        rr_min=_get_float("RR_MIN", DEFAULT_RR_MIN),
        similarity_min=_get_float("SIMILARITY_MIN", DEFAULT_SIMILARITY_MIN),
        novelty_threshold=_get_float("NOVELTY_THRESHOLD", DEFAULT_NOVELTY_THRESHOLD),
        projection_bias_min=_get_float(
            "PROJECTION_BIAS_MIN", DEFAULT_PROJECTION_BIAS_MIN
        ),
        watch_timeout_bars=_get_int(
            "WATCH_TIMEOUT_BARS", DEFAULT_WATCH_TIMEOUT_BARS
        ),
        candidate_timeout_bars=_get_int(
            "CANDIDATE_TIMEOUT_BARS", DEFAULT_CANDIDATE_TIMEOUT_BARS
        ),
    )


def load_parameters_from_dict(
    market_profile: MarketProfile,
    config: dict[str, Any],
) -> PPFParameters:
    """Load PPF parameters from a configuration dict.

    C3: Each market profile loads independently.
    C10: Parameters are frozen after construction.
    """
    return PPFParameters(
        market_profile=market_profile,
        correlation_length=int(
            config.get("correlation_length", DEFAULT_CORRELATION_LENGTH)
        ),
        projection_horizon=int(
            config.get("projection_horizon", DEFAULT_PROJECTION_HORIZON)
        ),
        k=int(config.get("k", DEFAULT_K)),
        path_quality_min=float(
            config.get("path_quality_min", DEFAULT_PATH_QUALITY_MIN)
        ),
        rr_min=float(config.get("rr_min", DEFAULT_RR_MIN)),
        similarity_min=float(
            config.get("similarity_min", DEFAULT_SIMILARITY_MIN)
        ),
        novelty_threshold=float(
            config.get("novelty_threshold", DEFAULT_NOVELTY_THRESHOLD)
        ),
        projection_bias_min=float(
            config.get("projection_bias_min", DEFAULT_PROJECTION_BIAS_MIN)
        ),
        watch_timeout_bars=int(
            config.get("watch_timeout_bars", DEFAULT_WATCH_TIMEOUT_BARS)
        ),
        candidate_timeout_bars=int(
            config.get("candidate_timeout_bars", DEFAULT_CANDIDATE_TIMEOUT_BARS)
        ),
    )
