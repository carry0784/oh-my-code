"""F7 — MarketObservationValidator tests.

Covers PASS / HOLD / BLOCK verdicts and reason taxonomy per the
F7 design rules. Each test seeds the F5c receipts table directly
via AsyncSession and verifies the validator's read-only verdict.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_observation_receipt import MarketStateObservationReceiptRecord
from app.services.market_observation_validator import (
    MarketObservationValidationResult,
    MarketObservationValidator,
)

# Sentinel to distinguish "use default now()" from "explicit None"
_DEFAULT: Any = object()


def _seed(
    *,
    receipt_id: str,
    endpoint: str = "snapshot",
    exchange: str = "binance",
    symbol: str = "BTC/USDT",
    requested_at: datetime | None = None,
    observed_at: Any = _DEFAULT,
    source_status: str = "EXCHANGE_OK",
    validation_status: str = "PASS",
    freshness_status: str = "FRESH",
    error_type: str | None = None,
    admissible: bool = True,
    audit_created_at: datetime | None = None,
) -> MarketStateObservationReceiptRecord:
    now = datetime.now(timezone.utc)
    obs = now if observed_at is _DEFAULT else observed_at
    return MarketStateObservationReceiptRecord(
        receipt_id=receipt_id,
        endpoint=endpoint,
        exchange=exchange,
        symbol=symbol,
        requested_at=requested_at or now,
        observed_at=obs,
        audit_created_at=audit_created_at or now,
        source_status=source_status,
        validation_status=validation_status,
        freshness_status=freshness_status,
        error_type=error_type,
        response_shape_version="v1",
        admissible_for_decision=admissible,
        rollback_note="validator test seed",
        evidence_bundle_id=None,
    )


async def test_no_receipt_returns_hold_no_receipt(db_session: AsyncSession) -> None:
    validator = MarketObservationValidator(db_session)
    result = await validator.validate_latest(
        endpoint="snapshot", exchange="binance", symbol="BTC/USDT", max_age_seconds=60
    )
    assert result.verdict == "HOLD"
    assert result.reason == "NO_RECEIPT"
    assert result.receipt_id is None


async def test_clean_admissible_fresh_returns_pass(db_session: AsyncSession) -> None:
    db_session.add(_seed(receipt_id="market-obs-v7-pass001"))
    await db_session.commit()

    validator = MarketObservationValidator(db_session)
    result = await validator.validate_latest(
        endpoint="snapshot", exchange="binance", symbol="BTC/USDT", max_age_seconds=60
    )
    assert result.verdict == "PASS"
    assert result.reason == "OK"
    assert result.receipt_id == "market-obs-v7-pass001"
    assert result.admissible_for_decision is True


async def test_not_admissible_returns_block(db_session: AsyncSession) -> None:
    db_session.add(_seed(receipt_id="market-obs-v7-notadm001", admissible=False))
    await db_session.commit()

    validator = MarketObservationValidator(db_session)
    result = await validator.validate_latest(
        endpoint="snapshot", exchange="binance", symbol="BTC/USDT", max_age_seconds=60
    )
    assert result.verdict == "BLOCK"
    assert result.reason == "NOT_ADMISSIBLE"


async def test_validation_status_fail_returns_block(db_session: AsyncSession) -> None:
    # admissible=True but validation_status is the failure reason. The validator
    # should attribute the BLOCK to validation_status fail (defensive consistency).
    db_session.add(
        _seed(
            receipt_id="market-obs-v7-valfail001",
            validation_status="INVALID_SYMBOL",
            admissible=True,
        )
    )
    await db_session.commit()

    validator = MarketObservationValidator(db_session)
    result = await validator.validate_latest(
        endpoint="snapshot", exchange="binance", symbol="BTC/USDT", max_age_seconds=60
    )
    assert result.verdict == "BLOCK"
    assert result.reason == "VALIDATION_STATUS_FAIL"


async def test_source_status_fail_returns_block(db_session: AsyncSession) -> None:
    db_session.add(
        _seed(
            receipt_id="market-obs-v7-srcfail001",
            source_status="EXCHANGE_FAIL",
            admissible=True,
        )
    )
    await db_session.commit()

    validator = MarketObservationValidator(db_session)
    result = await validator.validate_latest(
        endpoint="snapshot", exchange="binance", symbol="BTC/USDT", max_age_seconds=60
    )
    assert result.verdict == "BLOCK"
    assert result.reason == "SOURCE_STATUS_FAIL"


async def test_freshness_status_fail_returns_block(db_session: AsyncSession) -> None:
    db_session.add(
        _seed(
            receipt_id="market-obs-v7-freshfail001",
            freshness_status="STALE_UNKNOWN",
            admissible=True,
        )
    )
    await db_session.commit()

    validator = MarketObservationValidator(db_session)
    result = await validator.validate_latest(
        endpoint="snapshot", exchange="binance", symbol="BTC/USDT", max_age_seconds=60
    )
    assert result.verdict == "BLOCK"
    assert result.reason == "FRESHNESS_STATUS_FAIL"


async def test_error_type_present_returns_block(db_session: AsyncSession) -> None:
    db_session.add(
        _seed(
            receipt_id="market-obs-v7-errpresent001",
            error_type="UpstreamTimeoutError",
            admissible=True,
        )
    )
    await db_session.commit()

    validator = MarketObservationValidator(db_session)
    result = await validator.validate_latest(
        endpoint="snapshot", exchange="binance", symbol="BTC/USDT", max_age_seconds=60
    )
    assert result.verdict == "BLOCK"
    assert result.reason == "ERROR_TYPE_PRESENT"


async def test_observed_at_missing_returns_hold(db_session: AsyncSession) -> None:
    db_session.add(
        _seed(
            receipt_id="market-obs-v7-noobs001",
            observed_at=None,
            admissible=True,
        )
    )
    await db_session.commit()

    validator = MarketObservationValidator(db_session)
    result = await validator.validate_latest(
        endpoint="snapshot", exchange="binance", symbol="BTC/USDT", max_age_seconds=60
    )
    assert result.verdict == "HOLD"
    assert result.reason == "OBSERVED_AT_MISSING"


async def test_stale_receipt_returns_hold(db_session: AsyncSession) -> None:
    # observed_at older than max_age_seconds → STALE_RECEIPT
    old_ts = datetime.now(timezone.utc) - timedelta(seconds=600)
    db_session.add(
        _seed(
            receipt_id="market-obs-v7-stale001",
            observed_at=old_ts,
            admissible=True,
        )
    )
    await db_session.commit()

    validator = MarketObservationValidator(db_session)
    result = await validator.validate_latest(
        endpoint="snapshot", exchange="binance", symbol="BTC/USDT", max_age_seconds=60
    )
    assert result.verdict == "HOLD"
    assert result.reason == "STALE_RECEIPT"


async def test_latest_selection_uses_newest_audit_created_at(
    db_session: AsyncSession,
) -> None:
    # Insert an OLDER admissible-but-failing receipt and a NEWER passing one.
    # The validator must select the NEWER one and return PASS.
    older = _seed(
        receipt_id="market-obs-v7-older001",
        admissible=False,
        audit_created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
    )
    newer = _seed(
        receipt_id="market-obs-v7-newer001",
        admissible=True,
        audit_created_at=datetime.now(timezone.utc),
    )
    db_session.add(older)
    db_session.add(newer)
    await db_session.commit()

    validator = MarketObservationValidator(db_session)
    result = await validator.validate_latest(
        endpoint="snapshot", exchange="binance", symbol="BTC/USDT", max_age_seconds=60
    )
    assert result.verdict == "PASS"
    assert result.receipt_id == "market-obs-v7-newer001"


async def test_query_error_returns_hold_validator_query_error() -> None:
    """If the underlying DB execute raises, the validator must HOLD."""

    class _FailingSession:
        async def execute(self, *args: object, **kwargs: object) -> None:
            raise RuntimeError("simulated DB query failure")

    validator = MarketObservationValidator(_FailingSession())  # type: ignore[arg-type]
    result = await validator.validate_latest(
        endpoint="snapshot", exchange="binance", symbol="BTC/USDT", max_age_seconds=60
    )
    assert result.verdict == "HOLD"
    assert result.reason == "VALIDATOR_QUERY_ERROR"
    assert result.receipt_id is None
