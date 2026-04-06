"""
Tests for BL-OPS-RESTART01 + BL-EXMODE01 operational hygiene.

Verifies:
  1. Disabled tasks NOT in active beat_schedule
  2. Active beat_schedule keys match expected set
  3. Startup fingerprint function works
  4. Hourly check includes exchange_mode items
  5. BL-OPS-RESTART01 document exists
"""

import os
import pytest

from workers.celery_app import celery_app


# ── Beat schedule contract ─────────────────────────────────────────


class TestBeatScheduleContract:
    """CR-049: Disabled tasks must not appear in active beat_schedule."""

    def test_check_pending_orders_not_in_schedule(self):
        """check_pending_orders must NOT be in active beat_schedule."""
        task_names = {v["task"] for v in celery_app.conf.beat_schedule.values()}
        assert "workers.tasks.order_tasks.check_pending_orders" not in task_names

    def test_sync_all_positions_not_in_schedule(self):
        """sync_all_positions must NOT be in active beat_schedule."""
        task_names = {v["task"] for v in celery_app.conf.beat_schedule.values()}
        assert "workers.tasks.market_tasks.sync_all_positions" not in task_names

    def test_sol_paper_trading_in_schedule(self):
        """sol_paper_trading must be in active beat_schedule (post beat-registration GO)."""
        task_names = {v["task"] for v in celery_app.conf.beat_schedule.values()}
        assert "workers.tasks.sol_paper_tasks.run_sol_paper_bar" in task_names

    def test_active_schedule_has_expected_keys(self):
        """Active beat_schedule must contain core data collection tasks."""
        keys = set(celery_app.conf.beat_schedule.keys())
        expected_active = {
            "expire-old-signals",
            "record-asset-snapshot-every-5m",
            "collect-market-state-every-5m",
            "collect-sol-market-state-every-5m",
            "collect-sentiment-hourly",
            "sol-paper-trading-hourly",
        }
        assert expected_active.issubset(keys), f"Missing keys: {expected_active - keys}"

    def test_all_schedule_entries_have_task_field(self):
        """Every beat_schedule entry must have a 'task' field."""
        for key, entry in celery_app.conf.beat_schedule.items():
            assert "task" in entry, f"beat_schedule['{key}'] missing 'task' field"
            assert "schedule" in entry, f"beat_schedule['{key}'] missing 'schedule' field"

    def test_strategy_cycles_are_dry_run(self):
        """All strategy cycle tasks must have dry_run=True."""
        for key, entry in celery_app.conf.beat_schedule.items():
            if "strategy-cycle" in key:
                kwargs = entry.get("kwargs", {})
                assert kwargs.get("dry_run") is True, (
                    f"beat_schedule['{key}'] must have dry_run=True"
                )


# ── Startup fingerprint ───────────────────────────────────────────


class TestStartupFingerprint:
    """BL-OPS-RESTART01: Startup fingerprint function must work."""

    def test_startup_fingerprint_callable(self):
        """_startup_fingerprint must be callable without error."""
        from workers.celery_app import _startup_fingerprint

        # Should not raise — just logs
        _startup_fingerprint("test")

    def test_startup_fingerprint_counts(self):
        """Fingerprint reports correct active/disabled counts."""
        from app.api.routes.ops import _BEAT_TASKS

        active = sum(1 for t in _BEAT_TASKS if t["status"] == "ACTIVE")
        disabled = sum(1 for t in _BEAT_TASKS if t["status"] == "DISABLED")

        schedule_count = len(celery_app.conf.beat_schedule)

        assert active == 13
        assert disabled == 2
        assert schedule_count == 13  # matches active count


# ── Hourly check exchange_mode items ───────────────────────────────


class TestHourlyCheckExchangeMode:
    """BL-EXMODE01: Hourly check must include exchange_mode items."""

    def test_hourly_items_include_exchange_mode(self):
        from app.core.constitution_check_runner import _HOURLY_ITEMS

        names = {item["name"] for item in _HOURLY_ITEMS}
        assert "exchange_mode" in names
        assert "disabled_beat_tasks" in names
        assert "blocked_api_count" in names

    def test_hourly_check_exchange_mode_observation(self):
        """exchange_mode hourly check must observe DATA_ONLY."""
        from app.core.constitution_check_runner import run_hourly_check

        result = run_hourly_check()

        mode_item = next((i for i in result.items if i.name == "exchange_mode"), None)
        assert mode_item is not None
        assert mode_item.observed == "DATA_ONLY"
        assert mode_item.grade.value == "OK"

    def test_hourly_check_disabled_tasks_observation(self):
        """disabled_beat_tasks hourly check must observe 2."""
        from app.core.constitution_check_runner import run_hourly_check

        result = run_hourly_check()

        item = next((i for i in result.items if i.name == "disabled_beat_tasks"), None)
        assert item is not None
        assert item.observed == "2"
        assert item.grade.value == "OK"

    def test_hourly_check_blocked_api_observation(self):
        """blocked_api_count hourly check must observe 5 in DATA_ONLY."""
        from app.core.constitution_check_runner import run_hourly_check

        result = run_hourly_check()

        item = next((i for i in result.items if i.name == "blocked_api_count"), None)
        assert item is not None
        assert item.observed == "5"
        assert item.grade.value == "OK"

    def test_hourly_check_total_items(self):
        """Hourly check now has 10 items (7 original + 3 BL-EXMODE01)."""
        from app.core.constitution_check_runner import run_hourly_check

        result = run_hourly_check()
        assert len(result.items) == 10


# ── Document existence ─────────────────────────────────────────────


class TestDocumentExistence:
    """BL-OPS-RESTART01 and BL-EXMODE01 documents must exist."""

    def test_bl_ops_restart01_exists(self):
        doc_path = os.path.join(
            os.path.dirname(__file__), "..", "docs", "architecture", "bl_ops_restart01.md"
        )
        assert os.path.isfile(doc_path), "BL-OPS-RESTART01 document not found"

        with open(doc_path, encoding="utf-8") as f:
            content = f.read()
        assert "BL-OPS-RESTART01" in content
        assert "celerybeat-schedule" in content
        assert "purge" in content

    def test_bl_exmode01_exists(self):
        doc_path = os.path.join(
            os.path.dirname(__file__), "..", "docs", "architecture", "bl_exmode01.md"
        )
        assert os.path.isfile(doc_path), "BL-EXMODE01 document not found"
