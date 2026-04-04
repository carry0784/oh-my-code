"""Strategy Analyzer — safe strategy module loading + analyze() invocation.

Phase 6B-1 of CR-048.  Provides:
  - Strategy module loading from compute_module path
  - analyze() invocation with error isolation
  - Signal/NoSignal/Error result wrapping
  - Per-pair failure never crashes the cycle
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


# ── Analysis Status ───────────────────────────────────────────────────


class AnalysisStatus(str, Enum):
    """Outcome of a single strategy×symbol analyze() call."""

    SIGNAL = "signal"
    NO_SIGNAL = "no_signal"
    ERROR = "error"
    SKIPPED = "skipped"


# ── Signal Contract ───────────────────────────────────────────────────


@dataclass
class AnalyzeSignal:
    """Minimal signal contract produced by analyze().

    This is the standardized output regardless of which strategy
    produced it. Raw strategy output is preserved in metadata.
    """

    symbol: str
    strategy_id: str
    timeframe: str
    direction: str  # "long" | "short"
    score: float  # 0.0-1.0 confidence
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "strategy_id": self.strategy_id,
            "timeframe": self.timeframe,
            "direction": self.direction,
            "score": self.score,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "generated_at": self.generated_at.isoformat(),
            "metadata": self.metadata,
        }


# ── Analyze Result ────────────────────────────────────────────────────


@dataclass
class AnalyzeResult:
    """Result of one analyze() invocation, wrapping all possible outcomes."""

    symbol: str
    strategy_id: str
    timeframe: str
    status: AnalysisStatus
    signal: AnalyzeSignal | None = None
    error_type: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict:
        d = {
            "symbol": self.symbol,
            "strategy_id": self.strategy_id,
            "timeframe": self.timeframe,
            "status": self.status.value,
        }
        if self.signal:
            d["signal"] = self.signal.to_dict()
        if self.error_type:
            d["error_type"] = self.error_type
            d["error_message"] = self.error_message
        return d


# ── Strategy Analyzer ─────────────────────────────────────────────────


class StrategyAnalyzer:
    """Loads strategy modules and invokes analyze() with error isolation.

    Each analyze() call is wrapped in try/except so that one pair's
    failure never crashes the entire cycle.
    """

    def __init__(self) -> None:
        self._module_cache: dict[str, object] = {}

    def analyze(
        self,
        *,
        compute_module: str,
        strategy_id: str,
        symbol: str,
        timeframe: str,
        ohlcv: list[list] | None = None,
        features: dict | None = None,
        **kwargs,
    ) -> AnalyzeResult:
        """Load strategy module and invoke analyze().

        Args:
            compute_module: dotted module path (e.g. "strategies.rsi_cross_strategy")
            strategy_id: strategy identifier
            symbol: symbol being evaluated
            timeframe: timeframe
            ohlcv: OHLCV candle data (may be None if not available)
            features: pre-computed features from cache
            **kwargs: additional args passed to strategy.analyze()

        Returns:
            AnalyzeResult wrapping signal/no-signal/error.
        """
        try:
            strategy_instance = self._load_strategy(compute_module)
        except Exception as e:
            logger.warning("Failed to load strategy module %s: %s", compute_module, e)
            return AnalyzeResult(
                symbol=symbol,
                strategy_id=strategy_id,
                timeframe=timeframe,
                status=AnalysisStatus.ERROR,
                error_type="module_load_error",
                error_message=str(e),
            )

        try:
            raw_result = strategy_instance.analyze(ohlcv or [], features=features, **kwargs)
        except Exception as e:
            logger.warning(
                "Strategy %s analyze() error for %s: %s",
                strategy_id,
                symbol,
                e,
            )
            return AnalyzeResult(
                symbol=symbol,
                strategy_id=strategy_id,
                timeframe=timeframe,
                status=AnalysisStatus.ERROR,
                error_type="analyze_error",
                error_message=str(e),
            )

        if raw_result is None:
            return AnalyzeResult(
                symbol=symbol,
                strategy_id=strategy_id,
                timeframe=timeframe,
                status=AnalysisStatus.NO_SIGNAL,
            )

        # Convert raw strategy output to standardized signal
        signal = self._to_signal(raw_result, strategy_id, symbol, timeframe)
        return AnalyzeResult(
            symbol=symbol,
            strategy_id=strategy_id,
            timeframe=timeframe,
            status=AnalysisStatus.SIGNAL,
            signal=signal,
        )

    def _load_strategy(self, compute_module: str) -> object:
        """Load and cache a strategy module instance.

        Expects the module to have a class with a name attribute
        and an analyze(ohlcv, **kwargs) method.
        """
        if compute_module in self._module_cache:
            return self._module_cache[compute_module]

        mod = importlib.import_module(compute_module)

        # Find strategy class: look for a class with analyze method
        strategy_cls = None
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if isinstance(attr, type) and hasattr(attr, "analyze") and attr_name != "BaseStrategy":
                strategy_cls = attr
                break

        if strategy_cls is None:
            raise ImportError(f"No strategy class with analyze() found in {compute_module}")

        instance = strategy_cls()
        self._module_cache[compute_module] = instance
        return instance

    @staticmethod
    def _to_signal(
        raw: dict,
        strategy_id: str,
        symbol: str,
        timeframe: str,
    ) -> AnalyzeSignal:
        """Convert raw strategy output dict to standardized AnalyzeSignal."""
        signal_type = raw.get("signal_type", "")
        if hasattr(signal_type, "value"):
            signal_type = signal_type.value

        direction = signal_type.lower() if signal_type else "unknown"

        return AnalyzeSignal(
            symbol=symbol,
            strategy_id=strategy_id,
            timeframe=timeframe,
            direction=direction,
            score=float(raw.get("confidence", 0.0)),
            entry_price=raw.get("entry_price"),
            stop_loss=raw.get("stop_loss"),
            take_profit=raw.get("take_profit"),
            metadata={
                k: v
                for k, v in raw.items()
                if k not in ("signal_type", "confidence", "entry_price", "stop_loss", "take_profit")
            },
        )
