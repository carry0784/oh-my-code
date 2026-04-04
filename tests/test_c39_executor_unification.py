"""
Card C-39: Executor Path Unification — Tests

검수 범위:
  C39-1: execute_single_plan은 public API로 존재
  C39-2: C-31 execute_retry_pass가 execute_single_plan 사용
  C39-3: C-38 auto_retry_orchestrator가 execute_single_plan 사용
  C39-4: C-38 _execute_single 제거 확인
  C39-5: manual/auto 동일 execution semantics
  C39-6: reason_prefix 분리
  C39-7: 기존 테스트 회귀 없음
  C39-8: 금지 조항

Sealed layers 미접촉. 기존 테스트 파일 미수정.
"""

from pathlib import Path
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from app.core.retry_executor import execute_single_plan, RetryAttemptResult
from app.core.retry_plan_store import RetryPlanStore

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXECUTOR_PATH = PROJECT_ROOT / "app" / "core" / "retry_executor.py"
ORCH_PATH = PROJECT_ROOT / "app" / "core" / "auto_retry_orchestrator.py"


@dataclass
class FakeChannelResult:
    channel: str
    delivered: bool
    detail: str = ""


# ===========================================================================
# C39-1: execute_single_plan public API
# ===========================================================================
class TestC39PublicAPI:
    def test_function_exists(self):
        assert callable(execute_single_plan)

    def test_returns_attempt_result(self):
        store = RetryPlanStore()
        store.enqueue(
            channel="ext",
            reason="timeout",
            reliability_tier="transient_failure",
            retryable=True,
            retry_after_seconds=0,
            incident="inc_1",
        )
        plan = store.list_plans()[0]

        fake = FakeChannelResult(channel="ext", delivered=True, detail="ok")
        mock_sender = MagicMock(return_value=fake)

        with patch("app.core.notification_sender.get_sender", return_value=mock_sender):
            result = execute_single_plan(
                plan_store=store,
                plan=plan,
                snapshot=None,
                retry_id=plan["retry_id"],
                channel="ext",
            )

        assert isinstance(result, RetryAttemptResult)
        assert result.success is True

    def test_reason_prefix_default(self):
        store = RetryPlanStore()
        store.enqueue(
            channel="ext",
            reason="timeout",
            reliability_tier="transient_failure",
            retryable=True,
            retry_after_seconds=0,
            incident="inc_1",
        )
        plan = store.list_plans()[0]

        captured_routing = {}

        def capture_sender(snapshot, routing):
            captured_routing.update(routing)
            return FakeChannelResult(channel="ext", delivered=True)

        with patch("app.core.notification_sender.get_sender", return_value=capture_sender):
            execute_single_plan(
                plan_store=store,
                plan=plan,
                snapshot=None,
                retry_id=plan["retry_id"],
                channel="ext",
            )

        assert captured_routing["reason"].startswith("retry:")

    def test_reason_prefix_custom(self):
        store = RetryPlanStore()
        store.enqueue(
            channel="ext",
            reason="timeout",
            reliability_tier="transient_failure",
            retryable=True,
            retry_after_seconds=0,
            incident="inc_2",
        )
        plan = store.list_plans()[0]

        captured_routing = {}

        def capture_sender(snapshot, routing):
            captured_routing.update(routing)
            return FakeChannelResult(channel="ext", delivered=True)

        with patch("app.core.notification_sender.get_sender", return_value=capture_sender):
            execute_single_plan(
                plan_store=store,
                plan=plan,
                snapshot=None,
                retry_id=plan["retry_id"],
                channel="ext",
                reason_prefix="auto_retry",
            )

        assert captured_routing["reason"].startswith("auto_retry:")


# ===========================================================================
# C39-2: C-31 uses execute_single_plan
# ===========================================================================
class TestC39ExecutorUsesShared:
    def test_executor_calls_execute_single_plan(self):
        content = EXECUTOR_PATH.read_text(encoding="utf-8")
        assert "execute_single_plan(" in content
        # Old name should not exist
        assert "def _execute_single_retry(" not in content

    def test_executor_internal_call(self):
        content = EXECUTOR_PATH.read_text(encoding="utf-8")
        assert 'reason_prefix="retry"' in content


