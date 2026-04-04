"""
StrategyGenome — CR-041 Phase 4
Represents strategy parameters as a genetic structure.
Supports crossover, mutation, and regime-specific adaptation.

Gene categories:
  - Indicator genes: RSI period, MACD fast/slow/signal, BB period/std
  - Entry genes: confidence threshold, signal strength filter
  - Risk genes: stop loss %, take profit %, position size %
  - Regime genes: preferred regime, regime sensitivity

Pure data structure + operators — no I/O.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import numpy as np

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Gene:
    """Single gene with value, bounds, and mutation rate."""

    name: str
    value: float
    min_val: float
    max_val: float
    mutation_rate: float = 0.1  # Probability of mutation
    mutation_scale: float = 0.2  # Scale of mutation (% of range)
    is_integer: bool = False

    def mutate(self, rng: np.random.RandomState) -> Gene:
        """Return a mutated copy of this gene."""
        new = copy.deepcopy(self)
        if rng.random() < self.mutation_rate:
            range_size = self.max_val - self.min_val
            delta = rng.normal(0, self.mutation_scale * range_size)
            new.value = float(np.clip(self.value + delta, self.min_val, self.max_val))
            if self.is_integer:
                new.value = float(round(new.value))
        return new


@dataclass
class StrategyGenome:
    """Complete genetic representation of a strategy."""

    id: str = field(default_factory=lambda: str(uuid4())[:8])
    generation: int = 0
    parent_ids: list[str] = field(default_factory=list)

    # Gene groups
    indicator_genes: dict[str, Gene] = field(default_factory=dict)
    entry_genes: dict[str, Gene] = field(default_factory=dict)
    risk_genes: dict[str, Gene] = field(default_factory=dict)
    regime_genes: dict[str, Gene] = field(default_factory=dict)

    # Metadata
    fitness: float = 0.0
    age: int = 0  # Generations survived
    wins: int = 0  # Tournament wins
    regime_tag: str = ""  # Preferred market regime

    @property
    def all_genes(self) -> dict[str, Gene]:
        return {
            **{f"ind.{k}": v for k, v in self.indicator_genes.items()},
            **{f"entry.{k}": v for k, v in self.entry_genes.items()},
            **{f"risk.{k}": v for k, v in self.risk_genes.items()},
            **{f"regime.{k}": v for k, v in self.regime_genes.items()},
        }

    def to_params(self) -> dict[str, float]:
        """Convert genome to flat parameter dictionary."""
        return {name: gene.value for name, gene in self.all_genes.items()}

    def to_dict(self) -> dict[str, Any]:
        """Serialize for storage."""
        return {
            "id": self.id,
            "generation": self.generation,
            "parent_ids": self.parent_ids,
            "fitness": self.fitness,
            "age": self.age,
            "wins": self.wins,
            "regime_tag": self.regime_tag,
            "params": self.to_params(),
        }


class GenomeFactory:
    """Creates and operates on StrategyGenomes."""

    def __init__(self, seed: int | None = None):
        self.rng = np.random.RandomState(seed)

    def create_default(self) -> StrategyGenome:
        """Create a genome with default SMA crossover parameters."""
        return StrategyGenome(
            indicator_genes={
                "strategy_type": Gene(
                    "strategy_type", 0, 0, 1, is_integer=True
                ),  # CR-045: 0=SMA, 1=RSI
                "fast_period": Gene("fast_period", 10, 3, 50, is_integer=True),
                "slow_period": Gene("slow_period", 20, 10, 200, is_integer=True),
                "rsi_period": Gene("rsi_period", 14, 5, 30, is_integer=True),
                "rsi_overbought": Gene("rsi_overbought", 70, 60, 90),
                "rsi_oversold": Gene("rsi_oversold", 30, 10, 40),
                "bb_period": Gene("bb_period", 20, 10, 50, is_integer=True),
                "bb_std": Gene("bb_std", 2.0, 1.0, 3.0),
            },
            entry_genes={
                "confidence_threshold": Gene("confidence_threshold", 0.6, 0.3, 0.95),
                "min_signal_strength": Gene("min_signal_strength", 0.5, 0.1, 0.9),
            },
            risk_genes={
                "stop_loss_pct": Gene("stop_loss_pct", 2.0, 0.5, 10.0),
                "take_profit_pct": Gene("take_profit_pct", 4.0, 1.0, 20.0),
                "position_size_pct": Gene("position_size_pct", 10.0, 1.0, 25.0),
                "max_drawdown_limit": Gene("max_drawdown_limit", 20.0, 5.0, 50.0),
            },
            regime_genes={
                "trend_sensitivity": Gene("trend_sensitivity", 0.5, 0.0, 1.0),
                "volatility_threshold": Gene("volatility_threshold", 3.0, 1.0, 8.0),
            },
        )

    def create_random(self) -> StrategyGenome:
        """Create a genome with randomized parameters."""
        genome = self.create_default()
        for gene_group in [
            genome.indicator_genes,
            genome.entry_genes,
            genome.risk_genes,
            genome.regime_genes,
        ]:
            for name, gene in gene_group.items():
                gene.value = float(self.rng.uniform(gene.min_val, gene.max_val))
                if gene.is_integer:
                    gene.value = float(round(gene.value))
        return genome

    def crossover(self, parent_a: StrategyGenome, parent_b: StrategyGenome) -> StrategyGenome:
        """Uniform crossover: each gene randomly selected from either parent."""
        child = self.create_default()
        child.generation = max(parent_a.generation, parent_b.generation) + 1
        child.parent_ids = [parent_a.id, parent_b.id]

        for group_name in ["indicator_genes", "entry_genes", "risk_genes", "regime_genes"]:
            parent_a_group = getattr(parent_a, group_name)
            parent_b_group = getattr(parent_b, group_name)
            child_group = getattr(child, group_name)

            for gene_name in child_group:
                if gene_name in parent_a_group and gene_name in parent_b_group:
                    if self.rng.random() < 0.5:
                        child_group[gene_name] = copy.deepcopy(parent_a_group[gene_name])
                    else:
                        child_group[gene_name] = copy.deepcopy(parent_b_group[gene_name])

        return child

    def mutate(self, genome: StrategyGenome) -> StrategyGenome:
        """Mutate all genes according to their mutation rates."""
        mutated = copy.deepcopy(genome)
        mutated.id = str(uuid4())[:8]

        for group_name in ["indicator_genes", "entry_genes", "risk_genes", "regime_genes"]:
            gene_group = getattr(mutated, group_name)
            for name, gene in gene_group.items():
                gene_group[name] = gene.mutate(self.rng)

        # Enforce constraint: fast_period < slow_period
        if "fast_period" in mutated.indicator_genes and "slow_period" in mutated.indicator_genes:
            fast = mutated.indicator_genes["fast_period"].value
            slow = mutated.indicator_genes["slow_period"].value
            if fast >= slow:
                mutated.indicator_genes["slow_period"].value = fast + 5

        return mutated

    def create_population(self, size: int) -> list[StrategyGenome]:
        """Create a population of random genomes."""
        return [self.create_random() for _ in range(size)]
