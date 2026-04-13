"""
SOL S-1 V-1 — Consensus Window Expansion Backtest

Tests Candidate 1: relax same-bar consensus to ±N bar window.
Compares baseline (N=0) vs N=1,2,3 on SOL/USDT:USDT only.

Measures:
  - consensus_rate, fire_rate_uplift, trade_count
  - min_trades per segment, fitness per segment
  - occupancy_block_rate
  - delayed_consensus_ledger (delay distribution)
  - newly_unblocked_trades, reblocked_by_occupancy

Constraints (V-1 GO):
  - SOL only
  - Candidate 1 only (no position sizing, no SMC sensitivity)
  - No strategy code modification (subclass only)
  - No auto-advance to V-2
  - B-1 core untouched

Usage:
  python scripts/sol_s1_v1_consensus_window_backtest.py
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
from app.models.signal import SignalType  # noqa: E402
from app.services.backtesting_engine import BacktestingEngine, BacktestConfig  # noqa: E402
from app.services.fitness_function import FitnessFunction  # noqa: E402
from app.services.history_data_manager import HistoryDataManager  # noqa: E402
from strategies.smc_wavetrend_strategy import (  # noqa: E402
    SMCWaveTrendStrategy,
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
LOOKBACK = 50
CONSENSUS_WINDOWS = [0, 1, 2, 3]  # N values to test

# Segment ratios (baseline)
SEGMENT_RATIOS = {"train": 0.60, "forward_1": 0.20, "forward_2": 0.10, "holdout": 0.10}


# ---------------------------------------------------------------------------
# Windowed Consensus Strategy (subclass, NO B-1 modification)
# ---------------------------------------------------------------------------

class WindowedConsensusStrategy(SMCWaveTrendStrategy):
    """
    Extends SMCWaveTrendStrategy with configurable consensus window.
    N=0 = same-bar (identical to baseline).
    N>0 = allow consensus if SMC and WT fire within ±N bars.
    """

    def __init__(self, symbol: str, consensus_window: int = 0, **kwargs):
        super().__init__(symbol, **kwargs)
        self.consensus_window = consensus_window

    @property
    def name(self) -> str:
        return f"SMC_WaveTrend_1H_w{self.consensus_window}"

    def analyze(self, ohlcv: list[list], **kwargs) -> dict | None:
        self._diag = {}

        if len(ohlcv) < self.min_bars:
            self._diag = {"diagnostic_populated": False}
            return None

        try:
            timestamps = np.array([bar[0] for bar in ohlcv])
            highs = np.array([bar[2] for bar in ohlcv], dtype=float)
            lows = np.array([bar[3] for bar in ohlcv], dtype=float)
            closes = np.array([bar[4] for bar in ohlcv], dtype=float)

            smc_trend_arr, smc_signals = calc_smc_pure_causal(
                highs, lows, closes, internal_length=self.internal_length,
            )
            wt1, wt2, wt_signals = calc_wavetrend(
                highs, lows, closes, n1=self.n1, n2=self.n2,
            )

            last_idx = len(ohlcv) - 1
            N = self.consensus_window
            window_start = max(0, last_idx - N)

            # Find consensus in window: smallest delay, prefer most recent
            best_dir = None
            best_delay = None

            for s_idx in range(window_start, last_idx + 1):
                smc_s = int(smc_signals[s_idx])
                if smc_s == 0:
                    continue
                for w_idx in range(window_start, last_idx + 1):
                    wt_w = int(wt_signals[w_idx])
                    if wt_w != smc_s:
                        continue
                    delay = abs(s_idx - w_idx)
                    if best_delay is None or delay < best_delay:
                        best_delay = delay
                        best_dir = smc_s

            # Build diagnostic
            smc_sig = int(smc_signals[last_idx])
            wt_sig = int(wt_signals[last_idx])
            smc_trend_val = int(smc_trend_arr[last_idx])
            wt1_val = float(wt1[last_idx]) if not np.isnan(wt1[last_idx]) else None
            wt2_val = float(wt2[last_idx]) if not np.isnan(wt2[last_idx]) else None

            self._diag = self._build_diag(
                smc_sig, wt_sig, smc_trend_val, wt1_val, wt2_val, closes[last_idx],
            )
            self._diag["consensus_window"] = N
            self._diag["consensus_delay"] = best_delay
            self._diag["windowed_consensus_dir"] = best_dir

            if best_dir is None:
                return None

            entry_price = closes[last_idx]
            bar_ts = int(timestamps[last_idx])

            if best_dir == 1:
                signal_type = SignalType.LONG
                stop_loss = entry_price * (1 - SL_PCT)
                take_profit = entry_price * (1 + TP_PCT)
            else:
                signal_type = SignalType.SHORT
                stop_loss = entry_price * (1 + SL_PCT)
                take_profit = entry_price * (1 - TP_PCT)

            return self.generate_signal(
                signal_type=signal_type,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=0.7,
                metadata={
                    "smc_signal": best_dir,
                    "wt_signal": best_dir,
                    "consensus_delay": best_delay,
                    "consensus_window": N,
                    "wt1_val": wt1_val,
                    "wt2_val": wt2_val,
                    "bar_timestamp": bar_ts,
                    "strategy_version": f"{self.name}_{self.version}",
                },
            )
        except Exception:
            self._diag = {"diagnostic_populated": False}
            raise


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class DelayedConsensusLedger:
    """Tracks delay distribution of consensus signals."""
    delay_0: int = 0  # same-bar (baseline)
    delay_1: int = 0
    delay_2: int = 0
    delay_3: int = 0
    beyond_window: int = 0
    total_consensus: int = 0


@dataclass
class SegmentResult:
    """Per-segment backtest result."""
    segment: str
    bars: int = 0
    trades: int = 0
    fitness: float = 0.0
    min_trades_met: bool = False
    total_return: float = 0.0
    win_rate: float = 0.0


@dataclass
class ConfigResult:
    """Complete result for one consensus window configuration."""
    consensus_window: int
    label: str

    # Full-data metrics
    total_bars: int = 0
    total_trades: int = 0
    consensus_signals: int = 0  # including blocked
    blocked_by_occupancy: int = 0
    occupancy_block_rate: float = 0.0
    fire_rate_pct: float = 0.0
    total_return: float = 0.0
    win_rate: float = 0.0
    max_drawdown: float = 0.0
    full_fitness: float = 0.0

    # Delay ledger
    delay_ledger: DelayedConsensusLedger = field(default_factory=DelayedConsensusLedger)

    # Per-segment
    segments: list[SegmentResult] = field(default_factory=list)

    # Uplift vs baseline
    fire_rate_uplift: float = 1.0
    fitness_ratio: float = 1.0
    trade_uplift: float = 1.0

    # Newly unblocked (vs baseline)
    newly_unblocked_trades: int = 0
    reblocked_by_occupancy: int = 0


# ---------------------------------------------------------------------------
# Pre-analysis: compute consensus distribution on full data
# ---------------------------------------------------------------------------

def precompute_signal_analysis(ohlcv: list) -> dict:
    """Compute SMC/WT signals for all bars and analyze consensus distribution."""
    highs = np.array([bar[2] for bar in ohlcv], dtype=float)
    lows = np.array([bar[3] for bar in ohlcv], dtype=float)
    closes = np.array([bar[4] for bar in ohlcv], dtype=float)

    _, smc_signals = calc_smc_pure_causal(highs, lows, closes, internal_length=5)
    _, _, wt_signals = calc_wavetrend(highs, lows, closes, n1=10, n2=21)

    total = len(ohlcv)
    smc_fired = int(np.count_nonzero(smc_signals))
    wt_fired = int(np.count_nonzero(wt_signals))

    # Count consensus at each delay level
    # For each bar, find minimum delay consensus
    delay_counts = {0: 0, 1: 0, 2: 0, 3: 0}
    first_consensus_by_bar = {}

    for max_n in [0, 1, 2, 3]:
        for bar in range(total):
            if bar in first_consensus_by_bar:
                continue  # already found at smaller N
            w_start = max(0, bar - max_n)
            found = False
            for s in range(w_start, bar + 1):
                if found:
                    break
                smc_s = int(smc_signals[s])
                if smc_s == 0:
                    continue
                for w in range(w_start, bar + 1):
                    if int(wt_signals[w]) == smc_s:
                        delay = abs(s - w)
                        if delay <= max_n and delay == max_n:
                            # This bar first gets consensus at this N level
                            delay_counts[max_n] = delay_counts.get(max_n, 0) + 1
                            first_consensus_by_bar[bar] = max_n
                            found = True
                            break

    # Cumulative: how many consensus bars at each N
    cumulative = {}
    running = 0
    for n in [0, 1, 2, 3]:
        running += delay_counts[n]
        cumulative[n] = running

    return {
        "total_bars": total,
        "smc_fired": smc_fired,
        "smc_rate_pct": round(smc_fired / total * 100, 2),
        "wt_fired": wt_fired,
        "wt_rate_pct": round(wt_fired / total * 100, 2),
        "delay_incremental": delay_counts,
        "delay_cumulative": cumulative,
    }


# ---------------------------------------------------------------------------
# Backtest runner
# ---------------------------------------------------------------------------

def run_backtest_config(
    ohlcv: list,
    consensus_window: int,
) -> ConfigResult:
    """Run full backtest for one consensus window configuration."""
    label = f"N={consensus_window}" if consensus_window > 0 else "baseline"
    strategy = WindowedConsensusStrategy(
        symbol=SYMBOL,
        consensus_window=consensus_window,
    )

    engine = BacktestingEngine(config=BacktestConfig(
        initial_capital=10000.0,
        position_size_pct=2.0,
    ))

    # Full-data backtest
    bt_result = engine.run(strategy, ohlcv, lookback=LOOKBACK)
    trades = bt_result.trades or []
    trade_count = len(trades)

    # Fitness
    fitness_fn = FitnessFunction(min_trades=MIN_TRADES)
    if trade_count >= MIN_TRADES:
        fb = fitness_fn.evaluate(bt_result.performance)
        full_fitness = float(fb.total)
    else:
        full_fitness = 0.0

    perf = bt_result.performance
    total_return = float(perf.total_return_pct) if perf else 0.0
    win_rate = float(perf.win_rate) if perf else 0.0
    max_dd = float(perf.max_drawdown_pct) if perf else 0.0

    result = ConfigResult(
        consensus_window=consensus_window,
        label=label,
        total_bars=len(ohlcv),
        total_trades=trade_count,
        fire_rate_pct=round(trade_count / len(ohlcv) * 100, 4),
        total_return=round(total_return, 4),
        win_rate=round(win_rate, 4),
        max_drawdown=round(max_dd, 4),
        full_fitness=round(full_fitness, 4),
    )

    # Per-segment backtest
    total = len(ohlcv)
    train_end = int(total * SEGMENT_RATIOS["train"])
    fw1_end = train_end + int(total * SEGMENT_RATIOS["forward_1"])
    fw2_end = fw1_end + int(total * SEGMENT_RATIOS["forward_2"])

    seg_data = {
        "train": ohlcv[0:train_end],
        "forward_1": ohlcv[train_end:fw1_end],
        "forward_2": ohlcv[fw1_end:fw2_end],
        "holdout": ohlcv[fw2_end:total],
    }

    for seg_name in ["train", "forward_1", "forward_2", "holdout"]:
        seg_strategy = WindowedConsensusStrategy(
            symbol=SYMBOL,
            consensus_window=consensus_window,
        )
        seg_bt = engine.run(seg_strategy, seg_data[seg_name], lookback=LOOKBACK)
        seg_trades = seg_bt.trades or []
        seg_trade_count = len(seg_trades)

        if seg_trade_count >= MIN_TRADES:
            seg_fb = fitness_fn.evaluate(seg_bt.performance)
            seg_fitness = float(seg_fb.total)
        else:
            seg_fitness = 0.0

        seg_perf = seg_bt.performance
        seg_ret = float(seg_perf.total_return_pct) if seg_perf else 0.0
        seg_wr = float(seg_perf.win_rate) if seg_perf else 0.0

        result.segments.append(SegmentResult(
            segment=seg_name,
            bars=len(seg_data[seg_name]),
            trades=seg_trade_count,
            fitness=round(seg_fitness, 4),
            min_trades_met=seg_trade_count >= MIN_TRADES,
            total_return=round(seg_ret, 4),
            win_rate=round(seg_wr, 4),
        ))

    return result


def _precompute_consensus_arrays(ohlcv: list) -> tuple[np.ndarray, np.ndarray]:
    """Precompute SMC and WT signals once (shared across all N configs)."""
    highs = np.array([bar[2] for bar in ohlcv], dtype=float)
    lows = np.array([bar[3] for bar in ohlcv], dtype=float)
    closes = np.array([bar[4] for bar in ohlcv], dtype=float)
    _, smc_signals = calc_smc_pure_causal(highs, lows, closes, internal_length=5)
    _, _, wt_signals = calc_wavetrend(highs, lows, closes, n1=10, n2=21)
    return smc_signals, wt_signals


def _has_consensus_at_bar(
    bar: int,
    smc_signals: np.ndarray,
    wt_signals: np.ndarray,
    consensus_window: int,
) -> tuple[int | None, int | None]:
    """
    Fast check: does consensus exist in [bar-N, bar]?
    Returns (direction, min_delay) or (None, None).
    Uses vectorized sub-window lookup.
    """
    w_start = max(0, bar - consensus_window)
    smc_window = smc_signals[w_start:bar + 1]
    wt_window = wt_signals[w_start:bar + 1]

    best_dir = None
    best_delay = None

    # Check direction +1
    smc_pos = np.where(smc_window == 1)[0]
    wt_pos = np.where(wt_window == 1)[0]
    if len(smc_pos) > 0 and len(wt_pos) > 0:
        # min delay = min |s - w| over all pairs
        for s in smc_pos:
            for w in wt_pos:
                d = abs(int(s) - int(w))
                if best_delay is None or d < best_delay:
                    best_delay = d
                    best_dir = 1
                    if d == 0:
                        break
            if best_delay == 0:
                break

    # Check direction -1
    smc_neg = np.where(smc_window == -1)[0]
    wt_neg = np.where(wt_window == -1)[0]
    if len(smc_neg) > 0 and len(wt_neg) > 0:
        for s in smc_neg:
            for w in wt_neg:
                d = abs(int(s) - int(w))
                if best_delay is None or d < best_delay:
                    best_delay = d
                    best_dir = -1
                    if d == 0:
                        break
            if best_delay == 0:
                break

    return best_dir, best_delay


def compute_occupancy_metrics(
    ohlcv: list,
    consensus_window: int,
    smc_signals: np.ndarray,
    wt_signals: np.ndarray,
) -> tuple[int, int]:
    """
    Manually simulate to count consensus signals and occupancy blocks.
    Returns (consensus_signals, blocked_count).
    """
    closes = np.array([bar[4] for bar in ohlcv], dtype=float)
    total = len(ohlcv)
    consensus_count = 0
    blocked_count = 0
    position_open = False
    position_entry_price = 0.0
    position_dir = 0

    for bar in range(total):
        if position_open:
            price = closes[bar]
            if position_dir == 1:
                ret = (price - position_entry_price) / position_entry_price
                if ret <= -SL_PCT or ret >= TP_PCT:
                    position_open = False
            else:
                ret = (position_entry_price - price) / position_entry_price
                if ret <= -SL_PCT or ret >= TP_PCT:
                    position_open = False

        found_dir, _ = _has_consensus_at_bar(bar, smc_signals, wt_signals, consensus_window)

        if found_dir is not None:
            consensus_count += 1
            if position_open:
                blocked_count += 1
            else:
                position_open = True
                position_entry_price = closes[bar]
                position_dir = found_dir

    return consensus_count, blocked_count


def compute_delay_ledger(
    ohlcv: list,
    consensus_window: int,
    smc_signals: np.ndarray,
    wt_signals: np.ndarray,
) -> DelayedConsensusLedger:
    """Compute delayed consensus ledger for given window."""
    ledger = DelayedConsensusLedger()
    total = len(ohlcv)

    for bar in range(total):
        _, best_delay = _has_consensus_at_bar(bar, smc_signals, wt_signals, consensus_window)
        if best_delay is not None:
            ledger.total_consensus += 1
            if best_delay == 0:
                ledger.delay_0 += 1
            elif best_delay == 1:
                ledger.delay_1 += 1
            elif best_delay == 2:
                ledger.delay_2 += 1
            elif best_delay == 3:
                ledger.delay_3 += 1
            else:
                ledger.beyond_window += 1

    return ledger


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(
    pre_analysis: dict,
    results: list[ConfigResult],
) -> str:
    """Generate V-1 comparison report."""
    lines = []
    baseline = results[0]

    # Pre-analysis
    lines.append("## Pre-Analysis: Signal Distribution")
    lines.append("")
    lines.append(f"**Total bars:** {pre_analysis['total_bars']}")
    lines.append(f"**SMC fired:** {pre_analysis['smc_fired']} ({pre_analysis['smc_rate_pct']}%)")
    lines.append(f"**WT fired:** {pre_analysis['wt_fired']} ({pre_analysis['wt_rate_pct']}%)")
    lines.append("")
    lines.append("### Consensus by Delay Level (Incremental / Cumulative)")
    lines.append("")
    lines.append("| Delay | New Consensus Bars | Cumulative | Cumulative Rate |")
    lines.append("|-------|-------------------|------------|-----------------|")
    for n in [0, 1, 2, 3]:
        inc = pre_analysis['delay_incremental'][n]
        cum = pre_analysis['delay_cumulative'][n]
        rate = round(cum / pre_analysis['total_bars'] * 100, 2)
        lines.append(f"| delay_{n} | +{inc} | {cum} | {rate}% |")
    lines.append("")

    # Comparison table
    lines.append("## Deliverable 1: Full-Data Comparison")
    lines.append("")
    lines.append("| Metric | Baseline (N=0) | N=1 | N=2 | N=3 |")
    lines.append("|--------|---------------|-----|-----|-----|")

    metrics = [
        ("Total trades", "total_trades"),
        ("Fire rate %", "fire_rate_pct"),
        ("Total return", "total_return"),
        ("Win rate", "win_rate"),
        ("Max drawdown", "max_drawdown"),
        ("Fitness", "full_fitness"),
        ("Consensus signals", "consensus_signals"),
        ("Blocked by occupancy", "blocked_by_occupancy"),
        ("Occupancy block rate %", "occupancy_block_rate"),
    ]

    for label, attr in metrics:
        vals = []
        for r in results:
            v = getattr(r, attr)
            if isinstance(v, float):
                vals.append(f"{v:.4f}" if abs(v) < 10 else f"{v:.2f}")
            else:
                vals.append(str(v))
        lines.append(f"| {label} | {' | '.join(vals)} |")

    # Uplift row
    lines.append(f"| **Fire rate uplift** | 1.00× | "
                 f"{results[1].fire_rate_uplift:.2f}× | "
                 f"{results[2].fire_rate_uplift:.2f}× | "
                 f"{results[3].fire_rate_uplift:.2f}× |")
    lines.append(f"| **Fitness ratio** | 1.00 | "
                 f"{results[1].fitness_ratio:.2f} | "
                 f"{results[2].fitness_ratio:.2f} | "
                 f"{results[3].fitness_ratio:.2f} |")
    lines.append(f"| **Trade uplift** | 1.00× | "
                 f"{results[1].trade_uplift:.2f}× | "
                 f"{results[2].trade_uplift:.2f}× | "
                 f"{results[3].trade_uplift:.2f}× |")
    lines.append("")

    # Delay ledger
    lines.append("## Deliverable 2: Delayed Consensus Ledger")
    lines.append("")
    lines.append("| Window | delay_0 | delay_1 | delay_2 | delay_3 | Total |")
    lines.append("|--------|---------|---------|---------|---------|-------|")
    for r in results:
        dl = r.delay_ledger
        lines.append(f"| N={r.consensus_window} | {dl.delay_0} | {dl.delay_1} | "
                     f"{dl.delay_2} | {dl.delay_3} | {dl.total_consensus} |")
    lines.append("")

    # Per-segment comparison
    lines.append("## Deliverable 3: Per-Segment Comparison")
    lines.append("")
    for seg_name in ["train", "forward_1", "forward_2", "holdout"]:
        lines.append(f"### {seg_name}")
        lines.append("")
        lines.append("| Metric | N=0 | N=1 | N=2 | N=3 |")
        lines.append("|--------|-----|-----|-----|-----|")
        for r in results:
            seg = next(s for s in r.segments if s.segment == seg_name)
        # Trades row
        vals = []
        for r in results:
            seg = next(s for s in r.segments if s.segment == seg_name)
            vals.append(str(seg.trades))
        lines.append(f"| Trades | {' | '.join(vals)} |")
        # min_trades row
        vals = []
        for r in results:
            seg = next(s for s in r.segments if s.segment == seg_name)
            vals.append("OK" if seg.min_trades_met else "**MISS**")
        lines.append(f"| min_trades | {' | '.join(vals)} |")
        # Fitness row
        vals = []
        for r in results:
            seg = next(s for s in r.segments if s.segment == seg_name)
            vals.append(f"{seg.fitness:.4f}")
        lines.append(f"| Fitness | {' | '.join(vals)} |")
        # Return row
        vals = []
        for r in results:
            seg = next(s for s in r.segments if s.segment == seg_name)
            vals.append(f"{seg.total_return:+.4f}")
        lines.append(f"| Return | {' | '.join(vals)} |")
        # Win rate row
        vals = []
        for r in results:
            seg = next(s for s in r.segments if s.segment == seg_name)
            vals.append(f"{seg.win_rate:.3f}")
        lines.append(f"| Win rate | {' | '.join(vals)} |")
        lines.append("")

    # Verdict
    lines.append("## V-1 Verdict")
    lines.append("")

    # Determine best candidate
    best = None
    best_n = 0
    for r in results[1:]:  # skip baseline
        if (r.fire_rate_uplift >= 1.5
                and r.fitness_ratio >= 0.80
                and r.occupancy_block_rate <= baseline.occupancy_block_rate * 1.5):
            if best is None or r.fire_rate_uplift > best.fire_rate_uplift:
                best = r
                best_n = r.consensus_window

    if best is not None:
        lines.append(f"**PASS**: N={best_n} meets all criteria")
        lines.append(f"- Fire rate uplift: {best.fire_rate_uplift:.2f}× (≥ 1.5× required)")
        lines.append(f"- Fitness ratio: {best.fitness_ratio:.2f} (≥ 0.80 required)")
        lines.append(f"- Occupancy block rate: {best.occupancy_block_rate:.1f}% "
                     f"(≤ {baseline.occupancy_block_rate * 1.5:.1f}% limit)")
    else:
        # Check if any has uplift but fails quality
        any_uplift = any(r.fire_rate_uplift >= 1.5 for r in results[1:])
        if any_uplift:
            lines.append("**INFORMATIVE_FAIL**: Fire rate uplift achieved but quality/stability guard failed")
        else:
            lines.append("**BLOCK**: No configuration achieved ≥ 1.5× fire rate uplift")

        for r in results[1:]:
            status = []
            if r.fire_rate_uplift < 1.5:
                status.append(f"uplift {r.fire_rate_uplift:.2f}× < 1.5×")
            if r.fitness_ratio < 0.80:
                status.append(f"fitness ratio {r.fitness_ratio:.2f} < 0.80")
            if r.occupancy_block_rate > baseline.occupancy_block_rate * 1.5:
                status.append(f"block rate {r.occupancy_block_rate:.1f}% > limit")
            lines.append(f"- N={r.consensus_window}: {', '.join(status)}")

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run_v1():
    print("=" * 60)
    print("SOL S-1 V-1 — Consensus Window Expansion Backtest")
    print("=" * 60)
    print(f"Symbol: {SYMBOL}")
    print(f"Windows: {CONSENSUS_WINDOWS}")
    print(f"Total bars: {TOTAL_BARS}")
    print()

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
    print(f"Loaded {len(ohlcv)} bars")

    # Pre-analysis
    print("\n[PRE-ANALYSIS] Computing signal distribution...")
    pre_analysis = precompute_signal_analysis(ohlcv)
    print(f"  SMC fired: {pre_analysis['smc_fired']} ({pre_analysis['smc_rate_pct']}%)")
    print(f"  WT fired: {pre_analysis['wt_fired']} ({pre_analysis['wt_rate_pct']}%)")
    for n in [0, 1, 2, 3]:
        cum = pre_analysis['delay_cumulative'][n]
        inc = pre_analysis['delay_incremental'][n]
        print(f"  N={n}: cumulative={cum} (+{inc} new)")

    # Precompute signals once
    print("\n[PRECOMPUTE] Computing SMC/WT signals for occupancy/delay analysis...")
    smc_signals_arr, wt_signals_arr = _precompute_consensus_arrays(ohlcv)
    print(f"  Done. SMC nonzero: {np.count_nonzero(smc_signals_arr)}, "
          f"WT nonzero: {np.count_nonzero(wt_signals_arr)}")

    # Run backtests
    results: list[ConfigResult] = []

    for n in CONSENSUS_WINDOWS:
        label = f"N={n}" if n > 0 else "baseline"
        print(f"\n[BACKTEST] Running {label}...")

        config_result = run_backtest_config(ohlcv, consensus_window=n)

        # Occupancy metrics
        print(f"  Computing occupancy metrics...")
        consensus_signals, blocked = compute_occupancy_metrics(
            ohlcv, consensus_window=n,
            smc_signals=smc_signals_arr, wt_signals=wt_signals_arr,
        )
        config_result.consensus_signals = consensus_signals
        config_result.blocked_by_occupancy = blocked
        config_result.occupancy_block_rate = round(
            blocked / consensus_signals * 100, 2
        ) if consensus_signals > 0 else 0.0

        # Delay ledger
        print(f"  Computing delay ledger...")
        config_result.delay_ledger = compute_delay_ledger(
            ohlcv, consensus_window=n,
            smc_signals=smc_signals_arr, wt_signals=wt_signals_arr,
        )

        print(f"  Trades: {config_result.total_trades}")
        print(f"  Fire rate: {config_result.fire_rate_pct}%")
        print(f"  Fitness: {config_result.full_fitness}")
        print(f"  Consensus signals: {consensus_signals} (blocked: {blocked})")
        print(f"  Occupancy block rate: {config_result.occupancy_block_rate}%")
        print(f"  Delay ledger: d0={config_result.delay_ledger.delay_0} "
              f"d1={config_result.delay_ledger.delay_1} "
              f"d2={config_result.delay_ledger.delay_2} "
              f"d3={config_result.delay_ledger.delay_3}")

        for seg in config_result.segments:
            mt = "OK" if seg.min_trades_met else "MISS"
            print(f"    {seg.segment}: {seg.trades}t fitness={seg.fitness} min_trades={mt}")

        results.append(config_result)

    # Compute uplifts vs baseline
    baseline = results[0]
    for r in results[1:]:
        r.fire_rate_uplift = round(
            r.total_trades / baseline.total_trades, 2
        ) if baseline.total_trades > 0 else 0.0
        r.fitness_ratio = round(
            r.full_fitness / baseline.full_fitness, 2
        ) if baseline.full_fitness > 0 else (1.0 if r.full_fitness == 0 else float("inf"))
        r.trade_uplift = r.fire_rate_uplift
        # Newly unblocked: consensus at N that weren't at N=0
        r.newly_unblocked_trades = max(0, r.total_trades - baseline.total_trades)
        # Reblocked: new consensus signals that got blocked
        r.reblocked_by_occupancy = max(0, r.blocked_by_occupancy - baseline.blocked_by_occupancy)

    # Generate report
    print(f"\n{'='*60}")
    print("DELIVERABLES")
    print(f"{'='*60}\n")

    report = generate_report(pre_analysis, results)
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
        "v1_at": datetime.now(timezone.utc).isoformat(),
        "chain": "Phase C Post-Closure — SOL S-1",
        "step": "V-1",
        "candidate": "Candidate 1 (Consensus window expansion)",
        "symbol": SYMBOL,
        "total_bars": len(ohlcv),
        "pre_analysis": pre_analysis,
        "configs": [],
    }

    for r in results:
        cfg = {
            "consensus_window": r.consensus_window,
            "label": r.label,
            "total_trades": r.total_trades,
            "fire_rate_pct": r.fire_rate_pct,
            "total_return": r.total_return,
            "win_rate": r.win_rate,
            "max_drawdown": r.max_drawdown,
            "full_fitness": r.full_fitness,
            "consensus_signals": r.consensus_signals,
            "blocked_by_occupancy": r.blocked_by_occupancy,
            "occupancy_block_rate": r.occupancy_block_rate,
            "fire_rate_uplift": r.fire_rate_uplift,
            "fitness_ratio": r.fitness_ratio,
            "trade_uplift": r.trade_uplift,
            "newly_unblocked_trades": r.newly_unblocked_trades,
            "reblocked_by_occupancy": r.reblocked_by_occupancy,
            "delay_ledger": asdict(r.delay_ledger),
            "segments": [asdict(s) for s in r.segments],
        }
        log_data["configs"].append(cfg)

    # Determine verdict
    best = None
    for r in results[1:]:
        if (r.fire_rate_uplift >= 1.5
                and r.fitness_ratio >= 0.80
                and r.occupancy_block_rate <= baseline.occupancy_block_rate * 1.5):
            if best is None or r.fire_rate_uplift > best.fire_rate_uplift:
                best = r
    if best:
        log_data["verdict"] = "PASS"
        log_data["best_n"] = best.consensus_window
    else:
        any_uplift = any(r.fire_rate_uplift >= 1.5 for r in results[1:])
        log_data["verdict"] = "INFORMATIVE_FAIL" if any_uplift else "BLOCK"
        log_data["best_n"] = None

    log_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "docs", "operations", "evidence",
        "sol_s1_v1_backtest_log.json",
    )
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False, cls=_NumpyEncoder)
    print(f"\n[LOG] Saved: {log_path}")


def main():
    asyncio.run(run_v1())


if __name__ == "__main__":
    main()
