"""F5c Market State Observation Receipt persistence service.

Async, append-only, fail-open: DB errors are logged but never raised to
the API caller. Persistence failure does not change the API response
and does not grant execution authority.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_observation_receipt import MarketStateObservationReceiptRecord
from app.schemas.market_observation_receipt_schema import MarketStateObservationReceipt

logger = logging.getLogger(__name__)


def _parse_iso_optional(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 string into a tz-aware datetime; None/empty → None."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class MarketStateObservationReceiptService:
    """Append-only persistence for MarketStateObservationReceipt.

    Fail-open: persistence failure → log + return False. Never raises
    persistence errors to the route caller. INSERT only (no UPDATE/DELETE).
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def persist(self, receipt: MarketStateObservationReceipt) -> bool:
        """Persist one receipt. Returns True on success, False on fail-open.

        The API response must remain unchanged regardless of the return value.
        Never raises persistence errors to the caller.
        """
        try:
            requested_at = _parse_iso_optional(receipt.requested_at) or datetime.now(timezone.utc)
            record = MarketStateObservationReceiptRecord(
                receipt_id=receipt.receipt_id,
                endpoint=receipt.endpoint,
                exchange=receipt.exchange,
                symbol=receipt.symbol,
                requested_at=requested_at,
                observed_at=_parse_iso_optional(receipt.observed_at),
                source_status=receipt.source_status,
                validation_status=receipt.validation_status,
                freshness_status=receipt.freshness_status,
                error_type=receipt.error_type,
                response_shape_version=receipt.response_shape_version,
                admissible_for_decision=receipt.admissible_for_decision,
                rollback_note=receipt.rollback_note,
                evidence_bundle_id=receipt.evidence_bundle_id,
            )
            self.db.add(record)
            await self.db.commit()
            return True
        except Exception as e:
            try:
                await self.db.rollback()
            except Exception:
                pass
            logger.warning(
                "market_observation_receipt_persist_failed receipt_id=%s error=%s",
                receipt.receipt_id,
                str(e),
            )
            return False
