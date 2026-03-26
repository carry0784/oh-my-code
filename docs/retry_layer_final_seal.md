# Retry Layer Final Seal

**Card**: C-41
**Type**: Institutional Seal (not a feature card)
**Date**: 2026-03-25
**Baseline at seal**: 1631 passed, 0 failed
**Status**: SEALED

---

## 1. Purpose

The retry layer exists to handle **bounded deferred resend attempts** for failed notification deliveries. Its purpose is narrowly defined:

- Retry exists to reattempt transient notification delivery failures.
- Retry is subordinate to policy, budget, and execution constitution.
- Retry is **not** an autonomous trading engine.
- Retry is **not** a scheduler platform.
- Retry is **not** a general workflow engine.
- Retry is **not** an event processing system.

The retry layer serves the notification pipeline only. It has no authority over trading decisions, signal generation, engine state, or any domain outside notification delivery reattempts.

---

## 2. System Scope

### Allowed Scope

| Capability | Card |
|------------|------|
| Eligibility classification | C-29 |
| Deferred retry queue storage | C-30 |
| Bounded retry execution | C-31 |
| Manual retry pass wiring | C-32 |
| Operator-triggered retry pass | C-33 |
| Flow-to-retry bridge (enqueue only) | C-34 |
| Retry policy gate | C-35 |
| Retry budget enforcement | C-36 |
| Retry metrics observation | C-37 |
| Gated auto retry orchestration | C-38 |
| Executor path unification | C-39 |
| Execution boundary lock | C-40 |

### Explicit Non-Scope

The retry layer must **never** expand into:

- Trading decision logic
- Signal generation or evaluation
- Engine control or state management
- Sealed layer mutation
- Arbitrary workflow orchestration
- Direct sender ownership outside executor
- Background daemon or scheduler platform
- General-purpose job queue
- Event-driven reactive automation

---

## 3. Allowed Responsibilities

The retry layer is permitted to:

1. Store retryable deferred plans in an append-only ledger
2. Read pending retry plans for review or execution
3. Filter plans by eligibility time window
4. Execute bounded retry attempts through `execute_single_plan()` only
5. Enforce retry gate conditions before execution
6. Enforce retry budget limits before execution
7. Record retry metrics for observational purposes only
8. Expose operator/manual retry entrypoint for explicit invocation
9. Run bounded auto retry under explicit gate/budget/orchestration law
10. Classify delivery outcomes as retryable or permanent
11. Suppress duplicate retry plans by channel+incident key
12. Expire plans by TTL or capacity eviction

Each responsibility is narrow and bounded. No responsibility grants open-ended authority.

---

## 4. Forbidden Responsibilities

The retry layer must **never**:

1. Make trading judgments or influence trading decisions
2. Generate, evaluate, or modify signals
3. Execute engine commands or control engine state
4. Own sender outside `execute_single_plan()` in `retry_executor.py`
5. Mutate retry plan state outside `execute_single_plan()` in `retry_executor.py`
6. Create hidden or duplicate executor functions
7. Bypass the policy gate
8. Bypass the retry budget
9. Bypass the execution SSOT
10. Self-register startup execution hooks
11. Run hidden daemon, worker, scheduler, or polling loop
12. Own a global automation platform
13. Silently retry without evidence (receipt/metrics)
14. Mutate unrelated system state
15. Import or call `get_sender()` outside `retry_executor.py`
16. Call `mark_executed()` or `mark_expired()` outside `retry_executor.py`
17. Accept execution authority from metrics, budget, or gate layers
18. Expand scope beyond notification delivery reattempts

Violation of any item is grounds for immediate NO-GO.

---

## 5. Execution Constitution

### The Law

`execute_single_plan()` defined in `app/core/retry_executor.py` is the **sole execution SSOT** (Single Source of Truth) for the retry layer.

### Binding Rules

