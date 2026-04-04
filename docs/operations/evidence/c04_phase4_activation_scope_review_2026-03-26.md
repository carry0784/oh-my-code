# C-04 Phase 4 Activation Scope Review

**evidence_id**: C04-PHASE4-SCOPE-REVIEW-2026-03-26
**date**: 2026-03-26
**review_type**: ACTIVATION_SCOPE_REVIEW
**auto_repair_performed**: false

---

## 1. Activation Review Summary

Phase 4 is an **activation-scope review**. It is NOT activation implementation.

Phase 4 determines:
- What may safely enter activation-adjacent presentation scope
- What must remain forbidden even during activation review
- What must be deferred to Phase 5 (execution) or later

Phase 4 does NOT:
- Implement activation
- Enable any control
- Create any write path
- Authorize execution
- Permit mutation

---

## 2. Constitutional Definitions

### What is "activation" for C-04?

**Activation** means transitioning C-04 from sealed/disabled presentation to a state where the operator can see that conditions are met and a controlled action **could** be initiated — but only under Phase 5 execution approval.

Activation is **NOT** execution. Activation is the gate between "invisible/disabled" and "visible/conditional" — not between "visible" and "running".

### Constitutional Hierarchy

```
Existence (Phase 3)     → card exists, sealed, disabled, read-only
Activation (Phase 4)    → card visible, conditional, preconditions shown, still non-executable
Execution (Phase 5)     → card can trigger controlled action under full 9-stage chain approval
```

---

## 3. Activation Boundary Table

| # | Candidate Item | Classification | Reason | Allowed Now? | Deferred |
|---|---------------|----------------|--------|-------------|----------|
| 1 | Disabled visual state refinement | **Phase 4 Review Possible** | Read-only styling adjustment, no action path | Review OK | — |
| 2 | Activation badge/state wording | **Phase 4 Review Possible** | Text change only ("SEALED"→"BLOCKED"/"NOT READY"), no action | Review OK | — |
| 3 | Explicit "still disabled" reason display | **Phase 4 Review Possible** | Informational text, already partially implemented | Review OK | — |
| 4 | Inactive control placeholder visibility | **Phase 4 Review Possible** | Disabled placeholder (grayed, no onclick, no tabindex) | Review OK | — |
| 5 | Operator guidance text | **Phase 4 Review Possible** | Read-only next-step guidance, no action trigger | Review OK | — |
| 6 | Client-side eligibility display only | **Phase 4 Review Possible** | Showing "X of 9 conditions met" — display only, not engine | Review OK | — |
| 7 | Activation precondition display only | **Phase 4 Review Possible** | Listing what must be true before activation — read-only | Review OK | — |
| 8 | Activation gating text | **Phase 4 Review Possible** | "Requires: approval + gate + preflight" — informational | Review OK | — |
| 9 | Non-clickable future-action placeholder | **Phase 4 Review Possible** | Visual indicator of where action would go — disabled/grayed | Review OK | — |
| 10 | Read-only status chip changes | **Phase 4 Review Possible** | Chip color/label reflecting current block state | Review OK | — |
| 11 | Enabling a button | **Phase 4 Forbidden** | Creates action path | No | Phase 5+ |
| 12 | Adding onclick | **Phase 4 Forbidden** | Creates execution trigger | No | Phase 5+ |
| 13 | Adding form submit | **Phase 4 Forbidden** | Creates write path | No | Phase 5+ |
| 14 | Adding fetch/API call | **Phase 4 Forbidden** | Creates network mutation path | No | Phase 5+ |
| 15 | Adding dispatch path | **Phase 4 Forbidden** | Creates execution semantics | No | Phase 5+ |
| 16 | Adding mutation | **Permanently Forbidden** (without full chain) | State change without 9-stage approval | No | Phase 5 only with full chain |
| 17 | Adding rollback | **Phase 5+** | Requires execution receipt first | No | Phase 5+ |
| 18 | Adding background task | **Permanently Forbidden** (for C-04) | C-04 is manual-only, no automated trigger | No | Never |
| 19 | Adding queueing | **Permanently Forbidden** (for C-04) | C-04 is synchronous manual boundary | No | Never |
| 20 | Adding command bus hookup | **Permanently Forbidden** (for C-04) | C-04 is not an event-driven component | No | Never |
| 21 | Adding state transition | **Phase 5+** | Requires execution approval | No | Phase 5+ |
| 22 | Adding real handler | **Phase 5+** | Requires execution approval + 9-stage chain | No | Phase 5+ |
| 23 | Adding activation endpoint | **Phase 5+** | Endpoint = write path precursor | No | Phase 5+ |
| 24 | Adding execution endpoint | **Phase 5+** | Write path | No | Phase 5+ |

---

## 4. Required Questions — Answers

### Q1: What is the strict constitutional meaning of "activation" for C-04?

Activation means **conditional visibility** of C-04's operational readiness — showing the operator whether preconditions are met, without enabling any action. It is the transition from "sealed/invisible internals" to "visible but non-executable readiness display".

### Q2: What may be reviewed in Phase 4 without crossing into execution?

Items 1-10 from the boundary table: visual refinement, wording, precondition display, operator guidance, eligibility display, placeholders — all read-only, non-clickable, non-triggerable.

### Q3: What UI changes are still safe if they remain non-clickable and read-only?

- Badge/chip label changes (SEALED → BLOCKED → NOT READY)
- Progress indicator showing "X/9 conditions met" (display only)
- Disabled placeholder button (grayed, `pointer-events: none`, no onclick, no tabindex)
- "Why blocked" expanded detail text
- Operator next-step guidance text

