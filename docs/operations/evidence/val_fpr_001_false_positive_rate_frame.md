# VAL-FPR-001: PPF Novelty False Positive Rate — Judgment Frame Definition

```
validation_id         = VAL-FPR-001
validation_scope      = FALSE_POSITIVE_RATE_ONLY
authority_boundary    = LEARNING_TO_VALIDATION
execution_binding     = NONE
promotion_open        = FALSE
production_authorized = FALSE
auto_advance          = FORBIDDEN
```

---

## 1. Doctrine Check

| Doctrine Principle | Status | Evidence |
|----|--------|---------|
| 자동·자율·자가진화형 구조 | COMPLIANT | 본 프레임은 기존 골격 변경 없이 Learning → Validation 체인 내부에서 정의 |
| Observation / Interpretation / Decision / Execution / Learning / Evolution / Constitution 고정 | COMPLIANT | 7-layer 골격 변경 없음 |
| Gate 정의 작업 ≠ 실행 승인 작업 | COMPLIANT | execution_binding=NONE, promotion_open=FALSE |
| false_positive_rate 정의 ≺ enforcement_safety | COMPLIANT | enforcement_safety 미착수 |
| false_positive_rate 정의 ≺ promotion_gate_criteria | COMPLIANT | promotion_gate_criteria 미착수 |

---

## 2. Framework Mapping

```
PPF Pipeline Position:

O9_REGIME_NOVELTY_FLAG=True
  → C11 novelty brake 작동
    → state → D1_IDLE
    → rejection_code = NOVELTY_BRAKE
    → allow_entry = False

이 판정 프레임이 검증하는 질문:
"O9=True 판단은 실제 시장 구조 변화를 정확히 감지했는가?"

         ┌──────────────┐
         │  O9=True 발생 │
         └──────┬───────┘
                │
         ┌──────▼───────┐
         │ 관찰 윈도우 개시 │
         └──────┬───────┘
                │
    ┌───────────┼───────────┐
    ▼           ▼           ▼
┌──────┐  ┌──────────┐  ┌──────────┐
│  TP  │  │    FP    │  │UNRESOLVED│
└──────┘  └──────────┘  └──────────┘
```

**판정 대상**: O9=True가 발생한 모든 novelty 이벤트  
**판정 주체**: 사후 분석(post-hoc review), 자동 판정 아님  
**판정 시점**: 관찰 윈도우 종료 후  

---

## 3. TP / FP / UNRESOLVED 판정 정의

### 3-A. TP (True Positive) 정의

O9=True (novelty 판단) 이후, 정의된 관찰 윈도우 내에서 아래 조건 중 **하나 이상**이 확인된 경우 TP로 판정한다.

| 조건 ID | 조건 명칭 | 설명 |
|---------|----------|------|
| TP-C1 | 시장 구조 변화 | 직전 swing high/low 기준 시장 구조(HH/HL → LH/LL 또는 역방향) 전환이 관찰 윈도우 내 확인됨 |
| TP-C2 | 변동성 레짐 전환 | 관찰 윈도우 내 변동성 측정값(ATR 기반)이 윈도우 시작 시점 대비 사전 정의 방향으로 레짐 경계를 초과함 |
| TP-C3 | 패턴 불일치 지속 | O1(pattern_similarity_score)이 관찰 윈도우 전체에 걸쳐 similarity_min(EV6) 미만으로 지속됨 |
| TP-C4 | 추세 방향 반전 | SSL Hybrid(O6) 방향이 novelty 발생 직전 대비 반전되고 윈도우 종료 시까지 유지됨 |

**판정 논리**: `TP = (TP-C1 OR TP-C2 OR TP-C3 OR TP-C4)` AND `NOT UNRESOLVED`

### 3-B. FP (False Positive) 정의

O9=True (novelty 판단)가 있었으나, 관찰 윈도우 내 아래 조건이 **모두** 충족된 경우 FP로 판정한다.

| 조건 ID | 조건 명칭 | 설명 |
|---------|----------|------|
| FP-C1 | 구조 변화 부재 | TP-C1 ~ TP-C4 조건 중 어느 것도 충족되지 않음 |
| FP-C2 | 정상 변동 범위 | 관찰 윈도우 내 가격 변동이 직전 N-bar 평균 범위 내에 머무름 |
| FP-C3 | 관찰 윈도우 완료 | 관찰 윈도우가 데이터 결손 없이 완전히 경과함 |
| FP-C4 | 혼입 이벤트 부재 | 관찰 윈도우 내 외부 이벤트 혼입이 확인되지 않음 |

**판정 논리**: `FP = FP-C1 AND FP-C2 AND FP-C3 AND FP-C4` AND `NOT UNRESOLVED`

### 3-C. UNRESOLVED 정의

