# SOL S-1 V-3 — Shadow Run Execution Explicit GO

**발행일:** 2026-04-10
**chain:** Phase C Post-Closure — SOL S-1 Root-Cause Chain
**step:** V-3 shadow run authorization
**previous_receipts:**
- `sol_s1_v3_design.md` (CLOSED/ACCEPT)
- `sol_s1_v3_go_receipt.md` (V-3 explicit GO)
- `sol_s1_v3_impl_scope_lock.md` (구현 범위 잠금, 필드 18)
- `sol_s1_v3_impl_start_go.md` (구현 착수 허가)
- `sol_s1_v3_impl_completion_receipt.md` (구현 완료, 8/8 검증 PASS)

**authorization_scope:** 96-bar shadow run 실행만 허가
**authorization_type:** 실행 허가 문서 (코드 변경 허가 문서 아님)
**implementation_artifacts_frozen:** true
**review_status:** ACCEPTED / 2026-04-10 (6-section review, 단점 3건 모두 문구/가시성 수준)
**document_state:** SEALED (실사용 실행 허가 문서)

---

## 목적

V-2에서 PASS한 C1C2_N2 config의 shadow drift 안정성을 실제 96-bar shadow run으로 검증한다.

본 GO는 다음과 같은 성격을 가진다:

- ✅ **실행 허가 문서**
- ❌ 코드 변경 허가 문서 아님
- ❌ baseline 수정 허가 문서 아님
- ❌ taxonomy 재설계 허가 문서 아님
- ❌ 설계서 수정 허가 문서 아님

본 GO 발행 이후 구현 산출물은 **동결(frozen)** 되며, run 중 어떠한 코드/필드/enum/baseline 변경도 허가되지 않는다.

---

## 참조 문서 3개 (고정)

| # | 문서 | 역할 | 상태 |
|---|------|------|------|
| 1 | `docs/operations/evidence/sol_s1_v3_design.md` | 설계 기준 / 4개 수치 잠금 | SEALED |
| 2 | `docs/operations/evidence/sol_s1_v3_impl_scope_lock.md` | 구현 경계 / 금지 파일 목록 / 필드 18 / enum 6 | SEALED |
| 3 | `docs/operations/evidence/sol_s1_v3_impl_completion_receipt.md` | 구현 산출물 동결 증거 / 8/8 검증 결과 | SEALED |

세 문서는 본 run GO에 의해 **참조-고정**되며, run 기간 중 본문/내용 수정 금지.

---

## Explicit Run GO — Verbatim

