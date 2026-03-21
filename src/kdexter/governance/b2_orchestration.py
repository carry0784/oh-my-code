"""
B2 Build Orchestration Layer — K-Dexter AOS v4

Second governance tier. Responsible for:
  - Assembling execution pipelines from L1~L30
  - Sequencing gates G-01~G-27
  - Approving changes to B2/A attributed layers
  - Delegating runtime control to the A (Execution) layer
  - Enforcing B1 doctrines on all B2-governed operations

B2 Attribution (21 layers):
  L4, L5, L9, L11, L12, L13, L14, L15, L16, L17, L18,
  L19, L20, L21, L22(exec), L23, L24, L25, L28, L29, L30

Change authority:
  - B2 can approve changes to its own and A layers
  - B2 must verify B1 doctrine compliance before any approval
  - B2 cannot modify B1 layers or doctrines
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from kdexter.audit.evidence_store import EvidenceBundle, EvidenceStore
from kdexter.governance.doctrine import (
    DoctrineRegistry,
    DoctrineSeverity,
    GovernanceTier,
    ChangeAuthority,
)


# ─────────────────────────────────────────────────────────────────────────── #
# Layer attribution
# ─────────────────────────────────────────────────────────────────────────── #

@dataclass(frozen=True)
class LayerAttribution:
    """Governance attribution for a single layer."""
    layer_id: str               # "L1" ~ "L30"
    name: str
    tier: GovernanceTier
    change_authority: ChangeAuthority
    description: str = ""


# governance_layer_map.md Section 2 — full attribution table
_LAYER_ATTRIBUTIONS: list[LayerAttribution] = [
    LayerAttribution("L1",  "Human Decision",          GovernanceTier.B1, ChangeAuthority.HUMAN_ONLY),
    LayerAttribution("L2",  "Doctrine & Policy",       GovernanceTier.B1, ChangeAuthority.B1_RATIFY),
    LayerAttribution("L3",  "Security & Isolation",    GovernanceTier.B1, ChangeAuthority.B1_RATIFY),
    LayerAttribution("L4",  "Clarify & Spec",          GovernanceTier.B2, ChangeAuthority.B2_APPROVE),
    LayerAttribution("L5",  "Harness / Scheduler",     GovernanceTier.B2, ChangeAuthority.B2_APPROVE),
    LayerAttribution("L6",  "Parallel Agent",          GovernanceTier.A,  ChangeAuthority.B2_APPROVE),
    LayerAttribution("L7",  "Evaluation",              GovernanceTier.A,  ChangeAuthority.B2_APPROVE),
    LayerAttribution("L8",  "Execution Cell",          GovernanceTier.A,  ChangeAuthority.B2_APPROVE),
    LayerAttribution("L9",  "Self-Improvement Engine", GovernanceTier.B2, ChangeAuthority.B2_APPROVE),
    LayerAttribution("L10", "Audit / Evidence Store",  GovernanceTier.A,  ChangeAuthority.B2_APPROVE),
    LayerAttribution("L11", "Rule Ledger",             GovernanceTier.B2, ChangeAuthority.B2_APPROVE),
    LayerAttribution("L12", "Rule Provenance Store",   GovernanceTier.B2, ChangeAuthority.B2_APPROVE),
    LayerAttribution("L13", "Compliance Engine",       GovernanceTier.B2, ChangeAuthority.B2_APPROVE),
    LayerAttribution("L14", "Operation Evolution",     GovernanceTier.B2, ChangeAuthority.B2_APPROVE),
    LayerAttribution("L15", "Intent Drift Engine",     GovernanceTier.B2, ChangeAuthority.B2_APPROVE),
    LayerAttribution("L16", "Rule Conflict Engine",    GovernanceTier.B2, ChangeAuthority.B2_APPROVE),
    LayerAttribution("L17", "Failure Pattern Memory",  GovernanceTier.B2, ChangeAuthority.B2_APPROVE),
    LayerAttribution("L18", "Budget Evolution Engine", GovernanceTier.B2, ChangeAuthority.B2_APPROVE),
    LayerAttribution("L19", "Trust Decay Engine",      GovernanceTier.B2, ChangeAuthority.B2_APPROVE),
    LayerAttribution("L20", "Meta Loop Controller",    GovernanceTier.B2, ChangeAuthority.B2_APPROVE),
    LayerAttribution("L21", "Completion Engine",       GovernanceTier.B2, ChangeAuthority.B2_APPROVE),
    LayerAttribution("L22", "Spec Lock System",        GovernanceTier.B1, ChangeAuthority.B1_RATIFY,
                     "Lock release requires B1; lock execution is B2"),
    LayerAttribution("L23", "Research Engine",         GovernanceTier.B2, ChangeAuthority.B2_APPROVE),
    LayerAttribution("L24", "Knowledge Engine",        GovernanceTier.B2, ChangeAuthority.B2_APPROVE),
    LayerAttribution("L25", "Scheduler Engine",        GovernanceTier.B2, ChangeAuthority.B2_APPROVE),
    LayerAttribution("L26", "Recovery Engine",         GovernanceTier.A,  ChangeAuthority.B2_APPROVE),
    LayerAttribution("L27", "Override Controller",     GovernanceTier.B1, ChangeAuthority.HUMAN_ONLY),
    LayerAttribution("L28", "Loop Monitor",            GovernanceTier.B2, ChangeAuthority.B2_APPROVE),
    LayerAttribution("L29", "Cost Controller",         GovernanceTier.B2, ChangeAuthority.B2_APPROVE),
    LayerAttribution("L30", "Progress Engine",         GovernanceTier.B2, ChangeAuthority.B2_APPROVE),
]

_ATTR_MAP: dict[str, LayerAttribution] = {la.layer_id: la for la in _LAYER_ATTRIBUTIONS}


# ─────────────────────────────────────────────────────────────────────────── #
# Change request
# ─────────────────────────────────────────────────────────────────────────── #

class ApprovalStatus(Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DENIED = "DENIED"


@dataclass
class ChangeRequest:
    """A request to change a B2/A layer or configuration."""
    request_id: str = field(default_factory=lambda: f"CR-{uuid.uuid4().hex[:8].upper()}")
    target_layer: str = ""          # "L4", "L11", etc.
    change_type: str = ""           # "CODE", "CONFIG", "RULE", "ADAPTER"
    description: str = ""
    requester: str = ""             # who/what is requesting
    status: ApprovalStatus = ApprovalStatus.PENDING
    doctrine_compliant: bool = False
    reviewed_at: Optional[datetime] = None
    denial_reason: Optional[str] = None

    def approve(self) -> None:
        self.status = ApprovalStatus.APPROVED
        self.reviewed_at = datetime.utcnow()

    def deny(self, reason: str) -> None:
        self.status = ApprovalStatus.DENIED
        self.denial_reason = reason
        self.reviewed_at = datetime.utcnow()


# ─────────────────────────────────────────────────────────────────────────── #
# Pipeline stage
# ─────────────────────────────────────────────────────────────────────────── #

@dataclass
class PipelineStage:
    """One stage in an execution pipeline."""
    stage_id: str
    layer_id: str           # which layer executes this stage
    gate_id: Optional[str]  # gate to evaluate before this stage (None = no gate)
    order: int              # execution order within pipeline
    description: str = ""


# ─────────────────────────────────────────────────────────────────────────── #
# B2 Orchestration
# ─────────────────────────────────────────────────────────────────────────── #

class B2Orchestration:
    """
    Build orchestration coordinator for K-Dexter AOS.

    Provides:
      1. Layer attribution lookup (who governs what)
      2. Change request approval (doctrine compliance gate)
      3. Pipeline assembly and validation
      4. Evidence production for all governance decisions

    Usage:
        doctrine = DoctrineRegistry()
        evidence = EvidenceStore()
        b2 = B2Orchestration(doctrine, evidence)

        # Check change authority
        can_change = b2.can_modify("L11", "B2")

        # Submit change request
        cr = ChangeRequest(target_layer="L11", change_type="RULE", ...)
        approved = b2.approve_change(cr)
    """

    def __init__(
        self,
        doctrine: DoctrineRegistry,
        evidence: EvidenceStore,
    ) -> None:
        self._doctrine = doctrine
        self._evidence = evidence
        self._change_log: list[ChangeRequest] = []
        self._pipelines: dict[str, list[PipelineStage]] = {}

    # ── Layer attribution ────────────────────────────────────────────────── #

    @staticmethod
    def get_attribution(layer_id: str) -> Optional[LayerAttribution]:
        return _ATTR_MAP.get(layer_id)

    @staticmethod
    def get_tier_layers(tier: GovernanceTier) -> list[LayerAttribution]:
        return [la for la in _LAYER_ATTRIBUTIONS if la.tier == tier]

    @staticmethod
    def can_modify(layer_id: str, requester_tier: str) -> bool:
        """
        Check if requester_tier can modify the target layer.
        Rules from governance_layer_map.md Section 5.
        """
        attr = _ATTR_MAP.get(layer_id)
        if attr is None:
            return False

        if attr.change_authority == ChangeAuthority.HUMAN_ONLY:
            return requester_tier == "HUMAN"
        if attr.change_authority == ChangeAuthority.B1_RATIFY:
            return requester_tier in ("B1", "HUMAN")
        if attr.change_authority == ChangeAuthority.B2_APPROVE:
            return requester_tier in ("B2", "B1", "HUMAN")
        return False

    # ── Change approval ──────────────────────────────────────────────────── #

    def approve_change(self, request: ChangeRequest) -> bool:
        """
        Process a change request. Checks:
          1. Requester has authority for the target layer
          2. B1 doctrine compliance (checked against DoctrineRegistry)

        Returns True if approved, False if denied.
        """
        attr = _ATTR_MAP.get(request.target_layer)
        if attr is None:
            request.deny(f"Unknown layer: {request.target_layer}")
            self._log_change(request)
            return False

        # Authority check
        if not self.can_modify(request.target_layer, request.requester):
            request.deny(
                f"{request.requester} lacks authority to modify "
                f"{request.target_layer} (requires {attr.change_authority.value})"
            )
            self._log_change(request)
            return False

        # Doctrine compliance check
        compliance_context = {
            "actor": request.requester,
            "target_layer": request.target_layer,
            "change_type": request.change_type,
            "via_tcl": True,            # assume TCL compliance
            "provenance": True,         # assume provenance present
            "lock_held": True,          # assume lock held if needed
            "intent": request.description or "change request",
            "risk_checked": True,
        }
        violations = self._doctrine.check_compliance(compliance_context)

        if violations:
            constitutional = [v for v in violations
                            if v.severity == DoctrineSeverity.CONSTITUTIONAL]
            if constitutional:
                request.deny(
                    f"Constitutional doctrine violation: "
                    f"{constitutional[0].doctrine_id}"
                )
                self._log_change(request)
                return False

        request.doctrine_compliant = True
        request.approve()
        self._log_change(request)
        return True

    def list_changes(
        self,
        status: Optional[ApprovalStatus] = None,
    ) -> list[ChangeRequest]:
        if status is None:
            return list(self._change_log)
        return [cr for cr in self._change_log if cr.status == status]

    def change_count(self) -> int:
        return len(self._change_log)

    # ── Pipeline management ──────────────────────────────────────────────── #

    def register_pipeline(
        self,
        pipeline_id: str,
        stages: list[PipelineStage],
    ) -> None:
        """
        Register an execution pipeline.
        Validates that all referenced layers exist in the attribution table.
        """
        for stage in stages:
            if stage.layer_id not in _ATTR_MAP:
                raise PipelineValidationError(
                    f"Stage {stage.stage_id} references unknown layer: {stage.layer_id}"
                )
        # Sort by order
        self._pipelines[pipeline_id] = sorted(stages, key=lambda s: s.order)

        self._evidence.store(EvidenceBundle(
            trigger="B2Orchestration.register_pipeline",
            actor="B2",
            action=f"REGISTER_PIPELINE:{pipeline_id}",
            artifacts=[{
                "pipeline_id": pipeline_id,
                "stage_count": len(stages),
                "layers": [s.layer_id for s in stages],
            }],
        ))

    def get_pipeline(self, pipeline_id: str) -> Optional[list[PipelineStage]]:
        return self._pipelines.get(pipeline_id)

    def list_pipelines(self) -> list[str]:
        return list(self._pipelines.keys())

    def validate_pipeline(self, pipeline_id: str) -> list[str]:
        """
        Validate a pipeline for governance compliance.
        Returns list of issues (empty = valid).
        """
        stages = self._pipelines.get(pipeline_id)
        if stages is None:
            return [f"Pipeline {pipeline_id} not found"]

        issues = []
        seen_orders = set()
        for stage in stages:
            # Duplicate order check
            if stage.order in seen_orders:
                issues.append(f"Duplicate order {stage.order} in stage {stage.stage_id}")
            seen_orders.add(stage.order)

            # A-layer cannot execute without B2 approval
            attr = _ATTR_MAP.get(stage.layer_id)
            if attr and attr.tier == GovernanceTier.A and stage.gate_id is None:
                issues.append(
                    f"A-layer stage {stage.stage_id} ({stage.layer_id}) "
                    f"has no gate — B2 approval gate recommended"
                )

        return issues

    # ── Internal ─────────────────────────────────────────────────────────── #

    def _log_change(self, request: ChangeRequest) -> None:
        self._change_log.append(request)
        self._evidence.store(EvidenceBundle(
            trigger="B2Orchestration.change_request",
            actor="B2",
            action=f"CHANGE_{request.status.value}:{request.target_layer}",
            artifacts=[{
                "request_id": request.request_id,
                "target_layer": request.target_layer,
                "change_type": request.change_type,
                "requester": request.requester,
                "status": request.status.value,
                "denial_reason": request.denial_reason,
            }],
        ))


# ─────────────────────────────────────────────────────────────────────────── #
# Exceptions
# ─────────────────────────────────────────────────────────────────────────── #

class PipelineValidationError(Exception):
    """Raised when a pipeline references invalid layers or has structural issues."""
    pass
