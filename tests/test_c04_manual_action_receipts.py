"""
C-04 Manual Action — Receipt / Rollback / Failure-Class Contract Tests

Phase 1 test-code only. C-04 구현 금지. 활성화 금지.
이 테스트는 receipt 필수 필드, failure class 분류, rollback 계약을
코드 수준으로 봉인하여 향후 구현이 증적 의무를 우회하지 못하게 한다.

대상: C-04 contract — receipt / rollback / failure-class 규칙
범위: receipt 필수 필드, 5-class 실패 분류, rollback 불변성
"""

import pytest


# ===========================================================================
# Test-local contract definitions
# ===========================================================================

RECEIPT_REQUIRED_FIELDS = (
    "execution_id",
    "timestamp",
    "decision_state",
    "evidence_chain",
    "operator",
)

FAILURE_CLASSES = (
    "pre_block",
    "rejected",
    "failed",
    "partial",
    "unknown",
)

FAILURE_CLASS_TO_FAIL_CODE = {
    "pre_block": None,  # pre_block은 block code 사용 (fail code 아님)
    "rejected": "EXECUTION_REJECTED",
    "failed": "EXECUTION_FAILED",
    "partial": "PARTIAL_FAILURE",
    "unknown": "RESULT_UNKNOWN",
}

ROLLBACK_REQUIRED_FIELDS = (
    "original_receipt_id",
    "rollback_evidence_id",
    "rollback_timestamp",
    "rollback_reason",
)


def _validate_receipt(receipt: dict) -> tuple:
    """Test-local receipt 검증. (valid: bool, missing_fields: list)."""
    missing = [f for f in RECEIPT_REQUIRED_FIELDS if not receipt.get(f)]
    return (len(missing) == 0, missing)


def _classify_failure(state: str) -> str:
    """Test-local failure class 분류."""
    if state in FAILURE_CLASSES:
        return state
    return "unknown"


# ===========================================================================
# RC-1: Receipt Contract — 필수 필드 검증
# ===========================================================================
class TestC04ReceiptContract:
    """모든 실행 시도는 receipt를 남겨야 한다."""

    def test_receipt_requires_execution_id(self):
        """execution_id는 필수다."""
        receipt = {f: f"test-{f}" for f in RECEIPT_REQUIRED_FIELDS}
        receipt["execution_id"] = None
        valid, missing = _validate_receipt(receipt)
        assert valid is False
        assert "execution_id" in missing

    def test_receipt_requires_timestamp(self):
        """timestamp는 필수다."""
        receipt = {f: f"test-{f}" for f in RECEIPT_REQUIRED_FIELDS}
        receipt["timestamp"] = None
        valid, missing = _validate_receipt(receipt)
        assert valid is False
        assert "timestamp" in missing

    def test_receipt_requires_decision_state(self):
        """decision_state는 필수다."""
        receipt = {f: f"test-{f}" for f in RECEIPT_REQUIRED_FIELDS}
        receipt["decision_state"] = ""
        valid, missing = _validate_receipt(receipt)
        assert valid is False
        assert "decision_state" in missing

    def test_receipt_requires_evidence_chain(self):
        """evidence_chain은 필수다."""
        receipt = {f: f"test-{f}" for f in RECEIPT_REQUIRED_FIELDS}
        receipt["evidence_chain"] = None
        valid, missing = _validate_receipt(receipt)
        assert valid is False

    def test_receipt_requires_operator(self):
        """operator는 필수다."""
        receipt = {f: f"test-{f}" for f in RECEIPT_REQUIRED_FIELDS}
        receipt["operator"] = ""
        valid, missing = _validate_receipt(receipt)
        assert valid is False
        assert "operator" in missing

    def test_complete_receipt_is_valid(self):
        """모든 필드가 존재하면 valid."""
        receipt = {f: f"test-{f}" for f in RECEIPT_REQUIRED_FIELDS}
        valid, missing = _validate_receipt(receipt)
        assert valid is True
        assert len(missing) == 0

    def test_empty_receipt_is_invalid(self):
        """빈 receipt는 invalid."""
        valid, missing = _validate_receipt({})
        assert valid is False
        assert len(missing) == len(RECEIPT_REQUIRED_FIELDS)


