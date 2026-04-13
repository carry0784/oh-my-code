# PPF Enforcement Readiness (Goal 6): enforce_deny=True Transition

```
document_id                = PPF-ENF-READINESS-001
scope                      = ENFORCE_DENY_TRANSITION_READINESS
authority_boundary         = READINESS_ASSESSMENT
execution_binding          = NONE
enforce_deny_authorized    = FALSE
auto_advance               = FORBIDDEN
assessed_at                = 2026-04-13
```

---

## Current State

```
enforce_deny      = False   (SHADOW_MANIFEST — shadow mode, deny overridden to allow)
target_state      = True    (PAPER_MANIFEST  — deny enforcement active)
transition_gate   = VAL-PDC-002 (template unfilled; requires 14d + 10 events)
```

The `enforce_deny` flag controls whether the PPF gate actually blocks execution:

```
SHADOW (enforce_deny=False): effective_allowed = raw OR True  = always True
PAPER  (enforce_deny=True):  effective_allowed = raw OR False = raw (true gate decision)
```

No code change is required to implement the transition itself — it is a manifest swap
in `app/agents/orchestrator.py` from `SHADOW_MANIFEST` to `PAPER_MANIFEST`.

---

## Code Readiness

| Item | Status | Evidence |
|------|--------|---------|
| PAPER_MANIFEST defined | PASS | strategies/ppf/ppf_gate_handler.py |
| enforce_deny formula verified (effective = raw OR NOT enforce_deny) | PASS | tests/test_ppf_enforcement_simulation.py TestEnforcementLogicFormula |
| Shadow→Paper behavior change verified | PASS | TestShadowToPaperTransitionChangesBehavior |
| Shadow allows on novelty brake | PASS | TestShadowManifestAllowsOnNoveltyBrake |
| Paper denies on novelty brake | PASS | TestPaperManifestDeniesOnNoveltyBrake |
| Paper allows when gate passes | PASS | TestPaperManifestAllowsWhenGatePasses |
| All 4 manifests frozen (C10) | PASS | TestAllManifestsEnforceDenyFlag::test_all_manifests_are_frozen |
| Shadow enforce_deny=False confirmed | PASS | TestAllManifestsEnforceDenyFlag::test_shadow_manifest_enforce_deny_false |
| Paper enforce_deny=True confirmed | PASS | TestAllManifestsEnforceDenyFlag::test_paper_manifest_enforce_deny_true |
| Guarded enforce_deny=True confirmed | PASS | TestAllManifestsEnforceDenyFlag::test_guarded_manifest_enforce_deny_true |
| Live enforce_deny=True confirmed | PASS | TestAllManifestsEnforceDenyFlag::test_live_manifest_enforce_deny_true |
| All manifests record_lv2=True | PASS | TestAllManifestsEnforceDenyFlag::test_all_manifests_record_lv2_true |
| All manifests record_lv3=True | PASS | TestAllManifestsEnforceDenyFlag::test_all_manifests_record_lv3_true |
| Handler-absent safe (orchestrator guard) | PASS | app/agents/orchestrator.py if self.ppf_gate_handler is not None |
| SCORE_THRESHOLD_DENY path verified | PASS | TestScoreThresholdDenyCode |
| deny_reason_code_version populated | PASS | TestShadowManifestAllowsOnNoveltyBrake::test_shadow_manifest_deny_reason_code_version_present |

**Test suite result**: 25/25 PASS (tests/test_ppf_enforcement_simulation.py)

---

## Operational Readiness

| Item | Status | Evidence |
|------|--------|---------|
| Shadow accumulation task registered | PASS | workers/tasks/ppf_shadow_tasks.py in celery_app.py include[] |
| Beat schedule entry active | PASS | ppf-shadow-eval-hourly (3600s, SOL/USDT) |
| SHADOW_MANIFEST used in shadow task | PASS | ppf_shadow_tasks.py manifest=SHADOW_MANIFEST |
| Novelty event persistence model | PASS | app/models/ppf_novelty_event.py PPFNoveltyEvent |
| Observation window advancement | PASS | ppf_shadow_tasks._advance_observation_windows |
| Fail-closed on error | PASS | ppf_shadow_tasks all exceptions caught, no side effects |
| Redis lock configured | PASS | _LOCK_KEY="ppf_shadow_eval_running", TTL=420s |
| max_retries=0 | PASS | @celery_app.task(max_retries=0) |
| Novelty events accumulated (≥ 10) | PENDING | 0/10 — shadow connect recently completed (2026-04-13) |
| Shadow operation (≥ 14 days) | PENDING | 0/14 — shadow connect recently completed (2026-04-13) |
| FPR judgments complete | PENDING | 0 judged — observation windows not yet closed |
| ENF judgments complete | PENDING | 0 judged — ENF judgment requires closed FPR window |
| VAL-PDC-002 template filled | PENDING | Template created; fill requires all above PENDING → PASS |

---

## Transition Procedure (for future execution, only after VAL-PDC-002 decision_outcome=GO)

### Step 1 — Verify operational prerequisites
```
ppf_novelty_events count WHERE deny_reason_code='NOVELTY_BRAKE' >= 10
ppf_novelty_events count WHERE observation_window_closed=True = all events
ppf_novelty_events fpr_judgment populated for all closed windows
ppf_novelty_events enf_judgment populated for all events
shadow_days >= 14 (continuous ppf-shadow-eval-hourly execution)
```

### Step 2 — Fill and seal VAL-PDC-002 template
```
docs/operations/evidence/ppf_promotion_path_goal3_template.md
decision_outcome must = GO
promotion_open must = TRUE
```

### Step 3 — Execute manifest swap
```python
# app/agents/orchestrator.py — change this line:
# BEFORE:
manifest=SHADOW_MANIFEST
# AFTER:
manifest=PAPER_MANIFEST
```

### Step 4 — Verify
```bash
pytest tests/test_ppf_enforcement_simulation.py -v
# Expected: 25 passed
```

### Step 5 — Deploy and record
```
Record deployment timestamp in VAL-PDC-002 audit fields.
Seal VAL-PDC-002.
```

---

## Blockers (as of 2026-04-13)

| Blocker | Type | Resolution |
|---------|------|-----------|
| EVIDENCE_INSUFFICIENT: 0/10 novelty events | OPERATIONAL | Accumulate via shadow operation |
| EVIDENCE_INSUFFICIENT: 0/14 shadow days | OPERATIONAL | Time passage (minimum 2026-04-27) |
| VAL-PDC-002 template unfilled | GATE | Fill after operational prerequisites met |
| NO CODE CHANGES REQUIRED | INFO | Transition = manifest swap only |

---

## Forbidden Areas

| ID | Prohibition |
|----|-------------|
| F-1 | Set enforce_deny=True (swap to PAPER_MANIFEST) before VAL-PDC-002 GO judgment |
| F-2 | Bypass VAL-PDC-002 gate under any circumstance |
| F-3 | Override PENDING items as PASS without actual data |
| F-4 | auto_advance in any form |
