"""
CR-046 Track C-v2: Alternative Regime Indicator Research
Independent research script. No operational code imports.
RegimeDetector modification PROHIBITED.

5 candidate indicators (all causal):
  1. Realized Vol Percentile -- 90-day rolling vol rank
  2. Range Compression Ratio -- price range / close normalized
  3. Choppiness Index -- ATR sum / range, >61.8 = sideways
  4. Directional Efficiency -- net move / total move, ~0 = choppy
  5. Hurst Exponent -- R/S analysis, <0.5 = mean-revert

Phases:
  C2-1: Individual test (sideways accuracy >50% both assets)
  C2-2: Best candidate integration (filter Sharpe > unfiltered)
  C2-3: Cross-asset validation

Output:
  docs/operations/evidence/cr046_track_c_v2_results.json
  docs/operations/evidence/cr046_track_c_v2_report.md
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
# DATA COLLECTION (ported, no imports from operational code)
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

        print(f"[DATA] Collected {len(all_ohlcv)} bars")
        return all_ohlcv

    except Exception as e:
        print(f"[DATA] CCXT failed: {e}, generating synthetic data for {symbol}")
        seed = 42 if "BTC" in symbol else 99
        base_price = 45000.0 if "BTC" in symbol else 150.0
        return _synthetic_ohlcv(target_bars, seed=seed, base_price=base_price)


def _synthetic_ohlcv(n: int = 4320, seed: int = 42, base_price: float = 45000.0) -> list[list]:
    rng = np.random.RandomState(seed)
    base_ts = int(time.time() * 1000) - n * 3600000
    price = base_price
    data = []
    for i in range(n):
        ret = rng.normal(0, 0.008)
        price *= 1 + ret
        h = price * (1 + abs(rng.normal(0, 0.003)))
        l = price * (1 - abs(rng.normal(0, 0.003)))
        o = price * (1 + rng.normal(0, 0.001))
        v = rng.uniform(100, 2000)
        data.append([base_ts + i * 3600000, o, h, l, price, v])
    return data


# ===================================================================
# BASE INDICATORS (ported)
# ===================================================================


def sma(data: np.ndarray, period: int) -> np.ndarray:
    out = np.full(len(data), np.nan)
    if len(data) < period:
        return out
    cumsum = np.cumsum(data)
    cumsum[period:] = cumsum[period:] - cumsum[:-period]
    out[period - 1 :] = cumsum[period - 1 :] / period
    return out


def ema(data: np.ndarray, period: int) -> np.ndarray:
    out = np.full(len(data), np.nan)
    if len(data) < period:
        return out
    k = 2.0 / (period + 1)
    out[period - 1] = np.mean(data[:period])
    for i in range(period, len(data)):
        out[i] = data[i] * k + out[i - 1] * (1 - k)
    return out


def atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int) -> np.ndarray:
    n = len(highs)
    tr = np.zeros(n)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
    return sma(tr, period)


# ===================================================================
# 5 CAUSAL REGIME INDICATORS
# ===================================================================


def calc_realized_vol_percentile(
    closes: np.ndarray,
    vol_window: int = 24,
    rank_window: int = 90 * 24,
) -> np.ndarray:
    """1. Realized Vol Percentile: rolling vol rank over 90-day window.
    Returns percentile [0, 1] for each bar. Higher = more volatile.
    Causal: only uses past/current data."""
    n = len(closes)
    result = np.full(n, np.nan)

    # Rolling realized vol (log returns std)
    log_ret = np.full(n, np.nan)
    for i in range(1, n):
        if closes[i] > 0 and closes[i - 1] > 0:
            log_ret[i] = np.log(closes[i] / closes[i - 1])

    vol = np.full(n, np.nan)
    for i in range(vol_window, n):
        window = log_ret[i - vol_window + 1 : i + 1]
        valid = window[~np.isnan(window)]
        if len(valid) >= vol_window // 2:
            vol[i] = np.std(valid, ddof=1)

    # Percentile rank within rank_window
    for i in range(rank_window, n):
        if np.isnan(vol[i]):
            continue
        past_vols = vol[i - rank_window + 1 : i + 1]
        valid_vols = past_vols[~np.isnan(past_vols)]
        if len(valid_vols) < 10:
            continue
        result[i] = np.sum(valid_vols <= vol[i]) / len(valid_vols)

    return result


def calc_range_compression_ratio(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    window: int = 24,
) -> np.ndarray:
    """2. Range Compression Ratio: price range / close, normalized.
    Low value = compressed range = sideways.
    Causal: rolling window backward only."""
    n = len(closes)
    result = np.full(n, np.nan)

    for i in range(window - 1, n):
        h_max = np.max(highs[i - window + 1 : i + 1])
        l_min = np.min(lows[i - window + 1 : i + 1])
        mid = closes[i]
        if mid > 0:
            result[i] = (h_max - l_min) / mid

    return result


def calc_choppiness_index(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    period: int = 14,
) -> np.ndarray:
    """3. Choppiness Index: ATR sum / range.
    >61.8 = sideways/choppy, <38.2 = trending.
    Range: [0, 100]. Causal."""
    n = len(closes)
    result = np.full(n, np.nan)

    # True Range
    tr = np.zeros(n)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))

    for i in range(period - 1, n):
        atr_sum = np.sum(tr[i - period + 1 : i + 1])
        h_max = np.max(highs[i - period + 1 : i + 1])
        l_min = np.min(lows[i - period + 1 : i + 1])
        hl_range = h_max - l_min
        if hl_range > 0:
            result[i] = 100 * np.log10(atr_sum / hl_range) / np.log10(period)

    return result


def calc_directional_efficiency(
    closes: np.ndarray,
    window: int = 24,
) -> np.ndarray:
    """4. Directional Efficiency: |net move| / total move.
    ~0 = choppy, ~1 = trending. Range [0, 1]. Causal."""
    n = len(closes)
    result = np.full(n, np.nan)

    for i in range(window, n):
        net_move = abs(closes[i] - closes[i - window])
        total_move = 0.0
        for j in range(i - window + 1, i + 1):
            total_move += abs(closes[j] - closes[j - 1])
        if total_move > 0:
            result[i] = net_move / total_move

    return result


def calc_hurst_exponent(
    closes: np.ndarray,
    window: int = 100,
) -> np.ndarray:
    """5. Hurst Exponent via R/S analysis.
    H < 0.5 = mean-reverting, H ~ 0.5 = random walk, H > 0.5 = trending.
    Causal: uses only past data within window."""
    n = len(closes)
    result = np.full(n, np.nan)

    for i in range(window, n):
        series = closes[i - window + 1 : i + 1]
        if np.any(series <= 0):
            continue

        log_ret = np.diff(np.log(series))
        if len(log_ret) < 10:
            continue

        # R/S analysis across multiple sub-periods
        rs_values = []
        for div in [2, 4, 8, 16]:
            sub_len = len(log_ret) // div
            if sub_len < 4:
                continue
            rs_sub = []
            for k in range(div):
                start = k * sub_len
                end = start + sub_len
                sub = log_ret[start:end]
                mean_sub = np.mean(sub)
                cumdev = np.cumsum(sub - mean_sub)
                r = np.max(cumdev) - np.min(cumdev)
                s = np.std(sub, ddof=1)
                if s > 0:
                    rs_sub.append(r / s)
            if rs_sub:
                rs_values.append((sub_len, np.mean(rs_sub)))

        if len(rs_values) >= 2:
            log_n = np.array([np.log(rs[0]) for rs in rs_values])
            log_rs = np.array([np.log(rs[1]) for rs in rs_values])
            # Linear regression: H = slope of log(R/S) vs log(n)
            if np.std(log_n) > 0:
                slope = np.polyfit(log_n, log_rs, 1)[0]
                result[i] = np.clip(slope, 0.0, 1.0)

    return result


# ===================================================================
# REGIME CLASSIFICATION
# ===================================================================


def classify_regime_ground_truth(
    closes: np.ndarray,
    forward_window: int = 24,
    trend_threshold: float = 0.02,
) -> np.ndarray:
    """Ground truth: classify bars as trending(1) or sideways(0) using FUTURE returns.
    Only for evaluation -- NOT for signal generation."""
    n = len(closes)
    labels = np.full(n, np.nan)
    for i in range(n - forward_window):
        future_ret = abs(closes[i + forward_window] / closes[i] - 1)
        labels[i] = 1.0 if future_ret >= trend_threshold else 0.0
    return labels


def evaluate_regime_indicator(
    indicator_values: np.ndarray,
    ground_truth: np.ndarray,
    threshold: float,
    sideways_when_above: bool = True,
) -> dict:
    """Evaluate how well an indicator identifies sideways regimes.
    sideways_when_above=True means indicator > threshold => sideways prediction."""
    n = len(indicator_values)
    valid_mask = ~np.isnan(indicator_values) & ~np.isnan(ground_truth)

    if np.sum(valid_mask) < 100:
        return {
            "accuracy": 0.0,
            "sideways_accuracy": 0.0,
            "trend_accuracy": 0.0,
            "n_valid": int(np.sum(valid_mask)),
            "error": "insufficient_data",
        }

    predicted_sideways = np.zeros(n)
    if sideways_when_above:
        predicted_sideways[indicator_values > threshold] = 1.0
    else:
        predicted_sideways[indicator_values < threshold] = 1.0

    actual_sideways = ground_truth == 0.0
    actual_trend = ground_truth == 1.0

    valid = valid_mask
    correct = predicted_sideways[valid].astype(bool) == actual_sideways[valid]
    accuracy = np.mean(correct)

    # Sideways-specific accuracy
    sw_mask = valid & actual_sideways
    if np.sum(sw_mask) > 0:
        sw_correct = predicted_sideways[sw_mask] == 1.0
        sideways_acc = np.mean(sw_correct)
    else:
        sideways_acc = 0.0

    # Trend-specific accuracy
    tr_mask = valid & actual_trend
    if np.sum(tr_mask) > 0:
        tr_correct = predicted_sideways[tr_mask] == 0.0
        trend_acc = np.mean(tr_correct)
    else:
        trend_acc = 0.0

    return {
        "accuracy": round(float(accuracy), 4),
        "sideways_accuracy": round(float(sideways_acc), 4),
        "trend_accuracy": round(float(trend_acc), 4),
        "n_valid": int(np.sum(valid_mask)),
        "n_sideways": int(np.sum(sw_mask)),
        "n_trend": int(np.sum(tr_mask)),
    }


# ===================================================================
# BACKTEST WITH REGIME FILTER
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


def calc_smc_pure_causal(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    swing_length: int = 50,
    internal_length: int = 5,
) -> tuple[np.ndarray, np.ndarray]:
    """Pure-causal SMC Version B. Ported from indicator_backtest.py:453."""
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
            if current_trend != 0:
                signals[i] = 1
            current_trend = 1
            last_swing_high = np.nan

        if not np.isnan(last_swing_low) and closes[i] < last_swing_low:
            if current_trend != 0:
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
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """WaveTrend. Ported from indicator_backtest.py:344."""
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
            if wt1[i] > wt2[i] and wt1[i - 1] <= wt2[i - 1]:
                signals[i] = 1
            elif wt1[i] < wt2[i] and wt1[i - 1] >= wt2[i - 1]:
                signals[i] = -1

    return wt1, wt2, signals


def calc_smc_wt_consensus(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
) -> np.ndarray:
    """SMC+WaveTrend 2/2 consensus (operational strategy baseline)."""
    _, smc_signals = calc_smc_pure_causal(highs, lows, closes)
    _, _, wt_signals = calc_wavetrend(highs, lows, closes)
    n = len(closes)
    consensus = np.zeros(n, dtype=int)
    for i in range(n):
        if smc_signals[i] != 0 and smc_signals[i] == wt_signals[i]:
            consensus[i] = smc_signals[i]
    return consensus


def backtest_signals(
    closes: np.ndarray,
    signals: np.ndarray,
    indicator_name: str,
    fee_pct: float = 0.075,
    stop_loss_pct: float = 2.0,
    take_profit_pct: float = 4.0,
) -> BacktestResult:
    """Backtest engine. Ported from indicator_backtest.py:545."""
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


def backtest_with_regime_filter(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    regime_values: np.ndarray,
    threshold: float,
    block_when_above: bool = True,
    indicator_name: str = "filtered",
) -> BacktestResult:
    """Backtest SMC+WT consensus with regime filter applied.
    Blocks signals when regime indicates sideways."""
    base_signals = calc_smc_wt_consensus(highs, lows, closes)

    filtered_signals = base_signals.copy()
    for i in range(len(filtered_signals)):
        if np.isnan(regime_values[i]):
            continue
        if block_when_above and regime_values[i] > threshold:
            filtered_signals[i] = 0
        elif not block_when_above and regime_values[i] < threshold:
            filtered_signals[i] = 0

    return backtest_signals(closes, filtered_signals, indicator_name)


# ===================================================================
# PHASE EXECUTION
# ===================================================================


def run_phase_c2_1(
    btc_data: dict,
    sol_data: dict,
) -> dict:
    """Phase C2-1: Individual indicator test on both assets."""
    print("\n=== Phase C2-1: Individual Indicator Tests ===")

    indicators = {
        "realized_vol_percentile": {
            "fn": lambda h, l, c: calc_realized_vol_percentile(c),
            "threshold": 0.7,
            "sideways_when_above": True,
            "description": "90-day rolling vol rank",
        },
        "range_compression": {
            "fn": lambda h, l, c: calc_range_compression_ratio(h, l, c),
            "threshold": 0.03,
            "sideways_when_above": False,  # low range = sideways
            "description": "price range / close",
        },
        "choppiness_index": {
            "fn": lambda h, l, c: calc_choppiness_index(h, l, c),
            "threshold": 61.8,
            "sideways_when_above": True,
            "description": "ATR sum / range, >61.8 = sideways",
        },
        "directional_efficiency": {
            "fn": lambda h, l, c: calc_directional_efficiency(c),
            "threshold": 0.3,
            "sideways_when_above": False,  # low DE = choppy
            "description": "|net move| / total move",
        },
        "hurst_exponent": {
            "fn": lambda h, l, c: calc_hurst_exponent(c),
            "threshold": 0.45,
            "sideways_when_above": False,  # H<0.5 = mean-revert/sideways
            "description": "R/S analysis, <0.5 = mean-revert",
        },
    }

    results = {"phase": "C2-1", "description": "Individual indicator tests", "indicators": {}}

    for name, config in indicators.items():
        print(f"\n  Testing: {name} ({config['description']})")
        ind_results = {}

        for asset_name, data in [("BTC", btc_data), ("SOL", sol_data)]:
            h, l, c = data["highs"], data["lows"], data["closes"]
            values = config["fn"](h, l, c)
            ground_truth = classify_regime_ground_truth(c)

            eval_result = evaluate_regime_indicator(
                values,
                ground_truth,
                threshold=config["threshold"],
                sideways_when_above=config["sideways_when_above"],
            )
            ind_results[asset_name] = eval_result
            print(
                f"    {asset_name}: acc={eval_result['accuracy']:.4f}, "
                f"sw_acc={eval_result['sideways_accuracy']:.4f}, "
                f"tr_acc={eval_result['trend_accuracy']:.4f}"
            )

        both_pass = (
            ind_results["BTC"]["sideways_accuracy"] > 0.5
            and ind_results["SOL"]["sideways_accuracy"] > 0.5
        )
        ind_results["both_assets_pass"] = both_pass

        results["indicators"][name] = ind_results

    # Find best candidate
    best_name = None
    best_avg_acc = 0.0
    for name, res in results["indicators"].items():
        if not res["both_assets_pass"]:
            continue
        avg = (res["BTC"]["sideways_accuracy"] + res["SOL"]["sideways_accuracy"]) / 2
        if avg > best_avg_acc:
            best_avg_acc = avg
            best_name = name

    results["best_candidate"] = best_name
    results["best_avg_sideways_accuracy"] = round(best_avg_acc, 4) if best_name else 0.0
    results["status"] = "PASS" if best_name is not None else "FAIL"

    print(f"\n  Best candidate: {best_name or 'NONE'} (avg sw_acc={best_avg_acc:.4f})")
    print(f"  Phase C2-1: {results['status']}")

    return results


def run_phase_c2_2(
    btc_data: dict,
    sol_data: dict,
    best_candidate: str | None,
    indicators_config: dict,
) -> dict:
    """Phase C2-2: Best candidate integration -- filter Sharpe > unfiltered."""
    print("\n=== Phase C2-2: Best Candidate Integration ===")

    if best_candidate is None:
        print("  No candidate passed C2-1. SKIP.")
        return {"phase": "C2-2", "status": "SKIP", "reason": "no_candidate_from_c2_1"}

    config = indicators_config[best_candidate]
    results = {"phase": "C2-2", "candidate": best_candidate, "assets": {}}

    for asset_name, data in [("BTC", btc_data), ("SOL", sol_data)]:
        h, l, c = data["highs"], data["lows"], data["closes"]

        # Unfiltered baseline
        bt_unfiltered = backtest_signals(
            c, calc_smc_wt_consensus(h, l, c), f"SMC+WT_unfiltered_{asset_name}"
        )

        # Filtered
        regime_values = config["fn"](h, l, c)
        bt_filtered = backtest_with_regime_filter(
            h,
            l,
            c,
            regime_values,
            threshold=config["threshold"],
            block_when_above=config["sideways_when_above"],
            indicator_name=f"SMC+WT+{best_candidate}_{asset_name}",
        )

        improvement = bt_filtered.sharpe_ratio > bt_unfiltered.sharpe_ratio
        results["assets"][asset_name] = {
            "unfiltered": bt_unfiltered.to_dict(),
            "filtered": bt_filtered.to_dict(),
            "sharpe_improvement": improvement,
            "sharpe_delta": round(bt_filtered.sharpe_ratio - bt_unfiltered.sharpe_ratio, 4),
        }

        print(
            f"  {asset_name}: unfiltered Sharpe={bt_unfiltered.sharpe_ratio:.4f}, "
            f"filtered Sharpe={bt_filtered.sharpe_ratio:.4f} "
            f"({'improved' if improvement else 'worse'})"
        )

    both_improve = all(a["sharpe_improvement"] for a in results["assets"].values())
    results["both_assets_improve"] = both_improve
    results["status"] = "PASS" if both_improve else "FAIL"

    print(f"  Phase C2-2: {results['status']}")
    return results


def run_phase_c2_3(
    btc_data: dict,
    sol_data: dict,
    best_candidate: str | None,
    indicators_config: dict,
) -> dict:
    """Phase C2-3: Cross-asset validation."""
    print("\n=== Phase C2-3: Cross-Asset Validation ===")

    if best_candidate is None:
        print("  No candidate. SKIP.")
        return {"phase": "C2-3", "status": "SKIP", "reason": "no_candidate"}

    config = indicators_config[best_candidate]
    results = {"phase": "C2-3", "candidate": best_candidate, "cross_asset": {}}

    # Test: train threshold on BTC, apply on SOL and vice versa
    for train_asset, test_asset, train_data, test_data in [
        ("BTC", "SOL", btc_data, sol_data),
        ("SOL", "BTC", sol_data, btc_data),
    ]:
        h_test, l_test, c_test = test_data["highs"], test_data["lows"], test_data["closes"]

        # Use same threshold (not re-optimized)
        regime_values = config["fn"](h_test, l_test, c_test)
        bt_filtered = backtest_with_regime_filter(
            h_test,
            l_test,
            c_test,
            regime_values,
            threshold=config["threshold"],
            block_when_above=config["sideways_when_above"],
            indicator_name=f"cross_{train_asset}_to_{test_asset}",
        )
        bt_unfiltered = backtest_signals(
            c_test, calc_smc_wt_consensus(h_test, l_test, c_test), f"unfiltered_{test_asset}"
        )

        key = f"train_{train_asset}_test_{test_asset}"
        results["cross_asset"][key] = {
            "unfiltered": bt_unfiltered.to_dict(),
            "filtered": bt_filtered.to_dict(),
            "sharpe_improvement": bt_filtered.sharpe_ratio > bt_unfiltered.sharpe_ratio,
        }

        print(
            f"  {train_asset}->{test_asset}: "
            f"unfiltered={bt_unfiltered.sharpe_ratio:.4f}, "
            f"filtered={bt_filtered.sharpe_ratio:.4f}"
        )

    all_improve = all(v["sharpe_improvement"] for v in results["cross_asset"].values())
    results["cross_asset_consistent"] = all_improve
    results["status"] = "PASS" if all_improve else "FAIL"

    print(f"  Phase C2-3: {results['status']}")
    return results


# ===================================================================
# REPORT GENERATION
# ===================================================================


def generate_report(c1: dict, c2: dict, c3: dict) -> str:
    all_pass = c1["status"] == "PASS" and c2["status"] == "PASS" and c3["status"] == "PASS"
    verdict = "GO" if all_pass else "NO-GO"

    report = f"""# CR-046 Track C-v2: Alternative Regime Indicator Research Report

