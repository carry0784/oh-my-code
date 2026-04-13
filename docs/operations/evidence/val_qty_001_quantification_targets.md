# VAL-QTY-001: PPF Novelty Quantification Targets — Numeric Criteria Definition

```
validation_id              = VAL-QTY-001
validation_scope           = NUMERIC_TARGET_DEFINITION_ONLY
authority_boundary         = QUANTIFICATION_FRAME
execution_binding          = NONE
promotion_open             = FALSE
production_authorized      = FALSE
auto_advance               = FORBIDDEN
```

---

## 1. Doctrine Check

| Doctrine Principle | Status | Evidence |
|----|--------|---------|
| 자동·자율·자가진화형 구조 | COMPLIANT | 기존 골격 변경 없이 수치 기준만 정의 |
| 7-layer 골격 고정 | COMPLIANT | 변경 없음 |
| 수치 정의 ≠ 승격 실행 | COMPLIANT | execution_binding=NONE, promotion_open=FALSE |
| 선행 체인 완료 | COMPLIANT | VAL-FPR-001 + VAL-ENF-001 + VAL-PRM-001 전부 SEALED |

---

## 2. Input Basis

| ID | 수치화 대상 |
|----|-----------|
| VAL-FPR-001 | TP/FP/UNRESOLVED 비율 기준 |
| VAL-ENF-001 | ENFORCED/BYPASSED/DEGRADED 비율 기준 |
| VAL-PRM-001 S2P-M1~M6 | shadow→paper 필수 조건의 N건, 비율 한도 |
| VAL-PRM-001 S2E-M1~M7 | shadow→enforcement 필수 조건의 N건, 비율 한도 |
| VAL-PRM-001 S2P-EI1~EI3, S2E-EI1~EI2 | EVIDENCE_INSUFFICIENT 해소 기준 |

---

## 3. Tier Structure (GREEN / YELLOW / RED)

모든 수치 기준은 3층 판정 구조를 따른다.

```
GREEN    승격 검토 가능 (모든 기준 충족)
YELLOW   추가 사례 필요 (일부 기준 미충족, 축적 대기)
RED      승격 금지 (위반 또는 심각한 미달)
```

**판정 규칙**:
- RED 1건 이상 → 전체 RED (승격 금지)
- YELLOW 1건 이상 + RED 0건 → 전체 YELLOW (추가 축적 필요)
- 전체 GREEN → 승격 검토 가능 (별도 결정 체인 필요)

---

## 4. False Positive Rate 수치 기준

### 4-A. 최소 판정 건수 (S2P-M1 / S2E-M2 대응)

VAL-FPR-001 프레임으로 판정 완료된 novelty 이벤트 최소 건수.

| Tier | Shadow → Paper | Paper → Enforcement | 근거 |
|------|---------------|---------------------|------|
| GREEN | ≥ 10건 | ≥ 10건 | 통계적 최소 유의 표본 |
| YELLOW | 5~9건 | 5~9건 | 추세 관찰은 가능하나 확정에 불충분 |
| RED | < 5건 | < 5건 | 판정 신뢰도 부족 |

### 4-B. UNRESOLVED 비율 (S2P-M2 대응)

판정 완료 이벤트 중 UNRESOLVED 비율 한도.

| Tier | 한도 | 근거 |
|------|------|------|
| GREEN | ≤ 20% | 5건 중 1건 이하 미결정 허용 |
| YELLOW | 21~40% | 미결정 비중 높아 판정 신뢰도 저하 |
| RED | > 40% | 판정 프레임 자체의 적용성 의심 |

### 4-C. FP 비율 상한 (참조 기준, S2E-M6 대응)

TP+FP 확정 건수 중 FP 비율. UNRESOLVED 제외 후 계산.

| Tier | 한도 | 근거 |
|------|------|------|
| GREEN | ≤ 50% | 감지 2건 중 1건 이상이 실제 변화 |
| YELLOW | 51~70% | 오탐 우세하나 일부 정탐 존재 |
| RED | > 70% | novelty 감지 신뢰도 심각하게 저하 |

