"""PPF Integrated Backtester — Phase A orchestrator.

Composes HistoryDataManager + PPFReplayEngine + NoveltyJudgmentEngine
to run PPF gate evaluation over historical OHLCV and produce a baseline
for Phase B live comparison.

Design constraints:
  - FullCycleBacktester is NOT called (complex dependencies, PPF evaluates independently)
  - PPF gate replay runs over full candle history, not per-strategy-segment
  - Results are additive metadata, never influence FullCycleResult.verdict
  - Baseline persisted to ppf_backtest_baselines table for Phase B matching
  - C1: No order generation (gate evaluation only)
  - C10: Parameters frozen at construction
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


# -- Data Contracts --


@dataclass
class PPFSegmentStats:
    """PPF gate statistics for one segment."""

    segment_name: str = ""
    total_bars: int = 0
    evaluated_bars: int = 0
    allow_count: int = 0
    deny_count: int = 0
    deny_rate: float = 0.0
    novelty_count: int = 0
    novelty_rate: float = 0.0
    state_distribution: dict[str, int] = field(default_factory=dict)
    deny_reason_distribution: dict[str, int] = field(default_factory=dict)


@dataclass
class PPFBacktestResult:
    """PPF-augmented backtest result."""

    segment_stats: dict[str, PPFSegmentStats] = field(default_factory=dict)
    overall_deny_rate: float = 0.0
    overall_novelty_rate: float = 0.0
    overall_allow_count: int = 0
    overall_deny_count: int = 0
    overall_evaluated_bars: int = 0
    overall_total_bars: int = 0
    novelty_event_count: int = 0
    fpr: float = 0.0
    tp_count: int = 0
    fp_count: int = 0
    unresolved_count: int = 0
    ppf_params_hash: str = ""


@dataclass
class IntegratedBacktestResult:
    """Combined result: OHLCV coverage + PPF backtest."""

    ppf: PPFBacktestResult = field(default_factory=PPFBacktestResult)
    symbol: str = ""
    exchange: str = ""
    timeframe: str = ""
    candle_count: int = 0
    coverage_pct: float = 0.0
    completed_at: str = ""
    baseline_id: str = ""


# -- Orchestrator --


class PPFIntegratedBacktester:
    """Orchestrates PPF gate replay over historical OHLCV.

    Execution flow:
      1. Load OHLCV history via HistoryDataManager
      2. Run PPFReplayEngine.replay_segment() over full dataset
      3. Run NoveltyJudgmentEngine.judge_from_replay()
      4. Aggregate PPF stats
      5. Persist baseline to DB
      6. Return IntegratedBacktestResult
    """

    def __init__(
        self,
        ppf_params: Any | None = None,
        novelty_window_bars: int = 20,
        novelty_threshold_pct: float = 3.0,
    ) -> None:
        self._ppf_params = ppf_params
        self._novelty_window_bars = novelty_window_bars
        self._novelty_threshold_pct = novelty_threshold_pct

    async def run(
        self,
        session: Any,
        symbol: str = "SOL/USDT",
        exchange: str = "binance",
        timeframe: str = "1h",
    ) -> IntegratedBacktestResult:
        """Execute integrated PPF backtest."""
        from app.services.history_data_manager import HistoryDataManager
        from app.services.ppf_novelty_judgment import NoveltyJudgmentEngine
        from app.services.ppf_replay_engine import PPFReplayEngine

        result = IntegratedBacktestResult(
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
        )

        # Step 1: Load OHLCV history
        hdm = HistoryDataManager()
        candles = await hdm.get_replay_candles(
            session=session,
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
        )

        if not candles:
            logger.warning(
                "ppf_integrated_backtest_no_candles symbol=%s exchange=%s",
                symbol,
                exchange,
            )
            result.completed_at = datetime.now(timezone.utc).isoformat()
            return result

        result.candle_count = len(candles)
        logger.info(
            "ppf_integrated_backtest_loaded symbol=%s bars=%d",
            symbol,
            len(candles),
        )

        # Step 2: PPF Replay over full dataset
        replay_engine = PPFReplayEngine(params=self._ppf_params)
        asset_tag = f"{exchange}:{symbol}:{timeframe}"
        replay_result = replay_engine.replay_segment(
            ohlcv=candles,
            risk_filter_pass=False,
            record_bar_results=True,
            asset_tag=asset_tag,
        )

        logger.info(
            "ppf_integrated_backtest_replay_done "
            "total=%d evaluated=%d allow=%d deny=%d novelty=%d",
            replay_result.total_bars,
            replay_result.evaluated_bars,
            replay_result.allow_count,
            replay_result.deny_count,
            replay_result.novelty_event_count,
        )

        # Step 3: Novelty judgment
        judgment_engine = NoveltyJudgmentEngine(
            window_bars=self._novelty_window_bars,
            disruption_threshold_pct=self._novelty_threshold_pct,
        )
        judgment_report = judgment_engine.judge_from_replay(
            ohlcv=candles,
            novelty_events=replay_result.novelty_events,
        )

        logger.info(
            "ppf_integrated_backtest_judgment_done "
            "total=%d tp=%d fp=%d unresolved=%d fpr=%.4f",
            judgment_report.total_events,
            judgment_report.tp_count,
            judgment_report.fp_count,
            judgment_report.unresolved_count,
            judgment_report.fpr,
        )

        # Step 4: Aggregate into PPFBacktestResult
        params_hash = self._compute_params_hash()

        full_stats = PPFSegmentStats(
            segment_name="full",
            total_bars=replay_result.total_bars,
            evaluated_bars=replay_result.evaluated_bars,
            allow_count=replay_result.allow_count,
            deny_count=replay_result.deny_count,
            deny_rate=replay_result.deny_rate,
            novelty_count=replay_result.novelty_event_count,
            novelty_rate=replay_result.novelty_rate,
            state_distribution=replay_result.state_distribution,
            deny_reason_distribution=replay_result.deny_reason_distribution,
        )

        ppf_result = PPFBacktestResult(
            segment_stats={"full": full_stats},
            overall_deny_rate=replay_result.deny_rate,
            overall_novelty_rate=replay_result.novelty_rate,
            overall_allow_count=replay_result.allow_count,
            overall_deny_count=replay_result.deny_count,
            overall_evaluated_bars=replay_result.evaluated_bars,
            overall_total_bars=replay_result.total_bars,
            novelty_event_count=replay_result.novelty_event_count,
            fpr=judgment_report.fpr,
            tp_count=judgment_report.tp_count,
            fp_count=judgment_report.fp_count,
            unresolved_count=judgment_report.unresolved_count,
            ppf_params_hash=params_hash,
        )

        result.ppf = ppf_result
        result.completed_at = datetime.now(timezone.utc).isoformat()

        # Step 5: Persist baseline
        try:
            baseline_id = await self._persist_baseline(
                session=session,
                result=result,
                symbol=symbol,
                exchange=exchange,
                timeframe=timeframe,
                params_hash=params_hash,
            )
            result.baseline_id = baseline_id
            logger.info(
                "ppf_integrated_backtest_baseline_persisted id=%s",
                baseline_id,
            )
        except Exception as exc:
            logger.warning(
                "ppf_integrated_backtest_baseline_persist_failed error=%s",
                str(exc)[:200],
            )

        return result

    async def _persist_baseline(
        self,
        session: Any,
        result: IntegratedBacktestResult,
        symbol: str,
        exchange: str,
        timeframe: str,
        params_hash: str,
    ) -> str:
        """Persist PPF backtest baseline for Phase B comparison."""
        from app.models.ppf_backtest_baseline import PPFBacktestBaseline

        baseline_id = str(uuid4())
        ppf = result.ppf

        # Serialize distributions as JSON
        full_stats = ppf.segment_stats.get("full")
        deny_dist_json = json.dumps(
            full_stats.deny_reason_distribution if full_stats else {}
        )
        state_dist_json = json.dumps(
            full_stats.state_distribution if full_stats else {}
        )

        # Serialize full result
        result_dict = {
            "symbol": symbol,
            "exchange": exchange,
            "timeframe": timeframe,
            "candle_count": result.candle_count,
            "overall_deny_rate": ppf.overall_deny_rate,
            "overall_novelty_rate": ppf.overall_novelty_rate,
            "overall_allow_count": ppf.overall_allow_count,
            "overall_deny_count": ppf.overall_deny_count,
            "overall_evaluated_bars": ppf.overall_evaluated_bars,
            "novelty_event_count": ppf.novelty_event_count,
            "fpr": ppf.fpr,
            "tp_count": ppf.tp_count,
            "fp_count": ppf.fp_count,
            "unresolved_count": ppf.unresolved_count,
            "completed_at": result.completed_at,
        }

        baseline = PPFBacktestBaseline(
            id=baseline_id,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            ppf_params_hash=params_hash,
            total_bars=ppf.overall_total_bars,
            evaluated_bars=ppf.overall_evaluated_bars,
            deny_rate=ppf.overall_deny_rate,
            novelty_rate=ppf.overall_novelty_rate,
            novelty_count=ppf.novelty_event_count,
            fpr=ppf.fpr,
            allow_count=ppf.overall_allow_count,
            deny_count=ppf.overall_deny_count,
            deny_reason_distribution=deny_dist_json,
            state_distribution=state_dist_json,
            result_json=json.dumps(result_dict),
        )

        session.add(baseline)
        await session.flush()

        return baseline_id

    def _compute_params_hash(self) -> str:
        """Compute SHA-256 hash of PPF parameters for reproducibility."""
        if self._ppf_params is None:
            return hashlib.sha256(b"default_params").hexdigest()[:16]

        try:
            import dataclasses

            params_dict = dataclasses.asdict(self._ppf_params)
            raw = json.dumps(params_dict, sort_keys=True, default=str)
            return hashlib.sha256(raw.encode()).hexdigest()[:16]
        except Exception:
            return hashlib.sha256(str(self._ppf_params).encode()).hexdigest()[:16]
