"""F7-SHADOW — SignalService consumer wiring tests.

Verifies that `SignalService.validate_with_agent`:
  1. invokes the Market State observation validator in shadow mode
  2. does NOT change the signal's status based on the validator verdict
  3. does NOT fail the decision path when the validator raises
  4. preserves the original agent result in the return value

Shadow contract: validator output is diagnostic-only.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.signal import Signal, SignalStatus
from app.services.market_observation_validator import (
    MarketObservationValidationResult,
)
from app.services.signal_service import SignalService


def _make_signal() -> Signal:
    return Signal(
        source="manual",
        exchange="binance",
        symbol="BTC/USDT",
        signal_type="long",
        entry_price=50000.0,
        stop_loss=49000.0,
        take_profit=52000.0,
        confidence=0.7,
        status=SignalStatus.PENDING,
    )


def _approved_agent_result() -> dict[str, Any]:
    return {
        "approved": True,
        "confidence": 0.85,
        "reasoning": "test approval",
    }


def _rejected_agent_result() -> dict[str, Any]:
    return {
        "approved": False,
        "confidence": 0.4,
        "reasoning": "test rejection",
    }


def _pass_validator_result() -> MarketObservationValidationResult:
    return MarketObservationValidationResult(
        verdict="PASS",
        reason="OK",
        receipt_id="market-obs-test-pass",
        endpoint="snapshot",
        exchange="binance",
        symbol="BTC/USDT",
        observed_at=None,
        audit_created_at=None,
        admissible_for_decision=True,
        freshness_status="FRESH",
        source_status="EXCHANGE_OK",
        validation_status="PASS",
        error_type=None,
    )


def _block_validator_result() -> MarketObservationValidationResult:
    return MarketObservationValidationResult(
        verdict="BLOCK",
        reason="NOT_ADMISSIBLE",
        receipt_id="market-obs-test-block",
        endpoint="snapshot",
        exchange="binance",
        symbol="BTC/USDT",
        observed_at=None,
        audit_created_at=None,
        admissible_for_decision=False,
        freshness_status="STALE_UNKNOWN",
        source_status="EXCHANGE_FAIL",
        validation_status="PASS",
        error_type=None,
    )


async def _persist_signal(db: AsyncSession) -> Signal:
    signal = _make_signal()
    db.add(signal)
    await db.commit()
    await db.refresh(signal)
    return signal


@patch("app.services.signal_service.MarketObservationValidator")
@patch("app.services.signal_service.SignalValidatorAgent")
async def test_shadow_validator_is_called_with_signal_fields(
    mock_agent_cls: Any,
    mock_validator_cls: Any,
    db_session: AsyncSession,
) -> None:
    mock_agent_cls.return_value.validate = AsyncMock(return_value=_approved_agent_result())
    mock_validator_cls.return_value.validate_latest = AsyncMock(
        return_value=_pass_validator_result()
    )

    signal = await _persist_signal(db_session)
    service = SignalService(db_session)
    await service.validate_with_agent(signal.id)

    mock_validator_cls.assert_called_once_with(db_session)
    mock_validator_cls.return_value.validate_latest.assert_awaited_once()
    call_kwargs = mock_validator_cls.return_value.validate_latest.await_args.kwargs
    assert call_kwargs["endpoint"] == "snapshot"
    assert call_kwargs["exchange"] == "binance"
    assert call_kwargs["symbol"] == "BTC/USDT"


@patch("app.services.signal_service.MarketObservationValidator")
@patch("app.services.signal_service.SignalValidatorAgent")
async def test_shadow_block_verdict_does_not_change_approved_decision(
    mock_agent_cls: Any,
    mock_validator_cls: Any,
    db_session: AsyncSession,
) -> None:
    # Agent approves; validator returns BLOCK. Shadow must NOT override.
    mock_agent_cls.return_value.validate = AsyncMock(return_value=_approved_agent_result())
    mock_validator_cls.return_value.validate_latest = AsyncMock(
        return_value=_block_validator_result()
    )

    signal = await _persist_signal(db_session)
    service = SignalService(db_session)
    result = await service.validate_with_agent(signal.id)

    assert result == _approved_agent_result()
    # SignalService mutates the session-managed signal in-place but does not
    # commit; assert on the in-memory state directly rather than via refresh
    # (refresh would reload the pre-mutation DB row).
    assert signal.status == SignalStatus.VALIDATED
    assert signal.confidence == 0.85


@patch("app.services.signal_service.MarketObservationValidator")
@patch("app.services.signal_service.SignalValidatorAgent")
async def test_shadow_pass_verdict_does_not_change_rejected_decision(
    mock_agent_cls: Any,
    mock_validator_cls: Any,
    db_session: AsyncSession,
) -> None:
    # Agent rejects; validator returns PASS. Shadow must NOT upgrade.
    mock_agent_cls.return_value.validate = AsyncMock(return_value=_rejected_agent_result())
    mock_validator_cls.return_value.validate_latest = AsyncMock(
        return_value=_pass_validator_result()
    )

    signal = await _persist_signal(db_session)
    service = SignalService(db_session)
    result = await service.validate_with_agent(signal.id)

    assert result == _rejected_agent_result()
    assert signal.status == SignalStatus.REJECTED


@patch("app.services.signal_service.MarketObservationValidator")
@patch("app.services.signal_service.SignalValidatorAgent")
async def test_shadow_validator_failure_does_not_break_decision(
    mock_agent_cls: Any,
    mock_validator_cls: Any,
    db_session: AsyncSession,
) -> None:
    # Validator raises. Decision path must still complete.
    mock_agent_cls.return_value.validate = AsyncMock(return_value=_approved_agent_result())
    mock_validator_cls.return_value.validate_latest = AsyncMock(
        side_effect=RuntimeError("simulated validator failure")
    )

    signal = await _persist_signal(db_session)
    service = SignalService(db_session)
    result = await service.validate_with_agent(signal.id)

    assert result == _approved_agent_result()
    assert signal.status == SignalStatus.VALIDATED


@patch("app.services.signal_service.MarketObservationValidator")
@patch("app.services.signal_service.SignalValidatorAgent")
async def test_shadow_disabled_skips_validator(
    mock_agent_cls: Any,
    mock_validator_cls: Any,
    db_session: AsyncSession,
) -> None:
    # When _F7_SHADOW_ENABLED is False, the validator must not be called.
    mock_agent_cls.return_value.validate = AsyncMock(return_value=_approved_agent_result())

    signal = await _persist_signal(db_session)
    service = SignalService(db_session)

    with patch("app.services.signal_service._F7_SHADOW_ENABLED", False):
        result = await service.validate_with_agent(signal.id)

    assert result == _approved_agent_result()
    mock_validator_cls.assert_not_called()
    assert signal.status == SignalStatus.VALIDATED
