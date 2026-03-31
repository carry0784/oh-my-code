# E-3: Handover / Onboarding Pack

Effective: 2026-03-31
Status: **ACTIVE** (Phase E-3)
Author: B (Implementer)
Scope: Quick-start and handover materials for new operators and reviewers

---

## 1. Purpose

Enable a new operator or reviewer to understand the 4-tier observation system
in **30 minutes or less**, using a structured reading path.

---

## 2. Quick Start (10 minutes)

### What is this system?

K-Dexter has a **4-tier sealed pipeline** that processes trading proposals:

```
Agent (T1) → Execution (T2) → Submit (T3) → Orders (T4)
```

On top of this pipeline sits a **read-only observation layer** that monitors
the pipeline without ever changing it. The observation layer produces a
**board** — a structured JSON response with 24 typed fields.

### What does the board show?

The board shows **factual observations** grouped into 6 sections:

| Section | What it tells you |
|---------|------------------|
| Seal Chain | Are all 4 tiers connected and running? |
| Infrastructure | Any orphaned or stale proposals? |
| Summary | Overall pressure level and suggested posture |
| Volume | How many proposals are in REVIEW vs WATCH state? |
| Pipeline | Is anything blocked, retrying, or slow? |
| Temporal | Are counts going up or down vs. the previous hour? |

### What the board does NOT do

| The board does NOT... | Because... |
|----------------------|-----------|
| Execute trades | Read-only — no write path |
| Trigger alerts | Observation, not alerting system |
| Recommend actions | Describes state, never prescribes |
| Predict the future | Shows current and recent past only |
| Score system health | Classifies, never judges |

### The one rule

**Every card is observation, not instruction. You decide what to do.**

---

## 3. Document Map (20 minutes reading)

Read these documents in order. Total: ~20 minutes.

### Essential (read all)

| Order | Document | Time | What you learn |
|-------|----------|------|---------------|
| 1 | `d0_operator_quick_map.md` | 3 min | All 24 fields, family map, 5 operator rules |
| 2 | `e1_operator_runbook.md` §2 | 3 min | The 5-minute daily read routine |
| 3 | `d2_operator_interpretation_pack.md` §2.1-2.4 | 5 min | High-risk cards: Trend, Latency, Blockage, Retry |
| 4 | `e1_operator_runbook.md` §5 | 2 min | The "Do Not Act" rules |

### Reference (read when needed)

| Document | When to read |
|----------|-------------|
| `d1_board_presentation_normalization.md` | When setting up board display layout |
| `d2_operator_interpretation_pack.md` §2.5-2.11 | When investigating specific card meaning |
| `d3_change_control_enforcement.md` | Before proposing any change |
| `e2_review_workflow.md` | When classifying a change request |
| `observation_constitution.md` | When understanding the governing rules |
| `observation_coverage_map.md` | When checking what is/isn't observed |

### Deep reference (for reviewers/inspectors only)

| Document | When to read |
|----------|-------------|
| `latency_observation_prereview.md` | Understanding Latency v1 scope decisions |
| `trend_observation_prereview.md` | Understanding Trend v1 scope decisions |
| `evidence/phase_c_interim_seal_2026-03-31.md` | Understanding the Phase C seal |

---

## 4. Family Structure Summary

```
┌──────────────────────────────────────────────────────┐
│                  OBSERVATION BOARD                     │
│                  24 fields / 11 cards                  │
├──────────────────────────────────────────────────────┤
│                                                        │
│  ┌─ Seal Chain ──────────────────────────────────┐    │
│  │  agent_tier, execution_tier, submit_tier,      │    │
│  │  order_tier, derived_flags, seal_chain_complete │    │
│  └────────────────────────────────────────────────┘    │
│                                                        │
│  ┌─ Infrastructure ──────────────────────────────┐    │
│  │  orphan_count/detail, cleanup_count/summary,   │    │
│  │  simulation_only, lineage, block_reasons        │    │
│  └────────────────────────────────────────────────┘    │
│                                                        │
│  ┌─ Summary / Decision ──────────────────────────┐    │
│  │  observation_summary, decision_summary,         │    │
│  │  decision_card                                  │    │
│  └────────────────────────────────────────────────┘    │
│                                                        │
│  ┌─ Volume ──────────────────────────────────────┐    │
│  │  review_volume, watch_volume                    │    │
│  └────────────────────────────────────────────────┘    │
│                                                        │
│  ┌─ Pipeline ────────────────────────────────────┐    │
│  │  blockage_summary, retry_pressure,              │    │
│  │  latency_observation                            │    │
│  └────────────────────────────────────────────────┘    │
│                                                        │
│  ┌─ Temporal ────────────────────────────────────┐    │
│  │  trend_observation                              │    │
│  └────────────────────────────────────────────────┘    │
│                                                        │
│  ┌─ Meta ────────────────────────────────────────┐    │
│  │  total_guard_checks, generated_at               │    │
│  └────────────────────────────────────────────────┘    │
│                                                        │
└──────────────────────────────────────────────────────┘
```

