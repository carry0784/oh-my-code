# CR-048 Stage 3B 경계 인벤토리

**문서 ID:** GOV-L3-STAGE3B-BOUNDARY-001
**작성일:** 2026-04-03
**Authority:** A (Decision Authority)
**CR:** CR-048
**전제:** Stage 3A L3 SEALED (4927/4927 PASS)
**목적:** 설계 이전 경계 실사 — "무엇이 pure인가, 무엇이 runtime인가, 어디서부터 오염이 시작되는가"

> 이 문서는 설계 결론을 포함하지 않는다. 확인 결과표 + 경계 지도 + 접촉 허용/금지표만 기술한다.

---

## 1. Stage 3A 산출물 경계 인벤토리

### 1-1. sector_rotator.py (215줄)

| 항목 | 값 |
|------|-----|
| **Import (외부)** | `dataclasses`, `enum` — stdlib만 |
| **Import (내부)** | `app.models.asset` (AssetSector, EXCLUDED_SECTORS) — 상수만 |
| **Import (금지 항목)** | sqlalchemy ❌, httpx ❌, requests ❌, aiohttp ❌, celery ❌, os ❌, asyncio ❌, RegimeDetector ❌ |
| **async 함수** | 0개 |
| **DB 접근** | 0개 |
| **네트워크 접근** | 0개 |
| **파일 I/O** | 0개 |
| **환경변수 접근** | 0개 |
| **side-effect** | 0개 |

#### 공개 API

| 이름 | 유형 | 입력 → 출력 | Pure |
|------|------|-------------|:----:|
| `RegimeLabel` | Enum(str) | 6 members (TRENDING_UP/DOWN, RANGING, HIGH_VOL, CRISIS, UNKNOWN) | ✅ |
| `SectorWeight` | frozen dataclass | sector, weight, regime → SectorWeight | ✅ |
| `RotationOutput` | frozen dataclass | regime, weights, over/underweight sectors → RotationOutput | ✅ |
| `get_sector_weight()` | function | (sector: AssetSector, regime: str) → float | ✅ |
| `compute_rotation()` | function | (regime: str, sectors: list\|None) → RotationOutput | ✅ |
| `apply_sector_weight_to_score()` | function | (base_score: float, sector: AssetSector, regime: str) → float | ✅ |

#### 상수

| 이름 | 값 | 용도 |
|------|-----|------|
| `DEFAULT_WEIGHT` | 1.0 | 미정의 regime/sector 기본값 |
| `MIN_WEIGHT` | 0.1 | 가중치 하한 클램핑 |
| `MAX_WEIGHT` | 2.0 | 가중치 상한 클램핑 |
| `_REGIME_SECTOR_WEIGHTS` | dict | RegimeLabel → {AssetSector → float} 매핑 |

#### 확장 가능 지점 (접촉이 아닌 인터페이스)

| # | 지점 | 설명 |
|:-:|------|------|
| E1 | `_REGIME_SECTOR_WEIGHTS` | 새 regime/sector 조합 추가 가능 (테이블 확장) |
| E2 | `compute_rotation()` sectors 파라미터 | 외부에서 sector 부분 집합 전달 가능 |
| E3 | `apply_sector_weight_to_score()` | screening 점수 조정 hook — screening pipeline 연결 후보 |
| E4 | `SectorWeight` 필드 | reason 필드 추가 가능 (3B 설계 검토에서 제안됨) |

**결론: sector_rotator.py는 완전 pure. 입력 → 계산 → 출력만 수행. 외부 상태 접근 0건.**

---

### 1-2. data_provider.py (203줄)

| 항목 | 값 |
|------|-----|
| **Import (외부)** | `abc`, `dataclasses`, `datetime`, `enum` — stdlib만 |
| **Import (내부)** | 없음 |
| **Import (금지 항목)** | sqlalchemy ❌, httpx ❌, requests ❌, aiohttp ❌, celery ❌, os ❌ |
| **async 함수** | 9개 — 전부 abstract, 구현체 없음 (... 만) |
| **DB 접근** | 0개 |
| **네트워크 접근** | 0개 |
| **파일 I/O** | 0개 |
| **환경변수 접근** | 0개 |
| **구현 코드** | 0줄 (docstring + `...` 만) |