아래 조건 중 **하나 이상**이 해당하면 UNRESOLVED로 판정한다. UNRESOLVED는 TP/FP에 우선한다.

| 조건 ID | 조건 명칭 | 설명 |
|---------|----------|------|
| UR-C1 | 데이터 결손 | 관찰 윈도우 내 OHLCV 캔들 결손률이 허용치 초과 |
| UR-C2 | 외부 이벤트 혼입 | 관찰 윈도우 내 거래소 점검, 급등락 서킷브레이커, 상장/폐지 등 외부 이벤트 발생 |
| UR-C3 | 관찰 윈도우 미충족 | 관찰 윈도우 종료 전 세션 종료, 시스템 중단 등으로 윈도우가 완전히 경과하지 못함 |
| UR-C4 | 세션 품질 불량 | 해당 novelty 이벤트 시점의 SessionPath가 DEGRADED_COMPLETION 또는 ABORT_* 중 하나 |
| UR-C5 | 상충 신호 존재 | TP 조건 일부와 FP 조건 일부가 동시에 충족되어 명확한 판정이 불가능한 경우 |

**판정 우선순위**: `UNRESOLVED > TP > FP`

---

## 4. 관찰 윈도우 정의

| 항목 | 정의 |
|------|------|
| 윈도우 시작 | O9=True 이벤트 발생 캔들의 close 시점 |
| 윈도우 길이 | EV2(projection_horizon) × 2 캔들 (현재 기본값: 10 × 2 = 20 캔들) |
| 윈도우 길이 근거 | projection_horizon은 PPF 예측 범위이며, 구조 변화 확인에는 예측 범위의 2배가 필요 |
| 타임프레임 | novelty 이벤트 발생 시 사용된 캔들 타임프레임과 동일 (asset_timeframe_tag 기준) |
| 유효 데이터 최소 비율 | 윈도우 내 캔들의 80% 이상이 유효해야 함 (미만 시 UR-C1) |
| 윈도우 중첩 처리 | 동일 세션 내 복수 O9=True 발생 시 각각 독립 윈도우 개시, 중첩 허용 |

---

## 5. 제외 조건 / 보류 조건 정의

### 5-A. 제외 조건 (Exclusion)

제외된 이벤트는 TP/FP/UNRESOLVED 어느 것으로도 계수되지 않으며, 통계 모수에서 완전히 배제된다.

| 제외 ID | 조건 | 근거 |
|---------|------|------|
| EX-1 | Constitution violation으로 PPF 자체가 비활성화된 세션 내 이벤트 | C6/C7/C10 위반 시 PPF 판단 자체가 무효 |
| EX-2 | 테스트/시뮬레이션 환경에서 발생한 이벤트 | 실 시장 데이터 기반이 아닌 판정은 통계적 의미 없음 |
| EX-3 | O9 계산에 사용된 입력 데이터가 사후 수정(backfill/correction)된 이벤트 | 판정 시점 데이터와 사후 데이터 불일치 |

### 5-B. 보류 조건 (Hold)

보류된 이벤트는 일시적으로 판정 보류 상태에 놓이며, 조건 해소 시 재판정한다.

| 보류 ID | 조건 | 해소 기준 |
|---------|------|----------|
| HLD-1 | 관찰 윈도우 진행 중 | 윈도우 종료 시 자동 해소 |
| HLD-2 | 데이터 파이프라인 지연으로 윈도우 내 캔들이 아직 미수신 | 데이터 수신 완료 시 해소, 일정 기한 초과 시 UR-C1로 전환 |
| HLD-3 | 외부 이벤트 영향 범위 미확정 | 이벤트 종료 및 영향 범위 확정 시 해소, 미확정 지속 시 UR-C2로 전환 |

---

## 6. 상태 전이 규칙

```
BEFORE:
  validation_state = VALIDATION_PENDING
  validation_scope = FALSE_POSITIVE_RATE_ONLY

TRANSITION (본 문서 완료 시):
  validation_state = VALIDATION_FRAME_DEFINED

BLOCKED TRANSITIONS:
  VALIDATION_FRAME_DEFINED → ENFORCEMENT_READY        ← 금지
  VALIDATION_FRAME_DEFINED → PROMOTION_READY           ← 금지
  VALIDATION_FRAME_DEFINED → PRODUCTION_AUTHORIZED     ← 금지
```

**개별 이벤트 판정 상태 전이**:

```
PENDING → HOLD       (HLD-1/2/3 해당 시)
PENDING → EXCLUDED   (EX-1/2/3 해당 시)
HOLD    → PENDING    (보류 조건 해소 시)
HOLD    → UNRESOLVED (보류 기한 초과 시)
PENDING → TP         (TP 조건 충족 확인)
PENDING → FP         (FP 조건 충족 확인)
PENDING → UNRESOLVED (UR 조건 해당 확인)
```

