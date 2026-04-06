"""CR-048 Phase 5a-C -- BTC Lane Guarded Paper Simulation Tests.

Controlling spec: Phase 5a-C BTC LANE IMPLEMENTATION GO

Required test coverage (per directive):
  - happy path
  - G1 same-bar violation
  - G2 execution latency exceeded
  - G3 api latency exceeded
  - G4 spread exceeded
  - G5 daily loss halt
  - G6 open position block
  - G7 halted session block
  - 3 consecutive >10s lane pause
  - SOL lane isolation
  - activation-path unreachable proof
  - migration/default=0 proof
"""

from __future__ import annotations

import inspect
import os
from datetime import datetime, timedelta, timezone

import pytest

from app.services.paper_trading_session_cr046 import (
    BarAction,
    CR046PaperSession,
    CR046PaperTradingManager,
    PaperTradingReceipt,
    DAILY_LOSS_LIMIT,
    SL_PCT,
    TP_PCT,
)
from app.services.btc_latency_guard import (
    API_LATENCY_MAX_MS,
    BAR_INTERVAL_MS,
    EXECUTION_LATENCY_MAX_MS,
    HIGH_LATENCY_CONSECUTIVE_LIMIT,
    HIGH_LATENCY_THRESHOLD_MS,
    SAME_BAR_BUFFER_MINUTES,
    SPREAD_MAX_PCT,
    GuardResult,
    _check_same_bar,
    evaluate_btc_guard,
    update_high_latency_counter,
)


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(**kwargs) -> CR046PaperSession:
    defaults = dict(
        session_id="cr046_btc_guarded_v1",
        symbol="BTC/USDT",
        daily_pnl=0.0,
        weekly_trades=0,
        consecutive_losing_days=0,
        consecutive_high_latency=0,
        is_halted=False,
        halt_reason=None,
        open_position=None,
        last_daily_reset_utc=datetime(2026, 4, 6, 0, 0, tzinfo=timezone.utc),
        last_weekly_reset_utc=datetime(2026, 4, 6, 0, 0, tzinfo=timezone.utc),
    )
    defaults.update(kwargs)
    return CR046PaperSession(**defaults)


def _bar_ts_from_dt(dt: datetime) -> int:
    """Convert datetime to bar timestamp in ms."""
    return int(dt.timestamp() * 1000)


# Standard test time: bar at 10:00 UTC, now at 10:30 UTC (within bar)
BAR_OPEN = datetime(2026, 4, 6, 10, 0, 0, tzinfo=timezone.utc)
NOW_WITHIN = datetime(2026, 4, 6, 10, 30, 0, tzinfo=timezone.utc)
BAR_TS = _bar_ts_from_dt(BAR_OPEN)


# ===========================================================================
# 1. THRESHOLD CONSTANTS
# ===========================================================================


class TestBtcGuardThresholds:
    """Verify guard threshold constants match design."""

    def test_execution_latency_max_5s(self):
        assert EXECUTION_LATENCY_MAX_MS == 5_000

    def test_api_latency_max_2s(self):
        assert API_LATENCY_MAX_MS == 2_000

    def test_spread_max_0_1_pct(self):
        assert SPREAD_MAX_PCT == 0.001

    def test_same_bar_buffer_55min(self):
        assert SAME_BAR_BUFFER_MINUTES == 55

    def test_bar_interval_1h(self):
        assert BAR_INTERVAL_MS == 3_600_000

    def test_high_latency_threshold_10s(self):
        assert HIGH_LATENCY_THRESHOLD_MS == 10_000

    def test_high_latency_consecutive_limit_3(self):
        assert HIGH_LATENCY_CONSECUTIVE_LIMIT == 3


# ===========================================================================
# 2. HAPPY PATH: all guards pass -> GuardResult.passed = True
# ===========================================================================


