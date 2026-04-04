"""Paper Evaluation Service — observation evaluation + promotion state wiring.

Phase 4C of CR-048.  Provides:
  - Internal safe mode / drift state lookup (no caller injection)
  - Paper evaluation via PaperEvaluator engine
  - PaperEvaluationRecord persistence (append-only)
  - Symbol.paper_evaluation_status update
  - Promotion state wiring: connects eligibility → evaluation → decision
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Symbol, SymbolStatus
from app.models.paper_shadow import (
    PaperObservation,
    PaperEvaluationRecord,
    PromotionDecision,
    PromotionEligibility,
    ObservationStatus,
)
from app.models.drift_ledger import DriftLedgerEntry
from app.models.safe_mode import SafeModeState, SafeModeStatus
from app.services.paper_evaluation import (
    PaperEvalInput,
    PaperEvalOutput,
    PaperEvalDecision,
    PaperEvaluator,
    PaperEvalThresholds,
)

logger = logging.getLogger(__name__)

# Singleton safe mode status row ID (matches safe_mode_persistence.py)
_SAFE_MODE_STATUS_ROW_ID = "safe-mode-singleton"


class PaperEvaluationService:
    """Service for paper evaluation and promotion state wiring."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Internal State Queries ──────────────────────────────────────

    async def is_safe_mode_active(self) -> bool:
        """Query DB for safe mode state. Returns True if not NORMAL."""
        result = await self.db.execute(
            select(SafeModeStatus).where(SafeModeStatus.id == _SAFE_MODE_STATUS_ROW_ID)
        )
        status = result.scalar_one_or_none()
        if status is None:
            return False  # no record = NORMAL (first boot)
        return status.current_state != SafeModeState.NORMAL

    async def has_unprocessed_drift(self) -> bool:
        """Query DB for unprocessed drift ledger entries."""
        result = await self.db.execute(
            select(func.count(DriftLedgerEntry.id)).where(
                DriftLedgerEntry.processed == False  # noqa: E712
            )
        )
        count = result.scalar_one()
        return count > 0

    # ── Paper Evaluation ────────────────────────────────────────────

    async def evaluate_paper(
        self,
        symbol_id: str,
        strategy_id: str,
        timeframe: str,
        *,
        evaluator: PaperEvaluator | None = None,
        expected_observations: int = 0,
    ) -> PaperEvalOutput:
        """Evaluate paper observations for a strategy×symbol×timeframe.

        Reads safe mode and drift state from DB internally.
        Aggregates observation history metrics.
        Returns PaperEvalOutput without persistence.
        """
        sym = await self._get_symbol(symbol_id)
        if sym is None:
            raise ValueError(f"Symbol not found: {symbol_id}")

        # Internal state queries (not caller-injected)
        safe_mode_active = await self.is_safe_mode_active()
        drift_active = await self.has_unprocessed_drift()

        # Aggregate observation metrics
        obs_stats = await self._aggregate_observations(strategy_id, sym.symbol, timeframe)

        inp = PaperEvalInput(
            strategy_id=strategy_id,
            symbol=sym.symbol,
            timeframe=timeframe,
            total_observations=obs_stats["total"],
            valid_observations=obs_stats["valid"],
            expected_observations=expected_observations or obs_stats["total"],
            cumulative_return_pct=obs_stats["cumulative_return_pct"],
            max_drawdown_pct=obs_stats["max_drawdown_pct"],
            avg_turnover_annual=obs_stats["avg_turnover_annual"],
            avg_slippage_pct=obs_stats["avg_slippage_pct"],
            safe_mode_active=safe_mode_active,
            drift_active=drift_active,
        )

        ev = evaluator or PaperEvaluator()
        return ev.evaluate(inp)

    async def evaluate_and_record(
        self,
        symbol_id: str,
        strategy_id: str,
        timeframe: str,
        *,
        evaluator: PaperEvaluator | None = None,
        expected_observations: int = 0,
    ) -> PaperEvaluationRecord:
        """Evaluate paper, record result, update Symbol.paper_evaluation_status.

        Returns the PaperEvaluationRecord.
        """
        sym = await self._get_symbol(symbol_id)
        if sym is None:
            raise ValueError(f"Symbol not found: {symbol_id}")

        output = await self.evaluate_paper(
            symbol_id,
            strategy_id,
            timeframe,
            evaluator=evaluator,
            expected_observations=expected_observations,
        )

        now = datetime.now(timezone.utc)
        rules = output.rules
        record = PaperEvaluationRecord(
            strategy_id=strategy_id,
            symbol=sym.symbol,
            timeframe=timeframe,
            observation_count=output.metrics_summary.get("total_observations", 0)
            if output.metrics_summary
            else 0,
            valid_observation_count=output.metrics_summary.get("valid_observations", 0)
            if output.metrics_summary
            else 0,
            expected_observation_count=output.metrics_summary.get("expected_observations", 0)
            if output.metrics_summary
            else 0,
            observation_window_fingerprint=output.observation_window_fingerprint,
            cumulative_return_pct=output.metrics_summary.get("cumulative_return_pct")
            if output.metrics_summary
            else None,
            max_drawdown_pct=output.metrics_summary.get("max_drawdown_pct")
            if output.metrics_summary
            else None,
            avg_turnover_annual=output.metrics_summary.get("avg_turnover_annual")
            if output.metrics_summary
            else None,
            avg_slippage_pct=output.metrics_summary.get("avg_slippage_pct")
            if output.metrics_summary
            else None,
            rule_min_observations=rules[0].passed if len(rules) > 0 else False,
            rule_cumulative_performance=rules[1].passed if len(rules) > 1 else False,
            rule_max_drawdown=rules[2].passed if len(rules) > 2 else False,
            rule_turnover=rules[3].passed if len(rules) > 3 else False,
            rule_slippage=rules[4].passed if len(rules) > 4 else False,
            rule_completeness=rules[5].passed if len(rules) > 5 else False,
            all_passed=output.all_passed,
            decision=output.decision.value,
            primary_reason=(output.primary_reason.value if output.primary_reason else None),
            failed_rules=(json.dumps(output.failed_rules) if output.failed_rules else None),
            metrics_summary=(
                json.dumps(output.metrics_summary) if output.metrics_summary else None
            ),
            evaluated_at=now,
        )
        self.db.add(record)
        await self.db.flush()

        # Update Symbol.paper_evaluation_status
        sym.paper_evaluation_status = output.decision.value
        sym.updated_at = now
        # Set paper_pass_at on PASS for freshness tracking
        if output.decision == PaperEvalDecision.PASS:
            sym.paper_pass_at = now
        await self.db.flush()

        return record

    async def get_evaluation_history(
        self,
        strategy_id: str,
        symbol: str,
        limit: int = 100,
    ) -> list[PaperEvaluationRecord]:
        """Return evaluation records, newest first."""
        result = await self.db.execute(
            select(PaperEvaluationRecord)
            .where(PaperEvaluationRecord.strategy_id == strategy_id)
            .where(PaperEvaluationRecord.symbol == symbol)
            .order_by(PaperEvaluationRecord.evaluated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # ── Internal Helpers ────────────────────────────────────────────

    async def _get_symbol(self, symbol_id: str) -> Symbol | None:
        result = await self.db.execute(select(Symbol).where(Symbol.id == symbol_id))
        return result.scalar_one_or_none()

    async def _aggregate_observations(
        self,
        strategy_id: str,
        symbol: str,
        timeframe: str,
    ) -> dict:
        """Aggregate metrics from observation history.

        Returns a dict with total, valid, and metric averages.
        In minimal implementation, extracts from metrics_snapshot JSON.
        """
        result = await self.db.execute(
            select(PaperObservation)
            .where(PaperObservation.strategy_id == strategy_id)
            .where(PaperObservation.symbol == symbol)
            .where(PaperObservation.timeframe == timeframe)
            .order_by(PaperObservation.observed_at)
        )
        observations = list(result.scalars().all())

        total = len(observations)
        valid = sum(1 for o in observations if o.observation_status == ObservationStatus.RECORDED)

        # Aggregate metrics from snapshots
        returns = []
        drawdowns = []
        turnovers = []
        slippages = []

        for obs in observations:
            if obs.observation_status != ObservationStatus.RECORDED:
                continue
            if not obs.metrics_snapshot:
                continue
            try:
                m = json.loads(obs.metrics_snapshot)
            except (json.JSONDecodeError, TypeError):
                continue

            if "return_pct" in m:
                returns.append(m["return_pct"])
            if "drawdown_pct" in m:
                drawdowns.append(m["drawdown_pct"])
            if "turnover_annual" in m:
                turnovers.append(m["turnover_annual"])
            if "slippage_pct" in m:
                slippages.append(m["slippage_pct"])

        return {
            "total": total,
            "valid": valid,
            "cumulative_return_pct": sum(returns) if returns else None,
            "max_drawdown_pct": max(drawdowns) if drawdowns else None,
            "avg_turnover_annual": (sum(turnovers) / len(turnovers)) if turnovers else None,
            "avg_slippage_pct": (sum(slippages) / len(slippages)) if slippages else None,
        }
