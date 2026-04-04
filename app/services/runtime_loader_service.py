"""Runtime Loader Service — DB-integrated load eligibility + receipt recording.

Phase 5A+5B of CR-048.  Provides:
  - Internal safe mode / drift state lookup
  - Real artifact fingerprint computation (strategy + feature pack)
  - Load eligibility evaluation via LoadEligibilityChecker
  - LoadDecisionReceipt persistence (append-only) with fingerprints
  - paper_pass_at based freshness check
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Symbol
from app.models.strategy_registry import Strategy
from app.models.feature_pack import FeaturePack
from app.models.load_decision_receipt import LoadDecisionReceipt
from app.models.drift_ledger import DriftLedgerEntry
from app.models.safe_mode import SafeModeStatus, SafeModeState
from app.services.runtime_strategy_loader import (
    LoadEligibilityChecker,
    LoadEligibilityOutput,
    LoadDecision,
    LoadRejectReason,
)
from app.services.bundle_fingerprint import (
    fingerprint_from_strategy,
    fingerprint_from_feature_pack,
)

logger = logging.getLogger(__name__)

_SAFE_MODE_STATUS_ROW_ID = "safe-mode-singleton"

# Default paper pass freshness: 14 days
DEFAULT_PAPER_PASS_TTL_DAYS = 14


class RuntimeLoaderService:
    """Service for runtime strategy load eligibility + receipt recording."""

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
            return False
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

    # ── Load Eligibility ────────────────────────────────────────────

    async def evaluate_load_eligibility(
        self,
        strategy_id: str,
        symbol_id: str,
        timeframe: str,
        *,
        checker: LoadEligibilityChecker | None = None,
        paper_pass_ttl_days: int = DEFAULT_PAPER_PASS_TTL_DAYS,
    ) -> LoadEligibilityOutput:
        """Evaluate whether a strategy×symbol pair is eligible for runtime load.

        Reads all state from DB internally.
        Computes real fingerprints for strategy and feature pack.
        """
        # Fetch symbol
        sym = await self._get_symbol(symbol_id)
        if sym is None:
            return LoadEligibilityOutput(
                strategy_id=strategy_id,
                symbol_id=symbol_id,
                timeframe=timeframe,
                decision=LoadDecision.REJECTED,
                checks=[],
                failed_checks=["symbol_exists"],
                primary_reason=LoadRejectReason.SYMBOL_NOT_FOUND,
            )

        # Fetch strategy
        strat = await self._get_strategy(strategy_id)
        if strat is None:
            return LoadEligibilityOutput(
                strategy_id=strategy_id,
                symbol_id=symbol_id,
                timeframe=timeframe,
                decision=LoadDecision.REJECTED,
                checks=[],
                failed_checks=["strategy_exists"],
                primary_reason=LoadRejectReason.STRATEGY_NOT_FOUND,
            )

        # Fetch feature pack for bundle integrity
        fp = await self._get_feature_pack(strat.feature_pack_id)

        # Internal state queries
        safe_mode_active = await self.is_safe_mode_active()
        drift_active = await self.has_unprocessed_drift()

        # Paper pass freshness (uses paper_pass_at if available, else updated_at)
        paper_pass_fresh = self._check_paper_pass_freshness(sym, paper_pass_ttl_days)

        # Compute real fingerprints
        strategy_fingerprint = fingerprint_from_strategy(strat)
        stored_checksum = strat.checksum  # what was stored at registration

        # Feature pack fingerprint
        if fp is not None:
            fp_fingerprint_actual = fingerprint_from_feature_pack(fp)
            fp_fingerprint_expected = fp.checksum  # stored at registration
        else:
            fp_fingerprint_actual = None
            fp_fingerprint_expected = None

        chk = checker or LoadEligibilityChecker()
        output = chk.check(
            screening_status=sym.status.value if hasattr(sym.status, "value") else str(sym.status),
            qualification_status=sym.qualification_status,
            promotion_eligibility_status=sym.promotion_eligibility_status,
            paper_evaluation_status=sym.paper_evaluation_status,
            strategy_status=strat.status.value
            if hasattr(strat.status, "value")
            else str(strat.status),
            checksum_expected=stored_checksum,
            checksum_actual=strategy_fingerprint,
            fp_fingerprint_expected=fp_fingerprint_expected,
            fp_fingerprint_actual=fp_fingerprint_actual,
            safe_mode_active=safe_mode_active,
            drift_active=drift_active,
            paper_pass_fresh=paper_pass_fresh,
        )
        output.strategy_id = strategy_id
        output.symbol_id = symbol_id
        output.timeframe = timeframe

        return output

    async def evaluate_and_record(
        self,
        strategy_id: str,
        symbol_id: str,
        timeframe: str,
        *,
        checker: LoadEligibilityChecker | None = None,
        paper_pass_ttl_days: int = DEFAULT_PAPER_PASS_TTL_DAYS,
    ) -> LoadDecisionReceipt:
        """Evaluate load eligibility, record receipt, return receipt."""
        output = await self.evaluate_load_eligibility(
            strategy_id,
            symbol_id,
            timeframe,
            checker=checker,
            paper_pass_ttl_days=paper_pass_ttl_days,
        )

        now = datetime.now(timezone.utc)
        receipt = LoadDecisionReceipt(
            strategy_id=strategy_id,
            symbol_id=symbol_id,
            timeframe=timeframe,
            decision=output.decision.value,
            primary_reason=(output.primary_reason.value if output.primary_reason else None),
            failed_checks=(json.dumps(output.failed_checks) if output.failed_checks else None),
            status_snapshot=(
                json.dumps(output.status_snapshot) if output.status_snapshot else None
            ),
            strategy_fingerprint=output.status_snapshot.get("strategy_fingerprint")
            if output.status_snapshot
            else None,
            fp_fingerprint=output.status_snapshot.get("fp_fingerprint")
            if output.status_snapshot
            else None,
            decided_at=now,
        )
        self.db.add(receipt)
        await self.db.flush()

        return receipt

    # ── Internal Helpers ────────────────────────────────────────────

    async def _get_symbol(self, symbol_id: str) -> Symbol | None:
        result = await self.db.execute(select(Symbol).where(Symbol.id == symbol_id))
        return result.scalar_one_or_none()

    async def _get_strategy(self, strategy_id: str) -> Strategy | None:
        result = await self.db.execute(select(Strategy).where(Strategy.id == strategy_id))
        return result.scalar_one_or_none()

    async def _get_feature_pack(self, feature_pack_id: str) -> FeaturePack | None:
        result = await self.db.execute(select(FeaturePack).where(FeaturePack.id == feature_pack_id))
        return result.scalar_one_or_none()

    def _check_paper_pass_freshness(self, sym: Symbol, ttl_days: int) -> bool:
        """Check if paper_evaluation_status=pass is still fresh.

        Uses paper_pass_at if available, else falls back to updated_at.
        """
        if sym.paper_evaluation_status != "pass":
            return True  # freshness only matters for pass
        if ttl_days <= 0:
            return True  # freshness check disabled

        cutoff = datetime.now(timezone.utc) - timedelta(days=ttl_days)

        # Prefer paper_pass_at, fall back to updated_at
        ts = getattr(sym, "paper_pass_at", None) or sym.updated_at
        if ts is None:
            return False  # no timestamp = stale
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts >= cutoff