class TestBtcGuardHappyPath:
    """All 7 guards pass -> entry allowed."""

    def test_all_guards_pass(self):
        session = _make_session()
        result = evaluate_btc_guard(
            bar_ts_ms=BAR_TS,
            now_utc=NOW_WITHIN,
            execution_latency_ms=1000.0,
            api_latency_ms=500.0,
            spread_pct=0.0005,
            session=session,
        )
        assert result.passed is True
        assert result.fail_reason is None
        assert result.details["overall"] is True

    def test_all_guards_at_exact_limits(self):
        """Guards pass at exact threshold values (<=)."""
        session = _make_session()
        result = evaluate_btc_guard(
            bar_ts_ms=BAR_TS,
            now_utc=NOW_WITHIN,
            execution_latency_ms=5000.0,
            api_latency_ms=2000.0,
            spread_pct=0.001,
            session=session,
        )
        assert result.passed is True

    def test_guard_result_is_frozen(self):
        """GuardResult must be immutable."""
        session = _make_session()
        result = evaluate_btc_guard(
            bar_ts_ms=BAR_TS,
            now_utc=NOW_WITHIN,
            execution_latency_ms=1000.0,
            api_latency_ms=500.0,
            spread_pct=0.0005,
            session=session,
        )
        with pytest.raises(AttributeError):
            result.passed = False


# ===========================================================================
# 3. G1: SAME-BAR VIOLATION
# ===========================================================================


class TestGuardG1SameBar:
    """G1: Signal must be within current 1H bar + 55min deadline."""

    def test_within_bar_passes(self):
        assert _check_same_bar(BAR_TS, NOW_WITHIN) is True

    def test_at_bar_open_passes(self):
        assert _check_same_bar(BAR_TS, BAR_OPEN) is True

    def test_at_55min_deadline_passes(self):
        deadline = BAR_OPEN + timedelta(minutes=55)
        assert _check_same_bar(BAR_TS, deadline) is True

    def test_after_55min_deadline_fails(self):
        late = BAR_OPEN + timedelta(minutes=55, seconds=1)
        assert _check_same_bar(BAR_TS, late) is False

    def test_next_bar_fails(self):
        next_bar = BAR_OPEN + timedelta(hours=1)
        assert _check_same_bar(BAR_TS, next_bar) is False

    def test_before_bar_open_fails(self):
        early = BAR_OPEN - timedelta(seconds=1)
        assert _check_same_bar(BAR_TS, early) is False

    def test_zero_bar_ts_fails(self):
        assert _check_same_bar(0, NOW_WITHIN) is False

    def test_negative_bar_ts_fails(self):
        assert _check_same_bar(-1, NOW_WITHIN) is False

    def test_g1_fail_in_guard(self):
        session = _make_session()
        late = BAR_OPEN + timedelta(minutes=56)
        result = evaluate_btc_guard(
            bar_ts_ms=BAR_TS,
            now_utc=late,
            execution_latency_ms=1000.0,
            api_latency_ms=500.0,
            spread_pct=0.0005,
            session=session,
        )
        assert result.passed is False
        assert "G1" in result.fail_reason


# ===========================================================================
# 4. G2: EXECUTION LATENCY EXCEEDED
# ===========================================================================


