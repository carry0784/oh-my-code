# CR-048 RI-2A 범위 심사 패키지

**문서 ID:** RI2A-SCOPE-001
**작성일:** 2026-04-03
**전제 기준선:** v2.0 (5299/5299 PASS, RI-1 SEALED, RI-1A ACCEPT)
**전제 문서:**
- RI1-OBS-EVIDENCE-001 (Shadow 운영 검증)
- RI1A-ALIGN-EVIDENCE-001 (Threshold Alignment — verdict 100%)
- RI2-REENTRY-001 (RI-2 재심사 패키지)
**Authority:** A

---

## 1. RI-2A 목표

### 정의

RI-2A는 **실시간 read-through wrapper** 계층입니다.

| 속성 | RI-1 (현재) | RI-2A (본 심사) | RI-2B (보류) |
|------|:-----------:|:---------------:|:------------:|
| 입력 | curated batch | **실시간 data collection** | 실시간 |
| pipeline 실행 | shadow (pure) | shadow (pure) | shadow + runtime |
| 기존 결과 비교 | 수동 주입 | **DB read-through** | DB read-through |
| DB write | 0 | **0** | bounded write |
| state transition | 0 | **0** | bounded |
| fail reason 비교 | 없음 | **있음 (신규)** | 있음 |

### 한 문장 목표

> **RI-2A = "실시간 데이터로 shadow를 돌리고, DB에서 기존 결과를 읽어 비교하되, 아무것도 쓰지 않는다."**

### RI-2A가 해소하는 남은 조건

| 조건 | RI-1A 상태 | RI-2A 해소 방법 |
|------|:----------:|:---------------:|
| 72H 연속 실행 | 0H (이관됨) | Celery beat → shadow task 5분 주기 |
| fail reason 일치율 | 미측정 | reason-level 비교 로직 추가 |
| INSUFFICIENT 33.3% | 구조적 | 운영 데이터로 재측정 (DATA_REJECTED 비율 하락 예상) |

---

## 2. Wrapper / Read-through 구조도

### 2.1 전체 데이터 흐름

```
┌───────────────────────────────────────────────────────────────────┐
│  DATA COLLECTION (기존 Celery beat task, 변경 0줄)                 │
│  market_data_task → MarketDataSnapshot                            │
│  backtest_readiness_task → BacktestReadiness                      │
└──────────────────────┬────────────────────────────────────────────┘
                       │ 입력 (read-only)
                       v
┌───────────────────────────────────────────────────────────────────┐
│  RI-2A SHADOW WRAPPER (신규 — write 0, state change 0)            │
│                                                                    │
│  ┌──────────────────────────────────────────────────────┐         │
│  │ Step 1: run_shadow_pipeline()                        │         │
│  │   transform → screen → qualify → ShadowRunResult     │         │
│  │   (RI-1 SEALED pure function, 수정 0줄)               │         │
│  └──────────────────────────────────────────────────────┘         │
│                       │                                           │
│  ┌──────────────────────────────────────────────────────┐         │
│  │ Step 2: DB read-through (신규)                       │         │
│  │   SELECT screening_results WHERE symbol = ?           │         │
│  │   SELECT qualification_results WHERE symbol = ?       │         │
│  │   → ShadowComparisonInput 구성                        │         │
│  │   (READ ONLY — INSERT/UPDATE 0건)                     │         │
│  └──────────────────────────────────────────────────────┘         │
│                       │                                           │
│  ┌──────────────────────────────────────────────────────┐         │
│  │ Step 3: compare_shadow_to_existing() (확장)          │         │
│  │   verdict 비교 + fail reason 비교 (신규)              │         │
│  │   → ShadowRunResult + ComparisonVerdict               │         │
│  │   (pure function 확장, DB write 0)                    │         │
│  └──────────────────────────────────────────────────────┘         │
│                       │                                           │
│  ┌──────────────────────────────────────────────────────┐         │
│  │ Step 4: 관찰 기록 (신규)                              │         │
│  │   shadow_observation_log INSERT (append-only)         │         │
│  │   → 별도 observation 전용 테이블                       │         │
│  │   (shadow 결과 기록만, Symbol/Screening 테이블 무접촉)   │         │
│  └──────────────────────────────────────────────────────┘         │
│                                                                    │
│  Step 4는 유일한 DB write이며, 기존 테이블에 영향 없음              │
└───────────────────────────────────────────────────────────────────┘
```

