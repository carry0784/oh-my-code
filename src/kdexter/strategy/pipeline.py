"""
Strategy Pipeline -- L4~L8 Orchestrator
K-Dexter AOS v4

Orchestrates the full signal-to-execution pipeline:
  Signal -> RiskFilter -> PositionSizer -> ExecutionCell -> Result

This is the entry point for the strategy pipeline, called by
the MainLoop at RUNNING state via the run_execution hook.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from kdexter.strategy.signal import Signal, SignalStatus
from kdexter.strategy.risk_filter import RiskFilter, AccountState, RiskCheckResult
from kdexter.strategy.position_sizer import PositionSizer, SizingResult
from kdexter.strategy.execution_cell import ExecutionCell, ExecutionResult


# ------------------------------------------------------------------ #
# Pipeline result
# ------------------------------------------------------------------ #

class PipelineStage(Enum):
    RISK_CHECK = "RISK_CHECK"
    POSITION_SIZING = "POSITION_SIZING"
    EXECUTION = "EXECUTION"
    COMPLETE = "COMPLETE"


@dataclass
class PipelineResult:
    """End-to-end result of processing a signal through the pipeline."""
    signal_id: str
    success: bool
    final_stage: PipelineStage
    risk_result: Optional[RiskCheckResult] = None
    sizing_result: Optional[SizingResult] = None
    execution_result: Optional[ExecutionResult] = None
    error: Optional[str] = None
    processed_at: datetime = field(default_factory=datetime.utcnow)


# ------------------------------------------------------------------ #
# Pipeline
# ------------------------------------------------------------------ #

class StrategyPipeline:
    """
    L4~L8 Strategy Pipeline orchestrator.

    Chains RiskFilter -> PositionSizer -> ExecutionCell for each signal.
    Tracks pipeline results for evaluation.

    Usage:
        pipeline = StrategyPipeline(
            risk_filter=rf,
            sizer=sizer,
            execution_cell=cell,
        )
        result = await pipeline.process(signal, account_state)
    """

    def __init__(
        self,
        risk_filter: RiskFilter,
        sizer: PositionSizer,
        execution_cell: ExecutionCell,
        account_state_fn: Optional[callable] = None,
    ) -> None:
        self._risk = risk_filter
        self._sizer = sizer
        self._cell = execution_cell
        self._account_fn = account_state_fn or (lambda: AccountState())
        self._results: list[PipelineResult] = []

    async def process(
        self,
        signal: Signal,
        account: Optional[AccountState] = None,
    ) -> PipelineResult:
        """
        Process a single signal through the full pipeline.

        Args:
            signal: trading signal to process
            account: account state (if None, uses account_state_fn)

        Returns:
            PipelineResult with stage-by-stage results
        """
        if account is None:
            account = self._account_fn()

        # Stage 1: Risk filter
        risk_result = self._risk.check(signal, account)
        if not risk_result.passed:
            result = PipelineResult(
                signal_id=signal.signal_id,
                success=False,
                final_stage=PipelineStage.RISK_CHECK,
                risk_result=risk_result,
                error=risk_result.rejection_reason,
            )
            self._results.append(result)
            return result

        # Stage 2: Position sizing
        sizing_result = self._sizer.size(signal, account)
        if not sizing_result.sized:
            result = PipelineResult(
                signal_id=signal.signal_id,
                success=False,
                final_stage=PipelineStage.POSITION_SIZING,
                risk_result=risk_result,
                sizing_result=sizing_result,
                error=sizing_result.rejection_reason,
            )
            self._results.append(result)
            return result

        # Stage 3: Execution
        exec_result = await self._cell.execute(signal)
        if not exec_result.success:
            result = PipelineResult(
                signal_id=signal.signal_id,
                success=False,
                final_stage=PipelineStage.EXECUTION,
                risk_result=risk_result,
                sizing_result=sizing_result,
                execution_result=exec_result,
                error=exec_result.error,
            )
            self._results.append(result)
            return result

        # All stages passed
        result = PipelineResult(
            signal_id=signal.signal_id,
            success=True,
            final_stage=PipelineStage.COMPLETE,
            risk_result=risk_result,
            sizing_result=sizing_result,
            execution_result=exec_result,
        )
        self._results.append(result)
        return result

    async def process_batch(
        self,
        signals: list[Signal],
        account: Optional[AccountState] = None,
    ) -> list[PipelineResult]:
        """Process multiple signals sequentially."""
        results = []
        for sig in signals:
            r = await self.process(sig, account)
            results.append(r)
        return results

    def results(self) -> list[PipelineResult]:
        return list(self._results)

    def success_rate(self) -> float:
        if not self._results:
            return 0.0
        return sum(1 for r in self._results if r.success) / len(self._results)

    def summary(self) -> dict:
        total = len(self._results)
        if total == 0:
            return {"total": 0, "success": 0, "failed": 0, "rate": 0.0}
        success = sum(1 for r in self._results if r.success)
        return {
            "total": total,
            "success": success,
            "failed": total - success,
            "rate": round(success / total, 4),
        }
