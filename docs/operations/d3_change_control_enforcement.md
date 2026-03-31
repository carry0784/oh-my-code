# D-3: Change Control Enforcement Pack

Effective: 2026-03-31
Status: **ACTIVE** (Phase D-3)
Author: B (Implementer)
Scope: Post-Phase C change control protocol for observation layer

---

## 1. Purpose

Define the review and approval protocol for ALL changes to the sealed
observation layer. Free expansion is terminated. Every change category
has an explicit gate.

---

## 2. Red Line Change List

These changes are **absolutely forbidden** without exception.

| # | Forbidden Change | Rule |
|---|-----------------|------|
| 1 | Set `action_allowed=True` on any card | OC-03 |
| 2 | Reintroduce `dict` fields in board response | OC-09 |
| 3 | Use free-form text in observation descriptions | OC-08 |
| 4 | Add prediction language to any card | OC-07 |
| 5 | Add imperative verbs to descriptions | OC-06 |
| 6 | Remove safety invariant fields | OC-04/OC-05 |
| 7 | Set any safety boolean to `False` | OC-04/OC-05 |
| 8 | Merge observation and decision schemas | OC-01/OC-02 |
| 9 | Add write paths to observation layer | OC-01 |
| 10 | Add alerting/escalation triggers to observation cards | OC-01 |

**These are non-negotiable. No A/B/C review can override them.**
They are constitutional constraints, not policy choices.

---

## 3. Change Categories and Gates

### Category A: No Review Needed

Changes that can be made by B without A/B/C review.

| Change | Conditions | Example |
|--------|-----------|---------|
| Fix typo in documentation | No semantic change | "obseravtion" -> "observation" |
| Update test assertions for existing behavior | Tests match current code | Fix flaky test timing |
| Add test coverage for existing paths | No new behavior | Missing branch coverage |
| Update `generated_at` format | No semantic change | ISO format precision |

### Category B: B Self-Review (document in commit message)

| Change | Conditions | Example |
|--------|-----------|---------|
| Add new default field to existing schema | Has default value, additive-only (OC-16) | Add `version: str = "1.0"` |
| Update drift sentinel for above | Matches field addition | Field count 24 -> 25 |
| Bug fix in observation service | No behavioral change to schema | Fix edge case in `_median()` |
| Template wording refinement | Same meaning, better clarity | "Concentrated in X" -> "X tier has highest concentration" |

**Required**: Commit message must state: "Self-review: [category B change]. No A/B/C review needed per D-3."

### Category C: Requires A/B/C Review

| Change | Gate | Minimum Evidence |
|--------|------|-----------------|
| New board field | OC-19 (5-step protocol) | Pre-review doc + C GO |
| New observation card | Full A/B/C cycle | Pre-review + design + implementation + C GO |
| New observation family | Full A/B/C cycle | Pre-review + justification + C GO |
| Remove existing field | OC-21 (deprecation) | 1-phase deprecation + A/B/C approval |
| Change field type | OC-11 exception | Migration plan + backward compat proof + C GO |
| Rename field | Treated as remove + add | Both OC-21 and OC-19 apply |
| Expand v1 scope (Latency) | Separate review | Pre-review for v2 scope + C GO |
| Expand v1 scope (Trend) | Separate review | Pre-review for v2 scope + C GO |
| Change default value | OC-17 | Justification + backward compat analysis + C GO |
| Add new enum member | OC-18 | Additive-only proof + C GO |

### Category D: Requires Constitutional Amendment

| Change | Gate | Minimum Evidence |
|--------|------|-----------------|
| Modify OC-01 through OC-21 | Full A/B/C review | Impact analysis + amendment proposal + A/B/C unanimous |
| Change safety invariant structure | Constitutional | Impact on all 7 safety classes + A/B/C unanimous |
| Reopen free expansion | Constitutional | Operational need justification + A/B/C unanimous |

---

## 4. Schema Change Checklist

For ANY schema modification (Category B or C):

