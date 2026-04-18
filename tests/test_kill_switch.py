"""Unit tests for kill_switch.py — uses fakeredis."""
from __future__ import annotations

import asyncio
import pytest

import fakeredis.aioredis

from app.services.event_bus import EventBus, TOPIC_KILL_GLOBAL, kill_topic
from app.services.kill_switch import AutoKillTriggers, KillSwitch


@pytest.fixture
async def ks_with_bus():
    """KillSwitch + EventBus both using same fakeredis client."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    bus = EventBus(client=client)
    await bus.connect()
    ks = KillSwitch(bus=bus, client=client)
    await ks.connect()
    yield ks, bus
    await ks.close()
    await bus.close()


@pytest.fixture
async def ks_only():
    """KillSwitch without an event bus (bus-less path)."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    ks = KillSwitch(client=client)
    await ks.connect()
    yield ks
    await ks.close()


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------
class TestInitialState:
    @pytest.mark.asyncio
    async def test_all_scopes_start_as_NONE(self, ks_only):
        for scope in ("global", "binance", "bitget"):
            state = await ks_only.get_state(scope)
            assert state["level"] == "NONE"

    @pytest.mark.asyncio
    async def test_entry_allowed_when_clean(self, ks_only):
        assert await ks_only.is_entry_allowed("binance") is True
        assert await ks_only.is_entry_allowed("bitget") is True


# ---------------------------------------------------------------------------
# Trigger + state transition
# ---------------------------------------------------------------------------
class TestTrigger:
    @pytest.mark.asyncio
    async def test_soft_trigger_blocks_entry_on_scope(self, ks_only):
        await ks_only.trigger("SOFT", scope="binance", reason="dd_2pct", by="auto")
        assert await ks_only.current_level("binance") == "SOFT"
        assert await ks_only.is_entry_allowed("binance") is False
        # Other venue not affected
        assert await ks_only.is_entry_allowed("bitget") is True

    @pytest.mark.asyncio
    async def test_global_soft_blocks_both_venues(self, ks_only):
        await ks_only.trigger("SOFT", scope="global", reason="dd_global", by="auto")
        assert await ks_only.is_entry_allowed("binance") is False
        assert await ks_only.is_entry_allowed("bitget") is False

    @pytest.mark.asyncio
    async def test_hard_triggers_force_close(self, ks_only):
        await ks_only.trigger("HARD", scope="bitget", reason="dd_5pct", by="auto")
        assert await ks_only.is_force_close_required("bitget") is True
        assert await ks_only.is_force_close_required("binance") is False
        # Global hard affects all venues
        await ks_only.trigger("HARD", scope="global", reason="dd_5pct_global", by="auto")
        assert await ks_only.is_force_close_required("binance") is True
        assert await ks_only.is_force_close_required("bitget") is True

    @pytest.mark.asyncio
    async def test_soft_does_not_require_force_close(self, ks_only):
        await ks_only.trigger("SOFT", scope="binance", reason="dd_2pct", by="auto")
        assert await ks_only.is_force_close_required("binance") is False

    @pytest.mark.asyncio
    async def test_higher_level_supersedes_lower(self, ks_only):
        await ks_only.trigger("SOFT", scope="binance", reason="r1", by="auto")
        ev = await ks_only.trigger("HARD", scope="binance", reason="r2", by="auto")
        assert ev.level == "HARD"
        assert await ks_only.current_level("binance") == "HARD"

    @pytest.mark.asyncio
    async def test_lower_level_from_auto_is_ignored(self, ks_only):
        await ks_only.trigger("HARD", scope="binance", reason="r1", by="auto")
        await ks_only.trigger("SOFT", scope="binance", reason="r2", by="auto")
        # Remains HARD
        assert await ks_only.current_level("binance") == "HARD"

    @pytest.mark.asyncio
    async def test_operator_can_override_downgrade(self, ks_only):
        """Operator can manually set a lower level (for testing / debug)."""
        await ks_only.trigger("HARD", scope="binance", reason="r1", by="auto")
        ev = await ks_only.trigger("SOFT", scope="binance", reason="debug", by="operator")
        assert ev.level == "SOFT"
        assert await ks_only.current_level("binance") == "SOFT"

    @pytest.mark.asyncio
    async def test_invalid_level_raises(self, ks_only):
        with pytest.raises(ValueError):
            await ks_only.trigger("NONE", scope="global", reason="nope")
        with pytest.raises(ValueError):
            await ks_only.trigger("MAYBE", scope="global", reason="?")


