"""
WebSocket Market Stream — Card B-8 v1.1

Unified WebSocket layer for Binance + Bitget spot tick + top-of-book data.

Design:
  - Each venue has its own subclass of `VenueStream`
  - All streams emit `TickEvent` with a common schema:
        TickEvent(venue, canonical, price, quantity, bid, ask, ts_ms, raw_msg)
  - Canonical symbols are resolved through symbol_registry.REGISTRY
  - Consumers attach callback(s) via `.on_tick(callback)`; callbacks may be
    sync or async
  - Windows-safe: uses ThreadedResolver via aiohttp TCPConnector
  - Reconnect: exponential backoff capped at 60s; after 10 failed attempts
    logs 'ws_give_up' and stops

No Redis dependency here — upstream integration (event bus) is a separate layer.
This module only speaks WebSocket <-> in-process callbacks.
"""
from __future__ import annotations

import abc
import asyncio
import json
import random
import time
from dataclasses import dataclass
from typing import Awaitable, Callable

import aiohttp

from app.core.logging import get_logger
from app.services.symbol_registry import REGISTRY, Venue

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Unified event
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TickEvent:
    """Unified tick event across venues."""

    venue: Venue
    canonical: str                # "BTC/USDT" — resolved from raw_id
    price: float | None           # last trade price (None if bookTicker-only event)
    quantity: float | None        # trade quantity (None for book-only)
    bid: float | None             # best bid
    ask: float | None             # best ask
    ts_ms: int                    # event timestamp (exchange-provided when possible)
    event_kind: str               # "trade" | "book" | "synthetic"
    raw_msg_size: int = 0         # size of original JSON (not the message itself)


TickCallback = Callable[[TickEvent], Awaitable[None] | None]


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------
class VenueStream(abc.ABC):
    """Abstract WebSocket stream for one venue."""

    name: Venue
    url: str

    def __init__(self, canonicals: list[str]):
        self.canonicals = list(canonicals)
        self._callbacks: list[TickCallback] = []
        self._running = False
        self._task: asyncio.Task | None = None
        self._session: aiohttp.ClientSession | None = None
        self._last_msg_at: float = 0.0
        self._messages_received: int = 0
        self._reconnects: int = 0

    # ---- API ----
    def on_tick(self, cb: TickCallback) -> None:
        self._callbacks.append(cb)

    def stats(self) -> dict:
        return {
            "venue": self.name,
            "running": self._running,
            "canonicals": len(self.canonicals),
            "messages_received": self._messages_received,
            "reconnects": self._reconnects,
            "last_msg_age_s": round(time.time() - self._last_msg_at, 2) if self._last_msg_at else None,
        }

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_forever(), name=f"ws-{self.name}")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    # ---- Internal: reconnect loop ----
    async def _run_forever(self) -> None:
        backoff = 1.0
        consecutive_failures = 0
        MAX_FAILURES = 10

        while self._running:
            try:
                await self._connect_and_stream()
                # Clean disconnect → reset backoff
                backoff = 1.0
                consecutive_failures = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                consecutive_failures += 1
                self._reconnects += 1
                logger.warning(
                    "ws_error",
                    venue=self.name,
                    attempt=consecutive_failures,
                    error=str(exc)[:200],
                )
                if consecutive_failures >= MAX_FAILURES:
                    logger.error("ws_give_up", venue=self.name, failures=consecutive_failures)
                    self._running = False
                    return
                # Jittered exponential backoff
                delay = backoff + random.uniform(0, backoff * 0.3)
                await asyncio.sleep(min(delay, 60.0))
                backoff = min(backoff * 2, 60.0)

    # ---- Session helper (ThreadedResolver for Windows DNS) ----
    def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(resolver=aiohttp.resolver.ThreadedResolver())
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session

    # ---- Dispatch ----
    async def _emit(self, ev: TickEvent) -> None:
        self._messages_received += 1
        self._last_msg_at = time.time()
        for cb in self._callbacks:
            try:
                res = cb(ev)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as exc:  # never let callback break the stream
                logger.error("ws_callback_error", venue=self.name, error=str(exc)[:200])

    # ---- Subclass contract ----
    @abc.abstractmethod
    async def _connect_and_stream(self) -> None:
        """Open WS, subscribe, loop on messages. Raise on disconnect."""


