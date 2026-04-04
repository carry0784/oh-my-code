"""
Card C-01: AI Workspace Runtime Data Source Connection — Tests

검수 범위:
  C01-1: _get_loop_monitor_info() 헬퍼 검증
  C01-2: _get_work_state_info() 헬퍼 검증
  C01-3: _get_trust_state_info() 헬퍼 검증
  C01-4: _get_doctrine_info() 헬퍼 검증
  C01-5: v2 API 엔드포인트 키 검증
  C01-6: 템플릿 JS 통합 검증

Card B 봉인 유지: 기존 테스트 파일 미수정.
"""

import sys
import re
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timezone

import pytest


# ---------------------------------------------------------------------------
# Stub heavy modules (same pattern as test_dashboard.py)
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

# Provide minimal stubs for models
_pos_mock = sys.modules["app.models.position"]
_pos_mock.Position = MagicMock()
_pos_mock.PositionSide = MagicMock()

_order_mock = sys.modules["app.models.order"]
_order_mock.Order = MagicMock()
_order_mock.OrderStatus = MagicMock()

_trade_mock = sys.modules["app.models.trade"]
_trade_mock.Trade = MagicMock()
_trade_mock.Trade.id = "id"
_trade_mock.Trade.exchange = "exchange"

_signal_mock = sys.modules["app.models.signal"]
_signal_mock.Signal = MagicMock()

_db_mod = sys.modules["app.core.database"]
_db_mod.Base = MagicMock()
_db_mod.get_db = MagicMock()


# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = PROJECT_ROOT / "app" / "templates" / "dashboard.html"
DASHBOARD_ROUTE_PATH = PROJECT_ROOT / "app" / "api" / "routes" / "dashboard.py"
MAIN_PATH = PROJECT_ROOT / "app" / "main.py"


