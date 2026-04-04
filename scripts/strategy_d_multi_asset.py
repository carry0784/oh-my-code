"""
CR-046 Phase 3: Multi-Asset / Multi-Regime Validation

Validates the canonical core pair (SMC + WaveTrend) across:
  3.1 ETH/USDT
  3.2 SOL/USDT
  3.3 Bull regime identification
  3.4 Sideways regime identification

Also measures:
  - core_pair_survival_rate: does SMC+WaveTrend stay as Top 2 across assets
  - third_slot_incremental_value: does adding a 3rd indicator help

Usage:
    python scripts/strategy_d_multi_asset.py
"""

from __future__ import annotations

import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.indicator_backtest import (
    calc_smc_pure_causal,
    calc_wavetrend,
    calc_supertrend,
    calc_squeeze_momentum,
    calc_macd,
    calc_williams_vix_fix,
    backtest_signals,
    build_composite_strategy,
)


def collect_asset_ohlcv(symbol="BTC/USDT", timeframe="1h", months=6):
    """Collect OHLCV for any asset."""
    try:
        import ccxt

        exchange = ccxt.binance({"enableRateLimit": True})
        all_ohlcv = []
        target_bars = months * 30 * 24
        since = exchange.milliseconds() - target_bars * 3600 * 1000
        batch_size = 1000

        print(f"  [DATA] Collecting {target_bars} bars of {symbol} {timeframe}...")
        while len(all_ohlcv) < target_bars:
            batch = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=batch_size)
            if not batch:
                break
            all_ohlcv.extend(batch)
            since = batch[-1][0] + 1
            if len(batch) < batch_size:
                break
            time.sleep(0.5)

        print(f"  [DATA] Collected {len(all_ohlcv)} bars for {symbol}")
        return all_ohlcv
    except Exception as e:
        print(f"  [DATA] Failed for {symbol}: {e}")
        return []


def compute_all_signals(highs, lows, closes):
    """Compute all 6 indicators. SMC uses Version B (pure-causal)."""
    signals = {}
    st_trend, st_sigs = calc_supertrend(highs, lows, closes, 10, 3.0)
    signals["Supertrend"] = st_sigs
    sq_val, sq_on, sq_sigs = calc_squeeze_momentum(highs, lows, closes)
    signals["SqueezeMom"] = sq_sigs
    _, _, _, macd_sigs = calc_macd(closes)
    signals["MACD"] = macd_sigs
    wvf_val, wvf_sigs = calc_williams_vix_fix(closes, lows)
    signals["WilliamsVF"] = wvf_sigs
    wt1, wt2, wt_sigs = calc_wavetrend(highs, lows, closes)
    signals["WaveTrend"] = wt_sigs
    smc_trend, smc_sigs = calc_smc_pure_causal(highs, lows, closes)
    signals["SMC"] = smc_sigs
    return signals


def test_core_pair(closes, signals):
    """Test canonical core pair: SMC + WaveTrend, 2/2 consensus."""
    core_signals = {"SMC": signals["SMC"], "WaveTrend": signals["WaveTrend"]}
    core_weights = {"SMC": 1.0, "WaveTrend": 1.0}
    composite = build_composite_strategy(closes, core_signals, core_weights, threshold=2.0)
    return backtest_signals(closes, composite, "CorePair(SMC+WaveTrend)")


def test_with_third(closes, signals, third_name):
    """Test core pair + 3rd indicator, 2/3 consensus."""
    trio_signals = {
        "SMC": signals["SMC"],
        "WaveTrend": signals["WaveTrend"],
        third_name: signals[third_name],
    }
    trio_weights = {"SMC": 1.0, "WaveTrend": 1.0, third_name: 1.0}
    composite = build_composite_strategy(closes, trio_signals, trio_weights, threshold=2.0)
    return backtest_signals(closes, composite, f"Trio(SMC+WT+{third_name})")


def rank_indicators(closes, signals):
    """Rank all indicators by Sharpe."""
    results = {}
    for name, sigs in signals.items():
        res = backtest_signals(closes, sigs, name)
        results[name] = res
    ranking = sorted(results.items(), key=lambda x: x[1].sharpe_ratio, reverse=True)
    return [(name, res.sharpe_ratio) for name, res in ranking]


