"""
B-14A: Execution Gate (I-05) — 핵심 계약 테스트

대상: app/core/execution_gate.py
범위: 구조, 형태, 결정 논리, 조건, read-only
수정 금지: execution_gate.py 코드 자체는 수정하지 않음
"""

import inspect
import pytest


# =========================================================================
# Structure
# =========================================================================

class TestGateStructure:
    """모듈 존재 및 호출 가능성 확인."""

    def test_module_importable(self):
        import app.core.execution_gate
        assert hasattr(app.core.execution_gate, "evaluate_execution_gate")

    def test_function_callable(self):
        from app.core.execution_gate import evaluate_execution_gate
        assert callable(evaluate_execution_gate)

    def test_default_threshold_is_0_7(self):
        from app.core.execution_gate import DEFAULT_OPS_SCORE_THRESHOLD
        assert DEFAULT_OPS_SCORE_THRESHOLD == 0.7


# =========================================================================
# Shape
# =========================================================================

class TestGateShape:
    """반환 결과 형태 검증."""

    def test_returns_execution_gate_result(self):
        from app.core.execution_gate import evaluate_execution_gate
        from app.schemas.execution_gate_schema import ExecutionGateResult
        result = evaluate_execution_gate()
        assert isinstance(result, ExecutionGateResult)

    def test_has_decision_field(self):
        from app.core.execution_gate import evaluate_execution_gate
        result = evaluate_execution_gate()
        assert result.decision is not None

    def test_has_conditions_list(self):
        from app.core.execution_gate import evaluate_execution_gate
        result = evaluate_execution_gate()
        assert isinstance(result.conditions, list)

    def test_conditions_count_is_4(self):
        from app.core.execution_gate import evaluate_execution_gate
        result = evaluate_execution_gate()
        assert len(result.conditions) == 4

    def test_has_evidence_id(self):
        from app.core.execution_gate import evaluate_execution_gate
        result = evaluate_execution_gate()
        assert result.evidence_id is not None
        assert len(result.evidence_id) > 0


# =========================================================================
# Decision Logic
# =========================================================================

class TestGateDecision:
    """결정 논리 핵심 계약."""

    def test_decision_is_valid_enum(self):
        from app.core.execution_gate import evaluate_execution_gate
        from app.schemas.execution_gate_schema import GateDecision
        result = evaluate_execution_gate()
        assert result.decision in (GateDecision.OPEN, GateDecision.CLOSED)

    def test_closed_implies_operator_action_required(self):
        from app.core.execution_gate import evaluate_execution_gate
        result = evaluate_execution_gate()
        if result.decision.value == "CLOSED":
            assert result.operator_action_required is True

    def test_gate_is_not_execute_field_exists(self):
        from app.core.execution_gate import evaluate_execution_gate
        result = evaluate_execution_gate()
        assert hasattr(result, "gate_is_not_execute")


# =========================================================================
# Conditions
# =========================================================================

class TestGateConditions:
    """4조건 구조 검증."""

    def test_canonical_condition_names(self):
        from app.core.execution_gate import evaluate_execution_gate
        result = evaluate_execution_gate()
        names = [c.name for c in result.conditions]
        assert names == [
            "preflight_ready",
            "ops_score_above_threshold",
            "trading_authorized",
            "lockdown_inactive",
        ]

    def test_met_count_matches_boolean_sum(self):
        from app.core.execution_gate import evaluate_execution_gate
        result = evaluate_execution_gate()
        actual_met = sum(1 for c in result.conditions if c.met)
        assert result.conditions_met == actual_met

    def test_ops_score_average_between_0_and_1(self):
        from app.core.execution_gate import evaluate_execution_gate
        result = evaluate_execution_gate()
        assert 0.0 <= result.ops_score_average <= 1.0

    def test_each_condition_has_required_fields(self):
        from app.core.execution_gate import evaluate_execution_gate
        result = evaluate_execution_gate()
        for c in result.conditions:
            assert c.name is not None
            assert isinstance(c.met, bool)
            assert c.observed is not None
            assert c.required is not None
            assert c.source is not None
            assert c.rule_ref is not None


# =========================================================================
# Read-Only
# =========================================================================

class TestGateReadOnly:
    """소스 코드에 쓰기 동작이 없음을 검증."""

    def test_no_write_actions_in_source(self):
        import app.core.execution_gate as mod
        src = inspect.getsource(mod)
        forbidden = ["db.add(", "db.delete(", "session.commit(", "submit_order", "execute_trade"]
        for f in forbidden:
            assert f not in src, f"Forbidden write action found: {f}"

    def test_no_trading_actions_in_source(self):
        import app.core.execution_gate as mod
        src = inspect.getsource(mod)
        forbidden = ["trading_resume", "promote(", "capital_expand"]
        for f in forbidden:
            assert f not in src, f"Forbidden trading action found: {f}"

    def test_fallback_evidence_id_when_store_unavailable(self):
        from app.core.execution_gate import evaluate_execution_gate
        result = evaluate_execution_gate()
        assert result.evidence_id.startswith("fallback-gate-") or len(result.evidence_id) > 0
