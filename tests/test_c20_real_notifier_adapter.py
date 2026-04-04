"""
Card C-20: Real Notifier Adapter (Discord/Webhook) — Tests

검수 범위:
  C20-1: real_notifier_adapter.py 모듈 구조
  C20-2: send_webhook() 동작
  C20-3: format_discord_payload() 형식
  C20-4: _send_external() 통합 — webhook 유무에 따른 분기
  C20-5: config 설정
  C20-6: 기존 sender 보존
  C20-7: 금지 조항 확인

Sealed layers 미접촉. 기존 테스트 파일 미수정.
"""

import sys
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_STUB_MODULES = [
    "app.core.database",
    "app.models",
    "app.models.order",
    "app.models.position",
    "app.models.signal",
    "app.models.trade",
    "app.models.asset_snapshot",
    "app.exchanges",
    "app.exchanges.factory",
    "app.exchanges.base",
    "app.exchanges.binance",
    "app.services",
    "app.services.order_service",
    "app.services.position_service",
    "app.services.signal_service",
    "ccxt",
    "ccxt.async_support",
    "redis",
    "celery",
    "asyncpg",
]
for mod_name in _STUB_MODULES:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

sys.modules["app.models.position"].Position = MagicMock()
sys.modules["app.models.position"].PositionSide = MagicMock()
sys.modules["app.models.order"].Order = MagicMock()
sys.modules["app.models.order"].OrderStatus = MagicMock()
sys.modules["app.models.trade"].Trade = MagicMock()
sys.modules["app.models.signal"].Signal = MagicMock()
sys.modules["app.core.database"].Base = MagicMock()
sys.modules["app.core.database"].get_db = MagicMock()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ADAPTER_PATH = PROJECT_ROOT / "app" / "core" / "real_notifier_adapter.py"
SENDER_PATH = PROJECT_ROOT / "app" / "core" / "notification_sender.py"
CONFIG_PATH = PROJECT_ROOT / "app" / "core" / "config.py"

from app.core.real_notifier_adapter import send_webhook, format_discord_payload
from app.core.notification_sender import send_notifications, ChannelResult


# ===========================================================================
# C20-1: 모듈 구조
# ===========================================================================
class TestC20ModuleStructure:
    def test_adapter_module_exists(self):
        assert ADAPTER_PATH.exists()

    def test_send_webhook_function_exists(self):
        content = ADAPTER_PATH.read_text(encoding="utf-8")
        assert "def send_webhook" in content

    def test_format_discord_payload_exists(self):
        content = ADAPTER_PATH.read_text(encoding="utf-8")
        assert "def format_discord_payload" in content

    def test_uses_stdlib_only(self):
        content = ADAPTER_PATH.read_text(encoding="utf-8")
        assert "import requests" not in content
        assert "import httpx" not in content
        assert "urllib.request" in content


# ===========================================================================
# C20-2: send_webhook()
# ===========================================================================
class TestC20SendWebhook:
    def test_empty_url_returns_false(self):
        assert send_webhook("", {"test": True}) is False

    def test_none_url_returns_false(self):
        assert send_webhook(None, {"test": True}) is False

    def test_invalid_url_returns_false(self):
        """존재하지 않는 URL → False (timeout/connection error)."""
        result = send_webhook("http://192.0.2.1:1/nonexistent", {"test": True})
        assert result is False

    def test_never_raises(self):
        """어떤 입력이든 예외를 전파하지 않는다."""
        assert send_webhook("not-a-url", {}) is False
        assert send_webhook("http://[invalid", {"a": 1}) is False

    def test_timeout_configured(self):
        content = ADAPTER_PATH.read_text(encoding="utf-8")
        assert "_WEBHOOK_TIMEOUT_S" in content
        assert "timeout=" in content


