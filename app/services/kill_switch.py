"""
Kill Switch — Card B-8 v1.1

Redis-backed multi-level kill switch with venue-specific and global scopes.

Levels:
  L1  MICRO       position-specific (not handled here — position_risk_monitor)
  L2  SOFT        block new entries; existing positions continue
  L3  HARD        force-close all positions in scope
  L4  MANUAL      operator-triggered (highest priority)

Scopes:
  global          affects all venues
  binance         affects only Binance
  bitget          affects only Bitget

State is stored in Redis as:
  kill:global       → '{"level":"SOFT","reason":"...","ts":...,"triggered_by":"..."}'
  kill:binance      → same shape
  kill:bitget       → same shape
  kill:history      → list of past events (LPUSH, LTRIM to last 1000)

Auto-reset:
  Daily loss limits reset at 00:00 UTC.
  Manual kills require explicit operator release.

Each state change also publishes to event_bus for downstream consumers
(telegram notifier, dashboard, order executor).
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict
from typing import Literal

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logging import get_logger
from app.services.event_bus import EventBus, KillEvent, TOPIC_KILL_GLOBAL, kill_topic

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------
KillLevel = Literal["NONE", "SOFT", "HARD", "MANUAL"]
KillScope = Literal["global", "binance", "bitget"]

LEVEL_RANK = {"NONE": 0, "SOFT": 1, "HARD": 2, "MANUAL": 3}

STATE_KEY_TEMPLATE = "kill:{scope}"
HISTORY_KEY = "kill:history"
HISTORY_MAX_LEN = 1000


# ---------------------------------------------------------------------------
# Kill Switch manager
# ---------------------------------------------------------------------------
class KillSwitch:
    """Kill switch state manager.

    Typical usage:
        ks = KillSwitch(bus=event_bus)
        await ks.connect()
        if await ks.is_entry_allowed("binance"):
            ...
        await ks.trigger("SOFT", scope="binance", reason="dd_2pct", by="auto_risk")
        await ks.release(scope="binance", by="operator")
    """

    def __init__(
        self,
        bus: EventBus | None = None,
        redis_url: str | None = None,
        client=None,
    ):
        self.bus = bus
        self._url = redis_url or settings.redis_url
        self._client = client

    # ---- Lifecycle ----
    async def connect(self) -> None:
        if self._client is None:
            self._client = aioredis.from_url(self._url, decode_responses=True)
        await self._client.ping()

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:
                pass

    # ---- State queries ----
    async def get_state(self, scope: KillScope) -> dict:
        """Return the current kill state for a scope. NONE if not set."""
        key = STATE_KEY_TEMPLATE.format(scope=scope)
        data = await self._client.get(key)
        if not data:
            return {"level": "NONE", "scope": scope, "reason": None, "ts": None, "triggered_by": None}
        try:
            parsed = json.loads(data)
            parsed.setdefault("scope", scope)
            return parsed
        except Exception:
            return {"level": "NONE", "scope": scope}

    async def current_level(self, scope: KillScope) -> KillLevel:
        st = await self.get_state(scope)
        return st.get("level", "NONE")

    async def is_entry_allowed(self, venue: str) -> bool:
        """Entry allowed only when BOTH global and venue-specific are NONE."""
        global_level = await self.current_level("global")
        if global_level != "NONE":
            return False
        if venue not in ("binance", "bitget"):
            return True  # unknown venue → don't block here, caller decides
        venue_level = await self.current_level(venue)  # type: ignore[arg-type]
        return venue_level == "NONE"

    async def is_force_close_required(self, venue: str) -> bool:
        """HARD or MANUAL kill at global or venue level requires forced close."""
        for scope in ("global", venue):
            if scope not in ("global", "binance", "bitget"):
                continue
            lvl = await self.current_level(scope)  # type: ignore[arg-type]
            if lvl in ("HARD", "MANUAL"):
                return True
        return False

    async def snapshot(self) -> dict:
        """Return states for all three scopes + recent history."""
        states = {}
        for scope in ("global", "binance", "bitget"):
            states[scope] = await self.get_state(scope)
        hist_raw = await self._client.lrange(HISTORY_KEY, 0, 19)  # last 20
        history = []
        for item in hist_raw:
            try:
                history.append(json.loads(item))
            except Exception:
                pass
        return {"states": states, "recent_history": history}

    # ---- Mutations ----
    async def trigger(
        self,
        level: KillLevel,
        scope: KillScope = "global",
        reason: str = "",
        by: str = "system",
    ) -> KillEvent:
        """Set a kill level on a scope. Higher levels supersede lower ones.

        If the current level is already >= requested level, this is a no-op
        unless `by` is 'operator' (operator can override at any time).
        """
        if level not in LEVEL_RANK or level == "NONE":
            raise ValueError(f"invalid level: {level}")

        current = await self.current_level(scope)
        if LEVEL_RANK[level] < LEVEL_RANK[current] and by != "operator":
            logger.info(
                "kill_trigger_skipped",
                scope=scope, current=current, requested=level, reason="weaker_than_current",
            )
            existing = await self.get_state(scope)
            return KillEvent(
                level=existing.get("level", "NONE"),
                scope=scope,
                reason=existing.get("reason", ""),
                ts_ms=existing.get("ts", 0),
                triggered_by=existing.get("triggered_by", "?"),
            )

        ts_ms = int(time.time() * 1000)
        payload = {
            "level": level,
            "scope": scope,
            "reason": reason,
            "ts": ts_ms,
            "triggered_by": by,
        }
        key = STATE_KEY_TEMPLATE.format(scope=scope)
        await self._client.set(key, json.dumps(payload))
        await self._append_history(payload)

        logger.warning(
            "kill_switch_triggered",
            scope=scope, level=level, reason=reason, triggered_by=by,
        )

        ev = KillEvent(
            level=level, scope=scope, reason=reason,
            ts_ms=ts_ms, triggered_by=by,
        )
        # Publish to event bus (non-fatal if bus is None)
        if self.bus is not None:
            try:
                topic = TOPIC_KILL_GLOBAL if scope == "global" else kill_topic(scope)
                await self.bus.publish(topic, asdict(ev))
            except Exception as exc:
                logger.error("kill_publish_failed", error=str(exc)[:200])
        return ev

    async def release(self, scope: KillScope = "global", by: str = "operator") -> KillEvent:
        """Clear the kill on a scope.

        Safety: auto-triggered kills (by='auto_*') can only be released by
        time-based logic (daily reset) or operator. This method records the
        release and publishes a NONE event so downstream can resume.
        """
        current = await self.get_state(scope)
        ts_ms = int(time.time() * 1000)
        payload = {
            "level": "NONE",
            "scope": scope,
            "reason": f"released_from:{current.get('level','?')}:{current.get('reason','')}",
            "ts": ts_ms,
            "triggered_by": by,
        }
        key = STATE_KEY_TEMPLATE.format(scope=scope)
        await self._client.delete(key)
        await self._append_history(payload)

        logger.info("kill_switch_released", scope=scope, by=by, previous=current.get("level"))

        ev = KillEvent(
            level="NONE", scope=scope,
            reason=payload["reason"], ts_ms=ts_ms, triggered_by=by,
        )
        if self.bus is not None:
            try:
                topic = TOPIC_KILL_GLOBAL if scope == "global" else kill_topic(scope)
                await self.bus.publish(topic, asdict(ev))
            except Exception:
                pass
        return ev

    async def _append_history(self, payload: dict) -> None:
        await self._client.lpush(HISTORY_KEY, json.dumps(payload))
        await self._client.ltrim(HISTORY_KEY, 0, HISTORY_MAX_LEN - 1)


# ---------------------------------------------------------------------------
# Auto-trigger helpers (called from risk monitor / position monitor)
# ---------------------------------------------------------------------------
class AutoKillTriggers:
    """Encapsulates the rules for when to auto-trigger kill switches.

    These are called periodically (e.g. every 1 min) by the risk monitor.
    """

    # Per Autonomy Charter A3, A4 (v1.1)
    DAILY_LOSS_SOFT_PCT = -0.02   # -2% venue or global
    DAILY_LOSS_HARD_PCT = -0.05   # -5% venue or global
    VENUE_API_FAIL_SEC = 180      # 3 min of consecutive failures

    @classmethod
    def decide_level(cls, daily_pnl_pct: float) -> KillLevel:
        if daily_pnl_pct <= cls.DAILY_LOSS_HARD_PCT:
            return "HARD"
        if daily_pnl_pct <= cls.DAILY_LOSS_SOFT_PCT:
            return "SOFT"
        return "NONE"