#### 공개 API

| 이름 | 유형 | 메서드 | 구현 |
|------|------|--------|:----:|
| `DataQuality` | Enum(str) | 4 members (HIGH, DEGRADED, STALE, UNAVAILABLE) | ✅ 값 정의 |
| `MarketDataSnapshot` | frozen dataclass | 10 fields (symbol, timestamp, price, mcap, volume, spread, atr, adx, price_vs_200ma, quality) | ✅ 구조 정의 |
| `FundamentalSnapshot` | frozen dataclass | 8 fields (symbol, timestamp, per, roe, tvl, active_addresses, revenue_growth, operating_margin, quality) | ✅ 구조 정의 |
| `BacktestReadiness` | frozen dataclass | 5 fields (symbol, available_bars, sharpe, missing_pct, quality) | ✅ 구조 정의 |
| `ProviderStatus` | frozen dataclass | 4 fields (provider_name, is_available, last_success, error_message) | ✅ 구조 정의 |
| `MarketDataProvider` | ABC | get_market_data, get_market_data_batch, health_check | ❌ abstract only |
| `FundamentalDataProvider` | ABC | get_fundamentals, health_check | ❌ abstract only |
| `BacktestDataProvider` | ABC | get_readiness, health_check | ❌ abstract only |
| `ScreeningDataProvider` | ABC | get_screening_data, get_provider_statuses | ❌ abstract only |

#### 확장 가능 지점

| # | 지점 | 설명 |
|:-:|------|------|
| E5 | `MarketDataProvider` 구현체 | Stage 3B-2에서 concrete class 작성 (외부 API 필요) |
| E6 | `FundamentalDataProvider` 구현체 | Stage 3B-2에서 concrete class 작성 |
| E7 | `BacktestDataProvider` 구현체 | Stage 3B-2에서 concrete class 작성 |
| E8 | `ScreeningDataProvider` 구현체 | 3개 provider 합성 — Stage 3B-2 핵심 |
| E9 | `ProviderCapability` dataclass 추가 | 3B 설계에서 제안된 capability 선언 |
| E10 | `DataQuality` 정책 함수 | stale/partial 데이터 처리 정책 |

**결론: data_provider.py는 순수 인터페이스. 구현체 0건. 구현은 전부 Stage 3B-2 영역.**

---

### 1-3. 전용 테스트 Purity Proof 범위

#### test_sector_rotator.py (330줄, 48 tests)

| Purity Guard 검증 항목 | AST 기반 | 결과 |
|------------------------|:--------:|:----:|
| asyncio import 금지 | ✅ | PASS |
| sqlalchemy import 금지 | ✅ | PASS |
| AsyncSession import 금지 | ✅ | PASS |
| httpx/requests import 금지 | ✅ | PASS |
| celery import 금지 | ✅ | PASS |
| os/shutil/tempfile import 금지 | ✅ | PASS |
| async 함수 존재 금지 | ✅ | PASS |
| RegimeDetector import 금지 | ✅ | PASS |

#### test_data_provider.py (270줄, 35 tests)

| Purity Guard 검증 항목 | AST 기반 | 결과 |
|------------------------|:--------:|:----:|
| httpx/requests import 금지 | ✅ | PASS |
| aiohttp import 금지 | ✅ | PASS |
| sqlalchemy import 금지 | ✅ | PASS |
| celery import 금지 | ✅ | PASS |
| os/dotenv import 금지 | ✅ | PASS |
| open()/Path() 금지 | ✅ | PASS |
| ABC 메서드에 구현 코드 금지 | ✅ (AST body 검사) | PASS |

#### Purity Guard 누락 항목 (Stage 3B 강화 후보)

