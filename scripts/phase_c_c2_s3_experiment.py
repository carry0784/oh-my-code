"""
Phase C C-2 — S-3 Density Uplift Experiment

FW2 ratio 10% -> 15% adjustment to test if larger FW2 segment
yields enough trades to meet min_trades(10).

This is NOT a root-cause fix. It is a low-blast density validation.

Usage:
  python scripts/phase_c_c2_s3_experiment.py

Constraints (C-2 LIMITED GO):
  - S-3 only (no S-1/S-2)
  - Shadow/paper only (no live)
  - No SMC/WT logic changes
  - No BacktestingEngine occupancy rule changes
  - No B-1 core / protected symbol modification
  - No auto-advance to C-3
"""

import json
import os
import sys
from dataclasses import dataclass
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
from app.services.full_cycle_backtester import (  # noqa: E402
    FullCycleBacktester,
    FullCycleConfig,
    FullCycleResult,
)
from strategies.smc_wavetrend_strategy import SMCWaveTrendStrategy  # noqa: E402

# ---------------------------------------------------------------------------
# Experiment configurations
# ---------------------------------------------------------------------------

ASSETS = ["SOL/USDT:USDT", "BTC/USDT:USDT"]

# Baseline: B-2 original ratios (DO NOT MODIFY these constants)
BASELINE_RATIOS = {
    "train": 0.60,
    "forward1": 0.20,
    "forward2": 0.10,
    "holdout": 0.10,
}

# S-3 Experiment: FW2 expanded
# FW2: 10% -> 15%, Holdout: 10% -> 5%
# Train and FW1 unchanged
S3_RATIOS = {
    "train": 0.60,
    "forward1": 0.20,
    "forward2": 0.15,
    "holdout": 0.05,
}

MIN_TRADES = 10


# ---------------------------------------------------------------------------
# Result structures
# ---------------------------------------------------------------------------


@dataclass
class SegmentComparison:
    """Before/after comparison for one segment."""

    segment_name: str
    baseline_bars: int
    s3_bars: int
    baseline_trades: int
    s3_trades: int
    baseline_fitness: float
    s3_fitness: float
    baseline_min_trades_met: bool
    s3_min_trades_met: bool
    trade_uplift: int
    trade_uplift_pct: float
    fitness_delta: float


@dataclass
class AssetExperiment:
    """Full experiment result for one asset."""

    symbol: str
    baseline: FullCycleResult | None
    s3: FullCycleResult | None
    comparisons: list[SegmentComparison]
    density_uplift_pass: bool  # FW2 trades >= min_trades after S-3
    quality_hold: bool  # No fitness degradation in other segments
    step_verdict: str  # PASS / INFORMATIVE_FAIL / HOLD


# ---------------------------------------------------------------------------
# Run experiment
# ---------------------------------------------------------------------------


async def run_single(session, symbol: str, ratios: dict, label: str) -> FullCycleResult:
    """Run a full-cycle backtest with given ratios."""
    config = FullCycleConfig(
        exchange="binance",
        symbol=symbol,
        timeframe="1h",
        train_ratio=ratios["train"],
        forward1_ratio=ratios["forward1"],
        forward2_ratio=ratios["forward2"],
        holdout_ratio=ratios["holdout"],
    )
    errors = config.validate()
    if errors:
        print(f"  [ERROR] Config validation failed: {errors}")
        raise ValueError(f"Config errors: {errors}")

    strategy = SMCWaveTrendStrategy(symbol=symbol)
    backtester = FullCycleBacktester(config=config)
    result = await backtester.run(session, strategy)
    print(f"  [{label}] verdict={result.verdict} overall_fitness={result.overall_fitness:.4f}")

    # Diagnostic: verify segment bar counts match expected ratios
    for seg_name, seg in result.segments.items():
        trades_n = len(seg.backtest.trades) if seg.backtest and seg.backtest.trades else 0
        print(
            f"    {seg_name}: bars={seg.bars} effective={seg.effective_bars} "
            f"trades={trades_n} fitness={seg.fitness.total:.4f}"
        )

    return result


