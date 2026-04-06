"""CR-048 Follow-Up 2A P2 — ShadowPipelineOrchestrator.

Read-only orchestrator connecting the adapter layer to the shadow
observation decision flow.

Controlling spec: CR-048 2A P2 ONLY GO
Scope: read-only single-symbol orchestration, no execute, no rollback.

Architecture:
  adapter → run_shadow_pipeline → fetch_existing → compare → record_observation → evaluate_write
  All steps are read-only or append-only (observation log + dry-run receipt).
  execute_bounded_write and rollback_bounded_write are NOT called.

Result normalization:
  WOULD_WRITE — shadow pipeline qualified AND write verdict is would_write
  NOOP        — shadow pipeline qualified but write verdict is would_skip (already matched)
  SKIP_STALE  — adapter returned STALE or UNAVAILABLE quality
  SKIP_UNAVAILABLE — adapter returned UNAVAILABLE or backtest unavailable
  ERROR_INTERNAL — unhandled exception in any pipeline step

Per-symbol failure: does NOT block next-symbol continuation.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import AssetClass, AssetSector
from app.services.adapters.backtest_readiness_stub import BacktestReadinessStub
from app.services.adapters.market_state_adapter import MarketStateAdapter
from app.services.data_provider import (
    BacktestReadiness,
    DataQuality,
    MarketDataSnapshot,
)
from app.services.pipeline_shadow_runner import (
    ShadowRunResult,
    compare_shadow_to_existing,
    run_shadow_pipeline,
)
from app.services.shadow_observation_service import record_shadow_observation
from app.services.shadow_readthrough import (
    ReadthroughComparisonResult,
    fetch_existing_for_comparison,
)
from app.services.shadow_write_service import (
    WriteVerdict,
    evaluate_shadow_write,
)

logger = logging.getLogger(__name__)


# ── P2 Result Enum ──────────────────────────────────────────────


class OrchestratorOutcome(str, Enum):
    """Standardised outcome for a single-symbol orchestration run."""

    WOULD_WRITE = "would_write"
    NOOP = "noop"
    SKIP_STALE = "skip_stale"
    SKIP_UNAVAILABLE = "skip_unavailable"
    ERROR_INTERNAL = "error_internal"


# ── Orchestration Result ────────────────────────────────────────


@dataclass(frozen=True)
class OrchestrationResult:
    """Immutable result of one symbol's orchestration pass."""

    symbol: str
    outcome: OrchestratorOutcome
    shadow_result: ShadowRunResult | None = None
    write_verdict: WriteVerdict | None = None
    intended_value: str | None = None
    observation_id: int | None = None
    receipt_id: str | None = None
    error_detail: str | None = None


# ── Orchestrator ────────────────────────────────────────────────


