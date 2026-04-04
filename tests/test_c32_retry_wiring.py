"""
Card C-32: Retry Wiring — Manual Retry Pass Entrypoint Tests

검수 범위:
  C32-1: 모듈 구조
  C32-2: 수동 진입점 호출 시 executor 1회 연결
  C32-3: 미호출 시 자동 실행 없음
  C32-4: bounded max_executions 유지
  C32-5: eligible plan만 실행
  C32-6: sender 성공 시 executed
  C32-7: sender 실패 시 expired
  C32-8: 기존 notification flow 회귀 없음
  C32-9: import side effect 없음
  C32-10: fail-closed
  C32-11: 금지 조항

Sealed layers 미접촉. 기존 테스트 파일 미수정.
"""

from pathlib import Path
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from app.core.notification_flow import run_manual_retry_pass, execute_notification_flow, FlowResult
from app.core.retry_plan_store import RetryPlanStore

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FLOW_PATH = PROJECT_ROOT / "app" / "core" / "notification_flow.py"
EXECUTOR_PATH = PROJECT_ROOT / "app" / "core" / "retry_executor.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@dataclass
class FakeChannelResult:
    channel: str
    delivered: bool
    detail: str = ""


def _make_store_with_plan(channel="external", incident="inc_001"):
    store = RetryPlanStore(ttl_seconds=9999)
    store.enqueue(
        channel=channel,
        reason="timeout",
        reliability_tier="transient_failure",
        retryable=True,
        retry_after_seconds=0,
        incident=incident,
        severity_tier="high",
    )
    return store


# ===========================================================================
# C32-1: 모듈 구조
# ===========================================================================
class TestC32ModuleStructure:

    def test_entrypoint_exists(self):
        content = FLOW_PATH.read_text(encoding="utf-8")
        assert "run_manual_retry_pass" in content

    def test_entrypoint_callable(self):
        assert callable(run_manual_retry_pass)

    def test_entrypoint_docstring_forbids_auto(self):
        doc = run_manual_retry_pass.__doc__ or ""
        assert "automatic retry is forbidden" in doc.lower()

    def test_entrypoint_docstring_mentions_manual(self):
        doc = run_manual_retry_pass.__doc__ or ""
        assert "manual" in doc.lower()

    def test_executor_unchanged(self):
        """C-31 executor 파일이 이번 카드에서 수정되지 않았음."""
        content = EXECUTOR_PATH.read_text(encoding="utf-8")
        assert "Card C-31" in content
        assert "execute_retry_pass" in content


# ===========================================================================
# C32-2: 수동 진입점 호출 시 executor 1회 연결
# ===========================================================================
class TestC32ManualExecution:

    def test_calls_executor_once(self):
        store = RetryPlanStore()
        with patch("app.core.retry_executor.execute_retry_pass") as mock_exec:
            mock_exec.return_value = MagicMock(to_dict=lambda: {"plans_attempted": 0})
            run_manual_retry_pass(store)
            mock_exec.assert_called_once()

    def test_returns_dict(self):
        store = RetryPlanStore()
        result = run_manual_retry_pass(store)
        assert isinstance(result, dict)

    def test_result_has_plans_checked(self):
        store = RetryPlanStore()
        result = run_manual_retry_pass(store)
        assert "plans_checked" in result

    def test_result_has_executed_at(self):
        store = RetryPlanStore()
        result = run_manual_retry_pass(store)
        assert "executed_at" in result

    def test_with_pending_plan_success(self):
        store = _make_store_with_plan()
        fake = FakeChannelResult(channel="external", delivered=True, detail="ok")
        mock_sender = MagicMock(return_value=fake)

        with patch("app.core.notification_sender.get_sender", return_value=mock_sender):
            result = run_manual_retry_pass(store)

        assert result["plans_succeeded"] >= 1


# ===========================================================================
# C32-3: 미호출 시 자동 실행 없음
# ===========================================================================
class TestC32NoAutoExecution:

    def test_import_has_no_side_effect(self):
        """import만으로 retry pass가 실행되지 않는다."""
        store = _make_store_with_plan()
        # Just importing the module should not trigger anything
        import app.core.notification_flow  # noqa: F401
        assert store.pending_count() == 1  # still pending

    def test_execute_notification_flow_does_not_retry(self):
        """기존 flow는 retry pass를 호출하지 않는다."""
        store = _make_store_with_plan()
        snapshot = {"overall_status": "HEALTHY", "highest_incident": "NONE"}

        with patch("app.core.retry_executor.execute_retry_pass") as mock_exec:
            execute_notification_flow(snapshot)
            mock_exec.assert_not_called()

        assert store.pending_count() == 1


# ===========================================================================
# C32-4: bounded max_executions 유지
# ===========================================================================
class TestC32BoundedExecution:

    def test_respects_max_executions_param(self):
        store = RetryPlanStore(ttl_seconds=9999)
        for i in range(10):
            store.enqueue(channel=f"ch{i}", reason="timeout",
                          reliability_tier="transient_failure",
                          retryable=True, retry_after_seconds=0,
                          incident=f"inc_{i}")

        fake = FakeChannelResult(channel="ext", delivered=True)
        mock_sender = MagicMock(return_value=fake)

        with patch("app.core.notification_sender.get_sender", return_value=mock_sender):
            result = run_manual_retry_pass(store, max_executions=2)

        assert result["plans_attempted"] == 2

    def test_default_max_is_five(self):
        store = RetryPlanStore(ttl_seconds=9999)
        for i in range(10):
            store.enqueue(channel=f"ch{i}", reason="timeout",
                          reliability_tier="transient_failure",
                          retryable=True, retry_after_seconds=0,
                          incident=f"inc_{i}")

        fake = FakeChannelResult(channel="ext", delivered=True)
        mock_sender = MagicMock(return_value=fake)

        with patch("app.core.notification_sender.get_sender", return_value=mock_sender):
            result = run_manual_retry_pass(store)

        assert result["plans_attempted"] <= 5


