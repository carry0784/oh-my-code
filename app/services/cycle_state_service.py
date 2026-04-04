"""Cycle State Service — system state queries for the strategy cycle runner.

Phase 6B-2 hardening of CR-048.  Provides:
  - safe_mode_active: True if SafeModeStatus is not NORMAL
  - drift_active: True if unprocessed drift ledger entries exist
  - guard_snapshot: JSON-serializable dict of all guard state at query time
  - duplicate cycle detection via cycle_id lookup

Reuses the same DB query patterns as RuntimeLoaderService but
scoped to what the cycle runner needs (no strategy/symbol loading).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.safe_mode import SafeModeState, SafeModeStatus
from app.models.drift_ledger import DriftLedgerEntry
from app.models.cycle_receipt import CycleReceiptRecord

logger = logging.getLogger(__name__)

# Same singleton row ID as PersistentSafeModeManager
_SAFE_MODE_STATUS_ROW_ID = "safe-mode-singleton"


class CycleStateService:
    """Reads system state for pre-cycle guard decisions.

    All methods are async (DB queries). Stateless — create per-task.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def is_safe_mode_active(self) -> bool:
        """True if SafeModeStatus current_state != NORMAL."""
        result = await self.db.execute(
            select(SafeModeStatus).where(SafeModeStatus.id == _SAFE_MODE_STATUS_ROW_ID)
        )
        status = result.scalar_one_or_none()
        if status is None:
            return False  # No row = NORMAL (first boot)
        return status.current_state != SafeModeState.NORMAL

    async def has_unprocessed_drift(self) -> bool:
        """True if any unprocessed drift ledger entries exist."""
        result = await self.db.execute(
            select(func.count(DriftLedgerEntry.id)).where(
                DriftLedgerEntry.processed == False  # noqa: E712
            )
        )
        count = result.scalar_one()
        return count > 0

    async def is_duplicate_cycle(self, cycle_id: str) -> bool:
        """True if a CycleReceiptRecord with this cycle_id already exists."""
        result = await self.db.execute(
            select(func.count(CycleReceiptRecord.id)).where(CycleReceiptRecord.cycle_id == cycle_id)
        )
        count = result.scalar_one()
        return count > 0

    async def guard_snapshot(
        self,
        *,
        market: str,
        is_open: bool,
        reason_code: str,
    ) -> dict:
        """Build a JSON-serializable guard state snapshot.

        Captures all guard inputs at query time for audit purposes.
        """
        safe_mode = await self.is_safe_mode_active()
        drift = await self.has_unprocessed_drift()

        return {
            "market": market,
            "is_open": is_open,
            "market_reason_code": reason_code,
            "safe_mode_active": safe_mode,
            "drift_active": drift,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
