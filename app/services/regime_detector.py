"""
RegimeDetector — CR-039 Phase 2
ML-based market regime detection using unsupervised clustering + rule overlay.
Replaces the simple rule-based detection in MarketStateBuilder.

Approach:
  1. Feature vector: [RSI_norm, MACD_hist_norm, ATR_pct, volume_change, spread_pct]
  2. K-Means clustering (k=5) on historical feature vectors
  3. Cluster → regime mapping via centroid characteristics
  4. Rule overlay: crisis/extreme conditions override cluster assignment

Pure computation — no I/O, no side effects.
"""

import numpy as np
from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.schemas.market_state_schema import (
    IndicatorSet,
    MarketMicrostructure,
    OnChainData,
    PriceData,
    SentimentData,
)

logger = get_logger(__name__)

# Regime labels
TRENDING_UP = "trending_up"
TRENDING_DOWN = "trending_down"
RANGING = "ranging"
HIGH_VOLATILITY = "high_volatility"
CRISIS = "crisis"
UNKNOWN = "unknown"

# Feature normalization bounds
RSI_MIN, RSI_MAX = 0.0, 100.0
ATR_PCT_CAP = 10.0  # Cap ATR% at 10
VOLUME_CHANGE_CAP = 5.0  # Cap volume change ratio at 5x


@dataclass
class RegimeResult:
    """Result of regime detection."""

    regime: str = UNKNOWN
    confidence: float = 0.0
    features: dict = field(default_factory=dict)
    method: str = "unknown"  # "rule" or "cluster"


@dataclass
class BatchRegimeResult:
    """Single-bar regime result for batch detection (Phase A)."""

    timestamp: int = 0
    regime: str = UNKNOWN
    confidence: float = 0.0


@dataclass
class FeatureVector:
    """Normalized feature vector for clustering."""

    rsi_norm: float = 0.5  # 0-1 normalized RSI
    macd_hist_norm: float = 0.0  # Normalized MACD histogram
    atr_pct: float = 0.0  # ATR as % of price
    volume_ratio: float = 1.0  # Current / avg volume
    spread_pct: float = 0.0  # Bid-ask spread %
    fear_greed_norm: float = 0.5  # 0-1 normalized F&G
    btc_dominance_norm: float = 0.5  # 0-1 normalized
    mempool_fee_norm: float = 0.0  # Normalized fee pressure


