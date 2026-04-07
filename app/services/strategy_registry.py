"""
StrategyRegistry — CR-042 Phase 5
Hall of Fame for top-performing strategies.

Maintains a ranked registry of the best strategy genomes discovered
during evolution. Supports deduplication, regime filtering, and
capacity limits.

Pure computation — no I/O.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger
from app.services.strategy_genome import StrategyGenome
from app.services.validation_pipeline import ValidationResult

logger = get_logger(__name__)


@dataclass
class RegistryEntry:
    """Single entry in the strategy registry."""

    genome: StrategyGenome
    registered_at: str = ""
    validation_status: str = ""
    regime_tag: str = ""
    lifetime_fitness: float = 0.0
    rank: int = 0


class StrategyRegistry:
    """Hall of Fame registry for top strategies."""

    def __init__(self, max_entries: int = 50, similarity_threshold: float = 0.95):
        self.max_entries = max_entries
        self.similarity_threshold = similarity_threshold
        self.entries: list[RegistryEntry] = []

    def register(
        self,
        genome: StrategyGenome,
        validation: ValidationResult | None = None,
    ) -> RegistryEntry | None:
        """
        Register a genome in the hall of fame.
        Returns None if a duplicate is detected.
        """
        if self.is_duplicate(genome):
            logger.info("registry_duplicate_rejected", genome_id=genome.id)
            return None

        entry = RegistryEntry(
            genome=copy.deepcopy(genome),
            registered_at=datetime.now(timezone.utc).isoformat(),
            validation_status=(validation.overall_status.value if validation else "unvalidated"),
            regime_tag=genome.regime_tag,
            lifetime_fitness=genome.fitness,
        )
        self.entries.append(entry)

        # Sort by fitness descending and assign ranks
        self.entries.sort(key=lambda e: e.lifetime_fitness, reverse=True)
        for i, e in enumerate(self.entries):
            e.rank = i + 1

        # Trim to max capacity
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[: self.max_entries]

        logger.info(
            "registry_entry_added",
            genome_id=genome.id,
            fitness=round(genome.fitness, 4),
            rank=entry.rank,
            total=len(self.entries),
        )
        return entry

    def get_top_n(self, n: int, regime: str | None = None) -> list[RegistryEntry]:
        """Get top N entries, optionally filtered by regime."""
        if regime:
            filtered = [e for e in self.entries if e.regime_tag == regime]
        else:
            filtered = self.entries
        return filtered[:n]

    def is_duplicate(self, genome: StrategyGenome, threshold: float | None = None) -> bool:
        """
        Check if a genome is too similar to existing entries.
        Similarity is based on parameter distance.
        """
        thresh = threshold if threshold is not None else self.similarity_threshold
        new_params = genome.to_params()

        for entry in self.entries:
            existing_params = entry.genome.to_params()
            similarity = self._param_similarity(new_params, existing_params)
            if similarity >= thresh:
                return True
        return False

    def retire(self, genome_id: str) -> bool:
        """Remove a genome from the registry."""
        before = len(self.entries)
        self.entries = [e for e in self.entries if e.genome.id != genome_id]
        removed = len(self.entries) < before
        if removed:
            # Re-rank remaining entries
            for i, e in enumerate(self.entries):
                e.rank = i + 1
            logger.info("registry_entry_retired", genome_id=genome_id)
        return removed

    def export(self) -> list[dict[str, Any]]:
        """Export registry as list of dicts."""
        return [
            {
                "rank": e.rank,
                "genome_id": e.genome.id,
                "fitness": e.lifetime_fitness,
                "regime_tag": e.regime_tag,
                "validation_status": e.validation_status,
                "registered_at": e.registered_at,
                "params": e.genome.to_params(),
            }
            for e in self.entries
        ]

    @property
    def size(self) -> int:
        return len(self.entries)

    def _param_similarity(self, params_a: dict[str, Any], params_b: dict[str, Any]) -> float:
        """Calculate similarity between two parameter sets (0.0 to 1.0)."""
        all_keys = set(params_a.keys()) | set(params_b.keys())
        if not all_keys:
            return 1.0

        matches = 0
        for key in all_keys:
            va = params_a.get(key, 0.0)
            vb = params_b.get(key, 0.0)
            # Consider similar if within 5% of each other
            max_val = max(abs(va), abs(vb), 1e-9)
            if abs(va - vb) / max_val < 0.05:
                matches += 1

        return matches / len(all_keys)