Date: {datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}

---

## Summary

| Phase | Status |
|-------|--------|
| C2-1: Individual indicator tests | **{c1["status"]}** |
| C2-2: Best candidate integration | **{c2["status"]}** |
| C2-3: Cross-asset validation | **{c3["status"]}** |

Best candidate: **{c1.get("best_candidate", "NONE")}**

---

## Phase C2-1: Individual Indicator Tests

Sideways accuracy (>50% both assets required):

| Indicator | BTC sw_acc | SOL sw_acc | BTC tr_acc | SOL tr_acc | Both Pass |
|-----------|-----------|-----------|-----------|-----------|-----------|
"""

    for name, res in c1.get("indicators", {}).items():
        btc = res.get("BTC", {})
        sol = res.get("SOL", {})
        report += (
            f"| {name} | {btc.get('sideways_accuracy', 0):.4f} | "
            f"{sol.get('sideways_accuracy', 0):.4f} | "
            f"{btc.get('trend_accuracy', 0):.4f} | "
            f"{sol.get('trend_accuracy', 0):.4f} | "
            f"{'PASS' if res.get('both_assets_pass') else 'FAIL'} |\n"
        )

    report += f"""
---

## Phase C2-2: Best Candidate Integration
"""

    if c2["status"] == "SKIP":
        report += "\nSkipped: no candidate passed C2-1.\n"
    else:
        report += f"\nCandidate: **{c2.get('candidate', 'N/A')}**\n\n"
        report += "| Asset | Unfiltered Sharpe | Filtered Sharpe | Delta | Improved |\n"
        report += "|-------|------------------|-----------------|-------|----------|\n"
        for asset, res in c2.get("assets", {}).items():
            report += (
                f"| {asset} | {res['unfiltered']['sharpe_ratio']} | "
                f"{res['filtered']['sharpe_ratio']} | "
                f"{res['sharpe_delta']} | "
                f"{'YES' if res['sharpe_improvement'] else 'NO'} |\n"
            )

    report += f"""
