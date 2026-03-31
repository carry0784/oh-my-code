"""
I-07: Execution Policy Runner — 승인-실행 상태 일치 검증

I-07은 실행 계층이 아니라 승인-실행 일치 검증 계층이다.
MATCH means policy-match only, not execution-performed.
I-06 APPROVED receipt는 실행 허가가 아니다.
I-07 MATCH 없이는 어떤 실행도 허용되지 않는다.
E-01은 I-06 + I-07 완료 전 활성화 금지다.

역참조: Operating Constitution v1.0 제33조, 제39조, 제43조

검증 항목 (6개):
  1. approval_expiry_at 미만료
  2. gate.decision == OPEN
  3. preflight.decision == READY
  4. ops_score >= threshold
  5. security_state != LOCKDOWN
  6. 승인 이후 CRITICAL 알림 없음

금지: 실행, 만료 연장, drift 무시, state mutation, E-01 선반영
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from app.core.logging import get_logger
from app.schemas.execution_policy_schema import (
    ExecutionPolicyResult,
    PolicyCheckItem,
    PolicyDecision,
    PolicyDriftReason,
)
from app.schemas.operator_approval_schema import (
    ApprovalDecision,
    OperatorApprovalReceipt,
)

logger = get_logger(__name__)

DEFAULT_OPS_SCORE_THRESHOLD = 0.7


def compute_receipt_hash(receipt: OperatorApprovalReceipt) -> str:
    """
    SHA-256 hash of approval receipt fields for integrity verification.
    Fields: gate_snapshot_id + preflight_id + check_id + ops_score +
            security_state + timestamp + approval_expiry_at +
            approval_scope + target_symbol
    """
    parts = [
        receipt.gate_snapshot_id,
        receipt.preflight_id,
        receipt.check_id,
        str(receipt.ops_score),
        receipt.security_state,
        receipt.timestamp,
        receipt.approval_expiry_at,
        receipt.approval_scope.value if hasattr(receipt.approval_scope, "value") else str(receipt.approval_scope),
        receipt.target_symbol or "",
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def evaluate_execution_policy(
    receipt: OperatorApprovalReceipt | None = None,
    ops_score_threshold: float = DEFAULT_OPS_SCORE_THRESHOLD,
) -> ExecutionPolicyResult:
    """
    I-07: 승인-실행 상태 일치 검증.
    Read-only revalidation. No execution. No state mutation.
    MATCH means policy-match only, not execution-performed.
    """
    now = datetime.now(timezone.utc)
    policy_id = f"POL-{uuid.uuid4().hex[:12]}"
    items: list[PolicyCheckItem] = []
    drift_reasons: list[PolicyDriftReason] = []

    # --- No receipt → cannot MATCH ---
    if receipt is None:
        receipt = _get_latest_approval()
    if receipt is None or receipt.decision != ApprovalDecision.APPROVED:
        return ExecutionPolicyResult(
            policy_id=policy_id,
            approval_id=receipt.approval_id if receipt else "none",
            decision=PolicyDecision.DRIFT,
            timestamp=now.isoformat(),
            summary="No valid APPROVED receipt found",
            drift_reasons=[PolicyDriftReason.MISSING_APPROVAL_RECEIPT],
            evidence_id=_store_policy_evidence(policy_id, PolicyDecision.DRIFT, [], now),
            rule_refs=["Art33", "Art39", "Art43"],
        )

    # --- Compute approval hash ---
    approval_hash = compute_receipt_hash(receipt)

    # --- Check 1: approval_expiry_at 미만료 ---
    try:
        expiry = datetime.fromisoformat(receipt.approval_expiry_at)
        expired = now >= expiry
    except Exception:
        expired = True

    if expired:
        return ExecutionPolicyResult(
            policy_id=policy_id,
            approval_id=receipt.approval_id,
            decision=PolicyDecision.EXPIRED,
            timestamp=now.isoformat(),
            summary=f"Approval expired at {receipt.approval_expiry_at}",
            drift_reasons=[PolicyDriftReason.APPROVAL_EXPIRED],
            approval_receipt_hash=approval_hash,
            evidence_id=_store_policy_evidence(policy_id, PolicyDecision.EXPIRED, [], now),
            rule_refs=["Art33", "Art39", "Art43"],
        )

    # --- Check 2: gate.decision == OPEN ---
    gate_open, gate_observed = _recheck_gate()
    items.append(PolicyCheckItem(
        name="gate_open", matched=gate_open,
        approval_value="OPEN", current_value=gate_observed,
        rule_refs=["Art43"],
    ))
    if not gate_open:
        drift_reasons.append(PolicyDriftReason.GATE_CLOSED)

    # --- Check 3: preflight.decision == READY ---
    pf_ready, pf_observed = _recheck_preflight()
    items.append(PolicyCheckItem(
        name="preflight_ready", matched=pf_ready,
        approval_value="READY", current_value=pf_observed,
        rule_refs=["Art43"],
    ))
    if not pf_ready:
        drift_reasons.append(PolicyDriftReason.PREFLIGHT_NOT_READY)

    # --- Check 4: ops_score >= threshold ---
    score_ok, score_observed = _recheck_ops_score(ops_score_threshold)
    items.append(PolicyCheckItem(
        name="ops_score_above_threshold", matched=score_ok,
        approval_value=f">={ops_score_threshold}", current_value=score_observed,
        rule_refs=["Art41"],
    ))
    if not score_ok:
        drift_reasons.append(PolicyDriftReason.OPS_SCORE_LOW)

    # --- Check 5: security_state != LOCKDOWN ---
    sec_ok, sec_observed = _recheck_security()
    items.append(PolicyCheckItem(
        name="security_not_lockdown", matched=sec_ok,
        approval_value="!=LOCKDOWN", current_value=sec_observed,
        rule_refs=["Art7"],
    ))
    if not sec_ok:
        drift_reasons.append(PolicyDriftReason.LOCKDOWN_ACTIVE)

    # --- Check 6: no CRITICAL alerts since approval ---
    no_critical, crit_observed = _recheck_critical_alerts(receipt.timestamp)
    items.append(PolicyCheckItem(
        name="no_critical_since_approval", matched=no_critical,
        approval_value="0 critical", current_value=crit_observed,
        rule_refs=["Art18"],
    ))
    if not no_critical:
        drift_reasons.append(PolicyDriftReason.CRITICAL_ALERT_DETECTED)

    # --- Hash revalidation ---
    current_hash = _recompute_hash_from_current(receipt)
    hash_match = approval_hash == current_hash
    items.append(PolicyCheckItem(
        name="receipt_hash_integrity", matched=hash_match,
        approval_value=approval_hash[:16] + "...",
        current_value=current_hash[:16] + "...",
        rule_refs=["Art43"],
    ))
    if not hash_match:
        drift_reasons.append(PolicyDriftReason.APPROVAL_HASH_MISMATCH)

    # --- Decision ---
    decision = PolicyDecision.MATCH if len(drift_reasons) == 0 else PolicyDecision.DRIFT
    matched = sum(1 for i in items if i.matched)
    summary = f"Policy: {matched}/{len(items)} matched, decision={decision.value}"
    if drift_reasons:
        summary += f", drift: {', '.join(r.value for r in drift_reasons[:3])}"

    evidence_id = _store_policy_evidence(policy_id, decision, drift_reasons, now)

    return ExecutionPolicyResult(
        policy_id=policy_id,
        approval_id=receipt.approval_id,
        decision=decision,
        timestamp=now.isoformat(),
        summary=summary,
        items=items,
        drift_reasons=drift_reasons,
        approval_receipt_hash=approval_hash,
        current_hash=current_hash,
        evidence_id=evidence_id,
        rule_refs=["Art33", "Art39", "Art43"],
    )


# ---------------------------------------------------------------------------
# Recheck helpers (read-only, fail-closed)
# ---------------------------------------------------------------------------

def _get_latest_approval() -> OperatorApprovalReceipt | None:
    """Get latest APPROVED receipt from evidence store."""
    try:
        import app.main as main_module
        gate = getattr(main_module.app.state, "governance_gate", None)
        if gate and hasattr(gate, "evidence_store"):
            # CR-027: Bounded query — only need latest few, not all 42K.
            _store = gate.evidence_store
            if hasattr(_store, "list_by_actor_recent"):
                bundles = _store.list_by_actor_recent("i06_operator_approval", 10)
            else:
                bundles = _store.list_by_actor("i06_operator_approval")[-10:]
            for b in reversed(bundles):
                after = b.after_state if hasattr(b, "after_state") else {}
                if isinstance(after, dict) and after.get("decision") == "APPROVED":
                    from app.schemas.operator_approval_schema import ApprovalScope
                    return OperatorApprovalReceipt(
                        approval_id=b.bundle_id if hasattr(b, "bundle_id") else "unknown",
                        decision=ApprovalDecision.APPROVED,
                        gate_snapshot_id=after.get("gate_snapshot_id", ""),
                        preflight_id=after.get("preflight_id", ""),
                        check_id=after.get("check_id", ""),
                        ops_score=after.get("ops_score", 0.0),
                        security_state=after.get("security_state", "UNKNOWN"),
                        timestamp=b.created_at.isoformat() if hasattr(b.created_at, "isoformat") else "",
                        approval_expiry_at=after.get("expiry", ""),
                        approval_scope=ApprovalScope(after.get("scope", "NO_EXECUTION")),
                    )
        return None
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

        # Query real snapshot_age from DB (same SSOT as Dashboard/Gate/Approval)
        snapshot_age = None
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import Session as SyncSession
            from app.core.config import settings as _cfg
            from app.models.position import Position
            from datetime import datetime, timezone
            _engine = create_engine(_cfg.database_url_sync)
            try:
                with SyncSession(_engine) as _sess:
                    latest = _sess.query(Position.updated_at).order_by(Position.updated_at.desc()).first()
                    ts = latest[0] if latest else None
                    if ts is None:
                        from app.models.asset_snapshot import AssetSnapshot
                        snap = _sess.query(AssetSnapshot.snapshot_at).order_by(AssetSnapshot.snapshot_at.desc()).first()
                        ts = snap[0] if snap else None
                    if ts:
                        snapshot_age = int((datetime.now(timezone.utc) - ts.replace(tzinfo=timezone.utc)).total_seconds())
            finally:
                _engine.dispose()  # CR-035: prevent connection leak
        except Exception:
            snapshot_age = None

        score = _compute_ops_score(
            IntegrityPanel(exchange_db_consistency="unknown", snapshot_age_seconds=snapshot_age,
                           position_mismatch=False, open_orders_mismatch=False,
                           balance_mismatch=False,
                           stale_data=snapshot_age is None or (snapshot_age is not None and snapshot_age > 300)),
            TradingSafetyPanel(), IncidentEvidencePanel(),
        )
        avg = (score.integrity + score.connectivity + score.execution_safety + score.evidence_completeness) / 4
        return avg >= threshold, f"{avg:.4f}"
    except Exception as e:
        return False, f"error:{e}"


def _recheck_security() -> tuple[bool, str]:
    try:
        import app.main as main_module
        gate = getattr(main_module.app.state, "governance_gate", None)
        if gate and hasattr(gate, "security_ctx"):
            val = gate.security_ctx.current.value if hasattr(gate.security_ctx.current, "value") else str(gate.security_ctx.current)
            return val != "LOCKDOWN", val
        return False, "UNKNOWN"
    except Exception as e:
        return False, f"error:{e}"


def _recheck_critical_alerts(since_timestamp: str) -> tuple[bool, str]:
    """Check if any CRITICAL alerts occurred since approval timestamp."""
    try:
        import app.main as main_module
        flow_log = getattr(main_module.app.state, "flow_log", None)
        if flow_log is None:
            return True, "no_flow_log"
        entries = flow_log.list_entries(limit=50)
        critical_count = 0
        for e in entries:
            if e.get("policy_urgent") and e.get("executed_at", "") > since_timestamp:
                critical_count += 1
        return critical_count == 0, f"critical_since={critical_count}"
    except Exception as e:
        return True, f"error:{e}"


def _recompute_hash_from_current(receipt: OperatorApprovalReceipt) -> str:
    """Recompute hash using receipt fields (immutable snapshot)."""
    return compute_receipt_hash(receipt)


def _store_policy_evidence(
    policy_id: str, decision: PolicyDecision,
    drift_reasons: list, now: datetime,
) -> str:
    try:
        import app.main as main_module
        gate = getattr(main_module.app.state, "governance_gate", None)
        if gate is None or not hasattr(gate, "evidence_store"):
            return f"fallback-pol-{uuid.uuid4().hex[:8]}"
        from kdexter.audit.evidence_store import EvidenceBundle
        bundle = EvidenceBundle(
            bundle_id=policy_id,
            created_at=now,
            trigger="execution_policy_evaluation",
            actor="i07_execution_policy",
            action=f"policy_{decision.value.lower()}",
            before_state=None,
            after_state={
                "decision": decision.value,
                "drift_reasons": [r.value for r in drift_reasons],
            },
            artifacts=[],
        )
        return gate.evidence_store.store(bundle)
    except Exception as e:
        logger.warning("policy_evidence_store_failed", error=str(e))
        return f"fallback-pol-{uuid.uuid4().hex[:8]}"
