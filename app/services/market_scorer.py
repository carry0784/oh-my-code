"""
MarketScorer — CR-039 Phase 2
Composite market scoring: technical + on-chain + sentiment → single score.

Score range: -100 (extreme bearish) to +100 (extreme bullish)
Components:
  - Technical score (40%): RSI, MACD, BB position, trend alignment
  - On-chain score (30%): hash rate trend, mempool pressure, fee levels
  - Sentiment score (30%): Fear & Greed, BTC dominance shift

Pure computation — no I/O, no side effects.
"""

from dataclasses import dataclass

from app.core.logging import get_logger
from app.schemas.market_state_schema import (
    IndicatorSet,
    OnChainData,
    PriceData,
    SentimentData,
)

logger = get_logger(__name__)


@dataclass
class ScoreBreakdown:
    """Detailed score breakdown per component."""
    total: float = 0.0           # -100 to +100
    technical: float = 0.0       # -100 to +100 (weight: 40%)
    on_chain: float = 0.0        # -100 to +100 (weight: 30%)
    sentiment: float = 0.0       # -100 to +100 (weight: 30%)
    grade: str = "NEUTRAL"       # STRONG_BULL / BULL / NEUTRAL / BEAR / STRONG_BEAR
    signal_strength: float = 0.0  # 0.0 to 1.0 (absolute confidence)
    details: dict | None = None


# Weights
W_TECHNICAL = 0.40
W_ONCHAIN = 0.30
W_SENTIMENT = 0.30


class MarketScorer:
    """Calculates composite market score from all data layers."""

    def score(
        self,
        price: PriceData,
        indicators: IndicatorSet,
        sentiment: SentimentData | None = None,
        on_chain: OnChainData | None = None,
    ) -> ScoreBreakdown:
        """Calculate composite market score."""
        sentiment = sentiment or SentimentData()
        on_chain = on_chain or OnChainData()

        tech = self._technical_score(price, indicators)
        chain = self._on_chain_score(on_chain)
        sent = self._sentiment_score(sentiment)

        total = (tech * W_TECHNICAL + chain * W_ONCHAIN + sent * W_SENTIMENT)
        total = max(-100, min(100, total))

        grade = self._grade(total)
        strength = abs(total) / 100.0

        result = ScoreBreakdown(
            total=round(total, 1),
            technical=round(tech, 1),
            on_chain=round(chain, 1),
            sentiment=round(sent, 1),
            grade=grade,
            signal_strength=round(strength, 3),
            details={
                "weights": {"technical": W_TECHNICAL, "on_chain": W_ONCHAIN, "sentiment": W_SENTIMENT},
            },
        )

        logger.info(
            "market_scored",
            total=result.total,
            grade=result.grade,
            tech=result.technical,
            chain=result.on_chain,
            sent=result.sentiment,
        )
        return result

    def _technical_score(self, price: PriceData, ind: IndicatorSet) -> float:
        """Technical analysis score: -100 to +100."""
        scores = []

        # RSI component (-100 to +100)
        if ind.rsi_14 is not None:
            # RSI 50 = neutral, 30 = -100, 70 = +100
            rsi_score = (ind.rsi_14 - 50) * 5  # Maps 30-70 to -100..+100
            scores.append(("rsi", _clamp(rsi_score)))

        # MACD histogram direction
        if ind.macd_histogram is not None and price.price > 0:
            # Normalize histogram by price
            macd_pct = ind.macd_histogram / price.price * 10000
            scores.append(("macd", _clamp(macd_pct)))

        # Bollinger Band position
        if ind.bb_upper is not None and ind.bb_lower is not None and ind.bb_upper != ind.bb_lower:
            bb_range = ind.bb_upper - ind.bb_lower
            bb_pos = (price.price - ind.bb_lower) / bb_range  # 0 to 1
            bb_score = (bb_pos - 0.5) * 200  # -100 to +100
            scores.append(("bb", _clamp(bb_score)))

        # Trend alignment: price vs SMA20, SMA50
        trend_points = 0
        if ind.sma_20 is not None:
            trend_points += 25 if price.price > ind.sma_20 else -25
        if ind.sma_50 is not None:
            trend_points += 25 if price.price > ind.sma_50 else -25
        if ind.sma_200 is not None:
            trend_points += 25 if price.price > ind.sma_200 else -25
        # EMA cross
        if ind.ema_12 is not None and ind.ema_26 is not None:
            trend_points += 25 if ind.ema_12 > ind.ema_26 else -25
        if trend_points != 0:
            scores.append(("trend", _clamp(trend_points)))

        if not scores:
            return 0.0
        return sum(s for _, s in scores) / len(scores)

    def _on_chain_score(self, on_chain: OnChainData) -> float:
        """On-chain health score: -100 to +100."""
        scores = []

        # Mempool fee pressure: high fees = congestion = activity (slightly bullish)
        # but extreme = panic (bearish)
        if on_chain.mempool_fee_fast is not None:
            if on_chain.mempool_fee_fast > 200:
                scores.append(("fee", -50.0))  # Panic-level fees
            elif on_chain.mempool_fee_fast > 100:
                scores.append(("fee", -20.0))  # High congestion
            elif on_chain.mempool_fee_fast > 30:
                scores.append(("fee", 20.0))   # Healthy activity
            else:
                scores.append(("fee", 0.0))    # Low activity, neutral

        # Mempool size: large mempool = high demand
        if on_chain.mempool_size is not None:
            if on_chain.mempool_size > 100000:
                scores.append(("mempool", -30.0))  # Extreme congestion
            elif on_chain.mempool_size > 50000:
                scores.append(("mempool", 10.0))    # Active
            else:
                scores.append(("mempool", 0.0))

        # BTC dominance: rising dominance during fear = flight to BTC (bearish for alts)
        # For BTC itself: high dominance = slight bull
        if on_chain.btc_dominance is not None:
            dom_score = (on_chain.btc_dominance - 50) * 2  # 50% = neutral
            scores.append(("dominance", _clamp(dom_score)))

        # Hash rate: presence of data = network healthy
        if on_chain.hash_rate is not None and on_chain.hash_rate > 0:
            scores.append(("hashrate", 10.0))  # Baseline healthy

        # Market cap: presence = data available
        if on_chain.total_market_cap_usd is not None:
            scores.append(("mcap", 0.0))  # Neutral — Phase 3 will track changes

        if not scores:
            return 0.0
        return sum(s for _, s in scores) / len(scores)

    def _sentiment_score(self, sentiment: SentimentData) -> float:
        """Sentiment score: -100 to +100."""
        if sentiment.fear_greed_index is None:
            return 0.0

        # F&G 0=Extreme Fear (-100), 50=Neutral (0), 100=Extreme Greed (+100)
        return _clamp((sentiment.fear_greed_index - 50) * 2)

    @staticmethod
    def _grade(total: float) -> str:
        if total >= 50:
            return "STRONG_BULL"
        elif total >= 20:
            return "BULL"
        elif total > -20:
            return "NEUTRAL"
        elif total > -50:
            return "BEAR"
        else:
            return "STRONG_BEAR"


def _clamp(value: float, lo: float = -100.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))
