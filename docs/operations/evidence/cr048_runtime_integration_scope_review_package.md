# CR-048 Runtime Integration Scope Review Package

**문서 ID:** CR048-RI-SCOPE-001
**작성일:** 2026-04-03
**전제 기준선:** v1.9 (5260/5260 PASS, Stage 4B SEALED)

---

## 1. 해석 및 요약

### 통합 목표

지금까지 봉인된 순수 자산들을 **런타임 서비스 경계에 연결**하여,
실제 운영 시스템이 스크리닝-자격검증 파이프라인을 **호출 가능한 상태**로 만드는 것.

구체적으로:
- `run_screening_qualification_pipeline()` → 현재 **런타임 소비자 0개** (테스트만 import)
- `transform_provider_to_screening()` → 현재 **런타임 소비자 0개** (테스트만 import)
- 이 함수들이 runtime path에서 호출되지 않으면, Stage 3B~4A의 순수 자산은 **영구 격리 상태**

### 왜 지금 열어야 하는지

1. **순수 자산 9개가 봉인되었지만, 실제 운영에 연결된 것은 0개**
   - `SymbolScreener.screen()` → `asset_service.screen_and_update()`에서 직접 호출 (기존)
   - `BacktestQualifier.qualify()` → `asset_service.qualify_and_record()`에서 직접 호출 (기존)
   - `run_screening_qualification_pipeline()` → **아무 서비스도 호출하지 않음**
   - `transform_provider_to_screening()` → **아무 서비스도 호출하지 않음**

2. **Stage 4A 파이프라인은 기존 screen/qualify를 조합했지만, 기존 경로는 여전히 분리 호출**
   - `screen_and_update()`는 `ScreeningInput`을 직접 받아 `screen()` 호출
   - `qualify_and_record()`는 `QualificationInput`을 직접 받아 `qualify()` 호출
   - 파이프라인의 **TransformResult → screen → qualify 일관 체인**은 아직 사용되지 않음

3. **순수 자산이 운영 경로에 연결되지 않으면, 봉인의 실질적 가치가 없음**

### 현재 상태 요약

```
순수 자산 (봉인 완료)          서비스 경계 (FROZEN)         런타임 (BLOCKED)
─────────────────────────    ────────────────────────    ─────────────
screening_transform.py   →   (연결 없음)              →   (없음)
screening_qual_pipeline.py → (연결 없음)              →   (없음)
symbol_screener.py       →   screen_and_update()     →   (수동 호출만)
backtest_qualification.py →  qualify_and_record()     →   (수동 호출만)
universe_manager.py      →   multi_symbol_runner.py  →   cycle_runner_tasks.py
```

---

## 2. 장점 / 단점

### 장점

- 봉인된 자산을 운영 경로에 연결하면 실질적 운영 가치가 생김
- Stage 4A 파이프라인의 fail-closed chain이 실제로 작동
- RI-1/RI-2 분리로 위험 단계적 통제 가능

### 단점

- **이 단계부터 write path 접촉 가능성이 생김**
- `asset_service.py` (RED)를 열지 않으면 실질 통합 불가
- `screen_and_update()` / `qualify_and_record()`는 FROZEN → 수정 시 봉인 해제 필요
- worker/Celery 연결 시 side-effect 경로 개방

---

## 3. 이유 / 근거

### 현재 기준선 대비 새 위험

| 위험 | 설명 | 통제 가능 여부 |
|------|------|:------------:|
| `asset_service.py` 접촉 | RED 파일, DB write 포함 | RI-2에서만, RI-1 제외 |
| `screen_and_update()` 수정 | FROZEN 함수, 서명 변경 테스트 존재 | 수정 불가, 신규 wrapper만 |
| `qualify_and_record()` 수정 | FROZEN 함수, 서명 변경 테스트 존재 | 수정 불가, 신규 wrapper만 |
| Worker task 연결 | Celery side-effect 경로 | RI-2에서만 |
| DB write path 개방 | 상태 전이 가능성 | RI-2에서만, RI-1은 read-only |

### 왜 통제 가능한지

1. FROZEN 함수는 **수정하지 않고 신규 wrapper로 감싸는 패턴**으로 접근
2. RI-1은 **read-only shadow** → DB write 없음, 상태 변경 없음
3. RI-2도 **기존 FROZEN 함수를 호출만** → 새 DB 로직 작성 없음

---

## 4. 실현 · 구현 대책

### 후보 진입점

