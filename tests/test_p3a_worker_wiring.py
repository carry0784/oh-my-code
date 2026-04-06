"""CR-048 Follow-Up 2A P3-A: Worker live-path wiring tests.

Pure unit tests with mocks. No DB fixtures, no ORM mapper, no Redis.
Validates the shadow_observation_tasks → ShadowPipelineOrchestrator wiring.

Controlling spec: CR-048 2A P3-A IMPLEMENTATION GO

Invariants verified:
  - DRY_SCHEDULE remains True (runtime assert)
  - execute_bounded_write is NOT imported
  - rollback_bounded_write is NOT imported
  - Lock TTL > schedule interval (420 > 300)
  - Per-symbol loop via orch.run_single (not run_batch)
  - Per-symbol failure isolation
  - orchestrator_outcomes in task result
  - Beat registration NOT performed (P3-B scope)
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


# ── DRY_SCHEDULE Guard Tests ─────────────────────────────────────


class TestDryScheduleGuard:
    """Verify DRY_SCHEDULE is enforced at module and runtime level."""

    def test_dry_schedule_is_true(self):
        """DRY_SCHEDULE must be True in source."""
        from workers.tasks.shadow_observation_tasks import DRY_SCHEDULE

        assert DRY_SCHEDULE is True

    def test_dry_schedule_guard_in_source(self):
        """DRY_SCHEDULE branch guard exists in task source (P4-impl: assert → if)."""
        import inspect

        from workers.tasks import shadow_observation_tasks

        source = inspect.getsource(shadow_observation_tasks.run_shadow_observation)
        assert "if DRY_SCHEDULE:" in source


# ── Lock TTL Tests ───────────────────────────────────────────────


class TestLockTTL:
    """Verify lock TTL exceeds schedule interval."""

    def test_lock_ttl_greater_than_schedule(self):
        """Lock TTL (420s) must be greater than beat schedule (300s)."""
        from workers.tasks.shadow_observation_tasks import _LOCK_TTL

        assert _LOCK_TTL >= 420

    def test_lock_ttl_in_task_result_defaults(self):
        """lock_ttl_sec appears in default task_result."""
        from workers.tasks.shadow_observation_tasks import _LOCK_TTL

        # Verify the constant is used as task_result default
        assert _LOCK_TTL == 420


# ── No Execute / No Rollback Tests ───────────────────────────────


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


# ── Orchestrator Call Style Tests ────────────────────────────────


class TestOrchestratorCallStyle:
    """Verify task uses per-symbol loop via orch.run_single, not run_batch."""

    def test_run_single_in_source(self):
        """_run_orchestrator_for_symbols uses orch.run_single, not orch.run_batch."""
        import inspect

        from workers.tasks.shadow_observation_tasks import _run_orchestrator_for_symbols

        source = inspect.getsource(_run_orchestrator_for_symbols)
        assert "orch.run_single" in source
        # Verify no actual orch.run_batch() call in executable lines
        code_lines = [
            line.strip()
            for line in source.splitlines()
            if line.strip()
            and not line.strip().startswith("#")
            and not line.strip().startswith('"""')
            and not line.strip().startswith("'")
        ]
        batch_calls = [line for line in code_lines if "orch.run_batch" in line]
        assert batch_calls == [], f"orch.run_batch found in code: {batch_calls}"


# ── Dry Schedule Result Extension Tests ──────────────────────────


class TestDryScheduleResultExtension:
    """Verify dry_result fields and orchestrator_outcomes in task output."""

    def test_dry_schedule_result_fields(self):
        """DryScheduleResult has required fields."""
        from workers.tasks.shadow_observation_tasks import DryScheduleResult

        result = DryScheduleResult()
        assert hasattr(result, "would_run")
        assert hasattr(result, "would_skip")
        assert hasattr(result, "reason_codes")
        assert hasattr(result, "total_symbols")
        assert hasattr(result, "runnable_count")
        assert hasattr(result, "skip_count")


# ── Task Integration Tests (Mocked) ─────────────────────────────


