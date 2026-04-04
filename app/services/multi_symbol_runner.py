"""Multi-Symbol Runner — orchestration for strategy evaluation.

Phase 6A+6B-1+6B-2 of CR-048.  Orchestrates:
  1. Pre-cycle guards (safe mode, drift, trading hours)
  2. Universe selection (eligible symbols)
  3. Per-symbol strategy lookup + routing
  4. Runtime load eligibility check
  5. Feature cache hit/miss
  6. Actual strategy analyze() invocation
  7. Append-only cycle receipt with analysis_status + skip_reason_code

Dry-run mode is the default. No order execution, no broker calls.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from app.services.universe_manager import (
    UniverseManager,
    UniverseSnapshot,
    SelectionOutcome,
)
from app.services.runtime_strategy_loader import (
    LoadEligibilityChecker,
    LoadEligibilityOutput,
    LoadDecision,
)
from app.services.strategy_router import StrategyRouter, RoutingResult
from app.services.feature_cache import FeatureCache, FeatureCacheKey
from app.services.strategy_analyzer import (
    StrategyAnalyzer,
    AnalyzeResult,
    AnalysisStatus,
)

logger = logging.getLogger(__name__)


# ── Cycle Entry Status ────────────────────────────────────────────────


class EntryAction(str, Enum):
    """What happened to a strategy×symbol pair in a cycle."""

    SIGNAL_CANDIDATE = "signal_candidate"  # kept for backwards compat
    ANALYZED_SIGNAL = "analyzed_signal"
    ANALYZED_NO_SIGNAL = "analyzed_no_signal"
    ANALYZED_ERROR = "analyzed_error"
    SKIP_LOAD_REJECTED = "skip_load_rejected"
    SKIP_ROUTE_REJECTED = "skip_route_rejected"
    SKIP_UNIVERSE_EXCLUDED = "skip_universe_excluded"


class CycleSkipReason(str, Enum):
    """Why an entire cycle was skipped (pre-cycle guard)."""

    NONE = "none"  # cycle ran normally
    MARKET_CLOSED = "market_closed"
    SAFE_MODE_ACTIVE = "safe_mode_active"
    DRIFT_ACTIVE = "drift_active"
    DUPLICATE_CYCLE = "duplicate_cycle"  # idempotency guard


@dataclass
class CycleEntry:
    """Record of one strategy×symbol evaluation in a cycle."""

    symbol_id: str
    symbol: str
    strategy_id: str
    timeframe: str
    action: EntryAction
    analysis_status: str | None = None  # signal/no_signal/error/skipped
    skip_reason: str | None = None
    signal_candidate: dict | None = None
    signal_data: dict | None = None  # actual analyze signal output
    error_type: str | None = None
    error_message: str | None = None
    load_decision: str | None = None
    route_result: bool | None = None
    cache_hit: bool | None = None


@dataclass
class CycleReceipt:
    """Append-only receipt for one runner cycle."""

    cycle_id: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    universe_size: int = 0
    strategies_evaluated: int = 0
    signal_candidates: int = 0
    signals_generated: int = 0
    no_signals: int = 0
    errors: int = 0
    skipped: int = 0
    entries: list[CycleEntry] = field(default_factory=list)
    dry_run: bool = True
    skip_reason_code: str = CycleSkipReason.NONE.value

    def finalize(self) -> None:
        self.completed_at = datetime.now(timezone.utc)
        self.signals_generated = sum(
            1 for e in self.entries if e.action == EntryAction.ANALYZED_SIGNAL
        )
        self.no_signals = sum(1 for e in self.entries if e.action == EntryAction.ANALYZED_NO_SIGNAL)
        self.errors = sum(1 for e in self.entries if e.action == EntryAction.ANALYZED_ERROR)
        self.signal_candidates = sum(
            1
            for e in self.entries
            if e.action
            in (
                EntryAction.SIGNAL_CANDIDATE,
                EntryAction.ANALYZED_SIGNAL,
                EntryAction.ANALYZED_NO_SIGNAL,
                EntryAction.ANALYZED_ERROR,
            )
        )
        self.skipped = sum(
            1
            for e in self.entries
            if e.action
            in (
                EntryAction.SKIP_LOAD_REJECTED,
                EntryAction.SKIP_ROUTE_REJECTED,
                EntryAction.SKIP_UNIVERSE_EXCLUDED,
            )
        )

    def to_dict(self) -> dict:
        return {
            "cycle_id": self.cycle_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "universe_size": self.universe_size,
            "strategies_evaluated": self.strategies_evaluated,
            "signal_candidates": self.signal_candidates,
            "signals_generated": self.signals_generated,
            "no_signals": self.no_signals,
            "errors": self.errors,
            "skipped": self.skipped,
            "dry_run": self.dry_run,
            "skip_reason_code": self.skip_reason_code,
            "entries": [
                {
                    "symbol": e.symbol,
                    "strategy_id": e.strategy_id,
                    "timeframe": e.timeframe,
                    "action": e.action.value,
                    "analysis_status": e.analysis_status,
                    "skip_reason": e.skip_reason,
                    "error_type": e.error_type,
                }
                for e in self.entries
            ],
        }


# ── Multi-Symbol Runner ──────────────────────────────────────────────


class MultiSymbolRunner:
    """Multi-symbol strategy evaluation runner.

    Default mode is dry-run (analyze only, no execution).
    """

    def __init__(
        self,
        *,
        universe_mgr: UniverseManager | None = None,
        load_checker: LoadEligibilityChecker | None = None,
        router: StrategyRouter | None = None,
        feature_cache: FeatureCache | None = None,
        analyzer: StrategyAnalyzer | None = None,
    ) -> None:
        self.universe_mgr = universe_mgr or UniverseManager()
        self.load_checker = load_checker or LoadEligibilityChecker()
        self.router = router or StrategyRouter()
        self.feature_cache = feature_cache or FeatureCache()
        self.analyzer = analyzer  # None = no analyze (legacy stub mode)

    def run_cycle(
        self,
        *,
        cycle_id: str,
        symbols: list[dict],
        strategies: list[dict],
        safe_mode_active: bool = False,
        drift_active: bool = False,
        bar_ts: str = "",
        dry_run: bool = True,
    ) -> CycleReceipt:
        """Run one evaluation cycle over the universe.

        If analyzer is set, runs actual analyze(). Otherwise generates
        pending_analyze stubs (backwards compat with 6A tests).
        """
        receipt = CycleReceipt(cycle_id=cycle_id, dry_run=dry_run)

        # Step 1: Universe selection
        universe = self.universe_mgr.select(
            symbols,
            safe_mode_active=safe_mode_active,
            drift_active=drift_active,
        )
        receipt.universe_size = len(universe.selected)

        if not universe.selected:
            receipt.finalize()
            return receipt

        # Step 2: For each selected symbol × strategy pair
        total_evals = 0
        symbols_dict = self._symbols_by_id(symbols)
        for sym_result in universe.selected:
            for strat in strategies:
                total_evals += 1
                entry = self._evaluate_pair(
                    sym_result=sym_result,
                    strat=strat,
                    symbols_dict=symbols_dict,
                    safe_mode_active=safe_mode_active,
                    drift_active=drift_active,
                    bar_ts=bar_ts,
                )
                receipt.entries.append(entry)

        receipt.strategies_evaluated = total_evals
        receipt.finalize()
        return receipt

    def _evaluate_pair(
        self,
        *,
        sym_result,
        strat: dict,
        symbols_dict: dict,
        safe_mode_active: bool,
        drift_active: bool,
        bar_ts: str,
    ) -> CycleEntry:
        """Evaluate one strategy×symbol pair."""
        sym_data = symbols_dict.get(sym_result.symbol_id, {})
        strat_id = strat["id"]
        timeframes = strat.get("timeframes", [])
        if not timeframes:
            return CycleEntry(
                symbol_id=sym_result.symbol_id,
                symbol=sym_result.symbol,
                strategy_id=strat_id,
                timeframe="",
                action=EntryAction.SKIP_ROUTE_REJECTED,
                analysis_status="skipped",
                skip_reason="no_timeframes",
            )

        timeframe = timeframes[0] if isinstance(timeframes, list) else timeframes

        # Step 2a: Routing check
        route_out = self.router.route(
            strategy_id=strat_id,
            strategy_asset_classes=strat.get("asset_classes", []),
            strategy_exchanges=strat.get("exchanges", []),
            strategy_sectors=strat.get("sectors"),
            strategy_timeframes=strat.get("timeframes", []),
            strategy_max_symbols=strat.get("max_symbols", 20),
            symbol=sym_result.symbol,
            symbol_asset_class=sym_data.get("asset_class", ""),
            symbol_exchanges=sym_data.get("exchanges", []),
            symbol_sector=sym_data.get("sector", ""),
            timeframe=timeframe,
        )

        if not route_out.routable:
            return CycleEntry(
                symbol_id=sym_result.symbol_id,
                symbol=sym_result.symbol,
                strategy_id=strat_id,
                timeframe=timeframe,
                action=EntryAction.SKIP_ROUTE_REJECTED,
                analysis_status="skipped",
                skip_reason=",".join(route_out.failed_checks),
                route_result=False,
            )

        # Step 2b: Load eligibility check
        load_out = self.load_checker.check(
            screening_status=sym_data.get("status", ""),
            qualification_status=sym_data.get("qualification_status", ""),
            promotion_eligibility_status=sym_data.get("promotion_eligibility_status", ""),
            paper_evaluation_status=sym_data.get("paper_evaluation_status", ""),
            strategy_status=strat.get("status", ""),
            checksum_expected=strat.get("checksum"),
            checksum_actual=strat.get("checksum_actual"),
            fp_fingerprint_expected=strat.get("fp_fingerprint_expected"),
            fp_fingerprint_actual=strat.get("fp_fingerprint_actual"),
            safe_mode_active=safe_mode_active,
            drift_active=drift_active,
            paper_pass_fresh=strat.get("paper_pass_fresh", True),
        )

        if load_out.decision != LoadDecision.APPROVED:
            return CycleEntry(
                symbol_id=sym_result.symbol_id,
                symbol=sym_result.symbol,
                strategy_id=strat_id,
                timeframe=timeframe,
                action=EntryAction.SKIP_LOAD_REJECTED,
                analysis_status="skipped",
                skip_reason=load_out.primary_reason.value if load_out.primary_reason else "unknown",
                load_decision="rejected",
                route_result=True,
            )

        # Step 2c: Feature cache check
        revision_token = strat.get("fp_fingerprint_actual", "")
        cache_key = FeatureCacheKey(
            symbol=sym_result.symbol,
            timeframe=timeframe,
            bar_ts=bar_ts,
            revision_token=revision_token,
        )
        cached = self.feature_cache.get(cache_key)
        cache_hit = cached is not None

        # Step 2d: Analyze (actual or stub)
        if self.analyzer is not None:
            return self._run_analyze(
                sym_result=sym_result,
                strat=strat,
                timeframe=timeframe,
                features=cached,
                cache_hit=cache_hit,
            )

        # Legacy stub mode (no analyzer): return signal_candidate
        signal_candidate = {
            "symbol": sym_result.symbol,
            "symbol_id": sym_result.symbol_id,
            "strategy_id": strat_id,
            "timeframe": timeframe,
            "cache_hit": cache_hit,
            "features": cached if cache_hit else None,
            "status": "pending_analyze",
        }

        return CycleEntry(
            symbol_id=sym_result.symbol_id,
            symbol=sym_result.symbol,
            strategy_id=strat_id,
            timeframe=timeframe,
            action=EntryAction.SIGNAL_CANDIDATE,
            analysis_status="pending",
            signal_candidate=signal_candidate,
            load_decision="approved",
            route_result=True,
            cache_hit=cache_hit,
        )

    def _run_analyze(
        self,
        *,
        sym_result,
        strat: dict,
        timeframe: str,
        features: dict | None,
        cache_hit: bool,
    ) -> CycleEntry:
        """Run actual analyze() with error isolation."""
        strat_id = strat["id"]
        compute_module = strat.get("compute_module", "")
        ohlcv = strat.get("ohlcv")  # optional OHLCV data

        result = self.analyzer.analyze(
            compute_module=compute_module,
            strategy_id=strat_id,
            symbol=sym_result.symbol,
            timeframe=timeframe,
            ohlcv=ohlcv,
            features=features,
        )

        if result.status == AnalysisStatus.SIGNAL:
            return CycleEntry(
                symbol_id=sym_result.symbol_id,
                symbol=sym_result.symbol,
                strategy_id=strat_id,
                timeframe=timeframe,
                action=EntryAction.ANALYZED_SIGNAL,
                analysis_status="signal",
                signal_data=result.signal.to_dict() if result.signal else None,
                load_decision="approved",
                route_result=True,
                cache_hit=cache_hit,
            )
        elif result.status == AnalysisStatus.NO_SIGNAL:
            return CycleEntry(
                symbol_id=sym_result.symbol_id,
                symbol=sym_result.symbol,
                strategy_id=strat_id,
                timeframe=timeframe,
                action=EntryAction.ANALYZED_NO_SIGNAL,
                analysis_status="no_signal",
                load_decision="approved",
                route_result=True,
                cache_hit=cache_hit,
            )
        else:  # ERROR
            return CycleEntry(
                symbol_id=sym_result.symbol_id,
                symbol=sym_result.symbol,
                strategy_id=strat_id,
                timeframe=timeframe,
                action=EntryAction.ANALYZED_ERROR,
                analysis_status="error",
                error_type=result.error_type,
                error_message=result.error_message,
                load_decision="approved",
                route_result=True,
                cache_hit=cache_hit,
            )

    @staticmethod
    def _symbols_by_id(symbols: list[dict]) -> dict:
        """Index symbols by symbol_id for fast lookup."""
        return {s["symbol_id"]: s for s in symbols}
