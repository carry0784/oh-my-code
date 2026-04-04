# CR-048 RI-2 재심사 패키지

**문서 ID:** RI2-REENTRY-001
**작성일:** 2026-04-03
**전제 기준선:** v2.0 (5299/5299 PASS, RI-1 SEALED)
**Authority:** A

---

## 1. RI-2 목표

### 무엇을 write-path에 연결하려는가

RI-1은 sealed Pure Zone 자산만으로 구성된 **read-only shadow pipeline**입니다.
RI-2는 이 shadow pipeline의 결과를 **기존 runtime entry point에 연결**하여,
pipeline 결과가 실제 DB 상태(screening_result, qualification_result, symbol status)에
반영되도록 하는 **bounded write-path**입니다.

구체적으로:
- `run_shadow_pipeline()` → `screen_and_update()` 입력 생성
- `run_shadow_pipeline()` → `qualify_and_record()` 입력 생성
- shadow comparison → runtime 결과와 대조 검증

### 왜 지금 열어야 하는가

**결론: 지금 열면 안 됩니다. 아래 분석 참조.**

현재 RI-1이 봉인된 직후이고, shadow pipeline의 운영 검증 데이터가 아직 없습니다.
RI-2를 열려면 shadow 결과의 안정성(verdict 일치율, fail reason 일치율)이
숫자로 검증되어야 합니다.

---

## 2. 진입 조건표

### RI-2 진입 필수 조건 (전부 충족해야 진입 가능)

| # | 조건 | 임계 | 현재 상태 | 충족 |
|---|------|------|----------|:----:|
| 1 | RI-1 shadow verdict 일치율 | ≥ 95% (MATCH / total ≥ 0.95) | **측정 불가** (운영 데이터 없음) | **X** |
| 2 | RI-1 shadow fail reason 일치율 | ≥ 90% (REASON_MISMATCH < 10%) | **측정 불가** | **X** |
| 3 | RI-1 shadow symbol coverage | ≥ 20 symbols (CRYPTO + US_STOCK + KR_STOCK 각 1종 이상) | **0 symbols** | **X** |
| 4 | RI-1 shadow 연속 실행 기간 | ≥ 72H (beat 또는 수동, 3일 이상) | **0H** | **X** |
| 5 | INSUFFICIENT_EXISTING_DATA 비율 | < 20% | **측정 불가** | **X** |
| 6 | Carried exception 허용 | max 1건 (PRE-EXISTING only) | 0건 | O |
| 7 | 전체 회귀 PASS | 5299/5299 유지 | 5299/5299 | O |
| 8 | RI-1 SEALED 상태 | 봉인 완료 | **SEALED** | O |

**현재 충족: 3/8. 진입 불가.**

### 측정 방법

| 조건 | 측정 방법 |
|------|----------|
| verdict 일치율 | shadow runner를 기존 screen_and_update/qualify_and_record 결과와 대조. 수동 스크립트 또는 테스트 harness |
| fail reason 일치율 | REASON_MISMATCH 빈도 = (reason 불일치 건) / (비교 가능 건) |
| symbol coverage | shadow runner에 입력한 고유 symbol 수 |
| 연속 실행 기간 | shadow runner 로그의 첫 timestamp ~ 마지막 timestamp |
| INSUFFICIENT 비율 | INSUFFICIENT_EXISTING_DATA / total shadow runs |

---

## 3. 후보 호출 지점

### 3-1. screen_and_update() — asset_service.py L348

| 항목 | 분석 |
|------|------|
| **함수** | `AssetService.screen_and_update(symbol_id, screening_input, screener?)` |
| **계층** | Data Plane (async, DB write) |
| **현재 상태** | FROZEN (Stage 2B 이후 수정 금지) |
| **내부 동작** | (1) DB에서 Symbol 조회 (2) SymbolScreener.screen() 호출 (3) ScreeningResult DB 기록 (4) Symbol.status 업데이트 (5) TTL 설정 (6) db.flush() |
| **write 가능성** | **HIGH** — ScreeningResult INSERT + Symbol UPDATE |
| **rollback 난이도** | **MEDIUM** — DB 기록 삭제 + status revert 필요 |
| **fail-closed 가능성** | **있음** — SymbolScreener.screen()은 pure이지만, DB write는 비가역적 |
| **위험도** | **HIGH** |

### 3-2. qualify_and_record() — asset_service.py L414