| Entry | 파일 | 현재 상태 | DB write | 접촉 위험 |
|-------|------|----------|:--------:|:---------:|
| `screen_and_update()` | asset_service.py | **FROZEN** | YES | 높음 |
| `qualify_and_record()` | asset_service.py | **FROZEN** | YES | 높음 |
| `run_screening_qualification_pipeline()` | screening_qualification_pipeline.py | **SEALED Pure** | NO | 없음 |
| `transform_provider_to_screening()` | screening_transform.py | **SEALED Pure** | NO | 없음 |
| `UniverseManager.select()` | universe_manager.py | **SEALED Pure** | NO | 없음 |
| `is_safe_mode_active()` | cycle_state_service.py | Non-frozen | READ | 낮음 |
| `has_unprocessed_drift()` | cycle_state_service.py | Non-frozen | READ | 낮음 |

### Runtime Entry Risk Matrix

| Entry | 현재 상태 | 접촉 위험 | 읽기/쓰기 | fail-closed 가능 | 권장 |
|-------|----------|:---------:|:---------:|:---------------:|:----:|
| `screen_and_update()` | FROZEN | 높음 | write | 중간 | **RI-2 보류** |
| `qualify_and_record()` | FROZEN | 높음 | write | 중간 | **RI-2 보류** |
| shadow pipeline wrapper | 신규 순수 | 낮음 | **read-only** | 높음 | **RI-1 우선** |
| cycle_state_service queries | 기존 read-only | 낮음 | read | 높음 | **RI-1 가능** |
| worker task wiring | RED | 높음 | write+schedule | 낮음 | **RI-2 이후** |

---

### RI-1: Read-Only Shadow Integration (권장 우선)

#### 목적

순수 파이프라인을 **read-only shadow 모드**로 실행하여,
기존 운영 경로를 건드리지 않고 **파이프라인 출력을 관찰/기록만** 하는 단계.

#### 구조

```
[기존 경로 — 변경 없음]
  screen_and_update() → ScreeningOutput → DB write (기존 그대로)
  qualify_and_record() → QualificationOutput → DB write (기존 그대로)

[RI-1 shadow 경로 — 신규, read-only]
  MarketDataSnapshot + BacktestReadiness
    → transform_provider_to_screening()   (sealed pure)
    → run_screening_qualification_pipeline()  (sealed pure)
    → PipelineOutput
    → shadow_log(PipelineOutput)   (append-only 기록, 상태 변경 없음)
```

#### 핵심 원칙

| 원칙 | 설명 |
|------|------|
| **No state mutation** | shadow 경로는 Symbol 상태를 변경하지 않음 |
| **No DB write to operational tables** | Symbol, ScreeningResult, QualificationResult 테이블 미접촉 |
| **Append-only shadow log** | 별도 shadow_pipeline_log 테이블 또는 JSON 파일 기록만 |
| **No worker task** | 수동 호출 또는 test harness에서만 실행 |
| **기존 경로 무변경** | screen_and_update / qualify_and_record 접촉 0 |

#### 허용 파일

| 파일 | 작업 | 위험 |
|------|------|:----:|
| `app/services/pipeline_shadow_runner.py` | **신규** — shadow wrapper | LOW |
| `tests/test_pipeline_shadow_runner.py` | **신규** — shadow 테스트 | ZERO |
| `tests/test_purity_guard.py` | **수정** — 10th Pure Zone (if shadow runner is pure) | ZERO |

#### 금지 파일 (RI-1)

| 파일 | 이유 |
|------|------|
| `app/services/asset_service.py` | RED — DB write 포함 |
| `app/services/screen_and_update()` | FROZEN — 수정 금지 |
| `app/services/qualify_and_record()` | FROZEN — 수정 금지 |
| `workers/*` | RED — Celery task 생성 금지 |
| `alembic/versions/*` | 신규 마이그레이션 금지 (RI-1은 DB 스키마 변경 없음) |
| `app/api/routes/*` | API 엔드포인트 생성 금지 |
| `app/models/*` | 모델 생성/수정 금지 |

#### Read-only vs Write Path 구분

| 항목 | RI-1 |
|------|:----:|
| DB read | 가능 (cycle_state_service 쿼리 등) |
| DB write (operational) | **금지** |
| DB write (shadow log) | **보류** — JSON 파일 또는 stdout 기록만 |
| Symbol 상태 전이 | **금지** |
| Candidate TTL 설정 | **금지** |
| 상태 전이 | **없음** |

#### RI-1 예상 테스트

| 항목 | 예상 |
|------|:----:|
| Shadow runner 단위 테스트 | ~15-20 |
| Purity guard (shadow runner가 pure인 경우) | ~12 |
| 기존 경로 무변경 회귀 | 기존 5260 PASS 유지 |
| **총 증가** | **~27-32** |

---

### RI-2: Bounded Write-Path Integration (RI-1 이후)

#### 목적

RI-1에서 shadow 검증이 완료된 후,
파이프라인 출력을 **기존 FROZEN 함수를 통해** 실제 DB에 반영하는 단계.

#### 구조

