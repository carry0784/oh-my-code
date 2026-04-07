"""Exchange factory per-task isolation tests.

Verifies that:
1. ExchangeFactory.create_fresh() always returns a new instance.
2. ExchangeFactory.reset() clears the singleton cache.
3. No Celery task file uses ExchangeFactory.create() (singleton) —
   all must use create_fresh() to prevent cross-asyncio.run() stale
   aiohttp session contamination.

Root cause: ccxt async client's aiohttp session binds to the event
loop active at construction time.  Celery solo-pool workers call
asyncio.run() per task, creating a new loop each time.  A cached
singleton's session references the *previous* (now closed) loop,
causing "Event loop is closed" errors and worker hang.

Introduced after CR-046 SOL Stage B worker hang (2026-04-07).
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
from unittest.mock import patch, MagicMock

import pytest

from exchanges.factory import ExchangeFactory, _FACTORY_REGISTRY


class TestCreateFresh:
    """create_fresh() must always return a distinct, uncached instance."""

    def test_create_fresh_returns_new_instance_each_call(self):
        """Two consecutive create_fresh() calls must return different objects."""
        mock_cls = MagicMock(side_effect=[MagicMock(), MagicMock()])
        with patch.dict(_FACTORY_REGISTRY, {"binance": mock_cls}):
            a = ExchangeFactory.create_fresh("binance")
            b = ExchangeFactory.create_fresh("binance")
            assert a is not b, "create_fresh must not return cached instance"
            assert mock_cls.call_count == 2

    def test_create_fresh_does_not_pollute_singleton_cache(self):
        """create_fresh() must not add to _instances."""
        original = dict(ExchangeFactory._instances)
        try:
            mock_cls = MagicMock(return_value=MagicMock())
            with patch.dict(_FACTORY_REGISTRY, {"binance": mock_cls}):
                ExchangeFactory.create_fresh("binance")
                assert (
                    "binance" not in ExchangeFactory._instances
                    or ExchangeFactory._instances.get("binance") is original.get("binance")
                ), "create_fresh must not modify _instances cache"
        finally:
            ExchangeFactory._instances = original

    def test_create_fresh_raises_on_unsupported(self):
        """create_fresh() must raise ValueError for unknown exchange."""
        with pytest.raises(ValueError, match="Unsupported exchange"):
            ExchangeFactory.create_fresh("nonexistent_exchange")


class TestReset:
    """reset() must clear the singleton cache."""

    def test_reset_clears_cache(self):
        """After reset(), _instances must be empty."""
        original = dict(ExchangeFactory._instances)
        try:
            ExchangeFactory._instances["test_exchange"] = MagicMock()
            ExchangeFactory.reset()
            assert len(ExchangeFactory._instances) == 0
        finally:
            ExchangeFactory._instances = original


class TestNoSingletonInCeleryTasks:
    """Blanket AST guard: no Celery task file may use ExchangeFactory.create()
    (the caching singleton).  All must use create_fresh()."""

    @staticmethod
    def _all_task_sources():
        """Yield (module_name, source_code) for every workers.tasks.* module."""
        import workers.tasks as pkg

        for _importer, mod_name, _is_pkg in pkgutil.walk_packages(
            pkg.__path__, prefix="workers.tasks."
        ):
            try:
                mod = importlib.import_module(mod_name)
                source_path = getattr(mod, "__file__", None)
                if source_path and source_path.endswith(".py"):
                    with open(source_path, "r", encoding="utf-8") as f:
                        yield mod_name, f.read()
            except Exception:
                continue

    def test_no_singleton_create_in_task_files(self):
        """No workers.tasks.* module should call ExchangeFactory.create()
        (the singleton method).  Only create_fresh() is allowed."""
        violations = []
        for mod_name, source in self._all_task_sources():
            tree = ast.parse(source)
            for node in ast.walk(tree):
                # Match: ExchangeFactory.create(...)
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "create"
                    and isinstance(node.func.value, ast.Attribute)
                    and node.func.value.attr == "ExchangeFactory"
                ):
                    violations.append(mod_name)
                    break  # one per module
                # Also match: ExchangeFactory.create(...) via Name
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "create"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "ExchangeFactory"
                ):
                    violations.append(mod_name)
                    break

        assert not violations, (
            f"ExchangeFactory.create() (singleton) found in: {violations}. "
            "Use ExchangeFactory.create_fresh() in Celery tasks to prevent "
            "stale aiohttp session from closed event loop."
        )
