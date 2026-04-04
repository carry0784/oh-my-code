"""
CCXT Base Adapter — Shared logic for ccxt-based exchanges
K-Dexter AOS — TCL Spec v1

Common implementation for Binance, Bitget, Upbit.
Handles lazy client init, order placement, and rate limiting.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from kdexter.tcl.adapters.rate_limiter import AsyncRateLimiter
from kdexter.tcl.commands import CommandTranscript, TCLCommand


class CcxtMixin:
    """
    Mixin providing shared ccxt operations for exchange adapters.

    Subclasses must have:
      - self._api_key, self._api_secret
      - self._client (initially None)
      - self._base_transcript(command), self._safe_fail(t, exc)
      - self.exchange_id property
    """

    _ccxt_exchange_cls: str = ""  # override in subclass

    def _init_rate_limiter(self, max_calls: int = 10, period: float = 1.0) -> None:
        self._rate_limiter = AsyncRateLimiter(max_calls=max_calls, period=period)

    def _get_ccxt_client(self):
        """Lazy-initialize ccxt client."""
        if self._client is not None:
            return self._client
        try:
            import ccxt  # type: ignore
        except ImportError:
            raise RuntimeError("ccxt not installed. Run: pip install ccxt")
        cls = getattr(ccxt, self._ccxt_exchange_cls, None)
        if cls is None:
            raise RuntimeError(f"ccxt has no exchange '{self._ccxt_exchange_cls}'")
        self._client = cls(
            {
                "apiKey": self._api_key,
                "secret": self._api_secret,
                "enableRateLimit": True,
                "options": {"defaultType": "spot"},
            }
        )
        if getattr(self, "_testnet", False):
            self._client.set_sandbox_mode(True)
        return self._client

    async def _ccxt_place_order(
        self, t: CommandTranscript, command: TCLCommand, side: str
    ) -> CommandTranscript:
        """Place order via ccxt. Side: 'buy' or 'sell'."""
        await self._rate_limiter.acquire()
        client = self._get_ccxt_client()
        order_type = command.order_type.value.lower() if command.order_type else "limit"
        raw = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.create_order(
                symbol=command.symbol,
                type=order_type,
                side=side,
                amount=command.quantity,
                price=command.price,
            ),
        )
        order_id = str(raw.get("id", raw.get("orderId", "")))
        parsed = {
            "order_id": order_id,
            "filled": raw.get("filled", 0),
            "avg_price": raw.get("average", raw.get("price", 0)),
            "status": raw.get("status", "unknown"),
        }
        t.complete(raw=raw, parsed=parsed, order_id=order_id)
        return t

    async def _ccxt_cancel_order(
        self, t: CommandTranscript, command: TCLCommand
    ) -> CommandTranscript:
        await self._rate_limiter.acquire()
        client = self._get_ccxt_client()
        oid = command.exchange_order_id or ""
        raw = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.cancel_order(oid, command.symbol),
        )
        parsed = {"order_id": oid, "cancelled": True}
        t.complete(raw=raw, parsed=parsed, order_id=oid)
        return t

    async def _ccxt_verify_order(
        self, t: CommandTranscript, command: TCLCommand
    ) -> CommandTranscript:
        await self._rate_limiter.acquire()
        client = self._get_ccxt_client()
        oid = command.exchange_order_id or ""
        raw = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.fetch_order(oid, command.symbol),
        )
        status = raw.get("status", "unknown")
        parsed = {
            "order_id": oid,
            "status": status,
            "filled": status in ("closed", "FILLED"),
        }
        t.complete(raw=raw, parsed=parsed, order_id=oid)
        t.verification_result = status in ("closed", "FILLED")
        return t

    async def _ccxt_query_balance(
        self, t: CommandTranscript, command: TCLCommand
    ) -> CommandTranscript:
        await self._rate_limiter.acquire()
        client = self._get_ccxt_client()
        raw = await asyncio.get_event_loop().run_in_executor(
            None,
            client.fetch_balance,
        )
        free = raw.get("free", {})
        parsed = {k: v for k, v in free.items() if v and float(v) > 0}
        t.complete(raw=raw, parsed=parsed)
        return t

    async def _ccxt_query_position(
        self, t: CommandTranscript, command: TCLCommand
    ) -> CommandTranscript:
        """Spot: positions derived from non-zero balances."""
        await self._rate_limiter.acquire()
        client = self._get_ccxt_client()
        raw = await asyncio.get_event_loop().run_in_executor(
            None,
            client.fetch_balance,
        )
        total = raw.get("total", {})
        positions = [
            {"asset": k, "amount": float(v)} for k, v in total.items() if v and float(v) > 0
        ]
        parsed = {"positions": positions}
        t.complete(raw={"positions": positions}, parsed=parsed)
        return t
