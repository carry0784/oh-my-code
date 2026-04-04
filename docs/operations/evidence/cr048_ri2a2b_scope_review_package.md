# CR-048 RI-2A-2b 범위 심사 패키지

**Stage**: RI-2A-2b (Shadow Observation Automation + Retention)
**Status**: SCOPE REVIEW 제출 (v1)
**Date**: 2026-04-04
**Authority**: A
**선행 조건**: RI-2A-2a SEALED (v2.2, 5354/5354 PASS)
**현재 기준선**: v2.4 (5430/5430 PASS)

---

## 1. 해석 및 요약

### 1.1 목적 정의

RI-2A-2b는 **shadow observation의 자동 반복 실행(beat/schedule)과 데이터 보존 정책(retention)을 정의**하는 범위 심사입니다.

> RI-2A-2b = "수동 trigger → 자동 주기 실행 전환 + 누적 데이터 관리 정책 수립"
> execution path, business write, gate state change와 **완전 무관**.

### 1.2 경계 선언

| 속성 | RI-2A-2a (SEALED) | RI-2A-2b (본 심사) | RI-2B (DEFERRED) |
|------|:------------------:|:------------------:|:----------------:|
| shadow observation INSERT | 수동 trigger | **자동 beat** | 자동 beat |
| business table write | 0 | **0** | bounded |
| execution path | 없음 | **없음** | bounded write |
| gate state change | 없음 | **없음** | 별도 승인 |
| symbols UPDATE | 금지 | **금지** | CAS bounded |
| EXECUTION_ENABLED | N/A | **N/A (무관)** | False→True |
| retention/purge | deferred | **본 심사 대상** | 동일 정책 적용 |

### 1.3 한 문장 목표

> **RI-2A-2b = "shadow_observation_log를 자동 주기로 INSERT하고, 누적 데이터의 보존/정리 정책을 정한다. business table은 건드리지 않는다."**

---

## 2. 장점 / 단점

### 2.1 장점

| # | 장점 | 설명 |
|---|------|------|
| 1 | **운영 증거 자동 축적** | 수동 trigger 의존성 제거, 72H 연속 실행 조건 충족 가능 |
| 2 | **RI-2B 전환 판단 근거 생성** | verdict 일치율, INSUFFICIENT 비율 등 시계열 데이터 자동 수집 |
| 3 | **관측 가능성 향상** | last_run, status, failure_reason 등 scheduler 상태 추적 |
| 4 | **데이터 관리 표준화** | hot/warm/audit 계층별 보존 기준 수립 |
| 5 | **rollback trivial** | beat entry 제거 + retention disable만으로 원복 가능 |

### 2.2 단점

| # | 단점 | 완화 방안 |
|---|------|-----------|
| 1 | **자동 반복 실행 리스크** | fail-closed 규칙 + dispatch 상한 |
| 2 | **중복 dispatch 가능성** | idempotency key + duplicate detection |
| 3 | **retention purge 시 감사 증거 손실** | audit tier 영구 보존 + purge receipt |
| 4 | **beat 등록 = L4 변경** | 별도 A 승인 gate 유지 |
| 5 | **DB 누적량 증가** | retention 정책으로 bounded |

---

## 3. 이유 / 근거

### 3.1 왜 RI-2A-2b가 지금 필요한가

| 이유 | 설명 |
|------|------|
| **72H 조건 미충족** | RI-2A scope review에서 정의된 72H 연속 실행 조건이 수동 trigger로는 달성 불가 |
| **RI-2B 전환 근거 부재** | verdict 일치율/INSUFFICIENT 비율 등 시계열 측정 없이 RI-2B-2b GO 판단 불가 |
| **데이터 무한 성장** | retention 정책 없이 observation log가 무제한 성장 → 운영 리스크 |
| **관측 사각지대** | scheduler 상태(last_run, skipped, failure) 추적 없이 운영 건전성 판단 불가 |

### 3.2 왜 RI-2B-2b보다 먼저인가

> 관측 자동화 → 운영 증거 축적 → write 전환 심사 순서가 맞다.
> RI-2A-2b 없이 RI-2B-2b를 열면 write 전환 판단의 근거가 부족하다.

---

## 4. Beat / Schedule 범위

### 4.1 신규 beat entry 후보

| Key | Task | Schedule | 이유 |
|-----|------|----------|------|
| `shadow-observation-5m` | `workers.tasks.shadow_observation_tasks.run_shadow_observation` | 300s (5분) | data collection과 동일 주기, pipeline 입력 갱신 시점 정렬 |

