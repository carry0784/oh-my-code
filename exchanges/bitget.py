"""
Bitget Exchange Adapter — Futures (선물 전용)
I-03: Bitget 어댑터 추가
"""

import ccxt.async_support as ccxt
from typing import Any

from exchanges.base import BaseExchange
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class BitgetExchange(BaseExchange):
    def __init__(self):
        super().__init__(settings.bitget_api_key, settings.bitget_api_secret)
        self.client = ccxt.bitget(
            {
                "apiKey": self.api_key,
                "secret": self.api_secret,
                "password": settings.bitget_passphrase,
                "enableRateLimit": True,
                "options": {
                    "defaultType": "swap",
                },
            }
        )
        if settings.bitget_sandbox:
            self.client.set_sandbox_mode(True)

    async def create_order(self, symbol, side, order_type, quantity, price=None):
        try:
            params = {}
            if order_type == "market":
                order = await self.client.create_market_order(symbol, side, quantity, params)
            else:
                order = await self.client.create_limit_order(symbol, side, quantity, price, params)
            logger.info("Bitget order created", order_id=order["id"], symbol=symbol)
            return order
        except Exception as e:
            logger.error("Bitget order failed", symbol=symbol, error=str(e))
            raise

    async def cancel_order(self, order_id, symbol):
        return await self.client.cancel_order(order_id, symbol)

    async def fetch_order(self, order_id, symbol):
        return await self.client.fetch_order(order_id, symbol)

    async def fetch_positions(self):
        return await self.client.fetch_positions()

    async def fetch_balance(self):
        return await self.client.fetch_balance()

    async def fetch_ticker(self, symbol):
        return await self.client.fetch_ticker(symbol)

    async def fetch_ohlcv(self, symbol, timeframe="1h", limit=100):
        return await self.client.fetch_ohlcv(symbol, timeframe, limit=limit)

    async def close(self):
        await self.client.close()
