import asyncio

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from workers.celery_app import celery_app
from app.core.config import settings
from app.models.position import Position, PositionSide
from exchanges.factory import ExchangeFactory
from app.core.logging import get_logger

logger = get_logger(__name__)

# Module-level bounded engine: pool_size=1, max_overflow=0
# Prevents per-invocation engine leak (CR-048 DB saturation fix)
_sync_engine = create_engine(
    settings.database_url_sync,
    pool_pre_ping=True,
    pool_size=1,
    max_overflow=0,
    pool_recycle=1800,
)
_SyncSessionFactory = sessionmaker(bind=_sync_engine)


@celery_app.task
def sync_all_positions():
    """Sync positions from all exchanges."""
    session = _SyncSessionFactory()
    try:
        for exchange_name in ["binance"]:
            try:

                async def _fetch():
                    # Fresh instance per asyncio.run() — prevents stale
                    # aiohttp session from closed event loop.
                    exchange = ExchangeFactory.create_fresh(exchange_name)
                    try:
                        return await exchange.fetch_positions()
                    finally:
                        await exchange.close()

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

        async def _fetch():
            # Fresh instance per asyncio.run() — prevents stale
            # aiohttp session from closed event loop.
            exch = ExchangeFactory.create_fresh(exchange)
            try:
                return await exch.fetch_ohlcv(symbol, timeframe, limit=100)
            finally:
                await exch.close()

        ohlcv = asyncio.run(_fetch())
        logger.info("Market data fetched", symbol=symbol, exchange=exchange, bars=len(ohlcv))
        return {"symbol": symbol, "timeframe": timeframe, "data": ohlcv}

    except Exception as e:
        logger.error("Market data fetch failed", symbol=symbol, error=str(e))
        raise
