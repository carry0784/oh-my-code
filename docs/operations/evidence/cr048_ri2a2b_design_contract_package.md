# CR-048 RI-2A-2b Design / Contract Package

**Stage**: RI-2A-2b (Shadow Observation Automation + Retention)
**Status**: IMPLEMENTATION PROMPT 제출 (v1)
**Date**: 2026-04-04
**Authority**: A
**선행 조건**: RI-2A-2b Scope Review v1 ACCEPTED
**현재 기준선**: v2.4 (5430/5430 PASS)

---

## Part 1. Implementation Prompt

### 1.1 목적

RI-2A-2b는 shadow observation의 **자동 주기 실행 기반(dry-schedule)과 보존 정책 정의(retention planner)**를 구현합니다.

> 모든 변경은 read-only, fail-closed, dry-schedule-first입니다.
> business table write 0, execution path 0, gate state change 0.

### 1.2 구현 범위

| # | 항목 | 설명 |
|---|------|------|
| 1 | **DRY_SCHEDULE mode** | `DRY_SCHEDULE=True` 하드코딩. pipeline 실행 없이 `would_run/would_skip/reason_code` 로그만 출력 |
| 2 | **단일 실행 보장** | Redis lock (`shadow_observation_running`, TTL=300s) + `expires=240s` + `max_retries=0` |
| 3 | **Observation status 필드** | `last_run`, `status`, `skipped_reason`, `failure_reason`, `symbols_processed`, `symbols_skipped`, `observations_inserted`, `observations_failed`, `duration_ms`, `consecutive_failures` |
| 4 | **Disable/rollback switch** | beat entry 주석 상태로 등록 (uncomment = A 승인 필요) |
| 5 | **Retention planner** | 정책 정의 상수만 (RETENTION_HOT_DAYS=30, RETENTION_WARM_DAYS=90, AUDIT_VERDICTS=frozenset). purge 실행 함수 없음 |
| 6 | **is_archived 모델 확장** | `ShadowObservationLog.is_archived: Boolean = False` + 마이그레이션 |
| 7 | **Dry-schedule 출력 계약** | `would_run`, `would_skip`, `reason_code` 3필드 필수 |

### 1.3 수정 파일 계획

| 파일 | 유형 | 변경 내용 |
|------|------|-----------|
| `workers/tasks/shadow_observation_tasks.py` | **신규** | Celery task: dry-schedule mode, Redis lock, observability 로그 |
| `tests/test_shadow_observation_beat.py` | **신규** | beat task 테스트 (dry-schedule, lock, skip, fail-closed) |
| `app/models/shadow_observation.py` | **수정** | `is_archived` 필드 1건 추가 (Boolean, default False) |
| `alembic/versions/0XX_shadow_obs_is_archived.py` | **신규** | `is_archived` 컬럼 ADD 마이그레이션 |
| `workers/celery_app.py` | **수정** | include에 `shadow_observation_tasks` 추가 + beat_schedule에 주석 상태로 entry 등록 |

### 1.4 미수정 파일 (SEALED 보호)

| 파일 | 상태 | 사유 |
|------|------|------|
| `app/services/shadow_observation_service.py` | 수정 0줄 | RI-2A-2a SEALED |
| `app/services/shadow_write_service.py` | 수정 0줄 | RI-2B-1/2a SEALED |
| `app/services/pipeline_shadow_runner.py` | 수정 0줄 | RI-1 SEALED |
| `app/services/shadow_readthrough.py` | 수정 0줄 | RI-2A-1 SEALED |
| FROZEN/RED 파일 전체 | 접촉 0건 | 영구 금지 |

---

## Part 2. Constitutional Comparison Review

### 2.1 헌법 조항 대조

