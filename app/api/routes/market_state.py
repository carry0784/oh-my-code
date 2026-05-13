"""
Market State API — CR-039 Phase 2
Read-only endpoints for market state, regime detection, scoring, and analysis.
No write operations — observation only.
"""

from datetime import datetime, timezone, timedelta
import re
import uuid
from typing import Any

from fastapi import APIRouter, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.logging import get_logger
from app.schemas.market_observation_receipt_schema import MarketStateObservationReceipt
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

# Pre-call input validation (F3). Matches exchanges.factory._FACTORY_REGISTRY
# exactly; if that registry changes, this set must be updated in lockstep.
_SUPPORTED_EXCHANGES: frozenset[str] = frozenset({"binance", "upbit", "bitget", "kis", "kiwoom"})
# Conservative symbol shape: uppercase alphanumeric base/quote separated by "/".
# Rejects empty, whitespace, lowercase, path-like, and overlong strings.
_SYMBOL_PATTERN: re.Pattern[str] = re.compile(r"^[A-Z0-9]{1,15}/[A-Z0-9]{1,15}$")

# F5b-LOG observation receipt rollback statement (recorded on every receipt).
_RECEIPT_ROLLBACK_NOTE = (
    "Disable by removing _emit_observation_receipt calls or by filtering "
    "event=market_observation_receipt at the logger. No DB rollback needed "
    "in F5b-LOG phase."
)


def _validate_inputs(exchange: str, symbol: str) -> tuple[str, str] | None:
    """Validate `exchange` and `symbol` route inputs before any side effect.

    Returns `(error_type, error_message)` on the first failure, or `None`
    when both inputs are admissible. F3 keeps HTTP semantics unchanged:
    callers should return their endpoint-specific error envelope rather
    than raise HTTPException (F2 deferred).
    """
    if exchange not in _SUPPORTED_EXCHANGES:
        return ("INVALID_EXCHANGE", f"unsupported exchange: {exchange!r}")
    if not _SYMBOL_PATTERN.match(symbol):
        return ("INVALID_SYMBOL", "invalid symbol format")
    return None


