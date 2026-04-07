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

        WARNING: Singleton instances bind their aiohttp session to the event
        loop that was running at construction time.  In Celery solo-pool
        workers each ``asyncio.run()`` creates a *new* loop, so the cached
        instance's session references a **closed** loop on all subsequent
        invocations.  For Celery tasks, prefer ``create_fresh()`` which
        always returns a new, unshared instance.
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
    def create_fresh(cls, exchange_name: str) -> BaseExchange:
        """Create a **new** exchange instance every time (no caching).

        Designed for Celery solo-pool workers where each task runs inside
        its own ``asyncio.run()`` call.  A fresh instance guarantees the
        underlying aiohttp session is bound to the *current* event loop,
        preventing "Event loop is closed" errors that occur when a cached
        singleton's session references a loop from a previous
        ``asyncio.run()`` invocation.

        The caller is responsible for closing the instance (via the
        async context manager ``exchange.connect()`` or explicit
        ``await exchange.close()``).
        """
        exchange_cls = _FACTORY_REGISTRY.get(exchange_name)
        if exchange_cls is None:
            raise ValueError(
                f"Unsupported exchange: '{exchange_name}'. "
                f"Supported: {sorted(_FACTORY_REGISTRY.keys())}. "
                f"If this exchange was previously supported, it has been removed."
            )
        return exchange_cls()

    @classmethod
    def reset(cls) -> None:
        """Clear the singleton cache (sync-safe).

        Call this **before** ``asyncio.run()`` in Celery tasks to ensure
        the next ``create()`` builds a fresh instance on the new event loop.
        Does **not** close existing instances — the caller must handle
        cleanup if needed.
        """
        cls._instances.clear()

    @classmethod
    async def close_all(cls):
        for exchange in cls._instances.values():
            await exchange.close()
        cls._instances.clear()
