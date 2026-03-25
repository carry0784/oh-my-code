# C-04 Phase 8 Scope Review — 2026-03-26

**evidence_id**: C04-PHASE8-SCOPE-REVIEW-2026-03-26
**date**: 2026-03-26
**review_type**: PHASE_8_ASYNC_INFRA_SCOPE_CLASSIFICATION
**auto_repair_performed**: false

---

## 1. Review Purpose

Scope-classification review only. Does NOT authorize polling infra, queueing, workers, command bus recovery, background retry, or background rollback. Current manual/sync sealed baseline remains intact.

---

## 2. Current Baseline

| Item | Status |
|------|--------|
| Phase 5/6/7 | All **SEALED** |
| Write path | 5 bounded POST |
| Async infra | **None** |
| Polling | **None** |
| Queue/worker/bus | **None** |
| Autonomous recovery | **None** |
| Hidden background | **None** |

---

## 3. Classification Table (45 items)

### Polling / Status Refresh (#1–8)

| # | Item | Classification | Reason | Now? |
|---|------|----------------|--------|------|
| 1 | Status refresh text only | **Phase 8 Review Possible** | Display text, no infra | No |
| 2 | Status refresh endpoint | **Phase 9+** | Requires async result store | No |
| 3 | Client polling loop | **Phase 9+** | Async client behavior | No |
| 4 | Bounded manual refresh button | **Phase 8 Review Possible** | Single click → re-fetch, not loop | No |
| 5 | Server polling job | **Permanently Forbidden** | Background job violates manual-only | No |
| 6 | Polling audit record | **Phase 9+** | Requires polling infra | No |
| 7 | Polling receipt | **Phase 9+** | Requires polling infra | No |
| 8 | Eventual status display only | **Phase 8 Review Possible** | Text wording, no computation | No |

### Queue / Worker / Bus (#9–18)

| # | Item | Classification | Reason | Now? |
|---|------|----------------|--------|------|
| 9 | Queue enqueue for retry | **Permanently Forbidden** | C-04 is synchronous manual boundary | No |
| 10 | Queue enqueue for rollback | **Permanently Forbidden** | C-04 is synchronous manual boundary | No |
| 11 | Worker retry execution | **Permanently Forbidden** | C-04 is manual-only | No |
| 12 | Worker rollback execution | **Permanently Forbidden** | C-04 is manual-only | No |
| 13 | Worker simulation execution | **Permanently Forbidden** | Simulation is read-only sync | No |
| 14 | Command bus recovery dispatch | **Permanently Forbidden** | C-04 is not event-driven | No |
| 15 | Command bus preview dispatch | **Permanently Forbidden** | C-04 is not event-driven | No |
| 16 | Bounded async receipt finalization | **Phase 9+** | Requires async model | No |
| 17 | Async audit aggregation | **Phase 9+** | Requires async model | No |
| 18 | Deferred execution result reconciliation | **Phase 9+** | Requires async model | No |

### Recovery Infra (#19–27)

| # | Item | Classification | Reason | Now? |
|---|------|----------------|--------|------|
| 19 | Delayed retry scheduler | **Permanently Forbidden** | Autonomous retry | No |
| 20 | Delayed rollback scheduler | **Permanently Forbidden** | Autonomous rollback | No |
| 21 | Bounded lock/lease for recovery | **Phase 8 Review Possible** | Prevents concurrent manual recovery (safety) | No |
| 22 | Idempotency guard for async retry | **Phase 9+** | Requires async retry model | No |
| 23 | Idempotency guard for async rollback | **Phase 9+** | Requires async rollback model | No |
| 24 | Dead-letter handling | **Phase 9+** | Requires queue infra | No |
| 25 | Timeout handling for async recovery | **Phase 9+** | Requires async model | No |
| 26 | Recovery state tracker | **Phase 8 Review Possible** | Read-only state display for recovery progress | No |
| 27 | Background recovery watchdog | **Permanently Forbidden** | Autonomous background | No |

### Async UX / Orchestration (#28–38)

| # | Item | Classification | Reason | Now? |
|---|------|----------------|--------|------|
| 28 | Manual refresh status control | **Phase 8 Review Possible** | Single manual refresh, not loop | No |
| 29 | Async status chip | **Phase 9+** | Requires async model | No |
| 30 | Eventual consistency warning text | **Phase 8 Review Possible** | Text-only, no computation | No |
| 31 | Background progress text only | **Phase 8 Review Possible** | Descriptive text | No |
| 32 | In-flight async result placeholder | **Phase 9+** | Requires async model | No |
| 33 | Async confirmation wording only | **Phase 8 Review Possible** | Text-only | No |
| 34 | Optimistic async success state | **Permanently Forbidden** | Fail-closed violation | No |
| 35 | Hidden async recovery flag | **Permanently Forbidden** | Transparency violation | No |
| 36 | Hidden polling flag | **Permanently Forbidden** | Transparency violation | No |
| 37 | Hidden queue flag | **Permanently Forbidden** | Transparency violation | No |
| 38 | Hidden worker flag | **Permanently Forbidden** | Transparency violation | No |

### Safety / Audit / Control (#39–45)

| # | Item | Classification | Reason | Now? |
|---|------|----------------|--------|------|
| 39 | Async receipt for retry | **Phase 9+** | Requires async retry | No |
| 40 | Async receipt for rollback | **Phase 9+** | Requires async rollback | No |
| 41 | Async audit for retry | **Phase 9+** | Requires async retry | No |
| 42 | Async audit for rollback | **Phase 9+** | Requires async rollback | No |
| 43 | Lock conflict warning text | **Phase 8 Review Possible** | Text-only safety warning | No |
| 44 | Recovery timeout warning text | **Phase 8 Review Possible** | Text-only safety warning | No |
| 45 | Dead-letter warning text | **Phase 8 Review Possible** | Text-only safety warning | No |

