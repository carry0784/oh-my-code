"""
Card C-36: Retry Budget Limit — Tests

검수 범위:
  C36-1: 모듈 구조
  C36-2: budget 통과
  C36-3: global budget 소진
  C36-4: channel budget 소진
  C36-5: sliding window
  C36-6: fail-closed
  C36-7: 금지 조항

Sealed layers 미접촉. 기존 테스트 파일 미수정.
"""

from pathlib import Path

import pytest

from app.core.retry_budget import (
    RetryBudget,
    BudgetCheck,
    DEFAULT_GLOBAL_BUDGET,
    DEFAULT_CHANNEL_BUDGET,
    DEFAULT_WINDOW_SECONDS,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUDGET_PATH = PROJECT_ROOT / "app" / "core" / "retry_budget.py"


# ===========================================================================
# C36-1: 모듈 구조
# ===========================================================================
class TestC36ModuleStructure:

    def test_module_exists(self):
        assert BUDGET_PATH.exists()

    def test_budget_class_exists(self):
        content = BUDGET_PATH.read_text(encoding="utf-8")
        assert "class RetryBudget" in content

    def test_budget_check_dataclass(self):
        b = BudgetCheck(allowed=True, reason="ok")
        assert b.allowed is True

    def test_defaults(self):
        assert DEFAULT_GLOBAL_BUDGET == 20
        assert DEFAULT_CHANNEL_BUDGET == 10
        assert DEFAULT_WINDOW_SECONDS == 3600


# ===========================================================================
# C36-2: budget 통과
# ===========================================================================
class TestC36BudgetPass:

    def test_fresh_budget_allows(self):
        budget = RetryBudget()
        result = budget.check("external")
        assert result.allowed is True
        assert result.reason == "within_budget"

    def test_after_one_record_still_allowed(self):
        budget = RetryBudget()
        budget.record("external")
        result = budget.check("external")
        assert result.allowed is True

    def test_global_used_tracked(self):
        budget = RetryBudget()
        budget.record("external")
        budget.record("slack")
        result = budget.check("external")
        assert result.global_used == 2


# ===========================================================================
# C36-3: global budget 소진
# ===========================================================================
class TestC36GlobalBudget:

    def test_global_budget_exhausted(self):
        budget = RetryBudget(global_budget=3)
        for i in range(3):
            budget.record(f"ch{i}")
        result = budget.check("external")
        assert result.allowed is False
        assert "global_budget_exhausted" in result.reason

    def test_global_budget_exact_limit(self):
        budget = RetryBudget(global_budget=2)
        budget.record("ext")
        budget.record("slack")
        result = budget.check("ext")
        assert result.allowed is False


# ===========================================================================
# C36-4: channel budget 소진
# ===========================================================================
class TestC36ChannelBudget:

    def test_channel_budget_exhausted(self):
        budget = RetryBudget(channel_budget=2)
        budget.record("external")
        budget.record("external")
        result = budget.check("external")
        assert result.allowed is False
        assert "channel_budget_exhausted" in result.reason

    def test_other_channel_unaffected(self):
        budget = RetryBudget(channel_budget=2)
        budget.record("external")
        budget.record("external")
        result = budget.check("slack")
        assert result.allowed is True

    def test_channel_used_tracked(self):
        budget = RetryBudget()
        budget.record("external")
        budget.record("external")
        result = budget.check("external")
        assert result.channel_used == 2


# ===========================================================================
# C36-5: sliding window
# ===========================================================================
class TestC36SlidingWindow:

    def test_reset_clears(self):
        budget = RetryBudget(global_budget=2)
        budget.record("ext")
        budget.record("ext")
        budget.reset()
        result = budget.check("ext")
        assert result.allowed is True

    def test_summary(self):
        budget = RetryBudget()
        budget.record("ext")
        budget.record("slack")
        s = budget.summary()
        assert s["global_used"] == 2
        assert "channels" in s
        assert s["channels"]["ext"] == 1
        assert s["channels"]["slack"] == 1


# ===========================================================================
# C36-6: fail-closed
# ===========================================================================
class TestC36FailClosed:

    def test_corrupted_state_denied(self):
        budget = RetryBudget()
        budget._global_log = "corrupted"
        result = budget.check("ext")
        assert result.allowed is False
        assert "error" in result.reason

    def test_record_error_safe(self):
        budget = RetryBudget()
        budget._global_log = "corrupted"
        budget.record("ext")  # Should not raise

    def test_summary_error_safe(self):
        budget = RetryBudget()
        budget._global_log = "corrupted"
        s = budget.summary()
        assert s.get("error") is True or s["global_used"] == 0


# ===========================================================================
# C36-7: 금지 조항
# ===========================================================================
class TestC36Forbidden:

    def test_no_forbidden_strings(self):
        content = BUDGET_PATH.read_text(encoding="utf-8")
        body = content.split('"""', 2)[-1] if '"""' in content else content
        forbidden = [
            'chain_of_thought', 'raw_prompt', 'internal_reasoning',
            'debug_trace',
        ]
        for f in forbidden:
            assert f not in body, f"Forbidden string '{f}'"

    def test_no_send_logic(self):
        content = BUDGET_PATH.read_text(encoding="utf-8")
        assert "send_webhook" not in content
        assert "send_notifications" not in content

    def test_no_engine(self):
        content = BUDGET_PATH.read_text(encoding="utf-8")
        assert "src.kdexter" not in content
