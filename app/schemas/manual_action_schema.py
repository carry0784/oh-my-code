"""
C-04 Manual Action Schema — Phase 5 Bounded Execution

9-stage chain gating. Fail-closed. Synchronous only.
No background / queue / worker / command bus.
No rollback / retry / polling / dry-run / partial preview.
No optimistic enable / execution.
Receipt + audit on every attempt (success, rejection, failure).
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ManualActionStageStatus(str, Enum):
    """Individual chain stage status."""

    PASS = "PASS"
    BLOCKED = "BLOCKED"
    MISSING = "MISSING"
    ERROR = "ERROR"


class ManualActionDecision(str, Enum):
    """Execution attempt outcome."""

    EXECUTED = "EXECUTED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class ManualActionChainState(BaseModel):
    """9-stage chain state — read-only snapshot for validation."""

    pipeline: ManualActionStageStatus = ManualActionStageStatus.MISSING
    preflight: ManualActionStageStatus = ManualActionStageStatus.MISSING
    gate: ManualActionStageStatus = ManualActionStageStatus.MISSING
    approval: ManualActionStageStatus = ManualActionStageStatus.MISSING
    policy: ManualActionStageStatus = ManualActionStageStatus.MISSING
    risk: ManualActionStageStatus = ManualActionStageStatus.MISSING
    auth: ManualActionStageStatus = ManualActionStageStatus.MISSING
    scope: ManualActionStageStatus = ManualActionStageStatus.MISSING
    evidence: ManualActionStageStatus = ManualActionStageStatus.MISSING

    @property
    def all_pass(self) -> bool:
        """All 9 stages must be PASS. Fail-closed."""
        stages = [
            self.pipeline,
            self.preflight,
            self.gate,
            self.approval,
            self.policy,
            self.risk,
            self.auth,
            self.scope,
            self.evidence,
        ]
        return all(s == ManualActionStageStatus.PASS for s in stages)

    @property
    def first_blocked_stage(self) -> Optional[str]:
        """Return name of first non-PASS stage, or None if all pass."""
        for name in [
            "pipeline",
            "preflight",
            "gate",
            "approval",
            "policy",
            "risk",
            "auth",
            "scope",
            "evidence",
        ]:
            if getattr(self, name) != ManualActionStageStatus.PASS:
                return name
        return None

    @property
    def block_code(self) -> str:
        """Return the block code for the first failing stage."""
        STAGE_TO_BLOCK = {
            "pipeline": "PIPELINE_NOT_READY",
            "preflight": "PREFLIGHT_NOT_READY",
            "gate": "GATE_CLOSED",
            "approval": "APPROVAL_REQUIRED",
            "policy": "POLICY_BLOCKED",
            "risk": "RISK_NOT_OK",
            "auth": "AUTH_NOT_OK",
            "scope": "SCOPE_NOT_OK",
            "evidence": "EVIDENCE_MISSING",
        }
        stage = self.first_blocked_stage
        if stage:
            return STAGE_TO_BLOCK.get(stage, "MANUAL_ACTION_DISABLED")
        return "MANUAL_ACTION_DISABLED"


class ManualActionCommand(BaseModel):
    """Execution command — created only when chain validates."""

    action_id: str = Field(description="Unique execution attempt ID")
    operator_id: str = Field(description="Who triggered the action")
    timestamp: str = Field(description="ISO 8601 attempt timestamp")
    preflight_id: str = Field(default="", description="I-04 preflight ID")
    gate_id: str = Field(default="", description="I-05 gate snapshot ID")
    approval_id: str = Field(default="", description="I-06 approval ID")
    evidence_id: str = Field(default="", description="Evidence chain reference")
    policy_id: str = Field(default="", description="I-07 policy snapshot ID")
    chain_state: ManualActionChainState = Field(
        default_factory=ManualActionChainState,
        description="Snapshot of 9-stage chain at attempt time",
    )


class ManualActionReceipt(BaseModel):
    """Receipt — created for EVERY attempt (success, rejection, failure)."""

    receipt_id: str = Field(description="Unique receipt ID")
    action_id: str = Field(description="Linked action attempt ID")
    operator_id: str = Field(description="Who triggered")
    timestamp: str = Field(description="ISO 8601")
    decision: ManualActionDecision = Field(description="EXECUTED / REJECTED / FAILED")
    chain_state: ManualActionChainState = Field(
        default_factory=ManualActionChainState,
        description="Chain state snapshot at decision time",
    )
    block_code: str = Field(default="", description="Block code if rejected")
    reason: str = Field(default="", description="Rejection/failure reason")
    error_summary: str = Field(default="", description="Error details if failed")
    evidence_ids: dict = Field(
        default_factory=dict,
        description="All linked evidence IDs used",
    )
    audit_id: str = Field(default="", description="Linked audit record ID")
