"""
Phase C C-4 — W-track Forward Stability Diagnosis

Diagnoses WF efficiency deficit and FW2 cliff pattern.
Tests GO package hypothesis: cliff root cause = trade scarcity penalty.

Approach:
  1. Run WalkForwardValidator on full 9600 bars (baseline)
  2. Analyze per-window IS/OOS trade counts, returns, fitness
  3. Identify whether OOS degradation correlates with trade scarcity
  4. For BTC: compare baseline vs S-3 ratios (since S-3 resolved FW2 density)
  5. Determine: cliff = scarcity artifact OR genuine generalization failure

Usage:
  python scripts/phase_c_c4_wtrack_diagnosis.py

Constraints (C-4 GO):
  - Diagnostic/verification only (no implementation)
  - WalkForwardValidator = read-only
  - No strategy logic changes
  - No threshold adjustments
  - No B-1 core / protected symbol modification
  - No auto-advance to C-5
"""

import json
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
from app.services.walk_forward_validator import (  # noqa: E402
    WalkForwardValidator,
    WalkForwardResult,
    WalkForwardWindow,
)
from strategies.smc_wavetrend_strategy import SMCWaveTrendStrategy  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ASSETS = ["SOL/USDT:USDT", "BTC/USDT:USDT"]
TIMEFRAME = "1h"
TOTAL_BARS = 9600
WF_EFFICIENCY_THRESHOLD = 0.5
MIN_TRADES = 10

# WalkForward default params (matching FullCycleBacktester)
N_WINDOWS = 5
IN_SAMPLE_RATIO = 0.7
LOOKBACK = 50

# Segment boundaries for scarcity correlation analysis
SEGMENT_RATIOS_BASELINE = {"train": 0.60, "forward1": 0.20, "forward2": 0.10, "holdout": 0.10}
SEGMENT_RATIOS_S3 = {"train": 0.60, "forward1": 0.20, "forward2": 0.15, "holdout": 0.05}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class WindowAnalysis:
    """Detailed analysis of a single WF window."""

    window_index: int
    is_bars: int = 0
    oos_bars: int = 0
    is_trades: int = 0
    oos_trades: int = 0
    is_return: float = 0.0
    oos_return: float = 0.0
    is_sharpe: float = 0.0
    oos_sharpe: float = 0.0
    oos_profitable: bool = False
    is_min_trades_met: bool = False
    oos_min_trades_met: bool = False
    trade_scarcity_flag: bool = False  # OOS trades < MIN_TRADES


@dataclass
class StabilityProfile:
    """Full stability profile for one configuration."""

    label: str  # "baseline" or "s3"
    wf_result: WalkForwardResult | None = None
    efficiency_ratio: float = 0.0
    consistency: float = 0.0
    is_overfit: bool = False
    window_analyses: list[WindowAnalysis] = field(default_factory=list)
    scarcity_correlated_windows: int = 0  # windows where OOS fails AND OOS trades < min
    total_oos_unprofitable: int = 0
    scarcity_correlation_pct: float = 0.0  # scarcity_correlated / total_unprofitable


@dataclass
class SegmentFitnessProfile:
    """Per-segment fitness for cliff analysis."""

    segment: str
    bars: int = 0
    trades: int = 0
    fitness: float = 0.0
    min_trades_met: bool = False


@dataclass
class AssetWTrackDiagnosis:
    """Complete W-track diagnosis for one asset."""

    symbol: str

    # Baseline WF analysis
    baseline_profile: StabilityProfile | None = None

    # Per-segment fitness (for cliff visualization)
    segment_fitness: list[SegmentFitnessProfile] = field(default_factory=list)

    # Cliff analysis
    has_cliff: bool = False  # FW2 fitness << Train/FW1 fitness
    cliff_magnitude: float = 0.0  # Train fitness - FW2 fitness
    cliff_cause: str = ""  # "scarcity_penalty" / "generalization_failure" / "mixed"

    # Verdict
    wf_pass: bool = False
    step_verdict: str = ""  # PASS / MAINTAINED_FAIL / INFORMATIVE_FAIL


