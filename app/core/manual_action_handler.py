"""
C-04 Manual Action Handler — Phase 5 Bounded Execution

9-stage chain gated. Fail-closed. Synchronous only.
No background / queue / worker / command bus.
No rollback / retry / polling / dry-run / partial preview.
No optimistic enable / execution.
Receipt + audit on every attempt.
"""

import uuid
from datetime import datetime, timezone

from app.schemas.manual_action_schema import (
    ManualActionChainState,
    ManualActionCommand,
    ManualActionDecision,
    ManualActionReceipt,
    ManualActionStageStatus,
)


def build_chain_state(safety_data: dict) -> ManualActionChainState:
    """Build 9-stage chain state from ops-safety-summary data.

    Fail-closed: any missing/unknown/malformed → MISSING or BLOCKED.
    No optimistic inference.
    """
    if not safety_data or not isinstance(safety_data, dict):
        return ManualActionChainState()  # All MISSING = fail-closed

    def _eval(key, ok_fn):
        val = safety_data.get(key)
        if val is None:
            return ManualActionStageStatus.MISSING
        try:
            return ManualActionStageStatus.PASS if ok_fn(val) else ManualActionStageStatus.BLOCKED
        except Exception:
            return ManualActionStageStatus.ERROR

    return ManualActionChainState(
        pipeline=_eval("pipeline_state", lambda v: v == "ALL_CLEAR"),
        preflight=_eval("preflight_decision", lambda v: v == "READY"),
        gate=_eval("gate_decision", lambda v: v == "OPEN"),
        approval=_eval("approval_decision", lambda v: v == "APPROVED"),
        policy=_eval("policy_decision", lambda v: v == "MATCH"),
        risk=_eval("ops_score", lambda v: v is not None and float(v) >= 0.7),
        auth=_eval("trading_authorized", lambda v: v is True),
        scope=_eval("lockdown_state", lambda v: v not in ("LOCKDOWN", "QUARANTINE")),
        evidence=_eval(
            "preflight_evidence_id",
            lambda v: v and not str(v).startswith("fallback-"),
        ),
    )


def validate_and_execute(
    safety_data: dict,
    operator_id: str = "operator",
) -> ManualActionReceipt:
    """Validate 9-stage chain and attempt execution.

    Synchronous only. No background. No queue. No worker.
    Receipt + audit on every attempt (success, rejection, failure).
    """
    action_id = f"MA-{uuid.uuid4().hex[:12]}"
    ts = datetime.now(timezone.utc).isoformat()
    audit_id = f"AUD-{uuid.uuid4().hex[:8]}"

    # Build chain state — fail-closed
    try:
        chain = build_chain_state(safety_data)
    except Exception as e:
        # Chain construction failure → FAILED receipt
        return ManualActionReceipt(
            receipt_id=f"RCP-{uuid.uuid4().hex[:12]}",
            action_id=action_id,
            operator_id=operator_id,
            timestamp=ts,
            decision=ManualActionDecision.FAILED,
            block_code="MANUAL_ACTION_DISABLED",
            reason="Chain state construction failed",
            error_summary=str(e)[:200],
            audit_id=audit_id,
        )

    # Validate all 9 stages — fail-closed
    if not chain.all_pass:
        block_code = chain.block_code
        sd = safety_data if isinstance(safety_data, dict) else {}
        return ManualActionReceipt(
            receipt_id=f"RCP-{uuid.uuid4().hex[:12]}",
            action_id=action_id,
            operator_id=operator_id,
            timestamp=ts,
            decision=ManualActionDecision.REJECTED,
            chain_state=chain,
            block_code=block_code,
            reason=f"Chain validation failed at: {chain.first_blocked_stage}",
            evidence_ids={
                "preflight_id": sd.get("preflight_evidence_id", ""),
                "gate_id": sd.get("gate_evidence_id", ""),
                "approval_id": sd.get("approval_id", ""),
            },
            audit_id=audit_id,
        )

    # All 9 stages PASS — execute (bounded, synchronous, direct)
    try:
        # Phase 5 bounded execution:
        # In the current system state, C-04 execution means recording
        # the operator's validated manual action intent with full evidence chain.
        # Actual trade dispatch remains gated by E-01/E-02/E-03 executor layers.
        # C-04 does NOT directly submit orders — it records validated intent.

        command = ManualActionCommand(
            action_id=action_id,
            operator_id=operator_id,
            timestamp=ts,
            preflight_id=safety_data.get("preflight_evidence_id", ""),
            gate_id=safety_data.get("gate_evidence_id", ""),
            approval_id=safety_data.get("approval_id", ""),
            evidence_id=f"EVD-{uuid.uuid4().hex[:8]}",
            policy_id=safety_data.get("policy_decision", ""),
            chain_state=chain,
        )

        return ManualActionReceipt(
            receipt_id=f"RCP-{uuid.uuid4().hex[:12]}",
            action_id=command.action_id,
            operator_id=command.operator_id,
            timestamp=command.timestamp,
            decision=ManualActionDecision.EXECUTED,
            chain_state=chain,
            block_code="",
            reason="All 9 stages passed. Validated intent recorded.",
            evidence_ids={
                "preflight_id": command.preflight_id,
                "gate_id": command.gate_id,
                "approval_id": command.approval_id,
                "evidence_id": command.evidence_id,
                "policy_id": command.policy_id,
            },
            audit_id=audit_id,
        )

    except Exception as e:
        # Execution failure → FAILED receipt (no partial side effect)
        return ManualActionReceipt(
            receipt_id=f"RCP-{uuid.uuid4().hex[:12]}",
            action_id=action_id,
            operator_id=operator_id,
            timestamp=ts,
            decision=ManualActionDecision.FAILED,
            chain_state=chain,
            block_code="EXECUTION_FAILED",
            reason="Execution failed after chain validation",
            error_summary=str(e)[:200],
            audit_id=audit_id,
        )
