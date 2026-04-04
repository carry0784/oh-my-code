"""
B-10: Ops Aggregate Service — 종합 운영 health 집계

6개 source를 read-only로 수집하여 overall_status / source_coverage / dominant_reason 산출.
판정 규칙:
  모든 source OK → HEALTHY
  stale/unavailable 1개 이상 → DEGRADED
  unavailable 2개 이상 → UNHEALTHY

금지: 거래 실행, AI 추천, write action, raw 원문 노출.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.logging import get_logger
from app.schemas.ops_aggregate_schema import (
    OpsAggregateResponse,
    OpsHealth,
    OverallStatus,
    SourceCoverage,
    SourceEntry,
    SourceStatus,
)

logger = get_logger(__name__)

_SOURCE_NAMES = [
    "ops_summary",
    "signal_pipeline",
    "position_overview",
    "evidence_summary",
    "market_feed",
    "runtime_status",
]


def build_ops_aggregate() -> OpsAggregateResponse:
    """B-10: 종합 운영 aggregate. Read-only. Fail-closed."""
    now = datetime.now(timezone.utc)
    sources: list[SourceEntry] = []

    # CR-027: Collect AI assist sources once, not 4x.
    # Each call runs preflight + gate + daily_check internally.
    _cached_src = None
    try:
        from app.core.ai_assist_source import collect_ai_assist_sources

        _cached_src = collect_ai_assist_sources()
    except Exception:
        pass

    sources.append(_check_ops_summary(_cached_src))
    sources.append(_check_signal_pipeline(_cached_src))
    sources.append(_check_position_overview(_cached_src))
    sources.append(_check_evidence_summary(_cached_src))
    sources.append(_check_market_feed())
    sources.append(_check_runtime_status())

    # Coverage
    ok = sum(1 for s in sources if s.status == SourceStatus.OK)
    stale = sum(1 for s in sources if s.status == SourceStatus.STALE)
    unavailable = sum(1 for s in sources if s.status == SourceStatus.UNAVAILABLE)
    coverage = SourceCoverage(
        sources_total=len(sources),
        ok=ok,
        stale=stale,
        unavailable=unavailable,
    )

    # Overall status
    if unavailable >= 2:
        overall = OverallStatus.UNHEALTHY
    elif stale > 0 or unavailable > 0:
        overall = OverallStatus.DEGRADED
    else:
        overall = OverallStatus.HEALTHY

    # Dominant reason
    dominant = ""
    if overall != OverallStatus.HEALTHY:
        bad = [s for s in sources if s.status != SourceStatus.OK]
        if len(bad) >= 2:
            dominant = f"multiple_sources: {', '.join(s.name for s in bad[:3])}"
        elif len(bad) == 1:
            dominant = f"{bad[0].name}_{bad[0].status.value.lower()}"

    return OpsAggregateResponse(
        overall_status=overall,
        source_coverage=coverage,
        dominant_reason=dominant,
        updated_at=now.isoformat(),
        sources=sources,
    )


def build_ops_health() -> OpsHealth:
    """v2 경량 요약. 4필드만."""
    agg = build_ops_aggregate()
    return OpsHealth(
        overall_status=agg.overall_status,
        source_coverage=agg.source_coverage,
        dominant_reason=agg.dominant_reason,
        updated_at=agg.updated_at,
    )


# ---------------------------------------------------------------------------
# Source checkers (read-only, fail-closed)
# ---------------------------------------------------------------------------


def _check_ops_summary(src=None) -> SourceEntry:
    try:
        if src is None:
            from app.core.ai_assist_source import collect_ai_assist_sources

            src = collect_ai_assist_sources()
        status = SourceStatus.OK if src.ops_summary.status_word != "UNKNOWN" else SourceStatus.STALE
        return SourceEntry(
            name="ops_summary",
            status=status,
            summary=f"status={src.ops_summary.status_word}, gate={src.ops_summary.gate_decision}",
        )
    except Exception:
        return SourceEntry(
            name="ops_summary", status=SourceStatus.UNAVAILABLE, summary="collection failed"
        )


def _check_signal_pipeline(src=None) -> SourceEntry:
    try:
        if src is None:
            from app.core.ai_assist_source import collect_ai_assist_sources

            src = collect_ai_assist_sources()
        # Signal pipeline is populated in async context only
        if src.signal_pipeline.total_24h > 0:
            return SourceEntry(
                name="signal_pipeline",
                status=SourceStatus.OK,
                summary=f"24h={src.signal_pipeline.total_24h}",
            )
        return SourceEntry(
            name="signal_pipeline",
            status=SourceStatus.STALE,
            summary="no 24h signals (sync context or empty)",
        )
    except Exception:
        return SourceEntry(
            name="signal_pipeline", status=SourceStatus.UNAVAILABLE, summary="collection failed"
        )


def _check_position_overview(src=None) -> SourceEntry:
    try:
        if src is None:
            from app.core.ai_assist_source import collect_ai_assist_sources

            src = collect_ai_assist_sources()
        return SourceEntry(
            name="position_overview",
            status=SourceStatus.OK,
            summary=f"positions={src.position_overview.total_positions}",
        )
    except Exception:
        return SourceEntry(
            name="position_overview", status=SourceStatus.UNAVAILABLE, summary="collection failed"
        )


def _check_evidence_summary(src=None) -> SourceEntry:
    try:
        if src is None:
            from app.core.ai_assist_source import collect_ai_assist_sources

            src = collect_ai_assist_sources()
        if src.evidence_summary.governance_active:
            return SourceEntry(
                name="evidence_summary",
                status=SourceStatus.OK,
                summary=f"bundles={src.evidence_summary.total_bundles}",
            )
        return SourceEntry(
            name="evidence_summary",
            status=SourceStatus.UNAVAILABLE,
            summary="governance not active",
        )
    except Exception:
        return SourceEntry(
            name="evidence_summary", status=SourceStatus.UNAVAILABLE, summary="collection failed"
        )


def _check_market_feed() -> SourceEntry:
    try:
        # Market feed requires async context for live quotes
        # In sync context, check if service module is importable
        from app.core.market_feed_service import build_empty_market_feed

        return SourceEntry(
            name="market_feed",
            status=SourceStatus.STALE,
            summary="available (live data in async context)",
        )
    except Exception:
        return SourceEntry(
            name="market_feed", status=SourceStatus.UNAVAILABLE, summary="service unavailable"
        )


def _check_runtime_status() -> SourceEntry:
    try:
        import app.main as main_module

        gate = getattr(main_module.app.state, "governance_gate", None)
        if gate is not None:
            return SourceEntry(
                name="runtime_status", status=SourceStatus.OK, summary="governance active"
            )
        return SourceEntry(
            name="runtime_status", status=SourceStatus.UNAVAILABLE, summary="governance_gate=None"
        )
    except Exception:
        return SourceEntry(
            name="runtime_status", status=SourceStatus.UNAVAILABLE, summary="app state inaccessible"
        )