**전이 불가 규칙**:
- TP/FP/UNRESOLVED → 다른 판정으로 재전이 금지 (판정 확정 후 불변)
- EXCLUDED → 다른 상태로 전이 금지

---

## 7. 로그 / Audit 필드

### 7-A. 기존 PPFLogEntry 필드 활용

| 필드 | 출처 | 역할 |
|------|------|------|
| `timestamp` | logging_schema.py | 이벤트 시점 |
| `asset_timeframe_tag` | logging_schema.py (L5) | 자산·타임프레임 식별 |
| `ppf_state` | logging_schema.py | 판정 시 PPF 상태 |
| `allow_entry` | logging_schema.py | 게이트 결과 |
| `rejection_reason_code` | logging_schema.py (L4) | 거부 사유 |
| `regime_novelty_flag` | logging_schema.py (L6) | O9 값 |
| `false_positive_flag` | logging_schema.py (L3) | 사후 FP 플래그 (기존) |
| `filter_contribution_map` | logging_schema.py (L2) | I1-I5 + O4/O5 값 |

### 7-B. VAL-FPR-001 전용 Audit 필드

novelty 이벤트 판정 레코드에 추가해야 할 필드:

| 필드 | 타입 | 설명 |
|------|------|------|
| `fpr_validation_id` | str | 고정: "VAL-FPR-001" |
| `fpr_event_id` | str | novelty 이벤트 고유 ID (e.g., `NOV-{timestamp}-{asset}`) |
| `fpr_case_label` | enum | `TP` / `FP` / `UNRESOLVED` / `EXCLUDED` / `HOLD` / `PENDING` |
| `fpr_tp_conditions_met` | list[str] | 충족된 TP 조건 ID 목록 (e.g., `["TP-C1", "TP-C4"]`) |
| `fpr_fp_conditions_met` | list[str] | 충족된 FP 조건 ID 목록 |
| `fpr_ur_conditions_met` | list[str] | 충족된 UNRESOLVED 조건 ID 목록 |
| `fpr_exclusion_id` | optional str | 적용된 제외 조건 ID (null if not excluded) |
| `fpr_hold_id` | optional str | 적용된 보류 조건 ID (null if not held) |
| `fpr_observation_window_start` | str (ISO 8601) | 관찰 윈도우 시작 시점 |
| `fpr_observation_window_end` | str (ISO 8601) | 관찰 윈도우 종료 시점 |
| `fpr_observation_window_completeness` | float | 윈도우 내 유효 캔들 비율 (0.0-1.0) |
| `fpr_judged_at` | optional str (ISO 8601) | 판정 수행 시점 (PENDING/HOLD 시 null) |
| `fpr_judged_by` | str | `"manual_review"` (현 단계, 자동 판정 아님) |
| `fpr_review_status` | enum | `DRAFT` / `REVIEWED` / `SEALED` |
| `fpr_promotion_block_reason` | str | 고정: "enforcement_safety_not_defined" |
| `fpr_execution_binding` | str | 고정: "NONE" |
| `fpr_auto_advance` | str | 고정: "FORBIDDEN" |
| `fpr_source_basis_ids` | list[str] | 판정 근거 문서 ID 목록 |

---

## 8. Comparison Basis for Future Cases

향후 novelty 이벤트 발생 시 비교 기준으로 사용할 baseline case 구조:

### 8-A. Baseline Case Record Schema

```python
@dataclass(frozen=True)
class NoveltyBaselineCase:
    # 이벤트 식별
    event_id: str                    # NOV-{timestamp}-{asset}
    timestamp: str                   # ISO 8601 UTC
    asset_timeframe_tag: str         # e.g., "binance:SOL/USDT:1h"
    
    # O9 발생 컨텍스트
    deny_code: str                   # "NOVELTY_BRAKE"
    raw_decision: str                # PPFState at rejection (always "D1_IDLE")
    novelty_flag: bool               # always True (O9=True)
    effective_allowed: bool          # always False (C11 enforced)
    ppf_state: str                   # "D1_IDLE"
    
    # 세션 컨텍스트
    session_ledger_quality: str      # SessionPath enum value
    session_stability: str           # SessionStability enum value
    budget_pressure: str             # BudgetPressureState enum value
    
    # 관찰 윈도우 결과
    observation_window_bars: int     # 실제 관찰된 캔들 수
    observation_window_completeness: float  # 유효 캔들 비율
    
    # O/I 스냅샷 (이벤트 발생 시점)
    o1_pattern_similarity: float
    o6_ssl_trend_strength: float
    o7_volume_force_strength: float
    i1_projection_bias: float
    i2_trend_alignment: float
    i4_path_quality: float
    
    # 판정 결과
    decision_outcome: str            # TP / FP / UNRESOLVED 중 하나
    final_case_label: str            # TP / FP / UNRESOLVED / EXCLUDED
    tp_conditions_met: tuple[str, ...] 
    fp_conditions_met: tuple[str, ...]
    ur_conditions_met: tuple[str, ...]
    
    # 메타
    review_status: str               # DRAFT / REVIEWED / SEALED
    source_basis_ids: tuple[str, ...]
```

