# CR-048 RI-2A-1 봉인 증빙 (Sealed Evidence)

**Stage**: RI-2A-1 (Shadow Read-through Comparison)
**Status**: SEALED
**Date**: 2026-04-03
**Authority**: A
**Baseline Transition**: v2.0 (5299) → v2.1 (5330)

---

## A 판정 이력

| 단계 | 판정 | 날짜 |
|------|------|------|
| RI-2A Scope Review | CONDITIONAL ACCEPT → RI-2A-1/2A-2 분리 | 2026-04-03 |
| RI-2A-1 Design/Contract | ACCEPT + IMPLEMENTATION GO (LIMITED) | 2026-04-03 |
| RI-2A-1 구현 완료 보고 | ACCEPT | 2026-04-03 |
| RI-2A-1 봉인 | **SEALED** | 2026-04-03 |

---

## 구현 범위

### 수정/생성 파일 (6개)

| 파일 | 작업 | 용도 |
|------|------|------|
| `app/services/pipeline_shadow_runner.py` | 수정 | INSUFFICIENT 2종 분리, ReasonComparisonDetail, reason-level comparison |
| `app/services/shadow_readthrough.py` | **신규** | DB read-through fetch + comparison orchestration |
| `tests/test_pipeline_shadow_runner.py` | 수정 | +10 tests (INSUFFICIENT split 4, reason-level 6) |
| `tests/test_shadow_readthrough.py` | **신규** | 21 tests (6 classes) |
| `scripts/ri1_shadow_observation.py` | 수정 | INSUFFICIENT enum 참조 갱신 |
| `scripts/ri1a_threshold_alignment_remeasurement.py` | 수정 | INSUFFICIENT enum 참조 갱신 |

### 신규 테스트: 31개 (58/58 PASS)

| 테스트 파일 | 클래스 | 수 |
|------------|--------|:-:|
| test_shadow_readthrough.py | TestExtractScreeningFailStages | 3 |
| | TestExtractQualificationFailChecks | 4 |
| | TestFetchExistingForComparison | 6 |
| | TestReadthroughComparison | 5 |
| | TestReadthroughNoWrite | 3 |
| test_pipeline_shadow_runner.py | TestInsufficientSplit | 4 |
| | TestReasonLevelComparison | 6 |

---

## 완료 기준 10/10 충족

| # | 기준 | 결과 |
|---|------|:----:|
| 1 | DB write 0 (INSERT/UPDATE/DELETE 없음) | **PASS** |
| 2 | read-through only (SELECT on screening_results + qualification_results) | **PASS** |
| 3 | fail-closed (DB 실패 → INSUFFICIENT, MATCH 추론 금지) | **PASS** |
| 4 | INSUFFICIENT 2종 분리 (STRUCTURAL/OPERATIONAL) | **PASS** |
| 5 | reason-level comparison (verdict/reason 분리) | **PASS** |
| 6 | FROZEN 수정 0 | **PASS** |
| 7 | RED 접촉 0 | **PASS** |
| 8 | 신규 테스트 PASS | **PASS** (58/58) |
| 9 | 전체 회귀 PASS | **PASS** (5330/5330) |
| 10 | 신규 경고/예외 0 | **PASS** |

---

## Read-through SELECT 범위

| 테이블 | 쿼리 | 바운드 |
|--------|------|:------:|
| `screening_results` | WHERE symbol = ? ORDER BY screened_at DESC LIMIT 1 | bounded |
| `qualification_results` | WHERE symbol = ? ORDER BY evaluated_at DESC LIMIT 1 | bounded |

**총 2 테이블, 2 SELECT, LIMIT 1 bounded. INSERT/UPDATE/DELETE: 0.**

---

## RI-2A-1 특성

| Property | Value |
|----------|:-----:|
| DB write | **0** |
| DB read | **2 SELECT** (bounded LIMIT 1) |
| State transition | **0** |
| New tables / migration | **0** |
| Celery/beat | **NONE** |
| FROZEN file contact | **0** |
| RED file contact | **0** |
| Async functions added | **1** (fetch_existing_for_comparison, shadow_readthrough.py) |
| Pure Zone files | **10** (unchanged) |
| New warnings | **0** |
| Exceptions | **0** |

---

## RI-2A-1 봉인 금지선 (Prohibitions)

| # | 금지 사항 |
|---|----------|
| 1 | RI-2A-1은 **read-through only** — DB write 금지 |
| 2 | 신규 테이블/마이그레이션 금지 |
| 3 | reason-level comparison은 **비교용** — 운영 반영 근거로 사용 금지 |
| 4 | FROZEN 수정 금지 |
| 5 | RED 접촉 금지 |
| 6 | RI-2A-1은 **RI-2A-2 이전의 무상태 비교 계층** — 운영 반영 계층 아님 |
| 7 | read-through 쿼리는 **bounded query 계약** 고정 — 무제한 조회 금지 |
| 8 | ComparisonVerdict는 **관찰 지표** — 자동 승격/차단 판단 근거 아님 |
| 9 | shadow_readthrough.py → 실행 경로 삽입 금지 |
| 10 | RI-2A-2 진입은 별도 A 범위 심사 필수 |

---

## 회귀 결과

| Metric | Value |
|--------|:-----:|
| Total tests | **5330** |
| Passed | **5330** |
| Failed | **0** |
| Warnings | **10** (PRE-EXISTING OBS-001) |
| New warnings | **0** |
| New exceptions | **0** |

---

## 봉인 서명

```
RI-2A-1 Shadow Read-through Comparison: SEALED
Authority: A
Date: 2026-04-03
Baseline: v2.0 → v2.1
Regression: 5330/5330 PASS
Prohibitions: 10 items enforced
Next: RI-2A-2 DEFERRED / 별도 A 범위 심사 필수
```
