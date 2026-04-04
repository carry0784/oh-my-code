"""Sector Rotator — regime-conditional sector weight calculator.

Stage 3A + 3B-1, CR-048.  Pure computation, zero I/O.

Given a market regime, returns sector weights that influence screening
priority.  The rotator does NOT modify Symbol.status or call any
external service.  It is a stateless function: regime_label in →
weight map out.

Design reference: design_screening_engine.md §1 "섹터 로테이션"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.models.asset import AssetSector


# ── Regime Labels ───────────────────────────────────────────────────


class RegimeLabel(str, Enum):
    """Market regime categories used for sector rotation.

    These labels are *inputs* consumed by the rotator.
    They do NOT depend on RegimeDetector — the caller supplies
    the label as a plain string/enum value.
    """

    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    HIGH_VOL = "high_vol"
    CRISIS = "crisis"
    UNKNOWN = "unknown"


class RotationReasonCode(str, Enum):
    """Explanation codes for sector weight decisions.

    Stage 3B-1.  These are *description-only* — they do NOT influence
    the weight calculation.  They exist solely for audit/explanation.
    """

    OVERWEIGHT_REGIME_ALIGNED = "overweight_regime_aligned"
    UNDERWEIGHT_REGIME_OPPOSED = "underweight_regime_opposed"
    NEUTRAL_DEFAULT = "neutral_default"
    NEUTRAL_UNLISTED = "neutral_unlisted"
    REDUCED_HIGH_VOL = "reduced_high_vol"
    REDUCED_CRISIS = "reduced_crisis"
    UNKNOWN_REGIME = "unknown_regime"


# ── Sector Weight Configuration ────────────────────────────────────

# Weights: 1.0 = neutral, >1.0 = overweight, <1.0 = underweight, 0.0 = skip
# Design card: design_screening_engine.md §1 섹터 로테이션 표

_REGIME_SECTOR_WEIGHTS: dict[RegimeLabel, dict[AssetSector, float]] = {
    RegimeLabel.TRENDING_UP: {
        # 가중 섹터
        AssetSector.LAYER1: 1.5,
        AssetSector.TECH: 1.5,
        AssetSector.SEMICONDUCTOR: 1.5,
        # 나머지는 neutral (1.0)
    },
    RegimeLabel.TRENDING_DOWN: {
        # 가중 섹터
        AssetSector.INFRA: 1.3,
        AssetSector.ENERGY: 1.3,
        AssetSector.FINANCE: 1.3,
        AssetSector.KR_FINANCE: 1.3,
        # 감소 섹터
        AssetSector.LAYER1: 0.5,
        AssetSector.TECH: 0.5,
    },
    RegimeLabel.RANGING: {
        # 가중 섹터
        AssetSector.DEFI: 1.3,
        AssetSector.IT: 1.3,
    },
    RegimeLabel.HIGH_VOL: {
        # 전체 exposure 축소 — 모든 허용 섹터 underweight
        AssetSector.LAYER1: 0.5,
        AssetSector.DEFI: 0.5,
        AssetSector.AI: 0.5,
        AssetSector.INFRA: 0.5,
        AssetSector.TECH: 0.5,
        AssetSector.HEALTHCARE: 0.5,
        AssetSector.ENERGY: 0.5,
        AssetSector.FINANCE: 0.5,
        AssetSector.SEMICONDUCTOR: 0.5,
        AssetSector.IT: 0.5,
        AssetSector.KR_FINANCE: 0.5,
        AssetSector.AUTOMOTIVE: 0.5,
    },
    RegimeLabel.CRISIS: {
        # 전체 exposure 대폭 축소
        AssetSector.LAYER1: 0.2,
        AssetSector.DEFI: 0.2,
        AssetSector.AI: 0.2,
        AssetSector.INFRA: 0.2,
        AssetSector.TECH: 0.2,
        AssetSector.HEALTHCARE: 0.2,
        AssetSector.ENERGY: 0.2,
        AssetSector.FINANCE: 0.2,
        AssetSector.SEMICONDUCTOR: 0.2,
        AssetSector.IT: 0.2,
        AssetSector.KR_FINANCE: 0.2,
        AssetSector.AUTOMOTIVE: 0.2,
    },
    RegimeLabel.UNKNOWN: {
        # Fail-safe: all neutral
    },
}

# Default weight for sectors not explicitly listed in a regime
DEFAULT_WEIGHT: float = 1.0

# Minimum allowed weight (never zero out a non-excluded sector entirely)
MIN_WEIGHT: float = 0.1

# Maximum allowed weight
MAX_WEIGHT: float = 2.0


# ── Output ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SectorWeight:
    """Weight assignment for a single sector under a regime."""

    sector: AssetSector
    weight: float
    regime: str
    reason: RotationReasonCode | None = None


@dataclass(frozen=True)
class RotationOutput:
    """Complete sector rotation result for a given regime."""

    regime: str
    weights: tuple[SectorWeight, ...]
    overweight_sectors: tuple[AssetSector, ...]
    underweight_sectors: tuple[AssetSector, ...]


# ── Pure Computation ────────────────────────────────────────────────


def _derive_reason(
    sector: AssetSector,
    regime: str,
    weight: float,
) -> RotationReasonCode:
    """Derive an explanation code for a weight assignment.

    Pure function.  The reason does NOT influence the weight value.
    It exists solely for audit/explanation purposes.
    """
    try:
        regime_label = RegimeLabel(regime)
    except ValueError:
        return RotationReasonCode.UNKNOWN_REGIME

    if regime_label == RegimeLabel.CRISIS:
        return RotationReasonCode.REDUCED_CRISIS
    if regime_label == RegimeLabel.HIGH_VOL:
        return RotationReasonCode.REDUCED_HIGH_VOL

    sector_map = _REGIME_SECTOR_WEIGHTS.get(regime_label, {})
    if sector in sector_map:
        if weight > DEFAULT_WEIGHT:
            return RotationReasonCode.OVERWEIGHT_REGIME_ALIGNED
        return RotationReasonCode.UNDERWEIGHT_REGIME_OPPOSED
    return RotationReasonCode.NEUTRAL_UNLISTED


def get_sector_weight(
    sector: AssetSector,
    regime: str,
) -> float:
    """Return the weight for a single sector under the given regime.

    Pure function.  No I/O, no DB, no network, no cache.
    Returns DEFAULT_WEIGHT (1.0) for unknown regime or unlisted sector.
    Weight is clamped to [MIN_WEIGHT, MAX_WEIGHT].
    """
    try:
        regime_label = RegimeLabel(regime)
    except ValueError:
        return DEFAULT_WEIGHT

    sector_map = _REGIME_SECTOR_WEIGHTS.get(regime_label, {})
    raw = sector_map.get(sector, DEFAULT_WEIGHT)
    return max(MIN_WEIGHT, min(MAX_WEIGHT, raw))


def compute_rotation(
    regime: str,
    sectors: list[AssetSector] | None = None,
) -> RotationOutput:
    """Compute sector weights for all (or specified) sectors under a regime.

    Pure function.  No I/O, no DB, no network, no cache.

    Args:
        regime: Market regime label (e.g. "trending_up").
        sectors: Optional subset of sectors to evaluate.
                 If None, evaluates all non-excluded AssetSector values.

    Returns:
        RotationOutput with per-sector weights and over/underweight lists.
    """
    from app.models.asset import EXCLUDED_SECTORS

    if sectors is None:
        sectors = [s for s in AssetSector if s not in EXCLUDED_SECTORS]

    weights: list[SectorWeight] = []
    overweight: list[AssetSector] = []
    underweight: list[AssetSector] = []

    for sector in sectors:
        w = get_sector_weight(sector, regime)
        reason = _derive_reason(sector, regime, w)
        weights.append(
            SectorWeight(sector=sector, weight=w, regime=regime, reason=reason),
        )
        if w > DEFAULT_WEIGHT:
            overweight.append(sector)
        elif w < DEFAULT_WEIGHT:
            underweight.append(sector)

    return RotationOutput(
        regime=regime,
        weights=tuple(weights),
        overweight_sectors=tuple(overweight),
        underweight_sectors=tuple(underweight),
    )


def apply_sector_weight_to_score(
    base_score: float,
    sector: AssetSector,
    regime: str,
) -> float:
    """Adjust a screening score by the sector's regime weight.

    Pure function.  Score is clamped to [0.0, 1.0].

    This is the integration point: the screening pipeline can call
    this to adjust a symbol's score based on sector rotation without
    modifying screen_and_update().
    """
    weight = get_sector_weight(sector, regime)
    adjusted = base_score * weight
    return max(0.0, min(1.0, adjusted))
