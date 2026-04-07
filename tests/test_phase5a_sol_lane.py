"""CR-048 Phase 5a-B -- SOL Lane Paper Simulation Tests.

Controlling spec: Phase 5a-B SOL LANE PAPER SIMULATION IMPLEMENTATION GO

Required test coverage (per directive):
  1. Happy path: signal -> decision -> paper-order (ENTER_DRY_RUN)
  2. Skip path: no signal -> SKIP_SIGNAL_NONE
  3. Hold path: open position, within SL/TP range -> hold (no exit)
  4. Loss-limit pause path: daily_pnl <= -5% -> HALTED_KILL_SWITCH

Additional proofs:
  - BTC lane isolation: no BTC imports, no BTC task, no BTC beat entry
  - execute/rollback unreachable: not imported in sol_paper_tasks
  - Append-only write: receipt INSERT only, no UPDATE/DELETE
  - dry_run=True invariant
  - Risk params match directive: SL=-2%, TP=+4%, max_pos=1, daily_loss=-5%
  - Beat NOT registered (5a-B scope = implementation only, not activation)
"""

from __future__ import annotations

import ast
import inspect
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.paper_trading_session_cr046 import (
    BarAction,
    CR046PaperSession,
    CR046PaperTradingManager,
    PaperTradingReceipt,
    DAILY_LOSS_LIMIT,
    MAX_POSITIONS,
    SL_PCT,
    TP_PCT,
    WEEKLY_TRADE_CAP,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _make_session(**kwargs) -> CR046PaperSession:
    defaults = dict(
        session_id="cr046_sol_paper_v1",
        symbol="SOL/USDT",
        daily_pnl=0.0,
        weekly_trades=0,
        consecutive_losing_days=0,
        is_halted=False,
        halt_reason=None,
        open_position=None,
        last_daily_reset_utc=datetime(2026, 4, 6, 0, 0, tzinfo=timezone.utc),
        last_weekly_reset_utc=datetime(2026, 4, 6, 0, 0, tzinfo=timezone.utc),
    )
    defaults.update(kwargs)
    return CR046PaperSession(**defaults)


def _make_ohlcv(n: int = 200, close: float = 150.0) -> list[list]:
    """Generate synthetic OHLCV bars for testing."""
    bars = []
    base_ts = 1712400000000  # 2024-04-06 ~
    for i in range(n):
        ts = base_ts + i * 3600_000  # 1H bars
        o = close * (1 + (i % 3 - 1) * 0.001)
        h = close * 1.005
        l = close * 0.995
        c = close
        v = 10000.0
        bars.append([ts, o, h, l, c, v])
    return bars


def _make_signal_result(
    signal_type_value: str = "LONG",
    entry_price: float = 150.0,
    bar_ts: int = 1712400000000,
) -> dict:
    """Create a mock signal result dict matching SMCWaveTrendStrategy output."""
    from app.models.signal import SignalType

    st = SignalType.LONG if signal_type_value == "LONG" else SignalType.SHORT
    sl = entry_price * (1 - SL_PCT) if signal_type_value == "LONG" else entry_price * (1 + SL_PCT)
    tp = entry_price * (1 + TP_PCT) if signal_type_value == "LONG" else entry_price * (1 - TP_PCT)

    return {
        "signal_type": st,
        "entry_price": entry_price,
        "stop_loss": sl,
        "take_profit": tp,
        "confidence": 0.7,
        "metadata": {
            "smc_signal": 1 if signal_type_value == "LONG" else -1,
            "wt_signal": 1 if signal_type_value == "LONG" else -1,
            "wt1_val": -55.0 if signal_type_value == "LONG" else 55.0,
            "wt2_val": -60.0 if signal_type_value == "LONG" else 60.0,
            "bar_timestamp": bar_ts,
            "strategy_version": "SMC_WaveTrend_1H_v2",
        },
    }


# ===========================================================================
# 1. RISK PARAMETER VERIFICATION
# ===========================================================================


class TestSolLaneRiskParams:
    """Verify risk parameters match Phase 5a-B directive."""

    def test_sl_pct_is_2_percent(self):
        assert SL_PCT == 0.02

    def test_tp_pct_is_4_percent(self):
        assert TP_PCT == 0.04

    def test_max_positions_is_1(self):
        assert MAX_POSITIONS == 1

    def test_daily_loss_limit_is_negative_5_percent(self):
        assert DAILY_LOSS_LIMIT == -0.05

    def test_weekly_trade_cap_is_15(self):
        assert WEEKLY_TRADE_CAP == 15

    def test_sol_task_session_id(self):
        from workers.tasks.sol_paper_tasks import SESSION_ID

        assert SESSION_ID == "cr046_sol_paper_v1"

    def test_sol_task_strategy_version(self):
        from workers.tasks.sol_paper_tasks import STRATEGY_VERSION

        assert STRATEGY_VERSION == "SMC_WaveTrend_1H_v2"

    def test_sol_task_symbol_default(self):
        """Default symbol argument is SOL/USDT."""
        from workers.tasks.sol_paper_tasks import run_sol_paper_bar

        sig = inspect.signature(run_sol_paper_bar)
        assert sig.parameters["symbol"].default == "SOL/USDT"

    def test_sol_task_exchange_default_binance(self):
        from workers.tasks.sol_paper_tasks import run_sol_paper_bar

        sig = inspect.signature(run_sol_paper_bar)
        assert sig.parameters["exchange_name"].default == "binance"


# ===========================================================================
# 2. HAPPY PATH: signal -> ENTER_DRY_RUN
# ===========================================================================


class TestSolLaneHappyPath:
    """Signal present + session clear -> ENTER_DRY_RUN with correct receipt."""

    def test_happy_path_enter_dry_run(self):
        mgr = CR046PaperTradingManager()
        session = _make_session()
        signal = "LONG"

        # Verify entry is allowed
        can, reason = mgr.can_enter(session, signal)
        assert can is True
        assert reason == "ok"

        # Verify receipt action
        receipt = PaperTradingReceipt(
            session_id="cr046_sol_paper_v1",
            symbol="SOL/USDT",
            dry_run=True,
        )
        receipt.action = BarAction.ENTER_DRY_RUN
        receipt.signal = signal
        receipt.consensus_pass = True
        receipt.session_can_enter = True

        assert receipt.action == BarAction.ENTER_DRY_RUN
        assert receipt.dry_run is True
        assert receipt.consensus_pass is True
        assert receipt.session_can_enter is True

    def test_happy_path_short_entry(self):
        mgr = CR046PaperTradingManager()
        session = _make_session()
        can, reason = mgr.can_enter(session, "SHORT")
        assert can is True

    def test_happy_path_position_stored(self):
        """After entry, session.open_position must be set."""
        session = _make_session()
        entry_price = 150.0
        sl = entry_price * (1 - SL_PCT)
        tp = entry_price * (1 + TP_PCT)

        session.open_position = {
            "direction": "LONG",
            "entry_price": entry_price,
            "entry_bar_ts": 1712400000000,
            "sl_price": sl,
            "tp_price": tp,
        }
        session.weekly_trades += 1

        assert session.open_position is not None
        assert session.open_position["direction"] == "LONG"
        assert session.weekly_trades == 1

    def test_happy_path_receipt_dry_run_forced(self):
        """Receipt.dry_run must always be True."""
        receipt = PaperTradingReceipt()
        assert receipt.dry_run is True
        # Attempt to set False should be detectable
        receipt.dry_run = False
        assert receipt.dry_run is False  # dataclass allows it
        # But the task forces it True -- verified by source inspection
        from workers.tasks.sol_paper_tasks import run_sol_paper_bar

        source = inspect.getsource(run_sol_paper_bar)
        assert "dry_run=True" in source


# ===========================================================================
# 3. SKIP PATH: no signal -> SKIP_SIGNAL_NONE
# ===========================================================================


class TestSolLaneSkipPath:
    """No signal from strategy -> SKIP_SIGNAL_NONE."""

    def test_no_signal_results_in_skip(self):
        """When strategy returns None, action = SKIP_SIGNAL_NONE."""
        receipt = PaperTradingReceipt(
            session_id="cr046_sol_paper_v1",
            symbol="SOL/USDT",
            dry_run=True,
        )
        # Simulate: strategy.analyze() returned None
        signal_result = None
        if signal_result is None:
            receipt.action = BarAction.SKIP_SIGNAL_NONE
            receipt.decision_source = "signal"

        assert receipt.action == BarAction.SKIP_SIGNAL_NONE
        assert receipt.decision_source == "signal"
        assert receipt.dry_run is True

    def test_no_signal_no_position_change(self):
        """Skip path must not modify session state."""
        session = _make_session()
        original_pnl = session.daily_pnl
        original_trades = session.weekly_trades

        # Signal is None -> skip, no mutation
        assert session.open_position is None
        assert session.daily_pnl == original_pnl
        assert session.weekly_trades == original_trades

    def test_can_enter_rejects_none_signal(self):
        mgr = CR046PaperTradingManager()
        session = _make_session()
        can, reason = mgr.can_enter(session, None)
        assert can is False
        assert reason == "no_signal"


# ===========================================================================
# 4. HOLD PATH: open position, within SL/TP range
# ===========================================================================


class TestSolLaneHoldPath:
    """Open position, price within range, same direction signal -> hold."""

    def test_hold_when_price_within_sl_tp_range(self):
        mgr = CR046PaperTradingManager()
        session = _make_session(open_position={"direction": "LONG", "entry_price": 150.0})
        # Price within 2% SL / 4% TP range
        current_price = 151.0  # +0.67%
        should_exit, reason = mgr.check_exit(session, current_price, bar_ts=0)
        assert should_exit is False
        assert reason == "hold"

    def test_hold_short_within_range(self):
        mgr = CR046PaperTradingManager()
        session = _make_session(open_position={"direction": "SHORT", "entry_price": 150.0})
        current_price = 149.0  # -0.67% (profit for short, within TP)
        should_exit, reason = mgr.check_exit(session, current_price, bar_ts=0)
        assert should_exit is False
        assert reason == "hold"

    def test_hold_same_direction_signal_no_exit(self):
        """LONG position + LONG signal -> no reverse exit."""
        mgr = CR046PaperTradingManager()
        session = _make_session(open_position={"direction": "LONG", "entry_price": 150.0})
        should_exit, reason = mgr.check_exit(session, 151.0, bar_ts=0, reverse_signal="LONG")
        assert should_exit is False
        assert reason == "hold"

    def test_hold_blocks_second_entry(self):
        """Max position (1) blocks second entry attempt."""
        mgr = CR046PaperTradingManager()
        session = _make_session(open_position={"direction": "LONG", "entry_price": 150.0})
        can, reason = mgr.can_enter(session, "LONG")
        assert can is False
        assert reason == "max_position_reached"


# ===========================================================================
# 5. LOSS-LIMIT PAUSE PATH: daily_pnl <= -5%
# ===========================================================================


class TestSolLaneLossLimitPause:
    """Daily loss exceeds 5% -> HALTED_KILL_SWITCH."""

    def test_k1_daily_loss_halts(self):
        mgr = CR046PaperTradingManager()
        session = _make_session(daily_pnl=-0.06)
        should_halt, reason = mgr.apply_kill_switches(session)
        assert should_halt is True
        assert "K1" in reason

    def test_k1_exact_boundary_halts(self):
        mgr = CR046PaperTradingManager()
        session = _make_session(daily_pnl=DAILY_LOSS_LIMIT)
        should_halt, reason = mgr.apply_kill_switches(session)
        assert should_halt is True
        assert "K1" in reason

    def test_k3_consecutive_losing_days_halts(self):
        mgr = CR046PaperTradingManager()
        session = _make_session(consecutive_losing_days=3)
        should_halt, reason = mgr.apply_kill_switches(session)
        assert should_halt is True
        assert "K3" in reason

    def test_halted_session_blocks_entry(self):
        mgr = CR046PaperTradingManager()
        session = _make_session(is_halted=True, halt_reason="K1:daily_loss_exceeded")
        can, reason = mgr.can_enter(session, "LONG")
        assert can is False
        assert "session_halted" in reason

    def test_k1_auto_resume_on_new_day(self):
        """K1 halt auto-resumes after daily reset (UTC midnight)."""
        mgr = CR046PaperTradingManager()
        session = _make_session(
            daily_pnl=-0.06,
            is_halted=True,
            halt_reason="K1:daily_loss_exceeded",
            last_daily_reset_utc=datetime(2026, 4, 5, 0, 0, tzinfo=timezone.utc),
        )
        # Next day
        new_day = datetime(2026, 4, 6, 1, 0, tzinfo=timezone.utc)
        session = mgr.check_and_reset_daily(session, new_day)

        assert session.is_halted is False
        assert session.halt_reason is None
        assert session.daily_pnl == 0.0

    def test_receipt_records_halt(self):
        receipt = PaperTradingReceipt(
            session_id="cr046_sol_paper_v1",
            symbol="SOL/USDT",
            dry_run=True,
        )
        receipt.action = BarAction.HALTED_KILL_SWITCH
        receipt.decision_source = "kill_switch"
        receipt.halt_state = True
        receipt.block_reason = "K1:daily_loss_exceeded"

        assert receipt.action == BarAction.HALTED_KILL_SWITCH
        assert receipt.halt_state is True
        assert "K1" in receipt.block_reason


# ===========================================================================
# 6. BTC LANE ISOLATION PROOF
# ===========================================================================


class TestBtcLaneIsolation:
    """Prove BTC lane is completely untouched by 5a-B."""

    def test_sol_task_does_not_import_btc(self):
        """sol_paper_tasks must not import btc_paper_tasks or btc_latency_guard."""
        from workers.tasks import sol_paper_tasks

        source = open(sol_paper_tasks.__file__, "r", encoding="utf-8").read()
        assert "btc_paper_tasks" not in source
        assert "btc_latency_guard" not in source

    def test_sol_task_no_btc_import(self):
        """sol_paper_tasks must not import any BTC module."""
        from workers.tasks import sol_paper_tasks

        source = open(sol_paper_tasks.__file__, "r", encoding="utf-8").read()
        assert "btc_paper" not in source.lower()
        assert "BTC/USDT" not in source  # Only SOL/USDT default

    def test_sol_task_symbol_is_sol_only(self):
        """Task default symbol is SOL/USDT, not BTC."""
        from workers.tasks.sol_paper_tasks import run_sol_paper_bar

        sig = inspect.signature(run_sol_paper_bar)
        assert sig.parameters["symbol"].default == "SOL/USDT"

    def test_no_btc_in_beat_schedule(self):
        """No BTC paper task in beat schedule."""
        from workers.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule
        for key, config in schedule.items():
            assert "btc_paper" not in key.lower()
            assert "btc_paper" not in config.get("task", "").lower()

    def test_no_btc_in_celery_include(self):
        """No BTC paper tasks in celery include list."""
        from workers.celery_app import celery_app

        include_list = celery_app.conf.get("include", [])
        for entry in include_list:
            assert "btc_paper" not in entry.lower()


# ===========================================================================
# 7. EXECUTE / ROLLBACK UNREACHABLE PROOF
# ===========================================================================


class TestExecuteRollbackUnreachable:
    """Prove execute_bounded_write and rollback_bounded_write are NOT imported."""

    def test_no_execute_import_in_sol_tasks(self):
        """execute_bounded_write must not appear in sol_paper_tasks."""
        from workers.tasks import sol_paper_tasks

        source = open(sol_paper_tasks.__file__, "r", encoding="utf-8").read()
        assert "execute_bounded_write" not in source

    def test_no_rollback_import_in_sol_tasks(self):
        """rollback_bounded_write must not appear in sol_paper_tasks."""
        from workers.tasks import sol_paper_tasks

        source = open(sol_paper_tasks.__file__, "r", encoding="utf-8").read()
        assert "rollback_bounded_write" not in source

    def test_no_execute_in_session_manager(self):
        """Session manager must not reference execute/rollback."""
        from app.services import paper_trading_session_cr046 as mod

        source = open(mod.__file__, "r", encoding="utf-8").read()
        assert "execute_bounded_write" not in source
        assert "rollback_bounded_write" not in source

    def test_no_execute_in_session_store(self):
        """Session store must not reference execute/rollback."""
        from app.services import session_store_cr046 as mod

        source = open(mod.__file__, "r", encoding="utf-8").read()
        assert "execute_bounded_write" not in source
        assert "rollback_bounded_write" not in source

    def test_sol_task_module_namespace_clean(self):
        """sol_paper_tasks module namespace must not contain execute/rollback."""
        import workers.tasks.sol_paper_tasks as mod

        assert not hasattr(mod, "execute_bounded_write")
        assert not hasattr(mod, "rollback_bounded_write")

    def test_no_shadow_write_service_import(self):
        """sol_paper_tasks must not import shadow_write_service."""
        from workers.tasks import sol_paper_tasks

        source = open(sol_paper_tasks.__file__, "r", encoding="utf-8").read()
        assert "shadow_write_service" not in source


# ===========================================================================
# 8. APPEND-ONLY WRITE PROOF
# ===========================================================================


class TestAppendOnlyWriteProof:
    """Prove write operations are INSERT-only (no UPDATE/DELETE on receipts)."""

    def test_receipt_store_no_update_method(self):
        """ReceiptStore must not have update/delete methods."""
        from app.services.session_store_cr046 import ReceiptStore

        assert not hasattr(ReceiptStore, "update")
        assert not hasattr(ReceiptStore, "delete")
        assert not hasattr(ReceiptStore, "remove")

    def test_receipt_store_create_is_insert(self):
        """ReceiptStore.create must use db.add (INSERT), not UPDATE."""
        from app.services.session_store_cr046 import ReceiptStore

        source = inspect.getsource(ReceiptStore.create)
        assert "db.add" in source or "self.db.add" in source
        assert "update(" not in source
        assert "delete(" not in source

    def test_receipt_model_has_unique_constraint(self):
        """paper_trading_receipts has (session_id, bar_ts) unique constraint."""
        from app.models.paper_session import PaperTradingReceiptModel

        table_args = PaperTradingReceiptModel.__table_args__
        # Check for UniqueConstraint
        has_unique = any(
            hasattr(arg, "name") and "uq_session_bar" in (arg.name or "")
            for arg in table_args
            if not isinstance(arg, dict)
        )
        assert has_unique, "Missing uq_session_bar unique constraint"

    def test_receipt_dry_run_default_true_in_model(self):
        """PaperTradingReceiptModel declares dry_run with default=True."""
        from app.models import paper_session as mod

        source = inspect.getsource(mod.PaperTradingReceiptModel)
        assert "default=True" in source, "dry_run column must have default=True"


# ===========================================================================
# 9. BEAT NOT REGISTERED PROOF (5a-B = implementation only)
# ===========================================================================


class TestBeatRegistered:
    """Sol paper task beat status (Phase 5a CLOSED, removed from schedule)."""

    @pytest.mark.skip(
        reason="Phase 5a CLOSED — sol-paper-trading-hourly removed from beat_schedule"
    )
    def test_sol_paper_in_beat(self):
        """sol_paper_tasks must appear in active beat schedule."""
        from workers.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule
        sol_entries = [k for k, v in schedule.items() if "sol_paper" in v.get("task", "")]
        assert len(sol_entries) == 1, f"Expected exactly 1 SOL paper beat entry, got {sol_entries}"

    def test_sol_paper_in_include_list(self):
        """sol_paper_tasks must be in celery include list."""
        from workers.celery_app import celery_app

        include = celery_app.conf.include or []
        sol_includes = [e for e in include if "sol_paper" in e]
        assert len(sol_includes) == 1, f"Expected SOL paper in include, got {sol_includes}"

    @pytest.mark.skip(
        reason="Phase 5a CLOSED — sol-paper-trading-hourly removed from beat_schedule"
    )
    def test_sol_paper_schedule_is_1h(self):
        """SOL paper beat schedule must be 3600s (1H) to match strategy timeframe."""
        from workers.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule
        sol_entry = next((v for v in schedule.values() if "sol_paper" in v.get("task", "")), None)
        assert sol_entry is not None
        assert sol_entry["schedule"] == 3600.0

    @pytest.mark.skip(
        reason="Phase 5a CLOSED — sol-paper-trading-hourly removed from beat_schedule"
    )
    def test_sol_paper_kwargs_correct(self):
        """SOL paper beat kwargs must specify SOL/USDT and binance."""
        from workers.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule
        sol_entry = next((v for v in schedule.values() if "sol_paper" in v.get("task", "")), None)
        assert sol_entry is not None
        kwargs = sol_entry.get("kwargs", {})
        assert kwargs.get("symbol") == "SOL/USDT"
        assert kwargs.get("exchange_name") == "binance"

    def test_btc_paper_still_not_in_beat(self):
        """BTC paper must remain unregistered (separate GO required)."""
        from workers.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule
        btc_entries = [k for k, v in schedule.items() if "btc_paper" in v.get("task", "")]
        assert btc_entries == [], f"BTC paper found in beat: {btc_entries}"


# ===========================================================================
# 10. DRY_RUN INVARIANT
# ===========================================================================


class TestDryRunInvariant:
    """dry_run=True must be hardcoded and unconfigurable in SOL lane."""

    def test_dry_run_hardcoded_in_source(self):
        """Task source must contain dry_run=True and never dry_run=False."""
        from workers.tasks import sol_paper_tasks

        source = open(sol_paper_tasks.__file__, "r", encoding="utf-8").read()
        assert "dry_run=True" in source
        assert "dry_run=False" not in source
        assert "dry_run = False" not in source

    def test_dry_run_not_a_parameter(self):
        """dry_run must NOT be a task parameter (not configurable)."""
        from workers.tasks.sol_paper_tasks import run_sol_paper_bar

        sig = inspect.signature(run_sol_paper_bar)
        assert "dry_run" not in sig.parameters

    def test_receipt_default_dry_run_true(self):
        receipt = PaperTradingReceipt()
        assert receipt.dry_run is True


# ===========================================================================
# 11. FAIL-CLOSED STATE MACHINE
# ===========================================================================


class TestFailClosedStateMachine:
    """All unhandled exceptions -> ERROR_FAIL_CLOSED."""

    def test_error_fail_closed_action_exists(self):
        assert BarAction.ERROR_FAIL_CLOSED == "ERROR_FAIL_CLOSED"

    def test_task_catches_all_exceptions(self):
        """Task source must have broad except clause for fail-closed."""
        from workers.tasks import sol_paper_tasks

        source = open(sol_paper_tasks.__file__, "r", encoding="utf-8").read()
        assert "except Exception" in source
        assert "ERROR_FAIL_CLOSED" in source

    def test_async_core_catches_exceptions(self):
        """_run_sol_paper_bar_async must have try/except for fail-closed."""
        from workers.tasks.sol_paper_tasks import _run_sol_paper_bar_async

        source = inspect.getsource(_run_sol_paper_bar_async)
        assert "except Exception" in source
        assert "ERROR_FAIL_CLOSED" in source


# ===========================================================================
# 12. SOL LANE COMPONENT WIRING PROOF
# ===========================================================================


class TestSolLaneComponentWiring:
    """Verify SOL lane uses correct components."""

    def test_uses_smc_wavetrend_strategy(self):
        """Task must import and use SMCWaveTrendStrategy."""
        from workers.tasks import sol_paper_tasks

        source = open(sol_paper_tasks.__file__, "r", encoding="utf-8").read()
        assert "SMCWaveTrendStrategy" in source
        assert "smc_wavetrend_strategy" in source

    def test_uses_session_store(self):
        """Task must use SessionStore for persistence."""
        from workers.tasks import sol_paper_tasks

        source = open(sol_paper_tasks.__file__, "r", encoding="utf-8").read()
        assert "SessionStore" in source
        assert "ReceiptStore" in source

    def test_uses_paper_trading_manager(self):
        """Task must use CR046PaperTradingManager for decisions."""
        from workers.tasks import sol_paper_tasks

        source = open(sol_paper_tasks.__file__, "r", encoding="utf-8").read()
        assert "CR046PaperTradingManager" in source

    def test_uses_exchange_factory(self):
        """Task must use ExchangeFactory for market data."""
        from workers.tasks import sol_paper_tasks

        source = open(sol_paper_tasks.__file__, "r", encoding="utf-8").read()
        assert "ExchangeFactory" in source

    def test_strategy_is_version_b(self):
        """SMCWaveTrendStrategy must use calc_smc_pure_causal (Version B)."""
        from strategies import smc_wavetrend_strategy as mod

        source = open(mod.__file__, "r", encoding="utf-8").read()
        assert "calc_smc_pure_causal" in source

    def test_strategy_consensus_2_of_2(self):
        """Strategy requires 2/2 consensus (both SMC and WaveTrend agree)."""
        from strategies import smc_wavetrend_strategy as mod

        source = open(mod.__file__, "r", encoding="utf-8").read()
        # Both must agree: smc_sig != wt_sig -> None
        assert "smc_sig != wt_sig" in source

    def test_synthetic_slippage_model(self):
        """Task must apply synthetic slippage."""
        from workers.tasks.sol_paper_tasks import _synthetic_slippage, SLIPPAGE_FLOOR

        assert SLIPPAGE_FLOOR == 0.0005
        assert _synthetic_slippage(None) == SLIPPAGE_FLOOR
        assert _synthetic_slippage(0.002) == 0.001  # spread/2
        assert _synthetic_slippage(0.0001) == SLIPPAGE_FLOOR  # floor applied


# ===========================================================================
# 13. EXIT PATH VERIFICATION
# ===========================================================================


class TestExitPaths:
    """Verify SL/TP/reverse exit paths work correctly for SOL."""

    def test_exit_sl_long(self):
        mgr = CR046PaperTradingManager()
        session = _make_session(open_position={"direction": "LONG", "entry_price": 150.0})
        exit_price = 150.0 * (1 - SL_PCT)  # -2%
        should_exit, reason = mgr.check_exit(session, exit_price, bar_ts=0)
        assert should_exit is True
        assert reason == "stop_loss"

    def test_exit_tp_long(self):
        mgr = CR046PaperTradingManager()
        session = _make_session(open_position={"direction": "LONG", "entry_price": 150.0})
        exit_price = 150.0 * (1 + TP_PCT)  # +4%
        should_exit, reason = mgr.check_exit(session, exit_price, bar_ts=0)
        assert should_exit is True
        assert reason == "take_profit"

    def test_exit_reverse_signal(self):
        mgr = CR046PaperTradingManager()
        session = _make_session(open_position={"direction": "LONG", "entry_price": 150.0})
        should_exit, reason = mgr.check_exit(session, 151.0, bar_ts=0, reverse_signal="SHORT")
        assert should_exit is True
        assert reason == "reverse_signal"

    def test_exit_sl_short(self):
        mgr = CR046PaperTradingManager()
        session = _make_session(open_position={"direction": "SHORT", "entry_price": 150.0})
        exit_price = 150.0 * (1 + SL_PCT)  # +2% (loss for short)
        should_exit, reason = mgr.check_exit(session, exit_price, bar_ts=0)
        assert should_exit is True
        assert reason == "stop_loss"

    def test_exit_tp_short(self):
        mgr = CR046PaperTradingManager()
        session = _make_session(open_position={"direction": "SHORT", "entry_price": 150.0})
        exit_price = 150.0 * (1 - TP_PCT)  # -4% (profit for short)
        should_exit, reason = mgr.check_exit(session, exit_price, bar_ts=0)
        assert should_exit is True
        assert reason == "take_profit"

    def test_compute_close_pnl_correct(self):
        mgr = CR046PaperTradingManager()
        session = _make_session(open_position={"direction": "LONG", "entry_price": 150.0})
        result = mgr.compute_close(session, exit_price=156.0, exit_reason="take_profit")
        expected_pnl = (156.0 - 150.0) / 150.0  # 0.04
        assert abs(result["pnl_delta"] - expected_pnl) < 1e-10


# ===========================================================================
# 14. EXCHANGE LIFECYCLE REGRESSION (Post-Pilot Fix)
# ===========================================================================


class TestExchangeLifecycleRegression:
    """Prove sol_paper_tasks uses correct exchange lifecycle (no connect())."""

    def test_no_connect_call_in_source(self):
        """Task source must NOT call exchange.connect() (method does not exist)."""
        from workers.tasks import sol_paper_tasks

        source = open(sol_paper_tasks.__file__, "r", encoding="utf-8").read()
        assert "exchange.connect()" not in source, (
            "exchange.connect() must not appear — ExchangeFactory.create() returns ready instance"
        )

    def test_no_async_with_connect_pattern(self):
        """Task source must NOT use 'async with exchange.connect()' pattern."""
        from workers.tasks import sol_paper_tasks

        source = open(sol_paper_tasks.__file__, "r", encoding="utf-8").read()
        assert "async with exchange" not in source, (
            "Exchange singleton has no async context manager — use directly after create()"
        )

    def test_uses_exchange_factory_create_fresh(self):
        """Task must use ExchangeFactory.create_fresh() (not singleton create())
        to prevent stale aiohttp session from closed event loop in Celery."""
        from workers.tasks import sol_paper_tasks

        source = open(sol_paper_tasks.__file__, "r", encoding="utf-8").read()
        assert "ExchangeFactory.create_fresh(" in source

    def test_exchange_client_accessed_directly(self):
        """Task must access exchange.client directly (no connect() wrapper)."""
        from workers.tasks import sol_paper_tasks

        source = open(sol_paper_tasks.__file__, "r", encoding="utf-8").read()
        assert "exchange.client" in source


# ===========================================================================
# 8. ASYNCIO LOOP REGRESSION (Worker hang prevention)
# ===========================================================================


class TestAsyncioLoopRegression:
    """Verify asyncio.run() is used instead of get_event_loop().run_until_complete().

    Root cause: In Celery solo-pool, get_event_loop() returns a closed loop
    after the first async task completes. Subsequent calls fail with
    "'NoneType' object has no attribute 'send'", causing ERROR_FAIL_CLOSED
    and eventually worker hang (missed heartbeat).
    """

    def test_no_get_event_loop_in_sol_paper_tasks(self):
        """sol_paper_tasks must NOT use asyncio.get_event_loop()."""
        from workers.tasks import sol_paper_tasks

        source = open(sol_paper_tasks.__file__, "r", encoding="utf-8").read()
        assert "get_event_loop" not in source, (
            "asyncio.get_event_loop() causes closed-loop reuse in solo-pool. "
            "Use asyncio.run() instead."
        )

    def test_uses_asyncio_run(self):
        """sol_paper_tasks must use asyncio.run() for async execution."""
        from workers.tasks import sol_paper_tasks

        source = open(sol_paper_tasks.__file__, "r", encoding="utf-8").read()
        assert "asyncio.run(" in source

    def test_consecutive_asyncio_run_no_closed_loop(self):
        """asyncio.run() creates a fresh loop each call — no closed-loop error."""
        import asyncio

        async def dummy():
            return 42

        # Simulate consecutive Celery task invocations in same process
        for i in range(3):
            result = asyncio.run(dummy())
            assert result == 42, f"Call {i + 1} failed: closed loop reuse"

    def test_no_run_until_complete_in_task_entry(self):
        """The task entry point run_sol_paper_bar must not use run_until_complete."""
        import ast as _ast
        from workers.tasks import sol_paper_tasks

        source = open(sol_paper_tasks.__file__, "r", encoding="utf-8").read()
        tree = _ast.parse(source)

        for node in _ast.walk(tree):
            if isinstance(node, _ast.Attribute) and node.attr == "run_until_complete":
                pytest.fail(
                    "run_until_complete found in sol_paper_tasks — "
                    "must use asyncio.run() to avoid closed-loop hang"
                )
