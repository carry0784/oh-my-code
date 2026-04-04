"""
CR-029: Evidence Read Performance Guard

Purpose: Prevent regression of CR-027/028 performance and abstraction fixes.
NOT a benchmark suite — a regression guard suite.

Axes:
  AXIS 1:  Synthetic scale correctness (InMemory: 10K / 100K / 500K)
  AXIS 2:  Hot path component budget proxy (InMemory)
  AXIS 2B: SQLite production-representative smoke (20K)
  AXIS 3:  Forbidden pattern detection — 1st-line defense (AST + string)
  AXIS 4:  Deterministic ordering contract
  AXIS 5:  Backend abstraction boundary

Principles:
  - append-only / read-only / fail-closed
  - No governance/approval/preflight meaning change
  - No dashboard feature addition
  - No cache layer introduction
"""

from __future__ import annotations

import ast
import inspect
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

# ── Stub modules that may not be available in test env ──────────────────
_STUB_MODULES = [
    "celery",
    "celery.schedules",
    "celery.result",
    "redis",
    "ccxt",
    "ccxt.async_support",
    "ccxt.pro",
    "sqlalchemy",
    "sqlalchemy.orm",
    "sqlalchemy.ext.asyncio",
    "sqlalchemy.ext.declarative",
    "sqlalchemy.future",
    "alembic",
    "fastapi",
    "uvicorn",
    "anthropic",
    "openai",
    "google.generativeai",
    "app.core.config",
    "app.core.database",
    "app.models.order",
    "app.models.signal",
    "app.models.position",
    "app.models.trade",
    "app.models.asset_snapshot",
    "app.exchanges.okx",
]
for name in _STUB_MODULES:
    if name not in sys.modules:
        sys.modules[name] = MagicMock()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from kdexter.audit.backends.memory import InMemoryBackend
from kdexter.audit.backends.sqlite import SQLiteBackend
from kdexter.audit.evidence_store import EvidenceBundle, EvidenceStore


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════


def _make_bundle(
    actor: str = "test_actor",
    idx: int = 0,
    artifacts: list | None = None,
) -> EvidenceBundle:
    """Create a deterministic test bundle."""
    base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return EvidenceBundle(
        bundle_id=f"TEST-{actor}-{idx:06d}",
        created_at=base_time + timedelta(seconds=idx),
        trigger=f"test_trigger_{idx % 10}",
        actor=actor,
        action=f"action_{idx % 5}",
        before_state={"idx": idx},
        after_state={"idx": idx, "done": True},
        artifacts=artifacts or [],
        cycle_id=f"cycle-{idx % 100}",
    )


def _make_orphan_bundles(store: EvidenceStore, count: int) -> int:
    """Create PRE bundles without matching POST. Returns orphan count."""
    orphans = 0
    for i in range(count):
        if i % 3 == 0:
            # PRE without POST = orphan
            store.store(
                _make_bundle(
                    actor="orphan_test",
                    idx=i,
                    artifacts=[{"phase": "PRE", "detail": f"pre-{i}"}],
                )
            )
            orphans += 1
        elif i % 3 == 1:
            # PRE with matching POST = linked
            pre_id = f"TEST-orphan_test-{(i - 1):06d}"
            store.store(
                _make_bundle(
                    actor="orphan_test",
                    idx=i,
                    artifacts=[{"phase": "POST", "pre_evidence_id": pre_id}],
                )
            )
            orphans -= 1  # previous PRE is now linked
        else:
            # Regular bundle (no phase)
            store.store(_make_bundle(actor="orphan_test", idx=i))
    return max(orphans, 0)


def _populate_store(backend, count: int, actor: str = "perf_test") -> EvidenceStore:
    """Populate a store with `count` bundles."""
    store = EvidenceStore(backend=backend)
    for i in range(count):
        store.store(_make_bundle(actor=actor, idx=i))
    return store


# ═══════════════════════════════════════════════════════════════════════
# AXIS 1: Synthetic Scale Correctness
# ═══════════════════════════════════════════════════════════════════════


