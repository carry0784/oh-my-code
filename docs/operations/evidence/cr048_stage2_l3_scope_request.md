# CR-048 Stage 2 L3 범위 요청서

**문서 ID:** GOV-L3-STAGE2-001
**작성일:** 2026-04-04
**Authority:** A (Decision Authority)
**CR:** CR-048
**변경 등급:** L3 (서비스 로직)
**전제:** Stage 1 L3 SEALED (A 승인 2026-04-04, 4709/4709 PASS)
**참조:** `cr048_staged_l3_expansion_proposal.md` Stage 2

> **본 문서는 Stage 2 L3 범위 요청서입니다. A 승인 전까지 구현 착수는 금지됩니다.**

---

## 1. 해석 및 요약

### 목적

Phase 2 Asset Service를 확장하여 **Symbol-Broker 교차 검증**, **TTL 만료 로직**, **종목 상태 전이 감사**를 구현합니다.

### 현재 상태

| 항목 | 값 |
|------|-----|
| Gate | LOCKED |
| 회귀 기준선 | 4709/4709 PASS |
| Stage 1 | **SEALED** (Gateway 7단계 + Registry CRUD + API 16개) |
| 허용 범위 | L0/L1/L2 + L3(model skeleton + Stage 1 control-plane) |
| 예외 | EX-001, EX-002 종결, EX-003 불필요 |

### 핵심 발견 — 기존 asset_service.py 현황

`app/services/asset_service.py`는 이미 **상당 부분 구현**되어 있습니다.

| 기능 | 현재 상태 | Stage 2 작업 |
|------|:--------:|:----------:|
| Symbol CRUD (get/list/register) | **구현됨** | 검증 강화 |
| Status transition (EXCLUDED guard) | **구현됨** | 감사 강화 |
| TTL 만료 조회 (get_expired_candidates) | **구현됨** | 만료 처리 로직 |
| Screening record (append-only) | **구현됨** | — |
| screen_and_update (스크리닝 통합) | **구현됨** | — |
| **Symbol-Broker 교차 검증** | **미구현** | 신규 |
| **TTL 만료 처리 (CORE→WATCH 강등)** | **미구현** | 신규 |
| **상태 전이 감사 이벤트** | **미구현** | 신규 |
| **Regime 전환 시 TTL 일괄 만료** | **미구현** | 신규 |

### 중요 리스크 — 기존 import 의존성

`asset_service.py`는 현재 아래를 import합니다:

```python
from app.services.symbol_screener import ScreeningInput, ScreeningOutput, SymbolScreener
from app.services.backtest_qualification import QualificationInput, QualificationOutput, BacktestQualifier
```

이 import들은 **Stage 3(SymbolScreener)** 및 **Phase 4(BacktestQualifier)** 범위입니다.
Stage 2에서는 이 import/함수를 **건드리지 않습니다** — 기존 코드 유지만.

---

## 2. Stage 1과의 차이점 표

| 항목 | Stage 1 | Stage 2 |
|------|---------|---------|
| **대상 파일** | injection_gateway, registry_service, registry.py, registry_schema | **asset_service.py**, asset_schema.py, 테스트 |
| **모델/DB 변경** | 없음 | **없음** (기존 Symbol/ScreeningResult 모델 유지) |
| **write 유형** | metadata create/retire | **status transition + TTL처리 + 감사** |
| **외부 의존** | constitution.py 상수만 | constitution.py + **broker_matrix 상수** |
| **Data Plane 영향** | 없음 | **간접적** (Symbol.status 변경이 runtime에 영향 가능) |
| **side-effect** | DB row 생성/상태변경만 | DB row 생성/상태변경 + **TTL 만료 처리** |
| **기존 코드** | gateway 확장 | **기존 asset_service 확장** |

### Stage 2 신규 리스크 5개

| # | 리스크 | 완화 방안 |
|:--:|--------|-----------|
| 1 | **Symbol.status 변경이 Runtime에 영향** | runtime_strategy_loader.py 미변경, Symbol.status 읽기는 기존 경로 |
| 2 | **기존 screen_and_update()에 SymbolScreener import** | 해당 함수 미수정, import 그대로 유지 |
| 3 | **TTL 만료 처리가 자동 강등 유발** | Celery task 미생성 (수동 호출만), 자동화는 Stage 3 |
| 4 | **asset_service.py가 이미 크고 복잡** (280+ lines) | 신규 기능만 추가, 기존 함수 수정 최소화 |
| 5 | **Regime 전환 연동이 RegimeDetector에 접근 필요** | RegimeDetector 미수정, 이벤트 수신 인터페이스만 정의 |

---

## 3. 이유 / 근거

### 근거 1 — Stage 1 → Stage 2 순차 의존

Stage 1에서 전략이 Registry에 등록되면, 다음은 "어떤 종목에 실행할 것인가"를 결정하는
Asset Registry의 강화가 필요합니다. 특히:
- Symbol에 할당된 broker가 허용 목록과 일치하는지 교차 검증
- TTL 만료된 CORE 종목의 자동 WATCH 강등
- 상태 전이 이력 추적 (감사)

