# VAL-PRM-001: PPF Novelty Promotion Gate Criteria — Definition

```
validation_id              = VAL-PRM-001
validation_scope           = PROMOTION_GATE_CRITERIA_ONLY
authority_boundary         = VALIDATION_TO_PROMOTION_CRITERIA
execution_binding          = NONE
promotion_open             = FALSE
production_authorized      = FALSE
auto_advance               = FORBIDDEN
numeric_target_definition  = explicitly_deferred_outside_current_scope
```

---

## 1. Doctrine Check

| Doctrine Principle | Status | Evidence |
|----|--------|---------|
| 자동·자율·자가진화형 구조 | COMPLIANT | 기존 골격 변경 없이 Validation → Promotion Criteria 체인 내부에서 정의 |
| 7-layer 골격 고정 | COMPLIANT | Observation / Interpretation / Decision / Execution / Learning / Evolution / Constitution 변경 없음 |
| 승격 기준 정의 ≠ 승격 실행 | COMPLIANT | execution_binding=NONE, promotion_open=FALSE |
| promotion_gate_criteria ≻ enforcement_safety | COMPLIANT | VAL-ENF-001 SEALED (2026-04-13) 선행 완료 |
| promotion_gate_criteria ≻ false_positive_rate | COMPLIANT | VAL-FPR-001 SEALED (2026-04-13) 선행 완료 |

---

## 2. Framework Mapping

```
Promotion Gate Criteria가 정의하는 질문:
"어떤 조건이 갖춰져야 shadow에서 paper/enforcement 판단 검토를 열 수 있는가?"

이 체인은 기준을 정의할 뿐, 실제로 열지는 않는다.

                ┌─────────────────────┐
                │   SHADOW (현재)      │
                └──────┬──────────────┘
                       │
          ┌────────────┼────────────┐
          ▼                         ▼
  ┌───────────────┐        ┌───────────────┐
  │shadow_to_paper│        │shadow_to_enf  │
  │  criteria     │        │  criteria     │
  └───────┬───────┘        └───────┬───────┘
          │                        │
    ┌─────┼─────┐            ┌─────┼─────┐
    ▼     ▼     ▼            ▼     ▼     ▼
  HARD  SOFT  EVID         HARD  SOFT  EVID
  BLOCK BLOCK INSUF        BLOCK BLOCK INSUF
```

**기준 정의 대상**: shadow → paper 전환, shadow → enforcement 전환  
**판정 주체**: 별도 승격 결정 체인 (본 체인 범위 밖)  
**본 체인 역할**: 기준 설계만. 승격 판단·실행은 금지.

---

## 3. Input Basis

| ID | 출처 | 승격 기준 입력 역할 |
|----|------|-------------------|
| VAL-FPR-001 | SEALED (2026-04-13) | TP/FP/UNRESOLVED 판정 프레임 → 승격 전 FP 비율 증거 요구 |
| VAL-ENF-001 | SEALED (2026-04-13) | ENFORCED/BYPASSED/DEGRADED 판정 프레임 → 승격 전 enforcement 안전성 증거 요구 |
| GAP-1 | VAL-ENF-001 Section 6-A | Shadow mode override → paper 승격 전 해소 필요 여부 판단 근거 |
| GAP-2 | VAL-ENF-001 Section 6-B | Post-exec recording skip → 기록 완전성 증거 요구 |
| GAP-3 | VAL-ENF-001 Section 6-C | Handler wiring verification → 배선 검증 증거 요구 |

---

## 4. Shadow → Paper Criteria (shadow_to_paper_criteria)

### 4-A. 필수 조건 (MUST)

shadow에서 paper로 전환을 **검토**하기 위해 아래 조건이 **모두** 충족되어야 한다.

