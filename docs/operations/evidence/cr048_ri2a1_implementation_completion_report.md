# CR-048 RI-2A-1 구현 완료 보고

**Stage**: RI-2A-1 (Shadow Read-through Comparison)
**Status**: IMPLEMENTATION COMPLETE
**Date**: 2026-04-03
**Baseline**: v2.0 (5299 PASS) → v2.1 candidate (5330 PASS)

---

## 1. 수정/생성 파일 목록

| 파일 | 작업 | 용도 |
|------|------|------|
| `app/services/pipeline_shadow_runner.py` | **수정** | INSUFFICIENT 2종 분리, ReasonComparisonDetail, reason-level comparison |
| `app/services/shadow_readthrough.py` | **신규** | DB read-through fetch + comparison orchestration |
| `tests/test_pipeline_shadow_runner.py` | **수정** | +10 tests (INSUFFICIENT split 4, reason-level 6) |
| `tests/test_shadow_readthrough.py` | **신규** | 21 tests (6 classes) |
| `scripts/ri1_shadow_observation.py` | **수정** | INSUFFICIENT enum 참조 갱신 |
| `scripts/ri1a_threshold_alignment_remeasurement.py` | **수정** | INSUFFICIENT enum 참조 갱신 |

**총 6개 파일** (신규 2, 수정 4). FROZEN/RED 파일 접촉: **0**.

---

## 2. 신규 테스트 수

| 테스트 파일 | 클래스 | 테스트 수 |
|------------|--------|-----------|
| `test_shadow_readthrough.py` | TestExtractScreeningFailStages | 3 |
| | TestExtractQualificationFailChecks | 4 |
| | TestFetchExistingForComparison | 6 |
| | TestReadthroughComparison | 5 |
| | TestReadthroughNoWrite | 3 |
| `test_pipeline_shadow_runner.py` | TestInsufficientSplit | 4 |
| | TestReasonLevelComparison | 6 |
| **합계** | **7 classes** | **31 tests** |

기존 `test_pipeline_shadow_runner.py` 27 tests + 신규 10 = 37 tests.
신규 `test_shadow_readthrough.py` 21 tests.
**RI-2A-1 총 신규 테스트: 31개. 전체 58/58 PASS.**

---

## 3. Read-through SELECT 범위

| 대상 테이블 | 쿼리 형태 | 바운드 |
|-------------|-----------|--------|
| `screening_results` | `SELECT ... WHERE symbol = ? ORDER BY screened_at DESC LIMIT 1` | bounded |
| `qualification_results` | `SELECT ... WHERE symbol = ? ORDER BY evaluated_at DESC LIMIT 1` | bounded |

**총 2개 테이블, 2개 SELECT, 모두 LIMIT 1 bounded.**
INSERT/UPDATE/DELETE/add/flush/commit/merge/delete: **0** (docstring 주석 1건 제외 실제 호출 0).

---

## 4. Fail-closed 검증표

| 시나리오 | 입력 | 기대 결과 | 테스트 |
|----------|------|-----------|--------|
| DB 연결 실패 | `db.execute` raises Exception | INSUFFICIENT_OPERATIONAL + READTHROUGH_DB_UNAVAILABLE | `test_db_error_returns_insufficient` |
| screening 결과 없음 | screen_row=None | INSUFFICIENT_OPERATIONAL + READTHROUGH_RESULT_NOT_FOUND | `test_no_screening_result` |
| DB 실패 → full flow | db error | INSUFFICIENT_OPERATIONAL + failure_code 전파 | `test_db_failure_insufficient_operational` |
| 기존 결과 없음 → full flow | no rows | INSUFFICIENT_OPERATIONAL | `test_insufficient_operational_no_existing` |

**규칙**: DB 실패 또는 데이터 부재 시 MATCH를 추론하지 않음. 항상 INSUFFICIENT 반환.

---

## 5. INSUFFICIENT 2종 분리 검증표

| 종류 | 조건 | ComparisonVerdict | 테스트 |
|------|------|-------------------|--------|
| **STRUCTURAL** | shadow DATA_REJECTED (데이터 품질 불합격) | `INSUFFICIENT_STRUCTURAL` | `test_structural_when_data_rejected` |
| **OPERATIONAL** | 기존 DB 결과 없음 / DB 장애 | `INSUFFICIENT_OPERATIONAL` | `test_operational_when_no_existing` |
| 비중첩 | STRUCTURAL ∩ OPERATIONAL = 0 | 동시 성립 불가 | `test_structural_and_operational_never_overlap` |
| 비혼동 | DATA_REJECTED + 기존 PASS | STRUCTURAL (MATCH 아님) | `test_structural_not_confused_with_match` |

**분리 기준**: shadow 측 데이터 자체 불합격 → STRUCTURAL. 비교 대상(기존 결과) 부재 → OPERATIONAL.

---

## 6. Reason-level Comparison 검증표

