from abc import ABC, abstractmethod
from typing import Any

from app.models.signal import SignalType


class BaseStrategy(ABC):
    def __init__(self, symbol: str, exchange: str = "binance"):
        self.symbol = symbol
        self.exchange = exchange

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def analyze(self, ohlcv: list[list], **kwargs) -> dict[str, Any]:
        """
        Analyze market data and return signal if conditions are met.

        Args:
            ohlcv: List of [timestamp, open, high, low, close, volume]

        Returns:
            dict with keys: signal_type, entry_price, stop_loss, take_profit, confidence
            or None if no signal
        """
        pass

    def generate_signal(
        self,
        signal_type: SignalType,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        confidence: float,
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        return {
            "source": self.name,
            "exchange": self.exchange,
            "symbol": self.symbol,
            "signal_type": signal_type,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "confidence": confidence,
            "metadata": metadata or {},
        }