| 조건 ID | 조건 명칭 | 설명 | 입력 근거 |
|---------|----------|------|----------|
| S2P-M1 | FPR 프레임 적용 실적 | VAL-FPR-001 프레임으로 최소 N건의 novelty 이벤트가 판정 완료 (TP/FP/UNRESOLVED 확정)되어야 함 | VAL-FPR-001 |
| S2P-M2 | UNRESOLVED 비율 한도 | 판정 완료 이벤트 중 UNRESOLVED 비율이 사전 정의 한도 이하 | VAL-FPR-001 |
| S2P-M3 | ENFORCED 비율 요구 | VAL-ENF-001 프레임 적용 결과 ENFORCED 비율이 사전 정의 한도 이상 | VAL-ENF-001 |
| S2P-M4 | BYPASSED 이벤트 0건 | enforcement 판정 중 BYPASSED가 0건이어야 함 | VAL-ENF-001 |
| S2P-M5 | Constitution 위반 0건 | 판정 기간 내 C6/C7/C10/C11 위반으로 PPF가 비활성화된 이력 0건 | constitution.py |
| S2P-M6 | 세션 품질 유지 | 판정 기간 내 SessionPath가 ABORT_*로 종료된 세션 비율이 한도 이하 | session_ledger.py |

**N건, 비율 한도 등 수치 목표는 본 체인에서 정의하지 않는다.** (별도 정량화 체인 범위)

### 4-B. 차단 조건 (BLOCK)

아래 조건 중 **하나라도** 해당하면 paper 전환 검토 자체가 차단된다.

#### HARD_BLOCK (절대 차단)

paper 전환을 어떤 조건에서도 허용하지 않는다. 해소 없이는 재검토 불가.

| 조건 ID | 조건 명칭 | 설명 |
|---------|----------|------|
| S2P-HB1 | BYPASSED 이벤트 존재 | enforcement 판정 중 BYPASSED가 1건 이상 존재 |
| S2P-HB2 | Constitution 위반 이력 | 판정 기간 내 constitution violation으로 PPF 비활성화 발생 |
| S2P-HB3 | VAL-FPR-001 미봉인 | FPR 프레임이 SEALED 상태가 아님 |
| S2P-HB4 | VAL-ENF-001 미봉인 | ENF 프레임이 SEALED 상태가 아님 |

#### SOFT_BLOCK (조건부 차단)

추가 검증 완료 시 해소 가능. 해소 근거를 Audit에 기록해야 함.

| 조건 ID | 조건 명칭 | 설명 | 해소 조건 |
|---------|----------|------|----------|
| S2P-SB1 | DEGRADED 이벤트 존재 | DEGRADED 판정이 1건 이상 | 원인 분석 완료 + 재발 방지 확인 |
| S2P-SB2 | GAP-2 미해소 | post-exec recording skip 미패치 | 코드 패치 또는 영향 없음 확인 |
| S2P-SB3 | GAP-3 미해소 | handler wiring 검증 미구현 | 코드 패치 또는 현재 구조로 충분함 확인 |

#### EVIDENCE_INSUFFICIENT (증거 부족)

충분한 데이터가 축적되면 자연 해소. 시간 경과로 해소 가능.

| 조건 ID | 조건 명칭 | 설명 | 해소 조건 |
|---------|----------|------|----------|
| S2P-EI1 | 판정 건수 부족 | FPR 프레임 적용 이벤트 수가 최소 요구치 미만 | 추가 shadow 운영으로 이벤트 축적 |
| S2P-EI2 | 관찰 윈도우 미완료 | 진행 중인 관찰 윈도우가 있어 판정 미확정 이벤트 존재 | 윈도우 종료 대기 |
| S2P-EI3 | 운영 기간 부족 | shadow 모드 운영 기간이 최소 요구치 미만 | 추가 shadow 운영 기간 경과 |

---

## 5. Shadow → Enforcement Criteria (shadow_to_enforcement_criteria)

### 5-A. 필수 조건 (MUST)

shadow에서 enforcement(enforce_deny=True)로 전환을 **검토**하기 위해 아래 조건이 **모두** 충족되어야 한다.

