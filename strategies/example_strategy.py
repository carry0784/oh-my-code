from typing import Any
import numpy as np

from strategies.base import BaseStrategy
from app.models.signal import SignalType


class SimpleMAStrategy(BaseStrategy):
    """Example strategy using simple moving average crossover."""

    def __init__(self, symbol: str, exchange: str = "binance", fast_period: int = 10, slow_period: int = 20):
        super().__init__(symbol, exchange)
        self.fast_period = fast_period
        self.slow_period = slow_period

    @property
    def name(self) -> str:
        return f"SMA_{self.fast_period}_{self.slow_period}"

    def analyze(self, ohlcv: list[list], **kwargs) -> dict[str, Any] | None:
        if len(ohlcv) < self.slow_period + 1:
            return None

        closes = np.array([candle[4] for candle in ohlcv])

        fast_ma = np.convolve(closes, np.ones(self.fast_period) / self.fast_period, mode="valid")
        slow_ma = np.convolve(closes, np.ones(self.slow_period) / self.slow_period, mode="valid")

        # Align arrays
        min_len = min(len(fast_ma), len(slow_ma))
        fast_ma = fast_ma[-min_len:]
        slow_ma = slow_ma[-min_len:]

        current_price = closes[-1]

        # Bullish crossover
        if fast_ma[-1] > slow_ma[-1] and fast_ma[-2] <= slow_ma[-2]:
            stop_loss = current_price * 0.98  # 2% stop
            take_profit = current_price * 1.04  # 4% target
            return self.generate_signal(
                signal_type=SignalType.LONG,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=0.6,
                metadata={"fast_ma": float(fast_ma[-1]), "slow_ma": float(slow_ma[-1])},
            )

        # Bearish crossover
        if fast_ma[-1] < slow_ma[-1] and fast_ma[-2] >= slow_ma[-2]:
            stop_loss = current_price * 1.02
            take_profit = current_price * 0.96
            return self.generate_signal(
                signal_type=SignalType.SHORT,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=0.6,
                metadata={"fast_ma": float(fast_ma[-1]), "slow_ma": float(slow_ma[-1])},
            )

        return None