### Q4: What changes would falsely simulate execution readiness and must remain forbidden?

- Enabled button with any visual affordance of clickability
- "Ready to execute" or "Click to proceed" text
- Green/active color on action controls
- Progress indicator labeled as "execution readiness" or "trade probability"
- Any element that responds to click, keyboard, or hover with action semantics

### Q5: Whether client-side display of preconditions is allowed, and under what limit?

**Allowed**, under these limits:
- Display only, no decision engine
- Shows current state, not predicted future state
- Uses existing data (ops-safety-summary), no new calculation
- "X/9 met" is a count, not a probability or recommendation
- Must not imply that reaching 9/9 automatically enables action

### Q6: Whether a disabled placeholder control may exist, and under what restrictions?

**Allowed**, under these restrictions:
- Visually disabled (grayed, reduced opacity)
- `pointer-events: none` in CSS
- No `onclick`, `onkeydown`, `addEventListener`, `tabindex`
- No `<form>`, no `<input type="submit">`
- No `href`, no `data-action`, no `hx-post`
- Tooltip/title may say "Requires Phase 5 approval"
- Must not become enabled through any client-side logic

### Q7: What must remain deferred to Phase 5?

- Enabling any control
- Adding any onclick/handler
- Adding any endpoint (activation or execution)
- Adding any state transition logic
- Adding any dispatch/executor call
- Adding any rollback capability
- Real handler implementation

### Q8: What remains prohibited even after Phase 4 review?

- Background task for C-04
- Queue/command bus hookup for C-04
- Automated trigger for C-04
- Any mutation without full 9-stage chain approval
- Any bypass of operator approval procedure

---

## 5. Constitutional Comparison

| Concept A | Concept B | Boundary |
|-----------|-----------|----------|
| **Existence** | **Activation** | Existence = card present but sealed. Activation = card shows readiness state but remains non-executable |
| **Activation** | **Execution** | Activation = visible conditional state. Execution = actual action dispatch through 9-stage chain |
| **Disabled control** | **Enabled control** | Disabled = visual placeholder, no event handler, no action path. Enabled = responds to input, triggers action |
| **Read-only precondition display** | **Operational decision engine** | Display = shows current state. Engine = makes eligibility decisions that gate real actions |
| **Visual placeholder** | **Real action path** | Placeholder = grayed non-interactive element. Real = onclick → fetch → endpoint → mutation |

---

## 6. Red-Line Prohibitions (Non-Negotiable in Phase 4)

| # | Red Line | Reason |
|---|----------|--------|
| RL-1 | Enabled button | Action path |
| RL-2 | onclick handler | Execution trigger |
| RL-3 | form submit | Write path |
| RL-4 | fetch/XHR | Network mutation |
| RL-5 | Write endpoint | Server-side action |
| RL-6 | Dispatch call | Execution semantics |
| RL-7 | State mutation | Unauthorized change |
| RL-8 | Rollback trigger | Requires execution receipt |
| RL-9 | Background action | C-04 is manual-only |
| RL-10 | Queue enqueue | C-04 is synchronous |
| RL-11 | Actual handler execution | Phase 5 only |
| RL-12 | Any execution semantics | Phase 5 only |
| RL-13 | Keyboard activation (Enter/Space on control) | Hidden action path |
| RL-14 | CSS-only fake disable | Must be structurally disabled |

---

## 7. Safe Phase 4 Candidate Scope

Maximum safe scope for a future Phase 4 implementation:

1. **Visual refinement**: SEALED badge → conditional badge (BLOCKED/NOT READY/PENDING)
2. **Precondition summary**: "X/9 conditions met" counter (read-only display)
3. **Why-blocked detail**: Expanded block reason list with per-stage explanation
4. **Operator guidance**: Fixed-mapping next-step text (same pattern as B-14A)
5. **Disabled action placeholder**: Grayed button-shaped element with `pointer-events: none`, no handler, labeled "Requires approval" or similar
6. **Activation state chip**: Color-coded chip reflecting activation eligibility (red/yellow/gray only — never green until Phase 5)
7. **Evidence completeness indicator**: "3/5 evidence fields present" (display only)

**Scope limit**: All items are read-only, non-interactive, non-triggerable presentation changes.

---

## 8. Deferred Scope

| Item | Deferred To | Reason |
|------|------------|--------|
| Enabled button | Phase 5 | Requires execution approval |
| onclick/handler | Phase 5 | Execution semantics |
| Activation endpoint | Phase 5 | Write path precursor |
| Execution endpoint | Phase 5 | Write path |
| State transition logic | Phase 5 | Mutation |
| Dispatch/executor wiring | Phase 5 | Execution |
| Rollback capability | Phase 5+ | Post-execution only |
| Background task | Never | C-04 is manual-only |
| Queue hookup | Never | C-04 is synchronous |

---

## 9. Final Judgment

**GO for Phase 4 scope definition**

The activation scope boundary is clearly defined:
- 10 items are Phase 4 review-possible (all read-only, non-executable)
- 14 items are forbidden or deferred
- Red lines are explicit and non-negotiable
- Constitutional separation between existence/activation/execution is maintained

---

## 10. Next Step

→ **C-04 Phase 4 Activation Approval Prompt**

This prompt will authorize implementation of Phase 4 activation-adjacent presentation only (items 1-10 from the boundary table), under the red-line prohibitions defined in this review.
