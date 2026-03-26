"""
I-06: Operator Approval Runner — 승인 영수증 발행

I-06은 승인 영수증 계층이지 실행 계층이 아니다.
APPROVED means operator-approved receipt only, not execution-authorized.
No Evidence, No Power — 7필드 하나라도 누락 시 승인 불가.

역참조: Operating Constitution v1.0 제43조, 제45조

금지: 거래 실행, 거래 재개, 승격, 자본 확대, state mutation
I-07/E-01 선반영 금지.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.core.logging import get_logger
from app.schemas.operator_approval_schema import (
    ApprovalDecision,
    ApprovalRejectionReason,
    ApprovalScope,
    OperatorApprovalReceipt,
)

logger = get_logger(__name__)

DEFAULT_EXPIRY_MINUTES = 15
DEFAULT_OPS_SCORE_THRESHOLD = 0.7


def issue_approval(
    approved_by: str = "operator",
    approval_reason: str = "",
    approval_scope: ApprovalScope = ApprovalScope.NO_EXECUTION,
    target_symbol: str | None = None,
    expiry_minutes: int = DEFAULT_EXPIRY_MINUTES,
    ops_score_threshold: float = DEFAULT_OPS_SCORE_THRESHOLD,
) -> OperatorApprovalReceipt:
    """
    Operator Approval Receipt 발행.
    7필드 검증 → APPROVED 또는 REJECTED receipt 생성.
    append-only evidence 기록. 실행 함수 호출 금지.
    """
    now = datetime.now(timezone.utc)
    expiry = now + timedelta(minutes=expiry_minutes)
    approval_id = f"APR-{uuid.uuid4().hex[:12]}"
    rejection_reasons: list[ApprovalRejectionReason] = []

    # --- Collect 7 fields ---
    gate_id, gate_ok = _collect_gate()
    preflight_id, preflight_ok = _collect_preflight()
    check_id, check_ok = _collect_check()
    ops_score_val, score_ok = _collect_ops_score(ops_score_threshold)
    sec_state, sec_ok = _collect_security_state()

    # --- Validate each field ---
    if not gate_id:
        rejection_reasons.append(ApprovalRejectionReason.MISSING_GATE)
    elif not gate_ok:
        rejection_reasons.append(ApprovalRejectionReason.GATE_NOT_OPEN)

    if not preflight_id:
        rejection_reasons.append(ApprovalRejectionReason.MISSING_PREFLIGHT)
    elif not preflight_ok:
        rejection_reasons.append(ApprovalRejectionReason.PREFLIGHT_NOT_READY)

    if not check_id:
        rejection_reasons.append(ApprovalRejectionReason.MISSING_CHECK)
    elif not check_ok:
        rejection_reasons.append(ApprovalRejectionReason.CHECK_BLOCKED)

    if not score_ok:
        rejection_reasons.append(ApprovalRejectionReason.OPS_SCORE_LOW)

    if not sec_ok:
        rejection_reasons.append(ApprovalRejectionReason.LOCKDOWN_ACTIVE)

    # --- Scope validation ---
    if approval_scope == ApprovalScope.SPECIFIC_SYMBOL_ONLY and not target_symbol:
        rejection_reasons.append(ApprovalRejectionReason.MISSING_TARGET_SYMBOL)

    # --- Decision ---
    decision = (
        ApprovalDecision.APPROVED
        if len(rejection_reasons) == 0
        else ApprovalDecision.REJECTED
    )

    receipt = OperatorApprovalReceipt(
        approval_id=approval_id,
        decision=decision,
        gate_snapshot_id=gate_id or "missing",
        preflight_id=preflight_id or "missing",
        check_id=check_id or "missing",
        ops_score=ops_score_val,
        security_state=sec_state,
        timestamp=now.isoformat(),
        approval_expiry_at=expiry.isoformat(),
        approval_scope=approval_scope,
        approved_by=approved_by,
        approval_reason=approval_reason,
        rule_refs=["Art43", "Art45"],
        rejection_reasons=rejection_reasons,
        target_symbol=target_symbol,
    )

    # Store evidence (append-only)
    _store_approval_evidence(receipt)

    logger.info(
        "operator_approval_issued",
        approval_id=approval_id,
        decision=decision.value,
        rejection_count=len(rejection_reasons),
        scope=approval_scope.value,
    )

    return receipt


def validate_approval_current(receipt: OperatorApprovalReceipt) -> bool:
    """
    승인 영수증이 현재 유효한지 확인.
    만료 여부만 확인. 상태 일치 검증은 I-07 범위.
    """
    if receipt.decision != ApprovalDecision.APPROVED:
        return False
    try:
        expiry = datetime.fromisoformat(receipt.approval_expiry_at)
        now = datetime.now(timezone.utc)
        return now < expiry
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Field collectors (read-only, fail-closed)
# ---------------------------------------------------------------------------

def _collect_gate() -> tuple[str, bool]:
    """Collect gate snapshot from I-05."""
    try:
        from app.core.execution_gate import evaluate_execution_gate
        result = evaluate_execution_gate()
        return result.evidence_id, result.decision.value == "OPEN"
    except Exception:
        return "", False


def _collect_preflight() -> tuple[str, bool]:
    """Collect preflight from I-04."""
    try:
        from app.core.recovery_preflight import run_recovery_preflight
        result = run_recovery_preflight()
        return result.evidence_id, result.decision.value == "READY"
    except Exception:
        return "", False


def _collect_check() -> tuple[str, bool]:
    """Collect latest check from I-03."""
    try:
        from app.core.constitution_check_runner import run_daily_check
        result = run_daily_check()
        return result.evidence_id, result.result.value != "BLOCK"
    except Exception:
        return "", False


def _collect_ops_score(threshold: float) -> tuple[float, bool]:
    """Collect ops score from I-01 with real DB-backed snapshot freshness."""
    try:
        from app.api.routes.dashboard import _compute_ops_score
        from app.schemas.ops_status import IntegrityPanel, TradingSafetyPanel, IncidentEvidencePanel

        # Query real snapshot_age from DB (same SSOT as Gate)
        snapshot_age = None
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import Session as SyncSession
            from app.core.config import settings as _cfg
            from app.models.position import Position
            from datetime import datetime, timezone
            _engine = create_engine(_cfg.database_url_sync)
            with SyncSession(_engine) as _sess:
                latest = _sess.query(Position.updated_at).order_by(Position.updated_at.desc()).first()
                ts = latest[0] if latest else None
                if ts is None:
                    from app.models.asset_snapshot import AssetSnapshot
                    snap = _sess.query(AssetSnapshot.snapshot_at).order_by(AssetSnapshot.snapshot_at.desc()).first()
                    ts = snap[0] if snap else None
                if ts:
                    snapshot_age = int((datetime.now(timezone.utc) - ts.replace(tzinfo=timezone.utc)).total_seconds())
        except Exception:
            snapshot_age = None

        integrity = IntegrityPanel(
            exchange_db_consistency="unknown",
            snapshot_age_seconds=snapshot_age,
            position_mismatch=False,
            open_orders_mismatch=False,
            balance_mismatch=False,
            stale_data=snapshot_age is None or (snapshot_age is not None and snapshot_age > 300),
        )
        score = _compute_ops_score(integrity, TradingSafetyPanel(), IncidentEvidencePanel())
        avg = (score.integrity + score.connectivity + score.execution_safety + score.evidence_completeness) / 4
        return round(avg, 4), avg >= threshold
    except Exception:
        return 0.0, False


def _collect_security_state() -> tuple[str, bool]:
    """Collect security state from I-01."""
    try:
        import app.main as main_module
        gate = getattr(main_module.app.state, "governance_gate", None)
        if gate and hasattr(gate, "security_ctx"):
            ctx = gate.security_ctx
            val = ctx.current.value if hasattr(ctx.current, "value") else str(ctx.current)
            return val, val != "LOCKDOWN"
        return "UNKNOWN", False
    except Exception:
        return "ERROR", False


def _store_approval_evidence(receipt: OperatorApprovalReceipt) -> None:
    """Store approval receipt to evidence store. Append-only."""
    try:
        import app.main as main_module
        gate = getattr(main_module.app.state, "governance_gate", None)
        if gate is None or not hasattr(gate, "evidence_store"):
            return

        from kdexter.audit.evidence_store import EvidenceBundle
        bundle = EvidenceBundle(
            bundle_id=receipt.approval_id,
            created_at=datetime.now(timezone.utc),
            trigger="operator_approval",
            actor="i06_operator_approval",
            action=f"approval_{receipt.decision.value.lower()}",
            before_state=None,
            after_state={
                "decision": receipt.decision.value,
                "scope": receipt.approval_scope.value,
                "gate_snapshot_id": receipt.gate_snapshot_id,
                "preflight_id": receipt.preflight_id,
                "check_id": receipt.check_id,
                "ops_score": receipt.ops_score,
                "security_state": receipt.security_state,
                "expiry": receipt.approval_expiry_at,
                "rejection_reasons": [r.value for r in receipt.rejection_reasons],
            },
            artifacts=[],
        )
        gate.evidence_store.store(bundle)
    except Exception as e:
        logger.warning("approval_evidence_store_failed", error=str(e))
