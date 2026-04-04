# Shadow Run — Day 0 Baseline Snapshot

Date: 2026-04-01
Purpose: Fix the exact system state before shadow run begins
Baseline Commit: `d813758`

---

## System Configuration

| Item | Value | Locked? |
|------|-------|---------|
| Mode | Mode 1 (Read-Only) | YES |
| dry_run | `True` (OrchestratorConfig + GovernanceGate) | YES |
| Promotion policy | `PENDING_OPERATOR` | YES |
| Demotion policy | Auto-approved (fail-closed) | YES |
| auto_approve_threshold | 0.8 (irrelevant while dry_run=True) | YES |

## Codebase State

| Item | Value |
|------|-------|
| Baseline commit | `d813758` |
| Phase 1-7 CRs | CR-038~CR-044, all SEALED |
| Total services | 32 (Phase 1-7) |
| Total tests | 3451+ PASS |
| Flaky excluded | 2 (pre-existing, non-Phase 1-7) |
| Execution path changes | 0 |
| Write path | 0 (all Phase 7 pure computation) |

## Kill-Switch Readiness

| Kill-Switch | Rehearsal Status | Evidence |
|-------------|-----------------|----------|
| R-1: Stop orchestrator | PASS (3/3) | test_killswitch_rehearsal.py |
| R-2: Force dry_run | PASS (3/3) | test_killswitch_rehearsal.py |
| R-3: Block-all governance | PASS (2/2) | test_killswitch_rehearsal.py |
| R-4: Mass retirement | PASS (3/3) | test_killswitch_rehearsal.py |
| R-5: Paper trading halt | PASS (3/3) | test_killswitch_rehearsal.py |
| R-6: Code rollback | PASS (2/2) | test_killswitch_rehearsal.py |

## Risk Register

| Risk | Status |
|------|--------|
| R-01: Over-optimization | OPEN — shadow will provide drift evidence |
| R-04: In-memory state loss | ACCEPTED with 5 mitigations |

## Shadow Run Parameters

| Parameter | Value |
|-----------|-------|
| Exchange | Binance (testnet or mainnet read-only) |
| Symbol | BTC/USDT |
| Data collection interval | 5 minutes (OHLCV) |
| Sentiment collection interval | 1 hour |
| Evolution config | n_islands=3, pop=6, max_gen=3, seed=42 |
| Lookback | 50 bars |
| Daily review time | 09:00 KST |
| Duration | 7 calendar days minimum |
| Start date | TBD (upon A's approval) |

## Documents in Force

| Document | Path |
|----------|------|
| Operational Readiness Review | evidence/operational_readiness_review.md |
| Kill-Switch Evidence | evidence/killswitch_rehearsal_evidence.md |
| R-04 Decision Memo | evidence/r04_decision_memo.md |
| Shadow Run Template | evidence/shadow_run_template.md |
| Operator Checklist | evidence/operator_authorization_checklist.md |
| GO/HOLD Criteria | evidence/go_hold_transition_criteria.md |

---

## Baseline Verification Signature

```
Baseline fixed at commit: d813758
Tests passing: 3451+
Kill-switch rehearsal: 19/19 PASS
Execution path changes: 0
Write path: 0
dry_run: True (2-layer)
Promotion: PENDING_OPERATOR

Prepared by: B (Implementer)
Review required: A (Decision Authority)
Date: 2026-04-01
```
