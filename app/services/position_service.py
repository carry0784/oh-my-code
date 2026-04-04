from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.position import Position, PositionSide
from app.exchanges.factory import ExchangeFactory
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class PositionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_positions(self, exchange: str | None = None) -> list[Position]:
        query = select(Position)
        if exchange:
            query = query.where(Position.exchange == exchange)
        result = await self.db.execute(query.order_by(Position.opened_at.desc()))
        return list(result.scalars().all())

    async def get_position(self, position_id: str) -> Position | None:
        result = await self.db.execute(select(Position).where(Position.id == position_id))
        return result.scalar_one_or_none()

    async def sync_from_exchange(self, exchange: str | None = None) -> None:
        exchanges_to_sync = [exchange] if exchange else ["binance"]

        for exch_name in exchanges_to_sync:
            try:
                exch = ExchangeFactory.create(exch_name)
                positions = await exch.fetch_positions()

                for pos_data in positions:
                    if pos_data.get("contracts", 0) == 0:
                        continue

                    existing = await self.db.execute(
                        select(Position).where(
                            Position.exchange == exch_name,
                            Position.symbol == pos_data["symbol"],
                        )
                    )
                    position = existing.scalar_one_or_none()

                    # symbol_name: preserve existing if new value is empty/None
                    new_symbol_name = pos_data.get("symbol_name") or None

                    if position:
                        position.quantity = abs(pos_data.get("contracts", 0))
                        position.current_price = pos_data.get("markPrice", 0)
                        position.unrealized_pnl = pos_data.get("unrealizedPnl", 0)
                        if new_symbol_name:
                            position.symbol_name = new_symbol_name
                    else:
                        position = Position(
                            exchange=exch_name,
                            symbol=pos_data["symbol"],
                            symbol_name=new_symbol_name,
                            side=PositionSide.LONG if pos_data.get("side") == "long" else PositionSide.SHORT,
                            quantity=abs(pos_data.get("contracts", 0)),
                            entry_price=pos_data.get("entryPrice", 0),
                            current_price=pos_data.get("markPrice", 0),
                            unrealized_pnl=pos_data.get("unrealizedPnl", 0),
                            leverage=pos_data.get("leverage", 1),
                            liquidation_price=pos_data.get("liquidationPrice"),
                        )
                        self.db.add(position)

                logger.info("Positions synced", exchange=exch_name)
            except Exception as e:
                logger.error("Position sync failed", exchange=exch_name, error=str(e))

    async def close_position(self, position_id: str) -> dict:
        position = await self.get_position(position_id)
        if not position:
            return {"success": False, "error": "Position not found"}

        exchange = ExchangeFactory.create(position.exchange)
        try:
            side = "sell" if position.side == PositionSide.LONG else "buy"
            result = await exchange.create_order(
                symbol=position.symbol,
                side=side,
                order_type="market",
                quantity=position.quantity,
            )
            logger.info("Position close order submitted", position_id=position_id, order=result)
            return {"success": True, "order": result}
        except Exception as e:
            logger.error("Position close failed", position_id=position_id, error=str(e))
            return {"success": False, "error": str(e)}