### 2.2 "실시간 연결"과 "상태 반영"의 분리

| 행위 | RI-2A 허용 | 사유 |
|------|:----------:|------|
| data collection 결과 **읽기** | **O** | read-only, 기존 task 무수정 |
| run_shadow_pipeline() **호출** | **O** | RI-1 SEALED pure function |
| DB에서 기존 결과 **SELECT** | **O** | read-through, 기존 데이터 무변경 |
| compare_shadow_to_existing() **호출** | **O** | pure function (확장 포함) |
| shadow_observation_log **INSERT** | **O** | 별도 테이블, 기존 테이블 무접촉 |
| screening_results **INSERT** | **X** | RI-2B scope |
| qualification_results **INSERT** | **X** | RI-2B scope |
| symbols 테이블 **UPDATE** | **X** | RI-2B scope |
| Symbol.status **전이** | **X** | RI-2B scope |

---

## 3. Shadow 결과 ↔ 기존 결과 비교 흐름

### 3.1 비교 데이터 소스

| 데이터 | RI-1 (현재) | RI-2A (심사) |
|--------|:-----------:|:------------:|
| Shadow verdict | run_shadow_pipeline() | run_shadow_pipeline() (동일) |
| Existing screening | **수동 주입** (ShadowComparisonInput) | **DB SELECT** (screening_results 최신 행) |
| Existing qualification | **수동 주입** | **DB SELECT** (qualification_results 최신 행) |
| Existing fail reason | **없음** | **DB SELECT** (screening/qual fail reasons) |

### 3.2 비교 확장: fail reason 일치율

현재 `compare_shadow_to_existing()`은 verdict-level만 비교합니다.
RI-2A에서 reason-level 비교를 추가합니다.

```
현재 (RI-1):
  shadow_screen_passed != existing_screen_passed → VERDICT_MISMATCH
  shadow_qual_passed != existing_qual_passed → VERDICT_MISMATCH
  else → MATCH

확장 (RI-2A):
  위 + 추가:
  shadow_screen_passed == existing_screen_passed == False:
    shadow_screen_fail_reasons != existing_screen_fail_reasons → REASON_MISMATCH
  shadow_qual_passed == existing_qual_passed == False:
    shadow_qual_fail_reasons != existing_qual_fail_reasons → REASON_MISMATCH
  else → MATCH
```

### 3.3 INSUFFICIENT 처리 규칙

A 지시에 따라 INSUFFICIENT를 2종으로 분리합니다.

| 분류 | 코드 | 조건 | 의미 |
|------|------|------|------|
| **STRUCTURAL_INSUFFICIENT** | `INSUFFICIENT_STRUCTURAL` | shadow verdict = DATA_REJECTED | shadow가 데이터 품질 불량으로 판정 거부. 기존 결과와 비교 불가 (구조적) |
| **OPERATIONAL_INSUFFICIENT** | `INSUFFICIENT_OPERATIONAL` | existing_screening_passed = None (DB에 기존 결과 없음) | 기존 결과가 아직 생성되지 않음. 운영 경과에 따라 해소 |

**집계 규칙:**
- INSUFFICIENT < 20% 임계는 **OPERATIONAL_INSUFFICIENT만 대상** (STRUCTURAL은 pipeline 결함이 아님)
- STRUCTURAL_INSUFFICIENT는 별도 지표로 추적 (DATA_REJECTED 비율)
- 두 지표 모두 대시보드 표시

---

## 4. DB write 0 / State Change 0 보장 규칙

### 4.1 Write 경계

| 계층 | DB 행위 | 대상 테이블 | 허용 |
|------|---------|-----------|:----:|
| Shadow pipeline (pure) | 없음 | — | — |
| DB read-through | **SELECT only** | screening_results, qualification_results, symbols | **O** |
| Observation log | **INSERT only** | shadow_observation_log (**신규 테이블**) | **O** |
| Screening/Qual write | INSERT/UPDATE | screening_results, qualification_results, symbols | **X (RI-2B)** |

### 4.2 신규 테이블: shadow_observation_log

