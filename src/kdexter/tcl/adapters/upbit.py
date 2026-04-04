"""
Upbit Exchange Adapter — TCL Spec v1
K-Dexter AOS

Translates TCL standard commands to Upbit API calls via ccxt.
Supports: spot trading (KRW pairs).

Upbit-specific notes:
  - KRW 원화 마켓 중심 (BTC/KRW, ETH/KRW, ...)
  - API 호출 제한: 초당 10회 (주문), 초당 30회 (조회)
  - 주문 단위: KRW 최소 5,000원
  - ccxt exchange ID: "upbit"

B1 Doctrine compliance:
  - Upper layers never see Upbit-specific types (JWT auth, etc.)
  - All exceptions wrapped into CommandTranscript.fail()
  - DRY_RUN uses internal simulation (Upbit has no public testnet)
"""

from __future__ import annotations

from typing import Optional

from kdexter.tcl.adapters import ExchangeAdapter
from kdexter.tcl.adapters.ccxt_base import CcxtMixin
from kdexter.tcl.commands import CommandTranscript, CommandType, ExecutionMode, TCLCommand


class UpbitAdapter(ExchangeAdapter, CcxtMixin):
    """
    Upbit exchange adapter (spot, KRW market).

    Args:
        access_key: Upbit API access key
        secret_key: Upbit API secret key

    Usage:
        adapter = UpbitAdapter(access_key="...", secret_key="...")
        dispatcher.register("upbit", adapter)
    """

    # Upbit rate limits
    ORDER_RATE_LIMIT_PER_SEC = 10
    QUERY_RATE_LIMIT_PER_SEC = 30
    MIN_ORDER_KRW = 5_000  # 최소 주문 금액

    def __init__(
        self,
        access_key: str = "",
        secret_key: str = "",
    ) -> None:
        self._api_key = access_key
        self._api_secret = secret_key
        self._access_key = access_key
        self._secret_key = secret_key
        self._client = None
        self._ccxt_exchange_cls = "upbit"
        self._init_rate_limiter(max_calls=10, period=1.0)

    @property
    def exchange_id(self) -> str:
        return "upbit"

    def _get_client(self):
        """Lazy-initialize ccxt Upbit client."""
        if self._client is None:
            try:
                import ccxt  # type: ignore

                self._client = ccxt.upbit(
                    {
                        "apiKey": self._access_key,
                        "secret": self._secret_key,
                        "enableRateLimit": True,
                    }
                )
            except ImportError:
                raise RuntimeError("ccxt not installed. Run: pip install ccxt")
        return self._client

    # ── execute (LIVE) ───────────────────────────────────────────────────── #

    async def execute(self, command: TCLCommand) -> CommandTranscript:
        t = self._base_transcript(command)
        try:
            if command.command_type == CommandType.ORDER_BUY:
                return await self._place_order(t, command, side="bid")
            elif command.command_type == CommandType.ORDER_SELL:
                return await self._place_order(t, command, side="ask")
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
                t.fail(f"Unsupported CommandType: {command.command_type.value}")
                return t
        except Exception as exc:
            return self._safe_fail(t, exc)

    # ── dry_run (simulation) ─────────────────────────────────────────────── #

    async def dry_run(self, command: TCLCommand) -> CommandTranscript:
        """Internal simulation — no real orders. Upbit has no public testnet."""
        t = self._base_transcript(command)
        try:
            if command.command_type in {
                CommandType.ORDER_BUY,
                CommandType.ORDER_SELL,
                CommandType.ORDER_DRY_RUN,
            }:
                # Upbit minimum order validation
                qty = command.quantity or 0.0
                price = command.price or 0.0
                estimated_krw = qty * price
                if estimated_krw > 0 and estimated_krw < self.MIN_ORDER_KRW:
                    t.fail(
                        f"Upbit minimum order: {self.MIN_ORDER_KRW:,} KRW, "
                        f"estimated={estimated_krw:,.0f} KRW"
                    )
                    return t

                sim_order_id = f"DRY-{command.idempotency_key[:8].upper()}"
                side = "bid" if command.command_type == CommandType.ORDER_BUY else "ask"
                raw = {
                    "uuid": sim_order_id,
                    "side": side,
                    "ord_type": command.order_type.value.lower(),
                    "market": self._to_upbit_symbol(command.symbol),
                    "volume": str(command.quantity),
                    "price": str(command.price) if command.price else None,
                    "state": "simulated",
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
                raw = {
                    "accounts": [
                        {
                            "currency": "KRW",
                            "balance": "10000000",
                            "locked": "0",
                            "avg_buy_price": "0",
                        },
                    ]
                }
                parsed = {"KRW": {"free": 10_000_000.0, "locked": 0.0}}
                t.complete(raw=raw, parsed=parsed)

            elif command.command_type == CommandType.POSITION_QUERY:
                raw = {"accounts": []}
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
            raw = {"uuid": exchange_order_id, "state": "done"}
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
            raw = {"uuid": exchange_order_id, "state": "cancel"}
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
            # Upbit spot: positions are derived from account balances
            raw: dict = {"accounts": [], "note": "spot — positions derived from balance"}
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
            raw = {"accounts": []}
            parsed: dict = {}
            t.complete(raw=raw, parsed=parsed)
        except Exception as exc:
            return self._safe_fail(t, exc)
        return t

    # ── internal helpers ─────────────────────────────────────────────────── #

    @staticmethod
    def _to_upbit_symbol(symbol: Optional[str]) -> str:
        """Convert standard symbol (BTC/KRW) to Upbit format (KRW-BTC)."""
        if not symbol:
            return ""
        parts = symbol.split("/")
        if len(parts) == 2:
            return f"{parts[1]}-{parts[0]}"  # BTC/KRW → KRW-BTC
        return symbol

    @staticmethod
    def _from_upbit_symbol(market: str) -> str:
        """Convert Upbit format (KRW-BTC) to standard (BTC/KRW)."""
        parts = market.split("-")
        if len(parts) == 2:
            return f"{parts[1]}/{parts[0]}"  # KRW-BTC → BTC/KRW
        return market

    async def _place_order(
        self, t: CommandTranscript, command: TCLCommand, side: str
    ) -> CommandTranscript:
        # Upbit uses bid/ask but ccxt normalizes to buy/sell
        ccxt_side = "buy" if side == "bid" else "sell"
        return await self._ccxt_place_order(t, command, ccxt_side)

    async def _cancel_order(self, t: CommandTranscript, command: TCLCommand) -> CommandTranscript:
        return await self._ccxt_cancel_order(t, command)

    async def _verify_order(self, t: CommandTranscript, command: TCLCommand) -> CommandTranscript:
        return await self._ccxt_verify_order(t, command)

    async def _query_position(self, t: CommandTranscript, command: TCLCommand) -> CommandTranscript:
        return await self._ccxt_query_position(t, command)

    async def _query_balance(self, t: CommandTranscript, command: TCLCommand) -> CommandTranscript:
        return await self._ccxt_query_balance(t, command)

    def _risk_check(self, t: CommandTranscript, command: TCLCommand) -> CommandTranscript:
        """Risk check with Upbit KRW constraints."""
        qty = command.quantity or 0.0
        price = command.price or 0.0
        estimated_value = qty * price
        cap = command.extra.get("order_cap_krw", 10_000_000)

        # Upbit minimum order check
        if estimated_value > 0 and estimated_value < self.MIN_ORDER_KRW:
            t.fail(
                f"RISK.CHECK failed: estimated_value={estimated_value:,.0f} KRW "
                f"< minimum={self.MIN_ORDER_KRW:,} KRW"
            )
        elif estimated_value > cap:
            t.fail(
                f"RISK.CHECK failed: estimated_value={estimated_value:,.0f} KRW "
                f"> cap={cap:,.0f} KRW"
            )
        else:
            t.complete(
                raw={"risk": "OK", "estimated_value": estimated_value, "cap": cap},
                parsed={"passed": True, "estimated_value": estimated_value},
            )
        return t
