# R-04 Decision Memo: In-Memory State Loss Risk

Date: 2026-04-01
Risk ID: R-04
Severity: HIGH
Decision: **ACCEPT with Mitigations**

---

## 1. Risk Description

All Phase 7 operational state is held in-memory:
- `AutonomousOrchestrator.lifecycle.records` — lifecycle state per genome
- `AutonomousOrchestrator.governance.decision_log` — all governance decisions
- `PaperTradingBridge.sessions` — active paper trading sessions
- `StrategyRegistry.entries` — hall of fame entries
- `AdvancedStrategyRunner` island populations

If the process restarts, all state is lost.

## 2. Impact Analysis

| Component | State Lost | Operational Impact |
|-----------|-----------|-------------------|
| Lifecycle records | All genome state history | Genomes must be re-registered; promoted strategies lose status |
| Governance log | All approval decisions | Audit trail gap; no evidence of past decisions |
| Paper sessions | Active trade records | Paper trading progress reset; incomplete sessions lost |
| Registry | Hall of fame entries | Must re-evolve to rebuild; no continuity |
| Evolution state | Island populations | Can restore from EvolutionCheckpoint (Phase 5 already handles this) |

## 3. Why Accept (Not Resolve Now)

### Reason 1: No Live Capital at Risk
In Mode 1 (dry_run=True), no real money is involved. State loss causes
operational inconvenience, not financial loss.

### Reason 2: Evolution State Already Has Persistence
Phase 5's `EvolutionStateManager` already provides checkpoint save/load.
The most expensive state to reconstruct (evolved populations) is already covered.

### Reason 3: Resolution Requires Schema Change
Adding DB persistence for lifecycle/governance/paper sessions would require:
- New Alembic migration (schema change)
- New ORM models
- Async session management in pure-computation services

This violates the "no execution path changes" constraint for Phase 1-7.

### Reason 4: Shadow Run Duration is Short
The 7-day shadow run period is short enough that manual re-initialization
is acceptable if a restart occurs.

## 4. Mitigations

| # | Mitigation | Implementation |
|---|-----------|----------------|
| M-1 | **EvolutionCheckpoint auto-save** | Already implemented — `AdvancedRunnerResult.checkpoint` is populated on every evolution run |
| M-2 | **Orchestrator summary logging** | `orchestrator.get_summary()` logged every cycle — log survives restart |
| M-3 | **Governance decision logging** | Every `governance_decision` structlog event persists to log files |
| M-4 | **Manual state re-initialization** | On restart, operator can re-register known genomes and re-start paper sessions |
| M-5 | **Shadow run restart protocol** | If restart during shadow, extend shadow duration by restart-gap hours |

## 5. Monitoring During Shadow

| What to Watch | How | Action Threshold |
|--------------|-----|-----------------|
| Process uptime | OS-level monitoring | Any restart = log incident |
| Lifecycle record count | `len(orchestrator.lifecycle.records)` per cycle log | Drop to 0 = restart detected |
| Governance log size | `len(orchestrator.governance.decision_log)` per cycle log | Drop to 0 = restart detected |
| Paper session count | `len(bridge.sessions)` per cycle log | Drop to 0 = restart detected |

## 6. Future Resolution Path (Post-Shadow)

If shadow run demonstrates that restarts cause operational problems,
file a new CR to add DB persistence for:
- `LifecycleRecord` → new ORM model
- `GovernanceDecision` → new ORM model
- `PaperSession` → new ORM model

This would be a Phase 8 enhancement, NOT a modification of Phase 1-7.

## 7. Decision

**ACCEPT** — R-04 is accepted as a known limitation for the shadow run period.
The combination of:
- No live capital risk (Mode 1)
- Evolution checkpointing (Phase 5)
- Structured logging (audit trail survives)
- Short shadow duration (7 days)

makes this an acceptable operational risk.

**Condition**: If the shadow run experiences >2 unplanned restarts, escalate
to RESOLVE by filing a new CR for persistence.

---

Signed: B (Implementer)
Review Required: A (Decision Authority)