**beat entry 1건만 추가. 기존 beat entry 변경 0건.**

### 4.2 주기 근거

| 후보 | 장점 | 단점 | 선택 |
|------|------|------|:----:|
| 1분 | 고해상도 | DB 부하, 의미 없는 중복 (data collection 5분 주기) | X |
| 5분 | data collection 정렬, 적절 해상도 | — | **O** |
| 15분 | 저부하 | 72H 내 관측 수 부족 (288건) | X |
| 1시간 | 최소 부하 | 해상도 부족, 72H 내 72건만 | X |

### 4.3 Scope: read-only automation only

```
beat dispatch
  → shadow_observation_task()
    → 각 symbol에 대해:
        1. run_shadow_pipeline()     (RI-1 SEALED, pure, 수정 0줄)
        2. run_readthrough_comparison() (RI-2A-1 SEALED, SELECT only)
        3. record_shadow_observation() (RI-2A-2a SEALED, INSERT only)
    → 결과: shadow_observation_log INSERT N건
    → business table write: 0건
    → symbols UPDATE: 0건
    → gate change: 0건
```

---

## 5. 단일 실행 보장 (Duplicate Dispatch 방지)

### 5.1 문제

Celery beat이 5분 주기로 dispatch할 때, 이전 실행이 아직 진행 중이면 중복 실행 가능.

### 5.2 방어 장치

| # | 장치 | 설명 |
|---|------|------|
| 1 | **task expiry** | `expires=240s` — 4분 내 미시작 시 자동 폐기 (5분 주기 겹침 방지) |
| 2 | **task lock (Redis)** | `shadow_observation_running` key, TTL=300s. 이미 실행 중이면 SKIP |
| 3 | **idempotency window** | `(symbol, input_fingerprint, shadow_timestamp)` — RI-2A-2a dedupe key 유지 |
| 4 | **max_retries=0** | 실패 시 재시도 없음 (다음 주기에 자연 재실행) |

### 5.3 중복 감지 로그

```python
# 이미 실행 중인 경우
logger.info("shadow_observation_skipped", reason="already_running", lock_ttl_remaining=...)
```

---

## 6. Fail-closed 규칙

### 6.1 원칙

> 오류 발생 시 자동 write/상태변경 없이 중단한다.
> shadow observation task의 실패가 다른 beat task에 영향을 주지 않는다.

### 6.2 실패 시나리오별 행동

| 시나리오 | 행동 | write | state change |
|---------|------|:-----:|:------------:|
| run_shadow_pipeline() 예외 | SKIP, 로그 기록 | 0 | 0 |
| run_readthrough_comparison() 예외 | SKIP, 로그 기록 | 0 | 0 |
| record_shadow_observation() 예외 | 로그 기록, task 성공 처리 | 0 | 0 |
| DB connection 실패 | SKIP, 로그 기록 | 0 | 0 |
| Redis lock 획득 실패 | SKIP, 로그 기록 | 0 | 0 |
| data collection 결과 없음 | SKIP, `skipped_reason=no_input` | 0 | 0 |
| 전체 symbol 0건 처리 | 정상 종료, `processed=0` 기록 | 0 | 0 |

### 6.3 자동 정지 조건

| 조건 | 행동 |
|------|------|
| 연속 실패 ≥ 10회 | 경고 로그 + `consecutive_failures` 카운터 기록 |
| 연속 실패 ≥ 30회 | **자동 정지 아님** — 로그만 기록. 정지는 수동 A 판단 |

> beat task 자동 정지(auto-disable)는 도입하지 않는다.
> 이유: 자동 정지 로직 자체가 state change이며, 복구 경로가 불명확해진다.
> 대신 연속 실패 카운터 + 운영자 알림으로 대응한다.

---

## 7. Retention 정책

### 7.1 3계층 보존 모델

| Tier | 명칭 | 보존 대상 | 보존 기간 | Purge 방식 |
|------|------|-----------|-----------|-----------|
| **Hot** | 최근 관측 | 전체 원본 row | **30일** | soft delete (is_archived=True) |
| **Warm** | 분석용 요약 | 일별/심볼별 집계 | **90일** | summary 테이블 별도 (RI-2A-2b scope 외) |
| **Audit** | 감사 증거 | verdict_mismatch, reason_mismatch row | **영구** | purge 금지 |

### 7.2 Purge 대상 판별 규칙

