"""
Knowledge Engine -- L24 K-Dexter AOS

Purpose: store and retrieve structured knowledge entries at runtime.
Acts as a lightweight in-process knowledge base for other engines.

Governance: B2 (governance_layer_map.md -- L24)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# ------------------------------------------------------------------ #
# Data models
# ------------------------------------------------------------------ #

@dataclass
class KnowledgeEntry:
    """A single knowledge entry in the store."""
    key: str
    value: object
    source: str              # identifier of the component that stored this
    stored_at: datetime = field(default_factory=datetime.utcnow)
    access_count: int = 0


# ------------------------------------------------------------------ #
# L24 Knowledge Engine
# ------------------------------------------------------------------ #

class KnowledgeEngine:
    """
    L24 Knowledge Engine.

    Provides a simple dict-backed store for runtime knowledge entries.
    Entries are keyed by an arbitrary string and carry provenance (source)
    and access statistics.

    Usage:
        engine = KnowledgeEngine()
        engine.store("incident.root_cause", "network timeout", source="L23")
        entry = engine.retrieve("incident.root_cause")
        if entry:
            print(entry.value, entry.access_count)
    """

    def __init__(self) -> None:
        self._store: dict[str, KnowledgeEntry] = {}

    # ---------------------------------------------------------------- #
    # Mutation
    # ---------------------------------------------------------------- #

    def store(self, key: str, value: object, source: str = "") -> KnowledgeEntry:
        """
        Store a knowledge entry.

        Overwrites any existing entry with the same key, resetting
        stored_at and access_count.

        Args:
            key: lookup key
            value: arbitrary value to store
            source: identifier of the caller / origin component

        Returns:
            The stored KnowledgeEntry
        """
        entry = KnowledgeEntry(key=key, value=value, source=source)
        self._store[key] = entry
        return entry

    def delete(self, key: str) -> bool:
        """
        Remove a knowledge entry.

        Returns:
            True if the key existed and was removed, False otherwise
        """
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> None:
        """Remove all knowledge entries."""
        self._store.clear()

    # ---------------------------------------------------------------- #
    # Retrieval
    # ---------------------------------------------------------------- #

    def retrieve(self, key: str) -> Optional[KnowledgeEntry]:
        """
        Retrieve a knowledge entry by key.

        Increments access_count on each successful retrieval.

        Args:
            key: lookup key

        Returns:
            KnowledgeEntry if found, None otherwise
        """
        entry = self._store.get(key)
        if entry is not None:
            entry.access_count += 1
        return entry

    def keys(self) -> list[str]:
        """Return all stored keys."""
        return list(self._store.keys())

    def __len__(self) -> int:
        return len(self._store)
