# CR-048 RI-2A-2 범위 심사 패키지

**문서 ID:** RI2A2-SCOPE-001
**작성일:** 2026-04-03
**전제 기준선:** v2.1 (5330/5330 PASS, RI-2A-1 SEALED)
**전제 문서:**
- RI2A-SCOPE-001 (RI-2A 범위 심사 — CONDITIONAL ACCEPT, RI-2A-1/2A-2 분리)
- RI2A1-SEALED (RI-2A-1 봉인 증빙 — read-through comparison SEALED)
**Authority:** A

---

## 1. RI-2A-2 목표

### 무엇을 관측 자산으로 남기려는지

RI-2A-1은 read-through comparison을 **실행하고 결과를 반환**하지만, 그 결과는 **메모리에서 소멸**합니다.
RI-2A-2의 목표는 이 비교 결과를 **관측 기록으로 축적**하여:

- verdict 일치율 추이를 시계열로 측정
- INSUFFICIENT_OPERATIONAL 비율 감소 추이를 관찰
- fail reason 일치율 기준선을 실측

할 수 있도록 하는 것입니다.

### 왜 지금 열어야 하는지

| 이유 | 상세 |
|------|------|
| RI-2B 진입 조건 | 72H 연속 실행 + verdict ≥95% + reason ≥90% — 이 수치를 측정하려면 관측 기록이 필요 |
| RI-1A는 curated batch | 실시간 데이터에서의 verdict/reason 일치율은 아직 **미측정** |
| 봉인 근거 축적 | 각 단계 봉인은 증빙 기반 — 시계열 관측 기록 없이는 증빙 불가 |

### 한 문장 목표

> **RI-2A-2 = "RI-2A-1 비교 결과를 별도 관측 테이블에 append-only로 기록하되, 기존 테이블과 운영 경로에 영향 0."**

---

## 2. 2단 분리안

### RI-2A-2a: Observation Append-only 적재

| 속성 | 값 |
|------|-----|
| 범위 | shadow_observation_log 신규 테이블 INSERT only |
| DB write 성격 | shadow observation write (append-only) |
| 기존 테이블 접촉 | 0 (FK 없음, 독립 테이블) |
| 트리거 | **수동 호출** 또는 **단건 스크립트** (beat 아님) |
| 실패 시 운영 영향 | 0 (observation 실패가 pipeline/실행 경로를 차단하지 않음) |
| Rollback | 테이블 DROP + 파일 삭제 (TRIVIAL) |

### RI-2A-2b: Beat / 스케줄 운영

| 속성 | 값 |
|------|-----|
| 범위 | Celery beat shadow_observation_task 5분 주기 등록 |
| DB write 성격 | RI-2A-2a와 동일 (shadow observation write) |
| 기존 테이블 접촉 | 0 |
| 트리거 | **Celery beat 자동 주기** (beat_schedule 변경) |
| 실패 시 운영 영향 | 낮음 — 다만 beat_schedule 변경은 L4 인접 |
| Rollback | beat_schedule에서 task 제거 (TRIVIAL) |

### 왜 둘을 분리해야 하는지

| 관점 | RI-2A-2a (적재) | RI-2A-2b (beat) |
|------|:---------------:|:---------------:|
| side-effect 범위 | INSERT 1개 테이블 | INSERT + 운영 스케줄 변경 |
| 운영 주기 개입 | **없음** (수동 트리거) | **있음** (5분 자동 실행) |
| beat_schedule 변경 | **없음** | **있음** (L4 인접) |
| 기존 worker 영향 | **없음** | worker에 새 task 추가 |
| 실패 전파 범위 | 호출자 한정 | beat → worker → 전체 task queue |
| 심사 독립성 | 테이블/모델/서비스만 | celery config + task + 모니터링 |

**핵심:** "데이터를 쌓을 수 있는가"와 "자동으로 돌릴 수 있는가"는 다른 문제입니다.
2a가 봉인된 후에야 2b의 필요성을 정확히 판단할 수 있습니다.

---

## 3. 허용 접촉면 / 금지 접촉면

### 3.1 RI-2A-2a 허용 접촉면

| 대상 | 접촉 유형 | 허용 |
|------|-----------|:----:|
| `shadow_observation_log` (신규 테이블) | **INSERT only** | **O** |
| `screening_results` | SELECT (RI-2A-1 경유) | **O** |
| `qualification_results` | SELECT (RI-2A-1 경유) | **O** |

### 3.2 신규 테이블 허용 여부

| 항목 | 판단 |
|------|------|
| 신규 테이블 | **shadow_observation_log 1개 허용 요청** |
| FK 관계 | **없음** (기존 테이블과 완전 독립) |
| 마이그레이션 | **신규 CREATE TABLE 1건** |
| 기존 테이블 스키마 변경 | **0** |

