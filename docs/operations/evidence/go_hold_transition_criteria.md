# GO / HOLD Transition Criteria

Date: 2026-04-01
Scope: Phase 1-7 Autonomous Self-Evolving System
Current Status: **CONDITIONAL GO (CG-1 Achieved)**

---

## 5-Level Authorization Model

```
BUILD COMPLETE ─── GOVERNANCE COMPLETE ─── CG-1: KILL-SWITCH PROVEN
                                              │
                                        CG-2: SHADOW PROVEN
                                              │
                                        OPERATOR AUTHORIZED
                                              │
                                        LIVE ELIGIBLE
```

---

## Level Transition Criteria

### BUILD COMPLETE → GOVERNANCE COMPLETE

| # | Criterion | Evidence |
|---|-----------|----------|
| GC-1 | All CRs registered and SEALED | g3_change_intake_registry.md: CR-038~044 SEALED |
| GC-2 | Execution path contamination = 0 | AST scan + git diff confirmed |
| GC-3 | dry_run=True enforced at 2 layers | OrchestratorConfig + GovernanceGate |
| GC-4 | Promotion requires operator | GovernanceGate → PENDING_OPERATOR for PROMOTED |
| GC-5 | All tests pass | 3454+ PASS (2 pre-existing flaky excluded) |

**Status: ACHIEVED**

### GOVERNANCE COMPLETE → CG-1: KILL-SWITCH PROVEN

| # | Criterion | Evidence |
|---|-----------|----------|
| CG1-1 | R-1: Orchestrator stoppable | 3/3 tests PASS |
| CG1-2 | R-2: dry_run enforceable | 3/3 tests PASS |
| CG1-3 | R-3: Governance block-all works | 2/2 tests PASS |
| CG1-4 | R-4: Mass retirement works | 3/3 tests PASS |
| CG1-5 | R-5: Paper trading haltable | 3/3 tests PASS |
| CG1-6 | R-6: Code rollback safe | 2/2 tests PASS |
| CG1-7 | Recovery clean | 3/3 tests PASS |
| CG1-8 | R-04 decision documented | ACCEPT with mitigations |

**Status: ACHIEVED** (19/19 rehearsal tests PASS)

### CG-1 → CG-2: SHADOW PROVEN

| # | Criterion | Threshold |
|---|-----------|-----------|
| CG2-1 | Shadow duration | >= 7 calendar days |
| CG2-2 | Orchestrator crashes | 0 |
| CG2-3 | Optimizer drift | < 20% daily for 7 days |
| CG2-4 | Governance block rate | > 0% (gates work) |
| CG2-5 | PENDING_OPERATOR | < 20 per day |
| CG2-6 | Health warnings | < 2 per day average |
| CG2-7 | Fitness trend | Non-decreasing 3-day MA |
| CG2-8 | Registry growth | >= 1 entry per 2 days |
| CG2-9 | Daily reconciliation | 4/4 checks pass |

**Status: NOT STARTED**

### CG-2 → OPERATOR AUTHORIZED

| # | Criterion | Source |
|---|-----------|--------|
| OA-1 | Shadow verdict = PASS | shadow_run_template.md |
| OA-2 | Kill-switch rehearsal current | killswitch_rehearsal_evidence.md |
| OA-3 | R-04 mitigations in place | r04_decision_memo.md |
| OA-4 | Operator checklist reviewed | operator_authorization_checklist.md |
| OA-5 | At least 1 mock approval completed | shadow daily log |
| OA-6 | A (Decision Authority) signs off | Manual signature |

**Status: NOT STARTED**

### OPERATOR AUTHORIZED → LIVE ELIGIBLE

| # | Criterion | Threshold |
|---|-----------|-----------|
| LE-1 | ESCROW_PROMOTED implemented (recommended) | New CR filed and sealed |
| LE-2 | Strategy Passport implemented (recommended) | New CR filed and sealed |
| LE-3 | DB persistence for lifecycle/governance (if R-04 escalated) | New CR filed and sealed |
| LE-4 | Production deployment review | Separate review process |
| LE-5 | Capital allocation limit set | Manual configuration |

**Status: NOT STARTED** (future phase)

---

## HOLD Triggers (any level)

| Trigger | From Level | Action |
|---------|-----------|--------|
| Kill-switch rehearsal fails | Any | HOLD until re-rehearsed |
| Execution path contamination detected | Any | HOLD until fixed |
| dry_run=True overridden | Any | IMMEDIATE STOP |
| Shadow run FAIL | CG-2 attempt | HOLD + investigate |
| Unplanned restart > 2 during shadow | CG-2 | HOLD + escalate R-04 |
| Circuit breaker triggered | Any | HOLD until resolved |
| Operator rejects 3+ consecutive strategies | OA | HOLD + review evolution quality |

---

## Current Position

```
[X] BUILD COMPLETE
[X] GOVERNANCE COMPLETE
[X] CG-1: KILL-SWITCH PROVEN
[~] CG-2: SHADOW PROVEN         ← CG-2A Proven / CG-2B Not Proven → EXTEND
[ ] OPERATOR AUTHORIZED
[ ] LIVE ELIGIBLE
```

**Status**: 7-day Shadow Run completed (2026-04-01). CG-2A (operational safety) PROVEN. CG-2B (strategy production/governance flow) NOT YET PROVEN due to Inactive Market Regime. Recommended: EXTEND via Option B (CR + redesign).
See: `shadow_7day_final_verdict.md`
