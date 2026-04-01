"""
CR-046 Phase 2: Out-of-Sample / Walk-Forward / Purged CV Validator

Validates Strategy D (SMC + WaveTrend + Supertrend, 2/3 consensus)
using Version B (pure-causal) SMC as canonical.

Tests:
  2.1 Temporal OOS split (4-month train / 2-month test)
  2.2 Walk-forward (3 windows, 3-month train / 1-month test)
  2.3 Purged cross-validation (5-fold, 48-bar embargo)
  2.4 Selection stability (Top 3 stable in >= 3/5 folds)

Usage:
    python scripts/strategy_d_oos_validator.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field

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
    collect_6month_ohlcv,
)


def compute_all_signals(highs, lows, closes):
    """Compute all 6 indicator signals. SMC uses Version B (pure-causal)."""
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

    # Version B (pure-causal) -- canonical
    smc_trend, smc_sigs = calc_smc_pure_causal(highs, lows, closes)
    signals["SMC"] = smc_sigs

    return signals


def rank_and_select_top3(closes, signals):
    """Rank indicators by Sharpe and select Top 3."""
    results = {}
    for name, sigs in signals.items():
        res = backtest_signals(closes, sigs, name)
        results[name] = res

    ranking = sorted(results.items(), key=lambda x: x[1].sharpe_ratio, reverse=True)
    top3_names = [name for name, _ in ranking[:3]]
    return top3_names, results, ranking


def build_strategy_d(closes, signals, top3_names):
    """Build Strategy D from top 3 indicators with 2/3 consensus."""
    top3_signals = {k: v for k, v in signals.items() if k in top3_names}
    top3_weights = {name: 1.0 for name in top3_names}
    composite = build_composite_strategy(closes, top3_signals, top3_weights, threshold=2.0)
    return backtest_signals(closes, composite, f"StrategyD({','.join(top3_names)})")


def test_temporal_oos(highs, lows, closes, n):
    """Test 2.1: Temporal OOS split (4-month train / 2-month test)."""
    # 4 months train, 2 months test
    train_end = int(n * 4 / 6)

    h_train, l_train, c_train = highs[:train_end], lows[:train_end], closes[:train_end]
    h_test, l_test, c_test = highs[train_end:], lows[train_end:], closes[train_end:]

    # Train: compute signals, rank, select top 3
    train_signals = compute_all_signals(h_train, l_train, c_train)
    top3_train, train_results, _ = rank_and_select_top3(c_train, train_signals)

    # Test: apply same top 3 selection
    test_signals = compute_all_signals(h_test, l_test, c_test)
    oos_result = build_strategy_d(c_test, test_signals, top3_train)

    return {
        "train_bars": train_end,
        "test_bars": n - train_end,
        "top3_selected": top3_train,
        "oos_sharpe": round(oos_result.sharpe_ratio, 2),
        "oos_return_pct": round(oos_result.total_return_pct, 2),
        "oos_win_rate": round(oos_result.win_rate, 1),
        "oos_pf": round(oos_result.profit_factor, 2),
        "oos_mdd": round(oos_result.max_drawdown_pct, 2),
        "oos_trades": oos_result.total_trades,
        "pass_sharpe": oos_result.sharpe_ratio > 0.5,
        "pass_return": oos_result.total_return_pct > 0,
    }


def test_walk_forward(highs, lows, closes, n):
    """Test 2.2: Walk-forward (3 windows, 3-month train / 1-month test)."""
    month_bars = n // 6  # ~720 bars per month
    windows = []

    for w in range(3):
        train_start = w * month_bars
        train_end = train_start + 3 * month_bars
        test_start = train_end
        test_end = min(test_start + month_bars, n)

        if test_end <= test_start or train_end > n:
            break

        h_tr = highs[train_start:train_end]
        l_tr = lows[train_start:train_end]
        c_tr = closes[train_start:train_end]

        h_te = highs[test_start:test_end]
        l_te = lows[test_start:test_end]
        c_te = closes[test_start:test_end]

        train_sigs = compute_all_signals(h_tr, l_tr, c_tr)
        top3, _, _ = rank_and_select_top3(c_tr, train_sigs)

        test_sigs = compute_all_signals(h_te, l_te, c_te)
        oos_res = build_strategy_d(c_te, test_sigs, top3)

        windows.append({
            "window": w + 1,
            "train_range": f"{train_start}-{train_end}",
            "test_range": f"{test_start}-{test_end}",
            "top3": top3,
            "oos_sharpe": round(oos_res.sharpe_ratio, 2),
            "oos_return_pct": round(oos_res.total_return_pct, 2),
            "oos_trades": oos_res.total_trades,
        })

    sharpes = [w["oos_sharpe"] for w in windows]
    mean_sharpe = np.mean(sharpes) if sharpes else 0.0

    return {
        "windows": windows,
        "mean_oos_sharpe": round(float(mean_sharpe), 2),
        "pass": float(mean_sharpe) > 0.3,
    }


def test_purged_cv(highs, lows, closes, n, n_folds=5, embargo=48):
    """Test 2.3: Purged cross-validation with embargo."""
    fold_size = n // n_folds
    folds = []

    for fold in range(n_folds):
        test_start = fold * fold_size
        test_end = min(test_start + fold_size, n)

        # Train = everything except test + embargo
        embargo_start = max(0, test_start - embargo)
        embargo_end = min(n, test_end + embargo)

        train_mask = np.ones(n, dtype=bool)
        train_mask[embargo_start:embargo_end] = False

        train_idx = np.where(train_mask)[0]
        if len(train_idx) < 200:  # need enough data
            continue

        h_tr = highs[train_idx]
        l_tr = lows[train_idx]
        c_tr = closes[train_idx]

        h_te = highs[test_start:test_end]
        l_te = lows[test_start:test_end]
        c_te = closes[test_start:test_end]

        train_sigs = compute_all_signals(h_tr, l_tr, c_tr)
        top3, _, ranking = rank_and_select_top3(c_tr, train_sigs)

        test_sigs = compute_all_signals(h_te, l_te, c_te)
        oos_res = build_strategy_d(c_te, test_sigs, top3)

        folds.append({
            "fold": fold + 1,
            "test_range": f"{test_start}-{test_end}",
            "top3": top3,
            "full_ranking": [name for name, _ in ranking],
            "oos_sharpe": round(oos_res.sharpe_ratio, 2),
            "oos_return_pct": round(oos_res.total_return_pct, 2),
            "oos_trades": oos_res.total_trades,
        })

    sharpes = [f["oos_sharpe"] for f in folds]
    mean_sharpe = np.mean(sharpes) if sharpes else 0.0
    std_sharpe = np.std(sharpes) if sharpes else 0.0

    return {
        "folds": folds,
        "mean_cv_sharpe": round(float(mean_sharpe), 2),
        "std_cv_sharpe": round(float(std_sharpe), 2),
        "pass": float(mean_sharpe) > 0.3,
    }


def test_selection_stability(folds_result):
    """Test 2.4: Check if Top 3 is stable across folds."""
    canonical_top3 = {"SMC", "WaveTrend", "Supertrend"}
    stable_count = 0

    for fold in folds_result["folds"]:
        fold_top3 = set(fold["top3"])
        if fold_top3 == canonical_top3:
            stable_count += 1

    return {
        "canonical_top3": sorted(canonical_top3),
        "stable_folds": stable_count,
        "total_folds": len(folds_result["folds"]),
        "pass": stable_count >= 3,
        "fold_selections": [
            {"fold": f["fold"], "top3": f["top3"], "match": set(f["top3"]) == canonical_top3}
            for f in folds_result["folds"]
        ],
    }


def main():
    print("=" * 70)
    print("  CR-046 PHASE 2: OOS / Walk-Forward / Purged CV Validation")
    print("  Strategy D: SMC(pure-causal) + WaveTrend + Supertrend")
    print("  SMC Version: B (canonical, pure-causal)")
    print("=" * 70)

    # Collect data
    ohlcv = collect_6month_ohlcv()
    highs = np.array([c[2] for c in ohlcv])
    lows = np.array([c[3] for c in ohlcv])
    closes = np.array([c[4] for c in ohlcv])
    n = len(closes)

    print(f"\n  Total bars: {n}")
    print(f"  Price range: {closes[0]:.0f} -> {closes[-1]:.0f}")

    results = {}

    # Test 2.1: Temporal OOS
    print("\n" + "-" * 70)
    print("  TEST 2.1: Temporal OOS Split (4-month train / 2-month test)")
    print("-" * 70)
    oos = test_temporal_oos(highs, lows, closes, n)
    results["temporal_oos"] = oos
    print(f"  Top 3 (train): {oos['top3_selected']}")
    print(f"  OOS Sharpe: {oos['oos_sharpe']}")
    print(f"  OOS Return: {oos['oos_return_pct']:+.2f}%")
    print(f"  OOS Trades: {oos['oos_trades']}")
    print(f"  OOS WinR: {oos['oos_win_rate']}%")
    print(f"  OOS PF: {oos['oos_pf']}")
    print(f"  OOS MDD: {oos['oos_mdd']}%")
    print(f"  PASS (Sharpe>0.5): {'YES' if oos['pass_sharpe'] else 'NO'}")
    print(f"  PASS (Return>0): {'YES' if oos['pass_return'] else 'NO'}")

    # Test 2.2: Walk-Forward
    print("\n" + "-" * 70)
    print("  TEST 2.2: Walk-Forward (3 windows)")
    print("-" * 70)
    wf = test_walk_forward(highs, lows, closes, n)
    results["walk_forward"] = wf
    for w in wf["windows"]:
        print(f"  Window {w['window']}: Top3={w['top3']}, "
              f"Sharpe={w['oos_sharpe']}, Return={w['oos_return_pct']:+.2f}%, "
              f"Trades={w['oos_trades']}")
    print(f"  Mean OOS Sharpe: {wf['mean_oos_sharpe']}")
    print(f"  PASS (mean>0.3): {'YES' if wf['pass'] else 'NO'}")

    # Test 2.3: Purged CV
    print("\n" + "-" * 70)
    print("  TEST 2.3: Purged Cross-Validation (5-fold, 48h embargo)")
    print("-" * 70)
    cv = test_purged_cv(highs, lows, closes, n)
    results["purged_cv"] = cv
    for f in cv["folds"]:
        print(f"  Fold {f['fold']}: Top3={f['top3']}, "
              f"Sharpe={f['oos_sharpe']}, Return={f['oos_return_pct']:+.2f}%, "
              f"Trades={f['oos_trades']}")
    print(f"  Mean CV Sharpe: {cv['mean_cv_sharpe']}")
    print(f"  Std CV Sharpe: {cv['std_cv_sharpe']}")
    print(f"  PASS (mean>0.3): {'YES' if cv['pass'] else 'NO'}")

    # Test 2.4: Selection Stability
    print("\n" + "-" * 70)
    print("  TEST 2.4: Selection Stability")
    print("-" * 70)
    stability = test_selection_stability(cv)
    results["selection_stability"] = stability
    for s in stability["fold_selections"]:
        match = "MATCH" if s["match"] else "DIFFER"
        print(f"  Fold {s['fold']}: {s['top3']} [{match}]")
    print(f"  Stable folds: {stability['stable_folds']}/{stability['total_folds']}")
    print(f"  PASS (>=3/5): {'YES' if stability['pass'] else 'NO'}")

    # Summary
    print("\n" + "=" * 70)
    print("  PHASE 2 SUMMARY")
    print("=" * 70)

    judgments = {
        "research_validity": {
            "oos_sharpe_pass": oos["pass_sharpe"],
            "oos_return_pass": oos["pass_return"],
            "wf_mean_sharpe_pass": wf["pass"],
            "cv_mean_sharpe_pass": cv["pass"],
            "selection_stable": stability["pass"],
        },
        "execution_realism": "Phase 4 (pending)",
        "operational_fit": "CG-2B PROVEN (CR-047)",
    }
    results["judgments"] = judgments

    rv = judgments["research_validity"]
    rv_pass_count = sum(1 for v in rv.values() if v is True)
    rv_total = len(rv)
    rv_pass = rv_pass_count == rv_total

    print(f"\n  Research Validity: {rv_pass_count}/{rv_total} checks passed")
    for k, v in rv.items():
        print(f"    {k}: {'PASS' if v else 'FAIL'}")

    print(f"\n  Execution Realism: Phase 4 (pending)")
    print(f"  Operational Fit: CG-2B PROVEN (CR-047)")

    overall = "PASS" if rv_pass else ("CONDITIONAL" if rv_pass_count >= 3 else "FAIL")
    results["phase2_verdict"] = overall
    print(f"\n  Phase 2 Verdict: {overall}")

    # Save
    os.makedirs("docs/operations/evidence", exist_ok=True)
    out_path = "docs/operations/evidence/cr046_phase2_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Results saved to {out_path}")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
