"""
Card C-14: Alert Routing / Notification Bridge — Tests

검수 범위:
  C14-1: alert_router.py 모듈 존재 및 구조
  C14-2: route_snapshot() 라우팅 결정 로직
  C14-3: Snapshot 엔드포인트에 routing 필드 포함
  C14-4: 금지 조항 확인

Sealed layers 미접촉. 기존 테스트 파일 미수정.
"""

import sys
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Stub heavy modules for dashboard route import
# ---------------------------------------------------------------------------
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
ALERT_ROUTER_PATH = PROJECT_ROOT / "app" / "core" / "alert_router.py"
DASHBOARD_ROUTE_PATH = PROJECT_ROOT / "app" / "api" / "routes" / "dashboard.py"

# Import the actual router (no heavy deps)
from app.core.alert_router import route_snapshot


# ===========================================================================
# C14-1: 모듈 존재 및 구조
# ===========================================================================
class TestC14ModuleStructure:
    def test_module_exists(self):
        assert ALERT_ROUTER_PATH.exists()

    def test_route_snapshot_function_exists(self):
        content = ALERT_ROUTER_PATH.read_text(encoding="utf-8")
        assert "def route_snapshot" in content

    def test_returns_dict(self):
        result = route_snapshot(
            {"highest_incident": "NONE", "active_incidents": [], "degraded_reasons": []}
        )
        assert isinstance(result, dict)

    def test_result_has_channels(self):
        result = route_snapshot(
            {"highest_incident": "NONE", "active_incidents": [], "degraded_reasons": []}
        )
        assert "channels" in result
        assert isinstance(result["channels"], list)

    def test_result_has_severity_tier(self):
        result = route_snapshot(
            {"highest_incident": "NONE", "active_incidents": [], "degraded_reasons": []}
        )
        assert "severity_tier" in result

    def test_result_has_reason(self):
        result = route_snapshot(
            {"highest_incident": "NONE", "active_incidents": [], "degraded_reasons": []}
        )
        assert "reason" in result


# ===========================================================================
# C14-2: 라우팅 결정 로직
# ===========================================================================
class TestC14RoutingLogic:
    def test_clear_when_no_incidents(self):
        result = route_snapshot(
            {
                "highest_incident": "NONE",
                "active_incidents": [],
                "degraded_reasons": [],
            }
        )
        assert result["severity_tier"] == "clear"
        assert result["channels"] == []

    def test_critical_on_lockdown(self):
        result = route_snapshot(
            {
                "highest_incident": "LOCKDOWN",
                "active_incidents": ["LOCKDOWN"],
                "degraded_reasons": [],
            }
        )
        assert result["severity_tier"] == "critical"
        assert "console" in result["channels"]
        assert "external" in result["channels"]
        assert "snapshot" in result["channels"]

    def test_critical_on_quarantined(self):
        result = route_snapshot(
            {
                "highest_incident": "QUARANTINED",
                "active_incidents": ["QUARANTINED"],
                "degraded_reasons": [],
            }
        )
        assert result["severity_tier"] == "critical"

    def test_critical_on_loop_exceeded(self):
        result = route_snapshot(
            {
                "highest_incident": "LOOP_EXCEEDED",
                "active_incidents": ["LOOP_EXCEEDED"],
                "degraded_reasons": [],
            }
        )
        assert result["severity_tier"] == "critical"
        assert "external" in result["channels"]

    def test_high_on_work_failed(self):
        result = route_snapshot(
            {
                "highest_incident": "WORK_FAILED",
                "active_incidents": ["WORK_FAILED"],
                "degraded_reasons": [],
            }
        )
        assert result["severity_tier"] == "high"
        assert "console" in result["channels"]
        assert "snapshot" in result["channels"]
        assert "external" not in result["channels"]

    def test_high_on_work_blocked(self):
        result = route_snapshot(
            {
                "highest_incident": "WORK_BLOCKED",
                "active_incidents": ["WORK_BLOCKED"],
                "degraded_reasons": [],
            }
        )
        assert result["severity_tier"] == "high"

    def test_high_on_loop_critical(self):
        result = route_snapshot(
            {
                "highest_incident": "LOOP_CRITICAL",
                "active_incidents": ["LOOP_CRITICAL"],
                "degraded_reasons": [],
            }
        )
        assert result["severity_tier"] == "high"

    def test_low_on_doctrine_violation(self):
        result = route_snapshot(
            {
                "highest_incident": "DOCTRINE_VIOLATION_x2",
                "active_incidents": ["DOCTRINE_VIOLATION_x2"],
                "degraded_reasons": [],
            }
        )
        assert result["severity_tier"] == "low"
        assert result["channels"] == ["snapshot"]

    def test_low_on_degraded_only(self):
        result = route_snapshot(
            {
                "highest_incident": "NONE",
                "active_incidents": [],
                "degraded_reasons": ["venue:binance:stale"],
            }
        )
        assert result["severity_tier"] == "low"
        assert result["channels"] == ["snapshot"]

    def test_deterministic(self):
        """동일 입력 → 동일 결과."""
        snapshot = {
            "highest_incident": "LOCKDOWN",
            "active_incidents": ["LOCKDOWN"],
            "degraded_reasons": ["venue:binance:disconnected"],
        }
        r1 = route_snapshot(snapshot)
        r2 = route_snapshot(snapshot)
        assert r1 == r2

    def test_no_side_effects(self):
        """입력 snapshot이 변경되지 않는다."""
        snapshot = {
            "highest_incident": "NONE",
            "active_incidents": [],
            "degraded_reasons": [],
        }
        original = dict(snapshot)
        route_snapshot(snapshot)
        assert snapshot == original


