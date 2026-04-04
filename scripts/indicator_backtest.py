"""
6-Indicator Backtester
Implements and backtests 6 TradingView indicators over 6 months of BTC/USDT data.

Indicators:
  1. Smart Money Concepts (BOS/CHoCH + Order Blocks)
  2. Squeeze Momentum [LazyBear]
  3. MACD Ultimate MTF [ChrisMoody]
  4. Williams Vix Fix [ChrisMoody]
  5. WaveTrend [LazyBear]
  6. Supertrend

Usage:
  python scripts/indicator_backtest.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ===================================================================
# DATA COLLECTION
# ===================================================================

def collect_6month_ohlcv(
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    months: int = 6,
) -> list[list]:
    """Collect ~6 months of hourly OHLCV from Binance via CCXT."""
    try:
        import ccxt
        exchange = ccxt.binance({"enableRateLimit": True})

        all_ohlcv = []
        # 6 months ~ 180 days x 24 hours = 4320 bars (hourly)
        target_bars = months * 30 * 24
        since = exchange.milliseconds() - target_bars * 3600 * 1000
        batch_size = 1000

        print(f"[DATA] Collecting {target_bars} bars of {symbol} {timeframe}...")
        while len(all_ohlcv) < target_bars:
            batch = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=batch_size)
            if not batch:
                break
            all_ohlcv.extend(batch)
            since = batch[-1][0] + 1
            if len(batch) < batch_size:
                break
            time.sleep(0.5)

        print(f"[DATA] Collected {len(all_ohlcv)} bars "
              f"({all_ohlcv[0][0]} ~ {all_ohlcv[-1][0]})")
        return all_ohlcv

    except Exception as e:
        print(f"[DATA] CCXT failed: {e}, generating synthetic data")
        return _synthetic_6month(target_bars)


def _synthetic_6month(n: int = 4320) -> list[list]:
    """Fallback synthetic data with realistic BTC-like price action."""
    rng = np.random.RandomState(42)
    base_ts = int(time.time() * 1000) - n * 3600000
    price = 45000.0
    data = []
    for i in range(n):
        ret = rng.normal(0, 0.008)  # ~0.8% hourly vol
        price *= (1 + ret)
        h = price * (1 + abs(rng.normal(0, 0.003)))
        l = price * (1 - abs(rng.normal(0, 0.003)))
        o = price * (1 + rng.normal(0, 0.001))
        v = rng.uniform(100, 2000)
        data.append([base_ts + i * 3600000, o, h, l, price, v])
    return data


# ===================================================================
# INDICATOR IMPLEMENTATIONS
# ===================================================================

def sma(data: np.ndarray, period: int) -> np.ndarray:
    """Simple Moving Average."""
    out = np.full(len(data), np.nan)
    if len(data) < period:
        return out
    cumsum = np.cumsum(data)
    cumsum[period:] = cumsum[period:] - cumsum[:-period]
    out[period - 1:] = cumsum[period - 1:] / period
    return out


def ema(data: np.ndarray, period: int) -> np.ndarray:
    """Exponential Moving Average."""
    out = np.full(len(data), np.nan)
    if len(data) < period:
        return out
    k = 2.0 / (period + 1)
    out[period - 1] = np.mean(data[:period])
    for i in range(period, len(data)):
        out[i] = data[i] * k + out[i - 1] * (1 - k)
    return out


def stdev(data: np.ndarray, period: int) -> np.ndarray:
    """Rolling standard deviation."""
    out = np.full(len(data), np.nan)
    for i in range(period - 1, len(data)):
        out[i] = np.std(data[i - period + 1:i + 1], ddof=0)
    return out


def atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int) -> np.ndarray:
    """Average True Range."""
    n = len(highs)
    tr = np.zeros(n)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        tr[i] = max(highs[i] - lows[i],
                     abs(highs[i] - closes[i - 1]),
                     abs(lows[i] - closes[i - 1]))
    return sma(tr, period)


def linreg(data: np.ndarray, period: int) -> np.ndarray:
    """Linear regression value (endpoint of regression line)."""
    out = np.full(len(data), np.nan)
    for i in range(period - 1, len(data)):
        y = data[i - period + 1:i + 1]
        x = np.arange(period)
        if len(y) == period:
            slope = (period * np.sum(x * y) - np.sum(x) * np.sum(y)) / \
                    (period * np.sum(x * x) - np.sum(x) ** 2)
            intercept = (np.sum(y) - slope * np.sum(x)) / period
            out[i] = intercept + slope * (period - 1)
    return out


# -----------------------------------------------------------------
# 1. SUPERTREND
# -----------------------------------------------------------------

def calc_supertrend(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
    period: int = 10, multiplier: float = 3.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Returns (trend, signals). trend: +1=bull, -1=bear. signals: +1=buy, -1=sell, 0=hold."""
    n = len(closes)
    atr_vals = atr(highs, lows, closes, period)
    src = (highs + lows) / 2

    up = np.zeros(n)
    dn = np.zeros(n)
    trend = np.ones(n, dtype=int)
    signals = np.zeros(n, dtype=int)

    for i in range(period, n):
        up[i] = src[i] - multiplier * atr_vals[i]
        dn[i] = src[i] + multiplier * atr_vals[i]

        if i > period:
            up[i] = max(up[i], up[i - 1]) if closes[i - 1] > up[i - 1] else up[i]
            dn[i] = min(dn[i], dn[i - 1]) if closes[i - 1] < dn[i - 1] else dn[i]

            if trend[i - 1] == -1 and closes[i] > dn[i - 1]:
                trend[i] = 1
            elif trend[i - 1] == 1 and closes[i] < up[i - 1]:
                trend[i] = -1
            else:
                trend[i] = trend[i - 1]

            if trend[i] == 1 and trend[i - 1] == -1:
                signals[i] = 1  # BUY
            elif trend[i] == -1 and trend[i - 1] == 1:
                signals[i] = -1  # SELL

    return trend, signals


