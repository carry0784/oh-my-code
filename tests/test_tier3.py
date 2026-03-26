"""
Tier 3 Tests -- Remaining Loops (Self-Improvement + Evolution)
K-Dexter AOS v4

Tests:
  1. SelfImprovementLoop: phases, hooks, backtest, rule creation, ceiling
  2. EvolutionLoop: phases, sandbox, gate, promotion, ceiling

Run: python tests/test_tier3.py
"""
from __future__ import annotations

import asyncio
import sys

from kdexter.audit.evidence_store import EvidenceStore
from kdexter.governance.doctrine import DoctrineRegistry
from kdexter.ledger.rule_ledger import RuleLedger, RuleProvenance, Rule
from kdexter.loops.concurrency import (
    LoopCounter, LoopPriority, LoopPriorityQueue, RuleLedgerLock,
)
from kdexter.loops.self_improvement_loop import (
    SelfImprovementLoop, SIHooks, SIPhase, SIResult,
    ImprovementProposal, PerformanceSample, SIFailureError,
    BACKTEST_ACCEPTANCE_THRESHOLD,
)
from kdexter.loops.evolution_loop import (
    EvolutionLoop, EvoHooks, EvoPhase, EvoResult,
    StrategyCandidate, SandboxResult, EvoFailureError,
    SANDBOX_FITNESS_THRESHOLD, PROMOTION_FITNESS_THRESHOLD,
)
from kdexter.state_machine.security_state import SecurityStateContext


# ── Helpers ──────────────────────────────────────────────────────────────── #

def _make_si(hooks=None):
    lock = RuleLedgerLock()
    ledger = RuleLedger(lock)
    evidence = EvidenceStore()
    security = SecurityStateContext()
    counter = LoopCounter()
    queue = LoopPriorityQueue()
    loop = SelfImprovementLoop(
        rule_ledger=ledger, rule_lock=lock,
        evidence_store=evidence, security=security,
        loop_counter=counter, loop_queue=queue,
        hooks=hooks,
    )
    return loop, ledger, evidence, counter


def _make_evo(hooks=None):
    lock = RuleLedgerLock()
    ledger = RuleLedger(lock)
    evidence = EvidenceStore()
    security = SecurityStateContext()
    doctrine = DoctrineRegistry()
    counter = LoopCounter()
    queue = LoopPriorityQueue()
    loop = EvolutionLoop(
        rule_ledger=ledger, rule_lock=lock,
        evidence_store=evidence, security=security,
        doctrine=doctrine,
        loop_counter=counter, loop_queue=queue,
        hooks=hooks,
    )
    return loop, ledger, evidence, counter


# ======================================================================== #
# 1. SelfImprovementLoop
# ======================================================================== #

def test_si_default_no_proposals():
    """Default hooks produce no proposals -> finishes at PROPOSE."""
    loop, ledger, evidence, _ = _make_si()
    loop.accept_trigger("F-S-001", "STRATEGY", "HIGH")
    result = asyncio.run(loop.run())
    assert result.phase_reached == SIPhase.PROPOSE
    assert result.proposals_generated == 0
    assert result.error is None
    print("  [1] SI default no proposals  OK")


def test_si_full_cycle():
    """Full cycle with proposals that pass backtest."""
    async def fake_propose(sample):
        return [
            ImprovementProposal(
                parameter_name="stop_loss",
                current_value="0.05",
                proposed_value="0.03",
                rationale="tighter stop loss",
            ),
        ]

    hooks = SIHooks(propose=fake_propose)
    loop, ledger, evidence, _ = _make_si(hooks)
    loop.accept_trigger("F-S-001", "STRATEGY", "HIGH", incident_id="INC-TEST")
    result = asyncio.run(loop.run())

    assert result.phase_reached == SIPhase.VERIFY
    assert result.proposals_generated == 1
    assert result.proposals_accepted == 1
    assert result.rules_created == 1
    assert len(ledger.list_all()) == 1
    assert evidence.count() >= 3  # analyze + propose + backtest + rule + verify
    print("  [2] SI full cycle  OK")


