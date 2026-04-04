"""
Card C-37: Retry Metrics — Tests

검수 범위:
  C37-1: 모듈 구조
  C37-2: attempt 기록
  C37-3: skip / budget / gate 기록
  C37-4: channel별 추적
  C37-5: summary
  C37-6: fail-closed
  C37-7: 금지 조항

Sealed layers 미접촉. 기존 테스트 파일 미수정.
"""

from pathlib import Path

import pytest

from app.core.retry_metrics import RetryMetrics, RetryMetricsSummary

PROJECT_ROOT = Path(__file__).resolve().parent.parent
METRICS_PATH = PROJECT_ROOT / "app" / "core" / "retry_metrics.py"


# ===========================================================================
# C37-1: 모듈 구조
# ===========================================================================
class TestC37ModuleStructure:
    def test_module_exists(self):
        assert METRICS_PATH.exists()

    def test_metrics_class_exists(self):
        content = METRICS_PATH.read_text(encoding="utf-8")
        assert "class RetryMetrics" in content

    def test_summary_dataclass(self):
        s = RetryMetricsSummary()
        assert s.total_attempts == 0

    def test_summary_to_dict(self):
        s = RetryMetricsSummary(total_attempts=5)
        d = s.to_dict()
        assert d["total_attempts"] == 5


# ===========================================================================
# C37-2: attempt 기록
# ===========================================================================
class TestC37Attempts:
    def test_record_success(self):
        m = RetryMetrics()
        m.record_attempt("ext", success=True)
        s = m.summary()
        assert s.total_attempts == 1
        assert s.total_succeeded == 1
        assert s.total_failed == 0

    def test_record_failure(self):
        m = RetryMetrics()
        m.record_attempt("ext", success=False)
        s = m.summary()
        assert s.total_attempts == 1
        assert s.total_failed == 1
        assert s.total_succeeded == 0

    def test_mixed_attempts(self):
        m = RetryMetrics()
        m.record_attempt("ext", True)
        m.record_attempt("ext", False)
        m.record_attempt("slack", True)
        s = m.summary()
        assert s.total_attempts == 3
        assert s.total_succeeded == 2
        assert s.total_failed == 1


# ===========================================================================
# C37-3: skip / budget / gate
# ===========================================================================
class TestC37SpecialRecords:
    def test_record_skip(self):
        m = RetryMetrics()
        m.record_skip("not eligible")
        assert m.summary().total_skipped == 1

    def test_record_budget_denied(self):
        m = RetryMetrics()
        m.record_budget_denied()
        assert m.summary().total_budget_denied == 1

    def test_record_gate_denied(self):
        m = RetryMetrics()
        m.record_gate_denied()
        assert m.summary().total_gate_denied == 1

    def test_record_pass(self):
        m = RetryMetrics()
        m.record_pass()
        s = m.summary()
        assert s.total_passes == 1
        assert s.last_pass_at != ""


# ===========================================================================
# C37-4: channel별 추적
# ===========================================================================
class TestC37ChannelTracking:
    def test_per_channel_counts(self):
        m = RetryMetrics()
        m.record_attempt("ext", True)
        m.record_attempt("ext", False)
        m.record_attempt("slack", True)
        s = m.summary()
        assert s.channels["ext"]["attempts"] == 2
        assert s.channels["ext"]["succeeded"] == 1
        assert s.channels["ext"]["failed"] == 1
        assert s.channels["slack"]["attempts"] == 1

    def test_independent_channels(self):
        m = RetryMetrics()
        m.record_attempt("ext", True)
        m.record_attempt("slack", False)
        s = m.summary()
        assert s.channels["ext"]["succeeded"] == 1
        assert s.channels["slack"]["failed"] == 1


# ===========================================================================
# C37-5: summary
# ===========================================================================
class TestC37Summary:
    def test_fresh_summary(self):
        m = RetryMetrics()
        s = m.summary()
        assert s.total_attempts == 0
        assert s.channels == {}

    def test_reset(self):
        m = RetryMetrics()
        m.record_attempt("ext", True)
        m.record_pass()
        m.reset()
        s = m.summary()
        assert s.total_attempts == 0
        assert s.total_passes == 0
        assert s.last_pass_at == ""


# ===========================================================================
# C37-6: fail-closed
# ===========================================================================
class TestC37FailClosed:
    def test_corrupted_state_summary_safe(self):
        m = RetryMetrics()
        m._channel_attempts = "corrupted"
        s = m.summary()
        assert isinstance(s, RetryMetricsSummary)
        assert s.total_attempts == 0  # fallback

    def test_record_on_corrupted_safe(self):
        m = RetryMetrics()
        m._total_attempts = "bad"
        m.record_attempt("ext", True)  # Should not raise


# ===========================================================================
# C37-7: 금지 조항
# ===========================================================================
class TestC37Forbidden:
    def test_no_forbidden_strings(self):
        content = METRICS_PATH.read_text(encoding="utf-8")
        body = content.split('"""', 2)[-1] if '"""' in content else content
        forbidden = [
            "chain_of_thought",
            "raw_prompt",
            "internal_reasoning",
            "debug_trace",
        ]
        for f in forbidden:
            assert f not in body, f"Forbidden string '{f}'"

    def test_no_send_logic(self):
        content = METRICS_PATH.read_text(encoding="utf-8")
        assert "send_webhook" not in content

    def test_no_engine(self):
        content = METRICS_PATH.read_text(encoding="utf-8")
        assert "src.kdexter" not in content
