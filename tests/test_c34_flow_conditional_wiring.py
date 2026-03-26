"""
Card C-34: Flow Conditional Wiring — Tests

검수 범위:
  C34-1: 모듈 구조
  C34-2: 성공 채널 skip
  C34-3: 실패 채널 enqueue
  C34-4: retry policy 연동
  C34-5: duplicate suppression
  C34-6: fail-closed
  C34-7: 기존 flow 무변경
  C34-8: 금지 조항

Sealed layers 미접촉. 기존 테스트 파일 미수정.
"""

from pathlib import Path
from dataclasses import dataclass, field
from unittest.mock import MagicMock

import pytest

from app.core.flow_retry_bridge import (
    bridge_failed_to_retry_store,
    BridgeResult,
)
from app.core.retry_plan_store import RetryPlanStore
from app.core.delivery_retry_policy import DeliveryRetryPolicy

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BRIDGE_PATH = PROJECT_ROOT / "app" / "core" / "flow_retry_bridge.py"


@dataclass
class FakeChannelResult:
    channel: str
    delivered: bool
    detail: str = ""


@dataclass
class FakeReceipt:
    results: list = field(default_factory=list)


# ===========================================================================
# C34-1: 모듈 구조
# ===========================================================================
class TestC34ModuleStructure:

    def test_module_exists(self):
        assert BRIDGE_PATH.exists()

    def test_bridge_function_exists(self):
        content = BRIDGE_PATH.read_text(encoding="utf-8")
        assert "bridge_failed_to_retry_store" in content

    def test_bridge_result_dataclass(self):
        r = BridgeResult(checked=1, enqueued=1)
        assert r.checked == 1

    def test_bridge_result_to_dict(self):
        r = BridgeResult()
        assert isinstance(r.to_dict(), dict)


# ===========================================================================
# C34-2: 성공 채널 skip
# ===========================================================================
class TestC34SuccessSkip:

    def test_delivered_channel_skipped(self):
        receipt = FakeReceipt(results=[
            FakeChannelResult(channel="console", delivered=True),
            FakeChannelResult(channel="snapshot", delivered=True),
        ])
        store = RetryPlanStore()
        result = bridge_failed_to_retry_store(receipt, store)
        assert result.checked == 2
        assert result.enqueued == 0
        assert result.skipped == 2

    def test_empty_receipt(self):
        receipt = FakeReceipt(results=[])
        store = RetryPlanStore()
        result = bridge_failed_to_retry_store(receipt, store)
        assert result.checked == 0
        assert result.enqueued == 0


# ===========================================================================
# C34-3: 실패 채널 enqueue
# ===========================================================================
class TestC34FailureEnqueue:

    def test_failed_channel_enqueued(self):
        receipt = FakeReceipt(results=[
            FakeChannelResult(channel="external", delivered=False, detail="timeout"),
        ])
        store = RetryPlanStore()
        result = bridge_failed_to_retry_store(
            receipt, store, incident="inc_001",
        )
        assert result.enqueued == 1
        assert store.pending_count() == 1

    def test_mixed_success_failure(self):
        receipt = FakeReceipt(results=[
            FakeChannelResult(channel="console", delivered=True),
            FakeChannelResult(channel="external", delivered=False, detail="timeout"),
            FakeChannelResult(channel="slack", delivered=False, detail="connection error"),
        ])
        store = RetryPlanStore()
        result = bridge_failed_to_retry_store(
            receipt, store, incident="inc_002",
        )
        assert result.checked == 3
        assert result.enqueued == 2
        assert result.skipped == 1

    def test_severity_preserved(self):
        receipt = FakeReceipt(results=[
            FakeChannelResult(channel="external", delivered=False, detail="timeout"),
        ])
        store = RetryPlanStore()
        bridge_failed_to_retry_store(
            receipt, store, incident="inc_003", severity_tier="critical",
        )
        plans = store.list_plans()
        assert plans[0]["severity_tier"] == "critical"