```
[ ] 1. Identify change category (A/B/C/D)
[ ] 2. If Category C or D: obtain required approvals BEFORE implementation
[ ] 3. Verify change is additive-only (OC-16) or has exception approval
[ ] 4. Verify default value exists for new fields
[ ] 5. Update drift sentinel test (field count + name snapshot)
[ ] 6. Update contract test for new/changed field
[ ] 7. Verify backward compatibility (OC-20)
[ ] 8. Run governance tests: pytest tests/test_board_contract_governance.py -v
[ ] 9. Verify 0 FAILED / 0 WARNING
[ ] 10. Update coverage map if board field added (OC-19 step 4)
[ ] 11. Update constitution inventory if board field added (OC-19 step 5)
[ ] 12. Document in commit message with change category
```

---

## 5. Board Field Change Checklist

For adding a new field to `FourTierBoardResponse` (always Category C):

```
[ ] 1. Write pre-review document (like latency_observation_prereview.md)
[ ] 2. Obtain C inspector GO on pre-review
[ ] 3. Design typed Pydantic schema (OC-09: no dict, no Any)
[ ] 4. Set default value (OC-19 step 2)
[ ] 5. Implement service (read-only, no mutations)
[ ] 6. Add safety invariant (4-field for observation, 3-field for decision)
[ ] 7. Add template-locked descriptions (OC-08)
[ ] 8. Write tests (minimum: zero-safe, safety, drift sentinel, board integration)
[ ] 9. Update drift sentinel (OC-19 step 3)
[ ] 10. Update coverage map (OC-19 step 4)
[ ] 11. Update constitution inventory OC-14 (OC-19 step 5)
[ ] 12. Update D-1 presentation normalization (section assignment)
[ ] 13. Update D-2 interpretation guide (card entry)
[ ] 14. Obtain C inspector GO on implementation
[ ] 15. Run full governance verification
```

---

## 6. Safety Invariant Change Protocol

**Safety invariant changes are Category D (constitutional).**

The following is NEVER permitted:
- Removing any of the 4 observation safety fields
- Removing any of the 3 decision safety fields
- Setting `read_only`, `simulation_only`, `no_action_executed`, or `no_prediction` to `False`
- Setting `action_allowed` to `True`
- Adding `action_allowed` to any observation card

If a future use case requires relaxing a safety constraint, the constitutional
amendment process applies:
1. Full impact analysis across all 7 safety classes
2. A/B/C unanimous approval required
3. Existing governance tests must be updated to reflect new constraints
4. The amendment must be documented in the constitution changelog

---

## 7. Template Wording Change Protocol

Description templates (OC-08) are **Category B** (B self-review) for wording
refinement and **Category C** (A/B/C review) for semantic change.

| Change Type | Category | Example |
|-------------|----------|---------|
| Fix grammar | A | "Concentated" -> "Concentrated" |
| Clarify without semantic change | B | "in X tier" -> "X tier has highest share" |
| Add new template variant | C | New density signal pattern |
| Change classification logic | C | ±5% stable threshold -> ±10% |
| Add forbidden-to-allowed wording | D | Allow "improving" — constitutional violation |

---

## 8. Family Management Protocol

**Adding a new family is Category C (A/B/C review).**

Current families (5, all COMPLETE):
1. Volume (2 cards)
2. Pipeline (3 cards)
3. Summary/Decision (3 cards)
4. Infrastructure (2 cards)
5. Temporal (1 card)

To add a 6th family:
1. Justify why existing families cannot accommodate the new card
2. Write pre-review document for the family
3. Obtain C inspector GO
4. Follow OC-19 for any new board fields
5. Update D-1 section layout

---

## 9. Exception Process

If a change does not fit any category above:

1. B writes a change proposal (1 page max) describing:
   - What the change is
   - Why it is needed
   - Which constitutional rules it touches
   - What the risk is
2. A reviews and assigns a category
3. If Category C or D, standard review process applies
4. If A cannot assign a category, default to Category C (requires A/B/C review)

**Principle: when in doubt, require review.**

---

## 10. Governance Verification Requirement

After ANY change to the observation layer (Categories A through D):

```bash
# Minimum verification
pytest tests/test_board_contract_governance.py -v

# Expected result
60 passed / 0 failed / 0 warning
```

For Category C and D changes, full test suite must pass:

```bash
pytest tests/ -x
```

---

## 11. Post-Phase C Change Log

| Date | Change | Category | Reviewer | Tests After |
|------|--------|----------|----------|-------------|
| (none yet) | | | | |

This table must be updated for every change to the observation layer.
