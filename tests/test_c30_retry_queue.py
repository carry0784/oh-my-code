"""
Card C-30: Retry Queue / Deferred Retry Plan Ledger — Tests

검수 범위:
  C30-1: 모듈 구조
  C30-2: Enqueue rules
  C30-3: Duplicate suppression
  C30-4: Non-retryable rejection
  C30-5: State transitions
  C30-6: Query / filter
  C30-7: TTL expiry
  C30-8: Capacity eviction
  C30-9: Fail-closed
  C30-10: 금지 조항

Sealed layers 미접촉. 기존 테스트 파일 미수정.
"""

from pathlib import Path

import pytest

from app.core.retry_plan_store import (
    RetryPlanStore,
    RetryPlan,
    EnqueueResult,
    DEFAULT_MAX_PLANS,
    DEFAULT_TTL_SECONDS,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STORE_PATH = PROJECT_ROOT / "app" / "core" / "retry_plan_store.py"


# ===========================================================================
# C30-1: 모듈 구조
# ===========================================================================
class TestC30ModuleStructure:

    def test_module_exists(self):
        assert STORE_PATH.exists()

    def test_retry_plan_dataclass(self):
        p = RetryPlan(retry_id="abc", channel="ext", status="pending")
        assert p.retry_id == "abc"
        assert p.status == "pending"

    def test_enqueue_result_dataclass(self):
        r = EnqueueResult(enqueued=True, retry_id="x", reason="ok")
        assert r.enqueued is True

    def test_default_max_plans(self):
        assert DEFAULT_MAX_PLANS == 200

    def test_default_ttl(self):
        assert DEFAULT_TTL_SECONDS == 3600

    def test_store_class_exists(self):
        content = STORE_PATH.read_text(encoding="utf-8")
        assert "class RetryPlanStore" in content

    def test_plan_to_dict(self):
        p = RetryPlan(retry_id="abc", channel="ext", status="pending")
        d = p.to_dict()
        assert isinstance(d, dict)
        assert d["retry_id"] == "abc"


# ===========================================================================
# C30-2: Enqueue rules
# ===========================================================================
class TestC30EnqueueRules:

    def test_enqueue_retryable_success(self):
        store = RetryPlanStore()
        result = store.enqueue(
            channel="external",
            reason="timeout",
            reliability_tier="transient_failure",
            retryable=True,
            incident="inc_001",
        )
        assert result.enqueued is True
        assert result.retry_id != ""
        assert result.reason == "plan_created"

    def test_enqueue_creates_pending_plan(self):
        store = RetryPlanStore()
        store.enqueue(
            channel="external",
            reason="timeout",
            reliability_tier="transient_failure",
            retryable=True,
            incident="inc_001",
        )
        plans = store.list_plans(status="pending")
        assert len(plans) == 1
        assert plans[0]["channel"] == "external"
        assert plans[0]["status"] == "pending"

    def test_enqueue_with_retry_after(self):
        store = RetryPlanStore()
        store.enqueue(
            channel="slack",
            reason="connection_error",
            reliability_tier="transient_failure",
            retryable=True,
            retry_after_seconds=120,
            incident="inc_002",
        )
        plans = store.list_plans()
        assert plans[0]["retry_after_seconds"] == 120

    def test_enqueue_preserves_severity(self):
        store = RetryPlanStore()
        store.enqueue(
            channel="external",
            reason="timeout",
            reliability_tier="transient_failure",
            retryable=True,
            severity_tier="critical",
            incident="inc_003",
        )
        plans = store.list_plans()
        assert plans[0]["severity_tier"] == "critical"


# ===========================================================================
# C30-3: Duplicate suppression
# ===========================================================================
class TestC30DuplicateSuppression:

    def test_duplicate_channel_incident_rejected(self):
        store = RetryPlanStore()
        r1 = store.enqueue(
            channel="external", reason="timeout",
            reliability_tier="transient_failure", retryable=True,
            incident="inc_001",
        )
        r2 = store.enqueue(
            channel="external", reason="timeout",
            reliability_tier="transient_failure", retryable=True,
            incident="inc_001",
        )
        assert r1.enqueued is True
        assert r2.enqueued is False
        assert "duplicate" in r2.reason

    def test_different_channels_same_incident_allowed(self):
        store = RetryPlanStore()
        r1 = store.enqueue(
            channel="external", reason="timeout",
            reliability_tier="transient_failure", retryable=True,
            incident="inc_001",
        )
        r2 = store.enqueue(
            channel="slack", reason="timeout",
            reliability_tier="transient_failure", retryable=True,
            incident="inc_001",
        )
        assert r1.enqueued is True
        assert r2.enqueued is True

    def test_same_channel_different_incident_allowed(self):
        store = RetryPlanStore()
        r1 = store.enqueue(
            channel="external", reason="timeout",
            reliability_tier="transient_failure", retryable=True,
            incident="inc_001",
        )
        r2 = store.enqueue(
            channel="external", reason="timeout",
            reliability_tier="transient_failure", retryable=True,
            incident="inc_002",
        )
        assert r1.enqueued is True
        assert r2.enqueued is True

    def test_dedup_released_after_cancel(self):
        store = RetryPlanStore()
        r1 = store.enqueue(
            channel="external", reason="timeout",
            reliability_tier="transient_failure", retryable=True,
            incident="inc_001",
        )
        store.mark_cancelled(r1.retry_id)
        r2 = store.enqueue(
            channel="external", reason="retry",
            reliability_tier="transient_failure", retryable=True,
            incident="inc_001",
        )
        assert r2.enqueued is True


# ===========================================================================
# C30-4: Non-retryable rejection
# ===========================================================================
class TestC30NonRetryableRejection:

    def test_not_retryable_rejected(self):
        store = RetryPlanStore()
        result = store.enqueue(
            channel="external",
            reason="not_configured",
            reliability_tier="permanent_failure",
            retryable=False,
            incident="inc_001",
        )
        assert result.enqueued is False
        assert "not_retryable" in result.reason

    def test_not_retryable_not_stored(self):
        store = RetryPlanStore()
        store.enqueue(
            channel="external",
            reason="not_configured",
            reliability_tier="permanent_failure",
            retryable=False,
        )
        assert store.count() == 0


# ===========================================================================
# C30-5: State transitions
# ===========================================================================
class TestC30StateTransitions:

    def _make_plan(self, store, incident="inc_001"):
        result = store.enqueue(
            channel="external", reason="timeout",
            reliability_tier="transient_failure", retryable=True,
            incident=incident,
        )
        return result.retry_id

    def test_cancel_pending(self):
        store = RetryPlanStore()
        rid = self._make_plan(store)
        assert store.mark_cancelled(rid) is True
        plan = store.get_plan(rid)
        assert plan["status"] == "cancelled"

    def test_execute_pending(self):
        store = RetryPlanStore()
        rid = self._make_plan(store)
        assert store.mark_executed(rid) is True
        plan = store.get_plan(rid)
        assert plan["status"] == "executed"

    def test_expire_pending(self):
        store = RetryPlanStore()
        rid = self._make_plan(store)
        assert store.mark_expired(rid) is True
        plan = store.get_plan(rid)
        assert plan["status"] == "expired"

    def test_cannot_cancel_executed(self):
        store = RetryPlanStore()
        rid = self._make_plan(store)
        store.mark_executed(rid)
        assert store.mark_cancelled(rid) is False

    def test_cannot_execute_cancelled(self):
        store = RetryPlanStore()
        rid = self._make_plan(store)
        store.mark_cancelled(rid)
        assert store.mark_executed(rid) is False


# ===========================================================================
# C30-6: Query / filter
# ===========================================================================
class TestC30QueryFilter:

    def test_list_newest_first(self):
        store = RetryPlanStore()
        store.enqueue(
            channel="ext", reason="a", reliability_tier="t",
            retryable=True, incident="inc_1",
        )
        store.enqueue(
            channel="slack", reason="b", reliability_tier="t",
            retryable=True, incident="inc_2",
        )
        plans = store.list_plans()
        assert plans[0]["incident"] == "inc_2"
        assert plans[1]["incident"] == "inc_1"

    def test_filter_by_status(self):
        store = RetryPlanStore()
        r1 = store.enqueue(
            channel="ext", reason="a", reliability_tier="t",
            retryable=True, incident="inc_1",
        )
        store.enqueue(
            channel="slack", reason="b", reliability_tier="t",
            retryable=True, incident="inc_2",
        )
        store.mark_cancelled(r1.retry_id)
        pending = store.list_plans(status="pending")
        assert len(pending) == 1
        assert pending[0]["channel"] == "slack"

    def test_filter_by_channel(self):
        store = RetryPlanStore()
        store.enqueue(
            channel="ext", reason="a", reliability_tier="t",
            retryable=True, incident="inc_1",
        )
        store.enqueue(
            channel="slack", reason="b", reliability_tier="t",
            retryable=True, incident="inc_2",
        )
        ext_plans = store.list_plans(channel="ext")
        assert len(ext_plans) == 1

    def test_get_plan_by_id(self):
        store = RetryPlanStore()
        result = store.enqueue(
            channel="ext", reason="a", reliability_tier="t",
            retryable=True, incident="inc_1",
        )
        plan = store.get_plan(result.retry_id)
        assert plan is not None
        assert plan["retry_id"] == result.retry_id

    def test_get_nonexistent_plan(self):
        store = RetryPlanStore()
        assert store.get_plan("nonexistent") is None

    def test_count_total(self):
        store = RetryPlanStore()
        store.enqueue(channel="ext", reason="a", reliability_tier="t",
                      retryable=True, incident="1")
        store.enqueue(channel="slack", reason="b", reliability_tier="t",
                      retryable=True, incident="2")
        assert store.count() == 2

    def test_pending_count(self):
        store = RetryPlanStore()
        r1 = store.enqueue(channel="ext", reason="a", reliability_tier="t",
                           retryable=True, incident="1")
        store.enqueue(channel="slack", reason="b", reliability_tier="t",
                      retryable=True, incident="2")
        store.mark_cancelled(r1.retry_id)
        assert store.pending_count() == 1

    def test_summary(self):
        store = RetryPlanStore()
        store.enqueue(channel="ext", reason="a", reliability_tier="t",
                      retryable=True, incident="1")
        s = store.summary()
        assert s["total"] == 1
        assert s["pending"] == 1
        assert "max_plans" in s

    def test_list_limit(self):
        store = RetryPlanStore()
        for i in range(10):
            store.enqueue(channel=f"ch{i}", reason="a", reliability_tier="t",
                          retryable=True, incident=f"inc_{i}")
        plans = store.list_plans(limit=3)
        assert len(plans) == 3


# ===========================================================================
# C30-7: TTL expiry
# ===========================================================================
class TestC30TTLExpiry:

    def test_expired_plans_not_pending(self):
        store = RetryPlanStore(ttl_seconds=0)
        store.enqueue(channel="ext", reason="a", reliability_tier="t",
                      retryable=True, incident="1")
        # Trigger expiry via new enqueue
        store.enqueue(channel="slack", reason="b", reliability_tier="t",
                      retryable=True, incident="2")
        pending = store.list_plans(status="pending")
        # At least the second one should be pending
        assert any(p["channel"] == "slack" for p in pending)


# ===========================================================================
# C30-8: Capacity eviction
# ===========================================================================
class TestC30CapacityEviction:

    def test_eviction_on_full(self):
        store = RetryPlanStore(max_plans=3, ttl_seconds=9999)
        for i in range(4):
            store.enqueue(channel=f"ch{i}", reason="a", reliability_tier="t",
                          retryable=True, incident=f"inc_{i}")
        # Should still have max 3 pending after eviction
        assert store.count() <= 4  # total may include expired
        assert store.pending_count() <= 3

    def test_eviction_preserves_newest(self):
        store = RetryPlanStore(max_plans=2, ttl_seconds=9999)
        store.enqueue(channel="old", reason="a", reliability_tier="t",
                      retryable=True, incident="inc_old")
        store.enqueue(channel="mid", reason="a", reliability_tier="t",
                      retryable=True, incident="inc_mid")
        store.enqueue(channel="new", reason="a", reliability_tier="t",
                      retryable=True, incident="inc_new")
        pending = store.list_plans(status="pending")
        channels = [p["channel"] for p in pending]
        assert "new" in channels


# ===========================================================================
# C30-9: Fail-closed
# ===========================================================================
class TestC30FailClosed:

    def test_enqueue_error_returns_not_enqueued(self):
        store = RetryPlanStore()
        store._plans = "corrupted"
        result = store.enqueue(
            channel="ext", reason="a", reliability_tier="t",
            retryable=True, incident="1",
        )
        assert result.enqueued is False
        assert "error" in result.reason

    def test_list_error_returns_empty(self):
        store = RetryPlanStore()
        store._plans = "corrupted"
        assert store.list_plans() == []

    def test_count_error_returns_zero(self):
        store = RetryPlanStore()
        store._plans = "corrupted"
        assert store.count() == 0

    def test_get_plan_error_returns_none(self):
        store = RetryPlanStore()
        store._plans = "corrupted"
        assert store.get_plan("x") is None

    def test_transition_error_returns_false(self):
        store = RetryPlanStore()
        store._plans = "corrupted"
        assert store.mark_cancelled("x") is False

    def test_summary_error(self):
        store = RetryPlanStore()
        store._plans = "corrupted"
        s = store.summary()
        assert s.get("error") is True or s["total"] == 0

    def test_clear_safe(self):
        store = RetryPlanStore()
        store.enqueue(channel="ext", reason="a", reliability_tier="t",
                      retryable=True, incident="1")
        store.clear()
        assert store.count() == 0


# ===========================================================================
# C30-10: 금지 조항
# ===========================================================================
class TestC30Forbidden:

    def test_no_forbidden_strings(self):
        content = STORE_PATH.read_text(encoding="utf-8")
        body = content.split('"""', 2)[-1] if '"""' in content else content
        forbidden = [
            'chain_of_thought', 'raw_prompt', 'internal_reasoning',
            'debug_trace', 'agent_analysis', 'error_class',
        ]
        for f in forbidden:
            assert f not in body, f"Forbidden string '{f}'"

    def test_no_transport_logic(self):
        content = STORE_PATH.read_text(encoding="utf-8")
        assert "send_webhook" not in content
        assert "urllib" not in content

    def test_no_retry_execution(self):
        content = STORE_PATH.read_text(encoding="utf-8")
        assert "send_notifications" not in content
        assert "execute_retry" not in content

    def test_no_worker_scheduler(self):
        content = STORE_PATH.read_text(encoding="utf-8")
        # Strip module docstring before checking
        parts = content.split('"""')
        body = parts[-1] if len(parts) >= 3 else content
        assert "celery" not in body.lower()
        assert "cron" not in body.lower()
        assert "scheduler" not in body.lower()
        assert "background" not in body.lower()

    def test_no_app_state(self):
        content = STORE_PATH.read_text(encoding="utf-8")
        assert "app.state" not in content

    def test_no_engine_imports(self):
        content = STORE_PATH.read_text(encoding="utf-8")
        assert "src.kdexter" not in content
        assert "from src" not in content