def _emit_observation_receipt(
    endpoint: str,
    exchange: str,
    symbol: str,
    requested_at: str,
    observed_at: str,
    source_status: str,
    validation_status: str,
    error_type: str | None,
) -> None:
    """Emit one F5b-LOG observation receipt via structured logger.

    Admissibility is derived from inputs; FRESH requires every gate to PASS.
    No DB write, no EvidenceStore write — F5b stops at log emission.
    """
    if (
        observed_at
        and source_status == "EXCHANGE_OK"
        and validation_status == "PASS"
        and error_type is None
    ):
        freshness_status = "FRESH"
    else:
        freshness_status = "STALE_UNKNOWN"
    admissible_for_decision = freshness_status == "FRESH"
    receipt = MarketStateObservationReceipt(
        receipt_id=f"market-obs-{uuid.uuid4().hex[:12]}",
        endpoint=endpoint,
        exchange=exchange,
        symbol=symbol,
        requested_at=requested_at,
        observed_at=observed_at,
        source_status=source_status,
        validation_status=validation_status,
        freshness_status=freshness_status,
        error_type=error_type,
        admissible_for_decision=admissible_for_decision,
        audit_created_at=datetime.now(timezone.utc).isoformat(),
        rollback_note=_RECEIPT_ROLLBACK_NOTE,
    )
    logger.info("market_observation_receipt", **receipt.model_dump())


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
    requested_at = datetime.now(timezone.utc).isoformat()
    validation_error = _validate_inputs(exchange, symbol)
    if validation_error is not None:
        err_type, err_msg = validation_error
        logger.warning(
            "market_snapshot_input_invalid",
            error_type=err_type,
            exchange=exchange,
            symbol=symbol,
        )
        _emit_observation_receipt(
            endpoint="snapshot",
            exchange=exchange,
            symbol=symbol,
            requested_at=requested_at,
            observed_at=requested_at,
            source_status="EXCHANGE_FAIL" if err_type == "INVALID_EXCHANGE" else "MIXED",
            validation_status=err_type,
            error_type=err_type,
        )
        return {
            "error": err_msg,
            "error_type": err_type,
            "exchange": exchange,
            "symbol": symbol,
        }
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

        snapshot_at_iso = snapshot.snapshot_at.isoformat() if snapshot.snapshot_at else ""
        _emit_observation_receipt(
            endpoint="snapshot",
            exchange=exchange,
            symbol=symbol,
            requested_at=requested_at,
            observed_at=snapshot_at_iso,
            source_status="EXCHANGE_OK",
            validation_status="PASS",
            error_type=None,
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
        _emit_observation_receipt(
            endpoint="snapshot",
            exchange=exchange,
            symbol=symbol,
            requested_at=requested_at,
            observed_at="",
            source_status="EXCHANGE_FAIL",
            validation_status="PASS",
            error_type=type(e).__name__,
        )
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
    requested_at = datetime.now(timezone.utc).isoformat()
    validation_error = _validate_inputs(exchange, symbol)
    if validation_error is not None:
        err_type, err_msg = validation_error
        logger.warning(
            "regime_detection_input_invalid",
            error_type=err_type,
            exchange=exchange,
            symbol=symbol,
        )
        _emit_observation_receipt(
            endpoint="regime",
            exchange=exchange,
            symbol=symbol,
            requested_at=requested_at,
            observed_at=requested_at,
            source_status="EXCHANGE_FAIL" if err_type == "INVALID_EXCHANGE" else "MIXED",
            validation_status=err_type,
            error_type=err_type,
        )
        return {
            "error": err_msg,
            "error_type": err_type,
            "regime": "unknown",
        }
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

        observed_at = datetime.now(timezone.utc).isoformat()
        _emit_observation_receipt(
            endpoint="regime",
            exchange=exchange,
            symbol=symbol,
            requested_at=requested_at,
            observed_at=observed_at,
            source_status="EXCHANGE_OK",
            validation_status="PASS",
            error_type=None,
        )
        return {
            "regime": result.regime,
            "confidence": result.confidence,
            "method": result.method,
            "features": result.features,
            "observed_at": observed_at,
        }
    except Exception as e:
        logger.error("regime_detection_failed", error=str(e))
        _emit_observation_receipt(
            endpoint="regime",
            exchange=exchange,
            symbol=symbol,
            requested_at=requested_at,
            observed_at="",
            source_status="EXCHANGE_FAIL",
            validation_status="PASS",
            error_type=type(e).__name__,
        )
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
    requested_at = datetime.now(timezone.utc).isoformat()
    validation_error = _validate_inputs(exchange, symbol)
    if validation_error is not None:
        err_type, err_msg = validation_error
        logger.warning(
            "score_calculation_input_invalid",
            error_type=err_type,
            exchange=exchange,
            symbol=symbol,
        )
        _emit_observation_receipt(
            endpoint="score",
            exchange=exchange,
            symbol=symbol,
            requested_at=requested_at,
            observed_at=requested_at,
            source_status="EXCHANGE_FAIL" if err_type == "INVALID_EXCHANGE" else "MIXED",
            validation_status=err_type,
            error_type=err_type,
        )
        return {
            "error": err_msg,
            "error_type": err_type,
            "total": 0,
            "grade": "NEUTRAL",
        }
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

        observed_at = datetime.now(timezone.utc).isoformat()
        _emit_observation_receipt(
            endpoint="score",
            exchange=exchange,
            symbol=symbol,
            requested_at=requested_at,
            observed_at=observed_at,
            source_status="EXCHANGE_OK",
            validation_status="PASS",
            error_type=None,
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
            "observed_at": observed_at,
        }
    except Exception as e:
        logger.error("score_calculation_failed", error=str(e))
        _emit_observation_receipt(
            endpoint="score",
            exchange=exchange,
            symbol=symbol,
            requested_at=requested_at,
            observed_at="",
            source_status="EXCHANGE_FAIL",
            validation_status="PASS",
            error_type=type(e).__name__,
        )
        return {"error": str(e), "total": 0, "grade": "NEUTRAL"}
    finally:
        if exch is not None:
            await exch.close()