| 조건 ID | 조건 명칭 | 설명 | 입력 근거 |
|---------|----------|------|----------|
| S2E-M1 | Paper 선행 완료 | shadow → paper 전환이 먼저 실행되고, paper 운영 실적이 존재해야 함 | S2P 기준 |
| S2E-M2 | Paper 기간 FPR 실적 | paper 모드에서 FPR 프레임 적용 이벤트가 최소 N건 판정 완료 | VAL-FPR-001 |
| S2E-M3 | Paper 기간 ENFORCED 실적 | paper 모드에서 ENFORCED 비율이 한도 이상 | VAL-ENF-001 |
| S2E-M4 | Paper 기간 BYPASSED 0건 | paper 모드에서 BYPASSED 이벤트 0건 | VAL-ENF-001 |
| S2E-M5 | GAP-1 해소 확인 | shadow override 경로가 enforce_deny=True 전환 시 정상 차단되는지 검증 완료 | GAP-1 |
| S2E-M6 | Paper 기간 FP 비율 안정 | paper 모드에서 FP 비율이 이전 shadow 기간 대비 급증하지 않음 | VAL-FPR-001 |
| S2E-M7 | Constitution 위반 0건 | paper 모드 전체 기간 동안 constitution violation 0건 | constitution.py |

**N건, 비율 한도 등 수치 목표는 본 체인에서 정의하지 않는다.**

### 5-B. 차단 조건 (BLOCK)

#### HARD_BLOCK

| 조건 ID | 조건 명칭 | 설명 |
|---------|----------|------|
| S2E-HB1 | Paper 미선행 | shadow → paper 전환이 완료되지 않은 상태에서 enforcement 전환 시도 |
| S2E-HB2 | Paper 기간 BYPASSED 존재 | paper 모드에서 BYPASSED 이벤트 1건 이상 |
| S2E-HB3 | GAP-1 미해소 | shadow mode override 경로가 검증되지 않음 |
| S2E-HB4 | Constitution 위반 이력 | paper 모드 내 constitution violation 발생 |

#### SOFT_BLOCK

| 조건 ID | 조건 명칭 | 설명 | 해소 조건 |
|---------|----------|------|----------|
| S2E-SB1 | Paper 기간 DEGRADED 존재 | DEGRADED 판정 1건 이상 | 원인 분석 완료 + 재발 방지 확인 |
| S2E-SB2 | FP 비율 상승 추세 | paper 기간 FP 비율이 shadow 대비 상승 | 원인 분석 + 안정화 확인 |

#### EVIDENCE_INSUFFICIENT

| 조건 ID | 조건 명칭 | 설명 | 해소 조건 |
|---------|----------|------|----------|
| S2E-EI1 | Paper 판정 건수 부족 | paper 모드 FPR 이벤트 수가 최소치 미만 | 추가 paper 운영 |
| S2E-EI2 | Paper 운영 기간 부족 | paper 모드 운영 기간이 최소치 미만 | 추가 paper 운영 기간 경과 |

---

## 6. Promotion Block Conditions 요약

### 6-A. 3층 블록 구조

```
HARD_BLOCK           절대 차단. 해소 없이 재검토 불가.
                     → 위반 이력, 선행 미완료, 프레임 미봉인
                     
SOFT_BLOCK           조건부 차단. 추가 검증 후 해소 가능.
                     → DEGRADED 이벤트, GAP 미패치, FP 추세 이상
                     
EVIDENCE_INSUFFICIENT  증거 부족. 시간/데이터 축적으로 자연 해소.
                     → 판정 건수 부족, 윈도우 미완료, 운영 기간 부족
```

### 6-B. 블록 해소 프로토콜

