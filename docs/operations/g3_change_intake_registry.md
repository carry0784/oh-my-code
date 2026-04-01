# G-3: Change Intake Registry

Effective: 2026-03-31
Status: **ACTIVE** (Phase G-3)
Author: B (Implementer)
Scope: Centralized change request tracking for sealed observation system

---

## 1. Purpose

Provide a single registry for all change requests to the sealed observation
system. Every proposed change — whether approved, deferred, or rejected —
is recorded here with its category, rationale, reviewer, and outcome.

---

## 2. Registry Rules

### Rule G3-01: All changes must be registered

No change to the observation layer (code, schema, test, document) may be
made without a registry entry. This includes Category A changes.

### Rule G3-02: Register before implementing

The registry entry must exist BEFORE the change is implemented.
Post-hoc registration is a process violation (log as incident).

### Rule G3-03: Category assignment is immutable after review

Once A assigns a category (or B self-assigns for A/B), the category
cannot be downgraded without A's explicit approval.
Upgrading (B->C, C->D) is always allowed.

### Rule G3-04: Rejected/deferred changes stay in the registry

Do not delete entries for rejected or deferred changes.
They serve as precedent for future similar requests.

---

## 3. Change Request Ledger

| CR-ID | Date | Requester | Description | Category | Reviewer(s) | Decision | Evidence | Notes |
|-------|------|-----------|-------------|----------|-------------|----------|----------|-------|
| CR-001 | (example) | (name) | (what) | (A/B/C/D) | (who) | (approved/rejected/deferred) | (commit/doc link) | (notes) |

### Field Definitions

| Field | Description |
|-------|-------------|
| CR-ID | Sequential identifier: CR-001, CR-002, ... |
| Date | Date the request was registered (YYYY-MM-DD) |
| Requester | Person or role requesting the change |
| Description | One-line description of the proposed change |
| Category | A (no review) / B (self-review) / C (A/B/C review) / D (constitutional) |
| Reviewer(s) | Who reviewed (B for A/B, A+B+C for C/D) |
| Decision | approved / rejected / deferred / withdrawn |
| Evidence | Link to commit, PR, or document |
| Notes | Additional context, conditions, or follow-up |

---

## 4. Intake Process

### Step 1: Submit Request

Requester fills out:

```
CR-ID: (next sequential)
Date: YYYY-MM-DD
Requester: (name/role)
Description: (one line)
Proposed category: (A/B/C/D or "unsure")
Justification: (why this change is needed)
Affected files: (list)
Affected OC rules: (list or "none")
```

### Step 2: Category Classification

Follow E-2 decision tree:

- If requester is confident in category: B verifies
- If requester is unsure: A classifies
- If A is unsure: default to Category C

### Step 3: Review Routing

| Category | Route |
|----------|-------|
| A | B records and proceeds |
| B | B implements with self-review commit note |
| C | B writes proposal, A reviews scope, C inspects compliance |
| D | B writes amendment, A+B+C unanimous review |

### Step 4: Record Outcome

Update the ledger with:
- Decision (approved/rejected/deferred)
- Evidence (commit hash, PR link, or doc reference)
- Notes (conditions, follow-up required)

---

## 5. Category Distribution Tracking

Maintain a running tally:

```
Month: YYYY-MM

| Category | Submitted | Approved | Rejected | Deferred |
|----------|-----------|----------|----------|----------|
| A        |           |          |          |          |
| B        |           |          |          |          |
| C        |           |          |          |          |
| D        |           |          |          |          |
| Total    |           |          |          |          |

"Default to C" applied: (count)
Reclassifications: (count and details)
```

### Health Indicators

| Indicator | Healthy | Warning | Concern |
|-----------|---------|---------|---------|
| Category A/B ratio | > 60% of total | 40-60% | < 40% |
| Category D requests | 0-1 per quarter | 2-3 per quarter | > 3 per quarter |
| Rejection rate | < 20% | 20-40% | > 40% |
| Default-to-C rate | < 30% of ambiguous | 30-50% | > 50% |
| Post-hoc registrations | 0 | 1-2 per month | > 2 per month |

### Interpretation