def test_si_backtest_rejection():
    """Proposals below threshold are rejected."""
    async def fake_propose(sample):
        return [ImprovementProposal(
            parameter_name="x", current_value="1", proposed_value="2", rationale="test",
        )]

    async def fake_backtest(proposal):
        return 0.2  # below BACKTEST_ACCEPTANCE_THRESHOLD

    hooks = SIHooks(propose=fake_propose, backtest=fake_backtest)
    loop, ledger, evidence, _ = _make_si(hooks)
    loop.accept_trigger("F-S-002", "STRATEGY", "MEDIUM")
    result = asyncio.run(loop.run())

    assert result.phase_reached == SIPhase.BACKTEST
    assert result.proposals_generated == 1
    assert result.proposals_accepted == 0
    assert result.rules_created == 0
    print("  [3] SI backtest rejection  OK")


def test_si_risk_check_fail():
    """M-03 risk check failure aborts at PROPOSE."""
    async def fake_risk():
        return False

    async def fake_propose(sample):
        return [ImprovementProposal(parameter_name="x")]

    hooks = SIHooks(check_risk=fake_risk, propose=fake_propose)
    loop, _, _, _ = _make_si(hooks)
    loop.accept_trigger("F-S-001", "STRATEGY", "HIGH")
    result = asyncio.run(loop.run())

    assert result.phase_reached == SIPhase.FAILED
    assert "M-03" in result.error
    print("  [4] SI risk check fail  OK")


def test_si_security_check_fail():
    """M-04 security check failure aborts at APPLY."""
    async def fake_security():
        return False

    async def fake_propose(sample):
        return [ImprovementProposal(
            parameter_name="x", current_value="1", proposed_value="2", rationale="t",
        )]

    hooks = SIHooks(check_security=fake_security, propose=fake_propose)
    loop, _, _, _ = _make_si(hooks)
    loop.accept_trigger("F-S-001", "STRATEGY", "HIGH")
    result = asyncio.run(loop.run())

    assert result.phase_reached == SIPhase.FAILED
    assert "M-04" in result.error
    print("  [5] SI security check fail  OK")


def test_si_ceiling_enforcement():
    """Loop ceiling (per_incident=3) enforced."""
    loop, ledger, evidence, counter = _make_si()
    incident = "INC-CEIL"

    # Run 3 times successfully
    for _ in range(3):
        loop.accept_trigger("F-S-001", "STRATEGY", "HIGH", incident_id=incident)
        asyncio.run(loop.run())

    # 4th should hit ceiling
    loop.accept_trigger("F-S-001", "STRATEGY", "HIGH", incident_id=incident)
    result = asyncio.run(loop.run())
    assert result.phase_reached == SIPhase.FAILED
    assert "ceiling" in result.error.lower()
    print("  [6] SI ceiling enforcement  OK")


def test_si_is_active_lifecycle():
    """is_active toggles during run."""
    loop, _, _, _ = _make_si()
    assert not loop.is_active
    assert loop.current_phase == SIPhase.IDLE

    loop.accept_trigger("F-S-001", "STRATEGY", "HIGH")
    asyncio.run(loop.run())
    assert not loop.is_active  # should be inactive after run
    print("  [7] SI active lifecycle  OK")


def test_si_provenance_on_rules():
    """Rules created by SI have proper provenance (L9, incident_id)."""
    async def fake_propose(sample):
        return [ImprovementProposal(
            parameter_name="alpha", current_value="0.1",
            proposed_value="0.2", rationale="optimize alpha",
        )]

    hooks = SIHooks(propose=fake_propose)
    loop, ledger, _, _ = _make_si(hooks)
    loop.accept_trigger("F-S-001", "STRATEGY", "HIGH", incident_id="INC-PROV")
    asyncio.run(loop.run())

    rules = ledger.list_all()
    assert len(rules) == 1
    rule = rules[0]
    assert rule.provenance is not None
    assert rule.provenance.author_layer == "L9"
    assert rule.provenance.source_incident == "INC-PROV"
    print("  [8] SI provenance on rules  OK")


# ======================================================================== #
# 2. EvolutionLoop
# ======================================================================== #