### 3.3 기존 테이블 접촉 금지

| 테이블 | RI-2A-2a 접촉 | RI-2A-2b 접촉 |
|--------|:-------------:|:-------------:|
| symbols | **금지** | **금지** |
| screening_results | SELECT만 (RI-2A-1) | SELECT만 |
| qualification_results | SELECT만 (RI-2A-1) | SELECT만 |
| promotion_states | **금지** | **금지** |
| paper_sessions | **금지** | **금지** |
| signals | **금지** | **금지** |
| orders | **금지** | **금지** |

### 3.4 FROZEN / RED 유지표

**FROZEN 함수:**

| FROZEN 함수 | RI-2A-2a | RI-2A-2b |
|-------------|:--------:|:--------:|
| `screen_and_update()` | **미접촉** | **미접촉** |
| `qualify_and_record()` | **미접촉** | **미접촉** |
| `run_screening_qualification_pipeline()` | 호출 (RI-1 경유, 수정 0줄) | 호출 |
| `run_shadow_pipeline()` | 호출 (RI-1 SEALED, 수정 0줄) | 호출 |
| `compare_shadow_to_existing()` | 호출 (RI-2A-1 SEALED, 수정 0줄) | 호출 |

**RED 파일:**

| RED 파일 | RI-2A-2a | RI-2A-2b |
|----------|:--------:|:--------:|
| `exchanges/*` | **금지** | **금지** |
| `workers/tasks/order_tasks.py` | **금지** | **금지** |
| `workers/tasks/market_tasks.py` | **금지** | **금지** |
| `app/services/multi_symbol_runner.py` | **금지** | **금지** |
| `app/services/strategy_router.py` | **금지** | **금지** |
| `app/services/runtime_strategy_loader.py` | **금지** | **금지** |

---

## 4. DB Write 성격 정의

### 4.1 Business write vs Shadow observation write

| 구분 | Business Write | Shadow Observation Write |
|------|:--------------:|:-----------------------:|
| 대상 | screening_results, qualification_results, symbols | **shadow_observation_log** |
| 운영 판단 영향 | 있음 (Symbol.status 전이 근거) | **없음** (관측 기록일 뿐) |
| 실행 경로 참조 | 있음 (RuntimeStrategyLoader 등) | **없음** |
| 실패 시 운영 영향 | 있음 (데이터 불일치) | **없음** (observation 미기록일 뿐) |
| 분류 | **RI-2B scope** | **RI-2A-2 scope** |

**RI-2A-2의 write는 shadow observation write입니다. Business write가 아닙니다.**

### 4.2 Append-only 보장 방식

| 보장 수단 | 상세 |
|-----------|------|
| 모델 수준 | `ShadowObservationLog`에 UPDATE/DELETE 메서드 미구현 |
| 서비스 수준 | observation service에 `record_observation()` (INSERT만) 단일 메서드 |
| 테스트 수준 | mock DB에서 `db.add()` 이외 write 메서드 호출 0회 검증 |
| 테스트 수준 | `flush`, `commit` 외 `merge`, `delete`, `execute(UPDATE)` 호출 0회 검증 |
| 코드 리뷰 | grep: UPDATE/DELETE/merge/remove 등 write 패턴 0건 검증 |

### 4.3 신규 테이블 스키마 (안)

```python
class ShadowObservationLog(Base):
    __tablename__ = "shadow_observation_log"

    id: Mapped[int]                           # PK, auto-increment
    symbol: Mapped[str]                       # 관찰 대상 symbol
    asset_class: Mapped[str]                  # CRYPTO / US_STOCK / KR_STOCK
    shadow_verdict: Mapped[str]               # qualified / screen_failed / qualify_failed / data_rejected
    comparison_verdict: Mapped[str]           # match / verdict_mismatch / reason_mismatch / insufficient_*
    shadow_screening_passed: Mapped[bool | None]
    shadow_qualification_passed: Mapped[bool | None]
    existing_screening_passed: Mapped[bool | None]
    existing_qualification_passed: Mapped[bool | None]
    reason_comparison_json: Mapped[str | None]  # ReasonComparisonDetail JSON
    readthrough_failure_code: Mapped[str | None]  # ReadthroughFailureCode
    input_fingerprint: Mapped[str]            # 입력 해시 (재현성)
    shadow_timestamp: Mapped[datetime]        # shadow 실행 시각 (UTC)
    created_at: Mapped[datetime]              # 기록 시각 (UTC)
```

**테이블 특성:**
- 기존 테이블과 **FK 없음** (완전 독립)
- **INSERT만 허용** (UPDATE/DELETE 금지 — append-only)
- **INDEX**: (symbol, created_at), (comparison_verdict, created_at) — 집계 쿼리용
- symbols, screening_results, qualification_results에 **접촉 0**