```
[RI-2 통합 경로]
  MarketDataSnapshot + BacktestReadiness
    → transform_provider_to_screening()
    → run_screening_qualification_pipeline()
    → PipelineOutput
    → if QUALIFIED:
        screen_and_update(symbol_id, screening_input)  ← FROZEN 함수 호출
        qualify_and_record(symbol_id, qual_input)       ← FROZEN 함수 호출
    → if SCREEN_FAILED / DATA_REJECTED:
        기록만 (상태 변경 없음)
```

#### 핵심 원칙

| 원칙 | 설명 |
|------|------|
| **FROZEN 함수 호출만** | screen_and_update / qualify_and_record 수정 금지, 호출만 허용 |
| **파이프라인 verdict 기반 gating** | QUALIFIED일 때만 write path 진입 |
| **fail-closed** | 파이프라인 실패 → write path 미진입 |
| **기존 함수 동작 보존** | FROZEN 함수의 내부 guard (excluded sector, TTL 등) 그대로 유지 |

#### RI-2 추가 위험

| 위험 | 설명 | 통제 |
|------|------|------|
| DB write 발생 | screen_and_update가 Symbol 상태 변경 | FROZEN 함수의 기존 guard 의존 |
| asset_service.py 접촉 | RED 파일 import 필요 | import만, 수정 금지 |
| Worker task 연결 | 주기적 실행 필요 | RI-2 후반부 또는 별도 단계 |
| 상태 불일치 | pipeline verdict ≠ 개별 screen/qualify 결과 | 불일치 시 write 차단 |

#### RI-2 선행 조건

1. **RI-1 SEALED** (shadow 검증 완료)
2. **Shadow log에서 pipeline verdict와 기존 경로 결과 비교 완료**
3. **불일치율 < 임계값** (예: 5% 미만)
4. **A 승인**

---

## 5. 실행방법

### 범위 분할: RI-1 / RI-2 필수 분리

| 단계 | 범위 | 위험 | DB write | 선행 |
|------|------|:----:|:--------:|------|
| **RI-1** | Shadow read-only | LOW | 없음 | Stage 4B SEALED |
| **RI-2** | Bounded write-path | MEDIUM | 있음 (FROZEN 경유) | RI-1 SEALED + A 승인 |

**RI-1과 RI-2는 반드시 분리합니다.** RI-2는 RI-1 봉인 후에만 열 수 있습니다.

### Stage 3B~4B Sealed 자산 재사용표

| 자산 | 파일 | RI-1 재사용 | RI-2 재사용 | 변경 |
|------|------|:----------:|:----------:|:----:|
| `TransformResult` | screening_transform.py | import | import | 0줄 |
| `_REJECT_DECISIONS` | screening_transform.py | import | import | 0줄 |
| `transform_provider_to_screening()` | screening_transform.py | **call** | call | 0줄 |
| `ScreeningInput` | symbol_screener.py | import | import | 0줄 |
| `SymbolScreener` | symbol_screener.py | import | import | 0줄 |
| `BacktestQualifier` | backtest_qualification.py | import | import | 0줄 |
| `run_screening_qualification_pipeline()` | screening_qualification_pipeline.py | **call** | call | 0줄 |
| `PipelineOutput` / `PipelineVerdict` | screening_qualification_pipeline.py | import | import | 0줄 |
| `UniverseManager` | universe_manager.py | 미사용 | 미사용 | 0줄 |
| `DataQualityDecision` | data_provider.py | import | import | 0줄 |
| `BacktestReadiness` | data_provider.py | import | import | 0줄 |
| `MarketDataSnapshot` | data_provider.py | import | import | 0줄 |
| Qualification fixtures | qualification_fixtures.py | 테스트 재사용 | 테스트 재사용 | 0줄 |
| Screening fixtures | screening_fixtures.py | 테스트 재사용 | 테스트 재사용 | 0줄 |

**전 자산 0줄 변경. import/call만.**

### FROZEN 유지 대상 (RI-1, RI-2 공통)

| 파일 | 함수 | FROZEN 유지 |
|------|------|:----------:|
| asset_service.py | `screen_and_update()` | **YES** |
| asset_service.py | `qualify_and_record()` | **YES** |
| screening_transform.py | 전체 | **YES** |
| symbol_screener.py | 전체 | **YES** |
| backtest_qualification.py | 전체 | **YES** |
| screening_qualification_pipeline.py | 전체 | **YES** |
| data_provider.py | contracts | **YES** |

### RED 유지 대상 (RI-1, RI-2 공통)