```python
class ShadowObservationLog(Base):
    __tablename__ = "shadow_observation_log"

    id: int                          # PK, auto
    symbol: str                      # 관찰 대상 symbol
    asset_class: str                 # CRYPTO / US_STOCK / KR_STOCK
    shadow_verdict: str              # qualified / screen_failed / qualify_failed / data_rejected
    comparison_verdict: str          # match / verdict_mismatch / reason_mismatch / insufficient_*
    shadow_timestamp: datetime       # shadow 실행 시각
    input_fingerprint: str           # 입력 해시
    existing_screening_passed: bool | None
    existing_qualification_passed: bool | None
    shadow_fail_reasons: str | None  # JSON
    existing_fail_reasons: str | None # JSON
    created_at: datetime             # 기록 시각
```

**이 테이블은:**
- 기존 테이블과 **FK 없음** (독립)
- **INSERT만 허용** (UPDATE/DELETE 금지 — append-only)
- symbols, screening_results, qualification_results 테이블에 **접촉 0**

### 4.3 접촉 금지 테이블 명시

| 테이블 | RI-2A 접촉 | 접촉 유형 |
|--------|:----------:|:---------:|
| symbols | **SELECT만** | read-through |
| screening_results | **SELECT만** | read-through |
| qualification_results | **SELECT만** | read-through |
| shadow_observation_log | **INSERT만** | append-only |
| promotion_states | **금지** | — |
| paper_sessions | **금지** | — |
| signals | **금지** | — |
| orders | **금지** | — |

### 4.4 코드 수준 보장

| 보장 방법 | 설명 |
|-----------|------|
| **DB session 분리** | shadow wrapper는 별도 read-only session 사용 (autocommit=False, read-only flag) |
| **observation log 전용 session** | INSERT용 별도 session (shadow_observation_log만 대상) |
| **테스트 검증** | mock DB에서 UPDATE/DELETE 호출 0회 확인 |
| **purity guard 확장** | shadow pipeline 함수의 purity 유지 확인 (기존 117 tests 보존) |

---

## 5. FROZEN / RED 접촉면 분석

### 5.1 FROZEN 함수 접촉 규칙

**"호출도 안 하는지" vs "호출만 허용":**

| FROZEN 함수 | RI-2A 접촉 | 규칙 |
|-------------|:----------:|------|
| `run_screening_qualification_pipeline()` | **호출** | RI-1에서 이미 호출 중. RI-2A에서도 동일 경로. 수정 0줄 |
| `transform_provider_to_screening()` | **호출** | 위와 동일 |
| `SymbolScreener.screen()` | **간접 호출** (pipeline 내부) | 수정 0줄 |
| `BacktestQualifier.qualify()` | **간접 호출** (pipeline 내부) | 수정 0줄 |
| `UniverseManager.select()` | **미접촉** | RI-2A scope 아님 |
| `screen_and_update()` | **미접촉** | RI-2B scope (DB write 포함) |
| `qualify_and_record()` | **미접촉** | RI-2B scope (DB write 포함) |

**핵심:** RI-2A는 FROZEN 함수를 **호출하되 수정하지 않는다**.
호출 자체는 RI-1에서 이미 검증된 경로이며, RI-2A에서 추가되는 것은 "입력 소스의 변경" (curated → 실시간)뿐입니다.

### 5.2 RED 파일 접촉 금지

| RED 파일 | RI-2A 접촉 |
|----------|:----------:|
| `app/services/multi_symbol_runner.py` | **금지** |
| `app/services/strategy_router.py` | **금지** |
| `app/services/regime_detector.py` | **금지** (CR-046) |
| `app/services/runtime_strategy_loader.py` | **금지** |
| `app/services/feature_cache.py` | **금지** |
| `workers/tasks/order_tasks.py` | **금지** |
| `exchanges/*` | **금지** |

### 5.3 수정 허용 파일

| 파일 | 수정 유형 | 사유 |
|------|-----------|------|
| `app/services/pipeline_shadow_runner.py` | **확장** | reason-level 비교 로직 추가, ComparisonVerdict 확장 |
| `app/models/shadow_observation.py` | **신규** | ShadowObservationLog 모델 |
| `app/services/shadow_observation_service.py` | **신규** | DB read-through + observation log 기록 |
| `workers/tasks/shadow_observation_tasks.py` | **신규** | Celery beat shadow task |
| `alembic/versions/0XX_shadow_observation_log.py` | **신규** | 신규 테이블 마이그레이션 |
| `tests/test_shadow_observation_*.py` | **신규** | RI-2A 테스트 |
| `tests/test_pipeline_shadow_runner.py` | **확장** | reason-level 비교 테스트 추가 |
| `tests/test_purity_guard.py` | **확장** | 신규 파일 purity 검증 (해당 시) |