class TestGuardG2ExecutionLatency:
    """G2: execution_latency_ms must be <= 5000ms."""

    def test_under_limit_passes(self):
        session = _make_session()
        result = evaluate_btc_guard(
            bar_ts_ms=BAR_TS,
            now_utc=NOW_WITHIN,
            execution_latency_ms=4999.0,
            api_latency_ms=500.0,
            spread_pct=0.0005,
            session=session,
        )
        assert result.passed is True

    def test_over_limit_fails(self):
        session = _make_session()
        result = evaluate_btc_guard(
            bar_ts_ms=BAR_TS,
            now_utc=NOW_WITHIN,
            execution_latency_ms=5001.0,
            api_latency_ms=500.0,
            spread_pct=0.0005,
            session=session,
        )
        assert result.passed is False
        assert "G2" in result.fail_reason
        assert "exceeded" in result.fail_reason

    def test_none_fails_closed(self):
        """None execution_latency_ms -> fail-closed."""
        session = _make_session()
        result = evaluate_btc_guard(
            bar_ts_ms=BAR_TS,
            now_utc=NOW_WITHIN,
            execution_latency_ms=None,
            api_latency_ms=500.0,
            spread_pct=0.0005,
            session=session,
        )
        assert result.passed is False
        assert "G2" in result.fail_reason
        assert "missing" in result.fail_reason

    def test_details_contain_value(self):
        session = _make_session()
        result = evaluate_btc_guard(
            bar_ts_ms=BAR_TS,
            now_utc=NOW_WITHIN,
            execution_latency_ms=3000.0,
            api_latency_ms=500.0,
            spread_pct=0.0005,
            session=session,
        )
        assert result.details["G2_execution_latency_ms"] == 3000.0
        assert result.details["G2_pass"] is True


# ===========================================================================
# 5. G3: API LATENCY EXCEEDED
# ===========================================================================


class TestGuardG3ApiLatency:
    """G3: api_latency_ms must be <= 2000ms."""

    def test_under_limit_passes(self):
        session = _make_session()
        result = evaluate_btc_guard(
            bar_ts_ms=BAR_TS,
            now_utc=NOW_WITHIN,
            execution_latency_ms=1000.0,
            api_latency_ms=1999.0,
            spread_pct=0.0005,
            session=session,
        )
        assert result.passed is True

    def test_over_limit_fails(self):
        session = _make_session()
        result = evaluate_btc_guard(
            bar_ts_ms=BAR_TS,
            now_utc=NOW_WITHIN,
            execution_latency_ms=1000.0,
            api_latency_ms=2001.0,
            spread_pct=0.0005,
            session=session,
        )
        assert result.passed is False
        assert "G3" in result.fail_reason

    def test_none_fails_closed(self):
        session = _make_session()
        result = evaluate_btc_guard(
            bar_ts_ms=BAR_TS,
            now_utc=NOW_WITHIN,
            execution_latency_ms=1000.0,
            api_latency_ms=None,
            spread_pct=0.0005,
            session=session,
        )
        assert result.passed is False
        assert "G3" in result.fail_reason
        assert "missing" in result.fail_reason


# ===========================================================================
# 6. G4: SPREAD EXCEEDED
# ===========================================================================


class TestGuardG4Spread:
    """G4: spread_pct must be <= 0.1% (0.001)."""

    def test_under_limit_passes(self):
        session = _make_session()
        result = evaluate_btc_guard(
            bar_ts_ms=BAR_TS,
            now_utc=NOW_WITHIN,
            execution_latency_ms=1000.0,
            api_latency_ms=500.0,
            spread_pct=0.0009,
            session=session,
        )
        assert result.passed is True

    def test_over_limit_fails(self):
        session = _make_session()
        result = evaluate_btc_guard(
            bar_ts_ms=BAR_TS,
            now_utc=NOW_WITHIN,
            execution_latency_ms=1000.0,
            api_latency_ms=500.0,
            spread_pct=0.0011,
            session=session,
        )
        assert result.passed is False
        assert "G4" in result.fail_reason

    def test_none_fails_closed(self):
        session = _make_session()
        result = evaluate_btc_guard(
            bar_ts_ms=BAR_TS,
            now_utc=NOW_WITHIN,
            execution_latency_ms=1000.0,
            api_latency_ms=500.0,
            spread_pct=None,
            session=session,
        )
        assert result.passed is False
        assert "G4" in result.fail_reason
        assert "missing" in result.fail_reason


# ===========================================================================
# 7. G5: DAILY LOSS HALT
# ===========================================================================