---

## 5. 실패 시 영향 분석

### Observation Write Risk Matrix

| 실패 유형 | 발생 조건 | 운영 영향 | 처리 방식 |
|-----------|-----------|:---------:|-----------|
| **INSERT 실패** | DB 연결 끊김, 디스크 풀, constraint 위반 | **0** | stderr 로그 기록, 호출자에 에러 전파 안 함 |
| **Duplicate 기록** | 동일 symbol + 동일 timestamp 재실행 | **0** | 허용 (append-only, UNIQUE 제약 없음). 집계 시 dedup 가능 |
| **Stale 축적** | 오래된 observation 대량 축적 | **0** | retention policy: 90일 초과 시 batch DELETE (수동/예약) |
| **Schema mismatch** | 마이그레이션 누락/충돌 | **0** | 테이블 독립이므로 기존 테이블 영향 없음 |
| **Transaction 충돌** | observation session이 다른 session과 충돌 | **0** | 별도 session 사용, 기존 read-through session과 분리 |

### 핵심 보장

> **observation INSERT 실패는 어떤 경우에도 pipeline 실행, read-through 비교, 기존 데이터에 영향을 주지 않는다.**

실패 처리 원칙:
1. observation INSERT는 **best-effort** (실패 시 무시)
2. observation 실패가 shadow pipeline을 **차단하지 않음**
3. observation 실패가 RI-2A-1 read-through를 **차단하지 않음**
4. observation 실패 로그는 **stderr + structlog** (별도 추적 가능)

### Retention / Purge

| 정책 | 상세 |
|------|------|
| 기본 보존 | **90일** |
| Purge 방식 | batch DELETE (created_at < now - 90d), 수동 또는 예약 |
| Purge 시점 | RI-2A-2b (beat) 범위 또는 수동 — RI-2A-2a에서는 purge 미구현 |
| Purge 영향 | 기존 테이블 영향 0 (독립 테이블) |

### Rollback 절차

| 시나리오 | 절차 | 비용 |
|----------|------|:----:|
| RI-2A-2a 전체 철회 | 1. 서비스/모델 파일 삭제 2. Alembic downgrade (DROP TABLE) 3. 테스트 삭제 | **TRIVIAL** |
| 관측 기록만 삭제 | TRUNCATE shadow_observation_log | **TRIVIAL** |
| 스키마 수정 필요 | 신규 마이그레이션 (기존 테이블 영향 0) | **TRIVIAL** |

---

## 6. Beat 도입 여부

### 이번 심사 대상인가?

**아닙니다.** Beat은 RI-2A-2b 범위입니다.

### RI-2A-2a에서 beat을 미루는 이유

| # | 이유 |
|---|------|
| 1 | beat_schedule 변경은 **L4 인접** — 기존 worker/beat에 영향 |
| 2 | beat 등록 전에 먼저 **"기록이 가능한가"**를 검증해야 함 |
| 3 | beat 실패 전파 범위가 넓음 (worker queue 영향) |
| 4 | RI-2A-2a가 봉인되면, 2b는 단순히 "호출 주기를 자동화"하는 문제로 축소됨 |
| 5 | A 지시: "2a 봉인 후 필요성 재입증 방식이 가장 안전" |

### RI-2A-2a의 실행 방식

| 방식 | 상세 |
|------|------|
| 수동 호출 | `await record_shadow_observation(db, shadow_result, readthrough_result)` |
| 스크립트 | `scripts/ri2a2_observation_runner.py` — 수동 batch 실행 |
| 테스트 | pytest 내에서 검증 |

beat 없이도 관측 기록의 **정합성, append-only 보장, 실패 무영향**을 완전히 검증할 수 있습니다.

---

## 7. 테스트 / 회귀 계획

### 예상 신규 테스트

| 테스트 클래스 | 예상 수 | 검증 대상 |
|-------------|:-------:|-----------|
| TestShadowObservationModel | ~4 | 모델 필드, frozen, import safety |
| TestRecordObservation | ~5 | INSERT 정상, 필드 매핑, timestamp UTC |
| TestAppendOnlyGuarantee | ~4 | UPDATE 0, DELETE 0, merge 0, add만 허용 |
| TestInsertFailureIsolation | ~3 | INSERT 실패 시 pipeline/readthrough 무영향 |
| TestDuplicateHandling | ~2 | 동일 symbol+timestamp 재기록 허용 |
| TestObservationFromShadowResult | ~3 | ShadowRunResult → observation 변환 정확성 |
| TestObservationFromReadthrough | ~3 | ReadthroughComparisonResult → observation 변환 |
| **총 예상** | **~24** | |