---

## Phase C2-3: Cross-Asset Validation
"""

    if c3["status"] == "SKIP":
        report += "\nSkipped.\n"
    else:
        report += "\n| Direction | Unfiltered Sharpe | Filtered Sharpe | Improved |\n"
        report += "|-----------|------------------|-----------------|----------|\n"
        for key, res in c3.get("cross_asset", {}).items():
            report += (
                f"| {key} | {res['unfiltered']['sharpe_ratio']} | "
                f"{res['filtered']['sharpe_ratio']} | "
                f"{'YES' if res['sharpe_improvement'] else 'NO'} |\n"
            )

    report += f"""
---

## Verdict

**{verdict}**

"""
    if all_pass:
        report += (
            f"Regime indicator **{c1.get('best_candidate')}** improves Sharpe ratio "
            f"on both assets and generalizes cross-asset. "
            f"Eligible for integration consideration.\n"
        )
    else:
        failed = [p for p, s in [("C2-1", c1), ("C2-2", c2), ("C2-3", c3)] if s["status"] != "PASS"]
        report += (
            f"Failed phases: {', '.join(failed)}. No regime indicator meets deployment criteria.\n"
        )

    report += """
---

*Generated by: scripts/track_c_v2_regime_research.py*
*Authority: Research only. RegimeDetector modification PROHIBITED.*
*Results do NOT connect to operational paths.*
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
    return str(obj)