### Summary

| Group | Count |
|-------|-------|
| **Phase 8 Review Possible** | **12** |
| **Phase 8 Forbidden** | **0** |
| **Phase 9+** | **16** |
| **Permanently Forbidden** | **17** |

---

## 4. Constitutional Questions

**Polling vs refresh**: Polling becomes async infra when it creates a server-side job, introduces a timer loop, or decouples request from response. A single manual refresh button (operator-clicks → re-fetch → display) is bounded and reviewable.

**Bounded manual refresh without opening polling**: Yes. A single-click refresh that calls an existing GET endpoint is not a polling loop. It must not auto-repeat.

**Queue/worker/bus vs manual/sync**: No. C-04's constitutional identity is manual/sync. Queue/worker/bus fundamentally violate this by decoupling operator action from execution result. **Permanently forbidden** for C-04.

**Stronger audit/receipt for async**: Before any async recovery, a separate receipt finalization model (deferred receipt → confirmed receipt) and async audit aggregation model would be required. These are Phase 9+.

**Idempotency/lease/lock in Phase 8**: Only a bounded lock/lease for preventing concurrent manual recovery (#21) is reviewable in Phase 8 — it's a safety mechanism, not async infra.

**Deferred receipt finalization**: Phase 9+. Requires async execution model.

**Async status UX without fake progress**: Only text-based warning/description (#30,31,33) is safe in Phase 8. Any progress bar or status chip that implies real-time tracking requires Phase 9+.

**Permanently forbidden**: All autonomous recovery (#19,20,27), all queue/worker/bus (#9–15), all hidden flags (#35–38), optimistic async (#34), server polling job (#5).

**Recovery state tracking**: A read-only display showing "last recovery attempt" status (#26) is reviewable. An active tracker that monitors background recovery is permanently forbidden.

**Manual refresh vs polling**: Manual refresh = operator clicks once, gets one response. Polling = automated repeated requests. The line is: no auto-repeat, no timer, no loop.

---

## 5. Constitutional Comparison

| Concept A | Concept B | Boundary |
|-----------|-----------|----------|
| Manual refresh | Polling loop | Refresh = one click, one response. Polling = auto-repeating timer. |
| Sync receipt | Async receipt finalization | Sync = immediate. Async = deferred confirmation required. |
| Manual retry | Queued retry | Manual = operator clicks, waits. Queued = enqueue, process later. |
| Manual rollback | Worker rollback | Manual = operator-initiated sync. Worker = background autonomous. |
| Display-only status | Background state tracker | Display = reads last known. Tracker = monitors actively. |
| Warning text | Active orchestration | Text = informational. Orchestration = controls flow. |
| Explicit audit | Hidden async behavior | Explicit = traced. Hidden = silent side effect. |
| Lock/idempotency guard | Autonomous recovery engine | Guard = prevents conflict. Engine = executes autonomously. |

---

## 6. Red Lines

| # | Red Line |
|---|----------|
| RL-1 | Server polling job |
| RL-2 | Hidden polling flag |
| RL-3 | Hidden queue flag |
| RL-4 | Hidden worker flag |
| RL-5 | Background recovery watchdog |
| RL-6 | Automatic retry scheduler |
| RL-7 | Automatic rollback scheduler |
| RL-8 | Worker retry execution |
| RL-9 | Worker rollback execution |
| RL-10 | Worker simulation execution |
| RL-11 | Command bus recovery dispatch |
| RL-12 | Command bus preview dispatch |
| RL-13 | Optimistic async success |
| RL-14 | Silent deferred execution |
| RL-15 | Hidden autonomous recovery |
| RL-16 | Queue without strict audit |
| RL-17 | Worker without strict audit |
| RL-18 | Queue enqueue for retry |
| RL-19 | Queue enqueue for rollback |

---

## 7. Safe Phase 8 Candidate Scope

12 items reviewable (all text/display/guard-only):

- Status refresh text + bounded manual refresh button
- Eventual consistency warning text
- Background progress text (descriptive)
- Async confirmation wording
- Bounded lock/lease for recovery
- Recovery state tracker (read-only display)
- Lock conflict warning text
- Recovery timeout warning text
- Dead-letter warning text

---

## 8. Deferred (Phase 9+)

16 items: status refresh endpoint, client polling loop, polling audit/receipt, bounded async receipt finalization, async audit aggregation, deferred result reconciliation, idempotency guards for async, dead-letter handling, timeout handling, async status chip, in-flight placeholder, async receipts/audits for retry/rollback.

---

## 9. Permanent Prohibitions

17 items: server polling job, queue enqueue for retry/rollback, worker retry/rollback/simulation, command bus recovery/preview, delayed retry/rollback schedulers, background watchdog, optimistic async, hidden polling/queue/worker/async flags.

---

## 10. Boundary Preservation

- Phase 8 scope review does **NOT** open async execution
- Phase 8 scope review does **NOT** open hidden orchestration
- Phase 8 scope review does **NOT** break sealed Phase 5/6/7 baselines
- Phase 8 scope review **preserves** explicit manual control

---

## 11. Final Judgment

**GO for Phase 8 scope definition**

45 items classified: 12 reviewable (text/display/guard), 16 deferred, 17 permanently forbidden. All boundaries intact.

---

## 12. Next Step

→ **C-04 Phase 8 Approval Prompt**
