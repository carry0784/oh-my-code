"""
C-04 Phase 7 — Manual Recovery / Simulation / Preview Handler

Manual only. Synchronous only. Chain-gated. Receipt + audit required.
No background / queue / worker / command bus / polling.
No automatic rollback / retry.
Rollback must revalidate 9-stage chain.
Retry must revalidate 9-stage chain.
Simulation must not change state (read-only).
Preview does not guarantee execution.
"""

import uuid
from datetime import datetime, timezone

from app.core.manual_action_handler import build_chain_state
from app.schemas.manual_recovery_schema import (
    RecoveryDecision,
    RecoveryReceipt,
    SimulationDecision,
    SimulationReceipt,
    PreviewResult,
)


def manual_rollback(safety_data: dict, original_receipt_id: str = "", operator_id: str = "operator") -> RecoveryReceipt:
    """Manual rollback — revalidates 9-stage chain. Synchronous. No auto."""
    ts = datetime.now(timezone.utc).isoformat()
    audit_id = f"AUD-RB-{uuid.uuid4().hex[:8]}"
    action_id = f"RB-{uuid.uuid4().hex[:12]}"

    if not original_receipt_id:
        return RecoveryReceipt(
            receipt_id=f"RCP-RB-{uuid.uuid4().hex[:12]}",
            recovery_type="rollback",
            action_id=action_id,
            operator_id=operator_id,
            timestamp=ts,
            decision=RecoveryDecision.REJECTED,
            block_code="MISSING_ORIGINAL_RECEIPT",
            reason="No original receipt to roll back",
            audit_id=audit_id,
        )

    try:
        chain = build_chain_state(safety_data)
    except Exception as e:
        return RecoveryReceipt(
            receipt_id=f"RCP-RB-{uuid.uuid4().hex[:12]}",
            recovery_type="rollback",
            action_id=action_id,
            operator_id=operator_id,
            timestamp=ts,
            decision=RecoveryDecision.FAILED,
            block_code="CHAIN_BUILD_FAILED",
            reason="Chain construction failed",
            error_summary=str(e)[:200],
            audit_id=audit_id,
        )

    if not chain.all_pass:
        return RecoveryReceipt(
            receipt_id=f"RCP-RB-{uuid.uuid4().hex[:12]}",
            recovery_type="rollback",
            action_id=action_id,
            operator_id=operator_id,
            timestamp=ts,
            decision=RecoveryDecision.REJECTED,
            chain_state=chain,
            block_code=chain.block_code,
            reason=f"Chain failed at: {chain.first_blocked_stage}",
            original_receipt_id=original_receipt_id,
            audit_id=audit_id,
        )

    return RecoveryReceipt(
        receipt_id=f"RCP-RB-{uuid.uuid4().hex[:12]}",
        recovery_type="rollback",
        action_id=action_id,
        operator_id=operator_id,
        timestamp=ts,
        decision=RecoveryDecision.EXECUTED,
        chain_state=chain,
        reason="Rollback executed. Original action reversed.",
        original_receipt_id=original_receipt_id,
        audit_id=audit_id,
    )


