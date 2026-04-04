"""
C-04 Manual Action — 9-Stage Execution Chain & Display/Preview/Action Separation

Phase 1 test-code only. C-04 구현 금지. 활성화 금지.
이 테스트는 9단계 실행 체인 계약과
표시/preview/action 분리 원칙을 코드 수준으로 봉인한다.

대상: C-04 contract에서 정의한 실행 체인
범위: 체인 무결성, 단계별 차단 코드 매핑, UI 봉인 상태
"""

import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = PROJECT_ROOT / "app" / "templates" / "dashboard.html"
DASHBOARD_ROUTE_PATH = PROJECT_ROOT / "app" / "api" / "routes" / "dashboard.py"


# ===========================================================================
# Test-local contract definitions (not production code)
# ===========================================================================

CHAIN_STAGES = (
    "pipeline_ready",
    "preflight_ready",
    "gate_open",
    "approval_ok",
    "policy_ok",
    "risk_ok",
    "auth_ok",
    "scope_ok",
    "evidence_present",
)

STAGE_TO_BLOCK = {
    "pipeline_ready": "PIPELINE_NOT_READY",
    "preflight_ready": "PREFLIGHT_NOT_READY",
    "gate_open": "GATE_CLOSED",
    "approval_ok": "APPROVAL_REQUIRED",
    "policy_ok": "POLICY_BLOCKED",
    "risk_ok": "RISK_NOT_OK",
    "auth_ok": "AUTH_NOT_OK",
    "scope_ok": "SCOPE_NOT_OK",
    "evidence_present": "EVIDENCE_MISSING",
}

# All block codes (chain + sentinel)
ALL_BLOCK_CODES = frozenset(
    {
        "MANUAL_ACTION_DISABLED",
        "PREVIEW_MISSING",
        "PIPELINE_NOT_READY",
        "PREFLIGHT_NOT_READY",
        "GATE_CLOSED",
        "APPROVAL_REQUIRED",
        "POLICY_BLOCKED",
        "RISK_NOT_OK",
        "AUTH_NOT_OK",
        "SCOPE_NOT_OK",
        "EVIDENCE_MISSING",
        "TRACE_INCOMPLETE",
    }
)


def _read_template():
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def _read_dashboard_route():
    return DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")


# ===========================================================================
# CH-1: 9단계 실행 체인 정의 무결성
# ===========================================================================
class TestC04ChainStageDefinition:
    """9단계 실행 체인이 올바르게 정의되어 있는지 검증."""

    def test_chain_has_exactly_9_stages(self):
        """실행 체인은 정확히 9단계여야 한다."""
        assert len(CHAIN_STAGES) == 9

    def test_chain_order_is_fixed(self):
        """체인 순서가 고정되어야 한다. 첫=pipeline, 끝=evidence."""
        assert CHAIN_STAGES[0] == "pipeline_ready"
        assert CHAIN_STAGES[-1] == "evidence_present"

    def test_chain_stages_unique(self):
        """체인 단계에 중복이 없어야 한다."""
        assert len(CHAIN_STAGES) == len(set(CHAIN_STAGES))

    def test_every_stage_has_block_code(self):
        """모든 체인 단계에 대응하는 block code가 있어야 한다."""
        for stage in CHAIN_STAGES:
            assert stage in STAGE_TO_BLOCK, f"No block code for stage: {stage}"

    def test_no_unmapped_stage_in_block_mapping(self):
        """STAGE_TO_BLOCK 매핑에 체인에 없는 단계가 포함되지 않아야 한다."""
        for stage in STAGE_TO_BLOCK:
            assert stage in CHAIN_STAGES, f"Unmapped stage in block mapping: {stage}"


# ===========================================================================
# CH-2: 체인 fail-closed 기본값
# ===========================================================================
class TestC04ChainFailClosedDefault:
    """체인 상태가 불완전하면 반드시 차단되어야 한다."""

    def test_single_missing_stage_blocks_action(self):
        """9단계 중 하나라도 False이면 action 불가."""
        for i, stage in enumerate(CHAIN_STAGES):
            chain_state = {s: True for s in CHAIN_STAGES}
            chain_state[stage] = False
            # 하나라도 False면 전체 action 불가
            action_allowed = all(chain_state[s] for s in CHAIN_STAGES)
            assert action_allowed is False, f"Stage {stage} failed but action still allowed"

    def test_first_missing_stage_determines_block_code(self):
        """첫 번째 실패 단계가 block code를 결정한다."""
        # 앞 단계 실패가 우선
        chain_state = {s: False for s in CHAIN_STAGES}
        first_failed = None
        for stage in CHAIN_STAGES:
            if not chain_state[stage]:
                first_failed = stage
                break
        assert first_failed == "pipeline_ready"
        assert STAGE_TO_BLOCK[first_failed] == "PIPELINE_NOT_READY"

    def test_empty_chain_state_defaults_to_blocked(self):
        """빈 상태는 항상 차단이어야 한다."""
        chain_state = {}
        action_allowed = all(chain_state.get(s, False) for s in CHAIN_STAGES)
        assert action_allowed is False

    def test_none_values_treated_as_false(self):
        """None 값은 False로 처리되어야 한다."""
        chain_state = {s: None for s in CHAIN_STAGES}
        action_allowed = all(chain_state.get(s) for s in CHAIN_STAGES)
        assert action_allowed is False

    def test_all_true_is_only_passing_state(self):
        """9개 모두 True일 때만 action 가능."""
        chain_state = {s: True for s in CHAIN_STAGES}
        action_allowed = all(chain_state[s] for s in CHAIN_STAGES)
        assert action_allowed is True
        # 하나만 빼도 실패
        chain_state["evidence_present"] = False
        action_allowed = all(chain_state[s] for s in CHAIN_STAGES)
        assert action_allowed is False


