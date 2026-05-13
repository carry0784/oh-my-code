"""F7 Market State Observation Validator — read-only decision gate.

Consumes MarketStateObservationReceiptRecord rows persisted by F5c and
classifies the latest receipt for an (endpoint, exchange, symbol) tuple
as PASS / HOLD / BLOCK for downstream decision use.

This service is INTENTIONALLY DETACHED from any decision-engine or
execution call site in this PR. Wiring a consumer is a separate
operator-approved step.

Read-only contract:
  - No DB write
  - No commit / no rollback (except defensive rollback on query error)
  - No mutation of fetched records
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_observation_receipt import MarketStateObservationReceiptRecord

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MarketObservationValidationResult:
    """Outcome of a single validator query.

    `verdict` is one of:
        - PASS  — the latest receipt is admissible and fresh
        - HOLD  — caller should defer / retry (recoverable condition)
        - BLOCK — caller must not proceed (terminal failure of this lookup)

    `reason` is a stable machine-readable label; see the validator docstring
    for the full enumeration.
    """

    verdict: str
    reason: str
    receipt_id: Optional[str]
    endpoint: str
    exchange: str
    symbol: str
    observed_at: Optional[datetime]
    audit_created_at: Optional[datetime]
    admissible_for_decision: bool
    freshness_status: Optional[str]
    source_status: Optional[str]
    validation_status: Optional[str]
    error_type: Optional[str]


class MarketObservationValidator:
    """Read-only validator for F5c persisted observation receipts.

    Usage:
        result = await MarketObservationValidator(db).validate_latest(
            endpoint="snapshot",
            exchange="binance",
            symbol="BTC/USDT",
            max_age_seconds=60,
        )

    The validator does NOT mutate records, does NOT commit, and does NOT
    raise on query errors — it returns a HOLD verdict instead, with
    reason="VALIDATOR_QUERY_ERROR".
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def validate_latest(
        self,
        *,
        endpoint: str,
        exchange: str,
        symbol: str,
        max_age_seconds: int,
    ) -> MarketObservationValidationResult:
        """Fetch the newest receipt for (endpoint, exchange, symbol) and
        classify it.

        Verdict enumeration:
          - PASS  / OK
          - HOLD  / NO_RECEIPT
          - HOLD  / OBSERVED_AT_MISSING
          - HOLD  / STALE_RECEIPT
          - HOLD  / VALIDATOR_QUERY_ERROR
          - BLOCK / NOT_ADMISSIBLE
          - BLOCK / VALIDATION_STATUS_FAIL
          - BLOCK / SOURCE_STATUS_FAIL
          - BLOCK / FRESHNESS_STATUS_FAIL
          - BLOCK / ERROR_TYPE_PRESENT
        """
        try:
            result = await self.db.execute(
                select(MarketStateObservationReceiptRecord)
                .where(
                    MarketStateObservationReceiptRecord.endpoint == endpoint,
                    MarketStateObservationReceiptRecord.exchange == exchange,
                    MarketStateObservationReceiptRecord.symbol == symbol,
                )
                .order_by(MarketStateObservationReceiptRecord.audit_created_at.desc())
                .limit(1)
            )
            record: Optional[MarketStateObservationReceiptRecord] = result.scalar_one_or_none()
        except Exception as e:
            logger.warning(
                "market_observation_validator_query_failed endpoint=%s exchange=%s symbol=%s error=%s",
                endpoint,
                exchange,
                symbol,
                str(e),
            )
            return MarketObservationValidationResult(
                verdict="HOLD",
                reason="VALIDATOR_QUERY_ERROR",
                receipt_id=None,
                endpoint=endpoint,
                exchange=exchange,
                symbol=symbol,
                observed_at=None,
                audit_created_at=None,
                admissible_for_decision=False,
                freshness_status=None,
                source_status=None,
                validation_status=None,
                error_type=None,
            )

        if record is None:
            return MarketObservationValidationResult(
                verdict="HOLD",
                reason="NO_RECEIPT",
                receipt_id=None,
                endpoint=endpoint,
                exchange=exchange,
                symbol=symbol,
                observed_at=None,
                audit_created_at=None,
                admissible_for_decision=False,
                freshness_status=None,
                source_status=None,
                validation_status=None,
                error_type=None,
            )

        # Pre-build the shared snapshot of receipt fields for any verdict.
        def _result(verdict: str, reason: str) -> MarketObservationValidationResult:
            return MarketObservationValidationResult(
                verdict=verdict,
                reason=reason,
                receipt_id=record.receipt_id,
                endpoint=record.endpoint,
                exchange=record.exchange,
                symbol=record.symbol,
                observed_at=record.observed_at,
                audit_created_at=record.audit_created_at,
                admissible_for_decision=bool(record.admissible_for_decision),
                freshness_status=record.freshness_status,
                source_status=record.source_status,
                validation_status=record.validation_status,
                error_type=record.error_type,
            )

        # Rule 2: admissible flag is the headline gate
        if not bool(record.admissible_for_decision):
            return _result("BLOCK", "NOT_ADMISSIBLE")

        # Rule 3-6: granular failure attribution (only reached if admissible
        # flag was True but a sub-gate disagrees — defensive consistency check)
        if record.validation_status != "PASS":
            return _result("BLOCK", "VALIDATION_STATUS_FAIL")
        if record.source_status != "EXCHANGE_OK":
            return _result("BLOCK", "SOURCE_STATUS_FAIL")
        if record.freshness_status != "FRESH":
            return _result("BLOCK", "FRESHNESS_STATUS_FAIL")
        if record.error_type is not None:
            return _result("BLOCK", "ERROR_TYPE_PRESENT")

        # Rule 7-8: time-based gates
        if record.observed_at is None:
            return _result("HOLD", "OBSERVED_AT_MISSING")
        # SQLite + aiosqlite returns DateTime values without tzinfo even when
        # stored as tz-aware. Treat naive datetimes as UTC for the age check.
        observed_at = record.observed_at
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)
        age_seconds = (datetime.now(timezone.utc) - observed_at).total_seconds()
        if age_seconds > max_age_seconds:
            return _result("HOLD", "STALE_RECEIPT")

        # Rule 9: clean pass
        return _result("PASS", "OK")