| 항목 | 분석 |
|------|------|
| **함수** | `AssetService.qualify_and_record(symbol_id, qualification_input, qualifier?)` |
| **계층** | Data Plane (async, DB write) |
| **현재 상태** | FROZEN (Stage 2B 이후 수정 금지) |
| **내부 동작** | (1) DB에서 Symbol 조회 (2) EXCLUDED 차단 (3) BacktestQualifier.qualify() 호출 (4) QualificationResult DB 기록 (5) Symbol.qualification_status 업데이트 (6) db.flush() |
| **write 가능성** | **HIGH** — QualificationResult INSERT + Symbol UPDATE |
| **rollback 난이도** | **MEDIUM** — DB 기록 삭제 + qualification_status revert |
| **fail-closed 가능성** | **있음** — qualify()는 pure이지만, DB write는 비가역적 |
| **위험도** | **HIGH** |

### 3-3. run_screening_qualification_pipeline() — screening_qualification_pipeline.py

| 항목 | 분석 |
|------|------|
| **함수** | `run_screening_qualification_pipeline(transform_result, backtest, ...)` |
| **계층** | Pure Zone (sync, no DB) |
| **현재 상태** | SEALED (Stage 4A, 8th Pure Zone) |
| **내부 동작** | Pure composition: FC-0→FC-1→FC-2→Screen→FC-3→Qualify→FC-4→FC-5 |
| **write 가능성** | **ZERO** — pure function |
| **rollback 난이도** | **N/A** |
| **위험도** | **ZERO** |

### 3-4. UniverseManager.select() — universe_manager.py

| 항목 | 분석 |
|------|------|
| **함수** | `UniverseManager.select(candidates, now_utc)` |
| **계층** | Pure Zone (sync, no DB) |
| **현재 상태** | SEALED (Stage 4B, 9th Pure Zone) |
| **write 가능성** | **ZERO** — pure function |
| **위험도** | **ZERO** |

### 3-5. MultiSymbolRunner.run_cycle() — multi_symbol_runner.py

| 항목 | 분석 |
|------|------|
| **함수** | `MultiSymbolRunner.run_cycle()` |
| **계층** | Data Plane (orchestration) |
| **현재 상태** | RED (접촉 금지) |
| **내부 동작** | 다종목 × 다전략 병렬 실행, 신호 생성, DB write |
| **write 가능성** | **VERY HIGH** — 신호, 주문 생성 |
| **위험도** | **CRITICAL** |

### Runtime Entry Risk Matrix

| 호출 대상 | write 가능성 | rollback 난이도 | fail-closed 가능 | RI-2 후보 |
|-----------|:-----------:|:-------------:|:---------------:|:---------:|
| `run_screening_qualification_pipeline()` | ZERO | N/A | YES | **이미 RI-1에 포함** |
| `UniverseManager.select()` | ZERO | N/A | YES | **이미 RI-1에 포함** |
| `screen_and_update()` | HIGH | MEDIUM | YES (pure core) | **RI-2A 후보** |
| `qualify_and_record()` | HIGH | MEDIUM | YES (pure core) | **RI-2A 후보** |
| `MultiSymbolRunner.run_cycle()` | VERY HIGH | HIGH | PARTIAL | **RI-2B 또는 별도 CR** |

---

## 4. 허용 접촉면 / 금지 접촉면

### RI-2A (bounded wrapper / read-through) — 우선 심사

| 파일 | 허용 | 금지 |
|------|:----:|:----:|
| `app/services/pipeline_shadow_runner.py` | **확장** (wrapper 추가) | 순수성 파괴 |
| `app/services/asset_service.py` | **읽기** (screen_and_update/qualify_and_record 호출) | **수정 금지** (FROZEN) |
| `tests/test_pipeline_shadow_runner.py` | **확장** (비교 테스트 추가) | — |
| `tests/test_purity_guard.py` | **확장** (필요 시) | — |
| `app/services/screening_qualification_pipeline.py` | **읽기** | **수정 금지** (FROZEN) |
| `app/services/screening_transform.py` | **읽기** | **수정 금지** (FROZEN) |
| 기타 8 Pure Zone files | **읽기** | **수정 금지** (FROZEN) |

| 파일 | 허용 | 금지 |
|------|:----:|:----:|
| `app/services/multi_symbol_runner.py` | — | **접촉 금지** (RED) |
| `app/services/strategy_router.py` | — | **접촉 금지** (RED) |
| `app/services/regime_detector.py` | — | **접촉 금지** (RED, CR-046) |
| `app/services/runtime_strategy_loader.py` | — | **접촉 금지** (RED) |
| `app/services/feature_cache.py` | — | **접촉 금지** (RED) |
| `workers/*` | — | **접촉 금지** (RED) |
| `exchanges/*` | — | **접촉 금지** (RED) |

### RI-2B (bounded write enable) — 후속 심사

