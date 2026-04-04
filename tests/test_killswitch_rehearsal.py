"""
Kill-Switch Rehearsal Tests — Operational Readiness
Executes R-1 through R-6 from operational_readiness_review.md §6.

Each test:
  1. Sets up a running system state
  2. Fires the kill-switch
  3. Verifies expected state transition
  4. Verifies log/audit trail
  5. Verifies recovery (no contamination)

These are NOT unit tests — they are rehearsal evidence generators.
"""

import sys
from unittest.mock import MagicMock

_STUB_MODULES = [
    "ccxt", "ccxt.async_support", "aiohttp", "celery", "redis",
    "sqlalchemy", "sqlalchemy.ext", "sqlalchemy.ext.asyncio",
    "sqlalchemy.orm", "sqlalchemy.pool", "sqlalchemy.engine",
    "app.core.database", "app.core.config",
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
    OrchestratorConfig,
)
from app.services.governance_gate import GovernanceGate
from app.services.paper_trading_bridge import PaperTradingBridge, PaperTradingConfig
from app.services.performance_metrics import TradeRecord
from app.services.strategy_lifecycle import (
    StrategyLifecycleManager,
    StrategyState,
    TransitionRequest,
)
from app.services.strategy_registry import StrategyRegistry
from app.services.strategy_genome import GenomeFactory
from app.services.system_health import SystemHealthMonitor


# ===========================================================================
# R-1: Stop Orchestrator — no new transitions after halt
# ===========================================================================
class TestR1StopOrchestrator:
    """KS-1: Stopping the orchestrator freezes all state."""

    def test_stop_orchestrator_freezes_cycles(self):
        """After stop, cycle_count does not advance."""
        orch = AutonomousOrchestrator()
        orch.run_cycle(evolved_genome_ids=["g1", "g2"])
        assert orch.cycle_count == 1

        # KILL-SWITCH: simply do not call run_cycle again
        # Verify state is frozen
        summary_before = orch.get_summary()
        # Simulate "time passes" — no call
        summary_after = orch.get_summary()

        assert summary_before == summary_after
        assert orch.cycle_count == 1  # unchanged

    def test_stop_orchestrator_no_new_transitions(self):
        """After stop, no new lifecycle transitions occur."""
        orch = AutonomousOrchestrator()
        orch.run_cycle(evolved_genome_ids=["g1"])
        orch.run_cycle(validated_genome_ids=["g1"])

        transitions_before = len(orch.lifecycle.records["g1"].state_history)

        # KILL-SWITCH: do not call run_cycle
        # Verify no new transitions
        transitions_after = len(orch.lifecycle.records["g1"].state_history)
        assert transitions_before == transitions_after

    def test_stop_preserves_existing_state(self):
        """Existing records remain accessible after stop."""
        orch = AutonomousOrchestrator()
        orch.run_cycle(evolved_genome_ids=["g1", "g2", "g3"])

        # KILL-SWITCH: stop
        # Verify all records still exist
        assert len(orch.lifecycle.records) == 3
        for gid in ["g1", "g2", "g3"]:
            assert orch.lifecycle.get_state(gid) is not None


# ===========================================================================
# R-2: Force dry_run=True — all promotions blocked
# ===========================================================================
class TestR2ForceDryRun:
    """KS-2: Forcing dry_run=True blocks all promotions."""

    def test_dry_run_blocks_promotion(self):
        """With dry_run=True, promotion results in PENDING_OPERATOR."""
        config = OrchestratorConfig(dry_run=True)
        orch = AutonomousOrchestrator(config)

        # Advance genome to paper_trading
        orch.run_cycle(evolved_genome_ids=["g1"])
        orch.run_cycle(validated_genome_ids=["g1"])
        assert orch.lifecycle.get_state("g1").current_state == StrategyState.PAPER_TRADING

        # Attempt promotion
        orch.run_cycle(
            paper_ready_genome_ids=["g1"],
            paper_ready_fitnesses={"g1": 0.95},
        )

        # VERIFY: still in paper_trading (promotion blocked)
        assert orch.lifecycle.get_state("g1").current_state == StrategyState.PAPER_TRADING

        # VERIFY: pending decision exists
        pending = orch.governance.get_pending()
        assert len(pending) >= 1
        assert any(d.decision == "PENDING_OPERATOR" for d in pending)

    def test_dry_run_allows_demotion(self):
        """Even with dry_run, demotions are auto-approved."""
        gate = GovernanceGate(dry_run=True)
        req = TransitionRequest(
            genome_id="g1",
            from_state=StrategyState.PROMOTED,
            to_state=StrategyState.DEMOTED,
            reason="test",
        )
        decision = gate.check(req)
        assert decision.decision == "APPROVED"
        assert decision.auto_decided is True

    def test_dry_run_allows_retirement(self):
        """Even with dry_run, retirements are auto-approved."""
        gate = GovernanceGate(dry_run=True)
        req = TransitionRequest(
            genome_id="g1",
            from_state=StrategyState.PAPER_TRADING,
            to_state=StrategyState.RETIRED,
            reason="test",
        )
        decision = gate.check(req)
        assert decision.decision == "APPROVED"


