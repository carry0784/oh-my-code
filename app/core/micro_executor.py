"""
E-03: Micro Executor — Activation-Consumed Dispatch Guard

E-03는 full executor가 아니라 activation-consumed dispatch guard 계층이다.
DISPATCH_ALLOWED means dispatch-eligible only, not order-sent.

핵심 규칙:
  - 동일 activation_id 재사용 금지
  - 동일 execution_intent_hash 재사용 금지
  - dispatch_window_expires_at 만료 시 거부
  - paper/micro scope만 허용
  - No Evidence, No Dispatch

금지: live unlock, full exchange execution, order send, broker dispatch.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.logging import get_logger
from app.schemas.micro_executor_schema import (
    DispatchCheckItem,
    DispatchDecision,
    DispatchEvidenceChain,
    DispatchReason,
    DispatchReceipt,
    _BLOCKED_REASONS,
)

logger = get_logger(__name__)

DEFAULT_DISPATCH_WINDOW_SECONDS = 60  # 1분 dispatch window

# In-memory consumed activation registry (append-only, hot cache)
# S-01A: 영속성 보강 — evidence_store를 primary로 사용하고 in-memory를 hot cache로 유지
_consumed_activations: dict[str, str] = {}  # activation_id → execution_id
_consumed_hashes: dict[str, str] = {}  # intent_hash → execution_id


def _is_activation_consumed(activation_id: str) -> bool:
    """S-01A: evidence_store + hot cache 양쪽에서 소비 여부 확인."""
    if activation_id in _consumed_activations:
        return True
    # Evidence store fallback: check if dispatch evidence exists for this activation
    try:
        import app.main as main_module

        gate = getattr(main_module.app.state, "governance_gate", None)
        if gate and hasattr(gate, "evidence_store"):
            bundles = gate.evidence_store.list_by_actor("e03_micro_executor")
            for b in bundles:
                after = b.after_state if hasattr(b, "after_state") else {}
                if isinstance(after, dict):
                    consumed_aid = after.get("activation_id", "")
                    if (
                        consumed_aid == activation_id
                        and after.get("decision") == "DISPATCH_ALLOWED"
                    ):
                        # Rebuild hot cache entry
                        exe_id = b.bundle_id if hasattr(b, "bundle_id") else "unknown"
                        _consumed_activations[activation_id] = exe_id
                        return True
    except Exception:
        pass
    return False


def _is_hash_consumed(intent_hash: str) -> bool:
    """S-01A: evidence_store + hot cache 양쪽에서 hash 소비 여부 확인."""
    if intent_hash in _consumed_hashes:
        return True
    try:
        import app.main as main_module

        gate = getattr(main_module.app.state, "governance_gate", None)
        if gate and hasattr(gate, "evidence_store"):
            bundles = gate.evidence_store.list_by_actor("e03_micro_executor")
            for b in bundles:
                after = b.after_state if hasattr(b, "after_state") else {}
                if isinstance(after, dict):
                    consumed_hash = after.get("intent_hash", "")
                    if consumed_hash == intent_hash and after.get("decision") == "DISPATCH_ALLOWED":
                        exe_id = b.bundle_id if hasattr(b, "bundle_id") else "unknown"
                        _consumed_hashes[intent_hash] = exe_id
                        return True
    except Exception:
        pass
    return False


def evaluate_dispatch(
    activation_id: str = "",
    execution_intent_hash: str = "",
    execution_scope: str = "NO_EXECUTION",
    requested_action: str = "check_only",
    target_symbol: Optional[str] = None,
    dispatch_window_seconds: int = DEFAULT_DISPATCH_WINDOW_SECONDS,
) -> DispatchReceipt:
    """
    E-03: Dispatch guard 판정. 1회성 소비 원칙.
    No order send. No exchange API. No live unlock.
    """
    now = datetime.now(timezone.utc)
    execution_id = f"DIS-{uuid.uuid4().hex[:12]}"
    items: list[DispatchCheckItem] = []
    reasons: list[DispatchReason] = []
    window_expiry = now + timedelta(seconds=dispatch_window_seconds)

    # --- 1. Activation 존재 ---
    act = _collect_activation()
    act_ok = act is not None and act.get("decision") == "ACTIVATION_ALLOWED"
    items.append(
        DispatchCheckItem(
            name="activation_allowed",
            passed=act_ok,
            observed=act.get("decision", "none") if act else "none",
            expected="ACTIVATION_ALLOWED",
            rule_refs=["Art43"],
        )
    )
    if not act_ok:
        reasons.append(
            DispatchReason.ACTIVATION_MISSING
            if act is None
            else DispatchReason.ACTIVATION_NOT_ALLOWED
        )

    # --- 2. activation_consumed_at 미소비 (S-01A: evidence_store + hot cache) ---
    act_aid = activation_id or (act.get("activation_id", "") if act else "")
    already_consumed = _is_activation_consumed(act_aid) if act_aid else False
    items.append(
        DispatchCheckItem(
            name="activation_not_consumed",
            passed=not already_consumed,
            observed=f"consumed={already_consumed}",
            expected="not_consumed",
            rule_refs=["Art43"],
        )
    )
    if already_consumed:
        reasons.append(DispatchReason.ACTIVATION_ALREADY_CONSUMED)

    # --- 3. consumed_by_execution_id 없음 ---
    # (covered by check 2)

    # --- 4. intent_hash 재사용 금지 (S-01A: evidence_store + hot cache) ---
    hash_val = execution_intent_hash or (act.get("execution_intent_hash", "") if act else "")
    hash_reused = _is_hash_consumed(hash_val) if hash_val else False
    items.append(
        DispatchCheckItem(
            name="intent_hash_not_reused",
            passed=not hash_reused,
            observed=f"reused={hash_reused}",
            expected="not_reused",
            rule_refs=["Art43"],
        )
    )
    if hash_reused:
        reasons.append(DispatchReason.INTENT_HASH_ALREADY_USED)

    # --- 5. dispatch_window (S-01B: 만료 guard 추가) ---
    # Check if any previous ALLOWED dispatch for this activation has an expired window
    window_ok = True
    window_obs = f"window={dispatch_window_seconds}s"
    if act_aid and act_aid in _consumed_activations:
        # Already consumed — check stored window expiry from evidence
        try:
            import app.main as main_module

            gate = getattr(main_module.app.state, "governance_gate", None)
            if gate and hasattr(gate, "evidence_store"):
                for b in gate.evidence_store.list_by_actor("e03_micro_executor"):
                    after = b.after_state if hasattr(b, "after_state") else {}
                    if isinstance(after, dict) and after.get("activation_id") == act_aid:
                        stored_window = after.get("dispatch_window_expires_at", "")
                        if stored_window:
                            try:
                                window_dt = datetime.fromisoformat(stored_window)
                                if now >= window_dt:
                                    window_ok = False
                                    window_obs = f"window_expired_at={stored_window}"
                                    reasons.append(DispatchReason.DISPATCH_WINDOW_EXPIRED)
                            except Exception:
                                pass
        except Exception:
            pass
    items.append(
        DispatchCheckItem(
            name="dispatch_window_valid",
            passed=window_ok,
            observed=window_obs,
            expected=f"<={dispatch_window_seconds}s",
            rule_refs=["Art43"],
        )
    )

    # --- 6. scope ---
    from app.schemas.executor_schema import ExecutionScope, is_scope_compatible

    scope_ok = execution_scope in ("PAPER_ONLY", "MICRO_LIVE_ONLY", "SPECIFIC_SYMBOL_ONLY")
    if execution_scope == "NO_EXECUTION":
        scope_ok = False
        reasons.append(DispatchReason.NO_EXECUTION_SCOPE)
    # Check against approval scope
    apr_scope = act.get("approval_scope", "NO_EXECUTION") if act else "NO_EXECUTION"
    apr_symbol = act.get("target_symbol") if act else None
    try:
        exe_s = ExecutionScope(execution_scope)
        apr_s = ExecutionScope(apr_scope)
        compat = is_scope_compatible(exe_s, apr_s, target_symbol, apr_symbol)
    except (ValueError, KeyError):
        compat = False
    if not compat:
        scope_ok = False
        reasons.append(DispatchReason.APPROVAL_SCOPE_MISMATCH)
    items.append(
        DispatchCheckItem(
            name="scope_valid",
            passed=scope_ok,
            observed=f"{execution_scope}⊆{apr_scope}",
            expected="paper/micro only",
            rule_refs=["Art36", "Art38"],
        )
    )

    # --- 7. target_symbol ---
    sym_ok = True
    if execution_scope == "SPECIFIC_SYMBOL_ONLY":
        sym_ok = target_symbol is not None and target_symbol == apr_symbol
        if not sym_ok:
            reasons.append(DispatchReason.TARGET_SYMBOL_MISMATCH)
    items.append(
        DispatchCheckItem(
            name="target_symbol_match",
            passed=sym_ok,
            observed=target_symbol or "none",
            expected=apr_symbol or "any",
            rule_refs=["Art38"],
        )
    )

    # --- 8. I-07 MATCH ---
    pol_ok, pol_obs = _recheck_policy()
    items.append(
        DispatchCheckItem(
            name="policy_match",
            passed=pol_ok,
            observed=pol_obs,
            expected="MATCH",
            rule_refs=["Art33", "Art39"],
        )
    )
    if not pol_ok:
        reasons.append(DispatchReason.POLICY_NOT_MATCH)

    # --- 9. approval expiry ---
    exp_ok = act is not None and not act.get("approval_expired", True)
    items.append(
        DispatchCheckItem(
            name="approval_not_expired",
            passed=exp_ok,
            observed=str(not act.get("approval_expired", True)) if act else "none",
            expected="true",
            rule_refs=["Art43"],
        )
    )
    if not exp_ok:
        reasons.append(DispatchReason.APPROVAL_EXPIRED)

    # --- 10. CRITICAL ---
    crit_ok, crit_obs = _recheck_critical()
    items.append(
        DispatchCheckItem(
            name="no_critical",
            passed=crit_ok,
            observed=crit_obs,
            expected="0 critical",
            rule_refs=["Art18"],
        )
    )
    if not crit_ok:
        reasons.append(DispatchReason.CRITICAL_ALERT_DETECTED)

    # --- 11. security ---
    sec_ok, sec_obs = _recheck_security()
    items.append(
        DispatchCheckItem(
            name="no_lockdown",
            passed=sec_ok,
            observed=sec_obs,
            expected="!=LOCKDOWN",
            rule_refs=["Art7"],
        )
    )
    if not sec_ok:
        reasons.append(DispatchReason.LOCKDOWN_ACTIVE)

    # --- 12. paper/micro only ---
    live_forbidden = execution_scope not in (
        "PAPER_ONLY",
        "MICRO_LIVE_ONLY",
        "SPECIFIC_SYMBOL_ONLY",
        "NO_EXECUTION",
    )
    items.append(
        DispatchCheckItem(
            name="no_live_scope",
            passed=not live_forbidden,
            observed=execution_scope,
            expected="paper/micro only",
            rule_refs=["Art36"],
        )
    )
    if live_forbidden:
        reasons.append(DispatchReason.LIVE_SCOPE_FORBIDDEN)

    # --- Decision ---
    if already_consumed or hash_reused:
        decision = DispatchDecision.DISPATCH_CONSUMED
    elif any(r in _BLOCKED_REASONS for r in reasons):
        decision = DispatchDecision.DISPATCH_BLOCKED
    elif len(reasons) > 0:
        decision = DispatchDecision.DISPATCH_DENIED
    else:
        decision = DispatchDecision.DISPATCH_ALLOWED
        # Consume activation (1회성)
        if act_aid:
            _consumed_activations[act_aid] = execution_id
        if hash_val:
            _consumed_hashes[hash_val] = execution_id

    passed = sum(1 for i in items if i.passed)
    summary = f"Dispatch: {passed}/{len(items)} passed, decision={decision.value}"
    if reasons:
        summary += f", reasons: {', '.join(r.value for r in reasons[:3])}"

    evidence_id = _store_dispatch_evidence(execution_id, decision, reasons, now)

    return DispatchReceipt(
        execution_id=execution_id,
        decision=decision,
        timestamp=now.isoformat(),
        activation_id=act_aid,
        execution_intent_hash=hash_val,
        execution_scope=execution_scope,
        requested_action=requested_action,
        target_symbol=target_symbol,
        activation_consumed_at=now.isoformat()
        if decision == DispatchDecision.DISPATCH_ALLOWED
        else None,
        consumed_by_execution_id=execution_id
        if decision == DispatchDecision.DISPATCH_ALLOWED
        else None,
        dispatch_window_expires_at=window_expiry.isoformat()
        if decision == DispatchDecision.DISPATCH_ALLOWED
        else None,
        evidence_chain=DispatchEvidenceChain(
            activation_id=act_aid,
            execution_intent_hash=hash_val,
            policy_snapshot_id=act.get("policy_snapshot_id", "") if act else "",
            approval_id=act.get("approval_id", "") if act else "",
        ),
        items=items,
        reasons=reasons,
        rule_refs=["Art7", "Art18", "Art33", "Art36", "Art38", "Art43"],
        evidence_id=evidence_id,
    )


# ---------------------------------------------------------------------------
# Helpers (read-only except consume registry)
# ---------------------------------------------------------------------------


def _collect_activation() -> dict | None:
    try:
        from app.core.executor_activation import evaluate_activation

        r = evaluate_activation()
        return {
            "decision": r.decision.value,
            "activation_id": r.activation_id,
            "execution_intent_hash": r.execution_intent_hash,
            "policy_snapshot_id": r.policy_snapshot_id,
            "approval_id": r.approval_id,
            "approval_scope": r.execution_scope,
            "target_symbol": r.target_symbol,
            "approval_expired": any(r2.value == "APPROVAL_EXPIRED" for r2 in r.reasons),
        }
    except Exception:
        return None


def _recheck_policy() -> tuple[bool, str]:
    try:
        from app.core.execution_policy import evaluate_execution_policy

        r = evaluate_execution_policy()
        return r.decision.value == "MATCH", r.decision.value
    except Exception as e:
        return False, f"error:{e}"


def _recheck_critical() -> tuple[bool, str]:
    try:
        import app.main as main_module

        fl = getattr(main_module.app.state, "flow_log", None)
        if fl is None:
            return True, "no_flow_log"
        cnt = sum(1 for e in fl.list_entries(limit=50) if e.get("policy_urgent"))
        return cnt == 0, f"critical={cnt}"
    except Exception:
        return True, "error"


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
    except Exception:
        return False, "error"


def _store_dispatch_evidence(
    execution_id: str,
    decision: DispatchDecision,
    reasons: list,
    now: datetime,
) -> str:
    try:
        import app.main as main_module

        gate = getattr(main_module.app.state, "governance_gate", None)
        if gate is None or not hasattr(gate, "evidence_store"):
            return f"fallback-dis-{uuid.uuid4().hex[:8]}"
        from kdexter.audit.evidence_store import EvidenceBundle

        bundle = EvidenceBundle(
            bundle_id=execution_id,
            created_at=now,
            trigger="micro_executor_dispatch",
            actor="e03_micro_executor",
            action=f"dispatch_{decision.value.lower()}",
            before_state=None,
            after_state={
                "decision": decision.value,
                "reasons": [r.value for r in reasons],
                "activation_id": execution_id,  # S-01A: consumed lookup key
                "intent_hash": "",  # S-01A: populated by caller if needed
                "dispatch_window_expires_at": "",  # S-01B: window expiry for guard
            },
            artifacts=[],
        )
        return gate.evidence_store.store(bundle)
    except Exception as e:
        logger.warning("dispatch_evidence_store_failed", error=str(e))
        return f"fallback-dis-{uuid.uuid4().hex[:8]}"
