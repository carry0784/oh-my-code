# VAL-ENF-001: PPF Novelty Enforcement Safety — Gate Definition

```
validation_id              = VAL-ENF-001
validation_scope           = ENFORCEMENT_SAFETY_ONLY
authority_boundary         = VALIDATION_TO_ENFORCEMENT_FRAME
execution_binding          = NONE
promotion_open             = FALSE
production_authorized      = FALSE
auto_advance               = FORBIDDEN
numeric_target_definition  = explicitly_deferred_outside_current_and_next_gate_scope
```

---

## 1. Doctrine Check

| Doctrine Principle | Status | Evidence |
|----|--------|---------|
| 자동·자율·자가진화형 구조 | COMPLIANT | 기존 골격 변경 없이 Validation → Enforcement Frame 체인 내부에서 정의 |
| 7-layer 골격 고정 | COMPLIANT | Observation / Interpretation / Decision / Execution / Learning / Evolution / Constitution 변경 없음 |
| Gate 정의 작업 ≠ 실행 승인 작업 | COMPLIANT | execution_binding=NONE, promotion_open=FALSE |
| enforcement_safety ≻ false_positive_rate | COMPLIANT | VAL-FPR-001 SEALED (2026-04-13) 선행 완료 |
| enforcement_safety ≺ promotion_gate_criteria | COMPLIANT | promotion_gate_criteria 미착수 |

---

## 2. Input Basis

| ID | 출처 | 역할 |
|----|------|------|
| VAL-FPR-001 | SEALED (2026-04-13) | TP/FP/UNRESOLVED 판정 프레임 |
| C11 | constitution.py | novelty brake 헌법 조항 |
| gate.py:evaluate() | strategies/ppf/gate.py | 3중 fail-closed 게이트 |
| decision.py:evaluate() | strategies/ppf/decision.py | 상태 머신 novelty brake (1순위 체크) |
| orchestrator.py:step_5_75 | app/agents/orchestrator.py | PPF 통합 지점 |
| ppf_gate_handler.py | strategies/ppf/ | enforce_deny / shadow 모드 분기 |

---

## 3. Framework Mapping

```
Enforcement Safety가 검증하는 질문:
"novelty brake deny 판정이 실행 경로에서 우회 없이 강제되는가?"

         ┌──────────────────┐
         │  O9=True 발생     │
         └──────┬───────────┘
                │
         ┌──────▼───────────┐
         │ C11 novelty brake │
         │ → D1_IDLE forced  │
         └──────┬───────────┘
                │
         ┌──────▼───────────┐
         │ gate.evaluate()   │
         │ → allow_entry=F   │
         └──────┬───────────┘
                │
         ┌──────▼───────────┐
         │ Step 5.75         │
         │ enforce_deny 분기  │
         └──────┬───────────┘
                │
    ┌───────────┼───────────┐
    ▼           ▼           ▼
┌──────┐  ┌──────────┐  ┌──────────┐
│ENFORCED│ │BYPASSED  │  │DEGRADED  │
│(safe) │  │(unsafe)  │  │(partial) │
└──────┘  └──────────┘  └──────────┘
```

---

## 4. 현재 Enforcement Layer 분석

### 4-A. 기존 안전 보장 (확인됨)

| Layer | 메커니즘 | Fail-Closed | 상태 |
|-------|---------|------------|------|
| Constitution | `check_c11_novelty_brake()` → PPF 영구 비활성화 | YES | VERIFIED |
| Gate evaluation | 3중 fail-closed (pre-check, exception, state check) | YES | VERIFIED |
| State machine | novelty brake = 1순위 체크, D6 ephemeral | YES | VERIFIED |
| Step 5.75 | `if not _ppf_result.allowed → return denial` | YES (enforce 모드) | VERIFIED |
| Post-execution | metadata-only recording, 주문 변경 없음 | YES | VERIFIED |

### 4-B. 식별된 Gap (3건)

| Gap ID | 위치 | 설명 | 심각도 |
|--------|------|------|--------|
| GAP-1 | ppf_gate_handler.py (shadow mode) | `enforce_deny=False` 시 raw gate deny가 `effective_allowed=True`로 override됨. Shadow 모드에서 의도된 동작이나, enforce 전환 시 이 경로의 안전성 검증 필요 | MEDIUM |
| GAP-2 | orchestrator.py (post-execution) | `_order_result is None`이면 post-execution recording이 무경고로 건너뜀. LV-2/LV-3 기록 누락 가능 | LOW |
| GAP-3 | orchestrator.py (__init__) | ppf_gate_handler 배선 검증 없음. governance_gate는 line 43에서 명시적 체크가 있으나 PPF에는 동등한 검증이 없음 | LOW |

