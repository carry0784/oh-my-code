# K-V3 System Final Constitution

**Card**: C-46 (System Final Constitution)
**Type**: Supreme Institutional Document
**Date**: 2026-03-25
**Baseline at seal**: 1631 passed, 0 failed

---

## Preamble

This document is the supreme constitutional authority for the K-V3 system. All subsystem seals, layer boundaries, and operational rules are subordinate to this constitution. No card, feature, or refactor may violate this document without an explicit constitutional amendment card.

---

## Article 1: Layer Hierarchy

The system is organized into the following layers, listed in order of constitutional authority:

```
1. GOVERNANCE (supreme)
2. ENGINE (core runtime)
3. EXECUTION (trade pipeline)
4. NOTIFICATION (observation + delivery)
5. RETRY (bounded deferred resend)
6. DASHBOARD (read-only display)
```

### 1.1 Authority Rule

Higher layers have authority over lower layers. No lower layer may:

- Override a higher layer's decision
- Mutate a higher layer's state
- Bypass a higher layer's gate
- Self-promote to higher authority

### 1.2 Isolation Rule

Each layer operates within its defined scope. Cross-layer interaction is permitted only through documented interfaces and only in the direction of authority (higher commands, lower obeys or reports).

---

## Article 2: Sealed Subsystems

The following subsystems are institutionally sealed:

| Subsystem | Seal Document | Lock Card |
|-----------|--------------|-----------|
| Engine (Card B) | `engine_layer_seal.md` | Card B |
| Retry Layer | `retry_layer_final_seal.md` | C-40/C-41 |
| Notification Layer | `notification_layer_seal.md` | C-42 |
| Execution Layer | `execution_layer_seal.md` | C-43 |
| Engine Layer | `engine_layer_seal.md` | C-44 |
| Governance Layer | `governance_layer_seal.md` | C-45 |

### 2.1 Sealed Subsystem Rule

A sealed subsystem may only be modified by an explicit constitutional card that:

- Has a card number
- Declares scope and blast radius
- Includes constitutional comparison review
- Includes forbidden pattern scan
- Includes full regression evidence
- Passes all existing lock tests
- Receives explicit GO

### 2.2 Seal Precedence

If a conflict exists between a feature card and a seal document, the seal document prevails.

---

## Article 3: Card System

### 3.1 Card B (Engine Baseline)

- **Status**: SEALED
- **Tests**: 57
- **Rule**: Modification forbidden. New card required for any change.
- **Sealed contracts**: packaging, singleton, gate, evidence, idempotent, logging, stats

### 3.2 C-Series Cards

- **Status**: ALL GO (C-01 through C-46)
- **Tests**: 1017 (C-series total)
- **Rule**: Each card is individually sealed upon GO. Reopening requires a new card.

### 3.3 Card Rules

1. One card = one task. Mixed work forbidden.
2. Start only from clean baseline. If regression dirty, create repair card first.
3. Sealed card modification requires a new card.
4. Card scope expansion forbidden mid-implementation.
5. Each card must include constitutional comparison review.

---

## Article 4: Execution SSOT

### 4.1 Retry Execution

`execute_single_plan()` in `retry_executor.py` is the sole execution SSOT for all retry paths.

- Manual, auto, and operator paths must converge on this function.
- Sender ownership is centralized in this function.
- State mutation is centralized in this function.
- Creating duplicate executors is forbidden.

### 4.2 Trade Execution

Orders are submitted only through the execution layer services (`order_service.py`) via exchange factory clients.

- Direct exchange API calls outside the factory are forbidden.
- Order submission requires prior signal approval and risk check.

### 4.3 Notification Execution

Notification delivery goes through the sender registry (`notification_sender.py`).

- Channel senders are registered, not hardcoded.
- All sends are fail-closed.
- Receipt is always recorded.

---

## Article 5: State Ownership

| State | Owner | Consumers (read-only) |
|-------|-------|----------------------|
| Trust State | Engine (state_machine) | Dashboard, Notification |
| Work State | Engine (state_machine) | Dashboard, Notification |
| Security State | Engine (state_machine) | Dashboard, Notification |
| Governance Gates | Engine (gates) | Dashboard, Readiness Probes |
| Loop Health | Engine (loop_monitor) | Dashboard |
| Order/Position/Trade | Execution (services) | Dashboard |
| Retry Plans | Retry (plan_store) | Operator Endpoint |
| Receipts | Notification (receipt_store) | Dashboard |

### 5.1 State Mutation Rule

Only the owning layer may mutate its state. Consuming layers have read-only access. Violation of this rule is constitutionally invalid.

