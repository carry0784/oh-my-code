"""
K-Dexter Latency Observation Schema (v1)

Per-tier observational elapsed-time summary.
No percentiles, no mean, no end-to-end, no trend.

Measures: proposal created_at → receipt milestone timestamp (per tier).
Reports: median, min, max seconds + sample metadata.

Safety:
  - Read-only: no writes, no mutations
  - Simulation-only: no execution triggered
  - No prediction: no SLA, no scoring, no threshold judgment
  - No recommendation: no action trigger, no escalation
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class TierLatency(BaseModel):
    """Per-tier elapsed time observation."""
    tier_name: str = ""
    tier_number: int = 0
    measured: bool = False
    sample_size: int = 0
    excluded_count: int = 0
    sample_limited: bool = False
    min_seconds: float = 0.0
    max_seconds: float = 0.0
    median_seconds: float = 0.0


class LatencyDensitySignal(BaseModel):
    """Descriptive density signal for latency observation."""
    has_measurements: bool = False
    tiers_measured: int = 0
    slowest_tier: str = ""
    slowest_median: float = 0.0
    description: str = ""


class LatencySafety(BaseModel):
    """Safety invariant — observation layer standard (4 fields)."""
    read_only: bool = True
    simulation_only: bool = True
    no_action_executed: bool = True
    no_prediction: bool = True


class LatencyObservationSchema(BaseModel):
    """
    Latency Observation v1 — per-tier elapsed-time summary.

    Each tier measures elapsed seconds from proposal creation
    to receipt milestone. No end-to-end, no percentiles, no mean.
    """
    agent_latency: TierLatency = Field(default_factory=lambda: TierLatency(tier_name="Agent", tier_number=1))
    execution_latency: TierLatency = Field(default_factory=lambda: TierLatency(tier_name="Execution", tier_number=2))
    submit_latency: TierLatency = Field(default_factory=lambda: TierLatency(tier_name="Submit", tier_number=3))
    order_latency: TierLatency = Field(default_factory=lambda: TierLatency(tier_name="Orders", tier_number=4))
    density: LatencyDensitySignal = Field(default_factory=LatencyDensitySignal)
    safety: LatencySafety = Field(default_factory=LatencySafety)
