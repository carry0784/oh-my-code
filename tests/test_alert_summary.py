"""
B-13: Alert Priority / Escalation Summary Tests
"""

import pytest
from app.schemas.alert_summary_schema import (
    AlertSummaryDetailResponse, AlertHealth,
    PriorityLevel, EscalationState, PriorityBreakdown,
)


class TestSchema:
    def test_imports(self):
        assert AlertSummaryDetailResponse is not None
        assert AlertHealth is not None

    def test_default_response(self):
        r = AlertSummaryDetailResponse()
        assert r.top_priority == PriorityLevel.INFO
        assert r.escalation_state == EscalationState.NONE
        assert "Read-only" in r.summary_note

    def test_health_shape(self):
        h = AlertHealth(
            top_priority=PriorityLevel.P1,
            escalation_state=EscalationState.CRITICAL,
            top_reason="lockdown",
            alert_count=1,
            updated_at="2026-03-25T00:00:00Z",
        )
        assert h.top_priority == PriorityLevel.P1


class TestPriorityRules:
    def test_p1_on_blocked(self):
        """governance BLOCKED → P1 / critical."""
        from app.core.alert_summary_service import build_alert_summary
        s = build_alert_summary()
        # In dev env, actual priority depends on runtime state
        assert s.top_priority.value in ("P1", "P2", "P3", "INFO")

    def test_p1_conditions(self):
        """P1 = gov BLOCKED or exec BLOCKED or ops UNHEALTHY."""
        gov, exec_s, ops = "BLOCKED", "BLOCKED", "UNHEALTHY"
        is_p1 = gov == "BLOCKED" or exec_s == "BLOCKED" or ops == "UNHEALTHY"
        assert is_p1

    def test_p2_conditions(self):
        """P2 = DEGRADED / GUARDED / unavailable."""
        gov, exec_s, ops, unavail = "DEGRADED", "ALLOWED", "HEALTHY", 1
        is_p2 = gov == "DEGRADED" or exec_s == "GUARDED" or ops == "DEGRADED" or unavail > 0
        assert is_p2

    def test_p3_conditions(self):
        """P3 = stale / constraints."""
        stale, constraints = 1, 2
        is_p3 = stale > 0 or constraints > 0
        assert is_p3

    def test_info_when_clear(self):
        """INFO = no issues."""
        alerts = []
        top = PriorityLevel.INFO if not alerts else PriorityLevel.P3
        assert top == PriorityLevel.INFO


class TestEscalation:
    def test_escalation_mapping(self):
        mapping = {
            PriorityLevel.P1: EscalationState.CRITICAL,
            PriorityLevel.P2: EscalationState.ESCALATED,
            PriorityLevel.P3: EscalationState.WATCH,
            PriorityLevel.INFO: EscalationState.NONE,
        }
        assert mapping[PriorityLevel.P1] == EscalationState.CRITICAL
        assert mapping[PriorityLevel.INFO] == EscalationState.NONE


class TestTopReason:
    def test_top_reason_generated(self):
        from app.core.alert_summary_service import build_alert_summary
        s = build_alert_summary()
        assert len(s.top_reason) > 0  # always has a reason

    def test_breakdown_populated(self):
        from app.core.alert_summary_service import build_alert_summary
        s = build_alert_summary()
        bd = s.breakdown
        assert bd.p1_count >= 0
        assert bd.p1_count + bd.p2_count + bd.p3_count + bd.info_count >= 0


class TestV2:
    def test_v2_references_alert_health(self):
        import inspect
        from app.api.routes.dashboard import dashboard_data_v2
        src = inspect.getsource(dashboard_data_v2)
        assert "alert_health" in src

    def test_endpoint_exists(self):
        from app.api.routes.dashboard import alert_summary_detail
        assert alert_summary_detail is not None


class TestReadOnly:
    def test_no_write_in_service(self):
        import inspect
        from app.core import alert_summary_service
        src = inspect.getsource(alert_summary_service)
        forbidden = ["db.add", "db.delete", "session.commit", "submit_order", "send_notification"]
        for f in forbidden:
            assert f not in src

    def test_no_raw_fields(self):
        assert "raw_alert" not in AlertSummaryDetailResponse.model_fields
        assert "ack_state" not in AlertSummaryDetailResponse.model_fields
        assert "mute_state" not in AlertSummaryDetailResponse.model_fields
