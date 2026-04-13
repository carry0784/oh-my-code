"""
Phase C C-3 — R-track Regime Diversity Diagnosis

Quantifies regime distribution, per-regime trade density, fitness,
coverage gaps, and asset asymmetry to determine whether low RDS is
a detector artefact or a structural market property.

This is a DIAGNOSTIC script. No strategy/detector modifications.

Usage:
  python scripts/phase_c_c3_rtrack_diagnosis.py

Constraints (C-3 GO):
  - Diagnostic only (no implementation)
  - RegimeDetector = read-only
  - No strategy logic changes
  - No SMC/WT signal changes
  - No B-1 core / protected symbol modification
  - No C-4/W-track/S-1 follow-up
  - No auto-advance to C-4
"""

import json
import math
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np

# Ensure UTF-8 stdout on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio  # noqa: E402

from app.core.database import async_session_factory  # noqa: E402
from app.services.backtesting_engine import BacktestingEngine, BacktestConfig  # noqa: E402
from app.services.fitness_function import FitnessFunction  # noqa: E402
from app.services.history_data_manager import HistoryDataManager  # noqa: E402
from app.services.regime_detector import RegimeDetector, BatchRegimeResult  # noqa: E402
from strategies.smc_wavetrend_strategy import SMCWaveTrendStrategy  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ASSETS = ["SOL/USDT:USDT", "BTC/USDT:USDT"]
TIMEFRAME = "1h"
TOTAL_BARS = 9600
RDS_THRESHOLD = 0.55
MIN_TRADES = 10

# Segment ratios (B-2 original — diagnostic baseline)
SEGMENT_RATIOS = {
    "train": 0.60,
    "forward1": 0.20,
    "forward2": 0.10,
    "holdout": 0.10,
}

SEGMENT_NAMES = ("train", "forward_1", "forward_2", "holdout")

# All known regime labels
ALL_REGIMES = ["trending_up", "trending_down", "ranging", "high_volatility", "crisis", "unknown"]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class RegimeBarStats:
    """Per-regime bar-level statistics."""
    regime: str
    bar_count: int = 0
    bar_share: float = 0.0  # fraction of total bars


@dataclass
class RegimeTradeStats:
    """Per-regime trade-level statistics."""
    regime: str
    trade_count: int = 0
    trade_share: float = 0.0  # fraction of total trades
    win_count: int = 0
    loss_count: int = 0
    win_rate: float = 0.0
    total_return_pct: float = 0.0


@dataclass
class RegimeFitnessStats:
    """Per-regime fitness approximation."""
    regime: str
    trade_count: int = 0
    win_rate: float = 0.0
    avg_return_pct: float = 0.0
    has_enough_trades: bool = False  # >= MIN_TRADES


@dataclass
class SegmentRegimeProfile:
    """Regime distribution within a single segment."""
    segment_name: str
    total_bars: int = 0
    regime_bars: dict[str, int] = field(default_factory=dict)
    regime_shares: dict[str, float] = field(default_factory=dict)
    dominant_regime: str = ""
    dominant_share: float = 0.0
    effective_regime_count: int = 0  # regimes with >= 5% share
    rds: float = 0.0  # 1 - HHI


@dataclass
class AssetRegimeDiagnosis:
    """Complete regime diagnosis for one asset."""
    symbol: str

    # Global regime distribution
    total_bars: int = 0
    global_regime_bars: dict[str, int] = field(default_factory=dict)
    global_regime_shares: dict[str, float] = field(default_factory=dict)
    global_rds: float = 0.0
    global_dominant_regime: str = ""
    global_dominant_share: float = 0.0
    global_effective_regime_count: int = 0

    # Per-segment regime profiles
    segment_profiles: list[SegmentRegimeProfile] = field(default_factory=list)

    # Per-regime trade stats
    regime_trade_stats: list[RegimeTradeStats] = field(default_factory=list)

    # Coverage gap: regimes with 0 trades
    regime_blank_zones: list[str] = field(default_factory=list)
    regime_blank_zone_count: int = 0

    # Verdict
    rds_pass: bool = False
    step_verdict: str = ""  # PASS / MAINTAINED_FAIL / INFORMATIVE_FAIL


