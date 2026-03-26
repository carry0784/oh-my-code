"""
Card C-38: Auto Retry Orchestrator — Tests

검수 범위:
  C38-1: 모듈 구조
  C38-2: gate 통과 시 실행
  C38-3: gate 차단 시 미실행
  C38-4: budget 차단 시 skip
  C38-5: metrics 기록
  C38-6: bounded execution
  C38-7: pass lock 관리
  C38-8: fail-closed
  C38-9: 금지 조항

Sealed layers 미접촉. 기존 테스트 파일 미수정.
"""

from pathlib import Path
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from app.core.auto_retry_orchestrator import (
    run_auto_retry,
    AutoRetryResult,
    DEFAULT_MAX_EXECUTIONS,
)
from app.core.retry_plan_store import RetryPlanStore
from app.core.retry_policy_gate import RetryPolicyGate
from app.core.retry_budget import RetryBudget
from app.core.retry_metrics import RetryMetrics

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ORCH_PATH = PROJECT_ROOT / "app" / "core" / "auto_retry_orchestrator.py"


@dataclass
class FakeChannelResult:
    channel: str
    delivered: bool
    detail: str = ""


def _store_with_plans(n=3):
    store = RetryPlanStore(ttl_seconds=9999)
    for i in range(n):
        store.enqueue(channel=f"ch{i}", reason="timeout",
                      reliability_tier="transient_failure",
                      retryable=True, retry_after_seconds=0,
                      incident=f"inc_{i}")
    return store


# ===========================================================================
# C38-1: 모듈 구조
# ===========================================================================
class TestC38ModuleStructure:

    def test_module_exists(self):
        assert ORCH_PATH.exists()

    def test_auto_retry_result(self):
        r = AutoRetryResult(gate_allowed=True)
        assert r.gate_allowed is True

    def test_result_to_dict(self):
        r = AutoRetryResult()
        assert isinstance(r.to_dict(), dict)

    def test_default_max(self):
        assert DEFAULT_MAX_EXECUTIONS == 5


# ===========================================================================
# C38-2: gate 통과 시 실행
# ===========================================================================
class TestC38GatePass:

    def test_no_gate_proceeds(self):
        store = _store_with_plans(2)
        fake = FakeChannelResult(channel="ext", delivered=True)
        mock_sender = MagicMock(return_value=fake)

        with patch("app.core.notification_sender.get_sender", return_value=mock_sender):
            result = run_auto_retry(store)

        assert result.gate_allowed is True
        assert result.plans_attempted >= 1

    def test_gate_pass_executes(self):
        store = _store_with_plans(1)
        gate = RetryPolicyGate()
        fake = FakeChannelResult(channel="ext", delivered=True)
        mock_sender = MagicMock(return_value=fake)

        with patch("app.core.notification_sender.get_sender", return_value=mock_sender):
            result = run_auto_retry(store, gate=gate)

        assert result.gate_allowed is True
        assert result.plans_succeeded >= 1


# ===========================================================================
# C38-3: gate 차단 시 미실행
# ===========================================================================
class TestC38GateBlock:

    def test_disabled_gate_blocks(self):
        store = _store_with_plans()
        gate = RetryPolicyGate(enabled=False)
        result = run_auto_retry(store, gate=gate)
        assert result.gate_allowed is False
        assert result.plans_attempted == 0

    def test_maintenance_gate_blocks(self):
        store = _store_with_plans()
        gate = RetryPolicyGate(maintenance_mode=True)
        result = run_auto_retry(store, gate=gate)
        assert result.gate_allowed is False

    def test_gate_denied_records_metrics(self):
        store = _store_with_plans()
        gate = RetryPolicyGate(enabled=False)
        metrics = RetryMetrics()
        run_auto_retry(store, gate=gate, metrics=metrics)
        assert metrics.summary().total_gate_denied == 1


# ===========================================================================
# C38-4: budget 차단 시 skip
# ===========================================================================
class TestC38BudgetBlock:

    def test_budget_exhausted_skips(self):
        store = _store_with_plans(3)
        budget = RetryBudget(global_budget=0)
        result = run_auto_retry(store, budget=budget)
        assert result.plans_budget_denied >= 1
        assert result.plans_attempted == 0

    def test_channel_budget_exhausted(self):
        store = RetryPlanStore(ttl_seconds=9999)
        store.enqueue(channel="ext", reason="timeout",
                      reliability_tier="transient_failure",
                      retryable=True, retry_after_seconds=0,
                      incident="inc_1")
        budget = RetryBudget(channel_budget=0)
        result = run_auto_retry(store, budget=budget)
        assert result.plans_budget_denied >= 1

    def test_budget_denied_records_metrics(self):
        store = _store_with_plans(1)
        budget = RetryBudget(global_budget=0)
        metrics = RetryMetrics()
        run_auto_retry(store, budget=budget, metrics=metrics)
        assert metrics.summary().total_budget_denied >= 1


