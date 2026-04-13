"""
Phase B Full-Cycle Smoke + Diagnostic Script (B-3)

Purpose: Diagnostic/observation layer — NOT strategy modification.
  - Runs FullCycleBacktester on SOL + BTC
  - Diagnoses B-2 FAIL root causes across 3 tracks:
    B-3A: Trade Scarcity
    B-3B: Regime Diversity
    B-3C: Forward Stability
  - Cross-asset comparison for failure signature isolation

Allowed by: phase_b_b3_go_receipt.md
Prohibited: core/strategy/threshold modification

Exit conditions:
  IMPROVED: 1+ FAIL cause measurably reduced, no regression elsewhere
  RESOLVED: all FAIL causes eliminated, verdict=PASS
  MAINTAINED_FAIL: structural limit confirmed, FAIL preserved (legitimate)

Usage:
  python -X utf8 scripts/phase_b_full_cycle_smoke.py
  python -X utf8 scripts/phase_b_full_cycle_smoke.py --symbol SOL/USDT:USDT
  python -X utf8 scripts/phase_b_full_cycle_smoke.py --symbol BTC/USDT:USDT
"""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

# ── Project imports ──────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import async_session_factory
from app.services.full_cycle_backtester import (
    FullCycleConfig,
    FullCycleBacktester,
    FullCycleResult,
    SegmentSplitter,
    SEGMENT_NAMES,
    TRAIN_FITNESS_THRESHOLD,
    FORWARD1_FITNESS_THRESHOLD,
    FORWARD2_FITNESS_THRESHOLD,
    WF_EFFICIENCY_THRESHOLD,
    RDS_THRESHOLD,
    W_TRAIN,
    W_FORWARD1,
    W_FORWARD2,
)
from app.services.history_data_manager import HistoryDataManager
from app.services.regime_detector import RegimeDetector
from strategies.smc_wavetrend_strategy import SMCWaveTrendStrategy

# ── Constants ────────────────────────────────────────────────────
EVIDENCE_DIR = Path(__file__).resolve().parent.parent / "docs" / "operations" / "evidence"
DIAGNOSIS_LOG_PATH = EVIDENCE_DIR / "phase_b_b3_diagnosis_log.json"

DEFAULT_SYMBOLS = ["SOL/USDT:USDT", "BTC/USDT:USDT"]
MIN_TRADES = 10  # FitnessFunction default


# ── Diagnostic Data Contracts ────────────────────────────────────


@dataclass
class ScarcityDiagnosis:
    """B-3A: Trade Scarcity analysis per symbol."""
    symbol: str = ""
    segment_trades: dict[str, int] = field(default_factory=dict)
    segment_trade_density: dict[str, float] = field(default_factory=dict)  # trades per 100 bars
    min_trades_miss: dict[str, bool] = field(default_factory=dict)
    total_trades: int = 0
    scarcity_level: str = "unknown"  # low / moderate / severe


@dataclass
class RegimeDiagnosis:
    """B-3B: Regime Diversity analysis per symbol."""
    symbol: str = ""
    global_rds: float = 0.0
    global_regime_mix: dict[str, float] = field(default_factory=dict)
    segment_rds: dict[str, float] = field(default_factory=dict)
    segment_regime_mix: dict[str, dict[str, float]] = field(default_factory=dict)
    dominant_regime: str = ""
    dominant_pct: float = 0.0
    regime_bias: str = "unknown"  # balanced / mild_bias / severe_bias


@dataclass
class StabilityDiagnosis:
    """B-3C: Forward Stability analysis per symbol."""
    symbol: str = ""
    segment_fitness: dict[str, float] = field(default_factory=dict)
    fitness_degradation: dict[str, float] = field(default_factory=dict)  # vs train
    wf_efficiency: float = 0.0
    wf_consistency: float = 0.0
    wf_is_overfit: bool = False
    overall_fitness: float = 0.0
    degradation_profile: str = "unknown"  # stable / gradual / cliff / erratic


@dataclass
class AssetDiagnosis:
    """Complete diagnostic for one asset."""
    symbol: str = ""
    verdict: str = ""
    reason_codes: list[str] = field(default_factory=list)
    pass_count: int = 0
    scarcity: ScarcityDiagnosis = field(default_factory=ScarcityDiagnosis)
    regime: RegimeDiagnosis = field(default_factory=RegimeDiagnosis)
    stability: StabilityDiagnosis = field(default_factory=StabilityDiagnosis)
    failure_signature: str = ""


@dataclass
class CrossAssetReport:
    """Cross-asset comparison report."""
    diagnosed_at: str = ""
    assets: dict[str, AssetDiagnosis] = field(default_factory=dict)
    common_failures: list[str] = field(default_factory=list)
    asset_specific_failures: dict[str, list[str]] = field(default_factory=dict)
    b3_exit_status: str = "PENDING"  # IMPROVED / RESOLVED / MAINTAINED_FAIL


