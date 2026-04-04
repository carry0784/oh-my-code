# CR-048 Stage 3B-2 Stub Scope Review

**문서 ID:** DESIGN-STAGE3B2-001
**작성일:** 2026-04-03
**CR:** CR-048
**Stage:** Stage 3B-2 (Provider Stub + ScreeningInput Transformation)
**변경 등급:** L0 (설계 문서)
**전제:** Gate LOCKED, Stage 3B-1 SEALED (5075/5075 PASS)

> 본 문서는 Stage 3B-2 설계 범위 검토 문서입니다. A 승인 전까지 구현 착수하지 않습니다.

---

## 1. 범위 개요

### 목적

Stage 3B-1에서 봉인된 Pure Zone 계약 (DataQualityDecision, ProviderCapability, SymbolMetadata, check_stale/check_partial/normalize_symbol 등)을 기반으로, **DataProvider → ScreeningInput 변환 경로**를 설계한다.

### 3계층 분리 원칙

Stage 3B-2의 핵심은 아래 3개 계층이 **절대 한 파일/한 계층으로 섞이지 않는 것**이다.

| Layer | 이름 | 위치 | 3B-2 상태 |
|:-----:|------|------|:---------:|
| **L1** | Pure Transformation | `app/services/screening_transform.py` | **허용** |
| **L2** | Provider Stub | `tests/stubs/screening_stubs.py` | **허용** |
| **L3** | Runtime/Service Path | `app/services/asset_service.py` + workers | **차단** |

- **L1은 `app/services/`에 배치** — 향후 runtime에서 사용될 순수 변환 함수.
- **L2는 `tests/stubs/`에 배치** — 테스트 전용 stub. production import 금지.
- **L3은 Stage 3B-2에서 접촉하지 않는다.**

---

## 2. 허용 범위

### 신규 파일

| 파일 | 용도 | Layer |
|------|------|:-----:|
| `app/services/screening_transform.py` | ScreeningInput 변환 순수 함수 + ScreeningInputSource + TransformResult | L1 |
| `tests/stubs/__init__.py` | stubs 패키지 | L2 |
| `tests/stubs/screening_stubs.py` | Stub provider 구현 (fixture 기반, sync only) | L2 |
| `tests/fixtures/screening_fixtures.py` | Golden set fixture 데이터 (시장별 4종 + failure mode 9종) | L2 |
| `tests/test_screening_transform.py` | 변환 함수 계약 테스트 | L1 테스트 |
| `tests/test_screening_stubs.py` | Stub provider 동작 + purity 테스트 | L2 테스트 |

### 허용 작업

| 작업 | 허용 |
|------|:----:|
| frozen dataclass 정의 (ScreeningInputSource, TransformResult) | YES |
| pure function 정의 (no async, no I/O) | YES |
| stub class (fixture return only, sync) | YES |
| golden set fixture 데이터 작성 | YES |
| Stage 3B-1 계약 import (read-only 참조) | YES |
| Stage 3A 계약 import (read-only 참조) | YES |

---

## 3. 금지 범위

| 금지 항목 | 사유 |
|-----------|------|
| `app/services/asset_service.py` 접촉 | FROZEN 함수 보호 |
| `screen_and_update()` 수정 | FR-01 |
| `qualify_and_record()` 수정 | FR-01 |
| DB write (session.add/commit) | DATA_ONLY 정책 |
| Real API (httpx, requests, aiohttp, ccxt) | 실연결 금지 |
| Worker/task/beat 등록 | Runtime 차단 |
| `exchanges/*` 접촉 | Runtime 차단 |
| `runtime_strategy_loader.py` 접촉 | Runtime 차단 |
| `feature_cache.py` 접촉 | Runtime 차단 |
| Stage 3B-1 sealed 계약 수정 | SEALED baseline |
| Stage 3A sealed 계약 수정 | SEALED baseline |
| Provider-specific exception을 L1에 주입 | L1/L2 분리 위반 |
| async def in L1 or L2 | Pure zone 규칙 |
| L1 (screening_transform.py)에서 L2 (stubs) import | 의존 방향 위반 |

---

## 4. 파일 분류표

