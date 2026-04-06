"""BacktestReadinessStub — CR-048 Follow-Up 2A P1.

Stub BacktestDataProvider returning CR-046 sealed backtest readiness values.

Pure lookup, no DB, no I/O.
Returns UNAVAILABLE for unknown symbols.
"""

from __future__ import annotations

from app.services.data_provider import BacktestReadiness, DataQuality

# ── CR-046 sealed results ────────────────────────────────────────────

_STUB_CONFIG: dict[str, BacktestReadiness] = {
    "SOL/USDT": BacktestReadiness(
        symbol="SOL/USDT",
        available_bars=1500,
        sharpe_ratio=1.0,
        missing_data_pct=1.0,
        quality=DataQuality.HIGH,
    ),
    "BTC/USDT": BacktestReadiness(
        symbol="BTC/USDT",
        available_bars=2000,
        sharpe_ratio=1.2,
        missing_data_pct=0.5,
        quality=DataQuality.HIGH,
    ),
}


class BacktestReadinessStub:
    """Stub provider returning CR-046 sealed backtest readiness values.

    Pure lookup, no DB, no I/O. Returns UNAVAILABLE for unknown symbols.
    """

    STUB_VERSION: str = "cr046-sealed-v1"

    def get_readiness(self, symbol: str) -> BacktestReadiness:
        """Return sealed BacktestReadiness for *symbol*.

        Unknown symbols receive quality=UNAVAILABLE.
        Never raises.
        """
        return _STUB_CONFIG.get(
            symbol,
            BacktestReadiness(symbol=symbol, quality=DataQuality.UNAVAILABLE),
        )

    def get_supported_symbols(self) -> list[str]:
        """Return list of symbols with sealed CR-046 data."""
        return list(_STUB_CONFIG.keys())