| 조건 | Purge 허용 |
|------|:----------:|
| `comparison_verdict = 'match'` AND `created_at < now() - 30d` | **O** (soft delete) |
| `comparison_verdict = 'match'` AND `created_at < now() - 90d` | **O** (hard delete) |
| `comparison_verdict IN ('verdict_mismatch', 'reason_mismatch')` | **X** (audit 영구 보존) |
| `comparison_verdict LIKE 'insufficient%'` AND `created_at < now() - 90d` | **O** (hard delete) |
| 모든 row WHERE `is_archived = False` | **X** (hot tier) |

### 7.3 감사 증거 보존 예외

> **verdict_mismatch, reason_mismatch 건은 영구 보존한다.**
> 이유: shadow와 기존 결과의 불일치는 pipeline 결함 또는 데이터 변동의 증거이며,
> RI-2B write 전환 판단 근거로 사용되므로 삭제하면 판단 기반이 소실된다.

### 7.4 Purge 실행 정책

| 항목 | 값 |
|------|-----|
| Purge trigger | **수동 실행만** (beat 자동 purge 금지) |
| Purge batch size | 1000 rows/실행 |
| Purge receipt | purge 실행마다 `(purge_timestamp, rows_deleted, criteria, operator)` 기록 |
| Purge 전 검증 | audit tier row가 purge 대상에 포함되지 않음 확인 필수 |
| Purge 승인 | **A 승인 불필요** (정책 범위 내 match row soft/hard delete) |
| 정책 변경 승인 | **A 승인 필수** (보존 기간, audit 대상, purge 기준 변경) |

### 7.5 모델 확장 (retention 지원)

| 필드 | 타입 | 용도 | 기본값 |
|------|------|------|--------|
| `is_archived` | Boolean | soft delete 마커 | False |

> **모델 변경 1필드만.** RI-2A-2a SEALED 모델의 기존 15필드는 수정 0건.
> is_archived 추가에 대한 마이그레이션 1건 필요.

---

## 8. Idempotency 및 Replay 안전성

### 8.1 중복 적재 방지

| 수준 | 장치 | 설명 |
|------|------|------|
| Task 수준 | Redis lock (5.2 참조) | 동시 실행 방지 |
| Row 수준 | dedupe key `(symbol, input_fingerprint, shadow_timestamp)` | 동일 입력→동일 해시→중복 감지 |
| Window 수준 | shadow_timestamp 5분 window 내 동일 symbol 중복 INSERT 검사 | 쿼리 시점 dedupe |

### 8.2 Replay 안전성

> shadow observation INSERT는 append-only이므로, replay(재실행)는 항상 안전하다.
> 최악의 경우 동일 내용의 row가 중복 생성되지만, business state에 영향 없음.
> 중복 row는 dedupe key로 식별 가능하며, retention purge 시 정리됨.

### 8.3 중복 정리 방지

> retention purge는 **원본 row를 기준으로만** 동작한다.
> dedupe된 중복 row는 별도 정리 대상이 아니며, 동일 retention 정책 적용.

---

## 9. 관찰 가능성 (Observability)

### 9.1 Task 실행 로그 필드

| 필드 | 타입 | 설명 |
|------|------|------|
| `last_run` | datetime | 마지막 실행 시각 |
| `status` | enum | `completed`, `skipped`, `failed` |
| `skipped_reason` | str | null | `already_running`, `no_input`, `lock_failed` |
| `failure_reason` | str | null | exception 메시지 (truncated) |
| `symbols_processed` | int | 처리된 symbol 수 |
| `symbols_skipped` | int | skip된 symbol 수 |
| `observations_inserted` | int | INSERT 성공 건수 |
| `observations_failed` | int | INSERT 실패 건수 |
| `duration_ms` | int | 실행 소요 시간 |
| `consecutive_failures` | int | 연속 실패 횟수 (Redis counter) |

### 9.2 로그 출력 형식

```python
logger.info(
    "shadow_observation_task_completed",
    last_run=...,
    status="completed",
    symbols_processed=25,
    symbols_skipped=3,
    observations_inserted=22,
    observations_failed=0,
    duration_ms=1450,
    consecutive_failures=0,
)
```

### 9.3 운영 진단 쿼리 (예시)