@dataclass
class CrossAssetComparison:
    """Cross-asset regime asymmetry."""
    regime: str
    sol_share: float = 0.0
    btc_share: float = 0.0
    delta: float = 0.0  # abs difference
    asymmetric: bool = False  # delta > 0.10


# ---------------------------------------------------------------------------
# Computation functions
# ---------------------------------------------------------------------------

def compute_regime_labels(detector: RegimeDetector, ohlcv: list) -> list[str]:
    """Get per-bar regime labels."""
    results = detector.detect_batch(ohlcv)
    labels = [entry.regime for entry in results]
    # Pad if shorter than ohlcv (warmup bars)
    while len(labels) < len(ohlcv):
        labels.insert(0, "unknown")
    return labels


def compute_regime_distribution(labels: list[str]) -> tuple[dict[str, int], dict[str, float]]:
    """Count bars per regime and compute shares."""
    counts: dict[str, int] = {}
    for lbl in labels:
        counts[lbl] = counts.get(lbl, 0) + 1

    total = len(labels)
    shares: dict[str, float] = {}
    for regime, count in counts.items():
        shares[regime] = count / total if total > 0 else 0.0

    return counts, shares


def compute_rds(shares: dict[str, float]) -> float:
    """Regime Diversity Score = 1 - HHI (Herfindahl-Hirschman Index)."""
    hhi = sum(s ** 2 for s in shares.values())
    return 1.0 - hhi


def compute_effective_regime_count(shares: dict[str, float], threshold: float = 0.05) -> int:
    """Count regimes with share >= threshold."""
    return sum(1 for s in shares.values() if s >= threshold)


def compute_dominant_regime(shares: dict[str, float]) -> tuple[str, float]:
    """Find the regime with the largest share."""
    if not shares:
        return "unknown", 0.0
    dominant = max(shares, key=shares.get)
    return dominant, shares[dominant]


def build_segment_boundaries(total: int) -> dict[str, tuple[int, int]]:
    """Compute segment index boundaries using baseline ratios."""
    train_end = int(total * SEGMENT_RATIOS["train"])
    fw1_end = train_end + int(total * SEGMENT_RATIOS["forward1"])
    fw2_end = fw1_end + int(total * SEGMENT_RATIOS["forward2"])
    return {
        "train": (0, train_end),
        "forward_1": (train_end, fw1_end),
        "forward_2": (fw1_end, fw2_end),
        "holdout": (fw2_end, total),
    }


def build_segment_regime_profile(
    segment_name: str,
    labels: list[str],
    start: int,
    end: int,
) -> SegmentRegimeProfile:
    """Build regime profile for a single segment."""
    seg_labels = labels[start:end]
    counts, shares = compute_regime_distribution(seg_labels)
    rds = compute_rds(shares)
    eff_count = compute_effective_regime_count(shares)
    dominant, dom_share = compute_dominant_regime(shares)

    return SegmentRegimeProfile(
        segment_name=segment_name,
        total_bars=len(seg_labels),
        regime_bars=counts,
        regime_shares={k: round(v, 4) for k, v in shares.items()},
        dominant_regime=dominant,
        dominant_share=round(dom_share, 4),
        effective_regime_count=eff_count,
        rds=round(rds, 4),
    )


def classify_trades_by_regime(
    trades: list,
    ohlcv: list,
    regime_labels: list[str],
) -> list[RegimeTradeStats]:
    """Assign each trade to a regime based on entry timestamp."""
    # Build timestamp -> index lookup
    ts_to_idx: dict[int, int] = {}
    for i, candle in enumerate(ohlcv):
        ts_to_idx[candle[0]] = i

    # Count trades per regime
    regime_trades: dict[str, list] = {r: [] for r in ALL_REGIMES}

    for trade in trades:
        # TradeRecord has entry_time (ms timestamp)
        entry_ts = trade.entry_time if hasattr(trade, "entry_time") else 0
        idx = ts_to_idx.get(entry_ts)
        if idx is not None and idx < len(regime_labels):
            regime = regime_labels[idx]
        else:
            # Fallback: find closest candle
            regime = "unknown"
            if entry_ts > 0:
                for i, candle in enumerate(ohlcv):
                    if candle[0] >= entry_ts:
                        if i < len(regime_labels):
                            regime = regime_labels[i]
                        break

        regime_trades.setdefault(regime, [])
        regime_trades[regime].append(trade)

    # Build stats
    total_trades = len(trades)
    stats_list = []
    for regime in ALL_REGIMES:
        r_trades = regime_trades.get(regime, [])
        count = len(r_trades)
        wins = sum(1 for t in r_trades if t.return_pct > 0)
        losses = count - wins
        total_ret = sum(t.return_pct for t in r_trades)

        stats_list.append(RegimeTradeStats(
            regime=regime,
            trade_count=count,
            trade_share=round(count / total_trades, 4) if total_trades > 0 else 0.0,
            win_count=wins,
            loss_count=losses,
            win_rate=round(wins / count, 4) if count > 0 else 0.0,
            total_return_pct=round(total_ret, 4),
        ))

    return stats_list