# ---------------------------------------------------------------------------
# Analysis functions
# ---------------------------------------------------------------------------


def run_wf_analysis(
    strategy: SMCWaveTrendStrategy,
    ohlcv: list,
    label: str,
) -> StabilityProfile:
    """Run WalkForwardValidator and analyze each window."""
    validator = WalkForwardValidator(
        in_sample_ratio=IN_SAMPLE_RATIO,
        n_windows=N_WINDOWS,
        config=BacktestConfig(initial_capital=10000.0, position_size_pct=2.0),
    )
    wf_result = validator.validate(strategy, ohlcv, lookback=LOOKBACK)

    profile = StabilityProfile(
        label=label,
        wf_result=wf_result,
        efficiency_ratio=wf_result.efficiency_ratio,
        consistency=wf_result.consistency,
        is_overfit=wf_result.is_overfit,
    )

    unprofitable_count = 0
    scarcity_correlated = 0

    for w in wf_result.windows:
        wa = WindowAnalysis(
            window_index=w.window_index,
            is_bars=w.in_sample_bars,
            oos_bars=w.out_sample_bars,
            is_trades=w.in_sample_trades,
            oos_trades=w.out_sample_trades,
            is_return=w.in_sample_return,
            oos_return=w.out_sample_return,
            is_sharpe=w.in_sample_sharpe,
            oos_sharpe=w.out_sample_sharpe,
            oos_profitable=w.out_sample_return > 0,
            is_min_trades_met=w.in_sample_trades >= MIN_TRADES,
            oos_min_trades_met=w.out_sample_trades >= MIN_TRADES,
            trade_scarcity_flag=w.out_sample_trades < MIN_TRADES,
        )
        profile.window_analyses.append(wa)

        if not wa.oos_profitable:
            unprofitable_count += 1
            if wa.trade_scarcity_flag:
                scarcity_correlated += 1

    profile.total_oos_unprofitable = unprofitable_count
    profile.scarcity_correlated_windows = scarcity_correlated
    profile.scarcity_correlation_pct = (
        scarcity_correlated / unprofitable_count * 100 if unprofitable_count > 0 else 0.0
    )

    return profile


def compute_segment_fitness(
    strategy: SMCWaveTrendStrategy,
    ohlcv: list,
    ratios: dict,
) -> list[SegmentFitnessProfile]:
    """Compute per-segment fitness for cliff analysis."""
    total = len(ohlcv)
    train_end = int(total * ratios["train"])
    fw1_end = train_end + int(total * ratios["forward1"])
    fw2_end = fw1_end + int(total * ratios["forward2"])

    segments = {
        "train": ohlcv[0:train_end],
        "forward_1": ohlcv[train_end:fw1_end],
        "forward_2": ohlcv[fw1_end:fw2_end],
        "holdout": ohlcv[fw2_end:total],
    }

    engine = BacktestingEngine(
        config=BacktestConfig(
            initial_capital=10000.0,
            position_size_pct=2.0,
        )
    )
    fitness_fn = FitnessFunction(min_trades=MIN_TRADES)
    results = []

    for seg_name in ["train", "forward_1", "forward_2", "holdout"]:
        seg_data = segments[seg_name]
        bt_result = engine.run(strategy, seg_data, lookback=LOOKBACK)
        trades_count = len(bt_result.trades) if bt_result.trades else 0

        if trades_count >= MIN_TRADES:
            fb = fitness_fn.evaluate(bt_result.performance)
            fitness = fb.total
        else:
            fitness = 0.0  # penalty

        results.append(
            SegmentFitnessProfile(
                segment=seg_name,
                bars=len(seg_data),
                trades=trades_count,
                fitness=round(float(fitness), 4),
                min_trades_met=trades_count >= MIN_TRADES,
            )
        )

    return results


