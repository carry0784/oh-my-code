# Engine Layer Final Seal

**Card**: C-44 (Engine Layer Seal)
**Type**: Institutional Seal
**Date**: 2026-03-25
**Baseline at seal**: 1631 passed, 0 failed

---

## 1. Purpose

The engine layer (`src/kdexter/`) is the **core autonomous intelligence system** that orchestrates loops, state machines, gates, strategy, and governance.

- Engine is the highest-authority runtime layer.
- Engine owns loop execution, trust decay, state transitions, and governance enforcement.
- Engine is **sealed as Card B** and must not be modified without a dedicated constitutional card.
- Engine state is consumed by dashboard/notification layers in read-only mode.

---

## 2. System Scope

### Subsystems

| Subsystem | Path | Role |
|-----------|------|------|
| Bootstrap | `bootstrap.py` | System initialization |
| Governance | `governance/` | Constitution (B1), orchestration (B2), doctrine |
| Gates | `gates/` | Gate evaluator, registry, criteria, hooks |
| Engines | `engines/` | Loop monitor, trust decay, cost controller, scheduler, harness, evaluation, progress, research, knowledge, intent drift, failure router, override controller, parallel agent, rule conflict, spec lock, budget evolution, completion, clarify spec, human decision |
| State Machines | `state_machine/` | Security state, trust state, work state |
| Strategy | `strategy/` | Position sizer, execution cell, pipeline, risk filter, signal |
| Loops | `loops/` | Main loop, evolution loop, recovery loop, self-improvement loop, concurrency |
| Ledger | `ledger/` | Mandatory ledger, forbidden ledger, rule ledger |
| Audit | `audit/` | Evidence store, memory backend, SQLite backend |
| TCL | `tcl/` | Trade command layer, exchange adapters |
| Config | `config/` | Thresholds |
| Layers | `layers/` | Registry |

### Explicit Non-Scope

- HTTP endpoint serving (belongs to app layer)
- Dashboard rendering (belongs to app layer)
- Notification delivery (belongs to notification layer)
- Retry management (belongs to retry layer)

---

## 3. Sealed Status

The engine layer is **Card B SEALED** (57 contracts).

### Sealed Contracts

- packaging
- singleton
- gate
- evidence
- idempotent
- logging
- stats

### Modification Rule

**No engine layer modification is permitted without creating a new constitutional card.**

All C-series cards (C-01 through C-41) have maintained non-contact with `src/kdexter/`. This invariant is permanent.

---

## 4. Allowed Responsibilities

1. Own and execute main operational loops
2. Manage trust, work, and security state machines
3. Enforce governance gates and constitutional rules
4. Track loop health, ceiling pressure, and incidents
5. Maintain audit evidence and ledger records
6. Execute strategy pipelines and position sizing
7. Route failures and manage recovery loops
8. Control costs and budgets at engine level

---

## 5. Forbidden Responsibilities (from app/notification/retry perspective)

1. Engine must never be modified by dashboard, notification, or retry layers
2. Engine state must not be mutated by observation layers
3. Engine loops must not be controlled by notification outcomes
4. Engine gates must not be bypassed by retry logic
5. Engine evidence must not be forged by external layers

---

## 6. Consumption Rules

External layers (app, notification, retry) may **consume** engine state:

- Read loop monitor data for dashboard display
- Read trust/work/doctrine state for dashboard display
- Read gate status for readiness probes
- Read evidence availability for provenance display

External layers must **never**:

- Write to engine state
- Call engine methods that cause state transitions
- Import engine modules for execution purposes
- Mock engine modules in ways that affect production behavior

---

## 7. Invariants

1. Card B sealed contracts are permanent
2. `src/kdexter/` is not imported by retry layer
3. `src/kdexter/` is not mutated by notification layer
4. Engine state is consumed read-only by dashboard
5. All 57 Card B tests must pass at all times
6. Engine modification requires a new constitutional card

---

## 8. Amendment Rule

The engine layer is the most protected subsystem. Amendment requires:

1. A dedicated constitutional card
2. Full Card B regression verification
3. Sealed contract preservation proof
4. Blast radius analysis
5. Explicit GO from review process

---

*Sealed by Card C-44.*
