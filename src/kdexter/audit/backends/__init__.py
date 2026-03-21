"""
Evidence Backends — K-Dexter AOS v4

Abstract base class for evidence storage backends.
Implementations: InMemoryBackend (default), SQLiteBackend (persistent).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from kdexter.audit.evidence_store import EvidenceBundle


class EvidenceBackend(ABC):
    """Abstract backend for EvidenceStore."""

    @abstractmethod
    def store(self, bundle: EvidenceBundle) -> str: ...

    @abstractmethod
    def get(self, bundle_id: str) -> Optional[EvidenceBundle]: ...

    @abstractmethod
    def count(self) -> int: ...

    @abstractmethod
    def count_for_cycle(self, cycle_id: str) -> int: ...

    @abstractmethod
    def count_by_actor(self, actor: str) -> int: ...

    @abstractmethod
    def list_by_trigger(self, trigger: str) -> list[EvidenceBundle]: ...

    @abstractmethod
    def list_by_actor(self, actor: str) -> list[EvidenceBundle]: ...

    @abstractmethod
    def list_all(self) -> list[EvidenceBundle]: ...

    @abstractmethod
    def clear(self) -> None: ...