```text
V-3 SHADOW RUN EXECUTION GO

목적
V-2에서 PASS한 C1C2_N2 config의 shadow drift 안정성을 96-bar shadow run으로
검증한다. 본 GO는 실행 허가 문서이며, 코드 변경 허가 문서가 아니다.

참조 문서 (고정, 수정 금지)
- 설계: docs/operations/evidence/sol_s1_v3_design.md
- 구현 경계: docs/operations/evidence/sol_s1_v3_impl_scope_lock.md
- 구현 완료: docs/operations/evidence/sol_s1_v3_impl_completion_receipt.md

허용 실행
- scripts/sol_s1_v3_shadow_run.py 단일 스크립트 실행만 허가
- 환경 변수 SOL_S1_V3_RUN_AUTHORIZED=v3_run_go_granted 설정 허가
- --run CLI flag 사용 허가
- evidence log / completion receipt 신규 작성 허가
  * docs/operations/evidence/sol_s1_v3_shadow_log.json
  * docs/operations/evidence/sol_s1_v3_completion_receipt.md

잠금 기준 (수정 금지)
- 최소 기간 = 96 bars
- Yellow 연장 = 최대 1회, +48 bars
- invalid run = 0
- 최소 trades = 10 이상
- config = C1C2_N2 단일 (fallback 자동 전환 금지)

상태 전이 기준 (설계서 §3 재확인, 수정 금지)
- Green:
  ECR >= 60% AND
  block_rate <= 40% AND
  SD_delta <= +10pp AND
  invalid = 0
- Yellow:
  ECR 55% 이상 60% 미만 OR
  block_rate 40% 초과 45% 이하 OR
  SD_delta +10pp 초과 +15pp 이하
  (rolling 12-bar 기준 연속 3회 시 Yellow 확정)
- Red:
  ECR < 55% OR
  block_rate > 45% OR
  SD_delta > +15pp OR
  invalid >= 1
  (Red 진입 시 즉시 fail-closed 중단)

V-2 baseline 고정 참조값 (수정 금지)
- ECR = 64.3%
- block_rate = 35.7%
- same_direction_ratio = 70.9%
- fitness = 0.4428

Stop reason enum (6, 수정/확장 금지)
- STOP_PASS_GREEN
- STOP_RED_ECR
- STOP_RED_BLOCK_RATE
- STOP_RED_SD_RATIO
- STOP_INVALID_RUN
- STOP_YELLOW_EXTENSION_EXHAUSTED

Evidence log 필수 필드 = 18 (수정 금지)
(설계서 §6.2 및 scope lock 문서 참조)

실행 단계 금지 항목 (재잠금 4건 + 영구 금지 항목)
[재잠금 4건]
- 코드 보강 금지
- 필드 추가 금지
- baseline 수정 금지
- taxonomy 수정 금지

[추가 금지]
- helper 파일 추가 금지 (module_split_used=true 금지)
- stop_reason enum 확장 금지
- strategy parameter 변경 금지
- fallback N1 자동 전환 금지
- 수익성 판정 금지
- V-4 unlock 논의 금지
- V-1/V-2 산출물 수정 금지
- 설계서/scope lock/impl completion receipt 수정 금지
- CLAUDE.md / 헌법 수정 금지

run 완료 후 처리 절차
1. run completion receipt 작성 (필수 필드 16개 후술)
2. RUN_RESULT_CLASS 판정 (PASS | FAIL | INVALID)
3. STATE = STANDBY
4. V-4 unlock 판정은 별도 체인 (본 GO 범위 외)
5. auto_advance = 금지

implementation_artifacts_frozen = true
```

---

## 아이디어 3건 반영 조항 (전건 채택)

### 1. `implementation_artifacts_frozen = true` 조항 (아이디어 1)

본 run GO는 구현 산출물 동결을 선언한다.

| 동결 대상 | 경로 | 동결 의미 |
|----------|------|----------|
| shadow run script | `scripts/sol_s1_v3_shadow_run.py` | 코드 수정 금지 |
| 설계서 | `sol_s1_v3_design.md` | 수치/임계값/공식 수정 금지 |
| scope lock | `sol_s1_v3_impl_scope_lock.md` | 금지 목록/필드 18/enum 6 수정 금지 |
| impl completion receipt | `sol_s1_v3_impl_completion_receipt.md` | 구현 증거 수정 금지 |

run 중 위 산출물에 대한 수정 발생 시:
- run 즉시 invalid 판정
- `RUN_RESULT_CLASS = INVALID`
- 추가 별도 GO로만 재시작 가능

### 2. `authorization_source` / `implementation_receipt_ref` 필드 (아이디어 2)

run completion receipt에 **출처 추적 2필드** 필수:

| 필드 | 값 | 의미 |
|------|---|------|
| `authorization_source` | `"sol_s1_v3_run_go.md"` | 본 run GO 문서 참조 |
| `implementation_receipt_ref` | `"sol_s1_v3_impl_completion_receipt.md"` | 구현 완료 receipt 참조 |

두 필드는 run receipt의 **trust chain anchor** 역할을 한다. 누락 시 receipt invalid.

### 3. `RUN_RESULT_CLASS` 2층 판정 분리 (아이디어 3)

최종 판정을 **shadow 상태**와 **행정 판정**으로 분리한다:

| Layer | 필드 | 값 |
|-------|------|---|
| 1층 (shadow 실측) | `final_state` | GREEN \| YELLOW \| RED |
| 2층 (행정 판정) | `run_result_class` | PASS \| FAIL \| INVALID |

#### 판정 매핑 규칙

