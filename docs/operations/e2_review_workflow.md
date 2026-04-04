# E-2: Review Workflow Pack

Effective: 2026-03-31
Status: **ACTIVE** (Phase E-2)
Author: B (Implementer)
Scope: Practical A/B/C/D review routing with examples

---

## 1. Purpose

Turn the abstract change categories from D-3 into a **practical decision tree**
with real examples. When a change request arrives, this document tells you
exactly which review path to follow.

---

## 2. Decision Tree

```
Change request arrives
    │
    ├─ Does it touch code? ─── NO ──── Documentation-only?
    │       │                               │
    │       YES                         Typo fix ──── Category A (no review)
    │       │                               │
    │       │                         Semantic change ── Category B (self-review)
    │       │
    ├─ Does it touch safety invariants? ── YES ── Category D (constitutional)
    │       │
    │       NO
    │       │
    ├─ Does it add a board field? ── YES ── Category C (A/B/C review)
    │       │
    │       NO
    │       │
    ├─ Does it change a schema? ── YES ─┬─ Additive with default? ── Category B
    │       │                           └─ Remove/rename/retype? ── Category C
    │       NO
    │       │
    ├─ Does it change template wording? ─┬─ Same meaning? ── Category B
    │       │                            └─ Different meaning? ── Category C
    │       NO
    │       │
    ├─ Does it change governance tests? ─┬─ Add coverage? ── Category B
    │       │                            └─ Relax assertion? ── Category C
    │       NO
    │       │
    └─ Bug fix / test fix / infra ── Category A or B
```

**When in doubt: default to Category C (requires A/B/C review).**

---

## 3. Category Examples

### Category A: No Review Needed

These changes can be made immediately by B.

| # | Example | Why Category A |
|---|---------|---------------|
| 1 | Fix typo: "obseravtion" -> "observation" in doc | No semantic change |
| 2 | Fix flaky test by adjusting timing tolerance | Test matches existing behavior |
| 3 | Add missing test for existing code path | No new behavior introduced |
| 4 | Update `generated_at` ISO format precision | Cosmetic, no behavioral change |
| 5 | Fix import ordering in test file | No behavioral change |

### Category B: B Self-Review

B can make these changes with a documented commit message.

| # | Example | Why Category B | Commit Note Required |
|---|---------|---------------|---------------------|
| 1 | Add `schema_version: str = "1.0"` to TrendObservationSchema | Additive field with default (OC-16) | "Self-review: additive field, D-3 Category B" |
| 2 | Refine template: "Concentrated in {tier}" -> "{tier} tier has highest concentration" | Same meaning, clearer wording | "Self-review: wording refinement, same semantics" |
| 3 | Fix edge case: `_median([])` returns 0.0 instead of crash | Bug fix, no schema change | "Self-review: edge case fix" |
| 4 | Add 3 new governance tests for existing rules | Adds coverage, no relaxation | "Self-review: additional test coverage" |
| 5 | Update drift sentinel field count after Category B field addition | Follows from prior additive change | "Self-review: drift sentinel update for new field" |

### Category C: Requires A/B/C Review

These changes MUST be reviewed by all three roles before implementation.

| # | Example | Why Category C | Pre-Requisite |
|---|---------|---------------|--------------|
| 1 | Add new `manual_volume` board field | New board field (OC-19) | Pre-review doc + C GO |
| 2 | Add "Health Score" observation family | New family | Pre-review doc + C GO |
| 3 | Expand Latency v1 to include p95/p99 | v1 scope expansion | Separate v2 pre-review + C GO |
| 4 | Add persistent storage for Trend buffer | v1 scope expansion | Separate v2 pre-review + C GO |
| 5 | Change `PressureEnum` to add `EXTREME` level | Enum expansion (OC-18) | Justification + C GO |
| 6 | Remove deprecated `cleanup_simulation_only` field | Field removal (OC-21) | 1-phase deprecation + A/B/C approval |
| 7 | Change `delta` field type from `int` to `float` in TrendObservation | Type change (OC-11) | Migration plan + backward compat + C GO |
| 8 | Add percentage change to Trend descriptions | v1 scope expansion | v2 pre-review + C GO |
| 9 | Relax governance test from 60 tests to 55 | Relaxing assertion | Justification + A/B/C approval |
| 10 | Change stable threshold from delta==0 to abs(delta)<=2 | Classification logic change | Impact analysis + C GO |

