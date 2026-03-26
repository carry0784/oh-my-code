"""
Card C-25: Audit Replay / Incident Reconstruction View — Tests

검수 범위:
  C25-1: /api/audit-replay 엔드포인트
  C25-2: Replay 구조 (sequence + stages)
  C25-3: Incident summary 집계
  C25-4: Receipt 매칭
  C25-5: 기존 엔드포인트 보존
  C25-6: 금지 조항

Sealed layers 미접촉. 기존 테스트 파일 미수정.
"""

import sys
import re
from pathlib import Path
from unittest.mock import MagicMock

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
DASHBOARD_ROUTE_PATH = PROJECT_ROOT / "app" / "api" / "routes" / "dashboard.py"


def _get_fn_body():
    content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
    fn_match = re.search(
        r'async def audit_replay.*?(?=\n@router\.|\nasync def dashboard_data)',
        content, re.DOTALL
    )
    assert fn_match, "audit_replay not found"
    return fn_match.group()


# ===========================================================================
# C25-1: /api/audit-replay 엔드포인트
# ===========================================================================
class TestC25Endpoint:

    def test_endpoint_exists(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"/api/audit-replay"' in content

    def test_endpoint_is_get(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        idx = content.index("async def audit_replay")
        preceding = content[max(0, idx - 100):idx]
        assert "@router.get" in preceding

    def test_fail_closed(self):
        fn_body = _get_fn_body()
        assert "except" in fn_body


# ===========================================================================
# C25-2: Replay 구조
# ===========================================================================
class TestC25ReplayStructure:

    def test_has_replay_version(self):
        assert '"replay_version"' in _get_fn_body()

    def test_has_generated_at(self):
        assert '"generated_at"' in _get_fn_body()

    def test_has_sequence(self):
        assert '"sequence"' in _get_fn_body()

    def test_has_incident_summary(self):
        assert '"incident_summary"' in _get_fn_body()

    def test_sequence_has_stages(self):
        assert '"stages"' in _get_fn_body()

    def test_stages_include_routing(self):
        assert '"routing"' in _get_fn_body()

    def test_stages_include_policy(self):
        assert '"policy"' in _get_fn_body()

    def test_stages_include_sender(self):
        assert '"sender"' in _get_fn_body()

    def test_stages_include_receipt(self):
        assert '"receipt"' in _get_fn_body()

    def test_causal_order(self):
        """Sequence는 oldest-first (인과 순서)."""
        fn_body = _get_fn_body()
        assert "reversed(flow_entries)" in fn_body


# ===========================================================================
# C25-3: Incident summary
# ===========================================================================
class TestC25IncidentSummary:

    def test_summary_has_total_events(self):
        assert '"total_events"' in _get_fn_body()

    def test_summary_has_sent(self):
        assert '"sent"' in _get_fn_body()

    def test_summary_has_suppressed(self):
        assert '"suppressed"' in _get_fn_body()

    def test_summary_has_escalated(self):
        assert '"escalated"' in _get_fn_body()

    def test_summary_has_resolved(self):
        assert '"resolved"' in _get_fn_body()

    def test_summary_has_errors(self):
        assert '"errors"' in _get_fn_body()


# ===========================================================================
# C25-4: Receipt 매칭
# ===========================================================================
class TestC25ReceiptMatching:

    def test_builds_receipt_lookup(self):
        fn_body = _get_fn_body()
        assert "receipt_lookup" in fn_body

    def test_matches_by_receipt_id(self):
        fn_body = _get_fn_body()
        assert "receipt_id" in fn_body

    def test_handles_unmatched_receipt(self):
        fn_body = _get_fn_body()
        assert '"matched"' in fn_body or '"(none)"' in fn_body


# ===========================================================================
# C25-5: 기존 엔드포인트 보존
# ===========================================================================
class TestC25ExistingPreserved:

    def test_v2_preserved(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"/api/data/v2"' in content

    def test_snapshot_preserved(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"/api/snapshot"' in content

    def test_audit_export_preserved(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"/api/audit-export"' in content

    def test_flow_log_preserved(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"/api/flow-log"' in content

    def test_receipts_preserved(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"/api/receipts"' in content


# ===========================================================================
# C25-6: 금지 조항
# ===========================================================================
class TestC25Forbidden:

    def test_no_forbidden_strings(self):
        fn_body = _get_fn_body()
        body = fn_body.split('"""', 2)[-1] if '"""' in fn_body else fn_body
        forbidden = [
            'chain_of_thought', 'raw_prompt', 'internal_reasoning',
            'debug_trace', 'agent_analysis', 'error_class',
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

    def test_is_not_raw_log_viewer(self):
        """Structured reconstruction, not raw dump."""
        fn_body = _get_fn_body()
        assert '"stages"' in fn_body  # structured stages
        assert "JSON.stringify" not in fn_body
