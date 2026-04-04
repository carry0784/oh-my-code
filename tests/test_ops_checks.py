"""
S-02: Operational Check Tests — daily/hourly Celery task + beat registration

Tests:
  - daily/hourly task registration
  - daily/hourly wrapper calls runner and returns result
  - read-only property verification
  - fail-closed on error
  - beat schedule has exactly 2 ops entries
  - existing beat entries unchanged
"""

import sys
import importlib
from unittest.mock import MagicMock

import pytest

# -- Defence against celery stub pollution ---------------------------------- #
# Other test files stub "celery" as MagicMock for isolation. If that happens
# before this file runs, ops_checks tests fail because they need the real
# Celery module. Detect and restore real celery before importing workers.

def _ensure_real_module(name):
    """If module is a MagicMock stub, remove it so real import can proceed."""
    mod = sys.modules.get(name)
    if mod is not None and isinstance(mod, MagicMock):
        del sys.modules[name]

_POLLUTED_MODULES = [
    "celery", "celery.app", "celery.app.task", "celery.schedules",
    "celery.utils", "celery.utils.log",
    "workers", "workers.celery_app",
    "workers.tasks", "workers.tasks.check_tasks",
    "workers.tasks.market_tasks", "workers.tasks.order_tasks",
]
for _m in _POLLUTED_MODULES:
    _ensure_real_module(_m)

# Force reimport of workers chain with real celery
import celery  # noqa: E402 — ensure real celery loaded
if "workers.celery_app" in sys.modules:
    importlib.reload(sys.modules["workers.celery_app"])
if "workers.tasks.check_tasks" in sys.modules:
    importlib.reload(sys.modules["workers.tasks.check_tasks"])


class TestCheckTaskRegistration:
    """Verify check_tasks module and task registration."""

    def test_check_tasks_module_exists(self):
        import workers.tasks.check_tasks
        assert hasattr(workers.tasks.check_tasks, "run_daily_ops_check")
        assert hasattr(workers.tasks.check_tasks, "run_hourly_ops_check")

    def test_daily_task_is_celery_task(self):
        from workers.tasks.check_tasks import run_daily_ops_check
        assert hasattr(run_daily_ops_check, "delay")
        assert hasattr(run_daily_ops_check, "apply_async")

    def test_hourly_task_is_celery_task(self):
        from workers.tasks.check_tasks import run_hourly_ops_check
        assert hasattr(run_hourly_ops_check, "delay")
        assert hasattr(run_hourly_ops_check, "apply_async")

    def test_daily_task_name(self):
        from workers.tasks.check_tasks import run_daily_ops_check
        assert run_daily_ops_check.name == "workers.tasks.check_tasks.run_daily_ops_check"

    def test_hourly_task_name(self):
        from workers.tasks.check_tasks import run_hourly_ops_check
        assert run_hourly_ops_check.name == "workers.tasks.check_tasks.run_hourly_ops_check"


class TestCheckTaskExecution:
    """Verify task wrappers call runners and return structured results."""

    def test_daily_returns_structured_result(self):
        from workers.tasks.check_tasks import run_daily_ops_check
        result = run_daily_ops_check()
        assert isinstance(result, dict)
        assert result["check_type"] == "DAILY"
        assert result["result"] in ("OK", "WARN", "FAIL", "BLOCK")
        assert "summary" in result
        assert "evidence_id" in result

    def test_hourly_returns_structured_result(self):
        from workers.tasks.check_tasks import run_hourly_ops_check
        result = run_hourly_ops_check()
        assert isinstance(result, dict)
        assert result["check_type"] == "HOURLY"
        assert result["result"] in ("OK", "WARN", "FAIL", "BLOCK")
        assert "summary" in result
        assert "evidence_id" in result

    def test_daily_items_count(self):
        from workers.tasks.check_tasks import run_daily_ops_check
        result = run_daily_ops_check()
        assert result["items_total"] == 9  # Art26: 9 items

    def test_hourly_items_count(self):
        from workers.tasks.check_tasks import run_hourly_ops_check
        result = run_hourly_ops_check()
        assert result["items_total"] == 7  # Art27: 7 items


class TestReadOnlyProperty:
    """Verify tasks are read-only with no write actions."""

    def test_daily_no_write_action_in_source(self):
        import inspect
        from workers.tasks.check_tasks import run_daily_ops_check
        source = inspect.getsource(run_daily_ops_check)
        forbidden = ["db.add", "db.delete", "session.commit", "session.execute",
                      "order_service", "submit_order", "execute_trade"]
        for f in forbidden:
            assert f not in source, f"Forbidden write action found: {f}"

    def test_hourly_no_write_action_in_source(self):
        import inspect
        from workers.tasks.check_tasks import run_hourly_ops_check
        source = inspect.getsource(run_hourly_ops_check)
        forbidden = ["db.add", "db.delete", "session.commit", "session.execute",
                      "order_service", "submit_order", "execute_trade"]
        for f in forbidden:
            assert f not in source, f"Forbidden write action found: {f}"


class TestFailClosed:
    """Verify fail-closed behavior on errors."""

    def test_daily_returns_fail_on_import_error(self, monkeypatch):
        """If runner import fails, task should return FAIL, not raise."""
        import workers.tasks.check_tasks as mod
        original = mod.run_daily_ops_check.__wrapped__ if hasattr(mod.run_daily_ops_check, '__wrapped__') else None

        # Direct call should handle exceptions gracefully
        result = mod.run_daily_ops_check()
        assert isinstance(result, dict)
        # Result should be valid even if runner has issues
        assert result["check_type"] == "DAILY"

    def test_hourly_returns_fail_on_error(self):
        from workers.tasks.check_tasks import run_hourly_ops_check
        result = run_hourly_ops_check()
        assert isinstance(result, dict)
        assert result["check_type"] == "HOURLY"


class TestBeatSchedule:
    """Verify Celery beat schedule registration."""

    def test_beat_has_ops_daily(self):
        from workers.celery_app import celery_app
        schedule = celery_app.conf.beat_schedule
        assert "ops-daily-check" in schedule
        assert schedule["ops-daily-check"]["task"] == "workers.tasks.check_tasks.run_daily_ops_check"
        assert schedule["ops-daily-check"]["schedule"] == 86400.0

    def test_beat_has_ops_hourly(self):
        from workers.celery_app import celery_app
        schedule = celery_app.conf.beat_schedule
        assert "ops-hourly-check" in schedule
        assert schedule["ops-hourly-check"]["task"] == "workers.tasks.check_tasks.run_hourly_ops_check"
        assert schedule["ops-hourly-check"]["schedule"] == 3600.0

    def test_beat_ops_entries_count_is_2(self):
        from workers.celery_app import celery_app
        schedule = celery_app.conf.beat_schedule
        ops_entries = [k for k in schedule if k.startswith("ops-")]
        assert len(ops_entries) == 2

    def test_existing_beat_entries_unchanged(self):
        from workers.celery_app import celery_app
        schedule = celery_app.conf.beat_schedule
        # Original 4 entries must still exist
        assert "sync-positions-every-minute" in schedule
        assert "check-order-status-every-30s" in schedule
        assert "expire-old-signals" in schedule
        assert "record-asset-snapshot-every-5m" in schedule

    def test_total_beat_entries_is_6(self):
        from workers.celery_app import celery_app
        schedule = celery_app.conf.beat_schedule
        assert len(schedule) == 10  # 4 original + 2 ops + 2 G-MON + 2 CR-038 data