# ---------------------------------------------------------------------------
# Binance stream
# ---------------------------------------------------------------------------
class BinanceStream(VenueStream):
    """Binance public spot WebSocket combined stream.

    Combines `<symbol>@trade` and `<symbol>@bookTicker` for each canonical.
    URL: wss://stream.binance.com:9443/stream?streams=btcusdt@trade/btcusdt@bookTicker/...
    """

    name: Venue = "binance"

    def _stream_list(self) -> list[str]:
        out = []
        for c in self.canonicals:
            raw = REGISTRY.to_venue_raw(c, "binance")
            if not raw:
                continue
            lower = raw.lower()
            out.append(f"{lower}@trade")
            out.append(f"{lower}@bookTicker")
        return out

    @property
    def url(self) -> str:  # type: ignore[override]
        streams = "/".join(self._stream_list())
        return f"wss://stream.binance.com:9443/stream?streams={streams}"

    async def _connect_and_stream(self) -> None:
        session = self._ensure_session()
        async with session.ws_connect(self.url, heartbeat=30) as ws:
            logger.info("ws_connected", venue=self.name, streams=len(self._stream_list()))
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self._handle_text(msg.data)
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    raise ConnectionError(f"binance ws closed: {msg.type}")

    async def _handle_text(self, text: str) -> None:
        try:
            payload = json.loads(text)
        except Exception:
            return

        data = payload.get("data") or {}
        stream = payload.get("stream", "")

        # e.g. "btcusdt@trade" or "btcusdt@bookTicker"
        if "@" not in stream:
            return
        raw_id_lower, channel = stream.split("@", 1)
        canonical = REGISTRY.canonical_from_raw(self.name, raw_id_lower.upper())
        if canonical is None:
            return

        ts_ms = int(data.get("E") or data.get("T") or time.time() * 1000)

        if channel == "trade":
            # {"e":"trade","E":...,"s":"BTCUSDT","t":12345,"p":"75000.0","q":"0.01","T":...}
            price = float(data.get("p", 0)) or None
            qty = float(data.get("q", 0)) or None
            ev = TickEvent(
                venue=self.name, canonical=canonical,
                price=price, quantity=qty,
                bid=None, ask=None,
                ts_ms=ts_ms, event_kind="trade",
                raw_msg_size=len(text),
            )
            await self._emit(ev)
        elif channel == "bookTicker":
            # {"u":...,"s":"BTCUSDT","b":"75000","B":"1.0","a":"75001","A":"1.0"}
            bid = float(data.get("b", 0)) or None
            ask = float(data.get("a", 0)) or None
            ev = TickEvent(
                venue=self.name, canonical=canonical,
                price=None, quantity=None,
                bid=bid, ask=ask,
                ts_ms=ts_ms, event_kind="book",
                raw_msg_size=len(text),
            )
            await self._emit(ev)


