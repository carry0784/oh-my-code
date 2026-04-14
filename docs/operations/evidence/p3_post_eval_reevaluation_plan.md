# P3 Post-Eval Reevaluation Plan

## Plan Metadata

| Field | Value |
|---|---|
| reevaluation_plan_id | `REEVAL-PLAN-D001` |
| issued_at | 2026-04-14T01:00:00Z |
| issued_by | governance_loop |
| scope | reevaluation_procedure_design_only |
| main_baseline_ref | `11cd437` (Phase A closure) |
| production_authorized | **FALSE** |
| live_release_permission | **FORBIDDEN** |
| p3_non_interference_confirmed | **TRUE** |
| input_documents | `phase_a_closure_receipt.md`, `advisory_ledger_b001.md`, `deployment_readiness_receipt.md` |

---

## 1. Evaluation Basis Window

| Field | Value |
|---|---|
| p3_start_date | 2026-04-14 (shadow activation) |
| p3_end_date | ~2026-04-28 (14D window) |
| minimum_bars | 336 (14D x 24H, VAL-QTY-001) |
| minimum_novelty_events | 10 (VAL-QTY-001 S2P-EI1) |
| evaluation_trigger | P3 window close (bar count >= 336 AND elapsed >= 14D) |
| evaluation_mode | post-hoc batch (NOT real-time) |

### Window Rules

- Evaluation begins only AFTER P3 window closes. Mid-window evaluation is forbidden.
- If minimum_bars or minimum_novelty_events are not met at window close, the window extends automatically until both thresholds are satisfied.
- No manual override to shorten the window.

---

## 2. Evaluation Input Priority

| Priority | Input Source | Description |
|---|---|---|
| 1 | P3 observed evidence | PPFNoveltyEvent rows, shadow gate evaluations, LV-2/LV-3 ledger entries accumulated during P3 window |
| 2 | VAL-PDC-002 comparison report | PPFComparisonReport from PPFBacktestComparator.compare() — live vs backtest baseline metrics |
| 3 | PPF validation chain receipts | P1 (implementation seal), P2 (backtest baseline), P3 (shadow accumulation) completion records |
| 4 | Advisory ledger (ADV-LEDGER-B001) | 7 advisories — hard/conditional/accepted_risk status |
| 5 | Deployment readiness receipt (DEPLOY-READY-C001) | Probe/metrics/rollback validation results |
| 6 | Topology-specific confirmations | Network exposure, K8s namespace config — required for conditional blocker resolution |

**Principle: Observed data (priority 1-2) always takes precedence over preparation documents (priority 3-6). If observed data contradicts a prior receipt, observed data wins.**

---

## 3. Comparator Input Set

### 3.1 Primary Metrics (from PPFBacktestComparator)

| Metric | Comparison Method | Tolerance | Source |
|---|---|---|---|
| novelty_rate | \|live - backtest\| <= 0.05 | +/-5 pp | PPFNoveltyEvent count / evaluated bars |
| fpr | \|live - backtest\| <= 0.05 | +/-5 pp | JudgmentReport (TP/FP classification) |
| deny_reason_distribution | Jensen-Shannon divergence <= 0.1 | JS <= 0.1 | Novelty event deny_reason_code distribution |
| deny_rate | NOT COMPUTED (structural limitation) | n/a | Absence recorded in insufficiency_reasons |
| state_distribution | NOT COMPUTED (not yet implemented) | n/a | Absence recorded in insufficiency_reasons |

### 3.2 Quantity Thresholds (VAL-QTY-001)

| Threshold | Value | Purpose |
|---|---|---|
| MIN_LIVE_BARS | 336 | Statistical significance floor |
| MIN_NOVELTY_EVENTS | 10 | Minimum sample for FPR calculation |

### 3.3 Supplementary Inputs

| Input | Source | Purpose |
|---|---|---|
| Baseline seal integrity | PPFBaselineManager.verify_seal() | Tamper detection (SHA-256 of frozen metrics) |
| Constitution compliance | C1-C11 check suite | Gate-only, no-order, no-adaptation invariants |
| Governance hard block status | PPFGovernanceEngine.check_live_entry() | Always returns HARD_BLOCK (permanent) |
| LV-2 execution divergence | execution_ledger entries | Post-execution comparison: PPF gate vs actual outcome |
| LV-3 session lifecycle | session_ledger entries | Session-level PPF behavior patterns |