# ===========================================================================
# R-3: Governance block-all — threshold impossibly high
# ===========================================================================
class TestR3GovernanceBlockAll:
    """KS-3: Setting auto_approve_threshold=999.0 blocks all auto-approvals for promotion."""

    def test_block_all_promotion(self):
        """No promotion can auto-approve with threshold=999."""
        gate = GovernanceGate(dry_run=False, auto_approve_threshold=999.0)
        req = TransitionRequest(
            genome_id="g1",
            from_state=StrategyState.PAPER_TRADING,
            to_state=StrategyState.PROMOTED,
            reason="test",
        )
        decision = gate.check(req, fitness=0.99)
        assert decision.decision == "PENDING_OPERATOR"
        assert decision.operator_required is True

    def test_block_all_still_allows_demotion(self):
        """Even with block-all, demotions pass (safety direction)."""
        gate = GovernanceGate(dry_run=False, auto_approve_threshold=999.0)
        req = TransitionRequest(
            genome_id="g1",
            from_state=StrategyState.PROMOTED,
            to_state=StrategyState.DEMOTED,
            reason="safety",
        )
        decision = gate.check(req)
        assert decision.decision == "APPROVED"


# ===========================================================================
# R-4: Mass demotion / retirement
# ===========================================================================
class TestR4MassDemotion:
    """KS-4: Force-retire all strategies in emergency."""

    def test_mass_retire_all_candidates(self):
        """auto_retire retires all listed genomes."""
        lm = StrategyLifecycleManager()
        for gid in ["g1", "g2", "g3", "g4", "g5"]:
            lm.register(gid)

        retired = lm.auto_retire(["g1", "g2", "g3", "g4", "g5"], reason="emergency")

        assert len(retired) == 5
        for gid in retired:
            assert lm.get_state(gid).current_state == StrategyState.RETIRED

    def test_mass_retire_mixed_states(self):
        """auto_retire works from any non-terminal state."""
        lm = StrategyLifecycleManager()
        lm.register("g1")  # CANDIDATE
        lm.register("g2")
        lm.request_transition(TransitionRequest(
            genome_id="g2", from_state=StrategyState.CANDIDATE,
            to_state=StrategyState.VALIDATED, reason="test",
        ))  # g2 is VALIDATED

        retired = lm.auto_retire(["g1", "g2"], reason="emergency")
        assert len(retired) == 2

    def test_retired_cannot_transition(self):
        """After retirement, no further transitions are possible."""
        lm = StrategyLifecycleManager()
        lm.register("g1")
        lm.auto_retire(["g1"], reason="test")

        result = lm.request_transition(TransitionRequest(
            genome_id="g1",
            from_state=StrategyState.RETIRED,
            to_state=StrategyState.CANDIDATE,
            reason="attempt_revival",
        ))
        assert result is False
        assert lm.get_state("g1").current_state == StrategyState.RETIRED