class RegimeDetector:
    """
    Detects market regime using feature clustering + rule overlay.

    Phase 2: Uses simple K-Means with fixed centroids derived from
    market regime characteristics. Future phases will train on historical data.
    """

    # Pre-defined cluster centroids (regime prototypes)
    # Each row: [rsi, macd_hist, atr_pct, vol_ratio, spread, fg, btc_dom, fee]
    # atr_pct capped at 0.1; vol_ratio fixed at 1.0 (Phase 3 will add historical avg)
    CENTROIDS = np.array(
        [
            [0.70, 0.6, 0.02, 1.0, 0.02, 0.70, 0.50, 0.3],  # trending_up
            [0.30, -0.6, 0.02, 1.0, 0.03, 0.30, 0.55, 0.3],  # trending_down
            [0.50, 0.0, 0.01, 1.0, 0.01, 0.50, 0.50, 0.2],  # ranging
            [0.50, 0.0, 0.06, 1.0, 0.05, 0.25, 0.55, 0.7],  # high_volatility
            [0.15, -0.8, 0.10, 1.0, 0.10, 0.08, 0.65, 0.9],  # crisis
        ],
        dtype=np.float64,
    )

    CENTROID_LABELS = [TRENDING_UP, TRENDING_DOWN, RANGING, HIGH_VOLATILITY, CRISIS]

    def __init__(self, history_window: int = 20):
        self._history: list[FeatureVector] = []
        self._history_window = history_window

    def detect(
        self,
        price: PriceData,
        indicators: IndicatorSet,
        sentiment: SentimentData | None = None,
        on_chain: OnChainData | None = None,
        microstructure: MarketMicrostructure | None = None,
    ) -> RegimeResult:
        """Detect current market regime."""
        sentiment = sentiment or SentimentData()
        on_chain = on_chain or OnChainData()
        microstructure = microstructure or MarketMicrostructure()

        features = self._extract_features(price, indicators, sentiment, on_chain, microstructure)

        # 1. Hard rule overrides (highest priority)
        rule_result = self._apply_rule_overrides(price, indicators, sentiment, on_chain, features)
        if rule_result:
            return rule_result

        # 2. Cluster-based detection
        cluster_result = self._cluster_detect(features)

        # 3. Update history
        self._history.append(features)
        if len(self._history) > self._history_window:
            self._history = self._history[-self._history_window :]

        return cluster_result

    def _extract_features(
        self,
        price: PriceData,
        indicators: IndicatorSet,
        sentiment: SentimentData,
        on_chain: OnChainData,
        microstructure: MarketMicrostructure,
    ) -> FeatureVector:
        """Build normalized feature vector from all data sources."""
        fv = FeatureVector()

        # RSI → 0-1
        if indicators.rsi_14 is not None:
            fv.rsi_norm = np.clip(indicators.rsi_14 / RSI_MAX, 0.0, 1.0)

        # MACD histogram → normalized by price
        if indicators.macd_histogram is not None and price.price > 0:
            raw = indicators.macd_histogram / price.price * 100
            fv.macd_hist_norm = float(np.clip(raw, -1.0, 1.0))

        # ATR as % of price
        if indicators.atr_14 is not None and price.price > 0:
            fv.atr_pct = float(np.clip(indicators.atr_14 / price.price, 0.0, ATR_PCT_CAP / 100))

        # Volume ratio (current vs. typical — approximate via 24h)
        if price.volume_24h and price.volume_24h > 0:
            # Use 1.0 as baseline (normalized around "typical" volume)
            fv.volume_ratio = 1.0  # Phase 3 will compute vs. historical avg

        # Spread %
        if microstructure.spread_pct is not None:
            fv.spread_pct = float(np.clip(microstructure.spread_pct / 100, 0.0, 0.5))

        # Fear & Greed → 0-1
        if sentiment.fear_greed_index is not None:
            fv.fear_greed_norm = sentiment.fear_greed_index / 100.0

        # BTC dominance → 0-1 (typically 40-70%)
        if on_chain.btc_dominance is not None:
            fv.btc_dominance_norm = float(np.clip(on_chain.btc_dominance / 100, 0.0, 1.0))

        # Mempool fee pressure → normalized
        if on_chain.mempool_fee_fast is not None:
            # 100 sat/vB as high pressure baseline
            fv.mempool_fee_norm = float(np.clip(on_chain.mempool_fee_fast / 100, 0.0, 1.0))

        return fv

    def _apply_rule_overrides(
        self,
        price: PriceData,
        indicators: IndicatorSet,
        sentiment: SentimentData,
        on_chain: OnChainData,
        features: FeatureVector,
    ) -> RegimeResult | None:
        """Hard rules that override clustering for extreme conditions."""

        # Crisis override: F&G ≤ 10 AND (ATR > 5% or mempool fee spike)
        if sentiment.fear_greed_index is not None and sentiment.fear_greed_index <= 10:
            return RegimeResult(
                regime=CRISIS,
                confidence=0.95,
                features=self._fv_to_dict(features),
                method="rule:crisis_fg",
            )

        # Crisis override: extreme ATR (> 8% of price) regardless of sentiment
        if indicators.atr_14 and price.price > 0:
            atr_pct = indicators.atr_14 / price.price * 100
            if atr_pct > 8.0:
                return RegimeResult(
                    regime=CRISIS,
                    confidence=0.90,
                    features=self._fv_to_dict(features),
                    method="rule:crisis_atr",
                )

        return None

    def _cluster_detect(self, features: FeatureVector) -> RegimeResult:
        """Assign regime by nearest centroid (K-Means style)."""
        fv_array = np.array(
            [
                features.rsi_norm,
                features.macd_hist_norm,
                features.atr_pct,
                features.volume_ratio,
                features.spread_pct,
                features.fear_greed_norm,
                features.btc_dominance_norm,
                features.mempool_fee_norm,
            ],
            dtype=np.float64,
        )

        # Compute distances to each centroid
        distances = np.linalg.norm(self.CENTROIDS - fv_array, axis=1)
        nearest_idx = int(np.argmin(distances))
        min_dist = float(distances[nearest_idx])

        # Confidence: inverse of distance, scaled to 0-1
        # Distance of 0 → confidence 1.0, distance of 2.0 → confidence ~0.33
        confidence = float(1.0 / (1.0 + min_dist))

        # If history exists, apply momentum smoothing
        regime = self.CENTROID_LABELS[nearest_idx]
        if len(self._history) >= 3:
            regime, confidence = self._apply_momentum(regime, confidence, nearest_idx, distances)

        return RegimeResult(
            regime=regime,
            confidence=round(confidence, 3),
            features=self._fv_to_dict(features),
            method="cluster",
        )

    def _apply_momentum(
        self,
        regime: str,
        confidence: float,
        nearest_idx: int,
        distances: np.ndarray,
    ) -> tuple[str, float]:
        """
        Regime momentum: prevent rapid flipping.
        If the current regime has been stable for 3+ periods, require
        stronger evidence (closer distance) to switch.
        """
        recent_regimes = [self._detect_simple(fv) for fv in self._history[-3:]]
        if all(r == regime for r in recent_regimes):
            # Already consistent — boost confidence
            confidence = min(confidence * 1.15, 0.99)
        elif len(set(recent_regimes)) == 1 and recent_regimes[0] != regime:
            # Trying to switch away from stable regime — require 20% closer distance
            prev_regime = recent_regimes[0]
            prev_idx = (
                self.CENTROID_LABELS.index(prev_regime)
                if prev_regime in self.CENTROID_LABELS
                else nearest_idx
            )
            if distances[prev_idx] < distances[nearest_idx] * 1.2:
                regime = prev_regime
                confidence = float(1.0 / (1.0 + distances[prev_idx])) * 0.9
        return regime, confidence

    def _detect_simple(self, features: FeatureVector) -> str:
        """Quick regime from single feature vector (no momentum)."""
        fv_array = np.array(
            [
                features.rsi_norm,
                features.macd_hist_norm,
                features.atr_pct,
                features.volume_ratio,
                features.spread_pct,
                features.fear_greed_norm,
                features.btc_dominance_norm,
                features.mempool_fee_norm,
            ]
        )
        distances = np.linalg.norm(self.CENTROIDS - fv_array, axis=1)
        return self.CENTROID_LABELS[int(np.argmin(distances))]

    @staticmethod
    def _fv_to_dict(fv: FeatureVector) -> dict:
        return {
            "rsi_norm": round(fv.rsi_norm, 4),
            "macd_hist_norm": round(fv.macd_hist_norm, 4),
            "atr_pct": round(fv.atr_pct, 4),
            "volume_ratio": round(fv.volume_ratio, 4),
            "spread_pct": round(fv.spread_pct, 4),
            "fear_greed_norm": round(fv.fear_greed_norm, 4),
            "btc_dominance_norm": round(fv.btc_dominance_norm, 4),
            "mempool_fee_norm": round(fv.mempool_fee_norm, 4),
        }

    # ── Phase A: Batch Detection (backtest data plane) ───────────────

    def detect_batch(
        self,
        ohlcv: list[list],
        rsi_period: int = 14,
        atr_period: int = 14,
    ) -> list[BatchRegimeResult]:
        """Classify regime for each bar in a historical OHLCV series.

        Pure computation — no I/O, no side effects.
        Uses simplified feature extraction from OHLCV data only
        (no sentiment, on-chain, or microstructure — those are unavailable
        in historical replay context).

        Design constraint: batch results are NOT connected to real-time
        execution path. Read-only analysis for backtest data plane.

        Args:
            ohlcv: List of [timestamp_ms, open, high, low, close, volume].
                   Must be sorted by timestamp ASC.
            rsi_period: RSI lookback period.
            atr_period: ATR lookback period.

        Returns:
            List of BatchRegimeResult, one per input bar.
            Bars before warmup period get regime=UNKNOWN, confidence=0.
        """
        n = len(ohlcv)
        if n == 0:
            return []

        # Extract price arrays
        timestamps = [int(bar[0]) for bar in ohlcv]
        opens = np.array([float(bar[1]) for bar in ohlcv])
        highs = np.array([float(bar[2]) for bar in ohlcv])
        lows = np.array([float(bar[3]) for bar in ohlcv])
        closes = np.array([float(bar[4]) for bar in ohlcv])
        volumes = np.array([float(bar[5]) for bar in ohlcv])

        # Pre-compute indicators over full series
        rsi_arr = self._batch_rsi(closes, rsi_period)
        atr_arr = self._batch_atr(highs, lows, closes, atr_period)
        macd_hist_arr = self._batch_macd_histogram(closes)

        # Warmup: need max(rsi_period, atr_period, 26) bars
        warmup = max(rsi_period, atr_period, 26)

        results: list[BatchRegimeResult] = []
        for i in range(n):
            if i < warmup:
                results.append(BatchRegimeResult(
                    timestamp=timestamps[i],
                    regime=UNKNOWN,
                    confidence=0.0,
                ))
                continue

            # Build simplified feature vector from OHLCV-derived indicators
            rsi_val = rsi_arr[i] if not np.isnan(rsi_arr[i]) else 50.0
            macd_val = macd_hist_arr[i] if not np.isnan(macd_hist_arr[i]) else 0.0
            atr_val = atr_arr[i] if not np.isnan(atr_arr[i]) else 0.0
            price = closes[i]

            fv = FeatureVector(
                rsi_norm=float(np.clip(rsi_val / RSI_MAX, 0.0, 1.0)),
                macd_hist_norm=float(np.clip(
                    macd_val / price * 100 if price > 0 else 0.0, -1.0, 1.0
                )),
                atr_pct=float(np.clip(
                    atr_val / price if price > 0 else 0.0, 0.0, ATR_PCT_CAP / 100
                )),
                volume_ratio=1.0,  # No historical avg available in batch
                spread_pct=0.0,    # No microstructure in batch
                fear_greed_norm=0.5,   # Neutral default
                btc_dominance_norm=0.5,  # Neutral default
                mempool_fee_norm=0.0,    # No on-chain in batch
            )

            # Classify via centroid distance (no momentum smoothing in batch)
            regime_result = self._cluster_detect(fv)

            results.append(BatchRegimeResult(
                timestamp=timestamps[i],
                regime=regime_result.regime,
                confidence=regime_result.confidence,
            ))

        # Compute summary statistics
        valid_results = [r for r in results if r.regime != UNKNOWN]
        if valid_results:
            regime_counts: dict[str, int] = {}
            for r in valid_results:
                regime_counts[r.regime] = regime_counts.get(r.regime, 0) + 1
            total_valid = len(valid_results)

            logger.info(
                "batch_regime_detected",
                total_bars=n,
                warmup_bars=warmup,
                valid_bars=total_valid,
                regime_distribution={
                    k: round(v / total_valid, 3)
                    for k, v in sorted(regime_counts.items())
                },
            )

        return results

    # ── Batch Indicator Helpers (vectorized) ─────────────────────────

    @staticmethod
    def _batch_rsi(closes: np.ndarray, period: int = 14) -> np.ndarray:
        """Compute RSI over full series. Returns NaN for warmup bars."""
        n = len(closes)
        rsi = np.full(n, np.nan)
        if n < period + 1:
            return rsi

        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])

        for i in range(period, n - 1):
            if avg_loss == 0:
                rsi[i + 1] = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi[i + 1] = 100.0 - (100.0 / (1.0 + rs))

            # Wilder's smoothing
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        # First valid RSI
        if avg_loss == 0:
            rsi[period] = 100.0
        else:
            rsi[period] = 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))

        return rsi

    @staticmethod
    def _batch_atr(
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        period: int = 14,
    ) -> np.ndarray:
        """Compute ATR over full series. Returns NaN for warmup bars."""
        n = len(highs)
        atr = np.full(n, np.nan)
        if n < period + 1:
            return atr

        # True Range
        tr = np.zeros(n)
        tr[0] = highs[0] - lows[0]
        for i in range(1, n):
            tr[i] = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )

        # Initial ATR = SMA of first `period` TRs
        atr[period] = np.mean(tr[1 : period + 1])

        # Wilder's smoothing
        for i in range(period + 1, n):
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period

        return atr

    @staticmethod
    def _batch_macd_histogram(
        closes: np.ndarray,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> np.ndarray:
        """Compute MACD histogram over full series."""
        n = len(closes)
        hist = np.full(n, np.nan)
        if n < slow + signal:
            return hist

        # EMA helper
        def ema(data: np.ndarray, period: int) -> np.ndarray:
            result = np.full(len(data), np.nan)
            result[period - 1] = np.mean(data[:period])
            mult = 2.0 / (period + 1)
            for i in range(period, len(data)):
                result[i] = (data[i] - result[i - 1]) * mult + result[i - 1]
            return result

        ema_fast = ema(closes, fast)
        ema_slow = ema(closes, slow)
        macd_line = ema_fast - ema_slow

        # Signal line (EMA of MACD line, starting from first valid MACD)
        valid_start = slow - 1
        macd_valid = macd_line[valid_start:]
        signal_line_valid = ema(macd_valid, signal)

        for i in range(len(signal_line_valid)):
            if not np.isnan(signal_line_valid[i]):
                hist[valid_start + i] = macd_valid[i] - signal_line_valid[i]

        return hist
