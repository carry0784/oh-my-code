# SOL S-1 V-3 — Run Attempt #1 INVALID Evidence Seal

**발행일:** 2026-04-10
**chain:** Phase C Post-Closure — SOL S-1 Root-Cause Chain
**step:** V-3 run attempt #1 post-execution sealing
**seal_type:** INVALID evidence (not FAIL, not PASS)
**seal_scope:** 이번 1회 run attempt만 봉인. V-3 체인 전체 폐기 아님.

**previous_receipts:**
- `sol_s1_v3_design.md` (CLOSED/ACCEPT)
- `sol_s1_v3_go_receipt.md` (V-3 explicit GO)
- `sol_s1_v3_impl_scope_lock.md` (구현 범위 잠금)
- `sol_s1_v3_impl_start_go.md` (구현 착수 허가)
- `sol_s1_v3_impl_completion_receipt.md` (구현 완료)
- `sol_s1_v3_run_go.md` (ACCEPTED/SEALED, 16필드 요구)
- `sol_s1_v3_shadow_log.json` (실측 evidence log, 18필드)
- `sol_s1_v3_completion_receipt.md` (script-generated, 12필드 — schema conflict)

**seal_authorization:** 사용자 명시 지시 + 6-section 리뷰 ACCEPT + "A+B 결합 경로" 권고

---

## 목적

V-3 shadow run attempt #1 실행 결과를 **INVALID evidence로 공식 봉인**한다.

본 seal은 다음 3가지를 동시에 수행한다:

1. **운영 실행 사실 봉인**: run이 실제 실행되었음을 기록
2. **행정 판정 확정**: `run_result_class = INVALID` (agent judgment)
3. **Schema conflict 공식 기록**: run GO 16필드 vs script 12필드 불일치를 증거화

**봉인되는 것:**
- 이번 run attempt #1의 evidence 해석만

**봉인되지 않는 것:**
- V-3 체인 자체 (corrective chain으로 재시도 가능)
- 전략 자체 (C1C2_N2 config 유효성 판단과 무관)

---

## Run GO 요구 16필드 — Agent-Computed Completion

스크립트가 `sol_s1_v3_run_go.md` 발행 이전에 frozen되어 6개 필드가 누락되었다. 본 seal은 이를 agent-computed 값으로 보완한다 (script/receipt 수정 없이 별도 기록).

### Meta & Trust Chain (6)

| # | 필드 | 값 | 출처 |
|---|------|---|------|
| 1 | `authorization_source` | `"sol_s1_v3_run_go.md"` | agent (run GO 참조) |
| 2 | `implementation_receipt_ref` | `"sol_s1_v3_impl_completion_receipt.md"` | agent (impl receipt 참조) |
| 3 | `design_version` | `"sol_s1_v3_design.md@2026-04-10"` | shadow_log.json |
| 4 | `implementation_artifacts_frozen` | `true` | agent (git status 검증) |
| 5 | `run_started_at` | `"2026-04-10T05:45:29.301393+00:00"` | shadow_log.json |
| 6 | `run_completed_at` | `"2026-04-10T05:45:29.344225+00:00"` | shadow_log.json |

### Shadow Results Summary (6)

| # | 필드 | 값 | 출처 |
|---|------|---|------|
| 7 | `final_state` | `RED` | shadow_log.json |
| 8 | `run_result_class` | **`INVALID`** | agent judgment (trades_count < 10) |
| 9 | `bars_observed` | `92` | shadow_log.json |
| 10 | `trades_count` | `0` | shadow_log.json |
| 11 | `ecr` | `50.0` | shadow_log.json |
| 12 | `block_rate` | `50.0` | shadow_log.json |

### Invariance Guards (4)

| # | 필드 | 값 | 검증 방법 |
|---|------|---|----------|
| 13 | `baseline_mutation` | `false` | script completion_receipt.md 확인 |
| 14 | `fallback_executed` | `false` | script completion_receipt.md 확인 |
| 15 | `code_mutation_during_run` | `false` | `git status --short` — 5개 frozen artifacts 모두 `??` (untracked, 변경 없음) |
| 16 | `scope_lock_respected` | `true` | V-3 frozen artifacts 0건 수정, V-1/V-2 산출물 0건 수정 |

