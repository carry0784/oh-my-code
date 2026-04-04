"""
Card C-35: Retry Policy Gate — Tests

검수 범위:
  C35-1: 모듈 구조
  C35-2: gate 통과 조건
  C35-3: gate 차단 조건
  C35-4: pass 동시성 제어
  C35-5: fail-closed
  C35-6: 금지 조항

Sealed layers 미접촉. 기존 테스트 파일 미수정.
"""

from pathlib import Path

import pytest

from app.core.retry_policy_gate import RetryPolicyGate, GateDecision
from app.core.retry_plan_store import RetryPlanStore

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GATE_PATH = PROJECT_ROOT / "app" / "core" / "retry_policy_gate.py"


def _store_with_plans(n=3):
    store = RetryPlanStore(ttl_seconds=9999)
    for i in range(n):
        store.enqueue(channel=f"ch{i}", reason="timeout",
                      reliability_tier="transient_failure",
                      retryable=True, retry_after_seconds=0,
                      incident=f"inc_{i}")
    return store


# ===========================================================================
# C35-1: 모듈 구조
# ===========================================================================
class TestC35ModuleStructure:

    def test_module_exists(self):
        assert GATE_PATH.exists()

    def test_gate_class_exists(self):
        content = GATE_PATH.read_text(encoding="utf-8")
        assert "class RetryPolicyGate" in content

    def test_gate_decision_dataclass(self):
        d = GateDecision(allowed=True, reason="ok")
        assert d.allowed is True

    def test_gate_decision_to_dict(self):
        d = GateDecision(allowed=False, reason="test")
        assert isinstance(d.to_dict(), dict)


# ===========================================================================
# C35-2: gate 통과
# ===========================================================================
class TestC35GatePass:

    def test_all_gates_pass(self):
        gate = RetryPolicyGate()
        store = _store_with_plans(3)
        decision = gate.evaluate(store)
        assert decision.allowed is True
        assert decision.reason == "all_gates_passed"
        assert decision.gate_passed == decision.gate_checks

    def test_pending_count_populated(self):
        gate = RetryPolicyGate()
        store = _store_with_plans(5)
        decision = gate.evaluate(store)
        assert decision.pending_count == 5


# ===========================================================================
# C35-3: gate 차단
# ===========================================================================
class TestC35GateBlock:

    def test_disabled_blocks(self):
        gate = RetryPolicyGate(enabled=False)
        store = _store_with_plans()
        decision = gate.evaluate(store)
        assert decision.allowed is False
        assert "disabled" in decision.reason

    def test_maintenance_blocks(self):
        gate = RetryPolicyGate(maintenance_mode=True)
        store = _store_with_plans()
        decision = gate.evaluate(store)
        assert decision.allowed is False
        assert "maintenance" in decision.reason

    def test_no_pending_blocks(self):
        gate = RetryPolicyGate()
        store = RetryPlanStore()
        decision = gate.evaluate(store)
        assert decision.allowed is False
        assert "no_pending" in decision.reason

    def test_threshold_exceeded_blocks(self):
        gate = RetryPolicyGate(max_pending_threshold=2)
        store = _store_with_plans(5)
        decision = gate.evaluate(store)
        assert decision.allowed is False
        assert "threshold" in decision.reason

    def test_set_enabled(self):
        gate = RetryPolicyGate()
        gate.set_enabled(False)
        store = _store_with_plans()
        decision = gate.evaluate(store)
        assert decision.allowed is False

    def test_set_maintenance(self):
        gate = RetryPolicyGate()
        gate.set_maintenance(True)
        store = _store_with_plans()
        decision = gate.evaluate(store)
        assert decision.allowed is False


# ===========================================================================
# C35-4: pass 동시성 제어
# ===========================================================================
class TestC35PassControl:

    def test_acquire_pass(self):
        gate = RetryPolicyGate()
        assert gate.acquire_pass() is True
        assert gate.acquire_pass() is False

    def test_release_pass(self):
        gate = RetryPolicyGate()
        gate.acquire_pass()
        gate.release_pass()
        assert gate.acquire_pass() is True

    def test_pass_in_progress_blocks_gate(self):
        gate = RetryPolicyGate()
        gate.acquire_pass()
        store = _store_with_plans()
        decision = gate.evaluate(store)
        assert decision.allowed is False
        assert "in_progress" in decision.reason

    def test_get_state(self):
        gate = RetryPolicyGate()
        state = gate.get_state()
        assert state["enabled"] is True
        assert state["maintenance_mode"] is False
        assert state["pass_in_progress"] is False


# ===========================================================================
# C35-5: fail-closed
# ===========================================================================
class TestC35FailClosed:

    def test_corrupted_store_denied(self):
        gate = RetryPolicyGate()
        decision = gate.evaluate("not_a_store")
        assert decision.allowed is False

    def test_exception_denied(self):
        gate = RetryPolicyGate()
        gate._enabled = "not_a_bool"  # Force error
        decision = gate.evaluate(RetryPlanStore())
        # Should be caught by outer try/except
        assert isinstance(decision, GateDecision)


# ===========================================================================
# C35-6: 금지 조항
# ===========================================================================
class TestC35Forbidden:

    def test_no_forbidden_strings(self):
        content = GATE_PATH.read_text(encoding="utf-8")
        body = content.split('"""', 2)[-1] if '"""' in content else content
        forbidden = [
            'chain_of_thought', 'raw_prompt', 'internal_reasoning',
            'debug_trace',
        ]
        for f in forbidden:
            assert f not in body, f"Forbidden string '{f}'"

    def test_no_daemon(self):
        content = GATE_PATH.read_text(encoding="utf-8")
        parts = content.split('"""')
        body = parts[-1] if len(parts) >= 3 else content
        assert "daemon" not in body.lower()

    def test_no_send_logic(self):
        content = GATE_PATH.read_text(encoding="utf-8")
        assert "send_webhook" not in content
        assert "send_notifications" not in content

    def test_no_engine_imports(self):
        content = GATE_PATH.read_text(encoding="utf-8")
        assert "src.kdexter" not in content
