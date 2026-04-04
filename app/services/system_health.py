"""
SystemHealth — CR-044 Phase 7
System health monitoring and dashboard data.

Aggregates health metrics from all subsystems:
evolution, registry, lifecycle, portfolio.

Pure computation — no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SystemHealthReport:
    timestamp: str = ""
    evolution_generation: int = 0
    registry_size: int = 0
    active_paper_sessions: int = 0
    promoted_strategies: int = 0
    portfolio_sharpe: float = 0.0
    portfolio_drawdown_pct: float = 0.0
    governance_pending: int = 0
    warnings: list[str] = field(default_factory=list)
    is_healthy: bool = True


class SystemHealthMonitor:
    """Aggregates system health from all subsystems."""

    def __init__(
        self,
        max_drawdown_threshold: float = 30.0,
        min_registry_size: int = 3,
        max_pending_governance: int = 10,
    ):
        self.max_dd = max_drawdown_threshold
        self.min_registry = min_registry_size
        self.max_pending = max_pending_governance

    def collect(
        self,
        evolution_generation: int = 0,
        registry_size: int = 0,
        active_paper_sessions: int = 0,
        promoted_count: int = 0,
        portfolio_sharpe: float = 0.0,
        portfolio_drawdown_pct: float = 0.0,
        governance_pending: int = 0,
    ) -> SystemHealthReport:
        report = SystemHealthReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            evolution_generation=evolution_generation,
            registry_size=registry_size,
            active_paper_sessions=active_paper_sessions,
            promoted_strategies=promoted_count,
            portfolio_sharpe=portfolio_sharpe,
            portfolio_drawdown_pct=portfolio_drawdown_pct,
            governance_pending=governance_pending,
        )

        # Check circuit breakers
        warnings = self.check_circuit_breakers(report)
        report.warnings = warnings
        report.is_healthy = len(warnings) == 0

        logger.info("system_health_collected",
                     healthy=report.is_healthy,
                     warnings=len(warnings))
        return report

    def check_circuit_breakers(self, report: SystemHealthReport) -> list[str]:
        warnings = []

        if report.portfolio_drawdown_pct > self.max_dd:
            warnings.append(
                f"Portfolio drawdown {report.portfolio_drawdown_pct:.1f}% exceeds limit {self.max_dd:.1f}%"
            )

        if report.registry_size < self.min_registry:
            warnings.append(
                f"Registry size {report.registry_size} below minimum {self.min_registry}"
            )

        if report.governance_pending > self.max_pending:
            warnings.append(
                f"Governance queue {report.governance_pending} exceeds limit {self.max_pending}"
            )

        if report.portfolio_sharpe < 0:
            warnings.append(f"Portfolio Sharpe ratio negative: {report.portfolio_sharpe:.4f}")

        return warnings