- **High A/B ratio**: System is stable, most changes are minor. Good.
- **High C/D ratio**: Many significant changes proposed. May indicate scope pressure.
- **High rejection rate**: Requesters may not understand the constraints. Training needed.
- **High default-to-C**: Decision tree may need refinement. Or changes are genuinely ambiguous.
- **Post-hoc registrations**: Process discipline gap. Address immediately.

---

## 6. Precedent Index

As the registry grows, common patterns will emerge. Maintain a short
precedent index for frequently asked categories:

| Pattern | Precedent | Category |
|---------|-----------|----------|
| Typo fix in docs | CR-xxx | A |
| Additive schema field with default | CR-xxx | B |
| Template wording refinement (same meaning) | CR-xxx | B |
| New board field | CR-xxx | C |
| v1 scope expansion | CR-xxx | C |
| Safety invariant modification | CR-xxx | D |

Update this index as real precedents accumulate during the pilot period.

---

## 7. Monthly Registry Summary

At the end of each month, produce:

```
# Change Intake Summary: YYYY-MM

Total requests: N
  Approved: N
  Rejected: N
  Deferred: N
  Withdrawn: N

By category:
  A: N
  B: N
  C: N
  D: N

Key decisions:
  - CR-xxx: (one-line summary)
  - CR-xxx: (one-line summary)

Process observations:
  - (any drift, bottleneck, or improvement noted)

Governance alignment:
  - Red lines intact: (yes/no)
  - Category consistency: (high/medium/low)
  - Escalation events: (count)
```

---

## 8. Integration with Other Phase G Documents

| Document | Integration Point |
|----------|------------------|
| G-1 Pilot Operations | Exception events may generate change requests |
| G-2 Governance Sustainment | Bi-weekly drift review uses registry data |
| D-3 Change Control | Registry enforces D-3 category routing |
| E-2 Review Workflow | Registry is the execution layer for E-2 process |

---

## 9. Current Registry

(Empty at creation. First entries will be added when changes are proposed.)

