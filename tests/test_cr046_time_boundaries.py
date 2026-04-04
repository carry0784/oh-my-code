"""CR-046 Time Boundary Tests"""

import pytest
from datetime import datetime, timezone, timedelta

from app.services.paper_trading_session_cr046 import (
    CR046PaperSession,
    CR046PaperTradingManager,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_session(**kwargs) -> CR046PaperSession:
    defaults = dict(
        session_id="test",
        symbol="SOL/USDT",
        daily_pnl=0.0,
        weekly_trades=0,
        consecutive_losing_days=0,
        is_halted=False,
        halt_reason=None,
        open_position=None,
        last_daily_reset_utc=datetime(2026, 3, 31, 0, 0, tzinfo=timezone.utc),
        last_weekly_reset_utc=datetime(2026, 3, 30, 0, 0, tzinfo=timezone.utc),  # Monday
    )
    defaults.update(kwargs)
    return CR046PaperSession(**defaults)


mgr = CR046PaperTradingManager()


# ---------------------------------------------------------------------------
# TestDailyReset
# ---------------------------------------------------------------------------


class TestDailyReset:
    def test_daily_reset_at_utc_midnight(self):
        # daily_pnl=-0.03, current_utc is the next calendar day -> resets to 0.0
        session = _make_session(
            daily_pnl=-0.03,
            last_daily_reset_utc=datetime(2026, 3, 31, 0, 0, tzinfo=timezone.utc),
        )
        current_utc = datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc)
        updated = mgr.check_and_reset_daily(session, current_utc)
        assert updated.daily_pnl == 0.0

    def test_daily_reset_updates_last_reset_timestamp(self):
        # After reset, last_daily_reset_utc must be set to the current day's midnight
        session = _make_session(
            last_daily_reset_utc=datetime(2026, 3, 31, 0, 0, tzinfo=timezone.utc),
        )
        current_utc = datetime(2026, 4, 1, 9, 30, tzinfo=timezone.utc)
        updated = mgr.check_and_reset_daily(session, current_utc)
        expected_midnight = datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc)
        assert updated.last_daily_reset_utc == expected_midnight

    def test_daily_reset_not_before_midnight(self):
        # Same calendar day at 23:59 -> no reset
        session = _make_session(
            daily_pnl=-0.03,
            last_daily_reset_utc=datetime(2026, 3, 31, 0, 0, tzinfo=timezone.utc),
        )
        current_utc = datetime(2026, 3, 31, 23, 59, tzinfo=timezone.utc)
        updated = mgr.check_and_reset_daily(session, current_utc)
        assert updated.daily_pnl == -0.03

    def test_daily_reset_not_triggered_at_same_midnight(self):
        # current_utc is the same midnight as last_daily_reset_utc -> no reset
        reset_ts = datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc)
        session = _make_session(
            daily_pnl=-0.02,
            last_daily_reset_utc=reset_ts,
        )
        updated = mgr.check_and_reset_daily(session, reset_ts)
        assert updated.daily_pnl == -0.02

    def test_daily_reset_increments_consecutive_losing_days_on_loss(self):
        # daily_pnl < 0 before reset -> consecutive_losing_days += 1
        session = _make_session(
            daily_pnl=-0.02,
            consecutive_losing_days=1,
            last_daily_reset_utc=datetime(2026, 3, 31, 0, 0, tzinfo=timezone.utc),
        )
        current_utc = datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc)
        updated = mgr.check_and_reset_daily(session, current_utc)
        assert updated.consecutive_losing_days == 2

    def test_daily_reset_resets_k1_halt_on_new_day(self):
        # K1 halt must be lifted automatically on the next day's reset
        session = _make_session(
            daily_pnl=-0.06,
            is_halted=True,
            halt_reason="K1:daily_loss_exceeded",
            last_daily_reset_utc=datetime(2026, 3, 31, 0, 0, tzinfo=timezone.utc),
        )
        current_utc = datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc)
        updated = mgr.check_and_reset_daily(session, current_utc)
        assert updated.is_halted is False
        assert updated.halt_reason is None


