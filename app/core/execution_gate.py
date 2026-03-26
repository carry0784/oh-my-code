"""
I-05: Execution Gate — 4조건 통합 판정 러너

역참조: Operating Constitution v1.0 제7조, 제41조, 제42조, 제43조

4조건 (AND):
  1. preflight.decision == READY  (제43조, I-04)
  2. ops_score >= threshold        (제41조, I-01)
  3. trading_authorized == true    (제42조, I-01)
  4. lockdown == false             (제7조, I-01)

OPEN means gate-open, not execution-authorized.
자동 거래 실행/재개/승격/자본 확대 금지.
Read-only 판정. State mutation 금지.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.core.logging import get_logger
from app.schemas.execution_gate_schema import (
    ExecutionGateResult,
    GateCondition,
    GateDecision,
)

logger = get_logger(__name__)

DEFAULT_OPS_SCORE_THRESHOLD = 0.7


def evaluate_execution_gate(
    ops_score_threshold: float = DEFAULT_OPS_SCORE_THRESHOLD,
) -> ExecutionGateResult:
    """
    Execution Gate 4조건 통합 판정.
    Read-only. No state mutation. No auto-execution.
    OPEN means gate-open, not execution-authorized.
    """
    now = datetime.now(timezone.utc)
    conditions: list[GateCondition] = []

    # --- Condition 1: preflight.decision == READY (제43조) ---
    pf_met, pf_observed = _check_preflight()
    conditions.append(GateCondition(
        name="preflight_ready",
        met=pf_met,
        observed=pf_observed,
        required="READY",
        source="I-04",
        rule_ref="Art43",
    ))

    # --- Condition 2: ops_score >= threshold (제41조) ---
    score_avg, score_met, score_observed = _check_ops_score(ops_score_threshold)
    conditions.append(GateCondition(
        name="ops_score_above_threshold",
        met=score_met,
        observed=score_observed,
        required=f">={ops_score_threshold}",
        source="I-01",
        rule_ref="Art41",
    ))

    # --- Condition 3: trading_authorized == true (제42조) ---
    ta_met, ta_observed = _check_trading_authorized()
    conditions.append(GateCondition(
        name="trading_authorized",
        met=ta_met,
        observed=ta_observed,
        required="true",
        source="I-01",
        rule_ref="Art42",
    ))

    # --- Condition 4: lockdown == false (제7조) ---
    ld_met, ld_observed = _check_lockdown()
    conditions.append(GateCondition(
        name="lockdown_inactive",
        met=ld_met,
        observed=ld_observed,
        required="false",
        source="I-01",
        rule_ref="Art7",
    ))

    # --- Decision ---
    met_count = sum(1 for c in conditions if c.met)
    decision = GateDecision.OPEN if met_count == 4 else GateDecision.CLOSED

    # Summary
    unmet = [c.name for c in conditions if not c.met]
    if decision == GateDecision.OPEN:
        summary = "Execution Gate OPEN: all 4 conditions met"
    else:
        summary = f"Execution Gate CLOSED: {', '.join(unmet)} not met"

    # Evidence
    evidence_id = _store_gate_evidence(decision, conditions, now)

    return ExecutionGateResult(
        timestamp=now.isoformat(),
        decision=decision,
        summary=summary,
        conditions=conditions,
        conditions_met=met_count,
        conditions_total=4,
        ops_score_average=round(score_avg, 4),
        ops_score_threshold=ops_score_threshold,
        evidence_id=evidence_id,
        rule_refs=["Art7", "Art41", "Art42", "Art43"],
        operator_action_required=decision == GateDecision.CLOSED,
    )


# ---------------------------------------------------------------------------
# Condition checkers (read-only, fail-closed)
# ---------------------------------------------------------------------------

def _check_preflight() -> tuple[bool, str]:
    """Check preflight decision. Reuse I-04 runner."""
    try:
        from app.core.recovery_preflight import run_recovery_preflight
        result = run_recovery_preflight()
        decision = result.decision.value
        return decision == "READY", decision
    except Exception as e:
        return False, f"error:{e}"


def _check_ops_score(threshold: float) -> tuple[float, bool, str]:
    """Check ops score average against threshold. Reuse I-01 computation."""
    try:
        from app.api.routes.dashboard import (
            _compute_integrity_panel,
            _compute_trading_safety_panel,
            _compute_incident_panel,
            _compute_ops_score,
        )
        from datetime import datetime, timezone

        # We need lightweight read-only computation without DB session
        # Use ops_score from app state if available, else compute minimal
        import app.main as main_module
        gate = getattr(main_module.app.state, "governance_gate", None)

        # Compute real snapshot_age from DB (sync) for accurate connectivity score
        from app.schemas.ops_status import IntegrityPanel, TradingSafetyPanel, IncidentEvidencePanel
        snapshot_age = None
        try:
            from sqlalchemy import create_engine, select, desc
            from sqlalchemy.orm import Session
            from app.core.config import settings as _cfg
            from app.models.position import Position
            engine = create_engine(_cfg.database_url_sync)
            with Session(engine) as sess:
                latest = sess.query(Position.updated_at).order_by(Position.updated_at.desc()).first()
                ts = latest[0] if latest else None
                if ts is None:
                    from app.models.asset_snapshot import AssetSnapshot
                    snap = sess.query(AssetSnapshot.snapshot_at).order_by(AssetSnapshot.snapshot_at.desc()).first()
                    ts = snap[0] if snap else None
                if ts:
                    now = datetime.now(timezone.utc)
                    snapshot_age = int((now - ts.replace(tzinfo=timezone.utc)).total_seconds())
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
        trading = TradingSafetyPanel()
        incident = IncidentEvidencePanel()

        score = _compute_ops_score(integrity, trading, incident)
        avg = (score.integrity + score.connectivity + score.execution_safety + score.evidence_completeness) / 4
        return avg, avg >= threshold, f"{avg:.4f}"
    except Exception as e:
        return 0.0, False, f"error:{e}"


def _check_trading_authorized() -> tuple[bool, str]:
    """Check trading_authorized from dual lock. Reuse I-01 computation."""
    try:
        import app.main as main_module
        gate = getattr(main_module.app.state, "governance_gate", None)

        if gate is None:
            return False, "governance_gate=None"

        # Check security state
        if hasattr(gate, "security_ctx"):
            ctx = gate.security_ctx
            state_val = ctx.current.value if hasattr(ctx.current, "value") else str(ctx.current)
            if state_val != "NORMAL":
                return False, f"security={state_val}"

        return True, "true"
    except Exception as e:
        return False, f"error:{e}"


def _check_lockdown() -> tuple[bool, str]:
    """Check lockdown is inactive."""
    try:
        import app.main as main_module
        gate = getattr(main_module.app.state, "governance_gate", None)

        if gate is None:
            return False, "governance_gate=None"

        if hasattr(gate, "security_ctx"):
            ctx = gate.security_ctx
            state_val = ctx.current.value if hasattr(ctx.current, "value") else str(ctx.current)
            is_lockdown = state_val == "LOCKDOWN"
            return not is_lockdown, f"lockdown={is_lockdown}"

        return False, "no_security_ctx"
    except Exception as e:
        return False, f"error:{e}"


def _store_gate_evidence(
    decision: GateDecision,
    conditions: list[GateCondition],
    now: datetime,
) -> str:
    """Store gate evaluation to evidence store. Append-only."""
    try:
        import app.main as main_module
        gate = getattr(main_module.app.state, "governance_gate", None)
        if gate is None or not hasattr(gate, "evidence_store"):
            return f"fallback-gate-{uuid.uuid4().hex[:8]}"

        from kdexter.audit.evidence_store import EvidenceBundle
        bundle = EvidenceBundle(
            bundle_id=str(uuid.uuid4()),
            created_at=now,
            trigger="execution_gate_evaluation",
            actor="i05_execution_gate",
            action="gate_evaluated",
            before_state=None,
            after_state={
                "decision": decision.value,
                "conditions_met": sum(1 for c in conditions if c.met),
                "conditions_total": len(conditions),
                "unmet": [c.name for c in conditions if not c.met],
            },
            artifacts=[
                {"name": c.name, "met": c.met, "observed": c.observed, "rule_ref": c.rule_ref}
                for c in conditions
            ],
        )
        return gate.evidence_store.store(bundle)
    except Exception as e:
        logger.warning("gate_evidence_store_failed", error=str(e))
        return f"fallback-gate-{uuid.uuid4().hex[:8]}"
