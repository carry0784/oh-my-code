"""PPF Baseline Manager — freeze/seal lifecycle for Phase A backtest baselines.

Manages the immutability contract for PPFBacktestBaseline rows:
  - A baseline can only be frozen ONCE (frozen=False → True, irreversible)
  - Freeze computes seal_hash = SHA-256(critical field digest)
  - Once frozen, no field updates are allowed (enforced by this service)
  - Phase B can only start on a frozen baseline
  - Invalidation marks a baseline as unusable but NEVER deletes it

DML rules:
  INSERT: handled by PPFIntegratedBacktester._persist_baseline()
  UPDATE: only freeze/phase_b_started/invalidated transitions via this service
  DELETE: PROHIBITED (no delete path exists)
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.ppf_backtest_baseline import PPFBacktestBaseline

logger = get_logger(__name__)


class PPFBaselineManager:
    """Manages PPF backtest baseline freeze/seal lifecycle.

    All methods require an AsyncSession (injected, not created).
    Caller manages transaction boundaries.
    """

    # ── Freeze ──────────────────────────────────────────────────────────

    async def freeze_baseline(
        self,
        session: AsyncSession,
        baseline_id: str,
        frozen_by: str = "system",
        preflight_hash: str | None = None,
    ) -> dict[str, Any]:
        """Freeze a baseline for Phase B comparison.

        Returns:
            {"success": bool, "seal_hash": str|None, "error": str|None}
        """
        baseline = await self._load_baseline(session, baseline_id)
        if baseline is None:
            return {"success": False, "seal_hash": None,
                    "error": f"baseline_id={baseline_id} not found"}

        if baseline.frozen:
            return {"success": False, "seal_hash": baseline.seal_hash,
                    "error": "ALREADY_FROZEN: baseline cannot be frozen twice"}

        if baseline.invalidated:
            return {"success": False, "seal_hash": None,
                    "error": "INVALIDATED: cannot freeze an invalidated baseline"}

        seal_hash = self._compute_seal_hash(baseline)

        baseline.frozen = True
        baseline.frozen_at = datetime.utcnow()
        baseline.frozen_by = frozen_by
        baseline.seal_hash = seal_hash
        if preflight_hash is not None:
            baseline.preflight_hash = preflight_hash

        await session.flush()

        logger.info(
            "ppf_baseline_frozen",
            baseline_id=baseline_id,
            frozen_by=frozen_by,
            seal_hash=seal_hash,
        )
        return {"success": True, "seal_hash": seal_hash, "error": None}

    # ── Seal Verification ───────────────────────────────────────────────

    async def verify_seal(
        self,
        session: AsyncSession,
        baseline_id: str,
    ) -> dict[str, Any]:
        """Verify baseline seal integrity (tamper detection).

        Returns:
            {"valid": bool, "stored_hash": str|None, "computed_hash": str|None, "error": str|None}
        """
        baseline = await self._load_baseline(session, baseline_id)
        if baseline is None:
            return {"valid": False, "stored_hash": None, "computed_hash": None,
                    "error": f"baseline_id={baseline_id} not found"}

        if not baseline.frozen:
            return {"valid": False, "stored_hash": None, "computed_hash": None,
                    "error": "NOT_FROZEN: baseline has no seal to verify"}

        computed = self._compute_seal_hash(baseline)
        stored = baseline.seal_hash or ""
        valid = computed == stored

        if not valid:
            logger.warning(
                "ppf_baseline_seal_mismatch",
                baseline_id=baseline_id,
                stored_hash=stored,
                computed_hash=computed,
            )
        else:
            logger.info(
                "ppf_baseline_seal_verified",
                baseline_id=baseline_id,
            )

        return {
            "valid": valid,
            "stored_hash": stored,
            "computed_hash": computed,
            "error": None,
        }

    # ── Phase B Start ───────────────────────────────────────────────────

    async def start_phase_b(
        self,
        session: AsyncSession,
        baseline_id: str,
    ) -> dict[str, Any]:
        """Mark baseline as Phase B started. Requires frozen=True.

        Returns:
            {"success": bool, "error": str|None}
        """
        baseline = await self._load_baseline(session, baseline_id)
        if baseline is None:
            return {"success": False,
                    "error": f"baseline_id={baseline_id} not found"}

        if not baseline.frozen:
            return {"success": False,
                    "error": "NOT_FROZEN: Phase B requires a frozen baseline"}

        if baseline.invalidated:
            return {"success": False,
                    "error": "INVALIDATED: cannot start Phase B on invalidated baseline"}

        if baseline.phase_b_started:
            return {"success": False,
                    "error": "ALREADY_STARTED: Phase B already in progress"}

        baseline.phase_b_started = True
        baseline.phase_b_started_at = datetime.utcnow()
        await session.flush()

        logger.info(
            "ppf_baseline_phase_b_started",
            baseline_id=baseline_id,
        )
        return {"success": True, "error": None}

    # ── Invalidation ────────────────────────────────────────────────────

    async def invalidate_baseline(
        self,
        session: AsyncSession,
        baseline_id: str,
        reason: str,
    ) -> dict[str, Any]:
        """Mark baseline as invalidated. Does NOT delete.

        Returns:
            {"success": bool, "error": str|None}
        """
        baseline = await self._load_baseline(session, baseline_id)
        if baseline is None:
            return {"success": False,
                    "error": f"baseline_id={baseline_id} not found"}

        if baseline.invalidated:
            return {"success": False,
                    "error": "ALREADY_INVALIDATED"}

        baseline.invalidated = True
        baseline.invalidated_reason = reason[:500]
        await session.flush()

        logger.info(
            "ppf_baseline_invalidated",
            baseline_id=baseline_id,
            reason=reason[:200],
        )
        return {"success": True, "error": None}

    # ── Query ───────────────────────────────────────────────────────────

    async def get_active_baseline(
        self,
        session: AsyncSession,
        symbol: str = "SOL/USDT",
        exchange: str = "binance",
        timeframe: str = "1h",
    ) -> PPFBacktestBaseline | None:
        """Get the most recent frozen, non-invalidated baseline."""
        stmt = (
            select(PPFBacktestBaseline)
            .where(PPFBacktestBaseline.symbol == symbol)
            .where(PPFBacktestBaseline.exchange == exchange)
            .where(PPFBacktestBaseline.timeframe == timeframe)
            .where(PPFBacktestBaseline.frozen == True)  # noqa: E712
            .where(PPFBacktestBaseline.invalidated == False)  # noqa: E712
            .order_by(PPFBacktestBaseline.created_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    # ── Internal ────────────────────────────────────────────────────────

    async def _load_baseline(
        self,
        session: AsyncSession,
        baseline_id: str,
    ) -> PPFBacktestBaseline | None:
        """Load a baseline by ID."""
        stmt = select(PPFBacktestBaseline).where(
            PPFBacktestBaseline.id == baseline_id
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    def _compute_seal_hash(self, baseline: PPFBacktestBaseline) -> str:
        """SHA-256 of critical frozen field values for tamper detection.

        Fields included in seal:
          deny_rate, novelty_rate, fpr, evaluated_bars,
          allow_count, deny_count, state_distribution, deny_reason_distribution
        """
        payload = {
            "deny_rate": baseline.deny_rate,
            "novelty_rate": baseline.novelty_rate,
            "fpr": baseline.fpr,
            "evaluated_bars": baseline.evaluated_bars,
            "allow_count": baseline.allow_count,
            "deny_count": baseline.deny_count,
            "state_distribution": baseline.state_distribution or "{}",
            "deny_reason_distribution": baseline.deny_reason_distribution or "{}",
        }
        raw = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
