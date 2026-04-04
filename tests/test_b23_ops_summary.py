"""
B-23 / STEP 1~3: Ops Safety Summary Extended + Tab 2 패널 테스트

대상:
- /dashboard/api/ops-safety-summary 확장 필드
- B-23 Ops Summary Panel
- Tab 2 Observation Layer 섹션 존재
"""

import inspect
import pytest


class TestOpsSafetySummaryEndpoint:
    """ops-safety-summary 확장 필드 검증."""

    def test_schema_importable(self):
        from app.schemas.ops_safety_schema import OpsSafetySummary

        assert OpsSafetySummary is not None

    def test_schema_has_extended_fields(self):
        from app.schemas.ops_safety_schema import OpsSafetySummary

        fields = set(OpsSafetySummary.model_fields.keys())
        required = {
            "timestamp",
            "preflight_decision",
            "gate_decision",
            "approval_decision",
            "all_clear",
            "blocked_reasons",
            "next_safe_steps",
            "pipeline_state",
            "ops_score",
            "policy_decision",
            "lockdown_state",
            "trading_authorized",
            "check_grade",
            "conditions_met",
            "preflight_evidence_id",
            "gate_evidence_id",
            "approval_id",
            "safety_note",
        }
        assert required.issubset(fields)

    def test_default_values(self):
        from app.schemas.ops_safety_schema import OpsSafetySummary

        s = OpsSafetySummary(timestamp="2026-01-01T00:00:00Z")
        assert s.pipeline_state == "UNKNOWN"
        assert s.ops_score is None
        assert s.policy_decision == "UNKNOWN"
        assert s.lockdown_state == "UNKNOWN"
        assert s.trading_authorized is None
        assert s.check_grade == "UNKNOWN"
        assert s.conditions_met is None
        assert s.all_clear is False
        assert s.safety_note == "Read-only. No execution authority."


class TestOpsSafetySummaryReadOnly:
    """ops-safety-summary endpoint read-only 보장."""

    def test_endpoint_registered_in_dashboard(self):
        from app.api.routes.dashboard import router

        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/api/ops-safety-summary" in paths

    def test_no_write_actions_in_endpoint_source(self):
        import app.api.routes.dashboard as mod

        src = inspect.getsource(mod.ops_safety_summary)
        forbidden = ["db.add(", "db.delete(", "session.commit(", "submit_order", "execute_trade"]
        for f in forbidden:
            assert f not in src, f"Write action found: {f}"


class TestTab2SectionsExist:
    """Tab 2 B-17~B-23 HTML 섹션 존재 테스트."""

    def test_dashboard_template_has_b23(self):
        from pathlib import Path

        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        assert 'id="b23-ops-summary"' in html

    def test_dashboard_template_has_exchange_environment(self):
        from pathlib import Path

        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        assert 'id="exchange-environment"' in html

    def test_dashboard_template_has_strategy_context(self):
        from pathlib import Path

        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        assert 'id="strategy-context"' in html

    def test_dashboard_template_has_execution_pipeline(self):
        from pathlib import Path

        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        assert 'id="execution-pipeline"' in html

    def test_dashboard_template_has_unified_timeline(self):
        from pathlib import Path

        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        assert 'id="unified-timeline"' in html

    def test_dashboard_template_has_risk_monitor(self):
        from pathlib import Path

        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        assert 'id="risk-monitor"' in html

    def test_dashboard_template_has_scenario_viewer(self):
        from pathlib import Path

        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        assert 'id="scenario-viewer"' in html

    def test_dashboard_template_has_safety_summary_panel(self):
        from pathlib import Path

        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        assert 'id="b14-pf-badge"' in html


class TestTab2RenderFunctions:
    """Tab 2 JS 렌더 함수 존재 확인."""

    def test_render_functions_in_template(self):
        from pathlib import Path

        html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        functions = [
            "renderExchangeEnvironment",
            "renderStrategyContext",
            "renderExecutionPipeline",
            "renderUnifiedTimeline",
            "renderRiskMonitor",
            "renderScenarioViewer",
            "fetchB23OpsSummary",
        ]
        for fn in functions:
            assert fn in html, f"Missing render function: {fn}"