| 블록 유형 | 해소 주체 | 해소 기록 | 자동 해소 |
|----------|----------|----------|----------|
| HARD_BLOCK | 별도 승격 결정 체인에서만 해소 가능 | 해소 근거 + Audit 기록 필수 | 불가 |
| SOFT_BLOCK | 분석 완료 후 수동 해소 | 원인 분석 + 재발 방지 기록 필수 | 불가 |
| EVIDENCE_INSUFFICIENT | 데이터 축적 시 자동 해소 가능 | 축적 시점 기록 | 가능 (조건 충족 시) |

### 6-C. 블록 우선순위

```
HARD_BLOCK > SOFT_BLOCK > EVIDENCE_INSUFFICIENT

HARD_BLOCK 1건 이상 → 승격 검토 자체 차단 (SOFT/EVID 무관)
SOFT_BLOCK 1건 이상 + HARD 0건 → 해소 대기 (EVID 무관)
EVIDENCE_INSUFFICIENT만 → 데이터 축적 대기
전체 0건 → 승격 검토 가능 상태 (별도 결정 체인 필요)
```

---

## 7. 승격 경로 순서 제약

```
                SHADOW
                  │
                  ▼
          ┌──── PAPER ◄── S2P 기준 충족 필요
          │       │
          │       ▼
          │  ENFORCEMENT ◄── S2E 기준 충족 필요 (paper 선행 필수)
          │       │
          │       ▼
          │  PRODUCTION  ◄── 본 체인 범위 밖 (별도 체인 필요)
          │
          └── 역방향 전이 규칙:
              PAPER → SHADOW       가능 (강등)
              ENFORCEMENT → PAPER  가능 (강등)
              ENFORCEMENT → SHADOW 가능 (긴급 강등)
              PRODUCTION → *       본 체인 범위 밖
```

**순서 제약**: `SHADOW → PAPER → ENFORCEMENT → PRODUCTION`  
**건너뛰기 금지**: `SHADOW → ENFORCEMENT` 직접 전환 불가 (S2E-HB1)  
**역방향 전이**: 강등은 허용 (안전 방향)

---

## 8. State Transition Rules

```
BEFORE:
  fpr_state         = VALIDATION_FRAME_DEFINED (SEALED)
  enf_state         = ENFORCEMENT_FRAME_DEFINED (SEALED)
  promotion_state   = PROMOTION_CRITERIA_PENDING

TRANSITION (본 문서 완료 시):
  promotion_state   = PROMOTION_CRITERIA_DEFINED

BLOCKED TRANSITIONS:
  PROMOTION_CRITERIA_DEFINED → PROMOTION_OPEN           ← 금지
  PROMOTION_CRITERIA_DEFINED → ENFORCEMENT_ACTIVE        ← 금지
  PROMOTION_CRITERIA_DEFINED → PRODUCTION_AUTHORIZED     ← 금지
```

---

## 9. Audit / Receipt Fields

### 9-A. 기존 필드 계승

VAL-FPR-001의 `fpr_*` 필드 및 VAL-ENF-001의 `enf_*` 필드를 그대로 활용한다.

### 9-B. VAL-PRM-001 전용 Audit 필드