def extract_segment_trades(result: FullCycleResult, segment_name: str) -> int:
    """Get trade count from a segment result.

    result.segments is dict[str, SegmentResult].
    """
    seg = result.segments.get(segment_name)
    if seg is None:
        return 0
    if seg.backtest and seg.backtest.trades is not None:
        return len(seg.backtest.trades)
    return 0


def extract_segment_fitness(result: FullCycleResult, segment_name: str) -> float:
    """Get fitness from a segment result.

    seg.fitness is FitnessBreakdown (dataclass with .total field).
    """
    seg = result.segments.get(segment_name)
    if seg is None:
        return 0.0
    if seg.fitness is not None:
        return seg.fitness.total if hasattr(seg.fitness, "total") else float(seg.fitness)
    return 0.0


def extract_segment_bars(result: FullCycleResult, segment_name: str) -> int:
    """Get bar count from a segment result."""
    seg = result.segments.get(segment_name)
    if seg is None:
        return 0
    return seg.bars


def compare_results(
    symbol: str,
    baseline: FullCycleResult,
    s3: FullCycleResult,
) -> AssetExperiment:
    """Compare baseline vs S-3 results for one asset."""
    comparisons = []
    segments = ["train", "forward_1", "forward_2", "holdout"]

    for seg_name in segments:
        b_trades = extract_segment_trades(baseline, seg_name)
        s_trades = extract_segment_trades(s3, seg_name)
        b_fitness = extract_segment_fitness(baseline, seg_name)
        s_fitness = extract_segment_fitness(s3, seg_name)
        b_bars = extract_segment_bars(baseline, seg_name)
        s_bars = extract_segment_bars(s3, seg_name)

        uplift = s_trades - b_trades
        uplift_pct = (
            (uplift / b_trades * 100) if b_trades > 0 else (float("inf") if s_trades > 0 else 0.0)
        )

        comparisons.append(
            SegmentComparison(
                segment_name=seg_name,
                baseline_bars=b_bars,
                s3_bars=s_bars,
                baseline_trades=b_trades,
                s3_trades=s_trades,
                baseline_fitness=b_fitness,
                s3_fitness=s_fitness,
                baseline_min_trades_met=b_trades >= MIN_TRADES,
                s3_min_trades_met=s_trades >= MIN_TRADES,
                trade_uplift=uplift,
                trade_uplift_pct=round(uplift_pct, 1),
                fitness_delta=round(s_fitness - b_fitness, 4),
            )
        )

    # FW2 specific check
    fw2_comp = next(c for c in comparisons if c.segment_name == "forward_2")
    density_pass = fw2_comp.s3_min_trades_met

    # Quality hold: train and FW1 fitness should not degrade significantly
    train_comp = next(c for c in comparisons if c.segment_name == "train")
    fw1_comp = next(c for c in comparisons if c.segment_name == "forward_1")
    quality_hold = (
        train_comp.fitness_delta >= -0.05  # Allow 5% tolerance
        and fw1_comp.fitness_delta >= -0.05
    )

    # Step verdict
    if density_pass and quality_hold:
        verdict = "PASS"
    elif not density_pass and quality_hold:
        verdict = "INFORMATIVE_FAIL"
    elif not quality_hold:
        verdict = "HOLD"
    else:
        verdict = "INFORMATIVE_FAIL"

    return AssetExperiment(
        symbol=symbol,
        baseline=baseline,
        s3=s3,
        comparisons=comparisons,
        density_uplift_pass=density_pass,
        quality_hold=quality_hold,
        step_verdict=verdict,
    )


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def generate_report(experiments: list[AssetExperiment]) -> str:
    """Generate C-2 deliverables as markdown."""
    lines = []

    # Deliverable 1: Change scope attestation
    lines.append("## Deliverable 1: 변경 범위 증빙")
    lines.append("")
    lines.append("| 항목 | Baseline | S-3 | 변경 |")
    lines.append("|------|----------|-----|------|")
    lines.append(
        f"| train_ratio | {BASELINE_RATIOS['train']:.2f} | {S3_RATIOS['train']:.2f} | 미변경 |"
    )
    lines.append(
        f"| forward1_ratio | {BASELINE_RATIOS['forward1']:.2f} | {S3_RATIOS['forward1']:.2f} | 미변경 |"
    )
    lines.append(
        f"| forward2_ratio | {BASELINE_RATIOS['forward2']:.2f} | {S3_RATIOS['forward2']:.2f} | **+0.05** |"
    )
    lines.append(
        f"| holdout_ratio | {BASELINE_RATIOS['holdout']:.2f} | {S3_RATIOS['holdout']:.2f} | **-0.05** |"
    )
    lines.append("")
    lines.append("**B-1 core 수정:** 없음 (FullCycleConfig 인스턴스 값만 변경, dataclass 미수정)")
    lines.append("**Protected symbol 수정:** 없음")
    lines.append("**SMC/WT 로직 수정:** 없음")
    lines.append("")

    # Deliverable 2: Before/after density comparison
    lines.append("## Deliverable 2: Before/After Density 비교표")
    lines.append("")

    for exp in experiments:
        lines.append(f"### {exp.symbol}")
        lines.append("")
        lines.append(
            "| Segment | Bars (B/S3) | Trades (B/S3) | Fitness (B/S3) | Uplift | min_trades | Delta |"
        )
        lines.append(
            "|---------|-------------|---------------|----------------|--------|------------|-------|"
        )

        for c in exp.comparisons:
            b_mt = "OK" if c.baseline_min_trades_met else "MISS"
            s_mt = "OK" if c.s3_min_trades_met else "MISS"
            sign = "+" if c.fitness_delta >= 0 else ""
            lines.append(
                f"| {c.segment_name} | {c.baseline_bars}/{c.s3_bars} "
                f"| {c.baseline_trades}/{c.s3_trades} "
                f"| {c.baseline_fitness:.4f}/{c.s3_fitness:.4f} "
                f"| {'+' if c.trade_uplift >= 0 else ''}{c.trade_uplift} ({'+' if c.trade_uplift_pct >= 0 else ''}{c.trade_uplift_pct}%) "
                f"| {b_mt}/{s_mt} "
                f"| {sign}{c.fitness_delta:.4f} |"
            )

        lines.append("")

        # Verdict-level comparison
        b_verdict = exp.baseline.verdict if exp.baseline else "N/A"
        s_verdict = exp.s3.verdict if exp.s3 else "N/A"
        b_overall = exp.baseline.overall_fitness if exp.baseline else 0
        s_overall = exp.s3.overall_fitness if exp.s3 else 0
        b_rds = exp.baseline.regime_diversity_score if exp.baseline else 0
        s_rds = exp.s3.regime_diversity_score if exp.s3 else 0

        lines.append(f"**Verdict:** {b_verdict} -> {s_verdict}")
        lines.append(f"**Overall fitness:** {b_overall:.4f} -> {s_overall:.4f}")
        lines.append(f"**RDS:** {b_rds:.4f} -> {s_rds:.4f}")
        lines.append(f"**Density PASS:** {exp.density_uplift_pass}")
        lines.append(f"**Quality hold:** {exp.quality_hold}")
        lines.append(f"**Step verdict:** **{exp.step_verdict}**")
        lines.append("")

    # Deliverable 3: Quality maintenance table
    lines.append("## Deliverable 3: Quality 유지 판정표")
    lines.append("")
    lines.append("| Asset | Train Delta | FW1 Delta | Quality Hold | Density PASS | Step Verdict |")
    lines.append("|-------|-------------|-----------|--------------|--------------|--------------|")

    for exp in experiments:
        train_d = next(c for c in exp.comparisons if c.segment_name == "train")
        fw1_d = next(c for c in exp.comparisons if c.segment_name == "forward_1")
        lines.append(
            f"| {exp.symbol} | {train_d.fitness_delta:+.4f} | {fw1_d.fitness_delta:+.4f} "
            f"| {exp.quality_hold} | {exp.density_uplift_pass} | **{exp.step_verdict}** |"
        )

    lines.append("")

    # Cross-asset summary
    lines.append("## Cross-Asset 종합")
    lines.append("")
    verdicts = [exp.step_verdict for exp in experiments]
    if all(v == "PASS" for v in verdicts):
        overall = "PASS (양심볼 density uplift + quality hold)"
    elif any(v == "HOLD" for v in verdicts):
        overall = "HOLD (quality degradation detected)"
    elif all(v == "INFORMATIVE_FAIL" for v in verdicts):
        overall = "INFORMATIVE_FAIL (양심볼 density uplift 부족)"
    else:
        detail = " / ".join(f"{e.symbol}={e.step_verdict}" for e in experiments)
        overall = f"ASYMMETRIC ({detail})"
    lines.append(f"**C-2 Overall:** {overall}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def run_experiment():
    print("=" * 60)
    print("Phase C C-2 — S-3 Density Uplift Experiment")
    print("=" * 60)
    print()
    print(f"Baseline ratios: {BASELINE_RATIOS}")
    print(f"S-3 ratios:      {S3_RATIOS}")
    print()

    experiments: list[AssetExperiment] = []

    async with async_session_factory() as session:
        for symbol in ASSETS:
            print(f"--- {symbol} ---")

            # Baseline run (original ratios)
            print(f"  Running BASELINE...")
            baseline = await run_single(session, symbol, BASELINE_RATIOS, "BASELINE")

            # S-3 run (FW2 expanded)
            print(f"  Running S-3...")
            s3 = await run_single(session, symbol, S3_RATIOS, "S-3")

            # Compare
            exp = compare_results(symbol, baseline, s3)
            experiments.append(exp)
            print(f"  Step verdict: {exp.step_verdict}")
            print()

    # Generate report
    print("=" * 60)
    print("DELIVERABLES")
    print("=" * 60)
    print()

    report = generate_report(experiments)
    print(report)

    # Save JSON log
    log_data = {
        "experiment_at": datetime.now(timezone.utc).isoformat(),
        "phase": "C",
        "step": "C-2",
        "track": "S-track",
        "candidate": "S-3",
        "baseline_ratios": BASELINE_RATIOS,
        "s3_ratios": S3_RATIOS,
        "assets": {},
    }

    for exp in experiments:
        asset_data = {
            "symbol": exp.symbol,
            "step_verdict": exp.step_verdict,
            "density_uplift_pass": bool(exp.density_uplift_pass),
            "quality_hold": bool(exp.quality_hold),
            "baseline_verdict": exp.baseline.verdict if exp.baseline else None,
            "s3_verdict": exp.s3.verdict if exp.s3 else None,
            "baseline_overall_fitness": float(exp.baseline.overall_fitness)
            if exp.baseline
            else None,
            "s3_overall_fitness": float(exp.s3.overall_fitness) if exp.s3 else None,
            "segments": {},
        }
        for c in exp.comparisons:
            asset_data["segments"][c.segment_name] = {
                "baseline_bars": c.baseline_bars,
                "s3_bars": c.s3_bars,
                "baseline_trades": c.baseline_trades,
                "s3_trades": c.s3_trades,
                "baseline_fitness": c.baseline_fitness,
                "s3_fitness": c.s3_fitness,
                "trade_uplift": c.trade_uplift,
                "trade_uplift_pct": c.trade_uplift_pct,
                "fitness_delta": c.fitness_delta,
                "baseline_min_trades_met": bool(c.baseline_min_trades_met),
                "s3_min_trades_met": bool(c.s3_min_trades_met),
            }
        log_data["assets"][exp.symbol] = asset_data

    log_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "docs",
        "operations",
        "evidence",
        "phase_c_c2_s3_experiment_log.json",
    )

    class _NumpyEncoder(json.JSONEncoder):
        """Handle numpy types in JSON serialization."""

        def default(self, obj):
            if isinstance(obj, (np.bool_,)):
                return bool(obj)
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                return float(obj)
            return super().default(obj)

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False, cls=_NumpyEncoder)
    print(f"\n[LOG] Saved: {log_path}")


def main():
    asyncio.run(run_experiment())


if __name__ == "__main__":
    main()
