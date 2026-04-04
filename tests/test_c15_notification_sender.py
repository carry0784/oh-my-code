"""
Card C-15: Notification Sender Bridge — Tests

검수 범위:
  C15-1: 모듈 구조 및 데이터 모델
  C15-2: sender registry
  C15-3: send_notifications() 디스패치 로직
  C15-4: built-in senders (console, snapshot, external)
  C15-5: fail-closed 동작
  C15-6: 금지 조항 확인

Sealed layers 미접촉. 기존 테스트 파일 미수정.
"""

from pathlib import Path

import pytest

from app.core.notification_sender import (
    ChannelResult,
    NotificationReceipt,
    register_sender,
    get_sender,
    send_notifications,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SENDER_PATH = PROJECT_ROOT / "app" / "core" / "notification_sender.py"


# ===========================================================================
# C15-1: 모듈 구조 및 데이터 모델
# ===========================================================================
class TestC15ModuleStructure:
    def test_module_exists(self):
        assert SENDER_PATH.exists()

    def test_channel_result_dataclass(self):
        r = ChannelResult(channel="test", delivered=True, detail="ok")
        assert r.channel == "test"
        assert r.delivered is True
        assert r.detail == "ok"

    def test_notification_receipt_dataclass(self):
        nr = NotificationReceipt()
        assert nr.channels_attempted == 0
        assert nr.channels_delivered == 0
        assert isinstance(nr.results, list)

    def test_send_notifications_function_exists(self):
        content = SENDER_PATH.read_text(encoding="utf-8")
        assert "def send_notifications" in content


# ===========================================================================
# C15-2: Sender Registry
# ===========================================================================
class TestC15Registry:
    def test_console_sender_registered(self):
        assert get_sender("console") is not None

    def test_snapshot_sender_registered(self):
        assert get_sender("snapshot") is not None

    def test_external_sender_registered(self):
        assert get_sender("external") is not None

    def test_unknown_channel_returns_none(self):
        assert get_sender("nonexistent_channel_xyz") is None

    def test_custom_sender_registration(self):
        def my_sender(snapshot, routing):
            return ChannelResult(channel="custom", delivered=True, detail="custom ok")

        register_sender("custom_test", my_sender)
        assert get_sender("custom_test") is my_sender


# ===========================================================================
# C15-3: send_notifications() 디스패치
# ===========================================================================
class TestC15Dispatch:
    def _make_snapshot(self):
        return {
            "snapshot_version": "C-13",
            "generated_at": "2026-03-24T10:00:00Z",
            "overall_status": "NORMAL",
            "highest_incident": "NONE",
        }

    def test_returns_receipt(self):
        routing = {"channels": [], "severity_tier": "clear"}
        receipt = send_notifications(self._make_snapshot(), routing)
        assert isinstance(receipt, NotificationReceipt)

    def test_clear_routing_no_channels(self):
        routing = {"channels": [], "severity_tier": "clear"}
        receipt = send_notifications(self._make_snapshot(), routing)
        assert receipt.channels_attempted == 0
        assert receipt.channels_delivered == 0
        assert len(receipt.results) == 0

    def test_dispatches_to_all_channels(self):
        routing = {"channels": ["console", "snapshot"], "severity_tier": "high"}
        receipt = send_notifications(self._make_snapshot(), routing)
        assert receipt.channels_attempted == 2
        assert len(receipt.results) == 2

    def test_receipt_has_attempted_at(self):
        routing = {"channels": ["console"], "severity_tier": "high"}
        receipt = send_notifications(self._make_snapshot(), routing)
        assert receipt.attempted_at != ""

    def test_receipt_has_severity_tier(self):
        routing = {"channels": ["console"], "severity_tier": "critical"}
        receipt = send_notifications(self._make_snapshot(), routing)
        assert receipt.severity_tier == "critical"

    def test_unregistered_channel_fails_gracefully(self):
        routing = {"channels": ["nonexistent_abc"], "severity_tier": "low"}
        receipt = send_notifications(self._make_snapshot(), routing)
        assert receipt.channels_attempted == 1
        assert receipt.channels_delivered == 0
        assert receipt.results[0].delivered is False
        assert "no sender registered" in receipt.results[0].detail


# ===========================================================================
# C15-4: Built-in senders
# ===========================================================================
class TestC15BuiltinSenders:
    def _make_snapshot(self):
        return {
            "snapshot_version": "C-13",
            "generated_at": "2026-03-24T10:00:00Z",
            "overall_status": "NORMAL",
            "highest_incident": "LOCKDOWN",
        }

    def test_console_sender_succeeds(self):
        routing = {"channels": ["console"], "severity_tier": "critical"}
        receipt = send_notifications(self._make_snapshot(), routing)
        console_result = receipt.results[0]
        assert console_result.channel == "console"
        assert console_result.delivered is True
        assert "[ALERT]" in console_result.detail

    def test_snapshot_sender_succeeds(self):
        routing = {"channels": ["snapshot"], "severity_tier": "low"}
        receipt = send_notifications(self._make_snapshot(), routing)
        snap_result = receipt.results[0]
        assert snap_result.channel == "snapshot"
        assert snap_result.delivered is True
        assert "C-13" in snap_result.detail

    def test_external_sender_stub_not_delivered(self):
        routing = {"channels": ["external"], "severity_tier": "critical"}
        receipt = send_notifications(self._make_snapshot(), routing)
        ext_result = receipt.results[0]
        assert ext_result.channel == "external"
        assert ext_result.delivered is False
        assert "stub" in ext_result.detail or "webhook delivery failed" in ext_result.detail


# ===========================================================================
# C15-5: Fail-closed 동작
# ===========================================================================
class TestC15FailClosed:
    def test_sender_exception_captured(self):
        """Sender가 예외를 발생시켜도 receipt에 기록된다."""

        def failing_sender(snapshot, routing):
            raise RuntimeError("test error")

        register_sender("failing_test_ch", failing_sender)
        routing = {"channels": ["failing_test_ch"], "severity_tier": "high"}
        receipt = send_notifications({}, routing)
        assert receipt.channels_attempted == 1
        assert receipt.channels_delivered == 0
        assert "sender error" in receipt.results[0].detail

    def test_no_exception_propagated(self):
        """send_notifications는 절대 예외를 전파하지 않는다."""

        def bad_sender(snapshot, routing):
            raise ValueError("boom")

        register_sender("bad_test_ch", bad_sender)
        routing = {"channels": ["bad_test_ch"], "severity_tier": "critical"}
        # Should not raise
        receipt = send_notifications({}, routing)
        assert isinstance(receipt, NotificationReceipt)


# ===========================================================================
# C15-6: 금지 조항 확인
# ===========================================================================
class TestC15Forbidden:
    def test_no_forbidden_strings(self):
        content = SENDER_PATH.read_text(encoding="utf-8")
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

    def test_no_hardcoded_transport(self):
        """실제 외부 전송 라이브러리 하드코딩 없음."""
        content = SENDER_PATH.read_text(encoding="utf-8")
        transport_libs = [
            "import requests",
            "import httpx",
            "import smtplib",
            "import discord",
            "import slack",
        ]
        for lib in transport_libs:
            assert lib not in content, f"Transport lib '{lib}' hardcoded"

    def test_no_state_mutation(self):
        content = SENDER_PATH.read_text(encoding="utf-8")
        assert "app.state" not in content
