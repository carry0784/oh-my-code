"""
Strategy Pipeline Tests -- L4~L8
K-Dexter AOS v4

Tests: Signal, RiskFilter, PositionSizer, ExecutionCell, StrategyPipeline

Run: python -X utf8 tests/test_strategy_pipeline.py
"""
from __future__ import annotations

import asyncio
import sys

from kdexter.strategy.signal import (
    Signal, SignalDirection, SignalStrength, SignalStatus,
)
from kdexter.strategy.risk_filter import (
    RiskFilter, RiskLimits, AccountState, RiskCheckResult,
)
from kdexter.strategy.position_sizer import (
    PositionSizer, SizingParams, SizingMethod, SizingResult,
)
from kdexter.strategy.execution_cell import ExecutionCell, ExecutionResult
from kdexter.strategy.pipeline import StrategyPipeline, PipelineStage
from kdexter.audit.evidence_store import EvidenceStore
from kdexter.tcl.commands import (
    TCLDispatcher, TCLCommand, CommandTranscript, CommandType, ExecutionMode,
)
from kdexter.tcl.adapters import ExchangeAdapter


def run(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# ------------------------------------------------------------------ #
# Mock exchange adapter for tests
# ------------------------------------------------------------------ #

class MockAdapter(ExchangeAdapter):
    @property
    def exchange_id(self) -> str:
        return "mock"

    async def execute(self, command: TCLCommand) -> CommandTranscript:
        t = self._base_transcript(command)
        t.complete({"status": "ok"}, {"filled": True}, "ORD-MOCK-001")
        return t

    async def dry_run(self, command: TCLCommand) -> CommandTranscript:
        t = self._base_transcript(command)
        t.complete({"status": "simulated"}, {"simulated": True})
        return t

    async def verify(self, exchange_order_id: str) -> CommandTranscript:
        t = CommandTranscript()
        t.complete({"status": "filled"}, {"filled": True}, exchange_order_id)
        return t

    async def cancel(self, exchange_order_id: str) -> CommandTranscript:
        t = CommandTranscript()
        t.complete({"status": "cancelled"}, {"cancelled": True}, exchange_order_id)
        return t

    async def query_position(self, symbol=None) -> CommandTranscript:
        t = CommandTranscript()
        t.complete({"positions": []}, {"count": 0})
        return t

    async def query_balance(self, currency=None) -> CommandTranscript:
        t = CommandTranscript()
        t.complete({"balance": 10000}, {"available": 10000})
        return t


def _make_signal(**kwargs) -> Signal:
    defaults = dict(
        signal_id="SIG-001",
        strategy_id="STRAT-A",
        exchange="mock",
        symbol="BTC/USDT",
        direction=SignalDirection.BUY,
        entry_price=50000.0,
        stop_loss=48000.0,
        take_profit=55000.0,
    )
    defaults.update(kwargs)
    return Signal(**defaults)


def _make_account(**kwargs) -> AccountState:
    defaults = dict(
        total_equity=100000.0,
        available_balance=80000.0,
        current_drawdown_pct=0.02,
    )
    defaults.update(kwargs)
    return AccountState(**defaults)


# ======================================================================== #
# 1. Signal Model
# ======================================================================== #

def test_signal_creation():
    s = _make_signal()
    assert s.status == SignalStatus.PENDING
    assert s.direction == SignalDirection.BUY
    assert s.symbol == "BTC/USDT"
    print("  [1] Signal creation  OK")


def test_signal_lifecycle():
    s = _make_signal()
    s.approve_risk()
    assert s.status == SignalStatus.RISK_APPROVED
    s.set_size(0.5)
    assert s.status == SignalStatus.SIZED
    assert s.quantity == 0.5
    s.mark_dispatched()
    assert s.status == SignalStatus.DISPATCHED
    s.mark_filled()
    assert s.status == SignalStatus.FILLED
    print("  [2] Signal lifecycle  OK")


def test_signal_rejection():
    s = _make_signal()
    s.reject("Too risky")
    assert s.status == SignalStatus.RISK_REJECTED
    assert s.rejection_reason == "Too risky"
    print("  [3] Signal rejection  OK")


def test_signal_expiry():
    from datetime import timedelta
    s = _make_signal(ttl_seconds=0)
    # TTL=0 means immediately expired
    assert s.is_expired is True
    s2 = _make_signal(ttl_seconds=3600)
    assert s2.is_expired is False
    print("  [4] Signal expiry  OK")


# ======================================================================== #
# 2. Risk Filter
# ======================================================================== #

def test_risk_pass():
    rf = RiskFilter(RiskLimits())
    s = _make_signal()
    acc = _make_account()
    result = rf.check(s, acc)
    assert result.passed is True
    assert s.status == SignalStatus.RISK_APPROVED
    print("  [5] Risk filter pass  OK")


def test_risk_drawdown_reject():
    rf = RiskFilter(RiskLimits(max_drawdown_pct=0.05))
    s = _make_signal()
    acc = _make_account(current_drawdown_pct=0.06)
    result = rf.check(s, acc)
    assert result.passed is False
    assert "Drawdown" in result.rejection_reason
    print("  [6] Risk drawdown reject  OK")


def test_risk_forbidden_symbol():
    rf = RiskFilter(RiskLimits(forbidden_symbols=["LUNA/USDT"]))
    s = _make_signal(symbol="LUNA/USDT")
    result = rf.check(s, _make_account())
    assert result.passed is False
    assert "Forbidden symbol" in result.rejection_reason
    print("  [7] Risk forbidden symbol  OK")


def test_risk_forbidden_exchange():
    rf = RiskFilter(RiskLimits(forbidden_exchanges=["mock"]))
    s = _make_signal()
    result = rf.check(s, _make_account())
    assert result.passed is False
    assert "Forbidden exchange" in result.rejection_reason
    print("  [8] Risk forbidden exchange  OK")


def test_risk_exposure_limit():
    rf = RiskFilter(RiskLimits(max_portfolio_exposure_pct=0.30))
    s = _make_signal()
    acc = _make_account(total_exposure_pct=0.35)
    result = rf.check(s, acc)
    assert result.passed is False
    assert "Portfolio exposure" in result.rejection_reason
    print("  [9] Risk exposure limit  OK")


def test_risk_daily_trade_limit():
    rf = RiskFilter(RiskLimits(max_daily_trades=10))
    s = _make_signal()
    acc = _make_account(daily_trade_count=10)
    result = rf.check(s, acc)
    assert result.passed is False
    assert "Daily trade" in result.rejection_reason
    print("  [10] Risk daily trade limit  OK")


def test_risk_expired_signal():
    rf = RiskFilter()
    s = _make_signal(ttl_seconds=0)
    result = rf.check(s, _make_account())
    assert result.passed is False
    assert "expired" in result.rejection_reason
    print("  [11] Risk expired signal reject  OK")


def test_risk_pass_rate():
    rf = RiskFilter()
    for i in range(3):
        rf.check(_make_signal(signal_id=f"S-{i}"), _make_account())
    assert rf.pass_rate() == 1.0
    print("  [12] Risk pass rate tracking  OK")


# ======================================================================== #
# 3. Position Sizer
# ======================================================================== #

def test_sizer_fixed_fraction():
    sizer = PositionSizer(SizingParams(
        method=SizingMethod.FIXED_FRACTION,
        fixed_fraction_pct=0.02,
    ))
    s = _make_signal()
    s.approve_risk()
    acc = _make_account(total_equity=100000)
    result = sizer.size(s, acc)
    # risk_amount = 100000 * 0.02 = 2000
    # risk_per_unit = |50000 - 48000| = 2000
    # qty = 2000 / 2000 = 1.0
    assert result.sized is True
    assert result.quantity == 1.0
    assert result.risk_amount == 2000.0
    assert s.status == SignalStatus.SIZED
    print("  [13] Fixed fraction sizing  OK")


def test_sizer_kelly():
    sizer = PositionSizer(SizingParams(
        method=SizingMethod.KELLY,
        kelly_win_rate=0.55,
        kelly_payoff_ratio=1.5,
        kelly_fraction=0.25,
    ))
    s = _make_signal()
    s.approve_risk()
    acc = _make_account(total_equity=100000)
    result = sizer.size(s, acc)
    # kelly_f = (0.55*1.5 - 0.45)/1.5 = (0.825-0.45)/1.5 = 0.375/1.5 = 0.25
    # practical_f = 0.25 * 0.25 = 0.0625
    # risk_amount = 100000 * 0.0625 = 6250
    # risk_per_unit = 2000, qty = 6250/2000 = 3.125
    assert result.sized is True
    assert abs(result.quantity - 3.125) < 0.01
    print("  [14] Kelly sizing  OK")


def test_sizer_fixed_quantity():
    sizer = PositionSizer(SizingParams(
        method=SizingMethod.FIXED_QUANTITY,
        fixed_quantity=0.5,
    ))
    s = _make_signal()
    s.approve_risk()
    result = sizer.size(s, _make_account())
    assert result.sized is True
    assert result.quantity == 0.5
    print("  [15] Fixed quantity sizing  OK")


def test_sizer_not_risk_approved():
    sizer = PositionSizer()
    s = _make_signal()  # still PENDING
    result = sizer.size(s, _make_account())
    assert result.sized is False
    assert "not risk-approved" in result.rejection_reason
    print("  [16] Sizer rejects non-approved signal  OK")


def test_sizer_min_max_clamp():
    sizer = PositionSizer(SizingParams(
        method=SizingMethod.FIXED_QUANTITY,
        fixed_quantity=10.0,
        max_quantity=5.0,
    ))
    s = _make_signal()
    s.approve_risk()
    result = sizer.size(s, _make_account())
    assert result.quantity == 5.0  # clamped to max
    print("  [17] Sizer min/max clamp  OK")


# ======================================================================== #
# 4. Execution Cell
# ======================================================================== #

def test_exec_cell_dry_run():
    dispatcher = TCLDispatcher()
    dispatcher.register("mock", MockAdapter())
    evidence = EvidenceStore()
    cell = ExecutionCell(tcl=dispatcher, evidence=evidence)

    s = _make_signal()
    s.approve_risk()
    s.set_size(0.5)

    result = run(cell.execute(s))
    assert result.success is True
    assert result.transcript is not None
    assert s.status == SignalStatus.FILLED  # DRY_RUN auto-fills
    assert evidence.count() > 0
    print("  [18] Execution cell dry run  OK")


def test_exec_cell_not_sized():
    dispatcher = TCLDispatcher()
    evidence = EvidenceStore()
    cell = ExecutionCell(tcl=dispatcher, evidence=evidence)

    s = _make_signal()  # PENDING, not sized
    result = run(cell.execute(s))
    assert result.success is False
    assert "not sized" in result.error
    print("  [19] Execution cell rejects unsized signal  OK")


def test_exec_cell_no_adapter():
    dispatcher = TCLDispatcher()  # no adapter registered
    evidence = EvidenceStore()
    cell = ExecutionCell(tcl=dispatcher, evidence=evidence)

    s = _make_signal()
    s.approve_risk()
    s.set_size(0.5)

    result = run(cell.execute(s))
    assert result.success is False
    assert "AdapterNotFound" in (result.error or "")
    print("  [20] Execution cell no adapter  OK")


def test_exec_cell_sell():
    dispatcher = TCLDispatcher()
    dispatcher.register("mock", MockAdapter())
    evidence = EvidenceStore()
    cell = ExecutionCell(tcl=dispatcher, evidence=evidence)

    s = _make_signal(direction=SignalDirection.SELL)
    s.approve_risk()
    s.set_size(1.0)

    result = run(cell.execute(s))
    assert result.success is True
    print("  [21] Execution cell sell order  OK")


def test_exec_cell_success_rate():
    dispatcher = TCLDispatcher()
    dispatcher.register("mock", MockAdapter())
    evidence = EvidenceStore()
    cell = ExecutionCell(tcl=dispatcher, evidence=evidence)

    for i in range(3):
        s = _make_signal(signal_id=f"S-{i}")
        s.approve_risk()
        s.set_size(0.1)
        run(cell.execute(s))

    assert cell.success_rate() == 1.0
    print("  [22] Execution cell success rate  OK")


# ======================================================================== #
# 5. Strategy Pipeline (end-to-end)
# ======================================================================== #

def test_pipeline_success():
    dispatcher = TCLDispatcher()
    dispatcher.register("mock", MockAdapter())
    evidence = EvidenceStore()

    pipeline = StrategyPipeline(
        risk_filter=RiskFilter(),
        sizer=PositionSizer(SizingParams(
            method=SizingMethod.FIXED_FRACTION,
            fixed_fraction_pct=0.02,
        )),
        execution_cell=ExecutionCell(tcl=dispatcher, evidence=evidence),
    )

    s = _make_signal()
    acc = _make_account(total_equity=100000)
    result = run(pipeline.process(s, acc))

    assert result.success is True
    assert result.final_stage == PipelineStage.COMPLETE
    assert result.risk_result.passed is True
    assert result.sizing_result.sized is True
    assert result.execution_result.success is True
    print("  [23] Pipeline end-to-end success  OK")


def test_pipeline_risk_reject():
    dispatcher = TCLDispatcher()
    evidence = EvidenceStore()

    pipeline = StrategyPipeline(
        risk_filter=RiskFilter(RiskLimits(max_drawdown_pct=0.01)),
        sizer=PositionSizer(),
        execution_cell=ExecutionCell(tcl=dispatcher, evidence=evidence),
    )

    s = _make_signal()
    acc = _make_account(current_drawdown_pct=0.05)
    result = run(pipeline.process(s, acc))

    assert result.success is False
    assert result.final_stage == PipelineStage.RISK_CHECK
    assert "Drawdown" in result.error
    print("  [24] Pipeline risk rejection  OK")


def test_pipeline_batch():
    dispatcher = TCLDispatcher()
    dispatcher.register("mock", MockAdapter())
    evidence = EvidenceStore()

    pipeline = StrategyPipeline(
        risk_filter=RiskFilter(),
        sizer=PositionSizer(SizingParams(fixed_fraction_pct=0.01)),
        execution_cell=ExecutionCell(tcl=dispatcher, evidence=evidence),
    )

    signals = [_make_signal(signal_id=f"SIG-{i}") for i in range(5)]
    acc = _make_account(total_equity=100000)
    results = run(pipeline.process_batch(signals, acc))

    assert len(results) == 5
    assert all(r.success for r in results)
    print("  [25] Pipeline batch processing  OK")


def test_pipeline_summary():
    dispatcher = TCLDispatcher()
    dispatcher.register("mock", MockAdapter())
    evidence = EvidenceStore()

    pipeline = StrategyPipeline(
        risk_filter=RiskFilter(),
        sizer=PositionSizer(SizingParams(fixed_fraction_pct=0.01)),
        execution_cell=ExecutionCell(tcl=dispatcher, evidence=evidence),
    )

    for i in range(3):
        s = _make_signal(signal_id=f"S-{i}")
        run(pipeline.process(s, _make_account()))

    summary = pipeline.summary()
    assert summary["total"] == 3
    assert summary["success"] == 3
    assert summary["rate"] == 1.0
    print("  [26] Pipeline summary  OK")


def test_pipeline_mixed_results():
    dispatcher = TCLDispatcher()
    dispatcher.register("mock", MockAdapter())
    evidence = EvidenceStore()

    pipeline = StrategyPipeline(
        risk_filter=RiskFilter(RiskLimits(forbidden_symbols=["LUNA/USDT"])),
        sizer=PositionSizer(SizingParams(fixed_fraction_pct=0.01)),
        execution_cell=ExecutionCell(tcl=dispatcher, evidence=evidence),
    )

    s1 = _make_signal(signal_id="S-1", symbol="BTC/USDT")
    s2 = _make_signal(signal_id="S-2", symbol="LUNA/USDT")
    s3 = _make_signal(signal_id="S-3", symbol="ETH/USDT")

    acc = _make_account()
    r1 = run(pipeline.process(s1, acc))
    r2 = run(pipeline.process(s2, acc))
    r3 = run(pipeline.process(s3, acc))

    assert r1.success is True
    assert r2.success is False
    assert r3.success is True
    assert pipeline.success_rate() == 2/3
    print("  [27] Pipeline mixed results  OK")


# ======================================================================== #
# Runner
# ======================================================================== #

if __name__ == "__main__":
    print("\nStrategy Pipeline Tests (L4~L8)")
    print("=" * 60)

    tests = [
        ("Signal Model", [
            test_signal_creation,
            test_signal_lifecycle,
            test_signal_rejection,
            test_signal_expiry,
        ]),
        ("Risk Filter", [
            test_risk_pass,
            test_risk_drawdown_reject,
            test_risk_forbidden_symbol,
            test_risk_forbidden_exchange,
            test_risk_exposure_limit,
            test_risk_daily_trade_limit,
            test_risk_expired_signal,
            test_risk_pass_rate,
        ]),
        ("Position Sizer", [
            test_sizer_fixed_fraction,
            test_sizer_kelly,
            test_sizer_fixed_quantity,
            test_sizer_not_risk_approved,
            test_sizer_min_max_clamp,
        ]),
        ("Execution Cell", [
            test_exec_cell_dry_run,
            test_exec_cell_not_sized,
            test_exec_cell_no_adapter,
            test_exec_cell_sell,
            test_exec_cell_success_rate,
        ]),
        ("Strategy Pipeline", [
            test_pipeline_success,
            test_pipeline_risk_reject,
            test_pipeline_batch,
            test_pipeline_summary,
            test_pipeline_mixed_results,
        ]),
    ]

    total = 0
    passed = 0
    failed_tests = []

    for section, fns in tests:
        print(f"\n--- {section} ---")
        for fn in fns:
            total += 1
            try:
                fn()
                passed += 1
            except Exception as e:
                failed_tests.append((fn.__name__, str(e)))
                print(f"  FAILED: {fn.__name__}: {e}")

    print(f"\n{'=' * 60}")
    print(f"Results: {passed}/{total} passed")
    if failed_tests:
        print("FAILED:")
        for name, err in failed_tests:
            print(f"  - {name}: {err}")
        sys.exit(1)
    else:
        print("All tests PASSED")
