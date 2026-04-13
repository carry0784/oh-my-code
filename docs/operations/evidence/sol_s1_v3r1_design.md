# SOL S-1 V-3R1 — Corrective Chain Design

**발행일:** 2026-04-10
**revision_date:** 2026-04-10 (사용자 REVISE 지시 반영)
**sealed_at:** 2026-04-10 (사용자 REV-1 ACCEPT + SEAL APPROVED)
**chain:** Phase C Post-Closure — SOL S-1 Root-Cause Chain
**step:** V-3R1 design (Receipt / Mode Alignment Corrective Chain)
**chain_type:** corrective (검증 정합성 보정), **전략 개선 아님**
**design_status:** SEALED (REV-1 ACCEPT / seal_decision=APPROVED)
**review_status:** ACCEPTED (사용자 6-section 재리뷰 통과, Q1-Q6 전원 ACCEPT)
**document_state:** SEALED

**revision_log:**
- DRAFT (2026-04-10): 초안 작성, 6개 질문 사용자 리뷰 요청
- REV-1 (2026-04-10): Q2 schema hash 필수/선택 분리, Q3 execution_mode 판정 방식 명시 선언 우선, 금지영역 1건 보강, 더 좋은 아이디어 3건 추가
- SEAL-1 (2026-04-10): 사용자 REV-1 ACCEPT 판정 (Q1-Q6 전원 ACCEPT), 비차단 메모 1건 반영 (Meta-layer 표기 "핵심 5 + 보강 2" 명확화), 아이디어 3 반영 (V-3R1 PASS = corrective-chain PASS only), REVISED_DRAFT → SEALED 전환

**meta_layer_notation (SEAL-1 비차단 메모 반영):**
```
Meta-layer core       = 5 fields
  (technical_execution_status, governance_validity_status,
   execution_mode, run_duration_ms, bars_per_second)
Meta-layer extensions = 2 fields
  (execution_mode_source, mode_consistency_check)
Meta-layer total      = 5 + 2 = 7 fields
```

**v3r1_pass_scope (SEAL-1 아이디어 3 반영):**
```
V-3R1 PASS = corrective-chain PASS only
→ V-3R1 PASS는 검증 인프라 보정 체인의 통과만 의미한다
→ V-3 shadow drift verification 의 최종 통과 근거 아님
→ V-4 unlock 의 근거 아님
```