| # | 누락된 검증 | 대상 파일 | 위험도 |
|:-:|------------|-----------|:------:|
| G1 | `aiohttp` import 금지 | sector_rotator.py | LOW |
| G2 | `open()/Path()` 파일 I/O 금지 | sector_rotator.py | LOW |
| G3 | `os.environ` 환경변수 접근 금지 | sector_rotator.py | LOW |
| G4 | `json.load/dump` 파일 경유 I/O 금지 | 양쪽 | LOW |
| G5 | `logging.getLogger` 사용 감지 | 양쪽 | INFO |
| G6 | `@app.task` / `shared_task` 데코레이터 금지 | 양쪽 | MED |
| G7 | `Session` / `engine` / `connection` 금지 | 양쪽 | MED |
| G8 | `import redis` / `import celery` 금지 | sector_rotator.py | MED |
| G9 | `socket` / `urllib` 네트워크 금지 | 양쪽 | MED |
| G10 | `subprocess` / `Popen` 금지 | 양쪽 | MED |

---

## 2. 기존 Screener 경로 경계 지도

### 2-1. 경로 개요

```
[ScreeningInput]        ← 순수 데이터 (frozen dataclass)
        │
        v
[SymbolScreener.screen()]   ← PURE LOGIC (sync, no I/O)
  ├─ _stage1_exclusion()    ← PURE
  ├─ _stage2_liquidity()    ← PURE
  ├─ _stage3_technical()    ← PURE
  ├─ _stage4_fundamental()  ← PURE
  └─ _stage5_backtest()     ← PURE
        │
        v
[ScreeningOutput]       ← 순수 결과 (frozen dataclass)
        │
========│=========================== ← 🔴 WRITE BOUNDARY
        v
[AssetService.screen_and_update()]   ← ASYNC + DB
  ├─ get_symbol_by_id()     ← DB SELECT
  ├─ sc.screen(input)       ← PURE 호출
  ├─ record_screening()     ← DB INSERT (ScreeningResult)
  └─ Symbol UPDATE          ← DB UPDATE (status, score, ttl)
```

### 2-2. 경로 상세 분석표

| 항목 | 값 |
|------|-----|
| **진입점** | `AssetService.screen_and_update()` (asset_service.py L348) |
| **읽기 경로** | `get_symbol_by_id()` → DB SELECT (Symbol 테이블) |
| **순수 계산** | `SymbolScreener.screen(ScreeningInput)` → 5단계 stateless 계산 |
| **정렬/필터** | screener 내부 5단계 필터 (sector → liquidity → technical → fundamental → backtest) |
| **기록 경계** | `record_screening()` L333 → DB INSERT (ScreeningResult) |
| **상태 변경 경계** | L390-408 → Symbol.status/screening_score/candidate_expire_at UPDATE |
| **금지 경계** | `screen_and_update()` 전체 — **Stage 3B 접촉 금지** (FROZEN) |
| **FROZEN 함수** | `screen_and_update()` L348-410, `qualify_and_record()` L414-483 |

### 2-3. qualify_and_record() 경계 분석

```
[QualificationInput]         ← 순수 데이터 (frozen dataclass)
        │
        v
[BacktestQualifier.qualify()]   ← PURE LOGIC (sync, no I/O)
  ├─ _check1_data_compat()      ← PURE
  ├─ _check2_warmup()           ← PURE
  ├─ _check3_leakage()          ← PURE
  ├─ _check4_data_quality()     ← PURE
  ├─ _check5_min_bars()         ← PURE
  ├─ _check6_performance()      ← PURE
  └─ _check7_cost_sanity()      ← PURE
        │
        v
[QualificationOutput]        ← 순수 결과 (frozen dataclass)
        │
========│=========================== ← 🔴 WRITE BOUNDARY
        v
[AssetService.qualify_and_record()]  ← ASYNC + DB
  ├─ get_symbol_by_id()      ← DB SELECT
  ├─ EXCLUDED guard           ← 방어 (qualification 거부)
  ├─ q.qualify(input)         ← PURE 호출
  ├─ QualificationResult INSERT ← DB INSERT
  └─ Symbol UPDATE             ← DB UPDATE (qualification_status)
```

### 2-4. AssetService 메서드 분류

#### READ-ONLY 메서드 (Write 없음)

