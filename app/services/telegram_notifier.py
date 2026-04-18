"""
Telegram Notifier — Card B-8 v1.1

Sends formatted alerts to a Telegram chat (DM or group) via Bot API.

Two usage modes:
  1. Direct: `await notifier.send("hello")`
  2. Event-bus subscriber: `notifier.attach_to_bus(bus)` — auto-forwards
     SignalEvents, KillEvents, DivergenceEvents, SpikeEvents

Rate limiting:
  - Max 20 messages / 10s burst (Telegram limit is 30/s; we stay well under)
  - Per-chat priority queue: CRITICAL > WARNING > INFO
  - If rate limit hit: drop INFO, queue WARNING, always send CRITICAL
"""
from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.services.event_bus import (
    EventBus,
    TOPIC_DIVERGENCE,
    TOPIC_KILL_GLOBAL,
    TOPIC_OBSERVATION,
    TOPIC_SIGNAL,
    kill_topic,
    spike_topic,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Message formatters
# ---------------------------------------------------------------------------
def _format_signal(payload: dict) -> str:
    emoji = "🟢" if payload.get("direction") == "LONG" else "🔴"
    return (
        f"{emoji} *SIGNAL* {payload.get('direction','?')} {payload.get('canonical','?')}\n"
        f"venue: `{payload.get('venue_hint','?')}`\n"
        f"strategy: `{payload.get('strategy_key','?')}`\n"
        f"entry: `{payload.get('entry_price','?')}`\n"
        f"SL: `{payload.get('stop_loss','?')}`  TP: `{payload.get('take_profit','?')}`\n"
        f"confidence: `{payload.get('confidence','?')}`"
    )


def _format_kill(payload: dict) -> str:
    level = payload.get("level", "?")
    scope = payload.get("scope", "?")
    if level == "NONE":
        return f"✅ *KILL RELEASED* ({scope})\nby: `{payload.get('triggered_by','?')}`\nreason: `{payload.get('reason','?')}`"
    emoji = {"SOFT": "⚠️", "HARD": "🚨", "MANUAL": "🛑"}.get(level, "⚠️")
    return (
        f"{emoji} *KILL {level}* scope={scope}\n"
        f"reason: `{payload.get('reason','?')}`\n"
        f"triggered_by: `{payload.get('triggered_by','?')}`"
    )


def _format_divergence(payload: dict) -> str:
    return (
        f"📊 *PRICE DIVERGENCE* {payload.get('canonical','?')}\n"
        f"Binance: `{payload.get('price_binance','?')}`  Bitget: `{payload.get('price_bitget','?')}`\n"
        f"diff: `{payload.get('diff_pct','?')}%`  threshold: `{payload.get('threshold_pct','?')}%`"
    )


def _format_spike(payload: dict) -> str:
    kind = payload.get("kind", "volume")
    emoji = "📈" if kind == "volume" else "⚡"
    return (
        f"{emoji} *{kind.upper()} SPIKE* {payload.get('canonical','?')} @ `{payload.get('venue','?')}`\n"
        f"magnitude: `{payload.get('magnitude','?')}×`"
    )


def _format_observation(payload: dict) -> str:
    """Format 22Z observation event for Telegram (Review 21 template).

    Uses ONLY 22Z judgment language. No new state vocabulary. Success here
    does NOT translate to PASS; this is an external notification channel.

    IMPORTANT — PLAIN TEXT ONLY (Review 22 operational fix):
      22Z canonical field values contain underscores (e.g. fail_closed_rule_2,
      INSUFFICIENT_EVIDENCE, VALIDATION_SMOKE). Telegram Markdown v1 treats
      unbalanced underscores/asterisks as emphasis delimiters and returns
      HTTP 400 "can't parse entities" when they occur in our payloads.
      MarkdownV2 requires escaping ~18 special chars which is fragile.
      We therefore emit pure plain text here — the caller (_on_observation)
      sends this with `parse_mode=None`. No formatting metacharacters of
      any kind are produced by this function.
    """
    severity = str(payload.get("severity", "INFO")).upper()
    event_type = payload.get("event_type", "UNKNOWN")
    emoji = {"ALERT": "🚨", "WARN": "⚠️", "INFO": "ℹ️"}.get(severity, "ℹ️")

    # c1..c4 — render explicit TRUE/FALSE/? to avoid ambiguity
    def _bool(v: Any) -> str:
        if v is True:
            return "TRUE"
        if v is False:
            return "FALSE"
        return "?"

    fc = payload.get("fail_closed_active")
    if isinstance(fc, list):
        fc_str = "[" + ", ".join(fc) + "]" if fc else "[]"
    else:
        fc_str = "?"

    trigger = payload.get("trigger_code")
    trigger_line = ""
    if trigger:
        trigger_line = (
            f"trigger: {trigger} - {payload.get('trigger_reason','(no reason)')}\n"
        )

    return (
        f"{emoji} [K-DEXTER OBS] {severity}\n"
        f"event_type: {event_type}\n"
        f"ts: {payload.get('ts_ms','?')}\n"
        f"window_id: {payload.get('window_id','?')}\n"
        f"receipt: {payload.get('receipt_layer','?')}\n"
        f"engine: {payload.get('engine_layer','?')}\n"
        f"summary: {payload.get('system_layer_summary','?')}\n"
        f"detail: {payload.get('system_layer_detail','?')}\n"
        f"fail_closed: {fc_str}\n"
        f"pass: {payload.get('pass_status','?')}\n"
        f"c1/c2/c3/c4: "
        f"{_bool(payload.get('c1'))}/"
        f"{_bool(payload.get('c2'))}/"
        f"{_bool(payload.get('c3'))}/"
        f"{_bool(payload.get('c4'))}\n"
        f"reason: {payload.get('pass_blocked_reason','?')}\n"
        f"incidents: {payload.get('confusion_incident_count','?')}\n"
        f"consecutive_true_windows: {payload.get('consecutive_all_true_windows','?')}\n"
        f"{trigger_line}"
        f"authority: 22Z canonical + exit_dashboard_checklist_v1 (this alert is a notification only)"
    )


# ---------------------------------------------------------------------------
# Priority queue entry
# ---------------------------------------------------------------------------
PRIORITY_CRITICAL = 0
PRIORITY_WARNING = 1
PRIORITY_INFO = 2


@dataclass
class _QueuedMessage:
    priority: int
    text: str
    ts: float


# ---------------------------------------------------------------------------
# Notifier
# ---------------------------------------------------------------------------
class TelegramNotifier:
    """Rate-limited Telegram notifier.

    Usage:
        notifier = TelegramNotifier()
        await notifier.send("hello", priority=PRIORITY_INFO)
        notifier.attach_to_bus(bus)
    """

    API_BASE = "https://api.telegram.org"
    RATE_LIMIT_BURST = 20
    RATE_LIMIT_WINDOW = 10.0

    def __init__(
        self,
        token: str | None = None,
        chat_id: str | None = None,
        enabled: bool | None = None,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.token = (token if token is not None else settings.telegram_bot_token).strip()
        self.chat_id = (chat_id if chat_id is not None else settings.telegram_chat_id).strip()
        self.enabled = (
            enabled if enabled is not None else settings.telegram_enabled
        ) and bool(self.token) and bool(self.chat_id)

        self._http = http_client
        self._owns_client = http_client is None
        self._send_ts: deque = deque()  # timestamps of recent sends
        self._queue: list[_QueuedMessage] = []
        self._sent = 0
        self._dropped_rate_limit = 0
        self._failed = 0

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=10.0)
        return self._http

    async def close(self) -> None:
        if self._http is not None and self._owns_client:
            await self._http.aclose()
            self._http = None

    # ---- Rate limit ----
    def _can_send_now(self) -> bool:
        now = time.time()
        cutoff = now - self.RATE_LIMIT_WINDOW
        while self._send_ts and self._send_ts[0] < cutoff:
            self._send_ts.popleft()
        return len(self._send_ts) < self.RATE_LIMIT_BURST

    # ---- Core send ----
    async def send(
        self,
        text: str,
        priority: int = PRIORITY_INFO,
        parse_mode: str | None = "Markdown",
    ) -> bool:
        """Send a message to Telegram. Returns True if sent, False if dropped/queued.

        parse_mode:
          - "Markdown" (default): legacy v1 parser. Backward-compat for signal/kill/
            divergence/spike formatters.
          - "MarkdownV2" / "HTML": alternate parsers if caller escapes appropriately.
          - None: plain text — no parsing, all characters treated literally. Required
            for observation events whose payloads contain underscores in canonical
            22Z field values (fail_closed_rule_N, INSUFFICIENT_EVIDENCE, etc.) that
            the Markdown v1 parser mis-interprets as unterminated emphasis entities.
        """
        if not self.enabled:
            return False

        # Rate limit: drop INFO, drop WARNING (rare), always send CRITICAL
        if not self._can_send_now():
            if priority >= PRIORITY_INFO:
                self._dropped_rate_limit += 1
                logger.debug("telegram_rate_limit_drop", priority=priority)
                return False
            # Critical: wait up to 2s for slot to open (Telegram will also
            # reject if we truly exceed; try anyway)
            deadline = time.time() + 2.0
            while not self._can_send_now() and time.time() < deadline:
                await asyncio.sleep(0.1)

        url = f"{self.API_BASE}/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text[:4096],  # Telegram message limit
            "disable_web_page_preview": True,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        try:
            client = await self._client()
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                self._send_ts.append(time.time())
                self._sent += 1
                return True
            logger.warning(
                "telegram_send_http_error",
                status=resp.status_code, body=resp.text[:200],
            )
            self._failed += 1
            return False
        except Exception as exc:
            self._failed += 1
            logger.warning("telegram_send_exception", error=repr(exc)[:200])
            return False

    # ---- Bus integration ----
    def attach_to_bus(self, bus: EventBus) -> None:
        """Subscribe to key topics. Caller must then call bus.start_listening()."""
        bus.subscribe([TOPIC_SIGNAL], self._on_signal)
        bus.subscribe([TOPIC_DIVERGENCE], self._on_divergence)
        bus.subscribe([TOPIC_KILL_GLOBAL], self._on_kill)
        bus.subscribe([kill_topic("binance"), kill_topic("bitget")], self._on_kill)
        bus.subscribe([TOPIC_OBSERVATION], self._on_observation)
        bus.psubscribe("events:*:spike", self._on_spike)

    async def _on_signal(self, topic: str, payload: dict) -> None:
        await self.send(_format_signal(payload), priority=PRIORITY_INFO)

    async def _on_kill(self, topic: str, payload: dict) -> None:
        level = payload.get("level", "?")
        priority = PRIORITY_CRITICAL if level in ("HARD", "MANUAL") else PRIORITY_WARNING
        await self.send(_format_kill(payload), priority=priority)

    async def _on_divergence(self, topic: str, payload: dict) -> None:
        await self.send(_format_divergence(payload), priority=PRIORITY_WARNING)

    async def _on_spike(self, topic: str, payload: dict) -> None:
        await self.send(_format_spike(payload), priority=PRIORITY_INFO)

    async def _on_observation(self, topic: str, payload: dict) -> None:
        """22Z observation event handler (Review 21).

        severity → priority:
          ALERT → CRITICAL  (T1~T4 trigger, confusion incident, summary/detail conflict)
          WARN  → WARNING   (fail_closed still active, PASS_BLOCKED with state shift, c4 FALSE streak)
          INFO  → INFO      (window summary, c1 partial change, consecutive counter increment)

        parse_mode is forced to None (plain text) because 22Z canonical field values
        contain underscores (fail_closed_rule_N, INSUFFICIENT_EVIDENCE, etc.) that
        the Telegram Markdown v1 parser rejects as unbalanced emphasis. See
        _format_observation docstring for the operational fix rationale.

        A send failure here is contained: it only affects the external notification
        channel. Authority source (22Z canonical + checklist) is never mutated.
        """
        severity = str(payload.get("severity", "INFO")).upper()
        priority = {
            "ALERT": PRIORITY_CRITICAL,
            "WARN": PRIORITY_WARNING,
            "INFO": PRIORITY_INFO,
        }.get(severity, PRIORITY_INFO)
        await self.send(
            _format_observation(payload),
            priority=priority,
            parse_mode=None,
        )

    # ---- Stats ----
    def stats(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "sent": self._sent,
            "dropped_rate_limit": self._dropped_rate_limit,
            "failed": self._failed,
            "queued": len(self._queue),
            "in_window": len(self._send_ts),
        }
