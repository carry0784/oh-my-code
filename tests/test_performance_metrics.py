"""Tests for PerformanceMetrics — CR-040 Phase 3."""

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

from app.services.performance_metrics import (
    PerformanceCalculator,
    PerformanceReport,
    TradeRecord,
)


def _make_trades(pnl_list: list[float], price: float = 100.0) -> list[TradeRecord]:
    """Helper to create trades with specified PnL outcomes."""
    trades = []
    for pnl in pnl_list:
        if pnl >= 0:
            exit_p = price + pnl + price * 0.002  # offset fee
            trades.append(
                TradeRecord(
                    entry_price=price, exit_price=exit_p, side="long", quantity=1.0, fee_pct=0.001
                )
            )
        else:
            exit_p = price + pnl + price * 0.002
            trades.append(
                TradeRecord(
                    entry_price=price, exit_price=exit_p, side="long", quantity=1.0, fee_pct=0.001
                )
            )
    return trades


class TestTradeRecord:
    def test_long_profit(self):
        t = TradeRecord(entry_price=100, exit_price=110, side="long", quantity=1.0, fee_pct=0.001)
        assert t.pnl > 0
        assert t.return_pct > 0

    def test_long_loss(self):
        t = TradeRecord(entry_price=100, exit_price=90, side="long", quantity=1.0, fee_pct=0.001)
        assert t.pnl < 0

    def test_short_profit(self):
        t = TradeRecord(entry_price=100, exit_price=90, side="short", quantity=1.0, fee_pct=0.001)
        assert t.pnl > 0

    def test_short_loss(self):
        t = TradeRecord(entry_price=100, exit_price=110, side="short", quantity=1.0, fee_pct=0.001)
        assert t.pnl < 0

    def test_fee_deduction(self):
        t_no_fee = TradeRecord(
            entry_price=100, exit_price=110, side="long", quantity=1.0, fee_pct=0.0
        )
        t_with_fee = TradeRecord(
            entry_price=100, exit_price=110, side="long", quantity=1.0, fee_pct=0.001
        )
        assert t_no_fee.pnl > t_with_fee.pnl


class TestPerformanceCalculator:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_empty_trades(self):
        result = self.calc.calculate([])
        assert result.total_trades == 0
        assert result.total_pnl == 0.0

    def test_single_winning_trade(self):
        trades = [TradeRecord(entry_price=100, exit_price=110, side="long", fee_pct=0.001)]
        result = self.calc.calculate(trades)
        assert result.total_trades == 1
        assert result.winning_trades == 1
        assert result.win_rate == 1.0
        assert result.total_pnl > 0

    def test_single_losing_trade(self):
        trades = [TradeRecord(entry_price=100, exit_price=90, side="long", fee_pct=0.001)]
        result = self.calc.calculate(trades)
        assert result.losing_trades == 1
        assert result.win_rate == 0.0

    def test_mixed_trades_win_rate(self):
        trades = [
            TradeRecord(entry_price=100, exit_price=110, side="long", fee_pct=0.001),
            TradeRecord(entry_price=100, exit_price=105, side="long", fee_pct=0.001),
            TradeRecord(entry_price=100, exit_price=90, side="long", fee_pct=0.001),
        ]
        result = self.calc.calculate(trades)
        assert result.total_trades == 3
        assert result.winning_trades == 2
        assert abs(result.win_rate - 2 / 3) < 0.01

    def test_equity_curve(self):
        trades = [
            TradeRecord(entry_price=100, exit_price=110, side="long", fee_pct=0),
            TradeRecord(entry_price=100, exit_price=95, side="long", fee_pct=0),
        ]
        result = self.calc.calculate(trades, initial_capital=1000)
        assert len(result.equity_curve) == 3  # initial + 2 trades
        assert result.equity_curve[0] == 1000

    def test_max_drawdown(self):
        trades = [
            TradeRecord(entry_price=100, exit_price=120, side="long", fee_pct=0),
            TradeRecord(entry_price=100, exit_price=80, side="long", fee_pct=0),
            TradeRecord(entry_price=100, exit_price=70, side="long", fee_pct=0),
        ]
        result = self.calc.calculate(trades, initial_capital=1000)
        assert result.max_drawdown_pct > 0

    def test_consecutive_losses(self):
        trades = [
            TradeRecord(entry_price=100, exit_price=90, side="long", fee_pct=0),
            TradeRecord(entry_price=100, exit_price=90, side="long", fee_pct=0),
            TradeRecord(entry_price=100, exit_price=90, side="long", fee_pct=0),
            TradeRecord(entry_price=100, exit_price=110, side="long", fee_pct=0),
        ]
        result = self.calc.calculate(trades)
        assert result.max_consecutive_losses == 3

    def test_profit_factor(self):
        trades = [
            TradeRecord(entry_price=100, exit_price=120, side="long", fee_pct=0),
            TradeRecord(entry_price=100, exit_price=90, side="long", fee_pct=0),
        ]
        result = self.calc.calculate(trades)
        assert result.profit_factor == 2.0  # 20 profit / 10 loss

    def test_sharpe_ratio_positive(self):
        # Mostly positive returns with slight variance → positive Sharpe
        trades = [
            TradeRecord(entry_price=100, exit_price=102 + i * 0.1, side="long", fee_pct=0)
            for i in range(20)
        ]
        result = self.calc.calculate(trades)
        assert result.sharpe_ratio > 0