| 메서드 | 라인 | 작업 | 위험 |
|--------|------|------|:----:|
| `get_symbol()` | L55-59 | SELECT | 없음 |
| `get_symbol_by_id()` | L61-65 | SELECT | 없음 |
| `list_symbols()` | L67-78 | SELECT | 없음 |
| `list_core_symbols()` | L80-85 | SELECT (CORE만) | 없음 |
| `get_expired_candidates()` | L303-312 | SELECT | 없음 |
| `get_screening_history()` | L337-344 | SELECT | 없음 |
| `get_qualification_history()` | L485-498 | SELECT | 없음 |

#### WRITE 메서드 (DB 변경)

| 메서드 | 라인 | 작업 | 테이블 | Celery |
|--------|------|------|--------|:------:|
| `register_symbol()` | L87-148 | INSERT | Symbol | ❌ |
| `transition_status()` | L150-197 | UPDATE + audit INSERT | Symbol, SymbolStatusAudit | ❌ |
| `_record_status_audit()` | L199-252 | INSERT | SymbolStatusAudit | ❌ |
| `process_expired_ttl()` | L254-300 | UPDATE (max 10건) | Symbol | ❌ manual |
| `record_screening()` | L314-335 | INSERT | ScreeningResult | ❌ |
| **`screen_and_update()`** | **L348-410** | **INSERT + UPDATE** | **ScreeningResult, Symbol** | **❌ FROZEN** |
| **`qualify_and_record()`** | **L414-483** | **INSERT + UPDATE** | **QualificationResult, Symbol** | **❌ FROZEN** |

---

## 3. 접촉 분류표 (GREEN / YELLOW / AMBER / RED)

### 3-1. 파일 분류

| 파일 | 등급 | 근거 |
|------|:----:|------|
| `app/services/sector_rotator.py` | 🟢 **GREEN** | Pure 계산, I/O 0, side-effect 0, Stage 3A 봉인 |
| `app/services/data_provider.py` | 🟢 **GREEN** | Pure ABC/Protocol, 구현 0, Stage 3A 봉인 |
| `app/services/symbol_screener.py` | 🟢 **GREEN** | Pure 계산, sync, I/O 0, side-effect 0 |
| `app/services/backtest_qualification.py` | 🟢 **GREEN** | Pure 계산, sync, I/O 0, side-effect 0 |
| `tests/test_sector_rotator.py` | 🟢 **GREEN** | Stage 3A 테스트, 소스 읽기만 |
| `tests/test_data_provider.py` | 🟢 **GREEN** | Stage 3A 테스트, 소스 읽기만 |
| `tests/test_symbol_screener.py` | 🟡 **YELLOW** | Screener 테스트, read-only지만 screening core 인접 |
| `tests/test_asset_registry.py` | 🟡 **YELLOW** | Asset 모델 테스트, read-only지만 screening core 인접 |
| `app/services/asset_service.py` | 🟠 **AMBER** | Screening 핵심 서비스, FROZEN 함수 포함, 현재 접촉 금지 |
| `app/services/asset_validators.py` | 🟡 **YELLOW** | Pure validator, I/O 없음, Stage 2B 봉인 |
| `app/models/asset.py` | 🟡 **YELLOW** | 모델/enum 정의, Stage 2A 이후 봉인 |
| `app/core/constitution.py` | 🟡 **YELLOW** | 상수 정의, Stage 2A 이후 봉인 |
| `workers/celery_app.py` | 🔴 **RED** | Beat/task 등록, 접촉 금지 |
| `workers/tasks/screening_tasks.py` | 🔴 **RED** | 미생성, Stage 3B-2에서도 생성 금지 (Stage 3B 범위 외) |
| `app/services/runtime_strategy_loader.py` | 🔴 **RED** | Runtime 실행, 접촉 금지 |
| `app/services/runtime_loader_service.py` | 🔴 **RED** | Runtime 서비스, 접촉 금지 |
| `app/services/feature_cache.py` | 🔴 **RED** | 캐시 구현, 접촉 금지 |
| `app/services/injection_gateway.py` | 🔴 **RED** | Stage 1 봉인, 접촉 금지 |
| `app/services/registry_service.py` | 🔴 **RED** | Stage 1 봉인, 접촉 금지 |
| `app/api/routes/registry.py` | 🔴 **RED** | Stage 1 봉인, 접촉 금지 |
| `exchanges/*` | 🔴 **RED** | 브로커 어댑터, 접촉 금지 |

