# CR-048 RI-2B 범위 심사 패키지

**Stage**: RI-2B (Bounded Write-Path)
**Status**: SCOPE REVIEW 제출 (v3 — 최종 점검 3건 보강)
**Date**: 2026-04-04
**Authority**: A
**선행 조건**: RI-2A-2a SEALED (v2.2, 5354/5354 PASS)

---

## 1. 범위 심사 목적

RI-2A 계열(관찰 계층)이 봉인된 상태에서, **운영 write를 초협소·수동·bounded 범위로 최초 개방**하기 위한 범위 심사.

A 지시에 따라 RI-2B를 2단 분리합니다:

| 단계 | 명칭 | 성격 | 상태 |
|------|------|------|------|
| **RI-2B-1** | Receipt-only Shadow Write | write 의도만 기록, 실제 상태 변경 없음 | **본 심사 대상** |
| **RI-2B-2** | Real Bounded Write | shadow receipt 검증 후 실제 상태 변경 | **DEFERRED** |

**본 심사는 RI-2B-1만 다룹니다. RI-2B-2는 RI-2B-1 봉인 후 별도 심사.**

---

## 2. RI-2B-1 정의: Receipt-only Shadow Write

### 핵심 개념

> 실제 운영 상태를 변경하지 않고, **"만약 write 했다면 무엇이 바뀌었을지"를 receipt로 기록**하는 단계.

즉, shadow pipeline 관측 결과를 기반으로:
- **어떤 테이블**의 **어떤 필드**가 **어떤 값으로** 바뀌었을지 계산
- 그 **의도(intent)를 receipt 테이블에 INSERT**
- **실제 business table은 변경하지 않음**

### Write Target

| 항목 | 값 |
|------|-----|
| 대상 테이블 | `shadow_write_receipt` (**신규**, append-only) |
| Business table write | **0** |
| 성격 | Write intent 기록 (dry-run receipt) |

### shadow_write_receipt 스키마 (안 v2)

| 필드 | 타입 | nullable | 설명 |
|------|------|:--------:|------|
| id | Integer (PK, auto) | N | |
| receipt_id | String(64) | N | Row identity (UUID) |
| dedupe_key | String(128) | N | **Semantic idempotency key** (아래 정의 참조) |
| symbol | String(32) | N | 대상 종목 |
| target_table | String(48) | N | 의도 대상 테이블명 (예: "symbols") |
| target_field | String(48) | N | 의도 대상 필드명 (예: "qualification_status") |
| current_value | String(128) | Y | 현재 값 (변경 전) |
| intended_value | String(128) | N | 의도 값 (변경 후) |
| would_change_summary | String(256) | N | 사람 가독 요약 (예: "symbols.qualification_status: unchecked → pass") |
| transition_reason | String(128) | N | 사유 코드 |
| block_reason_code | String(64) | Y | BLOCKED 시 구조화된 사유 코드 |
| shadow_observation_id | Integer | Y | 연결된 shadow_observation_log.id (FK 아님, 참조값만) |
| input_fingerprint | String(64) | N | 재현성 키 |
| dry_run | Boolean | N | **항상 True** (RI-2B-1) |
| executed | Boolean | N | **항상 False** (RI-2B-1) |
| business_write_count | Integer | N | **항상 0** (RI-2B-1) |
| verdict | String(32) | N | WOULD_WRITE / WOULD_SKIP / BLOCKED |
| created_at | DateTime(tz) | N (server_default) | |

**FK: 0. UNIQUE: 2 (receipt_id, dedupe_key). CASCADE: 0.**

### Semantic Dedupe Key 정의

`dedupe_key`는 아래 **7개 필드**를 정해진 순서로 연결한 SHA-256 해시 (hex, 64자):

```
dedupe_key = sha256(symbol | target_table | target_field | current_value | intended_value | input_fingerprint | dry_run)
```

#### Dedupe Key 입력요소 표 (고정)

| # | 필드 | 타입 | 예시 | 필수 |
|---|------|------|------|:----:|
| 1 | symbol | String | `"SOL/USDT"` | Y |
| 2 | target_table | String | `"symbols"` | Y |
| 3 | target_field | String | `"qualification_status"` | Y |
| 4 | current_value | String | `"unchecked"` | Y (None → `"NULL"`) |
| 5 | intended_value | String | `"pass"` | Y |
| 6 | input_fingerprint | String | `"a3f8..."` | Y |
| 7 | dry_run | String | `"true"` | Y (RI-2B-1에서 항상 `"true"`) |

**구분자**: `|` (pipe). **인코딩**: UTF-8. **해시**: SHA-256 hex lowercase.

