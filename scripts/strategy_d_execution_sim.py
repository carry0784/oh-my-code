"""
CR-046 Phase 4: Execution Realism Simulation

Scope: BTC/SOL + SMC+WaveTrend (canonical pairs only)
SMC Version: B (pure-causal, canonical)

Tests:
  4.1 Spread + slippage (0.05% per trade)
  4.2 Funding rate impact (-0.01% per 8h for shorts)
  4.3 Latency simulation (1-bar delay on entry)
  4.4 Realistic fee tier (0.1% taker, non-VIP Binance)

Usage:
    python scripts/strategy_d_execution_sim.py
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
    calc_smc_pure_causal,
    calc_wavetrend,
    build_composite_strategy,
    BacktestResult,
    Trade,
)
from scripts.strategy_d_multi_asset import collect_asset_ohlcv


def backtest_with_realism(
    closes: np.ndarray,
    signals: np.ndarray,
    name: str,
    fee_pct: float = 0.075,
    slippage_pct: float = 0.0,
    funding_rate_pct: float = 0.0,
    funding_interval_bars: int = 8,
    entry_delay: int = 0,
    stop_loss_pct: float = 2.0,
    take_profit_pct: float = 4.0,
) -> BacktestResult:
    """Backtest with execution realism parameters."""
    n = len(closes)
    result = BacktestResult(indicator=name)
    trades = []
    position = 0
    entry_price = 0.0
    entry_idx = 0
    equity = 100.0
    peak = 100.0
    max_dd = 0.0
    equity_curve = [100.0]
    bars_in_position = 0

    for i in range(1, n):
        if position != 0:
            bars_in_position += 1
            pnl_pct = position * (closes[i] / entry_price - 1) * 100

            # Funding rate for shorts
            if (
                position == -1
                and funding_rate_pct > 0
                and bars_in_position % funding_interval_bars == 0
            ):
                pnl_pct -= funding_rate_pct

            if pnl_pct <= -stop_loss_pct or pnl_pct >= take_profit_pct:
                exit_pnl = pnl_pct - fee_pct - slippage_pct
                equity *= 1 + exit_pnl / 100
                trades.append(
                    Trade(
                        entry_idx=entry_idx,
                        entry_price=entry_price,
                        direction=position,
                        exit_idx=i,
                        exit_price=closes[i],
                        pnl_pct=exit_pnl,
                        indicator=name,
                    )
                )
                position = 0
                bars_in_position = 0

            elif signals[i] != 0 and signals[i] != position:
                exit_pnl = pnl_pct - fee_pct - slippage_pct
                equity *= 1 + exit_pnl / 100
                trades.append(
                    Trade(
                        entry_idx=entry_idx,
                        entry_price=entry_price,
                        direction=position,
                        exit_idx=i,
                        exit_price=closes[i],
                        pnl_pct=exit_pnl,
                        indicator=name,
                    )
                )
                # Open reverse
                position = signals[i]
                delayed_i = min(i + entry_delay, n - 1)
                entry_price = closes[delayed_i]
                entry_idx = delayed_i
                equity *= 1 - fee_pct / 100 - slippage_pct / 100
                bars_in_position = 0

        elif signals[i] != 0 and position == 0:
            position = signals[i]
            delayed_i = min(i + entry_delay, n - 1)
            entry_price = closes[delayed_i]
            entry_idx = delayed_i
            equity *= 1 - fee_pct / 100 - slippage_pct / 100
            bars_in_position = 0

        peak = max(peak, equity)
        dd = (peak - equity) / peak * 100
        max_dd = max(max_dd, dd)
        equity_curve.append(equity)

    # Close remaining position
    if position != 0:
        pnl_pct = position * (closes[-1] / entry_price - 1) * 100 - fee_pct - slippage_pct
        equity *= 1 + pnl_pct / 100
        trades.append(
            Trade(
                entry_idx=entry_idx,
                entry_price=entry_price,
                direction=position,
                exit_idx=n - 1,
                exit_price=closes[-1],
                pnl_pct=pnl_pct,
                indicator=name,
            )
        )

    # Compute metrics
    result.total_trades = len(trades)
    result.trades = trades
    result.equity_curve = equity_curve
    result.total_return_pct = equity - 100.0
    result.max_drawdown_pct = max_dd

    if trades:
        wins = [t for t in trades if t.pnl_pct > 0]
        losses = [t for t in trades if t.pnl_pct <= 0]
        result.winning_trades = len(wins)
        result.losing_trades = len(losses)
        result.win_rate = len(wins) / len(trades) * 100
        result.avg_trade_pct = np.mean([t.pnl_pct for t in trades])
        gross_profit = sum(t.pnl_pct for t in wins) if wins else 0
        gross_loss = abs(sum(t.pnl_pct for t in losses)) if losses else 1
        result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        returns = [t.pnl_pct for t in trades]
        if len(returns) > 1 and np.std(returns) > 0:
            result.sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(len(returns))

    return result


def test_asset(symbol, ohlcv):
    """Run all Phase 4 tests on one asset."""
    highs = np.array([c[2] for c in ohlcv])
    lows = np.array([c[3] for c in ohlcv])
    closes = np.array([c[4] for c in ohlcv])

    # Compute canonical core signals
    _, smc_sigs = calc_smc_pure_causal(highs, lows, closes)
    _, _, wt_sigs = calc_wavetrend(highs, lows, closes)
    core_signals = {"SMC": smc_sigs, "WaveTrend": wt_sigs}
    composite = build_composite_strategy(
        closes, core_signals, {"SMC": 1.0, "WaveTrend": 1.0}, threshold=2.0
    )

    results = {}

    # Baseline (current settings)
    baseline = backtest_with_realism(closes, composite, f"{symbol}_baseline", fee_pct=0.075)
    results["baseline"] = {
        "sharpe": round(baseline.sharpe_ratio, 2),
        "return_pct": round(baseline.total_return_pct, 2),
        "pf": round(baseline.profit_factor, 2),
        "mdd": round(baseline.max_drawdown_pct, 2),
        "trades": baseline.total_trades,
    }

    # 4.1 Slippage
    slip = backtest_with_realism(
        closes, composite, f"{symbol}_slippage", fee_pct=0.075, slippage_pct=0.05
    )
    results["slippage"] = {
        "sharpe": round(slip.sharpe_ratio, 2),
        "return_pct": round(slip.total_return_pct, 2),
        "pf": round(slip.profit_factor, 2),
        "pass": slip.sharpe_ratio > 0.5,
    }

    # 4.2 Funding rate
    fund = backtest_with_realism(
        closes,
        composite,
        f"{symbol}_funding",
        fee_pct=0.075,
        funding_rate_pct=0.01,
        funding_interval_bars=8,
    )
    reduction = abs(baseline.total_return_pct - fund.total_return_pct)
    reduction_pct = (
        reduction / abs(baseline.total_return_pct) * 100 if baseline.total_return_pct != 0 else 0
    )
    results["funding"] = {
        "sharpe": round(fund.sharpe_ratio, 2),
        "return_pct": round(fund.total_return_pct, 2),
        "return_reduction_pct": round(reduction_pct, 1),
        "pass": reduction_pct < 30,
    }

    # 4.3 Latency (1-bar delay)
    latency = backtest_with_realism(
        closes, composite, f"{symbol}_latency", fee_pct=0.075, entry_delay=1
    )
    results["latency"] = {
        "sharpe": round(latency.sharpe_ratio, 2),
        "return_pct": round(latency.total_return_pct, 2),
        "pf": round(latency.profit_factor, 2),
        "pass": latency.sharpe_ratio > 0,
    }

    # 4.4 Realistic fee (0.1% taker)
    realfee = backtest_with_realism(closes, composite, f"{symbol}_realfee", fee_pct=0.1)
    results["realistic_fee"] = {
        "sharpe": round(realfee.sharpe_ratio, 2),
        "return_pct": round(realfee.total_return_pct, 2),
        "pf": round(realfee.profit_factor, 2),
        "pass": realfee.profit_factor > 1.0,
    }

    # Combined worst-case
    worst = backtest_with_realism(
        closes,
        composite,
        f"{symbol}_worst_case",
        fee_pct=0.1,
        slippage_pct=0.05,
        funding_rate_pct=0.01,
        entry_delay=1,
    )
    results["worst_case"] = {
        "sharpe": round(worst.sharpe_ratio, 2),
        "return_pct": round(worst.total_return_pct, 2),
        "pf": round(worst.profit_factor, 2),
        "mdd": round(worst.max_drawdown_pct, 2),
        "trades": worst.total_trades,
    }

    return results


def main():
    print("=" * 70)
    print("  CR-046 PHASE 4: Execution Realism Simulation")
    print("  Scope: BTC/SOL + SMC+WaveTrend (canonical only)")
    print("  SMC: Version B (pure-causal)")
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

        results = test_asset(symbol, ohlcv)
        all_results[symbol] = results

        bl = results["baseline"]
        print(
            f"\n  Baseline: Sharpe={bl['sharpe']}, Return={bl['return_pct']:+.2f}%, "
            f"PF={bl['pf']}, MDD={bl['mdd']}%, Trades={bl['trades']}"
        )

        for test_name in ["slippage", "funding", "latency", "realistic_fee"]:
            t = results[test_name]
            pass_str = "PASS" if t["pass"] else "FAIL"
            print(
                f"  4.{['slippage', 'funding', 'latency', 'realistic_fee'].index(test_name) + 1} "
                f"{test_name}: Sharpe={t['sharpe']}, Return={t['return_pct']:+.2f}% [{pass_str}]"
            )

        wc = results["worst_case"]
        print(
            f"  Worst-case: Sharpe={wc['sharpe']}, Return={wc['return_pct']:+.2f}%, "
            f"PF={wc['pf']}, MDD={wc['mdd']}%"
        )

    # Summary
    print(f"\n{'=' * 70}")
    print("  PHASE 4 SUMMARY")
    print("=" * 70)

    for symbol, results in all_results.items():
        tests = ["slippage", "funding", "latency", "realistic_fee"]
        passed = sum(1 for t in tests if results[t]["pass"])
        print(f"\n  {symbol}: {passed}/4 tests passed")
        for t in tests:
            p = "PASS" if results[t]["pass"] else "FAIL"
            print(f"    {t}: {p}")

    # Overall judgment
    all_results["judgment"] = {
        "research_validity": "Phase 2 CONDITIONAL, Phase 3 CONDITIONAL",
        "execution_realism": "See per-asset results",
        "operational_fit": "CG-2B PROVEN (CR-047)",
    }

    out_path = "docs/operations/evidence/cr046_phase4_results.json"
    os.makedirs("docs/operations/evidence", exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n  Results saved to {out_path}")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
