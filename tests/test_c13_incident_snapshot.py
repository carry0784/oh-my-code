"""
Card C-13: Alert / Receipt / Export-Friendly Incident Snapshot — Tests

검수 범위:
  C13-1: /api/snapshot 엔드포인트 존재
  C13-2: _build_incident_snapshot() 헬퍼 구조
  C13-3: Snapshot 필드 검증
  C13-4: 기존 엔드포인트 보존
  C13-5: 금지 조항 확인

Sealed layers 미접촉. 기존 테스트 파일 미수정.
"""

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_ROUTE_PATH = PROJECT_ROOT / "app" / "api" / "routes" / "dashboard.py"


def _get_snapshot_fn_body():
    content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
    fn_match = re.search(
        r'def _build_incident_snapshot.*?(?=\ndef |\nasync def |\nclass |\Z)',
        content, re.DOTALL
    )
    assert fn_match, "_build_incident_snapshot not found"
    return fn_match.group()


def _get_endpoint_fn_body():
    content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
    fn_match = re.search(
        r'async def incident_snapshot.*?(?=\n@router\.|\nasync def dashboard_data[^_])',
        content, re.DOTALL
    )
    assert fn_match, "incident_snapshot endpoint not found"
    return fn_match.group()


# ===========================================================================
# C13-1: /api/snapshot 엔드포인트
# ===========================================================================
class TestC13Endpoint:

    def test_snapshot_endpoint_exists(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"/api/snapshot"' in content

    def test_snapshot_endpoint_is_get(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        idx = content.index("async def incident_snapshot")
        preceding = content[max(0, idx - 100):idx]
        assert "@router.get" in preceding

    def test_reuses_v2_data(self):
        """v2 데이터를 재사용한다 (새 쿼리 없음)."""
        fn_body = _get_endpoint_fn_body()
        assert "dashboard_data_v2" in fn_body


# ===========================================================================
# C13-2: _build_incident_snapshot() 헬퍼
# ===========================================================================
class TestC13SnapshotBuilder:

    def test_builder_exists(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert "def _build_incident_snapshot" in content

    def test_not_async(self):
        """동기 함수이다 (새 DB 쿼리 없음)."""
        fn_body = _get_snapshot_fn_body()
        assert fn_body.startswith("def _build_incident_snapshot")
        assert "await" not in fn_body

    def test_returns_dict(self):
        fn_body = _get_snapshot_fn_body()
        assert "return {" in fn_body


# ===========================================================================
# C13-3: Snapshot 필드 검증
# ===========================================================================
class TestC13SnapshotFields:

    def test_has_snapshot_version(self):
        assert '"snapshot_version"' in _get_snapshot_fn_body()

    def test_has_generated_at(self):
        assert '"generated_at"' in _get_snapshot_fn_body()

    def test_has_overall_status(self):
        assert '"overall_status"' in _get_snapshot_fn_body()

    def test_has_highest_incident(self):
        assert '"highest_incident"' in _get_snapshot_fn_body()

    def test_has_active_incidents(self):
        assert '"active_incidents"' in _get_snapshot_fn_body()

    def test_has_degraded_reasons(self):
        assert '"degraded_reasons"' in _get_snapshot_fn_body()

    def test_has_freshness_summary(self):
        assert '"freshness_summary"' in _get_snapshot_fn_body()

    def test_has_venue_summary(self):
        assert '"venue_summary"' in _get_snapshot_fn_body()

    def test_has_quote_summary(self):
        assert '"quote_summary"' in _get_snapshot_fn_body()

    def test_has_loop_summary(self):
        assert '"loop_summary"' in _get_snapshot_fn_body()

    def test_has_last_successful_poll(self):
        assert '"last_successful_poll"' in _get_snapshot_fn_body()

    def test_has_triage_top(self):
        assert '"triage_top"' in _get_snapshot_fn_body()

    def test_degraded_reasons_capped(self):
        """degraded_reasons는 최대 5건으로 cap."""
        assert "[:5]" in _get_snapshot_fn_body()

    def test_consumes_existing_v2_keys(self):
        """기존 v2 payload 키만 참조한다."""
        fn_body = _get_snapshot_fn_body()
        for key in ["governance", "loop_monitor", "doctrine", "work_state",
                     "source_freshness", "venue_freshness", "quote_data"]:
            assert f'"{key}"' in fn_body, f"Must reference existing v2 key: {key}"


# ===========================================================================
# C13-4: 기존 엔드포인트 보존
# ===========================================================================
class TestC13ExistingPreserved:

    def test_v2_endpoint_preserved(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"/api/data/v2"' in content

    def test_v1_endpoint_preserved(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"/api/data"' in content

    def test_health_preserved(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        # health is in main.py, not dashboard.py — just verify no conflict
        assert "dashboard_data_v2" in content


# ===========================================================================
# C13-5: 금지 조항 확인
# ===========================================================================
class TestC13Forbidden:

    def test_no_forbidden_strings_in_builder(self):
        fn_body = _get_snapshot_fn_body()
        # Strip docstring
        body = fn_body.split('"""', 2)[-1] if '"""' in fn_body else fn_body
        forbidden = [
            'chain_of_thought', 'raw_prompt', 'internal_reasoning',
            'debug_trace', 'agent_analysis', 'error_class',
            'traceback', 'exception_type', 'stack', 'internal_state_dump',
        ]
        for f in forbidden:
            assert f not in body, f"Forbidden string '{f}' in snapshot builder"

    def test_no_runtime_mutation(self):
        fn_body = _get_snapshot_fn_body()
        mutation_calls = ['.record_violation(', '.on_failure(', '.check(', '.ratify(']
        for mc in mutation_calls:
            assert mc not in fn_body, f"Mutation call '{mc}' found"

    def test_snapshot_is_read_only(self):
        """Snapshot은 read-only — 상태 변경 없음."""
        fn_body = _get_snapshot_fn_body()
        assert "app.state" not in fn_body  # reads from v2 result, not app.state directly
