"""
EvolutionState — CR-042 Phase 5
Serialization and persistence of evolution state.

Enables pausing and resuming evolution across runs by checkpointing
population state, fitness history, and mutation schedule.

Pure computation — no I/O (serializes to/from dicts, not files).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.core.logging import get_logger
from app.services.strategy_genome import Gene, StrategyGenome

logger = get_logger(__name__)


@dataclass
class EvolutionCheckpoint:
    """Snapshot of evolution state at a point in time."""
    timestamp: str = ""
    generation: int = 0
    islands: list[dict] = field(default_factory=list)
    hall_of_fame: list[dict] = field(default_factory=list)
    mutation_schedule: dict = field(default_factory=dict)
    fitness_history: list[float] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class EvolutionStateManager:
    """Manages serialization of evolution state for persistence."""

    def save(
        self,
        generation: int,
        populations: list[list[StrategyGenome]],
        hall_of_fame: list[StrategyGenome] | None = None,
        mutation_state: dict | None = None,
        fitness_history: list[float] | None = None,
    ) -> EvolutionCheckpoint:
        """Create a checkpoint from current state."""
        checkpoint = EvolutionCheckpoint(
            timestamp=datetime.now(timezone.utc).isoformat(),
            generation=generation,
            islands=[
                [g.to_dict() for g in pop]
                for pop in populations
            ],
            hall_of_fame=[g.to_dict() for g in (hall_of_fame or [])],
            mutation_schedule=mutation_state or {},
            fitness_history=list(fitness_history or []),
        )

        logger.info("checkpoint_saved",
                    generation=generation,
                    islands=len(populations),
                    hof_size=len(checkpoint.hall_of_fame))
        return checkpoint

    def load(self, checkpoint: EvolutionCheckpoint) -> dict:
        """
        Restore state from a checkpoint.

        Returns dict with:
          - generation: int
          - populations: list[list[StrategyGenome]]
          - hall_of_fame: list[StrategyGenome]
          - mutation_schedule: dict
          - fitness_history: list[float]
        """
        populations = []
        for island_data in checkpoint.islands:
            pop = [self._dict_to_genome(gd) for gd in island_data]
            populations.append(pop)

        hof = [self._dict_to_genome(gd) for gd in checkpoint.hall_of_fame]

        logger.info("checkpoint_loaded",
                    generation=checkpoint.generation,
                    islands=len(populations),
                    hof_size=len(hof))

        return {
            "generation": checkpoint.generation,
            "populations": populations,
            "hall_of_fame": hof,
            "mutation_schedule": checkpoint.mutation_schedule,
            "fitness_history": checkpoint.fitness_history,
        }

    def to_json(self, checkpoint: EvolutionCheckpoint) -> str:
        """Serialize checkpoint to JSON string."""
        data = {
            "timestamp": checkpoint.timestamp,
            "generation": checkpoint.generation,
            "islands": checkpoint.islands,
            "hall_of_fame": checkpoint.hall_of_fame,
            "mutation_schedule": checkpoint.mutation_schedule,
            "fitness_history": checkpoint.fitness_history,
            "metadata": checkpoint.metadata,
        }
        return json.dumps(data, default=str)

    def from_json(self, json_str: str) -> EvolutionCheckpoint:
        """Deserialize checkpoint from JSON string."""
        data = json.loads(json_str)
        return EvolutionCheckpoint(**data)

    def _dict_to_genome(self, data: dict) -> StrategyGenome:
        """Reconstruct a StrategyGenome from its dict representation."""
        genome = StrategyGenome(
            id=data.get("id", ""),
            generation=data.get("generation", 0),
            parent_ids=data.get("parent_ids", []),
            fitness=data.get("fitness", 0.0),
            age=data.get("age", 0),
            wins=data.get("wins", 0),
            regime_tag=data.get("regime_tag", ""),
        )
        # Params are flat — we can't fully reconstruct gene bounds from params alone,
        # but we preserve the values for fitness comparison.
        group_attr_map = {
            "ind": "indicator_genes",
            "entry": "entry_genes",
            "risk": "risk_genes",
            "regime": "regime_genes",
        }
        params = data.get("params", {})
        for key, value in params.items():
            parts = key.split(".", 1)
            if len(parts) == 2:
                group_name, gene_name = parts
                gene = Gene(name=gene_name, value=float(value), min_val=0, max_val=1000)
                group_attr = group_attr_map.get(group_name)
                if group_attr:
                    getattr(genome, group_attr)[gene_name] = gene

        return genome
