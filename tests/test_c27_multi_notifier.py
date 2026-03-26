"""
Card C-27: Multi-Notifier Adapter — Tests

검수 범위:
  C27-1: notifier_adapters.py 모듈 구조
  C27-2: File notifier
  C27-3: Slack notifier (stub)
  C27-4: Channel registration
  C27-5: Config entries
  C27-6: 기존 sender 보존
  C27-7: 금지 조항

Sealed layers 미접촉. 기존 테스트 파일 미수정.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_STUB_MODULES = [
    "app.core.database", "app.models", "app.models.order",
    "app.models.position", "app.models.signal", "app.models.trade",
    "app.models.asset_snapshot", "app.exchanges", "app.exchanges.factory",
    "app.exchanges.base", "app.exchanges.binance", "app.exchanges.okx",
    "app.services", "app.services.order_service",
    "app.services.position_service", "app.services.signal_service",
    "ccxt", "ccxt.async_support", "redis", "celery", "asyncpg",
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
ADAPTERS_PATH = PROJECT_ROOT / "app" / "core" / "notifier_adapters.py"
SENDER_PATH = PROJECT_ROOT / "app" / "core" / "notification_sender.py"
CONFIG_PATH = PROJECT_ROOT / "app" / "core" / "config.py"

from app.core.notifier_adapters import send_file, send_slack
from app.core.notification_sender import get_sender, send_notifications


# ===========================================================================
# C27-1: 모듈 구조
# ===========================================================================
class TestC27ModuleStructure:

    def test_adapters_module_exists(self):
        assert ADAPTERS_PATH.exists()

    def test_send_file_exists(self):
        content = ADAPTERS_PATH.read_text(encoding="utf-8")
        assert "def send_file" in content

    def test_send_slack_exists(self):
        content = ADAPTERS_PATH.read_text(encoding="utf-8")
        assert "def send_slack" in content


# ===========================================================================
# C27-2: File notifier
# ===========================================================================
class TestC27FileNotifier:

    def test_file_not_configured_returns_false(self):
        with patch("app.core.config.settings", MagicMock(notifier_file_path="")):
            result = send_file({"overall_status": "NORMAL"}, {})
            assert result.delivered is False
            assert "not configured" in result.detail

    def test_file_configured_writes(self, tmp_path):
        path = str(tmp_path / "alerts.jsonl")
        with patch("app.core.config.settings", MagicMock(notifier_file_path=path)):
            result = send_file(
                {"overall_status": "LOCKDOWN", "highest_incident": "LOCKDOWN"},
                {"severity_tier": "critical", "channels": ["file"]},
            )
            assert result.delivered is True
            assert result.channel == "file"
            assert Path(path).exists()

    def test_file_appends_jsonl(self, tmp_path):
        import json
        path = str(tmp_path / "alerts.jsonl")
        with patch("app.core.config.settings", MagicMock(notifier_file_path=path)):
            send_file({"overall_status": "A"}, {})
            send_file({"overall_status": "B"}, {})
        with open(path) as f:
            lines = [l.strip() for l in f if l.strip()]
        assert len(lines) == 2
        assert json.loads(lines[0])["status"] == "A"
        assert json.loads(lines[1])["status"] == "B"

    def test_file_fail_closed(self):
        """쓰기 불가 경로 → delivered=False."""
        import sys as _sys
        bad_path = "NUL:\\impossible\\path.jsonl" if _sys.platform == "win32" else "/proc/0/impossible.jsonl"
        with patch("app.core.config.settings", MagicMock(notifier_file_path=bad_path)):
            result = send_file({}, {})
            assert result.delivered is False


# ===========================================================================
# C27-3: Slack notifier (stub)
# ===========================================================================
class TestC27SlackNotifier:

    def test_slack_not_configured_returns_false(self):
        with patch("app.core.config.settings", MagicMock(notifier_slack_url="")):
            result = send_slack({"overall_status": "NORMAL"}, {})
            assert result.delivered is False
            assert "not configured" in result.detail

    def test_slack_channel_name(self):
        with patch("app.core.config.settings", MagicMock(notifier_slack_url="")):
            result = send_slack({}, {})
            assert result.channel == "slack"


# ===========================================================================
# C27-4: Channel registration
# ===========================================================================
class TestC27ChannelRegistration:

    def test_file_sender_registered(self):
        """file sender가 registry에 존재하거나 수동 등록 가능."""
        from app.core.notification_sender import register_sender
        register_sender("file", send_file)
        assert get_sender("file") is not None

    def test_slack_sender_registered(self):
        """slack sender가 registry에 존재하거나 수동 등록 가능."""
        from app.core.notification_sender import register_sender
        register_sender("slack", send_slack)
        assert get_sender("slack") is not None

    def test_existing_senders_preserved(self):
        assert get_sender("console") is not None
        assert get_sender("snapshot") is not None
        assert get_sender("external") is not None

    def test_dispatch_to_file_channel(self):
        """send_notifications가 file 채널로 디스패치 가능."""
        routing = {"channels": ["file"], "severity_tier": "low"}
        receipt = send_notifications({"overall_status": "NORMAL"}, routing)
        assert receipt.channels_attempted == 1
        file_result = [r for r in receipt.results if r.channel == "file"]
        assert len(file_result) == 1


# ===========================================================================
# C27-5: Config
# ===========================================================================
class TestC27Config:

    def test_file_path_setting(self):
        content = CONFIG_PATH.read_text(encoding="utf-8")
        assert "notifier_file_path" in content

    def test_slack_url_setting(self):
        content = CONFIG_PATH.read_text(encoding="utf-8")
        assert "notifier_slack_url" in content

    def test_defaults_empty(self):
        content = CONFIG_PATH.read_text(encoding="utf-8")
        assert 'notifier_file_path: str = ""' in content
        assert 'notifier_slack_url: str = ""' in content


# ===========================================================================
# C27-6: 기존 sender 보존
# ===========================================================================
class TestC27ExistingSendersPreserved:

    def test_console_still_works(self):
        routing = {"channels": ["console"], "severity_tier": "high"}
        receipt = send_notifications({"overall_status": "NORMAL", "highest_incident": "NONE"}, routing)
        assert receipt.channels_delivered >= 1

    def test_snapshot_still_works(self):
        routing = {"channels": ["snapshot"], "severity_tier": "low"}
        receipt = send_notifications({"snapshot_version": "C-13"}, routing)
        snap = [r for r in receipt.results if r.channel == "snapshot"]
        assert snap[0].delivered is True


# ===========================================================================
# C27-7: 금지 조항
# ===========================================================================
class TestC27Forbidden:

    def test_no_forbidden_strings(self):
        content = ADAPTERS_PATH.read_text(encoding="utf-8")
        body = content.split('"""', 2)[-1] if '"""' in content else content
        forbidden = [
            'chain_of_thought', 'raw_prompt', 'internal_reasoning',
            'debug_trace', 'agent_analysis', 'error_class',
        ]
        for f in forbidden:
            assert f not in body, f"Forbidden string '{f}'"

    def test_no_app_state(self):
        content = ADAPTERS_PATH.read_text(encoding="utf-8")
        assert "app.state" not in content