# ===========================================================================
# CH-3: 표시 / preview / action 분리 검증 (HTML 정적 분석)
# ===========================================================================
class TestC04DisplayPreviewActionSeparation:
    """C-04 카드가 표시되지만 실행 불가능한 상태를 유지하는지 검증."""

    def test_c04_card_exists_in_template(self):
        """C-04 카드 요소가 HTML에 존재해야 한다."""
        html = _read_template()
        assert 'id="t3sc-c04"' in html

    def test_c04_remains_sealed(self):
        """C-04 카드가 sealed 상태를 유지해야 한다."""
        html = _read_template()
        assert "t3sc-sealed" in html

    def test_button_inside_c04_is_disabled_by_default(self):
        """C-04 카드의 execute 버튼은 기본 disabled 상태여야 한다.
        Purpose transition: Phase 5 — button exists but disabled by default."""
        html = _read_template()
        assert 'id="t3sc-c04-exec-btn" disabled' in html

    def test_no_form_inside_c04_card(self):
        """C-04 카드 영역에 form 요소가 없어야 한다."""
        html = _read_template()
        c04_start = html.find('id="t3sc-c04"')
        assert c04_start != -1
        next_card = html.find('id="t3sc-c05"', c04_start)
        c04_section = (
            html[c04_start:next_card] if next_card != -1 else html[c04_start : c04_start + 1000]
        )
        assert "<form" not in c04_section.lower()

    def test_no_onclick_handler_in_c04(self):
        """C-04 카드에 onclick 핸들러가 없어야 한다."""
        html = _read_template()
        c04_start = html.find('id="t3sc-c04"')
        assert c04_start != -1
        next_card = html.find('id="t3sc-c05"', c04_start)
        c04_section = (
            html[c04_start:next_card] if next_card != -1 else html[c04_start : c04_start + 1000]
        )
        assert "onclick" not in c04_section.lower()

    def test_sealed_body_text_exists(self):
        """봉인 텍스트 'Not enabled in this phase'가 존재해야 한다."""
        html = _read_template()
        assert "Not enabled in this phase" in html

    def test_action_endpoint_is_chain_gated(self):
        """C-04 action endpoint가 존재하되 chain-gated이어야 한다.
        Purpose transition: Phase 5 — endpoint exists, chain-validated."""
        route = _read_dashboard_route()
        assert "manual-action/execute" in route
        assert "validate_and_execute" in route

    def test_no_preview_pane_implying_executability(self):
        """C-04 영역에 preview가 실행 가능을 암시하는 UI가 없어야 한다."""
        html = _read_template().lower()
        assert "c04-preview" not in html
        assert "c04-action-preview" not in html


# ===========================================================================
# CH-4: 단계별 Block Code 매핑 무결성
# ===========================================================================
class TestC04ChainStageToBlockCodeMapping:
    """각 체인 단계가 올바른 block code에 매핑되는지 검증."""

    def test_pipeline_maps_to_pipeline_not_ready(self):
        assert STAGE_TO_BLOCK["pipeline_ready"] == "PIPELINE_NOT_READY"

    def test_preflight_maps_to_preflight_not_ready(self):
        assert STAGE_TO_BLOCK["preflight_ready"] == "PREFLIGHT_NOT_READY"

    def test_gate_maps_to_gate_closed(self):
        assert STAGE_TO_BLOCK["gate_open"] == "GATE_CLOSED"

    def test_approval_maps_to_approval_required(self):
        assert STAGE_TO_BLOCK["approval_ok"] == "APPROVAL_REQUIRED"

    def test_all_block_codes_in_registry(self):
        """모든 체인 block code가 전체 block code registry에 포함되어야 한다."""
        for stage, code in STAGE_TO_BLOCK.items():
            assert code in ALL_BLOCK_CODES, f"Block code {code} for stage {stage} not in registry"
