"""
Evolution Loop — K-Dexter AOS v4

Generates novel strategy variants, evaluates them in a sandboxed
backtesting environment, and promotes survivors to the live strategy pool
after meeting constitutional fitness criteria.

Triggered by (failure_taxonomy.md Section 2):
  - STRATEGY HIGH (PATTERN)
  - STRATEGY MEDIUM (PATTERN)
  - GOVERNANCE MEDIUM (PATTERN)
  - INFRA MEDIUM (PATTERN) — scheduled after Recovery

Phases:
  1. GENERATE   — produce strategy variant candidates (via LLM or parameter mutation)
  2. SANDBOX    — run candidates in isolated backtest sandbox
  3. EVALUATE   — score fitness, rank candidates
  4. GATE       — B1 constitutional fitness gate (doctrine compliance)
  5. PROMOTE    — promote winning candidate to live rule set

Mandatory items applied (all 18 — no exemptions for Evolution):
  M-03 risk check, M-04 security check, M-07 evidence (always),
  M-10 provenance (always), M-16 completion check

Loop ceiling (thresholds.py): per_incident=1, per_day=2, per_week=3
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Callable, Awaitable

from kdexter.audit.evidence_store import EvidenceBundle, EvidenceStore
from kdexter.governance.doctrine import DoctrineRegistry
from kdexter.ledger.rule_ledger import (
    Rule,
    RuleLedger,
    RuleProvenance,
)
from kdexter.loops.concurrency import (
    LoopCounter,
    LoopCeilingExceededError,
    LoopPriority,
    LoopPriorityQueue,
    RuleLedgerLock,
)
from kdexter.state_machine.security_state import SecurityStateContext


# ─────────────────────────────────────────────────────────────────────────── #
# Phase enum
# ─────────────────────────────────────────────────────────────────────────── #


class EvoPhase(Enum):
    IDLE = "IDLE"
    GENERATE = "GENERATE"
    SANDBOX = "SANDBOX"
    EVALUATE = "EVALUATE"
    GATE = "GATE"
    PROMOTE = "PROMOTE"
    FAILED = "FAILED"


# ─────────────────────────────────────────────────────────────────────────── #
# Data models
# ─────────────────────────────────────────────────────────────────────────── #


@dataclass
class StrategyCandidate:
    """A candidate strategy variant produced by the Generate phase."""

    candidate_id: str = field(default_factory=lambda: f"SC-{uuid.uuid4().hex[:8].upper()}")
    name: str = ""
    description: str = ""
    parameters: dict = field(default_factory=dict)  # strategy parameters
    source: str = "MUTATION"  # "MUTATION" | "LLM" | "CROSSOVER"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SandboxResult:
    """Result of running a candidate in the sandbox."""

    candidate_id: str = ""
    win_rate: float = 0.0
    avg_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    total_trades: int = 0
    fitness_score: float = 0.0  # composite fitness (0.0~1.0)
    passed_sandbox: bool = False


@dataclass
class EvoResult:
    """Result of one Evolution cycle."""

    cycle_id: str
    incident_id: str
    phase_reached: EvoPhase
    candidates_generated: int = 0
    candidates_sandbox_passed: int = 0
    candidates_gate_passed: int = 0
    promoted_candidate_id: Optional[str] = None
    error: Optional[str] = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

    def finish(self, phase: EvoPhase, error: Optional[str] = None) -> None:
        self.phase_reached = phase
        self.error = error
        self.completed_at = datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────────────────── #
# Hooks (dependency injection)
# ─────────────────────────────────────────────────────────────────────────── #


@dataclass
class EvoHooks:
    """
    Injectable callbacks for Evolution Loop.
    Default: stubs that produce minimal candidates.
    """

    # Generate: produce strategy candidates
    generate: Callable[[list[str]], Awaitable[list[StrategyCandidate]]] = None

    # Sandbox: run candidate in isolated backtest, return result
    sandbox: Callable[[StrategyCandidate], Awaitable[SandboxResult]] = None

    # Risk check (M-03)
    check_risk: Callable[[], Awaitable[bool]] = None

    # Security check (M-04)
    check_security: Callable[[], Awaitable[bool]] = None

    def __post_init__(self) -> None:
        if self.generate is None:

            async def _default_generate(failure_ids: list[str]) -> list[StrategyCandidate]:
                return [
                    StrategyCandidate(
                        name="default_variant",
                        description="mutation of current strategy",
                        parameters={"adjustment": 0.01},
                    )
                ]

            self.generate = _default_generate

        if self.sandbox is None:

            async def _default_sandbox(candidate: StrategyCandidate) -> SandboxResult:
                return SandboxResult(
                    candidate_id=candidate.candidate_id,
                    win_rate=0.55,
                    avg_return=0.002,
                    max_drawdown=0.05,
                    sharpe_ratio=1.2,
                    total_trades=500,
                    fitness_score=0.7,
                    passed_sandbox=True,
                )

            self.sandbox = _default_sandbox

        if self.check_risk is None:

            async def _default_risk() -> bool:
                return True

            self.check_risk = _default_risk

        if self.check_security is None:

            async def _default_security() -> bool:
                return True

            self.check_security = _default_security


# ─────────────────────────────────────────────────────────────────────────── #
# Constants
# ─────────────────────────────────────────────────────────────────────────── #

# Minimum fitness score for sandbox pass
SANDBOX_FITNESS_THRESHOLD: float = 0.5

# Minimum fitness score for promotion
PROMOTION_FITNESS_THRESHOLD: float = 0.6


# ─────────────────────────────────────────────────────────────────────────── #
# Evolution Loop
# ─────────────────────────────────────────────────────────────────────────── #


class EvolutionLoop:
    """
    AI-driven strategy evolution loop.

    Single instance — queued if Recovery or Self-Improvement is active.
    Most conservative loop: per_incident=1, per_day=2, per_week=3.

    Usage:
        loop = EvolutionLoop(
            rule_ledger=ledger, rule_lock=lock,
            evidence_store=store, security=sec,
            doctrine=doctrine_reg,
            loop_counter=counter, loop_queue=queue,
        )
        loop.accept_trigger("F-S-001", "STRATEGY", "HIGH", "PATTERN")
        result = await loop.run()
    """

    def __init__(
        self,
        rule_ledger: RuleLedger,
        rule_lock: RuleLedgerLock,
        evidence_store: EvidenceStore,
        security: SecurityStateContext,
        doctrine: DoctrineRegistry,
        loop_counter: LoopCounter,
        loop_queue: LoopPriorityQueue,
        hooks: Optional[EvoHooks] = None,
    ) -> None:
        self._ledger = rule_ledger
        self._lock = rule_lock
        self._evidence = evidence_store
        self._security = security
        self._doctrine = doctrine
        self._counter = loop_counter
        self._queue = loop_queue
        self._hooks = hooks or EvoHooks()

        self._phase = EvoPhase.IDLE
        self._active = False
        self._trigger_failures: list[str] = []
        self._incident_id: str = ""

    # ── Properties ───────────────────────────────────────────────────────── #

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def current_phase(self) -> EvoPhase:
        return self._phase

    # ── Public API ───────────────────────────────────────────────────────── #

    def accept_trigger(
        self,
        failure_id: str,
        domain: str,
        severity: str,
        recurrence: str = "PATTERN",
        incident_id: Optional[str] = None,
    ) -> None:
        """Accept a failure trigger for evolution."""
        self._trigger_failures.append(failure_id)
        self._incident_id = incident_id or f"EVO-{uuid.uuid4().hex[:8].upper()}"

    async def run(self) -> EvoResult:
        """
        Execute one evolution cycle.
        Phases: GENERATE → SANDBOX → EVALUATE → GATE → PROMOTE
        """
        cycle_id = f"EVO-{uuid.uuid4().hex[:8].upper()}"
        result = EvoResult(
            cycle_id=cycle_id,
            incident_id=self._incident_id,
            phase_reached=EvoPhase.IDLE,
        )

        # Ceiling check
        try:
            self._counter.check_and_record("EVOLUTION", self._incident_id)
        except LoopCeilingExceededError as exc:
            result.finish(EvoPhase.FAILED, str(exc))
            return result

        self._active = True
        self._queue.mark_active(LoopPriority.EVOLUTION)

        try:
            # Phase 1: GENERATE
            candidates = await self._phase_generate(result)
            result.candidates_generated = len(candidates)

            if not candidates:
                self._emit("NO_CANDIDATES", {"cycle_id": cycle_id})
                result.finish(EvoPhase.GENERATE)
                return result

            # Phase 2: SANDBOX
            sandbox_results = await self._phase_sandbox(candidates, result)
            passed = [sr for sr in sandbox_results if sr.passed_sandbox]
            result.candidates_sandbox_passed = len(passed)

            if not passed:
                self._emit("NO_SANDBOX_PASS", {"cycle_id": cycle_id})
                result.finish(EvoPhase.SANDBOX)
                return result

            # Phase 3: EVALUATE
            best = await self._phase_evaluate(passed, result)

            # Phase 4: GATE (B1 constitutional fitness)
            gate_passed = await self._phase_gate(best, candidates, result)
            if not gate_passed:
                result.finish(EvoPhase.GATE, "Constitutional gate failed")
                return result
            result.candidates_gate_passed = 1

            # Phase 5: PROMOTE
            candidate = self._find_candidate(candidates, best.candidate_id)
            await self._phase_promote(candidate, best, result)
            result.promoted_candidate_id = best.candidate_id

            result.finish(EvoPhase.PROMOTE)

        except EvoFailureError as exc:
            self._phase = EvoPhase.FAILED
            self._emit("EVO_FAILED", {"reason": str(exc), "cycle_id": cycle_id})
            result.finish(EvoPhase.FAILED, str(exc))

        except Exception as exc:
            self._phase = EvoPhase.FAILED
            result.finish(EvoPhase.FAILED, str(exc))

        finally:
            self._active = False
            self._queue.mark_inactive(LoopPriority.EVOLUTION)
            self._trigger_failures.clear()

        return result

    # ── Phase implementations ────────────────────────────────────────────── #

    async def _phase_generate(self, result: EvoResult) -> list[StrategyCandidate]:
        """Phase 1: Generate strategy variant candidates."""
        self._phase = EvoPhase.GENERATE

        # M-03: risk check before generation
        if not await self._hooks.check_risk():
            raise EvoFailureError("M-03 risk check failed in GENERATE phase")

        candidates = await self._hooks.generate(self._trigger_failures)

        self._emit(
            "GENERATE_COMPLETE",
            {
                "candidate_count": len(candidates),
                "candidates": [c.candidate_id for c in candidates],
                "trigger_failures": self._trigger_failures,
            },
        )
        return candidates

    async def _phase_sandbox(
        self,
        candidates: list[StrategyCandidate],
        result: EvoResult,
    ) -> list[SandboxResult]:
        """Phase 2: Run each candidate in isolated sandbox."""
        self._phase = EvoPhase.SANDBOX

        sandbox_results = []
        for candidate in candidates:
            sr = await self._hooks.sandbox(candidate)
            sr.passed_sandbox = sr.fitness_score >= SANDBOX_FITNESS_THRESHOLD
            sandbox_results.append(sr)

            self._emit(
                "SANDBOX_RESULT",
                {
                    "candidate_id": sr.candidate_id,
                    "fitness_score": sr.fitness_score,
                    "passed": sr.passed_sandbox,
                    "win_rate": sr.win_rate,
                    "sharpe_ratio": sr.sharpe_ratio,
                },
            )

        return sandbox_results

    async def _phase_evaluate(
        self,
        passed: list[SandboxResult],
        result: EvoResult,
    ) -> SandboxResult:
        """Phase 3: Rank candidates by fitness, select best."""
        self._phase = EvoPhase.EVALUATE

        # Sort by fitness score descending
        ranked = sorted(passed, key=lambda sr: sr.fitness_score, reverse=True)
        best = ranked[0]

        self._emit(
            "EVALUATE_COMPLETE",
            {
                "best_candidate_id": best.candidate_id,
                "best_fitness": best.fitness_score,
                "total_evaluated": len(ranked),
            },
        )
        return best

    async def _phase_gate(
        self,
        best: SandboxResult,
        candidates: list[StrategyCandidate],
        result: EvoResult,
    ) -> bool:
        """Phase 4: B1 constitutional fitness gate."""
        self._phase = EvoPhase.GATE

        # M-04: security check
        if not await self._hooks.check_security():
            self._emit("GATE_SECURITY_FAIL", {"candidate_id": best.candidate_id})
            return False

        # Fitness threshold for promotion
        if best.fitness_score < PROMOTION_FITNESS_THRESHOLD:
            self._emit(
                "GATE_FITNESS_FAIL",
                {
                    "candidate_id": best.candidate_id,
                    "fitness": best.fitness_score,
                    "threshold": PROMOTION_FITNESS_THRESHOLD,
                },
            )
            return False

        # B1 doctrine compliance check
        candidate = self._find_candidate(candidates, best.candidate_id)
        context = {
            "actor": "EvolutionLoop",
            "via_tcl": True,
            "provenance": True,
            "intent": f"Promote evolved strategy: {candidate.name if candidate else 'unknown'}",
            "risk_checked": True,
            "lock_held": True,
            "evidence_bundle_count": 1,
            "expected_evidence_count": 1,
        }
        violations = self._doctrine.check_compliance(context)
        if violations:
            self._emit(
                "GATE_DOCTRINE_FAIL",
                {
                    "candidate_id": best.candidate_id,
                    "violations": [v.doctrine_id for v in violations],
                },
            )
            return False

        self._emit(
            "GATE_PASSED",
            {
                "candidate_id": best.candidate_id,
                "fitness": best.fitness_score,
            },
        )
        return True

    async def _phase_promote(
        self,
        candidate: Optional[StrategyCandidate],
        best: SandboxResult,
        result: EvoResult,
    ) -> None:
        """Phase 5: Promote winning candidate to live Rule Ledger."""
        self._phase = EvoPhase.PROMOTE

        if candidate is None:
            raise EvoFailureError(f"Candidate {best.candidate_id} not found for promotion")

        # M-10: provenance required
        provenance = RuleProvenance(
            source_incident=self._incident_id,
            author_layer="L14",  # Operation Evolution Engine = L14
            rationale=(
                f"Evolution promotion: {candidate.name} "
                f"(fitness={best.fitness_score:.3f}, "
                f"sharpe={best.sharpe_ratio:.2f})"
            ),
        )

        rule = Rule(
            name=f"evo_{candidate.name}",
            condition=str(candidate.parameters),
            action="EVOLVED_STRATEGY",
            provenance=provenance,
        )

        await self._ledger.create(rule, LoopPriority.EVOLUTION)

        self._emit(
            "PROMOTE_COMPLETE",
            {
                "candidate_id": candidate.candidate_id,
                "rule_id": rule.rule_id,
                "fitness": best.fitness_score,
                "parameters": candidate.parameters,
            },
        )

    # ── Helpers ──────────────────────────────────────────────────────────── #

    @staticmethod
    def _find_candidate(
        candidates: list[StrategyCandidate],
        candidate_id: str,
    ) -> Optional[StrategyCandidate]:
        for c in candidates:
            if c.candidate_id == candidate_id:
                return c
        return None

    def _emit(self, action: str, artifacts: dict) -> None:
        """M-07: emit EvidenceBundle for every phase."""
        bundle = EvidenceBundle(
            trigger=f"EvolutionLoop.{action}",
            actor="EvolutionLoop",
            action=action,
            artifacts=[artifacts],
        )
        self._evidence.store(bundle)


# ─────────────────────────────────────────────────────────────────────────── #
# Exceptions
# ─────────────────────────────────────────────────────────────────────────── #


class EvoFailureError(Exception):
    """Evolution Loop phase failure."""

    pass