### 3-2. 함수 분류

| 함수 | 파일 | 등급 | 근거 |
|------|------|:----:|------|
| `SymbolScreener.screen()` | symbol_screener.py | 🟢 **GREEN** | Pure, stateless, sync |
| `SymbolScreener._stage1~5()` | symbol_screener.py | 🟢 **GREEN** | Pure 내부 계산 |
| `BacktestQualifier.qualify()` | backtest_qualification.py | 🟢 **GREEN** | Pure, stateless, sync |
| `BacktestQualifier._check1~7()` | backtest_qualification.py | 🟢 **GREEN** | Pure 내부 계산 |
| `get_sector_weight()` | sector_rotator.py | 🟢 **GREEN** | Pure, stateless, sync |
| `compute_rotation()` | sector_rotator.py | 🟢 **GREEN** | Pure, stateless, sync |
| `apply_sector_weight_to_score()` | sector_rotator.py | 🟢 **GREEN** | Screening 점수 조정 hook |
| `AssetService.get_symbol()` | asset_service.py | 🟡 **YELLOW** | DB SELECT, read-only |
| `AssetService.list_core_symbols()` | asset_service.py | 🟡 **YELLOW** | DB SELECT, read-only |
| `AssetService.get_screening_history()` | asset_service.py | 🟡 **YELLOW** | DB SELECT, read-only |
| `AssetService.register_symbol()` | asset_service.py | 🟠 **AMBER** | DB INSERT, broker guard |
| `AssetService.transition_status()` | asset_service.py | 🟠 **AMBER** | DB UPDATE + audit |
| `AssetService.process_expired_ttl()` | asset_service.py | 🟠 **AMBER** | DB UPDATE, manual, max 10 |
| **`AssetService.screen_and_update()`** | **asset_service.py** | 🔴 **RED (FROZEN)** | **DB INSERT + UPDATE, 접촉 절대 금지** |
| **`AssetService.qualify_and_record()`** | **asset_service.py** | 🔴 **RED (FROZEN)** | **DB INSERT + UPDATE, 접촉 절대 금지** |

---

## 4. 오염 패턴 사전

Stage 3B에서 금지되는 패턴 목록. 이후 Purity Guard 테스트의 입력물.

### 4-1. 금지 Import (16종)

| # | 패턴 | 위험 | 이유 |
|:-:|------|:----:|------|
| P1 | `import asyncio` | HIGH | Pure 파일에 async 오염 |
| P2 | `from sqlalchemy` | HIGH | DB 의존 유입 |
| P3 | `from sqlalchemy.ext.asyncio import AsyncSession` | HIGH | DB 세션 의존 |
| P4 | `import httpx` | HIGH | 네트워크 호출 |
| P5 | `import requests` | HIGH | 네트워크 호출 |
| P6 | `import aiohttp` | HIGH | 네트워크 호출 |
| P7 | `from celery` | HIGH | Task 등록 위험 |
| P8 | `import redis` | MED | 캐시 의존 |
| P9 | `import os` | MED | 환경변수/파일 접근 |
| P10 | `from dotenv` | MED | 환경변수 로딩 |
| P11 | `import socket` | MED | 소켓 통신 |
| P12 | `import urllib` | MED | HTTP 클라이언트 |
| P13 | `import subprocess` | MED | 프로세스 실행 |
| P14 | `import shutil` | LOW | 파일 조작 |
| P15 | `import tempfile` | LOW | 임시 파일 |
| P16 | `from app.services.regime_detector` | HIGH | CR-046 금지 위반 |

### 4-2. 금지 Async 패턴 (3종)

| # | 패턴 | 위험 | 이유 |
|:-:|------|:----:|------|
| A1 | `async def` (pure 파일 내) | HIGH | Pure 계층에 async 오염 |
| A2 | `await` (pure 파일 내) | HIGH | 비동기 호출 침투 |
| A3 | `asyncio.run()` / `asyncio.get_event_loop()` | HIGH | 이벤트루프 직접 접근 |

### 4-3. 금지 Side-effect 패턴 (9종)

