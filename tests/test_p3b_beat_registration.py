"""CR-048 Follow-Up 2A P3-B: Beat registration + dry-run verification tests.

Pure unit tests with mocks. No DB fixtures, no ORM mapper, no Redis.
Validates shadow_observation beat activation under DRY_SCHEDULE=True.

Controlling spec: CR-048 2A P3-B IMPLEMENTATION GO

Invariants verified:
  - Beat entry "shadow-observation-5m" is present in active beat_schedule
  - Beat interval is exactly 300 seconds
  - Beat task name matches actual task
  - Active beat count delta = +1 (from 10 to 11)
  - DRY_SCHEDULE remains True
  - execute_bounded_write is NOT imported
  - rollback_bounded_write is NOT imported
  - Lock-not-acquired produces explicit skip result
  - Dry-run sample result dict shape
  - shadow_observation_tasks is in celery include list
  - Entry is present but gated (DRY_SCHEDULE=True gate)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ── Beat Entry Present Tests ───────────────────────────────────


class TestBeatEntryPresent:
    """Verify shadow-observation-5m is active in beat_schedule."""

    def test_beat_entry_exists(self):
        """shadow-observation-5m must be in beat_schedule."""
        from workers.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule or {}
        assert "shadow-observation-5m" in schedule

    def test_beat_interval_300s(self):
        """Beat interval must be exactly 300 seconds."""
        from workers.celery_app import celery_app

        entry = celery_app.conf.beat_schedule["shadow-observation-5m"]
        assert entry["schedule"] == 300.0, f"Beat interval must be 300.0s, got {entry['schedule']}"

    def test_beat_task_name(self):
        """Beat task name must match the registered Celery task."""
        from workers.celery_app import celery_app

        entry = celery_app.conf.beat_schedule["shadow-observation-5m"]
        expected = "workers.tasks.shadow_observation_tasks.run_shadow_observation"
        assert entry["task"] == expected

    def test_no_kwargs_in_beat_entry(self):
        """Beat entry should not have kwargs (task manages its own config)."""
        from workers.celery_app import celery_app

        entry = celery_app.conf.beat_schedule["shadow-observation-5m"]
        assert "kwargs" not in entry or entry.get("kwargs") is None


# ── Active Beat Count Delta Tests ──────────────────────────────


class TestActiveBeatCountDelta:
    """Verify beat count changed from 10 to 11."""

    def test_total_beat_count(self):
        """Active beat schedule must have exactly 11 entries (was 10)."""
        from workers.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule or {}
        assert len(schedule) == 11, (
            f"Expected 11 beat entries (10 pre-P3-B + 1 shadow), got {len(schedule)}"
        )

    def test_shadow_is_the_only_new_entry(self):
        """Only shadow-observation-5m was added (delta = +1)."""
        from workers.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule or {}
        pre_p3b_entries = {
            "sync-positions-every-minute",
            "check-order-status-every-30s",
            "expire-old-signals",
            "record-asset-snapshot-every-5m",
            "ops-daily-check",
            "ops-hourly-check",
            "governance-monitor-daily",
            "governance-monitor-weekly",
            "collect-market-state-every-5m",
            "collect-sentiment-hourly",
        }
        new_entries = set(schedule.keys()) - pre_p3b_entries
        assert new_entries == {"shadow-observation-5m"}, f"Unexpected new entries: {new_entries}"


# ── Include List Tests ─────────────────────────────────────────


class TestIncludeList:
    """Verify shadow_observation_tasks is in celery include list."""

    def test_module_in_include(self):
        """shadow_observation_tasks must be in celery app include list."""
        from workers.celery_app import celery_app

        includes = celery_app.conf.get("include", [])
        assert "workers.tasks.shadow_observation_tasks" in includes


# ── DRY_SCHEDULE Gate Tests ────────────────────────────────────


class TestDryScheduleGate:
    """Verify beat entry is present but gated by DRY_SCHEDULE=True."""

    def test_dry_schedule_remains_true(self):
        """DRY_SCHEDULE must be True (P4 scope for False)."""
        from workers.tasks.shadow_observation_tasks import DRY_SCHEDULE

        assert DRY_SCHEDULE is True

    def test_runtime_assert_in_task(self):
        """Runtime assert DRY_SCHEDULE is True must exist in task code."""
        import inspect

        from workers.tasks import shadow_observation_tasks

        source = inspect.getsource(shadow_observation_tasks.run_shadow_observation)
        assert "assert DRY_SCHEDULE is True" in source

    def test_entry_present_but_gated(self):
        """Beat entry exists AND DRY_SCHEDULE is True — entry is present but gated."""
        from workers.celery_app import celery_app
        from workers.tasks.shadow_observation_tasks import DRY_SCHEDULE

        schedule = celery_app.conf.beat_schedule or {}
        assert "shadow-observation-5m" in schedule, "Beat entry must be present"
        assert DRY_SCHEDULE is True, "DRY_SCHEDULE must remain True (P4 gate)"


# ── No Execute / No Rollback Tests ────────────────────────────


class TestNoExecuteNoRollback:
    """Verify execute/rollback are not imported in task module."""

    def test_no_execute_import(self):
        """execute_bounded_write is not in module namespace."""
        import workers.tasks.shadow_observation_tasks as mod

        assert not hasattr(mod, "execute_bounded_write")

    def test_no_rollback_import(self):
        """rollback_bounded_write is not in module namespace."""
        import workers.tasks.shadow_observation_tasks as mod

        assert not hasattr(mod, "rollback_bounded_write")


# ── Duplicate Start / Lock-Not-Acquired Tests ─────────────────


class TestDuplicateStartBehavior:
    """Verify lock-not-acquired produces explicit skip result."""

    @patch("workers.tasks.shadow_observation_tasks._release_lock")
    @patch("workers.tasks.shadow_observation_tasks._try_acquire_lock")
    def test_lock_not_acquired_skip_result(self, mock_acquire, mock_release):
        """Lock failure produces skip result with explicit reason."""
        mock_acquire.return_value = False

        from workers.tasks.shadow_observation_tasks import run_shadow_observation

        result = run_shadow_observation()

        assert result["status"] == "skipped"
        assert result["dry_schedule"] is True
        assert result["lock_acquired"] is False
        assert result["skipped_reason"] == "ALREADY_RUNNING"
        assert result["symbols_processed"] == 0
        assert result["symbols_skipped"] == 0
        mock_release.assert_not_called()

    @patch("workers.tasks.shadow_observation_tasks._release_lock")
    @patch("workers.tasks.shadow_observation_tasks._try_acquire_lock")
    def test_lock_not_acquired_result_shape(self, mock_acquire, mock_release):
        """Lock-not-acquired result has the fixed shape for P4 review."""
        mock_acquire.return_value = False

        from workers.tasks.shadow_observation_tasks import run_shadow_observation

        result = run_shadow_observation()

        # Verify the exact shape matches governance-specified format
        required_keys = {
            "status",
            "dry_schedule",
            "lock_acquired",
            "skipped_reason",
            "symbols_processed",
            "symbols_skipped",
        }
        assert required_keys.issubset(set(result.keys()))
        assert result == {
            **result,  # preserve any extra fields
            "status": "skipped",
            "dry_schedule": True,
            "lock_acquired": False,
            "skipped_reason": "ALREADY_RUNNING",
            "symbols_processed": 0,
            "symbols_skipped": 0,
        }


# ── Dry-Run Sample Result Dict Tests ──────────────────────────


class TestDryRunSampleResult:
    """Verify dry-run result dict shape and content."""

    @patch("workers.tasks.shadow_observation_tasks._run_orchestrator_for_symbols")
    @patch("workers.tasks.shadow_observation_tasks._release_lock")
    @patch("workers.tasks.shadow_observation_tasks._try_acquire_lock")
    @patch("workers.tasks.shadow_observation_tasks._reset_consecutive_failures")
    def test_successful_dry_run_result_shape(
        self,
        mock_reset_failures,
        mock_acquire,
        mock_release,
        mock_orch_run,
    ):
        """Successful dry-run produces complete result dict."""
        mock_acquire.return_value = True

        mock_result = MagicMock()
        mock_result.symbol = "SOL/USDT"
        mock_result.outcome = MagicMock()
        mock_result.outcome.value = "would_write"
        mock_result.observation_id = 1
        mock_result.receipt_id = "receipt-001"

        mock_orch_run.return_value = [mock_result]

        from workers.tasks.shadow_observation_tasks import run_shadow_observation

        result = run_shadow_observation()

        # Full result shape verification
        assert result["status"] == "completed"
        assert result["dry_schedule"] is True
        assert result["lock_acquired"] is True
        assert result["lock_ttl_sec"] == 420
        assert result["symbols_processed"] >= 1
        assert result["observations_inserted"] >= 1
        assert result["receipts_created"] >= 1
        assert isinstance(result["orchestrator_outcomes"], dict)
        assert isinstance(result["last_run"], str)
        assert isinstance(result["duration_ms"], int)
        assert result["consecutive_failures"] == 0

    @patch("workers.tasks.shadow_observation_tasks._run_orchestrator_for_symbols")
    @patch("workers.tasks.shadow_observation_tasks._release_lock")
    @patch("workers.tasks.shadow_observation_tasks._try_acquire_lock")
    @patch("workers.tasks.shadow_observation_tasks._reset_consecutive_failures")
    def test_dry_run_result_has_all_audit_fields(
        self,
        mock_reset_failures,
        mock_acquire,
        mock_release,
        mock_orch_run,
    ):
        """Dry-run result includes all fields required for audit trail."""
        mock_acquire.return_value = True
        mock_orch_run.return_value = []

        from workers.tasks.shadow_observation_tasks import run_shadow_observation

        result = run_shadow_observation()

        required_fields = {
            "last_run",
            "status",
            "skipped_reason",
            "failure_reason",
            "symbols_processed",
            "symbols_skipped",
            "observations_inserted",
            "observations_failed",
            "receipts_created",
            "orchestrator_outcomes",
            "lock_acquired",
            "lock_ttl_sec",
            "duration_ms",
            "consecutive_failures",
            "dry_schedule",
        }
        missing = required_fields - set(result.keys())
        assert missing == set(), f"Missing audit fields: {missing}"


# ── Business Write Zero Proof ──────────────────────────────────


class TestBusinessWriteZero:
    """Verify no business write paths exist in task code."""

    def test_no_sql_write_patterns(self):
        """Task source must not contain UPDATE/DELETE for business tables."""
        import re
        import inspect

        import workers.tasks.shadow_observation_tasks as mod

        source = inspect.getsource(mod)
        forbidden = [
            r"UPDATE\s+symbols",
            r"UPDATE\s+screening",
            r"UPDATE\s+qualification",
            r"DELETE\s+FROM\s+symbols",
            r"DELETE\s+FROM\s+screening",
            r"DELETE\s+FROM\s+qualification",
            r"DELETE\s+FROM\s+shadow_observation",
        ]
        for pattern in forbidden:
            assert not re.search(pattern, source, re.IGNORECASE), (
                f"Business write pattern found: {pattern}"
            )
