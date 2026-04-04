"""
Card C-17: Receipt Review / Audit View — Tests

검수 범위:
  C17-1: /api/receipts 엔드포인트
  C17-2: Receipt Review 대시보드 패널
  C17-3: JS 렌더링 함수
  C17-4: CSS 스타일
  C17-5: Tab 2 통합
  C17-6: app.state.receipt_store 슬롯
  C17-7: 금지 조항 확인

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
TEMPLATE_PATH = PROJECT_ROOT / "app" / "templates" / "dashboard.html"
CSS_PATH = PROJECT_ROOT / "app" / "static" / "css" / "dashboard.css"
DASHBOARD_ROUTE_PATH = PROJECT_ROOT / "app" / "api" / "routes" / "dashboard.py"
MAIN_PATH = PROJECT_ROOT / "app" / "main.py"


# ===========================================================================
# C17-1: /api/receipts 엔드포인트
# ===========================================================================
class TestC17Endpoint:
    def test_endpoint_exists(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"/api/receipts"' in content

    def test_endpoint_is_get(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        idx = content.index("async def receipt_review")
        preceding = content[max(0, idx - 100) : idx]
        assert "@router.get" in preceding

    def test_returns_receipts_key(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        fn_match = re.search(
            r"async def receipt_review.*?(?=\n@router\.|\nasync def )", content, re.DOTALL
        )
        assert fn_match
        assert '"receipts"' in fn_match.group()

    def test_returns_available_key(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        fn_match = re.search(
            r"async def receipt_review.*?(?=\n@router\.|\nasync def )", content, re.DOTALL
        )
        assert fn_match
        assert '"available"' in fn_match.group()

    def test_fail_closed(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        fn_match = re.search(
            r"async def receipt_review.*?(?=\n@router\.|\nasync def )", content, re.DOTALL
        )
        assert fn_match
        assert "except" in fn_match.group()

    def test_uses_receipt_store_from_app_state(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        fn_match = re.search(
            r"async def receipt_review.*?(?=\n@router\.|\nasync def )", content, re.DOTALL
        )
        assert fn_match
        assert "receipt_store" in fn_match.group()


# ===========================================================================
# C17-2: Dashboard panel
# ===========================================================================
class TestC17Panel:
    def test_block_exists(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="receipt-review-block"' in content

    def test_body_exists(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="receipt-review-body"' in content

    def test_title_correct(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "Receipt Review" in content


# ===========================================================================
# C17-3: JS 렌더링 함수
# ===========================================================================
class TestC17RenderFunction:
    def _get_fn_body(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = content.index("function renderReceiptReview")
        fn_end = content.index("function renderKeyFacts")
        return content[fn_start:fn_end]

    def test_function_exists(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "function renderReceiptReview" in content

    def test_fetches_receipts_api(self):
        assert "/dashboard/api/receipts" in self._get_fn_body()

    def test_not_available_fallback(self):
        assert "NOT AVAILABLE" in self._get_fn_body()

    def test_shows_severity_badge(self):
        fn_body = self._get_fn_body()
        assert "severity_tier" in fn_body
        assert "rr-badge" in fn_body

    def test_shows_incident(self):
        assert "highest_incident" in self._get_fn_body()

    def test_shows_channel_count(self):
        fn_body = self._get_fn_body()
        assert "channels_delivered" in fn_body
        assert "channels_attempted" in fn_body

    def test_shows_timestamp(self):
        assert "stored_at" in self._get_fn_body()

    def test_shows_overflow(self):
        assert "rr-overflow" in self._get_fn_body()

    def test_no_forbidden_strings(self):
        fn_body = self._get_fn_body()
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
            assert f not in fn_body, f"Forbidden string '{f}'"


# ===========================================================================
# C17-4: CSS
# ===========================================================================
class TestC17CSS:
    def test_row_class(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".rr-row" in content

    def test_severity_classes(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        for cls in [".rr-critical", ".rr-high", ".rr-low", ".rr-clear"]:
            assert cls in content, f"CSS class {cls} must exist"

    def test_overflow_class(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".rr-overflow" in content


# ===========================================================================
# C17-5: Tab 2 통합
# ===========================================================================
class TestC17Integration:
    def test_called_from_render_tab2(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "renderReceiptReview()" in content

    def test_block_between_chronology_and_event_log(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        ic_pos = content.index('id="incident-chronology-block"')
        rr_pos = content.index('id="receipt-review-block"')
        el_pos = content.index('id="event-log-block"')
        assert ic_pos < rr_pos < el_pos

    def test_existing_blocks_preserved(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        for bid in [
            "key-facts-block",
            "loop-ceiling-block",
            "quote-feed-block",
            "venue-status-block",
            "freshness-timeline-block",
            "provenance-block",
            "triage-checklist-block",
            "handoff-receipt-block",
            "incident-chronology-block",
            "event-log-block",
            "incident-overlay",
        ]:
            assert bid in content, f"{bid} must be preserved"


# ===========================================================================
# C17-6: app.state.receipt_store 슬롯
# ===========================================================================
class TestC17AppStateSlot:
    def test_receipt_store_initialized_in_main(self):
        content = MAIN_PATH.read_text(encoding="utf-8")
        assert "app.state.receipt_store" in content

    def test_imports_receipt_store_class(self):
        content = MAIN_PATH.read_text(encoding="utf-8")
        assert "ReceiptStore" in content