# ===========================================================================
# C20-3: format_discord_payload()
# ===========================================================================
class TestC20DiscordPayload:
    def test_returns_dict_with_content(self):
        snapshot = {"overall_status": "NORMAL", "highest_incident": "NONE"}
        payload = format_discord_payload(snapshot)
        assert isinstance(payload, dict)
        assert "content" in payload

    def test_includes_status(self):
        payload = format_discord_payload(
            {"overall_status": "LOCKDOWN", "highest_incident": "LOCKDOWN"}
        )
        assert "LOCKDOWN" in payload["content"]

    def test_includes_incident(self):
        payload = format_discord_payload(
            {"overall_status": "NORMAL", "highest_incident": "LOOP_EXCEEDED"}
        )
        assert "LOOP_EXCEEDED" in payload["content"]

    def test_includes_triage_if_present(self):
        payload = format_discord_payload(
            {
                "overall_status": "NORMAL",
                "highest_incident": "NONE",
                "triage_top": "Check loop ceilings",
            }
        )
        assert "Check loop ceilings" in payload["content"]

    def test_handles_empty_snapshot(self):
        payload = format_discord_payload({})
        assert "content" in payload


# ===========================================================================
# C20-4: _send_external() 통합
# ===========================================================================
class TestC20ExternalIntegration:
    def test_no_webhook_returns_not_configured(self):
        """webhook URL 미설정 시 not configured."""
        mock_settings = MagicMock(notifier_webhook_url="")
        with patch("app.core.config.settings", mock_settings):
            from app.core.notification_sender import _send_external

            result = _send_external({"overall_status": "NORMAL"}, {})
            assert result.delivered is False
            assert "not configured" in result.detail

    def test_sender_references_adapter(self):
        """sender가 real_notifier_adapter를 참조한다."""
        content = SENDER_PATH.read_text(encoding="utf-8")
        assert "real_notifier_adapter" in content

    def test_sender_references_webhook_url(self):
        content = SENDER_PATH.read_text(encoding="utf-8")
        assert "notifier_webhook_url" in content


# ===========================================================================
# C20-5: Config
# ===========================================================================
class TestC20Config:
    def test_notifier_webhook_url_setting(self):
        content = CONFIG_PATH.read_text(encoding="utf-8")
        assert "notifier_webhook_url" in content

    def test_default_empty(self):
        content = CONFIG_PATH.read_text(encoding="utf-8")
        assert 'notifier_webhook_url: str = ""' in content


# ===========================================================================
# C20-6: 기존 sender 보존
# ===========================================================================
class TestC20ExistingSendersPreserved:
    def test_console_sender_still_works(self):
        routing = {"channels": ["console"], "severity_tier": "high"}
        receipt = send_notifications(
            {"overall_status": "NORMAL", "highest_incident": "NONE"}, routing
        )
        assert receipt.channels_delivered >= 1
        console = [r for r in receipt.results if r.channel == "console"]
        assert len(console) == 1
        assert console[0].delivered is True

    def test_snapshot_sender_still_works(self):
        routing = {"channels": ["snapshot"], "severity_tier": "low"}
        receipt = send_notifications({"snapshot_version": "C-13", "generated_at": "2026"}, routing)
        snap = [r for r in receipt.results if r.channel == "snapshot"]
        assert len(snap) == 1
        assert snap[0].delivered is True


# ===========================================================================
# C20-7: 금지 조항
# ===========================================================================
class TestC20Forbidden:
    def test_no_forbidden_strings_in_adapter(self):
        content = ADAPTER_PATH.read_text(encoding="utf-8")
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

    def test_no_state_mutation(self):
        content = ADAPTER_PATH.read_text(encoding="utf-8")
        assert "app.state" not in content

    def test_adapter_is_pure_transport(self):
        """Adapter는 순수 전송 — routing/snapshot/receipt 로직 없음."""
        content = ADAPTER_PATH.read_text(encoding="utf-8")
        assert "route_snapshot" not in content
        assert "ReceiptStore" not in content
        assert "_build_incident_snapshot" not in content