---

## 5. Enforcement Safety 규칙 정의

### 5-A. ENFORCED (안전) 조건

novelty deny 판정이 아래 조건을 **모두** 충족할 때 ENFORCED로 판정한다.

| 조건 ID | 조건 명칭 | 설명 |
|---------|----------|------|
| ENF-C1 | C11 작동 확인 | O9=True 시 constitution.check_c11_novelty_brake()가 호출되고 위반 없이 통과 (D1_IDLE 유지) |
| ENF-C2 | Gate deny 관철 | gate.evaluate() 반환값이 False |
| ENF-C3 | Step 5.75 차단 | orchestrator에서 Step 6(OrderExecutor) 도달 전에 denial response 반환 |
| ENF-C4 | 주문 미생성 | deny 이벤트 이후 해당 signal에 대한 Order 레코드가 생성되지 않음 |
| ENF-C5 | Audit 기록 완전 | PPFLogEntry에 rejection_reason_code=NOVELTY_BRAKE, allow_entry=False 기록 존재 |

**판정**: `ENFORCED = ENF-C1 AND ENF-C2 AND ENF-C3 AND ENF-C4 AND ENF-C5`

### 5-B. BYPASSED (비안전) 조건

아래 조건 중 **하나 이상**이 확인되면 BYPASSED로 판정한다.

| 조건 ID | 조건 명칭 | 설명 |
|---------|----------|------|
| BYP-C1 | Shadow override | enforce_deny=False로 인해 raw deny가 effective_allowed=True로 전환됨 (GAP-1) |
| BYP-C2 | Gate 우회 | gate.evaluate() 호출 없이 Step 6 도달 |
| BYP-C3 | Handler 부재 통과 | ppf_gate_handler=None이면서 governance가 PPF 체크를 요구하는 상태 |
| BYP-C4 | 주문 생성 확인 | deny 이벤트 이후 해당 signal에 대한 Order 레코드가 생성됨 |

**판정**: `BYPASSED = BYP-C1 OR BYP-C2 OR BYP-C3 OR BYP-C4`

### 5-C. DEGRADED (부분 안전) 조건

deny가 관철되었으나 보조 안전 장치가 불완전한 경우 DEGRADED로 판정한다.

| 조건 ID | 조건 명칭 | 설명 |
|---------|----------|------|
| DEG-C1 | Audit 기록 불완전 | deny는 관철되었으나 PPFLogEntry 기록이 누락 또는 불완전 |
| DEG-C2 | Post-exec 기록 누락 | deny 후 LV-2/LV-3 recording이 건너뛰어짐 (GAP-2) |
| DEG-C3 | Constitution 미실행 | deny가 state machine 레벨에서 발생했으나 constitution check가 실행되지 않음 |

**판정**: `DEGRADED = NOT BYPASSED AND (DEG-C1 OR DEG-C2 OR DEG-C3)`

**판정 우선순위**: `BYPASSED > DEGRADED > ENFORCED`

---

## 6. Gap별 안전성 규칙

### 6-A. GAP-1: Shadow Mode Override

```
현재 상태:
  enforce_deny = False (shadow mode)
  → raw deny가 effective_allowed=True로 override
  → 이것은 shadow mode의 의도된 동작

안전성 규칙:
  IF enforce_deny=False:
    shadow mode 판정: BYPASSED(BYP-C1) — 의도된 bypass
    enforcement_safety 관점: NOT_APPLICABLE (shadow는 enforcement 대상 아님)
  IF enforce_deny=True:
    raw deny MUST propagate to effective_allowed=False
    위반 시: BYPASSED(BYP-C1) — 비의도 bypass, CRITICAL
```

**현재 enforce_deny 상태**: `False` (shadow mode, 봉인 시점 기준)  
**enforce_deny=True 전환 권한**: 본 체인에서 정의하지 않음 (promotion_gate_criteria 범위)

### 6-B. GAP-2: Post-Execution Recording Skip

```
현재 상태:
  _order_result=None이면 recording 건너뜀
  warning log 없음

안전성 규칙:
  deny 이벤트 시 recording skip은 enforcement 자체에는 영향 없음
  (deny → 주문 미생성 → _order_result=None은 정상 경로)
  
  판정:
  IF deny AND _order_result=None AND recording skipped:
    ENFORCED (주문 미생성이 확인되므로 안전)
    BUT DEG-C2 해당 가능 (LV-3 세션 기록 불완전)
```

