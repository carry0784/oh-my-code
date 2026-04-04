"""
Data Collection Tasks — CR-038 Phase 1
Celery tasks for periodic market data and sentiment collection.
Read-only — never modifies exchange state.
"""

import asyncio
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from workers.celery_app import celery_app
from app.core.config import settings
from app.core.logging import get_logger
from app.models.market_state import MarketState
from app.services.market_data_collector import MarketDataCollector
from app.services.sentiment_collector import SentimentCollector
from app.services.indicator_calculator import IndicatorCalculator
from app.services.market_state_builder import MarketStateBuilder
from exchanges.factory import ExchangeFactory

logger = get_logger(__name__)


def _get_sync_session() -> Session:
    engine = create_engine(settings.database_url_sync)
    try:
        return Session(engine)
    except Exception:
        engine.dispose()
        raise


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def collect_market_state(
    self,
    symbol: str = "BTC/USDT",
    exchange_name: str = "binance",
    ohlcv_timeframe: str = "1h",
    ohlcv_limit: int = 200,
):
    """Collect full market state: price + indicators + sentiment → persist snapshot."""
    try:
        exchange = ExchangeFactory.create(exchange_name)

        async def _collect():
            collector = MarketDataCollector(exchange.client)
            market_data = await collector.collect(
                symbol=symbol,
                ohlcv_timeframe=ohlcv_timeframe,
                ohlcv_limit=ohlcv_limit,
            )

            sentiment_collector = SentimentCollector()
            sentiment = await sentiment_collector.collect()

            calculator = IndicatorCalculator()
            indicators = calculator.calculate(market_data.ohlcv)

            builder = MarketStateBuilder()
            snapshot = builder.build(market_data, indicators, sentiment)
            return snapshot

        snapshot = asyncio.run(_collect())

        # Persist to DB
        _engine = create_engine(settings.database_url_sync)
        try:
            with Session(_engine) as sess:
                state = MarketState(
                    exchange=snapshot.exchange,
                    symbol=snapshot.symbol,
                    price=snapshot.price_data.price,
                    bid=snapshot.microstructure.bid,
                    ask=snapshot.microstructure.ask,
                    spread_pct=snapshot.microstructure.spread_pct,
                    volume_24h=snapshot.price_data.volume_24h,
                    rsi_14=snapshot.indicators.rsi_14,
                    macd_line=snapshot.indicators.macd_line,
                    macd_signal=snapshot.indicators.macd_signal,
                    macd_histogram=snapshot.indicators.macd_histogram,
                    bb_upper=snapshot.indicators.bb_upper,
                    bb_middle=snapshot.indicators.bb_middle,
                    bb_lower=snapshot.indicators.bb_lower,
                    atr_14=snapshot.indicators.atr_14,
                    obv=snapshot.indicators.obv,
                    sma_20=snapshot.indicators.sma_20,
                    sma_50=snapshot.indicators.sma_50,
                    sma_200=snapshot.indicators.sma_200,
                    ema_12=snapshot.indicators.ema_12,
                    ema_26=snapshot.indicators.ema_26,
                    fear_greed_index=snapshot.sentiment.fear_greed_index,
                    fear_greed_label=snapshot.sentiment.fear_greed_label,
                    hash_rate=snapshot.on_chain.hash_rate,
                    difficulty=snapshot.on_chain.difficulty,
                    tx_count_24h=snapshot.on_chain.tx_count_24h,
                    mempool_size=snapshot.on_chain.mempool_size,
                    mempool_fee_fast=snapshot.on_chain.mempool_fee_fast,
                    mempool_fee_medium=snapshot.on_chain.mempool_fee_medium,
                    btc_dominance=snapshot.on_chain.btc_dominance,
                    total_market_cap_usd=snapshot.on_chain.total_market_cap_usd,
                    funding_rate=snapshot.microstructure.funding_rate,
                    open_interest=snapshot.microstructure.open_interest,
                    regime=snapshot.regime,
                    snapshot_at=snapshot.snapshot_at or datetime.now(timezone.utc),
                )
                sess.add(state)
                sess.commit()
        finally:
            _engine.dispose()

        logger.info(
            "market_state_persisted",
            exchange=snapshot.exchange,
            symbol=snapshot.symbol,
            regime=snapshot.regime,
            price=snapshot.price_data.price,
        )
        return {
            "exchange": snapshot.exchange,
            "symbol": snapshot.symbol,
            "regime": snapshot.regime,
            "price": snapshot.price_data.price,
        }

    except Exception as e:
        logger.error(
            "market_state_collection_failed",
            symbol=symbol,
            exchange=exchange_name,
            error=str(e),
        )
        raise self.retry(exc=e)


@celery_app.task
def collect_sentiment_only():
    """Lightweight sentiment-only collection (runs less frequently)."""
    try:
        async def _collect():
            collector = SentimentCollector()
            return await collector.collect()

        result = asyncio.run(_collect())
        logger.info(
            "sentiment_collected",
            fear_greed=result.fear_greed_index,
            label=result.fear_greed_label,
        )
        return {
            "fear_greed_index": result.fear_greed_index,
            "fear_greed_label": result.fear_greed_label,
        }
    except Exception as e:
        logger.error("sentiment_collection_failed", error=str(e))
        raise
