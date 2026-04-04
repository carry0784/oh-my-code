# CR-048 RI-2A-2a 봉인 증빙 (Sealed Evidence)

**Stage**: RI-2A-2a (Shadow Observation Log — Append-only)
**Status**: SEALED
**Date**: 2026-04-04
**Authority**: A
**Baseline Transition**: v2.1 (5330) → v2.2 (5354)

---

## A 판정 이력

| 단계 | 판정 | 날짜 |
|------|------|------|
| RI-2A-2 Scope Review | ACCEPT → RI-2A-2a/2b 분리 | 2026-04-04 |
| RI-2A-2a Design/Contract | ACCEPT + IMPLEMENTATION GO (LIMITED) | 2026-04-04 |
| RI-2A-2a 구현 완료 보고 | ACCEPT | 2026-04-04 |
| RI-2A-2a 봉인 | **SEALED** | 2026-04-04 |

---

## 구현 범위

### 수정/생성 파일 (5개)

| 파일 | 작업 | 용도 |
|------|------|------|
| `app/models/shadow_observation.py` | **신규** | ShadowObservationLog ORM (append-only, FK 0, UNIQUE 0) |
| `app/services/shadow_observation_service.py` | **신규** | record_shadow_observation() — INSERT only |
| `alembic/versions/021_shadow_observation_log.py` | **신규** | CREATE TABLE + 3 indexes |
| `tests/test_shadow_observation.py` | **신규** | 24 tests (7 classes) |
| `app/models/__init__.py` | **수정** | ShadowObservationLog import 추가 |

**총 5개 파일** (신규 4, 수정 1). FROZEN/RED 접촉: **0**.

### 신규 테스트: 24개 (24/24 PASS)

| 테스트 파일 | 클래스 | 수 |
|------------|--------|:-:|
| test_shadow_observation.py | TestShadowObservationModel | 4 |
| | TestRecordObservation | 5 |
| | TestAppendOnlyGuarantee | 4 |
| | TestInsertFailureIsolation | 3 |
| | TestInputValidation | 3 |
| | TestDuplicateAllowed | 2 |
| | TestReasonComparisonSerialization | 3 |

---

## 완료 기준 11/11 충족

| # | 기준 | 결과 |
|---|------|:----:|
| 1 | Schema 구현 (15필드, FK 0, UNIQUE 0) | **PASS** |
| 2 | Append-only (INSERT만) | **PASS** |
| 3 | UPDATE/DELETE 금지 (경로 0) | **PASS** |
| 4 | Manual trigger only (beat/task 0) | **PASS** |
| 5 | Duplicate 허용 (insert 차단 안 함) | **PASS** |
| 6 | Business write 아님 (기존 테이블 write 0) | **PASS** |
| 7 | Failure 무영향 (insert 실패 → 본경로 영향 0) | **PASS** |
| 8 | FROZEN 수정 0줄 | **PASS** |
| 9 | RED 접촉 0건 | **PASS** |
| 10 | 신규 테스트 PASS | **PASS** (24/24) |
| 11 | 전체 회귀 PASS | **PASS** (5354/5354) |

---

## DDL / 스키마 요약

### shadow_observation_log 테이블 (15필드)

| 필드 | 타입 | nullable |
|------|------|:--------:|
| id | Integer (PK, auto) | N |
| symbol | String(32) | N |
| asset_class | String(16) | N |
| asset_sector | String(32) | N |
| shadow_verdict | String(32) | N |
| shadow_screening_passed | Boolean | Y |
| shadow_qualification_passed | Boolean | Y |
| comparison_verdict | String(32) | N |
| existing_screening_passed | Boolean | Y |
| existing_qualification_passed | Boolean | Y |
| reason_comparison_json | Text | Y |
| readthrough_failure_code | String(48) | Y |
| existing_screening_result_id | String(64) | Y |
| existing_qualification_result_id | String(64) | Y |
| input_fingerprint | String(64) | N |
| shadow_timestamp | DateTime(tz) | N |
| created_at | DateTime(tz) | N (server_default) |

**FK: 0. UNIQUE: 0. CASCADE: 0.**

### 인덱스 (3개)

| 인덱스 | 컬럼 |
|--------|------|
| ix_shadow_obs_symbol | (symbol) |
| ix_shadow_obs_created_at | (created_at) |
| ix_shadow_obs_verdict | (comparison_verdict, created_at) |