# ---------------------------------------------------------------------------
# Release
# ---------------------------------------------------------------------------
class TestRelease:
    @pytest.mark.asyncio
    async def test_release_restores_entry(self, ks_only):
        await ks_only.trigger("SOFT", scope="binance", reason="x")
        assert await ks_only.is_entry_allowed("binance") is False
        await ks_only.release(scope="binance", by="operator")
        assert await ks_only.is_entry_allowed("binance") is True

    @pytest.mark.asyncio
    async def test_release_only_affects_specified_scope(self, ks_only):
        await ks_only.trigger("HARD", scope="global", reason="x")
        await ks_only.trigger("SOFT", scope="binance", reason="y")
        await ks_only.release(scope="binance", by="operator")
        # binance cleared
        assert await ks_only.current_level("binance") == "NONE"
        # global still HARD → entry still blocked
        assert await ks_only.is_entry_allowed("binance") is False

    @pytest.mark.asyncio
    async def test_release_no_prior_trigger_is_noop(self, ks_only):
        ev = await ks_only.release(scope="bitget", by="operator")
        assert ev.level == "NONE"
        assert await ks_only.current_level("bitget") == "NONE"


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------
class TestHistory:
    @pytest.mark.asyncio
    async def test_history_captures_triggers_and_releases(self, ks_only):
        await ks_only.trigger("SOFT", scope="binance", reason="r1", by="auto")
        await ks_only.trigger("HARD", scope="binance", reason="r2", by="auto")
        await ks_only.release(scope="binance", by="operator")

        snap = await ks_only.snapshot()
        hist = snap["recent_history"]
        assert len(hist) == 3
        # Newest-first (LPUSH)
        assert hist[0]["level"] == "NONE"  # release
        assert hist[1]["level"] == "HARD"
        assert hist[2]["level"] == "SOFT"


# ---------------------------------------------------------------------------
# Event Bus integration
# ---------------------------------------------------------------------------
class TestBusIntegration:
    @pytest.mark.asyncio
    async def test_trigger_publishes_to_event_bus(self, ks_with_bus):
        ks, bus = ks_with_bus
        received = []

        async def cb(topic, payload):
            received.append((topic, payload))

        bus.subscribe([kill_topic("binance")], cb)
        await bus.start_listening()
        await asyncio.sleep(0.05)

        await ks.trigger("SOFT", scope="binance", reason="dd_2pct", by="auto")

        for _ in range(50):
            if received:
                break
            await asyncio.sleep(0.02)

        assert len(received) == 1
        topic, payload = received[0]
        assert topic == kill_topic("binance")
        assert payload["level"] == "SOFT"
        assert payload["scope"] == "binance"

    @pytest.mark.asyncio
    async def test_global_trigger_publishes_to_global_topic(self, ks_with_bus):
        ks, bus = ks_with_bus
        received = []

        async def cb(topic, payload):
            received.append((topic, payload))

        bus.subscribe([TOPIC_KILL_GLOBAL], cb)
        await bus.start_listening()
        await asyncio.sleep(0.05)

        await ks.trigger("HARD", scope="global", reason="dd_5pct", by="auto")

        for _ in range(50):
            if received:
                break
            await asyncio.sleep(0.02)

        assert len(received) == 1
        assert received[0][1]["level"] == "HARD"


# ---------------------------------------------------------------------------
# Auto-triggers
# ---------------------------------------------------------------------------
class TestAutoKillTriggers:
    def test_decide_level_none_when_profitable(self):
        assert AutoKillTriggers.decide_level(0.05) == "NONE"
        assert AutoKillTriggers.decide_level(0.0) == "NONE"

    def test_decide_level_soft_at_minus_2_pct(self):
        assert AutoKillTriggers.decide_level(-0.02) == "SOFT"
        assert AutoKillTriggers.decide_level(-0.025) == "SOFT"

    def test_decide_level_hard_at_minus_5_pct(self):
        assert AutoKillTriggers.decide_level(-0.05) == "HARD"
        assert AutoKillTriggers.decide_level(-0.10) == "HARD"

    def test_just_above_threshold_is_none(self):
        assert AutoKillTriggers.decide_level(-0.019) == "NONE"
