"""Strategy Catalog — declarative registry of all available strategies.

Single source of truth for strategy metadata, regime affinity,
validation status, and track assignment. Adding a new strategy
requires one entry here plus the implementation file.

Track separation:
  - OPERATIONAL: production-eligible strategies (SMC+WT canonical)
  - EXPERIMENTAL: validation-in-progress (Track B, Track C-v2)
  - RESEARCH: early-stage, not yet validated

Regime affinity:
  - Strategies declare which regimes they are designed for.
  - Router/evolution manager uses this for regime-aware selection.
  - Empty list = regime-agnostic (runs in all regimes).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Track(str, Enum):
    """Strategy development track."""

    OPERATIONAL = "operational"
    EXPERIMENTAL = "experimental"
    RESEARCH = "research"


class ValidationStatus(str, Enum):
    """Validation pipeline status."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    CONDITIONAL_PASS = "conditional_pass"
    PASS = "pass"
    FAIL = "fail"


@dataclass(frozen=True)
class StrategyEntry:
    """Single strategy catalog entry."""

    name: str
    compute_module: str
    version: str
    description: str

    # Market scope
    asset_classes: tuple[str, ...] = ("CRYPTO",)
    symbols: tuple[str, ...] = ()  # empty = all symbols in asset class
    exchanges: tuple[str, ...] = ("BINANCE",)
    timeframes: tuple[str, ...] = ("1h",)

    # Regime affinity (empty = regime-agnostic)
    regime_affinity: tuple[str, ...] = ()

    # Track & validation
    track: Track = Track.RESEARCH
    validation_status: ValidationStatus = ValidationStatus.NOT_STARTED
    validation_notes: str = ""

    # Consensus
    consensus_components: tuple[str, ...] = ()
    consensus_threshold: str = ""  # e.g., "2/2", "2/3"

    # Dependencies
    min_bars: int = 50
    indicators_used: tuple[str, ...] = ()


# ── Catalog ──────────────────────────────────────────────────────────────

STRATEGY_CATALOG: dict[str, StrategyEntry] = {
    # ── OPERATIONAL (production-eligible) ─────────────────────────────
    "SMC_WaveTrend_1H": StrategyEntry(
        name="SMC_WaveTrend_1H",
        compute_module="strategies.smc_wavetrend_strategy",
        version="v2",
        description="Canonical SMC pure-causal + WaveTrend consensus (CR-046)",
        symbols=("SOL/USDT", "BTC/USDT"),
        timeframes=("1h",),
        regime_affinity=("trending_up", "trending_down"),
        track=Track.OPERATIONAL,
        validation_status=ValidationStatus.PASS,
        validation_notes="CG-2A SEALED, Phase 1-4 PASS, SOL primary, BTC guarded",
        consensus_components=("SMC_pure_causal_v2", "WaveTrend"),
        consensus_threshold="2/2",
        min_bars=50,
        indicators_used=("SMC_pure_causal", "WaveTrend"),
    ),
    # ── EXPERIMENTAL (Track B / Track C-v2) ──────────────────────────
    "SMC_MACD_1H": StrategyEntry(
        name="SMC_MACD_1H",
        compute_module="strategies.smc_macd_strategy",
        version="v1",
        description="Track B: SMC pure-causal + MACD consensus for ETH (CR-046)",
        symbols=("ETH/USDT",),
        timeframes=("1h",),
        regime_affinity=("trending_up", "trending_down"),
        track=Track.EXPERIMENTAL,
        validation_status=ValidationStatus.NOT_STARTED,
        validation_notes="Track B: ETH SMC+MACD branch, pending validation",
        consensus_components=("SMC_pure_causal_v2", "MACD_signal"),
        consensus_threshold="2/2",
        min_bars=50,
        indicators_used=("SMC_pure_causal", "MACD"),
    ),
    "RSI_14_70_30": StrategyEntry(
        name="RSI_14_70_30",
        compute_module="strategies.rsi_strategy",
        version="v1",
        description="RSI overbought/oversold crossover (CR-045)",
        symbols=(),  # regime-agnostic, all symbols
        timeframes=("1h",),
        regime_affinity=("ranging", "high_volatility"),
        track=Track.EXPERIMENTAL,
        validation_status=ValidationStatus.NOT_STARTED,
        validation_notes="Operational integration decision pending per Step 4 G3",
        consensus_components=("RSI_cross",),
        consensus_threshold="1/1",
        min_bars=16,
        indicators_used=("RSI",),
    ),
}


# ── Lookup helpers ───────────────────────────────────────────────────────


def get_entry(name: str) -> StrategyEntry | None:
    """Look up a strategy by name."""
    return STRATEGY_CATALOG.get(name)


def list_by_track(track: Track) -> list[StrategyEntry]:
    """List all strategies in a given track."""
    return [e for e in STRATEGY_CATALOG.values() if e.track == track]


def list_by_regime(regime: str) -> list[StrategyEntry]:
    """List strategies with affinity for a given regime."""
    return [
        e for e in STRATEGY_CATALOG.values() if not e.regime_affinity or regime in e.regime_affinity
    ]


def list_by_symbol(symbol: str) -> list[StrategyEntry]:
    """List strategies eligible for a given symbol."""
    return [e for e in STRATEGY_CATALOG.values() if not e.symbols or symbol in e.symbols]
