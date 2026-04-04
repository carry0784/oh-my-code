"""CR-046 Paper Session Manager Tests"""

import pytest
from datetime import datetime, timezone

from app.services.paper_trading_session_cr046 import (
    CR046PaperSession,
    CR046PaperTradingManager,
    PaperTradingReceipt,
    BarAction,
    DAILY_LOSS_LIMIT,
    WEEKLY_TRADE_CAP,
    SL_PCT,
    TP_PCT,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clean_session(**kwargs) -> CR046PaperSession:
    """Return a clean session with sane defaults, overridable via kwargs."""
    defaults = dict(
        session_id="test-session-001",
        symbol="SOL/USDT",
        daily_pnl=0.0,
        weekly_trades=0,
        consecutive_losing_days=0,
        is_halted=False,
        halt_reason=None,
        open_position=None,
        last_daily_reset_utc=datetime(2026, 3, 31, 0, 0, tzinfo=timezone.utc),
        last_weekly_reset_utc=datetime(2026, 3, 30, 0, 0, tzinfo=timezone.utc),
    )
    defaults.update(kwargs)
    return CR046PaperSession(**defaults)


def _long_position(entry_price: float = 100.0) -> dict:
    return {"direction": "LONG", "entry_price": entry_price}


def _short_position(entry_price: float = 100.0) -> dict:
    return {"direction": "SHORT", "entry_price": entry_price}


mgr = CR046PaperTradingManager()


# ---------------------------------------------------------------------------
# TestCanEnter
# ---------------------------------------------------------------------------


class TestCanEnter:
    def test_daily_loss_limit_blocks_entry(self):
        # daily_pnl below limit (-0.06 < -0.05) must block
        session = _clean_session(daily_pnl=-0.06)
        ok, reason = mgr.can_enter(session, "LONG")
        assert ok is False
        assert "daily_loss_limit" in reason

    def test_daily_loss_limit_at_exact_boundary_blocks(self):
        # daily_pnl exactly equal to limit must also block (<=)
        session = _clean_session(daily_pnl=DAILY_LOSS_LIMIT)
        ok, reason = mgr.can_enter(session, "LONG")
        assert ok is False
        assert "daily_loss_limit" in reason

    def test_weekly_cap_blocks_entry(self):
        # weekly_trades == WEEKLY_TRADE_CAP must block
        session = _clean_session(weekly_trades=15)
        ok, reason = mgr.can_enter(session, "LONG")
        assert ok is False
        assert "weekly_cap" in reason

    def test_weekly_cap_below_limit_does_not_block(self):
        # weekly_trades == 14 must not block on cap alone
        session = _clean_session(weekly_trades=14)
        ok, _ = mgr.can_enter(session, "LONG")
        assert ok is True

    def test_max_position_blocks_second_entry(self):
        # open_position not None must block a new entry
        session = _clean_session(open_position=_long_position())
        ok, reason = mgr.can_enter(session, "LONG")
        assert ok is False
        assert reason == "max_position_reached"

    def test_halted_session_blocks(self):
        # is_halted=True must block regardless of other state
        session = _clean_session(is_halted=True, halt_reason="K1:daily_loss_exceeded")
        ok, reason = mgr.can_enter(session, "LONG")
        assert ok is False
        assert "session_halted" in reason

    def test_no_signal_blocks(self):
        # signal=None must block
        session = _clean_session()
        ok, reason = mgr.can_enter(session, None)
        assert ok is False
        assert reason == "no_signal"

    def test_normal_entry_allowed(self):
        # Clean session with a valid signal must be allowed
        session = _clean_session()
        ok, reason = mgr.can_enter(session, "LONG")
        assert ok is True
        assert reason == "ok"

    def test_normal_entry_short_allowed(self):
        session = _clean_session()
        ok, reason = mgr.can_enter(session, "SHORT")
        assert ok is True
        assert reason == "ok"

    def test_halt_checked_before_signal(self):
        # Halted session must block even when signal is None (halt checked first)
        session = _clean_session(is_halted=True, halt_reason="K3:3_consecutive_losing_days")
        ok, reason = mgr.can_enter(session, None)
        assert ok is False
        assert "session_halted" in reason


# ---------------------------------------------------------------------------
# TestCheckExit
# ---------------------------------------------------------------------------


class TestCheckExit:
    def test_sl_exit_long(self):
        # LONG, price drops exactly SL_PCT (2%) -> stop_loss
        entry = 100.0
        session = _clean_session(open_position=_long_position(entry))
        exit_price = entry * (1 - SL_PCT)  # 98.0
        should_exit, reason = mgr.check_exit(session, exit_price, bar_ts=0)
        assert should_exit is True
        assert reason == "stop_loss"

    def test_sl_exit_long_beyond(self):
        # LONG, price drops more than SL_PCT -> stop_loss
        entry = 100.0
        session = _clean_session(open_position=_long_position(entry))
        exit_price = entry * 0.97  # -3%
        should_exit, reason = mgr.check_exit(session, exit_price, bar_ts=0)
        assert should_exit is True
        assert reason == "stop_loss"

    def test_tp_exit_long(self):
        # LONG, price rises exactly TP_PCT (4%) -> take_profit
        entry = 100.0
        session = _clean_session(open_position=_long_position(entry))
        exit_price = entry * (1 + TP_PCT)  # 104.0
        should_exit, reason = mgr.check_exit(session, exit_price, bar_ts=0)
        assert should_exit is True
        assert reason == "take_profit"

    def test_tp_exit_long_beyond(self):
        # LONG, price rises beyond TP -> take_profit
        entry = 100.0
        session = _clean_session(open_position=_long_position(entry))
        exit_price = entry * 1.05  # +5%
        should_exit, reason = mgr.check_exit(session, exit_price, bar_ts=0)
        assert should_exit is True
        assert reason == "take_profit"

    def test_sl_exit_short(self):
        # SHORT, price rises exactly SL_PCT -> stop_loss
        entry = 100.0
        session = _clean_session(open_position=_short_position(entry))
        exit_price = entry * (1 + SL_PCT)  # 102.0
        should_exit, reason = mgr.check_exit(session, exit_price, bar_ts=0)
        assert should_exit is True
        assert reason == "stop_loss"

    def test_tp_exit_short(self):
        # SHORT, price drops exactly TP_PCT -> take_profit
        entry = 100.0
        session = _clean_session(open_position=_short_position(entry))
        exit_price = entry * (1 - TP_PCT)  # 96.0
        should_exit, reason = mgr.check_exit(session, exit_price, bar_ts=0)
        assert should_exit is True
        assert reason == "take_profit"

    def test_reverse_signal_exit(self):
        # LONG position, reverse_signal="SHORT" -> reverse_signal
        session = _clean_session(open_position=_long_position(100.0))
        # price within normal range so SL/TP will not trigger first
        should_exit, reason = mgr.check_exit(session, 101.0, bar_ts=0, reverse_signal="SHORT")
        assert should_exit is True
        assert reason == "reverse_signal"

    def test_reverse_signal_same_direction_no_exit(self):
        # LONG position, reverse_signal="LONG" -> same direction, no reverse exit
        session = _clean_session(open_position=_long_position(100.0))
        should_exit, reason = mgr.check_exit(session, 101.0, bar_ts=0, reverse_signal="LONG")
        assert should_exit is False
        assert reason == "hold"

    def test_hold_when_within_range(self):
        # price within SL/TP range, no reverse signal -> hold
        entry = 100.0
        session = _clean_session(open_position=_long_position(entry))
        # +1% -- within the 2% SL and 4% TP window
        should_exit, reason = mgr.check_exit(session, 101.0, bar_ts=0)
        assert should_exit is False
        assert reason == "hold"

    def test_no_position_returns_false(self):
        # No open position -> no exit
        session = _clean_session()
        should_exit, reason = mgr.check_exit(session, 100.0, bar_ts=0)
        assert should_exit is False
        assert reason == "no_position"


# ---------------------------------------------------------------------------
# TestComputeClose
# ---------------------------------------------------------------------------


class TestComputeClose:
    def test_compute_close_returns_dict_no_io(self):
        # Must return a plain dict with the expected keys
        session = _clean_session(open_position=_long_position(100.0))
        result = mgr.compute_close(session, exit_price=103.0, exit_reason="take_profit")
        assert isinstance(result, dict)
        assert "pnl_delta" in result
        assert "exit_reason" in result
        assert "updated_fields" in result

    def test_compute_close_updated_fields_structure(self):
        # updated_fields must contain daily_pnl and open_position=None
        session = _clean_session(open_position=_long_position(100.0))
        result = mgr.compute_close(session, exit_price=103.0, exit_reason="take_profit")
        uf = result["updated_fields"]
        assert "daily_pnl" in uf
        assert uf["open_position"] is None

    def test_long_profitable_close(self):
        # entry 100, exit 103 -> pnl_delta ~= 0.03
        session = _clean_session(open_position=_long_position(100.0))
        result = mgr.compute_close(session, exit_price=103.0, exit_reason="take_profit")
        assert abs(result["pnl_delta"] - 0.03) < 1e-10

    def test_long_loss_close(self):
        # entry 100, exit 98 -> pnl_delta ~= -0.02
        session = _clean_session(open_position=_long_position(100.0))
        result = mgr.compute_close(session, exit_price=98.0, exit_reason="stop_loss")
        assert abs(result["pnl_delta"] - (-0.02)) < 1e-10

    def test_short_profitable_close(self):
        # entry 100, exit 97 -> pnl_delta ~= 0.03
        session = _clean_session(open_position=_short_position(100.0))
        result = mgr.compute_close(session, exit_price=97.0, exit_reason="take_profit")
        assert abs(result["pnl_delta"] - 0.03) < 1e-10

    def test_short_loss_close(self):
        # entry 100, exit 102 -> pnl_delta ~= -0.02
        session = _clean_session(open_position=_short_position(100.0))
        result = mgr.compute_close(session, exit_price=102.0, exit_reason="stop_loss")
        assert abs(result["pnl_delta"] - (-0.02)) < 1e-10

    def test_daily_pnl_accumulated_in_updated_fields(self):
        # existing daily_pnl=0.01, profitable close +0.03 -> updated daily_pnl ~= 0.04
        session = _clean_session(daily_pnl=0.01, open_position=_long_position(100.0))
        result = mgr.compute_close(session, exit_price=103.0, exit_reason="take_profit")
        assert abs(result["updated_fields"]["daily_pnl"] - 0.04) < 1e-10

    def test_exit_reason_preserved(self):
        session = _clean_session(open_position=_long_position(100.0))
        result = mgr.compute_close(session, exit_price=98.0, exit_reason="stop_loss")
        assert result["exit_reason"] == "stop_loss"

    def test_no_position_returns_zero_delta(self):
        # No open position -> pnl_delta = 0.0
        session = _clean_session()
        result = mgr.compute_close(session, exit_price=100.0, exit_reason="manual")
        assert result["pnl_delta"] == 0.0
        assert result["updated_fields"] == {}

    def test_source_session_not_mutated(self):
        # compute_close must not mutate the session (pure function contract)
        session = _clean_session(daily_pnl=0.0, open_position=_long_position(100.0))
        mgr.compute_close(session, exit_price=103.0, exit_reason="take_profit")
        assert session.open_position is not None
        assert session.daily_pnl == 0.0


# ---------------------------------------------------------------------------
# TestKillSwitches
# ---------------------------------------------------------------------------


class TestKillSwitches:
    def test_kill_switch_daily_loss(self):
        # daily_pnl <= DAILY_LOSS_LIMIT -> K1
        session = _clean_session(daily_pnl=-0.06)
        should_halt, reason = mgr.apply_kill_switches(session)
        assert should_halt is True
        assert "K1" in reason
        assert "daily_loss" in reason

    def test_kill_switch_daily_loss_exact_boundary(self):
        # daily_pnl == DAILY_LOSS_LIMIT -> K1
        session = _clean_session(daily_pnl=DAILY_LOSS_LIMIT)
        should_halt, reason = mgr.apply_kill_switches(session)
        assert should_halt is True
        assert "K1" in reason

    def test_kill_switch_consecutive_losing_days(self):
        # 3 consecutive losing days -> K3
        session = _clean_session(consecutive_losing_days=3)
        should_halt, reason = mgr.apply_kill_switches(session)
        assert should_halt is True
        assert "K3" in reason
        assert "consecutive" in reason

    def test_kill_switch_consecutive_losing_days_more_than_3(self):
        # More than 3 is also K3
        session = _clean_session(consecutive_losing_days=5)
        should_halt, reason = mgr.apply_kill_switches(session)
        assert should_halt is True
        assert "K3" in reason

    def test_no_kill_switch_normal(self):
        # Clean session -> no halt
        session = _clean_session()
        should_halt, reason = mgr.apply_kill_switches(session)
        assert should_halt is False
        assert reason is None

    def test_no_kill_switch_2_consecutive_losing_days(self):
        # 2 consecutive losing days -> not yet K3
        session = _clean_session(consecutive_losing_days=2)
        should_halt, reason = mgr.apply_kill_switches(session)
        assert should_halt is False
        assert reason is None

    def test_no_kill_switch_daily_pnl_just_above_limit(self):
        # daily_pnl slightly above limit -> no kill
        session = _clean_session(daily_pnl=-0.04)
        should_halt, reason = mgr.apply_kill_switches(session)
        assert should_halt is False
        assert reason is None


# ---------------------------------------------------------------------------
# TestReceipt
# ---------------------------------------------------------------------------


class TestReceipt:
    def test_receipt_all_fields_present(self):
        receipt = PaperTradingReceipt()
        assert receipt.receipt_id  # UUID generated, non-empty
        assert receipt.dry_run is True
        assert receipt.action == BarAction.READY
        assert hasattr(receipt, "session_id")
        assert hasattr(receipt, "decision_source")
        assert hasattr(receipt, "bar_ts")

    def test_receipt_uuid_unique_per_instance(self):
        r1 = PaperTradingReceipt()
        r2 = PaperTradingReceipt()
        assert r1.receipt_id != r2.receipt_id

    def test_receipt_default_action_is_ready(self):
        receipt = PaperTradingReceipt()
        assert receipt.action == BarAction.READY

    def test_receipt_default_dry_run_true(self):
        # Must default to True -- paper trading guard
        receipt = PaperTradingReceipt()
        assert receipt.dry_run is True

    def test_receipt_session_id_settable(self):
        receipt = PaperTradingReceipt(session_id="ses-42", bar_ts=1711929600000)
        assert receipt.session_id == "ses-42"
        assert receipt.bar_ts == 1711929600000

    def test_receipt_has_guard_fields(self):
        # guard_pass and guard_details must exist
        receipt = PaperTradingReceipt()
        assert hasattr(receipt, "guard_pass")
        assert hasattr(receipt, "guard_details")

    def test_receipt_has_latency_fields(self):
        receipt = PaperTradingReceipt()
        assert hasattr(receipt, "execution_latency_ms")
        assert hasattr(receipt, "api_latency_ms")

    def test_receipt_strategy_version_default(self):
        receipt = PaperTradingReceipt()
        assert receipt.strategy_version == "SMC_WaveTrend_1H_v2"


# ---------------------------------------------------------------------------
# TestBarAction
# ---------------------------------------------------------------------------


class TestBarAction:
    def test_all_constants_present(self):
        assert BarAction.READY == "READY"
        assert BarAction.SKIP_SIGNAL_NONE == "SKIP_SIGNAL_NONE"
        assert BarAction.SKIP_GOVERNANCE_BLOCK == "SKIP_GOVERNANCE_BLOCK"
        assert BarAction.SKIP_SESSION_BLOCK == "SKIP_SESSION_BLOCK"
        assert BarAction.SKIP_LATENCY_GUARD == "SKIP_LATENCY_GUARD"
        assert BarAction.ENTER_DRY_RUN == "ENTER_DRY_RUN"
        assert BarAction.EXIT_TP == "EXIT_TP"
        assert BarAction.EXIT_SL == "EXIT_SL"
        assert BarAction.EXIT_REVERSE == "EXIT_REVERSE"
        assert BarAction.HALTED_KILL_SWITCH == "HALTED_KILL_SWITCH"
        assert BarAction.SKIP_DUPLICATE_BAR == "SKIP_DUPLICATE_BAR"
        assert BarAction.ERROR_FAIL_CLOSED == "ERROR_FAIL_CLOSED"