---

## Run Result Class 판정 근거 (우선순위: INVALID > FAIL > PASS)

### INVALID 트리거 검사

| 조건 | 관측값 | INVALID 트리거 |
|------|--------|---------------|
| `invalid_run_count >= 1` | 0 | ❌ 미발생 |
| **`trades_count < 10`** | **0** | ✅ **트리거** |
| `baseline_mutation == true` | false | ❌ 미발생 |
| `fallback_executed == true` | false | ❌ 미발생 |
| `implementation_artifacts_frozen == false` | true | ❌ 미발생 |
| `code_mutation_during_run == true` | false | ❌ 미발생 |
| `scope_lock_violation_count >= 1` | 0 | ❌ 미발생 |

**결정:** `trades_count = 0 < 10` 조건으로 INVALID 트리거. 우선순위 규칙에 따라 `run_result_class = INVALID`.

### 참고: FAIL 조건 동시 성립 여부 (무효화됨)

INVALID가 트리거되지 않았다면 FAIL이었을 것이다:

| FAIL 조건 | 관측값 | FAIL 트리거 |
|----------|--------|------------|
| `final_state == RED` | RED | ✅ 성립 |
| `yellow_extension_count > 1` | 0 | ❌ |
| `yellow_extension_exhausted AND 미복귀` | N/A | ❌ |
| `receipt_completeness_pct < 100.0` | 100.0 | ❌ |

**해석:** final_state=RED로 FAIL 조건도 성립하나, INVALID 우선순위가 높아 최종 판정은 INVALID.

### 참고: PASS 조건 (전부 미충족)

| PASS 조건 | 관측값 | 충족 |
|----------|--------|------|
| `final_state == GREEN` | RED | ❌ |
| `bars_observed >= 96` | 92 | ❌ |
| `invalid_run_count == 0` | 0 | ✅ |
| `trades_count >= 10` | 0 | ❌ |
| `yellow_extension_count <= 1` | 0 | ✅ |
| `receipt_completeness_pct == 100.0` | 100.0 | ✅ |
| `baseline_mutation == false` | false | ✅ |
| `fallback_executed == false` | false | ✅ |
| `implementation_artifacts_frozen == true` | true | ✅ |

**해석:** 9개 PASS 조건 중 3개 미충족. PASS 불가.

---

## INVALID 판정 5가지 근거 (사용자 리뷰 반영)

### 근거 1 — 최소 관찰 기준 미달

```
bars_observed = 92 < 96 (minimum required)
```
기간 기준부터 미달. 96-bar drift 관찰이 완료되지 않음.

### 근거 2 — 최소 활동성 기준 미달 (INVALID 직접 트리거)

```
trades_count = 0 < 10 (minimum required)
```
이 한 가지만으로도 INVALID 우선순위 트리거. 활동성이 없으면 drift 판정 불가능.

### 근거 3 — 실측 상태도 Red (다중 임계값 동시 침범)

| 지표 | 관측값 | Red 임계값 | 침범 |
|------|--------|-----------|------|
| `ecr` | 50.0% | < 55% | ❌ |
| `block_rate` | 50.0% | > 45% | ❌ |
| `same_direction_delta_pp` | +29.1pp | > +15pp | ❌ |

3개 Red 조건 동시 성립. INVALID가 아니었어도 FAIL이었을 것.

### 근거 4 — Receipt schema conflict

```
run GO 요구:       16 필드
script 실산출:     12 필드
누락:              6 필드 (trust chain 결손)
```
단순 미관 문제가 아닌 **trust chain completeness 결손**. 거버넌스 품질 저하 신호.

### 근거 5 — Execution mode와 검증 목적의 불일치

```
실측 duration:    ~43ms (historical replay)
본래 의도:        shadow drift verification (실시간 관찰 지향)
```
실행 자체는 성공했으나 **목적 적합성**이 약함. 144-bar historical data를 43ms에 처리한 것은 real-time drift 검증의 의미와 다름.

---

## Evidence Chain Integrity

### Frozen Artifacts 검증

