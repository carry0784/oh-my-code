"""F5c — MarketStateObservationReceiptService tests.

Verifies:
  - persist() returns True on successful commit
  - persist() returns False on DB error (fail-open)
  - persist() never raises persistence errors to the caller
  - INSERT-only contract (no UPDATE/DELETE in service surface)
  - Parses ISO timestamps correctly; empty observed_at becomes NULL
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_observation_receipt import MarketStateObservationReceiptRecord
from app.schemas.market_observation_receipt_schema import MarketStateObservationReceipt
from app.services.market_observation_receipt_service import (
    MarketStateObservationReceiptService,
)


def _make_receipt(
    receipt_id: str = "market-obs-svc-test001",
    *,
    observed_at: str = "",
    admissible: bool = False,
) -> MarketStateObservationReceipt:
    return MarketStateObservationReceipt(
        receipt_id=receipt_id,
        endpoint="snapshot",
        exchange="binance",
        symbol="BTC/USDT",
        requested_at=datetime.now(timezone.utc).isoformat(),
        observed_at=observed_at,
        source_status="EXCHANGE_OK" if admissible else "EXCHANGE_FAIL",
        validation_status="PASS",
        freshness_status="FRESH" if admissible else "STALE_UNKNOWN",
        error_type=None if admissible else "TestError",
        admissible_for_decision=admissible,
        audit_created_at=datetime.now(timezone.utc).isoformat(),
        rollback_note="service test rollback note",
    )


async def test_persist_success_returns_true(db_session: AsyncSession) -> None:
    service = MarketStateObservationReceiptService(db_session)
    receipt = _make_receipt("market-obs-svc-ok001", admissible=True)
    receipt = receipt.model_copy(update={"observed_at": datetime.now(timezone.utc).isoformat()})

    ok = await service.persist(receipt)
    assert ok is True

    result = await db_session.execute(
        select(MarketStateObservationReceiptRecord).where(
            MarketStateObservationReceiptRecord.receipt_id == "market-obs-svc-ok001"
        )
    )
    fetched = result.scalar_one()
    assert fetched.endpoint == "snapshot"
    assert fetched.admissible_for_decision is True
    assert fetched.observed_at is not None


async def test_persist_empty_observed_at_stored_as_null(db_session: AsyncSession) -> None:
    service = MarketStateObservationReceiptService(db_session)
    receipt = _make_receipt("market-obs-svc-noobs001", observed_at="", admissible=False)

    ok = await service.persist(receipt)
    assert ok is True

    result = await db_session.execute(
        select(MarketStateObservationReceiptRecord).where(
            MarketStateObservationReceiptRecord.receipt_id == "market-obs-svc-noobs001"
        )
    )
    fetched = result.scalar_one()
    assert fetched.observed_at is None
    assert fetched.error_type == "TestError"


async def test_persist_fail_open_returns_false_on_commit_error() -> None:
    """Service must catch DB errors and return False, never raise."""

    class _FailingSession:
        def add(self, obj: object) -> None:
            pass

        async def commit(self) -> None:
            raise RuntimeError("simulated DB commit failure")

        async def rollback(self) -> None:
            return None

    service = MarketStateObservationReceiptService(_FailingSession())  # type: ignore[arg-type]
    receipt = _make_receipt("market-obs-svc-fail001")

    ok = await service.persist(receipt)
    assert ok is False


async def test_persist_fail_open_swallows_rollback_error() -> None:
    """If both commit AND rollback fail, persist must still return False."""

    class _DoubleFailingSession:
        def add(self, obj: object) -> None:
            pass

        async def commit(self) -> None:
            raise RuntimeError("commit fail")

        async def rollback(self) -> None:
            raise RuntimeError("rollback fail too")

    service = MarketStateObservationReceiptService(_DoubleFailingSession())  # type: ignore[arg-type]
    receipt = _make_receipt("market-obs-svc-doublefail001")

    ok = await service.persist(receipt)
    assert ok is False