---

## 5. Red Lines (Never Cross)

These are absolute constraints. Violating any of these is a constitutional breach.

| # | Red Line | Short Reason |
|---|----------|-------------|
| 1 | No `action_allowed=True` | Observation never triggers actions |
| 2 | No `dict` fields in board | All fields must be typed |
| 3 | No free-form descriptions | Templates only |
| 4 | No prediction language | "will", "expected to", "trending toward" are forbidden |
| 5 | No imperative verbs | "must", "should", "execute" are forbidden |
| 6 | No safety field removal | Safety invariants are permanent |
| 7 | No safety booleans set False | read_only, no_prediction, etc. are always True |
| 8 | No observation-decision merge | Firewall is permanent |
| 9 | No write paths in observation | Read-only is permanent |
| 10 | No alert triggers in observation | Observation describes, never alerts |

---

## 6. Interpretation Quick Reference

For the 5 highest-risk cards:

| Card | Means | Does NOT Mean |
|------|-------|--------------|
| **Trend** | Count went up/down vs last hour | Count will continue to rise/fall |
| **Latency** | Proposals took X seconds in this tier | The tier is "slow" or "fast" |
| **Blockage** | X% of proposals are blocked | The system is "failing" |
| **Retry** | N items are pending retry | The system is "overwhelmed" |
| **Decision** | Posture is INTERVENE | You MUST intervene now |

**Universal rule**: All observation is factual description. The operator
synthesizes meaning and decides response.

---

## 7. Change Control Quick Guide

| Want to... | Category | Who approves? |
|-----------|----------|--------------|
| Fix a typo | A | No one (just do it) |
| Add a field with default | B | B self-review |
| Refine template wording | B | B self-review |
| Add a new board field | C | A + B + C review |
| Add a new card | C | A + B + C review |
| Expand Latency/Trend v1 scope | C | A + B + C review |
| Change safety invariants | D | A + B + C unanimous |
| Reopen free expansion | D | A + B + C unanimous |

**When in doubt**: treat as Category C (requires A/B/C review).

---

## 8. Handover Checklist

When transferring this system to a new team member:

```
[ ] 1. New member reads Quick Start (§2) — 10 min
[ ] 2. New member reads Essential documents (§3) — 20 min
[ ] 3. New member performs supervised 5-minute daily read — 10 min
[ ] 4. New member identifies all 6 board sections from memory
[ ] 5. New member states the 5 operator rules from d0
[ ] 6. New member correctly classifies 3 example changes (one B, one C, one D)
[ ] 7. New member passes the interpretation test (§9)
[ ] 8. New member performs unsupervised daily read — sign off
```

---

## 9. Interpretation Self-Test

New operators should be able to answer these correctly:

| # | Question | Correct Answer |
|---|----------|---------------|
| 1 | Trend shows "increasing" for blocked_total. Does this mean blockage will continue to rise? | No. "Increasing" means count went up vs last hour. No prediction. |
| 2 | Pressure level is CRITICAL. Is this an emergency? | No. CRITICAL is a count-based classification, not an alarm. |
| 3 | Decision posture is INTERVENE. Must I intervene immediately? | No. Posture is a suggestion. Operator decides. |
| 4 | Latency median for Submit tier is 45 seconds. Is this too slow? | Cannot determine from observation data alone. No SLA threshold defined. |
| 5 | Trend shows insufficient_data=True. Is something broken? | No. Normal after restart. Buffer needs time to fill. |
| 6 | Orphan count is 3. Should I delete the orphans? | No. Orphan detection is read-only. Orphans may be normal lifecycle. |
| 7 | REVIEW volume is concentrated in Agent tier (80%). Is Agent tier failing? | No. Concentration means most REVIEW items are there. Not a failure signal. |
| 8 | Can I add a new observation card without review? | No. Free expansion is terminated. New cards require A/B/C review (Category C). |

Score: 8/8 = ready. Below 8/8 = re-read the interpretation pack.

---

## 10. Handover Bundle Index

All documents that make up the complete operational package:

| Phase | Document | Purpose |
|-------|----------|---------|
| C | `observation_constitution.md` | Governing rules (OC-01 through OC-21 + closure) |
| C | `observation_coverage_map.md` | What is observed and where |
| C | `evidence/phase_c_interim_seal_2026-03-31.md` | Phase C final seal |
| C | `latency_observation_prereview.md` | Latency v1 scope decisions |
| C | `trend_observation_prereview.md` | Trend v1 scope decisions |
| D | `d0_operator_quick_map.md` | 1-page field reference |
| D | `d1_board_presentation_normalization.md` | Display layout and grouping |
| D | `d2_operator_interpretation_pack.md` | Card-by-card interpretation guide |
| D | `d3_change_control_enforcement.md` | Change review protocol |
| E | `e1_operator_runbook.md` | Daily/weekly operating routines |
| E | `e2_review_workflow.md` | Review routing with examples |
| E | `e3_handover_onboarding.md` | This document — onboarding and handover |
