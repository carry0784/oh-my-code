import asyncio
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from workers.celery_app import celery_app
from app.core.config import settings
from app.core.database import engine
from app.models.order import Order, OrderStatus
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


@celery_app.task(bind=True, max_retries=3)
def submit_order(self, order_id: str):
    """Submit order to exchange."""
    session = _SyncSessionFactory()
    try:
        order = session.query(Order).filter(Order.id == order_id).first()
        if not order:
            logger.error("Order not found", order_id=order_id)
            return {"success": False, "error": "Order not found"}

        async def _submit():
            # Fresh instance per asyncio.run() — prevents stale
            # aiohttp session from closed event loop.
            exchange = ExchangeFactory.create_fresh(order.exchange)
            try:
                return await exchange.create_order(
                    symbol=order.symbol,
                    side=order.side.value,
                    order_type=order.order_type.value,
                    quantity=order.quantity,
                    price=order.price,
                )
            finally:
                await exchange.close()

        result = asyncio.run(_submit())
        order.exchange_order_id = result.get("id")
        order.status = OrderStatus.SUBMITTED
        session.commit()

        logger.info("Order submitted via worker", order_id=order_id)
        return {"success": True, "exchange_order_id": order.exchange_order_id}

    except Exception as e:
        logger.error("Order submission failed", order_id=order_id, error=str(e))
        self.retry(exc=e, countdown=5)
    finally:
        session.close()


@celery_app.task
def check_pending_orders():
    """Check status of submitted orders."""
    session = _SyncSessionFactory()
    try:
        orders = session.query(Order).filter(Order.status == OrderStatus.SUBMITTED).all()

        for order in orders:
            if not order.exchange_order_id:
                continue

            async def _fetch():
                # Fresh instance per asyncio.run() — prevents stale
                # aiohttp session from closed event loop.
                exchange = ExchangeFactory.create_fresh(order.exchange)
                try:
                    return await exchange.fetch_order(order.exchange_order_id, order.symbol)
                finally:
                    await exchange.close()

            try:
                result = asyncio.run(_fetch())
                status_map = {
                    "closed": OrderStatus.FILLED,
                    "canceled": OrderStatus.CANCELLED,
                    "rejected": OrderStatus.REJECTED,
                }
                if result.get("status") in status_map:
                    order.status = status_map[result["status"]]
                    order.filled_quantity = result.get("filled", 0)
                    order.average_price = result.get("average")

            except Exception as e:
                logger.error("Order status check failed", order_id=order.id, error=str(e))

        session.commit()
        logger.info("Order status check complete", count=len(orders))

    finally:
        session.close()
