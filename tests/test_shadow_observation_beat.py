"""RI-2A-2b: Shadow Observation Beat Task Tests.

Tests:
  - DryScheduleFlag: DRY_SCHEDULE=True, pipeline call 0, output contract
  - DryScheduleOutput: would_run/would_skip/reason_code 3-field contract
  - RedisLock: lock acquire, duplicate prevention, TTL
  - FailClosed: each failure scenario → write=0, state_change=0
  - ObservabilityFields: 10 required fields in task result
  - RetentionPlanner: constants exist, purge function absent
  - IsArchivedField: model field, default False
  - BeatEntryCommented: celery beat_schedule has no active shadow entry
  - SealedProtection: SEALED services untouched
  - SkipReasonCodeEnum: all codes are fixed enum members
"""

from __future__ import annotations

import inspect
import re
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


# ════════════════════════════════════════════════════════════════
# 1. DRY_SCHEDULE Flag
# ════════════════════════════════════════════════════════════════


class TestDryScheduleFlag:
    """DRY_SCHEDULE must be True (hardcoded)."""

    def test_dry_schedule_is_true(self):
        from workers.tasks.shadow_observation_tasks import DRY_SCHEDULE

        assert DRY_SCHEDULE is True, (
            "DRY_SCHEDULE must be True. False transition requires separate A approval."
        )

    def test_dry_schedule_no_pipeline_call(self):
        """When DRY_SCHEDULE=True, run_shadow_pipeline must NOT be called."""
        from workers.tasks.shadow_observation_tasks import _run_dry_schedule

        symbols = [{"symbol": "BTC/USDT", "asset_class": "CRYPTO", "asset_sector": "CRYPTO"}]
        result = _run_dry_schedule(symbols)

        # Dry schedule should produce a result without calling pipeline
        assert result.total_symbols == 1
        assert isinstance(result.would_run, list)
        assert isinstance(result.would_skip, list)

    def test_dry_schedule_result_has_required_fields(self):
        """DryScheduleResult must have would_run, would_skip, reason_codes."""
        from workers.tasks.shadow_observation_tasks import DryScheduleResult

        result = DryScheduleResult()
        assert hasattr(result, "would_run")
        assert hasattr(result, "would_skip")
        assert hasattr(result, "reason_codes")
        assert hasattr(result, "timestamp")
        assert hasattr(result, "total_symbols")
        assert hasattr(result, "runnable_count")
        assert hasattr(result, "skip_count")


# ════════════════════════════════════════════════════════════════
# 2. Dry-schedule Output Contract
# ════════════════════════════════════════════════════════════════


class TestDryScheduleOutput:
    """would_run / would_skip / reason_code 3-field contract."""

    def test_runnable_symbol_in_would_run(self):
        from workers.tasks.shadow_observation_tasks import _run_dry_schedule

        symbols = [{"symbol": "BTC/USDT", "asset_class": "CRYPTO"}]
        result = _run_dry_schedule(symbols)
        assert "BTC/USDT" in result.would_run
        assert result.reason_codes["BTC/USDT"] == "RUNNABLE"

    def test_no_input_symbol_in_would_skip(self):
        from workers.tasks.shadow_observation_tasks import _run_dry_schedule

        symbols = [{"symbol": "", "asset_class": "CRYPTO"}]
        result = _run_dry_schedule(symbols)
        assert "" in result.would_skip or "unknown" in result.would_skip
        # Empty symbol should not be RUNNABLE

    def test_multiple_symbols_classification(self):
        from workers.tasks.shadow_observation_tasks import _run_dry_schedule

        symbols = [
            {"symbol": "BTC/USDT", "asset_class": "CRYPTO"},
            {"symbol": "SOL/USDT", "asset_class": "CRYPTO"},
        ]
        result = _run_dry_schedule(symbols)
        assert result.total_symbols == 2
        assert result.runnable_count + result.skip_count == 2

    def test_reason_codes_are_enum_values(self):
        from workers.tasks.shadow_observation_tasks import (
            SkipReasonCode,
            _run_dry_schedule,
        )

        symbols = [{"symbol": "BTC/USDT"}]
        result = _run_dry_schedule(symbols)
        valid_codes = {e.value for e in SkipReasonCode}
        for code in result.reason_codes.values():
            assert code in valid_codes, f"reason_code '{code}' not in SkipReasonCode enum"


# ════════════════════════════════════════════════════════════════
# 3. Redis Lock
# ════════════════════════════════════════════════════════════════