---

## RI-2A-2a 특성

| Property | Value |
|----------|:-----:|
| DB write | **INSERT only** (shadow_observation_log) |
| DB read | **0** (서비스 자체는 read 없음) |
| Business table write | **0** |
| State transition | **0** |
| New tables | **1** (shadow_observation_log) |
| New migrations | **1** (021_shadow_observation_log) |
| Celery/beat | **NONE** |
| FROZEN file contact | **0** |
| RED file contact | **0** |
| Trigger method | **Manual only** (pytest / script) |
| New warnings | **0** |
| Exceptions | **0** |

---

## Append-only 검증

| 검증 항목 | 결과 | 테스트 |
|-----------|:----:|--------|
| db.add() 호출 | 1회 (INSERT 시) | `test_only_add_called` |
| db.merge() 호출 | **0** | `test_no_merge_called` |
| db.delete() 호출 | **0** | `test_no_delete_called` |
| 서비스에 update/delete 메서드 | **없음** | `test_service_has_no_update_delete_methods` |
| grep UPDATE/DELETE (코드) | **0** (docstring 제외) | grep 검증 |

---

## INSERT Failure Isolation 검증

| 실패 유형 | 운영 영향 | 결과 | 테스트 |
|-----------|:---------:|:----:|--------|
| db.flush() 실패 | 0 | return None, 예외 미전파 | `test_flush_failure_returns_none` |
| db.add() 실패 | 0 | return None, 예외 미전파 | `test_add_failure_returns_none` |
| RuntimeError | 0 | return None, 예외 미전파 | `test_failure_does_not_raise` |
| shadow_result=None | 0 | return None, add 미호출 | `test_shadow_result_none` |
| readthrough_result=None | 0 | return None, add 미호출 | `test_readthrough_result_none` |

---

## RI-2A-2a 봉인 금지선 (Prohibitions)

| # | 금지 사항 |
|---|----------|
| 1 | RI-2A-2a는 **append-only observation write 전용** — business table write 금지 |
| 2 | UPDATE/DELETE **영구 금지** — observation row 수정/삭제 경로 없음 |
| 3 | beat / Celery 자동 실행 금지 — manual trigger only |
| 4 | observation 결과의 **운영 반영 금지** — 자동 승격/차단/promotion 판단 근거 아님 |
| 5 | 집계 시 dedup 가능하더라도 **원본 row 수정 금지** |
| 6 | ComparisonVerdict는 **관찰 지표** — 운영 판단 근거 아님 |
| 7 | FROZEN 수정 금지 (pipeline_shadow_runner.py, shadow_readthrough.py 등) |
| 8 | RED 접촉 금지 (exchanges/*, order_tasks, market_tasks, multi_symbol_runner) |
| 9 | RI-2A-2b 진입은 **별도 A 심사 필수** |
| 10 | Retention/purge 구현은 **RI-2A-2b 범위** — RI-2A-2a에서 금지 |

---

## Dedupe Key 문서화

| 용도 | Dedupe Key | 비고 |
|------|-----------|------|
| 집계 시 중복 제거 | `(symbol, input_fingerprint, shadow_timestamp)` | 동일 입력+시각 → 같은 관측 |
| 쿼리 시 최신 관측 | `ORDER BY created_at DESC LIMIT 1` | 최신 1건만 참조 |

**원본 row는 절대 수정/삭제하지 않음. dedup은 쿼리 시점에만 적용.**

---

## 회귀 결과

| Metric | Value |
|--------|:-----:|
| Total tests | **5354** |
| Passed | **5354** |
| Failed | **0** |
| Warnings | **10** (PRE-EXISTING OBS-001) |
| New warnings | **0** |
| New exceptions | **0** |

---

## 봉인 경계 선언

> **RI-2A-2a는 관찰 전용 봉인 단계이며, 어떠한 운영 write path / 자동 실행 / retention 행위도 포함하지 않는다.**

---

## 봉인 서명

```
RI-2A-2a Shadow Observation Log (Append-only): SEALED
Authority: A
Date: 2026-04-04
Baseline: v2.1 → v2.2
Regression: 5354/5354 PASS
Prohibitions: 10 items enforced
business_impact: false
Next: RI-2A-2b DEFERRED / 별도 A 범위 심사 필수
```