---

## Article 6: Fail-Closed Doctrine

Every component in the system must be fail-closed:

1. **Gate failure** -> deny (not allow)
2. **Sender failure** -> record failure receipt (not silent skip)
3. **Policy failure** -> use safe default (not bypass)
4. **Store failure** -> reject operation (not corrupt state)
5. **Budget exhaustion** -> deny retry (not continue)
6. **Unknown state** -> treat as unavailable (not as healthy)

Silent failure, silent bypass, and silent fallback are constitutionally forbidden.

---

## Article 7: Forbidden Patterns (System-Wide)

The following patterns are forbidden across the entire system:

### 7.1 Information Exposure

- `chain_of_thought` in production responses
- `raw_prompt` in production responses
- `internal_reasoning` in production responses
- `debug_trace` in production responses
- `agent_analysis` in production responses

### 7.2 Autonomous Escalation

- Self-promoting authority
- Bypassing governance gates
- Overriding risk management
- Silent autonomous trading

### 7.3 Hidden Automation

- Undeclared background daemons
- Import-time side effects that execute logic
- Startup hooks that bypass constitutional review
- Hidden schedulers or polling loops

### 7.4 Cross-Layer Violations

- Lower layers mutating higher layer state
- Observation layers influencing decisions
- Notification outcomes affecting trading
- Retry outcomes affecting governance

---

## Article 8: Dashboard Constitution

The dashboard (`app/api/routes/dashboard.py` + `app/templates/dashboard.html`) is the primary operator interface.

### 8.1 Dashboard Rules

1. Read-only: No write actions, no trade execution, no order submission
2. Missing data shown as "-" or "NOT AVAILABLE", never faked as 0
3. Fail-closed: Backend unavailable shown as explicit state
4. Additive only: New panels are added, existing panels are preserved
5. No raw debug/reasoning exposure

### 8.2 Dashboard Panels (C-Series)

| Panel | Card | Purpose |
|-------|------|---------|
| Loop Ceiling Monitor | C-02 | Loop health display |
| Health/Ready/Startup | C-03 | Probe status |
| Degraded Status | C-04 | Partial failure display |
| Quote Feed | C-05 | Real-time quote display |
| Venue Status | C-06 | Exchange connectivity |
| Incident Overlay | C-07 | Highest severity display |
| Freshness Timeline | C-08 | Data age display |
| Source Provenance | C-09 | Data source tracking |
| Operator Triage | C-10 | Guided investigation |
| Handoff Receipt | C-11 | Operator handoff |
| Incident Chronology | C-12 | Event timeline |
| Flow Review | C-23 | Notification flow log |
| Receipt Review | C-17 | Delivery receipts |
| Replay UI | C-26 | Audit replay |

---

## Article 9: Testing Constitution

### 9.1 Baseline Rule

The system must maintain a clean baseline at all times. Current baseline: **1631 passed, 0 failed**.

### 9.2 Regression Rule

Every card must pass full regression before GO. Regression failure blocks card approval.

### 9.3 Card B Preservation

All 57 Card B tests must pass at all times. Card B test modification is forbidden.

### 9.4 Boundary Lock Tests

C-40 execution boundary lock tests (25 tests) enforce structural invariants. These tests must pass unmodified for any retry-layer change.

---

## Article 10: Amendment Procedure

### 10.1 Constitution Amendment

This constitution may only be amended by:

1. A dedicated constitutional amendment card
2. Full system regression verification
3. Impact analysis on all sealed subsystems
4. Explicit justification for each amended article
5. Explicit GO from review process

### 10.2 Subsystem Seal Amendment

Individual subsystem seals follow their own amendment rules as defined in their seal documents. This constitution takes precedence over individual seal documents in case of conflict.

### 10.3 Emergency Amendment

No emergency procedure exists. All amendments follow the standard constitutional card process. Claims of emergency do not justify bypassing amendment procedure.

---

## Article 11: Final Declaration

The K-V3 system is constitutionally governed as of this document.

- **Governance** is supreme and may not be overridden.
- **Engine** is sealed and may not be modified without constitutional card.
- **Execution** is bounded by governance and risk management.
- **Notification** is observational and subordinate.
- **Retry** is bounded, unified, and institutionally sealed.
- **Dashboard** is read-only and additive-only.

All layers, modules, and future cards are bound by this constitution.

Any action that violates this constitution is **invalid**, regardless of:

- Test results
- Operational convenience
- Performance justification
- Feature urgency

**This constitution is the supreme authority of the K-V3 system.**

---

*Ratified by Card C-46. This document supersedes all prior informal agreements.*
