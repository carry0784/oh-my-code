"""
Card C-31: Retry Executor / Wiring — Tests

검수 범위:
  C31-1: 모듈 구조
  C31-2: Single-pass execution
  C31-3: Eligibility filtering
  C31-4: Bounded execution (max_executions)
  C31-5: Success → mark_executed
  C31-6: Failure → mark_expired
  C31-7: No sender → mark_expired
  C31-8: Fail-closed
  C31-9: Summary helper
  C31-10: 금지 조항

Sealed layers 미접촉. 기존 테스트 파일 미수정.
"""

from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
from dataclasses import dataclass

import pytest

from app.core.retry_executor import (
    execute_retry_pass,
    get_retry_summary,
    RetryPassResult,
    RetryAttemptResult,
    DEFAULT_MAX_EXECUTIONS,
)
from app.core.retry_plan_store import RetryPlanStore

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXECUTOR_PATH = PROJECT_ROOT / "app" / "core" / "retry_executor.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store_with_plan(channel="external", incident="inc_001",
                          eligible_seconds=0):
    """Create a store with one immediately-eligible pending plan."""
    store = RetryPlanStore(ttl_seconds=9999)
    store.enqueue(
        channel=channel,
        reason="timeout",
        reliability_tier="transient_failure",
        retryable=True,
        retry_after_seconds=eligible_seconds,
        incident=incident,
        severity_tier="high",
    )
    return store


@dataclass
class FakeChannelResult:
    channel: str
    delivered: bool
    detail: str = ""


# ===========================================================================
# C31-1: 모듈 구조
# ===========================================================================
class TestC31ModuleStructure:

    def test_module_exists(self):
        assert EXECUTOR_PATH.exists()

    def test_pass_result_dataclass(self):
        r = RetryPassResult(plans_checked=3)
        assert r.plans_checked == 3

    def test_attempt_result_dataclass(self):
        a = RetryAttemptResult(retry_id="x", channel="ext", success=True)
        assert a.success is True

    def test_default_max_executions(self):
        assert DEFAULT_MAX_EXECUTIONS == 5

    def test_executor_class_exists(self):
        content = EXECUTOR_PATH.read_text(encoding="utf-8")
        assert "execute_retry_pass" in content

    def test_pass_result_to_dict(self):
        r = RetryPassResult(plans_checked=1)
        d = r.to_dict()
        assert isinstance(d, dict)
        assert d["plans_checked"] == 1


# ===========================================================================
# C31-2: Single-pass execution
# ===========================================================================
class TestC31SinglePass:

    def test_empty_store_returns_zero(self):
        store = RetryPlanStore()
        result = execute_retry_pass(store)
        assert result.plans_checked == 0
        assert result.plans_attempted == 0

    def test_single_plan_executed(self):
        store = _make_store_with_plan()
        fake_result = FakeChannelResult(channel="external", delivered=True, detail="ok")
        mock_sender = MagicMock(return_value=fake_result)

        with patch("app.core.notification_sender.get_sender", return_value=mock_sender):
            result = execute_retry_pass(store)

        assert result.plans_attempted == 1
        assert result.plans_succeeded == 1
        assert len(result.results) == 1
        assert result.results[0].success is True

    def test_executed_at_populated(self):
        store = RetryPlanStore()
        result = execute_retry_pass(store)
        assert result.executed_at != ""


# ===========================================================================
# C31-3: Eligibility filtering
# ===========================================================================
class TestC31EligibilityFiltering:

    def test_future_plan_not_eligible(self):
        store = RetryPlanStore(ttl_seconds=9999)
        store.enqueue(
            channel="external",
            reason="timeout",
            reliability_tier="transient_failure",
            retryable=True,
            retry_after_seconds=9999,
            incident="inc_future",
        )
        result = execute_retry_pass(store)
        assert result.plans_checked == 1
        assert result.plans_eligible == 0
        assert result.plans_attempted == 0

    def test_past_plan_eligible(self):
        store = _make_store_with_plan(eligible_seconds=0)
        fake_result = FakeChannelResult(channel="external", delivered=True)
        mock_sender = MagicMock(return_value=fake_result)

        with patch("app.core.notification_sender.get_sender", return_value=mock_sender):
            result = execute_retry_pass(store)

        assert result.plans_eligible >= 1
        assert result.plans_attempted >= 1