```
PASS ← final_state == GREEN
       AND bars_observed >= 96
       AND invalid_run_count == 0
       AND trades_count >= 10
       AND yellow_extension_count <= 1 (복귀 완료)
       AND receipt_completeness_pct == 100.0
       AND baseline_mutation == false
       AND fallback_executed == false
       AND implementation_artifacts_frozen == true

FAIL ← final_state == RED
       OR yellow_extension_count > 1
       OR (yellow_extension_exhausted AND 미복귀)
       OR receipt_completeness_pct < 100.0

INVALID ← invalid_run_count >= 1
          OR trades_count < 10
          OR baseline_mutation == true
          OR fallback_executed == true
          OR implementation_artifacts_frozen == false
          OR code_mutation_during_run == true
          OR scope_lock_violation_count >= 1
```

**우선순위:** INVALID > FAIL > PASS (한 조건이라도 INVALID면 즉시 INVALID)

---

## Run Completion Receipt 필수 필드 (16개)

run 완료 후 `docs/operations/evidence/sol_s1_v3_completion_receipt.md` 작성 시 아래 필드 필수 포함.

### Meta & Trust Chain (6)

| # | 필드 | 타입 | 출처 |
|---|------|------|------|
| 1 | `authorization_source` | str | "sol_s1_v3_run_go.md" (본 문서) |
| 2 | `implementation_receipt_ref` | str | "sol_s1_v3_impl_completion_receipt.md" |
| 3 | `design_version` | str | "sol_s1_v3_design.md@2026-04-10" |
| 4 | `implementation_artifacts_frozen` | bool | true (필수) |
| 5 | `run_started_at` | ISO8601 | run 실제 시작 시각 |
| 6 | `run_completed_at` | ISO8601 | run 실제 종료 시각 |

### Shadow Results Summary (6, evidence log 복사)

| # | 필드 | 타입 | 출처 |
|---|------|------|------|
| 7 | `final_state` | enum | GREEN \| YELLOW \| RED |
| 8 | `run_result_class` | enum | PASS \| FAIL \| INVALID |
| 9 | `bars_observed` | int | evidence log |
| 10 | `trades_count` | int | evidence log |
| 11 | `ecr` | float | evidence log |
| 12 | `block_rate` | float | evidence log |

### Invariance Guards (4)

| # | 필드 | 타입 | 기대값 |
|---|------|------|-------|
| 13 | `baseline_mutation` | bool | false (필수) |
| 14 | `fallback_executed` | bool | false (필수) |
| 15 | `code_mutation_during_run` | bool | false (필수) |
| 16 | `scope_lock_respected` | bool | true (필수) |

### 금지 조합 (즉시 invalid)

```
❌ authorization_source != "sol_s1_v3_run_go.md"
❌ implementation_receipt_ref != "sol_s1_v3_impl_completion_receipt.md"
❌ implementation_artifacts_frozen == false
❌ baseline_mutation == true
❌ fallback_executed == true
❌ code_mutation_during_run == true
❌ scope_lock_respected == false
```

---

## 금지 항목 재잠금 (4건, 본 GO 핵심)

| # | 금지 | 위반 시 |
|---|------|--------|
| 1 | **코드 보강 금지** | `scripts/sol_s1_v3_shadow_run.py` 수정 금지 (1 byte도 금지) |
| 2 | **필드 추가 금지** | evidence log 필드 18개 외 추가 금지, receipt 필드 16개 외 추가 금지 |
| 3 | **baseline 수정 금지** | ECR 64.3 / block 35.7 / SD 70.9 / fitness 0.4428 수정 금지 |
| 4 | **taxonomy 수정 금지** | block taxonomy 3종 / stop_reason enum 6종 / state 3종 수정 금지 |

**위반 감지 즉시:**
- `RUN_RESULT_CLASS = INVALID`
- run 중단
- 별도 복구 GO 없이는 재실행 금지

---

## 실행 승인 경계 (Authorization Matrix)