| # | 패턴 | 위험 | 이유 |
|:-:|------|:----:|------|
| S1 | `open(` (파일 열기) | MED | 파일 I/O |
| S2 | `Path(` + `.read_text` / `.write_text` | MED | 파일 I/O |
| S3 | `os.environ` / `os.getenv` | MED | 환경변수 접근 |
| S4 | `json.load(` / `json.dump(` (파일 경유) | MED | 파일 I/O |
| S5 | `.add(` / `.flush(` / `.commit(` (session 메서드) | HIGH | DB write |
| S6 | `.execute(` (SQL) | HIGH | DB query |
| S7 | `@app.task` / `@shared_task` | HIGH | Celery task 등록 |
| S8 | `@celery_app.task` | HIGH | Celery task 등록 |
| S9 | `beat_schedule` 수정 | HIGH | 스케줄 변경 |

### 4-4. 금지 Runtime 의존 패턴 (4종)

| # | 패턴 | 위험 | 이유 |
|:-:|------|:----:|------|
| R1 | `AssetService` import (pure 파일에서) | HIGH | Service layer 의존 침투 |
| R2 | `RegistryService` import | HIGH | 봉인된 Stage 1 의존 |
| R3 | `InjectionGateway` import | HIGH | 봉인된 Stage 1 의존 |
| R4 | `RuntimeStrategyLoader` import | HIGH | Runtime 실행 의존 |

---

## 5. Screener 데이터 요구사항 역방향 추출

### 5-1. ScreeningInput → DataProvider 매핑

| ScreeningInput 필드 | Stage | DataProvider 타입 | 매핑 필드 | None 시 동작 |
|---------------------|:-----:|-------------------|-----------|:------------:|
| `symbol` | ID | (caller) | — | 필수 |
| `asset_class` | ID | (caller) | — | 필수 |
| `sector` | 1 | (caller) | — | 필수 |
| `market_cap_usd` | 1 | `MarketDataSnapshot` | `market_cap_usd` | skip |
| `listing_age_days` | 1 | (외부 데이터) | 미정의 | skip |
| `avg_daily_volume_usd` | 2 | `MarketDataSnapshot` | `avg_daily_volume_usd` | **FAIL** |
| `spread_pct` | 2 | `MarketDataSnapshot` | `spread_pct` | skip |
| `atr_pct` | 3 | `MarketDataSnapshot` | `atr_pct` | **FAIL** |
| `adx` | 3 | `MarketDataSnapshot` | `adx` | **FAIL** |
| `price_vs_200ma` | 3 | `MarketDataSnapshot` | `price_vs_200ma` | skip |
| `per` | 4 | `FundamentalSnapshot` | `per` | skip |
| `roe` | 4 | `FundamentalSnapshot` | `roe` | skip |
| `tvl_usd` | 4 | `FundamentalSnapshot` | `tvl_usd` | skip |
| `available_bars` | 5 | `BacktestReadiness` | `available_bars` | **FAIL** |
| `sharpe_ratio` | 5 | `BacktestReadiness` | `sharpe_ratio` | skip |
| `missing_data_pct` | 5 | `BacktestReadiness` | `missing_data_pct` | skip |

### 5-2. Missing-Aware 필드 (None = FAIL)

| 필드 | Stage | FAIL 이유 |
|------|:-----:|-----------|
| `avg_daily_volume_usd` | 2 | 유동성 판단 불가 → 보수적 거부 |
| `atr_pct` | 3 | 변동성 판단 불가 → 보수적 거부 |
| `adx` | 3 | 추세 강도 판단 불가 → 보수적 거부 |
| `available_bars` | 5 | 백테스트 가용성 판단 불가 → 보수적 거부 |

**이 4개 필드는 DataProvider가 반드시 채워야 하는 필수 필드.**
DataQuality가 UNAVAILABLE인 경우에도 None 전달 → screener에서 FAIL 처리.

### 5-3. Stale/Partial 허용 한도 (현재 미정의)

| 항목 | 현재 상태 | Stage 3B 정의 필요 |
|------|-----------|:------------------:|
| 시세 stale 허용 | 미정의 | ✅ |
| 거래량 stale 허용 | 미정의 | ✅ |
| 기본적분석 stale 허용 | 미정의 | ✅ |
| 부분 데이터 허용 정책 | 미정의 | ✅ |
| DataQuality → ScreeningInput 변환 정책 | 미정의 | ✅ |

