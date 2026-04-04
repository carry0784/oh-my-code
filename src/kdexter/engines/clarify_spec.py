"""
Clarify & Spec Engine — L4
K-Dexter AOS v4

Responsible for generating Spec Twins: structured specifications
that define what a cycle should accomplish. The MainLoop references
the spec_twin_id at every stage.

B2 Orchestration layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class SpecStatus(Enum):
    DRAFT = "DRAFT"
    CLARIFIED = "CLARIFIED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass
class SpecTwin:
    spec_id: str
    intent: str
    objectives: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    status: SpecStatus = SpecStatus.DRAFT
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    clarified_at: Optional[datetime] = None


class ClarifySpecEngine:
    """
    L4 Clarify & Spec engine.

    Creates and manages Spec Twins that define cycle objectives.
    """

    def __init__(self) -> None:
        self._specs: dict[str, SpecTwin] = {}

    def create(
        self,
        spec_id: str,
        intent: str,
        objectives: Optional[list[str]] = None,
        constraints: Optional[list[str]] = None,
    ) -> SpecTwin:
        spec = SpecTwin(
            spec_id=spec_id,
            intent=intent,
            objectives=objectives or [],
            constraints=constraints or [],
        )
        self._specs[spec_id] = spec
        return spec

    def clarify(self, spec_id: str) -> bool:
        spec = self._specs.get(spec_id)
        if spec is None or spec.status != SpecStatus.DRAFT:
            return False
        spec.status = SpecStatus.CLARIFIED
        spec.clarified_at = datetime.now(timezone.utc)
        return True

    def approve(self, spec_id: str) -> bool:
        spec = self._specs.get(spec_id)
        if spec is None or spec.status != SpecStatus.CLARIFIED:
            return False
        spec.status = SpecStatus.APPROVED
        return True

    def get(self, spec_id: str) -> Optional[SpecTwin]:
        return self._specs.get(spec_id)

    def list_all(self) -> list[SpecTwin]:
        return list(self._specs.values())
