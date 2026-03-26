"""
Card C-09: Source Provenance / Evidence Trace Visibility — Tests

검수 범위:
  C09-1: API provenance 헬퍼
  C09-2: Operator Panel Source Provenance 블록
  C09-3: JS 렌더링 함수
  C09-4: CSS 스타일
  C09-5: Tab 2 통합
  C09-6: 금지 조항 확인

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
TEMPLATE_PATH = PROJECT_ROOT / "app" / "templates" / "dashboard.html"
CSS_PATH = PROJECT_ROOT / "app" / "static" / "css" / "dashboard.css"
DASHBOARD_ROUTE_PATH = PROJECT_ROOT / "app" / "api" / "routes" / "dashboard.py"


# ===========================================================================
# C09-1: API provenance 헬퍼
# ===========================================================================
class TestC09APIHelper:

    def _get_fn_body(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        fn_match = re.search(
            r'def _get_provenance_metadata.*?(?=\ndef |\Z)',
            content, re.DOTALL
        )
        assert fn_match, "_get_provenance_metadata not found"
        return fn_match.group()

    def test_helper_exists(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert "def _get_provenance_metadata" in content

    def test_v2_returns_provenance_key(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"provenance"' in content

    def test_returns_entries_list(self):
        assert '"entries"' in self._get_fn_body()

    def test_entries_have_state_field(self):
        assert '"state"' in self._get_fn_body()

    def test_entries_have_source_field(self):
        assert '"source"' in self._get_fn_body()

    def test_entries_have_basis_field(self):
        assert '"basis"' in self._get_fn_body()

    def test_entries_have_data_origin_field(self):
        assert '"data_origin"' in self._get_fn_body()

    def test_covers_governance(self):
        assert '"governance"' in self._get_fn_body()

    def test_covers_loop_health(self):
        assert '"loop_health"' in self._get_fn_body()

    def test_covers_work_state(self):
        assert '"work_state"' in self._get_fn_body()

    def test_covers_trust_state(self):
        assert '"trust_state"' in self._get_fn_body()

    def test_covers_doctrine(self):
        assert '"doctrine"' in self._get_fn_body()

    def test_covers_venue_freshness(self):
        assert '"venue_freshness"' in self._get_fn_body()

    def test_covers_quote_feed(self):
        assert '"quote_feed"' in self._get_fn_body()

    def test_no_new_db_queries(self):
        fn_body = self._get_fn_body()
        assert "await" not in fn_body
        assert "db.execute" not in fn_body

    def test_no_forbidden_strings(self):
        fn_body = self._get_fn_body()
        # Strip docstring before checking
        body_after_docstring = fn_body.split('"""', 2)[-1] if '"""' in fn_body else fn_body
        forbidden = [
            'chain_of_thought', 'raw_prompt', 'internal_reasoning',
            'debug_trace', 'agent_analysis', 'error_class',
        ]
        for f in forbidden:
            assert f not in body_after_docstring, f"Forbidden string '{f}' in provenance helper code"


# ===========================================================================
# C09-2: Operator Panel 블록
# ===========================================================================
class TestC09ProvenanceBlock:

    def test_block_exists(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="provenance-block"' in content

    def test_body_exists(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="provenance-body"' in content

    def test_title_correct(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "Source Provenance" in content


# ===========================================================================
# C09-3: JS 렌더링 함수
# ===========================================================================
class TestC09RenderFunction:

    def _get_fn_body(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = content.index("function renderSourceProvenance")
        fn_end = content.index("function renderKeyFacts")
        return content[fn_start:fn_end]

    def test_function_exists(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "function renderSourceProvenance" in content

    def test_references_provenance_data(self):
        assert "data.provenance" in self._get_fn_body()

    def test_not_available_fallback(self):
        assert "NOT AVAILABLE" in self._get_fn_body()

    def test_shows_state_name(self):
        assert "entry.state" in self._get_fn_body()

    def test_shows_data_origin(self):
        assert "data_origin" in self._get_fn_body()

    def test_shows_basis(self):
        assert "entry.basis" in self._get_fn_body()

    def test_origin_classes(self):
        fn_body = self._get_fn_body()
        assert "pv-connected" in fn_body
        assert "pv-disconnected" in fn_body
        assert "pv-fallback" in fn_body

    def test_no_forbidden_strings(self):
        fn_body = self._get_fn_body()
        forbidden = [
            'agent_analysis', 'raw_prompt', 'chain_of_thought',
            'internal_reasoning', 'debug_trace', 'error_class',
            'traceback', 'exception_type', 'stack', 'internal_state_dump',
        ]
        for f in forbidden:
            assert f not in fn_body, f"Forbidden string '{f}' in provenance render"


# ===========================================================================
# C09-4: CSS
# ===========================================================================
class TestC09CSS:

    def test_row_class(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".pv-row" in content

    def test_origin_classes(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        for cls in ['.pv-connected', '.pv-disconnected', '.pv-fallback']:
            assert cls in content, f"CSS class {cls} must exist"

    def test_state_class(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".pv-state" in content

    def test_basis_class(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".pv-basis" in content


# ===========================================================================
# C09-5: Tab 2 통합
# ===========================================================================
class TestC09Integration:

    def test_called_from_render_tab2(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "renderSourceProvenance(data)" in content

    def test_block_between_freshness_and_event_log(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        ft_pos = content.index('id="freshness-timeline-block"')
        pv_pos = content.index('id="provenance-block"')
        el_pos = content.index('id="event-log-block"')
        assert ft_pos < pv_pos < el_pos

    def test_existing_blocks_preserved(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        for bid in ['key-facts-block', 'loop-ceiling-block', 'quote-feed-block',
                     'venue-status-block', 'freshness-timeline-block',
                     'event-log-block', 'incident-overlay']:
            assert bid in content, f"{bid} must be preserved"