| 파일 | 3B-2 Status | 사유 |
|------|:-----------:|------|
| `app/services/screening_transform.py` | **NEW** | L1 Pure Transformation |
| `tests/stubs/screening_stubs.py` | **NEW** | L2 Provider Stub |
| `tests/fixtures/screening_fixtures.py` | **NEW** | Golden set fixture |
| `tests/test_screening_transform.py` | **NEW** | L1 계약 테스트 |
| `tests/test_screening_stubs.py` | **NEW** | L2 purity 테스트 |
| `app/services/data_provider.py` | **READ-ONLY** | Stage 3B-1 SEALED |
| `app/services/symbol_screener.py` | **READ-ONLY** | Stage 3A SEALED |
| `app/services/sector_rotator.py` | **READ-ONLY** | Stage 3A/3B-1 SEALED |
| `app/services/backtest_qualification.py` | **READ-ONLY** | Stage 3A SEALED |
| `app/services/asset_validators.py` | **READ-ONLY** | Stage 2A SEALED |
| `app/core/constitution.py` | **READ-ONLY** | Stage 2A SEALED |
| `app/services/asset_service.py` | **FORBIDDEN** | FROZEN 함수 |
| `workers/*` | **FORBIDDEN** | Runtime |
| `exchanges/*` | **FORBIDDEN** | Runtime |
| `app/services/runtime_strategy_loader.py` | **FORBIDDEN** | Runtime |
| `app/services/feature_cache.py` | **FORBIDDEN** | Runtime |

---

## 5. Stub → 실연결 차단 규칙

| 규칙 ID | 내용 |
|---------|------|
| SB-01 | Stub은 fixture data만 반환 (constructor-injected) |
| SB-02 | Stub 파일에 httpx, requests, aiohttp, ccxt, sqlalchemy import **금지** |
| SB-03 | Stub 파일에 os.environ, dotenv, open() 접근 **금지** |
| SB-04 | Stub 메서드에 async def **금지** (sync only) |
| SB-05 | Stub → real provider 전환은 별도 Stage 승인 필요 |
| SB-06 | ProviderCapability는 fixture 파일에서 선언, stub 코드에 하드코딩 금지 |
| SB-07 | Stub는 `tests/` 하위에만 배치 |
| SB-08 | `screening_transform.py` (L1)에서 stub import 금지 |

---

## 6. 봉인 조건

| 조건 | 검증 방법 |
|------|-----------|
| Pure transformation 테스트 PASS | `test_screening_transform.py` |
| Stub provider 테스트 PASS | `test_screening_stubs.py` |
| Golden set fixture ≥ F1-F9 커버 | fixture에 9개 failure mode 시나리오 |
| Purity guard: screening_transform.py | 32 forbidden pattern 통과 |
| L1→L2 의존 없음 | import graph 검증 |
| L2에 실연결 코드 없음 | SB-01~SB-08 검증 |
| 전체 회귀 PASS | pytest 전수 |
| A 판정 | ACCEPT |

---

## 7. 의존 관계

```
Stage 3B-1 (SEALED)
  ├─ DataQualityDecision, ProviderCapability, SymbolMetadata
  ├─ check_stale, check_partial, normalize_symbol, is_screening_capable
  └─ FailureModeRecovery, STALE_LIMITS
      │
      ▼
Stage 3B-2 (THIS)
  ├─ L1: screening_transform.py
  │       ├─ validate_screening_preconditions()  ← imports check_stale, check_partial, normalize_symbol
  │       ├─ build_screening_input()             ← imports ScreeningInput (3A), SymbolMetadata (3B-1)
  │       ├─ transform_provider_to_screening()   ← orchestrates validate + build
  │       ├─ ScreeningInputSource (frozen)       ← audit dataclass
  │       └─ TransformResult (frozen)            ← validate+build 결과
  │
  ├─ L2: screening_stubs.py
  │       ├─ StubMarketDataProvider   ← fixture dict → MarketDataSnapshot
  │       ├─ StubBacktestDataProvider ← fixture dict → BacktestReadiness
  │       ├─ StubFundamentalDataProvider ← fixture dict → FundamentalSnapshot
  │       └─ StubScreeningDataProvider   ← composes above
  │
  └─ Fixtures: screening_fixtures.py
          ├─ Normal: BTC/USDT, SOL/USDT, AAPL, 005930
          ├─ Failure: F1 empty, F2 partial, F4 stale, F5 bars, F6 listing, F7 namespace
          └─ Edge: degraded, partial_usable, stale_usable
```

---

```
CR-048 Stage 3B-2 Stub Scope Review v1.0
Document ID: DESIGN-STAGE3B2-001
Date: 2026-04-03
Status: SUBMITTED (A 검토 대기)
```