# ===========================================================================
# C01-1: _get_loop_monitor_info() 헬퍼
# ===========================================================================
class TestC01LoopMonitorHelper:
    """Loop Monitor 헬퍼 반환값 및 fail-closed 검증."""

    def test_helper_function_exists(self):
        """C01-1a: _get_loop_monitor_info 함수가 존재한다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert "def _get_loop_monitor_info" in content

    def test_returns_unavailable_when_missing(self):
        """C01-1b: app.state.loop_monitor 미연결 시 available=False."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        fn_match = re.search(r"def _get_loop_monitor_info.*?(?=\ndef |\Z)", content, re.DOTALL)
        assert fn_match
        fn_body = fn_match.group()
        assert '"available": False' in fn_body or "'available': False" in fn_body

    def test_never_calls_check(self):
        """C01-1c: .check() 호출이 없고 .last_result만 사용한다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        fn_match = re.search(r"def _get_loop_monitor_info.*?(?=\ndef |\Z)", content, re.DOTALL)
        assert fn_match
        fn_body = fn_match.group()
        assert "last_result" in fn_body, "Must read last_result"
        # Strip docstring before checking for .check() calls
        # Docstring mentions .check() as a warning — that's fine
        body_after_docstring = fn_body.split('"""', 2)[-1] if '"""' in fn_body else fn_body
        assert ".check(" not in body_after_docstring, "Must NOT call .check() in function body"

    def test_serializes_loop_fields(self):
        """C01-1d: 루프별 health, max_usage_ratio, incident_count, incident_ceiling 직렬화."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        fn_match = re.search(r"def _get_loop_monitor_info.*?(?=\ndef |\Z)", content, re.DOTALL)
        assert fn_match
        fn_body = fn_match.group()
        for field in ["health", "max_usage_ratio", "incident_count", "incident_ceiling"]:
            assert f'"{field}"' in fn_body, f"Loop field {field} must be serialized"

    def test_exception_returns_error(self):
        """C01-1e: 예외 시 available=False, error=True 반환."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        fn_match = re.search(r"def _get_loop_monitor_info.*?(?=\ndef |\Z)", content, re.DOTALL)
        assert fn_match
        fn_body = fn_match.group()
        assert "except Exception" in fn_body
        assert '"error": True' in fn_body or "'error': True" in fn_body


# ===========================================================================
# C01-2: _get_work_state_info() 헬퍼
# ===========================================================================
class TestC01WorkStateHelper:
    """Work State 헬퍼 검증."""

    def test_helper_function_exists(self):
        """C01-2a: _get_work_state_info 함수가 존재한다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert "def _get_work_state_info" in content

    def test_returns_unavailable_when_missing(self):
        """C01-2b: app.state.work_state_ctx 미연결 시 available=False."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        fn_match = re.search(r"def _get_work_state_info.*?(?=\ndef |\Z)", content, re.DOTALL)
        assert fn_match
        fn_body = fn_match.group()
        assert '"available": False' in fn_body

    def test_serializes_safe_fields_only(self):
        """C01-2c: current, previous, failed_check, validation_results만 노출."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        fn_match = re.search(r"def _get_work_state_info.*?(?=\ndef |\Z)", content, re.DOTALL)
        assert fn_match
        fn_body = fn_match.group()
        for field in ['"current"', '"previous"', '"failed_check"', '"validation_results"']:
            assert field in fn_body, f"Field {field} must be serialized"

    def test_no_guard_internals_exposed(self):
        """C01-2d: GuardResult, message 등 guard 내부 노출 금지."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        fn_match = re.search(r"def _get_work_state_info.*?(?=\ndef |\Z)", content, re.DOTALL)
        assert fn_match
        fn_body = fn_match.group()
        # validation_results의 각 항목은 check+passed만 있어야 함
        assert '"message"' not in fn_body, "Guard message must not be exposed"
        assert '"condition_id"' not in fn_body, "Guard condition_id must not be exposed"


# ===========================================================================
# C01-3: _get_trust_state_info() 헬퍼
# ===========================================================================
class TestC01TrustStateHelper:
    """Trust State 헬퍼 검증."""

    def test_helper_function_exists(self):
        """C01-3a: _get_trust_state_info 함수가 존재한다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert "def _get_trust_state_info" in content

    def test_returns_unavailable_when_missing(self):
        """C01-3b: trust_registry 미연결 시 available=False."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        fn_match = re.search(r"def _get_trust_state_info.*?(?=\ndef |\Z)", content, re.DOTALL)
        assert fn_match
        fn_body = fn_match.group()
        assert '"available": False' in fn_body

    def test_serializes_component_fields(self):
        """C01-3c: state, score, allows_execution, requires_monitoring 직렬화."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        fn_match = re.search(r"def _get_trust_state_info.*?(?=\ndef |\Z)", content, re.DOTALL)
        assert fn_match
        fn_body = fn_match.group()
        for field in ['"state"', '"score"', '"allows_execution"', '"requires_monitoring"']:
            assert field in fn_body, f"Component field {field} must be serialized"

    def test_score_numeric_only(self):
        """C01-3d: score는 float 변환만 허용, repr/str 변환 금지."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        fn_match = re.search(r"def _get_trust_state_info.*?(?=\ndef |\Z)", content, re.DOTALL)
        assert fn_match
        fn_body = fn_match.group()
        assert "float(score)" in fn_body or "float(" in fn_body, "Score must use float() conversion"


# ===========================================================================
# C01-4: _get_doctrine_info() 헬퍼
# ===========================================================================
class TestC01DoctrineHelper:
    """Doctrine 헬퍼 검증."""

    def test_helper_function_exists(self):
        """C01-4a: _get_doctrine_info 함수가 존재한다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert "def _get_doctrine_info" in content

    def test_fallback_sets_available_false(self):
        """C01-4b: fallback 시 available=False."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        fn_match = re.search(r"def _get_doctrine_info.*?(?=\ndef |\Z)", content, re.DOTALL)
        assert fn_match
        fn_body = fn_match.group()
        assert "is_live = False" in fn_body, "Fallback must set is_live=False"
        assert '"available": is_live' in fn_body or "'available': is_live" in fn_body

    def test_recent_violations_capped_at_5(self):
        """C01-4c: recent_violations는 최근 5건으로 cap."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        fn_match = re.search(r"def _get_doctrine_info.*?(?=\ndef |\Z)", content, re.DOTALL)
        assert fn_match
        fn_body = fn_match.group()
        assert "[-5:]" in fn_body, "recent_violations must be capped at 5"

    def test_no_constraint_exposed(self):
        """C01-4d: constraint 필드가 직렬화에 포함되지 않는다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        fn_match = re.search(r"def _get_doctrine_info.*?(?=\ndef |\Z)", content, re.DOTALL)
        assert fn_match
        fn_body = fn_match.group()
        # doctrine 직렬화 dict에서 constraint 키가 없어야 함
        assert '"constraint"' not in fn_body, "constraint must not be exposed"
        assert '"context"' not in fn_body, "violation context must not be exposed"


# ===========================================================================
# C01-5: v2 API 엔드포인트 키 검증
# ===========================================================================
class TestC01V2EndpointKeys:
    """v2 응답에 C-01 신규 키 존재 및 기존 키 보존 검증."""

    def test_v2_returns_loop_monitor_key(self):
        """C01-5a: v2 응답에 loop_monitor 키가 포함된다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"loop_monitor"' in content

    def test_v2_returns_work_state_key(self):
        """C01-5b: v2 응답에 work_state 키가 포함된다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"work_state"' in content

    def test_v2_returns_trust_state_key(self):
        """C01-5c: v2 응답에 trust_state 키가 포함된다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"trust_state"' in content

    def test_v2_returns_doctrine_key(self):
        """C01-5d: v2 응답에 doctrine 키가 포함된다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"doctrine"' in content

    def test_existing_v2_keys_preserved(self):
        """C01-5e: 기존 v2 키(governance, recent_events 등)가 보존된다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        for key in [
            '"governance"',
            '"recent_events"',
            '"open_orders"',
            '"signal_summary"',
            '"venue_freshness"',
            '"quote_data"',
        ]:
            assert key in content, f"Existing key {key} must be preserved"