### 5-4. listing_age_days 공백

| 항목 | 상태 |
|------|------|
| ScreeningInput에 존재 | ✅ |
| MarketDataSnapshot에 대응 필드 | ❌ 없음 |
| FundamentalSnapshot에 대응 필드 | ❌ 없음 |

**listing_age_days는 DataProvider 계약에 포함되지 않음.** 별도 소스(registry metadata 또는 외부 API)에서 채워야 함.

---

## 6. Stage 3B 접촉 허용/금지표

### 6-1. 접촉 허용 (Allowed Touch Matrix)

| # | 대상 | 허용 범위 | 조건 |
|:-:|------|-----------|------|
| T1 | `sector_rotator.py` | E4: SectorWeight에 reason 필드 추가 | frozen dataclass 확장, 기존 API 비파괴 |
| T2 | `data_provider.py` | E9: ProviderCapability dataclass 추가 | 신규 frozen dataclass, 기존 ABC 비수정 |
| T3 | `data_provider.py` | E10: DataQuality 정책 함수 추가 | 신규 pure 함수, 기존 코드 비수정 |
| T4 | `tests/test_sector_rotator.py` | Purity Guard 테스트 강화 | 기존 테스트 비수정, 신규 테스트 추가만 |
| T5 | `tests/test_data_provider.py` | Purity Guard 테스트 강화 | 기존 테스트 비수정, 신규 테스트 추가만 |
| T6 | 신규: `tests/test_purity_guard.py` | 통합 Purity Guard 테스트 | 신규 파일 생성 |
| T7 | 신규: `tests/test_failure_modes.py` | Failure Mode 테스트 | 신규 파일 생성 |

### 6-2. 접촉 금지 (Prohibited Touch Matrix)

| # | 대상 | 금지 사유 | 위반 시 |
|:-:|------|-----------|---------|
| X1 | **`screen_and_update()`** | **FROZEN** | 즉시 중단 |
| X2 | **`qualify_and_record()`** | **FROZEN** | 즉시 중단 |
| X3 | `asset_service.py` 전체 | AMBER, Stage 2B 봉인 | A 승인 필요 |
| X4 | `symbol_screener.py` 로직 수정 | GREEN이지만 screening core | 수정 금지, 읽기만 |
| X5 | `backtest_qualification.py` 로직 수정 | GREEN이지만 qualification core | 수정 금지, 읽기만 |
| X6 | `workers/celery_app.py` | RED, beat/task 등록 | 접촉 금지 |
| X7 | `workers/tasks/*` | RED, task 생성/수정 | 접촉 금지 |
| X8 | `exchanges/*` | RED, 브로커 어댑터 | 접촉 금지 |
| X9 | `injection_gateway.py` | RED, Stage 1 봉인 | 접촉 금지 |
| X10 | `registry_service.py` | RED, Stage 1 봉인 | 접촉 금지 |
| X11 | `registry.py` (API) | RED, Stage 1 봉인 | 접촉 금지 |
| X12 | `runtime_strategy_loader.py` | RED, Runtime 실행 | 접촉 금지 |
| X13 | `feature_cache.py` | RED, 캐시 구현 | 접촉 금지 |
| X14 | `asset_validators.py` 로직 수정 | YELLOW, Stage 2A 봉인 | 수정 금지 |
| X15 | `constitution.py` 상수 수정 | YELLOW, Stage 2A 봉인 | 수정 금지 |

### 6-3. Stage 3B-1 vs 3B-2 경계 기준 (Litmus Test)

| 질문 | YES → 3B-1 | NO → 3B-2 |
|------|:-----------:|:---------:|
| 외부 API 호출이 필요한가? | | ✅ |
| DB 세션이 필요한가? | | ✅ |
| Celery task가 필요한가? | | ✅ |
| async 구현이 필요한가? | | ✅ |
| 기존 FROZEN 함수를 수정하는가? | | **금지** |
| 기존 screening 로직을 변경하는가? | | **금지** |
| pure 함수/계약만 추가하는가? | ✅ | |
| frozen dataclass만 추가하는가? | ✅ | |
| 테스트만 추가하는가? | ✅ | |

