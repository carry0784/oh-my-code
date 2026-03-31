from exchanges.base import BaseExchange
from exchanges.binance import BinanceExchange
from exchanges.upbit import UpBitExchange
from exchanges.bitget import BitgetExchange
from exchanges.kis import KISExchange
from exchanges.kiwoom import KiwoomExchange

# Supported exchanges (must match app.core.config SSOT)
_FACTORY_REGISTRY: dict[str, type] = {
    "binance": BinanceExchange,
    "upbit": UpBitExchange,
    "bitget": BitgetExchange,
    "kis": KISExchange,
    "kiwoom": KiwoomExchange,
}


class ExchangeFactory:
    _instances: dict[str, BaseExchange] = {}

    @classmethod
    def create(cls, exchange_name: str) -> BaseExchange:
        """Create or return cached exchange instance.

        Idempotent: returns cached singleton for the same exchange key.
        Safe to call multiple times — only the first call creates an instance.
        Raises ValueError for unsupported exchanges (fail-closed).
        """
        if exchange_name in cls._instances:
            return cls._instances[exchange_name]

        exchange_cls = _FACTORY_REGISTRY.get(exchange_name)
        if exchange_cls is None:
            raise ValueError(
                f"Unsupported exchange: '{exchange_name}'. "
                f"Supported: {sorted(_FACTORY_REGISTRY.keys())}. "
                f"If this exchange was previously supported, it has been removed."
            )

        instance = exchange_cls()
        cls._instances[exchange_name] = instance
        return instance

    @classmethod
    async def close_all(cls):
        for exchange in cls._instances.values():
            await exchange.close()
        cls._instances.clear()
