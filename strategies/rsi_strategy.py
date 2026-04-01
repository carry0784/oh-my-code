"""
RSICrossStrategy — CR-045
RSI overbought/oversold crossover strategy.
Generates signals when RSI crosses above oversold or below overbought thresholds.

Higher signal frequency than SMA crossover in ranging/inactive markets.
"""

from typing import Any

import numpy as np

from app.models.signal import SignalType
from strategies.base import BaseStrategy


class RSICrossStrategy(BaseStrategy):
    """RSI overbought/oversold crossover strategy."""

    def __init__(
        self,
        symbol: str,
        exchange: str = "binance",
        rsi_period: int = 14,
        rsi_overbought: float = 70.0,
        rsi_oversold: float = 30.0,
    ):
        super().__init__(symbol, exchange)
        self.rsi_period = rsi_period
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold

    @property
    def name(self) -> str:
        return f"RSI_{self.rsi_period}_{int(self.rsi_overbought)}_{int(self.rsi_oversold)}"

    def _compute_rsi(self, closes: np.ndarray) -> np.ndarray:
        """Compute RSI from close prices."""
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        # Wilder's smoothed moving average
        avg_gain = np.zeros(len(deltas))
        avg_loss = np.zeros(len(deltas))

        # Initial SMA for first period
        if len(gains) < self.rsi_period:
            return np.full(len(closes), 50.0)  # neutral if insufficient data

        avg_gain[self.rsi_period - 1] = np.mean(gains[:self.rsi_period])
        avg_loss[self.rsi_period - 1] = np.mean(losses[:self.rsi_period])

        for i in range(self.rsi_period, len(deltas)):
            avg_gain[i] = (avg_gain[i - 1] * (self.rsi_period - 1) + gains[i]) / self.rsi_period
            avg_loss[i] = (avg_loss[i - 1] * (self.rsi_period - 1) + losses[i]) / self.rsi_period

        # Compute RSI
        rsi = np.full(len(closes), 50.0)
        for i in range(self.rsi_period - 1, len(deltas)):
            if avg_loss[i] == 0:
                rsi[i + 1] = 100.0
            else:
                rs = avg_gain[i] / avg_loss[i]
                rsi[i + 1] = 100.0 - (100.0 / (1.0 + rs))

        return rsi

    def analyze(self, ohlcv: list[list], **kwargs) -> dict[str, Any] | None:
        if len(ohlcv) < self.rsi_period + 2:
            return None

        closes = np.array([candle[4] for candle in ohlcv])
        rsi = self._compute_rsi(closes)
        current_price = closes[-1]

        # Bullish: RSI crosses above oversold (from below to above)
        if rsi[-2] <= self.rsi_oversold and rsi[-1] > self.rsi_oversold:
            stop_loss = current_price * 0.98
            take_profit = current_price * 1.04
            return self.generate_signal(
                signal_type=SignalType.LONG,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=0.6,
                metadata={"rsi": float(rsi[-1]), "rsi_prev": float(rsi[-2])},
            )

        # Bearish: RSI crosses below overbought (from above to below)
        if rsi[-2] >= self.rsi_overbought and rsi[-1] < self.rsi_overbought:
            stop_loss = current_price * 1.02
            take_profit = current_price * 0.96
            return self.generate_signal(
                signal_type=SignalType.SHORT,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=0.6,
                metadata={"rsi": float(rsi[-1]), "rsi_prev": float(rsi[-2])},
            )

        return None