### 근거 2 — 기존 구현 위에 확장

`asset_service.py`는 이미 기본 CRUD와 상태 전이를 구현하고 있으므로,
Stage 2는 **완전 신규가 아니라 기존 코드의 검증/감사 강화**입니다.

### 근거 3 — 모델/DB 변경 없이 가능

Symbol, ScreeningResult 모델에 이미 필요한 컬럼이 모두 존재합니다:
- `status`, `status_reason_code`, `candidate_expire_at`
- `override_by`, `override_reason`, `override_at`
- `exchanges`, `broker_policy`

따라서 Alembic 마이그레이션 없이 서비스 로직만 추가하면 됩니다.

---

## 4. 파일 3분할 분류표

### GREEN (허용) — Stage 2에서 변경 가능

| 파일 | 작업 | 등급 | 근거 |
|------|------|:----:|------|
| `app/services/asset_service.py` | 확장 — Symbol-Broker 검증, TTL 처리, 감사 이벤트 | L3 | 설계 카드 A-05, A-06, A-07, A-08 |
| `app/schemas/asset_schema.py` | 확장 — 감사 응답, TTL 응답 스키마 | L2 | Pydantic 검증 |
| `tests/test_asset_service_phase2.py` | 신규 — Phase 2 서비스 테스트 | L1 | Symbol-Broker, TTL, 감사 |
| `tests/test_asset_service_contracts.py` | 신규 — 설계 계약 테스트 | L1 | A-05~A-08 계약 검증 |

### RED (금지) — Stage 2에서 변경 불가

| 파일/범위 | 사유 |
|-----------|------|
| `app/services/symbol_screener.py` | Stage 3 범위 |
| `app/services/sector_rotator.py` | Stage 3 범위 |
| `app/services/data_provider.py` | Stage 3 범위 |
| `app/services/runtime_strategy_loader.py` | Data Plane — Phase 5 |
| `app/services/runtime_loader_service.py` | Data Plane — Phase 5 |
| `app/services/feature_cache.py` | Data Plane — Phase 5 |
| `app/services/backtest_qualification.py` | Phase 4 |
| `app/services/paper_shadow_service.py` | Phase 4 |
| `app/services/injection_gateway.py` | Stage 1 SEALED |
| `app/services/registry_service.py` | Stage 1 SEALED |
| `app/api/routes/registry.py` | Stage 1 SEALED |
| `workers/tasks/*` | Celery task — L4 |
| `exchanges/*` | 거래소 어댑터 |
| `app/models/*` | 모델 변경 없음 |
| `alembic/versions/*` | DB 스키마 변경 없음 |
| `app/services/regime_detector.py` | 수정 금지 (읽기 참조만) |

### AMBER (회색지대) — 사전 예외 승인 시에만

| 파일 | 잠재적 필요성 | 예외 조건 |
|------|-------------|-----------|
| `app/core/constitution.py` | Symbol-Broker 검증에 새 상수 필요 시 | 상수 추가만 허용, 기존 값 변경 금지 |
| `app/api/routes/asset.py` (존재 시) | TTL/감사 조회 엔드포인트 필요 시 | GET만 추가 허용, write 신중 |
| `tests/test_asset_registry.py` (기존) | 기존 테스트 호환 수정 필요 시 | assertion 정렬만, 로직 변경 금지 |
| `app/services/asset_service.py` — screen_and_update() | 기존 함수 내 버그 발견 시 | 버그 수정만 허용, 기능 추가 금지, 사전 보고 |

---

## 5. Capability Wall

### 허용 기능

| Capability | 범위 | 비고 |
|------------|------|------|
| Symbol-Broker 교차 검증 | `Symbol.exchanges ∩ FORBIDDEN_BROKERS = ∅` 강제 | constitution.py 참조 |
| AssetClass별 허용 브로커 검증 | CRYPTO↔BINANCE/BITGET/UPBIT, US_STOCK↔KIS_US, KR_STOCK↔KIS_KR/KIWOOM_KR | ALLOWED_BROKERS 참조 |
| TTL 만료 처리 | `candidate_expire_at < now` → CORE→WATCH 강등 | 수동 호출만, 자동 Celery task 금지 |
| 상태 전이 감사 | 전이 시 from/to/reason/triggered_by/at 기록 | SymbolStatusEvent 패턴 |
| EXCLUDED→CORE 직행 금지 강화 | 기존 구현 + 테스트 추가 | A-05 계약 |
| EXCLUDED→WATCH 전환 A 승인 필요 | manual_override + override_by/reason/at 필수 | A-06 계약 |
| Regime 전환 시 TTL 만료 인터페이스 | 이벤트 수신 메서드 정의만 | RegimeDetector 미수정 |

### 금지 기능