class ShadowPipelineOrchestrator:
    """Read-only orchestrator: adapter → shadow pipeline → observation → write evaluation.

    Invariants:
      - Zero execute calls (execute_bounded_write NOT imported/used)
      - Zero rollback calls
      - Fail-closed: every error path → ERROR_INTERNAL or SKIP_*
      - Per-symbol isolation: one symbol's failure does not affect others
      - No PR #59 dependency: adapter uses getattr fallback for adx_14
    """

    def __init__(
        self,
        market_adapter: MarketStateAdapter | None = None,
        backtest_stub: BacktestReadinessStub | None = None,
        asset_class: AssetClass = AssetClass.CRYPTO,
        asset_sector: AssetSector = AssetSector.DEFI,
    ):
        self._market_adapter = market_adapter or MarketStateAdapter()
        self._backtest_stub = backtest_stub or BacktestReadinessStub()
        self._asset_class = asset_class
        self._asset_sector = asset_sector

    # ── Single-symbol orchestration ─────────────────────────────

    async def run_single(
        self,
        db: AsyncSession,
        symbol: str,
        now_utc: datetime | None = None,
    ) -> OrchestrationResult:
        """Orchestrate one symbol through the full shadow pipeline.

        Steps:
          1. Fetch market data via adapter (fail-closed)
          2. Fetch backtest readiness via stub (fail-closed)
          3. Gate on input quality (SKIP_STALE / SKIP_UNAVAILABLE)
          4. Run shadow pipeline (pure, no DB)
          5. Fetch existing results for comparison (DB read-only)
          6. Compare shadow vs existing
          7. Record shadow observation (append-only INSERT)
          8. Evaluate write verdict (dry-run receipt INSERT)
          9. Normalise to OrchestratorOutcome
        """
        now = now_utc or datetime.now(timezone.utc)

        try:
            # Step 1: Market data
            market = await self._market_adapter.get_market_data(db, symbol, now)

            # Step 2: Backtest readiness
            backtest = self._backtest_stub.get_readiness(symbol)

            # Step 3: Quality gate
            skip_outcome = self._check_quality_gate(market, backtest)
            if skip_outcome is not None:
                return OrchestrationResult(symbol=symbol, outcome=skip_outcome)

            # Step 4: Shadow pipeline (pure)
            shadow_result = run_shadow_pipeline(
                market=market,
                backtest=backtest,
                asset_class=self._asset_class,
                sector=self._asset_sector,
                now_utc=now,
            )

            # Step 5: Fetch existing for comparison
            existing_input, existing_source = await fetch_existing_for_comparison(db, symbol)

            # Step 6: Compare
            compared = compare_shadow_to_existing(shadow_result, existing_input)

            # Step 7: Build readthrough comparison result
            readthrough_result = ReadthroughComparisonResult(
                symbol=symbol,
                shadow_result=compared,
                comparison_verdict=compared.comparison_verdict,
                reason_comparison=compared.reason_comparison,
                existing_source=existing_source,
            )

            # Step 8: Record observation (append-only, failure swallowed)
            obs_log = await record_shadow_observation(
                db=db,
                shadow_result=compared,
                readthrough_result=readthrough_result,
                asset_class=self._asset_class,
                asset_sector=self._asset_sector,
                existing_screening_passed=existing_input.existing_screening_passed,
                existing_qualification_passed=existing_input.existing_qualification_passed,
            )
            observation_id = obs_log.id if obs_log else None

            # Step 9: Evaluate write (dry-run receipt, no execution)
            receipt_id = str(uuid.uuid4())
            # current_value: fetch from existing comparison input
            current_qual = existing_input.existing_symbol_status
            receipt = await evaluate_shadow_write(
                db=db,
                receipt_id=receipt_id,
                shadow_result=compared,
                readthrough_result=readthrough_result,
                symbol=symbol,
                current_qualification_status=current_qual,
                shadow_observation_id=observation_id,
            )

            # Step 10: Normalise outcome
            write_verdict = None
            intended_value = None
            final_receipt_id = None

            if receipt is not None:
                write_verdict = WriteVerdict(receipt.verdict)
                intended_value = receipt.intended_value
                final_receipt_id = receipt.receipt_id

            outcome = self._normalise_outcome(write_verdict)

            return OrchestrationResult(
                symbol=symbol,
                outcome=outcome,
                shadow_result=compared,
                write_verdict=write_verdict,
                intended_value=intended_value,
                observation_id=observation_id,
                receipt_id=final_receipt_id,
            )

        except Exception as exc:
            logger.exception("ShadowPipelineOrchestrator: unhandled error for symbol=%s", symbol)
            return OrchestrationResult(
                symbol=symbol,
                outcome=OrchestratorOutcome.ERROR_INTERNAL,
                error_detail=f"{type(exc).__name__}: {exc}",
            )

    # ── Multi-symbol batch ──────────────────────────────────────

    async def run_batch(
        self,
        db: AsyncSession,
        symbols: Sequence[str],
        now_utc: datetime | None = None,
    ) -> list[OrchestrationResult]:
        """Run orchestration for each symbol. Per-symbol isolation.

        One symbol's failure does NOT block the next.
        """
        results: list[OrchestrationResult] = []
        for symbol in symbols:
            result = await self.run_single(db, symbol, now_utc)
            results.append(result)
        return results

    # ── Private helpers ─────────────────────────────────────────

    @staticmethod
    def _check_quality_gate(
        market: MarketDataSnapshot,
        backtest: BacktestReadiness,
    ) -> OrchestratorOutcome | None:
        """Return SKIP outcome if quality is insufficient, else None.

        Gate order:
          1. UNAVAILABLE on either input → SKIP_UNAVAILABLE
          2. STALE on market → SKIP_STALE
          3. Otherwise → None (proceed)
        """
        if market.quality == DataQuality.UNAVAILABLE:
            return OrchestratorOutcome.SKIP_UNAVAILABLE
        if backtest.quality == DataQuality.UNAVAILABLE:
            return OrchestratorOutcome.SKIP_UNAVAILABLE
        if market.quality == DataQuality.STALE:
            return OrchestratorOutcome.SKIP_STALE
        return None

    @staticmethod
    def _normalise_outcome(
        write_verdict: WriteVerdict | None,
    ) -> OrchestratorOutcome:
        """Map WriteVerdict to OrchestratorOutcome.

        WOULD_WRITE → WOULD_WRITE
        WOULD_SKIP  → NOOP
        BLOCKED     → NOOP (blocked writes are operational no-ops)
        None        → ERROR_INTERNAL (receipt creation failed)
        """
        if write_verdict is None:
            return OrchestratorOutcome.ERROR_INTERNAL
        if write_verdict == WriteVerdict.WOULD_WRITE:
            return OrchestratorOutcome.WOULD_WRITE
        # WOULD_SKIP and BLOCKED both map to NOOP
        return OrchestratorOutcome.NOOP
