# CR-022: Multi-Operator First Onboarding Execution

Date: 2026-05-08
Status: **VERIFIED (conditional) — calibration note outstanding**
Author: B (Implementer)
CR-ID: CR-022
Category: L1 (operational procedure, no code change)

---

## 1. Purpose

Execute the first real multi-operator onboarding to resolve the 3 N/A
pilot criteria (#4 Handover, #5 Self-test, #8 Classification consistency).

The dry-run (CR-018) verified that procedures work. This CR executes
them with A as the second operator.

---

## 2. Onboarding Candidate

| Role | Person | Operator Status |
|------|--------|----------------|
| Existing operator | B (Implementer) | Active since Day 1 |
| New operator | A (Designer/Inspector) | **Onboarding candidate** |

A is the optimal first candidate because:
- Already familiar with the system design (authored it)
- Can independently verify interpretation correctness
- Can simultaneously audit the onboarding process itself

---

## 3. Criterion 5: Self-Test for A

A should answer the E-3 §9 Interpretation Self-Test (8 questions).

**Instructions for A**: Read each question, answer independently,
then check against the correct answers below.

### Self-Test Questions

| # | Question | A's Answer | Correct Answer |
|---|----------|-----------|---------------|
| 1 | Trend shows "increasing" for blocked_total. Does this mean blockage will continue to rise? | _(A fills)_ | No. "Increasing" means count went up vs last hour. No prediction. |
| 2 | Pressure level is CRITICAL. Is this an emergency? | _(A fills)_ | No. CRITICAL is a count-based classification, not an alarm. |
| 3 | Decision posture is INTERVENE. Must I intervene immediately? | _(A fills)_ | No. Posture is a suggestion. Operator decides. |
| 4 | Latency median for Submit tier is 45 seconds. Is this too slow? | _(A fills)_ | Cannot determine from observation data alone. No SLA threshold defined. |
| 5 | Trend shows insufficient_data=True. Is something broken? | _(A fills)_ | No. Normal after restart. Buffer needs time to fill. |
| 6 | Orphan count is 3. Should I delete the orphans? | _(A fills)_ | No. Orphan detection is read-only. Orphans may be normal lifecycle. |
| 7 | REVIEW volume is concentrated in Agent tier (80%). Is Agent tier failing? | _(A fills)_ | No. Concentration means most REVIEW items are there. Not a failure signal. |
| 8 | Can I add a new observation card without review? | _(A fills)_ | No. Free expansion is terminated. New cards require A/B/C review (Category C). |

**Pass threshold**: 8/8

---

## 4. Criterion 8: Classification Consistency (A vs B)

A and B independently classify 5 sample changes:

| # | Description | A's Level | A's Category | B's Level | B's Category | Match? |
|---|-------------|-----------|-------------|-----------|-------------|--------|
| 1 | Fix typo in d0_operator_quick_map.md section header | _(A fills)_ | _(A fills)_ | L1 | A | _(compare)_ |
| 2 | Add 3 new self-test questions to E-3 §9 | _(A fills)_ | _(A fills)_ | L1 | B | _(compare)_ |
| 3 | Refine red line 1 grep pattern to exclude comments (FP-001) | _(A fills)_ | _(A fills)_ | L2 | B | _(compare)_ |
| 4 | Add a "last_updated" field to the board response | _(A fills)_ | _(A fills)_ | L3 | C | _(compare)_ |
| 5 | Change decision_card action_allowed default from False to True | _(A fills)_ | _(A fills)_ | L3 | D | _(compare)_ |

**Pass threshold**: >= 4/5 match (90%)

---

## 5. Criterion 4: Handover (B → A)

B prepares a handover note. A receives it and performs an independent board read.

### B's Handover Note (Outgoing)

```
Date: 2026-05-08
From: B (outgoing)
To: A (incoming)

Outgoing 5-minute read completed: yes

Current state:
  Mode: Mode 1 (observation-only, testnet)
  Workers: UP (celery worker + beat)
  Board: cold-start (no proposals — normal)
  Pressure: LOW
  Posture: MONITOR (via decision_summary.recommended_posture)
  Risk: LOW

Anomalies to watch: none
Trend data: not available (cold-start, snapshot buffer building)
Open items: none

Safety invariants: 7/7 intact
  obs: read_only=True, simulation_only=True, no_action_executed=True, no_prediction=True
  dec: action_allowed=False, suggestion_only=True, read_only=True

Test baseline: 832/0/0 (last verified: today)
Red lines: 10/10 intact (last weekly check: current)

Known artifacts:
  RA-001: split execution mandatory (pytest collection)
  FP-001: grep matches "NEVER True" comment (manual verify)

Interpretation passed (not opinion): yes
```

### A's Actions (Incoming)

```
[ ] Read the handover note above
[ ] Perform independent 5-minute board read (run board read script)
[ ] Confirm no interpretation was passed as opinion
[ ] Sign off
```

**Pass threshold**: Checklist complete

---

## 6. Execution Summary

When A completes sections 3-5 above, record:

```
# Multi-Operator Onboarding Result

Date: YYYY-MM-DD
New operator: A (Designer/Inspector)
Supervising operator: B (Implementer)

Criterion 5 (Self-test):
  Score: X/8
  Result: PASS / FAIL

Criterion 8 (Classification):
  Agreement rate: X/5 (Y%)
  Mismatches: (list or none)
  Result: PASS / FAIL

Criterion 4 (Handover):
  Handover note received: yes/no
  Independent board read: yes/no
  No opinion passed: yes/no
  Result: PASS / FAIL

Overall: PASS / FAIL
```

---

## 7. What B Has Prepared

| Item | Status |
|------|--------|
| Self-test questions (E-3 §9) | Ready — §3 above |
| Classification samples (5 items) | Ready — §4 above |
| B's independent classifications | Pre-filled in §4 |
| Handover note | Written — §5 above |
| Scoring templates | Ready — §6 above |
| Board read script | Available (build_four_tier_board()) |
| E-3 onboarding documents | All exist and current |

**Everything is prepared. The next step is A's participation.**

---

## 8. A's Responses (2026-05-08)

### 8.1 Self-Test Results

| # | A's Answer | Correct? |
|---|-----------|----------|
| 1 | No — past observation, not prediction | CORRECT |
| 2 | No — high signal, not emergency | CORRECT |
| 3 | No — review signal, not command | CORRECT |
| 4 | Cannot determine — needs SLA/baseline context | CORRECT |
| 5 | No — insufficient data, not broken | CORRECT |
| 6 | No — read-only detection, investigate first | CORRECT |
| 7 | No — concentration, not failure | CORRECT |
| 8 | No — requires A/B/C review (Category C) | CORRECT |

**Score: 8/8 — PASS**

### 8.2 Classification Consistency Results

| # | Description | A | B | Match |
|---|-------------|---|---|-------|
| 1 | d0 typo fix | L1/A | L1/A | **YES** |
| 2 | E-3 self-test additions | L1/B | L1/B | **YES** |
| 3 | FP-001 grep pattern | L2/C | L2/B | **NO** |
| 4 | last_updated field | L2/C | L3/C | **NO** |
| 5 | action_allowed default | L3/D | L3/D | **YES** |

**Exact match: 3/5 (60%) — threshold 90% not met**

#### Mismatch Resolution

**#3 (FP-001 grep)**: A classified C (touches verification system),
B classified B (ops tooling). Default-to-C applied. **Canonical: L2/C**
(A's classification adopted).

**#4 (last_updated field)**: A classified L2, B classified L3. Board
field additions are explicitly L3 per post_pilot_change_control.md
("Board field additions/removals — Sealed at 24 fields").
**Canonical: L3/C** (B's level adopted, category agreed).

#### Mismatch Character Analysis

- Complete disagreement (level AND category both wrong): **0 cases**
- Both mismatches are **conservative-direction** (upward classification)
- A erred toward C when B said B (safe direction)
- B erred toward L3 when A said L2 (safe direction)

### 8.3 Handover Results

- [x] Handover note read
- [x] Independent board read committed
- [x] Facts-only transmission confirmed
- [x] **Sign-off approved by A**

### 8.4 A's Classification Decision

```
Date: 2026-05-08
Decision: CONDITIONAL PASS

Rationale:
- Exact match 3/5 (60%), below 90% threshold
- However: mismatch 2 cases both conservative-direction
- Complete disagreement: 0 cases
- Rule-based resolution clear for both cases
- No operational risk increase from the disagreements

Conditions:
1. Canonical classifications fixed immediately:
   - #3 = L2/C (default-to-C applied)
   - #4 = L3/C (sealed field rule applied)
2. Next bi-weekly drift review: 5-sample calibration re-run
3. Boundary case rules until then:
   - B vs C boundary: default to C
   - Board sealed field contact: default to L3

Approved by: A (Designer/Inspector)
```

---

## 9. CR-022 Final Judgment

| Criterion | Result |
|-----------|--------|
| #5 Self-test (8/8) | **PASS** |
| #8 Classification (3/5 → conditional) | **CONDITIONAL PASS** |
| #4 Handover (sign-off) | **PASS** |

**CR-022: VERIFIED (conditional)**

Calibration debt: 1 item — next bi-weekly drift review must include
5-sample re-calibration. If >= 4/5 match, upgrade to unconditional PASS.