---

## 7. 오염 시작점 지도

### 7-1. Pure → Runtime 오염 경계선

```
                    PURE ZONE (GREEN)
    ┌─────────────────────────────────────────┐
    │  sector_rotator.py     (계산)            │
    │  data_provider.py      (인터페이스)       │
    │  symbol_screener.py    (5단계 계산)       │
    │  backtest_qualification.py (7단계 계산)   │
    │  asset_validators.py   (7 pure 검증)     │
    │  constitution.py       (상수 정의)        │
    └─────────────────┬───────────────────────┘
                      │
    ══════════════════╪════════════════════════ ← 🔴 오염 경계선
                      │
              RUNTIME ZONE (AMBER/RED)
    ┌─────────────────┴───────────────────────┐
    │  asset_service.py  (DB CRUD + 오케스트레이션)│
    │    ├─ screen_and_update()  ← FROZEN     │
    │    ├─ qualify_and_record() ← FROZEN     │
    │    ├─ register_symbol()                 │
    │    └─ transition_status()               │
    ├─────────────────────────────────────────┤
    │  workers/tasks/*   (Celery task)        │
    │  exchanges/*       (브로커 API)          │
    │  injection_gateway (검증 + 차단)         │
    │  registry_service  (CRUD)               │
    └─────────────────────────────────────────┘
```

### 7-2. Stage 3B가 오염 경계를 넘는 시나리오 (금지)

| # | 시나리오 | 결과 | 방지책 |
|:-:|---------|------|--------|
| C1 | DataProvider 구현체가 sector_rotator.py에 import됨 | Pure 오염 | P1-P5 금지 패턴 검사 |
| C2 | ScreeningDataProvider가 asset_service.py를 직접 호출 | FROZEN 침범 | R1 금지 패턴 검사 |
| C3 | sector_rotator에 async 함수 추가 | Pure 오염 | A1 금지 패턴 검사 |
| C4 | data_provider.py에 구현 코드 추가 | ABC 순수성 파괴 | AST body 검사 |
| C5 | screening_tasks.py 생성 | Beat/task 등록 위험 | X7 금지 규칙 |
| C6 | ProviderCapability가 DB 의존 | Pure 계약 오염 | P2-P3 금지 검사 |

---

## 중간 판정 체크리스트

| # | 확인 항목 | 결과 |
|:-:|----------|:----:|
| 1 | Pure 계층의 정확한 범위 확정 | ✅ §1 + §3 |
| 2 | Screener의 read-only 경계 확정 | ✅ §2-2 |
| 3 | Qualification/write path 시작점 확정 | ✅ §2-3 (L333, L475) |
| 4 | Stage 3B 허용 접촉면 후보 확정 | ✅ §6-1 (T1-T7) |
| 5 | Stage 3B 금지 접촉면 확정 | ✅ §6-2 (X1-X15) |
| 6 | 오염 패턴 사전 작성 | ✅ §4 (32종) |
| 7 | Screener 데이터 요구사항 역추출 | ✅ §5 (16필드) |
| 8 | listing_age_days 공백 식별 | ✅ §5-4 |
| 9 | Stale/Partial 정책 미정의 식별 | ✅ §5-3 |

---

```
CR-048 Stage 3B Boundary Inventory v1.0
Document ID: GOV-L3-STAGE3B-BOUNDARY-001
Date: 2026-04-03
Authority: A
Status: SUBMITTED (A 검토 대기)
Purpose: 경계 실사 — 설계 이전 확인
Pure Zone: 6 files (sector_rotator, data_provider, symbol_screener, backtest_qualification, asset_validators, constitution)
Runtime Zone: asset_service + workers + exchanges
FROZEN: screen_and_update ✅, qualify_and_record ✅
Allowed Touch: 7 items (T1-T7)
Prohibited Touch: 15 items (X1-X15)
Contamination Patterns: 32 types (P16 + A3 + S9 + R4)
Screener Data Fields: 16 (4 mandatory, 12 optional)
```
