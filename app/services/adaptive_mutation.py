"""
AdaptiveMutation — CR-042 Phase 5
Adaptive mutation rate controller for evolutionary strategies.

Mutation rates adjust based on fitness trajectory:
  - Plateau detected → increase mutation rate (explore more)
  - Improving → decrease mutation rate (exploit current direction)
  - Stagnation → spike mutation rate (escape local optima)

Pure computation — no I/O.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import copy
from app.core.logging import get_logger
from app.services.strategy_genome import StrategyGenome, GenomeFactory

logger = get_logger(__name__)


@dataclass
class MutationSchedule:
    """Tracks adaptive mutation state."""

    base_rate: float = 0.1
    current_rate: float = 0.1
    min_rate: float = 0.01
    max_rate: float = 0.5
    plateau_window: int = 5  # generations to detect plateau
    plateau_threshold: float = 0.005  # min fitness improvement to not be "plateau"
    stagnation_window: int = 10  # generations to detect stagnation
    history: list[float] = field(default_factory=list)  # best fitness per generation


class AdaptiveMutationController:
    """Controls mutation rates based on evolutionary progress."""

    def __init__(self, schedule: MutationSchedule | None = None):
        self.schedule = schedule or MutationSchedule()

    def update(self, generation: int, best_fitness: float) -> MutationSchedule:
        """Update schedule with new generation's best fitness."""
        self.schedule.history.append(best_fitness)

        if len(self.schedule.history) < self.schedule.plateau_window:
            # Not enough history yet
            return self.schedule

        # Check for plateau: recent window shows < threshold improvement
        recent = self.schedule.history[-self.schedule.plateau_window :]
        improvement = max(recent) - min(recent)

        if improvement < self.schedule.plateau_threshold:
            # Plateau detected — check if stagnation (longer plateau)
            if len(self.schedule.history) >= self.schedule.stagnation_window:
                stag_window = self.schedule.history[-self.schedule.stagnation_window :]
                stag_improvement = max(stag_window) - min(stag_window)
                if stag_improvement < self.schedule.plateau_threshold:
                    # Stagnation — spike mutation rate
                    self.schedule.current_rate = min(
                        self.schedule.current_rate * 2.0, self.schedule.max_rate
                    )
                    logger.info(
                        "mutation_stagnation_spike",
                        rate=round(self.schedule.current_rate, 4),
                        gen=generation,
                    )
                    return self.schedule

            # Regular plateau — increase moderately
            self.schedule.current_rate = min(
                self.schedule.current_rate * 1.3, self.schedule.max_rate
            )
            logger.info(
                "mutation_plateau_increase",
                rate=round(self.schedule.current_rate, 4),
                gen=generation,
            )
        else:
            # Improving — decrease rate (exploit)
            self.schedule.current_rate = max(
                self.schedule.current_rate * 0.9, self.schedule.min_rate
            )
            logger.info(
                "mutation_improving_decrease",
                rate=round(self.schedule.current_rate, 4),
                gen=generation,
            )

        return self.schedule

    def get_rate(self) -> float:
        """Get current adaptive mutation rate."""
        return self.schedule.current_rate

    def apply_to_genome(self, genome: StrategyGenome) -> StrategyGenome:
        """Apply current adaptive rate to all genes in a genome."""
        modified = copy.deepcopy(genome)
        rate = self.schedule.current_rate

        for group_name in ["indicator_genes", "entry_genes", "risk_genes", "regime_genes"]:
            gene_group = getattr(modified, group_name)
            for name, gene in gene_group.items():
                gene.mutation_rate = rate

        return modified

    def reset(self) -> None:
        """Reset to base rates."""
        self.schedule.current_rate = self.schedule.base_rate
        self.schedule.history.clear()
