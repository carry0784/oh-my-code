"""
Card C-24: Notification Audit Export / Replay Bundle — Tests

검수 범위:
  C24-1: /api/audit-export 엔드포인트
  C24-2: Bundle 구조 검증
  C24-3: Summary 집계
  C24-4: 기존 엔드포인트 보존
  C24-5: 금지 조항

Sealed layers 미접촉. 기존 테스트 파일 미수정.
"""

import sys
import re
from pathlib import Path
from unittest.mock import MagicMock

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
DASHBOARD_ROUTE_PATH = PROJECT_ROOT / "app" / "api" / "routes" / "dashboard.py"


def _get_fn_body():
    content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
    fn_match = re.search(
        r"async def audit_export.*?(?=\n@router\.|\nasync def dashboard_data)", content, re.DOTALL
    )
    assert fn_match, "audit_export not found"
    return fn_match.group()


# ===========================================================================
# C24-1: /api/audit-export 엔드포인트
# ===========================================================================
class TestC24Endpoint:
    def test_endpoint_exists(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"/api/audit-export"' in content

    def test_endpoint_is_get(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        idx = content.index("async def audit_export")
        preceding = content[max(0, idx - 100) : idx]
        assert "@router.get" in preceding

    def test_fail_closed(self):
        fn_body = _get_fn_body()
        assert "except" in fn_body


# ===========================================================================
# C24-2: Bundle 구조
# ===========================================================================
class TestC24BundleStructure:
    def test_has_bundle_version(self):
        assert '"bundle_version"' in _get_fn_body()

    def test_has_generated_at(self):
        assert '"generated_at"' in _get_fn_body()

    def test_has_flow_log_section(self):
        assert '"flow_log"' in _get_fn_body()

    def test_has_receipts_section(self):
        assert '"receipts"' in _get_fn_body()

    def test_has_summary_section(self):
        assert '"summary"' in _get_fn_body()

    def test_flow_log_has_entries_key(self):
        fn_body = _get_fn_body()
        assert '"entries"' in fn_body

    def test_flow_log_has_available_key(self):
        fn_body = _get_fn_body()
        assert '"available"' in fn_body


# ===========================================================================
# C24-3: Summary 집계
# ===========================================================================
class TestC24Summary:
    def test_summary_has_total_flows(self):
        assert '"total_flows"' in _get_fn_body()

    def test_summary_has_total_receipts(self):
        assert '"total_receipts"' in _get_fn_body()

    def test_summary_has_sent_count(self):
        assert '"sent_count"' in _get_fn_body()

    def test_summary_has_suppressed_count(self):
        assert '"suppressed_count"' in _get_fn_body()

    def test_summary_has_escalated_count(self):
        assert '"escalated_count"' in _get_fn_body()

    def test_summary_has_failed_count(self):
        assert '"failed_count"' in _get_fn_body()

    def test_summary_has_top_severity(self):
        assert '"top_severity"' in _get_fn_body()

    def test_uses_flow_log_from_app_state(self):
        assert "flow_log" in _get_fn_body()

    def test_uses_receipt_store_from_app_state(self):
        assert "receipt_store" in _get_fn_body()


# ===========================================================================
# C24-4: 기존 엔드포인트 보존
# ===========================================================================
class TestC24ExistingPreserved:
    def test_v2_endpoint_preserved(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"/api/data/v2"' in content

    def test_snapshot_endpoint_preserved(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"/api/snapshot"' in content

    def test_receipts_endpoint_preserved(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"/api/receipts"' in content

    def test_flow_log_endpoint_preserved(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"/api/flow-log"' in content


# ===========================================================================
# C24-5: 금지 조항
# ===========================================================================
class TestC24Forbidden:
    def test_no_forbidden_strings(self):
        fn_body = _get_fn_body()
        # Strip docstring
        body = fn_body.split('"""', 2)[-1] if '"""' in fn_body else fn_body
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

    def test_no_db_queries(self):
        fn_body = _get_fn_body()
        assert "db.execute" not in fn_body
        assert "select(" not in fn_body

    def test_no_transport_logic(self):
        fn_body = _get_fn_body()
        assert "send_webhook" not in fn_body
        assert "urllib" not in fn_body