| CR-ID | Date | Requester | Description | Category | Reviewer(s) | Decision | Evidence | Notes |
|-------|------|-----------|-------------|----------|-------------|----------|----------|-------|
| CR-001 | 2026-03-31 | A | Phase D: Board Presentation Normalization | A | B | approved | d1_board_presentation_normalization.md | Documentation only, no code change |
| CR-002 | 2026-03-31 | A | Phase D: Operator Interpretation Pack | A | B | approved | d2_operator_interpretation_pack.md | Documentation only, no code change |
| CR-003 | 2026-03-31 | A | Phase D: Change Control Enforcement Pack | A | B | approved | d3_change_control_enforcement.md | Documentation only, no code change |
| CR-004 | 2026-03-31 | A | Phase D: Operator Quick Map | A | B | approved | d0_operator_quick_map.md | Documentation only, no code change |
| CR-005 | 2026-03-31 | A | Phase E: Operator Runbook Pack | A | B | approved | e1_operator_runbook.md | Documentation only, no code change |
| CR-006 | 2026-03-31 | A | Phase E: Review Workflow Pack | A | B | approved | e2_review_workflow.md | Documentation only, no code change |
| CR-007 | 2026-03-31 | A | Phase E: Handover/Onboarding Pack | A | B | approved | e3_handover_onboarding.md | Documentation only, no code change |
| CR-008 | 2026-03-31 | A | Phase G: Pilot Operations Window | A | B | approved | g1_pilot_operations_window.md | Documentation only, no code change |
| CR-009 | 2026-03-31 | A | Phase G: Governance Sustainment Loop | A | B | approved | g2_governance_sustainment_loop.md | Documentation only, no code change |
| CR-010 | 2026-03-31 | A | Phase G: Change Intake Registry | A | B | approved | g3_change_intake_registry.md | Documentation only, no code change |
| CR-011 | 2026-03-31 | A | Phase H: Pilot log + governance calendar activation | A | B | approved | h_pilot_log.md, h_governance_calendar.md | Operational activation, no code change |
| CR-012 | 2026-05-08 | A | Post-Pilot: Pilot closure seal + freeze exit control | A | B | approved | phase_h_pilot_closure_2026-05-08.md, post_pilot_change_control.md | L1 documentation, no code change |
| CR-013 | 2026-05-08 | A | Post-Pilot: Governance calendar pending items closure | A | B | approved | h_governance_calendar.md | Bi-weekly drift reviews waived (single operator), monthly audit done |
| CR-014 | 2026-05-08 | A | Post-Pilot: OKX removal closure confirmation | A | B | approved | okx_removal_seal_2026-03-30.md | Code removal pre-pilot; confirmed 0 references post-pilot |
| CR-015 | 2026-05-08 | B | Runner artifact normalization memo (RA-001) | B | B | approved | runner_artifact_normalization_2026-05-08.md | L2 diagnosis doc, no code change, split workaround retained |
| CR-016 | 2026-05-08 | A | Multi-operator readiness pack (criteria 4/5/8) | A | B | approved | multi_operator_readiness_pack.md | L1 documentation, awaiting first operator onboarding |
| CR-017 | 2026-05-08 | A | Runner normalization closure: operational standard | B | B | approved | runner_artifact_normalization_2026-05-08.md §7 | L2 ops standard, split execution mandatory, RA-001 CLOSED |
| CR-018 | 2026-05-08 | A | Multi-operator dry-run verification | B | B | approved | multi_operator_readiness_pack.md §8 | Tabletop: self-test 8/8, classification 5/5, handover template OK |
| CR-019 | 2026-05-08 | A | Cold-start observation expansion scope analysis | B | B | approved | cold_start_observation_expansion.md | Finding: no code change needed, cold-start resolves at live trading activation |
| CR-020 | 2026-05-08 | A | Warm-start activation gate pack | A | B | approved | warm_start_activation_gate.md | Gate doc: Mode 1 (obs-only) / Mode 2 (full), A decision: ACTIVATE Mode 1 |
| CR-021 | 2026-05-08 | A | Warm-start read-only verification | B | B | approved | warm_start_verification_2026-05-08.md | Mode 1 VERIFIED: 7/7 invariants, 832/0/0, workers operational |
| CR-022 | 2026-05-08 | A | Multi-operator first onboarding execution | B | A+B | approved | multi_operator_onboarding_2026-05-08.md | VERIFIED (conditional): self-test 8/8, handover PASS, classification 3/5 CONDITIONAL PASS |
| CR-023 | 2026-05-14 | B | Mode 1 sustained operation 7-day review | B | B | approved | mode1_sustained_review_2026-05-14.md | 7/7 PASS: worker 7d up, safety intact, 832/0/0, 0 incidents |
| CR-024 | 2026-05-14 | A | Mode 1 Steady-State Governance Pack | A | B | approved | mode1_steady_state_governance.md | Formalizes Mode 1 as steady-state, cadence matrix, calibration plan |
| CR-025 | 2026-05-14 | A | Classification Calibration Recheck Pack | B | A+B | approved | classification_calibration_recheck_2026-05-14.md | 4/5 PASS — calibration debt resolved, pilot 8/8 PASS |
| CR-026 | 2026-05-14 | A | Dashboard Readiness Alignment Pack | B | A+B | approved | (evidence in CR-026 report) | L2/C: API 기준 PASS, safety panel/latency/connectivity/stale 정렬 완료 |
| CR-027 | 2026-05-14 | A | ops-status evidence hot path 성능 복구 | B | A+B | approved | (sealed report in session) | L2/C: 196s→0.059s ops-status, 7.6s→0.237s aggregate, 9 files, 832/0/0, dashboard 정상 복구 |
| CR-028 | 2026-05-14 | B | backend abstraction cleanup + SQLite orphan detection 보정 | B | B | approved | evidence_read_performance_rule.md | L2/B SEALED: count_orphan_pre() facade 신설, _bundles 직접접근 0건, SQLite skip→actual compute, 3119/0/0 PASS, LOW 리스크 2건 이월 |
| CR-029 | 2026-05-14 | A | Evidence Read Performance Guard | B | B | approved | test_evidence_performance_guard.py, evidence_read_performance_rule.md | L2/B SEALED: 52 guard tests (6 axes), InMemory 10K/100K/500K + SQLite 20K smoke, budget proxy, AST 1st-line defense, 3171/0/0 PASS |
| CR-030 | 2026-05-14 | A | Orphan Aggregation Long-Term Design Review | A | B | approved | cr030_orphan_aggregation_design_review.md | SEALED: 설계 검토 전용, A안(현행유지) 채택, B/C안 구현 금지, 재검토 트리거 0/4, 후속 구현 카드 없음 |
| CR-031 | 2026-05-14 | A | Steady-State Reopen Trigger Protocol | A | B | approved | steady_state_reopen_trigger_protocol.md | SEALED: 6개 재개시 트리거, 3단계 관찰체계, 30일 무변경 관찰기간(~06-13), 금지행위 6건, 구현 금지/관찰 유지 |
| CR-032 | 2026-05-14 | A | Mode 2 Transition Readiness Assessment | A | B | approved | mode2_transition_readiness_assessment.md | L1/A: 실행 파이프라인 7개 컴포넌트 검증, 안전장치 10개 감사, 3단계 전환 계획(M2-1/M2-2/M2-3) |
| CR-033 | 2026-05-14 | A | M2-1 Live-Read Execution Verification | B | A+B | approved | m2_1_live_read_execution.md | SEALED: CONDITIONAL PASS, Auth/Balance/Ticker/WriteBlock PASS, Dashboard DB timeout 분리(CR-034), TESTNET=true 복원 |
| CR-034 | 2026-03-31 | A | Dashboard PostgreSQL datetime timeout 수정 | B | A+B | approved | cr034_dashboard_db_timeout_investigation.md | SEALED: BL-TZ02 naive UTC 경계 정규화, 1파일/8줄, DataError 0건, enforcement NORMAL 복원, 3171/0/0 PASS |
| CR-035 | 2026-03-31 | B | v2 endpoint timeout 원인 격리 + 재발 방지 | B | A+B | **SEALED** | cr035_v2_timeout_investigation.md, cr035_phase_b_prevention.md | SEALED: Phase A 운영 사고 확정, Phase B 3계층 방지(dispose 7곳 + pool 방어 + 기동 가드), 3171/0/0 PASS, M2-2 REVIEW 준비 |
| M2-1.5 | 2026-03-31 | A | Dry-Run Pipeline Passthrough Test | B | A | **SEALED** | m2_1_5_dryrun_passthrough.md | SEALED — PASS: 10/10 체크리스트, 15 guard PASS, abort 3건 정상, side-effect 0, 3-tier lineage 정합 |
| M2-2 | 2026-03-31 | A | Micro-Live 단일 주문 실행 | B | A | **SEALED** | m2_2_review_package.md, m2_2_post_run_review.md | SEALED — PASS: Binance order 59922222570 FILLED, 0.00015 BTC @ 66292.36 (9.94 USDT), 15 guard PASS, constitution 10/10 |
| CR-036 | 2026-03-31 | B | M2-2 execution path contract fix | B | A | **SEALED** | cr036_execution_path_contract_fix.md | SEALED: spot 모드 복원 + create_order 계약 정합, 5테스트 PASS, 3176/0/0 PASS, dry-run 10/10 재검증 |
| CR-037 | 2026-03-31 | B | create_market_order params keyword contract fix | B | A | **SEALED** | cr037_params_keyword_contract_fix.md | SEALED: params dict→CCXT price 위치 바인딩 수정, 1파일 2줄, M2-2 FILLED로 실증, 추가 live HOLD 해제 |
| CR-038 | 2026-04-01 | A | Phase 1: 데이터 수집 계층 확장 (자가진화형 시스템 기반) | C | A+B | **SEALED** | commit c702810 | SEALED: 11 신규 + 3 수정, 57 tests, 3233/0/0 PASS, 무료 온체인 API 4개(Alternative.me+Blockchain.com+Mempool.space+CoinGecko), 실행 경로 변경 0건 |
| CR-039 | 2026-04-01 | A | Phase 2: Regime Detection + 분석 엔진 (자가진화형 시스템) | C | A+B | approved | (구현 중) | 신규: regime_detector, market_scorer, market_state_analyzer, /api/v1/market-state 엔드포인트. 기존 실행 경로 변경 0건 |