def analyze_asset(symbol, ohlcv):
    """Full analysis of one asset."""
    highs = np.array([c[2] for c in ohlcv])
    lows = np.array([c[3] for c in ohlcv])
    closes = np.array([c[4] for c in ohlcv])
    n = len(closes)
    buy_hold = (closes[-1] / closes[0] - 1) * 100

    signals = compute_all_signals(highs, lows, closes)

    # Core pair
    core_res = test_core_pair(closes, signals)

    # With Supertrend
    trio_st = test_with_third(closes, signals, "Supertrend")

    # With MACD
    trio_macd = test_with_third(closes, signals, "MACD")

    # Ranking
    ranking = rank_indicators(closes, signals)
    top2 = [name for name, _ in ranking[:2]]
    core_pair_survival = set(top2) == {"SMC", "WaveTrend"}

    # 3rd slot incremental value
    st_incremental = trio_st.sharpe_ratio - core_res.sharpe_ratio
    macd_incremental = trio_macd.sharpe_ratio - core_res.sharpe_ratio

    return {
        "symbol": symbol,
        "bars": n,
        "buy_hold_pct": round(buy_hold, 2),
        "price_range": f"{closes[0]:.0f} -> {closes[-1]:.0f}",
        "core_pair": {
            "sharpe": round(core_res.sharpe_ratio, 2),
            "return_pct": round(core_res.total_return_pct, 2),
            "win_rate": round(core_res.win_rate, 1),
            "pf": round(core_res.profit_factor, 2),
            "mdd": round(core_res.max_drawdown_pct, 2),
            "trades": core_res.total_trades,
        },
        "trio_supertrend": {
            "sharpe": round(trio_st.sharpe_ratio, 2),
            "return_pct": round(trio_st.total_return_pct, 2),
            "trades": trio_st.total_trades,
            "incremental_sharpe": round(st_incremental, 2),
        },
        "trio_macd": {
            "sharpe": round(trio_macd.sharpe_ratio, 2),
            "return_pct": round(trio_macd.total_return_pct, 2),
            "trades": trio_macd.total_trades,
            "incremental_sharpe": round(macd_incremental, 2),
        },
        "ranking": ranking[:6],
        "top2": top2,
        "core_pair_survival": core_pair_survival,
    }


def identify_regimes(closes):
    """Identify bull/bear/sideways sub-periods."""
    n = len(closes)
    quarter = n // 4
    regimes = []
    for i in range(4):
        start = i * quarter
        end = min((i + 1) * quarter, n)
        ret = (closes[end - 1] / closes[start] - 1) * 100
        if ret > 10:
            label = "bull"
        elif ret < -10:
            label = "bear"
        else:
            label = "sideways"
        regimes.append(
            {
                "quarter": i + 1,
                "start": start,
                "end": end,
                "return_pct": round(ret, 2),
                "regime": label,
            }
        )
    return regimes