> 입력요소 추가/제거는 스키마 버전 변경으로 간주하며, 별도 A 심사 필수.

| 속성 | 설명 |
|------|------|
| 용도 | **동일 의미 요청의 중복 INSERT 차단** |
| UNIQUE 제약 | dedupe_key에 UNIQUE 인덱스 |
| 중복 호출 시 | IntegrityError catch → 기존 receipt 반환 |
| receipt_id와의 차이 | receipt_id = row identity, dedupe_key = semantic identity |

### Block Reason Code 표준화

| 코드 | 의미 |
|------|------|
| `PRECONDITION_FAILED` | 전이 사전조건 미충족 (예: 현재 상태가 unchecked 아님) |
| `OUT_OF_SCOPE` | 허용 target_table/field 밖의 요청 |
| `ALREADY_MATCHED` | intended_value == current_value (변경 불필요) |
| `FORBIDDEN_TARGET` | 금지 의도 대상 (symbols.status, strategies.status 등) |
| `INPUT_INVALID` | 필수 입력 누락 또는 형식 오류 |
| `FROZEN_VIOLATION` | FROZEN 파일/계층 접촉 감지 |

### Verdict 정의

| Verdict | 의미 | 실제 write |
|---------|------|:----------:|
| `WOULD_WRITE` | shadow 결과가 write 조건 충족 | **없음** (dry-run) |
| `WOULD_SKIP` | shadow 결과가 write 조건 미충족 | **없음** |
| `BLOCKED` | 금지선 위반 감지 (FROZEN/RED/forbidden) | **없음** |

**세 가지 모두 실제 business table write는 0.**

### Verdict 결정표 (Deterministic)

| # | 조건 | verdict | block_reason_code |
|---|------|---------|-------------------|
| 1 | target_table/field가 허용 목록 밖 | `BLOCKED` | `OUT_OF_SCOPE` |
| 2 | target_table/field가 금지 목록 | `BLOCKED` | `FORBIDDEN_TARGET` |
| 3 | shadow_result 또는 readthrough_result가 None | `BLOCKED` | `INPUT_INVALID` |
| 4 | current_value == intended_value (이미 목표 상태) | `WOULD_SKIP` | — |
| 5 | current_value가 전이 사전조건 미충족 (예: unchecked 아닌 상태) | `BLOCKED` | `PRECONDITION_FAILED` |
| 6 | shadow qualification verdict가 전이 조건 미충족 | `WOULD_SKIP` | — |
| 7 | 위 모든 검사 통과 + dry_run=True | `WOULD_WRITE` | — |

**평가 순서: 1→2→3→4→5→6→7 (금지선 차단 먼저 → 비즈니스 조건 → 최종 판정)**

> **금지선 우선 차단 원칙**: Step 1~3은 금지선/입력검증으로 **반드시 선행 차단**된다.
> Step 4~6은 비즈니스 조건 평가. Step 7은 모든 검사를 통과한 경우에만 도달.
> 이 결정표는 구현 시 정확히 이 순서로 평가되어야 하며, 임의 판정 금지.
> Step 순서 변경은 설계 변경으로 간주하며, 별도 A 심사 필수.

---

## 3. Write Target 분석: 의도 대상 (RI-2B-2 선행 검증)

RI-2B-1에서 "의도"로 기록할 수 있는 대상은 아래로 제한합니다:

| target_table | target_field | 허용 전이 | 비고 |
|-------------|-------------|-----------|------|
| `symbols` | `qualification_status` | `unchecked → pass`, `unchecked → fail` | shadow qualification 결과 기반 |

**RI-2B-1에서 허용하는 의도 대상은 1개 테이블 × 1개 필드 × 2개 전이만.**

### 금지 의도 대상

| target_table | target_field | 금지 사유 |
|-------------|-------------|-----------|
| `symbols` | `status` (CORE/WATCH/EXCLUDED) | 3상태 전이는 screening pipeline 전용 |
| `symbols` | `promotion_eligibility_status` | 승격 경로 변경은 RI-2B-2+ |
| `symbols` | `paper_evaluation_status` | paper 경로는 CR-046 frozen |
| `strategies` | `status` | 전략 승격은 Phase 4+ |
| `screening_results` | * | screening pipeline 전용 |
| `qualification_results` | * | qualification pipeline 전용 |
| `promotion_events` | * | promotion gate 전용 |

---

## 4. 10대 필수 원칙 준수표