**설계 근거**: PPF novelty brake는 보수적 안전 장치이므로, FP 허용 범위가 일반 분류기보다 넓다. 그러나 70% 초과 시 기회 비용이 과도하여 gate 자체의 유효성이 의심된다.

### 4-D. FP 비율 안정성 (S2E-M6 대응)

paper 기간 FP 비율이 shadow 기간 대비 급증하지 않아야 한다.

| Tier | 조건 | 근거 |
|------|------|------|
| GREEN | paper FP% ≤ shadow FP% + 15pp | 모드 전환으로 인한 FP 증가가 허용 범위 내 |
| YELLOW | shadow FP% + 15pp < paper FP% ≤ shadow FP% + 30pp | 유의미한 증가, 원인 분석 필요 |
| RED | paper FP% > shadow FP% + 30pp | 모드 전환이 FP 급증을 유발, enforcement 전환 차단 |

---

## 5. Enforcement Safety 수치 기준

### 5-A. ENFORCED 비율 (S2P-M3 / S2E-M3 대응)

전체 novelty deny 이벤트 중 ENFORCED 비율.

| Tier | 한도 | 근거 |
|------|------|------|
| GREEN | ≥ 90% | 10건 중 9건 이상 완전 강제 |
| YELLOW | 70~89% | DEGRADED가 일부 존재하나 deny 자체는 관철 |
| RED | < 70% | enforcement 안전성 보장 불충분 |

### 5-B. BYPASSED 건수 (S2P-M4 / S2E-M4 대응)

BYPASSED 이벤트 절대 건수.

| Tier | 한도 | 근거 |
|------|------|------|
| GREEN | 0건 | deny 우회 없음 |
| YELLOW | — | 해당 없음 (BYPASSED는 0/비0 이분법) |
| RED | ≥ 1건 | deny 우회 발생 → HARD_BLOCK 자동 발동 |

### 5-C. DEGRADED 건수 (SOFT_BLOCK 연계)

DEGRADED 이벤트 건수.

| Tier | 한도 | 근거 |
|------|------|------|
| GREEN | 0건 | 보조 안전 장치 완전 |
| YELLOW | 1~2건 | 원인 분석 후 해소 가능 |
| RED | ≥ 3건 | 보조 안전 장치 체계적 결함 의심 |

---

## 6. Session Quality 수치 기준

### 6-A. ABORT 세션 비율 (S2P-M6 대응)

판정 기간 내 SessionPath가 ABORT_*로 종료된 세션 비율.

| Tier | 한도 | 근거 |
|------|------|------|
| GREEN | ≤ 10% | 10 세션 중 1회 이하 비정상 종료 |
| YELLOW | 11~25% | 세션 안정성 저하, 원인 분석 필요 |
| RED | > 25% | 세션 운영 품질 심각, 판정 기반 불안정 |

### 6-B. Constitution 위반 (S2P-M5 / S2E-M7 대응)

| Tier | 한도 | 근거 |
|------|------|------|
| GREEN | 0건 | 헌법 위반 없음 |
| YELLOW | — | 해당 없음 (위반은 0/비0 이분법) |
| RED | ≥ 1건 | HARD_BLOCK 자동 발동 |

---

## 7. 운영 기간 수치 기준

### 7-A. Shadow 운영 기간 (S2P-EI3 대응)

| Tier | 한도 | 근거 |
|------|------|------|
| GREEN | ≥ 14일 (연속) | 2주 연속 운영으로 주중/주말 패턴 포함 |
| YELLOW | 7~13일 | 1주 이상이나 주간 패턴 미포함 가능 |
| RED | < 7일 | 운영 패턴 파악 불충분 |

### 7-B. Paper 운영 기간 (S2E-EI2 대응)

| Tier | 한도 | 근거 |
|------|------|------|
| GREEN | ≥ 14일 (연속) | shadow와 동일 기준 |
| YELLOW | 7~13일 | 1주 이상이나 패턴 미포함 가능 |
| RED | < 7일 | 운영 패턴 파악 불충분 |

### 7-C. 미완료 관찰 윈도우 (S2P-EI2 대응)

