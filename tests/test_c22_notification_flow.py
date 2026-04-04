"""
Card C-22: Notification Execution Flow — Tests

검수 범위:
  C22-1: 모듈 구조
  C22-2: Full flow execution (route → policy → send → persist)
  C22-3: Policy suppression
  C22-4: Policy escalation
  C22-5: Fail-closed at each step
  C22-6: No-policy passthrough
  C22-7: 금지 조항

Sealed layers 미접촉. 기존 테스트 파일 미수정.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.notification_flow import execute_notification_flow, FlowResult
from app.core.alert_policy import AlertPolicy
from app.core.notification_receipt_store import ReceiptStore

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FLOW_PATH = PROJECT_ROOT / "app" / "core" / "notification_flow.py"


def _make_snapshot(**overrides):
    base = {
        "snapshot_version": "C-13",
        "generated_at": "2026-03-24T10:00:00Z",
        "overall_status": "NORMAL",
        "highest_incident": "NONE",
        "active_incidents": [],
        "degraded_reasons": [],
    }
    base.update(overrides)
    return base


# ===========================================================================
# C22-1: 모듈 구조
# ===========================================================================
class TestC22ModuleStructure:
    def test_module_exists(self):
        assert FLOW_PATH.exists()

    def test_flow_result_dataclass(self):
        r = FlowResult()
        assert r.routing_ok is False
        assert r.policy_action == ""
        assert r.channels_attempted == 0
        assert isinstance(r.errors, list)

    def test_flow_result_to_dict(self):
        r = FlowResult(executed_at="2026", routing_ok=True)
        d = r.to_dict()
        assert isinstance(d, dict)
        assert d["routing_ok"] is True

    def test_execute_function_exists(self):
        content = FLOW_PATH.read_text(encoding="utf-8")
        assert "def execute_notification_flow" in content


# ===========================================================================
# C22-2: Full flow execution
# ===========================================================================
class TestC22FullFlow:
    def test_full_flow_with_incident(self):
        """Incident snapshot → route → policy → send → persist."""
        policy = AlertPolicy()
        store = ReceiptStore()
        snapshot = _make_snapshot(
            highest_incident="WORK_FAILED",
            active_incidents=["WORK_FAILED"],
            overall_status="NORMAL",
        )
        result = execute_notification_flow(snapshot, policy, store)
        assert result.routing_ok is True
        assert result.policy_ok is True
        assert result.send_ok is True
        assert result.channels_attempted > 0
        assert result.receipt_id.startswith("RX-")
        assert store.count() == 1

    def test_full_flow_clear(self):
        """Clear snapshot → no channels → no send."""
        policy = AlertPolicy()
        store = ReceiptStore()
        snapshot = _make_snapshot()
        result = execute_notification_flow(snapshot, policy, store)
        assert result.routing_ok is True
        assert result.policy_ok is True
        assert result.policy_suppressed is True
        assert result.channels_attempted == 0

    def test_returns_flow_result(self):
        result = execute_notification_flow(_make_snapshot())
        assert isinstance(result, FlowResult)
        assert result.executed_at != ""


# ===========================================================================
# C22-3: Policy suppression
# ===========================================================================
class TestC22PolicySuppression:
    def test_duplicate_suppressed(self):
        policy = AlertPolicy()
        store = ReceiptStore()
        snapshot = _make_snapshot(
            highest_incident="LOCKDOWN",
            active_incidents=["LOCKDOWN"],
        )
        # First: sends
        r1 = execute_notification_flow(snapshot, policy, store)
        assert r1.channels_attempted > 0
        # Second: suppressed (within cooldown)
        r2 = execute_notification_flow(snapshot, policy, store)
        assert r2.policy_suppressed is True
        assert r2.channels_attempted == 0

    def test_suppressed_flow_does_not_persist(self):
        policy = AlertPolicy()
        store = ReceiptStore()
        snapshot = _make_snapshot(
            highest_incident="WORK_BLOCKED",
            active_incidents=["WORK_BLOCKED"],
        )
        execute_notification_flow(snapshot, policy, store)  # first
        execute_notification_flow(snapshot, policy, store)  # suppressed
        assert store.count() == 1  # only first persisted


# ===========================================================================
# C22-4: Policy escalation
# ===========================================================================
class TestC22PolicyEscalation:
    def test_degraded_escalation(self):
        policy = AlertPolicy(escalation_threshold=2, cooldown_seconds=0)
        store = ReceiptStore()
        snapshot = _make_snapshot(
            highest_incident="DOCTRINE_VIOLATION_x1",
            active_incidents=["DOCTRINE_VIOLATION_x1"],
            degraded_reasons=["venue:binance:stale"],
        )
        execute_notification_flow(snapshot, policy, store)  # low
        r2 = execute_notification_flow(snapshot, policy, store)  # escalated
        assert r2.policy_action == "escalate"
        assert "external" in r2.routing.get("channels", []) or r2.channels_attempted > 0


# ===========================================================================
# C22-5: Fail-closed at each step
# ===========================================================================
class TestC22FailClosed:
    def test_routing_failure_captured(self):
        with patch("app.core.alert_router.route_snapshot", side_effect=RuntimeError("boom")):
            result = execute_notification_flow(_make_snapshot())
            assert result.routing_ok is False
            assert any("routing" in e for e in result.errors)

    def test_send_failure_captured(self):
        with patch(
            "app.core.notification_sender.send_notifications", side_effect=RuntimeError("boom")
        ):
            snapshot = _make_snapshot(
                highest_incident="LOCKDOWN",
                active_incidents=["LOCKDOWN"],
            )
            result = execute_notification_flow(snapshot)
            assert result.routing_ok is True
            assert any("send" in e for e in result.errors)

    def test_persist_failure_captured(self):
        bad_store = MagicMock()
        bad_store.store.side_effect = RuntimeError("db crash")
        snapshot = _make_snapshot(
            highest_incident="WORK_FAILED",
            active_incidents=["WORK_FAILED"],
        )
        result = execute_notification_flow(snapshot, store=bad_store)
        assert result.send_ok is True
        assert any("persist" in e for e in result.errors)

    def test_empty_snapshot_does_not_crash(self):
        result = execute_notification_flow({})
        assert isinstance(result, FlowResult)


# ===========================================================================
# C22-6: No-policy passthrough
# ===========================================================================
class TestC22NoPolicyPassthrough:
    def test_no_policy_sends_directly(self):
        """policy=None → routing 결과 그대로 전송."""
        snapshot = _make_snapshot(
            highest_incident="LOCKDOWN",
            active_incidents=["LOCKDOWN"],
        )
        result = execute_notification_flow(snapshot, policy=None, store=None)
        assert result.routing_ok is True
        assert result.policy_ok is True
        assert result.policy_action == "passthrough"
        assert result.channels_attempted > 0

    def test_no_store_skips_persistence(self):
        snapshot = _make_snapshot(
            highest_incident="WORK_FAILED",
            active_incidents=["WORK_FAILED"],
        )
        result = execute_notification_flow(snapshot, policy=None, store=None)
        assert result.receipt_id == ""


# ===========================================================================
# C22-7: 금지 조항
# ===========================================================================
class TestC22Forbidden:
    def test_no_forbidden_strings(self):
        content = FLOW_PATH.read_text(encoding="utf-8")
        body = content.split('"""', 2)[-1] if '"""' in content else content
        forbidden = [
            "chain_of_thought",
            "raw_prompt",
            "internal_reasoning",
            "debug_trace",
            "agent_analysis",
            "error_class",
        ]
        for f in forbidden:
            assert f not in body, f"Forbidden string '{f}'"

    def test_no_direct_transport(self):
        content = FLOW_PATH.read_text(encoding="utf-8")
        assert "urllib" not in content
        assert "send_webhook" not in content

    def test_no_app_state(self):
        content = FLOW_PATH.read_text(encoding="utf-8")
        assert "app.state" not in content