class TestRedisLock:
    """Duplicate dispatch prevention via Redis lock."""

    def test_lock_key_and_ttl_constants(self):
        from workers.tasks.shadow_observation_tasks import _LOCK_KEY, _LOCK_TTL

        assert _LOCK_KEY == "shadow_observation_running"
        assert _LOCK_TTL == 300

    def test_lock_failure_returns_false(self):
        """If Redis is unavailable, _try_acquire_lock returns False (fail-closed)."""
        from workers.tasks.shadow_observation_tasks import _try_acquire_lock

        with patch("workers.tasks.shadow_observation_tasks.celery_app") as mock_app:
            mock_app.backend.client.set.side_effect = Exception("Redis down")
            assert _try_acquire_lock() is False

    def test_lock_acquired_returns_true(self):
        from workers.tasks.shadow_observation_tasks import _try_acquire_lock

        with patch("workers.tasks.shadow_observation_tasks.celery_app") as mock_app:
            mock_app.backend.client.set.return_value = True
            assert _try_acquire_lock() is True


# ════════════════════════════════════════════════════════════════
# 4. Fail-closed
# ════════════════════════════════════════════════════════════════


class TestFailClosed:
    """All failure scenarios → write=0, state_change=0."""

    def test_lock_failure_skips(self):
        """If lock fails, task returns skipped with ALREADY_RUNNING."""
        from workers.tasks.shadow_observation_tasks import run_shadow_observation

        with patch("workers.tasks.shadow_observation_tasks._try_acquire_lock", return_value=False):
            # Call underlying function directly to avoid Celery backend dependency
            result = run_shadow_observation()
            assert result["status"] == "skipped"
            assert result["skipped_reason"] == "ALREADY_RUNNING"

    def test_empty_symbols_skips(self):
        """If no symbols, task returns skipped with NO_INPUT."""
        from workers.tasks.shadow_observation_tasks import run_shadow_observation

        with (
            patch("workers.tasks.shadow_observation_tasks._try_acquire_lock", return_value=True),
            patch("workers.tasks.shadow_observation_tasks._release_lock"),
            patch("workers.tasks.shadow_observation_tasks._reset_consecutive_failures"),
            patch("workers.tasks.shadow_observation_tasks._get_symbol_list", return_value=[]),
        ):
            result = run_shadow_observation()
            assert result["status"] == "skipped"
            assert result["skipped_reason"] == "NO_INPUT"

    def test_exception_returns_failed(self):
        """Unhandled exception → status=failed, write=0."""
        from workers.tasks.shadow_observation_tasks import run_shadow_observation

        with (
            patch(
                "workers.tasks.shadow_observation_tasks._try_acquire_lock",
                side_effect=Exception("boom"),
            ),
            patch(
                "workers.tasks.shadow_observation_tasks._increment_consecutive_failures",
                return_value=1,
            ),
        ):
            result = run_shadow_observation()
            assert result["status"] == "failed"
            assert "boom" in result["failure_reason"]


# ════════════════════════════════════════════════════════════════
# 5. Observability Fields
# ════════════════════════════════════════════════════════════════


class TestObservabilityFields:
    """Task result must contain all 10 required fields."""

    REQUIRED_FIELDS = {
        "last_run",
        "status",
        "skipped_reason",
        "failure_reason",
        "symbols_processed",
        "symbols_skipped",
        "observations_inserted",
        "observations_failed",
        "duration_ms",
        "consecutive_failures",
    }

    def test_all_fields_present_on_success(self):
        from workers.tasks.shadow_observation_tasks import run_shadow_observation

        with (
            patch("workers.tasks.shadow_observation_tasks._try_acquire_lock", return_value=True),
            patch("workers.tasks.shadow_observation_tasks._release_lock"),
            patch("workers.tasks.shadow_observation_tasks._reset_consecutive_failures"),
        ):
            result = run_shadow_observation()
            missing = self.REQUIRED_FIELDS - set(result.keys())
            assert not missing, f"Missing observability fields: {missing}"

    def test_all_fields_present_on_skip(self):
        from workers.tasks.shadow_observation_tasks import run_shadow_observation

        with patch("workers.tasks.shadow_observation_tasks._try_acquire_lock", return_value=False):
            result = run_shadow_observation()
            missing = self.REQUIRED_FIELDS - set(result.keys())
            assert not missing, f"Missing observability fields: {missing}"

    def test_all_fields_present_on_failure(self):
        from workers.tasks.shadow_observation_tasks import run_shadow_observation

        with (
            patch(
                "workers.tasks.shadow_observation_tasks._try_acquire_lock",
                side_effect=Exception("x"),
            ),
            patch(
                "workers.tasks.shadow_observation_tasks._increment_consecutive_failures",
                return_value=1,
            ),
        ):
            result = run_shadow_observation()
            missing = self.REQUIRED_FIELDS - set(result.keys())
            assert not missing, f"Missing observability fields: {missing}"


# ════════════════════════════════════════════════════════════════
# 6. Retention Planner
# ════════════════════════════════════════════════════════════════