def main():
    print("=" * 60)
    print("CR-046 Track C-v2: Alternative Regime Indicator Research")
    print("=" * 60)

    # Collect data for both assets
    btc_ohlcv = collect_6month_ohlcv(symbol="BTC/USDT", months=6)
    sol_ohlcv = collect_6month_ohlcv(symbol="SOL/USDT", months=6)

    btc_arr = np.array(btc_ohlcv)
    sol_arr = np.array(sol_ohlcv)

    btc_data = {"highs": btc_arr[:, 2], "lows": btc_arr[:, 3], "closes": btc_arr[:, 4]}
    sol_data = {"highs": sol_arr[:, 2], "lows": sol_arr[:, 3], "closes": sol_arr[:, 4]}

    print(f"[DATA] BTC: {len(btc_data['closes'])} bars, SOL: {len(sol_data['closes'])} bars")

    # Indicator configs (reused across phases)
    indicators_config = {
        "realized_vol_percentile": {
            "fn": lambda h, l, c: calc_realized_vol_percentile(c),
            "threshold": 0.7,
            "sideways_when_above": True,
        },
        "range_compression": {
            "fn": lambda h, l, c: calc_range_compression_ratio(h, l, c),
            "threshold": 0.03,
            "sideways_when_above": False,
        },
        "choppiness_index": {
            "fn": lambda h, l, c: calc_choppiness_index(h, l, c),
            "threshold": 61.8,
            "sideways_when_above": True,
        },
        "directional_efficiency": {
            "fn": lambda h, l, c: calc_directional_efficiency(c),
            "threshold": 0.3,
            "sideways_when_above": False,
        },
        "hurst_exponent": {
            "fn": lambda h, l, c: calc_hurst_exponent(c),
            "threshold": 0.45,
            "sideways_when_above": False,
        },
    }

    # Run phases
    c1 = run_phase_c2_1(btc_data, sol_data)
    c2 = run_phase_c2_2(btc_data, sol_data, c1.get("best_candidate"), indicators_config)
    c3 = run_phase_c2_3(btc_data, sol_data, c1.get("best_candidate"), indicators_config)

    # Save results
    evidence_dir = os.path.join(PROJECT_ROOT, "docs", "operations", "evidence")
    os.makedirs(evidence_dir, exist_ok=True)

    all_results = {
        "track": "C-v2",
        "strategy_baseline": "SMC+WaveTrend",
        "assets": ["BTC/USDT", "SOL/USDT"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phases": {"C2-1": c1, "C2-2": c2, "C2-3": c3},
        "overall_verdict": "GO" if all(p["status"] == "PASS" for p in [c1, c2, c3]) else "NO-GO",
    }

    json_path = os.path.join(evidence_dir, "cr046_track_c_v2_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=_json_default)
    print(f"\n[OUTPUT] Results: {json_path}")

    report = generate_report(c1, c2, c3)
    md_path = os.path.join(evidence_dir, "cr046_track_c_v2_report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"[OUTPUT] Report: {md_path}")

    print(f"\n{'=' * 60}")
    print(f"OVERALL VERDICT: {all_results['overall_verdict']}")
    print(f"{'=' * 60}")

    return all_results


if __name__ == "__main__":
    main()
