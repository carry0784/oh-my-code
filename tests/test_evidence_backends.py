"""
Evidence Backend Tests — InMemory + SQLite
K-Dexter AOS v4

Run: python -X utf8 tests/test_evidence_backends.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta

from kdexter.audit.evidence_store import DuplicateEvidenceError, EvidenceBundle, EvidenceStore
from kdexter.audit.backends.memory import InMemoryBackend
from kdexter.audit.backends.sqlite import SQLiteBackend


# ======================================================================== #
# Helpers
# ======================================================================== #

def _make_bundle(
    trigger="TEST", actor="tester", action="test_action",
    cycle_id="CYC-001", bundle_id=None, **kw
) -> EvidenceBundle:
    return EvidenceBundle(
        trigger=trigger, actor=actor, action=action,
        cycle_id=cycle_id,
        **({"bundle_id": bundle_id} if bundle_id else {}),
        **kw,
    )


def _run_backend_tests(backend, label, start_num):
    """Run the shared test suite against any backend. Returns (passed, failed_list)."""
    n = start_num
    passed = 0
    failed = []

    # [n] store and get
    try:
        b = _make_bundle()
        bid = backend.store(b)
        got = backend.get(bid)
        assert got is not None
        assert got.bundle_id == bid
        assert got.trigger == "TEST"
        assert got.actor == "tester"
        print(f"  [{n}] {label} store/get  OK")
        passed += 1
    except Exception as e:
        failed.append((f"{label} store/get", str(e)))
        print(f"  [{n}] FAILED: {label} store/get: {e}")
    n += 1

    # [n] get missing
    try:
        assert backend.get("nonexistent-id") is None
        print(f"  [{n}] {label} get missing  OK")
        passed += 1
    except Exception as e:
        failed.append((f"{label} get missing", str(e)))
        print(f"  [{n}] FAILED: {label} get missing: {e}")
    n += 1

    # [n] count
    try:
        backend.clear()
        assert backend.count() == 0
        backend.store(_make_bundle())
        backend.store(_make_bundle())
        assert backend.count() == 2
        print(f"  [{n}] {label} count  OK")
        passed += 1
    except Exception as e:
        failed.append((f"{label} count", str(e)))
        print(f"  [{n}] FAILED: {label} count: {e}")
    n += 1

    # [n] count_for_cycle
    try:
        backend.clear()
        backend.store(_make_bundle(cycle_id="A"))
        backend.store(_make_bundle(cycle_id="A"))
        backend.store(_make_bundle(cycle_id="B"))
        assert backend.count_for_cycle("A") == 2
        assert backend.count_for_cycle("B") == 1
        assert backend.count_for_cycle("C") == 0
        print(f"  [{n}] {label} count_for_cycle  OK")
        passed += 1
    except Exception as e:
        failed.append((f"{label} count_for_cycle", str(e)))
        print(f"  [{n}] FAILED: {label} count_for_cycle: {e}")
    n += 1

    # [n] count_by_actor
    try:
        backend.clear()
        backend.store(_make_bundle(actor="alice"))
        backend.store(_make_bundle(actor="alice"))
        backend.store(_make_bundle(actor="bob"))
        assert backend.count_by_actor("alice") == 2
        assert backend.count_by_actor("bob") == 1
        print(f"  [{n}] {label} count_by_actor  OK")
        passed += 1
    except Exception as e:
        failed.append((f"{label} count_by_actor", str(e)))
        print(f"  [{n}] FAILED: {label} count_by_actor: {e}")
    n += 1

    # [n] list_by_trigger
    try:
        backend.clear()
        backend.store(_make_bundle(trigger="GATE.EVAL"))
        backend.store(_make_bundle(trigger="GATE.CHECK"))
        backend.store(_make_bundle(trigger="TCL.EXEC"))
        result = backend.list_by_trigger("GATE")
        assert len(result) == 2
        print(f"  [{n}] {label} list_by_trigger  OK")
        passed += 1
    except Exception as e:
        failed.append((f"{label} list_by_trigger", str(e)))
        print(f"  [{n}] FAILED: {label} list_by_trigger: {e}")
    n += 1

    # [n] list_by_actor
    try:
        backend.clear()
        backend.store(_make_bundle(actor="MainLoop"))
        backend.store(_make_bundle(actor="MainLoop"))
        backend.store(_make_bundle(actor="Recovery"))
        result = backend.list_by_actor("MainLoop")
        assert len(result) == 2
        print(f"  [{n}] {label} list_by_actor  OK")
        passed += 1
    except Exception as e:
        failed.append((f"{label} list_by_actor", str(e)))
        print(f"  [{n}] FAILED: {label} list_by_actor: {e}")
    n += 1

    # [n] list_all ordered
    try:
        backend.clear()
        t1 = datetime(2025, 1, 1, 0, 0, 0)
        t2 = datetime(2025, 1, 1, 0, 0, 1)
        b1 = EvidenceBundle(trigger="second", created_at=t2)
        b2 = EvidenceBundle(trigger="first", created_at=t1)
        backend.store(b1)
        backend.store(b2)
        all_b = backend.list_all()
        assert len(all_b) == 2
        assert all_b[0].trigger == "first"
        assert all_b[1].trigger == "second"
        print(f"  [{n}] {label} list_all ordered  OK")
        passed += 1
    except Exception as e:
        failed.append((f"{label} list_all ordered", str(e)))
        print(f"  [{n}] FAILED: {label} list_all ordered: {e}")
    n += 1

    # [n] clear
    try:
        backend.clear()
        backend.store(_make_bundle())
        assert backend.count() == 1
        backend.clear()
        assert backend.count() == 0
        print(f"  [{n}] {label} clear  OK")
        passed += 1
    except Exception as e:
        failed.append((f"{label} clear", str(e)))
        print(f"  [{n}] FAILED: {label} clear: {e}")
    n += 1

    # [n] duplicate store rejected (append-only contract)
    try:
        backend.clear()
        b = _make_bundle(bundle_id="SAME-ID", action="v1")
        backend.store(b)
        b2 = _make_bundle(bundle_id="SAME-ID", action="v2")
        rejected = False
        try:
            backend.store(b2)
        except DuplicateEvidenceError:
            rejected = True
        assert rejected, "Duplicate bundle_id must raise DuplicateEvidenceError"
        assert backend.count() == 1
        got = backend.get("SAME-ID")
        assert got.action == "v1", "Original bundle must be preserved (append-only)"
        print(f"  [{n}] {label} duplicate store rejected  OK")
        passed += 1
    except Exception as e:
        failed.append((f"{label} duplicate store rejected", str(e)))
        print(f"  [{n}] FAILED: {label} duplicate store rejected: {e}")
    n += 1

    # [n] complex state serialization
    try:
        backend.clear()
        b = _make_bundle(
            before_state={"key": "value", "nested": [1, 2, 3]},
            after_state={"key": "new_value", "flag": True},
            artifacts=["artifact1", "artifact2"],
        )
        backend.store(b)
        got = backend.get(b.bundle_id)
        assert got.before_state["key"] == "value"
        assert got.after_state["flag"] is True
        assert len(got.artifacts) == 2
        print(f"  [{n}] {label} complex state  OK")
        passed += 1
    except Exception as e:
        failed.append((f"{label} complex state", str(e)))
        print(f"  [{n}] FAILED: {label} complex state: {e}")
    n += 1

    return passed, failed, n


# ======================================================================== #
# EvidenceStore facade tests
# ======================================================================== #

def test_evidence_store_default_backend():
    es = EvidenceStore()
    b = _make_bundle()
    es.store(b)
    assert es.count() == 1
    assert es.get(b.bundle_id) is not None
    print("  [23] EvidenceStore default (InMemory) backend  OK")


def test_evidence_store_sqlite_backend():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        backend = SQLiteBackend(db_path)
        es = EvidenceStore(backend=backend)
        b = _make_bundle()
        es.store(b)
        assert es.count() == 1
        assert es.get(b.bundle_id) is not None
        backend.close()
    finally:
        os.unlink(db_path)
        # Clean up WAL/SHM files
        for suffix in ("-wal", "-shm"):
            p = db_path + suffix
            if os.path.exists(p):
                os.unlink(p)
    print("  [24] EvidenceStore with SQLite backend  OK")


def test_sqlite_persistence_across_reopen():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        # Write
        backend1 = SQLiteBackend(db_path)
        b = _make_bundle(bundle_id="PERSIST-001")
        backend1.store(b)
        backend1.close()
        # Reopen
        backend2 = SQLiteBackend(db_path)
        got = backend2.get("PERSIST-001")
        assert got is not None
        assert got.trigger == "TEST"
        backend2.close()
    finally:
        os.unlink(db_path)
        for suffix in ("-wal", "-shm"):
            p = db_path + suffix
            if os.path.exists(p):
                os.unlink(p)
    print("  [25] SQLite persistence across reopen  OK")


# ======================================================================== #
# Runner
# ======================================================================== #

if __name__ == "__main__":
    print("\nEvidence Backend Tests (InMemory + SQLite)")
    print("=" * 60)

    total = 0
    passed = 0
    failed_tests = []

    # InMemory backend tests
    print("\n--- InMemoryBackend ---")
    mem = InMemoryBackend()
    p, f, _ = _run_backend_tests(mem, "Memory", 1)
    total += 11
    passed += p
    failed_tests.extend(f)

    # SQLite backend tests
    print("\n--- SQLiteBackend ---")
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = tf.name
    try:
        sq = SQLiteBackend(db_path)
        p, f, _ = _run_backend_tests(sq, "SQLite", 12)
        total += 11
        passed += p
        failed_tests.extend(f)
        sq.close()
    finally:
        os.unlink(db_path)
        for suffix in ("-wal", "-shm"):
            p2 = db_path + suffix
            if os.path.exists(p2):
                os.unlink(p2)

    # Facade tests
    print("\n--- EvidenceStore Facade ---")
    facade_tests = [
        test_evidence_store_default_backend,
        test_evidence_store_sqlite_backend,
        test_sqlite_persistence_across_reopen,
    ]
    for fn in facade_tests:
        total += 1
        try:
            fn()
            passed += 1
        except Exception as e:
            failed_tests.append((fn.__name__, str(e)))
            print(f"  FAILED: {fn.__name__}: {e}")

    print(f"\n{'=' * 60}")
    print(f"Results: {passed}/{total} passed")
    if failed_tests:
        print("FAILED:")
        for name, err in failed_tests:
            print(f"  - {name}: {err}")
        sys.exit(1)
    else:
        print("All tests PASSED")
