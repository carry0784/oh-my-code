"""
MarketStateAnalyzer — CR-039 Phase 2
Time-series analysis on stored MarketState snapshots.
Detects trends, regime transitions, divergences, and anomalies.

Read-only — queries DB but never writes.
"""

from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field

import numpy as np

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TrendAnalysis:
    """Trend detection result for a single metric."""
    direction: str = "flat"  # "up", "down", "flat"
    slope: float = 0.0       # Linear regression slope (normalized)
    r_squared: float = 0.0   # Goodness of fit (0-1)
    strength: str = "weak"   # "strong", "moderate", "weak"


@dataclass
class RegimeTransition:
    """Detected regime change."""
    from_regime: str
    to_regime: str
    timestamp: datetime | None = None
    confidence: float = 0.0


@dataclass
class Divergence:
    """Price-indicator divergence."""
    indicator: str          # e.g., "rsi", "obv", "macd"
    divergence_type: str    # "bullish" or "bearish"
    strength: float = 0.0   # 0-1


@dataclass
class MarketAnalysisResult:
    """Complete analysis result from stored snapshots."""
    price_trend: TrendAnalysis = field(default_factory=TrendAnalysis)
    rsi_trend: TrendAnalysis = field(default_factory=TrendAnalysis)
    volume_trend: TrendAnalysis = field(default_factory=TrendAnalysis)
    regime_transitions: list[RegimeTransition] = field(default_factory=list)
    divergences: list[Divergence] = field(default_factory=list)
    regime_stability: float = 0.0   # 0-1 (1 = no changes in window)
    snapshot_count: int = 0
    analysis_window_hours: int = 0


