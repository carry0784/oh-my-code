# E-1: Operator Runbook Pack

Effective: 2026-03-31
Status: **ACTIVE** (Phase E-1)
Author: B (Implementer)
Scope: Board reading routine for operators

---

## 1. Purpose

Define how operators read the 4-tier observation board in practice.
This is NOT a reference guide (see D-0 Quick Map and D-2 Interpretation Pack).
This IS a step-by-step operating procedure.

---

## 2. The 5-Minute Daily Read

Operators should complete this routine once per shift start.
Target time: **under 5 minutes**.

### Step 1: Seal Chain (30 seconds)

Open Section 1. Check:

| Check | What to look for | Normal state |
|-------|-----------------|--------------|
| All 4 tiers connected? | `connected=True` on all tiers | All True |
| `seal_chain_complete`? | Should be True | True |
| Any tier has 0 proposals? | Normal if system is idle | Depends on context |

**If any tier shows `connected=False`**: note it. Do NOT take action yet.
Proceed to Step 2.

### Step 2: Summary (60 seconds)

Open Section 3. Check:

| Check | What to look for | Normal state |
|-------|-----------------|--------------|
| Pressure level | LOW or MODERATE | LOW |
| Decision posture | MONITOR or REVIEW | MONITOR |
| Risk level | LOW or MEDIUM | LOW |

**Read the reason chain** in decision_summary. This tells you WHY
the posture is what it is.

**If pressure is HIGH or CRITICAL**: expand Volume and Pipeline sections
for detail. Do NOT treat as alarm.

### Step 3: Infrastructure Quick Scan (30 seconds)

Glance at Section 2 summary line (collapsed view):

| Check | What to look for | Normal state |
|-------|-----------------|--------------|
| Orphan count | 0 or low single digits | 0 |
| Cleanup candidates | 0 or low single digits | 0 |

**If orphan count is unexpectedly high**: expand for detail.
Orphans are not necessarily errors.

### Step 4: Pipeline Scan (60 seconds)

Expand Section 5 if Summary showed elevated pressure. Otherwise, glance at collapsed summary.

| Check | What to look for | Normal state |
|-------|-----------------|--------------|
| Blockage rate | Per-tier percentage | Low single digits |
| Retry backlog | Pending retry count | Low or zero |
| Latency median | Per-tier elapsed seconds | Varies by tier |

**Reading order**: Blockage first (is anything stuck?), then Retry
(is anything piling up?), then Latency (is anything slow?).

### Step 5: Trend (30 seconds)

Expand Section 6 only if Steps 1-4 showed something noteworthy.

| Check | What to look for | Normal state |
|-------|-----------------|--------------|
| `trend_available` | True if enough history | May be False after restart |
| Direction fields | stable / increasing / decreasing | stable |
| `insufficient_data` | True if not enough snapshots | True after restart |

**Remember**: Trend data is volatile. After any restart, trend shows
"insufficient data" until the buffer refills. This is normal, not an error.

### Done

Total: ~3-4 minutes for normal state, ~5 minutes if something is elevated.

---

## 3. Weekly Review Routine

Once per week (recommended: Monday morning), do a deeper pass.

### Week Review Step 1: Full Board Expanded (5 minutes)

Expand ALL sections. Read through each card's density signal description.
Note any patterns.

### Week Review Step 2: Volume Distribution (3 minutes)

Check REVIEW Volume and WATCH Volume:

| Question | Where to look |
|----------|--------------|
| Is REVIEW count growing week-over-week? | Compare to last week's notes |
| Is concentration shifting between tiers? | Tier distribution in review_volume |
| Are prolonged proposals accumulating? | Prolonged count in density signal |

### Week Review Step 3: Pipeline Trend (3 minutes)

Check Trend Observation (if available):

| Question | Where to look |
|----------|--------------|
| Are blocked counts increasing over sessions? | blocked_trend direction |
| Is retry backlog growing? | pending_retry_trend direction |

**Note**: Trend only covers the current process session. If the system
restarted during the week, trend data resets. Check `since_startup` timestamp.

### Week Review Step 4: Record Observations (2 minutes)

Write a brief note (3-5 lines) answering:
1. What is the current pressure level?
2. Are any tiers showing elevated blockage or retry?
3. Is trend data available and what does it show?
4. Any orphans or cleanup candidates of note?

This note is for your own records. The board does not store history.

---

## 4. What to Check First (Priority Order)

When something looks unusual, investigate in this order:

| Priority | Section | Why first |
|----------|---------|-----------|
| 1 | Seal Chain | Is the pipeline structurally intact? |
| 2 | Summary | What is the aggregated assessment? |
| 3 | Blockage | Is anything stuck? |
| 4 | Retry | Is anything piling up? |
| 5 | Volume | Where are the candidates concentrated? |
| 6 | Latency | Is anything slow? |
| 7 | Trend | Is it getting better or worse? (context only) |
| 8 | Infrastructure | Any orphans or stale proposals? |

---

## 5. The "Do Not Act" Rules

These rules prevent operators from over-reacting to observation data.

### Rule E1-01: Never act on a single card alone

No single card value, no matter how elevated, justifies immediate action.
Always cross-reference with at least one other section before considering response.

### Rule E1-02: Never act on trend direction alone

"Increasing" is a factual comparison. It does not mean "act now."
Always check the actual counts (are they high enough to matter?)
and the context (is the system under unusual load?).

### Rule E1-03: Never treat CRITICAL pressure as an alarm

CRITICAL is a count-based classification. It means "many candidates exist."
It does NOT mean "the system is failing" or "emergency."

### Rule E1-04: Never act during the first 2 hours after restart

After a restart:
- Trend data is unavailable (buffer is empty)
- Latency data may be sparse (few proposals processed)
- Volume counts may be low (pipeline is warming up)

Allow the system to stabilize before drawing conclusions from the board.

### Rule E1-05: Never assume causation from co-occurrence

Seeing high blockage AND increasing trend simultaneously does NOT mean
one caused the other. Observation cards describe co-occurring states,
never causal relationships.

---

## 6. Collapsed vs Expanded Usage Guide

| Situation | What to expand |
|-----------|---------------|
| Routine daily check | Seal Chain + Summary only |
| Elevated pressure | + Volume + Pipeline |
| Post-restart | + Temporal (check trend availability) |
| Investigating specific tier | + Infrastructure (orphans, block reasons) |
| Weekly review | All sections |

**Default**: Keep Temporal collapsed unless specifically needed.
Trend is the highest-risk card for misinterpretation.

---

## 7. Shift Handover Protocol

When handing off to the next operator:

1. Run the 5-minute daily read
2. Note current pressure level and any anomalies
3. Note whether trend data is available (or if a recent restart cleared it)
4. Pass the note to the next operator
5. The next operator runs their own 5-minute read to verify

Do NOT pass interpretations. Pass observations only.
Let the next operator form their own assessment.