---

## 4. Gate Conditions

### 4.1 VAL-PDC-002 Criteria (7 gates)

| Gate | Name | Condition | Source |
|---|---|---|---|
| C1 | MIN_BARS | bars_collected >= 336 | Phase B bar counter |
| C2 | DENY_RATE_DELTA | \|backtest - live\| <= 5 pp | ComparisonMetric (or insufficiency note) |
| C3 | FPR_DELTA | \|backtest - live\| <= 5 pp | ComparisonMetric |
| C4 | STATE_JS_DIVERGENCE | JS divergence <= 0.1 | ComparisonMetric |
| C5 | MIN_NOVELTY_EVENTS | novelty_events >= 10 | PPFNoveltyEvent count |
| C6 | SEAL_INTEGRITY | seal_valid == True | PPFBaselineManager.verify_seal() |
| C7 | NO_HARD_BLOCK | governance_has_hard_block == False | PPFGovernanceEngine |

### 4.2 Promotion Tier (computed from gate results)

| Tier | Conditions | Allowed Next Action |
|---|---|---|
| GREEN | novelty_events >= 10 AND all_checks_passed == True | Paper entry gate opens |
| YELLOW | novelty_events 5-9 AND all_checks_passed == True | HOLD only |
| RED | novelty_events < 5 OR all_checks_passed == False | BLOCK — all gates closed |

---

## 5. Hold / Pass / Block Criteria

### 5.1 HOLD Criteria

Reevaluation results in HOLD when ANY of the following are true:

| ID | Condition | Resolution Path |
|---|---|---|
| H1 | VAL-PDC-002 verdict = HOLD (tier YELLOW, 5-9 novelty events) | Extend observation window until novelty_events >= 10 |
| H2 | VAL-PDC-002 C6 fails (seal re-verification needed) | Re-run seal verification; if tampered, escalate to BLOCK |
| H3 | Conditional blocker (A2/A4/A6) relevant to target topology but unresolved | Resolve blocker or confirm non-applicability |
| H4 | Probe gap (Celery Worker/Beat) unresolved | Implement missing probes before paper entry |
| H5 | Insufficiency reasons present in PPFComparisonReport | Assess if structural (permanent) or temporal (wait for more data) |

**HOLD does not grant any permission. It means "wait and re-evaluate."**

### 5.2 PASS Criteria

Reevaluation results in PASS when ALL of the following are true:

| ID | Condition | Verification |
|---|---|---|
| P1 | VAL-PDC-002 verdict = GO (all 7 criteria pass, tier GREEN) | ValPDC002Judge.judge() output |
| P2 | Hard blockers A1, A7 = RESOLVED | Advisory ledger updated entry |
| P3 | Conditional blockers resolved OR confirmed non-applicable for target topology | Advisory ledger + topology confirmation |
| P4 | Probe validation = FULL PASS (including Celery) | Updated deployment readiness receipt |
| P5 | Constitution C1-C11 compliance = PASS | Constitution check suite output |
| P6 | P3 non-interference confirmed throughout window | LV-2/LV-3 ledger review |

**PASS enables shadow-to-paper transition planning. PASS does NOT authorize production or live entry.**

### 5.3 BLOCK Criteria

Reevaluation results in BLOCK when ANY of the following are true:

| ID | Condition | Implication |
|---|---|---|
| B1 | VAL-PDC-002 verdict = BLOCK (tier RED or critical metric failure) | Full stop. New baseline may be required. |
| B2 | Hard blocker A1 or A7 still OPEN at reevaluation time | Production gate remains locked. No state transition. |
| B3 | Constitution violation detected during P3 window | PPF deactivated (fail-closed). Requires investigation CR. |
| B4 | Baseline seal tampered (C6 fail + re-verification fail) | Baseline invalidated. New Phase A required. |
| B5 | P3 non-interference violated | All P3 data potentially tainted. Window restart required. |

