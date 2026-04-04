"""
C-04 Phase 7 — Manual Recovery / Simulation / Preview Schema

Manual only. Synchronous only. Chain-gated. Receipt + audit required.
No background / queue / worker / command bus / polling.
No automatic rollback / retry.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.manual_action_schema import ManualActionChainState


class RecoveryDecision(str, Enum):
    EXECUTED = "EXECUTED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class SimulationDecision(str, Enum):
    SIMULATED = "SIMULATED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class RecoveryReceipt(BaseModel):
    """Receipt for rollback/retry — created for every attempt."""

    receipt_id: str = Field(description="Unique recovery receipt ID")
    recovery_type: str = Field(description="rollback | retry")
    action_id: str = Field(description="Linked original action ID")
    operator_id: str = Field(description="Who initiated recovery")
    timestamp: str = Field(description="ISO 8601")
    decision: RecoveryDecision = Field(description="EXECUTED / REJECTED / FAILED")
    chain_state: ManualActionChainState = Field(default_factory=ManualActionChainState)
    block_code: str = Field(default="")
    reason: str = Field(default="")
    error_summary: str = Field(default="")
    original_receipt_id: str = Field(default="", description="Original execution receipt")
    audit_id: str = Field(default="")


class SimulationReceipt(BaseModel):
    """Receipt for simulation — read-only chain check, no mutation."""

    receipt_id: str = Field(description="Unique simulation receipt ID")
    operator_id: str = Field(description="Who initiated simulation")
    timestamp: str = Field(description="ISO 8601")
    decision: SimulationDecision = Field(description="SIMULATED / REJECTED / FAILED")
    chain_state: ManualActionChainState = Field(default_factory=ManualActionChainState)
    block_code: str = Field(default="")
    reason: str = Field(default="")
    simulation_note: str = Field(
        default="SIMULATED — not a guarantee. No state was changed.",
        description="Must always be present to prevent fake readiness interpretation",
    )
    audit_id: str = Field(default="")


class PreviewResult(BaseModel):
    """Preview — text-based action description, no computation."""

    operator_id: str = Field(default="")
    timestamp: str = Field(default="")
    action_summary: str = Field(default="No action to preview")
    chain_met: int = Field(default=0, description="Conditions met count (display only)")
    chain_total: int = Field(default=9)
    block_reason: str = Field(default="")
    preview_note: str = Field(
        default="Preview does not guarantee execution. Conditions may change.",
        description="Must always be present",
    )
