"""
Evidence Store — K-Dexter AOS v4

All executions must produce an EvidenceBundle.
No evidence = execution did not happen (audit completeness gate G-05).

EvidenceBundle: immutable record of a single action/transition.
EvidenceStore:  facade delegating to a pluggable backend.
  - backend=None → InMemoryBackend (default, backward-compatible)
  - backend=SQLiteBackend("path") → persistent SQLite storage

Append-only contract:
  - store() appends new bundles. Duplicate bundle_id raises DuplicateEvidenceError.
  - No update/delete/upsert API exists.
  - clear() is test-only and blocked in production.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from kdexter.audit.backends import EvidenceBackend


# ─────────────────────────────────────────────────────────────────────────── #
# Exceptions
# ─────────────────────────────────────────────────────────────────────────── #

class DuplicateEvidenceError(ValueError):
    """Raised when attempting to store a bundle with an existing bundle_id.

    Append-only contract: duplicate writes are forbidden.
    Callers must handle this explicitly — silent swallowing is not permitted.
    """
    pass


# ─────────────────────────────────────────────────────────────────────────── #
# Evidence Bundle (M-07)
# ─────────────────────────────────────────────────────────────────────────── #

@dataclass
class EvidenceBundle:
    """
    Immutable audit record for a single action.
    Must be attached to every state transition (M-07).
    """
    bundle_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    trigger: Optional[str] = None       # what caused this action
    actor: Optional[str] = None         # who performed the action
    action: Optional[str] = None        # what was done
    before_state: Optional[Any] = None
    after_state: Optional[Any] = None
    artifacts: list = field(default_factory=list)
    cycle_id: Optional[str] = None      # MainLoop cycle ID for grouping


# ─────────────────────────────────────────────────────────────────────────── #
# Evidence Store (facade)
# ─────────────────────────────────────────────────────────────────────────── #

class EvidenceStore:
    """
    Central evidence storage.
    Every state transition, gate evaluation, and TCL command execution
    must store an EvidenceBundle here (M-07).

    G-05 Audit Completeness Gate reads count() to verify coverage.

    Args:
        backend: pluggable storage backend. None → InMemoryBackend.
    """

    def __init__(self, backend: Optional[EvidenceBackend] = None) -> None:
        if backend is None:
            from kdexter.audit.backends.memory import InMemoryBackend
            backend = InMemoryBackend()
        self._backend = backend

    def store(self, bundle: EvidenceBundle) -> str:
        """Store an EvidenceBundle. Returns bundle_id."""
        return self._backend.store(bundle)

    def get(self, bundle_id: str) -> Optional[EvidenceBundle]:
        """Retrieve a single bundle by ID."""
        return self._backend.get(bundle_id)

    def count(self) -> int:
        """Total number of stored bundles. Used by G-05."""
        return self._backend.count()

    def count_for_cycle(self, cycle_id: str) -> int:
        """Count bundles belonging to a specific cycle."""
        return self._backend.count_for_cycle(cycle_id)

    def count_by_actor(self, actor: str) -> int:
        """Count bundles produced by a specific actor."""
        return self._backend.count_by_actor(actor)

    def list_by_trigger(self, trigger: str) -> list[EvidenceBundle]:
        """List bundles matching a trigger prefix."""
        return self._backend.list_by_trigger(trigger)

    def list_by_actor(self, actor: str) -> list[EvidenceBundle]:
        """List bundles produced by a specific actor."""
        return self._backend.list_by_actor(actor)

    def list_by_actor_recent(self, actor: str, limit: int = 20) -> list[EvidenceBundle]:
        """List most recent bundles by actor, bounded. CR-027."""
        return self._backend.list_by_actor_recent(actor, limit)

    def list_all(self) -> list[EvidenceBundle]:
        """Return all stored bundles, ordered by created_at."""
        return self._backend.list_all()

    def count_orphan_pre(self) -> int:
        """Count PRE-phase bundles not linked by POST/ERROR. CR-028."""
        return self._backend.count_orphan_pre()

    def clear(self) -> None:
        """Clear all stored bundles. Test-only — blocked in production."""
        env = os.environ.get("APP_ENV", "").lower()
        if env in ("production", "prod"):
            raise RuntimeError(
                "EvidenceStore.clear() is forbidden in production (APP_ENV=%s). "
                "Evidence is append-only and must not be erased." % env
            )
        self._backend.clear()
