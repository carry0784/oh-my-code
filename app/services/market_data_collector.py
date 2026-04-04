"""
MarketDataCollector — CR-038 Phase 1
Extended CCXT data collection: ticker, OHLCV, order book, recent trades,
funding rate, and open interest.
Read-only service — never places orders or modifies exchange state.
"""

from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger
from app.schemas.market_state_schema import (
    MarketDataCollectionResult,
    OHLCVBar,
)

logger = get_logger(__name__)


class MarketDataCollector:
    """Collects extended market data from a CCXT exchange client."""

    def __init__(self, exchange_client: Any):
        self.client = exchange_client

    async def collect(
        self,
        symbol: str,
        ohlcv_timeframe: str = "1h",
        ohlcv_limit: int = 200,
        order_book_limit: int = 20,
        trades_limit: int = 50,
    ) -> MarketDataCollectionResult:
        """Collect all available market data for a symbol."""
        now = datetime.now(timezone.utc)
        result = MarketDataCollectionResult(
            exchange=self._exchange_id(),
            symbol=symbol,
            collected_at=now,
        )

        # Parallel-safe: each fetch is independent, but we run sequentially
        # to respect exchange rate limits (CCXT enableRateLimit=True)
        result.ticker = await self._fetch_ticker(symbol)
        result.ohlcv = await self._fetch_ohlcv(symbol, ohlcv_timeframe, ohlcv_limit)
        result.order_book = await self._fetch_order_book(symbol, order_book_limit)
        result.recent_trades = await self._fetch_recent_trades(symbol, trades_limit)
        result.funding_rate = await self._fetch_funding_rate(symbol)
        result.open_interest = await self._fetch_open_interest(symbol)

        logger.info(
            "market_data_collected",
            exchange=result.exchange,
            symbol=symbol,
            has_ticker=result.ticker is not None,
            ohlcv_bars=len(result.ohlcv),
            has_order_book=result.order_book is not None,
            trades_count=len(result.recent_trades),
            has_funding=result.funding_rate is not None,
            has_oi=result.open_interest is not None,
        )
        return result

    def _exchange_id(self) -> str:
        return getattr(self.client, "id", "unknown")

    async def _fetch_ticker(self, symbol: str) -> dict[str, Any] | None:
        try:
            return await self.client.fetch_ticker(symbol)
        except Exception as e:
            logger.warning("ticker_fetch_failed", symbol=symbol, error=str(e))
            return None

    async def _fetch_ohlcv(self, symbol: str, timeframe: str, limit: int) -> list[OHLCVBar]:
        try:
            raw = await self.client.fetch_ohlcv(symbol, timeframe, limit=limit)
            return [
                OHLCVBar(
                    timestamp=int(bar[0]),
                    open=float(bar[1]),
                    high=float(bar[2]),
                    low=float(bar[3]),
                    close=float(bar[4]),
                    volume=float(bar[5]),
                )
                for bar in raw
            ]
        except Exception as e:
            logger.warning("ohlcv_fetch_failed", symbol=symbol, error=str(e))
            return []

    async def _fetch_order_book(self, symbol: str, limit: int) -> dict[str, Any] | None:
        try:
            if not self.client.has.get("fetchOrderBook", False):
                return None
            return await self.client.fetch_order_book(symbol, limit)
        except Exception as e:
            logger.warning("order_book_fetch_failed", symbol=symbol, error=str(e))
            return None

    async def _fetch_recent_trades(self, symbol: str, limit: int) -> list[dict[str, Any]]:
        try:
            if not self.client.has.get("fetchTrades", False):
                return []
            return await self.client.fetch_trades(symbol, limit=limit)
        except Exception as e:
            logger.warning("trades_fetch_failed", symbol=symbol, error=str(e))
            return []

    async def _fetch_funding_rate(self, symbol: str) -> float | None:
        try:
            if not self.client.has.get("fetchFundingRate", False):
                return None
            data = await self.client.fetch_funding_rate(symbol)
            return data.get("fundingRate")
        except Exception as e:
            logger.debug("funding_rate_not_available", symbol=symbol, error=str(e))
            return None

    async def _fetch_open_interest(self, symbol: str) -> float | None:
        try:
            if not self.client.has.get("fetchOpenInterest", False):
                return None
            data = await self.client.fetch_open_interest(symbol)
            return data.get("openInterest") or data.get("openInterestAmount")
        except Exception as e:
            logger.debug("open_interest_not_available", symbol=symbol, error=str(e))
            return None