- All manual retry execution must pass through `execute_single_plan()`
- All auto retry execution must pass through `execute_single_plan()`
- All operator-triggered retry execution must pass through `execute_single_plan()`
- Sender ownership (`get_sender()`) belongs only to `execute_single_plan()`
- State mutation (`mark_executed()`, `mark_expired()`) belongs only to `execute_single_plan()`
- Orchestration layers may coordinate but may **not** execute directly
- Bridge may enqueue but may **not** execute
- Operator endpoint may trigger but may **not** execute directly
- Metrics may observe but may **not** execute
- Gate may allow/deny but may **not** execute
- Budget may allow/deny but may **not** execute

### Identification

- Manual path uses `reason_prefix="retry"`
- Auto path uses `reason_prefix="auto_retry"`
- Both converge on the same `execute_single_plan()` function

---

## 6. Control Order Constitution

### Required Order

```
gate.evaluate() --> budget.check() --> execute_single_plan() --> metrics.record()
```

### Forbidden Orders

| Forbidden Path | Reason |
|---------------|--------|
| gate -> sender | Gate has no execution authority |
| budget -> sender | Budget has no execution authority |
| orchestrator -> sender | Orchestrator has no execution authority |
| metrics -> sender | Metrics has no execution authority |
| bridge -> sender | Bridge has no execution authority |
| operator -> sender | Operator endpoint has no execution authority |
| state mutation before execution law | State changes only inside SSOT |

The execution SSOT cannot be bypassed regardless of the caller's identity or urgency.

---

## 7. Boundary Map

| Module | File | Role | Allowed Authority | Forbidden Authority |
|--------|------|------|-------------------|---------------------|
| Retry Policy | `delivery_retry_policy.py` | Classify eligibility | Check retryable/permanent | Execute, send, mutate store |
| Plan Store | `retry_plan_store.py` | Store deferred plans | Enqueue, query, state transition methods | Execute retries, call sender |
| Executor | `retry_executor.py` | **SSOT execution** | Call sender, mutate plan state, define `execute_single_plan` | Trading logic, engine control |
| Flow Wiring | `notification_flow.py` | Manual retry entrypoint | Call `execute_retry_pass` | Call sender directly, call `execute_single_plan` directly |
| Operator Endpoint | `operator_retry.py` | HTTP trigger | Call `run_manual_retry_pass` | Call sender, call executor directly |
| Bridge | `flow_retry_bridge.py` | Enqueue failed deliveries | Evaluate eligibility, enqueue to store | Execute retries, call sender |
| Policy Gate | `retry_policy_gate.py` | Allow/deny retry pass | Evaluate system conditions | Execute retries, call sender |
| Budget | `retry_budget.py` | Allow/deny per-plan | Track sliding window usage | Execute retries, call sender |
| Metrics | `retry_metrics.py` | Observe outcomes | Record counters | Execute retries, influence decisions |
| Orchestrator | `auto_retry_orchestrator.py` | Coordinate auto retry | Call gate, budget, `execute_single_plan`, metrics | Own sender, own executor, mutate store directly |

---

## 8. Invariants

The following invariants are permanent and unconditional:

1. **State transition**: `pending -> executed` or `pending -> expired` only. No other transitions from pending.
2. **No duplicate executor**: `execute_single_plan()` is defined in exactly one file.
3. **No sender bypass**: `get_sender()` is called only inside `retry_executor.py` for retry execution.
4. **No store bypass**: `mark_executed()` and `mark_expired()` are called only inside `retry_executor.py`.
5. **No import side effect**: No retry module executes logic on import.
6. **No startup side effect**: No retry module registers startup hooks.
7. **No background hidden loop**: No retry module contains `while True`, daemon, or polling.
8. **Manual and auto paths share SSOT**: Both converge on `execute_single_plan()`.
9. **Retry layer does not own trading logic**: No signal, strategy, or engine code.
10. **Retry layer remains bounded**: Every execution pass has `max_executions` limit.
11. **Gate before execution**: Policy gate is evaluated before any execution.
12. **Budget before execution**: Budget is checked per-plan before execution.
13. **Metrics are observational only**: Metrics never influence execution decisions.
14. **Fail-closed everywhere**: Errors result in denial/skip, never in silent continuation.

---

## 9. Change Constitution for Future Cards

### Mandatory Rules

