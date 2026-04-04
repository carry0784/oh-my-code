"""Tests for MarketDataCollector — CR-038 Phase 1."""

import sys
from unittest.mock import MagicMock, AsyncMock

# Stub external dependencies before imports
_STUB_MODULES = [
    "ccxt",
    "ccxt.async_support",
    "aiohttp",
    "celery",
    "redis",
    "sqlalchemy",
    "sqlalchemy.ext",
    "sqlalchemy.ext.asyncio",
    "sqlalchemy.orm",
    "sqlalchemy.pool",
    "sqlalchemy.engine",
    "app.core.database",
    "app.core.config",
]
for name in _STUB_MODULES:
    if name not in sys.modules:
        sys.modules[name] = MagicMock()

_fake_base = type("FakeBase", (), {"__tablename__": "", "metadata": MagicMock()})
sys.modules["app.core.database"].Base = _fake_base
sys.modules["app.core.database"].engine = MagicMock()
sys.modules["app.core.database"].async_session_factory = MagicMock()

import pytest

from app.services.market_data_collector import MarketDataCollector


def _make_mock_client(
    ticker=None,
    ohlcv=None,
    order_book=None,
    trades=None,
    funding_rate=None,
    open_interest=None,
):
    """Create a mock CCXT client with configurable responses."""
    client = MagicMock()
    client.id = "binance"
    client.has = {
        "fetchOrderBook": order_book is not None,
        "fetchTrades": trades is not None,
        "fetchFundingRate": funding_rate is not None,
        "fetchOpenInterest": open_interest is not None,
    }
    client.fetch_ticker = AsyncMock(return_value=ticker or {"last": 50000})
    client.fetch_ohlcv = AsyncMock(return_value=ohlcv or [])
    client.fetch_order_book = AsyncMock(return_value=order_book)
    client.fetch_trades = AsyncMock(return_value=trades)
    client.fetch_funding_rate = AsyncMock(return_value=funding_rate or {})
    client.fetch_open_interest = AsyncMock(return_value=open_interest or {})
    return client


class TestMarketDataCollector:
    @pytest.mark.asyncio
    async def test_collect_ticker_only(self):
        client = _make_mock_client(ticker={"last": 65000, "bid": 64999, "ask": 65001})
        collector = MarketDataCollector(client)
        result = await collector.collect("BTC/USDT")

        assert result.exchange == "binance"
        assert result.symbol == "BTC/USDT"
        assert result.ticker["last"] == 65000
        assert result.collected_at is not None

    @pytest.mark.asyncio
    async def test_collect_with_ohlcv(self):
        ohlcv = [
            [1000000, 100, 105, 95, 102, 5000],
            [1003600, 102, 108, 100, 106, 6000],
        ]
        client = _make_mock_client(ohlcv=ohlcv)
        collector = MarketDataCollector(client)
        result = await collector.collect("BTC/USDT")

        assert len(result.ohlcv) == 2
        assert result.ohlcv[0].open == 100
        assert result.ohlcv[1].close == 106

    @pytest.mark.asyncio
    async def test_collect_with_order_book(self):
        book = {"bids": [[64999, 1.5]], "asks": [[65001, 2.0]]}
        client = _make_mock_client(order_book=book)
        collector = MarketDataCollector(client)
        result = await collector.collect("BTC/USDT")

        assert result.order_book is not None
        assert "bids" in result.order_book

    @pytest.mark.asyncio
    async def test_collect_with_trades(self):
        trades = [{"price": 65000, "amount": 0.1, "side": "buy"}]
        client = _make_mock_client(trades=trades)
        collector = MarketDataCollector(client)
        result = await collector.collect("BTC/USDT")

        assert len(result.recent_trades) == 1

    @pytest.mark.asyncio
    async def test_collect_with_funding_rate(self):
        client = _make_mock_client(funding_rate={"fundingRate": 0.0001})
        collector = MarketDataCollector(client)
        result = await collector.collect("BTC/USDT")

        assert result.funding_rate == 0.0001

    @pytest.mark.asyncio
    async def test_collect_with_open_interest(self):
        client = _make_mock_client(open_interest={"openInterest": 15000.0})
        collector = MarketDataCollector(client)
        result = await collector.collect("BTC/USDT")

        assert result.open_interest == 15000.0

    @pytest.mark.asyncio
    async def test_ticker_failure_returns_none(self):
        client = _make_mock_client()
        client.fetch_ticker = AsyncMock(side_effect=Exception("timeout"))
        collector = MarketDataCollector(client)
        result = await collector.collect("BTC/USDT")

        assert result.ticker is None

    @pytest.mark.asyncio
    async def test_ohlcv_failure_returns_empty(self):
        client = _make_mock_client()
        client.fetch_ohlcv = AsyncMock(side_effect=Exception("rate limit"))
        collector = MarketDataCollector(client)
        result = await collector.collect("BTC/USDT")

        assert result.ohlcv == []

    @pytest.mark.asyncio
    async def test_unsupported_feature_returns_none(self):
        client = _make_mock_client()
        # No fetchOrderBook capability
        client.has = {
            "fetchOrderBook": False,
            "fetchTrades": False,
            "fetchFundingRate": False,
            "fetchOpenInterest": False,
        }
        collector = MarketDataCollector(client)
        result = await collector.collect("BTC/USDT")

        assert result.order_book is None
        assert result.recent_trades == []
        assert result.funding_rate is None
        assert result.open_interest is None

    @pytest.mark.asyncio
    async def test_exchange_id_extraction(self):
        client = _make_mock_client()
        client.id = "upbit"
        collector = MarketDataCollector(client)
        result = await collector.collect("BTC/KRW")

        assert result.exchange == "upbit"
