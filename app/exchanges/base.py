from abc import ABC, abstractmethod
from typing import Any


class BaseExchange(ABC):
    def __init__(self, api_key: str, api_secret: str, **kwargs):
        self.api_key = api_key
        self.api_secret = api_secret

    @abstractmethod
    async def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float | None = None,
    ) -> dict[str, Any]:
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> dict[str, Any]:
        pass

    @abstractmethod
    async def fetch_order(self, order_id: str, symbol: str) -> dict[str, Any]:
        pass

    @abstractmethod
    async def fetch_positions(self) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    async def fetch_balance(self) -> dict[str, Any]:
        pass

    @abstractmethod
    async def fetch_ticker(self, symbol: str) -> dict[str, Any]:
        pass

    @abstractmethod
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 100,
    ) -> list[list]:
        pass