| Tier | 조건 | 근거 |
|------|------|------|
| GREEN | 미완료 윈도우 0건 | 모든 이벤트 판정 가능 |
| YELLOW | 미완료 윈도우 1~2건 | 소수 보류, 기존 확정 건으로 판단 가능 |
| RED | 미완료 윈도우 ≥ 3건 또는 전체 50% 이상 | 판정 기반 불안정 |

---

## 8. VAL-PRM-001 조건별 수치 매핑 요약

### 8-A. Shadow → Paper (S2P)

| 조건 ID | 수치 기준 참조 | GREEN | RED |
|---------|-------------|-------|-----|
| S2P-M1 | Section 4-A | ≥ 10건 | < 5건 |
| S2P-M2 | Section 4-B | UNRESOLVED ≤ 20% | > 40% |
| S2P-M3 | Section 5-A | ENFORCED ≥ 90% | < 70% |
| S2P-M4 | Section 5-B | BYPASSED = 0 | ≥ 1건 |
| S2P-M5 | Section 6-B | Constitution 위반 = 0 | ≥ 1건 |
| S2P-M6 | Section 6-A | ABORT ≤ 10% | > 25% |
| S2P-EI1 | Section 4-A | ≥ 10건 | < 5건 |
| S2P-EI2 | Section 7-C | 미완료 = 0 | ≥ 3건 |
| S2P-EI3 | Section 7-A | ≥ 14일 | < 7일 |

### 8-B. Shadow → Enforcement (S2E)

| 조건 ID | 수치 기준 참조 | GREEN | RED |
|---------|-------------|-------|-----|
| S2E-M1 | — | paper 완료 | paper 미완료 |
| S2E-M2 | Section 4-A | ≥ 10건 | < 5건 |
| S2E-M3 | Section 5-A | ENFORCED ≥ 90% | < 70% |
| S2E-M4 | Section 5-B | BYPASSED = 0 | ≥ 1건 |
| S2E-M5 | — | GAP-1 해소 | GAP-1 미해소 |
| S2E-M6 | Section 4-D | FP 증가 ≤ 15pp | 증가 > 30pp |
| S2E-M7 | Section 6-B | Constitution 위반 = 0 | ≥ 1건 |
| S2E-EI1 | Section 4-A | ≥ 10건 (paper) | < 5건 |
| S2E-EI2 | Section 7-B | ≥ 14일 | < 7일 |

---

## 9. Tier 산정 규칙

### 9-A. 개별 기준 Tier 산정

각 수치 기준은 독립적으로 GREEN/YELLOW/RED를 산정한다.

### 9-B. 전체 Tier 산정

```python
def compute_overall_tier(individual_tiers: list[str]) -> str:
    if any(t == "RED" for t in individual_tiers):
        return "RED"
    if any(t == "YELLOW" for t in individual_tiers):
        return "YELLOW"
    return "GREEN"
```

### 9-C. Tier와 Block 연계

| Overall Tier | Block 상태 | 의미 |
|-------------|-----------|------|
| GREEN | 전체 CLEAR | 승격 검토 가능 (별도 결정 체인 필요) |
| YELLOW | EVIDENCE_INSUFFICIENT 또는 SOFT_BLOCK | 추가 축적/분석 필요 |
| RED | HARD_BLOCK 또는 심각한 SOFT_BLOCK | 승격 금지, 원인 해소 필요 |

### 9-D. Tier 자동 판정 제약

- Tier 산정은 수치 비교에 의한 자동 계산 가능
- 그러나 **승격 결정은 자동 판정 불가** (별도 결정 체인에서 manual review)
- Tier=GREEN이 곧 promotion_open=True를 의미하지 않음

---

## 10. Validation Completion Criteria