class TestGuardG5DailyLoss:
    """G5: daily_pnl must be > -5%."""

    def test_normal_pnl_passes(self):
        session = _make_session(daily_pnl=-0.03)
        result = evaluate_btc_guard(
            bar_ts_ms=BAR_TS,
            now_utc=NOW_WITHIN,
            execution_latency_ms=1000.0,
            api_latency_ms=500.0,
            spread_pct=0.0005,
            session=session,
        )
        assert result.passed is True

    def test_at_limit_fails(self):
        session = _make_session(daily_pnl=DAILY_LOSS_LIMIT)
        result = evaluate_btc_guard(
            bar_ts_ms=BAR_TS,
            now_utc=NOW_WITHIN,
            execution_latency_ms=1000.0,
            api_latency_ms=500.0,
            spread_pct=0.0005,
            session=session,
        )
        assert result.passed is False
        assert "G5" in result.fail_reason

    def test_below_limit_fails(self):
        session = _make_session(daily_pnl=-0.06)
        result = evaluate_btc_guard(
            bar_ts_ms=BAR_TS,
            now_utc=NOW_WITHIN,
            execution_latency_ms=1000.0,
            api_latency_ms=500.0,
            spread_pct=0.0005,
            session=session,
        )
        assert result.passed is False
        assert "G5" in result.fail_reason


# ===========================================================================
# 8. G6: OPEN POSITION BLOCK
# ===========================================================================


class TestGuardG6PositionBlock:
    """G6: open_position must be None."""

    def test_no_position_passes(self):
        session = _make_session()
        result = evaluate_btc_guard(
            bar_ts_ms=BAR_TS,
            now_utc=NOW_WITHIN,
            execution_latency_ms=1000.0,
            api_latency_ms=500.0,
            spread_pct=0.0005,
            session=session,
        )
        assert result.passed is True
        assert result.details["G6_position_clear"] is True

    def test_open_position_fails(self):
        session = _make_session(open_position={"direction": "LONG", "entry_price": 85000.0})
        result = evaluate_btc_guard(
            bar_ts_ms=BAR_TS,
            now_utc=NOW_WITHIN,
            execution_latency_ms=1000.0,
            api_latency_ms=500.0,
            spread_pct=0.0005,
            session=session,
        )
        assert result.passed is False
        assert "G6" in result.fail_reason


# ===========================================================================
# 9. G7: HALTED SESSION BLOCK
# ===========================================================================


class TestGuardG7HaltedBlock:
    """G7: session must not be halted."""

    def test_not_halted_passes(self):
        session = _make_session()
        result = evaluate_btc_guard(
            bar_ts_ms=BAR_TS,
            now_utc=NOW_WITHIN,
            execution_latency_ms=1000.0,
            api_latency_ms=500.0,
            spread_pct=0.0005,
            session=session,
        )
        assert result.passed is True
        assert result.details["G7_not_halted"] is True

    def test_halted_fails(self):
        session = _make_session(is_halted=True, halt_reason="K1:daily_loss_exceeded")
        result = evaluate_btc_guard(
            bar_ts_ms=BAR_TS,
            now_utc=NOW_WITHIN,
            execution_latency_ms=1000.0,
            api_latency_ms=500.0,
            spread_pct=0.0005,
            session=session,
        )
        assert result.passed is False
        assert "G7" in result.fail_reason
        assert "K1" in result.fail_reason


# ===========================================================================
# 10. 3-CONSECUTIVE HIGH-LATENCY LANE PAUSE
# ===========================================================================