### 8-B. 비교 용도

| 비교 항목 | 목적 |
|----------|------|
| O/I 스냅샷 간 유사도 | 새 이벤트가 기존 TP/FP 패턴과 유사한지 사전 추정 |
| 세션 컨텍스트 유사도 | 세션 품질이 판정에 미치는 영향 패턴 축적 |
| 자산·타임프레임 분포 | 특정 자산/타임프레임에 FP가 집중되는지 파악 |
| TP/FP/UNRESOLVED 비율 변화 | 시간 경과에 따른 novelty 감지 정확도 추이 |

### 8-C. 비교 제약

- baseline case는 읽기 전용 참조 자료이며, 실시간 의사결정에 바인딩되지 않음
- 비교 결과로 자동 threshold tuning 또는 parameter 변경 금지
- 비교 결과는 다음 체인(enforcement_safety)의 입력 자료로만 사용 가능

---

## 9. Validation Completion Criteria

| # | 기준 | 상태 |
|---|------|------|
| 1 | TP / FP / UNRESOLVED 정의 완료 | DONE (Section 3) |
| 2 | 관찰 윈도우 정의 완료 | DONE (Section 4) |
| 3 | 제외 조건 / 보류 조건 정의 완료 | DONE (Section 5) |
| 4 | 상태 전이 규칙 정의 완료 | DONE (Section 6) |
| 5 | 로그 / Audit 필드 정의 완료 | DONE (Section 7) |
| 6 | Future-case comparison basis 정의 완료 | DONE (Section 8) |
| 7 | Execution / Promotion / Production 비개방 유지 확인 | CONFIRMED — 아래 Final State Block 참조 |

**모든 완료 기준 충족: 7/7**

---

## 10. Forbidden Areas

본 문서 범위 내에서 아래 사항은 명시적으로 금지된다.

| 금지 ID | 금지 사항 | 상태 |
|---------|----------|------|
| F-1 | enforcement_safety 정의 착수 | BLOCKED |
| F-2 | promotion_gate_criteria 정의 착수 | BLOCKED |
| F-3 | execution binding 변경 | BLOCKED |
| F-4 | promotion_open=true 전환 | BLOCKED |
| F-5 | production_authorized=true 전환 | BLOCKED |
| F-6 | auto_advance 해제 | BLOCKED |
| F-7 | 실거래/페이퍼트레이딩 연결 | BLOCKED |
| F-8 | 수치 threshold (% 목표) 정의 | BLOCKED — enforcement_safety 이후 별도 정량화 체인 범위 |
| F-9 | threshold tuning / parameter tuning | BLOCKED |
| F-10 | enforce_deny=true 전환 규칙 정의 | BLOCKED |
| F-11 | scheduler registration | BLOCKED |
| F-12 | 구조 확장 | BLOCKED |
| F-13 | 신규 상위 시스템 제안 | BLOCKED |

---

## 11. Final Validation State Block

```
─────────────────────────────────────────────────
  VAL-FPR-001  FINAL STATE
─────────────────────────────────────────────────
  validation_id          = VAL-FPR-001
  validation_scope       = FALSE_POSITIVE_RATE_ONLY
  validation_state       = VALIDATION_FRAME_DEFINED
  
  source_basis_ids       = [
    "DECISION-001(amended)",
    "L-PPF-NOVELTY-001",
    "O-A", "O-B-001", "O-B-002", "O-B-003", "O-B-004",
    "INTERP-001"
  ]
  
  tp_definition          = DEFINED (Section 3-A, 4 conditions)
  fp_definition          = DEFINED (Section 3-B, 4 conditions)
  unresolved_definition  = DEFINED (Section 3-C, 5 conditions)
  observation_window     = DEFINED (Section 4, EV2×2 candles)
  exclusion_conditions   = DEFINED (Section 5-A, 3 conditions)
  hold_conditions        = DEFINED (Section 5-B, 3 conditions)
  comparison_basis       = DEFINED (Section 8, frozen dataclass)
  
  completion_criteria    = 7/7 MET
  
  promotion_block_reason = enforcement_safety_not_defined
  execution_binding      = NONE
  promotion_open         = FALSE
  production_authorized  = FALSE
  auto_advance           = FORBIDDEN
  
  numeric_target_definition = explicitly_deferred_outside_current_and_next_gate_scope
  
  remaining_next_gate    = enforcement_safety
  current_promotion      = CLOSED
  
  review_status          = SEALED
  sealed_at              = 2026-04-13
─────────────────────────────────────────────────
```