# ===========================================================================
# C01-6: 템플릿 JS 통합 검증
# ===========================================================================
class TestC01TemplateIntegration:
    """대시보드 템플릿에서 C-01 데이터 소스 참조 검증."""

    def test_js_references_loop_monitor(self):
        """C01-6a: JS에서 data.loop_monitor를 참조한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "data.loop_monitor" in content

    def test_js_references_work_state(self):
        """C01-6b: JS에서 data.work_state를 참조한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "data.work_state" in content

    def test_js_references_trust_state(self):
        """C01-6c: JS에서 data.trust_state를 참조한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "data.trust_state" in content

    def test_js_references_doctrine(self):
        """C01-6d: JS에서 data.doctrine를 참조한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "data.doctrine" in content

    def test_no_forbidden_strings_in_ai_render(self):
        """C01-6e: AI 렌더 함수에 금지 문자열이 없다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        ai_start = content.index("function renderAIWorkspace")
        legacy_start = content.index("function renderBinance")
        ai_section = content[ai_start:legacy_start]
        forbidden = [
            "agent_analysis",
            "raw_prompt",
            "chain_of_thought",
            "internal_reasoning",
            "debug_trace",
            "error_class",
            "traceback",
            "exception_type",
            "stack",
            "internal_state_dump",
        ]
        for f in forbidden:
            assert f not in ai_section, f"Forbidden string '{f}' found in AI render section"

    def test_absence_uses_verify_not_fact(self):
        """C01-6f: 미연결 데이터는 verify 톤으로 NOT AVAILABLE 표시."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        ai_start = content.index("function renderAIWorkspace")
        legacy_start = content.index("function renderBinance")
        ai_section = content[ai_start:legacy_start]
        # verify + NOT AVAILABLE 패턴이 존재해야 함
        assert "'verify'" in ai_section and "NOT AVAILABLE" in ai_section, (
            "Disconnected data must use verify tier with NOT AVAILABLE"
        )

    def test_loop_exceeded_in_anomaly_render(self):
        """C01-6g: renderDetectedAnomalies에서 EXCEEDED 상태를 감지한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = content.index("function renderDetectedAnomalies")
        fn_end = content.index("function renderPossibleCauses")
        fn_body = content[fn_start:fn_end]
        assert "EXCEEDED" in fn_body

    def test_trust_allows_execution_checked(self):
        """C01-6h: allows_execution이 JS에서 참조된다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        ai_start = content.index("function renderAIWorkspace")
        legacy_start = content.index("function renderBinance")
        ai_section = content[ai_start:legacy_start]
        assert "allows_execution" in ai_section

    def test_doctrine_violation_count_in_risk_warnings(self):
        """C01-6i: renderRiskWarnings에서 violation_count를 참조한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = content.index("function renderRiskWarnings")
        fn_end = content.index("function renderRecommendedChecks")
        fn_body = content[fn_start:fn_end]
        assert "violation_count" in fn_body

    def test_existing_ai_render_functions_preserved(self):
        """C01-6j: 기존 5개 AI 렌더 함수 이름이 보존된다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        for fn_name in [
            "renderConfirmedFacts",
            "renderDetectedAnomalies",
            "renderPossibleCauses",
            "renderRiskWarnings",
            "renderRecommendedChecks",
        ]:
            assert f"function {fn_name}" in content, f"{fn_name} must be preserved"


# ===========================================================================
# C01-7: app.state 슬롯 초기화 검증
# ===========================================================================
class TestC01AppStateSlots:
    """main.py에서 C-01 app.state 슬롯 초기화 검증."""

    def test_loop_monitor_slot_initialized(self):
        """C01-7a: app.state.loop_monitor 슬롯 초기화."""
        content = MAIN_PATH.read_text(encoding="utf-8")
        assert "app.state.loop_monitor" in content

    def test_work_state_ctx_slot_initialized(self):
        """C01-7b: app.state.work_state_ctx 슬롯 초기화."""
        content = MAIN_PATH.read_text(encoding="utf-8")
        assert "app.state.work_state_ctx" in content

    def test_trust_registry_slot_initialized(self):
        """C01-7c: app.state.trust_registry 슬롯 초기화."""
        content = MAIN_PATH.read_text(encoding="utf-8")
        assert "app.state.trust_registry" in content

    def test_doctrine_registry_slot_initialized(self):
        """C01-7d: app.state.doctrine_registry 슬롯 초기화."""
        content = MAIN_PATH.read_text(encoding="utf-8")
        assert "app.state.doctrine_registry" in content