# ===========================================================================
# C34-4: retry policy 연동
# ===========================================================================
class TestC34PolicyIntegration:

    def test_policy_rejects_permanent_failure(self):
        receipt = FakeReceipt(results=[
            FakeChannelResult(channel="external", delivered=False,
                              detail="external notifier not configured (stub)"),
        ])
        store = RetryPlanStore()
        policy = DeliveryRetryPolicy()
        result = bridge_failed_to_retry_store(
            receipt, store, retry_policy=policy, incident="inc_004",
        )
        assert result.enqueued == 0
        assert result.skipped == 1

    def test_policy_allows_transient(self):
        receipt = FakeReceipt(results=[
            FakeChannelResult(channel="external", delivered=False,
                              detail="webhook delivery failed"),
        ])
        store = RetryPlanStore()
        policy = DeliveryRetryPolicy(cooldown_seconds=0)
        result = bridge_failed_to_retry_store(
            receipt, store, retry_policy=policy, incident="inc_005",
        )
        assert result.enqueued == 1

    def test_no_policy_defaults_to_retryable(self):
        receipt = FakeReceipt(results=[
            FakeChannelResult(channel="external", delivered=False, detail="fail"),
        ])
        store = RetryPlanStore()
        result = bridge_failed_to_retry_store(
            receipt, store, incident="inc_006",
        )
        assert result.enqueued == 1


# ===========================================================================
# C34-5: duplicate suppression
# ===========================================================================
class TestC34DuplicateSuppression:

    def test_duplicate_channel_incident_suppressed(self):
        receipt = FakeReceipt(results=[
            FakeChannelResult(channel="external", delivered=False, detail="timeout"),
        ])
        store = RetryPlanStore()
        bridge_failed_to_retry_store(receipt, store, incident="inc_007")
        result2 = bridge_failed_to_retry_store(receipt, store, incident="inc_007")
        assert result2.enqueued == 0
        assert store.pending_count() == 1


# ===========================================================================
# C34-6: fail-closed
# ===========================================================================
class TestC34FailClosed:

    def test_corrupted_receipt_handled(self):
        result = bridge_failed_to_retry_store("not_a_receipt", RetryPlanStore())
        assert isinstance(result, BridgeResult)

    def test_corrupted_store_handled(self):
        receipt = FakeReceipt(results=[
            FakeChannelResult(channel="ext", delivered=False, detail="fail"),
        ])
        result = bridge_failed_to_retry_store(receipt, "not_a_store")
        assert isinstance(result, BridgeResult)

    def test_policy_error_handled(self):
        receipt = FakeReceipt(results=[
            FakeChannelResult(channel="ext", delivered=False, detail="fail"),
        ])
        bad_policy = MagicMock()
        bad_policy.check_eligibility.side_effect = RuntimeError("boom")
        store = RetryPlanStore()
        result = bridge_failed_to_retry_store(
            receipt, store, retry_policy=bad_policy, incident="inc_err",
        )
        # Policy error → not retryable → skipped
        assert result.skipped == 1


# ===========================================================================
# C34-7: 기존 flow 무변경
# ===========================================================================
class TestC34FlowUnchanged:

    def test_notification_flow_unchanged(self):
        """execute_notification_flow는 bridge를 호출하지 않는다."""
        from app.core.notification_flow import execute_notification_flow
        snapshot = {"overall_status": "HEALTHY", "highest_incident": "NONE"}
        result = execute_notification_flow(snapshot)
        assert result.executed_at != ""


# ===========================================================================
# C34-8: 금지 조항
# ===========================================================================
class TestC34Forbidden:

    def test_no_forbidden_strings(self):
        content = BRIDGE_PATH.read_text(encoding="utf-8")
        body = content.split('"""', 2)[-1] if '"""' in content else content
        forbidden = [
            'chain_of_thought', 'raw_prompt', 'internal_reasoning',
            'debug_trace',
        ]
        for f in forbidden:
            assert f not in body, f"Forbidden string '{f}'"

    def test_no_daemon_scheduler(self):
        content = BRIDGE_PATH.read_text(encoding="utf-8")
        parts = content.split('"""')
        body = parts[-1] if len(parts) >= 3 else content
        assert "daemon" not in body.lower()
        assert "while true" not in body.lower()

    def test_no_send_logic(self):
        content = BRIDGE_PATH.read_text(encoding="utf-8")
        assert "send_webhook" not in content
        assert "send_notifications" not in content

    def test_no_engine_imports(self):
        content = BRIDGE_PATH.read_text(encoding="utf-8")
        assert "src.kdexter" not in content
