"""
B-08: AI Assist Data Source Tests

Tests:
  - schema validation
  - source collection (read-only)
  - empty/missing data fail-closed
  - excluded sources not exposed
  - v2 payload integration
"""

import pytest


class TestAIAssistSchema:
    """Schema structure validation."""

    def test_schema_imports(self):
        from app.schemas.ai_assist_schema import (
            AIAssistSources, OpsSummary, SignalPipelineSummary,
            PositionOverview, EvidenceSummary,
        )
        assert AIAssistSources is not None

    def test_default_ai_sources(self):
        from app.schemas.ai_assist_schema import AIAssistSources
        s = AIAssistSources()
        assert s.ops_summary.status_word == "UNKNOWN"
        assert s.signal_pipeline.total_24h == 0
        assert s.position_overview.total_positions == 0
        assert s.evidence_summary.governance_active is False
        assert "Read-only" in s.source_note

    def test_ops_summary_shape(self):
        from app.schemas.ai_assist_schema import OpsSummary
        o = OpsSummary()
        fields = set(OpsSummary.model_fields.keys())
        expected = {
            "status_word", "system_healthy", "trading_authorized",
            "ops_score_average", "latest_check_grade", "preflight_decision",
            "gate_decision", "gate_conditions_met", "approval_decision",
            "policy_decision", "alert_total", "alert_suppressed",
        }
        assert expected.issubset(fields)

    def test_signal_pipeline_shape(self):
        from app.schemas.ai_assist_schema import SignalPipelineSummary
        s = SignalPipelineSummary(total_24h=10, validated=7, rejected=2, executed=5, pending=1)
        assert s.total_24h == 10
        assert s.rejection_rate is None

    def test_position_overview_shape(self):
        from app.schemas.ai_assist_schema import PositionOverview
        p = PositionOverview(total_positions=3, exchanges_connected=2)
        assert p.total_positions == 3
        assert p.exchanges_total == 6

    def test_evidence_summary_shape(self):
        from app.schemas.ai_assist_schema import EvidenceSummary
        e = EvidenceSummary(governance_active=True, total_bundles=42)
        assert e.governance_active is True
        assert e.total_bundles == 42


class TestAIAssistSourceCollection:
    """Source collection behavior."""

    def test_collect_returns_ai_assist_sources(self):
        from app.core.ai_assist_source import collect_ai_assist_sources
        from app.schemas.ai_assist_schema import AIAssistSources
        result = collect_ai_assist_sources()
        assert isinstance(result, AIAssistSources)

    def test_collect_ops_summary_has_values(self):
        from app.core.ai_assist_source import collect_ai_assist_sources
        result = collect_ai_assist_sources()
        # In dev env, some values should be populated
        assert result.ops_summary.latest_check_grade in ("OK", "WARN", "FAIL", "BLOCK", "UNKNOWN")
        assert result.ops_summary.gate_decision in ("OPEN", "CLOSED", "UNKNOWN")

    def test_collect_evidence_summary(self):
        from app.core.ai_assist_source import collect_ai_assist_sources
        result = collect_ai_assist_sources()
        # governance_active depends on whether gate is initialized
        assert isinstance(result.evidence_summary.governance_active, bool)


class TestReadOnlyProperty:
    """Verify no write actions in source code."""

    def test_no_write_actions_in_source(self):
        import inspect
        from app.core.ai_assist_source import collect_ai_assist_sources
        source = inspect.getsource(inspect.getmodule(collect_ai_assist_sources))
        forbidden = ["db.add", "db.delete", "session.commit", "submit_order",
                      "execute_trade", "close_position", "create_order"]
        for f in forbidden:
            assert f not in source, f"Forbidden write action: {f}"

    def test_no_execution_function_in_schema(self):
        """Schema should not define functions that perform execution."""
        from app.schemas import ai_assist_schema
        assert not hasattr(ai_assist_schema, "execute_trade")
        assert not hasattr(ai_assist_schema, "submit_order")
        assert not hasattr(ai_assist_schema, "auto_recommend")


class TestFailClosed:
    """Verify fail-closed on missing/invalid data."""

    def test_collect_never_raises(self):
        from app.core.ai_assist_source import collect_ai_assist_sources
        # Should return safely even without full app context
        result = collect_ai_assist_sources()
        assert result is not None

    def test_empty_sources_are_safe(self):
        from app.schemas.ai_assist_schema import AIAssistSources
        s = AIAssistSources()
        d = s.model_dump()
        assert d["ops_summary"]["status_word"] == "UNKNOWN"
        assert d["signal_pipeline"]["total_24h"] == 0
        assert d["position_overview"]["total_positions"] == 0


class TestExcludedSources:
    """Verify excluded sources are not exposed."""

    def test_no_agent_analysis_field_in_schema(self):
        """Schema models should not have agent_analysis as a field."""
        from app.schemas.ai_assist_schema import AIAssistSources, OpsSummary
        assert "agent_analysis" not in AIAssistSources.model_fields
        assert "agent_analysis" not in OpsSummary.model_fields

    def test_no_guard_condition_in_schema(self):
        import inspect
        from app.schemas import ai_assist_schema
        source = inspect.getsource(ai_assist_schema)
        assert "guard_condition" not in source
        assert "condition_id" not in source

    def test_no_realtime_feed_in_schema(self):
        import inspect
        from app.schemas import ai_assist_schema
        source = inspect.getsource(ai_assist_schema)
        assert "orderbook" not in source.lower()
        assert "bid_ask" not in source.lower()


class TestV2Integration:
    """Verify v2 payload integration."""

    def test_v2_data_function_references_ai_assist(self):
        import inspect
        from app.api.routes.dashboard import dashboard_data_v2
        source = inspect.getsource(dashboard_data_v2)
        assert "ai_assist_sources" in source

    def test_ai_sources_endpoint_exists(self):
        from app.api.routes.dashboard import ai_sources
        assert ai_sources is not None
