# G-2: Governance Sustainment Loop

Effective: 2026-03-31
Status: **ACTIVE** (Phase G-2)
Author: B (Implementer)
Scope: Recurring governance checks for sealed observation system

---

## 1. Purpose

Define the cadence and content of recurring governance checks that ensure
the sealed observation system remains compliant over time. Phase F proved
compliance at a point in time. This document ensures **continuous compliance**.

---

## 2. Cadence

| Check | Frequency | Owner | Duration |
|-------|-----------|-------|----------|
| Governance Test Run | Weekly | B | 5 min |
| Red Line Spot Check | Weekly | B | 10 min |
| Category Drift Review | Bi-weekly | A + B | 15 min |
| Full Audit | Monthly | A + B + C | 30 min |
| Constitution Review | Quarterly | A + B + C | 60 min |

---

## 3. Weekly Governance Test Run

**Every Monday** (or first working day of the week).

### Procedure

```bash
# Step 1: Run governance tests
pytest tests/test_board_contract_governance.py -v

# Step 2: Run observation tests
pytest tests/test_trend_observation.py tests/test_latency_observation.py \
      tests/test_four_tier_board.py tests/test_observation_summary.py \
      tests/test_decision_card.py -v

# Step 3: Record result
```

### Weekly Test Log Entry

```
Week: YYYY-Wnn
Date run: YYYY-MM-DD
Runner: (name/ID)

Governance tests: X passed / Y failed / Z warning
Observation tests: X passed / Y failed / Z warning
Total: X passed / Y failed / Z warning

Baseline comparison:
  Expected: 244 / 0 / 0
  Actual: X / Y / Z
  Match: (yes/no)

If mismatch, action taken: (describe)
```

---

## 4. Weekly Red Line Spot Check

**Every Monday** (same session as test run).

Check each red line against current codebase state:

| # | Red Line | Check Method | Expected |
|---|----------|-------------|----------|
| 1 | No action_allowed=True | `grep -r "action_allowed.*True" app/schemas/` | 0 matches |
| 2 | No dict fields in board | Governance test (TestBoardDictFree) | PASS |
| 3 | No free-form descriptions | Manual: check recent commits for template bypass | None |
| 4 | No prediction language | `grep -ri "will likely\|expected to\|trending toward" app/` | 0 matches |
| 5 | No imperative verbs | `grep -ri "you should\|you must\|execute\|delete" app/schemas/ app/services/*observation* app/services/*volume* app/services/*blockage* app/services/*retry* app/services/*trend*` | 0 matches (in observation layer) |
| 6 | No safety field removal | Governance test (TestSafetyInvariantStandard) | PASS |
| 7 | No safety booleans False | Governance test (safety defaults) | PASS |
| 8 | No obs-decision merge | Governance test (TestObservationDecisionFirewall) | PASS |
| 9 | No write paths in obs | Manual: check recent commits | None |
| 10 | No alert triggers in obs | Manual: check recent commits | None |

### Weekly Red Line Log Entry

```
Week: YYYY-Wnn
Checker: (name/ID)

| # | Red Line | Check | Result |
|---|----------|-------|--------|
| 1 | action_allowed=True | grep | 0 matches / OK |
| 2 | dict fields | test | PASS |
| 3 | free-form | commit review | OK |
| 4 | prediction language | grep | 0 matches / OK |
| 5 | imperative verbs | grep | 0 matches / OK |
| 6 | safety removal | test | PASS |
| 7 | safety False | test | PASS |
| 8 | obs-decision merge | test | PASS |
| 9 | write paths | commit review | OK |
| 10 | alert triggers | commit review | OK |

All 10 red lines intact: (yes/no)
If no, which violated: (list)
Action taken: (describe)
```

---

## 5. Bi-Weekly Category Drift Review

**Every other Wednesday.**

### Procedure

1. A selects 5 random change requests from the past 2 weeks
   (or hypothetical if no real requests exist)
2. B independently classifies each as A/B/C/D
3. A independently classifies each as A/B/C/D
4. Compare classifications
5. If any mismatch: discuss and document resolution

### Category Drift Log Entry

```
Period: YYYY-MM-DD to YYYY-MM-DD
Reviewer A: (name)
Reviewer B: (name)

| # | Change Description | B's Category | A's Category | Match |
|---|-------------------|-------------|-------------|-------|
| 1 | ... | B | B | YES |
| 2 | ... | C | C | YES |
| 3 | ... | B | C | NO |

Agreement rate: X/5 (Y%)
Mismatches resolved: (describe each)
"Default to C" rule applied: (count)
```

---

## 6. Monthly Full Audit

**First Monday of each month.**

### Audit Checklist

```
Month: YYYY-MM
Auditors: A, B, C

GOVERNANCE TESTS
[ ] Governance tests pass (60/60)
[ ] Observation tests pass (244 total)
[ ] No new failures since last month

RED LINES
[ ] All 10 red lines intact
[ ] No violations in change log

BOARD INTEGRITY
[ ] Board field count = 24
[ ] Dict fields = 0
[ ] Safety classes = 7 observation + 2 decision
[ ] All safety booleans at expected values

DOCUMENT CURRENCY
[ ] d0 quick map matches current board fields
[ ] d1 presentation matches current section layout
[ ] d2 interpretation covers all current cards
[ ] d3 change control categories still valid
[ ] e1 runbook steps still match board structure
[ ] e2 workflow decision tree still accurate
[ ] e3 onboarding self-test still correct

PILOT OPERATIONS (if during G-1 pilot)
[ ] Daily log compliance >= 90%
[ ] Misinterpretation events <= threshold
[ ] Handover completion >= 90%

CHANGE LOG
[ ] All changes in D-3 change log
[ ] All categories correctly assigned
[ ] No unreviewed Category C/D changes

Result: CLEAN / FINDINGS (list)
```

---

## 7. Quarterly Constitution Review

**First week of each quarter.**

### Review Scope

| Item | Check |
|------|-------|
| OC-01 through OC-21 | Still enforced, still relevant |
| Phase C closure declaration | Still accurate |
| v1 scope locks (Latency, Trend) | Still in effect |
| Family list (5 families) | No unauthorized additions |
| Coverage map (13/13) | Still accurate |

### Questions to Answer

1. Have any OC rules become obsolete?
2. Have any red lines been challenged?
3. Is the change control process working smoothly?
4. Are operators following the runbook?
5. Should any v1 scope lock be reviewed for v2?

### Output

A brief (1-page max) quarterly governance health note documenting:
- Rules reviewed
- Issues found (if any)
- Recommendations (if any)
- Next quarter focus areas

---

## 8. Sustainment Failure Protocol

If any governance check fails:

| Severity | Trigger | Response | Timeline |
|----------|---------|----------|----------|
| Minor | Single red line grep hit (false positive possible) | Investigate, fix if real, log | 24 hours |
| Moderate | Governance test failure | Stop changes, diagnose, fix, re-run | 48 hours |
| Major | Red line violation in production code | Revert change, full audit, A/B/C review | Immediate |
| Critical | Safety invariant compromised | Revert, freeze all changes, constitutional review | Immediate |

### Escalation

```
Minor: B fixes independently
Moderate: B fixes, A reviews
Major: A/B/C review required
Critical: A/B/C unanimous + constitutional amendment process
```