# ── Diagnostic Functions ─────────────────────────────────────────


def diagnose_scarcity(result: FullCycleResult) -> ScarcityDiagnosis:
    """B-3A: Analyze trade scarcity per segment."""
    diag = ScarcityDiagnosis(symbol=result.config.symbol)

    total = 0
    for name in SEGMENT_NAMES:
        seg = result.segments.get(name)
        if not seg:
            continue
        trades = seg.backtest.performance.total_trades
        bars = seg.bars
        diag.segment_trades[name] = trades
        diag.segment_trade_density[name] = round(trades / bars * 100, 2) if bars > 0 else 0.0
        diag.min_trades_miss[name] = trades < MIN_TRADES
        total += trades

    diag.total_trades = total

    # Classify scarcity level
    miss_count = sum(1 for v in diag.min_trades_miss.values() if v)
    if miss_count == 0:
        diag.scarcity_level = "low"
    elif miss_count <= 1:
        diag.scarcity_level = "moderate"
    else:
        diag.scarcity_level = "severe"

    return diag


def diagnose_regime(
    result: FullCycleResult,
    ohlcv: list[list],
    segments: dict[str, list[list]],
) -> RegimeDiagnosis:
    """B-3B: Analyze regime diversity globally and per segment."""
    diag = RegimeDiagnosis(symbol=result.config.symbol)
    diag.global_rds = result.regime_diversity_score

    # Global regime mix from SegmentResult.regime_distribution aggregation
    # Use RegimeDetector directly for precise global counts
    detector = RegimeDetector()
    batch = detector.detect_batch(ohlcv)

    global_counts: dict[str, int] = {}
    total = 0
    for br in batch:
        global_counts[br.regime] = global_counts.get(br.regime, 0) + 1
        total += 1

    if total > 0:
        diag.global_regime_mix = {
            k: round(v / total, 4) for k, v in sorted(global_counts.items())
        }
        dominant = max(global_counts, key=global_counts.get)
        diag.dominant_regime = dominant
        diag.dominant_pct = round(global_counts[dominant] / total * 100, 1)

    # Per-segment regime from SegmentResult
    for name in SEGMENT_NAMES:
        seg = result.segments.get(name)
        if seg and seg.regime_distribution:
            diag.segment_regime_mix[name] = seg.regime_distribution
            # Compute per-segment RDS
            proportions = list(seg.regime_distribution.values())
            hhi = sum(p * p for p in proportions)
            diag.segment_rds[name] = round(1.0 - hhi, 4)

    # Classify bias
    if diag.global_rds >= RDS_THRESHOLD:
        diag.regime_bias = "balanced"
    elif diag.global_rds >= 0.40:
        diag.regime_bias = "mild_bias"
    else:
        diag.regime_bias = "severe_bias"

    return diag


def diagnose_stability(result: FullCycleResult) -> StabilityDiagnosis:
    """B-3C: Analyze forward stability and degradation."""
    diag = StabilityDiagnosis(symbol=result.config.symbol)

    train_fitness = 0.0
    for name in SEGMENT_NAMES:
        seg = result.segments.get(name)
        if not seg:
            continue
        fit = seg.fitness.total
        diag.segment_fitness[name] = round(fit, 4)
        if name == "train":
            train_fitness = fit

    # Degradation vs train
    for name in ("forward_1", "forward_2", "holdout"):
        seg_fit = diag.segment_fitness.get(name, 0.0)
        if train_fitness > 0:
            diag.fitness_degradation[name] = round(
                (train_fitness - seg_fit) / train_fitness * 100, 1
            )
        else:
            diag.fitness_degradation[name] = 0.0

    # Walk-forward
    wf = result.walk_forward
    if wf:
        diag.wf_efficiency = round(wf.efficiency_ratio, 4)
        diag.wf_consistency = round(wf.consistency, 4)
        diag.wf_is_overfit = bool(wf.is_overfit)

    diag.overall_fitness = round(result.overall_fitness, 4)

    # Classify degradation profile
    fw1_deg = diag.fitness_degradation.get("forward_1", 0.0)
    fw2_deg = diag.fitness_degradation.get("forward_2", 0.0)

    if fw1_deg < 20 and fw2_deg < 30:
        diag.degradation_profile = "stable"
    elif fw1_deg < 40 and fw2_deg < 60:
        diag.degradation_profile = "gradual"
    elif fw1_deg < 30 and fw2_deg >= 80:
        diag.degradation_profile = "cliff"
    else:
        diag.degradation_profile = "erratic"

    return diag


