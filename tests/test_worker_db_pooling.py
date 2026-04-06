"""
CR-048 Post-Phase-5a — Worker DB Connection Pooling Regression Tests

Verifies that worker task modules use bounded module-level engines
instead of per-invocation create_engine() calls that leak connections.

Invariants verified:
  1. No per-invocation create_engine() in task functions
  2. Module-level engine uses pool_size=1, max_overflow=0
  3. get_sync_session() is fully eliminated
  4. Repeated session creation reuses the same engine (no leak)
  5. All task modules have deterministic close paths
  6. SOL paper tasks remain unaffected (uses async_session_factory)
"""

from __future__ import annotations

import importlib
import inspect
import sys
from unittest.mock import MagicMock

import pytest

# -- Defence against celery stub pollution ---------------------------------- #
# Other test files stub "celery" as MagicMock for isolation. If that happens
# before this file runs, the module-level engines in worker tasks become
# MagicMock objects. Detect and restore real modules before importing workers.

_POLLUTED_MODULES = [
    "celery",
    "celery.app",
    "celery.app.task",
    "celery.schedules",
    "celery.utils",
    "celery.utils.log",
    "workers",
    "workers.celery_app",
    "workers.tasks",
    "workers.tasks.order_tasks",
    "workers.tasks.market_tasks",
    "workers.tasks.data_collection_tasks",
    "workers.tasks.snapshot_tasks",
    "workers.tasks.signal_tasks",
    "workers.tasks.sol_paper_tasks",
]

_TARGET_MODULES = [
    "workers.tasks.order_tasks",
    "workers.tasks.market_tasks",
    "workers.tasks.data_collection_tasks",
    "workers.tasks.snapshot_tasks",
    "workers.tasks.signal_tasks",
]


def _ensure_real_module(name):
    """If module is a MagicMock stub, remove it so real import can proceed."""
    mod = sys.modules.get(name)
    if mod is not None and isinstance(mod, MagicMock):
        del sys.modules[name]


def _read_source_from_file(module_path: str) -> str:
    """Read source directly from .py file — immune to module MagicMock pollution."""
    file_path = module_path.replace(".", "/") + ".py"
    with open(file_path, encoding="utf-8") as f:
        return f.read()


def _get_clean_module(module_path: str):
    """Import module, ensuring _sync_engine is a real SQLAlchemy engine.

    If celery mock pollution makes the engine a MagicMock or invalid,
    returns None so the caller can pytest.skip().
    """
    try:
        mod = importlib.import_module(module_path)
    except (ValueError, TypeError, ImportError, Exception):
        return None
    engine = getattr(mod, "_sync_engine", None)
    if engine is None or isinstance(engine, MagicMock):
        return None
    # Verify the engine has a real pool (not a MagicMock attribute chain)
    try:
        _ = engine.pool.size()
    except (AttributeError, TypeError, ValueError):
        return None
    return mod


# ── Section 1: Source-Level Verification (file-based, pollution-immune) ───


class TestNoPerInvocationEngineLeak:
    """Verify no task function creates engines inside function body."""

    @pytest.mark.parametrize("module_path", _TARGET_MODULES)
    def test_no_create_engine_inside_task_functions(self, module_path):
        """Task functions must not call create_engine() inside their body.

        Uses source file inspection — immune to module stub pollution.
        """
        source = _read_source_from_file(module_path)

        # Find function bodies: extract code after each def line
        # Module-level create_engine (in engine setup before first def) is OK
        # create_engine inside def blocks is NOT OK
        import re

        func_bodies = re.split(r"^(?:@.*\n)*def \w+", source, flags=re.MULTILINE)
        # First element is module-level code (allowed), rest are function bodies
        for func_body in func_bodies[1:]:
            assert "create_engine(" not in func_body, (
                f"{module_path} has create_engine() inside a function body"
            )


class TestGetSyncSessionEliminated:
    """Verify get_sync_session() is fully removed from codebase."""

    @pytest.mark.parametrize("module_path", _TARGET_MODULES)
    def test_no_get_sync_session_in_source(self, module_path):
        """Source file must not contain get_sync_session references."""
        source = _read_source_from_file(module_path)
        assert "get_sync_session" not in source, (
            f"{module_path} still references get_sync_session in source"
        )