| # | 원칙 | RI-2B-1 준수 방식 |
|---|------|-------------------|
| 1 | Manual trigger only | pytest / script만. beat/schedule/periodic 금지 |
| 2 | Beat/schedule/periodic/background loop 금지 | Celery task 등록 없음, beat_schedule 변경 없음 |
| 3 | Purge/retention 금지 | receipt는 append-only, 삭제/정리 없음 |
| 4 | Single bounded target only | shadow_write_receipt 1개 테이블만 INSERT |
| 5 | Whitelist state transition only | qualification_status의 unchecked→pass/fail만 |
| 6 | Idempotency key + durable receipt 필수 | receipt_id (UUID) UNIQUE 제약 |
| 7 | Rollback contract 필수 | dry_run=True 고정 → 실제 변경 없음 → rollback 불필요 |
| 8 | Exchange/API/후속 자동 side-effect 금지 | 외부 호출 0, 후속 chain 0 |
| 9 | FROZEN/RED 불가침 | pipeline_shadow_runner, shadow_readthrough, exchanges/* 무접촉 |
| 10 | 관찰 계층 봉인 파손 금지 | shadow_observation_log/service 무수정 |

---

## 5. 파일 목록 (예상)

| 파일 | 작업 | 등급 |
|------|------|:----:|
| `app/models/shadow_write_receipt.py` | **신규** — ShadowWriteReceipt ORM | L3 |
| `app/services/shadow_write_service.py` | **신규** — evaluate_shadow_write() (dry-run only) | L3 |
| `alembic/versions/022_shadow_write_receipt.py` | **신규** — CREATE TABLE | L3 |
| `tests/test_shadow_write_receipt.py` | **신규** — model + service + idempotency + forbidden + rollback tests | L1 |
| `app/models/__init__.py` | **수정** — import 추가 | L3 |

**총 5개 파일** (신규 4, 수정 1).

### 금지 파일 (무접촉 필수)

| 파일 | 사유 |
|------|------|
| `app/services/pipeline_shadow_runner.py` | FROZEN (RI-1 SEALED) |
| `app/services/shadow_readthrough.py` | FROZEN (RI-2A-1 SEALED) |
| `app/services/shadow_observation_service.py` | FROZEN (RI-2A-2a SEALED) |
| `app/models/shadow_observation.py` | FROZEN (RI-2A-2a SEALED) |
| `exchanges/*` | RED |
| `workers/tasks/order_tasks.py` | RED |
| `workers/tasks/market_tasks.py` | RED |
| `app/services/multi_symbol_runner.py` | RED |
| `app/services/asset_service.py` | 2B-1에서 변경 금지 (read 참조만 가능) |
| `app/models/asset.py` | 2B-1에서 변경 금지 |
| `workers/tasks/*` | task 등록 금지 |

---

## 6. Idempotency 계약 (2계층)

### Layer 1 — Row Identity (receipt_id)

| 항목 | 규칙 |
|------|------|
| receipt_id | 호출자가 생성하는 UUID, UNIQUE 제약 |
| 용도 | 개별 row 식별 |

### Layer 2 — Semantic Identity (dedupe_key)

| 항목 | 규칙 |
|------|------|
| dedupe_key | 입력 필드 조합의 SHA-256 해시, UNIQUE 제약 |
| 용도 | **동일 의미 요청의 중복 INSERT 차단** |
| 중복 호출 시 | dedupe_key UNIQUE 위반 → IntegrityError catch → 기존 receipt 반환 |
| 재실행 안전성 | 같은 의미 요청을 N번 호출해도 1개 row만 존재 |

**receipt_id ≠ dedupe_key**: receipt_id는 row를 식별하고, dedupe_key는 의도를 식별합니다.

---

## 7. Rollback 계약

| 항목 | 설명 |
|------|------|
| RI-2B-1 rollback 필요성 | **없음** — dry_run=True 고정, business table 변경 0 |
| Receipt 삭제 | **금지** — append-only |
| 잘못된 receipt 처리 | verdict를 BLOCKED로 새 receipt INSERT (원본 수정 금지) |

---

## 8. INSERT Failure Isolation (RI-2A-2a 패턴 계승)

| 실패 유형 | 운영 영향 | 처리 |
|-----------|:---------:|------|
| db.flush() 실패 | 0 | return None, 예외 미전파 |
| db.add() 실패 | 0 | return None, 예외 미전파 |
| UNIQUE 위반 (중복) | 0 | 기존 receipt 반환, 예외 미전파 |
| shadow_observation 없음 | 0 | return None, add 미호출 |

---

## 9. RI-2B-1 ↔ RI-2B-2 경계 (방화벽)

> **RI-2B-1은 shadow evidence 단계이며, symbols 포함 모든 business table 상태 변경은 금지된다.**
>
> **RI-2B-1 승인 범위는 shadow evidence append-only에 한정되며, 이를 근거로 RI-2B-2 real bounded write에 대한 승인 또는 착수 권한이 발생하지 않는다.**

| 항목 | RI-2B-1 (본 심사) | RI-2B-2 (DEFERRED) |
|------|:-----------------:|:------------------:|
| shadow_write_receipt INSERT | **허용** | 허용 |
| Business table write | **금지** | 허용 (bounded) |
| dry_run 플래그 | **항상 True** | True/False 선택 |
| 실제 상태 전이 실행 | **금지** | 허용 (whitelist만) |
| Rollback 필요 | **없음** | **필수** |
| 진입 조건 | RI-2A-2a SEALED | **RI-2B-1 SEALED** |

---

## 10. 테스트 수락 기준 (예상)

| # | 테스트 항목 | 검증 대상 |
|---|-----------|-----------|
| 1 | Model: tablename, fields, nullable, UNIQUE(receipt_id), UNIQUE(dedupe_key) | 스키마 계약 |
| 2 | Insert: WOULD_WRITE verdict 기록 + would_change_summary 검증 | 정상 경로 |
| 3 | Insert: WOULD_SKIP verdict 기록 (이미 목표 상태 / 전이 조건 미충족) | 조건 미충족 경로 |
| 4 | Insert: BLOCKED verdict 기록 + block_reason_code 검증 | 금지선 위반 감지 |
| 5 | Verdict 결정표 순서 검증 (7단계 순서대로 평가) | 결정적 판정 |
| 6 | Semantic dedupe: 동일 의미 요청 2회 → 1 row (dedupe_key UNIQUE) | 의미 중복 방지 |
| 7 | dry_run=True 고정 + executed=False 고정 + business_write_count=0 고정 | 비실행 증명 |
| 8 | Business table write 0 (symbols/strategies 무변경) | 방화벽 검증 |
| 9 | Forbidden target 차단 (OUT_OF_SCOPE, FORBIDDEN_TARGET) | 금지 의도 대상 거부 |
| 10 | Append-only: no update/delete methods on service | RI-2A-2a 패턴 계승 |
| 11 | Failure isolation: flush/add 실패 → None, 예외 미전파 | 격리 검증 |
| 12 | FROZEN/RED 무접촉 | 봉인 파손 없음 |
| 13 | 전체 회귀 PASS | baseline 유지 |

---

## 11. 위험 분석

| 위험 | 등급 | 완화 |
|------|:----:|------|
| Receipt가 사실상 business decision으로 변질 | **높음** | dry_run=True 고정, verdict는 관찰 지표로만 사용 금지선 |
| 의도 대상 확대 (target_table/field 무제한) | **중간** | whitelist 1개 테이블 × 1개 필드로 고정, 확장 시 별도 심사 |
| RI-2B-2 조기 진입 | **중간** | RI-2B-1 봉인 전 RI-2B-2 착수 금지 명시 |
| shadow_observation → receipt 자동 연쇄 | **중간** | manual trigger only, Celery/beat 금지 |

---

## 12. 현재 상태 / 다음 단계

```
Guarded Release ACTIVE · Gate LOCKED
Stage 1~4B L3: SEALED
RI-1 L3: SEALED
RI-2A-1 L3: SEALED
RI-2A-2a L3: SEALED
RI-2B-1: SCOPE REVIEW 제출 (본 문서)
RI-2B-2: DEFERRED
RI-2A-2b: DEFERRED
Baseline: v2.2 (5354/5354 PASS)
```

### 판정 기준 (A 원문)

> "좁고, 수동이며, 되돌릴 수 있고, 증빙 가능하며, 자동 반복되지 않는다"를 입증하지 못하면 GO 금지.

| 기준 | RI-2B-1 대응 |
|------|-------------|
| 좁다 | 1 테이블 × 1 필드 × 2 전이 (의도만) |
| 수동이다 | manual trigger only, beat/schedule 0 |
| 되돌릴 수 있다 | dry_run=True, business write 0 → rollback 불필요 |
| 증빙 가능하다 | receipt_id + idempotency + append-only |
| 자동 반복되지 않는다 | Celery task 0, background loop 0 |

---

## 13. 승인 범위 한정 선언

> **본 문서의 승인 범위는 RI-2B-1 shadow evidence 설계 심사에 한정되며, 실행 권한·운영 write 권한·후속 단계 권한을 생성하지 않는다.**

---

## A 판정 요청

RI-2B 범위 심사를 RI-2B-1/2B-2 분리 구조로 제출합니다.

- **ACCEPT** → RI-2B-1 설계/계약 패키지 진행
- **CONDITIONAL** → 지적 사항 반영 후 재제출
- **REJECT** → 방향 재검토