def test_evo_full_cycle():
    """Full cycle: generate -> sandbox -> evaluate -> gate -> promote."""
    loop, ledger, evidence, _ = _make_evo()
    loop.accept_trigger("F-S-001", "STRATEGY", "HIGH", "PATTERN", incident_id="INC-EVO")
    result = asyncio.run(loop.run())

    assert result.phase_reached == EvoPhase.PROMOTE
    assert result.candidates_generated == 1
    assert result.candidates_sandbox_passed == 1
    assert result.candidates_gate_passed == 1
    assert result.promoted_candidate_id is not None
    assert len(ledger.list_all()) == 1
    assert evidence.count() >= 4
    print("  [9] Evo full cycle  OK")


def test_evo_sandbox_fail():
    """Candidates below fitness threshold fail sandbox."""
    async def low_fitness_sandbox(candidate):
        return SandboxResult(
            candidate_id=candidate.candidate_id,
            fitness_score=0.2,  # below SANDBOX_FITNESS_THRESHOLD
            passed_sandbox=False,
        )

    hooks = EvoHooks(sandbox=low_fitness_sandbox)
    loop, ledger, _, _ = _make_evo(hooks)
    loop.accept_trigger("F-S-001", "STRATEGY", "HIGH", "PATTERN")
    result = asyncio.run(loop.run())

    assert result.phase_reached == EvoPhase.SANDBOX
    assert result.candidates_sandbox_passed == 0
    assert len(ledger.list_all()) == 0
    print("  [10] Evo sandbox fail  OK")


def test_evo_gate_fitness_fail():
    """Candidates below promotion threshold fail gate."""
    async def mediocre_sandbox(candidate):
        return SandboxResult(
            candidate_id=candidate.candidate_id,
            fitness_score=0.55,  # above sandbox but below promotion
            passed_sandbox=True,
        )

    hooks = EvoHooks(sandbox=mediocre_sandbox)
    loop, ledger, _, _ = _make_evo(hooks)
    loop.accept_trigger("F-S-001", "STRATEGY", "HIGH", "PATTERN")
    result = asyncio.run(loop.run())

    assert result.phase_reached == EvoPhase.GATE
    assert "gate failed" in result.error.lower()
    print("  [11] Evo gate fitness fail  OK")


def test_evo_gate_security_fail():
    """M-04 security check failure at gate phase."""
    async def fail_security():
        return False

    hooks = EvoHooks(check_security=fail_security)
    loop, _, _, _ = _make_evo(hooks)
    loop.accept_trigger("F-S-001", "STRATEGY", "HIGH", "PATTERN")
    result = asyncio.run(loop.run())

    assert result.phase_reached == EvoPhase.GATE
    print("  [12] Evo gate security fail  OK")


def test_evo_risk_check_fail():
    """M-03 risk check failure at generate phase."""
    async def fail_risk():
        return False

    hooks = EvoHooks(check_risk=fail_risk)
    loop, _, _, _ = _make_evo(hooks)
    loop.accept_trigger("F-S-001", "STRATEGY", "HIGH", "PATTERN")
    result = asyncio.run(loop.run())

    assert result.phase_reached == EvoPhase.FAILED
    assert "M-03" in result.error
    print("  [13] Evo risk check fail  OK")


def test_evo_ceiling_enforcement():
    """Loop ceiling (per_incident=1) enforced."""
    loop, _, _, counter = _make_evo()
    incident = "INC-ECEIL"

    # 1st run
    loop.accept_trigger("F-S-001", "STRATEGY", "HIGH", "PATTERN", incident_id=incident)
    r1 = asyncio.run(loop.run())
    assert r1.phase_reached == EvoPhase.PROMOTE

    # 2nd should hit ceiling
    loop.accept_trigger("F-S-001", "STRATEGY", "HIGH", "PATTERN", incident_id=incident)
    r2 = asyncio.run(loop.run())
    assert r2.phase_reached == EvoPhase.FAILED
    assert "ceiling" in r2.error.lower()
    print("  [14] Evo ceiling enforcement  OK")


def test_evo_no_candidates():
    """No candidates generated -> finishes at GENERATE."""
    async def empty_generate(failure_ids):
        return []

    hooks = EvoHooks(generate=empty_generate)
    loop, _, _, _ = _make_evo(hooks)
    loop.accept_trigger("F-S-001", "STRATEGY", "HIGH", "PATTERN")
    result = asyncio.run(loop.run())

    assert result.phase_reached == EvoPhase.GENERATE
    assert result.candidates_generated == 0
    print("  [15] Evo no candidates  OK")


