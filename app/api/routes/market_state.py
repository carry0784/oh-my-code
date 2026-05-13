"""
Market State API — CR-039 Phase 2
Read-only endpoints for market state, regime detection, scoring, and analysis.
No write operations — observation only.
"""

from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.logging import get_logger
from app.schemas.market_state_schema import (
    IndicatorSet,
    MarketDataCollectionResult,
    MarketMicrostructure,
    MarketStateSnapshot,
    OnChainData,
    PriceData,
    SentimentCollectionResult,
    SentimentData,
)
from app.services.indicator_calculator import IndicatorCalculator
from app.services.market_data_collector import MarketDataCollector
from app.services.market_scorer import MarketScorer, ScoreBreakdown
from app.services.market_state_analyzer import MarketStateAnalyzer, MarketAnalysisResult
from app.services.market_state_builder import MarketStateBuilder
from app.services.regime_detector import RegimeDetector, RegimeResult
from app.services.sentiment_collector import SentimentCollector
from exchanges.factory import ExchangeFactory

logger = get_logger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.get("/snapshot")  # type: ignore[untyped-decorator]
@limiter.limit("30/minute")  # type: ignore[untyped-decorator]
async def get_market_snapshot(
    request: Request,
    symbol: str = Query(default="BTC/USDT", description="Trading pair"),
    exchange: str = Query(default="binance", description="Exchange name"),
) -> dict[str, Any]:
    """
    Collect live market snapshot: price + indicators + sentiment + on-chain + regime + score.
    Read-only — no orders, no side effects.
    """
    exch = None
    try:
        exch = ExchangeFactory.create(exchange)
        collector = MarketDataCollector(exch.client)
        market_data = await collector.collect(symbol=symbol)

        sentiment_collector = SentimentCollector()
        sentiment = await sentiment_collector.collect()

        calculator = IndicatorCalculator()
        indicators = calculator.calculate(market_data.ohlcv)

        builder = MarketStateBuilder()
        snapshot = builder.build(market_data, indicators, sentiment)

        # Advanced regime detection
        detector = RegimeDetector()
        regime_result = detector.detect(
            price=snapshot.price_data,
            indicators=indicators,
            sentiment=snapshot.sentiment,
            on_chain=snapshot.on_chain,
            microstructure=snapshot.microstructure,
        )

        # Composite scoring
        scorer = MarketScorer()
        score = scorer.score(
            price=snapshot.price_data,
            indicators=indicators,
            sentiment=snapshot.sentiment,
            on_chain=snapshot.on_chain,
        )

        return {
            "exchange": snapshot.exchange,
            "symbol": snapshot.symbol,
            "price": snapshot.price_data.model_dump(),
            "indicators": indicators.model_dump(),
            "sentiment": snapshot.sentiment.model_dump(),
            "on_chain": snapshot.on_chain.model_dump(),
            "microstructure": snapshot.microstructure.model_dump(),
            "regime": {
                "label": regime_result.regime,
                "confidence": regime_result.confidence,
                "method": regime_result.method,
                "features": regime_result.features,
            },
            "score": {
                "total": score.total,
                "grade": score.grade,
                "technical": score.technical,
                "on_chain": score.on_chain,
                "sentiment": score.sentiment,
                "signal_strength": score.signal_strength,
            },
            "snapshot_at": snapshot.snapshot_at.isoformat() if snapshot.snapshot_at else None,
        }
    except Exception as e:
        logger.error("market_snapshot_failed", symbol=symbol, exchange=exchange, error=str(e))
        return {
            "error": str(e),
            "exchange": exchange,
            "symbol": symbol,
        }
    finally:
        if exch is not None:
            await exch.close()


@router.get("/regime")  # type: ignore[untyped-decorator]
@limiter.limit("30/minute")  # type: ignore[untyped-decorator]
async def get_regime(
    request: Request,
    symbol: str = Query(default="BTC/USDT"),
    exchange: str = Query(default="binance"),
) -> dict[str, Any]:
    """Get current market regime detection result."""
    exch = None
    try:
        exch = ExchangeFactory.create(exchange)
        collector = MarketDataCollector(exch.client)
        market_data = await collector.collect(symbol=symbol, ohlcv_limit=200)

        calculator = IndicatorCalculator()
        indicators = calculator.calculate(market_data.ohlcv)

        ticker = market_data.ticker or {}
        price = PriceData(
            price=ticker.get("last", 0),
            volume_24h=ticker.get("quoteVolume"),
        )

        detector = RegimeDetector()
        result = detector.detect(price=price, indicators=indicators)

        return {
            "regime": result.regime,
            "confidence": result.confidence,
            "method": result.method,
            "features": result.features,
        }
    except Exception as e:
        logger.error("regime_detection_failed", error=str(e))
        return {"error": str(e), "regime": "unknown"}
    finally:
        if exch is not None:
            await exch.close()


@router.get("/score")  # type: ignore[untyped-decorator]
@limiter.limit("30/minute")  # type: ignore[untyped-decorator]
async def get_score(
    request: Request,
    symbol: str = Query(default="BTC/USDT"),
    exchange: str = Query(default="binance"),
) -> dict[str, Any]:
    """Get composite market score."""
    exch = None
    try:
        exch = ExchangeFactory.create(exchange)
        collector = MarketDataCollector(exch.client)
        market_data = await collector.collect(symbol=symbol)

        sentiment_collector = SentimentCollector()
        sentiment = await sentiment_collector.collect()

        calculator = IndicatorCalculator()
        indicators = calculator.calculate(market_data.ohlcv)

        ticker = market_data.ticker or {}
        price = PriceData(
            price=ticker.get("last", 0),
            volume_24h=ticker.get("quoteVolume"),
        )
        sentiment_data = SentimentData(
            fear_greed_index=sentiment.fear_greed_index,
            fear_greed_label=sentiment.fear_greed_label,
        )

        scorer = MarketScorer()
        score = scorer.score(
            price=price,
            indicators=indicators,
            sentiment=sentiment_data,
            on_chain=sentiment.on_chain,
        )

        return {
            "total": score.total,
            "grade": score.grade,
            "signal_strength": score.signal_strength,
            "breakdown": {
                "technical": score.technical,
                "on_chain": score.on_chain,
                "sentiment": score.sentiment,
            },
        }
    except Exception as e:
        logger.error("score_calculation_failed", error=str(e))
        return {"error": str(e), "total": 0, "grade": "NEUTRAL"}
    finally:
        if exch is not None:
            await exch.close()