| 행위 | 본 GO 허가 | 다음 GO 필요 |
|------|-----------|-------------|
| 환경 변수 `SOL_S1_V3_RUN_AUTHORIZED` 설정 | ✅ | — |
| `--run` flag로 shadow run 실행 | ✅ | — |
| 96-bar 실제 signal/trade 관찰 | ✅ | — |
| Yellow 1회 +48 bar 연장 | ✅ | — |
| Green/Yellow/Red 상태 판정 | ✅ | — |
| `final_state` / `run_result_class` 기록 | ✅ | — |
| shadow log JSON 작성 | ✅ | — |
| run completion receipt 작성 | ✅ | — |
| 코드 수정 (script/design/scope_lock/impl_receipt) | ❌ | 별도 보강 GO |
| evidence log 필드 18개 외 추가 | ❌ | 별도 schema GO |
| stop_reason enum 확장 | ❌ | 별도 enum GO |
| baseline 값 변경 | ❌ | 금지 (영구) |
| block taxonomy 확장 | ❌ | 금지 (영구) |
| fallback N1 자동 전환 | ❌ | 금지 (영구) |
| 수익성 최적화 | ❌ | 금지 (영구) |
| V-4 unlock 판정 | ❌ | V-4 unlock 별도 체인 |
| 다음 run 자동 시작 | ❌ | `auto_advance = 금지` |

---

## 실행 절차 (운영자 기준)

### Pre-run 체크리스트 (고정 1줄)

```text
pre_run_check = frozen=true / env_set=true / run_go=granted / code_mutation=false
```

운영자는 `--run` 실행 직전 위 4개 조건을 모두 확인한다. 하나라도 false이면 실행 금지.

| 체크 항목 | 확인 방법 |
|----------|----------|
| `frozen=true` | 본 GO 헤더의 `implementation_artifacts_frozen: true` 확인 |
| `env_set=true` | 환경 변수 `SOL_S1_V3_RUN_AUTHORIZED=v3_run_go_granted` 설정 여부 |
| `run_go=granted` | 본 GO `review_status: ACCEPTED` 확인 |
| `code_mutation=false` | `git status` / `git diff` 후 script/design/scope_lock/impl_receipt 무변경 확인 |

### 순차 절차

```
1. 본 run GO 봉인 확인 (git commit 권장)
2. Pre-run 체크리스트 4개 통과 확인

3. 환경 변수 설정 (운영자 수동)
   Windows: set SOL_S1_V3_RUN_AUTHORIZED=v3_run_go_granted
   Linux:   export SOL_S1_V3_RUN_AUTHORIZED=v3_run_go_granted

4. shadow run 실행
   python scripts/sol_s1_v3_shadow_run.py --run

5. 실행 중 관찰
   - 최소 96 bars
   - Yellow 연장 발생 시 +48 bars (최대 1회, 복귀 완료 필수)
   - Red/invalid 감지 시 즉시 fail-closed 중단

6. 완료 후 산출물 확인
   - docs/operations/evidence/sol_s1_v3_shadow_log.json (필드 18)
   - docs/operations/evidence/sol_s1_v3_completion_receipt.md (필드 16)

7. run_result_class 판정
   - PASS / FAIL / INVALID 중 하나 (우선순위: INVALID > FAIL > PASS)

8. POST_RUN_STATE = STANDBY 복귀 (고정 선언)
9. 환경 변수 해제 (권장)
10. 다음 단계는 별도 explicit GO 없이는 시작 금지
```

---

## GO 발행 헌법 확인

```
✓ V-3 설계서 CLOSED / ACCEPT
✓ V-3 explicit GO COMPLETE
✓ V-3 구현 범위 잠금 COMPLETE
✓ V-3 구현 착수 허가 COMPLETE
✓ V-3 구현 완료 COMPLETE (8/8 검증 PASS)
✓ 참조 문서 3개 고정
✓ implementation_artifacts_frozen=true 선언
✓ authorization_source / implementation_receipt_ref 필드 잠금
✓ RUN_RESULT_CLASS 2층 판정 도입
✓ 금지 항목 4건 재잠금 (코드/필드/baseline/taxonomy)
✓ run completion receipt 필수 필드 16개 정의
✓ 잠금 기준 4개 재확인 (96 bars / Yellow +48 / invalid=0 / trades≥10)
✓ V-4 unlock 체인 분리 유지
✓ auto_advance = 금지 유지
✓ 실행 허가 문서 성격 유지 (코드 변경 허가 문서 아님)
```

---

## Chain 상태 갱신

