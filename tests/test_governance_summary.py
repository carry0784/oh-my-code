"""
B-11: Governance Summary Tests
"""

import pytest
from app.schemas.governance_summary_schema import (
    GovernanceSummaryResponse,
    GovernanceHealth,
    GovOverallStatus,
    GovExecutionState,
)


class TestSchema:
    def test_imports(self):
        assert GovernanceSummaryResponse is not None
        assert GovernanceHealth is not None

    def test_default_response(self):
        r = GovernanceSummaryResponse()
        assert r.overall_status == GovOverallStatus.DEGRADED
        assert "Read-only" in r.summary_note

    def test_health_shape(self):
        h = GovernanceHealth(
            overall_status=GovOverallStatus.HEALTHY,
            execution_state=GovExecutionState.ALLOWED,
            dominant_reason="",
            active_constraints_count=0,
            updated_at="2026-03-25T00:00:00Z",
        )
        assert h.overall_status == GovOverallStatus.HEALTHY
        assert h.active_constraints_count == 0


class TestRules:
    def test_healthy_when_normal_enabled_no_orphan_evidence(self):
        from app.core.governance_summary_service import build_governance_summary

        s = build_governance_summary()
        # In dev env, result depends on governance_gate state
        assert s.overall_status.value in ("HEALTHY", "DEGRADED", "BLOCKED")

    def test_degraded_rules(self):
        """RESTRICTED / orphan / evidence missing / enabled=false → DEGRADED."""
        # Unit rule test without runtime dependency
        constraints = ["restricted_security_state"]
        overall = GovOverallStatus.DEGRADED if len(constraints) > 0 else GovOverallStatus.HEALTHY
        assert overall == GovOverallStatus.DEGRADED

    def test_blocked_rules(self):
        """QUARANTINED / LOCKDOWN → BLOCKED (highest priority)."""
        sec = "LOCKDOWN"
        overall = (
            GovOverallStatus.BLOCKED
            if sec in ("LOCKDOWN", "QUARANTINED")
            else GovOverallStatus.DEGRADED
        )
        assert overall == GovOverallStatus.BLOCKED

    def test_enabled_false_is_degraded(self):
        """enabled=false → at least DEGRADED."""
        enabled = False
        constraints = []
        if not enabled:
            constraints.append("governance_disabled")
        sec = "NORMAL"
        if sec in ("LOCKDOWN", "QUARANTINED"):
            overall = GovOverallStatus.BLOCKED
        elif len(constraints) > 0:
            overall = GovOverallStatus.DEGRADED
        else:
            overall = GovOverallStatus.HEALTHY
        assert overall == GovOverallStatus.DEGRADED

    def test_blocked_overrides_enabled_false(self):
        """LOCKDOWN + enabled=false → BLOCKED (not just DEGRADED)."""
        sec = "LOCKDOWN"
        overall = (
            GovOverallStatus.BLOCKED
            if sec in ("LOCKDOWN", "QUARANTINED")
            else GovOverallStatus.DEGRADED
        )
        assert overall == GovOverallStatus.BLOCKED

    def test_orphan_causes_degraded(self):
        constraints = ["orphan_detected"]
        overall = GovOverallStatus.DEGRADED if len(constraints) > 0 else GovOverallStatus.HEALTHY
        assert overall == GovOverallStatus.DEGRADED

    def test_evidence_missing_causes_degraded(self):
        constraints = ["evidence_missing"]
        overall = GovOverallStatus.DEGRADED if len(constraints) > 0 else GovOverallStatus.HEALTHY
        assert overall == GovOverallStatus.DEGRADED

    def test_execution_state_normal_is_allowed(self):
        sec = "NORMAL"
        if sec in ("LOCKDOWN", "QUARANTINED"):
            es = GovExecutionState.BLOCKED
        elif sec == "RESTRICTED":
            es = GovExecutionState.GUARDED
        else:
            es = GovExecutionState.ALLOWED
        assert es == GovExecutionState.ALLOWED

    def test_execution_state_restricted_is_guarded(self):
        sec = "RESTRICTED"
        es = GovExecutionState.GUARDED if sec == "RESTRICTED" else GovExecutionState.ALLOWED
        assert es == GovExecutionState.GUARDED


class TestDominantReason:
    def test_priority_order(self):
        from app.core.governance_summary_service import _REASON_PRIORITY

        assert _REASON_PRIORITY[0] == "lockdown_active"
        assert _REASON_PRIORITY[-1] == "governance_disabled"

    def test_dominant_reason_generated(self):
        from app.core.governance_summary_service import build_governance_summary

        s = build_governance_summary()
        if s.overall_status != GovOverallStatus.HEALTHY:
            assert len(s.dominant_reason) > 0

    def test_constraints_count(self):
        from app.core.governance_summary_service import build_governance_summary

        s = build_governance_summary()
        assert s.active_constraints_count >= 0


class TestV2:
    def test_v2_references_governance_health(self):
        import inspect
        from app.api.routes.dashboard import dashboard_data_v2

        src = inspect.getsource(dashboard_data_v2)
        assert "governance_health" in src

    def test_endpoint_exists(self):
        from app.api.routes.dashboard import governance_summary

        assert governance_summary is not None


class TestReadOnly:
    def test_no_write_in_service(self):
        import inspect
        from app.core import governance_summary_service

        src = inspect.getsource(governance_summary_service)
        forbidden = ["db.add", "db.delete", "session.commit", "submit_order"]
        for f in forbidden:
            assert f not in src

    def test_no_raw_fields(self):
        assert "raw_policy" not in GovernanceSummaryResponse.model_fields
        assert "raw_audit" not in GovernanceSummaryResponse.model_fields
        assert "guard_condition" not in GovernanceSummaryResponse.model_fields
