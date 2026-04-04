"""
Binance Exchange Adapter — TCL Spec v1
K-Dexter AOS

Translates TCL standard commands to Binance API calls via ccxt.
Supports: spot trading (v1 scope). Futures: v2 roadmap.

B1 Doctrine compliance:
  - Upper layers never see Binance-specific types
  - All exceptions wrapped into CommandTranscript.fail()
  - DRY_RUN uses internal simulation (Binance testnet optional)
"""

from __future__ import annotations

from typing import Optional

from kdexter.tcl.adapters import ExchangeAdapter
from kdexter.tcl.adapters.ccxt_base import CcxtMixin
from kdexter.tcl.commands import CommandTranscript, CommandType, ExecutionMode, TCLCommand


class BinanceAdapter(ExchangeAdapter, CcxtMixin):
    """
    Binance exchange adapter (spot).

    Args:
        api_key:    Binance API key (empty string for DRY_RUN only)
        api_secret: Binance API secret
        testnet:    Use Binance testnet for DRY_RUN (default: False = internal sim)

    Usage:
        adapter = BinanceAdapter(api_key="...", api_secret="...")
        dispatcher.register("binance", adapter)
    """

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        testnet: bool = False,
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._testnet = testnet
        self._client = None  # ccxt.binance instance — initialized on first use
        self._ccxt_exchange_cls = "binance"
        self._init_rate_limiter(max_calls=10, period=1.0)

    @property
    def exchange_id(self) -> str:
        return "binance"

    def _get_client(self):
        """Lazy-initialize ccxt Binance client."""
        if self._client is None:
            try:
                import ccxt  # type: ignore

                self._client = ccxt.binance(
                    {
                        "apiKey": self._api_key,
                        "secret": self._api_secret,
                        "enableRateLimit": True,
                        "options": {"defaultType": "spot"},
                    }
                )
                if self._testnet:
                    self._client.set_sandbox_mode(True)
            except ImportError:
                raise RuntimeError("ccxt not installed. Run: pip install ccxt")
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
        """
        Internal simulation — no real orders.
        Returns synthetic response mirroring Binance API structure.
        """
        t = self._base_transcript(command)
        try:
            if command.command_type in {
                CommandType.ORDER_BUY,
                CommandType.ORDER_SELL,
                CommandType.ORDER_DRY_RUN,
            }:
                sim_order_id = f"DRY-{command.idempotency_key[:8].upper()}"
                raw = {
                    "orderId": sim_order_id,
                    "symbol": command.symbol,
                    "side": "BUY" if command.command_type == CommandType.ORDER_BUY else "SELL",
                    "type": command.order_type.value,
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
                raw = {"balances": [{"asset": "KRW", "free": "10000000", "locked": "0"}]}
                parsed = {"KRW": {"free": 10_000_000.0, "locked": 0.0}}
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
        from kdexter.tcl.commands import TCLCommand, CommandType, ExecutionMode

        cmd = TCLCommand(
            command_type=CommandType.ORDER_VERIFY,
            exchange=self.exchange_id,
            exchange_order_id=exchange_order_id,
        )
        t = self._base_transcript(cmd)
        try:
            client = self._get_client()
            # ccxt fetch_order requires symbol — stored in exchange_order_id context
            # TODO: pass symbol through when implementing full verify
            raw = {"orderId": exchange_order_id, "status": "FILLED"}
            parsed = {"order_id": exchange_order_id, "status": "FILLED", "filled": True}
            t.complete(raw=raw, parsed=parsed, order_id=exchange_order_id)
            t.verification_result = True
        except Exception as exc:
            return self._safe_fail(t, exc)
        return t

    # ── cancel ───────────────────────────────────────────────────────────── #

    async def cancel(self, exchange_order_id: str) -> CommandTranscript:
        from kdexter.tcl.commands import TCLCommand, CommandType

        cmd = TCLCommand(
            command_type=CommandType.ORDER_CANCEL,
            exchange=self.exchange_id,
            exchange_order_id=exchange_order_id,
        )
        t = self._base_transcript(cmd)
        try:
            # TODO: client.cancel_order(exchange_order_id, symbol)
            raw = {"orderId": exchange_order_id, "status": "CANCELED"}
            parsed = {"order_id": exchange_order_id, "cancelled": True}
            t.complete(raw=raw, parsed=parsed, order_id=exchange_order_id)
        except Exception as exc:
            return self._safe_fail(t, exc)
        return t

    # ── query_position ───────────────────────────────────────────────────── #

    async def query_position(self, symbol: Optional[str] = None) -> CommandTranscript:
        from kdexter.tcl.commands import TCLCommand, CommandType

        cmd = TCLCommand(
            command_type=CommandType.POSITION_QUERY,
            exchange=self.exchange_id,
            symbol=symbol,
        )
        t = self._base_transcript(cmd)
        try:
            # TODO: client.fetch_positions([symbol]) for futures
            # Spot: infer position from balance
            raw: dict = {"positions": [], "note": "spot — positions derived from balance"}
            parsed: dict = {"positions": []}
            t.complete(raw=raw, parsed=parsed)
        except Exception as exc:
            return self._safe_fail(t, exc)
        return t

    # ── query_balance ────────────────────────────────────────────────────── #

    async def query_balance(self, currency: Optional[str] = None) -> CommandTranscript:
        from kdexter.tcl.commands import TCLCommand, CommandType

        cmd = TCLCommand(
            command_type=CommandType.BALANCE_QUERY,
            exchange=self.exchange_id,
        )
        t = self._base_transcript(cmd)
        try:
            # TODO: raw = await asyncio.get_event_loop().run_in_executor(
            #           None, client.fetch_balance)
            raw = {"balances": []}  # placeholder until ccxt async integration
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

    async def _cancel_order(self, t: CommandTranscript, command: TCLCommand) -> CommandTranscript:
        return await self._ccxt_cancel_order(t, command)

    async def _verify_order(self, t: CommandTranscript, command: TCLCommand) -> CommandTranscript:
        return await self._ccxt_verify_order(t, command)

    async def _query_position(self, t: CommandTranscript, command: TCLCommand) -> CommandTranscript:
        return await self._ccxt_query_position(t, command)

    async def _query_balance(self, t: CommandTranscript, command: TCLCommand) -> CommandTranscript:
        return await self._ccxt_query_balance(t, command)

    def _risk_check(self, t: CommandTranscript, command: TCLCommand) -> CommandTranscript:
        """
        Basic risk check: quantity * estimated_price must not exceed budget cap.
        TODO: connect to L3 Security & Isolation for full policy enforcement.
        """
        qty = command.quantity or 0.0
        price = command.price or 0.0
        estimated_value = qty * price
        # Placeholder cap: 10M KRW per order
        cap = command.extra.get("order_cap_krw", 10_000_000)
        if estimated_value > cap:
            t.fail(f"RISK.CHECK failed: estimated_value={estimated_value:,.0f} > cap={cap:,.0f}")
        else:
            t.complete(
                raw={"risk": "OK", "estimated_value": estimated_value, "cap": cap},
                parsed={"passed": True, "estimated_value": estimated_value},
            )
        return t