def build_failure_signature(diag: AssetDiagnosis) -> str:
    """Build one-line failure signature."""
    parts = []
    parts.append(f"scarcity={diag.scarcity.scarcity_level}")
    parts.append(f"regime={diag.regime.regime_bias}")
    parts.append(f"stability={diag.stability.degradation_profile}")
    parts.append(f"verdict={diag.verdict}")
    return " | ".join(parts)


def determine_exit_status(report: CrossAssetReport) -> str:
    """Determine B-3 exit status based on cross-asset diagnosis.

    Since B-3 is diagnostic-only (no strategy modification),
    the exit status reflects what was OBSERVED, not what was FIXED.

    Rules:
      RESOLVED:        All assets verdict=PASS (unlikely in diagnostic-only phase)
      IMPROVED:        At least one FAIL cause is structurally understood
                       with a clear improvement path identified
      MAINTAINED_FAIL: Core limitations confirmed, FAIL is structural
    """
    all_verdicts = [a.verdict for a in report.assets.values()]

    if all(v == "PASS" for v in all_verdicts):
        return "RESOLVED"

    # In a diagnostic phase, MAINTAINED_FAIL is the expected outcome
    # since we're observing, not modifying. The value is in the diagnosis itself.
    # Mark as MAINTAINED_FAIL with diagnostic value.
    return "MAINTAINED_FAIL"


# ── Main Execution ───────────────────────────────────────────────


async def run_diagnosis(symbols: list[str]) -> CrossAssetReport:
    """Run full diagnostic for specified symbols."""
    report = CrossAssetReport(
        diagnosed_at=datetime.now(timezone.utc).isoformat(),
    )

    for symbol in symbols:
        print(f"\n{'='*60}")
        print(f"  DIAGNOSING: {symbol}")
        print(f"{'='*60}")

        cfg = FullCycleConfig(exchange="binance", symbol=symbol, timeframe="1h")
        backtester = FullCycleBacktester(cfg)
        strategy = SMCWaveTrendStrategy(symbol=symbol, exchange="binance")

        async with async_session_factory() as session:
            # Run full cycle
            result = await backtester.run(session, strategy)

            # Load raw candles for regime analysis
            mgr = HistoryDataManager()
            ohlcv = await mgr.get_replay_candles(
                session, "binance", symbol, "1h",
            )

        # Split for regime per-segment analysis
        segments = SegmentSplitter.split(ohlcv, cfg)

        # ── Diagnostics ──────────────────────────────────────
        scarcity = diagnose_scarcity(result)
        regime = diagnose_regime(result, ohlcv, segments)
        stability = diagnose_stability(result)

        # Extract reason codes from verdict log
        reason_codes: list[str] = []
        pass_count = 0
        thresholds = {
            "train": TRAIN_FITNESS_THRESHOLD,
            "forward_1": FORWARD1_FITNESS_THRESHOLD,
            "forward_2": FORWARD2_FITNESS_THRESHOLD,
        }
        for name, threshold in thresholds.items():
            seg = result.segments.get(name)
            if seg and seg.fitness.total >= threshold:
                pass_count += 1
            elif seg:
                reason_codes.append(f"{name}_FITNESS_LOW({seg.fitness.total:.4f}<{threshold})")

        wf = result.walk_forward
        if wf:
            if wf.efficiency_ratio >= WF_EFFICIENCY_THRESHOLD:
                pass_count += 1
            else:
                reason_codes.append(f"WF_EFFICIENCY_LOW({wf.efficiency_ratio:.4f}<{WF_EFFICIENCY_THRESHOLD})")
            if not wf.is_overfit:
                pass_count += 1
            else:
                reason_codes.append("WF_OVERFIT_DETECTED")

        if result.regime_diversity_score >= RDS_THRESHOLD:
            pass_count += 1
        else:
            reason_codes.append(f"RDS_LOW({result.regime_diversity_score:.4f}<{RDS_THRESHOLD})")

        if result.data_leakage_check:
            pass_count += 1
        else:
            reason_codes.append("DATA_LEAKAGE_DETECTED")

        asset_diag = AssetDiagnosis(
            symbol=symbol,
            verdict=result.verdict,
            reason_codes=reason_codes,
            pass_count=pass_count,
            scarcity=scarcity,
            regime=regime,
            stability=stability,
        )
        asset_diag.failure_signature = build_failure_signature(asset_diag)
        report.assets[symbol] = asset_diag

        # ── Print per-asset report ───────────────────────────
        print(f"\n  Verdict: {result.verdict} ({pass_count}/7 PASS)")
        print(f"  Overall Fitness: {result.overall_fitness:.4f}")
        if reason_codes:
            print(f"  Reason Codes: {reason_codes}")

        print(f"\n  [B-3A] Trade Scarcity: {scarcity.scarcity_level}")
        for name in SEGMENT_NAMES:
            trades = scarcity.segment_trades.get(name, 0)
            density = scarcity.segment_trade_density.get(name, 0.0)
            miss = scarcity.min_trades_miss.get(name, False)
            marker = " ** MISS" if miss else ""
            print(f"    {name}: trades={trades}, density={density}/100bars{marker}")

        print(f"\n  [B-3B] Regime Diversity: {regime.regime_bias}")
        print(f"    Global RDS: {regime.global_rds:.4f} (threshold: {RDS_THRESHOLD})")
        print(f"    Dominant: {regime.dominant_regime} ({regime.dominant_pct}%)")
        for name in SEGMENT_NAMES:
            seg_rds = regime.segment_rds.get(name, 0.0)
            print(f"    {name} RDS: {seg_rds:.4f}")

        print(f"\n  [B-3C] Forward Stability: {stability.degradation_profile}")
        for name in SEGMENT_NAMES:
            fit = stability.segment_fitness.get(name, 0.0)
            deg = stability.fitness_degradation.get(name, "—")
            deg_str = f" (degradation: {deg}%)" if name != "train" else ""
            print(f"    {name}: fitness={fit:.4f}{deg_str}")
        print(f"    WF: efficiency={stability.wf_efficiency:.4f}, consistency={stability.wf_consistency:.4f}, overfit={stability.wf_is_overfit}")

        print(f"\n  Failure Signature: {asset_diag.failure_signature}")

    # ── Cross-asset comparison ───────────────────────────────
    print(f"\n{'='*60}")
    print(f"  CROSS-ASSET COMPARISON")
    print(f"{'='*60}")

    all_reason_sets = [set(a.reason_codes) for a in report.assets.values()]
    if all_reason_sets:
        common = set.intersection(*all_reason_sets) if len(all_reason_sets) > 1 else all_reason_sets[0]
        report.common_failures = sorted(common)

        for symbol, diag in report.assets.items():
            specific = set(diag.reason_codes) - common
            report.asset_specific_failures[symbol] = sorted(specific)

    print(f"\n  Common failures across all assets:")
    for f in report.common_failures:
        print(f"    - {f}")

    print(f"\n  Asset-specific failures:")
    for symbol, failures in report.asset_specific_failures.items():
        if failures:
            print(f"    {symbol}: {failures}")
        else:
            print(f"    {symbol}: (none — all failures are common)")

    # Failure signature table
    print(f"\n  Failure Signatures:")
    for symbol, diag in report.assets.items():
        print(f"    {symbol}: {diag.failure_signature}")

    # ── B-3 exit status ──────────────────────────────────────
    report.b3_exit_status = determine_exit_status(report)

    print(f"\n{'='*60}")
    print(f"  B-3 EXIT STATUS: {report.b3_exit_status}")
    print(f"{'='*60}")

    return report


