"""
Tab 3 Safe Cards — C-01~C-09 (except C-04) read-only 검증

검증 대상:
- Safe Card 8개 HTML 존재
- C-04 봉인 상태
- 실행 버튼/트리거/write action 부재
- 추천/예측/AI 판단 문구 부재
- fail-closed 렌더링 함수 존재
"""

import pytest
from pathlib import Path


class TestTab3SafeCardElements:
    """Tab 3 Safe Card HTML 요소 존재 확인."""

    def test_c01_exists(self):
        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        assert 'id="t3sc-c01"' in html

    def test_c02_exists(self):
        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        assert 'id="t3sc-c02"' in html

    def test_c03_exists(self):
        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        assert 'id="t3sc-c03"' in html

    def test_c04_sealed(self):
        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        assert 'id="t3sc-c04"' in html
        assert "Not enabled in this phase" in html

    def test_c04_has_sealed_class(self):
        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        assert "t3sc-sealed" in html

    def test_c05_exists(self):
        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        assert 'id="t3sc-c05"' in html

    def test_c06_exists(self):
        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        assert 'id="t3sc-c06"' in html

    def test_c07_exists(self):
        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        assert 'id="t3sc-c07"' in html

    def test_c08_exists(self):
        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        assert 'id="t3sc-c08"' in html

    def test_c09_exists(self):
        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        assert 'id="t3sc-c09"' in html


class TestTab3NoActionElements:
    """Tab 3에 실행 버튼/트리거/write action이 없는지 확인."""

    def test_no_execute_button(self):
        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        # Tab 3 Safe Card 영역에 실행 버튼이 없어야 함
        assert "execute now" not in html.lower()
        assert "ready to trade" not in html.lower()

    def test_no_submit_action_in_safe_cards(self):
        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        assert "recommended action" not in html.lower()
        assert "likely executable" not in html.lower()
        assert "should proceed" not in html.lower()


class TestTab3RenderFunctions:
    """Tab 3 Safe Card JS 렌더 함수 존재 확인."""

    def test_render_tab3_safe_cards_exists(self):
        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        assert "renderTab3SafeCards" in html

    def test_render_c01_exists(self):
        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        assert "_renderC01" in html

    def test_render_c02_exists(self):
        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        assert "_renderC02" in html

    def test_render_c03_exists(self):
        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        assert "_renderC03" in html

    def test_render_c05_exists(self):
        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        assert "_renderC05" in html

    def test_render_c06_exists(self):
        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        assert "_renderC06" in html

    def test_render_c07_exists(self):
        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        assert "_renderC07" in html

    def test_render_c08_exists(self):
        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        assert "_renderC08" in html

    def test_render_c09_exists(self):
        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        assert "_renderC09" in html

    def test_render_c04_is_sealed_read_only(self):
        """C-04 렌더 함수가 존재하되, sealed/disabled/read-only여야 함.
        Purpose transition: absence → disabled-only renderer (control reinforcement)."""
        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        assert "_renderC04" in html
        # Must remain sealed — no action-capable elements
        start = html.find("function _renderC04")
        assert start != -1
        body = html[start : start + 2000].lower()
        assert "button" not in body
        assert "onclick" not in body
        assert "<form" not in body
        assert "fetch(" not in body


class TestTab3FailClosed:
    """Fail-closed 패턴 확인."""

    def test_unavailable_class_exists(self):
        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        assert "t3sc-unavailable" in html

    def test_fail_closed_in_render(self):
        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        assert "Unavailable" in html

    def test_section_titles_exist(self):
        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        assert "Control Context" in html
        assert "Action Console" in html
        assert "Execution Log" in html
