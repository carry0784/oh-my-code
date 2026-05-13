"""F5c — Market State route integration tests for DB persistence.

Verifies that the three Market State endpoints persist observation
receipts to DB on the F3 invalid-input path (which does not require
exchange mocking). Success / exception paths require external service
mocking and are covered separately by the service-level fail-open
test and unit tests; here we focus on the new route → DB integration.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_observation_receipt import MarketStateObservationReceiptRecord


async def test_invalid_exchange_persists_receipt_via_snapshot(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    resp = await client.get(
        "/api/v1/market-state/snapshot",
        params={"exchange": "not_an_exchange", "symbol": "BTC/USDT"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["error_type"] == "INVALID_EXCHANGE"

    result = await db_session.execute(
        select(MarketStateObservationReceiptRecord).where(
            MarketStateObservationReceiptRecord.endpoint == "snapshot",
            MarketStateObservationReceiptRecord.exchange == "not_an_exchange",
        )
    )
    records = result.scalars().all()
    assert len(records) >= 1
    record = records[-1]
    assert record.validation_status == "INVALID_EXCHANGE"
    assert record.error_type == "INVALID_EXCHANGE"
    assert record.admissible_for_decision is False
    assert record.source_status == "EXCHANGE_FAIL"


async def test_invalid_symbol_persists_receipt_via_regime(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    resp = await client.get(
        "/api/v1/market-state/regime",
        params={"exchange": "binance", "symbol": "bad symbol"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["error_type"] == "INVALID_SYMBOL"

    result = await db_session.execute(
        select(MarketStateObservationReceiptRecord).where(
            MarketStateObservationReceiptRecord.endpoint == "regime",
            MarketStateObservationReceiptRecord.validation_status == "INVALID_SYMBOL",
        )
    )
    records = result.scalars().all()
    assert len(records) >= 1
    record = records[-1]
    assert record.admissible_for_decision is False
    assert record.symbol == "bad symbol"


async def test_invalid_exchange_persists_receipt_via_score(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    resp = await client.get(
        "/api/v1/market-state/score",
        params={"exchange": "not_an_exchange", "symbol": "BTC/USDT"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["error_type"] == "INVALID_EXCHANGE"
    # Response shape preserved: F5c must not add receipt_id to API responses.
    assert "receipt_id" not in body

    result = await db_session.execute(
        select(MarketStateObservationReceiptRecord).where(
            MarketStateObservationReceiptRecord.endpoint == "score",
            MarketStateObservationReceiptRecord.validation_status == "INVALID_EXCHANGE",
        )
    )
    records = result.scalars().all()
    assert len(records) >= 1