class MarketStateAnalyzer:
    """Analyzes time-series of MarketState snapshots."""

    def analyze(
        self,
        snapshots: list[dict],
        window_hours: int = 24,
    ) -> MarketAnalysisResult:
        """
        Analyze a list of snapshot dicts.
        Each dict should have: price, rsi_14, macd_histogram, obv, volume_24h,
        regime, snapshot_at.
        """
        if len(snapshots) < 2:
            return MarketAnalysisResult(
                snapshot_count=len(snapshots),
                analysis_window_hours=window_hours,
            )

        result = MarketAnalysisResult(
            snapshot_count=len(snapshots),
            analysis_window_hours=window_hours,
        )

        prices = [s.get("price", 0) for s in snapshots]
        rsis = [s.get("rsi_14") for s in snapshots]
        volumes = [s.get("volume_24h") for s in snapshots]
        macds = [s.get("macd_histogram") for s in snapshots]
        obvs = [s.get("obv") for s in snapshots]
        regimes = [s.get("regime", "unknown") for s in snapshots]

        # Trend analysis
        result.price_trend = self._analyze_trend(prices)
        result.rsi_trend = self._analyze_trend([r for r in rsis if r is not None])
        result.volume_trend = self._analyze_trend([v for v in volumes if v is not None])

        # Regime transitions
        result.regime_transitions = self._detect_transitions(regimes, snapshots)
        result.regime_stability = self._regime_stability(regimes)

        # Divergences
        result.divergences = self._detect_divergences(prices, rsis, macds, obvs)

        logger.info(
            "market_analysis_complete",
            snapshots=result.snapshot_count,
            price_trend=result.price_trend.direction,
            regime_stability=result.regime_stability,
            transitions=len(result.regime_transitions),
            divergences=len(result.divergences),
        )
        return result

    def _analyze_trend(self, values: list[float | None]) -> TrendAnalysis:
        """Linear regression trend analysis."""
        clean = [v for v in values if v is not None and v != 0]
        if len(clean) < 3:
            return TrendAnalysis()

        x = np.arange(len(clean), dtype=np.float64)
        y = np.array(clean, dtype=np.float64)

        # Normalize y for slope comparison
        y_mean = np.mean(y)
        if y_mean == 0:
            return TrendAnalysis()
        y_norm = y / y_mean

        # Linear regression
        n = len(x)
        sum_x = np.sum(x)
        sum_y = np.sum(y_norm)
        sum_xy = np.sum(x * y_norm)
        sum_x2 = np.sum(x * x)

        denom = n * sum_x2 - sum_x * sum_x
        if denom == 0:
            return TrendAnalysis()

        slope = float((n * sum_xy - sum_x * sum_y) / denom)

        # R-squared
        y_pred = slope * x + (sum_y - slope * sum_x) / n
        ss_res = float(np.sum((y_norm - y_pred) ** 2))
        ss_tot = float(np.sum((y_norm - np.mean(y_norm)) ** 2))
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        # Direction and strength
        if abs(slope) < 0.001:
            direction = "flat"
            strength = "weak"
        elif slope > 0:
            direction = "up"
            strength = "strong" if slope > 0.01 else "moderate" if slope > 0.003 else "weak"
        else:
            direction = "down"
            strength = "strong" if slope < -0.01 else "moderate" if slope < -0.003 else "weak"

        return TrendAnalysis(
            direction=direction,
            slope=round(slope, 6),
            r_squared=round(max(0, min(1, r_squared)), 4),
            strength=strength,
        )

    def _detect_transitions(
        self, regimes: list[str], snapshots: list[dict]
    ) -> list[RegimeTransition]:
        """Find regime changes in the time series."""
        transitions = []
        for i in range(1, len(regimes)):
            if regimes[i] != regimes[i - 1] and regimes[i] != "unknown":
                ts = snapshots[i].get("snapshot_at")
                transitions.append(RegimeTransition(
                    from_regime=regimes[i - 1],
                    to_regime=regimes[i],
                    timestamp=ts if isinstance(ts, datetime) else None,
                    confidence=0.7,  # Base confidence; Phase 3 will use duration
                ))
        return transitions

    def _regime_stability(self, regimes: list[str]) -> float:
        """Calculate regime stability as ratio of non-transition periods."""
        if len(regimes) < 2:
            return 1.0
        changes = sum(1 for i in range(1, len(regimes)) if regimes[i] != regimes[i - 1])
        return round(1.0 - (changes / (len(regimes) - 1)), 4)

    def _detect_divergences(
        self,
        prices: list[float],
        rsis: list[float | None],
        macds: list[float | None],
        obvs: list[float | None],
    ) -> list[Divergence]:
        """Detect price-indicator divergences."""
        divergences = []

        # RSI divergence
        div = self._check_divergence(prices, rsis, "rsi")
        if div:
            divergences.append(div)

        # MACD divergence
        div = self._check_divergence(prices, macds, "macd")
        if div:
            divergences.append(div)

        # OBV divergence
        div = self._check_divergence(prices, obvs, "obv")
        if div:
            divergences.append(div)

        return divergences

    def _check_divergence(
        self,
        prices: list[float],
        indicator_values: list[float | None],
        indicator_name: str,
    ) -> Divergence | None:
        """
        Check for divergence between price and an indicator.
        Bullish divergence: price makes lower low, indicator makes higher low.
        Bearish divergence: price makes higher high, indicator makes lower high.
        """
        clean_prices = []
        clean_indicator = []
        for p, v in zip(prices, indicator_values):
            if v is not None and p > 0:
                clean_prices.append(p)
                clean_indicator.append(v)

        if len(clean_prices) < 5:
            return None

        # Compare first half vs second half
        mid = len(clean_prices) // 2
        first_prices = clean_prices[:mid]
        second_prices = clean_prices[mid:]
        first_ind = clean_indicator[:mid]
        second_ind = clean_indicator[mid:]

        price_mean_first = np.mean(first_prices)
        ind_mean_first = abs(np.mean(first_ind))

        # Use percent-change normalization so different-scale series are comparable
        price_trend = (np.mean(second_prices) - np.mean(first_prices)) / (price_mean_first + 1e-10)
        ind_trend = (np.mean(second_ind) - np.mean(first_ind)) / (ind_mean_first + 1e-10)

        # Bullish divergence: price down, indicator up
        if price_trend < 0 and ind_trend > 0:
            strength = min(abs(ind_trend / (abs(price_trend) + 1e-10)), 1.0)
            if strength > 0.1:
                return Divergence(
                    indicator=indicator_name,
                    divergence_type="bullish",
                    strength=round(strength, 3),
                )

        # Bearish divergence: price up, indicator down
        if price_trend > 0 and ind_trend < 0:
            strength = min(abs(ind_trend / (abs(price_trend) + 1e-10)), 1.0)
            if strength > 0.1:
                return Divergence(
                    indicator=indicator_name,
                    divergence_type="bearish",
                    strength=round(strength, 3),
                )

        return None
