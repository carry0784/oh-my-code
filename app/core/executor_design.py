"""
E-01: Executor Design — 전제 조건 검증 계약 (설계만)

이 파일은 E-01의 **전제 조건 검증만** 수행한다.
거래소 호출, 주문 전송, 자동 실행, unlock/resume 로직은 포함하지 않는다.
E-01 활성화는 별도 승인 전까지 금지다.

역참조: Operating Constitution v1.0 제36조~제38조

Fail-closed 규칙:
  - I-06 APPROVED receipt 없으면 → PRECONDITION_FAILED
  - I-06 만료 → PRECONDITION_FAILED
  - I-07 MATCH 아니면 → PRECONDITION_FAILED
  - scope 불일치 → SCOPE_MISMATCH
  - evidence chain 누락 → PRECONDITION_FAILED
  - executor 미활성화 → EXECUTOR_NOT_ACTIVATED (항상)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.core.logging import get_logger
from app.schemas.executor_schema import (
    EvidenceChainRef,
    ExecutionFailReason,
    ExecutionReceipt,
    ExecutionScope,
    ExecutionState,
    is_scope_compatible,
)

logger = get_logger(__name__)

# E-01은 활성화되지 않았다. 이 플래그는 별도 승인 전까지 False 고정.
_EXECUTOR_ACTIVATED = False


def validate_execution_preconditions(
    execution_scope: ExecutionScope = ExecutionScope.NO_EXECUTION,
    target_symbol: str | None = None,
) -> ExecutionReceipt:
    """
    E-01 전제 조건 검증. 설계 계약만 실행.
    실행 로직 없음. 거래소 호출 없음. 주문 전송 없음.

    Returns:
      ExecutionReceipt with state:
        PRECONDITION_FAILED — 전제 미충족
        SCOPE_MISMATCH — scope 불일치
        READY_TO_EXECUTE — 전제 충족 (활성화 전이므로 EXECUTOR_NOT_ACTIVATED 추가)
    """
    now = datetime.now(timezone.utc)
    execution_id = f"EXE-{uuid.uuid4().hex[:12]}"
    fail_reasons: list[ExecutionFailReason] = []

    # --- Collect I-06 approval ---
    approval = _collect_approval()
    if approval is None:
        fail_reasons.append(ExecutionFailReason.MISSING_APPROVAL)
    elif not approval.get("approved"):
        fail_reasons.append(ExecutionFailReason.APPROVAL_NOT_APPROVED)
    elif approval.get("expired"):
        fail_reasons.append(ExecutionFailReason.APPROVAL_EXPIRED)

    # --- Collect I-07 policy ---
    policy = _collect_policy()
    if policy is None:
        fail_reasons.append(ExecutionFailReason.MISSING_POLICY_MATCH)
    elif policy.get("decision") == "DRIFT":
        fail_reasons.append(ExecutionFailReason.POLICY_DRIFT)
    elif policy.get("decision") == "EXPIRED":
        fail_reasons.append(ExecutionFailReason.POLICY_EXPIRED)
    elif policy.get("decision") != "MATCH":
        fail_reasons.append(ExecutionFailReason.MISSING_POLICY_MATCH)

    # --- Scope compatibility ---
    approval_scope_str = approval.get("scope", "NO_EXECUTION") if approval else "NO_EXECUTION"
    approval_symbol = approval.get("target_symbol") if approval else None
    try:
        from app.schemas.operator_approval_schema import ApprovalScope
        apr_scope = ExecutionScope(approval_scope_str)
    except (ValueError, KeyError):
        apr_scope = ExecutionScope.NO_EXECUTION

    if not is_scope_compatible(execution_scope, apr_scope, target_symbol, approval_symbol):
        fail_reasons.append(ExecutionFailReason.SCOPE_MISMATCH)

    # --- Evidence chain ---
    chain = _build_evidence_chain(approval, policy)
    if not chain:
        fail_reasons.append(ExecutionFailReason.EVIDENCE_CHAIN_BROKEN)

    # --- Executor activated check (항상 False) ---
    if not _EXECUTOR_ACTIVATED:
        fail_reasons.append(ExecutionFailReason.EXECUTOR_NOT_ACTIVATED)

    # --- Determine state ---
    if ExecutionFailReason.SCOPE_MISMATCH in fail_reasons:
        state = ExecutionState.SCOPE_MISMATCH
    elif any(r for r in fail_reasons if r != ExecutionFailReason.EXECUTOR_NOT_ACTIVATED):
        state = ExecutionState.PRECONDITION_FAILED
    else:
        state = ExecutionState.READY_TO_EXECUTE  # but NOT_ACTIVATED will be added by validator

    summary_parts = [f"E-01 precondition check: state={state.value}"]
    if fail_reasons:
        summary_parts.append(f"fail_reasons: {', '.join(r.value for r in fail_reasons[:3])}")
    summary = ", ".join(summary_parts)

    evidence_id = _store_execution_evidence(execution_id, state, fail_reasons, now)

    return ExecutionReceipt(
        execution_id=execution_id,
        state=state,
        execution_scope=execution_scope,
        target_symbol=target_symbol,
        evidence_chain=chain or EvidenceChainRef(
            check_id="missing", preflight_id="missing",
            gate_snapshot_id="missing", approval_id="missing",
            approval_receipt_hash="missing", policy_snapshot_id="missing",
            policy_decision="missing",
        ),
        fail_reasons=fail_reasons,
        timestamp=now.isoformat(),
        summary=summary,
        evidence_id=evidence_id,
        rule_refs=["Art36", "Art37", "Art38"],
        executor_activated=_EXECUTOR_ACTIVATED,
    )


# ---------------------------------------------------------------------------
# Collectors (read-only)
# ---------------------------------------------------------------------------

def _collect_approval() -> dict | None:
    try:
        from app.core.operator_approval import issue_approval
        from app.schemas.operator_approval_schema import ApprovalScope, ApprovalDecision
        # Read latest — don't issue new one, just check state
        from app.core.execution_policy import _get_latest_approval
        receipt = _get_latest_approval()
        if receipt is None:
            return None
        from app.core.operator_approval import validate_approval_current
        return {
            "approved": receipt.decision == ApprovalDecision.APPROVED,
            "expired": not validate_approval_current(receipt),
            "scope": receipt.approval_scope.value if hasattr(receipt.approval_scope, "value") else str(receipt.approval_scope),
            "target_symbol": receipt.target_symbol,
            "approval_id": receipt.approval_id,
            "receipt_hash": "",
        }
    except Exception:
        return None


def _collect_policy() -> dict | None:
    try:
        from app.core.execution_policy import evaluate_execution_policy
        result = evaluate_execution_policy()
        return {
            "decision": result.decision.value,
            "policy_id": result.policy_id,
            "approval_receipt_hash": result.approval_receipt_hash,
        }
    except Exception:
        return None


def _build_evidence_chain(
    approval: dict | None, policy: dict | None,
) -> EvidenceChainRef | None:
    try:
        return EvidenceChainRef(
            check_id=approval.get("check_id", "derived") if approval else "missing",
            preflight_id=approval.get("preflight_id", "derived") if approval else "missing",
            gate_snapshot_id=approval.get("gate_snapshot_id", "derived") if approval else "missing",
            approval_id=approval.get("approval_id", "missing") if approval else "missing",
            approval_receipt_hash=policy.get("approval_receipt_hash", "") if policy else "missing",
            policy_snapshot_id=policy.get("policy_id", "missing") if policy else "missing",
            policy_decision=policy.get("decision", "missing") if policy else "missing",
        )
    except Exception:
        return None


def _store_execution_evidence(
    execution_id: str, state: ExecutionState,
    fail_reasons: list, now: datetime,
) -> str:
    try:
        import app.main as main_module
        gate = getattr(main_module.app.state, "governance_gate", None)
        if gate is None or not hasattr(gate, "evidence_store"):
            return f"fallback-exe-{uuid.uuid4().hex[:8]}"
        from kdexter.audit.evidence_store import EvidenceBundle
        bundle = EvidenceBundle(
            bundle_id=execution_id,
            created_at=now,
            trigger="executor_precondition_check",
            actor="e01_executor_design",
            action=f"precondition_{state.value.lower()}",
            before_state=None,
            after_state={
                "state": state.value,
                "fail_reasons": [r.value for r in fail_reasons],
                "executor_activated": _EXECUTOR_ACTIVATED,
            },
            artifacts=[],
        )
        return gate.evidence_store.store(bundle)
    except Exception as e:
        logger.warning("executor_evidence_store_failed", error=str(e))
        return f"fallback-exe-{uuid.uuid4().hex[:8]}"
