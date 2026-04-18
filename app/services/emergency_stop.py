"""
EmergencyStop — Card K (K-4)
Emergency stop protocol for the autonomous trading system.

Provides a fail-closed halt mechanism that:
  - Accepts manual or automatic triggers (drawdown, error rate, etc.)
  - Records every stop event in the HumanOverrideLedger (when available)
  - Checks automatic thresholds via check_auto_triggers()
  - Supports safe resume after human review

Auto-trigger thresholds:
  - portfolio_drawdown > 10 %
  - single_symbol_drawdown > 30 %
  - consecutive_losses > 15
  - system_error_count > 5 in the last 1 hour

Pure computation — no exchange API calls, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from app.core.logging import get_logger
from app.services.symbol_universe import ALL_SYMBOLS

if TYPE_CHECKING:
    from app.services.governance_as_code import GovernanceAsCode
    from app.services.human_override_ledger import HumanOverrideLedger

logger = get_logger(__name__)

# ── Auto-trigger thresholds ───────────────────────────────────────────────────

_THRESHOLD_PORTFOLIO_DD: float = 10.0        # portfolio drawdown %
_THRESHOLD_SYMBOL_DD: float = 30.0           # single-symbol drawdown %
_THRESHOLD_CONSECUTIVE_LOSSES: int = 15      # consecutive losses count
_THRESHOLD_ERROR_COUNT: int = 5              # system errors in last hour
_ERROR_WINDOW_SECONDS: int = 3600            # 1 hour rolling window


# ── Dataclasses ───────────────────────────────────────────────────────────────


@dataclass
class EmergencyStopEvent:
    """A recorded emergency stop event."""

    id: str
    timestamp: datetime
    trigger: str          # "manual" | "drawdown_breach" | "system_error" | "governance_violation"
    reason: str
    affected_symbols: list[str]
    actor: str
    actions_taken: list[str]
    resumed_at: datetime | None = None


# ── Service ───────────────────────────────────────────────────────────────────


class EmergencyStop:
    """Emergency stop protocol for the autonomous trading system.

    Usage::

        es = EmergencyStop()

        # Trigger a manual halt
        event = es.trigger(reason="Risk limit exceeded", actor="operator@firm")

        # Check automatic triggers with current portfolio metrics
        auto_event = es.check_auto_triggers({
            "portfolio_drawdown_pct": 12.5,
            "symbol_drawdowns": {"BTC/USDT": 35.0},
            "consecutive_losses": 16,
            "recent_error_timestamps": [...],
        })

        # Resume after review
        es.resume(event.id, actor="operator@firm", reason="Risk resolved")
    """

    def __init__(
        self,
        governance: GovernanceAsCode | None = None,
        override_ledger: HumanOverrideLedger | None = None,
    ) -> None:
        self._governance = governance
        self._override_ledger = override_ledger

        # Internal state
        self._halted: bool = False
        self._active_stops: list[EmergencyStopEvent] = []
        self._history: list[EmergencyStopEvent] = []

        # Track cancelled symbols (flag-only, no exchange API)
        self._cancelled_symbols: set[str] = set()

    # ── Public API ────────────────────────────────────────────────────────────

    def trigger(
        self,
        reason: str,
        affected_symbols: list[str] | None = None,
        actor: str = "system",
        trigger: str = "manual",
    ) -> EmergencyStopEvent:
        """Trigger an emergency stop.

        Sets the system state to HALTED, flags all pending orders for
        cancellation, records the event in the override ledger, and logs
        a CRITICAL entry.

        Args:
            reason: Human-readable explanation for the halt.
            affected_symbols: Specific symbols affected. Defaults to ALL_SYMBOLS.
            actor: Identifier of the initiating actor (operator or 'system').
            trigger: One of "manual", "drawdown_breach", "system_error",
                "governance_violation".

        Returns:
            The created EmergencyStopEvent.
        """
        symbols = affected_symbols if affected_symbols is not None else list(ALL_SYMBOLS)

        # 1. Set system state to HALTED
        self._halted = True

        # 2. Flag affected symbols for order cancellation (no exchange API)
        for sym in symbols:
            self._cancelled_symbols.add(sym)

        actions_taken: list[str] = [
            "system_state_set_to_HALTED",
            f"pending_orders_flagged_for_cancellation: {', '.join(symbols)}",
        ]

        # 3. Record in override ledger
        ledger_recorded = False
        if self._override_ledger is not None:
            try:
                self._override_ledger.record(
                    actor=actor,
                    action="emergency_stop",
                    reason=reason,
                    resource="system/emergency_stop",
                    prev_state={"halted": False, "trigger": None},
                    new_state={"halted": True, "trigger": trigger, "reason": reason},
                )
                actions_taken.append("override_ledger_recorded")
                ledger_recorded = True
            except Exception as exc:  # pragma: no cover
                logger.error(
                    "emergency_stop_ledger_record_failed",
                    error=str(exc),
                )

        if not ledger_recorded:
            actions_taken.append("override_ledger_unavailable_skipped")

        # 4. Log critical event
        logger.critical(
            "EMERGENCY_STOP_TRIGGERED",
            trigger=trigger,
            reason=reason,
            actor=actor,
            affected_symbols=symbols,
            actions_taken=actions_taken,
        )

        event = EmergencyStopEvent(
            id=str(uuid4()),
            timestamp=datetime.now(timezone.utc),
            trigger=trigger,
            reason=reason,
            affected_symbols=symbols,
            actor=actor,
            actions_taken=actions_taken,
            resumed_at=None,
        )

        self._active_stops.append(event)
        self._history.append(event)

        return event

    def resume(self, event_id: str, actor: str, reason: str) -> bool:
        """Resume the system from an emergency stop after human review.

        Clears the HALTED state only when the specified event is still active.
        Records the resumption in the override ledger.

        Args:
            event_id: ID of the EmergencyStopEvent being resolved.
            actor: Identifier of the operator authorising the resume.
            reason: Explanation of why it is safe to resume.

        Returns:
            True if resume was successful, False if the event was not found
            among active stops.
        """
        target: EmergencyStopEvent | None = None
        for event in self._active_stops:
            if event.id == event_id:
                target = event
                break

        if target is None:
            logger.warning(
                "emergency_stop_resume_not_found",
                event_id=event_id,
                actor=actor,
            )
            return False

        resumed_at = datetime.now(timezone.utc)
        target.resumed_at = resumed_at
        target.actions_taken.append(f"resumed_by:{actor} reason:{reason}")

        # Remove from active stops
        self._active_stops = [e for e in self._active_stops if e.id != event_id]

        # Only clear halted flag when no active stops remain
        if not self._active_stops:
            self._halted = False
            self._cancelled_symbols.clear()

        # Record in override ledger
        if self._override_ledger is not None:
            try:
                self._override_ledger.record(
                    actor=actor,
                    action="emergency_stop_resume",
                    reason=reason,
                    resource=f"system/emergency_stop/{event_id}",
                    prev_state={"halted": True, "event_id": event_id},
                    new_state={
                        "halted": self._halted,
                        "event_id": event_id,
                        "resumed_at": resumed_at.isoformat(),
                    },
                )
            except Exception as exc:  # pragma: no cover
                logger.error(
                    "emergency_stop_resume_ledger_failed",
                    error=str(exc),
                )

        logger.info(
            "emergency_stop_resumed",
            event_id=event_id,
            actor=actor,
            reason=reason,
            still_halted=self._halted,
        )

        return True

    def is_halted(self) -> bool:
        """Return True if the system is currently in emergency halt state."""
        return self._halted

    def get_active_stops(self) -> list[EmergencyStopEvent]:
        """Return all currently active (not yet resumed) stop events."""
        return list(self._active_stops)

    def get_history(self) -> list[EmergencyStopEvent]:
        """Return the full history of all stop events (including resumed ones)."""
        return list(self._history)

    def check_auto_triggers(
        self, portfolio_metrics: dict
    ) -> EmergencyStopEvent | None:
        """Check automatic stop triggers against current portfolio metrics.

        Evaluates the following thresholds:
          - portfolio_drawdown_pct > 10 %
          - any symbol drawdown > 30 %
          - consecutive_losses > 15
          - system errors in last 1 hour > 5

        If the system is already halted, checks are skipped (fail-closed:
        do not un-halt automatically).

        Args:
            portfolio_metrics: Dict with optional keys:
                - portfolio_drawdown_pct (float)
                - symbol_drawdowns (dict[str, float])
                - consecutive_losses (int)
                - recent_error_timestamps (list[datetime | str])

        Returns:
            EmergencyStopEvent if a threshold was breached, else None.
        """
        if self._halted:
            # Already stopped — do not produce another event
            return None

        # ── Check 1: portfolio drawdown ────────────────────────────────────
        portfolio_dd = float(portfolio_metrics.get("portfolio_drawdown_pct", 0.0))
        if portfolio_dd > _THRESHOLD_PORTFOLIO_DD:
            return self.trigger(
                reason=(
                    f"Portfolio drawdown {portfolio_dd:.2f}% exceeds threshold "
                    f"{_THRESHOLD_PORTFOLIO_DD:.0f}%"
                ),
                trigger="drawdown_breach",
                actor="system",
            )

        # ── Check 2: single-symbol drawdown ───────────────────────────────
        symbol_drawdowns: dict[str, float] = portfolio_metrics.get(
            "symbol_drawdowns", {}
        )
        for sym, dd in symbol_drawdowns.items():
            dd = float(dd)
            if dd > _THRESHOLD_SYMBOL_DD:
                return self.trigger(
                    reason=(
                        f"Symbol {sym} drawdown {dd:.2f}% exceeds threshold "
                        f"{_THRESHOLD_SYMBOL_DD:.0f}%"
                    ),
                    affected_symbols=[sym],
                    trigger="drawdown_breach",
                    actor="system",
                )

        # ── Check 3: consecutive losses ───────────────────────────────────
        consecutive_losses = int(portfolio_metrics.get("consecutive_losses", 0))
        if consecutive_losses > _THRESHOLD_CONSECUTIVE_LOSSES:
            return self.trigger(
                reason=(
                    f"Consecutive losses {consecutive_losses} exceeds threshold "
                    f"{_THRESHOLD_CONSECUTIVE_LOSSES}"
                ),
                trigger="system_error",
                actor="system",
            )

        # ── Check 4: system error rate ────────────────────────────────────
        error_count_in_window = self._count_recent_errors(
            portfolio_metrics.get("recent_error_timestamps", [])
        )
        if error_count_in_window > _THRESHOLD_ERROR_COUNT:
            return self.trigger(
                reason=(
                    f"System error count {error_count_in_window} in last 1h exceeds "
                    f"threshold {_THRESHOLD_ERROR_COUNT}"
                ),
                trigger="system_error",
                actor="system",
            )

        return None

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _count_recent_errors(
        self, error_timestamps: list[datetime | str]
    ) -> int:
        """Count error timestamps falling within the last ERROR_WINDOW_SECONDS.

        Accepts datetime objects or ISO-8601 strings.

        Args:
            error_timestamps: List of error occurrence timestamps.

        Returns:
            Count of errors within the rolling 1-hour window.
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=_ERROR_WINDOW_SECONDS)
        count = 0

        for ts in error_timestamps:
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts)
                except ValueError:
                    continue

            # Ensure timezone-aware for comparison
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

            if ts >= cutoff:
                count += 1

        return count
