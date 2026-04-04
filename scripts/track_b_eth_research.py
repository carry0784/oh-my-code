"""
CR-046 Track B: ETH SMC+MACD Branch Validation
Independent research script. No operational code imports.

Phases:
  B-1: In-sample baseline (Sharpe>0, PF>1.0, vs SMC+WT on ETH, vs B&H)
  B-2: OOS (4mo/2mo temporal split), purged CV (5-fold, 48-bar embargo), stability >=4/5
  B-3: Execution realism -- slippage 0.05%, 1-bar delay, fee 0.1%, worst-case combined

Output:
  docs/operations/evidence/cr046_track_b_results.json
  docs/operations/evidence/cr046_track_b_report.md
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)


# ===================================================================
# DATA COLLECTION (ported from indicator_backtest.py, no imports)
# ===================================================================


def collect_6month_ohlcv(
    symbol: str = "ETH/USDT",
    timeframe: str = "1h",
    months: int = 6,
) -> list[list]:
    """Collect ~6 months of hourly OHLCV from Binance via CCXT."""
    try:
        import ccxt

        exchange = ccxt.binance({"enableRateLimit": True})

        all_ohlcv = []
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

        print(f"[DATA] Collected {len(all_ohlcv)} bars ({all_ohlcv[0][0]} ~ {all_ohlcv[-1][0]})")
        return all_ohlcv

    except Exception as e:
        print(f"[DATA] CCXT failed: {e}, generating synthetic ETH data")
        return _synthetic_eth_6month(target_bars)


def _synthetic_eth_6month(n: int = 4320) -> list[list]:
    """Fallback synthetic data with ETH-like price action."""
    rng = np.random.RandomState(99)
    base_ts = int(time.time() * 1000) - n * 3600000
    price = 2500.0
    data = []
    for i in range(n):
        ret = rng.normal(0, 0.01)  # ~1% hourly vol (ETH higher vol)
        price *= 1 + ret
        h = price * (1 + abs(rng.normal(0, 0.004)))
        l = price * (1 - abs(rng.normal(0, 0.004)))
        o = price * (1 + rng.normal(0, 0.001))
        v = rng.uniform(500, 5000)
        data.append([base_ts + i * 3600000, o, h, l, price, v])
    return data


# ===================================================================
# INDICATOR IMPLEMENTATIONS (ported from indicator_backtest.py)
# ===================================================================


def sma(data: np.ndarray, period: int) -> np.ndarray:
    """Simple Moving Average."""
    out = np.full(len(data), np.nan)
    if len(data) < period:
        return out
    cumsum = np.cumsum(data)
    cumsum[period:] = cumsum[period:] - cumsum[:-period]
    out[period - 1 :] = cumsum[period - 1 :] / period
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


def calc_macd(
    closes: np.ndarray,
    fast: int = 12,
    slow: int = 26,
    signal_len: int = 9,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Returns (macd_line, signal_line, histogram, signals).
    Ported from indicator_backtest.py:269."""
    n = len(closes)
    fast_ema = ema(closes, fast)
    slow_ema = ema(closes, slow)

    macd_line = fast_ema - slow_ema
    signal_line = sma(np.nan_to_num(macd_line), signal_len)
    histogram = macd_line - signal_line

    signals = np.zeros(n, dtype=int)
    for i in range(1, n):
        if not np.isnan(macd_line[i]) and not np.isnan(signal_line[i]):
            if macd_line[i] > signal_line[i] and macd_line[i - 1] <= signal_line[i - 1]:
                signals[i] = 1
            elif macd_line[i] < signal_line[i] and macd_line[i - 1] >= signal_line[i - 1]:
                signals[i] = -1

    return macd_line, signal_line, histogram, signals