```sql
-- 최근 24H 실행 현황
SELECT date_trunc('hour', created_at), count(*),
       count(*) FILTER (WHERE comparison_verdict = 'match') as match_count
FROM shadow_observation_log
WHERE created_at > now() - interval '24 hours'
GROUP BY 1 ORDER BY 1;

-- verdict 일치율 (rolling 24H)
SELECT
  count(*) FILTER (WHERE comparison_verdict = 'match')::float /
  NULLIF(count(*) FILTER (WHERE comparison_verdict NOT LIKE 'insufficient%'), 0)
  as match_rate
FROM shadow_observation_log
WHERE created_at > now() - interval '24 hours';
```

---

## 10. Rollback / Disable 계획

### 10.1 Rollback 시나리오별 비용

| 시나리오 | 행동 | 비용 | 데이터 영향 |
|---------|------|:----:|:----------:|
| **beat 전체 중단** | beat_schedule에서 `shadow-observation-5m` 제거 | TRIVIAL | 0 (기존 데이터 보존) |
| **retention purge 중단** | purge 스크립트 미실행 | TRIVIAL | 0 (데이터 계속 누적) |
| **RI-2A-2b 전체 철회** | beat 제거 + `is_archived` 컬럼 DROP + 신규 코드 revert | LOW | 0 (observation_log 데이터 보존) |
| **observation_log 테이블 DROP** | 마이그레이션 revert | MEDIUM | 전체 관측 데이터 소실 |

### 10.2 단계적 disable 순서

```
1. beat_schedule에서 shadow-observation-5m 제거 (dispatch 중단)
2. Redis lock key 삭제 (잔여 lock 정리)
3. purge 스크립트 실행 금지 (데이터 보존)
4. 기존 observation_log 데이터는 보존 (DROP하지 않음)
```

### 10.3 RI-2A-2a 복귀 보장

> RI-2A-2b에 문제가 생겨도:
> - RI-2A-2a record_shadow_observation() 수동 trigger 경로는 **영향 0** (코드 분리)
> - RI-2A-1 readthrough 경로는 **영향 0**
> - RI-1 shadow pipeline은 **영향 0**
> - 기존 5430 테스트는 **영향 0** (신규 파일만 추가)

---

## 11. Runtime Delta

### 11.1 신규 파일

| 파일 | 유형 | 설명 |
|------|------|------|
| `workers/tasks/shadow_observation_tasks.py` | Celery task | shadow observation beat task |
| `tests/test_shadow_observation_beat.py` | 테스트 | beat task 단위 테스트 |

### 11.2 수정 파일

| 파일 | 변경 | 설명 |
|------|------|------|
| `workers/celery_app.py` | beat_schedule 1건 추가 | `shadow-observation-5m` entry |
| `app/models/shadow_observation.py` | 필드 1건 추가 | `is_archived: Boolean = False` |
| `alembic/versions/0XX_shadow_obs_retention.py` | 신규 마이그레이션 | `is_archived` 컬럼 추가 |

### 11.3 미수정 파일 (SEALED 보호)

| 파일 | 상태 | 사유 |
|------|------|------|
| `app/services/shadow_observation_service.py` | **수정 0줄** | RI-2A-2a SEALED |
| `app/services/shadow_write_service.py` | **수정 0줄** | RI-2B-1/2a SEALED |
| `app/services/pipeline_shadow_runner.py` | **수정 0줄** | RI-1 SEALED |
| `app/services/shadow_readthrough.py` | **수정 0줄** | RI-2A-1 SEALED |
| FROZEN/RED 파일 전체 | **접촉 0** | 기존 정책 유지 |

---

## 12. Risk Matrix

| # | 리스크 | 확률 | 영향 | 완화 |
|---|--------|:----:|:----:|------|
| R1 | 중복 dispatch → 중복 INSERT | 중 | 낮 | Redis lock + dedupe key + expires |
| R2 | DB connection 장애 → task 연속 실패 | 중 | 낮 | fail-closed, consecutive_failures 카운터 |
| R3 | observation_log 무한 성장 | 높 | 중 | retention 3계층 + purge 정책 |
| R4 | purge가 audit row 삭제 | 낮 | 높 | audit tier 영구 보존 규칙 + purge 전 검증 |
| R5 | beat entry가 기존 task와 충돌 | 낮 | 낮 | 독립 task name, 독립 Redis lock |
| R6 | is_archived 컬럼 추가가 기존 쿼리 깨뜨림 | 낮 | 중 | nullable Boolean, 기본값 False, 기존 INSERT 무영향 |
| R7 | scheduler 상태 추적 누락 | 중 | 낮 | 9.1 observability 필드 의무화 |

### 12.1 리스크 수준 종합

