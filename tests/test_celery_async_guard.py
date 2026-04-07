"""Cross-task asyncio safety guard for all Celery task files.

Ensures no Celery task entry-point uses asyncio.get_event_loop() or
run_until_complete(), which cause closed-loop reuse and worker hang
in Celery solo-pool workers.

Introduced as part of CROSS_TASK_ASYNC_HOTFIX_AND_REBASE recovery
(CR-046 SOL Stage B emergency, 2026-04-07).
"""

from __future__ import annotations

import ast
import importlib
import pkgutil

import pytest


def _all_task_modules():
    """Yield (module_name, source_code) for every workers.tasks.* module."""
    import workers.tasks as pkg

    for importer, mod_name, is_pkg in pkgutil.walk_packages(pkg.__path__, prefix="workers.tasks."):
        try:
            mod = importlib.import_module(mod_name)
            source_path = getattr(mod, "__file__", None)
            if source_path and source_path.endswith(".py"):
                with open(source_path, "r", encoding="utf-8") as f:
                    yield mod_name, f.read()
        except Exception:
            # Skip modules that can't be imported in test env
            continue


class TestCeleryAsyncGuard:
    """Blanket guard: no Celery task file may use get_event_loop() or
    run_until_complete() as a sync→async entry point."""

    def test_no_get_event_loop_in_any_task_file(self):
        """No workers.tasks.* module should call asyncio.get_event_loop()."""
        violations = []
        for mod_name, source in _all_task_modules():
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and node.attr == "get_event_loop":
                    violations.append(mod_name)
                    break  # one per module is enough

        assert not violations, (
            f"asyncio.get_event_loop() found in: {violations}. "
            "Use asyncio.run() to prevent closed-loop reuse in solo-pool."
        )

    def test_no_run_until_complete_in_any_task_file(self):
        """No workers.tasks.* module should call loop.run_until_complete()."""
        violations = []
        for mod_name, source in _all_task_modules():
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and node.attr == "run_until_complete":
                    violations.append(mod_name)
                    break

        assert not violations, (
            f"run_until_complete() found in: {violations}. "
            "Use asyncio.run() to prevent closed-loop reuse in solo-pool."
        )
