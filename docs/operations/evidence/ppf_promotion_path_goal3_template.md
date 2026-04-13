# VAL-PDC-002: PPF Shadow → Paper Promotion Re-assessment Template

```
validation_id              = VAL-PDC-002
validation_scope           = PROMOTION_DECISION_SHADOW_TO_PAPER
authority_boundary         = DECISION_ASSESSMENT
execution_binding          = NONE
promotion_open             = FALSE (to be re-evaluated at fill time)
production_authorized      = FALSE
auto_advance               = FORBIDDEN
status                     = TEMPLATE_UNFILLED
```

---

## Purpose

This document is the template scaffold for VAL-PDC-002 — the re-assessment judgment
that resolves the VAL-PDC-001 HOLD when recheck conditions are met.

This template MUST NOT be filled before all prerequisites below are TRUE.
Filling this template constitutes the Shadow → Paper promotion re-assessment.
The filled document becomes the binding judgment for that transition.

**Current state**: TEMPLATE_UNFILLED. VAL-PDC-001 HOLD is active.
**Predecessor**: VAL-PDC-001 HOLD (sealed 2026-04-13, reason=EVIDENCE_INSUFFICIENT)

---

## Prerequisites (must all be TRUE before filling)

- [ ] gate_connected = TRUE
      Evidence: shadow connect confirmed (orchestrator.py step 5.75 active)
- [ ] gate_days_14 = TRUE (14+ days shadow operation)
      Evidence: ppf_shadow_tasks beat task running continuously ≥ 14 calendar days
- [ ] gate_novelty_10 = TRUE (10+ novelty events observed)
      Evidence: ppf_novelty_events table count ≥ 10 where deny_reason_code = NOVELTY_BRAKE
- [ ] gate_fpr_complete = TRUE (all observation windows closed + judged)
      Evidence: PPFNoveltyEvent.observation_window_closed = True for all events,
               fpr_judgment populated (TP/FP/UNRESOLVED) for all closed windows
- [ ] gate_enf_complete = TRUE (enforcement behavior verified)
      Evidence: enf_judgment populated (ENFORCED/BYPASSED/DEGRADED) for all events

---

## Input Metrics (fill from ppf_novelty_events table)

| Metric | Value | Tier |
|--------|-------|------|
| S2P-M1: Total events (novelty_brake count) | __ | __ |
| S2P-M2: UNRESOLVED % (of judged events) | __% | __ |
| S2P-M3: ENFORCED % (of ENF-judged events) | __% | __ |
| S2P-M4: BYPASSED count | __ | __ |
| S2P-M5: Constitution violations | __ | __ |
| S2P-M6: ABORT sessions % | __% | __ |
| S2P-EI1: Min events (raw count) | __ | __ |
| S2P-EI3: Shadow days (calendar days of continuous operation) | __ | __ |

### Tier Reference (from VAL-QTY-001)

| Metric | GREEN | YELLOW | RED |
|--------|-------|--------|-----|
| S2P-M1 | ≥ 10 | 5–9 | < 5 |
| S2P-M2 | ≤ 20% | 21–35% | > 35% |
| S2P-M3 | ≥ 90% | 70–89% | < 70% |
| S2P-M4 | = 0 | — | ≥ 1 (HARD_BLOCK) |
| S2P-M5 | = 0 | — | ≥ 1 (HARD_BLOCK) |
| S2P-M6 | ≤ 10% | 11–25% | > 25% |
| S2P-EI1 | ≥ 10 | 5–9 | < 5 |
| S2P-EI3 | ≥ 14 days | 7–13 days | < 7 days |

---

## Block Assessment

| Block Type | Active | Reason |
|-----------|--------|--------|
| HARD_BLOCK | __ | __ (fill: BYPASSED ≥ 1 or Constitution violations ≥ 1) |
| SOFT_BLOCK | __ | __ (fill: DEGRADED events, or unresolved GAP) |
| EVIDENCE_INSUFFICIENT | __ | __ (fill: S2P-EI1 or S2P-EI3 below GREEN) |

---

## Overall Tier Determination

```
Individual tiers: __, __, __, __, __, __, __, __
                  M1  M2  M3  M4  M5  M6  EI1 EI3

Overall tier = __ (worst single tier among M1–M6, EI1, EI3)
```

---

## Decision

```
HARD_BLOCK  active: __  (YES/NO)
SOFT_BLOCK  active: __  (YES/NO)
EVIDENCE_INSUFFICIENT active: __ (YES/NO)
Overall tier: __

decision_outcome = __ (GO / HOLD / BLOCK)
```

### Decision Logic (from VAL-PRM-001)

| decision_outcome | Condition |
|-----------------|-----------|
| GO | Overall tier=GREEN + all BLOCKs inactive |
| HOLD | EVIDENCE_INSUFFICIENT only active + HARD/SOFT_BLOCK inactive |
| BLOCK | HARD_BLOCK ≥ 1 active, or tier=RED from structural violation |

---

## State Transition

```
BEFORE: VAL-PDC-001 HOLD (reason=EVIDENCE_INSUFFICIENT, sealed 2026-04-13)
AFTER:  VAL-PDC-002 __ (fill at judgment time)
```

---

## Authorization

```
promotion_open             = __ (TRUE only if decision_outcome = GO)
enforce_deny_transition    = __ (TRUE only if promotion_open = TRUE)
auto_advance               = FORBIDDEN (always)
execution_binding          = NONE (assessment only; no code change embedded here)
```

### Transition Procedure (execute only if decision_outcome = GO)

1. Verify all prerequisites above are checked TRUE.
2. Fill all Input Metrics from live ppf_novelty_events table.
3. Confirm HARD_BLOCK and SOFT_BLOCK are inactive.
4. Set promotion_open = TRUE and enforce_deny_transition = TRUE in this document.
5. In app/agents/orchestrator.py: change manifest from SHADOW_MANIFEST to PAPER_MANIFEST.
6. Run full test suite: `pytest tests/test_ppf_enforcement_simulation.py -v`
7. Confirm all 25 tests pass.
8. Deploy and record deployment timestamp.
9. Seal this document with filled values and deployment evidence.

---

## Forbidden Areas

| ID | Prohibition | Status |
|----|-------------|--------|
| F-1 | Fill this template before all prerequisites are TRUE | BLOCKED |
| F-2 | Set promotion_open=TRUE without decision_outcome=GO | BLOCKED |
| F-3 | Execute manifest swap before this template is filled and sealed | BLOCKED |
| F-4 | Override HOLD → GO without evidence accumulation | BLOCKED |
| F-5 | auto_advance in any form | BLOCKED |
| F-6 | Skip VAL-PDC-002 and proceed to GUARDED/PRODUCTION directly | BLOCKED |

---

## Audit Fields (fill at judgment time)

| Field | Value |
|-------|-------|
| `pdc_validation_id` | VAL-PDC-002 |
| `pdc_predecessor` | VAL-PDC-001 |
| `pdc_template_created` | 2026-04-13 |
| `pdc_filled_at` | __ |
| `pdc_filled_by` | __ |
| `pdc_decision_outcome` | __ |
| `pdc_overall_tier` | __ |
| `pdc_hard_blocks` | __ |
| `pdc_soft_blocks` | __ |
| `pdc_novelty_event_count` | __ |
| `pdc_shadow_days` | __ |
| `pdc_fpr_completed` | __ |
| `pdc_enf_completed` | __ |
| `pdc_promotion_open` | __ |
| `pdc_enforce_deny_transition` | __ |
| `pdc_auto_advance` | FORBIDDEN |
| `pdc_review_status` | TEMPLATE_UNFILLED |
