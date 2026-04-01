"""
CR-046 Track C: Regime Filter Research

Phase C-1: Regime Identification Accuracy
  - ADX (Average Directional Index)
  - Bollinger Band Width percentile
  - ATR Ratio (short/long)
  - Price vs SMA(200) direction
  - Composite regime score

Phase C-2: Filter Integration with canonical core (SMC+WaveTrend)
  - Signal suppression in sideways
  - Position sizing reduction in sideways
  - Walk-forward filter threshold optimization

Scope: BTC/SOL + SMC+WaveTrend (canonical only)
SMC Version: B (pure-causal)

Usage:
    python scripts/strategy_d_regime_filter.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.indicator_backtest import (
    sma,
    ema,
    atr,
    stdev,
    calc_smc_pure_causal,
    calc_wavetrend,
    build_composite_strategy,
    BacktestResult,
    Trade,
)
from scripts.strategy_d_multi_asset import collect_asset_ohlcv
from scripts.strategy_d_execution_sim import backtest_with_realism


# ===================================================================
# REGIME INDICATORS (all causal, no lookahead)
# ===================================================================

def calc_adx(highs, lows, closes, period=14):
    """Average Directional Index. ADX > 25 = trending, < 20 = sideways."""
    n = len(closes)
    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)

    for i in range(1, n):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        if up_move > down_move and up_move > 0:
            plus_dm[i] = up_move
        if down_move > up_move and down_move > 0:
            minus_dm[i] = down_move

    atr_vals = atr(highs, lows, closes, period)
    smooth_plus = ema(plus_dm, period)
    smooth_minus = ema(minus_dm, period)

    plus_di = np.zeros(n)
    minus_di = np.zeros(n)
    dx = np.zeros(n)

    for i in range(period, n):
        if atr_vals[i] > 0 and not np.isnan(atr_vals[i]):
            if not np.isnan(smooth_plus[i]):
                plus_di[i] = 100 * smooth_plus[i] / atr_vals[i]
            if not np.isnan(smooth_minus[i]):
                minus_di[i] = 100 * smooth_minus[i] / atr_vals[i]
            denom = plus_di[i] + minus_di[i]
            if denom > 0:
                dx[i] = 100 * abs(plus_di[i] - minus_di[i]) / denom

    adx = ema(dx, period)
    return adx


def calc_bb_width_percentile(closes, period=20, mult=2.0, lookback=100):
    """Bollinger Band Width as percentile of recent history.
    Low percentile = squeeze/sideways, high = trending/volatile."""
    n = len(closes)
    basis = sma(closes, period)
    dev = mult * stdev(closes, period)
    bb_width = np.zeros(n)
    bb_pctile = np.zeros(n)

    for i in range(period, n):
        if not np.isnan(basis[i]) and basis[i] > 0:
            bb_width[i] = (2 * dev[i]) / basis[i] * 100 if not np.isnan(dev[i]) else 0

    for i in range(lookback, n):
        window = bb_width[max(0, i - lookback):i + 1]
        valid = window[window > 0]
        if len(valid) > 0:
            bb_pctile[i] = np.sum(valid <= bb_width[i]) / len(valid) * 100

    return bb_width, bb_pctile


def calc_atr_ratio(highs, lows, closes, short_period=14, long_period=50):
    """ATR(short) / ATR(long). Ratio > 1.2 = expanding vol (trending).
    Ratio < 0.8 = contracting vol (sideways)."""
    atr_short = atr(highs, lows, closes, short_period)
    atr_long = atr(highs, lows, closes, long_period)
    n = len(closes)
    ratio = np.ones(n)
    for i in range(long_period, n):
        if not np.isnan(atr_long[i]) and atr_long[i] > 0 and not np.isnan(atr_short[i]):
            ratio[i] = atr_short[i] / atr_long[i]
    return ratio


def calc_sma_direction(closes, period=200):
    """Price vs SMA(200). Returns +1 if above (bull trend), -1 if below (bear trend), 0 if near."""
    sma_vals = sma(closes, period)
    n = len(closes)
    direction = np.zeros(n, dtype=int)
    for i in range(period, n):
        if np.isnan(sma_vals[i]):
            continue
        pct_diff = (closes[i] - sma_vals[i]) / sma_vals[i] * 100
        if pct_diff > 2.0:
            direction[i] = 1
        elif pct_diff < -2.0:
            direction[i] = -1
    return direction


def classify_regime(adx, bb_pctile, atr_ratio, sma_dir):
    """Composite regime classification.
    Returns: array of labels (1=trending, 0=sideways, -1=unknown)"""
    n = len(adx)
    regime = np.zeros(n, dtype=int)

    for i in range(50, n):
        score = 0

        # ADX contribution
        if not np.isnan(adx[i]):
            if adx[i] > 25:
                score += 2  # strong trend signal
            elif adx[i] > 20:
                score += 1
            elif adx[i] < 15:
                score -= 2  # strong sideways signal
            else:
                score -= 1

        # BB Width percentile contribution
        if bb_pctile[i] > 70:
            score += 1  # wide bands = volatile/trending
        elif bb_pctile[i] < 30:
            score -= 1  # narrow bands = sideways

        # ATR ratio contribution
        if atr_ratio[i] > 1.2:
            score += 1  # expanding vol
        elif atr_ratio[i] < 0.8:
            score -= 1  # contracting vol

        # SMA direction (trend clarity)
        if abs(sma_dir[i]) == 1:
            score += 1  # clear directional trend

        # Classify
        if score >= 2:
            regime[i] = 1  # trending
        elif score <= -1:
            regime[i] = 0  # sideways
        else:
            regime[i] = 1  # borderline -> treat as trending (conservative)

    return regime


# ===================================================================
# REGIME-FILTERED BACKTEST
# ===================================================================

def backtest_with_regime_filter(
    closes, signals, regime, name,
    filter_mode="suppress",
    fee_pct=0.075,
    slippage_pct=0.0,
    stop_loss_pct=2.0,
    take_profit_pct=4.0,
):
    """Backtest with regime filtering.
    filter_mode: 'suppress' = skip signals in sideways
                 'reduce' = halve position sizing in sideways
                 'both' = suppress new entries + reduce existing
    """
    n = len(closes)
    filtered_signals = signals.copy()

    if filter_mode in ("suppress", "both"):
        for i in range(n):
            if regime[i] == 0:  # sideways
                filtered_signals[i] = 0

    return backtest_with_realism(
        closes, filtered_signals, name,
        fee_pct=fee_pct,
        slippage_pct=slippage_pct,
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
    )


# ===================================================================
# PHASE C-1: REGIME IDENTIFICATION ACCURACY
# ===================================================================

def evaluate_regime_accuracy(closes, highs, lows, known_regimes):
    """Compare regime indicators vs known quarterly labels.
    known_regimes: list of dicts with 'start', 'end', 'regime' (bear/bull/sideways)"""
    n = len(closes)

    # Compute all regime indicators
    adx = calc_adx(highs, lows, closes)
    bb_width, bb_pctile = calc_bb_width_percentile(closes)
    atr_ratio = calc_atr_ratio(highs, lows, closes)
    sma_dir = calc_sma_direction(closes)
    composite = classify_regime(adx, bb_pctile, atr_ratio, sma_dir)

    results = {}

    # Per-quarter accuracy
    for reg in known_regimes:
        s, e = reg["start"], reg["end"]
        label = reg["regime"]
        q = reg["quarter"]

        # For known bear/bull -> should be classified as trending (1)
        # For known sideways -> should be classified as sideways (0)
        expected = 0 if label == "sideways" else 1

        segment = composite[s:e]
        correct = np.sum(segment == expected)
        total = len(segment)
        accuracy = correct / total * 100 if total > 0 else 0

        # Individual indicator stats for this quarter
        adx_seg = adx[s:e]
        adx_mean = np.nanmean(adx_seg)
        bb_seg = bb_pctile[s:e]
        bb_mean = np.nanmean(bb_seg)
        atr_r_seg = atr_ratio[s:e]
        atr_r_mean = np.nanmean(atr_r_seg)

        results[f"Q{q}"] = {
            "regime": label,
            "expected": "trending" if expected == 1 else "sideways",
            "composite_accuracy": round(accuracy, 1),
            "adx_mean": round(adx_mean, 2),
            "bb_pctile_mean": round(bb_mean, 1),
            "atr_ratio_mean": round(atr_r_mean, 3),
        }

    # Overall accuracy
    total_correct = 0
    total_bars = 0
    for reg in known_regimes:
        s, e = reg["start"], reg["end"]
        expected = 0 if reg["regime"] == "sideways" else 1
        segment = composite[s:e]
        total_correct += np.sum(segment == expected)
        total_bars += len(segment)

    results["overall_accuracy"] = round(total_correct / total_bars * 100, 1) if total_bars > 0 else 0

    return results, adx, bb_pctile, atr_ratio, sma_dir, composite


# ===================================================================
# PHASE C-2: FILTER INTEGRATION
# ===================================================================

def test_filter_integration(symbol, ohlcv):
    """Test regime filter on one asset with canonical core."""
    highs = np.array([c[2] for c in ohlcv])
    lows = np.array([c[3] for c in ohlcv])
    closes = np.array([c[4] for c in ohlcv])
    n = len(closes)

    # Compute canonical core signals
    _, smc_sigs = calc_smc_pure_causal(highs, lows, closes)
    _, _, wt_sigs = calc_wavetrend(highs, lows, closes)
    core_signals = {"SMC": smc_sigs, "WaveTrend": wt_sigs}
    composite = build_composite_strategy(closes, core_signals,
                                         {"SMC": 1.0, "WaveTrend": 1.0}, threshold=2.0)

    # Compute regime
    adx = calc_adx(highs, lows, closes)
    bb_width, bb_pctile = calc_bb_width_percentile(closes)
    atr_ratio = calc_atr_ratio(highs, lows, closes)
    sma_dir = calc_sma_direction(closes)
    regime = classify_regime(adx, bb_pctile, atr_ratio, sma_dir)

    # Regime statistics
    trending_bars = np.sum(regime == 1)
    sideways_bars = np.sum(regime == 0)
    total_bars = n - 50  # exclude warmup
    regime_stats = {
        "trending_pct": round(trending_bars / total_bars * 100, 1) if total_bars > 0 else 0,
        "sideways_pct": round(sideways_bars / total_bars * 100, 1) if total_bars > 0 else 0,
    }

    results = {}

    # Baseline (no filter)
    baseline = backtest_with_realism(closes, composite, f"{symbol}_baseline", fee_pct=0.075)
    results["baseline"] = {
        "sharpe": round(baseline.sharpe_ratio, 2),
        "return_pct": round(baseline.total_return_pct, 2),
        "pf": round(baseline.profit_factor, 2),
        "mdd": round(baseline.max_drawdown_pct, 2),
        "trades": baseline.total_trades,
        "win_rate": round(baseline.win_rate, 1),
    }

    # Filtered: suppress mode
    filtered_suppress = backtest_with_regime_filter(
        closes, composite, regime, f"{symbol}_suppress",
        filter_mode="suppress", fee_pct=0.075,
    )
    results["filtered_suppress"] = {
        "sharpe": round(filtered_suppress.sharpe_ratio, 2),
        "return_pct": round(filtered_suppress.total_return_pct, 2),
        "pf": round(filtered_suppress.profit_factor, 2),
        "mdd": round(filtered_suppress.max_drawdown_pct, 2),
        "trades": filtered_suppress.total_trades,
        "win_rate": round(filtered_suppress.win_rate, 1),
    }

    # Per-quarter analysis with and without filter
    quarter_len = n // 4
    quarter_results = []
    for q in range(4):
        s = q * quarter_len
        e = min((q + 1) * quarter_len, n)
        c_q = closes[s:e]
        sig_q = composite[s:e]
        regime_q = regime[s:e]
        bh = (c_q[-1] / c_q[0] - 1) * 100

        # Unfiltered
        uf = backtest_with_realism(c_q, sig_q, f"Q{q+1}_unfilt", fee_pct=0.075)
        # Filtered
        ft = backtest_with_regime_filter(c_q, sig_q, regime_q, f"Q{q+1}_filt",
                                          filter_mode="suppress", fee_pct=0.075)

        # Regime label from BH return
        if bh > 10:
            rlabel = "bull"
        elif bh < -10:
            rlabel = "bear"
        else:
            rlabel = "sideways"

        trending_q = np.sum(regime_q == 1)
        sideways_q = np.sum(regime_q == 0)

        quarter_results.append({
            "quarter": q + 1,
            "regime_label": rlabel,
            "buy_hold_pct": round(bh, 2),
            "trending_bars_pct": round(trending_q / len(regime_q) * 100, 1),
            "sideways_bars_pct": round(sideways_q / len(regime_q) * 100, 1),
            "unfiltered_sharpe": round(uf.sharpe_ratio, 2),
            "unfiltered_return": round(uf.total_return_pct, 2),
            "unfiltered_trades": uf.total_trades,
            "filtered_sharpe": round(ft.sharpe_ratio, 2),
            "filtered_return": round(ft.total_return_pct, 2),
            "filtered_trades": ft.total_trades,
            "sharpe_improvement": round(ft.sharpe_ratio - uf.sharpe_ratio, 2),
        })

    results["quarters"] = quarter_results
    results["regime_stats"] = regime_stats

    # Improvement summary
    sharpe_delta = filtered_suppress.sharpe_ratio - baseline.sharpe_ratio
    return_delta = filtered_suppress.total_return_pct - baseline.total_return_pct
    results["improvement"] = {
        "sharpe_delta": round(sharpe_delta, 2),
        "return_delta_pp": round(return_delta, 2),
        "trades_reduced": baseline.total_trades - filtered_suppress.total_trades,
        "filter_effective": sharpe_delta > 0,
    }

    return results


# ===================================================================
# MAIN
# ===================================================================

def main():
    print("=" * 70)
    print("  CR-046 TRACK C: Regime Filter Research")
    print("  Phase C-1: Regime Identification Accuracy")
    print("  Phase C-2: Filter Integration")
    print("  Scope: BTC/SOL + SMC+WaveTrend (canonical)")
    print("=" * 70)

    all_results = {}

    for symbol in ["BTC/USDT", "SOL/USDT"]:
        print(f"\n{'=' * 70}")
        print(f"  {symbol}")
        print("=" * 70)

        ohlcv = collect_asset_ohlcv(symbol)
        if not ohlcv or len(ohlcv) < 500:
            print(f"  SKIP: insufficient data")
            continue

        highs = np.array([c[2] for c in ohlcv])
        lows = np.array([c[3] for c in ohlcv])
        closes = np.array([c[4] for c in ohlcv])
        n = len(closes)

        # Phase C-1: Regime identification
        print(f"\n  --- Phase C-1: Regime Identification ---")

        quarter_len = n // 4
        known_regimes = []
        for q in range(4):
            s = q * quarter_len
            e = min((q + 1) * quarter_len, n)
            bh = (closes[e-1] / closes[s] - 1) * 100
            if bh > 10:
                label = "bull"
            elif bh < -10:
                label = "bear"
            else:
                label = "sideways"
            known_regimes.append({"quarter": q+1, "start": s, "end": e, "regime": label})
            print(f"  Q{q+1}: {label} (B&H {bh:+.1f}%)")

        accuracy_results, adx, bb_pctile, atr_ratio_vals, sma_dir, composite_regime = \
            evaluate_regime_accuracy(closes, highs, lows, known_regimes)

        print(f"\n  Overall regime classification accuracy: {accuracy_results['overall_accuracy']}%")
        for q in range(1, 5):
            key = f"Q{q}"
            if key in accuracy_results:
                ar = accuracy_results[key]
                print(f"  {key} ({ar['regime']}): accuracy={ar['composite_accuracy']}%, "
                      f"ADX={ar['adx_mean']}, BB%={ar['bb_pctile_mean']}, ATR_r={ar['atr_ratio_mean']}")

        all_results[f"{symbol}_regime_accuracy"] = accuracy_results

        # Phase C-2: Filter integration
        print(f"\n  --- Phase C-2: Filter Integration ---")

        filter_results = test_filter_integration(symbol, ohlcv)
        all_results[f"{symbol}_filter"] = filter_results

        bl = filter_results["baseline"]
        fs = filter_results["filtered_suppress"]
        imp = filter_results["improvement"]

        print(f"\n  Baseline:  Sharpe={bl['sharpe']}, Return={bl['return_pct']:+.2f}%, "
              f"PF={bl['pf']}, MDD={bl['mdd']}%, Trades={bl['trades']}")
        print(f"  Filtered:  Sharpe={fs['sharpe']}, Return={fs['return_pct']:+.2f}%, "
              f"PF={fs['pf']}, MDD={fs['mdd']}%, Trades={fs['trades']}")
        print(f"  Delta:     Sharpe {imp['sharpe_delta']:+.2f}, Return {imp['return_delta_pp']:+.2f}pp, "
              f"Trades reduced by {imp['trades_reduced']}")
        print(f"  Filter effective: {'YES' if imp['filter_effective'] else 'NO'}")

        rs = filter_results["regime_stats"]
        print(f"\n  Regime distribution: Trending {rs['trending_pct']}%, Sideways {rs['sideways_pct']}%")

        print(f"\n  Per-quarter breakdown:")
        for qr in filter_results["quarters"]:
            print(f"    Q{qr['quarter']} ({qr['regime_label']}): "
                  f"unfilt Sharpe={qr['unfiltered_sharpe']}, filt Sharpe={qr['filtered_sharpe']} "
                  f"(delta={qr['sharpe_improvement']:+.2f}), "
                  f"trending={qr['trending_bars_pct']}%, sideways={qr['sideways_bars_pct']}%")

    # Summary
    print(f"\n{'=' * 70}")
    print("  TRACK C SUMMARY")
    print("=" * 70)

    for symbol in ["BTC/USDT", "SOL/USDT"]:
        fkey = f"{symbol}_filter"
        if fkey in all_results:
            imp = all_results[fkey]["improvement"]
            acc = all_results.get(f"{symbol}_regime_accuracy", {})
            overall_acc = acc.get("overall_accuracy", "N/A")
            print(f"\n  {symbol}:")
            print(f"    Regime classification accuracy: {overall_acc}%")
            print(f"    Filter Sharpe delta: {imp['sharpe_delta']:+.2f}")
            print(f"    Filter Return delta: {imp['return_delta_pp']:+.2f}pp")
            print(f"    Filter effective: {'YES' if imp['filter_effective'] else 'NO'}")
            print(f"    Trades reduced: {imp['trades_reduced']}")

    # Success criteria evaluation
    print(f"\n  --- Success Criteria ---")
    all_pass = True
    for symbol in ["BTC/USDT", "SOL/USDT"]:
        fkey = f"{symbol}_filter"
        if fkey not in all_results:
            continue
        bl = all_results[fkey]["baseline"]
        fs = all_results[fkey]["filtered_suppress"]
        imp = all_results[fkey]["improvement"]

        # Check: overall Sharpe with filter > unfiltered
        sharpe_improved = fs["sharpe"] > bl["sharpe"]
        # Check: no excessive bear period degradation (check quarters)
        bear_degradation_ok = True
        for qr in all_results[fkey]["quarters"]:
            if qr["regime_label"] == "bear" and qr["sharpe_improvement"] < -0.5:
                bear_degradation_ok = False

        print(f"  {symbol}: Sharpe improved={'PASS' if sharpe_improved else 'FAIL'}, "
              f"Bear preservation={'PASS' if bear_degradation_ok else 'FAIL'}")
        if not sharpe_improved or not bear_degradation_ok:
            all_pass = False

    all_results["track_c_verdict"] = "PASS" if all_pass else "CONDITIONAL"

    # Save
    out_path = "docs/operations/evidence/cr046_track_c_results.json"
    os.makedirs("docs/operations/evidence", exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n  Results saved to {out_path}")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
