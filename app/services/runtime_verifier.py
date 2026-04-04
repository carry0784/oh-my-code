"""
Runtime Verifier — enforces immutability of loaded bundles.

Responsibilities:
  1. Load-time verification: reject loading if bundle hash mismatches
  2. Periodic integrity check: detect runtime drift
  3. Drift event recording: log to minimal drift ledger
  4. SM-3 candidate emission: flag for Safe Mode consideration

This module does NOT implement the full Safe Mode state machine or
the full Recovery Ledger.  It emits minimal drift events that Phase 9
will consume.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from app.services.runtime_bundle import (
    BundleManifest,
    BundleType,
    DriftSeverity,
)

logger = logging.getLogger(__name__)


# ── Drift event types ────────────────────────────────────────────────


class DriftAction(str, Enum):
    REFUSE_LOAD = "refuse_load"
    QUARANTINE_CANDIDATE = "quarantine_candidate"
    RUNTIME_DRIFT_DETECTED = "runtime_drift_detected"


@dataclass
class DriftEvent:
    """Minimal drift event for ledger recording."""

    id: str = field(default_factory=lambda: str(uuid4()))
    bundle_type: BundleType = BundleType.STRATEGY
    expected_hash: str = ""
    observed_hash: str = ""
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    action: DriftAction = DriftAction.REFUSE_LOAD
    sm3_candidate: bool = True
    severity: DriftSeverity = DriftSeverity.HIGH
    canonical_snapshot: str | None = None  # canonical JSON for audit


# ── Runtime Bundle Store ─────────────────────────────────────────────


class RuntimeBundleStore:
    """In-memory store of verified bundle hashes.

    Each bundle is registered at load time with its expected hash.
    Subsequent checks compare against the registered hash.
    """

    def __init__(self) -> None:
        self._bundles: dict[str, BundleManifest] = {}
        self._drift_events: list[DriftEvent] = []

    # ── Registration ─────────────────────────────────────────────────

    def register(self, key: str, manifest: BundleManifest) -> None:
        """Register a verified bundle manifest.

        Called at load time after initial verification passes.
        """
        self._bundles[key] = manifest
        logger.info(
            "Bundle registered: key=%s type=%s hash=%s",
            key,
            manifest.bundle_type.value,
            manifest.hash[:16],
        )

    def is_registered(self, key: str) -> bool:
        return key in self._bundles

    def get_manifest(self, key: str) -> BundleManifest | None:
        return self._bundles.get(key)

    # ── Verification ─────────────────────────────────────────────────

    def verify_load(self, key: str, manifest: BundleManifest) -> DriftEvent | None:
        """Verify a bundle at load time.

        If the key is already registered, compare hashes.
        Returns None if OK, or a DriftEvent if mismatch.
        """
        existing = self._bundles.get(key)
        if existing is None:
            # First load — register and pass
            self.register(key, manifest)
            return None

        if existing.hash == manifest.hash:
            return None

        # Mismatch — refuse load
        event = DriftEvent(
            bundle_type=manifest.bundle_type,
            expected_hash=existing.hash,
            observed_hash=manifest.hash,
            action=DriftAction.REFUSE_LOAD,
            sm3_candidate=True,
            severity=manifest.severity,
            canonical_snapshot=manifest.canonical_json,
        )
        self._drift_events.append(event)
        logger.error(
            "LOAD REFUSED: key=%s type=%s expected=%s observed=%s",
            key,
            manifest.bundle_type.value,
            existing.hash[:16],
            manifest.hash[:16],
        )
        return event

    def verify_integrity(self, key: str, manifest: BundleManifest) -> DriftEvent | None:
        """Periodic integrity check.

        Compares current state against the registered hash.
        Returns None if OK, or a DriftEvent if drift detected.
        """
        existing = self._bundles.get(key)
        if existing is None:
            logger.warning("Integrity check skipped: key=%s not registered", key)
            return None

        if existing.hash == manifest.hash:
            return None

        event = DriftEvent(
            bundle_type=manifest.bundle_type,
            expected_hash=existing.hash,
            observed_hash=manifest.hash,
            action=DriftAction.RUNTIME_DRIFT_DETECTED,
            sm3_candidate=True,
            severity=manifest.severity,
            canonical_snapshot=manifest.canonical_json,
        )
        self._drift_events.append(event)
        logger.error(
            "RUNTIME DRIFT: key=%s type=%s expected=%s observed=%s",
            key,
            manifest.bundle_type.value,
            existing.hash[:16],
            manifest.hash[:16],
        )
        return event

    # ── Event access ─────────────────────────────────────────────────

    @property
    def drift_events(self) -> list[DriftEvent]:
        return list(self._drift_events)

    def clear_events(self) -> None:
        self._drift_events.clear()

    def count_recent_drifts(self, bundle_type: BundleType, within_hours: int = 24) -> int:
        """Count drift events for a bundle type within a time window.

        Used for Phase 9 escalation rules:
          - 2+ in 24H → HUMAN_APPROVAL_REQUIRED
          - 3+ in 7D → permanent BLOCKED
        """
        cutoff = datetime.now(timezone.utc).timestamp() - (within_hours * 3600)
        return sum(
            1
            for e in self._drift_events
            if e.bundle_type == bundle_type and e.detected_at.timestamp() > cutoff
        )

    # ── Bulk operations ──────────────────────────────────────────────

    def unregister(self, key: str) -> None:
        """Remove a bundle (e.g. on strategy retirement)."""
        self._bundles.pop(key, None)

    def registered_keys(self) -> list[str]:
        return list(self._bundles.keys())


# ── Module-level singleton ───────────────────────────────────────────

_store: RuntimeBundleStore | None = None


def get_bundle_store() -> RuntimeBundleStore:
    """Get or create the global RuntimeBundleStore singleton."""
    global _store
    if _store is None:
        _store = RuntimeBundleStore()
    return _store


def reset_bundle_store() -> None:
    """Reset the store (testing only)."""
    global _store
    _store = None