| 필드 | 타입 | 설명 |
|------|------|------|
| `prm_validation_id` | str | 고정: "VAL-PRM-001" |
| `prm_target_transition` | enum | `SHADOW_TO_PAPER` / `SHADOW_TO_ENFORCEMENT` |
| `prm_must_conditions_status` | dict[str, bool] | 각 MUST 조건 ID별 충족 여부 |
| `prm_hard_blocks` | list[str] | 활성 HARD_BLOCK 조건 ID 목록 |
| `prm_soft_blocks` | list[str] | 활성 SOFT_BLOCK 조건 ID 목록 |
| `prm_evidence_gaps` | list[str] | 활성 EVIDENCE_INSUFFICIENT 조건 ID 목록 |
| `prm_block_level` | enum | `HARD_BLOCKED` / `SOFT_BLOCKED` / `EVIDENCE_WAIT` / `CLEAR` |
| `prm_promotion_eligible` | bool | 모든 MUST 충족 + 모든 BLOCK 해소 시 True |
| `prm_soft_block_resolutions` | list[dict] | 해소된 SOFT_BLOCK의 {id, resolved_at, resolution_evidence} |
| `prm_fpr_event_count` | int | FPR 프레임 적용 완료 이벤트 수 |
| `prm_fpr_tp_count` | int | TP 판정 수 |
| `prm_fpr_fp_count` | int | FP 판정 수 |
| `prm_fpr_unresolved_count` | int | UNRESOLVED 판정 수 |
| `prm_enf_enforced_count` | int | ENFORCED 판정 수 |
| `prm_enf_bypassed_count` | int | BYPASSED 판정 수 |
| `prm_enf_degraded_count` | int | DEGRADED 판정 수 |
| `prm_judged_at` | optional str (ISO 8601) | 판정 시점 |
| `prm_judged_by` | str | `"manual_review"` (현 단계) |
| `prm_review_status` | enum | `DRAFT` / `REVIEWED` / `SEALED` |
| `prm_promotion_open` | bool | 고정: False |
| `prm_execution_binding` | str | 고정: "NONE" |
| `prm_auto_advance` | str | 고정: "FORBIDDEN" |

### 9-C. Promotion Decision Receipt (승격 결정 시 생성, 본 체인 범위 밖)

본 체인에서는 receipt 구조만 정의하고, 실제 생성은 별도 승격 결정 체인에서 수행한다.

| 필드 | 타입 | 설명 |
|------|------|------|
| `receipt_id` | str | 자동 생성 |
| `transition_type` | enum | `SHADOW_TO_PAPER` / `SHADOW_TO_ENFORCEMENT` |
| `prm_validation_id` | str | "VAL-PRM-001" |
| `all_must_met` | bool | 모든 MUST 조건 충족 여부 |
| `all_blocks_cleared` | bool | 모든 BLOCK 해소 여부 |
| `decision` | enum | `APPROVED` / `DENIED` / `DEFERRED` |
| `decided_by` | str | 결정 주체 |
| `decided_at` | str (ISO 8601) | 결정 시점 |

---

## 10. FPR / ENF 입력 결과 반영 규칙

### 10-A. VAL-FPR-001 결과 반영

| FPR 판정 분포 | 승격 영향 |
|-------------|----------|
| TP 비율 높음 | novelty 감지 정확도 높음 → 승격 근거 강화 |
| FP 비율 높음 | novelty 감지 오탐 많음 → 기회 비용 리스크 → 승격 전 개선 필요 |
| UNRESOLVED 비율 높음 | 판정 신뢰도 부족 → EVIDENCE_INSUFFICIENT |

### 10-B. VAL-ENF-001 결과 반영

| ENF 판정 분포 | 승격 영향 |
|-------------|----------|
| ENFORCED 100% | enforcement 안전성 확보 → 승격 근거 강화 |
| BYPASSED 1건+ | HARD_BLOCK 즉시 발동 |
| DEGRADED 존재 | SOFT_BLOCK 발동, 원인 분석 필요 |

### 10-C. 교차 반영

VAL-FPR-001 Section 9의 FPR-ENF 연계 매트릭스를 참조하되, 자동 의사결정에 바인딩하지 않는다.

---

## 11. Validation Completion Criteria

| # | 기준 | 상태 |
|---|------|------|
| 1 | shadow_to_paper_criteria 정의 완료 | DONE (Section 4) |
| 2 | shadow_to_enforcement_criteria 정의 완료 | DONE (Section 5) |
| 3 | Promotion Block Conditions (3층) 정의 완료 | DONE (Section 6) |
| 4 | 승격 경로 순서 제약 정의 완료 | DONE (Section 7) |
| 5 | State Transition Rules 정의 완료 | DONE (Section 8) |
| 6 | Audit / Receipt Fields 정의 완료 | DONE (Section 9) |
| 7 | FPR / ENF 입력 반영 규칙 정의 완료 | DONE (Section 10) |
| 8 | promotion_open = FALSE 유지 확인 | CONFIRMED |
| 9 | execution_binding = NONE 유지 확인 | CONFIRMED |
| 10 | auto_advance = FORBIDDEN 유지 확인 | CONFIRMED |

