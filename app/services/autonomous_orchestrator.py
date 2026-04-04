"""
AutonomousOrchestrator — CR-044 Phase 7
Master loop connecting all subsystems.

Cycle: Evolve → Validate → Paper Trade → Lifecycle → Portfolio → Health

dry_run=True by default. All decisions gated by GovernanceGate.

Pure computation — no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.services.governance_gate import GovernanceGate, GovernanceDecision
from app.services.strategy_lifecycle import (
    StrategyLifecycleManager, StrategyState, TransitionRequest
)
from app.services.system_health import SystemHealthMonitor, SystemHealthReport

logger = get_logger(__name__)


@dataclass
class OrchestratorConfig:
    max_promoted: int = 5
    dry_run: bool = True
    auto_approve_threshold: float = 0.8


@dataclass
class CycleResult:
    cycle_number: int = 0
    candidates_evolved: int = 0
    validations_run: int = 0
    paper_evaluations: int = 0
    transitions: list[str] = field(default_factory=list)
    governance_decisions: list[GovernanceDecision] = field(default_factory=list)
    health: SystemHealthReport | None = None
    is_healthy: bool = True


class AutonomousOrchestrator:
    """Master orchestrator for the autonomous trading system."""

    def __init__(self, config: OrchestratorConfig | None = None):
        self.config = config or OrchestratorConfig()
        self.lifecycle = StrategyLifecycleManager()
        self.governance = GovernanceGate(
            dry_run=self.config.dry_run,
            auto_approve_threshold=self.config.auto_approve_threshold,
        )
        self.health_monitor = SystemHealthMonitor()
        self.cycle_count = 0

    def run_cycle(
        self,
        evolved_genome_ids: list[str] | None = None,
        validated_genome_ids: list[str] | None = None,
        paper_ready_genome_ids: list[str] | None = None,
        paper_ready_fitnesses: dict[str, float] | None = None,
        registry_size: int = 0,
        portfolio_sharpe: float = 0.0,
        portfolio_drawdown_pct: float = 0.0,
    ) -> CycleResult:
        """
        Run one orchestration cycle.

        External callers provide the results from evolution, validation,
        and paper trading steps. The orchestrator manages lifecycle
        transitions, governance checks, and health monitoring.
        """
        self.cycle_count += 1
        result = CycleResult(cycle_number=self.cycle_count)

        evolved_genome_ids = evolved_genome_ids or []
        validated_genome_ids = validated_genome_ids or []
        paper_ready_genome_ids = paper_ready_genome_ids or []
        paper_ready_fitnesses = paper_ready_fitnesses or {}

        # 1. Register new candidates
        for gid in evolved_genome_ids:
            if gid not in self.lifecycle.records:
                self.lifecycle.register(gid)
                result.candidates_evolved += 1

        # 2. Transition validated candidates
        for gid in validated_genome_ids:
            record = self.lifecycle.get_state(gid)
            if record and record.current_state == StrategyState.CANDIDATE:
                req = TransitionRequest(
                    genome_id=gid,
                    from_state=StrategyState.CANDIDATE,
                    to_state=StrategyState.VALIDATED,
                    reason="passed_validation",
                )
                decision = self.governance.check(req)
                result.governance_decisions.append(decision)
                if decision.decision == "APPROVED":
                    self.lifecycle.request_transition(req)
                    result.transitions.append(f"{gid}: candidate→validated")
                    result.validations_run += 1

                    # Auto-transition to paper trading
                    paper_req = TransitionRequest(
                        genome_id=gid,
                        from_state=StrategyState.VALIDATED,
                        to_state=StrategyState.PAPER_TRADING,
                        reason="auto_paper_start",
                    )
                    paper_decision = self.governance.check(paper_req)
                    result.governance_decisions.append(paper_decision)
                    if paper_decision.decision == "APPROVED":
                        self.lifecycle.request_transition(paper_req)
                        result.transitions.append(f"{gid}: validated→paper_trading")

        # 3. Evaluate paper trading results
        promoted_count = len(self.lifecycle.get_by_state(StrategyState.PROMOTED))
        for gid in paper_ready_genome_ids:
            record = self.lifecycle.get_state(gid)
            if record and record.current_state == StrategyState.PAPER_TRADING:
                fitness = paper_ready_fitnesses.get(gid, 0.0)
                req = TransitionRequest(
                    genome_id=gid,
                    from_state=StrategyState.PAPER_TRADING,
                    to_state=StrategyState.PROMOTED,
                    reason=f"paper_trading_passed_fitness_{fitness:.4f}",
                )
                decision = self.governance.check(req, fitness=fitness)
                result.governance_decisions.append(decision)

                if decision.decision == "APPROVED" and promoted_count < self.config.max_promoted:
                    self.lifecycle.request_transition(req)
                    result.transitions.append(f"{gid}: paper_trading→promoted")
                    promoted_count += 1
                    result.paper_evaluations += 1

        # 4. Health check
        result.health = self.health_monitor.collect(
            registry_size=registry_size,
            promoted_count=len(self.lifecycle.get_by_state(StrategyState.PROMOTED)),
            portfolio_sharpe=portfolio_sharpe,
            portfolio_drawdown_pct=portfolio_drawdown_pct,
            governance_pending=len(self.governance.get_pending()),
        )
        result.is_healthy = result.health.is_healthy

        logger.info("orchestrator_cycle_complete",
                     cycle=self.cycle_count,
                     transitions=len(result.transitions),
                     healthy=result.is_healthy)
        return result

    def get_summary(self) -> dict:
        return {
            "cycles_run": self.cycle_count,
            "total_records": len(self.lifecycle.records),
            "promoted": len(self.lifecycle.get_by_state(StrategyState.PROMOTED)),
            "paper_trading": len(self.lifecycle.get_by_state(StrategyState.PAPER_TRADING)),
            "retired": len(self.lifecycle.get_by_state(StrategyState.RETIRED)),
            "pending_governance": len(self.governance.get_pending()),
        }