RI-2A 봉인 후에만 심사.
RI-2B에서 추가로 허용할 수 있는 후보:

| 후보 | 성격 | 조건 |
|------|------|------|
| shadow → screen_and_update 입력 매핑 함수 | wrapper (pure) | RI-2A shadow 일치율 ≥ 95% |
| shadow → qualify_and_record 입력 매핑 함수 | wrapper (pure) | RI-2A 위와 동일 |
| 실제 screen_and_update 호출 (DB write) | write-path | RI-2A 봉인 + A 승인 |
| 실제 qualify_and_record 호출 (DB write) | write-path | RI-2A 봉인 + A 승인 |

---

## 5. Bounded write-path 정의

### 5-1. "호출 허용"과 "상태 반영 허용"의 분리

| 단계 | 허용 범위 | write 발생 |
|------|----------|:----------:|
| **RI-2A: wrapper/read-through** | shadow → FROZEN 함수 호출 (pure core), 결과 비교 로직 | **NO** |
| **RI-2B: bounded write enable** | screen_and_update / qualify_and_record 호출 허용 | **YES** |

### 5-2. RI-2A에서 생기는 write

**없음.** RI-2A는:
- shadow pipeline 결과 → screen_and_update/qualify_and_record **입력 형식으로 매핑**만 수행
- 실제 DB write는 RI-2B에서만 허용
- RI-2A는 "이 입력으로 호출하면 결과가 일치하는가"를 검증하는 단계

### 5-3. RI-2B에서 생기는 write

| write 대상 | 테이블 | 성격 | 허용 조건 |
|-----------|--------|------|-----------|
| ScreeningResult INSERT | screening_results | append-only | shadow verdict == MATCH 일 때만 |
| Symbol.status UPDATE | symbols | 상태 전이 | shadow → 기존 일치 확인 후만 |
| Symbol.candidate_expire_at UPDATE | symbols | TTL 갱신 | screen 성공 시만 |
| QualificationResult INSERT | qualification_results | append-only | shadow verdict == MATCH 일 때만 |
| Symbol.qualification_status UPDATE | symbols | 상태 전이 | 위와 동일 |

### 5-4. 여전히 금지인 write

| 금지 write | 사유 |
|-----------|------|
| Symbol.status → CORE 직행 (EXCLUDED에서) | STATUS_TRANSITION_RULES 위반 |
| PromotionState 전이 | Phase 4+ 범위 |
| Signal INSERT | MultiSymbolRunner 범위 (RED) |
| Order INSERT | OrderExecutor 범위 (RED) |
| beat_schedule 변경 | L4 |
| exchange_mode 변경 | L4 |

---

## 6. Fail-closed / Rollback 계획

### Mismatch 발생 시 즉시 중단 규칙

| 조건 | 행동 |
|------|------|
| shadow verdict ≠ runtime verdict | 즉시 중단, 불일치 로그, 수동 리뷰 |
| shadow QUALIFIED + runtime SCREEN_FAILED | 즉시 중단, screening 로직 불일치 조사 |
| shadow DATA_REJECTED + runtime proceed | 즉시 중단, transform 로직 불일치 조사 |
| VERDICT_MISMATCH 비율 > 5% (rolling 24H) | RI-2 전체 중단, RI-1 shadow-only 복귀 |

### Shadow fallback 규칙

| 상황 | 행동 |
|------|------|
| RI-2 write-path 장애 | shadow-only 모드로 자동 복귀 (RI-1 상태) |
| DB 장애 | write 중단, shadow 로그만 기록 |
| Pure core 예외 발생 | shadow + runtime 모두 중단, 원인 분석 |

### Rollback 비용

| RI-2 단계 | rollback 내용 | 비용 |
|-----------|-------------|------|
| RI-2A (wrapper only) | wrapper 함수 삭제, 테스트 삭제 | **TRIVIAL** |
| RI-2B (bounded write) | DB 기록 정리 + symbol status 복원 필요 | **MEDIUM** |

---

## 7. 테스트/회귀 계획

### RI-2A 예상 신규 테스트

| 테스트 Class | 예상 tests | 검증 대상 |
|-------------|:----------:|-----------|
| TestShadowToScreeningInputMapping | ~5 | shadow → ScreeningInput 매핑 정확성 |
| TestShadowToQualificationInputMapping | ~5 | shadow → QualificationInput 매핑 정확성 |
| TestShadowRuntimeComparison | ~8 | shadow vs runtime 결과 비교 (mock runtime) |
| TestShadowWrapperPurity | ~4 | wrapper가 DB/async 없이 pure 유지 |
| **총 RI-2A 예상** | **~22** | |

