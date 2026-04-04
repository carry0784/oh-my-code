"""
RegimeEvolution — CR-042 Phase 5
Regime-aware evolution manager.

Partitions OHLCV data by detected regime and assigns island populations
to specialize in specific market conditions. This ensures the system
evolves strategies optimized for each regime rather than one-size-fits-all.

Pure computation — no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.schemas.market_state_schema import IndicatorSet, PriceData, SentimentData
from app.services.regime_detector import RegimeDetector

logger = get_logger(__name__)


@dataclass
class RegimeSegment:
    """A segment of OHLCV data belonging to a specific regime."""
    regime: str
    start_idx: int
    end_idx: int
    bars: list[list] = field(default_factory=list)


class RegimeEvolutionManager:
    """Manages regime-specific evolution of strategy populations."""

    def __init__(self, regime_detector: RegimeDetector | None = None):
        self.detector = regime_detector or RegimeDetector()

    def partition_data_by_regime(
        self,
        ohlcv: list[list],
        indicator_sets: list[dict] | None = None,
        sentiment_sets: list[dict] | None = None,
    ) -> dict[str, list[list]]:
        """
        Partition OHLCV data into regime-specific buckets.

        Each bar gets assigned a regime via the detector. Bars are grouped
        by regime. Returns dict mapping regime_tag -> list of OHLCV bars.

        indicator_sets and sentiment_sets are optional per-bar enrichment
        dicts. The detector requires schema objects, so only the fields
        present in those dicts are forwarded; everything else defaults to None.
        """
        if len(ohlcv) < 20:
            return {"unknown": ohlcv}

        regime_buckets: dict[str, list[list]] = {}

        for i, bar in enumerate(ohlcv):
            # Build PriceData from OHLCV bar: [ts, open, high, low, close, volume]
            close = float(bar[4]) if len(bar) > 4 else 0.0
            volume = float(bar[5]) if len(bar) > 5 else None
            price_data = PriceData(price=close, volume_24h=volume)

            # Build IndicatorSet from optional per-bar dict
            ind_dict = indicator_sets[i] if indicator_sets and i < len(indicator_sets) else {}
            indicators = IndicatorSet(**{
                k: v for k, v in ind_dict.items()
                if k in IndicatorSet.model_fields
            }) if ind_dict else IndicatorSet()

            # Build SentimentData from optional per-bar dict
            sent_dict = sentiment_sets[i] if sentiment_sets and i < len(sentiment_sets) else {}
            sentiment = SentimentData(**{
                k: v for k, v in sent_dict.items()
                if k in SentimentData.model_fields
            }) if sent_dict else SentimentData()

            regime_result = self.detector.detect(price_data, indicators, sentiment)
            tag = regime_result.regime

            if tag not in regime_buckets:
                regime_buckets[tag] = []
            regime_buckets[tag].append(bar)

        logger.info("regime_partition_complete",
                    regimes=list(regime_buckets.keys()),
                    sizes={k: len(v) for k, v in regime_buckets.items()})
        return regime_buckets

    def identify_regime_segments(self, ohlcv: list[list], regimes: list[str]) -> list[RegimeSegment]:
        """
        Identify contiguous segments of the same regime.

        Args:
            ohlcv: Full OHLCV data
            regimes: List of regime labels, one per bar
        """
        if not regimes:
            return []

        segments = []
        current_regime = regimes[0]
        start_idx = 0

        for i in range(1, len(regimes)):
            if regimes[i] != current_regime:
                segment = RegimeSegment(
                    regime=current_regime,
                    start_idx=start_idx,
                    end_idx=i - 1,
                    bars=ohlcv[start_idx:i],
                )
                segments.append(segment)
                current_regime = regimes[i]
                start_idx = i

        # Last segment
        segments.append(RegimeSegment(
            regime=current_regime,
            start_idx=start_idx,
            end_idx=len(regimes) - 1,
            bars=ohlcv[start_idx:len(regimes)],
        ))

        logger.info("regime_segments_identified", count=len(segments))
        return segments

    def select_active_strategies(
        self,
        current_regime: str,
        regime_populations: dict[str, list],
    ) -> list:
        """Select strategies relevant to the current regime."""
        # Primary: strategies evolved for current regime
        active = list(regime_populations.get(current_regime, []))

        # Fallback: if no regime-specific strategies, use all
        if not active:
            for pop in regime_populations.values():
                active.extend(pop)

        return active

    def get_regime_tags(self) -> list[str]:
        """Return the set of known regime labels."""
        return ["bull_trend", "bear_trend", "high_volatility", "ranging", "crisis"]