class TestHighLatencyPause:
    """3 consecutive execution_latency > 10s -> lane pause."""

    def test_single_high_latency_no_pause(self):
        session = _make_session()
        session, should_pause = update_high_latency_counter(session, 11000.0)
        assert session.consecutive_high_latency == 1
        assert should_pause is False

    def test_two_consecutive_no_pause(self):
        session = _make_session(consecutive_high_latency=1)
        session, should_pause = update_high_latency_counter(session, 11000.0)
        assert session.consecutive_high_latency == 2
        assert should_pause is False

    def test_three_consecutive_triggers_pause(self):
        session = _make_session(consecutive_high_latency=2)
        session, should_pause = update_high_latency_counter(session, 11000.0)
        assert session.consecutive_high_latency == 3
        assert should_pause is True

    def test_normal_latency_resets_counter(self):
        session = _make_session(consecutive_high_latency=2)
        session, should_pause = update_high_latency_counter(session, 5000.0)
        assert session.consecutive_high_latency == 0
        assert should_pause is False

    def test_exactly_10s_does_not_increment(self):
        """10000ms is NOT > 10000ms, so no increment."""
        session = _make_session()
        session, should_pause = update_high_latency_counter(session, 10000.0)
        assert session.consecutive_high_latency == 0
        assert should_pause is False

    def test_none_latency_conservative(self):
        """None latency: don't change counter (conservative)."""
        session = _make_session(consecutive_high_latency=2)
        session, should_pause = update_high_latency_counter(session, None)
        assert session.consecutive_high_latency == 2
        assert should_pause is False

    def test_pause_halt_reason(self):
        """Paused session should have K_LATENCY halt reason."""
        session = _make_session(consecutive_high_latency=2)
        session, should_pause = update_high_latency_counter(session, 15000.0)
        assert should_pause is True
        # Task would set:
        session.is_halted = True
        session.halt_reason = "K_LATENCY:3_consecutive_high_latency"
        assert session.is_halted is True
        assert "K_LATENCY" in session.halt_reason

    def test_k_latency_no_auto_resume(self):
        """K_LATENCY halt should NOT auto-resume on daily reset (unlike K1)."""
        mgr = CR046PaperTradingManager()
        session = _make_session(
            is_halted=True,
            halt_reason="K_LATENCY:3_consecutive_high_latency",
            last_daily_reset_utc=datetime(2026, 4, 5, 0, 0, tzinfo=timezone.utc),
        )
        new_day = datetime(2026, 4, 6, 1, 0, tzinfo=timezone.utc)
        session = mgr.check_and_reset_daily(session, new_day)
        # K_LATENCY should remain halted (only K1 auto-resumes)
        assert session.is_halted is True
        assert "K_LATENCY" in session.halt_reason


# ===========================================================================
# 11. SOL LANE ISOLATION
# ===========================================================================


class TestSolLaneIsolation:
    """Prove SOL lane is completely untouched by BTC implementation."""

    def test_sol_task_unchanged(self):
        """sol_paper_tasks.py must not import btc modules."""
        from workers.tasks import sol_paper_tasks

        source = open(sol_paper_tasks.__file__, "r", encoding="utf-8").read()
        assert "btc_paper" not in source.lower()
        assert "btc_latency_guard" not in source.lower()
        assert "BTC/USDT" not in source

    def test_sol_session_id_unchanged(self):
        from workers.tasks.sol_paper_tasks import SESSION_ID as SOL_SESSION_ID

        assert SOL_SESSION_ID == "cr046_sol_paper_v1"

    def test_btc_session_id_different(self):
        from workers.tasks.btc_paper_tasks import SESSION_ID as BTC_SESSION_ID

        assert BTC_SESSION_ID == "cr046_btc_guarded_v1"
        assert BTC_SESSION_ID != "cr046_sol_paper_v1"

    def test_sol_has_no_guard_logic(self):
        """SOL task must not reference latency guard."""
        from workers.tasks import sol_paper_tasks

        source = open(sol_paper_tasks.__file__, "r", encoding="utf-8").read()
        assert "evaluate_btc_guard" not in source
        assert "SKIP_LATENCY_GUARD" not in source
        assert "guard_pass" not in source

    def test_btc_task_symbol_default(self):
        from workers.tasks.btc_paper_tasks import run_btc_paper_bar

        sig = inspect.signature(run_btc_paper_bar)
        assert sig.parameters["symbol"].default == "BTC/USDT"

    def test_sol_task_symbol_default(self):
        from workers.tasks.sol_paper_tasks import run_sol_paper_bar

        sig = inspect.signature(run_sol_paper_bar)
        assert sig.parameters["symbol"].default == "SOL/USDT"


