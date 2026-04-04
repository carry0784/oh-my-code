"""
IndicatorCalculator — CR-038 Phase 1
Pure-function technical indicator calculations from OHLCV data.
No external dependencies beyond numpy — all calculations are self-contained.
"""

import numpy as np

from app.core.logging import get_logger
from app.schemas.market_state_schema import IndicatorSet, OHLCVBar

logger = get_logger(__name__)


class IndicatorCalculator:
    """Calculates technical indicators from OHLCV bar data."""

    def calculate(self, bars: list[OHLCVBar]) -> IndicatorSet:
        """Calculate all indicators from OHLCV bars. Returns partial results on insufficient data."""
        if len(bars) < 2:
            return IndicatorSet()

        closes = np.array([b.close for b in bars], dtype=np.float64)
        highs = np.array([b.high for b in bars], dtype=np.float64)
        lows = np.array([b.low for b in bars], dtype=np.float64)
        volumes = np.array([b.volume for b in bars], dtype=np.float64)

        result = IndicatorSet()

        # RSI(14)
        if len(closes) >= 15:
            result.rsi_14 = self._rsi(closes, 14)

        # MACD(12, 26, 9)
        if len(closes) >= 35:
            macd_line, signal, histogram = self._macd(closes)
            result.macd_line = macd_line
            result.macd_signal = signal
            result.macd_histogram = histogram

        # Bollinger Bands(20, 2)
        if len(closes) >= 20:
            result.bb_upper, result.bb_middle, result.bb_lower = self._bollinger(closes, 20, 2.0)

        # ATR(14)
        if len(closes) >= 15:
            result.atr_14 = self._atr(highs, lows, closes, 14)

        # OBV
        if len(closes) >= 2:
            result.obv = self._obv(closes, volumes)

        # SMAs
        if len(closes) >= 20:
            result.sma_20 = float(np.mean(closes[-20:]))
        if len(closes) >= 50:
            result.sma_50 = float(np.mean(closes[-50:]))
        if len(closes) >= 200:
            result.sma_200 = float(np.mean(closes[-200:]))

        # EMAs
        if len(closes) >= 12:
            result.ema_12 = self._ema(closes, 12)
        if len(closes) >= 26:
            result.ema_26 = self._ema(closes, 26)

        return result

    @staticmethod
    def _rsi(closes: np.ndarray, period: int) -> float:
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        # Wilder's smoothing (exponential)
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])

        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return float(100.0 - (100.0 / (1.0 + rs)))

    @staticmethod
    def _ema(data: np.ndarray, period: int) -> float:
        multiplier = 2.0 / (period + 1)
        ema = float(data[0])
        for val in data[1:]:
            ema = (float(val) - ema) * multiplier + ema
        return ema

    @staticmethod
    def _macd(
        closes: np.ndarray,
        fast: int = 12,
        slow: int = 26,
        signal_period: int = 9,
    ) -> tuple[float, float, float]:
        def ema_series(data: np.ndarray, period: int) -> np.ndarray:
            result = np.empty_like(data)
            multiplier = 2.0 / (period + 1)
            result[0] = data[0]
            for i in range(1, len(data)):
                result[i] = (data[i] - result[i - 1]) * multiplier + result[i - 1]
            return result

        ema_fast = ema_series(closes, fast)
        ema_slow = ema_series(closes, slow)
        macd_line = ema_fast - ema_slow
        signal_line = ema_series(macd_line, signal_period)
        histogram = macd_line - signal_line

        return float(macd_line[-1]), float(signal_line[-1]), float(histogram[-1])

    @staticmethod
    def _bollinger(closes: np.ndarray, period: int, num_std: float) -> tuple[float, float, float]:
        window = closes[-period:]
        middle = float(np.mean(window))
        std = float(np.std(window, ddof=1))
        upper = middle + num_std * std
        lower = middle - num_std * std
        return upper, middle, lower

    @staticmethod
    def _atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int) -> float:
        tr = np.maximum(
            highs[1:] - lows[1:],
            np.maximum(
                np.abs(highs[1:] - closes[:-1]),
                np.abs(lows[1:] - closes[:-1]),
            ),
        )
        # Wilder's smoothing
        atr = float(np.mean(tr[:period]))
        for i in range(period, len(tr)):
            atr = (atr * (period - 1) + float(tr[i])) / period
        return atr

    @staticmethod
    def _obv(closes: np.ndarray, volumes: np.ndarray) -> float:
        obv = 0.0
        for i in range(1, len(closes)):
            if closes[i] > closes[i - 1]:
                obv += volumes[i]
            elif closes[i] < closes[i - 1]:
                obv -= volumes[i]
        return obv