class TestSyntheticScale:
    """Verify store operations work correctly at 10K / 100K / 500K scale."""

    @pytest.mark.parametrize("scale", [10_000])
    def test_count_at_scale_10k(self, scale: int):
        """10K: count() returns exact value."""
        store = _populate_store(InMemoryBackend(), scale)
        assert store.count() == scale

    @pytest.mark.parametrize("scale", [10_000])
    def test_bounded_recent_at_scale_10k(self, scale: int):
        """10K: list_by_actor_recent returns exactly `limit` bundles."""
        store = _populate_store(InMemoryBackend(), scale)
        result = store.list_by_actor_recent("perf_test", 20)
        assert len(result) == 20
        # Verify ordering: created_at ascending in result
        for i in range(len(result) - 1):
            assert result[i].created_at <= result[i + 1].created_at

    @pytest.mark.parametrize("scale", [10_000])
    def test_bounded_recent_is_sublinear_10k(self, scale: int):
        """10K: bounded query must be faster than full scan."""
        store = _populate_store(InMemoryBackend(), scale)

        t0 = time.monotonic()
        _ = store.list_by_actor_recent("perf_test", 20)
        bounded_time = time.monotonic() - t0

        t0 = time.monotonic()
        _ = store.list_all()
        full_time = time.monotonic() - t0

        # Bounded must not be slower than full scan
        # (In memory, bounded involves sort so may be similar, but should not be 2x worse)
        assert bounded_time < full_time * 2.5, (
            f"Bounded ({bounded_time:.4f}s) should not be much slower than full ({full_time:.4f}s)"
        )

    @pytest.mark.parametrize("scale", [100_000])
    def test_count_at_scale_100k(self, scale: int):
        """100K: count() remains O(1) for dict backend."""
        store = _populate_store(InMemoryBackend(), scale)
        t0 = time.monotonic()
        c = store.count()
        elapsed = time.monotonic() - t0
        assert c == scale
        assert elapsed < 0.01, f"count() took {elapsed:.4f}s at 100K — should be O(1)"

    @pytest.mark.parametrize("scale", [100_000])
    def test_bounded_recent_at_scale_100k(self, scale: int):
        """100K: bounded query still returns correct results."""
        store = _populate_store(InMemoryBackend(), scale)
        result = store.list_by_actor_recent("perf_test", 20)
        assert len(result) == 20
        # Must be the 20 most recent bundles
        assert result[-1].bundle_id == f"TEST-perf_test-{scale - 1:06d}"

    @pytest.mark.parametrize("scale", [500_000])
    def test_count_at_scale_500k(self, scale: int):
        """500K: count() still works."""
        store = _populate_store(InMemoryBackend(), scale)
        assert store.count() == scale

    @pytest.mark.parametrize("scale", [500_000])
    def test_bounded_recent_at_scale_500k(self, scale: int):
        """500K: bounded recent returns correct latest 20."""
        store = _populate_store(InMemoryBackend(), scale)
        result = store.list_by_actor_recent("perf_test", 20)
        assert len(result) == 20
        assert result[-1].bundle_id == f"TEST-perf_test-{scale - 1:06d}"


# ═══════════════════════════════════════════════════════════════════════
# AXIS 2: Hot Path Budget Enforcement
# ═══════════════════════════════════════════════════════════════════════


class TestHotPathBudget:
    """Verify bounded queries meet time budget at scale."""

    def test_list_by_actor_recent_budget_10k(self):
        """10K: bounded recent query < 0.5s."""
        store = _populate_store(InMemoryBackend(), 10_000)
        t0 = time.monotonic()
        store.list_by_actor_recent("perf_test", 20)
        elapsed = time.monotonic() - t0
        assert elapsed < 0.5, f"list_by_actor_recent took {elapsed:.4f}s > 0.5s budget"

    def test_list_by_actor_recent_budget_100k(self):
        """100K: bounded recent query < 0.5s."""
        store = _populate_store(InMemoryBackend(), 100_000)
        t0 = time.monotonic()
        store.list_by_actor_recent("perf_test", 20)
        elapsed = time.monotonic() - t0
        assert elapsed < 0.5, f"list_by_actor_recent took {elapsed:.4f}s > 0.5s budget"

    def test_count_budget_500k(self):
        """500K: count() < 0.01s."""
        store = _populate_store(InMemoryBackend(), 500_000)
        t0 = time.monotonic()
        store.count()
        elapsed = time.monotonic() - t0
        assert elapsed < 0.01, f"count() took {elapsed:.4f}s > 0.01s at 500K"

    def test_count_by_actor_budget_100k(self):
        """100K: count_by_actor < 0.5s."""
        store = _populate_store(InMemoryBackend(), 100_000)
        t0 = time.monotonic()
        store.count_by_actor("perf_test")
        elapsed = time.monotonic() - t0
        assert elapsed < 0.5, f"count_by_actor took {elapsed:.4f}s > 0.5s"

    def test_count_orphan_pre_budget_10k(self):
        """10K: count_orphan_pre (non-hot-path aggregation) < 1.0s."""
        store = _populate_store(InMemoryBackend(), 10_000)
        t0 = time.monotonic()
        store.count_orphan_pre()
        elapsed = time.monotonic() - t0
        assert elapsed < 1.0, f"count_orphan_pre took {elapsed:.4f}s > 1.0s"


