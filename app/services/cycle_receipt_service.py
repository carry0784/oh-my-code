"""Cycle Receipt Service — DB persistence for runner cycle receipts.

Phase 6B-1+6B-2 of CR-048.  Provides:
  - CycleReceiptRecord creation from CycleReceipt
  - Append-only guarantee (no update/delete)
  - Cycle history query
  - skip_reason_code persistence for whole-cycle skips
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cycle_receipt import CycleReceiptRecord
from app.services.multi_symbol_runner import CycleReceipt

logger = logging.getLogger(__name__)


class CycleReceiptService:
    """Service for persisting runner cycle receipts to DB."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def persist_receipt(
        self,
        receipt: CycleReceipt,
        *,
        safe_mode_active: bool = False,
        drift_active: bool = False,
        guard_snapshot: dict | None = None,
    ) -> CycleReceiptRecord:
        """Persist a CycleReceipt to the database.

        Converts the in-memory receipt to a DB record with
        entries serialized as JSON.
        """
        record = CycleReceiptRecord(
            cycle_id=receipt.cycle_id,
            universe_size=receipt.universe_size,
            strategies_evaluated=receipt.strategies_evaluated,
            signal_candidates=receipt.signal_candidates,
            skipped=receipt.skipped,
            dry_run=receipt.dry_run,
            entries_json=json.dumps(receipt.to_dict().get("entries", [])),
            safe_mode_active=safe_mode_active,
            drift_active=drift_active,
            skip_reason_code=receipt.skip_reason_code,
            guard_snapshot_json=json.dumps(guard_snapshot) if guard_snapshot else None,
            started_at=receipt.started_at,
            completed_at=receipt.completed_at,
        )
        self.db.add(record)
        await self.db.flush()
        return record

    async def get_cycle_history(
        self,
        limit: int = 50,
    ) -> list[CycleReceiptRecord]:
        """Return recent cycle receipts, newest first."""
        result = await self.db.execute(
            select(CycleReceiptRecord).order_by(CycleReceiptRecord.started_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def get_cycle_by_id(
        self,
        cycle_id: str,
    ) -> CycleReceiptRecord | None:
        """Return a specific cycle receipt by cycle_id."""
        result = await self.db.execute(
            select(CycleReceiptRecord).where(CycleReceiptRecord.cycle_id == cycle_id)
        )
        return result.scalar_one_or_none()