---

## 6. 72H 실시간 검증 계획

### 6.1 검증 구조

```
Celery Beat (5분 주기)
  → shadow_observation_task.apply_async()
    → 각 symbol에 대해:
        1. DB에서 최신 MarketDataSnapshot 읽기 (data_collection 결과)
        2. DB에서 최신 BacktestReadiness 읽기
        3. run_shadow_pipeline() 실행 (pure)
        4. DB에서 기존 screening/qualification 결과 SELECT
        5. compare_shadow_to_existing() 실행 (pure, reason-level 포함)
        6. shadow_observation_log INSERT
```

### 6.2 72H 달성 조건

| 조건 | 임계 | 측정 방법 |
|------|------|-----------|
| 연속 실행 기간 | ≥ 72H | shadow_observation_log의 MIN(created_at) ~ MAX(created_at) |
| 실행 간격 누락 | ≤ 3회 (15분 이상 gap) | 연속 기록 간 시간차 분석 |
| symbol coverage | ≥ 20 (3 asset class 각 1+) | DISTINCT(symbol) in observation_log |
| task 성공률 | ≥ 95% | 성공 task / 전체 scheduled task |

### 6.3 72H 실행 중 금지 사항

| 금지 | 사유 |
|------|------|
| pipeline 코드 수정 | 72H 기간 중 코드 변경 시 재시작 필수 |
| threshold 변경 | 기준 변경 시 비교 의미 상실 |
| beat_schedule 직접 수정 | L4 변경 |
| 기존 screening/qualification 결과 수동 수정 | 비교 기준 훼손 |

---

## 7. Fail Reason 일치율 측정 계획

### 7.1 측정 대상

fail reason 일치율은 **같은 verdict를 가진 건 중에서 reason이 다른 비율**입니다.

```
fail_reason_match_rate = 1 - (REASON_MISMATCH / comparable_and_same_verdict)
```

### 7.2 비교 가능 조건

| 조건 | REASON 비교 수행 |
|------|:----------------:|
| shadow=qualified, existing=qualified | **비교 불필요** (PASS끼리는 reason 없음) |
| shadow=screen_failed, existing=screen_failed | **비교 수행** (fail reasons 비교) |
| shadow=qualify_failed, existing=qualify_failed | **비교 수행** (fail reasons 비교) |
| verdict 불일치 | **비교 불가** (VERDICT_MISMATCH로 분류) |
| INSUFFICIENT | **비교 불가** |

### 7.3 fail reason 데이터 소스

| 소스 | 필드 |
|------|------|
| Shadow screening | `ScreeningOutput.failed_stages` (list of stage names) |
| Shadow qualification | `QualificationOutput.failed_checks` (list of check names) |
| Existing screening (DB) | `screening_results.failed_stages` (JSON) |
| Existing qualification (DB) | `qualification_results.failed_checks` (JSON) |

### 7.4 REASON_MISMATCH 분류 규칙

| 상황 | 분류 |
|------|------|
| shadow fail_reasons == existing fail_reasons (집합 일치) | MATCH |
| shadow fail_reasons ⊂ existing fail_reasons (shadow가 부분집합) | REASON_MISMATCH |
| shadow fail_reasons ⊃ existing fail_reasons | REASON_MISMATCH |
| 교집합 없음 | REASON_MISMATCH |
| 하나라도 None | INSUFFICIENT |

---

## 8. Rollback / Fail-closed 규칙

### 8.1 Fail-closed 조건

| 조건 | 행동 |
|------|------|
| run_shadow_pipeline() 예외 발생 | shadow task SKIP, 로그 기록, 다음 주기 재시도 |
| DB read-through 실패 | OPERATIONAL_INSUFFICIENT 기록, shadow 결과만 보존 |
| compare 예외 발생 | INSUFFICIENT 기록, shadow 결과만 보존 |
| observation_log INSERT 실패 | stderr 로그, task 자체는 성공 처리 (observation 실패가 pipeline을 차단하면 안 됨) |
| VERDICT_MISMATCH > 5% (rolling 24H) | **자동 경고** + 운영자 리뷰 요청 (task는 계속 실행) |
| VERDICT_MISMATCH > 15% (rolling 24H) | **shadow task 일시 중단** + A 리뷰 필수 |