**BLOCK requires explicit human intervention and a new Change Request before any re-attempt.**

---

## 6. Blocker Dependency Rules

### 6.1 Hard Blocker Resolution Requirements

| Blocker | Required Resolution | Gate Effect |
|---|---|---|
| A1 (Secret Key) | Startup assertion rejecting `"change-me-in-production"` deployed and verified | Unblocks production_authorized evaluation (does not auto-grant) |
| A7 (NetworkPolicy) | K8s NetworkPolicy manifests applied: API->DB, Worker->Redis/DB, Beat->Redis | Unblocks production_authorized evaluation (does not auto-grant) |

**Rule: Hard blocker resolution is NECESSARY but NOT SUFFICIENT for production_authorized = TRUE.**

### 6.2 Conditional Blocker Resolution Rules

| Blocker | Resolution Condition | Evaluation Time |
|---|---|---|
| A2 (Rate Limiting) | Required if API is network-exposed; not required if localhost/pod-internal | At topology confirmation |
| A4 (Dependency Audit) | Recommended; non-blocking if dependencies manually reviewed | At deployment preparation |
| A6 (Log Sanitization) | Required before production log aggregation is enabled | At observability stack deployment |

**Rule: Conditional blockers remain OPEN until topology is confirmed. They do not block HOLD/PASS verdict but do block production_authorized = TRUE if applicable.**

---

## 7. Promotion Open Prerequisites

`promotion_open = TRUE` requires ALL of the following simultaneously:

| # | Prerequisite | Current Status |
|---|---|---|
| 1 | VAL-PDC-002 verdict = GO | PENDING (P3 in progress) |
| 2 | Promotion tier = GREEN | PENDING (P3 in progress) |
| 3 | Hard blockers A1, A7 = RESOLVED | OPEN |
| 4 | Applicable conditional blockers = RESOLVED | OPEN |
| 5 | Deployment readiness = FULL PASS | CONDITIONAL (probe gap) |
| 6 | Constitution C1-C11 = PASS | ASSUMED PASS (verified at P1) |
| 7 | Explicit human Change Request issued | NOT ISSUED |
| 8 | production_authorized explicitly set to TRUE by human | **FALSE** |

**promotion_open is a conjunction. ANY single prerequisite failing keeps promotion closed.**

**Automatic promotion is permanently forbidden (FZ-05). No code path, governance state, or verdict combination can set promotion_open = TRUE without human action.**

---

## 8. Shadow to Paper to Live Order

### 8.1 State Transition Sequence

```
SHADOW (current)
  │
  ├── P3 window close
  ├── VAL-PDC-002 issued
  ├── Reevaluation verdict
  │
  ▼
PAPER (requires ALL of: PASS verdict + promotion_open + human CR)
  │
  ├── Paper accumulation window (TBD — separate CR)
  ├── Paper performance evaluation
  │
  ▼
LIVE (requires ALL of: paper PASS + hard blockers RESOLVED + human CR + production_authorized = TRUE)
```

### 8.2 Transition Gate Matrix

| Transition | Gate | Automated? | Human Required? |
|---|---|---|---|
| SHADOW -> PAPER | VAL-PDC-002 GO + GREEN + promotion_open | Verdict automated, gate check automated | **YES** — human CR to authorize transition |
| PAPER -> LIVE | Paper performance PASS + all blockers RESOLVED + production_authorized | Verdict automated | **YES** — human CR + explicit production_authorized = TRUE |
| Any -> SHADOW (rollback) | Performance degradation or governance violation detected | Automated detection | **YES** — human confirms rollback scope |

### 8.3 Paper Phase Design (scope boundary)

Paper phase detailed design is OUT OF SCOPE for this plan. It requires a separate Change Request that defines:
- Paper accumulation window duration
- Paper performance metrics and thresholds
- Paper-to-live gate criteria
- Paper-specific risk limits

This plan only establishes that paper phase EXISTS in the sequence and its entry prerequisites.

---

## 9. Forbidden Transitions

