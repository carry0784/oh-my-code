from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order, OrderStatus
from app.schemas.order import OrderCreate
from app.exchanges.factory import ExchangeFactory
from app.core.logging import get_logger

logger = get_logger(__name__)


class OrderService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_order(self, order_data: OrderCreate) -> Order:
        order = Order(
            exchange=order_data.exchange,
            symbol=order_data.symbol,
            side=order_data.side,
            order_type=order_data.order_type,
            quantity=order_data.quantity,
            price=order_data.price,
            signal_id=order_data.signal_id,
        )
        self.db.add(order)
        await self.db.flush()

        # Submit to exchange
        exchange = ExchangeFactory.create(order_data.exchange)
        try:
            result = await exchange.create_order(
                symbol=order.symbol,
                side=order.side.value,
                order_type=order.order_type.value,
                quantity=order.quantity,
                price=order.price,
            )
            order.exchange_order_id = result.get("id")
            order.status = OrderStatus.SUBMITTED
            logger.info("Order submitted", order_id=order.id, exchange_id=order.exchange_order_id)
        except Exception as e:
            order.status = OrderStatus.REJECTED
            logger.error("Order submission failed", order_id=order.id, error=str(e))

        return order

    async def get_orders(self, skip: int = 0, limit: int = 100) -> list[Order]:
        result = await self.db.execute(
            select(Order).offset(skip).limit(limit).order_by(Order.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_order(self, order_id: str) -> Order | None:
        result = await self.db.execute(select(Order).where(Order.id == order_id))
        return result.scalar_one_or_none()

    async def cancel_order(self, order_id: str) -> bool:
        order = await self.get_order(order_id)
        if not order or order.status not in [OrderStatus.PENDING, OrderStatus.SUBMITTED]:
            return False

        if order.exchange_order_id:
            exchange = ExchangeFactory.create(order.exchange)
            try:
                await exchange.cancel_order(order.exchange_order_id, order.symbol)
            except Exception as e:
                logger.error("Cancel order failed", order_id=order_id, error=str(e))
                return False

        order.status = OrderStatus.CANCELLED
        return True