def test_evo_provenance_on_rules():
    """Promoted rules have proper provenance (L14, incident_id)."""
    loop, ledger, _, _ = _make_evo()
    loop.accept_trigger("F-S-001", "STRATEGY", "HIGH", "PATTERN", incident_id="INC-EPROV")
    asyncio.run(loop.run())

    rules = ledger.list_all()
    assert len(rules) == 1
    rule = rules[0]
    assert rule.provenance is not None
    assert rule.provenance.author_layer == "L14"
    assert rule.provenance.source_incident == "INC-EPROV"
    print("  [16] Evo provenance on rules  OK")


def test_evo_multiple_candidates():
    """Multiple candidates — best fitness wins."""
    async def multi_generate(failure_ids):
        return [
            StrategyCandidate(name="weak", parameters={"a": 1}),
            StrategyCandidate(name="strong", parameters={"a": 2}),
        ]

    call_count = [0]
    async def varied_sandbox(candidate):
        call_count[0] += 1
        score = 0.4 if candidate.name == "weak" else 0.8
        return SandboxResult(
            candidate_id=candidate.candidate_id,
            fitness_score=score,
            win_rate=score,
            sharpe_ratio=score * 2,
            passed_sandbox=True,
        )

    hooks = EvoHooks(generate=multi_generate, sandbox=varied_sandbox)
    loop, ledger, _, _ = _make_evo(hooks)
    loop.accept_trigger("F-S-001", "STRATEGY", "HIGH", "PATTERN")
    result = asyncio.run(loop.run())

    assert result.phase_reached == EvoPhase.PROMOTE
    assert result.candidates_generated == 2
    # "weak" fails sandbox (0.4 < 0.5), only "strong" passes
    assert result.candidates_sandbox_passed == 1
    rules = ledger.list_all()
    assert len(rules) == 1
    assert "strong" in rules[0].name
    print("  [17] Evo multiple candidates best wins  OK")


def test_evo_is_active_lifecycle():
    """is_active toggles during run."""
    loop, _, _, _ = _make_evo()
    assert not loop.is_active
    assert loop.current_phase == EvoPhase.IDLE

    loop.accept_trigger("F-S-001", "STRATEGY", "HIGH", "PATTERN")
    asyncio.run(loop.run())
    assert not loop.is_active
    print("  [18] Evo active lifecycle  OK")


# ======================================================================== #
# Runner
# ======================================================================== #

if __name__ == "__main__":
    print("\nTier 3 Tests -- Remaining Loops (Self-Improvement + Evolution)")
    print("=" * 60)

    tests = [
        ("SelfImprovementLoop", [
            test_si_default_no_proposals,
            test_si_full_cycle,
            test_si_backtest_rejection,
            test_si_risk_check_fail,
            test_si_security_check_fail,
            test_si_ceiling_enforcement,
            test_si_is_active_lifecycle,
            test_si_provenance_on_rules,
        ]),
        ("EvolutionLoop", [
            test_evo_full_cycle,
            test_evo_sandbox_fail,
            test_evo_gate_fitness_fail,
            test_evo_gate_security_fail,
            test_evo_risk_check_fail,
            test_evo_ceiling_enforcement,
            test_evo_no_candidates,
            test_evo_provenance_on_rules,
            test_evo_multiple_candidates,
            test_evo_is_active_lifecycle,
        ]),
    ]

    total = 0
    passed = 0
    failed_tests = []

    for section, fns in tests:
        print(f"\n--- {section} ---")
        for fn in fns:
            total += 1
            try:
                fn()
                passed += 1
            except Exception as e:
                failed_tests.append((fn.__name__, str(e)))
                print(f"  FAILED: {fn.__name__}: {e}")

    print(f"\n{'=' * 60}")
    print(f"Results: {passed}/{total} passed")
    if failed_tests:
        print("FAILED:")
        for name, err in failed_tests:
            print(f"  - {name}: {err}")
        sys.exit(1)
    else:
        print("All tests PASSED")