**previous_receipts (전체 사슬):**
- `sol_s1_v3_design.md` (V-3 설계, SEALED)
- `sol_s1_v3_go_receipt.md` (V-3 explicit GO)
- `sol_s1_v3_impl_scope_lock.md` (V-3 구현 범위 잠금)
- `sol_s1_v3_impl_start_go.md` (V-3 구현 착수 허가)
- `sol_s1_v3_impl_completion_receipt.md` (V-3 구현 완료)
- `sol_s1_v3_run_go.md` (V-3 run GO, ACCEPTED/SEALED, 16필드 요구)
- `sol_s1_v3_shadow_log.json` (run attempt #1 실측)
- `sol_s1_v3_completion_receipt.md` (script 산출, 12필드, schema conflict)
- `sol_s1_v3_run_attempt1_invalid_seal.md` (attempt #1 INVALID 봉인)

**authorization_source:** 사용자 verbatim instruction (V-3R1 corrective chain 설계서 작성 지시)
**design_authority:** 사용자 6-section 리뷰 ACCEPT + 우선순위 1 승인

---

## 목적

V-3 run attempt #1에서 드러난 **두 가지 결함**을 보정하여 V-3 shadow drift verification을 다시 유효 검증 체인으로 복구한다.

### 결함 1 — Receipt Schema Conflict

```
run GO 요구:  16 필드 (Meta 6 + Summary 6 + Guards 4)
script 산출:  12 필드 (run_id, config_fingerprint, design_version, go_receipt_id,
                      started_at, ended_at, Results 12개, Witnesses 2개, Binding 3개)
누락:         6 필드 (authorization_source, implementation_receipt_ref,
                      implementation_artifacts_frozen, run_result_class,
                      code_mutation_during_run, scope_lock_respected)
```

**원인:** 스크립트가 `sol_s1_v3_impl_start_go.md` 시점에 frozen되었으나, `sol_s1_v3_run_go.md`에서 추가된 6개 필드는 반영되지 않음. `go_receipt_id: sol_s1_v3_impl_start_go.md`가 증거.

### 결함 2 — Execution Mode Ambiguity

```
실측 duration:     ~43ms
bars_observed:     92
trades_count:      0
script loaded:     144 bars (replay 데이터)
본래 의도:         shadow drift verification (real-time 지향)
```

**원인:** `execution_mode` 필드 부재로 replay vs real-time shadow의 의미가 구분되지 않음. 43ms 안에 144 bars를 처리한 것은 realtime_shadow 의미론과 다름.

### V-3R1의 목적 (명시)

**O:** V-3 재검증 가능 상태 복원
**X:** 전략 로직 개선, baseline 재조정, taxonomy 확장, 수익성 최적화

---

## 섹션 1 — 교리 검사

### 자동화 가능성

V-3R1의 모든 보정 항목은 **기계 판정 가능**해야 한다:

- Schema 16필드 완결성 → field count 자동 검증
- Execution mode 구분 → enum 자동 판정
- Schema hash 비교 → sha256 자동 계산
- Trust chain 참조 → string equality 자동 검증

**자동화 가능성 유지 여부:** ✅ 유지 (자유 서술 없음)

### 자율판단 가능성

본 체인은 2층 판정 구조를 **강화**한다:

```
technical_execution_status: EXECUTED | ABORTED | FAILED_TO_START
governance_validity_status: VALID | INVALID | CONFLICTED
```

**자율판단 가능성 유지 여부:** ✅ 강화 (기존 final_state + run_result_class 위에 meta-layer 추가)

### 자가진화 루프 연결성

V-3R1 자체가 **진화 증거**이다:
- V-3 attempt #1 실패 → schema drift 학습 → V-3R1 보정 → V-3 attempt #2 재검증
- 이는 "전략 진화"가 아니라 **"검증 인프라 진화"**

**자가진화 루프 유지 여부:** ✅ 유지 (체인 전체가 학습-보정 루프의 증거)

### 헌법/거버넌스 충돌 여부

| 헌법 조항 | V-3R1 영향 | 준수 |
|----------|-----------|------|
| baseline 불변 (ECR 64.3 / block 35.7 / SD 70.9 / fit 0.4428) | 수정 안 함 | ✅ |
| taxonomy 불변 (block 3 / stop_reason 6) | 수정 안 함 | ✅ |
| V-1/V-2 산출물 불변 | 수정 안 함 | ✅ |
| 전략 parameter source 불변 | 수정 안 함 | ✅ |
| V-4 unlock 금지 (V-3 INVALID 상태) | 논의 안 함 | ✅ |
| auto_advance 금지 | 유지 | ✅ |
| V-3 attempt #1 INVALID seal 보존 | 수정 안 함 | ✅ |

**헌법 충돌 여부:** ❌ 없음

**교리 검사 판정: 정합. 완료**

---

## 섹션 2 — 틀거리 매핑

### Observation

V-3R1이 관측할 항목:
- script frozen 상태 (수정 전 fingerprint)
- receipt schema 16필드 완결성
- execution_mode 실측값 (duration, bars per second)
- trust chain 참조 일치성

### Interpretation

V-3R1의 해석 규칙 (REV-1 수정):

**주 판정 기준 — 명시적 선언값**
- `execution_mode`는 **명시적 선언 필드**를 1차 판정 근거로 사용한다
- 값: `realtime_shadow | historical_replay | ambiguous`
- 선언 출처는 `execution_mode_source`로 별도 기록:
  `declared_by_go | declared_by_runner | inferred_from_runtime`

**보조 판정 기준 — 감사 보조지표**
- `run_duration_ms`, `bars_per_second`는 **감사 보조 witness**이며 판정 근거 본체가 아니다
- 보조 규칙 (경고만 발생, 단독 판정 금지):
  - `bars_per_second >= 1` → replay-like 경고
  - `bars_per_second <= 0.001` → realtime-like 경고
  - 그 사이 → ambiguous 기록
- 선언값과 witness가 어긋나면 `mode_consistency_check = warning | ambiguous`

**금지**
- 속도값(`bars_per_second`, `run_duration_ms`) **단독**으로 `execution_mode`를 확정 판정하는 설계는 금지

### Decision

V-3R1 완료 조건:
- 16필드 receipt 정렬 완료
- execution_mode 판정 로직 내재화
- schema hash 사전 검증 통과
- V-3 attempt #2 재실행 가능 상태

### Execution

V-3R1 허용 행위:
- `scripts/sol_s1_v3_shadow_run.py` 제한적 수정 (frozen 해제, scope lock 준수)
- V-3R1 전용 receipt template 생성 (선택)
- schema hash 사전 계산 유틸 추가 (선택, 단일 스크립트 원칙 유지)

V-3R1 금지 행위:
- 전략 로직 변경
- baseline 변경
- taxonomy 변경
- N1/N3 삽입
- 수익성 최적화
- V-4 unlock 논의

### Learning

V-3R1이 만드는 학습 지점:
- GO sealed 이후 schema drift 방지 규칙
- implementation frozen과 run GO의 순서 정합성 규칙
- replay vs realtime 검증 목적 분리 규칙

### Evolution

V-3R1은 **전략 진화가 아닌 검증 인프라 진화**이다. 진화 범위는:
- Receipt schema alignment (16 fields 이상)
- Execution mode awareness
- Schema hash pre-validation (선택)

진화하지 않는 것:
- 전략 로직
- baseline 수치
- V-2 선정 결과 (C1C2_N2)
- state transition 수치

### Constitution

V-3R1 후에도 유지되어야 할 헌법:
- `auto_advance = 금지`
- V-4 unlock은 V-3 attempt #2 PASS 후에만 재검토
- INVALID seal은 영구 보존 (덮어쓰기 금지)
- frozen artifacts 일체 존중 (V-3R1 수정 대상만 예외)

**틀거리 매핑 판정: 정합. 완료**

---

## 섹션 3 — 슬롯 분해

### 관측 규칙 (Observation Rules)

```
- receipt_field_count         : script output 실측
- evidence_field_count        : shadow_log.json 실측 (18 유지)
- run_duration_ms             : started_at ~ ended_at
- bars_per_second             : bars_observed / (run_duration_ms / 1000)
- frozen_artifact_hashes      : 사전/사후 sha256 비교 (선택)
```

### 해석 규칙 (Interpretation Rules, REV-1 수정)

```
# Schema 완결성
IF receipt_field_count < 16 THEN schema_conflict = true

# 상태 이원화
IF technical_status = EXECUTED AND governance_status = INVALID THEN result = CONFLICTED

# execution_mode 주 판정 (명시 선언값 우선)
IF execution_mode_declared IN (realtime_shadow, historical_replay)
    THEN execution_mode = execution_mode_declared
    AND execution_mode_source = declared_by_go (or declared_by_runner)
ELIF execution_mode_declared IS NULL
    THEN execution_mode = ambiguous
    AND execution_mode_source = inferred_from_runtime

# execution_mode 보조 sanity check (판정 근거 아님, 경고만)
IF bars_per_second >= 1
    THEN witness_hint = replay-like
ELIF bars_per_second <= 0.001
    THEN witness_hint = realtime-like
ELSE
    witness_hint = ambiguous

# 선언값과 witness 일치성
IF execution_mode = realtime_shadow AND witness_hint = replay-like
    THEN mode_consistency_check = warning
ELIF execution_mode = historical_replay AND witness_hint = realtime-like
    THEN mode_consistency_check = warning
ELIF witness_hint = ambiguous
    THEN mode_consistency_check = ambiguous
ELSE
    mode_consistency_check = consistent

# 금지 규칙 (본 설계서의 금지 조항)
FORBIDDEN: execution_mode를 bars_per_second / run_duration_ms 단독으로 확정 판정하는 설계
```

### 상태 전이 규칙 (State Transition Rules)

```
V-3R1 DRAFT → REVIEWED → SEALED → GO-issued → IMPLEMENTED → READY-for-V3-attempt2
                                                                    ↓
                                                         V-3 attempt #2 execution
                                                                    ↓
                                                       PASS | FAIL | INVALID 판정
```

### 시나리오 규칙 (Scenario Rules)

```
시나리오 A — Schema 보정만 필요
    → receipt 16필드 정렬
    → V-3 attempt #2 = historical_replay mode 명시 후 재실행
    → 단, "shadow drift"가 아닌 "replay validation"으로 목적 변경

시나리오 B — Mode 전환 필요
    → execution_mode = realtime_shadow 로 재정의
    → get_replay_candles 호출 대신 real-time tick stream 필요
    → 그러나 현재 인프라로 불가능할 수 있음

시나리오 C — 이원화 시나리오
    → V-3R1은 schema + mode 정렬만 수행
    → V-3R1 완료 후 시나리오 A (replay 확정) 또는 시나리오 B (realtime) 선택
    → 본 설계는 시나리오 C를 권장
```

### 실행 제한 규칙 (Execution Constraint Rules)

```
- V-3R1 구현 시 수정 대상 = scripts/sol_s1_v3_shadow_run.py 만 (최소주의)
- 신규 파일 = V-3R1 전용 evidence 문서만
- V-3 attempt #1 seal 절대 수정 금지
- V-1/V-2 일체 수정 금지
- strategy source 일체 수정 금지
- baseline 수정 금지
```

### 학습 항목 (Learning Items)

```
- GO sealed 이후에도 script frozen 기준 시점을 run GO 시점으로 맞춰야 함
- 단일 스크립트 원칙은 유지하되, run GO 필드 변경 시 script도 동기화 필요
- replay vs realtime 구분은 receipt에 필드로 명시해야 함
- schema conflict는 INVALID의 독립 원인 (trades 부족과 별도)
```

### 진화 후보 규칙 (Evolution Candidate Rules)

```
- run-go-schema alignment gate (신규)
- execution-mode validity gate (신규)
- schema_hash pre-validation gate (신규, 선택)
- frozen timestamp coherence check (신규, 선택)
```

### 헌법/거버넌스 제한 규칙 (Constitutional Rules)

```
- FAIL 재해석 금지
- INVALID seal 사후 편집 금지
- V-4 auto-unlock 금지
- 전략 개선 체인으로 전환 금지
- V-3R1 이름 남용 금지 (예: V-3R2, V-3R3 연쇄 생성 금지. R1 실패 시 별도 설계)
```

**슬롯 분해 판정: 충분. 완료**

---

## 섹션 4 — 금지영역 분리

### 절대 금지 (영구)

| # | 금지 행위 | 사유 |
|---|----------|------|
| 1 | 전략 로직 수정 | V-3R1은 검증 보정 체인 |
| 2 | baseline 수정 (64.3 / 35.7 / 70.9 / 0.4428) | V-2 sealed |
| 3 | taxonomy 수정 (block 3 / stop_reason 6) | sealed |
| 4 | V-1/V-2 산출물 수정 | sealed |
| 5 | strategy source 수정 | sealed |
| 6 | V-3 attempt #1 INVALID seal 수정/삭제 | evidence 오염 |
| 7 | V-4 unlock 논의 | V-3 PASS 미달성 |
| 8 | N1 shadow 실행 구현 | 별도 체인 |
| 9 | N3 확장 | sealed 영구 금지 |
| 10 | 수익성 최적화 로직 | V-3 본래 목적 아님 |
| 11 | auto_advance 활성화 | 헌법 위반 |
| 12 | CLAUDE.md / 헌법 수정 | sealed |
| 13 | **execution_mode를 속도값(bars_per_second / run_duration_ms) 단독으로 확정 판정하는 설계** | **REV-1 보강**: 명시 선언값이 주 판정 근거, 속도는 감사 보조지표 |

### 조건부 허용 (V-3R1 범위 내)

| # | 허용 행위 | 조건 |
|---|----------|------|
| 1 | `scripts/sol_s1_v3_shadow_run.py` 수정 | V-3R1 explicit GO 발행 후에만, 아래 6개 필드 추가 범위로 제한 |
| 2 | receipt 16필드 정렬 | run GO 요구 반영 |
| 3 | `execution_mode` 필드 추가 | 새 enum 2개 (realtime_shadow, historical_replay) |
| 4 | `technical_execution_status` 필드 추가 | enum 3개 (EXECUTED, ABORTED, FAILED_TO_START) |
| 5 | `governance_validity_status` 필드 추가 | enum 3개 (VALID, INVALID, CONFLICTED) |
| 6 | `run_result_class` 산출 로직 내재화 | 현재 agent judgment → script 내 자동 판정 |
| 7 | `code_mutation_during_run` 계산 규칙 | frozen hash 사전/사후 비교 (선택) |
| 8 | `scope_lock_respected` 계산 규칙 | 금지 파일 목록 체크 (선택) |
| 9 | `authorization_source` 상수 | "sol_s1_v3r1_run_go.md" 또는 사용자 결정 |
| 10 | `implementation_receipt_ref` 상수 | "sol_s1_v3r1_impl_completion_receipt.md" 또는 사용자 결정 |

### 의심 영역 (추가 GO 필요, REV-1 업데이트)

| # | 행위 | 추가 GO 요구 |
|---|------|-------------|
| 1 | ~~`receipt_schema_hash` / `evidence_schema_hash` 도입~~ | **REV-1: 필수로 승격, Q2 반영** |
| 2 | `frozen_artifacts_hash_before/after` 도입 | 선택 유지, 구현 시점 사용자 결정 |
| 3 | ~~`execution_mode` 판정 기준값 (10 bps / 0.001 bps)~~ | **REV-1: 판정 기준 변경 — 명시 선언값 주 판정, 속도값은 감사 보조. 임계값은 경고 전용 (bps >= 1 = replay-like, bps <= 0.001 = realtime-like)** |
| 4 | V-3 attempt #2 재실행의 execution_mode 고정 | replay 우선, realtime 별도 GO |
| 5 | `execution_mode_source` 필드 도입 (REV-1 아이디어 1) | 필수 승급 예정, Q6 봉인 시 확정 |
| 6 | `mode_consistency_check` 필드 도입 (REV-1 아이디어 2) | 필수 승급 예정, Q6 봉인 시 확정 |

**금지영역 분리 판정: 적절. 완료**

---

## 섹션 5 — 계획서화

### V-3R1 단계 구조 (V-3 원 체인과 대칭)

```
1. V-3R1 설계서 DRAFT 작성                  [현재 위치]
2. V-3R1 설계서 검토 / 봉인                  (사용자 ACCEPT 필요)
3. V-3R1 explicit GO 발행                    (사용자 verbatim text 필요)
4. V-3R1 구현 범위 잠금                       (scope lock)
5. V-3R1 구현 착수 허가                       (impl start GO)
6. V-3R1 구현 완료 receipt                    (impl completion)
7. V-3R1 run GO (재실행 승인)                 (실행 허가)
8. V-3 attempt #2 실행                         (운영자 수동)
9. V-3 attempt #2 completion receipt          (16필드 정렬)
10. V-3 attempt #2 judgment                   (PASS | FAIL | INVALID)
11. (IF PASS) V-4 unlock 별도 체인             (PASS 이후에만)
```

**권장:** 1-10단계를 생략 없이 거친다. 빠른 진행은 또 다른 schema drift의 원인.

### V-3R1 수정 대상 파일 (최소화)

```
modify (허용):
  - scripts/sol_s1_v3_shadow_run.py
    (16필드 receipt 정렬 + execution_mode 판정 + 이원화 상태 필드)

create (허용):
  - docs/operations/evidence/sol_s1_v3r1_design.md            [본 파일]
  - docs/operations/evidence/sol_s1_v3r1_go_receipt.md        (별도 GO 시)
  - docs/operations/evidence/sol_s1_v3r1_impl_scope_lock.md   (scope lock 시)
  - docs/operations/evidence/sol_s1_v3r1_impl_start_go.md     (구현 착수 시)
  - docs/operations/evidence/sol_s1_v3r1_impl_completion_receipt.md
  - docs/operations/evidence/sol_s1_v3r1_run_go.md
  - docs/operations/evidence/sol_s1_v3_attempt2_shadow_log.json
  - docs/operations/evidence/sol_s1_v3_attempt2_completion_receipt.md
  - docs/operations/evidence/sol_s1_v3_attempt2_seal.md       (결과 봉인)

do not touch:
  - sol_s1_v3_design.md                                       (SEALED)
  - sol_s1_v3_impl_scope_lock.md                              (SEALED)
  - sol_s1_v3_impl_completion_receipt.md                      (SEALED)
  - sol_s1_v3_run_go.md                                       (SEALED)
  - sol_s1_v3_shadow_log.json                                 (evidence)
  - sol_s1_v3_completion_receipt.md                           (evidence)
  - sol_s1_v3_run_attempt1_invalid_seal.md                    (SEALED)
  - scripts/sol_s1_v1_*.py, sol_s1_v2_*.py                    (SEALED)
  - strategies/*, app/core/config.py, CLAUDE.md               (SEALED)
```

### Receipt 16필드 최종 구조 (V-3R1 구현 목표)

#### Meta & Trust Chain (6)

```json
{
  "authorization_source":              "str (V-3R1 run GO 경로)",
  "implementation_receipt_ref":        "str (V-3R1 impl completion 경로)",
  "design_version":                    "str (V-3 설계 + V-3R1 설계 둘 다 참조)",
  "implementation_artifacts_frozen":   "bool (V-3R1 완료 후 true)",
  "run_started_at":                    "ISO8601",
  "run_completed_at":                  "ISO8601"
}
```

#### Shadow Results Summary (6)

```json
{
  "final_state":                       "GREEN | YELLOW | RED",
  "run_result_class":                  "PASS | FAIL | INVALID",
  "bars_observed":                     "int",
  "trades_count":                      "int",
  "ecr":                               "float",
  "block_rate":                        "float"
}
```

#### Invariance Guards (4)

```json
{
  "baseline_mutation":                 "bool (기대: false)",
  "fallback_executed":                 "bool (기대: false)",
  "code_mutation_during_run":          "bool (기대: false)",
  "scope_lock_respected":              "bool (기대: true)"
}
```

### Meta-Layer 필드 (REV-1 확정 / SEAL-1 표기 명확화)

**표기 규약:** Meta-layer = **핵심 5 + 보강 2** = 총 7 필드

#### 핵심 5 (Q1 ACCEPT — 설계 초안 시점부터 필수)

**status 이원화 (2)**
```json
{
  "technical_execution_status":        "EXECUTED | ABORTED | FAILED_TO_START",
  "governance_validity_status":        "VALID | INVALID | CONFLICTED"
}
```

**execution_mode 주 판정 (1)**
```json
{
  "execution_mode":                    "realtime_shadow | historical_replay | ambiguous  (명시 선언값 주 판정)"
}
```

**보조 witness 지표 (2)**
```json
{
  "run_duration_ms":                   "int (종료 - 시작, 감사 보조)",
  "bars_per_second":                   "float (실측, 감사 보조, 단독 판정 금지)"
}
```

#### 보강 2 (REV-1 추가, 더 좋은 아이디어 1/2 반영)

**execution_mode 출처/일치성 (2)**
```json
{
  "execution_mode_source":             "declared_by_go | declared_by_runner | inferred_from_runtime  (REV-1 아이디어 1)",
  "mode_consistency_check":            "consistent | warning | ambiguous  (REV-1 아이디어 2, 선언값 vs witness 일치성)"
}
```

### Schema Hash 필드 (REV-1 수정, Q2)

**필수 (2) — REV-1 승격**
```json
{
  "receipt_schema_hash":               "str (sha256 of 16-field receipt schema)",
  "evidence_schema_hash":              "str (sha256 of 18-field evidence schema)"
}
```

**선택 (2) — 유지**
```json
{
  "frozen_artifacts_hash_before":      "str (run 시작 시 V-3 frozen artifacts sha256, 선택)",
  "frozen_artifacts_hash_after":       "str (run 종료 시 V-3 frozen artifacts sha256, 선택)"
}
```

**수정 근거 (사용자 Q2 REVISE 지시):**
- 이번 체인의 본질은 schema drift 문제이므로 schema hash 2개는 **필수**
- frozen artifacts hash 전체 강제는 운영 복잡도 과다 → **선택**으로 유지

### Execution Mode 판정 로직 (REV-1 수정)

**변경 사유 (Q3 REVISE):** 속도값 단독 판정은 금지. 명시 선언값이 주 판정 근거.

```python
def determine_execution_mode(
    declared_mode: str | None,          # go/runner가 선언한 값
    declaration_source: str | None,     # declared_by_go | declared_by_runner | None
    run_duration_ms: int,
    bars_observed: int,
) -> dict:
    """
    REV-1 판정 규칙:
    1. 선언값이 있으면 선언값 채택 (주 판정)
    2. 선언값이 없으면 ambiguous (inferred_from_runtime)
    3. witness(bars_per_second)는 판정 근거 아님 — 일치성 경고용
    """
    # 보조 witness 계산
    if bars_observed > 0 and run_duration_ms > 0:
        bars_per_second = bars_observed / (run_duration_ms / 1000.0)
    else:
        bars_per_second = 0.0

    # witness hint (경고 생성용, 판정 근거 아님)
    if bars_per_second >= 1:
        witness_hint = "replay-like"
    elif bars_per_second <= 0.001:
        witness_hint = "realtime-like"
    else:
        witness_hint = "ambiguous"

    # 주 판정: 명시 선언값 우선
    if declared_mode in ("realtime_shadow", "historical_replay"):
        execution_mode = declared_mode
        execution_mode_source = declaration_source or "declared_by_runner"
    else:
        execution_mode = "ambiguous"
        execution_mode_source = "inferred_from_runtime"

    # 일치성 체크 (경고 생성)
    if execution_mode == "realtime_shadow" and witness_hint == "replay-like":
        mode_consistency_check = "warning"
    elif execution_mode == "historical_replay" and witness_hint == "realtime-like":
        mode_consistency_check = "warning"
    elif witness_hint == "ambiguous" or execution_mode == "ambiguous":
        mode_consistency_check = "ambiguous"
    else:
        mode_consistency_check = "consistent"

    return {
        "execution_mode": execution_mode,
        "execution_mode_source": execution_mode_source,
        "run_duration_ms": run_duration_ms,
        "bars_per_second": bars_per_second,
        "mode_consistency_check": mode_consistency_check,
    }
```

**보조 witness 임계값 (경고 전용, 판정 아님)**
- `bars_per_second >= 1` → replay-like 힌트
- `bars_per_second <= 0.001` → realtime-like 힌트
- 그 사이 → ambiguous 힌트

**중요:** 위 임계값은 **경고 생성용**이며, 선언값을 덮어쓰지 않는다. 속도 단독으로 `execution_mode`를 확정하는 설계는 절대 금지 (금지영역 #13).

### V-3 attempt #2 재실행 execution_mode 결정 가이드 (REV-1 수정)

| 목적 | 권장 mode | 근거 |
|------|----------|------|
| V-2 baseline 의 drift 감시 (본래 목적) | realtime_shadow | 실시간 관찰 필요 |
| C1C2_N2 config 의 replay 안정성 재확인 | historical_replay | V-2와 동일 데이터 재검증 |
| 두 가지 모두 | 두 단계로 분리 | R1은 replay, 별도 GO로 realtime |

**권장:** V-3R1 완료 후 **historical_replay mode로 먼저 재검증**하고, 이후 별도 GO로 realtime_shadow 확장. 단일 GO에 두 mode를 섞지 않는다.

### ⚠️ Attempt #2 목적 제한 (REV-1 고정 문구, Q4 boundary)

```
attempt #2 = corrective validation run
attempt #2 의 목적 = V-3R1 schema / trust chain / mode labeling 보정 확인
attempt #2 는 V-3 shadow drift verification 의 최종 통과 근거로 사용 금지
```

### ⚠️ Mode 간 PASS 전이 금지 (REV-1 아이디어 3)

```
historical_replay PASS != realtime_shadow PASS
```

- historical_replay mode 에서 얻은 PASS는 corrective validation 근거일 뿐, realtime_shadow drift verification 의 PASS 로 자동 전이되지 않는다
- 실시간 drift 검증의 PASS 근거는 **별도의 realtime_shadow mode run GO + 실제 실시간 관찰**로만 획득 가능하다
- 이 문장은 V-3R1 설계서와 V-3R1 run GO, V-3 attempt #2 seal 문서 모두에 **반드시 명시 복사**되어야 한다

### V-3R1 PASS 조건 (REV-1)

```
1. scripts/sol_s1_v3_shadow_run.py 가 16 필수 필드를 모두 출력
2. 7개 meta-layer 필드 추가:
   - technical_execution_status, governance_validity_status
   - execution_mode, execution_mode_source (REV-1 아이디어 1)
   - mode_consistency_check (REV-1 아이디어 2)
   - run_duration_ms, bars_per_second
3. Schema hash 2필드 필수 출력 (REV-1 Q2 반영):
   - receipt_schema_hash, evidence_schema_hash
4. execution_mode 판정 로직 내재화:
   - 명시 선언값(declared_mode)을 주 판정 근거로 사용
   - run_duration_ms / bars_per_second는 보조 witness로만 사용
   - 속도값 단독 판정 코드 절대 포함 금지 (금지영역 #13)
5. frozen artifacts 0건 수정 (V-3R1 범위 파일만 예외)
6. V-3 attempt #1 INVALID seal 0건 수정
7. V-3R1 전용 evidence 문서 체인 완결 (design → go → scope lock → impl start → impl completion → run go)
8. V-3 attempt #2 재실행 준비 상태 도달 (corrective validation 한정)
9. "historical_replay PASS != realtime_shadow PASS" 문구가 V-3R1 run GO + V-3 attempt #2 seal 에 복사 포함됨 (REV-1 아이디어 3)
```

### V-3R1 FAIL 조건 (일반 FAIL, 재설계 필요)

```
- 금지 파일 1건 이상 수정
- baseline 1건 이상 변경
- taxonomy 1건 이상 변경
- 16필드 중 1개 이상 누락 유지
- V-3 attempt #1 seal 수정
```

### V-3R1 INVALID 조건 (체인 무효, 별도 복구 GO 필요)

```
- V-3R1 설계서가 사용자 ACCEPT 없이 GO 발행
- V-3R1 explicit GO 없이 스크립트 수정
- V-3R1 구현 단계에서 run 실행 발생 (execution_started=true)
```

**계획서화 판정: 완결. 완료**

---

## Chain 상태 갱신 (SEAL-1)

| 단계 | 상태 | 비고 |
|------|------|------|
| Root-Cause Analysis | CLOSED | COMPLETE |
| V-1 | CLOSED | INFORMATIVE_FAIL |
| V-2 | CLOSED | PASS (C1C2_N2) |
| V-3 원 체인 (설계 ~ run GO) | COMPLETE | SEALED |
| V-3 run attempt #1 | EXECUTED / INVALID | SEALED |
| V-3R1 설계서 DRAFT | COMPLETE | 초안 작성 완료 |
| V-3R1 설계서 REVISED_DRAFT | COMPLETE | Q2/Q3 수정 반영 |
| **V-3R1 설계서 SEALED** | **현재 위치** | **사용자 REV-1 ACCEPT, Q1-Q6 전원 ACCEPT** |
| V-3R1 explicit GO | NOT STARTED | 본 설계 봉인 완료, 다음 단계 진입 가능 |
| V-3R1 구현 범위 잠금 | NOT STARTED | 별도 단계 |
| V-3R1 구현 착수 | NOT STARTED | 별도 단계 |
| V-3R1 구현 완료 | NOT STARTED | 별도 단계 |
| V-3R1 run GO | NOT STARTED | 별도 단계 |
| V-3 attempt #2 실행 | LOCKED | V-3R1 완료 필요, corrective validation 한정 |
| V-3 attempt #2 판정 | LOCKED | 실행 필요 |
| V-4 (Paper) | LOCKED | V-3 PASS 미달성 (realtime_shadow PASS 필요) |

---

## 봉인 (SEALED, 사용자 REV-1 ACCEPT 판정)

**seal_decision:** APPROVED (사용자 6-section 재리뷰에서 Q1-Q6 전원 ACCEPT)
**sealed_at:** 2026-04-10
**sealed_by:** 사용자 verbatim text ("REV-1 ACCEPT. REVISED_DRAFT → SEALED 전환 승인.")

---

### 봉인 항목 (SEALED)

- V-3R1은 **검증 정합성 보정 체인**이며, **전략 개선 체인이 아니다**
- 본 설계서는 V-3 attempt #1의 **schema conflict**와 **execution mode ambiguity**를 보정한다
- V-3R1 범위는 `scripts/sol_s1_v3_shadow_run.py` 제한적 수정 + V-3R1 전용 evidence 문서 생성
- baseline (64.3 / 35.7 / 70.9 / 0.4428) / taxonomy (block 3 / stop_reason 6) / strategy source 일체 불변
- V-1/V-2 산출물 일체 불변
- V-3 attempt #1 INVALID seal 영구 보존
- V-4 unlock은 V-3 attempt #2 PASS 이후에만 재검토

### SEAL-1 확정 사항 (Q1-Q6 전원 ACCEPT)

**Q1 ACCEPT — Meta-layer 필드 (핵심 5 + 보강 2 = 총 7)**
- 핵심 5: `technical_execution_status`, `governance_validity_status`, `execution_mode`, `run_duration_ms`, `bars_per_second`
- 보강 2: `execution_mode_source`, `mode_consistency_check` (REV-1 추가)

**Q2 ACCEPT — Schema hash 필수/선택 분리**
- 필수: `receipt_schema_hash`, `evidence_schema_hash`
- 선택: `frozen_artifacts_hash_before`, `frozen_artifacts_hash_after`

**Q3 ACCEPT — execution_mode 판정 방식**
- 주 판정 기준 = 명시 선언값 (`execution_mode_source`로 출처 기록)
- 보조 witness = `run_duration_ms` / `bars_per_second` (판정 근거 아님)
- 속도값 단독 판정 설계 절대 금지 (금지영역 #13)
- ambiguous 구간 명시 허용

**Q4 ACCEPT with boundary — V-3 attempt #2**
- historical_replay mode 우선 권장
- attempt #2 = corrective validation run (realtime_shadow 최종 통과 근거 아님)
- **historical_replay PASS != realtime_shadow PASS** (강제 복사 문구)

**Q5 ACCEPT — 10단계 구조 유지** (축약 없음)

**Q6 ACCEPT — 설계 봉인 승인** (REVISED_DRAFT → SEALED)

### SEAL-1 비차단 메모 반영 사항

**Meta-layer 표기 명확화:**
```
Meta-layer core       = 5 fields
Meta-layer extensions = 2 fields (execution_mode_source, mode_consistency_check)
Meta-layer total      = 5 + 2 = 7 fields
```

### SEAL-1 아이디어 3 반영 (PASS 범위 제한)

```
V-3R1 PASS = corrective-chain PASS only
→ V-3R1 PASS는 검증 인프라 보정 체인의 통과만 의미한다
→ V-3 shadow drift verification 의 최종 통과 근거 아님
→ V-4 unlock 의 근거 아님
→ V-3R1 PASS ≠ V-3 PASS ≠ V-4 unlock 근거
```

### 봉인 이후 변경 규칙

- SEALED 이후 본 설계서 본문 수정 금지
- 추후 정합성 오류 발견 시 V-3R2 별도 설계 체인으로 대응 (V-3R1 재편집 금지)
- 사용자 추가 아이디어 반영은 V-3R1 explicit GO 이후 단계에서 수행 가능
- auto_advance = 금지

---

## Global State Declaration (SEAL-1)

```
V-3 SHADOW RUN ATTEMPT #1          = EXECUTED / SEALED / INVALID
V-3 EVIDENCE SEAL                  = COMPLETE
V-4 UNLOCK                         = LOCKED (영구, realtime_shadow PASS 미달성)
V-3R1 DESIGN                       = SEALED (Q1-Q6 전원 ACCEPT, REV-1 + SEAL-1 반영)
V-3R1 EXPLICIT GO                  = NOT STARTED (다음 단계)
V-3R1 IMPLEMENTATION               = NOT STARTED
V-3 ATTEMPT #2                     = LOCKED (corrective validation 한정)
GLOBAL STATE                       = STANDBY
RUN_AUTHORIZATION                  = NOT GRANTED
IMPLEMENTATION_ARTIFACTS_FROZEN    = true (V-3 원 체인 유지)
NEXT LEGAL ACTION                  = V-3R1 explicit GO 초안 작성 및 사용자 리뷰
POST_SEAL_STATE                    = STANDBY
auto_advance                       = 금지
```

### 봉인 결과 (Q1-Q6)

| # | 질문 | 판정 | 비고 |
|---|------|------|------|
| Q1 | Meta-layer 5필드 채택 | ACCEPT | 핵심 5 확정 |
| Q2 | Schema hash 4필드 채택 | ACCEPT (REV-1) | 필수 2 + 선택 2 분리 |
| Q3 | execution_mode 임계값 확정 | ACCEPT (REV-1) | 명시 선언값 우선, 속도는 보조 |
| Q4 | V-3 attempt #2 실행모드 선택 | ACCEPT with boundary | historical_replay 우선, corrective 한정 |
| Q5 | 10단계 체인 축약 여부 | ACCEPT | 축약 없음 |
| Q6 | V-3R1 설계 봉인 결정 | ACCEPT (SEAL-1) | REVISED_DRAFT → SEALED 전환 승인 |

**overall_decision:** ACCEPT
**seal_decision:** APPROVED
**next_legal_step:** V-3R1 explicit GO 초안 작성
