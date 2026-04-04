"""
Card C-10: Operator Triage Checklist — Tests

검수 범위:
  C10-1: Operator Panel Triage Checklist 블록
  C10-2: JS 렌더링 함수 — 우선순위 체크리스트 로직
  C10-3: CSS 스타일
  C10-4: Tab 2 통합
  C10-5: 금지 조항 확인

Sealed layers 미접촉. API 변경 없음. 기존 v2 데이터 소비만.
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
    fn_start = content.index("function renderTriageChecklist")
    fn_end = content.index("function renderKeyFacts")
    return content[fn_start:fn_end]


# ===========================================================================
# C10-1: Operator Panel 블록
# ===========================================================================
class TestC10TriageBlock:
    def test_block_exists(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="triage-checklist-block"' in content

    def test_body_exists(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="triage-checklist-body"' in content

    def test_title_correct(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "Operator Triage Checklist" in content


# ===========================================================================
# C10-2: JS 렌더링 함수
# ===========================================================================
class TestC10RenderFunction:
    def test_function_exists(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "function renderTriageChecklist" in content

    def test_checks_backend_unavailable(self):
        fn_body = _get_fn_body()
        assert "BACKEND UNAVAILABLE" in fn_body

    def test_checks_lockdown(self):
        fn_body = _get_fn_body()
        assert "LOCKDOWN" in fn_body

    def test_checks_loop_exceeded(self):
        fn_body = _get_fn_body()
        assert "LOOP CEILING EXCEEDED" in fn_body

    def test_checks_doctrine_violation(self):
        fn_body = _get_fn_body()
        assert "DOCTRINE VIOLATION" in fn_body

    def test_checks_venue_disconnected(self):
        fn_body = _get_fn_body()
        assert "VENUE DISCONNECTED" in fn_body

    def test_checks_quote_feed(self):
        fn_body = _get_fn_body()
        assert "QUOTE FEED" in fn_body

    def test_checks_work_state(self):
        fn_body = _get_fn_body()
        assert "WORK STATE" in fn_body

    def test_checks_trust_degraded(self):
        fn_body = _get_fn_body()
        assert "TRUST DEGRADED" in fn_body

    def test_sorts_by_priority(self):
        fn_body = _get_fn_body()
        assert "items.sort(" in fn_body

    def test_caps_at_max_items(self):
        fn_body = _get_fn_body()
        assert "MAX_ITEMS" in fn_body
        assert "slice(0, MAX_ITEMS)" in fn_body

    def test_shows_all_clear_when_empty(self):
        fn_body = _get_fn_body()
        assert "ALL CLEAR" in fn_body

    def test_shows_overflow_message(self):
        fn_body = _get_fn_body()
        assert "tc-overflow" in fn_body

    def test_steps_are_ordered_list(self):
        """체크리스트 스텝이 ol 태그로 렌더링된다."""
        fn_body = _get_fn_body()
        assert "<ol" in fn_body
        assert "<li>" in fn_body

    def test_references_other_panels(self):
        """다른 패널 참조 가이드가 포함된다."""
        fn_body = _get_fn_body()
        assert "Loop Ceiling Monitor" in fn_body
        assert "Venue Status Monitor" in fn_body
        assert "Freshness Timeline" in fn_body
        assert "Source Provenance" in fn_body

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

    def test_no_auto_recovery_actions(self):
        """자동 복구/실행 로직이 없다."""
        fn_body = _get_fn_body()
        # Strip docstring and comments
        lines = fn_body.split("\n")
        code_lines = []
        in_doc = False
        for line in lines:
            s = line.strip()
            if '"""' in s:
                in_doc = not in_doc
                continue
            if in_doc or s.startswith("//"):
                continue
            code_lines.append(s.lower())
        code = " ".join(code_lines)
        import re

        for pattern in [r"\brestart\b", r"\breset\b", r"\bretry\b"]:
            assert not re.search(pattern, code), f"Recovery action '{pattern}' found"


# ===========================================================================
# C10-3: CSS
# ===========================================================================
class TestC10CSS:
    def test_item_class(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".tc-item" in content

    def test_severity_classes(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        for cls in [".tc-critical", ".tc-warning", ".tc-caution"]:
            assert cls in content, f"CSS class {cls} must exist"

    def test_steps_class(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".tc-steps" in content

    def test_clear_class(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".tc-clear" in content

    def test_overflow_class(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".tc-overflow" in content


# ===========================================================================
# C10-4: Tab 2 통합
# ===========================================================================
class TestC10Integration:
    def test_called_from_render_tab2(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "renderTriageChecklist(data, venueStates)" in content

    def test_block_between_provenance_and_event_log(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        pv_pos = content.index('id="provenance-block"')
        tc_pos = content.index('id="triage-checklist-block"')
        el_pos = content.index('id="event-log-block"')
        assert pv_pos < tc_pos < el_pos

    def test_existing_blocks_preserved(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        for bid in [
            "key-facts-block",
            "loop-ceiling-block",
            "quote-feed-block",
            "venue-status-block",
            "freshness-timeline-block",
            "provenance-block",
            "event-log-block",
            "incident-overlay",
        ]:
            assert bid in content, f"{bid} must be preserved"
