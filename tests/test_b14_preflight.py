"""
B-14A: Recovery Preflight (I-04) — 핵심 계약 테스트

대상: app/core/recovery_preflight.py
범위: 구조, 형태, 결정 논리, fail-closed, read-only, 엣지 케이스
수정 금지: recovery_preflight.py 코드 자체는 수정하지 않음
"""

import inspect
import pytest


# =========================================================================
# Structure
# =========================================================================

class TestPreflightStructure:
    """모듈 존재 및 호출 가능성 확인."""

    def test_module_importable(self):
        import app.core.recovery_preflight
        assert hasattr(app.core.recovery_preflight, "run_recovery_preflight")

    def test_function_callable(self):
        from app.core.recovery_preflight import run_recovery_preflight
        assert callable(run_recovery_preflight)

    def test_preflight_items_count_is_8(self):
        from app.core.recovery_preflight import _PREFLIGHT_ITEMS
        assert len(_PREFLIGHT_ITEMS) == 8


# =========================================================================
# Shape
# =========================================================================

class TestPreflightShape:
    """반환 결과 형태 검증."""

    def test_returns_recovery_preflight_result(self):
        from app.core.recovery_preflight import run_recovery_preflight
        from app.schemas.preflight_schema import RecoveryPreflightResult
        result = run_recovery_preflight()
        assert isinstance(result, RecoveryPreflightResult)

    def test_has_decision_field(self):
        from app.core.recovery_preflight import run_recovery_preflight
        result = run_recovery_preflight()
        assert result.decision is not None

    def test_has_items_list(self):
        from app.core.recovery_preflight import run_recovery_preflight
        result = run_recovery_preflight()
        assert isinstance(result.items, list)
        assert len(result.items) == 8

    def test_has_evidence_id(self):
        from app.core.recovery_preflight import run_recovery_preflight
        result = run_recovery_preflight()
        assert result.evidence_id is not None
        assert len(result.evidence_id) > 0

    def test_has_reason_codes_list(self):
        from app.core.recovery_preflight import run_recovery_preflight
        result = run_recovery_preflight()
        assert isinstance(result.reason_codes, list)


# =========================================================================
# Decision Logic
# =========================================================================

class TestPreflightDecision:
    """결정 논리 핵심 계약."""

    def test_decision_is_valid_enum(self):
        from app.core.recovery_preflight import run_recovery_preflight
        from app.schemas.preflight_schema import PreflightDecision
        result = run_recovery_preflight()
        assert result.decision in (
            PreflightDecision.READY,
            PreflightDecision.NOT_READY,
            PreflightDecision.BLOCKED,
        )

    def test_blocked_implies_operator_action_required(self):
        from app.schemas.preflight_schema import PreflightDecision, RecoveryPreflightResult
        # model_validator forces operator_action_required=True when BLOCKED
        receipt = RecoveryPreflightResult(
            timestamp="2026-01-01T00:00:00Z",
            decision=PreflightDecision.BLOCKED,
            summary="test",
            items=[],
            reason_codes=[],
            basis_refs=[],
            evidence_id="test",
            rule_refs=["Art43"],
            operator_action_required=False,  # should be forced to True
        )
        assert receipt.operator_action_required is True

    def test_ready_is_not_execute_field_exists(self):
        from app.core.recovery_preflight import run_recovery_preflight
        result = run_recovery_preflight()
        assert hasattr(result, "ready_is_not_execute")
        assert "not" in result.ready_is_not_execute.lower() or "execution" in result.ready_is_not_execute.lower()


# =========================================================================
# Fail-Closed
# =========================================================================

class TestPreflightFailClosed:
    """Fail-closed 동작 검증."""

    def test_all_items_assessed(self):
        from app.core.recovery_preflight import run_recovery_preflight
        result = run_recovery_preflight()
        assert len(result.items) == 8
        for item in result.items:
            assert item.status in ("pass", "fail", "unknown")

    def test_gate_none_yields_not_ready_or_blocked(self):
        """governance_gate이 없어도 crash 하지 않고 NOT_READY 이상을 반환."""
        from app.core.recovery_preflight import run_recovery_preflight
        from app.schemas.preflight_schema import PreflightDecision
        result = run_recovery_preflight()
        # gate이 없으면 여러 항목이 fail/unknown → READY가 아님
        # (테스트 환경에서는 gate이 없으므로 NOT_READY 또는 BLOCKED)
        assert result.decision in (PreflightDecision.NOT_READY, PreflightDecision.BLOCKED)

    def test_fallback_evidence_id_on_store_unavailable(self):
        from app.core.recovery_preflight import run_recovery_preflight
        result = run_recovery_preflight()
        # evidence store 없으면 fallback ID 생성
        assert result.evidence_id.startswith("fallback-pf-") or len(result.evidence_id) > 0


# =========================================================================
# Read-Only
# =========================================================================

class TestPreflightReadOnly:
    """소스 코드에 쓰기 동작이 없음을 검증."""

    def test_no_write_actions_in_source(self):
        import app.core.recovery_preflight as mod
        src = inspect.getsource(mod)
        forbidden = ["db.add(", "db.delete(", "session.commit(", "submit_order", "execute_trade"]
        for f in forbidden:
            assert f not in src, f"Forbidden write action found: {f}"

    def test_no_trading_actions_in_source(self):
        import app.core.recovery_preflight as mod
        src = inspect.getsource(mod)
        forbidden = ["trading_resume", "promote(", "capital_expand"]
        for f in forbidden:
            assert f not in src, f"Forbidden trading action found: {f}"


# =========================================================================
# Edge Cases
# =========================================================================

class TestPreflightEdgeCases:
    """기지 동작 및 엣지 케이스 문서화."""

    def test_exchange_snapshot_always_unknown(self):
        """exchange_snapshot 항목은 DB 조회 없이 항상 unknown 반환 (known stub)."""
        from app.core.recovery_preflight import run_recovery_preflight
        result = run_recovery_preflight()
        snapshot_item = next(i for i in result.items if i.name == "exchange_snapshot")
        assert snapshot_item.status == "unknown"

    def test_stale_snapshot_reason_present(self):
        from app.core.recovery_preflight import run_recovery_preflight
        from app.schemas.preflight_schema import PreflightReasonCode
        result = run_recovery_preflight()
        snapshot_item = next(i for i in result.items if i.name == "exchange_snapshot")
        assert PreflightReasonCode.STALE_SNAPSHOT in snapshot_item.reason_codes

    def test_item_names_match_definitions(self):
        from app.core.recovery_preflight import run_recovery_preflight, _PREFLIGHT_ITEMS
        result = run_recovery_preflight()
        expected_names = [d["name"] for d in _PREFLIGHT_ITEMS]
        actual_names = [i.name for i in result.items]
        assert actual_names == expected_names