# ===========================================================================
# C31-4: Bounded execution (max_executions)
# ===========================================================================
class TestC31BoundedExecution:

    def test_respects_max_executions(self):
        store = RetryPlanStore(ttl_seconds=9999)
        for i in range(10):
            store.enqueue(
                channel=f"ch{i}", reason="timeout",
                reliability_tier="transient_failure",
                retryable=True, retry_after_seconds=0,
                incident=f"inc_{i}",
            )
        fake_result = FakeChannelResult(channel="ext", delivered=True)
        mock_sender = MagicMock(return_value=fake_result)

        with patch("app.core.notification_sender.get_sender", return_value=mock_sender):
            result = execute_retry_pass(store, max_executions=3)

        assert result.plans_attempted == 3

    def test_default_max_executions_applied(self):
        store = RetryPlanStore(ttl_seconds=9999)
        for i in range(10):
            store.enqueue(
                channel=f"ch{i}", reason="timeout",
                reliability_tier="transient_failure",
                retryable=True, retry_after_seconds=0,
                incident=f"inc_{i}",
            )
        fake_result = FakeChannelResult(channel="ext", delivered=True)
        mock_sender = MagicMock(return_value=fake_result)

        with patch("app.core.notification_sender.get_sender", return_value=mock_sender):
            result = execute_retry_pass(store)

        assert result.plans_attempted <= DEFAULT_MAX_EXECUTIONS


# ===========================================================================
# C31-5: Success → mark_executed
# ===========================================================================
class TestC31Success:

    def test_success_marks_executed(self):
        store = _make_store_with_plan()
        fake_result = FakeChannelResult(channel="external", delivered=True, detail="ok")
        mock_sender = MagicMock(return_value=fake_result)

        with patch("app.core.notification_sender.get_sender", return_value=mock_sender):
            result = execute_retry_pass(store)

        assert result.results[0].new_status == "executed"
        # Plan should now be in executed state
        plans = store.list_plans(status="executed")
        assert len(plans) == 1

    def test_success_no_longer_pending(self):
        store = _make_store_with_plan()
        fake_result = FakeChannelResult(channel="external", delivered=True)
        mock_sender = MagicMock(return_value=fake_result)

        with patch("app.core.notification_sender.get_sender", return_value=mock_sender):
            execute_retry_pass(store)

        assert store.pending_count() == 0


# ===========================================================================
# C31-6: Failure → mark_expired
# ===========================================================================
class TestC31Failure:

    def test_failure_marks_expired(self):
        store = _make_store_with_plan()
        fake_result = FakeChannelResult(channel="external", delivered=False, detail="timeout")
        mock_sender = MagicMock(return_value=fake_result)

        with patch("app.core.notification_sender.get_sender", return_value=mock_sender):
            result = execute_retry_pass(store)

        assert result.plans_failed == 1
        assert result.results[0].new_status == "expired"

    def test_failure_no_longer_pending(self):
        store = _make_store_with_plan()
        fake_result = FakeChannelResult(channel="external", delivered=False, detail="fail")
        mock_sender = MagicMock(return_value=fake_result)

        with patch("app.core.notification_sender.get_sender", return_value=mock_sender):
            execute_retry_pass(store)

        assert store.pending_count() == 0


# ===========================================================================
# C31-7: No sender → mark_expired
# ===========================================================================
class TestC31NoSender:

    def test_no_sender_marks_expired(self):
        store = _make_store_with_plan(channel="nonexistent")

        with patch("app.core.notification_sender.get_sender", return_value=None):
            result = execute_retry_pass(store)

        assert result.plans_failed == 1
        assert result.results[0].new_status == "expired"
        assert "no sender" in result.results[0].detail


