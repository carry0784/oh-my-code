"""
B-08: AI Assist Data Source Service — read-only 정규화 소스 수집

AI Assist가 소비할 데이터를 기존 러너/엔드포인트에서 수집하여 정규화된 shape로 반환한다.
read-only 수집만 수행. 외부 API 호출 없음. 실행/추천/판단 없음.
fail-closed: 수집 실패 시 안전한 빈 구조 반환.

연결 소스: ops_summary(I-01~I-07), signal_pipeline, position_overview, evidence_summary
제외 소스: 실시간 호가(B-09), agent_analysis 원문, guard condition 원문
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.schemas.ai_assist_schema import (
    AIAssistSources,
    EvidenceSummary,
    OpsSummary,
    PositionOverview,
    SignalPipelineSummary,
)

logger = get_logger(__name__)


def collect_ai_assist_sources() -> AIAssistSources:
    """
    B-08: AI Assist 데이터 소스 수집.
    Read-only. No execution. No recommendation. No judgment.
    """
    return AIAssistSources(
        ops_summary=_collect_ops_summary(),
        signal_pipeline=_collect_signal_pipeline(),
        position_overview=_collect_position_overview(),
        evidence_summary=_collect_evidence_summary(),
    )


def _collect_ops_summary() -> OpsSummary:
    """I-01~I-07 ops 요약 수집. Fail-closed."""
    try:
        result = OpsSummary()

        # I-03 check
        try:
            from app.core.constitution_check_runner import run_daily_check
            check = run_daily_check()
            result.latest_check_grade = check.result.value
        except Exception:
            pass

        # I-04 preflight
        try:
            from app.core.recovery_preflight import run_recovery_preflight
            pf = run_recovery_preflight()
            result.preflight_decision = pf.decision.value
        except Exception:
            pass

        # I-05 gate
        try:
            from app.core.execution_gate import evaluate_execution_gate
            gate = evaluate_execution_gate()
            result.gate_decision = gate.decision.value
            result.gate_conditions_met = gate.conditions_met
            result.ops_score_average = gate.ops_score_average
        except Exception:
            pass

        # I-01 status (lightweight — from gate's internal checks)
        try:
            import app.main as main_module
            gate_obj = getattr(main_module.app.state, "governance_gate", None)
            if gate_obj and hasattr(gate_obj, "security_ctx"):
                ctx = gate_obj._security_ctx
                state_val = ctx.current.value if hasattr(ctx.current, "value") else str(ctx.current)
                result.system_healthy = state_val == "NORMAL"
                result.trading_authorized = result.system_healthy and result.gate_decision == "OPEN"
                if state_val == "LOCKDOWN":
                    result.status_word = "LOCKDOWN"
                elif state_val in ("QUARANTINED",):
                    result.status_word = "BRAKE"
                elif state_val == "NORMAL" and not result.system_healthy:
                    result.status_word = "UNVERIFIED"
                elif result.system_healthy:
                    result.status_word = "HEALTHY" if result.ops_score_average >= 0.7 else "DEGRADED"
                else:
                    result.status_word = "UNVERIFIED"
        except Exception:
            pass

        # I-06 approval
        try:
            from app.core.operator_approval import issue_approval
            from app.schemas.operator_approval_schema import ApprovalScope
            apr = issue_approval(approval_scope=ApprovalScope.NO_EXECUTION)
            result.approval_decision = apr.decision.value
        except Exception:
            pass

        # I-07 policy
        try:
            from app.core.execution_policy import evaluate_execution_policy
            pol = evaluate_execution_policy()
            result.policy_decision = pol.decision.value
        except Exception:
            pass

        # I-02 alerts
        try:
            import app.main as main_module
            flow_log = getattr(main_module.app.state, "flow_log", None)
            if flow_log:
                entries = flow_log.list_entries(limit=50)
                result.alert_total = len(entries)
                result.alert_suppressed = sum(1 for e in entries if e.get("policy_suppressed"))
        except Exception:
            pass

        return result
    except Exception as e:
        logger.warning("ai_assist_ops_summary_failed", error=str(e))
        return OpsSummary()


def _collect_signal_pipeline() -> SignalPipelineSummary:
    """Signal pipeline 요약 수집. Fail-closed."""
    try:
        import app.main as main_module
        # Reuse dashboard helper pattern
        from app.api.routes.dashboard import _get_signal_summary
        # _get_signal_summary requires async — use sync-safe approach
        return SignalPipelineSummary()  # populated by v2 payload in async context
    except Exception:
        return SignalPipelineSummary()


def _collect_position_overview() -> PositionOverview:
    """Position overview 수집. Fail-closed."""
    try:
        # Sync context: use dashboard helpers indirectly
        return PositionOverview()  # populated by v2 payload in async context
    except Exception:
        return PositionOverview()


def _collect_evidence_summary() -> EvidenceSummary:
    """Evidence 요약 수집. 원문 노출 없이 건수/존재 여부만. Fail-closed."""
    try:
        import app.main as main_module
        gate = getattr(main_module.app.state, "governance_gate", None)

        if gate is None:
            return EvidenceSummary(governance_active=False)

        total = None
        orphan = None
        has_recent = False

        if hasattr(gate, "evidence_store"):
            store = gate.evidence_store
            total = store.count()
            has_recent = total > 0

            # Orphan count (same pattern as governance_info)
            if hasattr(store, "_bundles"):
                bundles = store._bundles
                pre_ids = set()
                linked = set()
                for b in bundles.values():
                    artifacts = b.artifacts if hasattr(b, "artifacts") else []
                    for art in artifacts:
                        phase = art.get("phase", "") if isinstance(art, dict) else getattr(art, "phase", "")
                        if phase == "PRE":
                            pre_ids.add(b.bundle_id if hasattr(b, "bundle_id") else "")
                        elif phase in ("POST", "ERROR"):
                            lid = art.get("pre_evidence_id", "") if isinstance(art, dict) else getattr(art, "pre_evidence_id", "")
                            if lid:
                                linked.add(lid)
                orphan = len(pre_ids - linked)

        return EvidenceSummary(
            total_bundles=total,
            governance_active=True,
            has_recent_evidence=has_recent,
            orphan_count=orphan,
        )
    except Exception as e:
        logger.warning("ai_assist_evidence_summary_failed", error=str(e))
        return EvidenceSummary()