### 6-C. GAP-3: Handler Wiring Verification

```
현재 상태:
  ppf_gate_handler=None이면 Step 5.75 전체 건너뜀
  → PPF 없이 실행 진행 (handler-absent safe 설계)

안전성 규칙:
  IF ppf_gate_handler=None AND governance_requires_ppf=False:
    ENFORCED (PPF 미요구 상태에서 handler 부재는 정상)
  IF ppf_gate_handler=None AND governance_requires_ppf=True:
    BYPASSED(BYP-C3) — governance 요구를 충족하지 못함
    
  현재 governance_requires_ppf: 미정의 (promotion 미개방이므로 해당 없음)
```

---

## 7. 상태 전이 규칙

```
BEFORE:
  validation_state = VALIDATION_FRAME_DEFINED (VAL-FPR-001)
  enforcement_state = ENFORCEMENT_PENDING

TRANSITION (본 문서 완료 시):
  enforcement_state = ENFORCEMENT_FRAME_DEFINED

BLOCKED TRANSITIONS:
  ENFORCEMENT_FRAME_DEFINED → ENFORCEMENT_ACTIVE        ← 금지
  ENFORCEMENT_FRAME_DEFINED → PROMOTION_READY            ← 금지
  ENFORCEMENT_FRAME_DEFINED → PRODUCTION_AUTHORIZED      ← 금지
```

**개별 이벤트 enforcement 판정 상태 전이**:

```
PENDING   → ENFORCED   (ENF-C1~C5 모두 충족)
PENDING   → BYPASSED   (BYP-C1~C4 중 하나 이상)
PENDING   → DEGRADED   (NOT BYPASSED AND DEG-C1~C3 중 하나 이상)
```

**전이 불가 규칙**:
- ENFORCED/BYPASSED/DEGRADED → 다른 판정으로 재전이 금지 (확정 후 불변)
- enforce_deny=True 전환은 본 체인에서 수행하지 않음

---

## 8. 로그 / Audit 필드

### 8-A. 기존 필드 활용

VAL-FPR-001에서 정의한 `fpr_*` 필드 전체를 그대로 활용한다.

### 8-B. VAL-ENF-001 전용 Audit 필드

| 필드 | 타입 | 설명 |
|------|------|------|
| `enf_validation_id` | str | 고정: "VAL-ENF-001" |
| `enf_event_id` | str | novelty deny 이벤트 고유 ID (fpr_event_id와 동일) |
| `enf_case_label` | enum | `ENFORCED` / `BYPASSED` / `DEGRADED` / `PENDING` |
| `enf_conditions_met` | list[str] | 충족된 조건 ID 목록 (e.g., `["ENF-C1","ENF-C2","ENF-C3","ENF-C4","ENF-C5"]`) |
| `enf_bypass_conditions` | list[str] | 충족된 bypass 조건 ID (비어 있으면 bypass 아님) |
| `enf_degraded_conditions` | list[str] | 충족된 degraded 조건 ID |
| `enf_gap_id` | optional str | 관련 GAP ID (null if no gap triggered) |
| `enf_enforce_deny_state` | bool | 판정 시점의 enforce_deny 값 |
| `enf_handler_present` | bool | ppf_gate_handler 존재 여부 |
| `enf_order_created` | bool | deny 후 주문 생성 여부 (False=안전) |
| `enf_audit_complete` | bool | PPFLogEntry 기록 완전 여부 |
| `enf_lv3_recorded` | bool | LV-3 세션 기록 완전 여부 |
| `enf_judged_at` | optional str (ISO 8601) | 판정 수행 시점 |
| `enf_judged_by` | str | `"manual_review"` (현 단계) |
| `enf_review_status` | enum | `DRAFT` / `REVIEWED` / `SEALED` |
| `enf_promotion_block_reason` | str | 고정: "promotion_gate_criteria_not_defined" |
| `enf_execution_binding` | str | 고정: "NONE" |
| `enf_auto_advance` | str | 고정: "FORBIDDEN" |

---

## 9. Enforcement-FPR 연계 규칙

VAL-FPR-001과 VAL-ENF-001은 동일 novelty 이벤트에 대해 독립적으로 판정된다.