### 8.2 Rollback 비용

| 상황 | Rollback 내용 | 비용 |
|------|-------------|:----:|
| RI-2A 전체 철회 | shadow_observation_log 테이블 DROP, Celery task 제거, 신규 파일 삭제 | **TRIVIAL** |
| beat task만 중단 | beat_schedule에서 shadow task 제거 | **TRIVIAL** |
| reason 비교 로직만 철회 | pipeline_shadow_runner.py 확장 부분 revert | **TRIVIAL** |

**핵심:** RI-2A는 기존 테이블에 write 0이므로, rollback은 항상 trivial입니다.

### 8.3 RI-1 복귀 보장

RI-2A에 문제가 생겨도:
- RI-1 shadow pipeline (pure function)은 **영향 0** (코드 분리)
- 기존 5299 테스트는 **영향 0** (신규 파일만 추가)
- observation_log는 기존 테이블과 **FK 0** (DROP 가능)

---

## 9. RI-2A와 RI-2B 분리 기준

### 9.1 명확한 경계

| 기준 | RI-2A | RI-2B |
|------|:-----:|:-----:|
| **DB write 대상** | shadow_observation_log만 (신규) | screening_results, qualification_results, symbols |
| **기존 테이블 변경** | 0 | INSERT + UPDATE |
| **Symbol.status 전이** | 금지 | 허용 (bounded) |
| **FROZEN 함수 호출** | 금지 (pure pipeline만) | 허용 (screen_and_update, qualify_and_record) |
| **async 사용** | 필요 (DB read-through) | 필요 |
| **Celery task** | shadow observation task만 | screening/qualification task |
| **rollback 비용** | TRIVIAL | MEDIUM |

### 9.2 RI-2A → RI-2B 전환 조건

| # | 조건 | 임계 |
|---|------|------|
| 1 | RI-2A 봉인 완료 | A 승인 |
| 2 | 72H 연속 실행 완료 | ≥ 72H |
| 3 | verdict 일치율 (실시간) | ≥ 95% |
| 4 | fail reason 일치율 (실시간) | ≥ 90% |
| 5 | OPERATIONAL_INSUFFICIENT | < 20% |
| 6 | STRUCTURAL_INSUFFICIENT | < 40% (별도 추적) |
| 7 | 전체 회귀 PASS | N/N |
| 8 | 신규 예외 | max 1 |

### 9.3 RI-2B에서만 허용되는 것

| 행위 | RI-2B 조건 |
|------|-----------|
| screen_and_update() 호출 | shadow verdict == MATCH + comparison 검증 완료 |
| qualify_and_record() 호출 | shadow verdict == MATCH + comparison 검증 완료 |
| Symbol.status UPDATE | 기존 상태 → 새 상태 전이 규칙 준수 |
| ScreeningResult INSERT | shadow 결과와 일치 확인 후만 |
| FROZEN 함수 직접 호출 | 수정은 여전히 금지. 호출만 허용 |

---

## 10. 예상 신규 코드 / 테스트

### 10.1 신규 파일

| 파일 | 유형 | 설명 |
|------|------|------|
| `app/models/shadow_observation.py` | 모델 | ShadowObservationLog ORM |
| `app/services/shadow_observation_service.py` | 서비스 | DB read-through + shadow 실행 + observation log INSERT |
| `workers/tasks/shadow_observation_tasks.py` | Celery | 5분 주기 shadow observation task |
| `alembic/versions/0XX_shadow_observation_log.py` | 마이그레이션 | 신규 테이블 |

### 10.2 확장 파일

| 파일 | 변경 | 설명 |
|------|------|------|
| `app/services/pipeline_shadow_runner.py` | 확장 | ComparisonVerdict에 INSUFFICIENT_STRUCTURAL / INSUFFICIENT_OPERATIONAL 추가, reason-level 비교 |
| `tests/test_pipeline_shadow_runner.py` | 확장 | reason-level 비교 테스트 |
| `app/models/__init__.py` | 확장 | ShadowObservationLog import |

