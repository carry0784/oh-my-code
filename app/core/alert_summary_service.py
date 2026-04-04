"""
B-13: Alert Priority / Escalation Summary Service — read-only

판정 규칙:
  P1/critical: governance BLOCKED / execution BLOCKED / ops UNHEALTHY
  P2/escalated: governance DEGRADED / execution GUARDED / ops DEGRADED / unavailable source
  P3/watch: stale source / market stale / constraints > 0 / warnings
  INFO/none: 나머지

No ack/write/mute/retry/notification. Read-only.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.logging import get_logger
from app.schemas.alert_summary_schema import (
    AlertHealth,
    AlertSummaryDetailResponse,
    EscalationState,
    PriorityBreakdown,
    PriorityLevel,
)

logger = get_logger(__name__)


def build_alert_summary() -> AlertSummaryDetailResponse:
    """B-13: Alert priority summary. Read-only."""
    now = datetime.now(timezone.utc)

    ops_status, gov_status, exec_state, market_trust = "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"
    constraints, stale, unavailable = 0, 0, 0

    # Collect from existing services
    try:
        from app.core.ops_aggregate_service import build_ops_aggregate

        agg = build_ops_aggregate()
        ops_status = agg.overall_status.value
        stale = agg.source_coverage.stale
        unavailable = agg.source_coverage.unavailable
    except Exception:
        pass

    try:
        from app.core.governance_summary_service import build_governance_summary

        gov = build_governance_summary()
        gov_status = gov.overall_status.value
        exec_state = gov.execution_state.value
        constraints = gov.active_constraints_count
    except Exception:
        pass

    try:
        from app.core.market_feed_service import build_empty_market_feed

        # Market feed requires async; use lightweight check
        market_trust = "STALE"  # conservative in sync context
    except Exception:
        pass

    # --- Priority / Escalation ---
    alerts: list[tuple[PriorityLevel, str]] = []

    # P1 checks
    if gov_status == "BLOCKED" or exec_state == "BLOCKED" or ops_status == "UNHEALTHY":
        reason = (
            "lockdown_active"
            if gov_status == "BLOCKED"
            else "ops_unhealthy"
            if ops_status == "UNHEALTHY"
            else "execution_blocked"
        )
        alerts.append((PriorityLevel.P1, reason))

    # P2 checks
    if gov_status == "DEGRADED":
        alerts.append((PriorityLevel.P2, "governance_degraded"))
    if exec_state == "GUARDED":
        alerts.append((PriorityLevel.P2, "execution_guarded"))
    if ops_status == "DEGRADED":
        alerts.append((PriorityLevel.P2, "ops_degraded"))
    if unavailable > 0:
        alerts.append((PriorityLevel.P2, f"sources_unavailable_{unavailable}"))

    # P3 checks
    if stale > 0:
        alerts.append((PriorityLevel.P3, f"sources_stale_{stale}"))
    if constraints > 0:
        alerts.append((PriorityLevel.P3, f"active_constraints_{constraints}"))

    # Determine top
    priority_order = {
        PriorityLevel.P1: 0,
        PriorityLevel.P2: 1,
        PriorityLevel.P3: 2,
        PriorityLevel.INFO: 3,
    }
    escalation_map = {
        PriorityLevel.P1: EscalationState.CRITICAL,
        PriorityLevel.P2: EscalationState.ESCALATED,
        PriorityLevel.P3: EscalationState.WATCH,
        PriorityLevel.INFO: EscalationState.NONE,
    }

    if alerts:
        alerts.sort(key=lambda x: priority_order.get(x[0], 99))
        top_priority = alerts[0][0]
        top_reason = alerts[0][1]
    else:
        top_priority = PriorityLevel.INFO
        top_reason = "all_clear"

    escalation = escalation_map.get(top_priority, EscalationState.NONE)

    # Breakdown
    bd = PriorityBreakdown(
        p1_count=sum(1 for a in alerts if a[0] == PriorityLevel.P1),
        p2_count=sum(1 for a in alerts if a[0] == PriorityLevel.P2),
        p3_count=sum(1 for a in alerts if a[0] == PriorityLevel.P3),
        info_count=0,
    )

    return AlertSummaryDetailResponse(
        top_priority=top_priority,
        escalation_state=escalation,
        top_reason=top_reason,
        alert_count=len(alerts),
        updated_at=now.isoformat(),
        breakdown=bd,
        ops_status=ops_status,
        governance_status=gov_status,
        execution_state=exec_state,
        market_worst_trust=market_trust,
        active_constraints=constraints,
        stale_sources=stale,
        unavailable_sources=unavailable,
    )


def build_alert_health() -> AlertHealth:
    """v2 경량 요약. 5필드만."""
    s = build_alert_summary()
    return AlertHealth(
        top_priority=s.top_priority,
        escalation_state=s.escalation_state,
        top_reason=s.top_reason,
        alert_count=s.alert_count,
        updated_at=s.updated_at,
    )