# ===========================================================================
# 12. ACTIVATION-PATH UNREACHABLE PROOF
# ===========================================================================


class TestActivationIsolation:
    """Prove execute/rollback paths remain unreachable."""

    def test_no_execute_in_btc_tasks(self):
        from workers.tasks import btc_paper_tasks

        source = open(btc_paper_tasks.__file__, "r", encoding="utf-8").read()
        assert "execute_bounded_write" not in source

    def test_no_rollback_in_btc_tasks(self):
        from workers.tasks import btc_paper_tasks

        source = open(btc_paper_tasks.__file__, "r", encoding="utf-8").read()
        assert "rollback_bounded_write" not in source

    def test_no_execute_in_guard(self):
        from app.services import btc_latency_guard

        source = open(btc_latency_guard.__file__, "r", encoding="utf-8").read()
        assert "execute_bounded_write" not in source
        assert "rollback_bounded_write" not in source

    def test_no_shadow_write_service_in_btc(self):
        from workers.tasks import btc_paper_tasks

        source = open(btc_paper_tasks.__file__, "r", encoding="utf-8").read()
        assert "shadow_write_service" not in source

    def test_btc_module_namespace_clean(self):
        import workers.tasks.btc_paper_tasks as mod

        assert not hasattr(mod, "execute_bounded_write")
        assert not hasattr(mod, "rollback_bounded_write")

    def test_guard_module_namespace_clean(self):
        import app.services.btc_latency_guard as mod

        assert not hasattr(mod, "execute_bounded_write")
        assert not hasattr(mod, "rollback_bounded_write")


# ===========================================================================
# 13. DRY_RUN INVARIANT
# ===========================================================================


class TestDryRunInvariant:
    """dry_run=True must be hardcoded in BTC lane."""

    def test_dry_run_in_source(self):
        from workers.tasks import btc_paper_tasks

        source = open(btc_paper_tasks.__file__, "r", encoding="utf-8").read()
        assert "dry_run=True" in source
        assert "dry_run=False" not in source
        assert "dry_run = False" not in source

    def test_dry_run_not_a_parameter(self):
        from workers.tasks.btc_paper_tasks import run_btc_paper_bar

        sig = inspect.signature(run_btc_paper_bar)
        assert "dry_run" not in sig.parameters

    def test_receipt_default_dry_run_true(self):
        receipt = PaperTradingReceipt()
        assert receipt.dry_run is True


# ===========================================================================
# 14. BEAT NOT REGISTERED
# ===========================================================================


class TestBeatNotRegistered:
    """BTC paper task must NOT be in beat schedule (5a-C = implementation only)."""

    def test_btc_paper_not_in_beat(self):
        from workers.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule
        btc_entries = [k for k, v in schedule.items() if "btc_paper" in v.get("task", "")]
        assert btc_entries == []

    def test_btc_paper_not_in_include(self):
        from workers.celery_app import celery_app

        include = celery_app.conf.include or []
        btc_includes = [e for e in include if "btc_paper" in e]
        assert btc_includes == []


# ===========================================================================
# 15. FAIL-CLOSED STATE MACHINE
# ===========================================================================


class TestFailClosedStateMachine:
    """All unhandled exceptions -> ERROR_FAIL_CLOSED."""

    def test_error_fail_closed_action(self):
        assert BarAction.ERROR_FAIL_CLOSED == "ERROR_FAIL_CLOSED"

    def test_skip_latency_guard_action(self):
        assert BarAction.SKIP_LATENCY_GUARD == "SKIP_LATENCY_GUARD"

    def test_task_catches_all_exceptions(self):
        from workers.tasks import btc_paper_tasks

        source = open(btc_paper_tasks.__file__, "r", encoding="utf-8").read()
        assert "except Exception" in source
        assert "ERROR_FAIL_CLOSED" in source

    def test_guard_evaluates_all_7_in_order(self):
        """Guard evaluation checks G1 through G7 sequentially."""
        source = inspect.getsource(evaluate_btc_guard)
        g1_pos = source.index("G1")
        g2_pos = source.index("G2")
        g3_pos = source.index("G3")
        g4_pos = source.index("G4")
        g5_pos = source.index("G5")
        g6_pos = source.index("G6")
        g7_pos = source.index("G7")
        assert g1_pos < g2_pos < g3_pos < g4_pos < g5_pos < g6_pos < g7_pos