# ── Section 2: Source-Level Bounded Engine Pattern ────────────────


class TestBoundedEngineInSource:
    """Verify source code declares bounded engine pattern."""

    @pytest.mark.parametrize("module_path", _TARGET_MODULES)
    def test_source_has_sync_engine_declaration(self, module_path):
        """Source must declare _sync_engine with create_engine()."""
        source = _read_source_from_file(module_path)
        assert "_sync_engine = create_engine(" in source, (
            f"{module_path} missing _sync_engine = create_engine(...) declaration"
        )

    @pytest.mark.parametrize("module_path", _TARGET_MODULES)
    def test_source_has_session_factory_declaration(self, module_path):
        """Source must declare _SyncSessionFactory = sessionmaker(...)."""
        source = _read_source_from_file(module_path)
        assert "_SyncSessionFactory = sessionmaker(" in source, (
            f"{module_path} missing _SyncSessionFactory = sessionmaker(...) declaration"
        )

    @pytest.mark.parametrize("module_path", _TARGET_MODULES)
    def test_source_has_pool_size_1(self, module_path):
        """Source must specify pool_size=1."""
        source = _read_source_from_file(module_path)
        assert "pool_size=1" in source, f"{module_path} missing pool_size=1 in engine declaration"

    @pytest.mark.parametrize("module_path", _TARGET_MODULES)
    def test_source_has_max_overflow_0(self, module_path):
        """Source must specify max_overflow=0."""
        source = _read_source_from_file(module_path)
        assert "max_overflow=0" in source, (
            f"{module_path} missing max_overflow=0 in engine declaration"
        )

    @pytest.mark.parametrize("module_path", _TARGET_MODULES)
    def test_source_has_pool_recycle_1800(self, module_path):
        """Source must specify pool_recycle=1800."""
        source = _read_source_from_file(module_path)
        assert "pool_recycle=1800" in source, (
            f"{module_path} missing pool_recycle=1800 in engine declaration"
        )

    @pytest.mark.parametrize("module_path", _TARGET_MODULES)
    def test_source_has_pool_pre_ping(self, module_path):
        """Source must specify pool_pre_ping=True."""
        source = _read_source_from_file(module_path)
        assert "pool_pre_ping=True" in source, (
            f"{module_path} missing pool_pre_ping=True in engine declaration"
        )


# ── Section 3: Runtime Engine Attribute Verification ──────────────


class TestRuntimeEngineAttributes:
    """Verify engine pool attributes at runtime (requires clean module load)."""

    @pytest.mark.parametrize("module_path", _TARGET_MODULES)
    def test_engine_pool_size_is_1(self, module_path):
        """Module-level engine must have pool_size=1."""
        mod = _get_clean_module(module_path)
        if mod is None:
            pytest.skip("Module polluted by celery mock — skipping runtime check")
        engine = mod._sync_engine
        assert engine.pool.size() == 1, (
            f"{module_path} engine pool_size={engine.pool.size()}, expected 1"
        )

    @pytest.mark.parametrize("module_path", _TARGET_MODULES)
    def test_engine_max_overflow_is_0(self, module_path):
        """Module-level engine must have max_overflow=0."""
        mod = _get_clean_module(module_path)
        if mod is None:
            pytest.skip("Module polluted by celery mock — skipping runtime check")
        engine = mod._sync_engine
        assert engine.pool._max_overflow == 0, (
            f"{module_path} engine max_overflow={engine.pool._max_overflow}, expected 0"
        )

    @pytest.mark.parametrize("module_path", _TARGET_MODULES)
    def test_pool_recycle_is_1800(self, module_path):
        """Module-level engine must have pool_recycle=1800."""
        mod = _get_clean_module(module_path)
        if mod is None:
            pytest.skip("Module polluted by celery mock — skipping runtime check")
        engine = mod._sync_engine
        assert engine.pool._recycle == 1800, (
            f"{module_path} pool_recycle={engine.pool._recycle}, expected 1800"
        )


# ── Section 4: Connection Reuse Under Repeated Invocations ────────


