"""
K-Dexter 4-Tier Board Schema

Read-only response model for the unified 4-tier seal chain dashboard.
Aggregates Agent → Execution → Submit → Order layers into a single view.

Design rules:
  - No raw reasoning, no error_class, no prompts (N-01~N-12)
  - BLOCKED/FAILED counts separated, never merged
  - Orphan = GUARDED proposals without receipt (not yet terminal)
  - guard_reason_top shows most frequent block reasons
  - Lineage trace: AP-* → EP-* → SP-* → OX-*
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.decision_card_schema import DecisionCard
from app.schemas.decision_summary_schema import DecisionSummarySchema
from app.schemas.observation_summary_schema import ObservationSummarySchema
from app.schemas.review_volume_schema import ReviewVolumeSchema
from app.schemas.watch_volume_schema import WatchVolumeSchema
from app.schemas.blockage_summary_schema import BlockageSummarySchema
from app.schemas.retry_pressure_schema import RetryPressureSchema
from app.schemas.latency_observation_schema import LatencyObservationSchema
from app.schemas.trend_observation_schema import TrendObservationSchema


class TierSummary(BaseModel):
    """Summary counts for a single tier."""
    tier_name: str
    tier_number: int
    total: int = 0
    receipted_count: int = 0
    blocked_count: int = 0
    failed_count: int = 0
    orphan_count: int = 0
    stale_count: int = 0
    stale_threshold_seconds: float = 0.0
    guard_reason_top: list[str] = Field(default_factory=list)
    connected: bool = False


class OrderTierSummary(BaseModel):
    """Summary for the Order Executor tier (external caller)."""
    tier_name: str = "Orders"
    tier_number: int = 4
    total: int = 0
    filled_count: int = 0
    partial_count: int = 0
    rejected_count: int = 0
    timeout_count: int = 0
    error_count: int = 0
    pending_count: int = 0
    dry_run_count: int = 0
    connected: bool = False


class OrphanDetail(BaseModel):
    """Single orphan detail entry for board display."""
    proposal_id: str = ""
    tier: str = ""                          # "execution" | "submit"
    missing_parent_type: str = ""           # "agent_proposal_id" | "execution_proposal_id"
    missing_parent_id: Optional[str] = None
    current_status: str = ""
    created_at: str = ""


class CleanupActionSummary(BaseModel):
    """Cleanup action class counts (from simulation)."""
    INFO: int = 0
    WATCH: int = 0
    REVIEW: int = 0
    MANUAL_CLEANUP_CANDIDATE: int = 0


class DerivedFlags(BaseModel):
    """Current derived property flags across the chain."""
    execution_ready_pending: int = 0   # EXEC_GUARDED but not RECEIPTED
    submit_ready_pending: int = 0      # SUBMIT_GUARDED but not RECEIPTED
    execution_ready_true: int = 0      # EXEC_RECEIPTED
    submit_ready_true: int = 0         # SUBMIT_RECEIPTED


class LineageEntry(BaseModel):
    """Single lineage trace (most recent, for dashboard display)."""
    agent_proposal_id: Optional[str] = None
    execution_proposal_id: Optional[str] = None
    submit_proposal_id: Optional[str] = None
    order_id: Optional[str] = None
    status: Optional[str] = None
    submit_ready: Optional[bool] = None
    execution_ready: Optional[bool] = None


class FourTierBoardResponse(BaseModel):
    """
    Unified 4-tier seal chain board.

    Layout:
    ┌─────────────────────────────────────────────────────┐
    │ Tier 1: Agent      │ Receipted │ Blocked │ Orphan   │
    │ Tier 2: Execution  │ Receipted │ Blocked │ Orphan   │
    │ Tier 3: Submit     │ Receipted │ Blocked │ Orphan   │
    │ Tier 4: Orders     │ Filled    │ Error   │ Timeout  │
    ├─────────────────────────────────────────────────────┤
    │ Top Block Reasons (aggregated)                      │
    │ Derived Flags: execution_ready / submit_ready       │
    │ Recent Lineage Trace                                │
    └─────────────────────────────────────────────────────┘
    """
    agent_tier: TierSummary
    execution_tier: TierSummary
    submit_tier: TierSummary
    order_tier: OrderTierSummary
    derived_flags: DerivedFlags
    top_block_reasons_all: list[str] = Field(default_factory=list)
    recent_lineage: list[LineageEntry] = Field(default_factory=list, max_length=10)
    cross_tier_orphan_count: int = 0
    cross_tier_orphan_detail: list[OrphanDetail] = Field(default_factory=list)
    cleanup_candidate_count: int = 0
    cleanup_action_summary: CleanupActionSummary = Field(default_factory=CleanupActionSummary)
    cleanup_simulation_only: bool = True  # Always True — read-only operator review aid
    observation_summary: ObservationSummarySchema = Field(default_factory=ObservationSummarySchema)
    decision_summary: DecisionSummarySchema = Field(default_factory=DecisionSummarySchema)
    decision_card: Optional[DecisionCard] = None
    review_volume: ReviewVolumeSchema = Field(default_factory=ReviewVolumeSchema)
    watch_volume: WatchVolumeSchema = Field(default_factory=WatchVolumeSchema)
    blockage_summary: BlockageSummarySchema = Field(default_factory=BlockageSummarySchema)
    retry_pressure: RetryPressureSchema = Field(default_factory=RetryPressureSchema)
    latency_observation: LatencyObservationSchema = Field(default_factory=LatencyObservationSchema)
    trend_observation: TrendObservationSchema = Field(default_factory=TrendObservationSchema)
    total_guard_checks: int = 25  # SSOT: 10+4+5+6
    seal_chain_complete: bool = True
    generated_at: str = ""
