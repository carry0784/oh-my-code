"""
In-Memory Evidence Backend — K-Dexter AOS v4

Default backend. Stores bundles in a dict. No persistence across restarts.
Used by all tests and as the default when no backend is specified.
"""
from __future__ import annotations

from typing import Optional

from kdexter.audit.backends import EvidenceBackend
from kdexter.audit.evidence_store import EvidenceBundle


class InMemoryBackend(EvidenceBackend):
    """Dict-based in-memory evidence storage."""

    def __init__(self) -> None:
        self._bundles: dict[str, EvidenceBundle] = {}

    def store(self, bundle: EvidenceBundle) -> str:
        self._bundles[bundle.bundle_id] = bundle
        return bundle.bundle_id

    def get(self, bundle_id: str) -> Optional[EvidenceBundle]:
        return self._bundles.get(bundle_id)

    def count(self) -> int:
        return len(self._bundles)

    def count_for_cycle(self, cycle_id: str) -> int:
        return sum(1 for b in self._bundles.values() if b.cycle_id == cycle_id)

    def count_by_actor(self, actor: str) -> int:
        return sum(1 for b in self._bundles.values() if b.actor == actor)

    def list_by_trigger(self, trigger: str) -> list[EvidenceBundle]:
        return [b for b in self._bundles.values()
                if b.trigger and b.trigger.startswith(trigger)]

    def list_by_actor(self, actor: str) -> list[EvidenceBundle]:
        return [b for b in self._bundles.values() if b.actor == actor]

    def list_all(self) -> list[EvidenceBundle]:
        return sorted(self._bundles.values(), key=lambda b: b.created_at)

    def clear(self) -> None:
        self._bundles.clear()