# ---------------------------------------------------------------------------
# Main diagnosis
# ---------------------------------------------------------------------------

async def diagnose_asset(session, symbol: str) -> AssetRegimeDiagnosis:
    """Run full regime diagnosis for one asset."""
    print(f"\n{'='*60}")
    print(f"  {symbol} — R-track Regime Diagnosis")
    print(f"{'='*60}")

    # Step 1: Load OHLCV data
    hdm = HistoryDataManager()
    ohlcv = await hdm.get_replay_candles(
        session=session,
        exchange="binance",
        symbol=symbol,
        timeframe=TIMEFRAME,
        limit=TOTAL_BARS,
    )
    print(f"  Loaded {len(ohlcv)} bars")

    # Step 2: Compute regime labels
    detector = RegimeDetector()
    labels = compute_regime_labels(detector, ohlcv)
    print(f"  Regime labels computed: {len(labels)} bars")

    # Step 3: Global regime distribution
    g_counts, g_shares = compute_regime_distribution(labels)
    g_rds = compute_rds(g_shares)
    g_eff = compute_effective_regime_count(g_shares)
    g_dom, g_dom_share = compute_dominant_regime(g_shares)

    print(f"  Global RDS: {g_rds:.4f} (threshold: {RDS_THRESHOLD})")
    print(f"  Dominant regime: {g_dom} ({g_dom_share:.1%})")
    print(f"  Effective regime count: {g_eff}")
    for regime, share in sorted(g_shares.items(), key=lambda x: -x[1]):
        print(f"    {regime}: {g_counts[regime]} bars ({share:.1%})")

    # Step 4: Per-segment regime profiles
    boundaries = build_segment_boundaries(len(ohlcv))
    seg_profiles = []
    for seg_name in SEGMENT_NAMES:
        start, end = boundaries[seg_name]
        profile = build_segment_regime_profile(seg_name, labels, start, end)
        seg_profiles.append(profile)
        print(f"\n  [{seg_name}] bars={profile.total_bars} RDS={profile.rds:.4f} "
              f"dominant={profile.dominant_regime}({profile.dominant_share:.1%}) "
              f"effective_regimes={profile.effective_regime_count}")

    # Step 5: Run backtest to get trades for regime-trade cross-reference
    print(f"\n  Running backtest for trade-regime mapping...")
    strategy = SMCWaveTrendStrategy(symbol=symbol)
    bt_engine = BacktestingEngine(config=BacktestConfig(
        initial_capital=10000.0,
        position_size_pct=2.0,
    ))
    bt_result = bt_engine.run(strategy, ohlcv)
    all_trades = bt_result.trades if bt_result.trades else []
    print(f"  Total trades: {len(all_trades)}")

    # Step 6: Classify trades by regime
    regime_trade_stats = classify_trades_by_regime(all_trades, ohlcv, labels)

    # Print regime-trade distribution
    print(f"\n  Regime-Trade Distribution:")
    for rts in regime_trade_stats:
        if rts.trade_count > 0:
            print(f"    {rts.regime}: {rts.trade_count} trades "
                  f"({rts.trade_share:.1%}), "
                  f"win_rate={rts.win_rate:.1%}, "
                  f"return={rts.total_return_pct:+.2f}%")

    # Step 7: Identify blank zones (regimes present in data but 0 trades)
    blank_zones = []
    for rts in regime_trade_stats:
        if rts.trade_count == 0 and g_counts.get(rts.regime, 0) > 0:
            blank_zones.append(rts.regime)

    if blank_zones:
        print(f"\n  Regime blank zones (bars exist, 0 trades): {blank_zones}")

    # Step 8: Verdict
    rds_pass = g_rds >= RDS_THRESHOLD

    if rds_pass:
        verdict = "PASS"
    elif g_dom_share >= 0.80:
        # 80%+ in one regime = structurally concentrated market
        verdict = "MAINTAINED_FAIL"
    else:
        verdict = "INFORMATIVE_FAIL"

    print(f"\n  RDS PASS: {rds_pass}")
    print(f"  Step verdict: {verdict}")

    return AssetRegimeDiagnosis(
        symbol=symbol,
        total_bars=len(ohlcv),
        global_regime_bars=g_counts,
        global_regime_shares={k: round(v, 4) for k, v in g_shares.items()},
        global_rds=round(g_rds, 4),
        global_dominant_regime=g_dom,
        global_dominant_share=round(g_dom_share, 4),
        global_effective_regime_count=g_eff,
        segment_profiles=seg_profiles,
        regime_trade_stats=regime_trade_stats,
        regime_blank_zones=blank_zones,
        regime_blank_zone_count=len(blank_zones),
        rds_pass=rds_pass,
        step_verdict=verdict,
    )