# ---------------------------------------------------------------------------
# TestWeeklyReset
# ---------------------------------------------------------------------------


class TestWeeklyReset:
    def test_weekly_reset_at_monday_utc_midnight(self):
        # current_utc is the next Monday -> weekly_trades resets to 0
        session = _make_session(
            weekly_trades=10,
            # last weekly reset was Monday 2026-03-30
            last_weekly_reset_utc=datetime(2026, 3, 30, 0, 0, tzinfo=timezone.utc),
        )
        # Next Monday is 2026-04-06
        current_utc = datetime(2026, 4, 6, 0, 0, tzinfo=timezone.utc)
        updated = mgr.check_and_reset_weekly(session, current_utc)
        assert updated.weekly_trades == 0

    def test_weekly_reset_updates_last_weekly_reset_timestamp(self):
        # After reset, last_weekly_reset_utc must point to the new Monday's midnight
        session = _make_session(
            weekly_trades=5,
            last_weekly_reset_utc=datetime(2026, 3, 30, 0, 0, tzinfo=timezone.utc),
        )
        current_utc = datetime(2026, 4, 6, 12, 0, tzinfo=timezone.utc)  # Monday noon
        updated = mgr.check_and_reset_weekly(session, current_utc)
        expected_monday = datetime(2026, 4, 6, 0, 0, tzinfo=timezone.utc)
        assert updated.last_weekly_reset_utc == expected_monday

    def test_weekly_reset_not_on_sunday(self):
        # Sunday -> no reset because last_weekly_reset was this week's Monday
        session = _make_session(
            weekly_trades=8,
            last_weekly_reset_utc=datetime(2026, 3, 30, 0, 0, tzinfo=timezone.utc),
        )
        # 2026-04-05 is Sunday (same week as 2026-03-30 Monday)
        current_utc = datetime(2026, 4, 5, 20, 0, tzinfo=timezone.utc)
        updated = mgr.check_and_reset_weekly(session, current_utc)
        assert updated.weekly_trades == 8

    def test_weekly_reset_not_on_tuesday_same_week(self):
        # Tuesday of same week as last reset -> no reset
        session = _make_session(
            weekly_trades=3,
            last_weekly_reset_utc=datetime(2026, 3, 30, 0, 0, tzinfo=timezone.utc),
        )
        # 2026-03-31 is Tuesday
        current_utc = datetime(2026, 3, 31, 10, 0, tzinfo=timezone.utc)
        updated = mgr.check_and_reset_weekly(session, current_utc)
        assert updated.weekly_trades == 3

    def test_weekly_reset_two_weeks_later(self):
        # Two full weeks later -> still resets correctly
        session = _make_session(
            weekly_trades=12,
            last_weekly_reset_utc=datetime(2026, 3, 30, 0, 0, tzinfo=timezone.utc),
        )
        # 2026-04-13 is two Mondays ahead
        current_utc = datetime(2026, 4, 13, 0, 0, tzinfo=timezone.utc)
        updated = mgr.check_and_reset_weekly(session, current_utc)
        assert updated.weekly_trades == 0


# ---------------------------------------------------------------------------
# TestBarBoundary
# ---------------------------------------------------------------------------