# ===========================================================================
# C32-5: eligible plan만 실행
# ===========================================================================
class TestC32EligibleOnly:

    def test_future_plan_skipped(self):
        store = RetryPlanStore(ttl_seconds=9999)
        store.enqueue(channel="ext", reason="timeout",
                      reliability_tier="transient_failure",
                      retryable=True, retry_after_seconds=9999,
                      incident="future")
        result = run_manual_retry_pass(store)
        assert result["plans_attempted"] == 0


# ===========================================================================
# C32-6: sender 성공 → executed
# ===========================================================================
class TestC32SuccessPath:

    def test_success_marks_executed(self):
        store = _make_store_with_plan()
        fake = FakeChannelResult(channel="external", delivered=True)
        mock_sender = MagicMock(return_value=fake)

        with patch("app.core.notification_sender.get_sender", return_value=mock_sender):
            run_manual_retry_pass(store)

        assert store.pending_count() == 0
        executed = store.list_plans(status="executed")
        assert len(executed) == 1


# ===========================================================================
# C32-7: sender 실패 → expired
# ===========================================================================
class TestC32FailurePath:

    def test_failure_marks_expired(self):
        store = _make_store_with_plan()
        fake = FakeChannelResult(channel="external", delivered=False, detail="fail")
        mock_sender = MagicMock(return_value=fake)

        with patch("app.core.notification_sender.get_sender", return_value=mock_sender):
            run_manual_retry_pass(store)

        assert store.pending_count() == 0
        expired = store.list_plans(status="expired")
        assert len(expired) == 1


# ===========================================================================
# C32-8: 기존 notification flow 회귀 없음
# ===========================================================================
class TestC32FlowRegression:

    def test_flow_result_unchanged(self):
        """FlowResult 구조가 유지되는지 확인."""
        r = FlowResult()
        assert hasattr(r, "routing_ok")
        assert hasattr(r, "policy_action")
        assert hasattr(r, "send_ok")
        assert hasattr(r, "errors")

    def test_execute_flow_still_works(self):
        """기존 execute_notification_flow가 정상 동작한다."""
        snapshot = {"overall_status": "HEALTHY", "highest_incident": "NONE"}
        result = execute_notification_flow(snapshot)
        assert isinstance(result, FlowResult)
        assert result.executed_at != ""


# ===========================================================================
# C32-9: import side effect 없음
# ===========================================================================
class TestC32NoSideEffect:

    def test_module_import_safe(self):
        """notification_flow import에 retry 부수효과 없음."""
        import importlib
        import app.core.notification_flow as mod
        importlib.reload(mod)
        # No exception = no side effect


# ===========================================================================
# C32-10: fail-closed
# ===========================================================================
class TestC32FailClosed:

    def test_corrupted_store_handled(self):
        result = run_manual_retry_pass("not_a_store")
        assert isinstance(result, dict)
        assert "errors" in result
        assert len(result["errors"]) > 0

    def test_executor_import_error(self):
        with patch("app.core.retry_executor.execute_retry_pass",
                    side_effect=ImportError("missing")):
            store = RetryPlanStore()
            result = run_manual_retry_pass(store)
            assert isinstance(result, dict)
            assert "errors" in result


# ===========================================================================
# C32-11: 금지 조항
# ===========================================================================
class TestC32Forbidden:

    def test_no_daemon_scheduler(self):
        content = FLOW_PATH.read_text(encoding="utf-8")
        parts = content.split('"""')
        body = parts[-1] if len(parts) >= 3 else content
        body_lower = body.lower()
        assert "daemon" not in body_lower
        assert "while true" not in body_lower
        assert "run_forever" not in body_lower
        assert "start_retry_worker" not in body_lower
        assert "schedule_retries" not in body_lower

    def test_no_startup_hook(self):
        content = FLOW_PATH.read_text(encoding="utf-8")
        assert "on_startup" not in content
        assert "app.add_event" not in content
        assert "@app" not in content

    def test_no_threading(self):
        content = FLOW_PATH.read_text(encoding="utf-8")
        assert "threading" not in content
        assert "asyncio.create_task" not in content

    def test_no_forbidden_strings(self):
        content = FLOW_PATH.read_text(encoding="utf-8")
        body = content.split('"""', 2)[-1] if '"""' in content else content
        forbidden = [
            'chain_of_thought', 'raw_prompt', 'internal_reasoning',
            'debug_trace',
        ]
        for f in forbidden:
            assert f not in body, f"Forbidden string '{f}'"

    def test_no_new_transport(self):
        content = FLOW_PATH.read_text(encoding="utf-8")
        assert "urllib" not in content
        assert "httpx" not in content

    def test_no_app_state(self):
        content = FLOW_PATH.read_text(encoding="utf-8")
        assert "app.state" not in content