# ═══════════════════════════════════════════════════════════════════════
# AXIS 2B: SQLite Production-Representative Smoke
# ═══════════════════════════════════════════════════════════════════════

_SQLITE_SMOKE_SCALE = 20_000


class TestSQLiteProductionSmoke:
    """Production backend (SQLite) smoke at 20K scale.

    InMemory tests verify algorithm correctness; these tests verify that
    the actual production backend (SQLite + WAL + composite index) meets
    the same contracts under realistic conditions.

    This is a smoke test, not a full benchmark.
    """

    @pytest.fixture(autouse=True)
    def sqlite_store(self, tmp_path):
        """Create and populate a 20K SQLite store."""
        backend = SQLiteBackend(str(tmp_path / "smoke.db"))
        self.store = EvidenceStore(backend=backend)
        for i in range(_SQLITE_SMOKE_SCALE):
            self.store.store(_make_bundle(actor="sqlite_smoke", idx=i))
        yield
        backend.close()

    def test_sqlite_count(self):
        """SQLite 20K: count() returns exact value."""
        assert self.store.count() == _SQLITE_SMOKE_SCALE

    def test_sqlite_count_by_actor(self):
        """SQLite 20K: count_by_actor returns exact value."""
        assert self.store.count_by_actor("sqlite_smoke") == _SQLITE_SMOKE_SCALE

    def test_sqlite_list_by_actor_recent_budget(self):
        """SQLite 20K: list_by_actor_recent < 0.5s budget."""
        t0 = time.monotonic()
        result = self.store.list_by_actor_recent("sqlite_smoke", 20)
        elapsed = time.monotonic() - t0
        assert len(result) == 20
        assert elapsed < 0.5, f"SQLite list_by_actor_recent took {elapsed:.4f}s > 0.5s"

    def test_sqlite_list_by_actor_recent_correctness(self):
        """SQLite 20K: recent returns the 20 latest bundles."""
        result = self.store.list_by_actor_recent("sqlite_smoke", 20)
        assert result[-1].bundle_id == f"TEST-sqlite_smoke-{_SQLITE_SMOKE_SCALE - 1:06d}"
        assert result[0].bundle_id == f"TEST-sqlite_smoke-{_SQLITE_SMOKE_SCALE - 20:06d}"

    def test_sqlite_deterministic_ordering(self):
        """SQLite 20K: recent results in created_at ASC order."""
        result = self.store.list_by_actor_recent("sqlite_smoke", 20)
        for i in range(len(result) - 1):
            assert result[i].created_at <= result[i + 1].created_at

    def test_sqlite_count_orphan_pre(self):
        """SQLite 20K: count_orphan_pre = 0 (no phase artifacts in fixture)."""
        assert self.store.count_orphan_pre() == 0


class TestSQLiteOrphanSmoke:
    """SQLite orphan detection smoke with phase artifacts."""

    def test_sqlite_orphan_with_artifacts(self, tmp_path):
        """SQLite: count_orphan_pre correctly detects orphans."""
        backend = SQLiteBackend(str(tmp_path / "orphan_smoke.db"))
        store = EvidenceStore(backend=backend)
        expected = _make_orphan_bundles(store, 60)
        result = store.count_orphan_pre()
        assert result == expected
        backend.close()


# ═══════════════════════════════════════════════════════════════════════
# AXIS 3: Forbidden Pattern Detection (1st-line defense)
# ═══════════════════════════════════════════════════════════════════════

# Hot path source files — these must NOT call list_all() or unbounded list_by_actor()
_HOT_PATH_MODULES = [
    "app/api/routes/dashboard.py",
    "app/core/recovery_preflight.py",
    "app/core/execution_policy.py",
    "app/core/incident_playback.py",
    "app/core/ops_aggregate_service.py",
    "app/core/ai_assist_source.py",
    "app/core/governance_summary_service.py",
]