class TestBarBoundary:
    def test_bar_boundary_utc_hourly(self):
        # Bar timestamps must be on UTC hour boundaries (1H strategy)
        bar_ts = 1711929600000  # 2024-04-01 00:00:00 UTC in ms
        dt = datetime.fromtimestamp(bar_ts / 1000, tz=timezone.utc)
        assert dt.minute == 0
        assert dt.second == 0
        assert dt.microsecond == 0

    def test_bar_boundary_another_known_timestamp(self):
        # 2026-03-31 14:00:00 UTC
        bar_ts = 1774965600000
        dt = datetime.fromtimestamp(bar_ts / 1000, tz=timezone.utc)
        assert dt.minute == 0
        assert dt.second == 0
        assert dt.hour == 14

    def test_bar_ts_milliseconds_conversion(self):
        # Verify ms -> datetime round-trip for a known bar
        known_dt = datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc)
        bar_ts_ms = int(known_dt.timestamp() * 1000)
        recovered = datetime.fromtimestamp(bar_ts_ms / 1000, tz=timezone.utc)
        assert recovered == known_dt

    def test_bar_ts_not_sub_hourly_fails_assertion(self):
        # A bar_ts with non-zero minutes is not a valid 1H bar boundary
        # This confirms validation logic should reject such bars
        bar_ts = 1711929600000 + 5 * 60 * 1000  # +5 minutes
        dt = datetime.fromtimestamp(bar_ts / 1000, tz=timezone.utc)
        assert dt.minute != 0  # confirms it is not on an hour boundary


# ---------------------------------------------------------------------------
# TestConsecutiveLosing
# ---------------------------------------------------------------------------


class TestConsecutiveLosing:
    def test_consecutive_losing_days_increments_on_loss(self):
        # daily_pnl < 0 at reset -> consecutive_losing_days grows
        session = _make_session(
            daily_pnl=-0.01,
            consecutive_losing_days=0,
            last_daily_reset_utc=datetime(2026, 3, 31, 0, 0, tzinfo=timezone.utc),
        )
        current_utc = datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc)
        updated = mgr.check_and_reset_daily(session, current_utc)
        assert updated.consecutive_losing_days == 1

    def test_consecutive_losing_days_reset_on_profit(self):
        # daily_pnl > 0 at reset -> consecutive_losing_days reset to 0
        session = _make_session(
            daily_pnl=0.02,
            consecutive_losing_days=2,
            last_daily_reset_utc=datetime(2026, 3, 31, 0, 0, tzinfo=timezone.utc),
        )
        current_utc = datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc)
        updated = mgr.check_and_reset_daily(session, current_utc)
        assert updated.consecutive_losing_days == 0

    def test_consecutive_losing_days_unchanged_on_flat_day(self):
        # daily_pnl == 0.0 at reset -> consecutive_losing_days unchanged
        session = _make_session(
            daily_pnl=0.0,
            consecutive_losing_days=1,
            last_daily_reset_utc=datetime(2026, 3, 31, 0, 0, tzinfo=timezone.utc),
        )
        current_utc = datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc)
        updated = mgr.check_and_reset_daily(session, current_utc)
        # Neither loss nor profit -> counter stays the same
        assert updated.consecutive_losing_days == 1

    def test_three_consecutive_losing_days_triggers_k3(self):
        # Simulate three days of losses reaching K3
        session = _make_session(
            daily_pnl=-0.01,
            consecutive_losing_days=2,
            last_daily_reset_utc=datetime(2026, 3, 31, 0, 0, tzinfo=timezone.utc),
        )
        current_utc = datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc)
        updated = mgr.check_and_reset_daily(session, current_utc)
        # After the third loss day, consecutive_losing_days == 3
        assert updated.consecutive_losing_days == 3
        # K3 kill switch must now fire
        should_halt, reason = mgr.apply_kill_switches(updated)
        assert should_halt is True
        assert "K3" in reason

    def test_profit_day_after_two_losses_resets_counter(self):
        # Two losing days then profit -> consecutive_losing_days drops to 0
        session = _make_session(
            daily_pnl=0.03,
            consecutive_losing_days=2,
            last_daily_reset_utc=datetime(2026, 3, 31, 0, 0, tzinfo=timezone.utc),
        )
        current_utc = datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc)
        updated = mgr.check_and_reset_daily(session, current_utc)
        assert updated.consecutive_losing_days == 0
        # K3 must not fire after the reset
        should_halt, reason = mgr.apply_kill_switches(updated)
        assert should_halt is False