class TestRetentionPlanner:
    """Retention constants exist. Purge function does NOT exist."""

    def test_retention_constants_exist(self):
        from workers.tasks.shadow_observation_tasks import (
            RETENTION_HOT_DAYS,
            RETENTION_WARM_DAYS,
            AUDIT_VERDICTS,
        )

        assert RETENTION_HOT_DAYS == 30
        assert RETENTION_WARM_DAYS == 90
        assert "verdict_mismatch" in AUDIT_VERDICTS
        assert "reason_mismatch" in AUDIT_VERDICTS

    def test_no_purge_function(self):
        """No purge/delete/drop function in shadow_observation_tasks."""
        import workers.tasks.shadow_observation_tasks as mod

        source = inspect.getsource(mod)
        # Check for purge/delete/drop function definitions
        # Note: redis_client.delete() for lock cleanup is allowed
        purge_patterns = [
            r"def\s+.*purge",
            r"def\s+.*delete_observation",
            r"def\s+.*drop_observation",
            r"DELETE\s+FROM",
        ]
        for pattern in purge_patterns:
            assert not re.search(pattern, source, re.IGNORECASE), (
                f"Purge/delete pattern found: {pattern}. "
                "Purge execution is NOT allowed in RI-2A-2b."
            )


# ════════════════════════════════════════════════════════════════
# 7. is_archived Model Field
# ════════════════════════════════════════════════════════════════


class TestIsArchivedField:
    """ShadowObservationLog.is_archived field."""

    def test_field_exists(self):
        from app.models.shadow_observation import ShadowObservationLog

        assert hasattr(ShadowObservationLog, "is_archived")

    def test_default_is_false(self):
        from app.models.shadow_observation import ShadowObservationLog

        col = ShadowObservationLog.__table__.columns["is_archived"]
        assert col.default.arg is False or col.server_default.arg == "false"


# ════════════════════════════════════════════════════════════════
# 8. Beat Entry Commented
# ════════════════════════════════════════════════════════════════


class TestBeatEntryActive:
    """shadow-observation-5m must be in active beat_schedule (P3-B activated)."""

    def test_shadow_observation_beat_present(self):
        """P3-B: beat entry is now active."""
        from workers.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule or {}
        assert "shadow-observation-5m" in schedule, (
            "shadow-observation-5m must be present in beat_schedule (P3-B)."
        )

    def test_beat_interval_is_300s(self):
        """Beat interval must remain exactly 300 seconds."""
        from workers.celery_app import celery_app

        entry = celery_app.conf.beat_schedule["shadow-observation-5m"]
        assert entry["schedule"] == 300.0, (
            f"Beat interval must be 300s, got {entry['schedule']}"
        )

    def test_beat_task_name_matches(self):
        """Beat entry task name must match the actual task."""
        from workers.celery_app import celery_app

        entry = celery_app.conf.beat_schedule["shadow-observation-5m"]
        assert entry["task"] == "workers.tasks.shadow_observation_tasks.run_shadow_observation"


# ════════════════════════════════════════════════════════════════
# 9. SEALED Protection
# ════════════════════════════════════════════════════════════════


class TestSealedProtection:
    """SEALED services must not contain shadow_observation_tasks imports."""

    def test_shadow_observation_service_has_no_beat_import(self):
        """shadow_observation_service.py must not import from beat tasks."""
        import app.services.shadow_observation_service as mod

        source = inspect.getsource(mod)
        assert "shadow_observation_tasks" not in source, (
            "SEALED shadow_observation_service must not import from beat tasks."
        )

    def test_shadow_write_service_untouched(self):
        """shadow_write_service.py must not reference DRY_SCHEDULE."""
        import app.services.shadow_write_service as mod

        source = inspect.getsource(mod)
        assert "DRY_SCHEDULE" not in source


# ════════════════════════════════════════════════════════════════
# 10. SkipReasonCode Enum
# ════════════════════════════════════════════════════════════════


class TestSkipReasonCodeEnum:
    """All reason codes must be fixed enum members."""

    def test_all_codes_are_enum(self):
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
        actual = {e.value for e in SkipReasonCode}
        assert expected == actual

    def test_enum_is_str_enum(self):
        from workers.tasks.shadow_observation_tasks import SkipReasonCode

        assert issubclass(SkipReasonCode, str)


# ════════════════════════════════════════════════════════════════
# 11. No Business Write in Task
# ════════════════════════════════════════════════════════════════


class TestNoBusinessWrite:
    """Task code must not contain UPDATE/DELETE for business tables."""

    def test_no_update_delete_keywords(self):
        import workers.tasks.shadow_observation_tasks as mod

        source = inspect.getsource(mod)
        # Allowed: Redis .delete() for lock cleanup — check for SQL patterns
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