# ---------------------------------------------------------------------------
# Bitget stream
# ---------------------------------------------------------------------------
class BitgetStream(VenueStream):
    """Bitget public v2 WebSocket.

    URL: wss://ws.bitget.com/v2/ws/public
    Channels: `trade` + `books5` per symbol (SPOT product type)
    Subscription message: {"op":"subscribe","args":[{"instType":"SPOT","channel":"trade","instId":"BTCUSDT"}, ...]}
    """

    name: Venue = "bitget"
    url: str = "wss://ws.bitget.com/v2/ws/public"

    def _subscribe_args(self) -> list[dict]:
        args = []
        for c in self.canonicals:
            raw = REGISTRY.to_venue_raw(c, "bitget")
            if not raw:
                continue
            args.append({"instType": "SPOT", "channel": "trade", "instId": raw})
            args.append({"instType": "SPOT", "channel": "books5", "instId": raw})
        return args

    async def _connect_and_stream(self) -> None:
        session = self._ensure_session()
        async with session.ws_connect(self.url, heartbeat=25) as ws:
            args = self._subscribe_args()
            # Bitget accepts up to 50 args per subscribe; chunk if needed
            CHUNK = 50
            for i in range(0, len(args), CHUNK):
                await ws.send_json({"op": "subscribe", "args": args[i:i + CHUNK]})
            logger.info("ws_connected", venue=self.name, args=len(args))

            # Bitget requires a ping every ~30s (the library heartbeat suffices,
            # but Bitget also honors explicit "ping" text messages)
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self._handle_text(msg.data)
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    raise ConnectionError(f"bitget ws closed: {msg.type}")

    async def _handle_text(self, text: str) -> None:
        # Bitget may send "pong" text frames
        if text == "pong":
            return
        try:
            payload = json.loads(text)
        except Exception:
            return

        # Subscription ack / event
        if payload.get("event") == "subscribe":
            return

        arg = payload.get("arg") or {}
        channel = arg.get("channel")
        inst = arg.get("instId")
        if not inst:
            return
        canonical = REGISTRY.canonical_from_raw(self.name, inst)
        if canonical is None:
            return

        data_list = payload.get("data") or []
        ts_ms = int(payload.get("ts") or time.time() * 1000)

        if channel == "trade":
            for item in data_list:
                # {"ts": "...", "price": "75000", "size": "0.01", "side": "buy", ...}
                try:
                    price = float(item.get("price"))
                    qty = float(item.get("size"))
                except (TypeError, ValueError):
                    continue
                ev = TickEvent(
                    venue=self.name, canonical=canonical,
                    price=price, quantity=qty,
                    bid=None, ask=None,
                    ts_ms=int(item.get("ts", ts_ms)),
                    event_kind="trade",
                    raw_msg_size=len(text),
                )
                await self._emit(ev)
        elif channel == "books5":
            for item in data_list:
                bids = item.get("bids") or []
                asks = item.get("asks") or []
                bid = float(bids[0][0]) if bids and bids[0] else None
                ask = float(asks[0][0]) if asks and asks[0] else None
                ev = TickEvent(
                    venue=self.name, canonical=canonical,
                    price=None, quantity=None,
                    bid=bid, ask=ask,
                    ts_ms=int(item.get("ts", ts_ms)),
                    event_kind="book",
                    raw_msg_size=len(text),
                )
                await self._emit(ev)


# ---------------------------------------------------------------------------
# Multi-venue coordinator
# ---------------------------------------------------------------------------
class MultiVenueStream:
    """Manage one stream per venue. Caller attaches a single callback that
    receives TickEvents from all venues.
    """

    def __init__(self, canonicals: list[str], venues: list[Venue] | None = None):
        venues = venues or ["binance", "bitget"]
        self.streams: dict[Venue, VenueStream] = {}
        for v in venues:
            if v == "binance":
                self.streams[v] = BinanceStream(canonicals)
            elif v == "bitget":
                self.streams[v] = BitgetStream(canonicals)
            else:
                raise ValueError(f"unsupported venue: {v}")

    def on_tick(self, cb: TickCallback) -> None:
        for s in self.streams.values():
            s.on_tick(cb)

    async def start(self) -> None:
        await asyncio.gather(*(s.start() for s in self.streams.values()))

    async def stop(self) -> None:
        await asyncio.gather(
            *(s.stop() for s in self.streams.values()),
            return_exceptions=True,
        )

    def stats(self) -> list[dict]:
        return [s.stats() for s in self.streams.values()]