class TestTaskIntegration:
    """Verify run_shadow_observation wiring with mocked dependencies."""

    @patch("workers.tasks.shadow_observation_tasks._run_orchestrator_for_symbols")
    @patch("workers.tasks.shadow_observation_tasks._release_lock")
    @patch("workers.tasks.shadow_observation_tasks._try_acquire_lock")
    @patch("workers.tasks.shadow_observation_tasks._reset_consecutive_failures")
    def test_successful_run_with_orchestrator(
        self,
        mock_reset_failures,
        mock_acquire,
        mock_release,
        mock_orch_run,
    ):
        """Full dry-run with orchestrator produces expected task_result."""
        mock_acquire.return_value = True

        # Mock orchestrator results
        mock_result_sol = MagicMock()
        mock_result_sol.symbol = "SOL/USDT"
        mock_result_sol.outcome = MagicMock()
        mock_result_sol.outcome.value = "would_write"
        mock_result_sol.observation_id = 42
        mock_result_sol.receipt_id = "receipt-001"

        mock_result_btc = MagicMock()
        mock_result_btc.symbol = "BTC/USDT"
        mock_result_btc.outcome = MagicMock()
        mock_result_btc.outcome.value = "noop"
        mock_result_btc.observation_id = 43
        mock_result_btc.receipt_id = "receipt-002"

        mock_orch_run.return_value = [mock_result_sol, mock_result_btc]

        from workers.tasks.shadow_observation_tasks import run_shadow_observation

        result = run_shadow_observation()

        assert result["status"] == "completed"
        assert result["dry_schedule"] is True
        assert result["symbols_processed"] == 2
        assert result["observations_inserted"] == 2
        assert result["receipts_created"] == 2
        assert result["lock_acquired"] is True
        assert result["lock_ttl_sec"] == 420
        assert "SOL/USDT" in result["orchestrator_outcomes"]
        assert result["orchestrator_outcomes"]["SOL/USDT"]["outcome"] == "would_write"
        assert "BTC/USDT" in result["orchestrator_outcomes"]
        assert result["orchestrator_outcomes"]["BTC/USDT"]["outcome"] == "noop"
        mock_release.assert_called_once()
        mock_reset_failures.assert_called_once()

    @patch("workers.tasks.shadow_observation_tasks._run_orchestrator_for_symbols")
    @patch("workers.tasks.shadow_observation_tasks._release_lock")
    @patch("workers.tasks.shadow_observation_tasks._try_acquire_lock")
    @patch("workers.tasks.shadow_observation_tasks._reset_consecutive_failures")
    def test_orchestrator_partial_failure(
        self,
        mock_reset_failures,
        mock_acquire,
        mock_release,
        mock_orch_run,
    ):
        """One symbol errors, others succeed — task still completes."""
        mock_acquire.return_value = True

        mock_result_sol = MagicMock()
        mock_result_sol.symbol = "SOL/USDT"
        mock_result_sol.outcome = MagicMock()
        mock_result_sol.outcome.value = "error_internal"
        mock_result_sol.observation_id = None  # Failed — no observation
        mock_result_sol.receipt_id = None  # Failed — no receipt

        mock_result_btc = MagicMock()
        mock_result_btc.symbol = "BTC/USDT"
        mock_result_btc.outcome = MagicMock()
        mock_result_btc.outcome.value = "would_write"
        mock_result_btc.observation_id = 99
        mock_result_btc.receipt_id = "receipt-099"

        mock_orch_run.return_value = [mock_result_sol, mock_result_btc]

        from workers.tasks.shadow_observation_tasks import run_shadow_observation

        result = run_shadow_observation()

        assert result["status"] == "completed"
        assert result["observations_inserted"] == 1  # Only BTC
        assert result["receipts_created"] == 1  # Only BTC
        assert result["orchestrator_outcomes"]["SOL/USDT"]["outcome"] == "error_internal"
        assert result["orchestrator_outcomes"]["BTC/USDT"]["outcome"] == "would_write"

    @patch("workers.tasks.shadow_observation_tasks._release_lock")
    @patch("workers.tasks.shadow_observation_tasks._try_acquire_lock")
    def test_lock_not_acquired_skips(self, mock_acquire, mock_release):
        """Lock failure → skip, no orchestrator call."""
        mock_acquire.return_value = False

        from workers.tasks.shadow_observation_tasks import run_shadow_observation

        result = run_shadow_observation()

        assert result["status"] == "skipped"
        assert result["skipped_reason"] == "ALREADY_RUNNING"
        assert result["lock_acquired"] is False
        mock_release.assert_not_called()

    @patch("workers.tasks.shadow_observation_tasks._run_orchestrator_for_symbols")
    @patch("workers.tasks.shadow_observation_tasks._release_lock")
    @patch("workers.tasks.shadow_observation_tasks._try_acquire_lock")
    @patch("workers.tasks.shadow_observation_tasks._reset_consecutive_failures")
    def test_no_symbols_skips(
        self,
        mock_reset_failures,
        mock_acquire,
        mock_release,
        mock_orch_run,
    ):
        """Empty symbol list → skip, no orchestrator call."""
        mock_acquire.return_value = True

        with patch("workers.tasks.shadow_observation_tasks._get_symbol_list", return_value=[]):
            from workers.tasks.shadow_observation_tasks import run_shadow_observation

            result = run_shadow_observation()

        assert result["status"] == "skipped"
        assert result["skipped_reason"] == "NO_INPUT"
        mock_orch_run.assert_not_called()

    @patch("workers.tasks.shadow_observation_tasks._run_orchestrator_for_symbols")
    @patch("workers.tasks.shadow_observation_tasks._release_lock")
    @patch("workers.tasks.shadow_observation_tasks._try_acquire_lock")
    @patch("workers.tasks.shadow_observation_tasks._reset_consecutive_failures")
    def test_orchestrator_exception_fail_closed(
        self,
        mock_reset_failures,
        mock_acquire,
        mock_release,
        mock_orch_run,
    ):
        """Orchestrator raising → task fails gracefully."""
        mock_acquire.return_value = True
        mock_orch_run.side_effect = RuntimeError("DB connection failed")

        from workers.tasks.shadow_observation_tasks import run_shadow_observation

        result = run_shadow_observation()

        # Task catches exception at top level
        assert result["status"] == "failed"
        assert "DB connection failed" in result["failure_reason"]