| # | 기준 | 상태 |
|---|------|------|
| 1 | FPR 수치 기준 정의 완료 | DONE (Section 4, 4항목) |
| 2 | ENF 수치 기준 정의 완료 | DONE (Section 5, 3항목) |
| 3 | Session quality 수치 기준 정의 완료 | DONE (Section 6, 2항목) |
| 4 | 운영 기간 수치 기준 정의 완료 | DONE (Section 7, 3항목) |
| 5 | S2P 조건별 수치 매핑 완료 | DONE (Section 8-A) |
| 6 | S2E 조건별 수치 매핑 완료 | DONE (Section 8-B) |
| 7 | GREEN/YELLOW/RED tier 구조 정의 완료 | DONE (Section 3, 9) |
| 8 | Tier-Block 연계 정의 완료 | DONE (Section 9-C) |
| 9 | promotion_open = FALSE 유지 확인 | CONFIRMED |
| 10 | execution_binding = NONE 유지 확인 | CONFIRMED |
| 11 | auto_advance = FORBIDDEN 유지 확인 | CONFIRMED |

**모든 완료 기준 충족: 11/11**

---

## 11. Forbidden Areas

| 금지 ID | 금지 사항 | 상태 |
|---------|----------|------|
| F-1 | promotion_open=True 전환 | BLOCKED |
| F-2 | enforce_deny=True 전환 | BLOCKED |
| F-3 | execution binding 변경 | BLOCKED |
| F-4 | production_authorized=True 전환 | BLOCKED |
| F-5 | auto_advance 해제 | BLOCKED |
| F-6 | 실거래/페이퍼트레이딩 실제 개시 | BLOCKED |
| F-7 | 실제 승격 판정 수행 | BLOCKED (별도 promotion_decision_chain 범위) |
| F-8 | scheduler registration | BLOCKED |
| F-9 | GAP 코드 수정/패치 실행 | BLOCKED (별도 구현 체인) |
| F-10 | 구조 확장 | BLOCKED |
| F-11 | 수치 기준의 실시간 자동 적용 | BLOCKED |

---

## 12. Final Validation State Block

```
─────────────────────────────────────────────────
  VAL-QTY-001  FINAL STATE
─────────────────────────────────────────────────
  validation_id              = VAL-QTY-001
  validation_scope           = NUMERIC_TARGET_DEFINITION_ONLY
  quantification_state       = TARGETS_DEFINED
  
  source_basis_ids           = [
    "VAL-FPR-001 (SEALED)",
    "VAL-ENF-001 (SEALED)",
    "VAL-PRM-001 (SEALED)"
  ]
  
  fpr_targets                = DEFINED (Section 4, 4 metrics)
  enf_targets                = DEFINED (Section 5, 3 metrics)
  session_quality_targets    = DEFINED (Section 6, 2 metrics)
  operational_period_targets = DEFINED (Section 7, 3 metrics)
  s2p_mapping                = DEFINED (Section 8-A, 9 entries)
  s2e_mapping                = DEFINED (Section 8-B, 9 entries)
  tier_structure             = DEFINED (Section 3+9, GREEN/YELLOW/RED)
  
  completion_criteria        = 11/11 MET
  
  promotion_open             = FALSE
  execution_binding          = NONE
  production_authorized      = FALSE
  auto_advance               = FORBIDDEN
  
  remaining_next_step        = promotion_decision_chain OR HOLD
  current_promotion          = CLOSED
  
  review_status              = SEALED
  sealed_at                  = 2026-04-13
─────────────────────────────────────────────────
```

---

## Appendix: Full Chain Closure Status

```
─────────────────────────────────────────────────
  FULL VALIDATION CHAIN STATUS
─────────────────────────────────────────────────
  [x] VAL-FPR-001  false_positive_rate       SEALED (2026-04-13)
  [x] VAL-ENF-001  enforcement_safety        SEALED (2026-04-13)
  [x] VAL-PRM-001  promotion_gate_criteria   SEALED (2026-04-13)
  [x] VAL-QTY-001  quantification_targets    SEALED (2026-04-13)
  
  ALL DEFINITION CHAINS COMPLETE.
  
  promotion_open             = FALSE
  execution_binding          = NONE
  production_authorized      = FALSE
  auto_advance               = FORBIDDEN
  
  next_available_action      = promotion_decision_chain OR HOLD
─────────────────────────────────────────────────
```