def compute_asset_asymmetry(
    sol: AssetRegimeDiagnosis,
    btc: AssetRegimeDiagnosis,
) -> list[CrossAssetComparison]:
    """Compare regime distributions between SOL and BTC."""
    comparisons = []
    all_regimes = set(sol.global_regime_shares.keys()) | set(btc.global_regime_shares.keys())

    for regime in sorted(all_regimes):
        sol_share = sol.global_regime_shares.get(regime, 0.0)
        btc_share = btc.global_regime_shares.get(regime, 0.0)
        delta = abs(sol_share - btc_share)
        comparisons.append(CrossAssetComparison(
            regime=regime,
            sol_share=round(sol_share, 4),
            btc_share=round(btc_share, 4),
            delta=round(delta, 4),
            asymmetric=delta > 0.10,
        ))

    return comparisons


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(
    diagnoses: list[AssetRegimeDiagnosis],
    asymmetry: list[CrossAssetComparison],
) -> str:
    """Generate C-3 deliverables as markdown."""
    lines = []

    # Deliverable 1: Global Regime Distribution
    lines.append("## Deliverable 1: Global Regime Distribution")
    lines.append("")

    for diag in diagnoses:
        lines.append(f"### {diag.symbol}")
        lines.append("")
        lines.append(f"| Regime | Bars | Share | Trades | Trade Share |")
        lines.append(f"|--------|------|-------|--------|-------------|")

        for regime in ALL_REGIMES:
            bars = diag.global_regime_bars.get(regime, 0)
            share = diag.global_regime_shares.get(regime, 0.0)
            # Find trade count for this regime
            trade_count = 0
            trade_share = 0.0
            for rts in diag.regime_trade_stats:
                if rts.regime == regime:
                    trade_count = rts.trade_count
                    trade_share = rts.trade_share
                    break
            if bars > 0 or trade_count > 0:
                lines.append(f"| {regime} | {bars} | {share:.1%} | "
                             f"{trade_count} | {trade_share:.1%} |")

        lines.append("")
        lines.append(f"**RDS:** {diag.global_rds:.4f} (threshold: {RDS_THRESHOLD})")
        lines.append(f"**Dominant regime:** {diag.global_dominant_regime} ({diag.global_dominant_share:.1%})")
        lines.append(f"**Effective regime count:** {diag.global_effective_regime_count}")
        lines.append(f"**Blank zones:** {diag.regime_blank_zones if diag.regime_blank_zones else 'none'}")
        lines.append(f"**RDS PASS:** {diag.rds_pass}")
        lines.append(f"**Step verdict:** **{diag.step_verdict}**")
        lines.append("")

    # Deliverable 2: Per-Segment Regime Profile
    lines.append("## Deliverable 2: Per-Segment Regime Profile")
    lines.append("")

    for diag in diagnoses:
        lines.append(f"### {diag.symbol}")
        lines.append("")
        lines.append("| Segment | Bars | Dominant | Dom Share | Eff Regimes | RDS |")
        lines.append("|---------|------|----------|-----------|-------------|-----|")

        for sp in diag.segment_profiles:
            lines.append(f"| {sp.segment_name} | {sp.total_bars} | "
                         f"{sp.dominant_regime} | {sp.dominant_share:.1%} | "
                         f"{sp.effective_regime_count} | {sp.rds:.4f} |")

        lines.append("")

    # Deliverable 3: Regime-Trade Cross-Reference
    lines.append("## Deliverable 3: Regime-Trade Cross-Reference")
    lines.append("")

    for diag in diagnoses:
        lines.append(f"### {diag.symbol}")
        lines.append("")
        lines.append("| Regime | Trades | Share | Win Rate | Return |")
        lines.append("|--------|--------|-------|----------|--------|")

        for rts in diag.regime_trade_stats:
            if rts.trade_count > 0 or diag.global_regime_bars.get(rts.regime, 0) > 0:
                lines.append(f"| {rts.regime} | {rts.trade_count} | "
                             f"{rts.trade_share:.1%} | {rts.win_rate:.1%} | "
                             f"{rts.total_return_pct:+.2f}% |")

        lines.append("")
        # Trade concentration
        total_trades = sum(rts.trade_count for rts in diag.regime_trade_stats)
        dom_trade_regime = max(diag.regime_trade_stats, key=lambda x: x.trade_count)
        if total_trades > 0:
            lines.append(f"**Trade concentration:** {dom_trade_regime.trade_count}/{total_trades} "
                         f"({dom_trade_regime.trade_share:.1%}) in {dom_trade_regime.regime}")
        lines.append("")

    # Deliverable 4: Asset Regime Asymmetry
    lines.append("## Deliverable 4: Asset Regime Asymmetry")
    lines.append("")
    lines.append("| Regime | SOL Share | BTC Share | Delta | Asymmetric? |")
    lines.append("|--------|-----------|-----------|-------|-------------|")

    for cmp in asymmetry:
        asym_mark = "**YES**" if cmp.asymmetric else "no"
        lines.append(f"| {cmp.regime} | {cmp.sol_share:.1%} | "
                     f"{cmp.btc_share:.1%} | {cmp.delta:.1%} | {asym_mark} |")

    lines.append("")

    # RDS comparison
    sol_diag = diagnoses[0]
    btc_diag = diagnoses[1]
    lines.append(f"**SOL RDS:** {sol_diag.global_rds:.4f}")
    lines.append(f"**BTC RDS:** {btc_diag.global_rds:.4f}")
    rds_delta = abs(sol_diag.global_rds - btc_diag.global_rds)
    lines.append(f"**RDS delta:** {rds_delta:.4f}")
    lines.append("")

    # Cross-asset summary
    lines.append("## Cross-Asset Regime Verdict")
    lines.append("")
    verdicts = [d.step_verdict for d in diagnoses]
    if all(v == "PASS" for v in verdicts):
        overall = "PASS"
    elif all(v == "MAINTAINED_FAIL" for v in verdicts):
        overall = "MAINTAINED_FAIL (both assets structurally regime-concentrated)"
    elif any(v == "MAINTAINED_FAIL" for v in verdicts):
        detail = " / ".join(f"{d.symbol}={d.step_verdict}" for d in diagnoses)
        overall = f"ASYMMETRIC ({detail})"
    else:
        detail = " / ".join(f"{d.symbol}={d.step_verdict}" for d in diagnoses)
        overall = f"INFORMATIVE ({detail})"

    lines.append(f"**C-3 Overall:** {overall}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run_diagnosis():
    print("=" * 60)
    print("Phase C C-3 — R-track Regime Diversity Diagnosis")
    print("=" * 60)
    print(f"RDS threshold: {RDS_THRESHOLD}")
    print(f"Assets: {ASSETS}")

    diagnoses: list[AssetRegimeDiagnosis] = []

    async with async_session_factory() as session:
        for symbol in ASSETS:
            diag = await diagnose_asset(session, symbol)
            diagnoses.append(diag)

    # Cross-asset asymmetry
    asymmetry = compute_asset_asymmetry(diagnoses[0], diagnoses[1])

    print(f"\n{'='*60}")
    print("ASSET REGIME ASYMMETRY")
    print(f"{'='*60}")
    for cmp in asymmetry:
        if cmp.delta > 0.01:
            mark = " ** ASYMMETRIC" if cmp.asymmetric else ""
            print(f"  {cmp.regime}: SOL={cmp.sol_share:.1%} BTC={cmp.btc_share:.1%} "
                  f"delta={cmp.delta:.1%}{mark}")

    # Generate report
    print(f"\n{'='*60}")
    print("DELIVERABLES")
    print(f"{'='*60}\n")

    report = generate_report(diagnoses, asymmetry)
    print(report)

    # Save JSON log
    class _NumpyEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, (np.bool_,)):
                return bool(obj)
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                return float(obj)
            return super().default(obj)

    log_data = {
        "diagnosis_at": datetime.now(timezone.utc).isoformat(),
        "phase": "C",
        "step": "C-3",
        "track": "R-track",
        "rds_threshold": RDS_THRESHOLD,
        "total_bars": TOTAL_BARS,
        "assets": {},
    }

    for diag in diagnoses:
        asset_data = {
            "symbol": diag.symbol,
            "total_bars": diag.total_bars,
            "global_rds": float(diag.global_rds),
            "global_dominant_regime": diag.global_dominant_regime,
            "global_dominant_share": float(diag.global_dominant_share),
            "global_effective_regime_count": diag.global_effective_regime_count,
            "regime_blank_zone_count": diag.regime_blank_zone_count,
            "regime_blank_zones": diag.regime_blank_zones,
            "rds_pass": bool(diag.rds_pass),
            "step_verdict": diag.step_verdict,
            "global_regime_bars": {k: int(v) for k, v in diag.global_regime_bars.items()},
            "global_regime_shares": {k: float(v) for k, v in diag.global_regime_shares.items()},
            "segments": {},
            "regime_trade_stats": {},
        }

        for sp in diag.segment_profiles:
            asset_data["segments"][sp.segment_name] = {
                "total_bars": sp.total_bars,
                "rds": float(sp.rds),
                "dominant_regime": sp.dominant_regime,
                "dominant_share": float(sp.dominant_share),
                "effective_regime_count": sp.effective_regime_count,
                "regime_bars": {k: int(v) for k, v in sp.regime_bars.items()},
                "regime_shares": {k: float(v) for k, v in sp.regime_shares.items()},
            }

        for rts in diag.regime_trade_stats:
            asset_data["regime_trade_stats"][rts.regime] = {
                "trade_count": rts.trade_count,
                "trade_share": float(rts.trade_share),
                "win_count": rts.win_count,
                "loss_count": rts.loss_count,
                "win_rate": float(rts.win_rate),
                "total_return_pct": float(rts.total_return_pct),
            }

        log_data["assets"][diag.symbol] = asset_data

    # Asset asymmetry
    log_data["asset_asymmetry"] = {}
    for cmp in asymmetry:
        log_data["asset_asymmetry"][cmp.regime] = {
            "sol_share": float(cmp.sol_share),
            "btc_share": float(cmp.btc_share),
            "delta": float(cmp.delta),
            "asymmetric": bool(cmp.asymmetric),
        }

    # Overall verdict
    verdicts = [d.step_verdict for d in diagnoses]
    if all(v == "PASS" for v in verdicts):
        log_data["overall_verdict"] = "PASS"
    elif all(v == "MAINTAINED_FAIL" for v in verdicts):
        log_data["overall_verdict"] = "MAINTAINED_FAIL"
    elif any(v == "MAINTAINED_FAIL" for v in verdicts):
        log_data["overall_verdict"] = "ASYMMETRIC"
    else:
        log_data["overall_verdict"] = "INFORMATIVE"

    log_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "docs", "operations", "evidence",
        "phase_c_c3_rtrack_diagnosis_log.json",
    )
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False, cls=_NumpyEncoder)
    print(f"\n[LOG] Saved: {log_path}")


def main():
    asyncio.run(run_diagnosis())


if __name__ == "__main__":
    main()