| 파일 | 이유 | RI-1 접촉 | RI-2 접촉 |
|------|------|:---------:|:---------:|
| regime_detector.py | CR-046 | 금지 | 금지 |
| runtime_strategy_loader.py | runtime | 금지 | 금지 |
| feature_cache.py | Phase 5 | 금지 | 금지 |
| strategy_router.py | Phase 5 | 금지 | 금지 |
| multi_symbol_runner.py | Phase 6 | 금지 | 금지 |
| exchanges/* | broker | 금지 | 금지 |

### 허용/금지 접촉 매트릭스

| 파일/함수 | RI-1 | RI-2 |
|----------|:----:|:----:|
| Pure Zone 9 files (import/call) | **허용** | **허용** |
| `pipeline_shadow_runner.py` (신규) | **생성** | 재사용 |
| `asset_service.py` (수정) | **금지** | **금지** |
| `asset_service.py` (import, 호출만) | **금지** | **허용** |
| `screen_and_update()` (수정) | **금지** | **금지** |
| `screen_and_update()` (호출) | **금지** | **허용** |
| `qualify_and_record()` (수정) | **금지** | **금지** |
| `qualify_and_record()` (호출) | **금지** | **허용** |
| `cycle_state_service.py` (호출) | **허용** | **허용** |
| `workers/*` (신규 task) | **금지** | **보류** |
| `alembic/versions/*` (마이그레이션) | **금지** | **보류** |
| `app/api/routes/*` | **금지** | **금지** |
| `app/models/*` (신규) | **금지** | **보류** |

### fail-closed 위험 분석

#### RI-1 실패 지점

| 실패 지점 | 차단 방식 | 롤백 |
|----------|----------|------|
| Transform 실패 | PipelineVerdict.DATA_REJECTED → shadow log에 기록만 | 없음 (read-only) |
| Screen 실패 | PipelineVerdict.SCREEN_FAILED → shadow log에 기록만 | 없음 |
| Qualify 실패 | PipelineVerdict.QUALIFY_FAILED → shadow log에 기록만 | 없음 |
| Unknown decision | ValueError → catch + shadow log 기록 | 없음 |
| Shadow runner 자체 오류 | try/except → 에러 로그만, 운영 경로 무영향 | 없음 (독립 경로) |

**RI-1 롤백 비용: TRIVIAL** — shadow runner 파일 삭제만으로 완전 롤백. 운영 경로 무접촉.

#### RI-2 실패 지점

| 실패 지점 | 차단 방식 | 롤백 |
|----------|----------|------|
| Pipeline verdict ≠ QUALIFIED | write path 미진입 (fail-closed) | 없음 |
| screen_and_update() 실패 | FROZEN 함수 내부 guard 작동 | DB 트랜잭션 롤백 |
| qualify_and_record() 실패 | FROZEN 함수 내부 guard 작동 | DB 트랜잭션 롤백 |
| Pipeline-개별 결과 불일치 | 불일치 감지 → write 차단 | 없음 |

**RI-2 롤백 비용: LOW-MEDIUM** — integration wrapper 삭제 + 기존 경로 복원. FROZEN 함수 자체는 무변경.

---

## 6. 더 좋은 아이디어

1. **RI-1에서 "shadow comparison" 패턴을 쓰면 RI-2 진입 판단이 명확해집니다.**
   Shadow 경로에서 파이프라인 전체 실행 → 기존 개별 screen/qualify 결과와 비교 →
   불일치율이 낮으면 RI-2 진입 근거가 됩니다.

2. **RI-1의 shadow runner를 pure로 유지하면 10th Pure Zone이 됩니다.**
   Shadow runner가 DB/async 없이 순수하게 pipeline을 호출하고 결과만 반환하면,
   purity guard 대상으로 등록 가능 → 퇴행 방지 강화.

3. **RI-2에서 "pipeline-first, legacy-fallback" 패턴보다는
   "legacy-primary, pipeline-shadow" 패턴이 더 안전합니다.**
   즉, 기존 경로를 주 경로로 유지하고 파이프라인은 비교/검증용으로만 쓰다가,
   충분한 shadow 데이터 확보 후에 주 경로를 전환하는 방식.

4. **RI-1 완료 기준에 "shadow log 분석 리포트"를 포함하면,
   RI-2 범위 심사 근거가 자동으로 생깁니다.**

---

## A 판정 요청

| 판정 대상 | 선택지 |
|----------|--------|
| RI-1/RI-2 분리 | 분리 승인 / 통합 진행 |
| RI-1 범위 | Shadow read-only 승인 / 범위 조정 |
| RI-1 설계/구현 분리 | 설계 먼저 / 동시 진행 |
| Shadow runner 순수성 | Pure Zone 등록 후보 / 비등록 |

---

```
Runtime Integration Scope Review v1.0
Recommended: RI-1 (shadow read-only) first, RI-2 (bounded write) after seal
RI-1 risk: LOW (read-only, 0 DB write, 0 state mutation)
RI-2 risk: MEDIUM (FROZEN 함수 호출, DB write via existing guards)
Sealed asset changes: 0 lines across all stages
```
