"""
Card C-23: Notification Flow Review / Execution Audit Panel — Tests

검수 범위:
  C23-1: FlowLog 모듈 구조
  C23-2: FlowLog CRUD
  C23-3: /api/flow-log 엔드포인트
  C23-4: Dashboard panel + JS
  C23-5: CSS
  C23-6: Tab 2 통합
  C23-7: app.state.flow_log 슬롯
  C23-8: 금지 조항

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
FLOW_LOG_PATH = PROJECT_ROOT / "app" / "core" / "notification_flow_log.py"
TEMPLATE_PATH = PROJECT_ROOT / "app" / "templates" / "dashboard.html"
CSS_PATH = PROJECT_ROOT / "app" / "static" / "css" / "dashboard.css"
DASHBOARD_ROUTE_PATH = PROJECT_ROOT / "app" / "api" / "routes" / "dashboard.py"
MAIN_PATH = PROJECT_ROOT / "app" / "main.py"

from app.core.notification_flow_log import FlowLog, FlowLogEntry
from app.core.notification_flow import FlowResult


# ===========================================================================
# C23-1: FlowLog 모듈 구조
# ===========================================================================
class TestC23ModuleStructure:
    def test_module_exists(self):
        assert FLOW_LOG_PATH.exists()

    def test_flow_log_entry_dataclass(self):
        e = FlowLogEntry(log_id="FL-0001", policy_action="send")
        assert e.log_id == "FL-0001"
        d = e.to_dict()
        assert isinstance(d, dict)

    def test_flow_log_class_exists(self):
        content = FLOW_LOG_PATH.read_text(encoding="utf-8")
        assert "class FlowLog" in content


# ===========================================================================
# C23-2: FlowLog CRUD
# ===========================================================================
class TestC23FlowLogCRUD:
    def test_record_returns_log_id(self):
        log = FlowLog()
        lid = log.record(FlowResult(executed_at="2026"))
        assert lid.startswith("FL-")

    def test_count_increments(self):
        log = FlowLog()
        assert log.count() == 0
        log.record(FlowResult())
        assert log.count() == 1

    def test_latest_returns_most_recent(self):
        log = FlowLog()
        log.record(FlowResult(policy_action="send"))
        log.record(FlowResult(policy_action="suppress"))
        latest = log.latest()
        assert latest["policy_action"] == "suppress"

    def test_list_entries_newest_first(self):
        log = FlowLog()
        log.record(FlowResult(policy_action="A"))
        log.record(FlowResult(policy_action="B"))
        items = log.list_entries()
        assert items[0]["policy_action"] == "B"

    def test_ring_buffer_caps(self):
        log = FlowLog(max_entries=3)
        for i in range(5):
            log.record(FlowResult(policy_action=f"act-{i}"))
        assert log.count() == 3

    def test_records_flow_result_fields(self):
        log = FlowLog()
        fr = FlowResult(
            executed_at="2026-01-01",
            routing_ok=True,
            policy_action="escalate",
            policy_suppressed=False,
            policy_urgent=True,
            send_ok=True,
            channels_attempted=3,
            channels_delivered=2,
            receipt_id="RX-TEST",
            errors=["routing: timeout"],
        )
        log.record(fr)
        entry = log.latest()
        assert entry["routing_ok"] is True
        assert entry["policy_action"] == "escalate"
        assert entry["policy_urgent"] is True
        assert entry["channels_delivered"] == 2
        assert entry["error_count"] == 1
        assert entry["top_error"] == "routing: timeout"

    def test_fail_closed_on_bad_input(self):
        log = FlowLog()
        lid = log.record(42)
        assert lid.startswith("FL-")


# ===========================================================================
# C23-3: /api/flow-log 엔드포인트
# ===========================================================================
class TestC23Endpoint:
    def test_endpoint_exists(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"/api/flow-log"' in content

    def test_endpoint_is_get(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        idx = content.index("async def flow_log_review")
        preceding = content[max(0, idx - 100) : idx]
        assert "@router.get" in preceding

    def test_returns_entries_key(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        fn_match = re.search(
            r"async def flow_log_review.*?(?=\n@router\.|\nasync def )", content, re.DOTALL
        )
        assert fn_match
        assert '"entries"' in fn_match.group()

    def test_fail_closed(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        fn_match = re.search(
            r"async def flow_log_review.*?(?=\n@router\.|\nasync def )", content, re.DOTALL
        )
        assert fn_match
        assert "except" in fn_match.group()


# ===========================================================================
# C23-4: Dashboard panel + JS
# ===========================================================================
class TestC23Panel:
    def test_block_exists(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="flow-log-block"' in content

    def test_body_exists(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="flow-log-body"' in content

    def test_title_correct(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "Notification Flow Log" in content

    def test_render_function_exists(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "function renderFlowLog" in content

    def test_fetches_flow_log_api(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "/dashboard/api/flow-log" in content

    def test_shows_policy_action(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = content.index("function renderFlowLog")
        fn_end = content.index("function renderKeyFacts")
        fn_body = content[fn_start:fn_end]
        assert "policy_action" in fn_body

    def test_no_forbidden_strings(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = content.index("function renderFlowLog")
        fn_end = content.index("function renderKeyFacts")
        fn_body = content[fn_start:fn_end]
        forbidden = [
            "agent_analysis",
            "raw_prompt",
            "chain_of_thought",
            "internal_reasoning",
            "debug_trace",
            "error_class",
        ]
        for f in forbidden:
            assert f not in fn_body, f"Forbidden string '{f}'"


# ===========================================================================
# C23-5: CSS
# ===========================================================================
class TestC23CSS:
    def test_row_class(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".fl-row" in content

    def test_action_classes(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        for cls in [".fl-send", ".fl-suppress", ".fl-escalate", ".fl-resolve", ".fl-urgent"]:
            assert cls in content, f"CSS class {cls} must exist"


# ===========================================================================
# C23-6: Tab 2 통합
# ===========================================================================
class TestC23Integration:
    def test_called_from_render_tab2(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "renderFlowLog()" in content

    def test_block_between_receipt_and_event_log(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        rr_pos = content.index('id="receipt-review-block"')
        fl_pos = content.index('id="flow-log-block"')
        el_pos = content.index('id="event-log-block"')
        assert rr_pos < fl_pos < el_pos

    def test_existing_blocks_preserved(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        for bid in [
            "receipt-review-block",
            "incident-chronology-block",
            "event-log-block",
            "incident-overlay",
        ]:
            assert bid in content, f"{bid} must be preserved"


# ===========================================================================
# C23-7: app.state.flow_log 슬롯
# ===========================================================================
class TestC23AppState:
    def test_flow_log_initialized(self):
        content = MAIN_PATH.read_text(encoding="utf-8")
        assert "app.state.flow_log" in content
        assert "FlowLog" in content