### RI-2B 예상 신규 테스트

| 테스트 Class | 예상 tests | 검증 대상 |
|-------------|:----------:|-----------|
| TestBoundedScreenWrite | ~6 | shadow → screen_and_update 연결 (mock DB) |
| TestBoundedQualifyWrite | ~6 | shadow → qualify_and_record 연결 (mock DB) |
| TestMismatchHalt | ~4 | mismatch 시 즉시 중단 |
| TestFallbackToShadow | ~3 | 장애 시 RI-1 복귀 |
| **총 RI-2B 예상** | **~19** | |

### 기존 기준선 보호 방식

| 보호 조치 | 설명 |
|-----------|------|
| FROZEN 함수 무수정 | screen_and_update/qualify_and_record 시그니처/로직 변경 금지 |
| Purity guard 유지 | 10 Pure Zone files 무접촉, 117 purity tests 유지 |
| 기존 5299 tests 회귀 | 전체 회귀 PASS 필수 |
| Contract tests 유지 | 87 contract tests (design + phase2_3a) 무변경 |

---

## 8. 단계 분리 여부

### 권장: RI-2A / RI-2B 분리

| 단계 | 성격 | 범위 | write |
|------|------|------|:-----:|
| **RI-2A** | wrapper / read-through | shadow → FROZEN 함수 입력 매핑, 비교 검증, mock 테스트 | **NO** |
| **RI-2B** | bounded write enable | 실제 screen_and_update/qualify_and_record 호출 허용 | **YES** |

### RI-2A 단독으로 가치가 있는가?

**있습니다.** RI-2A는:
1. shadow 결과 → runtime 입력 형식 매핑의 정확성을 검증
2. mock 기반으로 "호출했을 때 결과가 일치하는가"를 사전 확인
3. 실제 DB write 없이 통합 가능성을 증명

### RI-2A → RI-2B 전환 조건

| # | 조건 | 임계 |
|---|------|------|
| 1 | RI-2A shadow → mock runtime verdict 일치율 | ≥ 98% |
| 2 | RI-2A 봉인 완료 | A 승인 |
| 3 | 매핑 함수 purity guard PASS | 전부 PASS |
| 4 | 전체 회귀 PASS | N/N |
| 5 | FROZEN 함수 수정 0줄 | 0줄 |

---

## 9. 종합 판정 권고

### RI-2 전체: **아직 열면 안 됩니다**

| 이유 | 설명 |
|------|------|
| 진입 조건 미충족 | 8개 중 3개만 충족 (shadow 운영 데이터 없음) |
| shadow 검증 기간 필요 | 최소 72H 연속 실행 + 20 symbols 이상 |
| write-path 위험 | screen_and_update/qualify_and_record 모두 DB write + status 전이 |

### 권고 경로

```
현재                    다음 1단계              다음 2단계              다음 3단계
RI-1 SEALED     →    Shadow 운영 검증      →    RI-2A 범위 심사     →    RI-2B 범위 심사
(v2.0)               (72H+, 20 symbols)        (wrapper only)          (bounded write)
                     데이터 수집만              구현은 별도 승인          구현은 별도 승인
```

### 선행 작업: Shadow 운영 검증 스크립트

RI-2 진입 조건을 충족하려면, 먼저 shadow runner를 **기존 데이터로 배치 실행**하여
verdict 일치율을 측정하는 스크립트가 필요합니다.

이것은:
- **read-only** (shadow runner 호출 + 비교만)
- **DB write 0** (기존 데이터 조회 + shadow 비교)
- **운영 코드 수정 0**

이므로 RI-1 범위 안에서 가능합니다.

---

## A 판정 요청

| 판정 대상 | 선택지 |
|----------|--------|
| RI-2 즉시 개방 | **비권장** — 진입 조건 미충족 (3/8) |
| Shadow 운영 검증 우선 | **권장** — 72H+ 배치 실행으로 진입 조건 충족 후 재심사 |
| RI-2A/2B 분리 | **권장** — write-path 단계적 개방 |
| RI-2 대신 별도 CR | 가능 — 하지만 RI-2가 자연스러운 다음 단계 |

---

```
CR-048 RI-2 Reentry Review Package v1.0
Baseline: v2.0 (5299/5299 PASS, RI-1 SEALED)
RI-2 진입 조건: 3/8 충족 (INSUFFICIENT)
권고: Shadow 운영 검증 우선 → RI-2A 범위 심사 → RI-2B 범위 심사
Risk: HIGH (write-path 개방)
Rollback: RI-2A TRIVIAL, RI-2B MEDIUM
```