| # | 헌법 조항 | RI-2A-2b 준수 | 검증 방법 |
|---|----------|:-------------:|-----------|
| C-01 | business table write 금지 | **PASS** | shadow_observation_log INSERT only. symbols/screening/qualification UPDATE 0 |
| C-02 | execution path 무접촉 | **PASS** | EXECUTION_ENABLED 참조 0, execute_bounded_write 호출 0 |
| C-03 | gate state change 금지 | **PASS** | Gate LOCKED 상태 변경 코드 0줄 |
| C-04 | FROZEN 함수 수정 0줄 | **PASS** | run_shadow_pipeline, screen_and_update 등 수정 0줄 |
| C-05 | RED 파일 접촉 0건 | **PASS** | multi_symbol_runner, strategy_router, exchanges/* 접촉 0 |
| C-06 | SEALED 서비스 코드 수정 0줄 | **PASS** | shadow_observation_service.py, shadow_write_service.py 수정 0줄 |
| C-07 | dry_run 우선 | **PASS** | DRY_SCHEDULE=True 하드코딩, False 전환은 별도 A 승인 |
| C-08 | fail-closed | **PASS** | 모든 실패 시 write=0, state_change=0, 로그만 기록 |
| C-09 | rollback trivial | **PASS** | beat 주석화 + is_archived DROP = 완전 복귀 |
| C-10 | 회귀 기준선 보호 | **PASS** | 5430/5430 전체 회귀 PASS 필수 |

### 2.2 FROZEN/RED 접촉면 분석

| 파일 분류 | RI-2A-2b 접촉 | 상세 |
|-----------|:-------------:|------|
| FROZEN 함수 | **호출 0** | dry-schedule은 pipeline 실행 자체를 안 함 |
| RED 파일 | **접촉 0** | 교환소, 라우터, 전략 로더 등 무접촉 |
| SEALED 서비스 | **수정 0** | 기존 4개 SEALED 서비스 코드 변경 없음 |

> **핵심:** DRY_SCHEDULE=True에서는 shadow pipeline 자체를 실행하지 않으므로,
> FROZEN 함수 호출도 0회입니다. Live 전환(DRY_SCHEDULE=False) 시에만 호출이 시작되며,
> 이는 별도 A 승인 대상입니다.

---

## Part 3. Activation Block Table

### 3.1 현재 상태 (구현 직후)

| 항목 | 상태 | 비고 |
|------|:----:|------|
| beat enabled? | **NO** | 주석 상태로 등록 |
| scheduler dispatch active? | **NO** | 주석 = dispatch 0 |
| DRY_SCHEDULE? | **YES (True)** | 하드코딩, False 전환 = A 승인 |
| retention deletion active? | **NO** | planner 정의만, purge 함수 없음 |
| business write path? | **NO** | shadow_observation_log INSERT only |
| execution authority? | **NO** | EXECUTION_ENABLED 무관 |
| rollback switch present? | **YES** | beat 주석 해제/복원 + is_archived DROP |
| idempotency verified? | **YES** | Redis lock + dedupe key + expires |
| observability fields verified? | **YES** | 10개 필드 계약 |

### 3.2 활성화 전환 게이트 (향후)

| 전환 | 필요 승인 | 전제 조건 |
|------|-----------|-----------|
| beat 주석 해제 (dispatch 시작) | **A 승인** | dry-schedule 24H 검증 완료 |
| DRY_SCHEDULE True→False (live 실행) | **A 승인** | beat dispatch 정상 + dry 로그 검증 |
| retention purge 실행 | **A 승인** | would_purge dry-run 결과 보고 |
| is_archived 실제 사용 | 구현 범위 내 | soft-delete 마커만, 실제 삭제 아님 |

---

## Part 4. Forbidden Clause Check

### 4.1 명시적 금지 확인

| # | 금지 조항 | 코드에서 위반 가능성 | 방지 방법 |
|---|----------|:-------------------:|-----------|
| F-01 | beat uncomment | 낮 | 주석 상태 유지, 테스트에서 주석 확인 |
| F-02 | celery active periodic enable | 낮 | beat_schedule에 entry 없음 (주석) |
| F-03 | delete/drop/purge 실행 | 없음 | purge 함수 미구현, 정의 상수만 |
| F-04 | business write | 없음 | symbols/screening/qualification UPDATE/INSERT 코드 0줄 |
| F-05 | EXECUTION_ENABLED 변경 | 없음 | shadow_write_service.py 수정 0줄 |
| F-06 | sealed baseline drift | 없음 | 5430 회귀 PASS 필수 |
| F-07 | auto-disable 로직 | 없음 | state change 금지 원칙 준수, 로그만 기록 |
| F-08 | DRY_SCHEDULE=False | 낮 | True 하드코딩, False 전환 = 별도 A 승인 |

### 4.2 금지선 보호 테스트

| 테스트 | 검증 대상 |
|--------|-----------|
| `test_dry_schedule_flag_true` | DRY_SCHEDULE == True 확인 |
| `test_dry_schedule_no_pipeline_call` | DRY_SCHEDULE=True 시 pipeline 호출 0회 |
| `test_beat_entry_commented` | celery_app.py에서 shadow-observation beat entry가 주석 상태 |
| `test_no_purge_function` | retention 상수만 존재, purge 함수 미존재 |
| `test_sealed_services_untouched` | SEALED 4개 서비스의 source hash 불변 |
| `test_no_business_write` | task 코드에 UPDATE/DELETE 키워드 0건 |

---

## Part 5. State Transition Impact

### 5.1 상태 전이 분석

| 대상 | 전이 | 영향 |
|------|------|------|
| Gate | LOCKED → LOCKED | 변경 없음 |
| EXECUTION_ENABLED | False → False | 무관 |
| DRY_SCHEDULE | (신규) True | 신규 상수, 기존 상태 무영향 |
| beat_schedule | 주석 entry 추가 | dispatch 0, 기존 entry 무변경 |
| shadow_observation_log | is_archived 컬럼 추가 | 기존 row 무영향 (default False) |
| celery include | +1 모듈 | 기존 모듈 무변경, task 등록만 |

### 5.2 DB 스키마 변경

| 변경 | 유형 | 리스크 |
|------|------|:------:|
| `shadow_observation_log.is_archived` ADD COLUMN | ALTER TABLE | TRIVIAL |
| 기존 row에 default False 적용 | 자동 | ZERO |
| 기존 테이블 스키마 | 변경 없음 | ZERO |
| 기존 인덱스 | 변경 없음 | ZERO |

---

## Part 6. Log / Audit Impact

### 6.1 신규 로그 이벤트

| 이벤트 | 수준 | 조건 |
|--------|:----:|------|
| `shadow_observation_dry_schedule_would_run` | INFO | DRY_SCHEDULE=True, 실행 가능한 symbol 존재 |
| `shadow_observation_dry_schedule_would_skip` | INFO | DRY_SCHEDULE=True, skip 조건 해당 |
| `shadow_observation_skipped` | INFO | Redis lock 실패, no_input 등 |
| `shadow_observation_task_completed` | INFO | 정상 완료 (dry 포함) |
| `shadow_observation_task_failed` | ERROR | 예외 발생 |
| `shadow_observation_consecutive_failures` | WARNING | consecutive_failures ≥ 10 |

### 6.2 기존 로그 영향

| 영향 | 설명 |
|------|------|
| 기존 beat task 로그 | **변경 없음** |
| 기존 shadow service 로그 | **변경 없음** (SEALED) |
| Celery worker 로그 | include 1건 추가에 따른 모듈 로드 로그 |

---

## Part 7. Unresolved Risks

| # | 리스크 | 상태 | 완화 |
|---|--------|:----:|------|
| U-01 | beat 주석 해제 시점의 A 승인 절차 미확정 | OPEN | activation_manifest 문서로 게이트 |
| U-02 | DRY_SCHEDULE False 전환 시 24H 검증 기준 미확정 | OPEN | dry 로그 분석 기준 사후 정의 |
| U-03 | retention purge dry-run → approve → activate 4단계 구현 시점 미확정 | OPEN | 본 단계는 planner 정의만 |
| U-04 | Warm tier summary 테이블 설계 미확정 | OPEN | RI-2A-2b scope 외 (향후) |
| U-05 | Redis 미가용 시 lock 동작 | LOW | lock 획득 실패 = SKIP (fail-closed) |

---

## Part 8. Activation Manifest

> A 추가 제안 반영: 실제 enable 전에만 사용하는 단일 체크리스트.

### 8.1 Activation Manifest Template (구현 후 작성 예정)

```
# RI-2A-2b Activation Manifest
# 아래 모든 항목이 TRUE여야 beat 주석 해제 / DRY_SCHEDULE False 전환 가능

beat_entry_commented: true          # → false 전환 시 A 승인
dry_schedule_true: true             # → false 전환 시 A 승인
dispatch_active: false              # beat uncomment 후 true
purge_active: false                 # 별도 A 승인 후 true
rollback_verified: false            # 구현 완료 후 true
idempotency_verified: false         # 테스트 PASS 후 true
observability_verified: false       # 10필드 구현 확인 후 true
dry_24h_clean: false                # dry-schedule 24H 무오류 후 true
consecutive_failures_zero: false    # 연속 실패 0 확인 후 true
```

### 8.2 Manifest 갱신 규칙

| 규칙 | 설명 |
|------|------|
| 갱신 권한 | A + 구현자 공동 |
| false→true 전환 | 증거 기반 (테스트 결과, 로그 분석) |
| true→false 복귀 | 장애 발생 시 즉시 |
| 전체 true 달성 | beat uncomment + DRY_SCHEDULE False 전환 GO 요청 가능 |

---

## Part 9. Retention 4단계 분리

> A 추가 제안 반영: planner → simulate → approve → activate

| 단계 | 명칭 | RI-2A-2b 구현 | 실행 시점 |
|------|------|:-------------:|-----------|
| **1. Planner** | 정책 정의 (상수, 기준) | **YES** | 본 구현 |
| **2. Simulate** | would_purge 쿼리 (삭제 대상 조회만) | **NO** (향후) | 별도 GO |
| **3. Approve** | A 승인 (simulate 결과 기반) | **NO** | A 판정 |
| **4. Activate** | 실제 purge 실행 | **NO** | 별도 GO |

### 본 구현에서 포함하는 Planner 상수

```python
# RI-2A-2b Retention Policy — planner constants only.
# Purge execution is NOT implemented. Requires separate A approval.

RETENTION_HOT_DAYS: int = 30          # Hot tier: full row retention
RETENTION_WARM_DAYS: int = 90         # Warm tier: summary retention (table deferred)
AUDIT_VERDICTS: frozenset[str] = frozenset({
    "verdict_mismatch",
    "reason_mismatch",
})  # Audit tier: permanent retention, purge prohibited

# Purge function: NOT IMPLEMENTED.
# Purge activation requires: simulate → A approve → activate (3 separate gates)
```

---

## Part 10. Dry-schedule 출력 계약

> A 추가 제안 반영: would_run / would_skip / reason_code 3필드 필수

### 10.1 출력 스키마

```python
@dataclass
class DryScheduleResult:
    """Dry-schedule mode output. Required fields for pre-enable verification."""
    would_run: list[str]        # symbols that would be processed
    would_skip: list[str]       # symbols that would be skipped
    reason_codes: dict[str, str]  # symbol → reason_code mapping
    timestamp: datetime
    total_symbols: int
    runnable_count: int
    skip_count: int
```

### 10.2 reason_code 정의

| Code | 의미 | would_run/skip |
|------|------|:--------------:|
| `RUNNABLE` | 실행 가능 | would_run |
| `NO_MARKET_DATA` | 최신 market data 없음 | would_skip |
| `NO_BACKTEST_READINESS` | backtest readiness 없음 | would_skip |
| `STALE_INPUT` | 입력 데이터 너무 오래됨 (>10분) | would_skip |
| `DUPLICATE_WINDOW` | 동일 window 내 중복 | would_skip |

### 10.3 로그 형식

```python
logger.info(
    "shadow_observation_dry_schedule_result",
    would_run=result.would_run,
    would_skip=result.would_skip,
    reason_codes=result.reason_codes,
    total_symbols=result.total_symbols,
    runnable_count=result.runnable_count,
    skip_count=result.skip_count,
)
```

---

## Part 11. 완료 기준 (Completion Criteria)

### 11.1 코드 기준 (18건)

| # | 기준 | 검증 방법 |
|---|------|-----------|
| 1 | `shadow_observation_tasks.py` 신규 생성 | 파일 존재 |
| 2 | DRY_SCHEDULE=True 하드코딩 | 소스 확인 |
| 3 | Redis lock 구현 (TTL=300s) | 테스트 |
| 4 | expires=240s 설정 | 소스 확인 |
| 5 | max_retries=0 설정 | 소스 확인 |
| 6 | would_run/would_skip/reason_code 출력 | 테스트 |
| 7 | observability 10필드 로그 출력 | 테스트 |
| 8 | consecutive_failures Redis counter | 테스트 |
| 9 | fail-closed: 모든 예외 시 write=0 | 테스트 |
| 10 | RETENTION_HOT_DAYS/WARM_DAYS/AUDIT_VERDICTS 상수 | 소스 확인 |
| 11 | purge 함수 미존재 | 소스 검사 |
| 12 | is_archived 모델 필드 추가 | 모델 확인 |
| 13 | is_archived 마이그레이션 | alembic 확인 |
| 14 | celery include에 모듈 추가 | 소스 확인 |
| 15 | beat_schedule에 주석 entry | 소스 확인 |
| 16 | SEALED 서비스 수정 0줄 | diff 확인 |
| 17 | FROZEN/RED 접촉 0건 | diff 확인 |
| 18 | 전체 회귀 PASS | pytest 실행 |

### 11.2 테스트 기준 (예상 ~20건)

| Class | 예상 tests | 검증 대상 |
|-------|:----------:|-----------|
| TestDryScheduleFlag | 3 | DRY_SCHEDULE=True, pipeline 호출 0, 출력 계약 |
| TestDryScheduleOutput | 4 | would_run/would_skip/reason_code 3필드 |
| TestRedisLock | 3 | lock 획득, 중복 방지, TTL |
| TestFailClosed | 3 | 각 실패 시나리오에서 write=0 |
| TestObservabilityFields | 3 | 10필드 로그 출력 검증 |
| TestRetentionPlanner | 2 | 상수 존재, purge 함수 미존재 |
| TestIsArchivedField | 2 | 모델 필드, default False |
| TestBeatEntryCommented | 1 | beat_schedule에 주석 확인 |
| TestSealedProtection | 2 | SEALED 서비스 hash 불변 |
| **총 예상** | **~23** | |

### 11.3 문서 기준 (3건)

| # | 문서 | 내용 |
|---|------|------|
| 1 | activation_manifest (초기 상태) | 모든 항목 false/true 초기값 |
| 2 | completion_evidence | 18 코드 기준 + 회귀 결과 |
| 3 | exception_register 항목 | RI-2A-2b 예외 (0건 예상) |

---

## Part 12. Final Decision Recommendation

### 12.1 종합 평가

| 항목 | 판정 |
|------|:----:|
| business write risk | ZERO |
| execution path risk | ZERO |
| gate change risk | ZERO |
| FROZEN/RED contact | ZERO |
| SEALED modification | ZERO |
| rollback cost | TRIVIAL |
| regression risk | LOW (신규 파일만) |
| 전체 판정 | **GO** |

### 12.2 추천

> **GO — RI-2A-2b 최소 구현 착수를 추천합니다.**
>
> 근거:
> 1. DRY_SCHEDULE=True 하드코딩 → 실제 pipeline 실행 없음
> 2. beat entry 주석 상태 → dispatch 없음
> 3. retention planner 정의만 → purge 없음
> 4. SEALED 서비스 수정 0줄
> 5. 모든 활성화 전환은 별도 A 승인 게이트

---

## A 판정 요청

| 판정 대상 | 선택지 |
|----------|--------|
| RI-2A-2b 구현 착수 | **GO / CONDITIONAL / HOLD** |
| 완료 기준 18건 | 승인 / 수정 |
| 예상 테스트 ~23건 | 승인 / 수정 |
| activation_manifest 도입 | 채택 / 보류 |
| retention 4단계 (planner only) | 채택 / 보류 |
| dry-schedule 출력 계약 | 채택 / 보류 |

---

```
CR-048 RI-2A-2b Design/Contract Package v1.0
Baseline: v2.4 (5430/5430 PASS)
Gate: LOCKED (변경 없음)
EXECUTION_ENABLED: False (무관)
DRY_SCHEDULE: True (하드코딩)
beat entry: 주석 상태 (dispatch 0)
retention: planner 정의만 (purge 0)
business write: ZERO
execution path: ZERO
SEALED modification: ZERO
FROZEN/RED contact: ZERO
New files: 3 (task, test, migration)
Modified files: 2 (model +1 field, celery_app +include +comment)
Completion criteria: 18 code + ~23 test + 3 doc
Recommendation: GO
```