| 수준 | 판정 |
|------|------|
| business table write | **ZERO** |
| execution path | **ZERO** |
| gate state change | **ZERO** |
| FROZEN 수정 | **ZERO** |
| RED 접촉 | **ZERO** |
| rollback 비용 | **TRIVIAL ~ LOW** |
| 전체 리스크 | **LOW** (관측 자동화 + 데이터 관리만) |

---

## 13. 승인 게이트

### 13.1 구현 전 A 승인 필요 항목

| # | 항목 | 승인 시점 |
|---|------|-----------|
| 1 | RI-2A-2b scope review (본 문서) | **지금** |
| 2 | beat_schedule 추가 (celery_app.py 수정) | 구현 GO 시 |
| 3 | retention 정책 세부 기준 (30d/90d/영구) | 구현 GO 시 |
| 4 | is_archived 모델 확장 | 구현 GO 시 |

### 13.2 구현 후 A 승인 필요 항목

| # | 항목 | 승인 시점 |
|---|------|-----------|
| 1 | RI-2A-2b completion evidence | 봉인 시 |
| 2 | beat 실제 활성화 | 별도 GO (dry-schedule 통과 후) |

### 13.3 금지 항목 (out-of-scope)

| # | 금지 | 사유 |
|---|------|------|
| 1 | business table write | RI-2B scope |
| 2 | EXECUTION_ENABLED 변경 | RI-2B-2b scope |
| 3 | symbols UPDATE | RI-2B scope |
| 4 | gate state change | A 전용 |
| 5 | 기존 beat entry 수정 | 범위 밖 |
| 6 | FROZEN/RED 파일 수정 | 영구 금지 |
| 7 | Warm tier summary 테이블 생성 | RI-2A-2b scope 외 (향후) |
| 8 | auto-disable 로직 | state change에 해당 |
| 9 | beat 실제 활성화 (production dispatch) | 별도 GO |
| 10 | purge 실제 실행 | 정책 수립만, 실행은 별도 |

---

## 14. Dry-schedule Mode 제안

### 14.1 개념

beat 등록은 하되, 실제 pipeline 실행 대신 "would_run" 로그만 남기는 중간 단계.

```python
DRY_SCHEDULE: bool = True  # True: 로그만, False: 실제 실행

# task 내부:
if DRY_SCHEDULE:
    logger.info("shadow_observation_would_run", symbols=symbol_list, timestamp=now)
    return {"status": "dry_schedule", "would_process": len(symbol_list)}
# else: 실제 pipeline 실행
```

### 14.2 Dry-schedule 장점

| 장점 | 설명 |
|------|------|
| beat dispatch 검증 | 주기, 중복 방지, expires 등 scheduler 동작 확인 |
| 부하 측정 | task dispatch 빈도, 소요 시간 측정 (pipeline 실행 없이) |
| 안전한 활성화 | dry → live 전환 시 A 승인 1건만 필요 |

### 14.3 Dry-schedule → Live 전환

| 단계 | 행동 | 승인 |
|------|------|------|
| RI-2A-2b 구현 | DRY_SCHEDULE=True 하드코딩 | 구현 GO |
| Dry 검증 (24H) | would_run 로그 확인, dispatch 정상성 검증 | 불필요 |
| Live 전환 | DRY_SCHEDULE=False | **A 승인 필수** |

---

## 15. Scheduler Readiness Score

### 15.1 체크리스트

| # | 항목 | 기준 | 가중치 |
|---|------|------|:------:|
| 1 | 단일 실행 보장 | Redis lock + expires 구현 | 20 |
| 2 | Fail-closed | 모든 실패 시나리오에서 write=0, state_change=0 | 20 |
| 3 | Idempotency | dedupe key + window 중복 검사 | 15 |
| 4 | Observability | 9.1 필수 필드 10개 중 10개 구현 | 15 |
| 5 | Rollback plan | 단계적 disable 순서 문서화 + 검증 | 15 |
| 6 | Retention safety | audit tier 영구 보존 + purge 전 검증 | 15 |
| **합계** | | | **100** |

### 15.2 구현 허용 기준

| 점수 | 판정 |
|:----:|------|
| ≥ 90 | GO |
| 70-89 | CONDITIONAL (부족 항목 보완 후 재심사) |
| < 70 | **구현 금지** |

---

## 16. 실행방법