def main():
    print("=" * 70)
    print("  CR-046 PHASE 3: Multi-Asset / Multi-Regime Validation")
    print("  Canonical Core: SMC (pure-causal) + WaveTrend")
    print("=" * 70)

    results = {}

    # Test 3.0: BTC/USDT (reference)
    assets = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]

    for symbol in assets:
        print(f"\n{'=' * 70}")
        print(f"  ASSET: {symbol}")
        print("=" * 70)

        ohlcv = collect_asset_ohlcv(symbol)
        if not ohlcv or len(ohlcv) < 500:
            print(f"  SKIP: insufficient data for {symbol}")
            results[symbol] = {"status": "SKIP", "reason": "insufficient data"}
            continue

        asset_result = analyze_asset(symbol, ohlcv)
        results[symbol] = asset_result

        cp = asset_result["core_pair"]
        print(f"\n  Buy & Hold: {asset_result['buy_hold_pct']:+.2f}%")
        print(f"\n  [Core Pair: SMC + WaveTrend]")
        print(f"    Sharpe: {cp['sharpe']}")
        print(f"    Return: {cp['return_pct']:+.2f}%")
        print(f"    Win Rate: {cp['win_rate']}%")
        print(f"    PF: {cp['pf']}")
        print(f"    MDD: {cp['mdd']}%")
        print(f"    Trades: {cp['trades']}")

        ts = asset_result["trio_supertrend"]
        print(f"\n  [+Supertrend]")
        print(f"    Sharpe: {ts['sharpe']} (incremental: {ts['incremental_sharpe']:+.2f})")
        print(f"    Return: {ts['return_pct']:+.2f}%, Trades: {ts['trades']}")

        tm = asset_result["trio_macd"]
        print(f"\n  [+MACD]")
        print(f"    Sharpe: {tm['sharpe']} (incremental: {tm['incremental_sharpe']:+.2f})")
        print(f"    Return: {tm['return_pct']:+.2f}%, Trades: {tm['trades']}")

        print(f"\n  [Ranking]")
        for rank, (name, sharpe) in enumerate(asset_result["ranking"], 1):
            print(f"    {rank}. {name}: {sharpe:.2f}")
        print(f"  Core pair survival: {'YES' if asset_result['core_pair_survival'] else 'NO'}")

    # Regime analysis on BTC
    if "BTC/USDT" in results and results["BTC/USDT"].get("bars"):
        print(f"\n{'=' * 70}")
        print("  REGIME ANALYSIS (BTC/USDT)")
        print("=" * 70)

        btc_ohlcv = collect_asset_ohlcv("BTC/USDT")
        closes = np.array([c[4] for c in btc_ohlcv])
        highs = np.array([c[2] for c in btc_ohlcv])
        lows = np.array([c[3] for c in btc_ohlcv])

        regimes = identify_regimes(closes)
        regime_results = []

        for reg in regimes:
            s, e = reg["start"], reg["end"]
            if e - s < 200:
                continue
            h_r, l_r, c_r = highs[s:e], lows[s:e], closes[s:e]
            sigs = compute_all_signals(h_r, l_r, c_r)
            core = test_core_pair(c_r, sigs)
            bh = (c_r[-1] / c_r[0] - 1) * 100

            regime_res = {
                "quarter": reg["quarter"],
                "regime": reg["regime"],
                "buy_hold_pct": round(bh, 2),
                "core_sharpe": round(core.sharpe_ratio, 2),
                "core_return_pct": round(core.total_return_pct, 2),
                "core_trades": core.total_trades,
                "core_mdd": round(core.max_drawdown_pct, 2),
                "beats_bh": core.total_return_pct > bh,
            }
            regime_results.append(regime_res)
            print(
                f"\n  Q{reg['quarter']} ({reg['regime']}): B&H={bh:+.1f}%, "
                f"Core={core.total_return_pct:+.2f}%, "
                f"Sharpe={core.sharpe_ratio:.2f}, Trades={core.total_trades}"
            )

        results["regime_analysis"] = regime_results

    # Summary
    print(f"\n{'=' * 70}")
    print("  PHASE 3 SUMMARY")
    print("=" * 70)

    # Core pair survival rate
    survival_count = sum(
        1 for k, v in results.items() if isinstance(v, dict) and v.get("core_pair_survival") is True
    )
    asset_count = sum(
        1
        for k, v in results.items()
        if isinstance(v, dict) and v.get("core_pair_survival") is not None
    )
    survival_rate = survival_count / asset_count if asset_count > 0 else 0

    print(f"\n  Core pair survival rate: {survival_count}/{asset_count} ({survival_rate:.0%})")

    # 3rd slot incremental value
    for symbol in assets:
        r = results.get(symbol, {})
        if isinstance(r, dict) and "trio_supertrend" in r:
            st_inc = r["trio_supertrend"]["incremental_sharpe"]
            macd_inc = r["trio_macd"]["incremental_sharpe"]
            print(
                f"  {symbol} 3rd-slot incremental: Supertrend={st_inc:+.2f}, MACD={macd_inc:+.2f}"
            )

    # Multi-asset core pair Sharpe
    print(f"\n  Multi-asset core pair Sharpe:")
    for symbol in assets:
        r = results.get(symbol, {})
        if isinstance(r, dict) and "core_pair" in r:
            cp = r["core_pair"]
            print(
                f"    {symbol}: Sharpe={cp['sharpe']}, "
                f"Return={cp['return_pct']:+.2f}%, PF={cp['pf']}"
            )

    # AC checks
    results["summary"] = {
        "core_pair_survival_rate": f"{survival_count}/{asset_count}",
        "research_validity": "See per-asset results",
        "execution_realism": "Phase 4 (pending)",
        "operational_fit": "CG-2B PROVEN (CR-047)",
    }

    # Save
    os.makedirs("docs/operations/evidence", exist_ok=True)
    out_path = "docs/operations/evidence/cr046_phase3_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Results saved to {out_path}")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