| FPR 판정 | ENF 판정 | 해석 |
|----------|---------|------|
| TP | ENFORCED | 정상: 실제 변화를 정확히 감지하고 안전하게 차단 |
| TP | BYPASSED | 위험: 실제 변화였으나 차단이 우회됨 |
| TP | DEGRADED | 주의: 실제 변화를 차단했으나 보조 안전 장치 불완전 |
| FP | ENFORCED | 비효율: 오탐이었으나 안전하게 차단 (기회 비용 발생) |
| FP | BYPASSED | 결과적 안전이나 우연: 오탐이 우회되어 실행 진행 |
| FP | DEGRADED | 비효율 + 불완전: 오탐 차단 + 보조 장치 불완전 |
| UNRESOLVED | * | 판정 보류: enforcement 판정도 참고 수준에 머무름 |

**이 매트릭스는 참조용이며, 자동 의사결정에 바인딩되지 않는다.**

---

## 10. Validation Completion Criteria

| # | 기준 | 상태 |
|---|------|------|
| 1 | ENFORCED / BYPASSED / DEGRADED 정의 완료 | DONE (Section 5) |
| 2 | Gap별 안전성 규칙 정의 완료 | DONE (Section 6) |
| 3 | 상태 전이 규칙 정의 완료 | DONE (Section 7) |
| 4 | 로그 / Audit 필드 정의 완료 | DONE (Section 8) |
| 5 | FPR-ENF 연계 규칙 정의 완료 | DONE (Section 9) |
| 6 | Execution / Promotion / Production 비개방 유지 확인 | CONFIRMED |
| 7 | enforce_deny 전환 미수행 확인 | CONFIRMED |
| 8 | numeric_target_definition deferred 유지 확인 | CONFIRMED |

**모든 완료 기준 충족: 8/8**

---

## 11. Forbidden Areas

| 금지 ID | 금지 사항 | 상태 |
|---------|----------|------|
| F-1 | enforce_deny=True 전환 | BLOCKED (promotion_gate_criteria 범위) |
| F-2 | promotion_gate_criteria 정의 착수 | BLOCKED |
| F-3 | execution binding 변경 | BLOCKED |
| F-4 | promotion_open=True 전환 | BLOCKED |
| F-5 | production_authorized=True 전환 | BLOCKED |
| F-6 | auto_advance 해제 | BLOCKED |
| F-7 | 실거래/페이퍼트레이딩 연결 | BLOCKED |
| F-8 | 수치 threshold (% 목표) 정의 | BLOCKED (별도 정량화 체인 범위) |
| F-9 | GAP 코드 수정/패치 | BLOCKED (코드 변경은 별도 구현 체인 범위) |
| F-10 | scheduler registration | BLOCKED |
| F-11 | 구조 확장 | BLOCKED |
| F-12 | 신규 상위 시스템 제안 | BLOCKED |

---

## 12. Final Validation State Block

```
─────────────────────────────────────────────────
  VAL-ENF-001  FINAL STATE
─────────────────────────────────────────────────
  validation_id              = VAL-ENF-001
  validation_scope           = ENFORCEMENT_SAFETY_ONLY
  enforcement_state          = ENFORCEMENT_FRAME_DEFINED
  
  source_basis_ids           = [
    "VAL-FPR-001 (SEALED)",
    "C11 (constitution.py)",
    "gate.py:evaluate()",
    "decision.py:evaluate()",
    "orchestrator.py:step_5_75",
    "ppf_gate_handler.py"
  ]
  
  enforced_definition        = DEFINED (Section 5-A, 5 conditions)
  bypassed_definition        = DEFINED (Section 5-B, 4 conditions)
  degraded_definition        = DEFINED (Section 5-C, 3 conditions)
  gap_analysis               = DEFINED (Section 6, 3 gaps)
  state_transition           = DEFINED (Section 7)
  audit_fields               = DEFINED (Section 8, 17 fields)
  fpr_enf_linkage            = DEFINED (Section 9, 6-cell matrix)
  
  completion_criteria        = 8/8 MET
  
  identified_gaps            = [
    "GAP-1: shadow mode override (MEDIUM)",
    "GAP-2: post-exec recording skip (LOW)",
    "GAP-3: handler wiring verification (LOW)"
  ]
  
  numeric_target_definition  = explicitly_deferred_outside_current_and_next_gate_scope
  promotion_block_reason     = promotion_gate_criteria_not_defined
  execution_binding          = NONE
  promotion_open             = FALSE
  production_authorized      = FALSE
  auto_advance               = FORBIDDEN
  
  remaining_next_gate        = promotion_gate_criteria
  current_promotion          = CLOSED
  
  review_status              = SEALED
  sealed_at                  = 2026-04-13
─────────────────────────────────────────────────
```
