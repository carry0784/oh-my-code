"""PPF constants, enums, and type definitions.

Authority: PPF-IMPLEMENTATION-001-CORRECTION-R1
- D1-D6: regular FSM states (D prefix)
- R1: transition outcome (R prefix, not a regular state)
- Rejection codes: 7 types
- All parameter defaults from EV1-EV10
"""

from __future__ import annotations

import enum
from typing import Final


# ---------------------------------------------------------------------------
# Decision States (D1-D6) - Regular FSM States
# ---------------------------------------------------------------------------

class PPFState(enum.Enum):
    """PPF decision states. D1-D6 are regular FSM states."""

    D1_IDLE = "IDLE"
    D2_WATCH = "WATCH"
    D3_CANDIDATE = "CANDIDATE"
    D4_QUALIFIED = "QUALIFIED"
    D5_ARMED = "ARMED"
    D6_EXECUTE_READY = "EXECUTE_READY"


# ---------------------------------------------------------------------------
# Transition Outcome (R1) - NOT a regular state
# ---------------------------------------------------------------------------

class TransitionOutcome(enum.Enum):
    """Transition outcomes. R1 is a separate outcome, not a regular state."""

    R1_REJECT = "REJECT"


# ---------------------------------------------------------------------------
# Rejection Reason Codes (7 types)
# ---------------------------------------------------------------------------

class RejectionCode(enum.Enum):
    """Rejection reason codes for L4 audit logging."""

    PATH_QUALITY_FAIL = "PATH_QUALITY_FAIL"
    RR_FAIL = "RR_FAIL"
    TREND_MISALIGN = "TREND_MISALIGN"
    VOLUME_WEAK = "VOLUME_WEAK"
    CONSENSUS_LOW = "CONSENSUS_LOW"
    NOVELTY_BRAKE = "NOVELTY_BRAKE"
    RISK_FILTER_FAIL = "RISK_FILTER_FAIL"


# ---------------------------------------------------------------------------
# Observation Field Names (O1-O9)
# ---------------------------------------------------------------------------

class ObsField(str, enum.Enum):
    """Canonical observation field names. Aliases are prohibited."""

    O1_PATTERN_SIMILARITY_SCORE = "pattern_similarity_score"
    O2_PROJECTION_DIRECTION = "projection_direction"
    O3_PROJECTION_CONSENSUS_RATIO = "projection_consensus_ratio"
    O4_EXPECTED_ADVERSE_EXCURSION_BEFORE_TARGET = (
        "expected_adverse_excursion_before_target"
    )
    O5_EXPECTED_FAVORABLE_EXCURSION_TO_TARGET = (
        "expected_favorable_excursion_to_target"
    )
    O6_SSL_TREND_STRENGTH = "ssl_trend_strength"
    O7_VOLUME_FORCE_STRENGTH = "volume_force_strength"
    O8_RECENT_SWING_DISTANCE_PCT = "recent_swing_distance_pct"
    O9_REGIME_NOVELTY_FLAG = "regime_novelty_flag"


# ---------------------------------------------------------------------------
# Interpretation Score Names (I1-I5)
# ---------------------------------------------------------------------------

class InterpScore(str, enum.Enum):
    """Interpretation score names with role separation.

    I1: direction + strength (sign = bullish/bearish)
    I2: trend alignment strength (positive = aligned, NOT direction)
    I3: volume alignment strength (positive = aligned, NOT direction)
    I4: path quality (higher = better)
    I5: structural R:R (higher = better)
    """

    I1_PROJECTION_BIAS = "projection_bias_score"
    I2_TREND_ALIGNMENT = "trend_alignment_score"
    I3_VOLUME_CONFIRMATION = "volume_confirmation_score"
    I4_PATH_QUALITY = "path_quality_score"
    I5_STRUCTURE_RR = "structure_rr_score"


# ---------------------------------------------------------------------------
# Default Parameter Values (EV1-EV10)
# ---------------------------------------------------------------------------

# EV1: correlation_length - pattern matching window (bars)
DEFAULT_CORRELATION_LENGTH: Final[int] = 50

# EV2: projection_horizon - projection length (bars)
DEFAULT_PROJECTION_HORIZON: Final[int] = 10

# EV3: K - ensemble similar pattern count (must be >= 2, C6)
DEFAULT_K: Final[int] = 10

# EV4: path_quality_min - path quality threshold
DEFAULT_PATH_QUALITY_MIN: Final[float] = 0.2

# EV5: rr_min - minimum risk-reward ratio
DEFAULT_RR_MIN: Final[float] = 2.0

# EV6: similarity_min - minimum similarity for WATCH entry
DEFAULT_SIMILARITY_MIN: Final[float] = 0.6

# EV7: novelty_threshold - regime safety brake threshold
DEFAULT_NOVELTY_THRESHOLD: Final[float] = 0.4

# EV8: projection_bias_min - minimum projection bias for QUALIFIED
DEFAULT_PROJECTION_BIAS_MIN: Final[float] = 0.2

# EV9: watch_timeout_bars - D2 timeout before D1 reset
DEFAULT_WATCH_TIMEOUT_BARS: Final[int] = 3

# EV10: candidate_timeout_bars - D3 timeout before D1 reset
DEFAULT_CANDIDATE_TIMEOUT_BARS: Final[int] = 5

# Epsilon for zero-division protection (0.001%)
EPSILON_PCT: Final[float] = 0.001

# Minimum K value (C6: K=1 prohibited)
MIN_K: Final[int] = 2

# ---------------------------------------------------------------------------
# Market Profile Identifiers (M1-M3)
# ---------------------------------------------------------------------------

class MarketProfile(str, enum.Enum):
    """Market profile identifiers for parameter separation (C3)."""

    M1_CRYPTO_FUTURES = "crypto_futures"
    M2_KOREAN_STOCKS = "korean_stocks"
    M3_SPOT_CRYPTO = "spot_crypto"