def save_diagnosis_log(report: CrossAssetReport) -> None:
    """Save diagnosis log to evidence directory."""

    def serialize(obj):
        if hasattr(obj, '__dataclass_fields__'):
            return asdict(obj)
        return str(obj)

    log = asdict(report)
    DIAGNOSIS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DIAGNOSIS_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False, default=serialize)
    print(f"\n  Diagnosis log saved: {DIAGNOSIS_LOG_PATH}")


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Phase B Full-Cycle Diagnostic")
    parser.add_argument("--symbol", type=str, help="Single symbol to diagnose")
    args = parser.parse_args()

    symbols = [args.symbol] if args.symbol else DEFAULT_SYMBOLS

    print("=" * 60)
    print("  Phase B B-3 — Full-Cycle Diagnostic")
    print(f"  symbols: {symbols}")
    print(f"  time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  nature: diagnostic/observation only")
    print("=" * 60)

    report = await run_diagnosis(symbols)
    save_diagnosis_log(report)

    # Final summary table
    print(f"\n{'='*60}")
    print(f"  DIAGNOSTIC SUMMARY TABLE")
    print(f"{'='*60}")
    print(f"  {'Symbol':<20} {'Verdict':<8} {'PASS':<6} {'Scarcity':<10} {'Regime':<14} {'Stability':<10} {'Fitness':<8}")
    print(f"  {'-'*20} {'-'*8} {'-'*6} {'-'*10} {'-'*14} {'-'*10} {'-'*8}")
    for symbol, diag in report.assets.items():
        print(
            f"  {symbol:<20} {diag.verdict:<8} {diag.pass_count}/7"
            f"    {diag.scarcity.scarcity_level:<10}"
            f" {diag.regime.regime_bias:<14}"
            f" {diag.stability.degradation_profile:<10}"
            f" {diag.stability.overall_fitness:<8.4f}"
        )

    print(f"\n  B-3 EXIT: {report.b3_exit_status}")
    print(f"  MAINTAINED_FAIL is a legitimate diagnostic outcome.")
    print(f"  Next step requires separate user GO declaration.")


if __name__ == "__main__":
    asyncio.run(main())