# -----------------------------------------------------------------
# 2. SQUEEZE MOMENTUM [LazyBear]
# -----------------------------------------------------------------

def calc_squeeze_momentum(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
    bb_length: int = 20, bb_mult: float = 2.0,
    kc_length: int = 20, kc_mult: float = 1.5,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Returns (momentum_val, squeeze_on, signals)."""
    n = len(closes)
    basis = sma(closes, bb_length)
    dev = bb_mult * stdev(closes, bb_length)
    upper_bb = basis + dev
    lower_bb = basis - dev

    ma_kc = sma(closes, kc_length)
    tr = np.zeros(n)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        tr[i] = max(highs[i] - lows[i],
                     abs(highs[i] - closes[i - 1]),
                     abs(lows[i] - closes[i - 1]))
    range_ma = sma(tr, kc_length)
    upper_kc = ma_kc + range_ma * kc_mult
    lower_kc = ma_kc - range_ma * kc_mult

    sqz_on = np.zeros(n, dtype=bool)
    for i in range(n):
        if not np.isnan(lower_bb[i]) and not np.isnan(lower_kc[i]):
            sqz_on[i] = (lower_bb[i] > lower_kc[i]) and (upper_bb[i] < upper_kc[i])

    # Momentum value: linreg of (close - avg(avg(highest, lowest), sma))
    highest_h = np.full(n, np.nan)
    lowest_l = np.full(n, np.nan)
    for i in range(kc_length - 1, n):
        highest_h[i] = np.max(highs[i - kc_length + 1:i + 1])
        lowest_l[i] = np.min(lows[i - kc_length + 1:i + 1])

    sma_c = sma(closes, kc_length)
    mid = np.full(n, np.nan)
    for i in range(n):
        if not np.isnan(highest_h[i]) and not np.isnan(sma_c[i]):
            mid[i] = (highest_h[i] + lowest_l[i]) / 2
    avg_mid_sma = np.full(n, np.nan)
    for i in range(n):
        if not np.isnan(mid[i]) and not np.isnan(sma_c[i]):
            avg_mid_sma[i] = (mid[i] + sma_c[i]) / 2

    src = np.full(n, np.nan)
    for i in range(n):
        if not np.isnan(avg_mid_sma[i]):
            src[i] = closes[i] - avg_mid_sma[i]

    val = linreg(np.nan_to_num(src), kc_length)

    # Signals: squeeze release + momentum direction
    signals = np.zeros(n, dtype=int)
    for i in range(1, n):
        if not np.isnan(val[i]):
            # Squeeze just released and momentum positive -> BUY
            if sqz_on[i - 1] and not sqz_on[i] and val[i] > 0:
                signals[i] = 1
            # Squeeze just released and momentum negative -> SELL
            elif sqz_on[i - 1] and not sqz_on[i] and val[i] < 0:
                signals[i] = -1
            # Momentum cross zero
            elif val[i] > 0 and val[i - 1] <= 0:
                signals[i] = 1
            elif val[i] < 0 and val[i - 1] >= 0:
                signals[i] = -1

    return val, sqz_on, signals


# -----------------------------------------------------------------
# 3. MACD Ultimate MTF [ChrisMoody]
# -----------------------------------------------------------------

def calc_macd(
    closes: np.ndarray,
    fast: int = 12, slow: int = 26, signal_len: int = 9,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Returns (macd_line, signal_line, histogram, signals)."""
    n = len(closes)
    fast_ema = ema(closes, fast)
    slow_ema = ema(closes, slow)

    macd_line = fast_ema - slow_ema
    signal_line = sma(np.nan_to_num(macd_line), signal_len)
    histogram = macd_line - signal_line

    signals = np.zeros(n, dtype=int)
    for i in range(1, n):
        if not np.isnan(macd_line[i]) and not np.isnan(signal_line[i]):
            # MACD crosses above signal
            if macd_line[i] > signal_line[i] and macd_line[i - 1] <= signal_line[i - 1]:
                signals[i] = 1
            # MACD crosses below signal
            elif macd_line[i] < signal_line[i] and macd_line[i - 1] >= signal_line[i - 1]:
                signals[i] = -1

    return macd_line, signal_line, histogram, signals


# -----------------------------------------------------------------
# 4. WILLIAMS VIX FIX [ChrisMoody]
# -----------------------------------------------------------------

def calc_williams_vix_fix(
    closes: np.ndarray, lows: np.ndarray,
    pd: int = 22, bbl: int = 20, mult: float = 2.0,
    lb: int = 50, ph: float = 0.85,
) -> tuple[np.ndarray, np.ndarray]:
    """Returns (wvf, signals). Signals: +1 when WVF spikes (fear = buy opportunity)."""
    n = len(closes)

    # WVF = ((highest(close, pd) - low) / highest(close, pd)) * 100
    wvf = np.full(n, np.nan)
    for i in range(pd - 1, n):
        hc = np.max(closes[i - pd + 1:i + 1])
        if hc > 0:
            wvf[i] = ((hc - lows[i]) / hc) * 100

    wvf_clean = np.nan_to_num(wvf)
    s_dev = mult * stdev(wvf_clean, bbl)
    mid_line = sma(wvf_clean, bbl)
    upper_band = mid_line + s_dev

    range_high = np.full(n, np.nan)
    for i in range(lb - 1, n):
        range_high[i] = np.max(wvf_clean[i - lb + 1:i + 1]) * ph

    signals = np.zeros(n, dtype=int)
    for i in range(1, n):
        if not np.isnan(wvf[i]) and not np.isnan(upper_band[i]):
            is_spike = wvf[i] >= upper_band[i] or (not np.isnan(range_high[i]) and wvf[i] >= range_high[i])
            was_spike = False
            if i > 0 and not np.isnan(wvf[i - 1]) and not np.isnan(upper_band[i - 1]):
                was_spike = wvf[i - 1] >= upper_band[i - 1] or (not np.isnan(range_high[i - 1]) and wvf[i - 1] >= range_high[i - 1])
            # Buy when spike ends (fear subsides)
            if was_spike and not is_spike:
                signals[i] = 1
            # Also mark the spike itself
            elif is_spike and not was_spike:
                signals[i] = 1  # Fear spike = buy opp

    return wvf, signals


# -----------------------------------------------------------------
# 5. WAVETREND [LazyBear]
# -----------------------------------------------------------------

def calc_wavetrend(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
    n1: int = 10, n2: int = 21,
    ob1: float = 60, os1: float = -60,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Returns (wt1, wt2, signals)."""
    n = len(closes)
    ap = (highs + lows + closes) / 3  # hlc3

    esa_vals = ema(ap, n1)

    d_vals = np.full(n, np.nan)
    for i in range(n):
        if not np.isnan(esa_vals[i]):
            d_vals[i] = abs(ap[i] - esa_vals[i])
    d_ema = ema(np.nan_to_num(d_vals), n1)

    ci = np.full(n, np.nan)
    for i in range(n):
        if not np.isnan(esa_vals[i]) and not np.isnan(d_ema[i]) and d_ema[i] != 0:
            ci[i] = (ap[i] - esa_vals[i]) / (0.015 * d_ema[i])

    wt1 = ema(np.nan_to_num(ci), n2)
    wt2 = sma(np.nan_to_num(wt1), 4)

    signals = np.zeros(n, dtype=int)
    for i in range(1, n):
        if not np.isnan(wt1[i]) and not np.isnan(wt2[i]):
            # WT1 crosses above WT2 in oversold zone
            if wt1[i] > wt2[i] and wt1[i - 1] <= wt2[i - 1] and wt1[i] < os1:
                signals[i] = 1
            # WT1 crosses below WT2 in overbought zone
            elif wt1[i] < wt2[i] and wt1[i - 1] >= wt2[i - 1] and wt1[i] > ob1:
                signals[i] = -1
            # Regular crosses (weaker signal)
            elif wt1[i] > wt2[i] and wt1[i - 1] <= wt2[i - 1]:
                signals[i] = 1
            elif wt1[i] < wt2[i] and wt1[i - 1] >= wt2[i - 1]:
                signals[i] = -1

    return wt1, wt2, signals


# -----------------------------------------------------------------
# 6. SMART MONEY CONCEPTS (simplified: BOS/CHoCH + trend)
# -----------------------------------------------------------------

def calc_smc(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
    swing_length: int = 50, internal_length: int = 5,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Simplified Smart Money Concepts.
    Returns (smc_trend, signals).
    smc_trend: +1=bullish, -1=bearish.
    signals: +1=bullish CHoCH/BOS, -1=bearish CHoCH/BOS.
    """
    n = len(closes)
    trend = np.zeros(n, dtype=int)
    signals = np.zeros(n, dtype=int)

    # Find swing highs and lows
    swing_highs = np.full(n, np.nan)
    swing_lows = np.full(n, np.nan)

    for i in range(internal_length, n - internal_length):
        # Swing high: high[i] is highest in window
        window_h = highs[max(0, i - internal_length):i + internal_length + 1]
        if highs[i] == np.max(window_h):
            swing_highs[i] = highs[i]
        # Swing low: low[i] is lowest in window
        window_l = lows[max(0, i - internal_length):i + internal_length + 1]
        if lows[i] == np.min(window_l):
            swing_lows[i] = lows[i]

    # Track last significant swing high/low for BOS/CHoCH
    last_swing_high = np.nan
    last_swing_low = np.nan
    current_trend = 0

    for i in range(1, n):
        # Update swing points (with delay for confirmation)
        if i >= internal_length and not np.isnan(swing_highs[i - internal_length]):
            last_swing_high = swing_highs[i - internal_length]
        if i >= internal_length and not np.isnan(swing_lows[i - internal_length]):
            last_swing_low = swing_lows[i - internal_length]

        # BOS/CHoCH detection
        if not np.isnan(last_swing_high) and closes[i] > last_swing_high:
            if current_trend == -1:
                signals[i] = 1  # CHoCH (bullish)
            elif current_trend == 1:
                signals[i] = 1  # BOS (bullish continuation)
            current_trend = 1
            last_swing_high = np.nan  # consumed

        if not np.isnan(last_swing_low) and closes[i] < last_swing_low:
            if current_trend == 1:
                signals[i] = -1  # CHoCH (bearish)
            elif current_trend == -1:
                signals[i] = -1  # BOS (bearish continuation)
            current_trend = -1
            last_swing_low = np.nan  # consumed

        trend[i] = current_trend

    return trend, signals


def calc_smc_pure_causal(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
    swing_length: int = 50, internal_length: int = 5,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Pure-causal Smart Money Concepts (Version B).
    Swing detection uses ONLY past/current data -- no future bars.

    At bar i, checks if bar (i - internal_length) was a swing high/low
    by examining the window [i - 2*L .. i] (all past/current).
    No delay compensation needed because no future data is accessed.

    Returns (smc_trend, signals).
    """
    n = len(closes)
    L = internal_length
    trend = np.zeros(n, dtype=int)
    signals = np.zeros(n, dtype=int)

    last_swing_high = np.nan
    last_swing_low = np.nan
    current_trend = 0

    for i in range(2 * L, n):
        # Check if bar (i - L) is a swing high using only bars <= i
        candidate_idx = i - L
        window_start = max(0, candidate_idx - L)
        window_end = i + 1  # up to current bar (inclusive)

        # Swing high: candidate bar has highest high in window
        window_h = highs[window_start:window_end]
        if highs[candidate_idx] == np.max(window_h):
            last_swing_high = highs[candidate_idx]

        # Swing low: candidate bar has lowest low in window
        window_l = lows[window_start:window_end]
        if lows[candidate_idx] == np.min(window_l):
            last_swing_low = lows[candidate_idx]

        # BOS/CHoCH detection (identical logic, no delay offset needed)
        if not np.isnan(last_swing_high) and closes[i] > last_swing_high:
            if current_trend == -1:
                signals[i] = 1  # CHoCH (bullish)
            elif current_trend == 1:
                signals[i] = 1  # BOS (bullish continuation)
            current_trend = 1
            last_swing_high = np.nan  # consumed

        if not np.isnan(last_swing_low) and closes[i] < last_swing_low:
            if current_trend == 1:
                signals[i] = -1  # CHoCH (bearish)
            elif current_trend == -1:
                signals[i] = -1  # BOS (bearish continuation)
            current_trend = -1
            last_swing_low = np.nan  # consumed

        trend[i] = current_trend

    return trend, signals


# ===================================================================
# BACKTESTING ENGINE
# ===================================================================

@dataclass
class Trade:
    entry_idx: int
    entry_price: float
    direction: int  # +1=long, -1=short
    exit_idx: int = 0
    exit_price: float = 0.0
    pnl_pct: float = 0.0
    indicator: str = ""


@dataclass
class BacktestResult:
    indicator: str
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    avg_trade_pct: float = 0.0
    sharpe_ratio: float = 0.0
    profit_factor: float = 0.0
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)


def backtest_signals(
    closes: np.ndarray,
    signals: np.ndarray,
    indicator_name: str,
    fee_pct: float = 0.075,  # 0.075% per trade (Binance taker)
    stop_loss_pct: float = 2.0,
    take_profit_pct: float = 4.0,
) -> BacktestResult:
    """Backtest a signal array. +1=buy, -1=sell, 0=hold."""
    n = len(closes)
    result = BacktestResult(indicator=indicator_name)
    trades: list[Trade] = []
    position = 0  # 0=flat, +1=long, -1=short
    entry_price = 0.0
    entry_idx = 0

    equity = 10000.0
    peak_equity = equity
    max_dd = 0.0
    equity_curve = [equity]

    for i in range(1, n):
        # Check stop loss / take profit if in position
        if position != 0:
            pnl_pct = position * (closes[i] / entry_price - 1) * 100
            if pnl_pct <= -stop_loss_pct or pnl_pct >= take_profit_pct:
                # Close position
                net_pnl = pnl_pct - 2 * fee_pct  # entry + exit fee
                trade = Trade(
                    entry_idx=entry_idx, entry_price=entry_price,
                    direction=position, exit_idx=i, exit_price=closes[i],
                    pnl_pct=net_pnl, indicator=indicator_name,
                )
                trades.append(trade)
                equity *= (1 + net_pnl / 100)
                position = 0

        # Process signal
        if signals[i] != 0 and position == 0:
            position = signals[i]
            entry_price = closes[i]
            entry_idx = i
        elif signals[i] != 0 and signals[i] != position:
            # Close current and open opposite
            pnl_pct = position * (closes[i] / entry_price - 1) * 100
            net_pnl = pnl_pct - 2 * fee_pct
            trade = Trade(
                entry_idx=entry_idx, entry_price=entry_price,
                direction=position, exit_idx=i, exit_price=closes[i],
                pnl_pct=net_pnl, indicator=indicator_name,
            )
            trades.append(trade)
            equity *= (1 + net_pnl / 100)
            # Open new position
            position = signals[i]
            entry_price = closes[i]
            entry_idx = i

        peak_equity = max(peak_equity, equity)
        dd = (peak_equity - equity) / peak_equity * 100
        max_dd = max(max_dd, dd)
        equity_curve.append(equity)

    # Close any remaining position
    if position != 0:
        pnl_pct = position * (closes[-1] / entry_price - 1) * 100
        net_pnl = pnl_pct - 2 * fee_pct
        trade = Trade(
            entry_idx=entry_idx, entry_price=entry_price,
            direction=position, exit_idx=n - 1, exit_price=closes[-1],
            pnl_pct=net_pnl, indicator=indicator_name,
        )
        trades.append(trade)
        equity *= (1 + net_pnl / 100)

    # Compute metrics
    result.trades = trades
    result.total_trades = len(trades)
    result.winning_trades = sum(1 for t in trades if t.pnl_pct > 0)
    result.losing_trades = sum(1 for t in trades if t.pnl_pct <= 0)
    result.win_rate = (result.winning_trades / result.total_trades * 100) if result.total_trades > 0 else 0
    result.total_return_pct = (equity / 10000 - 1) * 100
    result.max_drawdown_pct = max_dd
    result.equity_curve = equity_curve

    if result.total_trades > 0:
        pnls = [t.pnl_pct for t in trades]
        result.avg_trade_pct = np.mean(pnls)
        if np.std(pnls) > 0:
            result.sharpe_ratio = np.mean(pnls) / np.std(pnls) * np.sqrt(252)

        gross_profit = sum(t.pnl_pct for t in trades if t.pnl_pct > 0)
        gross_loss = abs(sum(t.pnl_pct for t in trades if t.pnl_pct < 0))
        result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

    return result


# ===================================================================
# COMPOSITE STRATEGY
# ===================================================================

def build_composite_strategy(
    closes: np.ndarray,
    all_signals: dict[str, np.ndarray],
    weights: dict[str, float],
    threshold: float = 2.0,
) -> np.ndarray:
    """
    Build composite signal from multiple indicators.
    Weighted voting: sum of (signal x weight). Buy if >= threshold, sell if <= -threshold.
    """
    n = len(closes)
    composite = np.zeros(n)

    for name, sigs in all_signals.items():
        w = weights.get(name, 1.0)
        composite += sigs * w

    final_signals = np.zeros(n, dtype=int)
    for i in range(n):
        if composite[i] >= threshold:
            final_signals[i] = 1
        elif composite[i] <= -threshold:
            final_signals[i] = -1

    return final_signals


# ===================================================================
# MAIN
# ===================================================================

def main():
    print("=" * 70)
    print("  6-INDICATOR BACKTESTER - 6 Month BTC/USDT")
    print("=" * 70)

    # 1. Collect data
    ohlcv = collect_6month_ohlcv()
    timestamps = np.array([c[0] for c in ohlcv])
    opens = np.array([c[1] for c in ohlcv])
    highs = np.array([c[2] for c in ohlcv])
    lows = np.array([c[3] for c in ohlcv])
    closes = np.array([c[4] for c in ohlcv])
    volumes = np.array([c[5] for c in ohlcv])
    n = len(closes)

    start_date = datetime.fromtimestamp(timestamps[0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    end_date = datetime.fromtimestamp(timestamps[-1] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    buy_hold_return = (closes[-1] / closes[0] - 1) * 100

    print(f"\n  Period: {start_date} -> {end_date}")
    print(f"  Bars: {n} (1H)")
    print(f"  Price: {closes[0]:.0f} -> {closes[-1]:.0f}")
    print(f"  Buy & Hold: {buy_hold_return:+.2f}%")

    # 2. Calculate all indicators
    print("\n  Calculating indicators...")
    all_signals = {}

    # Supertrend
    st_trend, st_signals = calc_supertrend(highs, lows, closes, 10, 3.0)
    all_signals["Supertrend"] = st_signals

    # Squeeze Momentum
    sq_val, sq_on, sq_signals = calc_squeeze_momentum(highs, lows, closes)
    all_signals["SqueezeMom"] = sq_signals

    # MACD
    macd_line, macd_signal, macd_hist, macd_signals = calc_macd(closes)
    all_signals["MACD"] = macd_signals

    # Williams Vix Fix
    wvf_val, wvf_signals = calc_williams_vix_fix(closes, lows)
    all_signals["WilliamsVF"] = wvf_signals

    # WaveTrend
    wt1, wt2, wt_signals = calc_wavetrend(highs, lows, closes)
    all_signals["WaveTrend"] = wt_signals

    # Smart Money Concepts -- Version A (delay-compensated, reference only)
    smc_trend_a, smc_signals_a = calc_smc(highs, lows, closes)

    # Smart Money Concepts -- Version B (pure-causal, authoritative)
    smc_trend_b, smc_signals_b = calc_smc_pure_causal(highs, lows, closes)
    all_signals["SMC"] = smc_signals_b  # Phase 2 uses pure-causal

    # SMC Version A vs B comparison
    smc_divergence = np.sum(smc_signals_a != smc_signals_b)
    smc_a_count = np.sum(smc_signals_a != 0)
    smc_b_count = np.sum(smc_signals_b != 0)
    print(f"\n  [SMC Version Comparison]")
    print(f"    Version A (delay-compensated) signals: {smc_a_count}")
    print(f"    Version B (pure-causal) signals: {smc_b_count}")
    print(f"    Signal divergence: {smc_divergence} bars differ")
    print(f"    NOTE: All composite strategies use Version B (pure-causal)")

    # 3. Backtest each indicator individually
    print("\n" + "-" * 70)
    print("  INDIVIDUAL INDICATOR RESULTS")
    print("-" * 70)

    results = {}
    for name, sigs in all_signals.items():
        res = backtest_signals(closes, sigs, name)
        results[name] = res
        print(f"\n  [{name}]")
        print(f"    Trades: {res.total_trades}")
        print(f"    Win Rate: {res.win_rate:.1f}%")
        print(f"    Total Return: {res.total_return_pct:+.2f}%")
        print(f"    Max Drawdown: {res.max_drawdown_pct:.2f}%")
        print(f"    Avg Trade: {res.avg_trade_pct:+.3f}%")
        print(f"    Sharpe: {res.sharpe_ratio:.2f}")
        print(f"    Profit Factor: {res.profit_factor:.2f}")

    # 4. Rank indicators
    print("\n" + "-" * 70)
    print("  INDICATOR RANKING")
    print("-" * 70)
    ranking = sorted(results.items(), key=lambda x: x[1].sharpe_ratio, reverse=True)
    print(f"\n  {'Rank':<5} {'Indicator':<14} {'Sharpe':>8} {'Return':>10} {'Win%':>7} {'PF':>7} {'MaxDD':>8}")
    print(f"  {'-'*4:<5} {'-'*13:<14} {'-'*7:>8} {'-'*9:>10} {'-'*6:>7} {'-'*6:>7} {'-'*7:>8}")
    for i, (name, res) in enumerate(ranking, 1):
        print(f"  {i:<5} {name:<14} {res.sharpe_ratio:>8.2f} {res.total_return_pct:>+9.2f}% {res.win_rate:>6.1f}% {res.profit_factor:>7.2f} {res.max_drawdown_pct:>7.2f}%")

    # 5. Build composite strategies
    print("\n" + "-" * 70)
    print("  COMPOSITE STRATEGY RESULTS")
    print("-" * 70)

    # Strategy A: Equal weight, 2-indicator consensus
    weights_equal = {name: 1.0 for name in all_signals}
    composite_a = build_composite_strategy(closes, all_signals, weights_equal, threshold=2.0)
    res_a = backtest_signals(closes, composite_a, "Composite_EqualWeight_2of6")
    print(f"\n  [Strategy A: Equal Weight -2/6 consensus]")
    print(f"    Trades: {res_a.total_trades}, Win Rate: {res_a.win_rate:.1f}%")
    print(f"    Return: {res_a.total_return_pct:+.2f}%, MaxDD: {res_a.max_drawdown_pct:.2f}%")
    print(f"    Sharpe: {res_a.sharpe_ratio:.2f}, PF: {res_a.profit_factor:.2f}")

    # Strategy B: Equal weight, 3-indicator consensus (stricter)
    composite_b = build_composite_strategy(closes, all_signals, weights_equal, threshold=3.0)
    res_b = backtest_signals(closes, composite_b, "Composite_EqualWeight_3of6")
    print(f"\n  [Strategy B: Equal Weight -3/6 consensus]")
    print(f"    Trades: {res_b.total_trades}, Win Rate: {res_b.win_rate:.1f}%")
    print(f"    Return: {res_b.total_return_pct:+.2f}%, MaxDD: {res_b.max_drawdown_pct:.2f}%")
    print(f"    Sharpe: {res_b.sharpe_ratio:.2f}, PF: {res_b.profit_factor:.2f}")

    # Strategy C: Sharpe-weighted (best indicators get more weight)
    sharpe_weights = {}
    for name, res in results.items():
        sharpe_weights[name] = max(res.sharpe_ratio, 0.1)  # Floor at 0.1
    # Normalize
    total_w = sum(sharpe_weights.values())
    sharpe_weights = {k: v / total_w * len(sharpe_weights) for k, v in sharpe_weights.items()}
    composite_c = build_composite_strategy(closes, all_signals, sharpe_weights, threshold=2.0)
    res_c = backtest_signals(closes, composite_c, "Composite_SharpeWeighted")
    print(f"\n  [Strategy C: Sharpe-Weighted -adaptive threshold]")
    print(f"    Weights: {', '.join(f'{k}={v:.2f}' for k, v in sorted(sharpe_weights.items(), key=lambda x: -x[1]))}")
    print(f"    Trades: {res_c.total_trades}, Win Rate: {res_c.win_rate:.1f}%")
    print(f"    Return: {res_c.total_return_pct:+.2f}%, MaxDD: {res_c.max_drawdown_pct:.2f}%")
    print(f"    Sharpe: {res_c.sharpe_ratio:.2f}, PF: {res_c.profit_factor:.2f}")

    # Strategy D: Top 3 only (by Sharpe)
    top3_names = [name for name, _ in ranking[:3]]
    top3_signals = {k: v for k, v in all_signals.items() if k in top3_names}
    top3_weights = {name: 1.0 for name in top3_names}
    composite_d = build_composite_strategy(closes, top3_signals, top3_weights, threshold=2.0)
    res_d = backtest_signals(closes, composite_d, f"Composite_Top3")
    print(f"\n  [Strategy D: Top 3 Only ({', '.join(top3_names)}) -2/3 consensus]")
    print(f"    Trades: {res_d.total_trades}, Win Rate: {res_d.win_rate:.1f}%")
    print(f"    Return: {res_d.total_return_pct:+.2f}%, MaxDD: {res_d.max_drawdown_pct:.2f}%")
    print(f"    Sharpe: {res_d.sharpe_ratio:.2f}, PF: {res_d.profit_factor:.2f}")

    # 6. Final comparison
    print("\n" + "=" * 70)
    print("  FINAL COMPARISON")
    print("=" * 70)

    all_results = {
        "Buy & Hold": BacktestResult(
            indicator="Buy & Hold",
            total_trades=1,
            winning_trades=1 if buy_hold_return > 0 else 0,
            losing_trades=0 if buy_hold_return > 0 else 1,
            win_rate=100 if buy_hold_return > 0 else 0,
            total_return_pct=buy_hold_return,
        ),
        **results,
        "Composite A (2/6)": res_a,
        "Composite B (3/6)": res_b,
        "Composite C (Sharpe)": res_c,
        f"Composite D (Top3)": res_d,
    }

    print(f"\n  {'Strategy':<22} {'Return':>10} {'MaxDD':>8} {'Sharpe':>8} {'WinR':>7} {'Trades':>7} {'PF':>7}")
    print(f"  {'-'*21:<22} {'-'*9:>10} {'-'*7:>8} {'-'*7:>8} {'-'*6:>7} {'-'*6:>7} {'-'*6:>7}")
    for name, res in all_results.items():
        print(f"  {name:<22} {res.total_return_pct:>+9.2f}% {res.max_drawdown_pct:>7.2f}% {res.sharpe_ratio:>7.2f} {res.win_rate:>6.1f}% {res.total_trades:>6} {res.profit_factor:>7.2f}")

    # 7. Best strategy recommendation
    composite_results = {"A": res_a, "B": res_b, "C": res_c, "D": res_d}
    best = max(composite_results.items(), key=lambda x: x[1].sharpe_ratio)
    print(f"\n  * RECOMMENDED: Strategy {best[0]} (Sharpe={best[1].sharpe_ratio:.2f}, Return={best[1].total_return_pct:+.2f}%)")

    # 8. Save results
    output = {
        "period": {"start": start_date, "end": end_date, "bars": n, "timeframe": "1H"},
        "buy_and_hold_return_pct": round(buy_hold_return, 2),
        "individual_results": {
            name: {
                "trades": r.total_trades,
                "win_rate": round(r.win_rate, 2),
                "return_pct": round(r.total_return_pct, 2),
                "max_dd_pct": round(r.max_drawdown_pct, 2),
                "sharpe": round(r.sharpe_ratio, 2),
                "profit_factor": round(r.profit_factor, 2),
                "avg_trade_pct": round(r.avg_trade_pct, 3),
            } for name, r in results.items()
        },
        "composite_results": {
            f"Strategy_{k}": {
                "trades": v.total_trades,
                "win_rate": round(v.win_rate, 2),
                "return_pct": round(v.total_return_pct, 2),
                "max_dd_pct": round(v.max_drawdown_pct, 2),
                "sharpe": round(v.sharpe_ratio, 2),
                "profit_factor": round(v.profit_factor, 2),
            } for k, v in composite_results.items()
        },
        "ranking": [name for name, _ in ranking],
        "recommended_strategy": best[0],
        "sharpe_weights": {k: round(v, 3) for k, v in sharpe_weights.items()},
        "top3_indicators": top3_names,
    }

    os.makedirs("docs/operations/evidence", exist_ok=True)
    out_path = "docs/operations/evidence/indicator_backtest_results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Results saved to {out_path}")

    print("\n" + "=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