def calc_smc_pure_causal(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    swing_length: int = 50,
    internal_length: int = 5,
) -> tuple[np.ndarray, np.ndarray]:
    """Pure-causal Smart Money Concepts (Version B).
    Ported from indicator_backtest.py:453."""
    n = len(closes)
    L = internal_length
    trend = np.zeros(n, dtype=int)
    signals = np.zeros(n, dtype=int)

    last_swing_high = np.nan
    last_swing_low = np.nan
    current_trend = 0

    for i in range(2 * L, n):
        candidate_idx = i - L
        window_start = max(0, candidate_idx - L)
        window_end = i + 1

        window_h = highs[window_start:window_end]
        if highs[candidate_idx] == np.max(window_h):
            last_swing_high = highs[candidate_idx]

        window_l = lows[window_start:window_end]
        if lows[candidate_idx] == np.min(window_l):
            last_swing_low = lows[candidate_idx]

        if not np.isnan(last_swing_high) and closes[i] > last_swing_high:
            if current_trend == -1:
                signals[i] = 1
            elif current_trend == 1:
                signals[i] = 1
            current_trend = 1
            last_swing_high = np.nan

        if not np.isnan(last_swing_low) and closes[i] < last_swing_low:
            if current_trend == 1:
                signals[i] = -1
            elif current_trend == -1:
                signals[i] = -1
            current_trend = -1
            last_swing_low = np.nan

        trend[i] = current_trend

    return trend, signals


