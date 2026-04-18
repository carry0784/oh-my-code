"""Unit tests for event_bus.py — using fakeredis (no real Redis needed)."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

import fakeredis.aioredis
import pytest

from app.services.event_bus import (
    DivergenceEvent,
    EventBus,
    KillEvent,
    SignalEvent,
    SpikeEvent,
    TOPIC_DIVERGENCE,
    TOPIC_KILL_GLOBAL,
    TOPIC_SIGNAL,
    TOPIC_TICK_BINANCE,
    _serialize,
    kill_topic,
    spike_topic,
    tick_topic,
)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------
@pytest.fixture
async def bus():
    """EventBus using fakeredis (no network)."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    b = EventBus(client=client)
    await b.connect()
    yield b
    await b.close()


# ---------------------------------------------------------------------------
# Topic helpers
# ---------------------------------------------------------------------------
class TestTopicHelpers:
    def test_tick_topic(self):
        assert tick_topic("binance") == "events:binance:tick"
        assert tick_topic("bitget") == "events:bitget:tick"

    def test_kill_topic(self):
        assert kill_topic("binance") == "events:binance:kill"
        assert kill_topic("global") == "events:global:kill"

    def test_spike_topic(self):
        assert spike_topic("binance") == "events:binance:spike"

    def test_constants_match_helpers(self):
        assert TOPIC_TICK_BINANCE == tick_topic("binance")
        assert TOPIC_KILL_GLOBAL == kill_topic("global")


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------
class TestSerialization:
    def test_serialize_dict(self):
        s = _serialize({"a": 1, "b": "x"})
        assert json.loads(s) == {"a": 1, "b": "x"}

    def test_serialize_dataclass(self):
        ev = KillEvent(level="HARD", scope="global", reason="test", ts_ms=123)
        s = _serialize(ev)
        d = json.loads(s)
        assert d["level"] == "HARD"
        assert d["scope"] == "global"
        assert d["reason"] == "test"
        assert d["ts_ms"] == 123

    def test_serialize_primitive(self):
        assert _serialize(42) == "42"
        assert _serialize("hello") == '"hello"'
        assert _serialize(True) == "true"