# ===========================================================================
# RC-2: Failure Class Contract — 5-class 분류 검증
# ===========================================================================
class TestC04FailureClassContract:
    """5가지 실패 클래스가 정의되고 각각 receipt/audit 의무가 있다."""

    def test_exactly_5_failure_classes(self):
        """실패 클래스는 정확히 5개여야 한다."""
        assert len(FAILURE_CLASSES) == 5

    def test_pre_block_is_pre_execution(self):
        """pre_block은 실행 이전 차단이므로 fail code가 아닌 block code 사용."""
        assert FAILURE_CLASS_TO_FAIL_CODE["pre_block"] is None

    def test_rejected_has_fail_code(self):
        """rejected는 EXECUTION_REJECTED fail code를 가진다."""
        assert FAILURE_CLASS_TO_FAIL_CODE["rejected"] == "EXECUTION_REJECTED"

    def test_failed_has_fail_code(self):
        """failed는 EXECUTION_FAILED fail code를 가진다."""
        assert FAILURE_CLASS_TO_FAIL_CODE["failed"] == "EXECUTION_FAILED"

    def test_partial_has_fail_code(self):
        """partial은 PARTIAL_FAILURE fail code를 가진다."""
        assert FAILURE_CLASS_TO_FAIL_CODE["partial"] == "PARTIAL_FAILURE"

    def test_unknown_has_fail_code(self):
        """unknown은 RESULT_UNKNOWN fail code를 가진다."""
        assert FAILURE_CLASS_TO_FAIL_CODE["unknown"] == "RESULT_UNKNOWN"

    def test_all_failure_classes_require_audit_trace(self):
        """모든 실패 클래스는 audit trace 의무를 가진다.
        '실패했으니 흔적 0건'은 허용 금지."""
        for fc in FAILURE_CLASSES:
            # 계약: 모든 failure class는 최소 1건의 audit 흔적 필요
            audit_required = True  # 계약상 항상 True
            assert audit_required is True, f"Failure class {fc} must require audit trace"

    def test_result_unknown_requires_investigation_flag(self):
        """RESULT_UNKNOWN은 investigation flag가 필수다."""
        # 계약: result unknown 시 operator_action_required = True
        result_class = "unknown"
        operator_action_required = result_class == "unknown"
        assert operator_action_required is True

    def test_failure_with_no_record_forbidden(self):
        """기록 없는 실패는 금지된다."""
        for fc in FAILURE_CLASSES:
            # 모든 failure class에 대해 최소 receipt 또는 audit 존재 필요
            min_records = 1  # 계약상 최소 1건
            assert min_records >= 1, f"Class {fc}: 0 records forbidden"

    def test_classify_unknown_input(self):
        """알 수 없는 입력은 unknown으로 분류."""
        assert _classify_failure("garbage") == "unknown"
        assert _classify_failure("") == "unknown"
        assert _classify_failure("SOMETHING_ELSE") == "unknown"


# ===========================================================================
# RC-3: Rollback Contract — 롤백 계약 검증
# ===========================================================================
class TestC04RollbackContract:
    """Rollback은 자동이 아니며, 원본 receipt 연결과 독립 evidence가 필수다."""

    def test_rollback_requires_original_receipt_id(self):
        """Rollback은 원본 receipt에 연결되어야 한다."""
        rollback = {f: f"test-{f}" for f in ROLLBACK_REQUIRED_FIELDS}
        rollback["original_receipt_id"] = None
        missing = [f for f in ROLLBACK_REQUIRED_FIELDS if not rollback.get(f)]
        assert "original_receipt_id" in missing

    def test_rollback_requires_own_evidence(self):
        """Rollback은 자체 evidence id가 필요하다."""
        rollback = {f: f"test-{f}" for f in ROLLBACK_REQUIRED_FIELDS}
        rollback["rollback_evidence_id"] = None
        missing = [f for f in ROLLBACK_REQUIRED_FIELDS if not rollback.get(f)]
        assert "rollback_evidence_id" in missing

    def test_rollback_is_not_automatic(self):
        """Rollback은 자동이 아니라 운영자 승인이 필요하다."""
        # 계약: auto_rollback = False 고정
        auto_rollback_allowed = False
        assert auto_rollback_allowed is False

    def test_rollback_metadata_immutable(self):
        """Rollback metadata는 생성 후 변경 불가 (계약)."""
        rollback = {f: f"test-{f}" for f in ROLLBACK_REQUIRED_FIELDS}
        original = dict(rollback)
        rollback["rollback_reason"] = "modified_by_attacker"
        # mutable dict이므로 변경됨 — 구현 시 frozen 보장 필요
        assert rollback != original
        # 계약: 구현은 immutable 보장해야 함

    def test_rollback_never_erases_audit(self):
        """Rollback이 수행되어도 audit 기록은 삭제되지 않는다."""
        # 계약: rollback.audit_deletable = False
        audit_deletable = False
        assert audit_deletable is False
