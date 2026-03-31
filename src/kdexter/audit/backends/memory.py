"""
In-Memory Evidence Backend — K-Dexter AOS v4

Default backend. Stores bundles in a dict. No persistence across restarts.
Used by all tests and as the default when no backend is specified.

Append-only: duplicate bundle_id raises DuplicateEvidenceError.
NOT_DURABLE: evidence is lost on process restart.
"""
from __future__ import annotations

from typing import Optional

from kdexter.audit.backends import EvidenceBackend
from kdexter.audit.evidence_store import DuplicateEvidenceError, EvidenceBundle


class InMemoryBackend(EvidenceBackend):
    """Dict-based in-memory evidence storage. NOT_DURABLE."""

    def __init__(self) -> None:
        self._bundles: dict[str, EvidenceBundle] = {}

    def store(self, bundle: EvidenceBundle) -> str:
        if bundle.bundle_id in self._bundles:
            raise DuplicateEvidenceError(
                f"Append-only violation: bundle_id={bundle.bundle_id} already exists. "
                f"Evidence records are immutable."
            )
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

    def list_by_actor_recent(self, actor: str, limit: int = 20) -> list[EvidenceBundle]:
        """List most recent bundles by actor, bounded by limit. CR-027."""
        matches = sorted(
            (b for b in self._bundles.values() if b.actor == actor),
            key=lambda b: b.created_at,
            reverse=True,
        )
        return list(reversed(matches[:limit]))

    def list_all(self) -> list[EvidenceBundle]:
        return sorted(self._bundles.values(), key=lambda b: b.created_at)

    def count_orphan_pre(self) -> int:
        """Count PRE-phase bundles not linked by POST/ERROR. CR-028."""
        pre_ids: set[str] = set()
        linked: set[str] = set()
        for b in self._bundles.values():
            artifacts = b.artifacts if hasattr(b, "artifacts") else []
            for art in artifacts:
                phase = art.get("phase", "") if isinstance(art, dict) else getattr(art, "phase", "")
                if phase == "PRE":
                    pre_ids.add(b.bundle_id if hasattr(b, "bundle_id") else "")
                elif phase in ("POST", "ERROR"):
                    lid = art.get("pre_evidence_id", "") if isinstance(art, dict) else getattr(art, "pre_evidence_id", "")
                    if lid:
                        linked.add(lid)
        return len(pre_ids - linked)

    def clear(self) -> None:
        self._bundles.clear()
