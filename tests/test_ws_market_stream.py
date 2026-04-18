"""Unit tests for ws_market_stream.py (mocked — no network)."""
from __future__ import annotations

import asyncio
import json
import pytest

from app.services.ws_market_stream import (
    BinanceStream,
    BitgetStream,
    MultiVenueStream,
    TickEvent,
    VenueStream,
)


# ---------------------------------------------------------------------------
# Binance message parser (exercise without real WS)
# ---------------------------------------------------------------------------
class TestBinanceStreamParser:
    @pytest.mark.asyncio
    async def test_parse_trade_message(self):
        stream = BinanceStream(["BTC/USDT"])
        received: list[TickEvent] = []

        async def collect(ev: TickEvent) -> None:
            received.append(ev)

        stream.on_tick(collect)

        # Official Binance spot trade format
        msg = json.dumps({
            "stream": "btcusdt@trade",
            "data": {
                "e": "trade", "E": 1776000000000, "s": "BTCUSDT",
                "t": 123, "p": "75000.50", "q": "0.0123",
                "T": 1776000000000, "m": False,
            },
        })
        await stream._handle_text(msg)

        assert len(received) == 1
        ev = received[0]
        assert ev.venue == "binance"
        assert ev.canonical == "BTC/USDT"
        assert ev.event_kind == "trade"
        assert ev.price == 75000.50
        assert ev.quantity == 0.0123
        assert ev.ts_ms == 1776000000000

    @pytest.mark.asyncio
    async def test_parse_book_ticker(self):
        stream = BinanceStream(["ETH/USDT"])
        received: list[TickEvent] = []

        async def collect(ev): received.append(ev)
        stream.on_tick(collect)

        msg = json.dumps({
            "stream": "ethusdt@bookTicker",
            "data": {
                "u": 999, "s": "ETHUSDT",
                "b": "2328.69", "B": "1.0",
                "a": "2328.70", "A": "1.0",
            },
        })
        await stream._handle_text(msg)

        assert len(received) == 1
        ev = received[0]
        assert ev.event_kind == "book"
        assert ev.bid == 2328.69
        assert ev.ask == 2328.70
        assert ev.canonical == "ETH/USDT"

    @pytest.mark.asyncio
    async def test_ignores_unknown_symbol(self):
        stream = BinanceStream(["BTC/USDT"])
        received = []
        stream.on_tick(lambda ev: received.append(ev))

        msg = json.dumps({
            "stream": "unknownusdt@trade",
            "data": {"s": "UNKNOWNUSDT", "p": "1", "q": "1", "T": 0},
        })
        await stream._handle_text(msg)
        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_ignores_malformed_json(self):
        stream = BinanceStream(["BTC/USDT"])
        await stream._handle_text("not valid json {{{")
        # Should not raise; no event emitted

    def test_url_includes_requested_symbols(self):
        stream = BinanceStream(["BTC/USDT", "ETH/USDT"])
        url = stream.url
        assert "btcusdt@trade" in url
        assert "btcusdt@bookTicker" in url
        assert "ethusdt@trade" in url
        assert "ethusdt@bookTicker" in url


# ---------------------------------------------------------------------------
# Bitget message parser
# ---------------------------------------------------------------------------
class TestBitgetStreamParser:
    @pytest.mark.asyncio
    async def test_parse_trade(self):
        stream = BitgetStream(["BTC/USDT"])
        received = []
        stream.on_tick(lambda ev: received.append(ev))

        msg = json.dumps({
            "action": "snapshot",
            "arg": {"instType": "SPOT", "channel": "trade", "instId": "BTCUSDT"},
            "data": [{"ts": "1776000000000", "price": "74397.14", "size": "0.5", "side": "buy"}],
            "ts": 1776000000000,
        })
        await stream._handle_text(msg)
        assert len(received) == 1
        ev = received[0]
        assert ev.venue == "bitget"
        assert ev.canonical == "BTC/USDT"
        assert ev.event_kind == "trade"
        assert ev.price == 74397.14
        assert ev.quantity == 0.5

    @pytest.mark.asyncio
    async def test_parse_books5(self):
        stream = BitgetStream(["BTC/USDT"])
        received = []
        stream.on_tick(lambda ev: received.append(ev))

        msg = json.dumps({
            "action": "snapshot",
            "arg": {"instType": "SPOT", "channel": "books5", "instId": "BTCUSDT"},
            "data": [{
                "bids": [["74397.14", "0.1"], ["74397.13", "0.2"]],
                "asks": [["74397.15", "0.1"], ["74397.16", "0.2"]],
                "ts": "1776000000000",
            }],
            "ts": 1776000000000,
        })
        await stream._handle_text(msg)
        assert len(received) == 1
        ev = received[0]
        assert ev.event_kind == "book"
        assert ev.bid == 74397.14
        assert ev.ask == 74397.15

    @pytest.mark.asyncio
    async def test_ignores_subscribe_ack(self):
        stream = BitgetStream(["BTC/USDT"])
        received = []
        stream.on_tick(lambda ev: received.append(ev))

        msg = json.dumps({"event": "subscribe", "arg": {"channel": "trade", "instId": "BTCUSDT"}})
        await stream._handle_text(msg)
        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_ignores_pong(self):
        stream = BitgetStream(["BTC/USDT"])
        received = []
        stream.on_tick(lambda ev: received.append(ev))
        await stream._handle_text("pong")
        assert len(received) == 0

    def test_subscribe_args_format(self):
        stream = BitgetStream(["BTC/USDT", "ETH/USDT"])
        args = stream._subscribe_args()
        # 2 symbols × 2 channels = 4
        assert len(args) == 4
        assert {"instType": "SPOT", "channel": "trade", "instId": "BTCUSDT"} in args
        assert {"instType": "SPOT", "channel": "books5", "instId": "ETHUSDT"} in args