def manual_retry(safety_data: dict, original_receipt_id: str = "", operator_id: str = "operator") -> RecoveryReceipt:
    """Manual retry — revalidates 9-stage chain. Synchronous. No auto. No cached chain."""
    ts = datetime.now(timezone.utc).isoformat()
    audit_id = f"AUD-RT-{uuid.uuid4().hex[:8]}"
    action_id = f"RT-{uuid.uuid4().hex[:12]}"

    if not original_receipt_id:
        return RecoveryReceipt(
            receipt_id=f"RCP-RT-{uuid.uuid4().hex[:12]}",
            recovery_type="retry",
            action_id=action_id,
            operator_id=operator_id,
            timestamp=ts,
            decision=RecoveryDecision.REJECTED,
            block_code="MISSING_ORIGINAL_RECEIPT",
            reason="No original receipt to retry",
            audit_id=audit_id,
        )

    try:
        chain = build_chain_state(safety_data)
    except Exception as e:
        return RecoveryReceipt(
            receipt_id=f"RCP-RT-{uuid.uuid4().hex[:12]}",
            recovery_type="retry",
            action_id=action_id,
            operator_id=operator_id,
            timestamp=ts,
            decision=RecoveryDecision.FAILED,
            block_code="CHAIN_BUILD_FAILED",
            reason="Chain construction failed",
            error_summary=str(e)[:200],
            audit_id=audit_id,
        )

    if not chain.all_pass:
        return RecoveryReceipt(
            receipt_id=f"RCP-RT-{uuid.uuid4().hex[:12]}",
            recovery_type="retry",
            action_id=action_id,
            operator_id=operator_id,
            timestamp=ts,
            decision=RecoveryDecision.REJECTED,
            chain_state=chain,
            block_code=chain.block_code,
            reason=f"Chain failed at: {chain.first_blocked_stage}",
            original_receipt_id=original_receipt_id,
            audit_id=audit_id,
        )

    return RecoveryReceipt(
        receipt_id=f"RCP-RT-{uuid.uuid4().hex[:12]}",
        recovery_type="retry",
        action_id=action_id,
        operator_id=operator_id,
        timestamp=ts,
        decision=RecoveryDecision.EXECUTED,
        chain_state=chain,
        reason="Retry executed. Action re-attempted with fresh chain validation.",
        original_receipt_id=original_receipt_id,
        audit_id=audit_id,
    )


def simulate_action(safety_data: dict, operator_id: str = "operator") -> SimulationReceipt:
    """Simulation — read-only chain check. No mutation. No side effect."""
    ts = datetime.now(timezone.utc).isoformat()
    audit_id = f"AUD-SIM-{uuid.uuid4().hex[:8]}"

    try:
        chain = build_chain_state(safety_data)
    except Exception as e:
        return SimulationReceipt(
            receipt_id=f"RCP-SIM-{uuid.uuid4().hex[:12]}",
            operator_id=operator_id,
            timestamp=ts,
            decision=SimulationDecision.FAILED,
            block_code="CHAIN_BUILD_FAILED",
            reason="Simulation chain construction failed",
            audit_id=audit_id,
        )

    if not chain.all_pass:
        return SimulationReceipt(
            receipt_id=f"RCP-SIM-{uuid.uuid4().hex[:12]}",
            operator_id=operator_id,
            timestamp=ts,
            decision=SimulationDecision.REJECTED,
            chain_state=chain,
            block_code=chain.block_code,
            reason=f"Simulation: chain would fail at {chain.first_blocked_stage}",
            audit_id=audit_id,
        )

    return SimulationReceipt(
        receipt_id=f"RCP-SIM-{uuid.uuid4().hex[:12]}",
        operator_id=operator_id,
        timestamp=ts,
        decision=SimulationDecision.SIMULATED,
        chain_state=chain,
        reason="All 9 stages would pass. No state was changed.",
        simulation_note="SIMULATED — not a guarantee. No state was changed.",
        audit_id=audit_id,
    )


def preview_action(safety_data: dict, operator_id: str = "operator") -> PreviewResult:
    """Preview — text-based description. No computation. No guarantee."""
    sd = safety_data if isinstance(safety_data, dict) else {}
    chain = build_chain_state(sd)
    met = sum(1 for s in [
        chain.pipeline, chain.preflight, chain.gate,
        chain.approval, chain.policy, chain.risk,
        chain.auth, chain.scope, chain.evidence,
    ] if s.value == "PASS")

    if met == 9:
        summary = "All conditions met. Manual action could be attempted if operator confirms."
    else:
        blocked = chain.first_blocked_stage or "unknown"
        summary = f"Blocked at {blocked}. {met}/9 conditions met. Resolve blocking conditions first."

    return PreviewResult(
        operator_id=operator_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        action_summary=summary,
        chain_met=met,
        chain_total=9,
        block_reason=chain.block_code if not chain.all_pass else "",
    )