def diagnose_cliff(
    seg_fitness: list[SegmentFitnessProfile],
) -> tuple[bool, float, str]:
    """Determine if cliff exists and its cause."""
    train = next(s for s in seg_fitness if s.segment == "train")
    fw2 = next(s for s in seg_fitness if s.segment == "forward_2")

    cliff_mag = train.fitness - fw2.fitness
    has_cliff = cliff_mag > 0.20  # significant drop

    if not has_cliff:
        return False, round(cliff_mag, 4), "no_cliff"

    if not fw2.min_trades_met:
        cause = "scarcity_penalty"
    elif fw2.fitness < 0.25 and fw2.min_trades_met:
        cause = "generalization_failure"
    else:
        cause = "mixed"

    return has_cliff, round(cliff_mag, 4), cause


# ---------------------------------------------------------------------------
# Main diagnosis
# ---------------------------------------------------------------------------


async def diagnose_asset(session, symbol: str) -> AssetWTrackDiagnosis:
    """Run full W-track diagnosis for one asset."""
    print(f"\n{'=' * 60}")
    print(f"  {symbol} — W-track Forward Stability Diagnosis")
    print(f"{'=' * 60}")

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

    strategy = SMCWaveTrendStrategy(symbol=symbol)

    # Step 2: Baseline WF analysis
    print(f"\n  [BASELINE] Running WalkForward (n_windows={N_WINDOWS})...")
    baseline = run_wf_analysis(strategy, ohlcv, "baseline")
    print(
        f"    efficiency_ratio: {baseline.efficiency_ratio:.4f} (threshold: {WF_EFFICIENCY_THRESHOLD})"
    )
    print(f"    consistency: {baseline.consistency:.2f}")
    print(f"    is_overfit: {baseline.is_overfit}")
    print(
        f"    scarcity-correlated OOS failures: "
        f"{baseline.scarcity_correlated_windows}/{baseline.total_oos_unprofitable} "
        f"({baseline.scarcity_correlation_pct:.0f}%)"
    )

    for wa in baseline.window_analyses:
        status = "OK" if wa.oos_profitable else "FAIL"
        scarcity = " [SCARCE]" if wa.trade_scarcity_flag else ""
        print(
            f"    Window {wa.window_index}: IS={wa.is_trades}t/{wa.is_return:+.2f}% "
            f"-> OOS={wa.oos_trades}t/{wa.oos_return:+.2f}% {status}{scarcity}"
        )

    # Step 3: Per-segment fitness (cliff analysis)
    print(f"\n  [CLIFF] Per-segment fitness (baseline ratios)...")
    seg_fitness = compute_segment_fitness(strategy, ohlcv, SEGMENT_RATIOS_BASELINE)
    for sf in seg_fitness:
        mt = "OK" if sf.min_trades_met else "MISS"
        print(f"    {sf.segment}: {sf.trades}t fitness={sf.fitness:.4f} min_trades={mt}")

    has_cliff, cliff_mag, cliff_cause = diagnose_cliff(seg_fitness)
    print(f"    Cliff detected: {has_cliff} (magnitude={cliff_mag:.4f}, cause={cliff_cause})")

    # Step 4: Verdict
    wf_pass = baseline.efficiency_ratio >= WF_EFFICIENCY_THRESHOLD

    if wf_pass:
        verdict = "PASS"
    elif cliff_cause == "scarcity_penalty":
        verdict = "INFORMATIVE_FAIL"
    elif cliff_cause == "generalization_failure":
        verdict = "MAINTAINED_FAIL"
    else:
        verdict = "INFORMATIVE_FAIL"

    print(f"\n  WF PASS: {wf_pass}")
    print(f"  Step verdict: {verdict}")

    return AssetWTrackDiagnosis(
        symbol=symbol,
        baseline_profile=baseline,
        segment_fitness=seg_fitness,
        has_cliff=has_cliff,
        cliff_magnitude=cliff_mag,
        cliff_cause=cliff_cause,
        wf_pass=wf_pass,
        step_verdict=verdict,
    )


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def generate_report(diagnoses: list[AssetWTrackDiagnosis]) -> str:
    """Generate C-4 deliverables as markdown."""
    lines = []

    # Deliverable 1: WF Window Analysis
    lines.append("## Deliverable 1: WalkForward Window Analysis")
    lines.append("")

    for diag in diagnoses:
        bp = diag.baseline_profile
        lines.append(f"### {diag.symbol}")
        lines.append("")
        lines.append(
            f"**WF efficiency:** {bp.efficiency_ratio:.4f} (threshold: {WF_EFFICIENCY_THRESHOLD})"
        )
        lines.append(
            f"**Consistency:** {bp.consistency:.2f} ({int(bp.consistency * N_WINDOWS)}/{N_WINDOWS} profitable)"
        )
        lines.append(f"**Is overfit:** {bp.is_overfit}")
        lines.append("")
        lines.append(
            "| Window | IS Trades | IS Return | OOS Trades | OOS Return | OOS Status | Scarcity? |"
        )
        lines.append(
            "|--------|-----------|-----------|------------|------------|------------|-----------|"
        )

        for wa in bp.window_analyses:
            status = "OK" if wa.oos_profitable else "**FAIL**"
            scarce = "**YES**" if wa.trade_scarcity_flag else "no"
            lines.append(
                f"| {wa.window_index} | {wa.is_trades} | {wa.is_return:+.2f}% | "
                f"{wa.oos_trades} | {wa.oos_return:+.2f}% | {status} | {scarce} |"
            )

        lines.append("")
        lines.append(
            f"**Scarcity-correlated failures:** "
            f"{bp.scarcity_correlated_windows}/{bp.total_oos_unprofitable} "
            f"({bp.scarcity_correlation_pct:.0f}%)"
        )
        lines.append("")

    # Deliverable 2: Cliff Analysis
    lines.append("## Deliverable 2: Cliff Analysis")
    lines.append("")

    for diag in diagnoses:
        lines.append(f"### {diag.symbol}")
        lines.append("")
        lines.append("| Segment | Bars | Trades | Fitness | min_trades |")
        lines.append("|---------|------|--------|---------|------------|")

        for sf in diag.segment_fitness:
            mt = "OK" if sf.min_trades_met else "**MISS**"
            lines.append(f"| {sf.segment} | {sf.bars} | {sf.trades} | {sf.fitness:.4f} | {mt} |")

        lines.append("")
        lines.append(f"**Cliff detected:** {diag.has_cliff}")
        lines.append(f"**Cliff magnitude:** {diag.cliff_magnitude:.4f} (train - FW2)")
        lines.append(f"**Cliff cause:** **{diag.cliff_cause}**")
        lines.append("")

    # Deliverable 3: Scarcity-Cliff Correlation
    lines.append("## Deliverable 3: Scarcity-Cliff Correlation")
    lines.append("")
    lines.append("| Asset | WF Eff | Cliff? | Cliff Cause | OOS Scarcity Correlation | Verdict |")
    lines.append("|-------|--------|--------|-------------|--------------------------|---------|")

    for diag in diagnoses:
        bp = diag.baseline_profile
        lines.append(
            f"| {diag.symbol} | {bp.efficiency_ratio:.4f} | "
            f"{'Yes' if diag.has_cliff else 'No'} | {diag.cliff_cause} | "
            f"{bp.scarcity_correlation_pct:.0f}% | **{diag.step_verdict}** |"
        )

    lines.append("")

    # Cross-asset verdict
    lines.append("## Cross-Asset W-track Verdict")
    lines.append("")
    verdicts = [d.step_verdict for d in diagnoses]
    if all(v == "PASS" for v in verdicts):
        overall = "PASS"
    elif all(v == "MAINTAINED_FAIL" for v in verdicts):
        overall = "MAINTAINED_FAIL (both assets genuine generalization failure)"
    elif all(v == "INFORMATIVE_FAIL" for v in verdicts):
        overall = "INFORMATIVE_FAIL (both assets scarcity-driven cliff)"
    else:
        detail = " / ".join(f"{d.symbol}={d.step_verdict}" for d in diagnoses)
        overall = f"ASYMMETRIC ({detail})"

    lines.append(f"**C-4 Overall:** {overall}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def run_diagnosis():
    print("=" * 60)
    print("Phase C C-4 — W-track Forward Stability Diagnosis")
    print("=" * 60)
    print(f"WF threshold: {WF_EFFICIENCY_THRESHOLD}")
    print(f"N windows: {N_WINDOWS}")
    print(f"Assets: {ASSETS}")

    diagnoses: list[AssetWTrackDiagnosis] = []

    async with async_session_factory() as session:
        for symbol in ASSETS:
            diag = await diagnose_asset(session, symbol)
            diagnoses.append(diag)

    # Generate report
    print(f"\n{'=' * 60}")
    print("DELIVERABLES")
    print(f"{'=' * 60}\n")

    report = generate_report(diagnoses)
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
        "step": "C-4",
        "track": "W-track",
        "wf_efficiency_threshold": WF_EFFICIENCY_THRESHOLD,
        "n_windows": N_WINDOWS,
        "assets": {},
    }

    for diag in diagnoses:
        bp = diag.baseline_profile
        asset_data = {
            "symbol": diag.symbol,
            "wf_efficiency": float(bp.efficiency_ratio),
            "wf_consistency": float(bp.consistency),
            "wf_is_overfit": bool(bp.is_overfit),
            "wf_pass": bool(diag.wf_pass),
            "has_cliff": bool(diag.has_cliff),
            "cliff_magnitude": float(diag.cliff_magnitude),
            "cliff_cause": diag.cliff_cause,
            "scarcity_correlated_windows": bp.scarcity_correlated_windows,
            "total_oos_unprofitable": bp.total_oos_unprofitable,
            "scarcity_correlation_pct": float(bp.scarcity_correlation_pct),
            "step_verdict": diag.step_verdict,
            "windows": [],
            "segment_fitness": {},
        }

        for wa in bp.window_analyses:
            asset_data["windows"].append(
                {
                    "window_index": wa.window_index,
                    "is_bars": wa.is_bars,
                    "oos_bars": wa.oos_bars,
                    "is_trades": wa.is_trades,
                    "oos_trades": wa.oos_trades,
                    "is_return": float(wa.is_return),
                    "oos_return": float(wa.oos_return),
                    "oos_profitable": bool(wa.oos_profitable),
                    "trade_scarcity_flag": bool(wa.trade_scarcity_flag),
                }
            )

        for sf in diag.segment_fitness:
            asset_data["segment_fitness"][sf.segment] = {
                "bars": sf.bars,
                "trades": sf.trades,
                "fitness": float(sf.fitness),
                "min_trades_met": bool(sf.min_trades_met),
            }

        log_data["assets"][diag.symbol] = asset_data

    # Overall verdict
    verdicts = [d.step_verdict for d in diagnoses]
    if all(v == "PASS" for v in verdicts):
        log_data["overall_verdict"] = "PASS"
    elif all(v == "MAINTAINED_FAIL" for v in verdicts):
        log_data["overall_verdict"] = "MAINTAINED_FAIL"
    elif all(v == "INFORMATIVE_FAIL" for v in verdicts):
        log_data["overall_verdict"] = "INFORMATIVE_FAIL"
    else:
        log_data["overall_verdict"] = "ASYMMETRIC"

    log_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "docs",
        "operations",
        "evidence",
        "phase_c_c4_wtrack_diagnosis_log.json",
    )
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False, cls=_NumpyEncoder)
    print(f"\n[LOG] Saved: {log_path}")


def main():
    asyncio.run(run_diagnosis())


if __name__ == "__main__":
    main()