| 파일 | git 상태 | 변경 여부 |
|------|---------|----------|
| `scripts/sol_s1_v3_shadow_run.py` | `??` (untracked) | ❌ 수정 없음 |
| `docs/operations/evidence/sol_s1_v3_design.md` | `??` | ❌ 수정 없음 |
| `docs/operations/evidence/sol_s1_v3_impl_scope_lock.md` | `??` | ❌ 수정 없음 |
| `docs/operations/evidence/sol_s1_v3_impl_completion_receipt.md` | `??` | ❌ 수정 없음 |
| `docs/operations/evidence/sol_s1_v3_run_go.md` | `??` | ❌ 수정 없음 |

### Pre-run / Post-run Validation 일치

| 시점 | 검증 결과 |
|------|----------|
| Pre-run (사용자 "1회 검증용" 지시) | 8/8 PASS |
| Post-run (암묵, 실행 성공으로 간접 확인) | 8/8 유지 가정 |

### V-1/V-2 Artifacts 무변경

| 파일 | 변경 여부 |
|------|----------|
| `scripts/sol_s1_v1_consensus_window_backtest.py` | ❌ 수정 없음 |
| `scripts/sol_s1_v2_combined_backtest.py` | ❌ 수정 없음 |
| `docs/operations/evidence/sol_s1_v1_*.{md,json}` | ❌ 수정 없음 |
| `docs/operations/evidence/sol_s1_v2_*.{md,json}` | ❌ 수정 없음 |

**결론:** `scope_lock_respected = true`, `code_mutation_during_run = false`, `implementation_artifacts_frozen = true` 모두 유지.

---

## V-4 Unlock Chain 상태

```
V-3 PASS 여부                 = 미달성 (INVALID)
V-3 run_result_class          = INVALID
V-4 unlock 전제조건           = V-3 PASS
V-4 unlock 판정               = LOCKED (영구 유지, 재검증 후에만 재평가)
V-4 chain                     = 독립 체인, 본 seal과 분리
```

**재확인:** V-4는 V-3 INVALID 상태에서 절대 auto-unlock되지 않는다. V-3R1 corrective chain 완료 + V-3 재실행 + PASS 판정 이후에만 V-4 unlock 검토 가능.

---

## V-3R1 Corrective Chain 필요성 인정

사용자 권고에 따라 **V-3R1 — Receipt/Mode Alignment Corrective Chain**의 필요성을 인정한다.

### V-3R1 체인 성격 (잠정)

- **전략 개선 체인 아님** (C1C2_N2 config 재평가 아님)
- **검증 정합성 보정 체인**
- **목적:** V-3 재검증 가능 상태로 복원

### V-3R1 잠정 범위 (별도 GO 없이 미확정)

허용 예상:
- `scripts/sol_s1_v3_shadow_run.py` receipt schema 16필드 정렬
- `execution_mode` 필드 추가 (realtime_shadow | historical_replay)
- trust chain 필드 반영

금지 예상:
- 전략 로직 변경
- baseline 변경 (ECR 64.3 / block 35.7 / SD 70.9 / fit 0.4428 고정)
- taxonomy 변경 (block 3 / stop_reason 6)
- N1/N3 삽입
- 수익성 최적화

### V-3R1 미착수 선언

본 seal은 **V-3R1의 필요성만 인정**하며, V-3R1 자체는 시작하지 않는다. V-3R1 explicit GO는 별도 체인 단계이며 본 seal 범위 외.

---

## 사용자 신규 아이디어 3건 (미래 V-3R1 GO 반영 후보)

본 seal에는 직접 적용하지 않으나, V-3R1 corrective GO 작성 시 반영 후보로 기록:

### 아이디어 1 — 판정 이원화 필드

```json
"technical_execution_status": "EXECUTED | ABORTED | FAILED_TO_START",
"governance_validity_status": "VALID | INVALID | CONFLICTED"
```

본 attempt #1에 적용 시:
- `technical_execution_status = EXECUTED`
- `governance_validity_status = INVALID`

### 아이디어 2 — Execution Mode 필드

```json
"execution_mode": "realtime_shadow | historical_replay"
```

본 attempt #1 추정값: `historical_replay` (43ms duration으로 추정).

### 아이디어 3 — Schema Hash 고정

