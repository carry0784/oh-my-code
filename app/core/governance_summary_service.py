"""
B-11: Governance Summary Service — read-only 통제 상태 집계

기존 governance info(security_state, orphan, evidence, enabled)를 수집하여
overall_status / execution_state / dominant_reason / active_constraints_count 산출.

No enforcement change. No guard change. No write action.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.logging import get_logger
from app.schemas.governance_summary_schema import (
    GovernanceHealth,
    GovernanceSummaryResponse,
    GovExecutionState,
    GovOverallStatus,
)

logger = get_logger(__name__)

# dominant_reason 우선순위 (높을수록 우선)
_REASON_PRIORITY = [
    "lockdown_active",
    "quarantined_security_state",
    "restricted_security_state",
    "orphan_detected",
    "evidence_missing",
    "governance_disabled",
]


def build_governance_summary() -> GovernanceSummaryResponse:
    """B-11: Governance summary. Read-only. No enforcement change."""
    now = datetime.now(timezone.utc)

    sec_state, enabled, orphan_detected, evidence_exists, evidence_total = _collect_governance_info()

    # --- Constraints ---
    constraints: list[str] = []

    if sec_state == "LOCKDOWN":
        constraints.append("lockdown_active")
    elif sec_state == "QUARANTINED":
        constraints.append("quarantined_security_state")
    elif sec_state == "RESTRICTED":
        constraints.append("restricted_security_state")

    if orphan_detected:
        constraints.append("orphan_detected")

    if not evidence_exists:
        constraints.append("evidence_missing")

    if not enabled:
        constraints.append("governance_disabled")

    # --- Overall status ---
    if sec_state in ("LOCKDOWN", "QUARANTINED"):
        overall = GovOverallStatus.BLOCKED
    elif len(constraints) > 0:
        overall = GovOverallStatus.DEGRADED
    else:
        overall = GovOverallStatus.HEALTHY

    # --- Execution state ---
    if sec_state in ("LOCKDOWN", "QUARANTINED"):
        exec_state = GovExecutionState.BLOCKED
    elif sec_state == "RESTRICTED":
        exec_state = GovExecutionState.GUARDED
    else:
        exec_state = GovExecutionState.ALLOWED

    # --- Dominant reason (highest priority) ---
    dominant = ""
    for reason in _REASON_PRIORITY:
        if reason in constraints:
            dominant = reason
            break

    return GovernanceSummaryResponse(
        overall_status=overall,
        execution_state=exec_state,
        dominant_reason=dominant,
        active_constraints_count=len(constraints),
        updated_at=now.isoformat(),
        security_state=sec_state,
        governance_enabled=enabled,
        orphan_detected=orphan_detected,
        evidence_exists=evidence_exists,
        evidence_total=evidence_total,
    )


def build_governance_health() -> GovernanceHealth:
    """v2 경량 요약. 5필드만."""
    s = build_governance_summary()
    return GovernanceHealth(
        overall_status=s.overall_status,
        execution_state=s.execution_state,
        dominant_reason=s.dominant_reason,
        active_constraints_count=s.active_constraints_count,
        updated_at=s.updated_at,
    )


def _collect_governance_info() -> tuple[str, bool, bool, bool, int]:
    """
    기존 governance 상태 수집. Read-only.
    Returns: (security_state, enabled, orphan_detected, evidence_exists, evidence_total)
    """
    sec_state = "UNKNOWN"
    enabled = False
    orphan_detected = False
    evidence_exists = False
    evidence_total = 0

    try:
        import app.main as main_module
        gate = getattr(main_module.app.state, "governance_gate", None)

        if gate is None:
            return sec_state, False, False, False, 0

        enabled = True

        # Security state
        if hasattr(gate, "security_ctx"):
            ctx = gate.security_ctx
            sec_state = ctx.current.value if hasattr(ctx.current, "value") else str(ctx.current)

        # Evidence
        if hasattr(gate, "evidence_store"):
            store = gate.evidence_store
            evidence_total = store.count()
            evidence_exists = evidence_total > 0

            # CR-028: Orphan detection via backend facade (no _bundles direct access)
            orphan_detected = store.count_orphan_pre() > 0

    except Exception as e:
        logger.warning("governance_summary_collect_failed", error=str(e))

    return sec_state, enabled, orphan_detected, evidence_exists, evidence_total