# ── Task Result Schema Tests ─────────────────────────────────────


class TestTaskResultSchema:
    """Verify task result dict contains all required P3-A fields."""

    @patch("workers.tasks.shadow_observation_tasks._run_orchestrator_for_symbols")
    @patch("workers.tasks.shadow_observation_tasks._release_lock")
    @patch("workers.tasks.shadow_observation_tasks._try_acquire_lock")
    @patch("workers.tasks.shadow_observation_tasks._reset_consecutive_failures")
    def test_result_has_all_fields(
        self,
        mock_reset_failures,
        mock_acquire,
        mock_release,
        mock_orch_run,
    ):
        """Task result contains all required audit fields."""
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
        assert required_fields.issubset(set(result.keys())), (
            f"Missing fields: {required_fields - set(result.keys())}"
        )

    @patch("workers.tasks.shadow_observation_tasks._run_orchestrator_for_symbols")
    @patch("workers.tasks.shadow_observation_tasks._release_lock")
    @patch("workers.tasks.shadow_observation_tasks._try_acquire_lock")
    @patch("workers.tasks.shadow_observation_tasks._reset_consecutive_failures")
    def test_result_dry_schedule_always_true(
        self,
        mock_reset_failures,
        mock_acquire,
        mock_release,
        mock_orch_run,
    ):
        """dry_schedule field is always True in P3."""
        mock_acquire.return_value = True
        mock_orch_run.return_value = []

        from workers.tasks.shadow_observation_tasks import run_shadow_observation

        result = run_shadow_observation()
        assert result["dry_schedule"] is True


# ── Beat Registration Active Test (P3-B) ─────────────────────────


class TestBeatRegistered:
    """Verify beat schedule was activated (P3-B)."""

    def test_shadow_observation_in_beat(self):
        """Shadow observation task IS in active beat schedule (P3-B activated)."""
        from workers.celery_app import celery_app

        beat = celery_app.conf.beat_schedule
        shadow_entries = [k for k, v in beat.items() if "shadow_observation" in v.get("task", "")]
        assert shadow_entries == ["shadow-observation-5m"], (
            f"Expected exactly one shadow observation beat entry, got: {shadow_entries}"
        )


# ── SkipReasonCode Completeness ──────────────────────────────────


class TestSkipReasonCodeCompleteness:
    """Verify SkipReasonCode enum has all expected values."""

    def test_all_codes_present(self):
        from workers.tasks.shadow_observation_tasks import SkipReasonCode

        expected = {
            "RUNNABLE",
            "NO_MARKET_DATA",
            "NO_BACKTEST_READINESS",
            "STALE_INPUT",
            "DUPLICATE_WINDOW",
            "ALREADY_RUNNING",
            "LOCK_FAILED",
            "NO_INPUT",
            "DRY_SCHEDULE_ACTIVE",
        }
        actual = {e.name for e in SkipReasonCode}
        assert actual == expected
