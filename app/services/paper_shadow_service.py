"""Paper Shadow Service — observation recording + promotion eligibility.

Phase 4B of CR-048.  Provides:
  - Paper observation recording (append-only)
  - Promotion eligibility evaluation via PromotionGate
  - Promotion decision recording with duplicate suppression
  - Symbol.promotion_eligibility_status updates
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Symbol, SymbolStatus
from app.models.paper_shadow import (
    PaperObservation,
    PromotionDecision,
    PromotionEligibility,
    ObservationStatus,
)
from app.services.promotion_gate import (
    EligibilityInput,
    EligibilityOutput,
    PromotionGate,
)

logger = logging.getLogger(__name__)


class PaperShadowService:
    """Service for paper shadow observations and promotion decisions."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Observations ────────────────────────────────────────────────

    async def record_observation(self, data: dict) -> PaperObservation:
        """Append a paper observation record."""
        obs = PaperObservation(
            strategy_id=data["strategy_id"],
            symbol=data["symbol"],
            timeframe=data.get("timeframe", "1h"),
            metrics_snapshot=(
                json.dumps(data["metrics_snapshot"])
                if isinstance(data.get("metrics_snapshot"), dict)
                else data.get("metrics_snapshot")
            ),
            observation_status=data.get("observation_status", ObservationStatus.RECORDED),
            source_qualification_result_id=data.get("source_qualification_result_id"),
            detail=data.get("detail"),
            observed_at=data.get("observed_at", datetime.now(timezone.utc)),
        )
        self.db.add(obs)
        await self.db.flush()
        return obs

    async def get_observation_history(
        self,
        strategy_id: str,
        symbol: str,
        limit: int = 100,
    ) -> list[PaperObservation]:
        """Return observation history, newest first."""
        result = await self.db.execute(
            select(PaperObservation)
            .where(PaperObservation.strategy_id == strategy_id)
            .where(PaperObservation.symbol == symbol)
            .order_by(PaperObservation.observed_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # ── Eligibility Evaluation ──────────────────────────────────────

    async def evaluate_eligibility(
        self,
        symbol_id: str,
        strategy_id: str,
        timeframe: str,
        *,
        safe_mode_active: bool = False,
        drift_active: bool = False,
        gate: PromotionGate | None = None,
    ) -> EligibilityOutput:
        """Evaluate promotion eligibility for a strategy×symbol×timeframe.

        Assembles EligibilityInput from DB lookups, then delegates
        to PromotionGate.evaluate().
        """
        sym = await self._get_symbol(symbol_id)
        if sym is None:
            raise ValueError(f"Symbol not found: {symbol_id}")

        inp = EligibilityInput(
            strategy_id=strategy_id,
            symbol=sym.symbol,
            timeframe=timeframe,
            screening_status=sym.status.value if hasattr(sym.status, "value") else str(sym.status),
            qualification_status=sym.qualification_status,
            is_excluded=(sym.status == SymbolStatus.EXCLUDED),
            safe_mode_active=safe_mode_active,
            drift_active=drift_active,
        )

        g = gate or PromotionGate()
        return g.evaluate(inp)

    async def evaluate_and_record_decision(
        self,
        symbol_id: str,
        strategy_id: str,
        timeframe: str,
        *,
        safe_mode_active: bool = False,
        drift_active: bool = False,
        gate: PromotionGate | None = None,
        decided_by: str = "system",
    ) -> PromotionDecision:
        """Evaluate eligibility, record decision, update Symbol.

        Duplicate suppression: if the latest decision for the same
        (strategy_id, symbol, timeframe) has the same decision value,
        the new record is still inserted but marked suppressed=True.
        """
        sym = await self._get_symbol(symbol_id)
        if sym is None:
            raise ValueError(f"Symbol not found: {symbol_id}")

        output = await self.evaluate_eligibility(
            symbol_id,
            strategy_id,
            timeframe,
            safe_mode_active=safe_mode_active,
            drift_active=drift_active,
            gate=gate,
        )

        # Check for duplicate suppression
        prev = await self._get_latest_decision(strategy_id, sym.symbol, timeframe)
        is_suppressed = prev is not None and prev.decision.value == output.decision.value

        now = datetime.now(timezone.utc)
        decision = PromotionDecision(
            strategy_id=strategy_id,
            symbol=sym.symbol,
            timeframe=timeframe,
            decision=output.decision,
            previous_decision=prev.decision.value if prev else None,
            reason=(output.block_reason.value if output.block_reason else None),
            eligibility_checks=json.dumps(
                [
                    {
                        "check": c.check_name,
                        "passed": c.passed,
                        "reason": c.reason.value if c.reason else None,
                    }
                    for c in output.checks
                ]
            ),
            blocked_checks=json.dumps([c.check_name for c in output.checks if not c.passed])
            if any(not c.passed for c in output.checks)
            else None,
            suppressed=is_suppressed,
            decided_by=decided_by,
            decided_at=now,
        )
        self.db.add(decision)
        await self.db.flush()

        # Update Symbol.promotion_eligibility_status
        sym.promotion_eligibility_status = output.decision.value
        sym.updated_at = now
        await self.db.flush()

        return decision

    async def get_decision_history(
        self,
        strategy_id: str,
        symbol: str,
        limit: int = 100,
    ) -> list[PromotionDecision]:
        """Return promotion decision history, newest first."""
        result = await self.db.execute(
            select(PromotionDecision)
            .where(PromotionDecision.strategy_id == strategy_id)
            .where(PromotionDecision.symbol == symbol)
            .order_by(PromotionDecision.decided_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # ── Internal ────────────────────────────────────────────────────

    async def _get_symbol(self, symbol_id: str) -> Symbol | None:
        result = await self.db.execute(select(Symbol).where(Symbol.id == symbol_id))
        return result.scalar_one_or_none()

    async def _get_latest_decision(
        self,
        strategy_id: str,
        symbol: str,
        timeframe: str,
    ) -> PromotionDecision | None:
        result = await self.db.execute(
            select(PromotionDecision)
            .where(PromotionDecision.strategy_id == strategy_id)
            .where(PromotionDecision.symbol == symbol)
            .where(PromotionDecision.timeframe == timeframe)
            .where(PromotionDecision.suppressed == False)  # noqa: E712
            .order_by(PromotionDecision.decided_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
