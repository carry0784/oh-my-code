import asyncio

from workers.celery_app import celery_app
from workers.tasks.order_tasks import get_sync_session
from app.models.position import Position, PositionSide
from exchanges.factory import ExchangeFactory
from app.core.logging import get_logger

logger = get_logger(__name__)


@celery_app.task
def sync_all_positions():
    """Sync positions from all exchanges."""
    session = get_sync_session()
    try:
        for exchange_name in ["binance"]:
            try:
                exchange = ExchangeFactory.create(exchange_name)

                async def _fetch():
                    return await exchange.fetch_positions()

                positions = asyncio.run(_fetch())

                for pos_data in positions:
                    contracts = pos_data.get("contracts", 0)
                    if contracts == 0:
                        continue

                    symbol = pos_data.get("symbol")
                    existing = (
                        session.query(Position)
                        .filter(
                            Position.exchange == exchange_name,
                            Position.symbol == symbol,
                        )
                        .first()
                    )

                    if existing:
                        existing.quantity = abs(contracts)
                        existing.current_price = pos_data.get("markPrice", 0)
                        existing.unrealized_pnl = pos_data.get("unrealizedPnl", 0)
                    else:
                        position = Position(
                            exchange=exchange_name,
                            symbol=symbol,
                            side=PositionSide.LONG
                            if pos_data.get("side") == "long"
                            else PositionSide.SHORT,
                            quantity=abs(contracts),
                            entry_price=pos_data.get("entryPrice", 0),
                            current_price=pos_data.get("markPrice", 0),
                            unrealized_pnl=pos_data.get("unrealizedPnl", 0),
                            leverage=pos_data.get("leverage", 1),
                            liquidation_price=pos_data.get("liquidationPrice"),
                        )
                        session.add(position)

                logger.info("Positions synced", exchange=exchange_name)

            except Exception as e:
                logger.error("Position sync failed", exchange=exchange_name, error=str(e))

        session.commit()

    finally:
        session.close()


@celery_app.task
def fetch_market_data(symbol: str, exchange: str = "binance", timeframe: str = "1h"):
    """Fetch OHLCV data for analysis."""
    try:
        exch = ExchangeFactory.create(exchange)

        async def _fetch():
            return await exch.fetch_ohlcv(symbol, timeframe, limit=100)

        ohlcv = asyncio.run(_fetch())
        logger.info("Market data fetched", symbol=symbol, exchange=exchange, bars=len(ohlcv))
        return {"symbol": symbol, "timeframe": timeframe, "data": ohlcv}

    except Exception as e:
        logger.error("Market data fetch failed", symbol=symbol, error=str(e))
        raise
