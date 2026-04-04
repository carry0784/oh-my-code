"""
Gate Registry — K-Dexter AOS v4

All gates G-01~G-08 (Phase 4 Shadow Validation) and G-16~G-27 (v4 criteria)
with quantitative pass criteria and self-contained evaluate functions.

G-09~G-15: Reserved for Phase 4 expansion (B1 approval required).
G-28~G-30: Reserved — no criteria assigned yet.

Each Gate carries its own evaluate callable:
  (EvaluationContext) -> GateVerdict

Gate ↔ Mandatory mapping (mandatory_enforcement_map.md §5):
  G-02 ↔ M-05, M-06    G-03 ↔ M-03      G-04 ↔ M-04, M-09
  G-05 ↔ M-07           G-16 ↔ M-09      G-18 ↔ M-10
  G-19 ↔ M-11           G-20 ↔ M-12      G-21 ↔ M-13
  G-22 ↔ M-08           G-23 ↔ M-14      G-24 ↔ M-15
  G-25 ↔ M-16           G-26 ↔ M-17      G-27 ↔ M-18
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

from kdexter.audit.evidence_store import EvidenceBundle
from kdexter.config.thresholds import (
    DRIFT_HIGH_THRESHOLD,
    TRUST_BOUNDARY_DEGRADED,
)
from kdexter.gates.criteria import (
    EvaluationContext,
    GateVerdict,
    PassCriteria,
)
from kdexter.state_machine.work_state import ValidatingCheck


# ─────────────────────────────────────────────────────────────────────────── #
# Enums & types
# ─────────────────────────────────────────────────────────────────────────── #


class GateStatus(Enum):
    PENDING = "PENDING"
    PASS = "PASS"
    FAIL = "FAIL"
    SKIPPED = "SKIPPED"


class GatePhase(Enum):
    SHADOW = "SHADOW"  # failures logged only — not enforced
    ACTIVE = "ACTIVE"  # failures block execution


GateEvalFn = Callable[[EvaluationContext], GateVerdict]


# ─────────────────────────────────────────────────────────────────────────── #
# Gate dataclass
# ─────────────────────────────────────────────────────────────────────────── #


@dataclass
class Gate:
    """
    A governance gate with quantitative criteria and self-contained evaluation.

    Attributes:
        gate_id:          Unique identifier (G-01, G-16, ...)
        name:             Human-readable name
        description:      Purpose and enforcement rationale
        mandatory_items:  Connected Mandatory items (M-xx)
        criteria:         Quantitative pass criteria list
        evaluate:         Callable that produces a GateVerdict
        phase:            SHADOW (log only) or ACTIVE (enforced)
        validating_check: Which VALIDATING check this gate belongs to (if any)
        status:           Current gate status (set after evaluation)
    """

    gate_id: str
    name: str
    description: str
    mandatory_items: list[str] = field(default_factory=list)
    criteria: list[PassCriteria] = field(default_factory=list)
    evaluate: Optional[GateEvalFn] = None
    phase: GatePhase = GatePhase.SHADOW
    validating_check: Optional[ValidatingCheck] = None
    status: GateStatus = GateStatus.PENDING


# ─────────────────────────────────────────────────────────────────────────── #
# Verdict helpers
# ─────────────────────────────────────────────────────────────────────────── #


def _verdict(
    gate_id: str,
    passed: bool,
    measured: object,
    criteria: PassCriteria,
    reason: str = "",
) -> GateVerdict:
    """Build a GateVerdict with an EvidenceBundle."""
    return GateVerdict(
        gate_id=gate_id,
        passed=passed,
        measured_value=measured,
        criteria=criteria,
        evidence=EvidenceBundle(
            trigger=f"Gate.{gate_id}",
            actor="GateEvaluator",
            action="PASS" if passed else "FAIL",
            before_state=None,
            after_state=None,
        ),
        reason=reason,
    )


def _bool_gate(
    gate_id: str,
    criteria: PassCriteria,
    value: bool,
) -> GateVerdict:
    """Shortcut for boolean gates."""
    return _verdict(
        gate_id, value, value, criteria, "" if value else f"{criteria.metric_name} is False"
    )


# ─────────────────────────────────────────────────────────────────────────── #
# G-01 ~ G-08: Phase 4 Shadow Validation
# ─────────────────────────────────────────────────────────────────────────── #

_C_SHADOW = PassCriteria(
    "shadow_mode", "is_true", True, description="System must be in shadow mode for Phase 4"
)

_C_ROLLBACK = PassCriteria(
    "rollback_plan_ready", "is_true", True, description="M-05: rollback plan must exist"
)
_C_RECOVERY_SIM = PassCriteria(
    "recovery_simulation_done", "is_true", True, description="M-06: recovery simulation must be run"
)

_C_RISK = PassCriteria(
    "risk_checked", "is_true", True, description="M-03: risk check must be complete"
)

_C_SECURITY = PassCriteria(
    "security_checked", "is_true", True, description="M-04: security check must be complete"
)
_C_NO_VIOLATIONS = PassCriteria(
    "constitution_violation_count",
    "==",
    0,
    unit="count",
    description="M-09: zero constitution violations",
)

_C_EVIDENCE = PassCriteria(
    "evidence_bundle_count", ">=", 0, unit="count", description="M-07: evidence count >= expected"
)

_C_SPEC = PassCriteria(
    "spec_twin_id", "is_true", True, description="M-02: spec_twin_id must be set"
)

_C_APPROVAL = PassCriteria(
    "approval_granted", "is_true", True, description="Approval must be granted"
)


def _eval_g01(ctx: EvaluationContext) -> GateVerdict:
    """G-01 Shadow Entry: shadow_mode must be active."""
    return _bool_gate("G-01", _C_SHADOW, ctx.shadow_mode)


def _eval_g02(ctx: EvaluationContext) -> GateVerdict:
    """G-02 State Recovery: rollback plan + recovery simulation."""
    w = ctx.work
    ok = w.rollback_plan_ready and w.recovery_simulation_done
    failed = []
    if not w.rollback_plan_ready:
        failed.append("rollback_plan_ready")
    if not w.recovery_simulation_done:
        failed.append("recovery_simulation_done")
    return _verdict("G-02", ok, ok, _C_ROLLBACK, f"Missing: {', '.join(failed)}" if failed else "")


def _eval_g03(ctx: EvaluationContext) -> GateVerdict:
    """G-03 Risk Control: risk_checked must be True."""
    return _bool_gate("G-03", _C_RISK, ctx.work.risk_checked)


def _eval_g04(ctx: EvaluationContext) -> GateVerdict:
    """G-04 Constitution Compliance: security_checked + zero violations."""
    w = ctx.work
    ok = w.security_checked and ctx.constitution_violation_count == 0
    reason = ""
    if not w.security_checked:
        reason = "security_checked is False"
    elif ctx.constitution_violation_count > 0:
        reason = f"constitution violations: {ctx.constitution_violation_count}"
    return _verdict("G-04", ok, ok, _C_SECURITY, reason)


def _eval_g05(ctx: EvaluationContext) -> GateVerdict:
    """G-05 Audit Completeness: evidence_bundle_count >= expected."""
    ok = ctx.evidence_bundle_count >= ctx.expected_evidence_count
    return _verdict(
        "G-05",
        ok,
        ctx.evidence_bundle_count,
        PassCriteria(
            "evidence_bundle_count",
            ">=",
            ctx.expected_evidence_count,
            unit="count",
            description="M-07",
        ),
        ""
        if ok
        else (f"evidence={ctx.evidence_bundle_count} < expected={ctx.expected_evidence_count}"),
    )


def _eval_g06(ctx: EvaluationContext) -> GateVerdict:
    """G-06 Spec Compliance: spec_twin_id must be set."""
    return _bool_gate("G-06", _C_SPEC, bool(ctx.work.spec_twin_id))


def _eval_g07(ctx: EvaluationContext) -> GateVerdict:
    """G-07 Approval Gate: approval_granted must be True."""
    return _bool_gate("G-07", _C_APPROVAL, ctx.work.approval_granted)


def _eval_g08(ctx: EvaluationContext) -> GateVerdict:
    """G-08 Execution Readiness: composite — all G-01~G-07 must pass."""
    sub_evals = [_eval_g01, _eval_g02, _eval_g03, _eval_g04, _eval_g05, _eval_g06, _eval_g07]
    failed_ids = []
    for fn in sub_evals:
        v = fn(ctx)
        if not v.passed:
            failed_ids.append(v.gate_id)
    ok = len(failed_ids) == 0
    crit = PassCriteria(
        "g01_to_g07_all_pass", "is_true", True, description="All G-01~G-07 must pass"
    )
    return _verdict(
        "G-08", ok, ok, crit, f"Failed sub-gates: {', '.join(failed_ids)}" if failed_ids else ""
    )


# ─────────────────────────────────────────────────────────────────────────── #
# G-16 ~ G-27: v4 Criteria (previously TBD, now defined)
# ─────────────────────────────────────────────────────────────────────────── #

_C_COMPLIANCE = PassCriteria(
    "constitution_violation_count",
    "==",
    0,
    unit="count",
    description="M-09: zero constitution violations",
)

_C_PROVENANCE = PassCriteria(
    "provenance_recorded", "is_true", True, description="M-10: provenance must be recorded"
)

_C_DRIFT = PassCriteria(
    "drift_score",
    "<=",
    DRIFT_HIGH_THRESHOLD,
    unit="ratio",
    description=f"M-11: drift_score <= {DRIFT_HIGH_THRESHOLD}",
)

_C_CONFLICT = PassCriteria(
    "conflict_count", "==", 0, unit="count", description="M-12: zero active rule conflicts"
)

_C_PATTERN = PassCriteria(
    "anti_pattern_detected",
    "is_false",
    False,
    description="M-13: no known failure pattern detected",
)

_C_BUDGET = PassCriteria(
    "resource_usage_ratio",
    "<=",
    1.0,
    unit="ratio",
    description="M-08: resource usage <= budget limit",
)

_C_TRUST = PassCriteria(
    "trust_score",
    ">=",
    TRUST_BOUNDARY_DEGRADED,
    unit="score",
    description=f"M-14: trust_score >= {TRUST_BOUNDARY_DEGRADED}",
)

_C_COMPLETION = PassCriteria(
    "completion_score", ">=", 0.80, unit="score", description="M-16: completion_score >= threshold"
)

_C_SPEC_LOCK = PassCriteria(
    "spec_mutation_count",
    "==",
    0,
    unit="count",
    description="M-17: no spec mutations after SPEC_READY",
)

_C_RESEARCH = PassCriteria(
    "research_complete", "is_true", True, description="M-18: research must be complete"
)


def _eval_g16(ctx: EvaluationContext) -> GateVerdict:
    """G-16 Compliance Gate: zero constitution violations."""
    ok = ctx.constitution_violation_count == 0
    return _verdict(
        "G-16",
        ok,
        ctx.constitution_violation_count,
        _C_COMPLIANCE,
        "" if ok else f"violations: {ctx.constitution_violation_count}",
    )


def _eval_g18(ctx: EvaluationContext) -> GateVerdict:
    """G-18 Provenance Gate: provenance_recorded must be True."""
    return _bool_gate("G-18", _C_PROVENANCE, ctx.work.provenance_recorded)


def _eval_g19(ctx: EvaluationContext) -> GateVerdict:
    """G-19 Drift Gate: drift_score <= DRIFT_HIGH_THRESHOLD (0.35)."""
    ok = ctx.drift_score <= DRIFT_HIGH_THRESHOLD
    return _verdict(
        "G-19",
        ok,
        ctx.drift_score,
        _C_DRIFT,
        "" if ok else f"drift={ctx.drift_score:.4f} > {DRIFT_HIGH_THRESHOLD}",
    )


def _eval_g20(ctx: EvaluationContext) -> GateVerdict:
    """G-20 Conflict Gate: zero active rule conflicts."""
    ok = ctx.conflict_count == 0
    return _verdict(
        "G-20",
        ok,
        ctx.conflict_count,
        _C_CONFLICT,
        "" if ok else f"conflicts: {ctx.conflict_count}",
    )


def _eval_g21(ctx: EvaluationContext) -> GateVerdict:
    """G-21 Pattern Gate: no known failure pattern detected."""
    ok = not ctx.anti_pattern_detected
    return _verdict(
        "G-21", ok, ctx.anti_pattern_detected, _C_PATTERN, "" if ok else "anti-pattern detected"
    )


def _eval_g22(ctx: EvaluationContext) -> GateVerdict:
    """G-22 Budget Gate: resource_usage_ratio <= 1.0."""
    ok = ctx.resource_usage_ratio <= 1.0
    return _verdict(
        "G-22",
        ok,
        ctx.resource_usage_ratio,
        _C_BUDGET,
        "" if ok else f"usage={ctx.resource_usage_ratio:.3f} > 1.0",
    )


def _eval_g23(ctx: EvaluationContext) -> GateVerdict:
    """G-23 Trust Gate: trust_score >= TRUST_BOUNDARY_DEGRADED (0.60)."""
    ok = ctx.trust_score >= TRUST_BOUNDARY_DEGRADED
    return _verdict(
        "G-23",
        ok,
        ctx.trust_score,
        _C_TRUST,
        "" if ok else f"trust={ctx.trust_score:.3f} < {TRUST_BOUNDARY_DEGRADED}",
    )


def _eval_g24(ctx: EvaluationContext) -> GateVerdict:
    """G-24 Loop Gate: all loop counts within ceiling."""
    # Check that no loop exceeds its per_incident ceiling
    from kdexter.config.thresholds import LOOP_COUNT_CEILINGS

    failed = []
    for loop_name, count in ctx.loop_counts.items():
        ceiling = LOOP_COUNT_CEILINGS.get(loop_name.upper())
        if ceiling and count > ceiling.per_incident:
            failed.append(f"{loop_name}={count}>{ceiling.per_incident}")
    ok = len(failed) == 0
    crit = PassCriteria(
        "loop_counts",
        "<=",
        "per_incident_ceiling",
        unit="count",
        description="M-15: loops within ceilings",
    )
    return _verdict(
        "G-24", ok, ctx.loop_counts, crit, f"Exceeded: {', '.join(failed)}" if failed else ""
    )


def _eval_g25(ctx: EvaluationContext) -> GateVerdict:
    """G-25 Completion Gate: completion_score >= threshold."""
    threshold = ctx.work.completion_threshold
    ok = ctx.work.completion_score >= threshold
    crit = PassCriteria(
        "completion_score",
        ">=",
        threshold,
        unit="score",
        description=f"M-16: completion >= {threshold}",
    )
    return _verdict(
        "G-25",
        ok,
        ctx.work.completion_score,
        crit,
        "" if ok else (f"score={ctx.work.completion_score:.3f} < threshold={threshold:.3f}"),
    )


def _eval_g26(ctx: EvaluationContext) -> GateVerdict:
    """G-26 Spec Lock Gate: no spec mutations after SPEC_READY."""
    ok = ctx.spec_mutation_count == 0
    return _verdict(
        "G-26",
        ok,
        ctx.spec_mutation_count,
        _C_SPEC_LOCK,
        "" if ok else f"mutations: {ctx.spec_mutation_count}",
    )


def _eval_g27(ctx: EvaluationContext) -> GateVerdict:
    """G-27 Research Gate: research_complete must be True."""
    return _bool_gate("G-27", _C_RESEARCH, ctx.work.research_complete)


# ─────────────────────────────────────────────────────────────────────────── #
# Gate instances
# ─────────────────────────────────────────────────────────────────────────── #

ALL_GATES: list[Gate] = [
    # ── Phase 4 Shadow Validation (G-01~G-08) ───────────────────────────── #
    Gate(
        "G-01",
        "Shadow Entry",
        "System must be in shadow mode for Phase 4 validation",
        [],
        [_C_SHADOW],
        _eval_g01,
        GatePhase.SHADOW,
    ),
    Gate(
        "G-02",
        "State Recovery",
        "Rollback plan + recovery simulation must be complete",
        ["M-05", "M-06"],
        [_C_ROLLBACK, _C_RECOVERY_SIM],
        _eval_g02,
        GatePhase.SHADOW,
    ),
    Gate(
        "G-03",
        "Risk Control",
        "Risk check must be complete before execution",
        ["M-03"],
        [_C_RISK],
        _eval_g03,
        GatePhase.SHADOW,
    ),
    Gate(
        "G-04",
        "Constitution Compliance",
        "Security checked + zero constitution violations",
        ["M-04", "M-09"],
        [_C_SECURITY, _C_NO_VIOLATIONS],
        _eval_g04,
        GatePhase.SHADOW,
    ),
    Gate(
        "G-05",
        "Audit Completeness",
        "Evidence bundles must cover all transitions",
        ["M-07"],
        [_C_EVIDENCE],
        _eval_g05,
        GatePhase.SHADOW,
    ),
    Gate(
        "G-06",
        "Spec Compliance",
        "Spec twin ID must be set",
        ["M-02"],
        [_C_SPEC],
        _eval_g06,
        GatePhase.SHADOW,
    ),
    Gate(
        "G-07",
        "Approval Gate",
        "Approval must be granted before execution",
        [],
        [_C_APPROVAL],
        _eval_g07,
        GatePhase.SHADOW,
    ),
    Gate(
        "G-08",
        "Execution Readiness",
        "Composite: all G-01~G-07 must pass",
        [],
        [],
        _eval_g08,
        GatePhase.SHADOW,
    ),
    # ── v4 Gates (G-16~G-27) — VALIDATING check mapping ────────────────── #
    Gate(
        "G-16",
        "Compliance Gate",
        "Zero constitution violations (M-09)",
        ["M-09"],
        [_C_COMPLIANCE],
        _eval_g16,
        GatePhase.ACTIVE,
        ValidatingCheck.COMPLIANCE_CHECK,
    ),
    Gate(
        "G-18",
        "Provenance Gate",
        "Rule provenance must be recorded (M-10)",
        ["M-10"],
        [_C_PROVENANCE],
        _eval_g18,
        GatePhase.ACTIVE,
    ),
    Gate(
        "G-19",
        "Drift Gate",
        f"Intent drift score <= {DRIFT_HIGH_THRESHOLD} (M-11, OQ-4)",
        ["M-11"],
        [_C_DRIFT],
        _eval_g19,
        GatePhase.ACTIVE,
        ValidatingCheck.DRIFT_CHECK,
    ),
    Gate(
        "G-20",
        "Conflict Gate",
        "Zero active rule conflicts (M-12)",
        ["M-12"],
        [_C_CONFLICT],
        _eval_g20,
        GatePhase.ACTIVE,
        ValidatingCheck.CONFLICT_CHECK,
    ),
    Gate(
        "G-21",
        "Pattern Gate",
        "No known failure pattern detected (M-13)",
        ["M-13"],
        [_C_PATTERN],
        _eval_g21,
        GatePhase.ACTIVE,
        ValidatingCheck.PATTERN_CHECK,
    ),
    Gate(
        "G-22",
        "Budget Gate",
        "Resource usage within budget limit (M-08)",
        ["M-08"],
        [_C_BUDGET],
        _eval_g22,
        GatePhase.ACTIVE,
        ValidatingCheck.BUDGET_CHECK,
    ),
    Gate(
        "G-23",
        "Trust Gate",
        f"Trust score >= {TRUST_BOUNDARY_DEGRADED} (M-14, OQ-5)",
        ["M-14"],
        [_C_TRUST],
        _eval_g23,
        GatePhase.ACTIVE,
        ValidatingCheck.TRUST_CHECK,
    ),
    Gate(
        "G-24",
        "Loop Gate",
        "All loop counts within per-incident ceilings (M-15, OQ-6)",
        ["M-15"],
        [],
        _eval_g24,
        GatePhase.ACTIVE,
        ValidatingCheck.LOOP_CHECK,
    ),
    Gate(
        "G-25",
        "Completion Gate",
        "Completion score >= threshold (M-16, OQ-7/OQ-9)",
        ["M-16"],
        [_C_COMPLETION],
        _eval_g25,
        GatePhase.ACTIVE,
    ),
    Gate(
        "G-26",
        "Spec Lock Gate",
        "No spec mutations after SPEC_READY (M-17)",
        ["M-17"],
        [_C_SPEC_LOCK],
        _eval_g26,
        GatePhase.ACTIVE,
        ValidatingCheck.LOCK_CHECK,
    ),
    Gate(
        "G-27",
        "Research Gate",
        "Research must be complete before execution (M-18)",
        ["M-18"],
        [_C_RESEARCH],
        _eval_g27,
        GatePhase.ACTIVE,
    ),
]

# Lookup by gate_id
GATE_MAP: dict[str, Gate] = {g.gate_id: g for g in ALL_GATES}

# Lookup by ValidatingCheck
GATES_BY_CHECK: dict[ValidatingCheck, list[Gate]] = {}
for _g in ALL_GATES:
    if _g.validating_check is not None:
        GATES_BY_CHECK.setdefault(_g.validating_check, []).append(_g)
