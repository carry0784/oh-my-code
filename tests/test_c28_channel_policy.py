"""
Card C-28: Channel Policy Wiring / Escalation Matrix — Tests

검수 범위:
  C28-1: ChannelPolicy 모듈 구조
  C28-2: 기본 matrix 검증
  C28-3: resolve_channels() 로직
  C28-4: Policy action 우선순위
  C28-5: Custom matrix / reconfiguration
  C28-6: Fail-closed
  C28-7: 기존 모듈 보존
  C28-8: 금지 조항

Sealed layers 미접촉. 기존 테스트 파일 미수정.
"""

from pathlib import Path

import pytest

from app.core.channel_policy import ChannelPolicy, _DEFAULT_MATRIX

PROJECT_ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = PROJECT_ROOT / "app" / "core" / "channel_policy.py"
ROUTER_PATH = PROJECT_ROOT / "app" / "core" / "alert_router.py"
ALERT_POLICY_PATH = PROJECT_ROOT / "app" / "core" / "alert_policy.py"


# ===========================================================================
# C28-1: 모듈 구조
# ===========================================================================
class TestC28ModuleStructure:
    def test_module_exists(self):
        assert POLICY_PATH.exists()

    def test_channel_policy_class(self):
        content = POLICY_PATH.read_text(encoding="utf-8")
        assert "class ChannelPolicy" in content

    def test_resolve_channels_method(self):
        content = POLICY_PATH.read_text(encoding="utf-8")
        assert "def resolve_channels" in content

    def test_default_matrix_defined(self):
        assert isinstance(_DEFAULT_MATRIX, dict)
        assert "critical" in _DEFAULT_MATRIX
        assert "clear" in _DEFAULT_MATRIX


# ===========================================================================
# C28-2: 기본 matrix 검증
# ===========================================================================
class TestC28DefaultMatrix:
    def test_critical_has_all_channels(self):
        assert "console" in _DEFAULT_MATRIX["critical"]
        assert "snapshot" in _DEFAULT_MATRIX["critical"]
        assert "external" in _DEFAULT_MATRIX["critical"]
        assert "file" in _DEFAULT_MATRIX["critical"]
        assert "slack" in _DEFAULT_MATRIX["critical"]

    def test_high_has_no_slack(self):
        assert "slack" not in _DEFAULT_MATRIX["high"]
        assert "console" in _DEFAULT_MATRIX["high"]
        assert "external" in _DEFAULT_MATRIX["high"]

    def test_low_is_snapshot_and_file_only(self):
        assert _DEFAULT_MATRIX["low"] == ["snapshot", "file"]

    def test_clear_is_empty(self):
        assert _DEFAULT_MATRIX["clear"] == []

    def test_escalate_matches_critical(self):
        assert set(_DEFAULT_MATRIX["escalate"]) == set(_DEFAULT_MATRIX["critical"])

    def test_resolve_is_compact(self):
        assert "console" in _DEFAULT_MATRIX["resolve"]
        assert "snapshot" in _DEFAULT_MATRIX["resolve"]
        assert "external" not in _DEFAULT_MATRIX["resolve"]


# ===========================================================================
# C28-3: resolve_channels() 로직
# ===========================================================================
class TestC28ResolveChannels:
    def test_critical_send(self):
        cp = ChannelPolicy()
        channels = cp.resolve_channels("critical", "send")
        assert "console" in channels
        assert "slack" in channels
        assert "external" in channels

    def test_high_send(self):
        cp = ChannelPolicy()
        channels = cp.resolve_channels("high", "send")
        assert "console" in channels
        assert "slack" not in channels

    def test_low_send(self):
        cp = ChannelPolicy()
        channels = cp.resolve_channels("low", "send")
        assert channels == ["snapshot", "file"]

    def test_clear_send(self):
        cp = ChannelPolicy()
        channels = cp.resolve_channels("clear", "send")
        assert channels == []


# ===========================================================================
# C28-4: Policy action 우선순위
# ===========================================================================
class TestC28ActionPriority:
    def test_suppress_always_empty(self):
        cp = ChannelPolicy()
        assert cp.resolve_channels("critical", "suppress") == []
        assert cp.resolve_channels("high", "suppress") == []
        assert cp.resolve_channels("low", "suppress") == []

    def test_escalate_overrides_tier(self):
        cp = ChannelPolicy()
        channels = cp.resolve_channels("low", "escalate")
        assert "slack" in channels
        assert "external" in channels

    def test_resolve_is_compact(self):
        cp = ChannelPolicy()
        channels = cp.resolve_channels("critical", "resolve")
        assert "console" in channels
        assert "file" in channels
        assert "external" not in channels
        assert "slack" not in channels

    def test_passthrough_uses_tier(self):
        cp = ChannelPolicy()
        channels = cp.resolve_channels("high", "passthrough")
        assert channels == cp.resolve_channels("high", "send")


# ===========================================================================
# C28-5: Custom matrix / reconfiguration
# ===========================================================================
class TestC28CustomMatrix:
    def test_custom_matrix_at_init(self):
        custom = {"critical": ["console"], "low": ["file"], "clear": []}
        cp = ChannelPolicy(matrix=custom)
        assert cp.resolve_channels("critical", "send") == ["console"]

    def test_update_tier(self):
        cp = ChannelPolicy()
        cp.update_tier("low", ["console", "file", "slack"])
        assert "slack" in cp.resolve_channels("low", "send")

    def test_get_matrix_returns_copy(self):
        cp = ChannelPolicy()
        m = cp.get_matrix()
        m["critical"].append("new_channel")
        assert "new_channel" not in cp.resolve_channels("critical", "send")


# ===========================================================================
# C28-6: Fail-closed
# ===========================================================================
class TestC28FailClosed:
    def test_unknown_tier_returns_fallback(self):
        cp = ChannelPolicy()
        channels = cp.resolve_channels("nonexistent_tier", "send")
        assert channels == ["snapshot"]

    def test_unknown_action_uses_tier(self):
        cp = ChannelPolicy()
        channels = cp.resolve_channels("critical", "unknown_action")
        assert "console" in channels


# ===========================================================================
# C28-7: 기존 모듈 보존
# ===========================================================================
class TestC28ExistingPreserved:
    def test_alert_router_unchanged(self):
        content = ROUTER_PATH.read_text(encoding="utf-8")
        assert "def route_snapshot" in content
        assert "channel_policy" not in content

    def test_alert_policy_unchanged(self):
        content = ALERT_POLICY_PATH.read_text(encoding="utf-8")
        assert "class AlertPolicy" in content
        assert "channel_policy" not in content


# ===========================================================================
# C28-8: 금지 조항
# ===========================================================================
class TestC28Forbidden:
    def test_no_forbidden_strings(self):
        content = POLICY_PATH.read_text(encoding="utf-8")
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

    def test_no_transport_logic(self):
        content = POLICY_PATH.read_text(encoding="utf-8")
        assert "send_webhook" not in content
        assert "urllib" not in content

    def test_no_app_state(self):
        content = POLICY_PATH.read_text(encoding="utf-8")
        assert "app.state" not in content

    def test_deterministic(self):
        """동일 입력 → 동일 결과."""
        cp = ChannelPolicy()
        r1 = cp.resolve_channels("critical", "send")
        r2 = cp.resolve_channels("critical", "send")
        assert r1 == r2
