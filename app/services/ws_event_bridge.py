"""
WS → Event Bus Bridge — Card B-8 v1.1

Consumes TickEvents from ws_market_stream and publishes selected subsets
onto the Redis Event Bus.

Throttling strategy:
  - Raw ticks are high-volume (hundreds/sec). Publishing every tick to Redis
    would flood the bus.
  - Instead, we throttle per (venue, canonical) to at most `max_rate_hz` ticks
    per second. Mid-throttle ticks are used to update in-memory state for
    spike/divergence detection without publishing.
  - ALL significant events (spike, divergence) are published unthrottled.

This bridge is a simple `TickCallback` for MultiVenueStream; it doesn't own
the stream lifecycle.
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import asdict
from typing import Any

from app.core.logging import get_logger
from app.services.event_bus import (
    DivergenceEvent,
    EventBus,
    SpikeEvent,
    tick_topic,
    TOPIC_DIVERGENCE,
    spike_topic,
)
from app.services.ws_market_stream import TickEvent

logger = get_logger(__name__)


class WSBridge:
    """Bridge WebSocket ticks to Event Bus with throttling + spike/divergence detection."""

    def __init__(
        self,
        bus: EventBus,
        max_rate_hz: float = 1.0,         # max 1 tick/s per (venue, canonical)
        divergence_threshold_pct: float = 0.2,
        spike_volume_multiple: float = 10.0,
        spike_window_sec: float = 60.0,
    ):
        self.bus = bus
        self.max_rate_hz = max_rate_hz
        self.div_threshold = divergence_threshold_pct / 100.0  # as ratio
        self.spike_vol_mult = spike_volume_multiple

        # State
        self._last_publish_ts: dict[tuple[str, str], float] = {}  # (venue, canonical) → sec
        # Per-(venue, canonical) latest mid price for divergence detection
        self._latest_mid: dict[tuple[str, str], float] = {}
        # Per-(venue, canonical) volume rolling window (list of (ts, qty))
        self._volume_window: dict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)
        self._spike_window_sec = spike_window_sec

        # Stats
        self.ticks_in = 0
        self.ticks_published = 0
        self.divergences_published = 0
        self.spikes_published = 0

    async def on_tick(self, ev: TickEvent) -> None:
        """Callback for MultiVenueStream. Always async."""
        self.ticks_in += 1
        key = (ev.venue, ev.canonical)

        # 1. Update state
        mid = None
        if ev.bid and ev.ask:
            mid = (ev.bid + ev.ask) / 2
        elif ev.price:
            mid = ev.price
        if mid is not None:
            self._latest_mid[key] = mid

        # 2. Volume spike detection (per-venue, per-canonical)
        if ev.event_kind == "trade" and ev.quantity:
            now = time.time()
            w = self._volume_window[key]
            w.append((now, ev.quantity))
            # Drop old
            cutoff = now - self._spike_window_sec
            w[:] = [(t, q) for t, q in w if t >= cutoff]
            if len(w) >= 10:  # need some baseline
                total_qty = sum(q for _, q in w)
                avg_qty = total_qty / len(w)
                if avg_qty > 0:
                    ratio = ev.quantity / avg_qty
                    if ratio >= self.spike_vol_mult:
                        await self._publish_spike(ev, ratio)

        # 3. Divergence check (between venues for the same canonical)
        #    Only check when both venues have a mid price
        if mid is not None:
            await self._check_divergence(ev.canonical)

        # 4. Throttled republish of tick itself
        now = time.time()
        last = self._last_publish_ts.get(key, 0)
        if now - last >= 1.0 / self.max_rate_hz:
            self._last_publish_ts[key] = now
            topic = tick_topic(ev.venue)
            try:
                await self.bus.publish(topic, asdict(ev))
                self.ticks_published += 1
            except Exception as exc:
                logger.error("ws_bridge_publish_failed", error=str(exc)[:200])

    async def _publish_spike(self, ev: TickEvent, magnitude: float) -> None:
        payload = SpikeEvent(
            venue=ev.venue,
            canonical=ev.canonical,
            kind="volume",
            magnitude=round(magnitude, 2),
            ts_ms=ev.ts_ms,
        )
        try:
            await self.bus.publish(spike_topic(ev.venue), asdict(payload))
            self.spikes_published += 1
            logger.info("spike_published", **asdict(payload))
        except Exception as exc:
            logger.error("spike_publish_failed", error=str(exc)[:200])

    async def _check_divergence(self, canonical: str) -> None:
        bn = self._latest_mid.get(("binance", canonical))
        bg = self._latest_mid.get(("bitget", canonical))
        if bn is None or bg is None or bn <= 0:
            return
        diff_pct = abs(bn - bg) / bn
        if diff_pct >= self.div_threshold:
            payload = DivergenceEvent(
                canonical=canonical,
                price_binance=bn,
                price_bitget=bg,
                diff_pct=round(diff_pct * 100, 3),
                threshold_pct=round(self.div_threshold * 100, 2),
                ts_ms=int(time.time() * 1000),
            )
            try:
                await self.bus.publish(TOPIC_DIVERGENCE, asdict(payload))
                self.divergences_published += 1
            except Exception:
                pass

    def stats(self) -> dict[str, Any]:
        return {
            "ticks_in": self.ticks_in,
            "ticks_published": self.ticks_published,
            "divergences_published": self.divergences_published,
            "spikes_published": self.spikes_published,
            "tracked_mids": len(self._latest_mid),
        }
