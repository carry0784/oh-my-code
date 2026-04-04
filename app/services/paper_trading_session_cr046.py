"""
CR-046 Paper Trading Session Manager

Layer separation:
  - CR046PaperTradingManager: Pure computation only. No I/O.
  - Task layer (sol_paper_tasks / btc_paper_tasks) handles all I/O.

Time policy:
  - daily_pnl reset: UTC 00:00
  - weekly_trades reset: Monday UTC 00:00 (fixed 7-day, not rolling)
  - consecutive_losing_days reset: on profit day
  - All timing values in ms
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


# ---------------------------------------------------------------------------
# State constants (fail-closed state machine)
# ---------------------------------------------------------------------------


class BarAction:
    READY = "READY"
    SKIP_SIGNAL_NONE = "SKIP_SIGNAL_NONE"
    SKIP_GOVERNANCE_BLOCK = "SKIP_GOVERNANCE_BLOCK"
    SKIP_SESSION_BLOCK = "SKIP_SESSION_BLOCK"
    SKIP_LATENCY_GUARD = "SKIP_LATENCY_GUARD"
    ENTER_DRY_RUN = "ENTER_DRY_RUN"
    EXIT_TP = "EXIT_TP"
    EXIT_SL = "EXIT_SL"
    EXIT_REVERSE = "EXIT_REVERSE"
    HALTED_KILL_SWITCH = "HALTED_KILL_SWITCH"
    SKIP_DUPLICATE_BAR = "SKIP_DUPLICATE_BAR"
    ERROR_FAIL_CLOSED = "ERROR_FAIL_CLOSED"


# ---------------------------------------------------------------------------
# Session dataclass
# ---------------------------------------------------------------------------


@dataclass
class CR046PaperSession:
    session_id: str = ""
    symbol: str = ""
    started_at: str = ""
    daily_pnl: float = 0.0
    weekly_trades: int = 0
    consecutive_losing_days: int = 0
    is_halted: bool = False
    halt_reason: str | None = None
    open_position: dict | None = None
    last_daily_reset_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_weekly_reset_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1
    last_updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Receipt dataclasses
# ---------------------------------------------------------------------------


@dataclass
class PaperTradingReceipt:
    receipt_id: str = field(default_factory=lambda: str(uuid4()))
    session_id: str = ""
    strategy_version: str = "SMC_WaveTrend_1H_v2"
    bar_ts: int = 0
    symbol: str = ""
    signal: str | None = None
    consensus_pass: bool = False
    session_can_enter: bool = False
    guard_pass: bool | None = None
    guard_details: dict | None = None
    action: str = BarAction.READY
    decision_source: str = ""
    dry_run: bool = True
    entry_price: float | None = None
    expected_sl: float | None = None
    expected_tp: float | None = None
    halt_state: bool = False
    block_reason: str | None = None
    execution_latency_ms: float | None = None
    api_latency_ms: float | None = None
    spread_pct: float | None = None


@dataclass
class PromotionReceipt:
    receipt_id: str = field(default_factory=lambda: str(uuid4()))
    session_id: str = ""
    promotion_target: str = ""
    promotion_basis: str = ""
    approved_by: str = ""
    approved_at: str = ""
    linked_receipt_ids: list[str] = field(default_factory=list)
    risk_notes: str | None = None


# ---------------------------------------------------------------------------
# Manager (pure computation, no I/O)
# ---------------------------------------------------------------------------

SL_PCT = 0.02  # 2% stop-loss
TP_PCT = 0.04  # 4% take-profit
DAILY_LOSS_LIMIT = -0.05  # -5%
WEEKLY_TRADE_CAP = 15
MAX_POSITIONS = 1


class CR046PaperTradingManager:
    """Pure computation. No I/O. No DB access. No logging."""

    def can_enter(
        self,
        session: CR046PaperSession,
        signal: str | None,
    ) -> tuple[bool, str]:
        """Check if a new position can be entered.

        Returns (can_enter, reason).
        """
        if session.is_halted:
            return False, f"session_halted:{session.halt_reason}"

        if signal is None:
            return False, "no_signal"

        if session.daily_pnl <= DAILY_LOSS_LIMIT:
            return False, f"daily_loss_limit:{session.daily_pnl:.4f}"

        if session.weekly_trades >= WEEKLY_TRADE_CAP:
            return False, f"weekly_cap:{session.weekly_trades}"

        if session.open_position is not None:
            return False, "max_position_reached"

        return True, "ok"

    def check_exit(
        self,
        session: CR046PaperSession,
        current_price: float,
        bar_ts: int,
        reverse_signal: str | None = None,
    ) -> tuple[bool, str]:
        """Check if the open position should be exited.

        Returns (should_exit, reason).
        """
        pos = session.open_position
        if pos is None:
            return False, "no_position"

        entry_price = pos["entry_price"]
        direction = pos["direction"]  # "LONG" or "SHORT"

        if direction == "LONG":
            pnl_pct = (current_price - entry_price) / entry_price
            if pnl_pct <= -SL_PCT:
                return True, "stop_loss"
            if pnl_pct >= TP_PCT:
                return True, "take_profit"
        else:  # SHORT
            pnl_pct = (entry_price - current_price) / entry_price
            if pnl_pct <= -SL_PCT:
                return True, "stop_loss"
            if pnl_pct >= TP_PCT:
                return True, "take_profit"

        if reverse_signal is not None and reverse_signal != direction:
            return True, "reverse_signal"

        return False, "hold"

    def compute_close(
        self,
        session: CR046PaperSession,
        exit_price: float,
        exit_reason: str,
    ) -> dict[str, Any]:
        """Compute close result. Returns dict, NO I/O.

        Returns: {pnl_delta, exit_reason, updated_fields}
        """
        pos = session.open_position
        if pos is None:
            return {"pnl_delta": 0.0, "exit_reason": exit_reason, "updated_fields": {}}

        entry_price = pos["entry_price"]
        direction = pos["direction"]

        if direction == "LONG":
            pnl_delta = (exit_price - entry_price) / entry_price
        else:
            pnl_delta = (entry_price - exit_price) / entry_price

        return {
            "pnl_delta": pnl_delta,
            "exit_reason": exit_reason,
            "updated_fields": {
                "daily_pnl": session.daily_pnl + pnl_delta,
                "open_position": None,
            },
        }

    def apply_kill_switches(
        self,
        session: CR046PaperSession,
    ) -> tuple[bool, str | None]:
        """Check kill-switches. Returns (should_halt, reason).

        Kill-switches:
        K1: daily loss > 5%
        K2: weekly loss > 10% (approximated by trade count + daily_pnl)
        K3: 3x consecutive losing days
        K4: exchange API down (checked externally)
        K5: A manual override (checked externally)
        """
        if session.daily_pnl <= DAILY_LOSS_LIMIT:
            return True, "K1:daily_loss_exceeded"

        if session.consecutive_losing_days >= 3:
            return True, "K3:3_consecutive_losing_days"

        return False, None

    def check_and_reset_daily(
        self,
        session: CR046PaperSession,
        current_utc: datetime,
    ) -> CR046PaperSession:
        """Reset daily counters if UTC midnight has passed."""
        last_reset = session.last_daily_reset_utc
        # Check if we've crossed UTC midnight
        if current_utc.date() > last_reset.date():
            # Check if previous day was losing
            if session.daily_pnl < 0:
                session.consecutive_losing_days += 1
            elif session.daily_pnl > 0:
                session.consecutive_losing_days = 0

            session.daily_pnl = 0.0
            session.last_daily_reset_utc = current_utc.replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            # Un-halt K1 on new day (auto-resume)
            if session.is_halted and session.halt_reason == "K1:daily_loss_exceeded":
                session.is_halted = False
                session.halt_reason = None

        return session

    def check_and_reset_weekly(
        self,
        session: CR046PaperSession,
        current_utc: datetime,
    ) -> CR046PaperSession:
        """Reset weekly counters if Monday UTC 00:00 has passed."""
        last_reset = session.last_weekly_reset_utc

        # Find the most recent Monday UTC 00:00
        days_since_monday = current_utc.weekday()  # 0=Monday
        this_monday = current_utc.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        if days_since_monday > 0:
            from datetime import timedelta

            this_monday = this_monday - timedelta(days=days_since_monday)

        if this_monday > last_reset:
            session.weekly_trades = 0
            session.last_weekly_reset_utc = this_monday

        return session