| 단계 | 상태 | 비고 |
|------|------|------|
| Root-Cause Analysis | CLOSED | COMPLETE |
| V-1 | CLOSED | INFORMATIVE_FAIL |
| V-2 | CLOSED | PASS (C1C2_N2) |
| V-3 설계서 | CLOSED | ACCEPT |
| V-3 explicit GO | COMPLETE | — |
| V-3 구현 범위 잠금 | COMPLETE | 필드 18 |
| V-3 구현 착수 허가 | COMPLETE | — |
| V-3 구현 완료 | COMPLETE | 8/8 검증 PASS |
| **V-3 shadow run GO** | **COMPLETE** | **본 receipt** |
| V-3 shadow run 실행 | 허가됨 (본 GO) | env var 설정 + `--run` flag |
| V-3 run completion receipt | NOT STARTED | run 완료 후 |
| V-3 PASS/FAIL 판정 | NOT STARTED | `run_result_class` 기반 |
| V-4 (Paper) | LOCKED | V-3 PASS + 별도 unlock 체인 |

---

## 봉인

- V-3 shadow run 실행이 본 GO로 허가되었다
- 본 GO는 **실행 허가 문서**이며 코드 변경 허가 문서가 아니다
- `implementation_artifacts_frozen = true` (스크립트/설계/scope lock/impl receipt 동결)
- 참조 문서 3개 고정: design / scope_lock / impl_completion_receipt
- 금지 항목 4건 재잠금: 코드 보강 / 필드 추가 / baseline 수정 / taxonomy 수정
- 잠금 기준: 96 bars / Yellow +48 max 1 / invalid=0 / trades≥10
- config = C1C2_N2 단일, fallback 자동 전환 금지
- V-2 baseline 고정 참조값 수정 금지 (ECR 64.3 / block 35.7 / SD 70.9 / fit 0.4428)
- Stop reason enum 6개 수정/확장 금지
- Evidence log 필수 필드 18개 수정 금지
- Run completion receipt 필수 필드 16개 정의 (Meta 6 + Summary 6 + Guards 4)
- `final_state` (shadow 실측) / `run_result_class` (행정 판정) 2층 분리
- `authorization_source` = "sol_s1_v3_run_go.md" 필수
- `implementation_receipt_ref` = "sol_s1_v3_impl_completion_receipt.md" 필수
- run 중 코드/파일 수정 감지 시 즉시 `RUN_RESULT_CLASS = INVALID`
- run 완료 후 STATE = STANDBY 복귀
- V-4 unlock 판정은 별도 체인
- auto_advance = 금지

---

## Global State Declaration

```
GLOBAL STATE                       = STANDBY (GO 발행 + ACCEPTED)
V-3 IMPLEMENTATION STATE           = COMPLETE
V-3 RUN STATE                      = AUTHORIZED / NOT STARTED
RUN_AUTHORIZATION                  = GRANTED (본 GO, ACCEPTED)
IMPLEMENTATION_ARTIFACTS_FROZEN    = true
REVIEW_STATUS                      = ACCEPTED (6-section review PASS)
DOCUMENT_STATE                     = SEALED
NEXT LEGAL ACTION                  = 운영자 env var 설정 + shadow run 실행
POST_RUN_STATE                     = STANDBY (고정)
auto_advance                       = 금지
V-4 UNLOCK CHAIN                   = 분리 유지
```

### 2층 상태 해석

본 상태는 **2층 구조**로 해석한다:

| 층 | 상태 | 의미 |
|---|------|------|
| 전역 시스템 | `GLOBAL STATE = STANDBY` | 자동 진행 없음, 다른 체인 금지 |
| 특정 run 권한 | `RUN_AUTHORIZATION = GRANTED` | V-3 shadow run 단일 실행만 허가 |

충돌 아님 — STANDBY는 "자동으로 다음 단계로 넘어가지 않음"을 의미하고, GRANTED는 "운영자 수동 실행은 허가됨"을 의미한다.

---

## POST_RUN_STATE 고정 선언

run 완료 후 (PASS/FAIL/INVALID 어느 경우든) 시스템은 다음 상태로 복귀한다:

```text
POST_RUN_STATE = STANDBY
```

- PASS 판정 시에도 V-4로 auto-advance 금지
- FAIL 판정 시에도 보강/재설계로 auto-advance 금지
- INVALID 판정 시에도 코드 수정으로 auto-advance 금지

다음 합법 행위는 **반드시 별도 explicit GO**를 통해서만 시작된다.
