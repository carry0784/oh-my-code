"""
Card C-26: Replay / Audit UI Panel — Tests

검수 범위:
  C26-1: Dashboard panel 블록
  C26-2: JS 렌더링 함수
  C26-3: CSS 스타일
  C26-4: Tab 2 통합
  C26-5: 금지 조항

Sealed layers 미접촉. API 변경 없음. 기존 테스트 파일 미수정.
"""

import sys
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


def _get_fn_body():
    content = TEMPLATE_PATH.read_text(encoding="utf-8")
    fn_start = content.index("function renderAuditReplay")
    fn_end = content.index("function renderKeyFacts")
    return content[fn_start:fn_end]


# ===========================================================================
# C26-1: Dashboard panel 블록
# ===========================================================================
class TestC26Panel:
    def test_block_exists(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="audit-replay-block"' in content

    def test_body_exists(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="audit-replay-body"' in content

    def test_title_correct(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "Audit Replay" in content


# ===========================================================================
# C26-2: JS 렌더링 함수
# ===========================================================================
class TestC26RenderFunction:
    def test_function_exists(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "function renderAuditReplay" in content

    def test_fetches_audit_replay_api(self):
        assert "/dashboard/api/audit-replay" in _get_fn_body()

    def test_not_available_fallback(self):
        assert "NOT AVAILABLE" in _get_fn_body()

    def test_shows_summary_bar(self):
        fn_body = _get_fn_body()
        assert "ar-summary" in fn_body
        assert "incident_summary" in fn_body

    def test_shows_sent_tag(self):
        assert "ar-sent" in _get_fn_body()

    def test_shows_suppressed_tag(self):
        assert "ar-suppressed" in _get_fn_body()

    def test_shows_escalated_tag(self):
        assert "ar-escalated" in _get_fn_body()

    def test_shows_resolved_tag(self):
        assert "ar-resolved" in _get_fn_body()

    def test_shows_timestamp(self):
        assert "executed_at" in _get_fn_body()

    def test_shows_policy_action(self):
        assert "policy.action" in _get_fn_body()

    def test_shows_sender_channels(self):
        fn_body = _get_fn_body()
        assert "channels_delivered" in fn_body
        assert "channels_attempted" in fn_body

    def test_shows_receipt_link(self):
        fn_body = _get_fn_body()
        assert "receipt.id" in fn_body

    def test_shows_error_indicator(self):
        assert "ar-err" in _get_fn_body()

    def test_shows_overflow(self):
        assert "ar-overflow" in _get_fn_body()

    def test_no_forbidden_strings(self):
        fn_body = _get_fn_body()
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
# C26-3: CSS
# ===========================================================================
class TestC26CSS:
    def test_summary_class(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".ar-summary" in content

    def test_step_class(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".ar-step" in content

    def test_action_tag_classes(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        for cls in [".ar-sent", ".ar-suppressed", ".ar-escalated", ".ar-resolved", ".ar-error"]:
            assert cls in content, f"CSS class {cls} must exist"

    def test_overflow_class(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".ar-overflow" in content


# ===========================================================================
# C26-4: Tab 2 통합
# ===========================================================================
class TestC26Integration:
    def test_called_from_render_tab2(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "renderAuditReplay()" in content

    def test_block_between_flow_log_and_event_log(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        fl_pos = content.index('id="flow-log-block"')
        ar_pos = content.index('id="audit-replay-block"')
        el_pos = content.index('id="event-log-block"')
        assert fl_pos < ar_pos < el_pos

    def test_existing_blocks_preserved(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        for bid in [
            "receipt-review-block",
            "flow-log-block",
            "incident-chronology-block",
            "event-log-block",
            "incident-overlay",
        ]:
            assert bid in content, f"{bid} must be preserved"