Any future card touching the retry layer must:

1. **Reuse `execute_single_plan()`** for all execution paths
2. **Not create a new executor** function or class
3. **Not use `get_sender()` directly** outside `retry_executor.py`
4. **Not mutate plan state directly** outside `retry_executor.py`
5. **Declare** in the card proposal:
   - Purpose
   - Scope
   - Blast radius (which modules are affected)
   - Affected invariants
   - Rollback plan
6. **Include constitutional comparison review** in submission
7. **Include forbidden pattern scan** in submission
8. **Include full regression evidence** in submission
9. **Pass all C-40 boundary lock tests** without modification

### Immediate NO-GO Triggers

A retry-layer card is automatically NO-GO if:

- A new execution path appears outside SSOT
- A new sender ownership appears outside executor
- State mutation escapes executor
- Hidden automation appears (daemon, scheduler, polling)
- Startup or import side effect appears
- Retry becomes a general automation engine
- Scope expands beyond retry constitution
- C-40 boundary lock tests are modified to pass

### Constitutional Status

The retry layer is a **sealed subsystem**. It may be modified only by an explicit constitutional card that:

- Has a card number
- Has a constitutional comparison review
- Has a forbidden pattern scan
- Has regression evidence
- Passes all existing boundary lock tests
- Receives explicit GO from the review process

---

## 10. GO / NO-GO Criteria

### GO Conditions (all must be true)

- [ ] SSOT (`execute_single_plan()`) preserved
- [ ] No new execution bypass
- [ ] No new hidden executor
- [ ] No sender/store bypass
- [ ] Boundedness preserved (max_executions enforced)
- [ ] Side-effect-free preserved (no import/startup effects)
- [ ] Gate/budget control order preserved
- [ ] Manual/auto path unification preserved
- [ ] Full regression clean
- [ ] C-40 boundary lock tests pass unmodified

### NO-GO Conditions (any one triggers NO-GO)

- New execution path outside SSOT
- New sender ownership outside executor
- State mutation escapes executor
- Hidden automation (daemon/scheduler/worker/polling)
- Startup or import side effect
- Retry becomes general automation engine
- Scope expansion beyond retry constitution
- C-40 tests modified to accommodate bypass
- Invariant violation without explicit constitutional amendment

---

## 11. Final Seal Statement

The Retry Layer is **institutionally sealed** as of Card C-41.

- **Execution SSOT is locked**: `execute_single_plan()` is the sole execution boundary.
- **Sender ownership is centralized**: Only `retry_executor.py` may call `get_sender()`.
- **State mutation is centralized**: Only `retry_executor.py` may call `mark_executed()`/`mark_expired()`.
- **Manual and auto paths are unified**: Both converge on the same SSOT.
- **Future drift is constitutionally restricted**: Any bypass is invalid and must be rejected.
- **Boundary enforcement is automated**: C-40 tests detect violations structurally.

Any card that violates this seal without explicit constitutional amendment is **invalid** and must receive **NO-GO**.

---

## 12. Retry Layer Amendment Rule

Changes to the retry layer are governed by the following amendment procedure:

1. **No amendment without a card**: Every retry-layer change requires an explicit card number (e.g., C-XX).
2. **No amendment without constitutional review**: The card must include a full constitutional comparison review against this document.
3. **No amendment without forbidden pattern scan**: The card must scan `app/` for all forbidden patterns listed in Section 4.
4. **No amendment without regression evidence**: The card must include `pytest -q` output showing all tests pass.
5. **No amendment without boundary lock verification**: All C-40 execution boundary lock tests must pass unmodified.
6. **No silent amendment**: Any change to this seal document itself requires a dedicated amendment card with explicit justification.
7. **No retroactive authorization**: A change cannot be approved after the fact by claiming it was "implicitly allowed."

**Amendment authority**: Only an explicit constitutional card with full review process can modify the retry layer or this seal document.

**Violation consequence**: Any retry-layer change that bypasses this amendment procedure is constitutionally invalid, regardless of test results.

---

*Sealed by Card C-41. This document is the institutional authority for the retry subsystem.*