# ===========================================================================
# C39-3: C-38 uses execute_single_plan
# ===========================================================================
class TestC39OrchestratorUsesShared:
    def test_orchestrator_imports_shared(self):
        content = ORCH_PATH.read_text(encoding="utf-8")
        assert "execute_single_plan" in content

    def test_orchestrator_calls_shared(self):
        content = ORCH_PATH.read_text(encoding="utf-8")
        assert 'reason_prefix="auto_retry"' in content


# ===========================================================================
# C39-4: _execute_single 제거 확인
# ===========================================================================
class TestC39OldCodeRemoved:
    def test_no_execute_single_in_orchestrator(self):
        content = ORCH_PATH.read_text(encoding="utf-8")
        assert "def _execute_single(" not in content

    def test_no_direct_sender_in_orchestrator(self):
        """C-38 should not directly import get_sender anymore."""
        content = ORCH_PATH.read_text(encoding="utf-8")
        # The only sender usage should be via execute_single_plan
        lines = content.split("\n")
        direct_sender_imports = [
            l
            for l in lines
            if "get_sender" in l
            and "execute_single_plan" not in l
            and not l.strip().startswith("#")
        ]
        assert len(direct_sender_imports) == 0


# ===========================================================================
# C39-5: manual/auto 동일 semantics
# ===========================================================================
class TestC39UnifiedSemantics:
    def test_both_use_same_function(self):
        """C-31과 C-38 모두 execute_single_plan을 사용한다."""
        executor_content = EXECUTOR_PATH.read_text(encoding="utf-8")
        orch_content = ORCH_PATH.read_text(encoding="utf-8")
        assert "execute_single_plan" in executor_content
        assert "execute_single_plan" in orch_content

    def test_mark_executed_on_success(self):
        """Shared helper marks executed on success."""
        store = RetryPlanStore()
        store.enqueue(
            channel="ext",
            reason="timeout",
            reliability_tier="transient_failure",
            retryable=True,
            retry_after_seconds=0,
            incident="inc_test",
        )
        plan = store.list_plans()[0]

        fake = FakeChannelResult(channel="ext", delivered=True)
        with patch(
            "app.core.notification_sender.get_sender", return_value=MagicMock(return_value=fake)
        ):
            result = execute_single_plan(
                store,
                plan,
                None,
                plan["retry_id"],
                "ext",
            )

        assert result.new_status == "executed"
        assert store.pending_count() == 0

    def test_mark_expired_on_failure(self):
        """Shared helper marks expired on failure."""
        store = RetryPlanStore()
        store.enqueue(
            channel="ext",
            reason="timeout",
            reliability_tier="transient_failure",
            retryable=True,
            retry_after_seconds=0,
            incident="inc_fail",
        )
        plan = store.list_plans()[0]

        fake = FakeChannelResult(channel="ext", delivered=False, detail="fail")
        with patch(
            "app.core.notification_sender.get_sender", return_value=MagicMock(return_value=fake)
        ):
            result = execute_single_plan(
                store,
                plan,
                None,
                plan["retry_id"],
                "ext",
            )

        assert result.new_status == "expired"


# ===========================================================================
# C39-6: reason_prefix 분리
# ===========================================================================
class TestC39ReasonPrefix:
    def test_c31_uses_retry_prefix(self):
        content = EXECUTOR_PATH.read_text(encoding="utf-8")
        assert 'reason_prefix="retry"' in content

    def test_c38_uses_auto_retry_prefix(self):
        content = ORCH_PATH.read_text(encoding="utf-8")
        assert 'reason_prefix="auto_retry"' in content


# ===========================================================================
# C39-7: 금지 조항
# ===========================================================================
class TestC39Forbidden:
    def test_no_forbidden_strings_executor(self):
        content = EXECUTOR_PATH.read_text(encoding="utf-8")
        body = content.split('"""', 2)[-1] if '"""' in content else content
        for f in ["chain_of_thought", "raw_prompt", "internal_reasoning"]:
            assert f not in body

    def test_no_forbidden_strings_orchestrator(self):
        content = ORCH_PATH.read_text(encoding="utf-8")
        body = content.split('"""', 2)[-1] if '"""' in content else content
        for f in ["chain_of_thought", "raw_prompt", "internal_reasoning"]:
            assert f not in body

    def test_no_engine(self):
        for path in [EXECUTOR_PATH, ORCH_PATH]:
            content = path.read_text(encoding="utf-8")
            assert "src.kdexter" not in content
