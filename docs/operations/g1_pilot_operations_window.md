# G-1: Pilot Operations Window

Effective: 2026-03-31
Status: **ACTIVE** (Phase G-1)
Author: B (Implementer)
Scope: 30-day controlled operational pilot for sealed observation system

---

## 1. Purpose

Verify that the sealed observation system works reliably in daily production
operation over a sustained period. Phase F proved it works in a drill.
Phase G-1 proves it works **repeatedly, over time, without drift**.

---

## 2. Pilot Parameters

| Parameter | Value |
|-----------|-------|
| Duration | 30 calendar days |
| Start date | (fill when pilot begins) |
| End date | (start + 30 days) |
| Participants | All operators with board access |
| Scope | Daily runbook, weekly review, handover events |
| Success criteria | See section 7 |

---

## 3. Daily Operations Log

Each operator records the following after their daily 5-minute read (E-1 section 2).

### Daily Log Entry Template

```
Date: YYYY-MM-DD
Operator: (name/ID)
Shift: (morning/afternoon/night)

Step 1 - Seal Chain:
  Tiers connected: [ ] Agent [ ] Execution [ ] Submit [ ] Orders
  seal_chain_complete: (True/False)

Step 2 - Summary:
  Pressure: (LOW/MODERATE/HIGH/CRITICAL)
  Posture: (MONITOR/REVIEW/INTERVENE/ESCALATE)
  Risk: (LOW/MEDIUM/HIGH)

Step 3 - Infrastructure:
  Orphans: (count)
  Cleanup candidates: (count)

Step 4 - Pipeline:
  Blocked: (count)
  Retry pending: (count)
  Latency measured: (yes/no)

Step 5 - Trend:
  Available: (yes/no)
  Direction(s) of note: (none / list)

Anomalies observed: (none / describe)
Misinterpretation risk: (none / describe)
Action taken: (none / describe)
Time spent: (minutes)

Runbook followed completely: (yes/no)
If no, what was skipped and why: (explain)
```

---

## 4. Weekly Review Log

Each week, one designated reviewer completes the following (E-1 section 3).

### Weekly Log Entry Template

```
Week: YYYY-Wnn (e.g., 2026-W14)
Reviewer: (name/ID)

Full board review completed: (yes/no)
Volume distribution changes noted: (none / describe)
Pipeline trend observations: (none / describe)
Orphan/cleanup accumulation: (none / describe)

Daily logs reviewed: (count out of expected)
Runbook compliance rate: (X/Y days followed = Z%)
Misinterpretation events this week: (count)
Exception events this week: (count)
Escalation events this week: (count)

Notes: (free text)
```

---

## 5. Handover Log

Each shift handover records:

### Handover Log Entry Template

```
Date: YYYY-MM-DD
From: (outgoing operator)
To: (incoming operator)

Outgoing 5-minute read completed: (yes/no)
Handover note passed: (yes/no)
Incoming 5-minute read completed: (yes/no)

Current pressure: (level)
Current posture: (posture)
Anomalies to watch: (none / list)
Trend data available: (yes/no)

Interpretation passed (not opinion): (yes/no)
```

---

## 6. Event Tracking

### Misinterpretation Events

When an operator initially misreads a card, log:

```
Date: YYYY-MM-DD
Operator: (name/ID)
Card: (which observation card)
Misreading: (what was incorrectly understood)
Correct reading: (what it actually means)
Root cause: (training gap / unclear template / ambiguous value / other)
Corrective action: (re-read guide / update template / escalate to review)
```

### Exception Events

When a situation arises not covered by existing procedures:

```
Date: YYYY-MM-DD
Operator: (name/ID)
Situation: (describe)
Procedure gap: (which document/section was insufficient)
Resolution: (how it was handled)
Follow-up: (update docs / add example / escalate)
```

### Escalation Events

When a change request requires escalation beyond initial classification:

```
Date: YYYY-MM-DD
Original category: (A/B/C/D)
Reclassified to: (A/B/C/D)
Reclassified by: (A/B/C role)
Reason: (describe)
Outcome: (approved/blocked/deferred)
```

---

## 7. Success Criteria (30-Day Pilot)

| # | Criterion | Threshold | Measurement |
|---|-----------|-----------|-------------|
| 1 | Runbook compliance | >= 90% of operating days | Daily log review |
| 2 | Misinterpretation events | <= 3 total in 30 days | Event log count |
| 3 | Red line violations | 0 | Event log + governance test |
| 4 | Handover completion | >= 90% of transitions | Handover log review |
| 5 | Self-test pass rate | 100% for new operators | Onboarding records |
| 6 | Exception events resolved | 100% within 48h | Event log review |
| 7 | Governance test baseline | 244 PASSED / 0 FAILED at pilot end | Test execution |
| 8 | Change classification consistency | >= 90% match on audit re-check | Weekly spot check |

### Pilot Outcome

| Result | Definition |
|--------|-----------|
| **PASS** | All 8 criteria met |
| **CONDITIONAL PASS** | 6-7 criteria met, remediation plan for gaps |
| **FAIL** | 5 or fewer criteria met, requires Phase F re-drill |

---

## 8. 30-Day Pilot Summary Report Template

At pilot end, produce the following report:

```
# 30-Day Pilot Operations Report

Pilot period: YYYY-MM-DD to YYYY-MM-DD
Total operating days: (count)
Total operators: (count)

## Compliance

| Criterion | Target | Actual | Status |
|-----------|--------|--------|--------|
| Runbook compliance | >= 90% | X% | PASS/FAIL |
| Misinterpretation events | <= 3 | N | PASS/FAIL |
| Red line violations | 0 | N | PASS/FAIL |
| Handover completion | >= 90% | X% | PASS/FAIL |
| Self-test pass rate | 100% | X% | PASS/FAIL |
| Exception resolution | 100% in 48h | X% | PASS/FAIL |
| Governance baseline | 244/0/0 | X/Y/Z | PASS/FAIL |
| Classification consistency | >= 90% | X% | PASS/FAIL |

## Events

| Type | Count | Details |
|------|-------|---------|
| Misinterpretation | N | (summary) |
| Exception | N | (summary) |
| Escalation | N | (summary) |

## Observations

(Key findings from 30 days of operation)

## Recommendations

(Changes to procedures, if any, following D-3 change control)

## Result: PASS / CONDITIONAL PASS / FAIL
```
