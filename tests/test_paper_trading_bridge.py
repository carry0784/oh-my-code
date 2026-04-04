"""Tests for PaperTradingBridge — CR-044 Phase 7."""

import sys
from unittest.mock import MagicMock

_STUB_MODULES = [
    "ccxt",
    "ccxt.async_support",
    "aiohttp",
    "celery",
    "redis",
    "sqlalchemy",
    "sqlalchemy.ext",
    "sqlalchemy.ext.asyncio",
    "sqlalchemy.orm",
    "sqlalchemy.pool",
    "sqlalchemy.engine",
    "app.core.database",
    "app.core.config",
]
for name in _STUB_MODULES:
    if name not in sys.modules:
        sys.modules[name] = MagicMock()
_fake_base = type("FakeBase", (), {"__tablename__": "", "metadata": MagicMock()})
sys.modules["app.core.database"].Base = _fake_base
sys.modules["app.core.database"].engine = MagicMock()
sys.modules["app.core.database"].async_session_factory = MagicMock()

import pytest
from app.services.paper_trading_bridge import (
    PaperTradingBridge,
    PaperTradingConfig,
)
from app.services.performance_metrics import PerformanceReport, TradeRecord


def _make_trade(entry: float = 100.0, exit_: float = 110.0, side: str = "long") -> TradeRecord:
    return TradeRecord(
        entry_price=entry,
        exit_price=exit_,
        side=side,
        quantity=1.0,
        entry_time=1000,
        exit_time=2000,
    )


def _make_paper_session_with_trades(bridge: PaperTradingBridge, genome_id: str, n: int) -> str:
    session_id = bridge.start_session(genome_id)
    for i in range(n):
        bridge.record_trade(session_id, _make_trade(100.0, 110.0 + i))
    return session_id


# ---------------------------------------------------------------------------
# test_start_session
# ---------------------------------------------------------------------------


def test_start_session():
    bridge = PaperTradingBridge()
    session_id = bridge.start_session("genome_A")

    assert session_id == "paper_1"
    assert session_id in bridge.sessions
    session = bridge.sessions[session_id]
    assert session.genome_id == "genome_A"
    assert session.is_active is True
    assert session.started_at != ""


# ---------------------------------------------------------------------------
# test_record_trade
# ---------------------------------------------------------------------------


def test_record_trade():
    bridge = PaperTradingBridge()
    session_id = bridge.start_session("genome_B")
    trade = _make_trade()

    result = bridge.record_trade(session_id, trade)

    assert result is True
    assert len(bridge.sessions[session_id].trades) == 1


# ---------------------------------------------------------------------------
# test_record_trade_closed_session
# ---------------------------------------------------------------------------


def test_record_trade_closed_session():
    bridge = PaperTradingBridge()
    session_id = bridge.start_session("genome_C")
    bridge.close_session(session_id)

    result = bridge.record_trade(session_id, _make_trade())

    assert result is False
    assert len(bridge.sessions[session_id].trades) == 0


# ---------------------------------------------------------------------------
# test_evaluate_no_trades — default 0.5 match score when no trades
# ---------------------------------------------------------------------------


def test_evaluate_no_trades():
    bridge = PaperTradingBridge()
    session_id = bridge.start_session("genome_D")
    backtest = PerformanceReport(total_return_pct=15.0, win_rate=0.55, total_trades=50)

    result = bridge.evaluate_session(session_id, backtest)

    assert result.trade_count == 0
    assert result.live_match_score == 0.5
    assert result.is_ready_for_promotion is False


# ---------------------------------------------------------------------------
# test_compute_live_match_same_direction — direction match contributes 0.6
# ---------------------------------------------------------------------------


def test_compute_live_match_same_direction():
    bridge = PaperTradingBridge()
    # Both positive returns, identical win rate → full score
    backtest = PerformanceReport(total_return_pct=10.0, win_rate=0.6, total_trades=30)
    paper = PerformanceReport(total_return_pct=8.0, win_rate=0.6, total_trades=20)

    score = bridge.compute_live_match(backtest, paper)

    # direction=1.0 * 0.6 + wr_sim=1.0 * 0.4 = 1.0
    assert score == pytest.approx(1.0, abs=1e-6)


# ---------------------------------------------------------------------------
# test_compute_live_match_opposite_direction — 0.0 direction component
# ---------------------------------------------------------------------------


def test_compute_live_match_opposite_direction():
    bridge = PaperTradingBridge()
    backtest = PerformanceReport(total_return_pct=10.0, win_rate=0.6, total_trades=30)
    # Paper is negative while backtest is positive
    paper = PerformanceReport(total_return_pct=-5.0, win_rate=0.6, total_trades=10)

    score = bridge.compute_live_match(backtest, paper)

    # direction=0.0 * 0.6 + wr_sim * 0.4 (total_trades=10 >= 5 so real calc)
    assert score < 0.5  # direction component is 0, only win-rate sim contributes


# ---------------------------------------------------------------------------
# test_promotion_readiness — sufficient trades + high match + low DD = ready
# ---------------------------------------------------------------------------


def test_promotion_readiness():
    config = PaperTradingConfig(
        min_paper_trades=5,
        live_match_threshold=0.6,
        max_paper_drawdown_pct=25.0,
    )
    bridge = PaperTradingBridge(config=config)
    session_id = _make_paper_session_with_trades(bridge, "genome_E", n=6)

    # Backtest with positive return and moderate win rate
    backtest = PerformanceReport(
        total_return_pct=12.0,
        win_rate=0.6,
        total_trades=50,
        max_drawdown_pct=10.0,
    )

    result = bridge.evaluate_session(session_id, backtest)

    assert result.trade_count == 6
    # Both backtest and paper are positive (all winning trades) → direction match
    assert result.live_match_score >= 0.6
    assert result.is_ready_for_promotion is True