# ===========================================================================
# C14-3: Snapshot 엔드포인트에 routing 포함
# ===========================================================================
class TestC14SnapshotIntegration:
    def test_snapshot_endpoint_includes_routing(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        fn_match = re.search(
            r"async def incident_snapshot.*?(?=\n@router\.|\nasync def dashboard_data[^_])",
            content,
            re.DOTALL,
        )
        assert fn_match
        fn_body = fn_match.group()
        assert "routing" in fn_body
        assert "route_snapshot" in fn_body

    def test_routing_fail_closed(self):
        """router 실패 시 안전 기본값."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        fn_match = re.search(
            r"async def incident_snapshot.*?(?=\n@router\.|\nasync def dashboard_data[^_])",
            content,
            re.DOTALL,
        )
        fn_body = fn_match.group()
        assert "router_unavailable" in fn_body
        assert "except" in fn_body


# ===========================================================================
# C14-4: 금지 조항 확인
# ===========================================================================
class TestC14Forbidden:
    def test_no_forbidden_strings_in_router(self):
        content = ALERT_ROUTER_PATH.read_text(encoding="utf-8")
        # Strip docstring
        body = content.split('"""', 2)[-1] if '"""' in content else content
        forbidden = [
            "chain_of_thought",
            "raw_prompt",
            "internal_reasoning",
            "debug_trace",
            "agent_analysis",
            "error_class",
            "traceback",
            "exception_type",
            "stack",
            "internal_state_dump",
        ]
        for f in forbidden:
            assert f not in body, f"Forbidden string '{f}' in alert_router"

    def test_no_notification_sending(self):
        """Router는 경로 결정만 — 실제 전송 없음."""
        content = ALERT_ROUTER_PATH.read_text(encoding="utf-8")
        sending_terms = [
            "requests.post",
            "httpx",
            "smtp",
            "discord",
            "slack",
            "webhook",
            "send_message",
        ]
        for term in sending_terms:
            assert term not in content, (
                f"Sending term '{term}' found — router should only decide routing"
            )

    def test_no_state_mutation(self):
        content = ALERT_ROUTER_PATH.read_text(encoding="utf-8")
        assert "app.state" not in content
        assert ".record(" not in content