# ---------------------------------------------------------------------------
# Publish / subscribe end-to-end with fakeredis
# ---------------------------------------------------------------------------
class TestPublishSubscribe:
    @pytest.mark.asyncio
    async def test_publish_with_no_subscribers_returns_zero(self, bus):
        n = await bus.publish(TOPIC_TICK_BINANCE, {"test": 1})
        assert n == 0

    @pytest.mark.asyncio
    async def test_exact_channel_subscribe_receives_message(self, bus):
        received = []

        async def cb(topic, payload):
            received.append((topic, payload))

        bus.subscribe([TOPIC_TICK_BINANCE], cb)
        await bus.start_listening()

        # Give the subscriber a moment to register
        await asyncio.sleep(0.05)

        n = await bus.publish(TOPIC_TICK_BINANCE, {"canonical": "BTC/USDT", "price": 75000})
        assert n == 1

        # Wait for delivery
        for _ in range(50):
            if received:
                break
            await asyncio.sleep(0.02)

        assert len(received) == 1
        topic, payload = received[0]
        assert topic == TOPIC_TICK_BINANCE
        assert payload["canonical"] == "BTC/USDT"
        assert payload["price"] == 75000

    @pytest.mark.asyncio
    async def test_pattern_subscribe_receives_multiple_topics(self, bus):
        received = []

        async def cb(topic, payload):
            received.append((topic, payload))

        bus.psubscribe("events:*:tick", cb)
        await bus.start_listening()
        await asyncio.sleep(0.05)

        await bus.publish(tick_topic("binance"), {"canonical": "BTC/USDT"})
        await bus.publish(tick_topic("bitget"), {"canonical": "BTC/USDT"})
        await bus.publish(TOPIC_KILL_GLOBAL, {"level": "HARD"})  # should NOT match

        for _ in range(100):
            if len(received) >= 2:
                break
            await asyncio.sleep(0.02)

        channels = {r[0] for r in received}
        assert tick_topic("binance") in channels
        assert tick_topic("bitget") in channels
        assert TOPIC_KILL_GLOBAL not in channels

    @pytest.mark.asyncio
    async def test_sync_and_async_callbacks_both_fire(self, bus):
        sync_hits = []
        async_hits = []

        def sync_cb(topic, payload):
            sync_hits.append(payload)

        async def async_cb(topic, payload):
            async_hits.append(payload)

        bus.subscribe([TOPIC_TICK_BINANCE], sync_cb)
        bus.subscribe([TOPIC_TICK_BINANCE], async_cb)
        await bus.start_listening()
        await asyncio.sleep(0.05)

        await bus.publish(TOPIC_TICK_BINANCE, {"x": 1})

        for _ in range(50):
            if sync_hits and async_hits:
                break
            await asyncio.sleep(0.02)

        assert len(sync_hits) == 1
        assert len(async_hits) == 1

    @pytest.mark.asyncio
    async def test_dataclass_publish_round_trip(self, bus):
        received = []

        async def cb(topic, payload):
            received.append(payload)

        bus.subscribe([TOPIC_KILL_GLOBAL], cb)
        await bus.start_listening()
        await asyncio.sleep(0.05)

        ev = KillEvent(level="HARD", scope="global", reason="auto_dd_5pct", ts_ms=1_776_000_000_000)
        await bus.publish(TOPIC_KILL_GLOBAL, ev)

        for _ in range(50):
            if received:
                break
            await asyncio.sleep(0.02)

        assert len(received) == 1
        payload = received[0]
        assert payload["level"] == "HARD"
        assert payload["scope"] == "global"
        assert payload["reason"] == "auto_dd_5pct"
        assert payload["ts_ms"] == 1_776_000_000_000

    @pytest.mark.asyncio
    async def test_divergence_event_round_trip(self, bus):
        received = []

        async def cb(topic, payload):
            received.append(payload)

        bus.subscribe([TOPIC_DIVERGENCE], cb)
        await bus.start_listening()
        await asyncio.sleep(0.05)

        ev = DivergenceEvent(
            canonical="BTC/USDT", price_binance=75000.0, price_bitget=74500.0,
            diff_pct=0.667, threshold_pct=0.2, ts_ms=1_776_000_000_000,
        )
        await bus.publish(TOPIC_DIVERGENCE, ev)

        for _ in range(50):
            if received:
                break
            await asyncio.sleep(0.02)

        assert len(received) == 1
        p = received[0]
        assert p["canonical"] == "BTC/USDT"
        assert p["diff_pct"] == 0.667

    @pytest.mark.asyncio
    async def test_callback_error_does_not_break_listener(self, bus):
        good_hits = []

        def bad_cb(topic, payload):
            raise RuntimeError("boom")

        async def good_cb(topic, payload):
            good_hits.append(payload)

        bus.subscribe([TOPIC_TICK_BINANCE], bad_cb)
        bus.subscribe([TOPIC_TICK_BINANCE], good_cb)
        await bus.start_listening()
        await asyncio.sleep(0.05)

        await bus.publish(TOPIC_TICK_BINANCE, {"n": 1})
        await bus.publish(TOPIC_TICK_BINANCE, {"n": 2})

        for _ in range(100):
            if len(good_hits) >= 2:
                break
            await asyncio.sleep(0.02)

        assert len(good_hits) == 2  # bad_cb error must not drop messages for good_cb


# ---------------------------------------------------------------------------
# Lifecycle errors
# ---------------------------------------------------------------------------
class TestLifecycle:
    @pytest.mark.asyncio
    async def test_publish_without_connect_raises(self):
        b = EventBus(client=None)  # not connected
        with pytest.raises(RuntimeError):
            await b.publish("x", {})

    @pytest.mark.asyncio
    async def test_start_listening_without_subscriptions_raises(self, bus):
        with pytest.raises(RuntimeError, match="no subscriptions"):
            await bus.start_listening()

    @pytest.mark.asyncio
    async def test_start_listening_twice_raises(self, bus):
        bus.subscribe([TOPIC_TICK_BINANCE], lambda t, p: None)
        await bus.start_listening()
        with pytest.raises(RuntimeError, match="already listening"):
            await bus.start_listening()