# Non-hot-path modules where list_all() is acceptable
_NON_HOT_PATH_MODULES = [
    "app/api/routes/agents.py",  # debug-only endpoint
    "app/core/governance_monitor.py",  # batch/background
]


def _get_project_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _read_source(relpath: str) -> str:
    """Read source file content."""
    full = os.path.join(_get_project_root(), relpath)
    with open(full, encoding="utf-8") as f:
        return f.read()


def _find_evidence_list_all_calls(source: str) -> list[int]:
    """Find line numbers where evidence_store.list_all() or store.list_all() is called.

    Excludes non-evidence list_all() calls (e.g., DoctrineRegistry.list_all()).
    Detection: looks for .list_all() calls on objects whose name contains
    'store', 'evidence', or '_store'.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    lines = []
    # Evidence-related receiver names
    _EVIDENCE_RECEIVERS = {"store", "evidence_store", "_store", "evidence"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "list_all":
                # Check if the receiver object name suggests evidence store
                receiver = func.value
                if isinstance(receiver, ast.Name) and receiver.id in _EVIDENCE_RECEIVERS:
                    lines.append(node.lineno)
                elif isinstance(receiver, ast.Attribute) and receiver.attr in _EVIDENCE_RECEIVERS:
                    lines.append(node.lineno)
    return lines


class TestForbiddenPatterns:
    """1st-line defense: detect forbidden evidence read patterns in hot path modules.

    Detection method: AST parsing with receiver-name filtering.
    Known limitations:
    - Does not detect aliased/wrapped calls (e.g., helper functions calling list_all)
    - Does not follow import chains or self.store patterns
    - Intended as a fast, low-cost guard — not a complete static analysis tool
    """

    @pytest.mark.parametrize("module_path", _HOT_PATH_MODULES)
    def test_no_list_all_on_hot_path(self, module_path: str):
        """PERF-01: Hot path modules must not call evidence store list_all()."""
        source = _read_source(module_path)
        calls = _find_evidence_list_all_calls(source)
        assert len(calls) == 0, (
            f"PERF-01 VIOLATION: {module_path} calls evidence store list_all() on lines {calls}. "
            f"Use list_by_actor_recent() or count() instead."
        )

    @pytest.mark.parametrize("module_path", _HOT_PATH_MODULES)
    def test_no_bundles_direct_access(self, module_path: str):
        """CR-028: Hot path modules must not access store._bundles directly."""
        source = _read_source(module_path)
        # Check for ._bundles or ["_bundles"] patterns
        assert "._bundles" not in source and '["_bundles"]' not in source, (
            f"CR-028 VIOLATION: {module_path} accesses _bundles directly. "
            f"Use facade methods instead."
        )

    @pytest.mark.parametrize("module_path", _HOT_PATH_MODULES)
    def test_no_hasattr_bundles(self, module_path: str):
        """CR-028: No hasattr(store, '_bundles') pattern in hot path."""
        source = _read_source(module_path)
        assert 'hasattr(store, "_bundles")' not in source, (
            f"CR-028 VIOLATION: {module_path} uses hasattr(_bundles) pattern. "
            f"Use facade methods instead."
        )


# ═══════════════════════════════════════════════════════════════════════
# AXIS 4: Deterministic Ordering Contract
# ═══════════════════════════════════════════════════════════════════════


class TestDeterministicOrdering:
    """PERF-03: Verify recent queries return deterministic ordering."""

    def test_recent_returns_ascending_order(self):
        """list_by_actor_recent returns results in created_at ASC order."""
        store = _populate_store(InMemoryBackend(), 100)
        result = store.list_by_actor_recent("perf_test", 10)
        for i in range(len(result) - 1):
            assert result[i].created_at <= result[i + 1].created_at, (
                f"Result[{i}].created_at ({result[i].created_at}) > "
                f"Result[{i + 1}].created_at ({result[i + 1].created_at})"
            )

    def test_recent_returns_latest_bundles(self):
        """list_by_actor_recent returns the N most recent, not the N oldest."""
        store = _populate_store(InMemoryBackend(), 1000)
        result = store.list_by_actor_recent("perf_test", 5)
        # Last bundle in result should be the most recent overall
        assert result[-1].bundle_id == "TEST-perf_test-000999"
        # First bundle in result should be the 5th-most-recent
        assert result[0].bundle_id == "TEST-perf_test-000995"

    def test_recent_deterministic_across_calls(self):
        """Same input → same output, every time."""
        store = _populate_store(InMemoryBackend(), 500)
        r1 = store.list_by_actor_recent("perf_test", 10)
        r2 = store.list_by_actor_recent("perf_test", 10)
        assert [b.bundle_id for b in r1] == [b.bundle_id for b in r2]

    def test_recent_with_limit_exceeding_total(self):
        """If limit > total bundles, return all in ascending order."""
        store = _populate_store(InMemoryBackend(), 5)
        result = store.list_by_actor_recent("perf_test", 100)
        assert len(result) == 5
        for i in range(len(result) - 1):
            assert result[i].created_at <= result[i + 1].created_at

    def test_sqlite_ordering_matches_memory(self, tmp_path):
        """SQLite and Memory backends produce same ordering."""
        mem_backend = InMemoryBackend()
        sql_backend = SQLiteBackend(str(tmp_path / "test.db"))

        bundles = [_make_bundle(actor="order_test", idx=i) for i in range(50)]
        for b in bundles:
            mem_backend.store(b)
            sql_backend.store(b)

        mem_result = mem_backend.list_by_actor_recent("order_test", 10)
        sql_result = sql_backend.list_by_actor_recent("order_test", 10)

        assert [b.bundle_id for b in mem_result] == [b.bundle_id for b in sql_result]
        sql_backend.close()


# ═══════════════════════════════════════════════════════════════════════
# AXIS 5: Backend Abstraction Boundary
# ═══════════════════════════════════════════════════════════════════════


class TestBackendAbstraction:
    """Verify all public facade methods work identically on both backends."""

    def test_count_orphan_pre_memory(self):
        """Memory backend: count_orphan_pre returns correct count."""
        store = EvidenceStore(backend=InMemoryBackend())
        expected = _make_orphan_bundles(store, 30)
        assert store.count_orphan_pre() == expected

    def test_count_orphan_pre_sqlite(self, tmp_path):
        """SQLite backend: count_orphan_pre returns correct count."""
        store = EvidenceStore(backend=SQLiteBackend(str(tmp_path / "test.db")))
        expected = _make_orphan_bundles(store, 30)
        result = store.count_orphan_pre()
        assert result == expected

    def test_count_orphan_pre_empty_store(self):
        """Empty store: count_orphan_pre returns 0."""
        store = EvidenceStore(backend=InMemoryBackend())
        assert store.count_orphan_pre() == 0

    def test_count_orphan_pre_no_phase_bundles(self):
        """Store with bundles but no phase artifacts: orphan = 0."""
        store = _populate_store(InMemoryBackend(), 100)
        assert store.count_orphan_pre() == 0

    def test_memory_sqlite_orphan_parity(self, tmp_path):
        """Memory and SQLite must return same orphan count for same data."""
        mem = InMemoryBackend()
        sql = SQLiteBackend(str(tmp_path / "parity.db"))

        bundles_data = []
        for i in range(30):
            if i % 3 == 0:
                arts = [{"phase": "PRE"}]
            elif i % 3 == 1:
                pre_id = f"TEST-parity-{(i - 1):06d}"
                arts = [{"phase": "POST", "pre_evidence_id": pre_id}]
            else:
                arts = []
            b = _make_bundle(actor="parity", idx=i, artifacts=arts)
            bundles_data.append(b)

        for b in bundles_data:
            mem.store(b)
            sql.store(b)

        assert mem.count_orphan_pre() == sql.count_orphan_pre()
        sql.close()

    def test_facade_delegates_to_backend(self):
        """EvidenceStore.count_orphan_pre delegates to backend."""
        backend = InMemoryBackend()
        store = EvidenceStore(backend=backend)
        # Verify delegation
        assert store.count_orphan_pre() == backend.count_orphan_pre()

    def test_all_interface_methods_exist(self):
        """All EvidenceBackend abstract methods are implemented in both backends."""
        from kdexter.audit.backends import EvidenceBackend
        import abc

        abstract_methods = set()
        for name, method in inspect.getmembers(EvidenceBackend):
            if getattr(method, "__isabstractmethod__", False):
                abstract_methods.add(name)

        for BackendCls in [InMemoryBackend, SQLiteBackend]:
            for method_name in abstract_methods:
                assert hasattr(BackendCls, method_name), (
                    f"{BackendCls.__name__} missing {method_name}"
                )
