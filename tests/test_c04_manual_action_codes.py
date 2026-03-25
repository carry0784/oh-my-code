"""
C-04 Manual Action — Block Code / Fail Code Registry & Boundary Tests

Phase 1 test-code only. C-04 구현 금지. 활성화 금지.
이 테스트는 block code(사전 차단)와 fail code(사후 실패)의
경계, 분류, 무결성을 코드 수준으로 봉인한다.

대상: C-04 contract에서 정의한 코드 체계
범위: registry 무결성, 분류 경계, 코드 매핑
"""

import pytest


# ===========================================================================
# Test-local contract definitions (not production code)
# ===========================================================================

# 12 Block Codes — pre-execution blocking (실행 이전 차단)
BLOCK_CODES = frozenset({
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
})

# 4 Fail Codes — post-execution failure (실행 진입 후 실패)
FAIL_CODES = frozenset({
    "EXECUTION_REJECTED",
    "EXECUTION_FAILED",
    "PARTIAL_FAILURE",
    "RESULT_UNKNOWN",
})

# Block codes that map to 9-stage chain failures
CHAIN_BLOCK_CODES = frozenset({
    "PIPELINE_NOT_READY",
    "PREFLIGHT_NOT_READY",
    "GATE_CLOSED",
    "APPROVAL_REQUIRED",
    "POLICY_BLOCKED",
    "RISK_NOT_OK",
    "AUTH_NOT_OK",
    "SCOPE_NOT_OK",
    "EVIDENCE_MISSING",
})

# Sentinel block codes (not tied to specific chain stage)
SENTINEL_BLOCK_CODES = frozenset({
    "MANUAL_ACTION_DISABLED",
    "PREVIEW_MISSING",
    "TRACE_INCOMPLETE",
})


# ===========================================================================
# BC-1: Block Code Registry 무결성
# ===========================================================================
class TestC04BlockCodeRegistry:
    """Block code registry 무결성 검증."""

    def test_block_codes_count_is_12(self):
        """Block code는 정확히 12개여야 한다."""
        assert len(BLOCK_CODES) == 12

    def test_block_codes_are_uppercase_snake(self):
        """모든 block code는 UPPERCASE_SNAKE_CASE 형식이어야 한다."""
        import re
        pattern = re.compile(r"^[A-Z][A-Z0-9_]+$")
        for code in BLOCK_CODES:
            assert pattern.match(code), f"Block code not UPPER_SNAKE: {code}"

    def test_block_codes_are_strings(self):
        """모든 block code는 문자열이어야 한다."""
        for code in BLOCK_CODES:
            assert isinstance(code, str)

    def test_block_codes_no_duplicates(self):
        """Block code에 중복이 없어야 한다."""
        block_list = list(BLOCK_CODES)
        assert len(block_list) == len(set(block_list))

    def test_manual_action_disabled_in_block_codes(self):
        """C-04 비활성 단계 sentinel code가 존재해야 한다."""
        assert "MANUAL_ACTION_DISABLED" in BLOCK_CODES

    def test_trace_incomplete_in_block_codes(self):
        """Trace 불완전 코드가 존재해야 한다."""
        assert "TRACE_INCOMPLETE" in BLOCK_CODES


# ===========================================================================
# BC-2: Fail Code Registry 무결성
# ===========================================================================
class TestC04FailCodeRegistry:
    """Fail code registry 무결성 검증."""

    def test_fail_codes_count_is_4(self):
        """Fail code는 정확히 4개여야 한다."""
        assert len(FAIL_CODES) == 4

    def test_fail_codes_are_uppercase_snake(self):
        """모든 fail code는 UPPERCASE_SNAKE_CASE 형식이어야 한다."""
        import re
        pattern = re.compile(r"^[A-Z][A-Z0-9_]+$")
        for code in FAIL_CODES:
            assert pattern.match(code), f"Fail code not UPPER_SNAKE: {code}"

    def test_fail_codes_no_overlap_with_block_codes(self):
        """Block code와 fail code는 겹치지 않아야 한다."""
        overlap = BLOCK_CODES & FAIL_CODES
        assert len(overlap) == 0, f"Overlap found: {overlap}"

    def test_execution_rejected_in_fail_codes(self):
        """EXECUTION_REJECTED가 존재해야 한다."""
        assert "EXECUTION_REJECTED" in FAIL_CODES

    def test_result_unknown_in_fail_codes(self):
        """RESULT_UNKNOWN이 존재해야 한다."""
        assert "RESULT_UNKNOWN" in FAIL_CODES


# ===========================================================================
# BC-3: Code Boundary — 사전 차단 vs 사후 실패 경계
# ===========================================================================
class TestC04CodeBoundary:
    """Block code(사전 차단)와 fail code(사후 실패)의 경계 검증."""

    def test_block_codes_are_pre_execution(self):
        """Block code는 실행 이전 차단만 의미한다.
        'EXECUTION' 접두사를 가진 코드는 block에 없어야 한다."""
        for code in BLOCK_CODES:
            assert not code.startswith("EXECUTION_"), (
                f"Block code should not start with EXECUTION_: {code}"
            )

    def test_fail_codes_are_post_execution(self):
        """Fail code는 실행 진입 후 결과만 의미한다.
        'EXECUTION_' 또는 'PARTIAL_' 또는 'RESULT_' 접두사만 허용."""
        allowed_prefixes = ("EXECUTION_", "PARTIAL_", "RESULT_")
        for code in FAIL_CODES:
            assert any(code.startswith(p) for p in allowed_prefixes), (
                f"Fail code has unexpected prefix: {code}"
            )

    def test_all_block_codes_prevent_execution(self):
        """모든 block code는 실행을 차단하는 의미만 가져야 한다.
        실행 성공/완료를 의미하는 코드가 있으면 안 된다."""
        success_indicators = {"SUCCESS", "COMPLETED", "DONE", "PASSED", "ALLOWED"}
        for code in BLOCK_CODES:
            for indicator in success_indicators:
                assert indicator not in code, (
                    f"Block code contains success indicator: {code}"
                )

    def test_fail_codes_imply_execution_attempted(self):
        """Fail code는 실행이 시도되었음을 의미해야 한다.
        'NOT_READY', 'MISSING', 'CLOSED' 같은 사전 차단 패턴이 없어야 한다."""
        pre_execution_indicators = {"NOT_READY", "MISSING", "CLOSED", "BLOCKED", "DISABLED"}
        for code in FAIL_CODES:
            for indicator in pre_execution_indicators:
                assert indicator not in code, (
                    f"Fail code contains pre-execution indicator: {code}"
                )

    def test_combined_codes_cover_full_lifecycle(self):
        """Block + Fail 코드가 전체 실행 수명주기를 커버해야 한다."""
        all_codes = BLOCK_CODES | FAIL_CODES
        assert len(all_codes) == 16
        # 사전 차단(12) + 사후 실패(4) = 16
        assert len(BLOCK_CODES) + len(FAIL_CODES) == 16
