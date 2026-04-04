"""
PerformanceMetrics — CR-040 Phase 3
Calculates trading performance metrics from a list of trade results.
Pure computation — no I/O, no side effects.
"""

from dataclasses import dataclass, field
import numpy as np

from app.core.logging import get_logger

logger = get_logger(__name__)

# Annualization: 365 days, 24h market
ANNUAL_FACTOR = 365.0
RISK_FREE_RATE = 0.04  # 4% annual (T-bill proxy)


@dataclass
class TradeRecord:
    """Single trade result."""

    entry_price: float
    exit_price: float
    side: str  # "long" or "short"
    quantity: float = 1.0
    entry_time: int = 0  # Unix timestamp
    exit_time: int = 0
    fee_pct: float = 0.001  # 0.1% per side

    @property
    def pnl(self) -> float:
        if self.side == "long":
            gross = (self.exit_price - self.entry_price) * self.quantity
        else:
            gross = (self.entry_price - self.exit_price) * self.quantity
        fees = self.entry_price * self.quantity * self.fee_pct * 2
        return gross - fees

    @property
    def return_pct(self) -> float:
        cost = self.entry_price * self.quantity
        if cost == 0:
            return 0.0
        return (self.pnl / cost) * 100


@dataclass
class PerformanceReport:
    """Complete performance metrics report."""

    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0

    total_pnl: float = 0.0
    avg_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0  # Gross profit / Gross loss

    max_drawdown_pct: float = 0.0
    max_consecutive_losses: int = 0

    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0

    avg_return_pct: float = 0.0
    total_return_pct: float = 0.0
    annualized_return_pct: float = 0.0
    volatility_pct: float = 0.0

    best_trade_pct: float = 0.0
    worst_trade_pct: float = 0.0
    avg_holding_periods: float = 0.0  # In bars/candles

    equity_curve: list[float] = field(default_factory=list)


class PerformanceCalculator:
    """Calculates comprehensive trading performance metrics."""

    def calculate(
        self,
        trades: list[TradeRecord],
        initial_capital: float = 10000.0,
        periods_per_year: float = ANNUAL_FACTOR * 24,  # Hourly bars
    ) -> PerformanceReport:
        """Calculate all metrics from trade list."""
        if not trades:
            return PerformanceReport()

        report = PerformanceReport()
        report.total_trades = len(trades)

        # PnL arrays
        pnls = np.array([t.pnl for t in trades])
        returns = np.array([t.return_pct / 100 for t in trades])

        # Win/Loss
        wins = pnls[pnls > 0]
        losses = pnls[pnls <= 0]
        report.winning_trades = len(wins)
        report.losing_trades = len(losses)
        report.win_rate = (
            report.winning_trades / report.total_trades if report.total_trades > 0 else 0
        )

        # PnL stats
        report.total_pnl = float(np.sum(pnls))
        report.avg_pnl = float(np.mean(pnls))
        report.avg_win = float(np.mean(wins)) if len(wins) > 0 else 0.0
        report.avg_loss = float(np.mean(losses)) if len(losses) > 0 else 0.0

        # Profit factor
        gross_profit = float(np.sum(wins)) if len(wins) > 0 else 0.0
        gross_loss = abs(float(np.sum(losses))) if len(losses) > 0 else 0.0
        report.profit_factor = (
            gross_profit / gross_loss
            if gross_loss > 0
            else float("inf")
            if gross_profit > 0
            else 0.0
        )

        # Return stats
        return_pcts = np.array([t.return_pct for t in trades])
        report.avg_return_pct = float(np.mean(return_pcts))
        report.best_trade_pct = float(np.max(return_pcts))
        report.worst_trade_pct = float(np.min(return_pcts))

        # Equity curve + drawdown
        equity = [initial_capital]
        for pnl in pnls:
            equity.append(equity[-1] + pnl)
        report.equity_curve = [round(e, 2) for e in equity]
        report.total_return_pct = ((equity[-1] - initial_capital) / initial_capital) * 100

        report.max_drawdown_pct = self._max_drawdown(equity)

        # Consecutive losses
        report.max_consecutive_losses = self._max_consecutive_losses(pnls)

        # Risk-adjusted metrics
        if len(returns) > 1:
            report.volatility_pct = float(np.std(returns, ddof=1)) * 100
            report.sharpe_ratio = self._sharpe(returns, periods_per_year)
            report.sortino_ratio = self._sortino(returns, periods_per_year)
            if report.max_drawdown_pct != 0:
                ann_return = report.total_return_pct * (periods_per_year / max(len(trades), 1))
                report.calmar_ratio = ann_return / abs(report.max_drawdown_pct)

        # Holding period (if timestamps available)
        holding_times = [t.exit_time - t.entry_time for t in trades if t.exit_time > t.entry_time]
        if holding_times:
            report.avg_holding_periods = float(np.mean(holding_times))

        logger.info(
            "performance_calculated",
            trades=report.total_trades,
            win_rate=round(report.win_rate, 3),
            sharpe=round(report.sharpe_ratio, 3),
            max_dd=round(report.max_drawdown_pct, 2),
            total_return=round(report.total_return_pct, 2),
        )
        return report

    @staticmethod
    def _max_drawdown(equity: list[float]) -> float:
        if len(equity) < 2:
            return 0.0
        peak = equity[0]
        max_dd = 0.0
        for val in equity[1:]:
            if val > peak:
                peak = val
            dd = (peak - val) / peak * 100 if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
        return round(max_dd, 4)

    @staticmethod
    def _max_consecutive_losses(pnls: np.ndarray) -> int:
        max_streak = 0
        current = 0
        for pnl in pnls:
            if pnl <= 0:
                current += 1
                max_streak = max(max_streak, current)
            else:
                current = 0
        return max_streak

    @staticmethod
    def _sharpe(returns: np.ndarray, periods_per_year: float) -> float:
        rf_per_period = RISK_FREE_RATE / periods_per_year
        excess = returns - rf_per_period
        std = np.std(excess, ddof=1)
        if std == 0:
            return 0.0
        return float(np.mean(excess) / std * np.sqrt(periods_per_year))

    @staticmethod
    def _sortino(returns: np.ndarray, periods_per_year: float) -> float:
        rf_per_period = RISK_FREE_RATE / periods_per_year
        excess = returns - rf_per_period
        downside = excess[excess < 0]
        if len(downside) < 2:
            return 0.0
        downside_std = np.std(downside, ddof=1)
        if downside_std == 0:
            return 0.0
        return float(np.mean(excess) / downside_std * np.sqrt(periods_per_year))