### 10.3 예상 테스트

| 테스트 Class | 예상 tests | 검증 대상 |
|-------------|:----------:|-----------|
| TestShadowObservationService | ~8 | read-through + shadow 실행 + log INSERT |
| TestShadowReadThrough | ~5 | DB SELECT로 기존 결과 조회 정확성 |
| TestReasonLevelComparison | ~6 | REASON_MISMATCH 감지 |
| TestInsufficientSplit | ~4 | STRUCTURAL vs OPERATIONAL 분류 |
| TestShadowObservationTask | ~4 | Celery task 등록, 실행, 에러 처리 |
| TestShadowObservationPurity | ~3 | 신규 서비스가 기존 Pure Zone 침범 안 함 |
| TestObservationLogAppendOnly | ~3 | INSERT만 허용, UPDATE/DELETE 차단 |
| TestFailClosed | ~4 | 예외 시 graceful degradation |
| **총 예상** | **~37** | |

### 10.4 기존 기준선 보호

| 보호 조치 | 상세 |
|-----------|------|
| FROZEN 함수 수정 0줄 | screen_and_update, qualify_and_record, pipeline 함수 무수정 |
| Pure Zone 10 files 무접촉 | 117 purity tests 유지 |
| 기존 5299 tests 회귀 | 전체 PASS 필수 |
| 기존 테이블 스키마 무변경 | 마이그레이션은 신규 테이블만 |

---

## 11. 종합

### 11.1 RI-2A 범위 요약

```
허용:
  ├─ data collection 결과 READ
  ├─ run_shadow_pipeline() 호출 (RI-1 SEALED pure)
  ├─ screening_results / qualification_results SELECT (read-through)
  ├─ compare_shadow_to_existing() 확장 (reason-level)
  ├─ shadow_observation_log INSERT (신규 테이블, append-only)
  └─ Celery shadow observation task (5분 주기)

금지:
  ├─ screening_results INSERT / UPDATE
  ├─ qualification_results INSERT / UPDATE
  ├─ symbols UPDATE
  ├─ Symbol.status 전이
  ├─ screen_and_update() 호출
  ├─ qualify_and_record() 호출
  ├─ FROZEN 함수 수정
  ├─ RED 파일 접촉
  └─ beat_schedule 기존 항목 변경
```

### 11.2 리스크 평가

| 리스크 | 수준 | 사유 |
|--------|:----:|------|
| 기존 데이터 훼손 | **ZERO** | write 0 (observation_log 제외) |
| 기존 코드 파괴 | **ZERO** | FROZEN 수정 0줄, 신규 파일만 추가 |
| Rollback 비용 | **TRIVIAL** | 신규 파일 삭제 + 테이블 DROP |
| 운영 간섭 | **ZERO** | shadow는 기존 pipeline과 독립 |
| 72H 실패 시 | **TRIVIAL** | task 중단, log 보존, RI-1으로 복귀 |

---

## A 판정 요청

| 판정 대상 | 선택지 |
|----------|--------|
| RI-2A 범위 | **본 문서 기준 승인 / 수정 요청 / 거부** |
| RI-2A 구현 GO | 범위 승인 후 별도 GO 필요 (본 문서는 범위 심사만) |
| INSUFFICIENT 2종 분리 | STRUCTURAL / OPERATIONAL 분리 승인 여부 |
| shadow_observation_log 신규 테이블 | 허용 여부 (유일한 DB write) |
| 72H Celery task | beat_schedule 추가 허용 여부 |

---

```
CR-048 RI-2A Scope Review Package v1.0
Baseline: v2.0 (5299/5299 PASS, RI-1 SEALED, RI-1A ACCEPT)
Scope: real-time read-through shadow observation
DB write: shadow_observation_log INSERT only (신규 테이블)
Existing table modification: ZERO
FROZEN function modification: ZERO lines
RED file access: ZERO
Rollback cost: TRIVIAL
Estimated new tests: ~37
72H plan: Celery beat 5분 주기 → shadow_observation_task
Fail reason measurement: reason-level comparison extension
INSUFFICIENT split: STRUCTURAL (DATA_REJECTED) vs OPERATIONAL (no existing data)
```