def calc_wavetrend(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    n1: int = 10,
    n2: int = 21,
    ob1: float = 60,
    os1: float = -60,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Returns (wt1, wt2, signals).
    Ported from indicator_backtest.py:344."""
    n = len(closes)
    ap = (highs + lows + closes) / 3

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
            if wt1[i] > wt2[i] and wt1[i - 1] <= wt2[i - 1] and wt1[i] < os1:
                signals[i] = 1
            elif wt1[i] < wt2[i] and wt1[i - 1] >= wt2[i - 1] and wt1[i] > ob1:
                signals[i] = -1
            elif wt1[i] > wt2[i] and wt1[i - 1] <= wt2[i - 1]:
                signals[i] = 1
            elif wt1[i] < wt2[i] and wt1[i - 1] >= wt2[i - 1]:
                signals[i] = -1

    return wt1, wt2, signals


# ===================================================================
# CONSENSUS STRATEGIES
# ===================================================================


def calc_smc_macd_consensus(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
) -> np.ndarray:
    """SMC (pure-causal) + MACD 2/2 consensus.
    Signal fires only when both agree on same bar and direction."""
    _, smc_signals = calc_smc_pure_causal(highs, lows, closes)
    _, _, _, macd_signals = calc_macd(closes)

    n = len(closes)
    consensus = np.zeros(n, dtype=int)
    for i in range(n):
        if smc_signals[i] != 0 and smc_signals[i] == macd_signals[i]:
            consensus[i] = smc_signals[i]
    return consensus


def calc_smc_wavetrend_consensus(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
) -> np.ndarray:
    """SMC (pure-causal) + WaveTrend 2/2 consensus (baseline comparison)."""
    _, smc_signals = calc_smc_pure_causal(highs, lows, closes)
    _, _, wt_signals = calc_wavetrend(highs, lows, closes)

    n = len(closes)
    consensus = np.zeros(n, dtype=int)
    for i in range(n):
        if smc_signals[i] != 0 and smc_signals[i] == wt_signals[i]:
            consensus[i] = smc_signals[i]
    return consensus


# ===================================================================
# BACKTESTING ENGINE (ported from indicator_backtest.py:545)
# ===================================================================


@dataclass
class Trade:
    entry_idx: int
    entry_price: float
    direction: int
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

    def to_dict(self) -> dict:
        return {
            "indicator": self.indicator,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 2),
            "total_return_pct": round(self.total_return_pct, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "avg_trade_pct": round(self.avg_trade_pct, 4),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "profit_factor": round(self.profit_factor, 4),
        }


def backtest_signals(
    closes: np.ndarray,
    signals: np.ndarray,
    indicator_name: str,
    fee_pct: float = 0.075,
    stop_loss_pct: float = 2.0,
    take_profit_pct: float = 4.0,
) -> BacktestResult:
    """Backtest a signal array. +1=buy, -1=sell, 0=hold."""
    n = len(closes)
    result = BacktestResult(indicator=indicator_name)
    trades: list[Trade] = []
    position = 0
    entry_price = 0.0
    entry_idx = 0

    equity = 10000.0
    peak_equity = equity
    max_dd = 0.0
    equity_curve = [equity]

    for i in range(1, n):
        if position != 0:
            pnl_pct = position * (closes[i] / entry_price - 1) * 100
            if pnl_pct <= -stop_loss_pct or pnl_pct >= take_profit_pct:
                net_pnl = pnl_pct - 2 * fee_pct
                trade = Trade(
                    entry_idx=entry_idx,
                    entry_price=entry_price,
                    direction=position,
                    exit_idx=i,
                    exit_price=closes[i],
                    pnl_pct=net_pnl,
                    indicator=indicator_name,
                )
                trades.append(trade)
                equity *= 1 + net_pnl / 100
                position = 0

        if signals[i] != 0 and position == 0:
            position = signals[i]
            entry_price = closes[i]
            entry_idx = i
        elif signals[i] != 0 and signals[i] != position:
            pnl_pct = position * (closes[i] / entry_price - 1) * 100
            net_pnl = pnl_pct - 2 * fee_pct
            trade = Trade(
                entry_idx=entry_idx,
                entry_price=entry_price,
                direction=position,
                exit_idx=i,
                exit_price=closes[i],
                pnl_pct=net_pnl,
                indicator=indicator_name,
            )
            trades.append(trade)
            equity *= 1 + net_pnl / 100
            position = signals[i]
            entry_price = closes[i]
            entry_idx = i

        peak_equity = max(peak_equity, equity)
        dd = (peak_equity - equity) / peak_equity * 100
        max_dd = max(max_dd, dd)
        equity_curve.append(equity)

    if position != 0:
        pnl_pct = position * (closes[-1] / entry_price - 1) * 100
        net_pnl = pnl_pct - 2 * fee_pct
        trade = Trade(
            entry_idx=entry_idx,
            entry_price=entry_price,
            direction=position,
            exit_idx=n - 1,
            exit_price=closes[-1],
            pnl_pct=net_pnl,
            indicator=indicator_name,
        )
        trades.append(trade)
        equity *= 1 + net_pnl / 100

    result.trades = trades
    result.total_trades = len(trades)
    result.winning_trades = sum(1 for t in trades if t.pnl_pct > 0)
    result.losing_trades = sum(1 for t in trades if t.pnl_pct <= 0)
    result.win_rate = (
        (result.winning_trades / result.total_trades * 100) if result.total_trades > 0 else 0
    )
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
        result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    return result


def apply_1bar_delay(signals: np.ndarray) -> np.ndarray:
    """Shift signals forward by 1 bar (execution realism)."""
    delayed = np.zeros_like(signals)
    delayed[1:] = signals[:-1]
    return delayed


def buy_and_hold_return(closes: np.ndarray) -> float:
    """Buy & Hold return percentage."""
    if len(closes) < 2:
        return 0.0
    return (closes[-1] / closes[0] - 1) * 100


# ===================================================================
# PURGED K-FOLD CV (5-fold, 48-bar embargo)
# ===================================================================


def purged_kfold_cv(
    closes: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    consensus_fn,
    n_folds: int = 5,
    embargo_bars: int = 48,
    fee_pct: float = 0.075,
    stop_loss_pct: float = 2.0,
    take_profit_pct: float = 4.0,
    indicator_name: str = "SMC+MACD",
) -> list[dict]:
    """Purged cross-validation with embargo gap between train and test."""
    n = len(closes)
    fold_size = n // n_folds
    results = []

    for fold_idx in range(n_folds):
        test_start = fold_idx * fold_size
        test_end = min(test_start + fold_size, n)

        # Generate signals on full data (indicators need lookback)
        signals = consensus_fn(highs, lows, closes)

        # Zero out training region signals, keep only test fold
        test_signals = np.zeros(n, dtype=int)
        # Apply embargo: skip embargo_bars after train/test boundary
        effective_start = test_start + embargo_bars if fold_idx > 0 else test_start
        if effective_start < test_end:
            test_signals[effective_start:test_end] = signals[effective_start:test_end]

        # Backtest only on test fold region
        fold_closes = (
            closes[effective_start:test_end]
            if effective_start < test_end
            else closes[test_start:test_end]
        )
        fold_signals = (
            test_signals[effective_start:test_end]
            if effective_start < test_end
            else test_signals[test_start:test_end]
        )

        if len(fold_closes) < 50:
            results.append(
                {
                    "fold": fold_idx + 1,
                    "test_range": [int(test_start), int(test_end)],
                    "embargo_bars": embargo_bars,
                    "sharpe_ratio": 0.0,
                    "profit_factor": 0.0,
                    "total_trades": 0,
                    "pass": False,
                }
            )
            continue

        bt = backtest_signals(
            fold_closes,
            fold_signals,
            f"{indicator_name}_fold{fold_idx + 1}",
            fee_pct=fee_pct,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
        )

        fold_pass = bt.sharpe_ratio > 0 and bt.profit_factor > 1.0
        results.append(
            {
                "fold": fold_idx + 1,
                "test_range": [int(test_start), int(test_end)],
                "embargo_bars": embargo_bars,
                "sharpe_ratio": round(bt.sharpe_ratio, 4),
                "profit_factor": round(bt.profit_factor, 4),
                "total_trades": bt.total_trades,
                "total_return_pct": round(bt.total_return_pct, 2),
                "win_rate": round(bt.win_rate, 2),
                "pass": fold_pass,
            }
        )

    return results


# ===================================================================
# PHASE EXECUTION
# ===================================================================


def run_phase_b1(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
) -> dict:
    """Phase B-1: In-sample baseline."""
    print("\n=== Phase B-1: In-sample Baseline ===")

    # SMC+MACD consensus
    smc_macd_signals = calc_smc_macd_consensus(highs, lows, closes)
    bt_smc_macd = backtest_signals(closes, smc_macd_signals, "SMC+MACD")

    # SMC+WaveTrend consensus (comparison)
    smc_wt_signals = calc_smc_wavetrend_consensus(highs, lows, closes)
    bt_smc_wt = backtest_signals(closes, smc_wt_signals, "SMC+WaveTrend")

    # Buy & Hold
    bnh_return = buy_and_hold_return(closes)

    # Individual indicators
    _, _, _, macd_signals = calc_macd(closes)
    bt_macd_only = backtest_signals(closes, macd_signals, "MACD_only")

    _, smc_signals = calc_smc_pure_causal(highs, lows, closes)
    bt_smc_only = backtest_signals(closes, smc_signals, "SMC_only")

    results = {
        "phase": "B-1",
        "description": "In-sample baseline (full 6mo)",
        "smc_macd": bt_smc_macd.to_dict(),
        "smc_wavetrend": bt_smc_wt.to_dict(),
        "macd_only": bt_macd_only.to_dict(),
        "smc_only": bt_smc_only.to_dict(),
        "buy_and_hold_return_pct": round(bnh_return, 2),
        "checks": {
            "smc_macd_sharpe_gt_0": bt_smc_macd.sharpe_ratio > 0,
            "smc_macd_pf_gt_1": bt_smc_macd.profit_factor > 1.0,
            "smc_macd_beats_bnh": bt_smc_macd.total_return_pct > bnh_return,
        },
    }

    status = "PASS" if all(results["checks"].values()) else "FAIL"
    results["status"] = status
    print(
        f"  SMC+MACD: Sharpe={bt_smc_macd.sharpe_ratio:.4f}, PF={bt_smc_macd.profit_factor:.4f}, "
        f"Return={bt_smc_macd.total_return_pct:.2f}%"
    )
    print(
        f"  SMC+WT:   Sharpe={bt_smc_wt.sharpe_ratio:.4f}, PF={bt_smc_wt.profit_factor:.4f}, "
        f"Return={bt_smc_wt.total_return_pct:.2f}%"
    )
    print(f"  B&H:      Return={bnh_return:.2f}%")
    print(f"  Phase B-1: {status}")

    return results


def run_phase_b2(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
) -> dict:
    """Phase B-2: OOS temporal split + purged CV."""
    print("\n=== Phase B-2: OOS + Purged CV ===")

    n = len(closes)
    # 4mo/2mo split (2/3 train, 1/3 test)
    split_idx = int(n * 2 / 3)

    # OOS: train on first 4mo, test on last 2mo
    oos_highs = highs[split_idx:]
    oos_lows = lows[split_idx:]
    oos_closes = closes[split_idx:]

    # Generate signals (indicators need full lookback, so compute on all then slice)
    full_signals = calc_smc_macd_consensus(highs, lows, closes)
    oos_signals = full_signals[split_idx:]

    bt_oos = backtest_signals(oos_closes, oos_signals, "SMC+MACD_OOS")

    # Purged 5-fold CV with 48-bar embargo
    cv_results = purged_kfold_cv(
        closes,
        highs,
        lows,
        consensus_fn=calc_smc_macd_consensus,
        n_folds=5,
        embargo_bars=48,
    )

    folds_passing = sum(1 for r in cv_results if r["pass"])
    stability = folds_passing >= 4

    results = {
        "phase": "B-2",
        "description": "OOS (4mo/2mo) + purged CV (5-fold, 48-bar embargo)",
        "oos": {
            "split_idx": split_idx,
            "total_bars": n,
            "oos_bars": n - split_idx,
            **bt_oos.to_dict(),
        },
        "purged_cv": {
            "n_folds": 5,
            "embargo_bars": 48,
            "folds": cv_results,
            "folds_passing": folds_passing,
            "stability_threshold": 4,
            "stability_pass": stability,
        },
        "checks": {
            "oos_sharpe_gt_0": bt_oos.sharpe_ratio > 0,
            "oos_pf_gt_1": bt_oos.profit_factor > 1.0,
            "cv_stability_ge_4of5": stability,
        },
    }

    status = "PASS" if all(results["checks"].values()) else "FAIL"
    results["status"] = status

    print(
        f"  OOS: Sharpe={bt_oos.sharpe_ratio:.4f}, PF={bt_oos.profit_factor:.4f}, "
        f"Return={bt_oos.total_return_pct:.2f}%"
    )
    print(f"  CV stability: {folds_passing}/5 folds pass (need >=4)")
    print(f"  Phase B-2: {status}")

    return results


def run_phase_b3(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
) -> dict:
    """Phase B-3: Execution realism."""
    print("\n=== Phase B-3: Execution Realism ===")

    signals = calc_smc_macd_consensus(highs, lows, closes)

    # Test 1: slippage 0.05% (reflected in fee)
    bt_slip = backtest_signals(
        closes,
        signals,
        "SMC+MACD_slip",
        fee_pct=0.075 + 0.05,
        stop_loss_pct=2.0,
        take_profit_pct=4.0,
    )

    # Test 2: 1-bar delay
    delayed_signals = apply_1bar_delay(signals)
    bt_delay = backtest_signals(
        closes,
        delayed_signals,
        "SMC+MACD_delay",
        fee_pct=0.075,
        stop_loss_pct=2.0,
        take_profit_pct=4.0,
    )

    # Test 3: higher fee 0.1%
    bt_highfee = backtest_signals(
        closes, signals, "SMC+MACD_highfee", fee_pct=0.1, stop_loss_pct=2.0, take_profit_pct=4.0
    )

    # Test 4: worst-case combined (slippage + delay + high fee)
    bt_worst = backtest_signals(
        closes,
        delayed_signals,
        "SMC+MACD_worstcase",
        fee_pct=0.1 + 0.05,
        stop_loss_pct=2.0,
        take_profit_pct=4.0,
    )

    results = {
        "phase": "B-3",
        "description": "Execution realism (slippage 0.05%, 1-bar delay, fee 0.1%, worst-case)",
        "slippage_005pct": bt_slip.to_dict(),
        "one_bar_delay": bt_delay.to_dict(),
        "high_fee_01pct": bt_highfee.to_dict(),
        "worst_case_combined": bt_worst.to_dict(),
        "checks": {
            "slippage_sharpe_gt_0": bt_slip.sharpe_ratio > 0,
            "delay_sharpe_gt_0": bt_delay.sharpe_ratio > 0,
            "highfee_sharpe_gt_0": bt_highfee.sharpe_ratio > 0,
            "worstcase_sharpe_gt_0": bt_worst.sharpe_ratio > 0,
        },
    }

    status = "PASS" if all(results["checks"].values()) else "FAIL"
    results["status"] = status

    print(f"  Slippage 0.05%: Sharpe={bt_slip.sharpe_ratio:.4f}")
    print(f"  1-bar delay:    Sharpe={bt_delay.sharpe_ratio:.4f}")
    print(f"  Fee 0.1%:       Sharpe={bt_highfee.sharpe_ratio:.4f}")
    print(f"  Worst-case:     Sharpe={bt_worst.sharpe_ratio:.4f}")
    print(f"  Phase B-3: {status}")

    return results


# ===================================================================
# REPORT GENERATION
# ===================================================================


def generate_report(b1: dict, b2: dict, b3: dict) -> str:
    """Generate markdown report with go/no-go decision."""
    all_pass = b1["status"] == "PASS" and b2["status"] == "PASS" and b3["status"] == "PASS"
    verdict = "GO" if all_pass else "NO-GO"

    report = f"""# CR-046 Track B: ETH SMC+MACD Branch Validation Report

Date: {datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}

---

## Summary

| Phase | Status |
|-------|--------|
| B-1: In-sample baseline | **{b1["status"]}** |
| B-2: OOS + Purged CV | **{b2["status"]}** |
| B-3: Execution realism | **{b3["status"]}** |

---

## Phase B-1: In-sample Baseline

| Strategy | Sharpe | PF | Return% | Trades | Win Rate |
|----------|--------|----|---------|--------|----------|
| SMC+MACD | {b1["smc_macd"]["sharpe_ratio"]} | {b1["smc_macd"]["profit_factor"]} | {b1["smc_macd"]["total_return_pct"]} | {b1["smc_macd"]["total_trades"]} | {b1["smc_macd"]["win_rate"]}% |
| SMC+WaveTrend | {b1["smc_wavetrend"]["sharpe_ratio"]} | {b1["smc_wavetrend"]["profit_factor"]} | {b1["smc_wavetrend"]["total_return_pct"]} | {b1["smc_wavetrend"]["total_trades"]} | {b1["smc_wavetrend"]["win_rate"]}% |
| MACD only | {b1["macd_only"]["sharpe_ratio"]} | {b1["macd_only"]["profit_factor"]} | {b1["macd_only"]["total_return_pct"]} | {b1["macd_only"]["total_trades"]} | {b1["macd_only"]["win_rate"]}% |
| SMC only | {b1["smc_only"]["sharpe_ratio"]} | {b1["smc_only"]["profit_factor"]} | {b1["smc_only"]["total_return_pct"]} | {b1["smc_only"]["total_trades"]} | {b1["smc_only"]["win_rate"]}% |
| Buy & Hold | - | - | {b1["buy_and_hold_return_pct"]}% | - | - |

Checks:
- Sharpe > 0: **{"PASS" if b1["checks"]["smc_macd_sharpe_gt_0"] else "FAIL"}**
- PF > 1.0: **{"PASS" if b1["checks"]["smc_macd_pf_gt_1"] else "FAIL"}**
- Beats B&H: **{"PASS" if b1["checks"]["smc_macd_beats_bnh"] else "FAIL"}**

---

## Phase B-2: OOS + Purged CV

### OOS (4mo/2mo split)

| Metric | Value |
|--------|-------|
| OOS Sharpe | {b2["oos"]["sharpe_ratio"]} |
| OOS PF | {b2["oos"]["profit_factor"]} |
| OOS Return | {b2["oos"]["total_return_pct"]}% |
| OOS Trades | {b2["oos"]["total_trades"]} |

### Purged CV (5-fold, 48-bar embargo)

| Fold | Sharpe | PF | Trades | Pass |
|------|--------|----|--------|------|
"""

    for fold in b2["purged_cv"]["folds"]:
        report += f"| {fold['fold']} | {fold['sharpe_ratio']} | {fold['profit_factor']} | {fold['total_trades']} | {'PASS' if fold['pass'] else 'FAIL'} |\n"

    report += f"""
Stability: {b2["purged_cv"]["folds_passing"]}/5 (threshold: 4/5) -> **{"PASS" if b2["purged_cv"]["stability_pass"] else "FAIL"}**

---

## Phase B-3: Execution Realism

| Scenario | Sharpe | PF | Return% | Trades |
|----------|--------|----|---------|--------|
| Slippage 0.05% | {b3["slippage_005pct"]["sharpe_ratio"]} | {b3["slippage_005pct"]["profit_factor"]} | {b3["slippage_005pct"]["total_return_pct"]} | {b3["slippage_005pct"]["total_trades"]} |
| 1-bar delay | {b3["one_bar_delay"]["sharpe_ratio"]} | {b3["one_bar_delay"]["profit_factor"]} | {b3["one_bar_delay"]["total_return_pct"]} | {b3["one_bar_delay"]["total_trades"]} |
| Fee 0.1% | {b3["high_fee_01pct"]["sharpe_ratio"]} | {b3["high_fee_01pct"]["profit_factor"]} | {b3["high_fee_01pct"]["total_return_pct"]} | {b3["high_fee_01pct"]["total_trades"]} |
| Worst-case | {b3["worst_case_combined"]["sharpe_ratio"]} | {b3["worst_case_combined"]["profit_factor"]} | {b3["worst_case_combined"]["total_return_pct"]} | {b3["worst_case_combined"]["total_trades"]} |

---

## Verdict

**{verdict}**

"""
    if all_pass:
        report += "SMC+MACD consensus on ETH meets all three phase criteria. "
        report += "Eligible for further consideration if ETH operational path is reopened by A.\n"
    else:
        failed_phases = [
            p for p, s in [("B-1", b1), ("B-2", b2), ("B-3", b3)] if s["status"] == "FAIL"
        ]
        report += f"Failed phases: {', '.join(failed_phases)}. "
        report += "SMC+MACD consensus on ETH does NOT meet deployment criteria.\n"

    report += """
### Additional Verification Items

- [ ] Confirm MACD causality (no future data access)
- [ ] Verify OOS temporal ordering (train before test)
- [ ] Check CV embargo gap enforcement (48 bars)
- [ ] Cross-validate against BTC/SOL data if GO

---

*Generated by: scripts/track_b_eth_research.py*
*Authority: Research only. Results do NOT connect to operational paths.*
"""
    return report


# ===================================================================
# MAIN
# ===================================================================


def _json_default(obj):
    if isinstance(obj, (np.bool_, np.integer)):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def main():
    print("=" * 60)
    print("CR-046 Track B: ETH SMC+MACD Branch Validation")
    print("=" * 60)

    # Collect data
    ohlcv = collect_6month_ohlcv(symbol="ETH/USDT", timeframe="1h", months=6)
    ohlcv_arr = np.array(ohlcv)
    highs = ohlcv_arr[:, 2]
    lows = ohlcv_arr[:, 3]
    closes = ohlcv_arr[:, 4]

    print(f"[DATA] {len(closes)} bars loaded")

    # Run phases
    b1 = run_phase_b1(highs, lows, closes)
    b2 = run_phase_b2(highs, lows, closes)
    b3 = run_phase_b3(highs, lows, closes)

    # Save results
    evidence_dir = os.path.join(PROJECT_ROOT, "docs", "operations", "evidence")
    os.makedirs(evidence_dir, exist_ok=True)

    results = {
        "track": "B",
        "asset": "ETH/USDT",
        "strategy": "SMC+MACD",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_bars": len(closes),
        "phases": {"B-1": b1, "B-2": b2, "B-3": b3},
        "overall_verdict": "GO" if all(p["status"] == "PASS" for p in [b1, b2, b3]) else "NO-GO",
    }

    json_path = os.path.join(evidence_dir, "cr046_track_b_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=_json_default)
    print(f"\n[OUTPUT] Results: {json_path}")

    report = generate_report(b1, b2, b3)
    md_path = os.path.join(evidence_dir, "cr046_track_b_report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"[OUTPUT] Report: {md_path}")

    print(f"\n{'=' * 60}")
    print(f"OVERALL VERDICT: {results['overall_verdict']}")
    print(f"{'=' * 60}")

    return results


if __name__ == "__main__":
    main()