**모든 완료 기준 충족: 10/10**

---

## 12. Forbidden Areas

| 금지 ID | 금지 사항 | 상태 |
|---------|----------|------|
| F-1 | promotion_open=True 전환 | BLOCKED |
| F-2 | enforce_deny=True 전환 | BLOCKED |
| F-3 | execution binding 변경 | BLOCKED |
| F-4 | production_authorized=True 전환 | BLOCKED |
| F-5 | auto_advance 해제 | BLOCKED |
| F-6 | 실거래/페이퍼트레이딩 실제 개시 | BLOCKED |
| F-7 | 수치 threshold (N건, % 한도) 확정 | BLOCKED (별도 정량화 체인 범위) |
| F-8 | scheduler registration | BLOCKED |
| F-9 | GAP 코드 수정/패치 실행 | BLOCKED (별도 구현 체인 범위) |
| F-10 | 구조 확장 | BLOCKED |
| F-11 | 신규 상위 시스템 제안 | BLOCKED |
| F-12 | 실제 승격 판단/결정 수행 | BLOCKED (별도 승격 결정 체인 범위) |

---

## 13. Final Validation State Block

```
─────────────────────────────────────────────────
  VAL-PRM-001  FINAL STATE
─────────────────────────────────────────────────
  validation_id              = VAL-PRM-001
  validation_scope           = PROMOTION_GATE_CRITERIA_ONLY
  promotion_state            = PROMOTION_CRITERIA_DEFINED
  
  source_basis_ids           = [
    "VAL-FPR-001 (SEALED)",
    "VAL-ENF-001 (SEALED)",
    "GAP-1 (shadow mode override)",
    "GAP-2 (post-exec recording skip)",
    "GAP-3 (handler wiring verification)"
  ]
  
  shadow_to_paper_criteria   = DEFINED (Section 4, MUST 6 + BLOCK 10)
  shadow_to_enf_criteria     = DEFINED (Section 5, MUST 7 + BLOCK 8)
  block_structure            = DEFINED (Section 6, 3-tier)
  path_constraints           = DEFINED (Section 7, sequential only)
  state_transition           = DEFINED (Section 8)
  audit_fields               = DEFINED (Section 9, 22 fields + receipt)
  fpr_enf_reflection         = DEFINED (Section 10)
  
  completion_criteria        = 10/10 MET
  
  numeric_target_definition  = explicitly_deferred_outside_current_scope
  promotion_open             = FALSE
  execution_binding          = NONE
  production_authorized      = FALSE
  auto_advance               = FORBIDDEN
  
  remaining_next_step        = separate_promotion_decision_chain_or_hold
  current_promotion          = CLOSED
  
  review_status              = SEALED
  sealed_at                  = 2026-04-13
─────────────────────────────────────────────────
```

---

## Appendix: Reopen 3-Gate Final Status

```
─────────────────────────────────────────────────
  REOPEN 3-GATE  CLOSURE STATUS
─────────────────────────────────────────────────
  [x] Gate 1: false_positive_rate    VAL-FPR-001  SEALED (2026-04-13)
  [x] Gate 2: enforcement_safety     VAL-ENF-001  SEALED (2026-04-13)
  [x] Gate 3: promotion_gate_criteria VAL-PRM-001  SEALED (2026-04-13)
  
  ALL 3 GATES DEFINED.
  
  promotion_open             = FALSE
  execution_binding          = NONE
  production_authorized      = FALSE
  auto_advance               = FORBIDDEN
  
  next_available_action      = separate_quantification_chain
                               OR separate_promotion_decision_chain
                               OR HOLD
─────────────────────────────────────────────────
```