# ===========================================================================
# C38-5: metrics 기록
# ===========================================================================
class TestC38Metrics:

    def test_success_recorded(self):
        store = _store_with_plans(1)
        metrics = RetryMetrics()
        fake = FakeChannelResult(channel="ext", delivered=True)
        mock_sender = MagicMock(return_value=fake)

        with patch("app.core.notification_sender.get_sender", return_value=mock_sender):
            run_auto_retry(store, metrics=metrics)

        s = metrics.summary()
        assert s.total_attempts >= 1
        assert s.total_succeeded >= 1

    def test_failure_recorded(self):
        store = _store_with_plans(1)
        metrics = RetryMetrics()
        fake = FakeChannelResult(channel="ext", delivered=False)
        mock_sender = MagicMock(return_value=fake)

        with patch("app.core.notification_sender.get_sender", return_value=mock_sender):
            run_auto_retry(store, metrics=metrics)

        assert metrics.summary().total_failed >= 1

    def test_pass_recorded(self):
        store = _store_with_plans(1)
        metrics = RetryMetrics()
        fake = FakeChannelResult(channel="ext", delivered=True)
        mock_sender = MagicMock(return_value=fake)

        with patch("app.core.notification_sender.get_sender", return_value=mock_sender):
            run_auto_retry(store, metrics=metrics)

        assert metrics.summary().total_passes == 1


# ===========================================================================
# C38-6: bounded execution
# ===========================================================================
class TestC38Bounded:

    def test_max_executions_respected(self):
        store = _store_with_plans(10)
        fake = FakeChannelResult(channel="ext", delivered=True)
        mock_sender = MagicMock(return_value=fake)

        with patch("app.core.notification_sender.get_sender", return_value=mock_sender):
            result = run_auto_retry(store, max_executions=2)

        assert result.plans_attempted == 2


# ===========================================================================
# C38-7: pass lock 관리
# ===========================================================================
class TestC38PassLock:

    def test_pass_lock_released_on_success(self):
        store = _store_with_plans(1)
        gate = RetryPolicyGate()
        fake = FakeChannelResult(channel="ext", delivered=True)
        mock_sender = MagicMock(return_value=fake)

        with patch("app.core.notification_sender.get_sender", return_value=mock_sender):
            run_auto_retry(store, gate=gate)

        # Lock should be released
        assert gate.get_state()["pass_in_progress"] is False

    def test_pass_lock_released_on_error(self):
        store = _store_with_plans(1)
        gate = RetryPolicyGate()
        mock_sender = MagicMock(side_effect=RuntimeError("boom"))

        with patch("app.core.notification_sender.get_sender", return_value=mock_sender):
            run_auto_retry(store, gate=gate)

        assert gate.get_state()["pass_in_progress"] is False


# ===========================================================================
# C38-8: fail-closed
# ===========================================================================
class TestC38FailClosed:

    def test_corrupted_store_handled(self):
        result = run_auto_retry("not_a_store")
        assert isinstance(result, AutoRetryResult)
        assert len(result.errors) > 0

    def test_sender_error_handled(self):
        store = _store_with_plans(1)
        mock_sender = MagicMock(side_effect=RuntimeError("fail"))

        with patch("app.core.notification_sender.get_sender", return_value=mock_sender):
            result = run_auto_retry(store)

        assert result.plans_failed >= 1

    def test_no_exception_propagation(self):
        result = run_auto_retry(None)
        assert isinstance(result, AutoRetryResult)


# ===========================================================================
# C38-9: 금지 조항
# ===========================================================================
class TestC38Forbidden:

    def test_no_forbidden_strings(self):
        content = ORCH_PATH.read_text(encoding="utf-8")
        body = content.split('"""', 2)[-1] if '"""' in content else content
        forbidden = [
            'chain_of_thought', 'raw_prompt', 'internal_reasoning',
            'debug_trace',
        ]
        for f in forbidden:
            assert f not in body, f"Forbidden string '{f}'"

    def test_no_infinite_loop(self):
        content = ORCH_PATH.read_text(encoding="utf-8")
        parts = content.split('"""')
        body = parts[-1] if len(parts) >= 3 else content
        assert "while true" not in body.lower()
        assert "run_forever" not in body.lower()

    def test_no_daemon(self):
        content = ORCH_PATH.read_text(encoding="utf-8")
        parts = content.split('"""')
        body = parts[-1] if len(parts) >= 3 else content
        assert "daemon" not in body.lower()
        assert "threading" not in body.lower()

    def test_no_engine(self):
        content = ORCH_PATH.read_text(encoding="utf-8")
        assert "src.kdexter" not in content
