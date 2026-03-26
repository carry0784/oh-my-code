import ccxt.async_support as ccxt
from typing import Any

from exchanges.base import BaseExchange
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class OKXExchange(BaseExchange):
    def __init__(self):
        super().__init__(settings.okx_api_key, settings.okx_api_secret)
        self.client = ccxt.okx({
            "apiKey": self.api_key,
            "secret": self.api_secret,
            "password": settings.okx_passphrase,
            "enableRateLimit": True,
            "session": self.create_session(),
            "options": {
                "defaultType": "swap",
            },
        })
        if settings.okx_sandbox:
            self.client.set_sandbox_mode(True)

    async def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float | None = None,
    ) -> dict[str, Any]:
        try:
            params = {"tdMode": "cross"}
            if order_type == "market":
                order = await self.client.create_market_order(symbol, side, quantity, params)
            else:
                order = await self.client.create_limit_order(symbol, side, quantity, price, params)
            logger.info("OKX order created", order_id=order["id"], symbol=symbol)
            return order
        except Exception as e:
            logger.error("OKX order failed", symbol=symbol, error=str(e))
            raise

    async def cancel_order(self, order_id: str, symbol: str) -> dict[str, Any]:
        return await self.client.cancel_order(order_id, symbol)

    async def fetch_order(self, order_id: str, symbol: str) -> dict[str, Any]:
        return await self.client.fetch_order(order_id, symbol)

    async def fetch_positions(self) -> list[dict[str, Any]]:
        return await self.client.fetch_positions()

    async def fetch_balance(self) -> dict[str, Any]:
        return await self.client.fetch_balance()

    async def fetch_ticker(self, symbol: str) -> dict[str, Any]:
        return await self.client.fetch_ticker(symbol)

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 100,
    ) -> list[list]:
        return await self.client.fetch_ohlcv(symbol, timeframe, limit=limit)

    async def close(self):
        await self.client.close()
