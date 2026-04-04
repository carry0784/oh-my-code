"""Tests for StrategyLifecycleManager — CR-044 Phase 7."""

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

from app.services.strategy_lifecycle import (
    StrategyLifecycleManager,
    StrategyState,
    TransitionRequest,
)


def _make_manager() -> StrategyLifecycleManager:
    return StrategyLifecycleManager()


def _register_and_advance(manager: StrategyLifecycleManager, gid: str) -> None:
    """Register a genome and walk it to PAPER_TRADING state."""
    manager.register(gid)
    manager.request_transition(
        TransitionRequest(
            genome_id=gid,
            from_state=StrategyState.CANDIDATE,
            to_state=StrategyState.VALIDATED,
            reason="test",
        )
    )
    manager.request_transition(
        TransitionRequest(
            genome_id=gid,
            from_state=StrategyState.VALIDATED,
            to_state=StrategyState.PAPER_TRADING,
            reason="test",
        )
    )


# ---------------------------------------------------------------------------
# test_register_creates_candidate
# ---------------------------------------------------------------------------


def test_register_creates_candidate():
    manager = _make_manager()
    record = manager.register("g1")

    assert record.genome_id == "g1"
    assert record.current_state == StrategyState.CANDIDATE
    assert record.promotion_count == 0
    assert record.demotion_count == 0
    assert "g1" in manager.records


# ---------------------------------------------------------------------------
# test_valid_transition_succeeds
# ---------------------------------------------------------------------------


def test_valid_transition_succeeds():
    manager = _make_manager()
    manager.register("g2")

    ok = manager.request_transition(
        TransitionRequest(
            genome_id="g2",
            from_state=StrategyState.CANDIDATE,
            to_state=StrategyState.VALIDATED,
            reason="passed_checks",
        )
    )

    assert ok is True
    assert manager.get_state("g2").current_state == StrategyState.VALIDATED


# ---------------------------------------------------------------------------
# test_invalid_transition_rejected — CANDIDATE → PROMOTED not allowed
# ---------------------------------------------------------------------------


def test_invalid_transition_rejected():
    manager = _make_manager()
    manager.register("g3")

    ok = manager.request_transition(
        TransitionRequest(
            genome_id="g3",
            from_state=StrategyState.CANDIDATE,
            to_state=StrategyState.PROMOTED,
            reason="skip_steps",
        )
    )

    assert ok is False
    # State must remain CANDIDATE
    assert manager.get_state("g3").current_state == StrategyState.CANDIDATE


# ---------------------------------------------------------------------------
# test_state_mismatch_rejected — request from_state doesn't match current
# ---------------------------------------------------------------------------


def test_state_mismatch_rejected():
    manager = _make_manager()
    manager.register("g4")
    # genome is CANDIDATE, but request claims from_state=VALIDATED
    ok = manager.request_transition(
        TransitionRequest(
            genome_id="g4",
            from_state=StrategyState.VALIDATED,
            to_state=StrategyState.PAPER_TRADING,
            reason="wrong_from_state",
        )
    )

    assert ok is False
    assert manager.get_state("g4").current_state == StrategyState.CANDIDATE


# ---------------------------------------------------------------------------
# test_retired_is_terminal — no transitions out of RETIRED
# ---------------------------------------------------------------------------


def test_retired_is_terminal():
    manager = _make_manager()
    manager.register("g5")
    # Retire from CANDIDATE (allowed)
    manager.request_transition(
        TransitionRequest(
            genome_id="g5",
            from_state=StrategyState.CANDIDATE,
            to_state=StrategyState.RETIRED,
            reason="initial_retire",
        )
    )
    assert manager.get_state("g5").current_state == StrategyState.RETIRED

    # Attempt any transition from RETIRED — must fail
    ok = manager.request_transition(
        TransitionRequest(
            genome_id="g5",
            from_state=StrategyState.RETIRED,
            to_state=StrategyState.CANDIDATE,
            reason="zombie",
        )
    )

    assert ok is False
    assert manager.get_state("g5").current_state == StrategyState.RETIRED


# ---------------------------------------------------------------------------
# test_promotion_increments_count
# ---------------------------------------------------------------------------


def test_promotion_increments_count():
    manager = _make_manager()
    _register_and_advance(manager, "g6")

    manager.request_transition(
        TransitionRequest(
            genome_id="g6",
            from_state=StrategyState.PAPER_TRADING,
            to_state=StrategyState.PROMOTED,
            reason="good_fitness",
        )
    )

    record = manager.get_state("g6")
    assert record.current_state == StrategyState.PROMOTED
    assert record.promotion_count == 1


# ---------------------------------------------------------------------------
# test_demotion_increments_count
# ---------------------------------------------------------------------------


def test_demotion_increments_count():
    manager = _make_manager()
    _register_and_advance(manager, "g7")

    manager.request_transition(
        TransitionRequest(
            genome_id="g7",
            from_state=StrategyState.PAPER_TRADING,
            to_state=StrategyState.DEMOTED,
            reason="underperformance",
        )
    )

    record = manager.get_state("g7")
    assert record.current_state == StrategyState.DEMOTED
    assert record.demotion_count == 1


# ---------------------------------------------------------------------------
# test_auto_retire — retires all listed genome_ids that are retirable
# ---------------------------------------------------------------------------


def test_auto_retire():
    manager = _make_manager()
    for gid in ["r1", "r2", "r3"]:
        manager.register(gid)
    # Advance r3 to RETIRED already — should be skipped
    manager.request_transition(
        TransitionRequest(
            genome_id="r3",
            from_state=StrategyState.CANDIDATE,
            to_state=StrategyState.RETIRED,
            reason="pre_retired",
        )
    )

    retired = manager.auto_retire(["r1", "r2", "r3"], reason="batch_retire")

    assert set(retired) == {"r1", "r2"}
    assert manager.get_state("r1").current_state == StrategyState.RETIRED
    assert manager.get_state("r2").current_state == StrategyState.RETIRED
    # r3 was already retired, should not appear in returned list
    assert "r3" not in retired
