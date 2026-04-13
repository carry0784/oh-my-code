"""
FullCycleBacktester — Phase B (400-Day 4-Segment Replay Engine)

B-1 Scope: Dataclasses + Segment Split Logic
B-2 Scope: Orchestrator + Regime Diversity + Verdict (NOT YET)
B-3 Scope: Smoke Test + Compliance Audit (NOT YET)

Design constraints:
  - Orchestrator ONLY — no existing module signature changes
  - Read-only data access via HistoryDataManager
  - No API endpoints, no Celery tasks, no live path
  - Deterministic: same input → same result
  - DL-001~006 data leakage rules enforced
  - BR-001~004 batch regime rules enforced

References:
  - phase_b_replay_engine_design_lock.md
  - phase_b_implementation_go_package.md (B-1 scope)
  - phase_b_implementation_go_receipt.md (B-1 authorization)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.backtesting_engine import BacktestConfig, BacktestResult
from app.services.fitness_function import FitnessBreakdown
from app.services.walk_forward_validator import WalkForwardResult
from app.services.regime_detector import BatchRegimeResult

from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────────

# 400-day default segment ratios (design lock §3)
DEFAULT_TRAIN_RATIO = 0.60       # 240 days = 5,760 bars @ 1h
DEFAULT_FORWARD1_RATIO = 0.20    # 80 days  = 1,920 bars
DEFAULT_FORWARD2_RATIO = 0.10    # 40 days  = 960 bars
DEFAULT_HOLDOUT_RATIO = 0.10     # 40 days  = 960 bars

# Fitness weights for overall_fitness (design review §6.4.1)
# Holdout excluded from overall_fitness (blind test purpose)
W_TRAIN = 0.40
W_FORWARD1 = 0.35
W_FORWARD2 = 0.25

# Segment names (canonical, ordered)
SEGMENT_NAMES = ("train", "forward_1", "forward_2", "holdout")

# Minimum bars per segment to be viable
MIN_SEGMENT_BARS = 100


# ── Data Contracts ───────────────────────────────────────────────────


@dataclass
class FullCycleConfig:
    """Configuration for a 400-day full-cycle backtest.

    Ratio sum must equal 1.0. Segment boundaries are computed
    from total candle count, not from timestamps directly.
    """

    exchange: str = "binance"
    symbol: str = "SOL/USDT"
    timeframe: str = "1h"

    # Segment ratios (must sum to 1.0)
    train_ratio: float = DEFAULT_TRAIN_RATIO
    forward1_ratio: float = DEFAULT_FORWARD1_RATIO
    forward2_ratio: float = DEFAULT_FORWARD2_RATIO
    holdout_ratio: float = DEFAULT_HOLDOUT_RATIO

    # BacktestingEngine configuration (passed through, not modified)
    lookback: int = 50
    backtest_config: BacktestConfig = field(default_factory=BacktestConfig)

    def validate(self) -> list[str]:
        """Validate config invariants. Returns list of error messages (empty = valid)."""
        errors: list[str] = []

        ratio_sum = (
            self.train_ratio
            + self.forward1_ratio
            + self.forward2_ratio
            + self.holdout_ratio
        )
        if abs(ratio_sum - 1.0) > 1e-9:
            errors.append(
                f"Segment ratios must sum to 1.0, got {ratio_sum:.6f}"
            )

        for name, ratio in [
            ("train_ratio", self.train_ratio),
            ("forward1_ratio", self.forward1_ratio),
            ("forward2_ratio", self.forward2_ratio),
            ("holdout_ratio", self.holdout_ratio),
        ]:
            if ratio <= 0.0:
                errors.append(f"{name} must be > 0, got {ratio}")

        if self.lookback < 1:
            errors.append(f"lookback must be >= 1, got {self.lookback}")

        return errors


@dataclass
class SegmentResult:
    """Result of a single segment backtest.

    Each segment holds its own BacktestResult, FitnessBreakdown,
    and regime distribution. Segments are independent — no data
    sharing between them (DL-001).
    """

    segment_name: str = ""            # "train", "forward_1", "forward_2", "holdout"
    start_ts: int = 0                 # First candle open_time (ms)
    end_ts: int = 0                   # Last candle open_time (ms)
    bars: int = 0                     # Total candles in segment
    effective_bars: int = 0           # Bars after lookback exclusion

    # Results (populated by B-2 orchestrator)
    backtest: BacktestResult = field(default_factory=BacktestResult)
    fitness: FitnessBreakdown = field(default_factory=FitnessBreakdown)
    regime_distribution: dict[str, float] = field(default_factory=dict)

    # DL-005: lookback boundary bars excluded
    lookback_excluded_bars: int = 0


@dataclass
class FullCycleResult:
    """Complete 400-day full-cycle backtest result.

    Aggregates all segment results, walk-forward validation,
    regime diversity, and final verdict.
    """

    config: FullCycleConfig = field(default_factory=FullCycleConfig)

    # Per-segment results (keyed by segment name)
    segments: dict[str, SegmentResult] = field(default_factory=dict)

    # Walk-forward on train segment (populated by B-2)
    walk_forward: WalkForwardResult | None = None

    # Regime diversity: 1 - HHI(regime_proportions), threshold >= 0.55
    regime_diversity_score: float = 0.0

    # Overall fitness (weighted: train 0.40, fw1 0.35, fw2 0.25)
    # Holdout excluded (blind test)
    overall_fitness: float = 0.0

    # Holdout executed flag (v1.1 addition, DL-003 tracking)
    holdout_executed: bool = False

    # DL check (True = no leakage detected)
    data_leakage_check: bool = True

    # Final verdict: PASS / FAIL / PENDING
    verdict: str = "PENDING"

    def summary(self) -> dict[str, Any]:
        """Return a concise summary dict for logging/receipt."""
        seg_summary = {}
        for name, seg in self.segments.items():
            seg_summary[name] = {
                "bars": seg.bars,
                "effective_bars": seg.effective_bars,
                "fitness": seg.fitness.total,
                "start_ts": seg.start_ts,
                "end_ts": seg.end_ts,
            }

        return {
            "symbol": self.config.symbol,
            "exchange": self.config.exchange,
            "timeframe": self.config.timeframe,
            "segments": seg_summary,
            "regime_diversity_score": self.regime_diversity_score,
            "overall_fitness": self.overall_fitness,
            "holdout_executed": self.holdout_executed,
            "data_leakage_check": self.data_leakage_check,
            "verdict": self.verdict,
        }


# ── Segment Splitter ────────────────────────────────────────────────


class SegmentSplitter:
    """Splits OHLCV candles into 4 non-overlapping segments.

    Design rules enforced:
      DL-001: Train data does not appear in Forward/Holdout
      DL-004: No future data reference (time-ordered split)
      DL-005: Lookback boundary bars excluded from effective count
      DL-006: Each segment's candles are bounded to that segment

    Boundary rule:
      - Boundary bar belongs to the EARLIER segment
      - No timestamp overlap between adjacent segments
      - Split is purely index-based on time-sorted candles
    """

    @staticmethod
    def split(
        ohlcv: list[list],
        config: FullCycleConfig,
    ) -> dict[str, list[list]]:
        """Split candles into 4 segments.

        Args:
            ohlcv: List of [timestamp_ms, open, high, low, close, volume],
                   MUST be sorted by timestamp ASC (HistoryDataManager guarantees this).
            config: FullCycleConfig with segment ratios.

        Returns:
            Dict keyed by segment name → list of candles.

        Raises:
            ValueError: If config is invalid, data is empty, or segments too small.
        """
        # ── Validate config ──────────────────────────────────
        config_errors = config.validate()
        if config_errors:
            raise ValueError(
                f"Invalid FullCycleConfig: {'; '.join(config_errors)}"
            )

        # ── Validate input data ──────────────────────────────
        if not ohlcv:
            raise ValueError("Cannot split empty OHLCV data")

        total = len(ohlcv)

        # ── Compute segment boundaries (index-based) ─────────
        #
        # Train:     [0, train_end)
        # Forward-1: [train_end, fw1_end)
        # Forward-2: [fw1_end, fw2_end)
        # Holdout:   [fw2_end, total)
        #
        # Boundary bar rule: bar at boundary index belongs to
        # the LATER segment (i.e., train_end is first bar of fw1).
        # This means the last bar of train is at index train_end - 1.

        train_end = int(total * config.train_ratio)
        fw1_end = train_end + int(total * config.forward1_ratio)
        fw2_end = fw1_end + int(total * config.forward2_ratio)
        # Holdout gets the remainder (avoids rounding loss)

        # ── Validate minimum segment sizes ───────────────────
        boundaries = {
            "train": (0, train_end),
            "forward_1": (train_end, fw1_end),
            "forward_2": (fw1_end, fw2_end),
            "holdout": (fw2_end, total),
        }

        for seg_name, (start, end) in boundaries.items():
            seg_size = end - start
            if seg_size < MIN_SEGMENT_BARS:
                raise ValueError(
                    f"Segment '{seg_name}' has {seg_size} bars, "
                    f"minimum is {MIN_SEGMENT_BARS}. "
                    f"Total candles: {total}"
                )

        # ── Slice candles ────────────────────────────────────
        segments = {
            "train": ohlcv[0:train_end],
            "forward_1": ohlcv[train_end:fw1_end],
            "forward_2": ohlcv[fw1_end:fw2_end],
            "holdout": ohlcv[fw2_end:total],
        }

        # ── DL-001 / DL-004 / DL-006 verification ───────────
        # Verify no timestamp overlap between adjacent segments
        for i in range(len(SEGMENT_NAMES) - 1):
            curr_name = SEGMENT_NAMES[i]
            next_name = SEGMENT_NAMES[i + 1]
            curr_seg = segments[curr_name]
            next_seg = segments[next_name]

            if curr_seg and next_seg:
                last_ts_curr = curr_seg[-1][0]   # timestamp of last candle
                first_ts_next = next_seg[0][0]   # timestamp of first candle

                if last_ts_curr >= first_ts_next:
                    raise ValueError(
                        f"DL-001 violation: timestamp overlap between "
                        f"'{curr_name}' (last_ts={last_ts_curr}) and "
                        f"'{next_name}' (first_ts={first_ts_next})"
                    )

        # ── Log split results ────────────────────────────────
        logger.info(
            "segments_split",
            total_candles=total,
            train=len(segments["train"]),
            forward_1=len(segments["forward_1"]),
            forward_2=len(segments["forward_2"]),
            holdout=len(segments["holdout"]),
        )

        return segments

    @staticmethod
    def build_segment_results(
        segments: dict[str, list[list]],
        lookback: int,
    ) -> dict[str, SegmentResult]:
        """Build SegmentResult shells from split candles.

        Populates metadata only (bars, timestamps, lookback exclusion).
        BacktestResult and FitnessBreakdown are left as defaults
        — populated by B-2 orchestrator.

        Args:
            segments: Output of split().
            lookback: Number of lookback bars required by strategy.

        Returns:
            Dict keyed by segment name → SegmentResult.
        """
        results: dict[str, SegmentResult] = {}

        for seg_name in SEGMENT_NAMES:
            candles = segments.get(seg_name, [])
            if not candles:
                results[seg_name] = SegmentResult(segment_name=seg_name)
                continue

            bars = len(candles)
            first_ts = int(candles[0][0])
            last_ts = int(candles[-1][0])

            # DL-005: First segment (train) needs no lookback exclusion
            # because there's no prior segment. For forward/holdout segments,
            # the first `lookback` bars are needed for indicator warmup but
            # should NOT be counted as tradeable (effective) bars.
            #
            # Note: The actual bar exclusion during backtesting is handled
            # by BacktestingEngine (it already skips the first `lookback` bars).
            # Here we just track the count for reporting/verification.
            if seg_name == "train":
                lookback_excluded = 0
            else:
                lookback_excluded = min(lookback, bars)

            effective = bars - lookback_excluded

            results[seg_name] = SegmentResult(
                segment_name=seg_name,
                start_ts=first_ts,
                end_ts=last_ts,
                bars=bars,
                effective_bars=effective,
                lookback_excluded_bars=lookback_excluded,
            )

        logger.info(
            "segment_results_built",
            segments={
                name: {
                    "bars": r.bars,
                    "effective": r.effective_bars,
                    "excluded": r.lookback_excluded_bars,
                }
                for name, r in results.items()
            },
        )

        return results

    @staticmethod
    def validate_no_leakage(
        segments: dict[str, list[list]],
    ) -> tuple[bool, list[str]]:
        """Validate DL-001 through DL-006 compliance.

        Args:
            segments: Output of split().

        Returns:
            (is_clean, violations) — True if no leakage, list of violation messages.
        """
        violations: list[str] = []

        # ── DL-001: No train data in forward/holdout ─────────
        # Collect all timestamps per segment
        ts_sets: dict[str, set[int]] = {}
        for seg_name in SEGMENT_NAMES:
            candles = segments.get(seg_name, [])
            ts_sets[seg_name] = {int(c[0]) for c in candles}

        # Check train timestamps don't appear in later segments
        train_ts = ts_sets.get("train", set())
        for later_seg in ("forward_1", "forward_2", "holdout"):
            overlap = train_ts & ts_sets.get(later_seg, set())
            if overlap:
                violations.append(
                    f"DL-001: {len(overlap)} train timestamps found in "
                    f"'{later_seg}': {sorted(list(overlap))[:5]}..."
                )

        # ── DL-004: No future data (strict ordering) ────────
        for i in range(len(SEGMENT_NAMES) - 1):
            curr_name = SEGMENT_NAMES[i]
            next_name = SEGMENT_NAMES[i + 1]
            curr_candles = segments.get(curr_name, [])
            next_candles = segments.get(next_name, [])

            if curr_candles and next_candles:
                if int(curr_candles[-1][0]) >= int(next_candles[0][0]):
                    violations.append(
                        f"DL-004: '{curr_name}' last_ts "
                        f"({curr_candles[-1][0]}) >= "
                        f"'{next_name}' first_ts ({next_candles[0][0]})"
                    )

        # ── DL-006: Each segment is self-bounded ────────────
        for seg_name in SEGMENT_NAMES:
            candles = segments.get(seg_name, [])
            if len(candles) < 2:
                continue
            timestamps = [int(c[0]) for c in candles]
            # Check monotonically increasing within segment
            for j in range(1, len(timestamps)):
                if timestamps[j] <= timestamps[j - 1]:
                    violations.append(
                        f"DL-006: Non-monotonic timestamp in '{seg_name}' "
                        f"at index {j}: {timestamps[j]} <= {timestamps[j-1]}"
                    )
                    break  # One violation per segment is enough

        is_clean = len(violations) == 0

        if is_clean:
            logger.info("leakage_check_passed", segments=list(segments.keys()))
        else:
            logger.warning(
                "leakage_check_failed",
                violation_count=len(violations),
                violations=violations,
            )

        return is_clean, violations


# ── B-2: FullCycleBacktester (Orchestrator) ─────────────────────────
# Implemented per phase_b_b2_go_package.md
# APPEND ONLY — B-1 core (lines 1-455) is FROZEN
# ─────────────────────────────────────────────────────────────────────

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.history_data_manager import HistoryDataManager
from app.services.backtesting_engine import BacktestingEngine
from app.services.fitness_function import FitnessFunction
from app.services.walk_forward_validator import WalkForwardValidator
from app.services.regime_detector import RegimeDetector
from strategies.base import BaseStrategy

# Verdict thresholds (design lock §9)
TRAIN_FITNESS_THRESHOLD = 0.4
FORWARD1_FITNESS_THRESHOLD = 0.3
FORWARD2_FITNESS_THRESHOLD = 0.25
WF_EFFICIENCY_THRESHOLD = 0.5
RDS_THRESHOLD = 0.55

# Data coverage threshold (FM-001)
COVERAGE_THRESHOLD_PCT = 95.0


class FullCycleBacktester:
    """400-day 4-segment full-cycle backtest orchestrator.

    Composes existing modules (all used as-is, no modifications):
      - HistoryDataManager  → replay candle query (async)
      - SegmentSplitter     → 4-segment split + leakage validation (B-1)
      - BacktestingEngine   → per-segment backtest (sync)
      - FitnessFunction     → per-segment fitness evaluation (sync)
      - RegimeDetector      → batch regime classification (sync)
      - WalkForwardValidator → train segment WF analysis (sync)

    Design constraints:
      - B-1 core (dataclasses, SegmentSplitter) is FROZEN
      - DL-002: strategy instance is NOT re-created between segments
      - DL-003: holdout is executed exactly once
      - BR-001~004: batch regime results are analysis-only
    """

    def __init__(self, config: FullCycleConfig | None = None):
        self.config = config or FullCycleConfig()
        self._data_mgr = HistoryDataManager()
        self._engine = BacktestingEngine(self.config.backtest_config)
        self._fitness = FitnessFunction()
        self._regime = RegimeDetector()
        self._wf = WalkForwardValidator(config=self.config.backtest_config)

    async def run(
        self,
        session: AsyncSession,
        strategy: BaseStrategy,
    ) -> FullCycleResult:
        """Execute full 4-segment cycle.

        Args:
            session: Async DB session for replay data access.
            strategy: Strategy instance (single instance, DL-002 compliant).

        Returns:
            FullCycleResult with verdict (PASS/FAIL) and all segment details.
        """
        result = FullCycleResult(config=self.config)
        cfg = self.config

        # ── Step 1: Load replay candles ──────────────────────
        ohlcv = await self._data_mgr.get_replay_candles(
            session, cfg.exchange, cfg.symbol, cfg.timeframe,
        )
        total_bars = len(ohlcv)

        logger.info(
            "full_cycle_start",
            symbol=cfg.symbol,
            exchange=cfg.exchange,
            total_bars=total_bars,
        )

        if total_bars == 0:
            result.verdict = "FAIL"
            logger.warning("full_cycle_no_data", symbol=cfg.symbol)
            return result

        # ── Step 2: Validate coverage ────────────────────────
        coverage = await self._data_mgr.check_coverage(
            session, cfg.exchange, cfg.symbol, cfg.timeframe,
        )
        if coverage.coverage_pct < COVERAGE_THRESHOLD_PCT:
            result.verdict = "FAIL"
            logger.warning(
                "full_cycle_insufficient_coverage",
                coverage_pct=coverage.coverage_pct,
                threshold=COVERAGE_THRESHOLD_PCT,
            )
            return result

        # ── Step 3: Split into 4 segments ────────────────────
        segments = SegmentSplitter.split(ohlcv, cfg)

        # ── Step 4: Validate no leakage (DL-001~006) ────────
        is_clean, violations = SegmentSplitter.validate_no_leakage(segments)
        result.data_leakage_check = is_clean
        if not is_clean:
            result.verdict = "FAIL"
            logger.error(
                "full_cycle_leakage_detected",
                violations=violations,
            )
            return result

        # ── Step 5: Build segment result shells ──────────────
        result.segments = SegmentSplitter.build_segment_results(
            segments, cfg.lookback,
        )

        # ── Step 6: Run backtest + fitness per segment ───────
        # DL-002: same strategy instance for all segments (no re-creation)
        verdict_inputs: dict[str, float] = {}

        for seg_name in SEGMENT_NAMES:
            seg_candles = segments[seg_name]
            seg_result = result.segments[seg_name]

            bt_result = self._engine.run(
                strategy, seg_candles, cfg.lookback,
            )
            seg_result.backtest = bt_result

            fb = self._fitness.evaluate(bt_result.performance)
            seg_result.fitness = fb
            verdict_inputs[seg_name] = fb.total

            # DL-003: mark holdout as executed (exactly once)
            if seg_name == "holdout":
                result.holdout_executed = True

            logger.info(
                "segment_backtest_done",
                segment=seg_name,
                bars=seg_result.bars,
                trades=bt_result.performance.total_trades,
                fitness=fb.total,
            )

        # ── Step 7: Regime diversity ─────────────────────────
        all_batch = self._regime.detect_batch(ohlcv)
        result.regime_diversity_score = self._compute_regime_diversity(
            all_batch, segments,
        )

        # Write per-segment regime distribution to SegmentResult
        self._fill_segment_regime_distribution(
            all_batch, segments, result.segments,
        )

        # ── Step 8: Walk-forward on train segment ────────────
        wf_result = self._wf.validate(
            strategy, segments["train"], cfg.lookback,
        )
        result.walk_forward = wf_result

        logger.info(
            "walk_forward_done",
            efficiency_ratio=wf_result.efficiency_ratio,
            is_overfit=wf_result.is_overfit,
            consistency=wf_result.consistency,
        )

        # ── Step 9: Overall fitness ──────────────────────────
        result.overall_fitness = self._compute_overall_fitness(
            verdict_inputs,
        )

        # ── Step 10: Verdict ─────────────────────────────────
        result.verdict = self._compute_verdict(result)

        logger.info(
            "full_cycle_complete",
            symbol=cfg.symbol,
            verdict=result.verdict,
            overall_fitness=result.overall_fitness,
            rds=result.regime_diversity_score,
            wf_eff=wf_result.efficiency_ratio,
        )

        return result

    # ── Private Methods ─────────────────────────────────────────

    def _compute_regime_diversity(
        self,
        batch_results: list[BatchRegimeResult],
        segments: dict[str, list[list]],
    ) -> float:
        """Compute Regime Diversity Score = 1 - HHI(regime_proportions).

        Uses regime distribution across ALL segments combined.
        BR-001: results are analysis-only, not connected to execution.

        Returns:
            RDS value (0.0 to 1.0). Higher = more diverse.
        """
        if not batch_results:
            return 0.0

        # Count regimes across all valid bars
        regime_counts: dict[str, int] = {}
        total = 0
        for br in batch_results:
            regime_counts[br.regime] = regime_counts.get(br.regime, 0) + 1
            total += 1

        if total == 0:
            return 0.0

        # Per-segment regime distribution (for SegmentResult reporting)
        # Map timestamps to segment names
        seg_ts_ranges: dict[str, tuple[int, int]] = {}
        for seg_name in SEGMENT_NAMES:
            seg_candles = segments.get(seg_name, [])
            if seg_candles:
                seg_ts_ranges[seg_name] = (
                    int(seg_candles[0][0]),
                    int(seg_candles[-1][0]),
                )

        # Build per-segment regime counts for reporting
        seg_regime_counts: dict[str, dict[str, int]] = {
            name: {} for name in SEGMENT_NAMES
        }
        for br in batch_results:
            for seg_name, (start, end) in seg_ts_ranges.items():
                if start <= br.timestamp <= end:
                    seg_counts = seg_regime_counts[seg_name]
                    seg_counts[br.regime] = seg_counts.get(br.regime, 0) + 1
                    break

        # Compute HHI from global proportions
        proportions = [count / total for count in regime_counts.values()]
        hhi = sum(p * p for p in proportions)
        rds = 1.0 - hhi

        logger.info(
            "regime_diversity_computed",
            regime_counts=regime_counts,
            hhi=round(hhi, 4),
            rds=round(rds, 4),
            threshold=RDS_THRESHOLD,
        )

        return round(rds, 4)

    @staticmethod
    def _fill_segment_regime_distribution(
        batch_results: list[BatchRegimeResult],
        segments: dict[str, list[list]],
        seg_results: dict[str, SegmentResult],
    ) -> None:
        """Write per-segment regime proportions to SegmentResult.regime_distribution.

        BR-001: Results are analysis/reporting only.
        """
        # Build timestamp → segment mapping
        seg_regime_counts: dict[str, dict[str, int]] = {
            name: {} for name in SEGMENT_NAMES
        }
        seg_ts_ranges: dict[str, tuple[int, int]] = {}
        for seg_name in SEGMENT_NAMES:
            candles = segments.get(seg_name, [])
            if candles:
                seg_ts_ranges[seg_name] = (
                    int(candles[0][0]),
                    int(candles[-1][0]),
                )

        for br in batch_results:
            for seg_name, (start, end) in seg_ts_ranges.items():
                if start <= br.timestamp <= end:
                    counts = seg_regime_counts[seg_name]
                    counts[br.regime] = counts.get(br.regime, 0) + 1
                    break

        # Convert counts to proportions and write to SegmentResult
        for seg_name in SEGMENT_NAMES:
            counts = seg_regime_counts[seg_name]
            seg_total = sum(counts.values())
            if seg_total > 0:
                seg_results[seg_name].regime_distribution = {
                    regime: round(count / seg_total, 4)
                    for regime, count in sorted(counts.items())
                }

    @staticmethod
    def _compute_overall_fitness(
        verdict_inputs: dict[str, float],
    ) -> float:
        """Compute weighted overall fitness (design review §6.4.1).

        Formula:
            overall = (W_TRAIN*f_train + W_FW1*f_fw1 + W_FW2*f_fw2)
                      / (W_TRAIN + W_FW1 + W_FW2)

        Holdout is excluded (blind test purpose).
        """
        f_train = verdict_inputs.get("train", 0.0)
        f_fw1 = verdict_inputs.get("forward_1", 0.0)
        f_fw2 = verdict_inputs.get("forward_2", 0.0)

        numerator = (
            W_TRAIN * f_train
            + W_FORWARD1 * f_fw1
            + W_FORWARD2 * f_fw2
        )
        denominator = W_TRAIN + W_FORWARD1 + W_FORWARD2

        if denominator == 0:
            return 0.0

        return round(numerator / denominator, 4)

    @staticmethod
    def _compute_verdict(result: FullCycleResult) -> str:
        """Compute final verdict from 7 PASS conditions.

        All conditions must be met for PASS.
        Returns "PASS" or "FAIL" with reason codes logged.
        """
        reasons: list[str] = []

        # Condition 1: Train fitness >= 0.4
        train_fit = result.segments.get("train")
        if train_fit and train_fit.fitness.total < TRAIN_FITNESS_THRESHOLD:
            reasons.append(
                f"TRAIN_FITNESS_LOW({train_fit.fitness.total:.4f}<{TRAIN_FITNESS_THRESHOLD})"
            )

        # Condition 2: Forward-1 fitness >= 0.3
        fw1_fit = result.segments.get("forward_1")
        if fw1_fit and fw1_fit.fitness.total < FORWARD1_FITNESS_THRESHOLD:
            reasons.append(
                f"FW1_FITNESS_LOW({fw1_fit.fitness.total:.4f}<{FORWARD1_FITNESS_THRESHOLD})"
            )

        # Condition 3: Forward-2 fitness >= 0.25
        fw2_fit = result.segments.get("forward_2")
        if fw2_fit and fw2_fit.fitness.total < FORWARD2_FITNESS_THRESHOLD:
            reasons.append(
                f"FW2_FITNESS_LOW({fw2_fit.fitness.total:.4f}<{FORWARD2_FITNESS_THRESHOLD})"
            )

        # Condition 4: WF efficiency_ratio >= 0.5
        wf = result.walk_forward
        if wf and wf.efficiency_ratio < WF_EFFICIENCY_THRESHOLD:
            reasons.append(
                f"WF_EFFICIENCY_LOW({wf.efficiency_ratio:.4f}<{WF_EFFICIENCY_THRESHOLD})"
            )

        # Condition 5: WF is_overfit == False
        if wf and wf.is_overfit:
            reasons.append("WF_OVERFIT_DETECTED")

        # Condition 6: Regime Diversity Score >= 0.55
        if result.regime_diversity_score < RDS_THRESHOLD:
            reasons.append(
                f"RDS_LOW({result.regime_diversity_score:.4f}<{RDS_THRESHOLD})"
            )

        # Condition 7: Data leakage check == True
        if not result.data_leakage_check:
            reasons.append("DATA_LEAKAGE_DETECTED")

        # ── Verdict ──────────────────────────────────────────
        raw_verdict = "PASS" if len(reasons) == 0 else "FAIL"

        # governed_verdict: same as raw for now (no governance override)
        # Kept separate for future evolution (user idea #2)
        governed_verdict = raw_verdict

        logger.info(
            "verdict_computed",
            raw_verdict=raw_verdict,
            governed_verdict=governed_verdict,
            reason_count=len(reasons),
            reason_codes=reasons,
            pass_conditions_met=7 - len(reasons),
            pass_conditions_total=7,
        )

        return governed_verdict