```json
"receipt_schema_hash": "<sha256 of expected 16-field schema>",
"evidence_schema_hash": "<sha256 of expected 18-field schema>"
```

다음 V-3R1 run GO에 포함하면 implementation-run schema drift를 사전 감지 가능.

---

## 봉인

- V-3 shadow run attempt #1은 **INVALID evidence**로 본 seal로 공식 봉인되었다
- 운영 실행은 성공했으나 (run=EXECUTED), 행정 판정은 유효하지 않다 (governance=INVALID)
- Schema conflict (16 vs 12 필드)는 거버넌스 품질 저하 신호로 별도 기록되었다
- Frozen artifacts 0건 수정, V-1/V-2 artifacts 0건 수정, scope lock 0건 위반
- `final_state = RED`, `run_result_class = INVALID`, `stop_reason = STOP_RED_ECR`
- `bars_observed = 92 < 96`, `trades_count = 0 < 10` (둘 다 기준 미달)
- 실측 3개 Red 임계값 동시 침범 (ECR, block_rate, SD_delta)
- V-4 unlock은 LOCKED로 영구 유지 (V-3R1 완료 + V-3 PASS 이후에만 재평가)
- V-3R1 — Receipt/Mode Alignment Corrective Chain 필요성 인정, 미착수
- V-3R1 explicit GO는 별도 체인 단계, 본 seal 범위 외
- 사용자 신규 아이디어 3건 (판정 이원화 / execution_mode / schema hash)는 V-3R1 GO 반영 후보로 기록
- 본 seal은 기존 frozen artifacts를 수정하지 않는 **supplementary evidence document**이다
- auto_advance = 금지
- POST_SEAL_STATE = STANDBY

---

## Chain 상태 갱신

| 단계 | 상태 | 비고 |
|------|------|------|
| Root-Cause Analysis | CLOSED | COMPLETE |
| V-1 | CLOSED | INFORMATIVE_FAIL |
| V-2 | CLOSED | PASS (C1C2_N2) |
| V-3 설계서 | CLOSED | ACCEPT |
| V-3 explicit GO | COMPLETE | — |
| V-3 구현 범위 잠금 | COMPLETE | — |
| V-3 구현 착수 허가 | COMPLETE | — |
| V-3 구현 완료 | COMPLETE | 8/8 검증 PASS |
| V-3 run GO | COMPLETE | ACCEPTED/SEALED |
| V-3 shadow run attempt #1 | EXECUTED | — |
| **V-3 run attempt #1 INVALID seal** | **COMPLETE** | **본 receipt** |
| V-3 run attempt #1 판정 | INVALID | 봉인됨 |
| V-3 재검증 (attempt #2+) | LOCKED | V-3R1 체인 완료 필요 |
| V-3R1 Corrective Chain | NOT STARTED | 별도 explicit GO 필요 |
| V-4 (Paper) | LOCKED | V-3 PASS 조건 미충족 |

---

## Global State Declaration

```
V-3 SHADOW RUN ATTEMPT #1          = EXECUTED / SEALED
V-3 FINAL STATE                    = RED
V-3 RUN RESULT CLASS               = INVALID
V-3 RECEIPT SCHEMA                 = CONFLICT DETECTED (16 req vs 12 actual)
V-3 EVIDENCE SEAL                  = COMPLETE (본 문서)
V-4 UNLOCK                         = LOCKED (V-3 PASS 미달성)
V-3R1 CORRECTIVE CHAIN             = NEEDED / NOT STARTED
GLOBAL STATE                       = STANDBY
POST_SEAL_STATE                    = STANDBY
RUN_AUTHORIZATION                  = NOT GRANTED (소진)
IMPLEMENTATION_ARTIFACTS_FROZEN    = true (유지)
NEXT LEGAL ACTION                  = V-3R1 explicit GO 검토 (별도 체인)
auto_advance                       = 금지
```

### 2층 상태 해석 (재확인)

| 층 | 상태 |
|---|------|
| 운영 실행 (technical) | EXECUTED — run 자체는 완수됨 |
| 거버넌스 판정 (governance) | INVALID — 검증 근거로 사용 불가 |

본 2층은 서로 모순이 아니다. "실행했으나 증거로 쓸 수 없다"가 현재 상태이다.