### 기존 기준선 보호 계획

| 보호 항목 | 방법 |
|-----------|------|
| 기존 5330 tests | 전체 회귀 PASS 필수 |
| FROZEN 함수 수정 0줄 | grep 검증 |
| RED 파일 접촉 0건 | git status 검증 |
| Pure Zone 10 files | purity guard 117 tests 유지 |
| 기존 테이블 스키마 | 마이그레이션은 신규 CREATE TABLE만 |
| RI-2A-1 read-through | shadow_readthrough.py 수정 0줄 |
| pipeline_shadow_runner.py | 수정 0줄 (RI-2A-1 SEALED) |

---

## 8. RI-2A-2a / RI-2A-2b 경계 요약

| 기준 | RI-2A-2a (본 심사) | RI-2A-2b (후속) |
|------|:------------------:|:---------------:|
| 신규 테이블 | shadow_observation_log | 없음 (2a 테이블 재사용) |
| 마이그레이션 | CREATE TABLE 1건 | 없음 |
| DB write | INSERT only (append-only) | INSERT only (동일) |
| 트리거 | **수동/스크립트** | **Celery beat 자동** |
| beat_schedule | **변경 없음** | 변경 (shadow task 추가) |
| worker 영향 | **없음** | 새 task 등록 |
| 72H 연속 실행 | **RI-2A-2b 범위** | **여기서 달성** |
| 봉인 조건 | INSERT 정상 + append-only + 회귀 PASS | 72H + verdict ≥95% + reason ≥90% |

---

## 9. RI-2A-2a 예상 파일 목록

### 신규

| 파일 | 유형 | 설명 |
|------|------|------|
| `app/models/shadow_observation.py` | 모델 | ShadowObservationLog ORM (append-only) |
| `app/services/shadow_observation_service.py` | 서비스 | record_shadow_observation() — INSERT만 |
| `alembic/versions/0XX_shadow_observation_log.py` | 마이그레이션 | CREATE TABLE shadow_observation_log |
| `tests/test_shadow_observation.py` | 테스트 | ~24 tests |

### 수정

| 파일 | 변경 | 설명 |
|------|------|------|
| `app/models/__init__.py` | import 추가 | ShadowObservationLog 등록 |

### 무수정 (봉인 유지)

| 파일 | 상태 |
|------|------|
| `app/services/pipeline_shadow_runner.py` | RI-2A-1 SEALED, 수정 0줄 |
| `app/services/shadow_readthrough.py` | RI-2A-1 SEALED, 수정 0줄 |
| `tests/test_pipeline_shadow_runner.py` | 수정 0줄 |
| `tests/test_shadow_readthrough.py` | 수정 0줄 |

---

## 10. 종합 리스크 평가

| 리스크 | 수준 | 사유 |
|--------|:----:|------|
| 기존 데이터 훼손 | **ZERO** | 기존 테이블 write 0 |
| 기존 코드 파괴 | **ZERO** | FROZEN 수정 0, RED 접촉 0, 신규 파일만 |
| Rollback 비용 | **TRIVIAL** | DROP TABLE + 파일 삭제 |
| 운영 간섭 | **ZERO** | beat 없음, 수동 트리거만, INSERT 실패 시 무영향 |
| RI-2A-1 영향 | **ZERO** | readthrough/comparison 코드 수정 0줄 |

---

## A 판정 요청

| 판정 대상 | 선택지 |
|----------|--------|
| RI-2A-2 2단 분리 (2a/2b) | 분리 승인 / 수정 / 거부 |
| RI-2A-2a 범위 (append-only 적재) | 승인 / 수정 / 거부 |
| shadow_observation_log 신규 테이블 | 허용 / 거부 |
| RI-2A-2b (beat) 후속 보류 | 승인 / 동시 심사 요구 |
| RI-2A-2a 설계/구현 GO | 범위 승인 후 별도 GO 필요 |

---

```
CR-048 RI-2A-2 Scope Review Package v1.0
Baseline: v2.1 (5330/5330 PASS, RI-2A-1 SEALED)
RI-2A-2a scope: shadow_observation_log INSERT only (신규 테이블, append-only, 수동 트리거)
RI-2A-2b scope: Celery beat 5분 주기 (DEFERRED — 2a 봉인 후)
DB write: shadow_observation_log INSERT only
Existing table modification: ZERO
Business table write: ZERO
FROZEN function modification: ZERO lines
RED file access: ZERO
RI-2A-1 code modification: ZERO lines
Rollback cost: TRIVIAL
Estimated new tests: ~24
Beat schedule change: NONE (RI-2A-2a), DEFERRED to RI-2A-2b
```
