"""
SOL S-1 V-2 — Candidate 1+2 Combined Backtest

Tests Candidate 1 (consensus window) + Candidate 2 (max_positions=2, size=1%).
Compares 5 configs: baseline, C1-only(N=1), C1+C2(N=1), C1+C2(N=2), C1+C2(N=3).

Key KPIs:
  - Executable Consensus Ratio (ECR)
  - fire_rate_uplift, fitness_ratio, occupancy_block_rate
  - Block reason taxonomy: BLOCK_MAX_POSITIONS, BLOCK_SAME_DIR, BLOCK_OPP_DIR
  - Per-segment min_trades, fitness

Constraints (V-2 GO):
  - SOL only
  - Candidate 1+2 combination only
  - No strategy code modification (subclass + custom engine sim)
  - No auto-advance to V-3

Usage:
  python scripts/sol_s1_v2_combined_backtest.py
"""

import json
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

import numpy as np

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
from strategies.smc_wavetrend_strategy import (  # noqa: E402
    calc_smc_pure_causal,
    calc_wavetrend,
    SL_PCT,
    TP_PCT,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SYMBOL = "SOL/USDT:USDT"
TIMEFRAME = "1h"
TOTAL_BARS = 9600
MIN_TRADES = 10
SEGMENT_RATIOS = {"train": 0.60, "forward_1": 0.20, "forward_2": 0.10, "holdout": 0.10}

# Config matrix: (label, consensus_window, max_positions, position_size_pct)
CONFIGS = [
    ("baseline", 0, 1, 2.0),
    ("C1_N1", 1, 1, 2.0),
    ("C1C2_N1", 1, 2, 1.0),
    ("C1C2_N2", 2, 2, 1.0),
    ("C1C2_N3", 3, 2, 1.0),
]


# ---------------------------------------------------------------------------
# Core simulation (custom, avoids BacktestingEngine position limit)
# ---------------------------------------------------------------------------


@dataclass
class SimPosition:
    entry_bar: int
    entry_price: float
    direction: int  # +1 long, -1 short
    size_pct: float


@dataclass
class SimTrade:
    entry_bar: int
    exit_bar: int
    entry_price: float
    exit_price: float
    direction: int
    size_pct: float
    return_pct: float
    exit_reason: str  # "sl" or "tp"


@dataclass
class BlockEvent:
    bar: int
    consensus_dir: int
    open_positions: int
    block_code: str
    slots_used: int
    slots_available: int


@dataclass
class SegmentMetrics:
    segment: str
    bars: int = 0
    trades: int = 0
    fitness: float = 0.0
    min_trades_met: bool = False
    total_return: float = 0.0
    win_rate: float = 0.0


@dataclass
class ConfigResult:
    label: str
    consensus_window: int
    max_positions: int
    position_size_pct: float

    # Full data
    total_bars: int = 0
    total_trades: int = 0
    consensus_signals: int = 0
    consensus_executable: int = 0
    consensus_blocked: int = 0
    ecr: float = 0.0  # executable consensus ratio
    fire_rate_pct: float = 0.0
    total_return_pct: float = 0.0
    win_rate: float = 0.0
    max_drawdown_pct: float = 0.0
    full_fitness: float = 0.0

    # Block taxonomy
    block_max_positions: int = 0
    block_same_direction: int = 0
    block_opposite_direction: int = 0

    # Segments
    segments: list[SegmentMetrics] = field(default_factory=list)

    # Uplifts (vs baseline)
    fire_rate_uplift: float = 1.0
    fitness_ratio: float = 1.0
    ecr_ratio: float = 1.0
    trade_uplift: float = 1.0


def _has_consensus(
    bar: int,
    smc_signals: np.ndarray,
    wt_signals: np.ndarray,
    consensus_window: int,
) -> int | None:
    """Check if consensus exists at bar within ±N window. Returns direction or None."""
    w_start = max(0, bar - consensus_window)
    smc_w = smc_signals[w_start : bar + 1]
    wt_w = wt_signals[w_start : bar + 1]

    for d in [1, -1]:
        if np.any(smc_w == d) and np.any(wt_w == d):
            return d
    return None


def simulate_config(
    ohlcv: list,
    smc_signals: np.ndarray,
    wt_signals: np.ndarray,
    consensus_window: int,
    max_positions: int,
    position_size_pct: float,
) -> tuple[list[SimTrade], list[BlockEvent], int, int, int]:
    """
    Custom simulation with configurable max_positions.
    Returns (trades, block_events, consensus_count, executable_count, blocked_count).
    """
    closes = np.array([bar[4] for bar in ohlcv], dtype=float)
    total = len(ohlcv)

    open_positions: list[SimPosition] = []
    completed_trades: list[SimTrade] = []
    block_events: list[BlockEvent] = []

    consensus_count = 0
    executable_count = 0
    blocked_count = 0

    block_max = 0
    block_same = 0
    block_opp = 0

    for bar in range(total):
        price = closes[bar]

        # Check exits
        remaining = []
        for pos in open_positions:
            if pos.direction == 1:
                ret = (price - pos.entry_price) / pos.entry_price
            else:
                ret = (pos.entry_price - price) / pos.entry_price

            if ret <= -SL_PCT:
                completed_trades.append(
                    SimTrade(
                        entry_bar=pos.entry_bar,
                        exit_bar=bar,
                        entry_price=pos.entry_price,
                        exit_price=price,
                        direction=pos.direction,
                        size_pct=pos.size_pct,
                        return_pct=round(ret * 100, 4),
                        exit_reason="sl",
                    )
                )
            elif ret >= TP_PCT:
                completed_trades.append(
                    SimTrade(
                        entry_bar=pos.entry_bar,
                        exit_bar=bar,
                        entry_price=pos.entry_price,
                        exit_price=price,
                        direction=pos.direction,
                        size_pct=pos.size_pct,
                        return_pct=round(ret * 100, 4),
                        exit_reason="tp",
                    )
                )
            else:
                remaining.append(pos)
        open_positions = remaining

        # Check consensus
        consensus_dir = _has_consensus(bar, smc_signals, wt_signals, consensus_window)
        if consensus_dir is None:
            continue

        consensus_count += 1
        slots_used = len(open_positions)
        slots_available = max_positions - slots_used

        if slots_available <= 0:
            # Blocked: classify reason
            blocked_count += 1
            block_max += 1

            # Sub-classify
            same_dir_count = sum(1 for p in open_positions if p.direction == consensus_dir)
            opp_dir_count = slots_used - same_dir_count

            if same_dir_count > 0 and opp_dir_count == 0:
                code = "BLOCK_SAME_DIRECTION"
                block_same += 1
            elif opp_dir_count > 0 and same_dir_count == 0:
                code = "BLOCK_OPPOSITE_DIRECTION"
                block_opp += 1
            else:
                code = "BLOCK_MAX_POSITIONS"

            block_events.append(
                BlockEvent(
                    bar=bar,
                    consensus_dir=consensus_dir,
                    open_positions=slots_used,
                    block_code=code,
                    slots_used=slots_used,
                    slots_available=0,
                )
            )
        else:
            # Entry
            executable_count += 1
            open_positions.append(
                SimPosition(
                    entry_bar=bar,
                    entry_price=price,
                    direction=consensus_dir,
                    size_pct=position_size_pct,
                )
            )

    return (
        completed_trades,
        block_events,
        consensus_count,
        executable_count,
        blocked_count,
    )


def compute_performance(
    trades: list[SimTrade],
    initial_capital: float = 10000.0,
) -> dict:
    """Compute performance metrics from sim trades."""
    if not trades:
        return {"total_return_pct": 0.0, "win_rate": 0.0, "max_drawdown_pct": 0.0}

    wins = sum(1 for t in trades if t.return_pct > 0)
    total = len(trades)

    # Equity curve
    equity = initial_capital
    peak = equity
    max_dd = 0.0
    for t in trades:
        pnl = equity * (t.size_pct / 100) * (t.return_pct / 100)
        equity += pnl
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak * 100
        if dd > max_dd:
            max_dd = dd

    total_return = (equity - initial_capital) / initial_capital * 100

    return {
        "total_return_pct": round(total_return, 4),
        "win_rate": round(wins / total, 4) if total > 0 else 0.0,
        "max_drawdown_pct": round(max_dd, 4),
    }


def run_config(
    ohlcv: list,
    smc_signals: np.ndarray,
    wt_signals: np.ndarray,
    label: str,
    consensus_window: int,
    max_positions: int,
    position_size_pct: float,
) -> ConfigResult:
    """Run full simulation for one config."""
    trades, blocks, cons_count, exec_count, block_count = simulate_config(
        ohlcv,
        smc_signals,
        wt_signals,
        consensus_window,
        max_positions,
        position_size_pct,
    )

    perf = compute_performance(trades)
    trade_count = len(trades)

    # Fitness via FitnessFunction (approximate: use BacktestingEngine for full-data)
    # For segment fitness, we run the engine per segment
    fitness_fn = FitnessFunction(min_trades=MIN_TRADES)

    # Full fitness approximation
    if trade_count >= MIN_TRADES:
        from app.services.performance_metrics import PerformanceReport

        # Build approximate report
        report = PerformanceReport()
        report.total_trades = trade_count
        report.winning_trades = sum(1 for t in trades if t.return_pct > 0)
        report.losing_trades = trade_count - report.winning_trades
        report.win_rate = report.winning_trades / trade_count if trade_count > 0 else 0
        report.total_return_pct = perf["total_return_pct"]
        report.max_drawdown_pct = perf["max_drawdown_pct"]

        avg_win_returns = [t.return_pct for t in trades if t.return_pct > 0]
        avg_loss_returns = [t.return_pct for t in trades if t.return_pct <= 0]
        report.avg_win = sum(avg_win_returns) / len(avg_win_returns) if avg_win_returns else 0
        report.avg_loss = sum(avg_loss_returns) / len(avg_loss_returns) if avg_loss_returns else 0
        report.profit_factor = (
            abs(sum(avg_win_returns)) / abs(sum(avg_loss_returns))
            if avg_loss_returns and sum(avg_loss_returns) != 0
            else 0
        )

        fb = fitness_fn.evaluate(report)
        full_fitness = float(fb.total)
    else:
        full_fitness = 0.0

    # Block taxonomy counts
    block_max_pos = sum(1 for b in blocks if b.block_code == "BLOCK_MAX_POSITIONS")
    block_same = sum(1 for b in blocks if b.block_code == "BLOCK_SAME_DIRECTION")
    block_opp = sum(1 for b in blocks if b.block_code == "BLOCK_OPPOSITE_DIRECTION")

    result = ConfigResult(
        label=label,
        consensus_window=consensus_window,
        max_positions=max_positions,
        position_size_pct=position_size_pct,
        total_bars=len(ohlcv),
        total_trades=trade_count,
        consensus_signals=cons_count,
        consensus_executable=exec_count,
        consensus_blocked=block_count,
        ecr=round(exec_count / cons_count * 100, 2) if cons_count > 0 else 0.0,
        fire_rate_pct=round(trade_count / len(ohlcv) * 100, 4),
        total_return_pct=perf["total_return_pct"],
        win_rate=perf["win_rate"],
        max_drawdown_pct=perf["max_drawdown_pct"],
        full_fitness=round(full_fitness, 4),
        block_max_positions=block_max_pos,
        block_same_direction=block_same,
        block_opposite_direction=block_opp,
    )

    # Per-segment analysis
    total = len(ohlcv)
    boundaries = {}
    pos = 0
    for seg_name in ["train", "forward_1", "forward_2", "holdout"]:
        seg_len = int(total * SEGMENT_RATIOS[seg_name])
        boundaries[seg_name] = (pos, pos + seg_len)
        pos += seg_len

    for seg_name in ["train", "forward_1", "forward_2", "holdout"]:
        start, end = boundaries[seg_name]
        seg_trades = [t for t in trades if start <= t.entry_bar < end]
        seg_count = len(seg_trades)

        if seg_count >= MIN_TRADES:
            seg_perf = compute_performance(seg_trades)
            from app.services.performance_metrics import PerformanceReport

            seg_report = PerformanceReport()
            seg_report.total_trades = seg_count
            seg_report.winning_trades = sum(1 for t in seg_trades if t.return_pct > 0)
            seg_report.losing_trades = seg_count - seg_report.winning_trades
            seg_report.win_rate = seg_report.winning_trades / seg_count if seg_count > 0 else 0
            seg_report.total_return_pct = seg_perf["total_return_pct"]
            seg_report.max_drawdown_pct = seg_perf["max_drawdown_pct"]

            aws = [t.return_pct for t in seg_trades if t.return_pct > 0]
            als = [t.return_pct for t in seg_trades if t.return_pct <= 0]
            seg_report.avg_win = sum(aws) / len(aws) if aws else 0
            seg_report.avg_loss = sum(als) / len(als) if als else 0
            seg_report.profit_factor = abs(sum(aws)) / abs(sum(als)) if als and sum(als) != 0 else 0

            seg_fb = fitness_fn.evaluate(seg_report)
            seg_fitness = float(seg_fb.total)
        else:
            seg_fitness = 0.0

        seg_perf_data = compute_performance(seg_trades)
        result.segments.append(
            SegmentMetrics(
                segment=seg_name,
                bars=end - start,
                trades=seg_count,
                fitness=round(seg_fitness, 4),
                min_trades_met=seg_count >= MIN_TRADES,
                total_return=seg_perf_data["total_return_pct"],
                win_rate=seg_perf_data["win_rate"],
            )
        )

    return result


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def generate_report(results: list[ConfigResult]) -> str:
    lines = []
    baseline = results[0]

    # Full-data comparison
    lines.append("## Deliverable 1: Full-Data Comparison")
    lines.append("")
    headers = ["Metric"] + [r.label for r in results]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["--------"] * len(headers)) + "|")

    rows = [
        ("Trades", lambda r: str(r.total_trades)),
        ("Fire rate %", lambda r: f"{r.fire_rate_pct:.4f}"),
        ("Fire rate uplift", lambda r: f"{r.fire_rate_uplift:.2f}×"),
        ("Consensus signals", lambda r: str(r.consensus_signals)),
        ("Executable", lambda r: str(r.consensus_executable)),
        ("Blocked", lambda r: str(r.consensus_blocked)),
        ("**ECR %**", lambda r: f"**{r.ecr:.1f}%**"),
        ("Block rate %", lambda r: f"{100 - r.ecr:.1f}%"),
        ("Fitness", lambda r: f"{r.full_fitness:.4f}"),
        ("Fitness ratio", lambda r: f"{r.fitness_ratio:.2f}"),
        ("Return %", lambda r: f"{r.total_return_pct:+.2f}%"),
        ("Win rate", lambda r: f"{r.win_rate:.3f}"),
        ("Max DD %", lambda r: f"{r.max_drawdown_pct:.2f}%"),
    ]

    for label, fn in rows:
        vals = [fn(r) for r in results]
        lines.append(f"| {label} | " + " | ".join(vals) + " |")
    lines.append("")

    # Block taxonomy
    lines.append("## Deliverable 2: Block Reason Taxonomy")
    lines.append("")
    lines.append("| Config | BLOCK_MAX_POS | BLOCK_SAME_DIR | BLOCK_OPP_DIR | Total Blocked |")
    lines.append("|--------|---------------|----------------|---------------|---------------|")
    for r in results:
        lines.append(
            f"| {r.label} | {r.block_max_positions} | "
            f"{r.block_same_direction} | {r.block_opposite_direction} | "
            f"{r.consensus_blocked} |"
        )
    lines.append("")

    # Per-segment
    lines.append("## Deliverable 3: Per-Segment Comparison")
    lines.append("")
    for seg_name in ["train", "forward_1", "forward_2", "holdout"]:
        lines.append(f"### {seg_name}")
        lines.append("")
        lines.append("| Metric | " + " | ".join(r.label for r in results) + " |")
        lines.append("|--------|" + "|".join(["-----"] * len(results)) + "|")

        for metric, fn in [
            (
                "Trades",
                lambda r, s=seg_name: str(
                    next(seg for seg in r.segments if seg.segment == s).trades
                ),
            ),
            (
                "min_trades",
                lambda r, s=seg_name: (
                    "OK"
                    if next(seg for seg in r.segments if seg.segment == s).min_trades_met
                    else "**MISS**"
                ),
            ),
            (
                "Fitness",
                lambda r, s=seg_name: (
                    f"{next(seg for seg in r.segments if seg.segment == s).fitness:.4f}"
                ),
            ),
            (
                "Return",
                lambda r, s=seg_name: (
                    f"{next(seg for seg in r.segments if seg.segment == s).total_return:+.2f}%"
                ),
            ),
            (
                "Win rate",
                lambda r, s=seg_name: (
                    f"{next(seg for seg in r.segments if seg.segment == s).win_rate:.3f}"
                ),
            ),
        ]:
            vals = [fn(r) for r in results]
            lines.append(f"| {metric} | " + " | ".join(vals) + " |")
        lines.append("")

    # 2-axis state
    lines.append("## Deliverable 4: 2-Axis State Transition")
    lines.append("")
    lines.append("| Config | Scarcity | Occupancy | State |")
    lines.append("|--------|----------|-----------|-------|")
    for r in results:
        scarcity = "High" if r.fire_rate_uplift < 1.5 else "Low"
        occupancy = "High" if r.ecr < 60 else "Low"
        state = {"HighLow": "S1", "LowHigh": "S2", "LowLow": "**S3**", "HighHigh": "S4"}
        s = state.get(scarcity + occupancy, "?")
        lines.append(f"| {r.label} | {scarcity} | {occupancy} | {s} |")
    lines.append("")

    # Verdict
    lines.append("## V-2 Verdict")
    lines.append("")

    passing = []
    for r in results[1:]:
        checks = {
            "fire_rate": r.fire_rate_uplift >= 1.5,
            "fitness": r.fitness_ratio >= 0.80,
            "ecr": r.ecr >= 60,
            "block_rate": (100 - r.ecr) <= 40,
            "fw2_min": any(s.min_trades_met for s in r.segments if s.segment == "forward_2"),
            "holdout_min": any(s.min_trades_met for s in r.segments if s.segment == "holdout"),
            "max_dd": r.max_drawdown_pct <= baseline.max_drawdown_pct * 2,
        }
        if all(checks.values()):
            passing.append((r, checks))

    if passing:
        best = max(passing, key=lambda x: x[0].fire_rate_uplift)
        r, checks = best
        lines.append(f"**PASS**: {r.label} meets all criteria")
        lines.append(f"- Fire rate uplift: {r.fire_rate_uplift:.2f}× (≥ 1.5×)")
        lines.append(f"- Fitness ratio: {r.fitness_ratio:.2f} (≥ 0.80)")
        lines.append(f"- ECR: {r.ecr:.1f}% (≥ 60%)")
        lines.append(f"- Block rate: {100 - r.ecr:.1f}% (≤ 40%)")
    else:
        informative = any(r.fire_rate_uplift >= 1.5 for r in results[1:])
        if informative:
            lines.append("**INFORMATIVE_FAIL**: Uplift achieved but guards failed")
        else:
            lines.append("**BLOCK**: No configuration achieved criteria")

        for r in results[1:]:
            fails = []
            if r.fire_rate_uplift < 1.5:
                fails.append(f"uplift {r.fire_rate_uplift:.2f}×")
            if r.fitness_ratio < 0.80:
                fails.append(f"fitness {r.fitness_ratio:.2f}")
            if r.ecr < 60:
                fails.append(f"ECR {r.ecr:.1f}%")
            if (100 - r.ecr) > 40:
                fails.append(f"block {100 - r.ecr:.1f}%")
            status = "FAIL: " + ", ".join(fails) if fails else "PASS"
            lines.append(f"- {r.label}: {status}")

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def run_v2():
    print("=" * 60, flush=True)
    print("SOL S-1 V-2 — Candidate 1+2 Combined Backtest", flush=True)
    print("=" * 60, flush=True)
    print(f"Symbol: {SYMBOL}", flush=True)
    print(f"Configs: {len(CONFIGS)}", flush=True)
    print(flush=True)

    # Load data
    async with async_session_factory() as session:
        hdm = HistoryDataManager()
        ohlcv = await hdm.get_replay_candles(
            session=session,
            exchange="binance",
            symbol=SYMBOL,
            timeframe=TIMEFRAME,
            limit=TOTAL_BARS,
        )
    print(f"Loaded {len(ohlcv)} bars", flush=True)

    # Precompute signals
    highs = np.array([bar[2] for bar in ohlcv], dtype=float)
    lows = np.array([bar[3] for bar in ohlcv], dtype=float)
    closes = np.array([bar[4] for bar in ohlcv], dtype=float)
    _, smc_signals = calc_smc_pure_causal(highs, lows, closes, internal_length=5)
    _, _, wt_signals = calc_wavetrend(highs, lows, closes, n1=10, n2=21)
    print(
        f"SMC nonzero: {np.count_nonzero(smc_signals)}, WT nonzero: {np.count_nonzero(wt_signals)}",
        flush=True,
    )

    results: list[ConfigResult] = []

    for label, cw, mp, psp in CONFIGS:
        print(f"\n[SIM] {label} (N={cw}, max_pos={mp}, size={psp}%)...", flush=True)
        r = run_config(ohlcv, smc_signals, wt_signals, label, cw, mp, psp)
        print(
            f"  Trades: {r.total_trades} | ECR: {r.ecr}% | "
            f"Fitness: {r.full_fitness} | Block: {r.consensus_blocked}",
            flush=True,
        )
        for seg in r.segments:
            mt = "OK" if seg.min_trades_met else "MISS"
            print(f"    {seg.segment}: {seg.trades}t fitness={seg.fitness} mt={mt}", flush=True)
        results.append(r)

    # Compute uplifts
    baseline = results[0]
    for r in results[1:]:
        r.fire_rate_uplift = (
            round(r.total_trades / baseline.total_trades, 2) if baseline.total_trades > 0 else 0
        )
        r.fitness_ratio = (
            round(r.full_fitness / baseline.full_fitness, 2)
            if baseline.full_fitness > 0
            else (1.0 if r.full_fitness == 0 else float("inf"))
        )
        r.trade_uplift = r.fire_rate_uplift
        r.ecr_ratio = round(r.ecr / baseline.ecr, 2) if baseline.ecr > 0 else 0

    # Report
    print(f"\n{'=' * 60}", flush=True)
    print("DELIVERABLES", flush=True)
    print(f"{'=' * 60}\n", flush=True)
    report = generate_report(results)
    print(report, flush=True)

    # JSON log
    class _Enc(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, (np.bool_,)):
                return bool(obj)
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                return float(obj)
            return super().default(obj)

    log = {
        "v2_at": datetime.now(timezone.utc).isoformat(),
        "chain": "Phase C Post-Closure — SOL S-1",
        "step": "V-2",
        "candidate": "Candidate 1+2 (Consensus window + Position sizing)",
        "symbol": SYMBOL,
        "total_bars": len(ohlcv),
        "configs": [asdict(r) for r in results],
    }

    # Verdict
    passing = [
        r
        for r in results[1:]
        if r.fire_rate_uplift >= 1.5
        and r.fitness_ratio >= 0.80
        and r.ecr >= 60
        and (100 - r.ecr) <= 40
    ]
    if passing:
        best = max(passing, key=lambda r: r.fire_rate_uplift)
        log["verdict"] = "PASS"
        log["best_config"] = best.label
    else:
        any_uplift = any(r.fire_rate_uplift >= 1.5 for r in results[1:])
        log["verdict"] = "INFORMATIVE_FAIL" if any_uplift else "BLOCK"
        log["best_config"] = None

    log_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "docs",
        "operations",
        "evidence",
        "sol_s1_v2_backtest_log.json",
    )
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False, cls=_Enc)
    print(f"\n[LOG] Saved: {log_path}", flush=True)


def main():
    asyncio.run(run_v2())


if __name__ == "__main__":
    main()
