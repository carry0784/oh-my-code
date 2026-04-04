"""
Trading Command Language (TCL) — Standard Commands & Dispatcher
K-Dexter AOS — TCL Spec v1

Upper layers (L6/L8) create TCLCommand instances and call TCLDispatcher.dispatch().
TCLDispatcher routes to the registered ExchangeAdapter and returns a CommandTranscript.

B1 Doctrine (Execution Interface Doctrine):
  - Upper layers NEVER call exchange APIs directly
  - Every command must be replayable (idempotency_key)
  - Every execution produces a CommandTranscript (Evidence Pack)
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from kdexter.tcl.adapters import ExchangeAdapter


# ─────────────────────────────────────────────────────────────────────────── #
# Enums
# ─────────────────────────────────────────────────────────────────────────── #

class CommandType(Enum):
    ORDER_BUY       = "ORDER.BUY"
    ORDER_SELL      = "ORDER.SELL"
    ORDER_CANCEL    = "ORDER.CANCEL"
    POSITION_QUERY  = "POSITION.QUERY"
    BALANCE_QUERY   = "BALANCE.QUERY"
    RISK_CHECK      = "RISK.CHECK"
    ORDER_DRY_RUN   = "ORDER.DRY_RUN"
    ORDER_VERIFY    = "ORDER.VERIFY"
    ORDER_REPLAY    = "ORDER.REPLAY"
    ORDER_ROLLBACK  = "ORDER.ROLLBACK"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT  = "LIMIT"
    STOP   = "STOP"


class ExecutionMode(Enum):
    DRY_RUN = "DRY_RUN"   # simulation — no real orders placed
    LIVE    = "LIVE"       # real execution (FINAL_GO required)


# ─────────────────────────────────────────────────────────────────────────── #
# Command
# ─────────────────────────────────────────────────────────────────────────── #

@dataclass
class TCLCommand:
    """
    A single TCL command issued by L6/L8.
    Upper layers must set idempotency_key once and reuse it on retries —
    never generate a new key for a retry of the same logical operation.
    """
    command_type: CommandType
    exchange: str                                   # "binance" | "bitget" | "upbit" | "kis" | "kiwoom"
    mode: ExecutionMode = ExecutionMode.DRY_RUN     # default SAFE — explicit LIVE required

    # Order params (BUY / SELL / DRY_RUN)
    symbol: Optional[str] = None                    # e.g. "BTC/KRW", "ETH/USDT"
    quantity: Optional[float] = None
    price: Optional[float] = None                   # None = market order
    order_type: OrderType = OrderType.MARKET

    # Cancel / Verify
    exchange_order_id: Optional[str] = None

    # Replay
    original_transcript_id: Optional[str] = None

    # Rollback
    target_position: Optional[float] = None

    # Idempotency key — reuse on retry, never replace
    idempotency_key: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Exchange-specific extras (use sparingly)
    extra: dict[str, Any] = field(default_factory=dict)

    def normalize(self) -> str:
        """Canonical string for audit logging and idempotency comparison."""
        return (
            f"{self.command_type.value}|{self.exchange}|{self.mode.value}"
            f"|{self.symbol}|qty={self.quantity}|price={self.price}"
            f"|{self.order_type.value}|key={self.idempotency_key}"
        )


# ─────────────────────────────────────────────────────────────────────────── #
# Transcript — audit record (M-07 Evidence Pack)
# ─────────────────────────────────────────────────────────────────────────── #

@dataclass
class CommandTranscript:
    """
    Complete audit record for a single TCL command execution.
    Must be attached to EvidenceBundle (M-07) for every execution.
    See docs/specs/tcl_spec_v1.md Section 5 for field definitions.
    """
    transcript_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    required_command: str = ""
    normalized_command: str = ""
    command_type: Optional[CommandType] = None
    exchange: str = ""
    mode: ExecutionMode = ExecutionMode.DRY_RUN
    command_timestamp: datetime = field(default_factory=datetime.utcnow)
    idempotency_key: str = field(default_factory=lambda: str(uuid.uuid4()))
    raw_response: Optional[dict] = None
    parsed_response: Optional[dict] = None
    order_ack: Optional[bool] = None
    exchange_order_id: Optional[str] = None
    retry_count: int = 0
    verification_result: Optional[bool] = None
    error: Optional[str] = None
    completed_at: Optional[datetime] = None

    @classmethod
    def from_command(cls, cmd: TCLCommand) -> "CommandTranscript":
        """Initialize transcript from TCLCommand before execution."""
        return cls(
            required_command=repr(cmd),
            normalized_command=cmd.normalize(),
            command_type=cmd.command_type,
            exchange=cmd.exchange,
            mode=cmd.mode,
            idempotency_key=cmd.idempotency_key,
        )

    def complete(
        self,
        raw: dict,
        parsed: dict,
        order_id: Optional[str] = None,
    ) -> None:
        """Mark as successfully completed."""
        self.raw_response = raw
        self.parsed_response = parsed
        self.exchange_order_id = order_id
        self.order_ack = True
        self.completed_at = datetime.utcnow()

    def fail(self, error: str) -> None:
        """Mark as failed."""
        self.error = error
        self.order_ack = False
        self.completed_at = datetime.utcnow()

    @property
    def succeeded(self) -> bool:
        return self.order_ack is True and self.error is None


# ─────────────────────────────────────────────────────────────────────────── #
# Dispatcher
# ─────────────────────────────────────────────────────────────────────────── #

class TCLDispatcher:
    """
    Routes TCLCommand to the registered ExchangeAdapter.

    Execution flow (see tcl_spec_v1.md Section 4):
      [1] Idempotency check — duplicate key returns cached transcript
      [2] Adapter lookup — raises AdapterNotFoundError if not registered
      [3] LIVE mode gate — raises LiveModeNotAuthorizedError if FINAL_GO pending
      [4] Auto RISK.CHECK before ORDER.BUY / ORDER.SELL
      [5] Execute via adapter (dry_run or execute based on mode)
      [6] Cache transcript for idempotency
      [7] Return CommandTranscript

    Usage:
        dispatcher = TCLDispatcher()
        dispatcher.register("binance", BinanceAdapter(...))
        transcript = await dispatcher.dispatch(command)
    """

    _RISK_CHECK_REQUIRED: frozenset[CommandType] = frozenset({
        CommandType.ORDER_BUY,
        CommandType.ORDER_SELL,
    })

    def __init__(self) -> None:
        self._adapters: dict[str, "ExchangeAdapter"] = {}
        self._idempotency_cache: dict[str, CommandTranscript] = {}
        self._live_authorized: bool = False

    def register(self, exchange: str, adapter: "ExchangeAdapter") -> None:
        """Register exchange adapter. exchange key is lowercased."""
        self._adapters[exchange.lower()] = adapter

    def authorize_live(self) -> None:
        """
        Authorize LIVE mode. Must be called by B2 after FINAL_GO gate passes.
        Corresponds to Phase 4 → Phase 5 promotion.
        """
        self._live_authorized = True

    def revoke_live(self) -> None:
        """Revoke LIVE mode — revert to DRY_RUN only (e.g., LOCKDOWN)."""
        self._live_authorized = False

    @property
    def live_authorized(self) -> bool:
        return self._live_authorized

    async def dispatch(self, command: TCLCommand) -> CommandTranscript:
        """
        Dispatch command. Returns CommandTranscript (always — even on error).
        Failed transcripts have succeeded=False and error message set.
        """
        # [1] Idempotency check (skip for DRY_RUN — simulation is always re-runnable)
        if command.command_type != CommandType.ORDER_DRY_RUN:
            cached = self._idempotency_cache.get(command.idempotency_key)
            if cached is not None:
                return cached

        # [2] Adapter lookup
        adapter = self._adapters.get(command.exchange.lower())
        if adapter is None:
            t = CommandTranscript.from_command(command)
            t.fail(
                f"AdapterNotFound: no adapter for '{command.exchange}'. "
                f"Registered: {list(self._adapters)}"
            )
            return t

        # [3] LIVE gate
        if command.mode == ExecutionMode.LIVE and not self._live_authorized:
            t = CommandTranscript.from_command(command)
            t.fail(
                "LiveModeNotAuthorized: FINAL_GO not yet achieved. "
                "Phase 4 Shadow Validation still active — DRY_RUN only."
            )
            return t

        # [4] Auto RISK.CHECK before buy/sell
        if command.command_type in self._RISK_CHECK_REQUIRED:
            risk_cmd = TCLCommand(
                command_type=CommandType.RISK_CHECK,
                exchange=command.exchange,
                mode=command.mode,
                symbol=command.symbol,
                quantity=command.quantity,
                extra={"side": command.command_type.value},
            )
            risk_t = await self._run(adapter, risk_cmd)
            if not risk_t.succeeded:
                t = CommandTranscript.from_command(command)
                t.fail(f"Blocked by RISK.CHECK: {risk_t.error}")
                return t

        # [5] Execute
        transcript = await self._run(adapter, command)

        # [6] Cache
        if command.command_type != CommandType.ORDER_DRY_RUN:
            self._idempotency_cache[command.idempotency_key] = transcript

        return transcript

    async def _run(
        self, adapter: "ExchangeAdapter", command: TCLCommand
    ) -> CommandTranscript:
        if command.mode == ExecutionMode.DRY_RUN:
            return await adapter.dry_run(command)
        return await adapter.execute(command)
