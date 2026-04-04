"""
Execution Cell -- L8 K-Dexter AOS v4

Converts sized signals into TCL commands and dispatches them.
This is the final stage of the L4~L8 pipeline before the order
hits the exchange via TCL.

Responsibilities:
  1. Convert Signal -> TCLCommand
  2. Dispatch via TCLDispatcher (D-001: TCL-only execution)
  3. Track execution results
  4. Produce evidence bundles (M-07)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from kdexter.audit.evidence_store import EvidenceBundle, EvidenceStore
from kdexter.strategy.signal import Signal, SignalDirection, SignalStatus
from kdexter.tcl.commands import (
    CommandTranscript,
    CommandType,
    ExecutionMode,
    OrderType,
    TCLCommand,
    TCLDispatcher,
)


# ------------------------------------------------------------------ #
# Data models
# ------------------------------------------------------------------ #


@dataclass
class ExecutionResult:
    """Result of executing a signal through TCL."""

    signal_id: str
    transcript: Optional[CommandTranscript] = None
    success: bool = False
    error: Optional[str] = None
    executed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ------------------------------------------------------------------ #
# L8 Execution Cell
# ------------------------------------------------------------------ #


class ExecutionCell:
    """
    L8 Execution Cell.

    Converts sized signals to TCL commands and dispatches them.
    Tracks all execution results and produces evidence.

    Usage:
        cell = ExecutionCell(tcl=dispatcher, evidence=store)
        result = await cell.execute(signal)
        if result.success:
            # order placed
    """

    def __init__(
        self,
        tcl: TCLDispatcher,
        evidence: EvidenceStore,
        default_mode: ExecutionMode = ExecutionMode.DRY_RUN,
    ) -> None:
        self._tcl = tcl
        self._evidence = evidence
        self._default_mode = default_mode
        self._results: list[ExecutionResult] = []

    @property
    def default_mode(self) -> ExecutionMode:
        return self._default_mode

    @default_mode.setter
    def default_mode(self, mode: ExecutionMode) -> None:
        self._default_mode = mode

    async def execute(
        self,
        signal: Signal,
        mode: Optional[ExecutionMode] = None,
    ) -> ExecutionResult:
        """
        Convert signal to TCL command and dispatch.

        Args:
            signal: must be SIZED (has quantity)
            mode: override execution mode (default: self._default_mode)

        Returns:
            ExecutionResult with transcript
        """
        exec_mode = mode or self._default_mode

        # Validate signal state
        if signal.status != SignalStatus.SIZED:
            result = ExecutionResult(
                signal_id=signal.signal_id,
                success=False,
                error=f"Signal not sized (status={signal.status.value})",
            )
            self._results.append(result)
            return result

        if signal.quantity is None or signal.quantity <= 0:
            result = ExecutionResult(
                signal_id=signal.signal_id,
                success=False,
                error="Signal quantity is zero or None",
            )
            self._results.append(result)
            return result

        # Build TCL command
        cmd = self._build_command(signal, exec_mode)

        # Dispatch via TCL (D-001 compliant)
        transcript = await self._tcl.dispatch(cmd)

        # Update signal status
        if transcript.succeeded:
            signal.mark_dispatched()
            # In DRY_RUN, we consider dispatched as "filled" for pipeline completeness
            if exec_mode == ExecutionMode.DRY_RUN:
                signal.mark_filled()
        else:
            signal.reject(f"TCL dispatch failed: {transcript.error}")

        # Record evidence (M-07)
        bundle = EvidenceBundle(
            trigger=f"ExecutionCell.execute",
            actor="L8_ExecutionCell",
            action=f"{signal.direction.value} {signal.symbol} qty={signal.quantity}",
            before_state=SignalStatus.SIZED.value,
            after_state=signal.status.value,
            artifacts=[
                {
                    "signal_id": signal.signal_id,
                    "transcript_id": transcript.transcript_id,
                    "succeeded": transcript.succeeded,
                    "mode": exec_mode.value,
                }
            ],
        )
        self._evidence.store(bundle)

        result = ExecutionResult(
            signal_id=signal.signal_id,
            transcript=transcript,
            success=transcript.succeeded,
            error=transcript.error,
        )
        self._results.append(result)
        return result

    def _build_command(self, signal: Signal, mode: ExecutionMode) -> TCLCommand:
        """Convert Signal to TCLCommand."""
        if signal.direction == SignalDirection.BUY:
            cmd_type = CommandType.ORDER_BUY
        elif signal.direction == SignalDirection.SELL:
            cmd_type = CommandType.ORDER_SELL
        else:
            # HOLD signals should not reach execution
            cmd_type = CommandType.POSITION_QUERY

        order_type = OrderType.MARKET
        if signal.entry_price is not None:
            order_type = OrderType.LIMIT

        return TCLCommand(
            command_type=cmd_type,
            exchange=signal.exchange,
            mode=mode,
            symbol=signal.symbol,
            quantity=signal.quantity,
            price=signal.entry_price,
            order_type=order_type,
            extra={
                "signal_id": signal.signal_id,
                "strategy_id": signal.strategy_id,
                "stop_loss": signal.stop_loss,
                "take_profit": signal.take_profit,
            },
        )

    def results(self) -> list[ExecutionResult]:
        return list(self._results)

    def success_rate(self) -> float:
        if not self._results:
            return 0.0
        return sum(1 for r in self._results if r.success) / len(self._results)
