"""
UpBit Exchange Adapter — Spot-only (현물 전용)
I-04: UpBit 어댑터 추가

UpBit은 현물 거래소이므로:
  - fetch_positions()는 fetch_balance()를 통해 현물 보유 자산을 반환
  - create_order()는 현물 주문만 지원
  - liquidation_price, leverage는 해당 없음 (None)
"""

import ccxt.async_support as ccxt
from typing import Any

from exchanges.base import BaseExchange
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class UpBitExchange(BaseExchange):
    def __init__(self):
        super().__init__(settings.upbit_api_key, settings.upbit_api_secret)
        self.client = ccxt.upbit(
            {
                "apiKey": self.api_key,
                "secret": self.api_secret,
                "enableRateLimit": True,
                "options": {
                    "defaultType": "spot",
                },
            }
        )

    async def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float | None = None,
    ) -> dict[str, Any]:
        try:
            params = {}
            if order_type == "market":
                order = await self.client.create_market_order(symbol, side, quantity, params)
            else:
                order = await self.client.create_limit_order(symbol, side, quantity, price, params)
            logger.info("UpBit order created", order_id=order["id"], symbol=symbol)
            return order
        except Exception as e:
            logger.error("UpBit order failed", symbol=symbol, error=str(e))
            raise

    async def cancel_order(self, order_id: str, symbol: str) -> dict[str, Any]:
        return await self.client.cancel_order(order_id, symbol)

    async def fetch_order(self, order_id: str, symbol: str) -> dict[str, Any]:
        return await self.client.fetch_order(order_id, symbol)

    async def fetch_positions(self) -> list[dict[str, Any]]:
        """
        UpBit은 현물 전용이므로 fetch_balance()를 통해
        잔고 > 0인 보유 자산을 position-like 형태로 변환하여 반환한다.

        반환 형식은 BaseExchange.fetch_positions() 계약과 동일:
        [{"symbol": "BTC/KRW", "contracts": 0.5, "side": "long", ...}, ...]
        """
        try:
            balance = await self.client.fetch_balance()
            positions = []
            for currency, amount_info in balance.get("total", {}).items():
                total = float(amount_info) if amount_info else 0.0
                if total <= 0 or currency in ("KRW", "USDT", "USD"):
                    continue
                # 현물 보유는 항상 long
                symbol = f"{currency}/KRW"
                # 현재가 조회 시도
                try:
                    ticker = await self.client.fetch_ticker(symbol)
                    mark_price = ticker.get("last", 0)
                except Exception:
                    mark_price = 0
                positions.append(
                    {
                        "symbol": symbol,
                        "contracts": total,
                        "side": "long",
                        "entryPrice": 0,  # UpBit API에서 평균 매수가 미제공
                        "markPrice": mark_price,
                        "unrealizedPnl": 0,  # 진입가 미확인으로 계산 불가
                        "leverage": 1,
                        "liquidationPrice": None,  # 현물은 청산가 없음
                    }
                )
            return positions
        except Exception as e:
            logger.error("UpBit fetch_positions failed", error=str(e))
            raise

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
