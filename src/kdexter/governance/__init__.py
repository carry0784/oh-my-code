"""
kdexter.governance

Governance layer package containing:
- Doctrine: shared immutable principles (D-001~D-010+)
- B1 Constitutional layer (immutable rules, forbidden actions, LOCKDOWN)
- B2 Build Orchestration layer (pipeline assembly, change approval, layer attribution)
"""

from kdexter.governance.doctrine import (
    ChangeAuthority,
    DoctrineArticle,
    DoctrineRatificationError,
    DoctrineRegistry,
    DoctrineSeverity,
    DoctrineStatus,
    DoctrineViolation,
    GovernanceTier,
)
from kdexter.governance.b1_constitution import (
    B1Constitution,
    ConstitutionalInvariant,
    ConstitutionalViolationError,
)
from kdexter.governance.b2_orchestration import (
    ApprovalStatus,
    B2Orchestration,
    ChangeRequest,
    LayerAttribution,
    PipelineStage,
    PipelineValidationError,
)

__all__ = [
    # Doctrine
    "ChangeAuthority",
    "DoctrineArticle",
    "DoctrineRatificationError",
    "DoctrineRegistry",
    "DoctrineSeverity",
    "DoctrineStatus",
    "DoctrineViolation",
    "GovernanceTier",
    # B1
    "B1Constitution",
    "ConstitutionalInvariant",
    "ConstitutionalViolationError",
    # B2
    "ApprovalStatus",
    "B2Orchestration",
    "ChangeRequest",
    "LayerAttribution",
    "PipelineStage",
    "PipelineValidationError",
]
