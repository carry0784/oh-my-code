from exchanges.base import BaseExchange
from exchanges.binance import BinanceExchange
from exchanges.okx import OKXExchange
from exchanges.upbit import UpBitExchange
from exchanges.bitget import BitgetExchange
from exchanges.kis import KISExchange
from exchanges.kiwoom import KiwoomExchange


class ExchangeFactory:
    _instances: dict[str, BaseExchange] = {}

    @classmethod
    def create(cls, exchange_name: str) -> BaseExchange:
        """Create or return cached exchange instance.

        Idempotent: returns cached singleton for the same exchange key.
        Safe to call multiple times — only the first call creates an instance.
        """
        if exchange_name in cls._instances:
            return cls._instances[exchange_name]

        if exchange_name == "binance":
            instance = BinanceExchange()
        elif exchange_name == "okx":
            instance = OKXExchange()
        elif exchange_name == "upbit":
            instance = UpBitExchange()
        elif exchange_name == "bitget":
            instance = BitgetExchange()
        elif exchange_name == "kis":
            instance = KISExchange()
        elif exchange_name == "kiwoom":
            instance = KiwoomExchange()
        else:
            raise ValueError(f"Unknown exchange: {exchange_name}")

        cls._instances[exchange_name] = instance
        return instance

    @classmethod
    async def close_all(cls):
        for exchange in cls._instances.values():
            await exchange.close()
        cls._instances.clear()
