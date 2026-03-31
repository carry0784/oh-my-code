"""
B-07 Evidence Persistence Tests — 7 tests

Validates:
  - append-only contract
  - read-after-write
  - restart recovery (SQLite)
  - failure transparency
  - audit key presence
  - no update/delete API
  - clear() production protection
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

from kdexter.audit.evidence_store import DuplicateEvidenceError, EvidenceBundle, EvidenceStore
from kdexter.audit.backends.memory import InMemoryBackend
from kdexter.audit.backends.sqlite import SQLiteBackend
from kdexter.audit.backends import EvidenceBackend


# ─────────────────────────────────────────────────────────────────────────── #
# Helpers
# ─────────────────────────────────────────────────────────────────────────── #

def _make_bundle(**kw) -> EvidenceBundle:
    defaults = dict(
        trigger="GovernanceGate.pre_check",
        actor="GovernanceGate",
        action="PRE_CHECK:ALLOWED",
        before_state="NORMAL",
        after_state="NORMAL",
        artifacts=[{
            "phase": "PRE",
            "gate_id": "test-gate-id-001",
            "gate_generation": 1,
            "gate_created_at": datetime.now(timezone.utc).isoformat(),
        }],
    )
    defaults.update(kw)
    return EvidenceBundle(**defaults)


# ═══════════════════════════════════════════════════════════════════════════ #
# B-07: EVIDENCE PERSISTENCE TESTS
# ═══════════════════════════════════════════════════════════════════════════ #

class TestEvidencePersistence:
    """B-07: EvidenceStore append-only, durability, and audit verification."""

    def test_evidence_persisted_and_readable(self):
        """Store a bundle, then read it back — read-after-write verification."""
        store = EvidenceStore()  # InMemoryBackend
        bundle = _make_bundle()
        bid = store.store(bundle)

        retrieved = store.get(bid)
        assert retrieved is not None
        assert retrieved.bundle_id == bid
        assert retrieved.trigger == "GovernanceGate.pre_check"
        assert retrieved.actor == "GovernanceGate"
        assert retrieved.before_state == "NORMAL"

    def test_evidence_append_only_no_overwrite(self):
        """Duplicate bundle_id raises DuplicateEvidenceError; original is preserved."""
        store = EvidenceStore()
        b1 = _make_bundle(bundle_id="FIXED-ID-001", action="ORIGINAL")
        store.store(b1)

        b2 = _make_bundle(bundle_id="FIXED-ID-001", action="OVERWRITE_ATTEMPT")
        with pytest.raises(DuplicateEvidenceError):
            store.store(b2)

        # Original must be preserved
        got = store.get("FIXED-ID-001")
        assert got.action == "ORIGINAL"
        assert store.count() == 1

    def test_evidence_restart_recovery(self):
        """SQLiteBackend: close and reopen, evidence survives (PERSISTED)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            # Write phase
            backend1 = SQLiteBackend(db_path)
            bundle = _make_bundle(bundle_id="PERSIST-B07-001")
            backend1.store(bundle)
            assert backend1.count() == 1
            backend1.close()

            # Reopen phase (simulates process restart)
            backend2 = SQLiteBackend(db_path)
            recovered = backend2.get("PERSIST-B07-001")
            assert recovered is not None
            assert recovered.trigger == "GovernanceGate.pre_check"
            assert recovered.actor == "GovernanceGate"
            assert backend2.count() == 1
            backend2.close()
        finally:
            os.unlink(db_path)
            for suffix in ("-wal", "-shm"):
                p = db_path + suffix
                if os.path.exists(p):
                    os.unlink(p)

    def test_evidence_write_failure_visible(self):
        """Backend write failure propagates to caller — no silent drop."""
        class FailingBackend(EvidenceBackend):
            def store(self, bundle): raise IOError("Disk full")
            def get(self, bid): return None
            def count(self): return 0
            def count_for_cycle(self, cid): return 0
            def count_by_actor(self, a): return 0
            def list_by_trigger(self, t): return []
            def list_by_actor(self, a): return []
            def list_by_actor_recent(self, a, limit=20): return []
            def list_all(self): return []
            def count_orphan_pre(self): return 0
            def clear(self): pass

        store = EvidenceStore(backend=FailingBackend())
        bundle = _make_bundle()

        with pytest.raises(IOError, match="Disk full"):
            store.store(bundle)

    def test_evidence_contains_audit_keys(self):
        """Evidence artifacts contain gate_id, timestamp, and bundle_id."""
        store = EvidenceStore()
        bundle = _make_bundle()
        bid = store.store(bundle)

        got = store.get(bid)
        assert got.bundle_id  # non-empty
        assert got.created_at is not None
        assert isinstance(got.created_at, datetime)

        # Artifact-level audit keys (gate_id from B-06)
        art = got.artifacts[0]
        assert "gate_id" in art
        assert "gate_generation" in art
        assert "gate_created_at" in art

    def test_no_update_delete_path(self):
        """EvidenceStore and backends have no update/delete/upsert API."""
        # EvidenceStore facade
        assert not hasattr(EvidenceStore, "update")
        assert not hasattr(EvidenceStore, "delete")
        assert not hasattr(EvidenceStore, "upsert")

        # InMemoryBackend
        assert not hasattr(InMemoryBackend, "update")
        assert not hasattr(InMemoryBackend, "delete")
        assert not hasattr(InMemoryBackend, "upsert")

        # SQLiteBackend
        assert not hasattr(SQLiteBackend, "update")
        assert not hasattr(SQLiteBackend, "delete")
        assert not hasattr(SQLiteBackend, "upsert")

        # EvidenceBackend ABC
        assert not hasattr(EvidenceBackend, "update")
        assert not hasattr(EvidenceBackend, "delete")
        assert not hasattr(EvidenceBackend, "upsert")

    def test_clear_blocked_in_production(self):
        """clear() raises RuntimeError when APP_ENV=production."""
        store = EvidenceStore()
        store.store(_make_bundle())

        with patch.dict("os.environ", {"APP_ENV": "production"}):
            with pytest.raises(RuntimeError, match="forbidden in production"):
                store.clear()

        # Verify evidence is still intact after blocked clear
        assert store.count() == 1