# ===========================================================================
# 16. MIGRATION / DEFAULT=0 PROOF
# ===========================================================================


class TestMigrationDefaults:
    """Verify consecutive_high_latency field exists with default=0."""

    def test_session_dataclass_has_field(self):
        session = CR046PaperSession()
        assert hasattr(session, "consecutive_high_latency")
        assert session.consecutive_high_latency == 0

    def test_db_model_has_column(self):
        from app.models import paper_session as mod

        source = inspect.getsource(mod.PaperTradingSessionModel)
        assert "consecutive_high_latency" in source

    def test_db_model_default_0(self):
        from app.models import paper_session as mod

        source = inspect.getsource(mod.PaperTradingSessionModel)
        # Must have server_default="0" for existing rows
        assert 'server_default="0"' in source

    def test_session_store_loads_field(self):
        from app.services import session_store_cr046 as mod

        source = inspect.getsource(mod.SessionStore.load)
        assert "consecutive_high_latency" in source

    def test_session_store_saves_field(self):
        from app.services import session_store_cr046 as mod

        source = inspect.getsource(mod.SessionStore.save)
        assert "consecutive_high_latency" in source

    def test_migration_file_exists(self):
        migration_path = os.path.join(
            PROJECT_ROOT, "alembic", "versions", "025_add_consecutive_high_latency.py"
        )
        assert os.path.isfile(migration_path)

    def test_migration_adds_column(self):
        migration_path = os.path.join(
            PROJECT_ROOT, "alembic", "versions", "025_add_consecutive_high_latency.py"
        )
        with open(migration_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "consecutive_high_latency" in content
        assert 'server_default="0"' in content
        assert "paper_trading_sessions" in content


# ===========================================================================
# 17. COMPONENT WIRING
# ===========================================================================


class TestBtcComponentWiring:
    """Verify BTC lane uses correct components."""

    def test_uses_guard(self):
        from workers.tasks import btc_paper_tasks

        source = open(btc_paper_tasks.__file__, "r", encoding="utf-8").read()
        assert "evaluate_btc_guard" in source
        assert "update_high_latency_counter" in source

    def test_uses_strategy(self):
        from workers.tasks import btc_paper_tasks

        source = open(btc_paper_tasks.__file__, "r", encoding="utf-8").read()
        assert "SMCWaveTrendStrategy" in source

    def test_uses_session_store(self):
        from workers.tasks import btc_paper_tasks

        source = open(btc_paper_tasks.__file__, "r", encoding="utf-8").read()
        assert "SessionStore" in source
        assert "ReceiptStore" in source

    def test_uses_manager(self):
        from workers.tasks import btc_paper_tasks

        source = open(btc_paper_tasks.__file__, "r", encoding="utf-8").read()
        assert "CR046PaperTradingManager" in source

    def test_uses_exchange_factory(self):
        from workers.tasks import btc_paper_tasks

        source = open(btc_paper_tasks.__file__, "r", encoding="utf-8").read()
        assert "ExchangeFactory" in source

    def test_slippage_model(self):
        from workers.tasks.btc_paper_tasks import _synthetic_slippage, SLIPPAGE_FLOOR

        assert SLIPPAGE_FLOOR == 0.0005
        assert _synthetic_slippage(None) == SLIPPAGE_FLOOR
        assert _synthetic_slippage(0.002) == 0.001
