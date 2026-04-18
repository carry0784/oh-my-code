"""
Event Bus — Card B-8 v1.1

Redis Pub/Sub wrapper for system-wide event distribution.

Design:
  - Topic namespace:
      events:{venue}:tick              — individual ticks (very high volume)
      events:{venue}:divergence        — cross-venue price gap warnings
      events:{venue}:spike             — volume / price spike detections
      events:{venue}:kill              — venue-specific kill switch
      events:global:kill               — global kill switch
      events:global:top3               — Top-3 re-ranking
      events:global:signal             — strategy entry signal (ready to route)
      events:global:order              — order placed / filled / cancelled
      events:global:position_close     — position exited
  - All messages are JSON-serialized
  - Publisher: `EventBus.publish(topic, payload)`
  - Subscriber: `EventBus.subscribe([topics], callback)`
  - Pattern subscribe: `EventBus.psubscribe("events:*:tick", cb)`
  - Supports both real Redis and fakeredis for tests
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
from dataclasses import dataclass, is_dataclass
from typing import Any, Awaitable, Callable, Iterable

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Topic constants
# ---------------------------------------------------------------------------
TOPIC_TICK_BINANCE = "events:binance:tick"
TOPIC_TICK_BITGET = "events:bitget:tick"
TOPIC_DIVERGENCE = "events:global:divergence"
TOPIC_SPIKE_TEMPLATE = "events:{venue}:spike"
TOPIC_KILL_GLOBAL = "events:global:kill"
TOPIC_KILL_TEMPLATE = "events:{venue}:kill"
TOPIC_TOP3 = "events:global:top3"
TOPIC_SIGNAL = "events:global:signal"
TOPIC_ORDER = "events:global:order"
TOPIC_POSITION_CLOSE = "events:global:position_close"
# 22Z observation alert channel (Review 21). NOT a doctrine extension: this
# topic carries *external notification* of observation events whose authority
# source remains the 22Z canonical system_state + exit_dashboard_checklist_v1.
# Telegram success/failure never mutates adjudication state.
TOPIC_OBSERVATION = "events:global:observation"

# Pattern subscriptions
PATTERN_ALL_TICKS = "events:*:tick"
PATTERN_ALL_KILLS = "events:*:kill"


def tick_topic(venue: str) -> str:
    return f"events:{venue}:tick"


def kill_topic(venue: str) -> str:
    return f"events:{venue}:kill"


def spike_topic(venue: str) -> str:
    return TOPIC_SPIKE_TEMPLATE.format(venue=venue)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------
def _serialize(payload: Any) -> str:
    """Serialize payload to JSON. Supports dataclasses."""
    if is_dataclass(payload) and not isinstance(payload, type):
        return json.dumps(dataclasses.asdict(payload), default=str)
    if isinstance(payload, (dict, list, str, int, float, bool)) or payload is None:
        return json.dumps(payload, default=str)
    # Fallback: try __dict__
    if hasattr(payload, "__dict__"):
        return json.dumps(payload.__dict__, default=str)
    return json.dumps(str(payload))


# ---------------------------------------------------------------------------
# Subscription callback type
# ---------------------------------------------------------------------------
Callback = Callable[[str, dict], Awaitable[None] | None]  # (topic, payload_dict) → ...


# ---------------------------------------------------------------------------
# Event Bus
# ---------------------------------------------------------------------------
class EventBus:
    """Redis Pub/Sub wrapper.

    Usage:
        bus = EventBus()
        await bus.connect()
        await bus.publish("events:binance:tick", {"canonical": "BTC/USDT", ...})
        await bus.subscribe(["events:binance:tick"], my_callback)
        await bus.close()
    """

    def __init__(self, redis_url: str | None = None, client=None):
        """Construct an EventBus.

        Args:
            redis_url: URL like redis://localhost:6379/3. Defaults to settings.redis_url.
            client: Pre-constructed redis client (for tests with fakeredis).
                    When provided, redis_url is ignored.
        """
        self._url = redis_url or settings.redis_url
        self._client = client
        self._pubsub = None
        self._subscriber_task: asyncio.Task | None = None
        self._callbacks: list[tuple[str, Callback, bool]] = []  # (channel, cb, is_pattern)

    # ---- Lifecycle ----
    async def connect(self) -> None:
        if self._client is None:
            self._client = aioredis.from_url(self._url, decode_responses=True)
        # Health check
        try:
            await self._client.ping()
        except Exception as exc:
            logger.error("event_bus_ping_failed", url=self._url, error=str(exc))
            raise

    async def close(self) -> None:
        # Stop subscriber
        if self._subscriber_task:
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except (asyncio.CancelledError, Exception):
                pass
            self._subscriber_task = None
        # Close pubsub
        if self._pubsub:
            try:
                # redis>=5 prefers aclose; fall back to close for older stubs
                close_fn = getattr(self._pubsub, "aclose", None) or self._pubsub.close
                await close_fn()
            except Exception:
                pass
            self._pubsub = None
        # Close client
        if self._client:
            try:
                await self._client.aclose()
            except Exception:
                pass

    # ---- Publisher ----
    async def publish(self, topic: str, payload: Any) -> int:
        """Publish payload (dataclass/dict/primitive) to topic.

        Returns number of subscribers that received the message.
        """
        if self._client is None:
            raise RuntimeError("EventBus not connected — call connect() first")
        data = _serialize(payload)
        return await self._client.publish(topic, data)

    # ---- Subscriber (channel-based) ----
    def subscribe(self, topics: Iterable[str], callback: Callback) -> None:
        """Register a callback for one or more exact topic channels.

        Subscriptions are batched and applied when `start_listening()` is called.
        """
        for t in topics:
            self._callbacks.append((t, callback, False))

    def psubscribe(self, pattern: str, callback: Callback) -> None:
        """Register a callback for a channel pattern (e.g. events:*:tick)."""
        self._callbacks.append((pattern, callback, True))

    async def start_listening(self) -> None:
        """Begin listening for all registered subscriptions.

        Starts a background task. Safe to call only once per EventBus instance.
        """
        if self._subscriber_task is not None:
            raise RuntimeError("already listening")
        if not self._callbacks:
            raise RuntimeError("no subscriptions registered; call subscribe() first")

        self._pubsub = self._client.pubsub()
        channels = [c for c, _, is_p in self._callbacks if not is_p]
        patterns = [c for c, _, is_p in self._callbacks if is_p]
        if channels:
            await self._pubsub.subscribe(*channels)
        if patterns:
            await self._pubsub.psubscribe(*patterns)

        self._subscriber_task = asyncio.create_task(
            self._listener_loop(), name="event-bus-listener"
        )

    async def _listener_loop(self) -> None:
        try:
            async for msg in self._pubsub.listen():
                msg_type = msg.get("type")
                if msg_type not in ("message", "pmessage"):
                    continue
                channel = msg.get("channel")
                data_raw = msg.get("data")
                if data_raw is None:
                    continue
                try:
                    payload = json.loads(data_raw) if isinstance(data_raw, str) else data_raw
                except Exception:
                    payload = {"_raw": str(data_raw)}

                # Find matching callbacks
                for sub_channel, cb, is_pattern in self._callbacks:
                    if is_pattern:
                        if msg_type == "pmessage" and msg.get("pattern") == sub_channel:
                            await self._invoke(cb, channel, payload)
                    else:
                        if msg_type == "message" and channel == sub_channel:
                            await self._invoke(cb, channel, payload)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("event_bus_listener_error", error=str(exc))
            raise

    @staticmethod
    async def _invoke(cb: Callback, channel: str, payload: dict) -> None:
        try:
            res = cb(channel, payload)
            if asyncio.iscoroutine(res):
                await res
        except Exception as exc:
            logger.error("event_bus_callback_error", channel=channel, error=str(exc)[:200])


# ---------------------------------------------------------------------------
# Common event payload helpers
# ---------------------------------------------------------------------------
@dataclass
class KillEvent:
    """Kill switch event payload."""
    level: str                     # "SOFT" | "HARD" | "MANUAL"
    scope: str                     # "global" | "binance" | "bitget"
    reason: str                    # human-readable
    ts_ms: int
    triggered_by: str = "system"   # "system" | "operator" | "auto_dd" etc.


@dataclass
class DivergenceEvent:
    """Cross-venue price divergence."""
    canonical: str
    price_binance: float
    price_bitget: float
    diff_pct: float
    threshold_pct: float
    ts_ms: int


@dataclass
class SpikeEvent:
    """Volume or price spike."""
    venue: str
    canonical: str
    kind: str                      # "volume" | "price"
    magnitude: float               # e.g. 10.5× for volume spike
    ts_ms: int


@dataclass
class SignalEvent:
    """Strategy entry signal ready for routing."""
    canonical: str
    direction: str                 # "LONG" | "SHORT"
    strategy_key: str
    venue_hint: str | None         # suggested venue (None = router decides)
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float
    ts_ms: int
    metadata: dict | None = None


@dataclass
class ObservationEvent:
    """22Z observation alert payload (Review 21 운영 알림 채널).

    Authority: 22Z canonical system_state + exit_dashboard_checklist_v1.md.
    This dataclass is a *notification envelope* — it does NOT create state and
    its success/failure does NOT mutate adjudication state.

    event_type: one of ObservationEventType enum values (see observation_alert.py).
    severity  : "ALERT" | "WARN" | "INFO" (mapped to telegram priority by notifier).

    All state fields use 22Z judgment language ONLY. No new vocabulary.
    """
    event_type: str                       # ObservationEventType
    severity: str                         # "ALERT" | "WARN" | "INFO"
    ts_ms: int
    window_id: str | None = None
    # 22Z layered state snapshot (4-line report + conjunctive gate)
    receipt_layer: str | None = None              # "HEALTHY" | ...
    engine_layer: str | None = None               # "VALID" | ...
    system_layer_summary: str | None = None       # "EVALUATING" | ...
    system_layer_detail: str | None = None        # "INSUFFICIENT_EVIDENCE" | ...
    fail_closed_active: list[str] | None = None   # ["fail_closed_rule_2", ...]
    pass_status: str | None = None                # "NOT_ACHIEVED" | ...
    c1: bool | None = None                        # evidence_threshold_met
    c2: bool | None = None                        # fail_closed_not_firing
    c3: bool | None = None                        # no_layer_confusion
    c4: bool | None = None                        # joint_conflict_stable
    pass_blocked_reason: str | None = None
    confusion_incident_count: int | None = None
    consecutive_all_true_windows: int | None = None
    # Optional trigger metadata when event_type is T1~T4
    trigger_code: str | None = None               # "T1" | "T2" | "T3" | "T4" | None
    trigger_reason: str | None = None
    # Fingerprint for dedup (caller-supplied or computed by observation_alert helper)
    fingerprint: str | None = None
