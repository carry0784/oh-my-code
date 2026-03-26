"""
Card C-29: Delivery Retry Eligibility / Retry Receipt Policy — Tests

검수 범위:
  C29-1: 모듈 구조
  C29-2: Retry eligibility rules
  C29-3: Permanent failure detection
  C29-4: Max retries + cooldown
  C29-5: Record attempt + state tracking
  C29-6: Fail-closed
  C29-7: 금지 조항

Sealed layers 미접촉. 기존 테스트 파일 미수정.
"""

from pathlib import Path

import pytest

from app.core.delivery_retry_policy import (
    DeliveryRetryPolicy,
    RetryEligibility,
    RetryReceipt,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_COOLDOWN_S,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = PROJECT_ROOT / "app" / "core" / "delivery_retry_policy.py"


# ===========================================================================
# C29-1: 모듈 구조
# ===========================================================================
class TestC29ModuleStructure:

    def test_module_exists(self):
        assert POLICY_PATH.exists()

    def test_retry_eligibility_dataclass(self):
        e = RetryEligibility(channel="ext", eligible=True, reason="ok")
        assert e.channel == "ext"
        assert e.eligible is True

    def test_retry_receipt_dataclass(self):
        r = RetryReceipt(channel="ext", attempted=True, attempt_number=1,
                         eligible=True, reason="retry")
        assert r.attempt_number == 1

    def test_default_max_retries(self):
        assert DEFAULT_MAX_RETRIES == 3

    def test_default_cooldown(self):
        assert DEFAULT_RETRY_COOLDOWN_S == 60

    def test_policy_class_exists(self):
        content = POLICY_PATH.read_text(encoding="utf-8")
        assert "class DeliveryRetryPolicy" in content


# ===========================================================================
# C29-2: Retry eligibility rules
# ===========================================================================
class TestC29EligibilityRules:

    def test_delivered_not_eligible(self):
        policy = DeliveryRetryPolicy()
        result = policy.check_eligibility("external", delivered=True, detail="ok")
        assert result.eligible is False
        assert "already_delivered" in result.reason

    def test_failed_delivery_eligible(self):
        policy = DeliveryRetryPolicy(cooldown_seconds=0)
        result = policy.check_eligibility("external", delivered=False, detail="timeout")
        assert result.eligible is True

    def test_suppressed_not_eligible(self):
        policy = DeliveryRetryPolicy()
        result = policy.check_eligibility("external", delivered=False,
                                          detail="timeout", policy_action="suppress")
        assert result.eligible is False
        assert "suppressed" in result.reason


# ===========================================================================
# C29-3: Permanent failure detection
# ===========================================================================
class TestC29PermanentFailure:

    def test_not_configured_is_permanent(self):
        policy = DeliveryRetryPolicy()
        result = policy.check_eligibility("external", delivered=False,
                                          detail="external notifier not configured (stub)")
        assert result.eligible is False
        assert "permanent_failure" in result.reason

    def test_stub_is_permanent(self):
        policy = DeliveryRetryPolicy()
        result = policy.check_eligibility("slack", delivered=False,
                                          detail="slack notifier not configured (stub)")
        assert result.eligible is False

    def test_timeout_is_not_permanent(self):
        policy = DeliveryRetryPolicy(cooldown_seconds=0)
        result = policy.check_eligibility("external", delivered=False,
                                          detail="webhook delivery failed")
        assert result.eligible is True


# ===========================================================================
# C29-4: Max retries + cooldown
# ===========================================================================
class TestC29MaxRetriesAndCooldown:

    def test_max_retries_exceeded(self):
        policy = DeliveryRetryPolicy(max_retries=2, cooldown_seconds=0)
        policy.record_attempt("external")
        policy.record_attempt("external")
        result = policy.check_eligibility("external", delivered=False, detail="fail")
        assert result.eligible is False
        assert "max_retries_exceeded" in result.reason

    def test_within_max_retries(self):
        policy = DeliveryRetryPolicy(max_retries=3, cooldown_seconds=0)
        policy.record_attempt("external")
        result = policy.check_eligibility("external", delivered=False, detail="fail")
        assert result.eligible is True
        assert result.attempt_number == 2

    def test_cooldown_blocks_retry(self):
        policy = DeliveryRetryPolicy(cooldown_seconds=300)
        policy.record_attempt("external")
        result = policy.check_eligibility("external", delivered=False, detail="fail")
        assert result.eligible is False
        assert "cooldown" in result.reason


# ===========================================================================
# C29-5: Record attempt + state tracking
# ===========================================================================
class TestC29StateTracking:

    def test_record_attempt_returns_receipt(self):
        policy = DeliveryRetryPolicy()
        receipt = policy.record_attempt("external")
        assert isinstance(receipt, RetryReceipt)
        assert receipt.channel == "external"
        assert receipt.attempt_number == 1
        assert receipt.timestamp != ""

    def test_attempts_increment(self):
        policy = DeliveryRetryPolicy()
        policy.record_attempt("external")
        policy.record_attempt("external")
        state = policy.get_state("external")
        assert state["attempts"] == 2

    def test_clear_channel_resets(self):
        policy = DeliveryRetryPolicy()
        policy.record_attempt("external")
        policy.clear_channel("external")
        state = policy.get_state("external")
        assert state["attempts"] == 0

    def test_reset_clears_all(self):
        policy = DeliveryRetryPolicy()
        policy.record_attempt("external")
        policy.record_attempt("slack")
        policy.reset()
        assert policy.get_state("external")["attempts"] == 0
        assert policy.get_state("slack")["attempts"] == 0

    def test_independent_channel_tracking(self):
        policy = DeliveryRetryPolicy()
        policy.record_attempt("external")
        policy.record_attempt("external")
        policy.record_attempt("slack")
        assert policy.get_state("external")["attempts"] == 2
        assert policy.get_state("slack")["attempts"] == 1


# ===========================================================================
# C29-6: Fail-closed
# ===========================================================================
class TestC29FailClosed:

    def test_error_returns_not_eligible(self):
        """check_eligibility는 예외를 전파하지 않는다."""
        policy = DeliveryRetryPolicy()
        # Force an error by corrupting internal state
        policy._state["bad"] = "not_a_state_object"
        result = policy.check_eligibility("bad", delivered=False, detail="x")
        assert result.eligible is False
        assert "error" in result.reason

    def test_get_state_unknown_channel(self):
        policy = DeliveryRetryPolicy()
        state = policy.get_state("nonexistent")
        assert state["attempts"] == 0
        assert state["last_attempt_at"] is None


# ===========================================================================
# C29-7: 금지 조항
# ===========================================================================
class TestC29Forbidden:

    def test_no_forbidden_strings(self):
        content = POLICY_PATH.read_text(encoding="utf-8")
        body = content.split('"""', 2)[-1] if '"""' in content else content
        forbidden = [
            'chain_of_thought', 'raw_prompt', 'internal_reasoning',
            'debug_trace', 'agent_analysis', 'error_class',
        ]
        for f in forbidden:
            assert f not in body, f"Forbidden string '{f}'"

    def test_no_transport_logic(self):
        content = POLICY_PATH.read_text(encoding="utf-8")
        assert "send_webhook" not in content
        assert "urllib" not in content

    def test_no_app_state(self):
        content = POLICY_PATH.read_text(encoding="utf-8")
        assert "app.state" not in content

    def test_deterministic_eligibility(self):
        """동일 상태 → 동일 결과."""
        policy = DeliveryRetryPolicy(cooldown_seconds=0)
        r1 = policy.check_eligibility("ext", False, "timeout")
        r2 = policy.check_eligibility("ext", False, "timeout")
        assert r1.eligible == r2.eligible
