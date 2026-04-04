"""Tests for AutonomousOrchestrator — CR-044 Phase 7."""

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

from app.services.autonomous_orchestrator import (
    AutonomousOrchestrator,
    CycleResult,
    OrchestratorConfig,
)
from app.services.strategy_lifecycle import StrategyState


def test_config_defaults():
    """OrchestratorConfig has sensible defaults."""
    config = OrchestratorConfig()
    assert config.max_promoted == 5
    assert config.dry_run is True
    assert config.auto_approve_threshold == 0.8


def test_run_cycle_registers_candidates():
    """Evolved genome IDs are registered as candidates."""
    orch = AutonomousOrchestrator()
    result = orch.run_cycle(evolved_genome_ids=["g1", "g2", "g3"])
    assert result.candidates_evolved == 3
    assert len(orch.lifecycle.records) == 3
    for gid in ["g1", "g2", "g3"]:
        assert orch.lifecycle.get_state(gid).current_state == StrategyState.CANDIDATE


def test_run_cycle_validates_candidates():
    """Validated genome IDs transition through candidate→validated→paper_trading."""
    orch = AutonomousOrchestrator()
    # First register as candidates
    orch.run_cycle(evolved_genome_ids=["g1", "g2"])
    # Then validate
    result = orch.run_cycle(validated_genome_ids=["g1"])
    assert result.validations_run == 1
    record = orch.lifecycle.get_state("g1")
    assert record.current_state == StrategyState.PAPER_TRADING


def test_run_cycle_paper_to_promoted_dry_run():
    """In dry_run mode, promotion is PENDING_OPERATOR, not auto-approved."""
    config = OrchestratorConfig(dry_run=True)
    orch = AutonomousOrchestrator(config)
    # Register → validate → paper
    orch.run_cycle(evolved_genome_ids=["g1"])
    orch.run_cycle(validated_genome_ids=["g1"])
    # Try promote from paper trading
    result = orch.run_cycle(
        paper_ready_genome_ids=["g1"],
        paper_ready_fitnesses={"g1": 0.9},
    )
    # Should still be in paper_trading because promotion needs operator
    record = orch.lifecycle.get_state("g1")
    assert record.current_state == StrategyState.PAPER_TRADING
    # Governance should have a pending decision
    pending = orch.governance.get_pending()
    assert len(pending) >= 1


def test_run_cycle_health_check_runs():
    """Every cycle includes a health check."""
    orch = AutonomousOrchestrator()
    result = orch.run_cycle(registry_size=10, portfolio_sharpe=1.0)
    assert result.health is not None
    assert result.is_healthy is True


def test_get_summary_structure():
    """get_summary returns expected keys."""
    orch = AutonomousOrchestrator()
    orch.run_cycle(evolved_genome_ids=["g1"])
    summary = orch.get_summary()
    assert "cycles_run" in summary
    assert "total_records" in summary
    assert "promoted" in summary
    assert summary["total_records"] == 1


def test_multiple_cycles_accumulate():
    """Multiple cycles accumulate state correctly."""
    orch = AutonomousOrchestrator()
    orch.run_cycle(evolved_genome_ids=["g1", "g2"])
    orch.run_cycle(evolved_genome_ids=["g3"])
    assert orch.cycle_count == 2
    assert len(orch.lifecycle.records) == 3