### Step 1: 본 Scope Review 승인 (A)
### Step 2: Design / Contract 문서 작성 (구현 전)
### Step 3: A 심사 → GO / CONDITIONAL / HOLD
### Step 4: 구현 (DRY_SCHEDULE=True 하드코딩)
### Step 5: Completion Evidence → A 봉인
### Step 6: Dry-schedule 24H 검증
### Step 7: Live 전환 승인 (A) → DRY_SCHEDULE=False

---

## 17. 더 좋은 아이디어

### 17.1 Observation Health Dashboard 쿼리 사전 정의

구현 전에 운영 진단에 필요한 SQL 쿼리 목록을 계약으로 확정하면:
- 어떤 관측 필드가 실제 필요한지 사전 검증 가능
- observability 설계와 retention 정책의 정합성 확인 가능

### 17.2 Retention Dry-run

실제 purge 전에 "would_purge" 모드로 삭제 대상만 조회:
```sql
SELECT count(*), comparison_verdict
FROM shadow_observation_log
WHERE is_archived = False
  AND created_at < now() - interval '30 days'
  AND comparison_verdict = 'match'
GROUP BY comparison_verdict;
```
이 쿼리 결과를 A에게 보고 → purge 실행 승인

### 17.3 beat 등록과 dispatch 분리

RI-2A-2b 구현 단계에서는 `celery_app.py`에 beat entry를 주석 상태로 등록하고,
dry-schedule 검증이 끝난 후에만 주석 해제하는 방법도 고려 가능.
이 경우 "코드 존재 ≠ 실행"이라는 RI-2B-2a/2b 패턴과 동일한 분리가 적용됨.

---

## 18. 종합

### 18.1 범위 요약

```
허용:
  ├─ shadow_observation_tasks.py 신규 생성 (Celery task)
  ├─ celery_app.py beat_schedule에 shadow-observation-5m 1건 추가
  ├─ shadow_observation.py에 is_archived 필드 1건 추가
  ├─ 마이그레이션 1건 (is_archived 컬럼)
  ├─ DRY_SCHEDULE=True 하드코딩 (실제 pipeline 실행 금지)
  ├─ retention 정책 문서화 (purge 실행은 별도)
  └─ 테스트 신규 추가

금지:
  ├─ business table write (symbols, screening_results, qualification_results)
  ├─ EXECUTION_ENABLED 변경
  ├─ gate state change
  ├─ FROZEN/RED 파일 수정
  ├─ 기존 beat entry 변경
  ├─ SEALED 서비스 코드 수정 (shadow_observation_service, shadow_write_service 등)
  ├─ DRY_SCHEDULE=False 전환 (별도 A 승인)
  ├─ purge 실제 실행 (별도 승인)
  └─ auto-disable 로직 (state change)
```

### 18.2 기준선 보호

| 보호 대상 | 보장 |
|-----------|------|
| Baseline v2.4 (5430/5430 PASS) | 전체 회귀 PASS 필수 |
| EXECUTION_ENABLED=False | 무관 (RI-2A-2b는 execution path 미접촉) |
| Gate LOCKED | 변경 0 |
| FROZEN 함수 | 수정 0줄 |
| RED 파일 | 접촉 0건 |
| SEALED 서비스 | 수정 0줄 |

---

## A 판정 요청

| 판정 대상 | 선택지 |
|----------|--------|
| RI-2A-2b 범위 | **승인 / 수정 요청 / 거부** |
| beat_schedule 1건 추가 | 허용 여부 |
| is_archived 모델 확장 | 허용 여부 |
| 3계층 retention (hot 30d / warm 90d / audit 영구) | 정책 승인 여부 |
| DRY_SCHEDULE 패턴 도입 | 채택 여부 |
| Scheduler Readiness Score | 채택 여부 |
| 구현 GO | 범위 승인 후 별도 GO 필요 |

---

```
CR-048 RI-2A-2b Scope Review Package v1.0
Baseline: v2.4 (5430/5430 PASS)
Gate: LOCKED (변경 없음)
EXECUTION_ENABLED: False (무관)
Scope: shadow observation beat automation + retention policy
Business table write: ZERO
Execution path: ZERO
Gate state change: ZERO
FROZEN modification: ZERO
RED access: ZERO
New beat entry: 1 (shadow-observation-5m, 300s, DRY_SCHEDULE=True)
Model extension: 1 field (is_archived: Boolean)
Migration: 1 (is_archived column)
Rollback cost: TRIVIAL ~ LOW
Estimated new files: 2 (task + test)
Estimated modified files: 3 (celery_app, model, migration)
SEALED service modification: ZERO
```
