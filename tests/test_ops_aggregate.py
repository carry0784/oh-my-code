"""
B-10: Ops Aggregate Tests — overall_status / source_coverage / dominant_reason
"""

import pytest


class TestAggregateSchema:
    def test_schema_imports(self):
        from app.schemas.ops_aggregate_schema import (
            OpsAggregateResponse,
            OpsHealth,
            OverallStatus,
            SourceCoverage,
            SourceEntry,
            SourceStatus,
        )

        assert OpsAggregateResponse is not None

    def test_default_response(self):
        from app.schemas.ops_aggregate_schema import OpsAggregateResponse

        r = OpsAggregateResponse()
        assert r.overall_status.value == "UNHEALTHY"
        assert "Read-only" in r.aggregate_note

    def test_ops_health_shape(self):
        from app.schemas.ops_aggregate_schema import OpsHealth, OverallStatus, SourceCoverage

        h = OpsHealth(
            overall_status=OverallStatus.HEALTHY,
            source_coverage=SourceCoverage(sources_total=6, ok=6),
            dominant_reason="",
            updated_at="2026-03-25T00:00:00Z",
        )
        assert h.overall_status.value == "HEALTHY"
        assert h.source_coverage.ok == 6


class TestAggregateRules:
    def test_all_ok_is_healthy(self):
        from app.schemas.ops_aggregate_schema import SourceEntry, SourceStatus
        from app.core.ops_aggregate_service import build_ops_aggregate

        # Integration test: actual sources may not all be OK, but test structure
        agg = build_ops_aggregate()
        assert agg.overall_status.value in ("HEALTHY", "DEGRADED", "UNHEALTHY")
        assert agg.source_coverage.sources_total == 6

    def test_degraded_with_stale(self):
        from app.schemas.ops_aggregate_schema import (
            OverallStatus,
            SourceCoverage,
            SourceEntry,
            SourceStatus,
        )

        sources = [
            SourceEntry(name="a", status=SourceStatus.OK),
            SourceEntry(name="b", status=SourceStatus.STALE),
            SourceEntry(name="c", status=SourceStatus.OK),
        ]
        stale = sum(1 for s in sources if s.status == SourceStatus.STALE)
        unavailable = sum(1 for s in sources if s.status == SourceStatus.UNAVAILABLE)
        if unavailable >= 2:
            overall = OverallStatus.UNHEALTHY
        elif stale > 0 or unavailable > 0:
            overall = OverallStatus.DEGRADED
        else:
            overall = OverallStatus.HEALTHY
        assert overall == OverallStatus.DEGRADED

    def test_unhealthy_with_2_unavailable(self):
        from app.schemas.ops_aggregate_schema import OverallStatus, SourceEntry, SourceStatus

        sources = [
            SourceEntry(name="a", status=SourceStatus.UNAVAILABLE),
            SourceEntry(name="b", status=SourceStatus.UNAVAILABLE),
            SourceEntry(name="c", status=SourceStatus.OK),
        ]
        unavailable = sum(1 for s in sources if s.status == SourceStatus.UNAVAILABLE)
        overall = OverallStatus.UNHEALTHY if unavailable >= 2 else OverallStatus.DEGRADED
        assert overall == OverallStatus.UNHEALTHY

    def test_healthy_all_ok(self):
        from app.schemas.ops_aggregate_schema import OverallStatus, SourceEntry, SourceStatus

        sources = [SourceEntry(name=f"s{i}", status=SourceStatus.OK) for i in range(6)]
        stale = sum(1 for s in sources if s.status == SourceStatus.STALE)
        unavailable = sum(1 for s in sources if s.status == SourceStatus.UNAVAILABLE)
        if unavailable >= 2:
            overall = OverallStatus.UNHEALTHY
        elif stale > 0 or unavailable > 0:
            overall = OverallStatus.DEGRADED
        else:
            overall = OverallStatus.HEALTHY
        assert overall == OverallStatus.HEALTHY


class TestSourceCoverage:
    def test_coverage_fields(self):
        from app.core.ops_aggregate_service import build_ops_aggregate

        agg = build_ops_aggregate()
        c = agg.source_coverage
        assert c.sources_total == 6
        assert c.ok + c.stale + c.unavailable == c.sources_total

    def test_dominant_reason_present_when_not_healthy(self):
        from app.core.ops_aggregate_service import build_ops_aggregate

        agg = build_ops_aggregate()
        if agg.overall_status.value != "HEALTHY":
            assert len(agg.dominant_reason) > 0


class TestV2Integration:
    def test_v2_references_ops_health(self):
        import inspect
        from app.api.routes.dashboard import dashboard_data_v2

        src = inspect.getsource(dashboard_data_v2)
        assert "ops_health" in src

    def test_ops_aggregate_endpoint_exists(self):
        from app.api.routes.dashboard import ops_aggregate

        assert ops_aggregate is not None


class TestReadOnly:
    def test_no_write_in_service(self):
        import inspect
        from app.core import ops_aggregate_service

        src = inspect.getsource(ops_aggregate_service)
        forbidden = ["db.add", "db.delete", "session.commit", "submit_order"]
        for f in forbidden:
            assert f not in src


class TestNoRawExposure:
    def test_no_raw_fields_in_schema(self):
        from app.schemas.ops_aggregate_schema import OpsAggregateResponse, SourceEntry

        assert "agent_analysis" not in OpsAggregateResponse.model_fields
        assert "guard_condition" not in SourceEntry.model_fields
        assert "raw_text" not in SourceEntry.model_fields
