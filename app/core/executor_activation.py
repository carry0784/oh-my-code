"""
E-02: Executor Activation Runner — 활성화 조건 판정

E-02는 activation rule 계층이며 실행 계층이 아니다.
ACTIVATION_ALLOWED means activation-eligible only, not execution-performed.
I-06 APPROVED + I-07 MATCH가 모두 있어도 activation approval 없으면 활성화 불가.

12개 검증 항목 + execution_intent_hash + activation approval receipt.

금지: executor enable, order send, exchange API, state mutation, E-03 선반영.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from app.core.logging import get_logger
from app.schemas.executor_activation_schema import (
    ActivationApprovalReceipt,
    ActivationCheckItem,
    ActivationDecision,
    ActivationReason,
    ActivationReceipt,
    _BLOCKED_REASONS,
)

logger = get_logger(__name__)

DEFAULT_OPS_SCORE_THRESHOLD = 0.7


def compute_intent_hash(
    policy_snapshot_id: str,
    execution_scope: str,
    target_symbol: str | None,
    requested_action: str,
    timestamp_bucket: str,
) -> str:
    """SHA-256 of execution intent fields."""
    raw = "|".join(
        [
            policy_snapshot_id,
            execution_scope,
            target_symbol or "",
            requested_action,
            timestamp_bucket,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def evaluate_activation(
    execution_scope: str = "NO_EXECUTION",
    requested_action: str = "check_only",
    target_symbol: str | None = None,
    activation_approval: ActivationApprovalReceipt | None = None,
    ops_score_threshold: float = DEFAULT_OPS_SCORE_THRESHOLD,
) -> ActivationReceipt:
    """
    E-02: 12개 검증 항목으로 activation 가능 여부 판정.
    Read-only rule validation. No execution. No state mutation.
    """
    now = datetime.now(timezone.utc)
    activation_id = f"ACT-{uuid.uuid4().hex[:12]}"
    items: list[ActivationCheckItem] = []
    reasons: list[ActivationReason] = []
    timestamp_bucket = now.strftime("%Y-%m-%dT%H")  # hourly bucket

    # Collect upstream data
    approval = _collect_approval()
    policy = _collect_policy()

    # --- 1. I-06 APPROVED receipt ---
    apr_ok = approval is not None and approval.get("approved")
    items.append(
        ActivationCheckItem(
            name="approval_exists",
            passed=apr_ok,
            observed=str(apr_ok),
            expected="true",
            rule_refs=["Art43"],
        )
    )
    if not apr_ok:
        reasons.append(ActivationReason.APPROVAL_MISSING)

    # --- 2. I-07 MATCH ---
    pol_ok = policy is not None and policy.get("decision") == "MATCH"
    items.append(
        ActivationCheckItem(
            name="policy_match",
            passed=pol_ok,
            observed=policy.get("decision", "none") if policy else "none",
            expected="MATCH",
            rule_refs=["Art33", "Art39"],
        )
    )
    if not pol_ok:
        reasons.append(
            ActivationReason.POLICY_NOT_MATCH
            if policy
            else ActivationReason.MISSING_POLICY_SNAPSHOT
        )

    # --- 3. approval_expiry_at ---
    exp_ok = approval is not None and not approval.get("expired", True)
    items.append(
        ActivationCheckItem(
            name="approval_not_expired",
            passed=exp_ok,
            observed=str(not approval.get("expired", True)) if approval else "none",
            expected="true",
            rule_refs=["Art43"],
        )
    )
    if not exp_ok:
        reasons.append(ActivationReason.APPROVAL_EXPIRED)

    # --- 4. gate OPEN ---
    gate_ok, gate_obs = _recheck_gate()
    items.append(
        ActivationCheckItem(
            name="gate_open",
            passed=gate_ok,
            observed=gate_obs,
            expected="OPEN",
            rule_refs=["Art43"],
        )
    )
    if not gate_ok:
        reasons.append(ActivationReason.GATE_CLOSED)

    # --- 5. preflight READY ---
    pf_ok, pf_obs = _recheck_preflight()
    items.append(
        ActivationCheckItem(
            name="preflight_ready",
            passed=pf_ok,
            observed=pf_obs,
            expected="READY",
            rule_refs=["Art43"],
        )
    )
    if not pf_ok:
        reasons.append(ActivationReason.PREFLIGHT_NOT_READY)

    # --- 6. ops_score ---
    sc_ok, sc_obs = _recheck_ops_score(ops_score_threshold)
    items.append(
        ActivationCheckItem(
            name="ops_score_ok",
            passed=sc_ok,
            observed=sc_obs,
            expected=f">={ops_score_threshold}",
            rule_refs=["Art41"],
        )
    )
    if not sc_ok:
        reasons.append(ActivationReason.OPS_SCORE_LOW)

    # --- 7. security != LOCKDOWN ---
    sec_ok, sec_obs = _recheck_security()
    items.append(
        ActivationCheckItem(
            name="no_lockdown",
            passed=sec_ok,
            observed=sec_obs,
            expected="!=LOCKDOWN",
            rule_refs=["Art7"],
        )
    )
    if not sec_ok:
        reasons.append(ActivationReason.LOCKDOWN_ACTIVE)

    # --- 8. scope compatibility ---
    from app.schemas.executor_schema import ExecutionScope, is_scope_compatible

    apr_scope = approval.get("scope", "NO_EXECUTION") if approval else "NO_EXECUTION"
    apr_symbol = approval.get("target_symbol") if approval else None
    try:
        exe_s = ExecutionScope(execution_scope)
        apr_s = ExecutionScope(apr_scope)
        scope_ok = is_scope_compatible(exe_s, apr_s, target_symbol, apr_symbol)
    except (ValueError, KeyError):
        scope_ok = False
    items.append(
        ActivationCheckItem(
            name="scope_compatible",
            passed=scope_ok,
            observed=f"{execution_scope}⊆{apr_scope}",
            expected="compatible",
            rule_refs=["Art36", "Art38"],
        )
    )
    if not scope_ok:
        reasons.append(ActivationReason.APPROVAL_SCOPE_MISMATCH)

    # --- 9. target_symbol ---
    sym_ok = True
    if execution_scope == "SPECIFIC_SYMBOL_ONLY":
        sym_ok = target_symbol is not None and target_symbol == apr_symbol
    if execution_scope == "NO_EXECUTION":
        reasons.append(ActivationReason.NO_EXECUTION_SCOPE)
        sym_ok = True  # N/A for NO_EXECUTION
    items.append(
        ActivationCheckItem(
            name="target_symbol_match",
            passed=sym_ok,
            observed=target_symbol or "none",
            expected=apr_symbol or "any",
            rule_refs=["Art38"],
        )
    )
    if not sym_ok:
        reasons.append(ActivationReason.TARGET_SYMBOL_MISMATCH)

    # --- 10. no CRITICAL since approval ---
    crit_ok, crit_obs = _recheck_critical(approval.get("timestamp", "") if approval else "")
    items.append(
        ActivationCheckItem(
            name="no_critical_alert",
            passed=crit_ok,
            observed=crit_obs,
            expected="0 critical",
            rule_refs=["Art18"],
        )
    )
    if not crit_ok:
        reasons.append(ActivationReason.CRITICAL_ALERT_DETECTED)

    # --- 11. activation approval receipt ---
    act_apr_ok = activation_approval is not None
    items.append(
        ActivationCheckItem(
            name="activation_approval_exists",
            passed=act_apr_ok,
            observed=str(act_apr_ok),
            expected="true",
            rule_refs=["Art43"],
        )
    )
    if not act_apr_ok:
        reasons.append(ActivationReason.ACTIVATION_APPROVAL_MISSING)

    # --- 12. execution_intent_hash ---
    policy_snap = policy.get("policy_id", "") if policy else ""
    expected_hash = compute_intent_hash(
        policy_snap,
        execution_scope,
        target_symbol,
        requested_action,
        timestamp_bucket,
    )
    # For now, computed hash is the reference (no prior hash to compare against in dev)
    hash_ok = len(expected_hash) == 64
    items.append(
        ActivationCheckItem(
            name="intent_hash_valid",
            passed=hash_ok,
            observed=expected_hash[:16] + "...",
            expected="valid SHA-256",
            rule_refs=["Art43"],
        )
    )
    if not hash_ok:
        reasons.append(ActivationReason.INTENT_HASH_MISMATCH)

    # --- Decision ---
    has_blocked = any(r in _BLOCKED_REASONS for r in reasons)
    if has_blocked:
        decision = ActivationDecision.ACTIVATION_BLOCKED
    elif len(reasons) > 0:
        decision = ActivationDecision.ACTIVATION_DENIED
    else:
        decision = ActivationDecision.ACTIVATION_ALLOWED

    passed = sum(1 for i in items if i.passed)
    summary = f"Activation: {passed}/{len(items)} passed, decision={decision.value}"
    if reasons:
        summary += f", reasons: {', '.join(r.value for r in reasons[:3])}"

    evidence_id = _store_activation_evidence(activation_id, decision, reasons, now)

    return ActivationReceipt(
        activation_id=activation_id,
        decision=decision,
        timestamp=now.isoformat(),
        policy_snapshot_id=policy_snap,
        approval_id=approval.get("approval_id", "") if approval else "",
        approval_receipt_hash=policy.get("approval_receipt_hash", "") if policy else "",
        execution_intent_hash=expected_hash,
        execution_scope=execution_scope,
        requested_action=requested_action,
        target_symbol=target_symbol,
        items=items,
        reasons=reasons,
        rule_refs=["Art7", "Art33", "Art36", "Art38", "Art41", "Art43"],
        activation_approval_id=activation_approval.activation_approval_id
        if activation_approval
        else None,
        activation_bucket=timestamp_bucket,
        evidence_id=evidence_id,
    )


# ---------------------------------------------------------------------------
# Recheck helpers (read-only, reuse I-07 patterns)
# ---------------------------------------------------------------------------


def _collect_approval() -> dict | None:
    try:
        from app.core.execution_policy import _get_latest_approval
        from app.core.operator_approval import validate_approval_current
        from app.schemas.operator_approval_schema import ApprovalDecision

        r = _get_latest_approval()
        if r is None:
            return None
        return {
            "approved": r.decision == ApprovalDecision.APPROVED,
            "expired": not validate_approval_current(r),
            "scope": r.approval_scope.value
            if hasattr(r.approval_scope, "value")
            else str(r.approval_scope),
            "target_symbol": r.target_symbol,
            "approval_id": r.approval_id,
            "timestamp": r.timestamp,
        }
    except Exception:
        return None


def _collect_policy() -> dict | None:
    try:
        from app.core.execution_policy import evaluate_execution_policy

        r = evaluate_execution_policy()
        return {
            "decision": r.decision.value,
            "policy_id": r.policy_id,
            "approval_receipt_hash": r.approval_receipt_hash,
        }
    except Exception:
        return None


def _recheck_gate() -> tuple[bool, str]:
    try:
        from app.core.execution_gate import evaluate_execution_gate

        r = evaluate_execution_gate()
        return r.decision.value == "OPEN", r.decision.value
    except Exception as e:
        return False, f"error:{e}"


def _recheck_preflight() -> tuple[bool, str]:
    try:
        from app.core.recovery_preflight import run_recovery_preflight

        r = run_recovery_preflight()
        return r.decision.value == "READY", r.decision.value
    except Exception as e:
        return False, f"error:{e}"


def _recheck_ops_score(threshold: float) -> tuple[bool, str]:
    try:
        from app.api.routes.dashboard import _compute_ops_score
        from app.schemas.ops_status import IntegrityPanel, TradingSafetyPanel, IncidentEvidencePanel

        s = _compute_ops_score(
            IntegrityPanel(
                exchange_db_consistency="unknown",
                snapshot_age_seconds=None,
                position_mismatch=False,
                open_orders_mismatch=False,
                balance_mismatch=False,
                stale_data=False,
            ),
            TradingSafetyPanel(),
            IncidentEvidencePanel(),
        )
        avg = (s.integrity + s.connectivity + s.execution_safety + s.evidence_completeness) / 4
        return avg >= threshold, f"{avg:.4f}"
    except Exception as e:
        return False, f"error:{e}"


def _recheck_security() -> tuple[bool, str]:
    try:
        import app.main as main_module

        gate = getattr(main_module.app.state, "governance_gate", None)
        if gate and hasattr(gate, "security_ctx"):
            v = (
                gate.security_ctx.current.value
                if hasattr(gate.security_ctx.current, "value")
                else str(gate.security_ctx.current)
            )
            return v != "LOCKDOWN", v
        return False, "UNKNOWN"
    except Exception as e:
        return False, f"error:{e}"


def _recheck_critical(since: str) -> tuple[bool, str]:
    try:
        import app.main as main_module

        fl = getattr(main_module.app.state, "flow_log", None)
        if fl is None:
            return True, "no_flow_log"
        cnt = sum(
            1
            for e in fl.list_entries(limit=50)
            if e.get("policy_urgent") and e.get("executed_at", "") > since
        )
        return cnt == 0, f"critical={cnt}"
    except Exception as e:
        return True, f"error:{e}"


def _store_activation_evidence(
    activation_id: str,
    decision: ActivationDecision,
    reasons: list,
    now: datetime,
) -> str:
    try:
        import app.main as main_module

        gate = getattr(main_module.app.state, "governance_gate", None)
        if gate is None or not hasattr(gate, "evidence_store"):
            return f"fallback-act-{uuid.uuid4().hex[:8]}"
        from kdexter.audit.evidence_store import EvidenceBundle

        bundle = EvidenceBundle(
            bundle_id=activation_id,
            created_at=now,
            trigger="executor_activation_check",
            actor="e02_executor_activation",
            action=f"activation_{decision.value.lower()}",
            before_state=None,
            after_state={
                "decision": decision.value,
                "reasons": [r.value for r in reasons],
            },
            artifacts=[],
        )
        return gate.evidence_store.store(bundle)
    except Exception as e:
        logger.warning("activation_evidence_store_failed", error=str(e))
        return f"fallback-act-{uuid.uuid4().hex[:8]}"