### Category D: Constitutional Amendment

These changes require unanimous A/B/C approval and formal amendment.

| # | Example | Why Category D | Required Evidence |
|---|---------|---------------|------------------|
| 1 | Allow `action_allowed=True` on a new card type | Violates OC-03 | Full impact analysis + A/B/C unanimous |
| 2 | Remove `no_prediction` from observation safety | Weakens safety invariant | Impact on all 7 safety classes + A/B/C unanimous |
| 3 | Reopen free expansion (allow new cards without review) | Reverses Phase C closure | Operational need justification + A/B/C unanimous |
| 4 | Allow `dict` fields back into board response | Violates OC-09 | Technical justification + A/B/C unanimous |
| 5 | Allow free-form descriptions in observation cards | Violates OC-08 | Risk analysis + A/B/C unanimous |
| 6 | Merge observation and decision schemas | Violates OC-01/OC-02 firewall | Architecture review + A/B/C unanimous |

---

## 4. Review Process Flow

### Category B Flow

```
B identifies change
  → B classifies as Category B (using decision tree)
  → B implements change
  → B runs governance tests (must pass)
  → B commits with "Self-review: [reason]. D-3 Category B."
  → B updates D-3 change log
  → Done
```

Time: minutes to hours.

### Category C Flow

```
B identifies change need
  → B writes change proposal or pre-review doc
  → A reviews scope and risk
  → C inspects compliance with constitution
  → C issues GO / CONDITIONAL GO / BLOCK
  → If GO: B implements
  → B runs full test suite
  → B reports to C for final verification
  → C issues FINAL GO
  → B commits and updates change log
  → Done
```

Time: hours to days.

### Category D Flow

```
Any role identifies constitutional tension
  → B writes amendment proposal (max 2 pages):
      - What changes
      - Why it is needed
      - Impact on all affected rules
      - Impact on all 7 safety classes
      - Backward compatibility analysis
  → A reviews strategic alignment
  → C reviews constitutional compliance
  → A/B/C unanimous vote required
  → If approved: B implements with full test suite
  → C performs final constitutional audit
  → Amendment documented in constitution changelog
  → Done
```

Time: days to weeks. This is intentionally slow.

---

## 5. Exception Process

When a change does not fit any category:

### Step 1: B writes a 1-page exception request

| Section | Content |
|---------|---------|
| What | Describe the change |
| Why | Why it is needed |
| Which rules | Which OC-xx rules are affected |
| Risk | What could go wrong |
| Proposed category | B's best guess (A/B/C/D) |

### Step 2: A assigns category

A reads the exception request and assigns:
- If clearly fits existing category: assign and proceed
- If ambiguous: default to Category C
- If potentially constitutional: assign Category D

### Step 3: Proceed with assigned category

Follow the standard flow for whichever category A assigned.

### Step 4: Document for future reference

After resolution, add the example to this document's Category Examples
section so future similar changes have a clear precedent.

---

## 6. Escalation Path

```
B unsure about category
  → Ask A for classification
    → A unsure
      → Default to Category C
        → C issues GO/BLOCK
          → If BLOCK and B disagrees
            → A mediates
              → A's decision is final
```

**Principle**: When in doubt, escalate up. The cost of over-review is
small. The cost of under-review can be structural damage.

---

## 7. Common Mistakes

| Mistake | Why it is wrong | Correct approach |
|---------|----------------|-----------------|
| "It's just a small change, no review needed" | Small changes can have large consequences (e.g., changing a default value) | Classify properly using the decision tree |
| "I'll add the review later" | Post-hoc review misses design issues | Review BEFORE implementation for Category C/D |
| "The tests pass so it must be fine" | Tests verify existing rules, not new ones | Passing tests + proper review = safe change |
| "A said it was okay verbally" | Verbal approval has no audit trail | A/B/C review must be documented |
| "It's the same as last time" | Context changes; prior approval does not carry forward | Each change gets its own classification |