# ===========================================================================
# C31-8: Fail-closed
# ===========================================================================
class TestC31FailClosed:

    def test_sender_exception_handled(self):
        store = _make_store_with_plan()
        mock_sender = MagicMock(side_effect=RuntimeError("boom"))

        with patch("app.core.notification_sender.get_sender", return_value=mock_sender):
            result = execute_retry_pass(store)

        assert result.plans_failed == 1
        assert "retry_error" in result.results[0].detail

    def test_corrupted_store_handled(self):
        store = MagicMock()
        store.list_plans.side_effect = RuntimeError("corrupted")
        result = execute_retry_pass(store)
        assert len(result.errors) > 0

    def test_no_exception_propagation(self):
        store = "not_a_store"
        result = execute_retry_pass(store)
        assert isinstance(result, RetryPassResult)
        assert len(result.errors) > 0

    def test_partial_success_failure_mix(self):
        store = RetryPlanStore(ttl_seconds=9999)
        store.enqueue(channel="ext", reason="a", reliability_tier="t",
                      retryable=True, retry_after_seconds=0, incident="1")
        store.enqueue(channel="slack", reason="b", reliability_tier="t",
                      retryable=True, retry_after_seconds=0, incident="2")

        call_count = 0

        def mixed_sender(snapshot, routing):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return FakeChannelResult(channel="ext", delivered=True)
            return FakeChannelResult(channel="slack", delivered=False, detail="fail")

        with patch("app.core.notification_sender.get_sender", return_value=mixed_sender):
            result = execute_retry_pass(store)

        assert result.plans_succeeded >= 1
        assert result.plans_failed >= 1


# ===========================================================================
# C31-9: Summary helper
# ===========================================================================
class TestC31Summary:

    def test_summary_from_store(self):
        store = _make_store_with_plan()
        summary = get_retry_summary(store)
        assert summary["pending"] == 1
        assert summary["total"] == 1

    def test_summary_error_safe(self):
        store = MagicMock()
        store.summary.side_effect = RuntimeError("fail")
        summary = get_retry_summary(store)
        assert summary.get("error") is True or summary["total"] == 0


# ===========================================================================
# C31-10: 금지 조항
# ===========================================================================
class TestC31Forbidden:

    def test_no_forbidden_strings(self):
        content = EXECUTOR_PATH.read_text(encoding="utf-8")
        body = content.split('"""', 2)[-1] if '"""' in content else content
        forbidden = [
            'chain_of_thought', 'raw_prompt', 'internal_reasoning',
            'debug_trace', 'agent_analysis', 'error_class',
        ]
        for f in forbidden:
            assert f not in body, f"Forbidden string '{f}'"

    def test_no_daemon_loop(self):
        content = EXECUTOR_PATH.read_text(encoding="utf-8")
        parts = content.split('"""')
        body = parts[-1] if len(parts) >= 3 else content
        assert "while true" not in body.lower()
        assert "daemon" not in body.lower()
        assert "infinite" not in body.lower()

    def test_no_engine_imports(self):
        content = EXECUTOR_PATH.read_text(encoding="utf-8")
        assert "src.kdexter" not in content
        assert "from src" not in content

    def test_no_app_state(self):
        content = EXECUTOR_PATH.read_text(encoding="utf-8")
        assert "app.state" not in content

    def test_reuses_existing_sender(self):
        """Executor must use get_sender from notification_sender."""
        content = EXECUTOR_PATH.read_text(encoding="utf-8")
        assert "get_sender" in content
        assert "notification_sender" in content

    def test_no_new_transport(self):
        content = EXECUTOR_PATH.read_text(encoding="utf-8")
        assert "urllib" not in content
        assert "requests" not in content
        assert "httpx" not in content