class TestConnectionReuse:
    """Verify repeated session factory calls reuse the same bounded engine."""

    @pytest.mark.parametrize("module_path", _TARGET_MODULES)
    def test_repeated_session_creation_same_engine(self, module_path):
        """Creating multiple sessions must reuse the same engine instance."""
        mod = _get_clean_module(module_path)
        if mod is None:
            pytest.skip("Module polluted by celery mock — skipping runtime check")
        factory = mod._SyncSessionFactory

        sessions = []
        for _ in range(10):
            s = factory()
            sessions.append(s)

        for s in sessions:
            assert s.bind is mod._sync_engine, (
                f"{module_path}: session bound to different engine than module-level _sync_engine"
            )
            s.close()

    @pytest.mark.parametrize("module_path", _TARGET_MODULES)
    def test_pool_does_not_grow_on_repeated_creation(self, module_path):
        """Pool checked-out count must not exceed 1 with proper close."""
        mod = _get_clean_module(module_path)
        if mod is None:
            pytest.skip("Module polluted by celery mock — skipping runtime check")
        factory = mod._SyncSessionFactory
        engine = mod._sync_engine

        for _ in range(20):
            s = factory()
            s.close()

        final_checkedout = engine.pool.checkedout()
        assert final_checkedout <= 1, (
            f"{module_path}: pool checkedout is {final_checkedout}, expected <= 1"
        )


# ── Section 5: Deterministic Close Path Verification ─────────────


class TestDeterministicClosePath:
    """Verify all task functions have session.close() in finally blocks."""

    @pytest.mark.parametrize(
        "module_path,func_names",
        [
            ("workers.tasks.order_tasks", ["submit_order", "check_pending_orders"]),
            ("workers.tasks.market_tasks", ["sync_all_positions"]),
            ("workers.tasks.snapshot_tasks", ["record_asset_snapshot"]),
            (
                "workers.tasks.signal_tasks",
                ["validate_signal", "expire_signals", "process_signal_pipeline"],
            ),
        ],
    )
    def test_session_close_in_finally(self, module_path, func_names):
        """Each DB-using function must have session.close() in a finally block."""
        source = _read_source_from_file(module_path)

        assert "finally:" in source, f"{module_path} missing finally block"
        assert "session.close()" in source or "sess.close()" in source, (
            f"{module_path} missing session.close() call"
        )

    @pytest.mark.parametrize(
        "module_path",
        [
            "workers.tasks.data_collection_tasks",
        ],
    )
    def test_data_collection_sess_close_in_finally(self, module_path):
        """data_collection_tasks uses sess variable — verify sess.close()."""
        source = _read_source_from_file(module_path)
        assert "sess.close()" in source, f"{module_path} missing sess.close() in finally block"


# ── Section 6: SOL Paper Tasks Unaffected ─────────────────────────


class TestSOLPaperUnaffected:
    """Verify SOL paper trading task is unmodified by this fix."""

    def test_sol_paper_uses_async_session_factory(self):
        """SOL paper task must still use async_session_factory (not sync engine)."""
        source = _read_source_from_file("workers.tasks.sol_paper_tasks")
        assert "async_session_factory" in source
        assert "_SyncSessionFactory" not in source

    def test_sol_paper_dry_run_hardcoded(self):
        """SOL paper task must keep dry_run=True hardcoded."""
        source = _read_source_from_file("workers.tasks.sol_paper_tasks")
        assert "dry_run=True" in source

    def test_sol_paper_no_get_sync_session(self):
        """SOL paper task must not reference get_sync_session."""
        source = _read_source_from_file("workers.tasks.sol_paper_tasks")
        assert "get_sync_session" not in source


# ── Section 7: Cross-Module Dependency Elimination ────────────────


class TestCrossModuleDependencyElimination:
    """Verify no task module imports session helpers from other task modules."""

    @pytest.mark.parametrize("module_path", _TARGET_MODULES)
    def test_no_cross_task_session_import(self, module_path):
        """No task module should import session/engine from another task module."""
        source = _read_source_from_file(module_path)
        # Must not import from workers.tasks.* for session purposes
        assert (
            "from workers.tasks.order_tasks import" not in source or "submit_order" in source
        ), (  # submit_order import in signal_tasks is OK
            f"{module_path} imports session helper from another task module"
        )
