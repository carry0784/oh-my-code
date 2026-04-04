"""
BacktestingEngine — CR-040 Phase 3
Runs strategies against historical OHLCV data and produces trade records.
Simulates order execution with configurable slippage and fees.
Pure computation — no exchange I/O, no side effects.
"""

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.core.logging import get_logger
from app.services.performance_metrics import PerformanceCalculator, PerformanceReport, TradeRecord
from strategies.base import BaseStrategy

logger = get_logger(__name__)


@dataclass
class BacktestConfig:
    """Backtesting configuration."""

    initial_capital: float = 10000.0
    position_size_pct: float = 10.0  # % of capital per trade
    max_positions: int = 1  # Max concurrent positions
    slippage_pct: float = 0.05  # 0.05% slippage
    fee_pct: float = 0.1  # 0.1% fee per side
    stop_loss_enabled: bool = True
    take_profit_enabled: bool = True


@dataclass
class BacktestResult:
    """Complete backtesting result."""

    strategy_name: str = ""
    config: BacktestConfig = field(default_factory=BacktestConfig)
    trades: list[TradeRecord] = field(default_factory=list)
    performance: PerformanceReport = field(default_factory=PerformanceReport)
    total_bars: int = 0
    signals_generated: int = 0


class BacktestingEngine:
    """Runs a strategy against historical OHLCV data."""

    def __init__(self, config: BacktestConfig | None = None):
        self.config = config or BacktestConfig()
        self._calculator = PerformanceCalculator()

    def run(
        self,
        strategy: BaseStrategy,
        ohlcv: list[list],
        lookback: int = 50,
    ) -> BacktestResult:
        """
        Run backtest.

        Args:
            strategy: Strategy instance with analyze() method.
            ohlcv: List of [timestamp, open, high, low, close, volume].
            lookback: Minimum bars before first signal check.

        Returns:
            BacktestResult with trades and performance metrics.
        """
        result = BacktestResult(
            strategy_name=strategy.name,
            config=self.config,
            total_bars=len(ohlcv),
        )

        if len(ohlcv) < lookback + 1:
            return result

        trades: list[TradeRecord] = []
        position: dict | None = None
        capital = self.config.initial_capital

        for i in range(lookback, len(ohlcv)):
            bar = ohlcv[i]
            timestamp = int(bar[0])
            high = float(bar[2])
            low = float(bar[3])
            close = float(bar[4])

            # Check stop loss / take profit on open position
            if position:
                exit_price, exit_reason = self._check_exit(position, high, low, close)
                if exit_price is not None:
                    trade = self._close_position(position, exit_price, timestamp)
                    trades.append(trade)
                    capital += trade.pnl
                    position = None

            # Generate signal on window
            if position is None:
                window = ohlcv[: i + 1]
                signal = strategy.analyze(window)

                if signal is not None:
                    result.signals_generated += 1
                    position = self._open_position(signal, close, timestamp, capital)

        # Close any remaining position at last bar
        if position:
            last_bar = ohlcv[-1]
            trade = self._close_position(position, float(last_bar[4]), int(last_bar[0]))
            trades.append(trade)

        result.trades = trades
        result.performance = self._calculator.calculate(trades, self.config.initial_capital)

        logger.info(
            "backtest_complete",
            strategy=strategy.name,
            bars=len(ohlcv),
            signals=result.signals_generated,
            trades=len(trades),
            total_return=round(result.performance.total_return_pct, 2),
        )
        return result

    def _open_position(self, signal: dict, price: float, timestamp: int, capital: float) -> dict:
        """Create a position from a signal."""
        # Apply slippage
        side = signal.get("signal_type")
        side_str = side.value if hasattr(side, "value") else str(side)
        if "long" in side_str.lower():
            entry = price * (1 + self.config.slippage_pct / 100)
            side_label = "long"
        else:
            entry = price * (1 - self.config.slippage_pct / 100)
            side_label = "short"

        size = capital * (self.config.position_size_pct / 100) / entry

        return {
            "side": side_label,
            "entry_price": entry,
            "quantity": size,
            "stop_loss": signal.get("stop_loss"),
            "take_profit": signal.get("take_profit"),
            "entry_time": timestamp,
        }

    def _check_exit(
        self, position: dict, high: float, low: float, close: float
    ) -> tuple[float | None, str | None]:
        """Check if position should be exited."""
        side = position["side"]
        sl = position.get("stop_loss")
        tp = position.get("take_profit")

        if side == "long":
            if self.config.stop_loss_enabled and sl and low <= sl:
                return sl, "stop_loss"
            if self.config.take_profit_enabled and tp and high >= tp:
                return tp, "take_profit"
        else:  # short
            if self.config.stop_loss_enabled and sl and high >= sl:
                return sl, "stop_loss"
            if self.config.take_profit_enabled and tp and low <= tp:
                return tp, "take_profit"

        return None, None

    def _close_position(self, position: dict, exit_price: float, timestamp: int) -> TradeRecord:
        """Close a position and create a TradeRecord."""
        # Apply slippage on exit
        if position["side"] == "long":
            actual_exit = exit_price * (1 - self.config.slippage_pct / 100)
        else:
            actual_exit = exit_price * (1 + self.config.slippage_pct / 100)

        return TradeRecord(
            entry_price=position["entry_price"],
            exit_price=actual_exit,
            side=position["side"],
            quantity=position["quantity"],
            entry_time=position["entry_time"],
            exit_time=timestamp,
            fee_pct=self.config.fee_pct / 100,
        )