# ---------------------------------------------------------------------------
# Callback dispatch + stats
# ---------------------------------------------------------------------------
class TestDispatch:
    @pytest.mark.asyncio
    async def test_multiple_callbacks_both_fire(self):
        stream = BinanceStream(["BTC/USDT"])
        hits_a = []
        hits_b = []
        stream.on_tick(lambda ev: hits_a.append(ev))

        async def async_cb(ev): hits_b.append(ev)
        stream.on_tick(async_cb)

        msg = json.dumps({
            "stream": "btcusdt@trade",
            "data": {"e": "trade", "s": "BTCUSDT", "p": "1", "q": "1", "T": 0},
        })
        await stream._handle_text(msg)
        assert len(hits_a) == 1
        assert len(hits_b) == 1

    @pytest.mark.asyncio
    async def test_callback_error_does_not_break_stream(self):
        stream = BinanceStream(["BTC/USDT"])
        ok_hits = []

        def bad(ev): raise RuntimeError("boom")
        def good(ev): ok_hits.append(ev)

        stream.on_tick(bad)
        stream.on_tick(good)

        msg = json.dumps({
            "stream": "btcusdt@trade",
            "data": {"e": "trade", "s": "BTCUSDT", "p": "1", "q": "1", "T": 0},
        })
        # Should not raise
        await stream._handle_text(msg)
        assert len(ok_hits) == 1

    def test_stats_shape(self):
        stream = BinanceStream(["BTC/USDT"])
        s = stream.stats()
        assert s["venue"] == "binance"
        assert s["running"] is False
        assert s["canonicals"] == 1
        assert s["messages_received"] == 0


# ---------------------------------------------------------------------------
# MultiVenue
# ---------------------------------------------------------------------------
class TestMultiVenue:
    def test_both_venues_created(self):
        m = MultiVenueStream(["BTC/USDT"])
        assert "binance" in m.streams
        assert "bitget" in m.streams

    def test_single_venue_filter(self):
        m = MultiVenueStream(["BTC/USDT"], venues=["binance"])
        assert "binance" in m.streams
        assert "bitget" not in m.streams

    def test_unsupported_venue_raises(self):
        with pytest.raises(ValueError):
            MultiVenueStream(["BTC/USDT"], venues=["coinbase"])

    @pytest.mark.asyncio
    async def test_shared_callback(self):
        m = MultiVenueStream(["BTC/USDT"])
        received = []
        m.on_tick(lambda ev: received.append(ev))

        # Hand-deliver a message to each venue
        msg_bn = json.dumps({
            "stream": "btcusdt@trade",
            "data": {"e": "trade", "s": "BTCUSDT", "p": "1", "q": "1", "T": 0},
        })
        await m.streams["binance"]._handle_text(msg_bn)

        msg_bg = json.dumps({
            "arg": {"channel": "trade", "instId": "BTCUSDT"},
            "data": [{"price": "2", "size": "2", "ts": "0"}],
            "ts": 0,
        })
        await m.streams["bitget"]._handle_text(msg_bg)

        assert len(received) == 2
        venues = {ev.venue for ev in received}
        assert venues == {"binance", "bitget"}