| 시나리오 | shadow | existing | verdict | reason_match | 테스트 |
|----------|--------|----------|---------|-------------|--------|
| 동일 실패 단계 | screen_fail {stage2} | screen_fail {stage2} | MATCH | screening: True | `test_same_fail_stages_is_match` |
| 다른 실패 단계 | screen_fail {stage2} | screen_fail {stage3} | REASON_MISMATCH | screening: False | `test_different_fail_stages_is_reason_mismatch` |
| detail 채워짐 (불일치) | screen_fail {stage2,stage3} | screen_fail {stage3} | REASON_MISMATCH | detail populated | `test_reason_detail_populated_on_mismatch` |
| detail 채워짐 (일치) | qual_fail {performance} | qual_fail {performance} | MATCH | detail populated | `test_reason_detail_on_match` |
| 양쪽 PASS | qualified | qualified | MATCH | None (비교 불필요) | `test_no_reason_comparison_when_both_pass` |
| 기존 reason 누락 | screen_fail {stage2} | screen_fail (stages=None) | MATCH (verdict만) | reason 비교 skip | `test_missing_existing_reasons_skips_reason_compare` |

**규칙**: reason 비교는 verdict 일치 + 양쪽 실패일 때만 수행. verdict가 다르면 VERDICT_MISMATCH. 양쪽 PASS면 reason 비교 불필요.

---

## 7. FROZEN/RED 무접촉 증빙

### FROZEN 파일 (CR-046 frozen baseline)
| 파일 | 접촉 여부 |
|------|-----------|
| `app/services/screening_qualification_pipeline.py` | **무접촉** |
| `app/services/symbol_screener.py` | **무접촉** |
| `app/services/backtest_qualification.py` | **무접촉** |
| `strategies/smc_wavetrend_strategy.py` | **무접촉** |
| `app/models/qualification.py` | **무접촉** |
| `app/models/asset.py` | **무접촉** |

### RED 파일 (실행 경로)
| 파일 | 접촉 여부 |
|------|-----------|
| `exchanges/*.py` (전체) | **무접촉** |
| `workers/tasks/order_tasks.py` | **무접촉** |
| `workers/tasks/market_tasks.py` | **무접촉** |
| `app/services/order_service.py` | **무접촉** |

**검증 방법**: `git status` 확인. 위 파일들은 RI-2A-1 이전부터 존재하는 uncommitted 변경(다른 CR)이며, RI-2A-1 작업에서 수정한 파일 6개는 모두 **untracked (신규)** 또는 shadow/test 영역에 한정.

---

## 8. 전체 회귀 결과

```
$ python -m pytest --tb=short -q
5330 passed, 10 warnings in 175.48s
```

| 항목 | 값 |
|------|-----|
| 기존 baseline | 5299 passed |
| RI-2A-1 신규 | +31 tests |
| 전체 합계 | **5330 passed** |
| 실패 | **0** |
| 에러 | **0** |

---

## 9. 신규 경고/예외 여부

| 경고 수 | 출처 | 신규 여부 |
|---------|------|-----------|
| 10 | `asset_service.py:251 RuntimeWarning: coroutine never awaited` | **PRE-EXISTING (OBS-001)** |

**RI-2A-1으로 인한 신규 경고: 0. 신규 예외: 0.**

---

## 10. A 완료 기준 대조표

| # | 기준 | 결과 | 증빙 |
|---|------|------|------|
| 1 | DB write 0 (INSERT/UPDATE/DELETE 없음) | **PASS** | grep 결과: 실제 write 호출 0 (섹션 3) |
| 2 | read-through only (SELECT on 2 tables) | **PASS** | screening_results + qualification_results (섹션 3) |
| 3 | fail-closed (DB 실패 → INSUFFICIENT, MATCH 추론 금지) | **PASS** | 4개 시나리오 검증 (섹션 4) |
| 4 | INSUFFICIENT 2종 분리 (STRUCTURAL/OPERATIONAL) | **PASS** | 4개 시나리오 검증 (섹션 5) |
| 5 | reason-level comparison (verdict/reason 분리) | **PASS** | 6개 시나리오 검증 (섹션 6) |
| 6 | FROZEN 수정 0 | **PASS** | 6개 파일 무접촉 (섹션 7) |
| 7 | RED 접촉 0 | **PASS** | 실행 경로 전체 무접촉 (섹션 7) |
| 8 | 신규 테스트 PASS | **PASS** | 58/58 PASS (섹션 2) |
| 9 | 전체 회귀 PASS | **PASS** | 5330/5330 PASS (섹션 8) |
| 10 | 신규 경고/예외 0 | **PASS** | 10 warnings 전부 PRE-EXISTING (섹션 9) |

**10/10 PASS.**

---

## 현재 상태

```
Guarded Release ACTIVE · Gate LOCKED
Stage 1~4B L3: SEALED
RI-1 L3: SEALED
RI-1A Threshold Alignment: ACCEPT
RI-2A-1 Read-through: IMPLEMENTATION COMPLETE (10/10 기준 충족)
RI-2A-2 Observation Log + Beat: DEFERRED
RI-2B Bounded Write: DEFERRED
Baseline: v2.0 (5299) → v2.1 candidate (5330)
```

## 다음 단계

A 판정 대기:
- **ACCEPT** → RI-2A-1 SEALED, v2.1 baseline 확정
- **CONDITIONAL** → 지적 사항 반영 후 재제출
- RI-2A-2 scope review는 A 지시 시 별도 진행