| ID | Forbidden Transition | Reason | Enforcement |
|---|---|---|---|
| FT-01 | SHADOW -> LIVE (skip paper) | Paper validation mandatory | PPFGovernanceEngine state machine (no direct transition path) |
| FT-02 | Any -> production_authorized = TRUE (automatic) | Human-only gate | No code path sets production_authorized = TRUE |
| FT-03 | HOLD -> PAPER (skip PASS) | HOLD means insufficient evidence | Reevaluation verdict must be PASS |
| FT-04 | BLOCK -> PAPER (skip resolution) | BLOCK requires CR and investigation | New Change Request required |
| FT-05 | Any -> promotion_open = TRUE (automatic) | Human CR mandatory | FZ-05 permanent prohibition |
| FT-06 | P3 window shorten (manual override) | Statistical validity protection | No manual override path exists |
| FT-07 | Conditional blocker -> RESOLVED (without topology confirmation) | Topology-dependent resolution | Blocker stays OPEN until topology confirmed |
| FT-08 | VAL-PDC-002 GO -> production_authorized = TRUE (inference) | Test PASS != production approval | FZ-05: live_authorized always False |
| FT-09 | Reevaluation PASS -> auto-execute promotion | Plan != execution | Separate human-authorized CR required |
| FT-10 | Hard blocker RESOLVED -> production_authorized = TRUE (inference) | Necessary but not sufficient | Additional prerequisites required (see Section 7) |

---

## 10. Audit Fields

| Field | Value | Purpose |
|---|---|---|
| reevaluation_plan_id | `REEVAL-PLAN-D001` | Unique identifier for this plan |
| plan_version | `1.0` | Document version |
| governance_state_at_issuance | A=COMPLETE, B=COMPLETE, C=COMPLETE, D=THIS | Phase tracking |
| main_baseline_ref | `11cd437` | Code baseline reference |
| readiness_status | `CONDITIONALLY_PREPARED_NOT_AUTHORIZED` | From DEPLOY-READY-C001 |
| production_authorized | `FALSE` | Standing invariant |
| p3_window_status | `ACTIVE` (~04-14 to ~04-28) | Shadow accumulation in progress |
| advisory_open_count | 5 | From ADV-LEDGER-B001 |
| advisory_hard_block_count | 2 (A1, A7) | Production-blocking advisories |
| advisory_conditional_count | 3 (A2, A4, A6) | Topology-dependent advisories |
| advisory_accepted_risk_count | 2 (A3, A5) | No action required |
| val_pdc_002_status | `PENDING` | Awaiting P3 window close |
| promotion_tier | `PENDING` | Computed after VAL-PDC-002 |
| promotion_open | `FALSE` | Standing state |
| live_authorized | `FALSE` | Permanent prohibition in current code |
| next_evaluation_date | ~2026-04-28 | P3 window close |
| next_action | Wait for P3 window close, then execute reevaluation procedure | No premature action |

---

## Governance Constraints

| Constraint | Value | Enforcement |
|---|---|---|
| production_authorized | **FALSE** | Standing invariant — human-only gate |
| live_release_permission | **FORBIDDEN** | No code path enables live |
| p3_non_interference | **TRUE** | Shadow accumulation protected |
| auto_transition | **FORBIDDEN** | All state transitions require human CR |
| auto_promotion | **FORBIDDEN** | FZ-05 permanent prohibition |
| plan_execution_conflation | **FORBIDDEN** | This plan defines procedure, not execution authority |

---

## Attestation

This plan certifies that the P3 post-evaluation reevaluation procedure (Phase D) has been designed under `reevaluation_procedure_design_only` scope.

- The plan defines WHAT data to evaluate, HOW to judge it, and WHAT transitions are possible.
- The plan does NOT authorize any execution, promotion, or state transition.
- Hard blockers A1 and A7 must be RESOLVED before production_authorized can be evaluated.
- Conditional blockers A2, A4, A6 remain OPEN until topology is confirmed.
- P3 observed data is the highest-priority input for reevaluation.
- Automatic transition and automatic promotion are permanently forbidden.

**Phase D (Reevaluation Plan): COMPLETE**
**Production Authorization: NOT GRANTED**
**Promotion Open: FALSE**
