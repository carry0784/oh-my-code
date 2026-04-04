"""
Exchange Adapters — TCL Abstract Base Class
K-Dexter AOS — TCL Spec v1

All exchange adapters must subclass ExchangeAdapter and implement
the abstract methods. The TCLDispatcher calls these methods; upper
layers (L6/L8) never call adapters directly.

Supported exchanges:
  - Binance       (ccxt, spot)
  - Bitget        (ccxt, spot)
  - Upbit         (ccxt, KRW pairs)
  - KIS           (한국투자증권 REST API, 국내 주식)
  - Kiwoom        (키움증권 COM/OpenAPI+, 국내 주식)

B1 Doctrine:
  - Adapters translate standard TCL commands to exchange-specific API calls
  - Adapters never introduce exchange-specific logic into upper layers
  - CLI-like abstraction required for exchanges without REST CLI (e.g., Kiwoom)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from kdexter.tcl.commands import TCLCommand, CommandTranscript


class ExchangeAdapter(ABC):
    """
    Abstract base class for all K-Dexter exchange adapters.

    Every adapter must implement:
      execute()        — live order execution
      dry_run()        — simulation (no real orders)
      verify()         — confirm order fill status
      cancel()         — cancel open order
      query_position() — current position
      query_balance()  — account balance

    Implementation guidelines:
      - Wrap all exchange exceptions into CommandTranscript.fail(error)
        Never let exchange-specific exceptions propagate to upper layers.
      - Set exchange_order_id in transcript on successful order placement.
      - DRY_RUN must never submit real orders — use exchange sandbox or
        internal simulation.
      - All methods must be async (non-blocking I/O).
    """

    @property
    @abstractmethod
    def exchange_id(self) -> str:
        """Lowercase exchange identifier e.g. 'binance', 'upbit'."""

    @abstractmethod
    async def execute(self, command: TCLCommand) -> CommandTranscript:
        """
        Execute command against the live exchange.
        Returns CommandTranscript with raw_response, parsed_response, exchange_order_id.
        """

    @abstractmethod
    async def dry_run(self, command: TCLCommand) -> CommandTranscript:
        """
        Simulate command execution without placing real orders.
        Must mirror the structure of execute() response.
        """

    @abstractmethod
    async def verify(self, exchange_order_id: str) -> CommandTranscript:
        """Query exchange for order fill status (ORDER.VERIFY)."""

    @abstractmethod
    async def cancel(self, exchange_order_id: str) -> CommandTranscript:
        """Cancel an open order (ORDER.CANCEL)."""

    @abstractmethod
    async def query_position(self, symbol: Optional[str] = None) -> CommandTranscript:
        """Query current position (POSITION.QUERY)."""

    @abstractmethod
    async def query_balance(self, currency: Optional[str] = None) -> CommandTranscript:
        """Query account balance (BALANCE.QUERY)."""

    # ── Shared helpers ──────────────────────────────────────────────────── #

    def _base_transcript(self, command: TCLCommand) -> CommandTranscript:
        """Create a pre-filled transcript from command."""
        return CommandTranscript.from_command(command)

    def _safe_fail(self, transcript: CommandTranscript, exc: Exception) -> CommandTranscript:
        """Wrap any exception into transcript.fail() — prevents exception leakage."""
        transcript.fail(f"{type(exc).__name__}: {exc}")
        return transcript
