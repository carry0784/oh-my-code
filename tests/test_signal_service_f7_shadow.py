"""F7-SHADOW — SignalService consumer wiring tests.

Verifies that `SignalService.validate_with_agent`:
  1. invokes the Market State observation validator in shadow mode
  2. does NOT change the signal's status based on the validator verdict
  3. does NOT fail the decision path when the validator raises
  4. preserves the original agent result in the return value

Shadow contract: validator output is diagnostic-only.

Implementation note:
This test file avoids the ORM `Signal` model entirely. Other tests in this
suite stub `app.core.database.Base` via `sys.modules` injection before the
real model module is loaded; the resulting `Signal._sa_instance_state` is
a MagicMock that breaks SQLAlchemy's `db.add()` because dunder attribute
access on MagicMock raises AttributeError. We therefore use plain stub
objects with the same attribute surface (`id`, `exchange`, `symbol`,
`status`, `confidence`) and monkeypatch `SignalService.get_signal` to
return them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.signal import SignalStatus
import app.services.signal_service as signal_service_module
from app.services.market_observation_validator import (
    MarketObservationValidationResult,
)
from app.services.signal_service import SignalService


@dataclass
class _SignalStub:
    id: str = "stub-signal-id"
    exchange: str = "binance"
    symbol: str = "BTC/USDT"
    signal_type: str = "long"
    confidence: float = 0.7
    status: SignalStatus = SignalStatus.PENDING
    agent_analysis: str | None = None


def _approved_agent_result() -> dict[str, Any]:
    return {"approved": True, "confidence": 0.85, "reasoning": "test approval"}


def _rejected_agent_result() -> dict[str, Any]:
    return {"approved": False, "confidence": 0.4, "reasoning": "test rejection"}


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


class _StubAgent:
    """Drop-in replacement for SignalValidatorAgent for tests."""

    def __init__(self, result: dict[str, Any]) -> None:
        self._result = result

    async def validate(self, signal: _SignalStub) -> dict[str, Any]:
        return self._result


class _StubValidator:
    """Drop-in replacement for MarketObservationValidator for tests."""

    last_kwargs: dict[str, Any] = {}
    call_count: int = 0

    def __init__(
        self,
        db: AsyncSession,
        *,
        result: MarketObservationValidationResult | None = None,
        raise_exc: BaseException | None = None,
    ) -> None:
        self.db = db
        self._result = result
        self._raise = raise_exc

    async def validate_latest(self, **kwargs: Any) -> MarketObservationValidationResult:
        type(self).call_count += 1
        type(self).last_kwargs = kwargs
        if self._raise is not None:
            raise self._raise
        assert self._result is not None
        return self._result


def _install_stubs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    signal: _SignalStub,
    agent_result: dict[str, Any],
    validator_result: MarketObservationValidationResult | None = None,
    validator_raises: BaseException | None = None,
) -> type[_StubValidator]:
    """Install stubs for get_signal, SignalValidatorAgent, and the validator.

    Returns the validator stub class so tests can inspect call_count/last_kwargs.
    """
    _StubValidator.call_count = 0
    _StubValidator.last_kwargs = {}

    async def _stub_get_signal(self: SignalService, signal_id: str) -> _SignalStub:
        return signal

    def _agent_factory() -> _StubAgent:
        return _StubAgent(agent_result)

    def _validator_factory(db: AsyncSession) -> _StubValidator:
        return _StubValidator(db, result=validator_result, raise_exc=validator_raises)

    monkeypatch.setattr(SignalService, "get_signal", _stub_get_signal)
    monkeypatch.setattr(signal_service_module, "SignalValidatorAgent", _agent_factory)
    monkeypatch.setattr(signal_service_module, "MarketObservationValidator", _validator_factory)
    return _StubValidator


@pytest.fixture
def stub_db() -> Any:
    """Lightweight db replacement; SignalService only passes it to the
    validator factory in F7-SHADOW path. No SQLAlchemy operations occur."""

    class _StubDB:
        pass

    return _StubDB()


async def test_shadow_validator_is_called_with_signal_fields(
    monkeypatch: pytest.MonkeyPatch,
    stub_db: Any,
) -> None:
    signal = _SignalStub()
    validator_cls = _install_stubs(
        monkeypatch,
        signal=signal,
        agent_result=_approved_agent_result(),
        validator_result=_pass_validator_result(),
    )

    service = SignalService(stub_db)
    await service.validate_with_agent(signal.id)

    assert validator_cls.call_count == 1
    assert validator_cls.last_kwargs["endpoint"] == "snapshot"
    assert validator_cls.last_kwargs["exchange"] == "binance"
    assert validator_cls.last_kwargs["symbol"] == "BTC/USDT"


async def test_shadow_block_verdict_does_not_change_approved_decision(
    monkeypatch: pytest.MonkeyPatch,
    stub_db: Any,
) -> None:
    signal = _SignalStub()
    _install_stubs(
        monkeypatch,
        signal=signal,
        agent_result=_approved_agent_result(),
        validator_result=_block_validator_result(),
    )

    service = SignalService(stub_db)
    result = await service.validate_with_agent(signal.id)

    assert result == _approved_agent_result()
    assert signal.status == SignalStatus.VALIDATED
    assert signal.confidence == 0.85


async def test_shadow_pass_verdict_does_not_change_rejected_decision(
    monkeypatch: pytest.MonkeyPatch,
    stub_db: Any,
) -> None:
    signal = _SignalStub()
    _install_stubs(
        monkeypatch,
        signal=signal,
        agent_result=_rejected_agent_result(),
        validator_result=_pass_validator_result(),
    )

    service = SignalService(stub_db)
    result = await service.validate_with_agent(signal.id)

    assert result == _rejected_agent_result()
    assert signal.status == SignalStatus.REJECTED


async def test_shadow_validator_failure_does_not_break_decision(
    monkeypatch: pytest.MonkeyPatch,
    stub_db: Any,
) -> None:
    signal = _SignalStub()
    _install_stubs(
        monkeypatch,
        signal=signal,
        agent_result=_approved_agent_result(),
        validator_raises=RuntimeError("simulated validator failure"),
    )

    service = SignalService(stub_db)
    result = await service.validate_with_agent(signal.id)

    assert result == _approved_agent_result()
    assert signal.status == SignalStatus.VALIDATED


async def test_shadow_disabled_skips_validator(
    monkeypatch: pytest.MonkeyPatch,
    stub_db: Any,
) -> None:
    signal = _SignalStub()
    validator_cls = _install_stubs(
        monkeypatch,
        signal=signal,
        agent_result=_approved_agent_result(),
        validator_result=_pass_validator_result(),
    )
    monkeypatch.setattr(signal_service_module, "_F7_SHADOW_ENABLED", False)

    service = SignalService(stub_db)
    result = await service.validate_with_agent(signal.id)

    assert result == _approved_agent_result()
    assert validator_cls.call_count == 0
    assert signal.status == SignalStatus.VALIDATED
