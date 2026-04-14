"""SMC+MACD Strategy — Track B (ETH branch).

SMC pure-causal (Version B) + MACD signal crossover consensus.
2/2 consensus required: both SMC and MACD must agree on direction.

Designed for ETH/USDT 1H as Track B experimental validation.
Separated from operational SMC+WT to avoid contamination.

Track: EXPERIMENTAL
Asset: ETH/USDT
Timeframe: 1H
Consensus: 2/2 (SMC + MACD)
"""

from __future__ import annotations

from typing import Any

import numpy as np

from app.models.signal import SignalType
from strategies.base import BaseStrategy
from strategies.indicators.macd import calc_macd
from strategies.smc_wavetrend_strategy import calc_smc_pure_causal

# Parameters
DEFAULT_INTERNAL_LENGTH = 5
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
SL_PCT = 0.02
TP_PCT = 0.04


class SMCMACDStrategy(BaseStrategy):
    """SMC pure-causal + MACD consensus strategy for ETH Track B.

    2/2 consensus: both SMC structural break and MACD crossover
    must fire in the same direction on the same bar.
    """

    def __init__(
        self,
        symbol: str = "ETH/USDT",
        exchange: str = "binance",
        internal_length: int = DEFAULT_INTERNAL_LENGTH,
        macd_fast: int = MACD_FAST,
        macd_slow: int = MACD_SLOW,
        macd_signal: int = MACD_SIGNAL,
    ):
        super().__init__(symbol, exchange)
        self.internal_length = internal_length
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal

    @property
    def name(self) -> str:
        return "SMC_MACD_1H"

    @property
    def min_bars(self) -> int:
        return max(2 * self.internal_length + 1, self.macd_slow + self.macd_signal + 1)

    def analyze(self, ohlcv: list[list], **kwargs) -> dict[str, Any] | None:
        if len(ohlcv) < self.min_bars:
            return None

        highs = np.array([c[2] for c in ohlcv], dtype=np.float64)
        lows = np.array([c[3] for c in ohlcv], dtype=np.float64)
        closes = np.array([c[4] for c in ohlcv], dtype=np.float64)
        current_price = closes[-1]

        # Indicator 1: SMC pure-causal
        smc_trend, smc_signals = calc_smc_pure_causal(
            highs,
            lows,
            closes,
            internal_length=self.internal_length,
        )

        # Indicator 2: MACD
        macd_line, signal_line, histogram, macd_signals = calc_macd(
            closes,
            fast_period=self.macd_fast,
            slow_period=self.macd_slow,
            signal_period=self.macd_signal,
        )

        # Diagnostic cache
        smc_last = int(smc_signals[-1])
        macd_last = int(macd_signals[-1])
        self._diag = {
            "smc_signal": smc_last,
            "macd_signal": macd_last,
            "macd_histogram": float(histogram[-1]) if not np.isnan(histogram[-1]) else 0.0,
            "smc_trend": int(smc_trend[-1]),
            "consensus": "NONE",
        }

        # 2/2 consensus check
        if smc_last == 0 and macd_last == 0:
            return None

        if smc_last != 0 and macd_last != 0 and smc_last == macd_last:
            direction = smc_last
            self._diag["consensus"] = "FULL"
        else:
            # Near-miss diagnostics
            if smc_last != 0 and macd_last == 0:
                self._diag["consensus"] = "SMC_ONLY"
            elif smc_last == 0 and macd_last != 0:
                self._diag["consensus"] = "MACD_ONLY"
            elif smc_last != macd_last:
                self._diag["consensus"] = "DIR_MISMATCH"
            return None

        # Generate signal
        if direction == 1:
            return self.generate_signal(
                signal_type=SignalType.LONG,
                entry_price=current_price,
                stop_loss=current_price * (1 - SL_PCT),
                take_profit=current_price * (1 + TP_PCT),
                confidence=0.65,
                metadata={
                    "smc_trend": int(smc_trend[-1]),
                    "macd_histogram": float(histogram[-1]) if not np.isnan(histogram[-1]) else 0.0,
                    "consensus": "2/2",
                    "track": "B",
                },
            )
        elif direction == -1:
            return self.generate_signal(
                signal_type=SignalType.SHORT,
                entry_price=current_price,
                stop_loss=current_price * (1 + SL_PCT),
                take_profit=current_price * (1 - TP_PCT),
                confidence=0.65,
                metadata={
                    "smc_trend": int(smc_trend[-1]),
                    "macd_histogram": float(histogram[-1]) if not np.isnan(histogram[-1]) else 0.0,
                    "consensus": "2/2",
                    "track": "B",
                },
            )

        return None
