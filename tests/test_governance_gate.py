"""Tests for GovernanceGate — CR-044 Phase 7."""

import sys
from unittest.mock import MagicMock

_STUB_MODULES = [
    "ccxt",
    "ccxt.async_support",
    "aiohttp",
    "celery",
    "redis",
    "sqlalchemy",
    "sqlalchemy.ext",
    "sqlalchemy.ext.asyncio",
    "sqlalchemy.orm",
    "sqlalchemy.pool",
    "sqlalchemy.engine",
    "app.core.database",
    "app.core.config",
]
for name in _STUB_MODULES:
    if name not in sys.modules:
        sys.modules[name] = MagicMock()
_fake_base = type("FakeBase", (), {"__tablename__": "", "metadata": MagicMock()})
sys.modules["app.core.database"].Base = _fake_base
sys.modules["app.core.database"].engine = MagicMock()
sys.modules["app.core.database"].async_session_factory = MagicMock()

from app.services.governance_gate import GovernanceGate
from app.services.strategy_lifecycle import StrategyState, TransitionRequest


def _req(
    to_state: StrategyState, from_state: StrategyState = StrategyState.PAPER_TRADING
) -> TransitionRequest:
    return TransitionRequest(
        genome_id="g_test",
        from_state=from_state,
        to_state=to_state,
        reason="test",
    )


# ---------------------------------------------------------------------------
# test_promotion_requires_operator_dry_run
# ---------------------------------------------------------------------------


def test_promotion_requires_operator_dry_run():
    gate = GovernanceGate(dry_run=True)

    decision = gate.check(_req(StrategyState.PROMOTED), fitness=0.95)

    assert decision.decision == "PENDING_OPERATOR"
    assert decision.operator_required is True
    assert decision.auto_decided is False


# ---------------------------------------------------------------------------
# test_demotion_auto_approved
# ---------------------------------------------------------------------------


def test_demotion_auto_approved():
    gate = GovernanceGate(dry_run=True)

    decision = gate.check(_req(StrategyState.DEMOTED, from_state=StrategyState.PAPER_TRADING))

    assert decision.decision == "APPROVED"
    assert decision.auto_decided is True
    assert decision.operator_required is False


# ---------------------------------------------------------------------------
# test_retirement_auto_approved
# ---------------------------------------------------------------------------


def test_retirement_auto_approved():
    gate = GovernanceGate(dry_run=True)

    decision = gate.check(_req(StrategyState.RETIRED, from_state=StrategyState.CANDIDATE))

    assert decision.decision == "APPROVED"
    assert decision.auto_decided is True


# ---------------------------------------------------------------------------
# test_validation_auto_approved
# ---------------------------------------------------------------------------


def test_validation_auto_approved():
    gate = GovernanceGate(dry_run=True)

    decision = gate.check(_req(StrategyState.VALIDATED, from_state=StrategyState.CANDIDATE))

    assert decision.decision == "APPROVED"
    assert decision.auto_decided is True


# ---------------------------------------------------------------------------
# test_paper_trading_auto_approved
# ---------------------------------------------------------------------------


def test_paper_trading_auto_approved():
    gate = GovernanceGate(dry_run=True)

    decision = gate.check(_req(StrategyState.PAPER_TRADING, from_state=StrategyState.VALIDATED))

    assert decision.decision == "APPROVED"
    assert decision.auto_decided is True


# ---------------------------------------------------------------------------
# test_promotion_auto_approved_high_fitness — dry_run=False + fitness >= threshold
# ---------------------------------------------------------------------------


def test_promotion_auto_approved_high_fitness():
    gate = GovernanceGate(dry_run=False, auto_approve_threshold=0.8)

    decision = gate.check(_req(StrategyState.PROMOTED), fitness=0.85)

    assert decision.decision == "APPROVED"
    assert decision.auto_decided is True
    assert decision.operator_required is False


# ---------------------------------------------------------------------------
# test_pending_decisions_tracked
# ---------------------------------------------------------------------------


def test_pending_decisions_tracked():
    gate = GovernanceGate(dry_run=True)

    # Fire three promotion requests (all PENDING in dry_run)
    for _ in range(3):
        gate.check(_req(StrategyState.PROMOTED), fitness=0.9)
    # One demotion (APPROVED, not pending)
    gate.check(_req(StrategyState.DEMOTED))

    pending = gate.get_pending()
    assert len(pending) == 3
    assert all(d.decision == "PENDING_OPERATOR" for d in pending)
    assert len(gate.decision_log) == 4
