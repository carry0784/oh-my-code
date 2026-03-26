"""
B-14A: Operator Approval (I-06) — 핵심 계약 테스트

대상: app/core/operator_approval.py
범위: 구조, 형태, 결정 논리, 검증, read-only
수정 금지: operator_approval.py 코드 자체는 수정하지 않음
"""

import inspect
from datetime import datetime, timezone

import pytest


# =========================================================================
# Structure
# =========================================================================

class TestApprovalStructure:
    """모듈 존재 및 호출 가능성 확인."""

    def test_module_importable(self):
        import app.core.operator_approval
        assert hasattr(app.core.operator_approval, "issue_approval")

    def test_function_callable(self):
        from app.core.operator_approval import issue_approval
        assert callable(issue_approval)

    def test_validate_approval_current_exists(self):
        from app.core.operator_approval import validate_approval_current
        assert callable(validate_approval_current)


# =========================================================================
# Shape
# =========================================================================

class TestApprovalShape:
    """반환 결과 형태 검증."""

    def test_returns_operator_approval_receipt(self):
        from app.core.operator_approval import issue_approval
        from app.schemas.operator_approval_schema import OperatorApprovalReceipt
        result = issue_approval()
        assert isinstance(result, OperatorApprovalReceipt)

    def test_has_decision_field(self):
        from app.core.operator_approval import issue_approval
        result = issue_approval()
        assert result.decision is not None

    def test_has_approval_id(self):
        from app.core.operator_approval import issue_approval
        result = issue_approval()
        assert result.approval_id is not None
        assert result.approval_id.startswith("APR-")

    def test_has_7_required_fields(self):
        from app.core.operator_approval import issue_approval
        result = issue_approval()
        assert result.gate_snapshot_id is not None
        assert result.preflight_id is not None
        assert result.check_id is not None
        assert result.ops_score is not None
        assert result.security_state is not None
        assert result.timestamp is not None
        assert result.approval_expiry_at is not None

    def test_has_rejection_reasons_list(self):
        from app.core.operator_approval import issue_approval
        result = issue_approval()
        assert isinstance(result.rejection_reasons, list)


# =========================================================================
# Decision Logic
# =========================================================================

class TestApprovalDecision:
    """결정 논리 핵심 계약."""

    def test_decision_is_valid_enum(self):
        from app.core.operator_approval import issue_approval
        from app.schemas.operator_approval_schema import ApprovalDecision
        result = issue_approval()
        assert result.decision in (ApprovalDecision.APPROVED, ApprovalDecision.REJECTED)

    def test_rejected_implies_operator_action_required(self):
        from app.core.operator_approval import issue_approval
        result = issue_approval()
        if result.decision.value == "REJECTED":
            assert result.operator_action_required is True

    def test_receipt_note_exists(self):
        from app.core.operator_approval import issue_approval
        result = issue_approval()
        assert hasattr(result, "receipt_note")


# =========================================================================
# Validation
# =========================================================================

class TestApprovalValidation:
    """7필드 검증 및 scope 계약."""

    def test_test_env_produces_rejection(self):
        """테스트 환경에서는 gate/preflight/check 실패로 REJECTED 예상."""
        from app.core.operator_approval import issue_approval
        result = issue_approval()
        # 테스트 환경에서 gate이 없으므로 rejection reason 존재
        assert len(result.rejection_reasons) > 0
        assert result.decision.value == "REJECTED"

    def test_specific_symbol_scope_without_target_rejected(self):
        from app.core.operator_approval import issue_approval
        from app.schemas.operator_approval_schema import ApprovalScope, ApprovalRejectionReason
        result = issue_approval(
            approval_scope=ApprovalScope.SPECIFIC_SYMBOL_ONLY,
            target_symbol=None,
        )
        reason_values = [r.value for r in result.rejection_reasons]
        assert "MISSING_TARGET_SYMBOL" in reason_values

    def test_expiry_is_after_timestamp(self):
        from app.core.operator_approval import issue_approval
        result = issue_approval()
        ts = datetime.fromisoformat(result.timestamp)
        expiry = datetime.fromisoformat(result.approval_expiry_at)
        assert expiry > ts

    def test_default_scope_is_no_execution(self):
        from app.core.operator_approval import issue_approval
        from app.schemas.operator_approval_schema import ApprovalScope
        result = issue_approval()
        assert result.approval_scope == ApprovalScope.NO_EXECUTION


# =========================================================================
# Expiry Validation
# =========================================================================

class TestApprovalExpiry:
    """만료 검증."""

    def test_validate_approval_current_returns_bool(self):
        from app.core.operator_approval import issue_approval, validate_approval_current
        receipt = issue_approval()
        result = validate_approval_current(receipt)
        assert isinstance(result, bool)

    def test_rejected_receipt_is_not_current(self):
        from app.core.operator_approval import issue_approval, validate_approval_current
        receipt = issue_approval()
        if receipt.decision.value == "REJECTED":
            assert validate_approval_current(receipt) is False


# =========================================================================
# Read-Only
# =========================================================================

class TestApprovalReadOnly:
    """소스 코드에 쓰기/실행 동작이 없음을 검증."""

    def test_no_write_actions_in_source(self):
        import app.core.operator_approval as mod
        src = inspect.getsource(mod)
        forbidden = ["db.add(", "db.delete(", "session.commit(", "submit_order", "execute_trade"]
        for f in forbidden:
            assert f not in src, f"Forbidden write action found: {f}"

    def test_no_trading_actions_in_source(self):
        import app.core.operator_approval as mod
        src = inspect.getsource(mod)
        forbidden = ["trading_resume", "capital_expand"]
        for f in forbidden:
            assert f not in src, f"Forbidden trading action found: {f}"

    def test_no_order_submission_in_source(self):
        import app.core.operator_approval as mod
        src = inspect.getsource(mod)
        assert "submit_order" not in src
        assert "execute_trade" not in src