| Capability | 이유 |
|------------|------|
| Hard delete (Symbol/ScreeningResult) | 금지 |
| SymbolScreener 파이프라인 실행 | Stage 3 |
| Celery screening task 생성 | Stage 3 |
| BacktestQualifier 실행 | Phase 4 |
| 외부 데이터 API 호출 | Stage 3 |
| RuntimeStrategyLoader 연동 | Phase 5 |
| Feature Cache 연동 | Phase 5 |
| Broker connect / 주문 실행 | Data Plane |
| beat schedule 변경 | L4 |
| exchange_mode 변경 | L4 |
| Promotion 상태 전이 실행 | Phase 4 |
| RegimeDetector 수정 | 금지 |

### Data Plane 영향 분석

| 영향 경로 | 직접/간접 | 위험도 | 완화 |
|-----------|:---------:|:------:|------|
| Symbol.status 변경 → runtime loader가 status 읽기 | 간접 | **중** | runtime_strategy_loader.py 미수정, 기존 읽기 경로만 |
| TTL 만료 강등 → CORE 종목 풀 감소 | 간접 | **저** | 수동 호출만, 자동 스케줄 금지 |
| Symbol.exchanges 검증 → 등록 거부 | 직접 (등록 시점) | **저** | 등록 시점에서만 작동, 기존 종목 미영향 |
| Regime 전환 인터페이스 → TTL 일괄 만료 | 간접 | **중** | 인터페이스 정의만, 실행은 Stage 3 |

---

## 6. 중단 조건 / 재진입 조건

### 중단 조건

| 조건 | 행동 |
|------|------|
| 회귀 실패 발생 | 즉시 중단, 원인 분석 |
| RED 파일 변경 필요 발견 | 즉시 중단, 사전 예외 요청 |
| AMBER 파일 변경 필요 | 작업 일시 중지, 사전 보고 |
| 기존 screen_and_update() 수정 필요 | 즉시 중단, 사전 보고 (Stage 3 경계) |
| runtime_strategy_loader 영향 감지 | 즉시 중단, EX 리뷰 |
| SymbolScreener/BacktestQualifier import 변경 필요 | 즉시 중단 (Stage 3/Phase 4 경계) |
| A 중단 지시 | 즉시 중단 |

### 봉인 조건

| # | 조건 | 검증 방법 |
|:--:|------|-----------|
| 1 | Symbol-Broker 교차 검증 테스트 PASS | 금지 브로커 등록 거부 + 허용 브로커 정상 |
| 2 | TTL 만료 로직 테스트 PASS | 만료 → CORE→WATCH 강등 |
| 3 | EXCLUDED→CORE 직행 금지 테스트 PASS | 상태 전이 거부 |
| 4 | EXCLUDED→WATCH A 승인 필요 테스트 PASS | manual_override 필수 |
| 5 | 상태 전이 감사 이벤트 테스트 PASS | from/to/reason/at 기록 |
| 6 | Regime TTL 만료 인터페이스 테스트 PASS | 메서드 존재 + 호출 가능 |
| 7 | 기존 계약 테스트 유지 (57+30건) | regression |
| 8 | 전체 회귀 PASS (4709+α) | `pytest --tb=short -q` |
| 9 | **A 판정** | 제출 후 판정 |

---

## 7. 예외 승인 필요 지점

| 지점 | 예외 유형 | 처리 |
|------|-----------|------|
| constitution.py 상수 추가 | 정책 인접 | **사전 보고 + A 승인** |
| 기존 screen_and_update() 버그 수정 | Stage 3 경계 | **사전 보고 + A 승인** |
| asset API 엔드포인트 추가 | capability 확장 | **사전 보고** |
| test_asset_registry.py 수정 | 기존 테스트 호환 | **사전 보고** |
| regime_detector.py 읽기 참조 | 외부 서비스 의존 | **import만 허용, 수정 금지** |

---

## A에게 제출하는 항목 (L3 확장 제안서 §4 기준)

| # | 항목 | 내용 |
|:--:|------|------|
| 1 | Stage 1 봉인 증빙 | SEALED (2026-04-04, `cr048_stage1_l3_completion_evidence.md`) |
| 2 | Stage 2 파일 목록 + 변경 범위 | GREEN 4파일, AMBER 4파일(조건부), RED 16+파일(금지) |
| 3 | 금지 범위 갱신표 | 본 문서 §4 RED 표 참조 |
| 4 | 예상 테스트 추가 수 | 30~50건 (Symbol-Broker 10~15 + TTL 10~15 + 감사 5~10 + 계약 5~10) |
| 5 | 회귀 기준선 현재 수치 | **4709/4709 PASS** |

---

**Stage 2 limited scope approval requested**

---

```
CR-048 Stage 2 L3 Scope Request v1.0
Document ID: GOV-L3-STAGE2-001
Date: 2026-04-04
Authority: A
Status: REJECTED (조건부 반려 — 2A/2B 분리 재상신 지시)
Decision Date: 2026-04-04
Gate: LOCKED (유지 전제)
Prerequisite: Stage 1 SEALED
Superseded By: GOV-L3-STAGE2A-001, GOV-L3-STAGE2B-001
```
