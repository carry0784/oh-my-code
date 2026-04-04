"""Stage 4A: Qualification pipeline fixtures.

Golden set for testing the screening-qualification pipeline.
Reuses Stage 3B-2 screening fixtures + adds qualification-specific data.
"""

from __future__ import annotations

from app.services.data_provider import BacktestReadiness, DataQuality


# ══════════════════════════════════════════════════════════════════════
# Normal: Qualification-PASS backtest readiness (paired with screening)
# ══════════════════════════════════════════════════════════════════════

QUAL_BACKTEST_BTC_PASS = BacktestReadiness(
    symbol="BTC/USDT",
    available_bars=2000,
    sharpe_ratio=0.85,
    missing_data_pct=0.3,
    quality=DataQuality.HIGH,
)

QUAL_BACKTEST_SOL_PASS = BacktestReadiness(
    symbol="SOL/USDT",
    available_bars=1500,
    sharpe_ratio=0.65,
    missing_data_pct=0.5,
    quality=DataQuality.HIGH,
)

QUAL_BACKTEST_AAPL_PASS = BacktestReadiness(
    symbol="AAPL",
    available_bars=3000,
    sharpe_ratio=1.1,
    missing_data_pct=0.1,
    quality=DataQuality.HIGH,
)

QUAL_BACKTEST_KR_PASS = BacktestReadiness(
    symbol="005930",
    available_bars=2500,
    sharpe_ratio=0.7,
    missing_data_pct=0.2,
    quality=DataQuality.HIGH,
)


# ══════════════════════════════════════════════════════════════════════
# Failure: Qualification-specific failure scenarios
# ══════════════════════════════════════════════════════════════════════

# Negative Sharpe → check 6 fail
QUAL_BACKTEST_NEGATIVE_SHARPE = BacktestReadiness(
    symbol="BTC/USDT",
    available_bars=2000,
    sharpe_ratio=-0.5,
    missing_data_pct=0.3,
    quality=DataQuality.HIGH,
)

# Insufficient bars → check 5 fail (bars < 500)
QUAL_BACKTEST_LOW_BARS = BacktestReadiness(
    symbol="BTC/USDT",
    available_bars=100,
    sharpe_ratio=0.85,
    missing_data_pct=0.3,
    quality=DataQuality.HIGH,
)

# High missing data → check 4 fail (missing > 5%)
QUAL_BACKTEST_HIGH_MISSING = BacktestReadiness(
    symbol="BTC/USDT",
    available_bars=2000,
    sharpe_ratio=0.85,
    missing_data_pct=10.0,
    quality=DataQuality.DEGRADED,
)