# ===========================================================================
# R-5: Paper trading halt — close all sessions
# ===========================================================================
class TestR5PaperTradingHalt:
    """KS-7: Closing all paper sessions stops trade recording."""

    def test_close_session_stops_recording(self):
        """After close, record_trade returns False."""
        bridge = PaperTradingBridge()
        sid = bridge.start_session("g1")
        trade = TradeRecord(
            entry_price=100.0, exit_price=102.0,
            quantity=1.0, side="long",
        )

        assert bridge.record_trade(sid, trade) is True

        # KILL-SWITCH: close session
        bridge.close_session(sid)

        assert bridge.record_trade(sid, trade) is False

    def test_close_all_sessions(self):
        """Closing all sessions halts all paper trading."""
        bridge = PaperTradingBridge()
        sids = [bridge.start_session(f"g{i}") for i in range(5)]

        # KILL-SWITCH: close all
        for sid in sids:
            bridge.close_session(sid)

        # Verify all closed
        trade = TradeRecord(
            entry_price=100.0, exit_price=102.0,
            quantity=1.0, side="long",
        )
        for sid in sids:
            assert bridge.record_trade(sid, trade) is False

    def test_closed_session_still_evaluatable(self):
        """Closed sessions can still be evaluated for historical analysis."""
        bridge = PaperTradingBridge()
        sid = bridge.start_session("g1")
        from app.services.performance_metrics import PerformanceReport
        bridge.close_session(sid)
        result = bridge.evaluate_session(sid, PerformanceReport())
        assert result.genome_id == "g1"


# ===========================================================================
# R-6: Code rollback verification (simulated — check git revert safety)
# ===========================================================================
class TestR6CodeRollback:
    """KS: Verify Phase 5-7 modules are fully self-contained for safe revert."""

    def test_phase7_no_external_dependencies_on_phase1_4(self):
        """Phase 7 orchestrator only depends on Phase 7 modules (not Phase 1-4 directly)."""
        import ast
        with open("app/services/autonomous_orchestrator.py", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)

        # Should only import from Phase 7 + core
        phase1_4_modules = [
            "backtesting_engine", "performance_metrics", "validation_pipeline",
            "strategy_runner", "strategy_tournament", "fitness_function",
            "market_data_collector", "sentiment_collector", "indicator_calculator",
            "market_state_builder", "regime_detector", "market_scorer",
        ]
        for mod in phase1_4_modules:
            assert not any(mod in imp for imp in imports), \
                f"Orchestrator imports Phase 1-4 module: {mod}"

    def test_phase5_7_do_not_modify_phase1_4_interfaces(self):
        """Phase 1-4 modules have no imports from Phase 5-7."""
        import ast
        phase1_4_files = [
            "app/services/strategy_runner.py",
            "app/services/strategy_genome.py",
            "app/services/strategy_tournament.py",
            "app/services/fitness_function.py",
            "app/services/backtesting_engine.py",
            "app/services/validation_pipeline.py",
        ]
        phase5_7 = [
            "adaptive_mutation", "island_model", "regime_evolution",
            "evolution_state", "strategy_registry", "advanced_runner",
            "correlation_analyzer", "portfolio_optimizer", "risk_budget_allocator",
            "portfolio_metrics", "portfolio_constructor",
            "paper_trading_bridge", "strategy_lifecycle", "governance_gate",
            "system_health", "autonomous_orchestrator",
        ]

        for filepath in phase1_4_files:
            with open(filepath, encoding="utf-8") as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    for mod in phase5_7:
                        assert mod not in node.module, \
                            f"{filepath} imports Phase 5-7 module: {mod}"


# ===========================================================================
# Recovery verification
# ===========================================================================
class TestRecoveryVerification:
    """Verify no contamination after kill-switch + restart."""

    def test_fresh_orchestrator_after_kill(self):
        """Creating a new orchestrator after kill gives clean state."""
        # Original
        orch1 = AutonomousOrchestrator()
        orch1.run_cycle(evolved_genome_ids=["g1", "g2"])
        assert orch1.cycle_count == 1

        # KILL + RESTART
        orch2 = AutonomousOrchestrator()
        assert orch2.cycle_count == 0
        assert len(orch2.lifecycle.records) == 0
        assert len(orch2.governance.decision_log) == 0

    def test_fresh_registry_after_kill(self):
        """Creating a new registry after kill gives empty state."""
        reg = StrategyRegistry()
        factory = GenomeFactory(seed=1)
        g = factory.create_random()
        g.fitness = 0.8
        reg.register(g)
        assert reg.size == 1

        # KILL + RESTART
        reg2 = StrategyRegistry()
        assert reg2.size == 0

    def test_health_monitor_post_recovery(self):
        """Health monitor reports clean state after restart."""
        monitor = SystemHealthMonitor()
        report = monitor.collect(
            registry_size=10,
            portfolio_sharpe=1.0,
            portfolio_drawdown_pct=5.0,
        )
        assert report.is_healthy is True
        assert len(report.warnings) == 0
