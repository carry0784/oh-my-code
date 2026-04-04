from exchanges.base import BaseExchange
from exchanges.binance import BinanceExchange
from exchanges.okx import OKXExchange


class ExchangeFactory:
    _instances: dict[str, BaseExchange] = {}

    @classmethod
    def create(cls, exchange_name: str) -> BaseExchange:
        if exchange_name in cls._instances:
            return cls._instances[exchange_name]

        if exchange_name == "binance":
            instance = BinanceExchange()
        elif exchange_name == "okx":
            instance = OKXExchange()
        else:
            raise ValueError(f"Unknown exchange: {exchange_name}")

        cls._instances[exchange_name] = instance
        return instance

    @classmethod
    async def close_all(cls):
        for exchange in cls._instances.values():
            await exchange.close()
        cls._instances.clear()
