"""
Bitget Exchange Adapter — TCL Spec v1
K-Dexter AOS

Translates TCL standard commands to Bitget API calls via ccxt.
Supports: spot trading (v1 scope). Futures (copy-trading): v2 roadmap.

B1 Doctrine compliance:
  - Upper layers never see Bitget-specific types
  - All exceptions wrapped into CommandTranscript.fail()
  - DRY_RUN uses internal simulation (Bitget demo trading optional)
"""
from __future__ import annotations

from typing import Optional

from kdexter.tcl.adapters import ExchangeAdapter
from kdexter.tcl.adapters.ccxt_base import CcxtMixin
from kdexter.tcl.commands import (
    CommandTranscript, CommandType, ExecutionMode, TCLCommand
)


class BitgetAdapter(ExchangeAdapter, CcxtMixin):
    """
    Bitget exchange adapter (spot).

    Args:
        api_key:    Bitget API key (empty string for DRY_RUN only)
        api_secret: Bitget API secret
        passphrase: Bitget API passphrase (required by Bitget)
        demo:       Use Bitget demo trading mode for DRY_RUN

    Usage:
        adapter = BitgetAdapter(api_key="...", api_secret="...", passphrase="...")
        dispatcher.register("bitget", adapter)
    """

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        passphrase: str = "",
        demo: bool = False,
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._passphrase = passphrase
        self._demo = demo
        self._testnet = demo
        self._client = None
        self._ccxt_exchange_cls = "bitget"
        self._init_rate_limiter(max_calls=10, period=1.0)

    @property
    def exchange_id(self) -> str:
        return "bitget"

    def _get_client(self):
        """Lazy-initialize ccxt Bitget client."""
        if self._client is None:
            try:
                import ccxt  # type: ignore
                self._client = ccxt.bitget({
                    "apiKey": self._api_key,
                    "secret": self._api_secret,
                    "password": self._passphrase,
                    "enableRateLimit": True,
                    "options": {"defaultType": "spot"},
                })
                if self._demo:
                    self._client.set_sandbox_mode(True)
            except ImportError:
                raise RuntimeError(
                    "ccxt not installed. Run: pip install ccxt"
                )
        return self._client

    # ── execute (LIVE) ───────────────────────────────────────────────────── #

    async def execute(self, command: TCLCommand) -> CommandTranscript:
        t = self._base_transcript(command)
        try:
            if command.command_type == CommandType.ORDER_BUY:
                return await self._place_order(t, command, side="buy")
            elif command.command_type == CommandType.ORDER_SELL:
                return await self._place_order(t, command, side="sell")
            elif command.command_type == CommandType.ORDER_CANCEL:
                return await self._cancel_order(t, command)
            elif command.command_type == CommandType.ORDER_VERIFY:
                return await self._verify_order(t, command)
            elif command.command_type == CommandType.POSITION_QUERY:
                return await self._query_position(t, command)
            elif command.command_type == CommandType.BALANCE_QUERY:
                return await self._query_balance(t, command)
            elif command.command_type == CommandType.RISK_CHECK:
                return self._risk_check(t, command)
            else:
                t.fail(f"Unsupported CommandType for execute(): {command.command_type.value}")
                return t
        except Exception as exc:
            return self._safe_fail(t, exc)

    # ── dry_run (simulation) ─────────────────────────────────────────────── #

    async def dry_run(self, command: TCLCommand) -> CommandTranscript:
        """Internal simulation — no real orders."""
        t = self._base_transcript(command)
        try:
            if command.command_type in {CommandType.ORDER_BUY, CommandType.ORDER_SELL,
                                        CommandType.ORDER_DRY_RUN}:
                sim_order_id = f"DRY-{command.idempotency_key[:8].upper()}"
                raw = {
                    "orderId": sim_order_id,
                    "symbol": command.symbol,
                    "side": "buy" if command.command_type == CommandType.ORDER_BUY else "sell",
                    "type": command.order_type.value.lower(),
                    "quantity": command.quantity,
                    "price": command.price,
                    "status": "SIMULATED",
                    "mode": "DRY_RUN",
                }
                parsed = {
                    "order_id": sim_order_id,
                    "filled": command.quantity,
                    "avg_price": command.price or 0.0,
                    "status": "SIMULATED",
                }
                t.complete(raw=raw, parsed=parsed, order_id=sim_order_id)

            elif command.command_type == CommandType.RISK_CHECK:
                t = self._risk_check(t, command)

            elif command.command_type == CommandType.BALANCE_QUERY:
                raw = {"balances": [{"coin": "USDT", "available": "10000", "frozen": "0"}]}
                parsed = {"USDT": {"free": 10_000.0, "locked": 0.0}}
                t.complete(raw=raw, parsed=parsed)

            elif command.command_type == CommandType.POSITION_QUERY:
                raw = {"positions": []}
                parsed = {"positions": []}
                t.complete(raw=raw, parsed=parsed)

            else:
                t.fail(f"DRY_RUN not implemented for {command.command_type.value}")

        except Exception as exc:
            return self._safe_fail(t, exc)
        return t

    # ── verify ───────────────────────────────────────────────────────────── #

    async def verify(self, exchange_order_id: str) -> CommandTranscript:
        cmd = TCLCommand(
            command_type=CommandType.ORDER_VERIFY,
            exchange=self.exchange_id,
            exchange_order_id=exchange_order_id,
        )
        t = self._base_transcript(cmd)
        try:
            raw = {"orderId": exchange_order_id, "status": "FILLED"}
            parsed = {"order_id": exchange_order_id, "status": "FILLED", "filled": True}
            t.complete(raw=raw, parsed=parsed, order_id=exchange_order_id)
            t.verification_result = True
        except Exception as exc:
            return self._safe_fail(t, exc)
        return t

    # ── cancel ───────────────────────────────────────────────────────────── #

    async def cancel(self, exchange_order_id: str) -> CommandTranscript:
        cmd = TCLCommand(
            command_type=CommandType.ORDER_CANCEL,
            exchange=self.exchange_id,
            exchange_order_id=exchange_order_id,
        )
        t = self._base_transcript(cmd)
        try:
            raw = {"orderId": exchange_order_id, "status": "CANCELLED"}
            parsed = {"order_id": exchange_order_id, "cancelled": True}
            t.complete(raw=raw, parsed=parsed, order_id=exchange_order_id)
        except Exception as exc:
            return self._safe_fail(t, exc)
        return t

    # ── query_position ───────────────────────────────────────────────────── #

    async def query_position(self, symbol: Optional[str] = None) -> CommandTranscript:
        cmd = TCLCommand(
            command_type=CommandType.POSITION_QUERY,
            exchange=self.exchange_id,
            symbol=symbol,
        )
        t = self._base_transcript(cmd)
        try:
            raw: dict = {"positions": [], "note": "spot — positions derived from balance"}
            parsed: dict = {"positions": []}
            t.complete(raw=raw, parsed=parsed)
        except Exception as exc:
            return self._safe_fail(t, exc)
        return t

    # ── query_balance ────────────────────────────────────────────────────── #

    async def query_balance(self, currency: Optional[str] = None) -> CommandTranscript:
        cmd = TCLCommand(
            command_type=CommandType.BALANCE_QUERY,
            exchange=self.exchange_id,
        )
        t = self._base_transcript(cmd)
        try:
            raw = {"balances": []}
            parsed: dict = {}
            t.complete(raw=raw, parsed=parsed)
        except Exception as exc:
            return self._safe_fail(t, exc)
        return t

    # ── internal helpers ─────────────────────────────────────────────────── #

    async def _place_order(
        self, t: CommandTranscript, command: TCLCommand, side: str
    ) -> CommandTranscript:
        return await self._ccxt_place_order(t, command, side)

    async def _cancel_order(
        self, t: CommandTranscript, command: TCLCommand
    ) -> CommandTranscript:
        return await self._ccxt_cancel_order(t, command)

    async def _verify_order(
        self, t: CommandTranscript, command: TCLCommand
    ) -> CommandTranscript:
        return await self._ccxt_verify_order(t, command)

    async def _query_position(
        self, t: CommandTranscript, command: TCLCommand
    ) -> CommandTranscript:
        return await self._ccxt_query_position(t, command)

    async def _query_balance(
        self, t: CommandTranscript, command: TCLCommand
    ) -> CommandTranscript:
        return await self._ccxt_query_balance(t, command)

    def _risk_check(
        self, t: CommandTranscript, command: TCLCommand
    ) -> CommandTranscript:
        """Basic risk check: quantity * price must not exceed budget cap."""
        qty = command.quantity or 0.0
        price = command.price or 0.0
        estimated_value = qty * price
        cap = command.extra.get("order_cap_usdt", 10_000)  # Bitget uses USDT
        if estimated_value > cap:
            t.fail(
                f"RISK.CHECK failed: estimated_value={estimated_value:,.2f} "
                f"> cap={cap:,.2f} USDT"
            )
        else:
            t.complete(
                raw={"risk": "OK", "estimated_value": estimated_value, "cap": cap},
                parsed={"passed": True, "estimated_value": estimated_value},
            )
        return t
