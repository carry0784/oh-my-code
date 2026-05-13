"""F5c — MarketStateObservationReceiptRecord model tests.

Verifies:
  - Table name and column presence
  - Primary key + receipt_id uniqueness
  - Nullable / not-null contract
  - Insertion via async session
  - Index presence
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_observation_receipt import MarketStateObservationReceiptRecord


def _make_record(receipt_id: str = "market-obs-test0001") -> MarketStateObservationReceiptRecord:
    now = datetime.now(timezone.utc)
    return MarketStateObservationReceiptRecord(
        receipt_id=receipt_id,
        endpoint="snapshot",
        exchange="binance",
        symbol="BTC/USDT",
        requested_at=now,
        observed_at=now,
        source_status="EXCHANGE_OK",
        validation_status="PASS",
        freshness_status="FRESH",
        error_type=None,
        response_shape_version="v1",
        admissible_for_decision=True,
        rollback_note="test rollback note",
        evidence_bundle_id=None,
    )


def test_tablename_is_market_observation_receipts() -> None:
    assert MarketStateObservationReceiptRecord.__tablename__ == "market_observation_receipts"


def test_expected_columns_present() -> None:
    cols = {c.name for c in MarketStateObservationReceiptRecord.__table__.columns}
    expected = {
        "id",
        "receipt_id",
        "endpoint",
        "exchange",
        "symbol",
        "requested_at",
        "observed_at",
        "audit_created_at",
        "source_status",
        "validation_status",
        "freshness_status",
        "error_type",
        "response_shape_version",
        "admissible_for_decision",
        "rollback_note",
        "evidence_bundle_id",
    }
    assert expected.issubset(cols), f"missing columns: {expected - cols}"


def test_expected_indexes_present() -> None:
    index_names = {ix.name for ix in MarketStateObservationReceiptRecord.__table__.indexes}
    expected_indexes = {
        "ix_market_obs_endpoint",
        "ix_market_obs_symbol",
        "ix_market_obs_audit_created_at",
        "ix_market_obs_admissible_at",
    }
    assert expected_indexes.issubset(
        index_names
    ), f"missing indexes: {expected_indexes - index_names}"


def test_receipt_id_is_unique_constraint() -> None:
    col = MarketStateObservationReceiptRecord.__table__.columns["receipt_id"]
    assert col.unique is True


def test_nullable_fields() -> None:
    cols = MarketStateObservationReceiptRecord.__table__.columns
    assert cols["observed_at"].nullable is True
    assert cols["error_type"].nullable is True
    assert cols["evidence_bundle_id"].nullable is True
    assert cols["requested_at"].nullable is False
    assert cols["endpoint"].nullable is False
    assert cols["receipt_id"].nullable is False


async def test_can_insert_single_record(db_session: AsyncSession) -> None:
    record = _make_record("market-obs-insert001")
    db_session.add(record)
    await db_session.commit()

    result = await db_session.execute(
        select(MarketStateObservationReceiptRecord).where(
            MarketStateObservationReceiptRecord.receipt_id == "market-obs-insert001"
        )
    )
    fetched = result.scalar_one()
    assert fetched.endpoint == "snapshot"
    assert fetched.exchange == "binance"
    assert fetched.symbol == "BTC/USDT"
    assert fetched.admissible_for_decision is True


async def test_duplicate_receipt_id_raises(db_session: AsyncSession) -> None:
    db_session.add(_make_record("market-obs-dup-test"))
    await db_session.commit()

    db_session.add(_make_record("market-obs-dup-test"))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_can_insert_with_nullable_fields_none(db_session: AsyncSession) -> None:
    now = datetime.now(timezone.utc)
    record = MarketStateObservationReceiptRecord(
        receipt_id="market-obs-nullable001",
        endpoint="regime",
        exchange="binance",
        symbol="BTC/USDT",
        requested_at=now,
        observed_at=None,
        source_status="EXCHANGE_FAIL",
        validation_status="PASS",
        freshness_status="STALE_UNKNOWN",
        error_type=None,
        response_shape_version="v1",
        admissible_for_decision=False,
        rollback_note="nullable-fields test",
        evidence_bundle_id=None,
    )
    db_session.add(record)
    await db_session.commit()

    result = await db_session.execute(
        select(MarketStateObservationReceiptRecord).where(
            MarketStateObservationReceiptRecord.receipt_id == "market-obs-nullable001"
        )
    )
    fetched = result.scalar_one()
    assert fetched.observed_at is None
    assert fetched.error_type is None
    assert fetched.evidence_bundle_id is None
    assert fetched.admissible_for_decision is False
