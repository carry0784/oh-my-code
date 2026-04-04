"""
Gate Evaluator — K-Dexter AOS v4

Stateless orchestrator that runs Gate evaluations against an EvaluationContext.
Produces GateSuiteResult with per-gate verdicts and EvidenceBundles.

Usage:
    evaluator = GateEvaluator(ALL_GATES)
    suite = evaluator.evaluate_all(ctx)
    if not suite.all_passed:
        print(suite.failed_gate_ids)
"""

from __future__ import annotations

import logging
from typing import Optional

from kdexter.audit.evidence_store import EvidenceBundle
from kdexter.gates.criteria import EvaluationContext, GateSuiteResult, GateVerdict
from kdexter.gates.gate_registry import Gate, GatePhase, GATES_BY_CHECK
from kdexter.state_machine.work_state import ValidatingCheck

logger = logging.getLogger(__name__)


class GateEvaluator:
    """
    Evaluates a set of gates against an EvaluationContext.

    - evaluate_all():      run every registered gate, collect all verdicts
    - evaluate_single():   run one gate by ID
    - evaluate_by_check(): run gates mapped to a ValidatingCheck (MainLoop hook compat)
    """

    def __init__(self, gates: list[Gate]) -> None:
        self._gates = {g.gate_id: g for g in gates}
        self._gates_by_check: dict[ValidatingCheck, list[Gate]] = {}
        for g in gates:
            if g.validating_check is not None:
                self._gates_by_check.setdefault(g.validating_check, []).append(g)

    def evaluate_all(self, ctx: EvaluationContext) -> GateSuiteResult:
        """
        Evaluate all registered gates. Does NOT fail-fast — runs every gate
        to produce a complete violation report.
        """
        verdicts: list[GateVerdict] = []
        for gate in self._gates.values():
            verdict = self._run_gate(gate, ctx)
            verdicts.append(verdict)

        failed = [v for v in verdicts if not v.passed]
        return GateSuiteResult(
            all_passed=len(failed) == 0,
            verdicts=verdicts,
            failed_gates=failed,
        )

    def evaluate_single(self, gate_id: str, ctx: EvaluationContext) -> GateVerdict:
        """Evaluate a single gate by ID. Raises KeyError if not found."""
        gate = self._gates[gate_id]
        return self._run_gate(gate, ctx)

    def evaluate_by_check(
        self,
        check: ValidatingCheck,
        ctx: EvaluationContext,
    ) -> tuple[bool, str]:
        """
        MainLoop hook-compatible interface.
        Returns (passed: bool, reason: str) for all gates mapped to the check.
        """
        gates = self._gates_by_check.get(check, [])
        if not gates:
            # No gates mapped to this check — pass by default
            return True, ""

        for gate in gates:
            verdict = self._run_gate(gate, ctx)
            if not verdict.passed:
                # In shadow mode, log but don't fail
                if gate.phase == GatePhase.SHADOW:
                    logger.warning(
                        f"[SHADOW] Gate {gate.gate_id} ({gate.name}) failed: "
                        f"{verdict.reason} — not enforced"
                    )
                    continue
                return False, f"[{gate.gate_id} {gate.name}] {verdict.reason}"

        return True, ""

    def _run_gate(self, gate: Gate, ctx: EvaluationContext) -> GateVerdict:
        """Run a single gate's evaluate function with error handling."""
        if gate.evaluate is None:
            logger.debug(f"Gate {gate.gate_id} has no evaluate function — auto-pass")
            from kdexter.gates.criteria import PassCriteria

            return GateVerdict(
                gate_id=gate.gate_id,
                passed=True,
                measured_value=None,
                criteria=PassCriteria(
                    "noop", "is_true", True, description="No evaluate function defined"
                ),
                evidence=EvidenceBundle(
                    trigger=f"Gate.{gate.gate_id}",
                    actor="GateEvaluator",
                    action="SKIP",
                ),
                reason="No evaluate function — auto-pass",
            )

        try:
            verdict = gate.evaluate(ctx)
            log_fn = logger.debug if verdict.passed else logger.info
            log_fn(
                f"Gate {gate.gate_id} ({gate.name}): "
                f"{'PASS' if verdict.passed else 'FAIL'}"
                f"{' — ' + verdict.reason if verdict.reason else ''}"
            )
            return verdict
        except Exception as exc:
            logger.exception(f"Gate {gate.gate_id} evaluation error: {exc}")
            from kdexter.gates.criteria import PassCriteria

            return GateVerdict(
                gate_id=gate.gate_id,
                passed=False,
                measured_value=None,
                criteria=PassCriteria(
                    "error", "==", "no_error", description="Gate must not raise exceptions"
                ),
                evidence=EvidenceBundle(
                    trigger=f"Gate.{gate.gate_id}",
                    actor="GateEvaluator",
                    action="ERROR",
                ),
                reason=f"Evaluation error: {exc}",
            )
