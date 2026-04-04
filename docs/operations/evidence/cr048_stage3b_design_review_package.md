# CR-048 Stage 3B 설계 검토 패키지

**문서 ID:** GOV-L3-STAGE3B-DESIGN-001
**작성일:** 2026-04-04
**Authority:** A (Decision Authority)
**CR:** CR-048
**전제:** Stage 3A L3 SEALED (4927/4927 PASS)
**변경 등급:** L0 (설계 문서 — 승인 전 구현 금지)

> 본 문서는 Stage 3B 설계 검토 패키지입니다. A 승인 전까지 구현 착수하지 않습니다.
> 포함 산출물: (1) Scope Review, (2) Boundary Contract Spec, (3) Failure Mode Matrix, (4) Purity Guard 강화 설계서, (5) Test Plan

---

# (1) 해석 및 요약

## Stage 3B의 본질

Stage 3B는 기능 추가가 아니라 **"계약층과 구현층 사이의 방화벽 설계"** 단계입니다.

Stage 3A에서 확보한 순수 계층:
- `sector_rotator.py` — 순수 계산, I/O 없음
- `data_provider.py` — ABC/Protocol, 구현체 없음

Stage 3B에서 추가할 것:
- **Purity Guard** — Stage 3A 순수성 재오염 방지 장치
- **Capability Matrix** — DataProvider 구현체 계약
- **Failure Mode** — empty/partial/stale/timeout 정책
- **SectorRotator reason code** — 설명용 보조 (runtime 분기 금지)

## 3B-1 / 3B-2 분리 제안

A의 제안대로 Stage 3B를 2단계로 분리합니다.

| 단계 | 범위 | 위험 |
|------|------|:----:|
| **3B-1** | 계약 강화 + Purity Guard + Failure Matrix + reason code | LOW |
| **3B-2** | adapter stub / fixture 기반 read-only 연결 검증 | MEDIUM |

### 분리 근거

1. 3B-1은 **코드 변경 없이도 테스트만으로 경계를 강화**할 수 있음
2. 3B-2는 **구현체 stub 생성이 필요**하여 import 오염 위험 발생
3. 3B-1 봉인 후 3B-2 진입이 안전 순서

### Litmus Test

> "이 변경이 `data_provider.py` 또는 `sector_rotator.py`에 신규 import를 추가하는가?"
> - NO → 3B-1
> - YES → 3B-2

---

# (2) 장점 / 단점

## 장점

| 장점 | 설명 |
|------|------|
| **계약 선행** | 구현 전에 실패 모드/능력/정규화 규칙을 확정 |
| **재오염 방지** | Purity Guard가 Stage 3A 파일을 자동 보호 |
| **2단계 분리** | 계약 강화(3B-1)와 연결 검증(3B-2)을 분리하여 위험 절반 |
| **read-only 보장** | write path 0 유지 |

## 단점

| 단점 | 완화 |
|------|------|
| 구현체 없이 계약만 추가하므로 실제 검증 제한 | 3B-2에서 stub 기반 검증 수행 |
| Purity Guard 테스트가 false positive 가능 | 금지 패턴 목록을 명확히 정의 |
| Capability Matrix가 구현 전에는 가설적 | CoinGecko/KIS 공식 API 문서 기반 |

---

# (3) 이유 / 근거

## 근거 1 — Stage 3A의 최대 위협은 "구현체 연결 시 오염"

Stage 3A가 순수한 이유는 **아무것도 연결되지 않았기 때문**. 구현체를 붙이는 순간 `data_provider.py`에 httpx/aiohttp/sqlalchemy가 들어올 수 있음. Purity Guard가 이 시점에서 자동 차단해야 함.

## 근거 2 — DataProvider 구현체 차이가 runtime if문으로 퍼지면 안 됨

CoinGecko는 REST, KIS는 WebSocket, KRX는 파일 다운로드. 구현체별 차이를 Capability Matrix로 선언하면 runtime 분기를 계약 수준에서 제어 가능.

## 근거 3 — 실패 모드를 미리 정의하지 않으면 fail-closed가 깨짐

Stage 2B의 fail-closed는 잘 작동했지만, 외부 API 실패는 다른 차원. timeout, partial data, stale data, rate limit 각각에 대한 정책이 없으면 cascading failure.

---

# (4) 실현 · 구현 대책

---

## Section A: Purity Guard 강화 설계서

### 목적

Stage 3A의 `sector_rotator.py`와 `data_provider.py`가 이후 단계에서 재오염되는 것을 **테스트 수준에서 자동 차단**.

### 금지 Import 패턴 (Pure 파일용)

| # | 금지 패턴 | 사유 |
|:-:|-----------|------|
| 1 | `import httpx` / `from httpx` | 네트워크 I/O |
| 2 | `import requests` / `from requests` | 네트워크 I/O |
| 3 | `import aiohttp` / `from aiohttp` | 네트워크 I/O |
| 4 | `from sqlalchemy` / `import sqlalchemy` | DB 접근 |
| 5 | `AsyncSession` | DB 세션 |
| 6 | `from celery` / `import celery` | Task 시스템 |
| 7 | `from workers` | Task 시스템 |
| 8 | `import os` (직접) | 환경/파일 접근 |
| 9 | `open(` (함수 호출) | 파일 I/O |
| 10 | `regime_detector` (import) | CR-046 금지 |

### 금지 Async 패턴 (sector_rotator.py 전용)

| # | 금지 패턴 | 사유 |
|:-:|-----------|------|
| 1 | `async def` | 순수 sync 모듈 |
| 2 | `await` | 순수 sync 모듈 |
| 3 | `asyncio.` | 순수 sync 모듈 |

> **data_provider.py는 ABC 메서드가 async이므로 async def 자체는 허용.** 단, `await`가 실제 I/O를 수행하는 구현 코드는 금지.

### 금지 Side-effect 패턴

| # | 금지 패턴 | 사유 |
|:-:|-----------|------|
| 1 | `db.add(` / `db.flush(` / `db.commit(` | DB write |
| 2 | `db.execute(` | DB query |
| 3 | `.post(` / `.put(` / `.delete(` / `.patch(` | HTTP write |
| 4 | `os.environ` | 환경변수 |
| 5 | `cache.set(` / `cache.get(` | 캐시 접근 |
| 6 | `create_task(` / `send_task(` | Task dispatch |

### Purity Guard 테스트 구조

```python
# tests/test_purity_guard.py
class TestPurityGuard:
    """자동 재오염 방지 — Stage 3A pure 파일 보호."""

    PURE_FILES = [
        "app/services/sector_rotator.py",
        "app/services/data_provider.py",
    ]

    FORBIDDEN_IMPORTS = [
        "httpx", "requests", "aiohttp", "sqlalchemy",
        "celery", "workers", "regime_detector",
    ]

    FORBIDDEN_PATTERNS = [
        "AsyncSession", "db.add(", "db.flush(", "db.commit(",
        "os.environ", "cache.set(", "create_task(",
    ]

    # sector_rotator.py 전용
    SYNC_ONLY_FILES = ["app/services/sector_rotator.py"]
    FORBIDDEN_ASYNC = ["async def", "await ", "asyncio."]
```

### 적용 시점

- **3B-1 착수 시** Purity Guard 테스트 먼저 작성
- 이후 모든 Stage에서 회귀에 포함
- Stage 3A 파일 수정 시 Guard가 먼저 FAIL → 수정 차단

---

## Section B: Boundary Contract Spec

### DataProvider Capability Matrix

| Capability | CoinGecko (Crypto) | KIS (US/KR Stock) | KRX (KR Stock) | 필수 여부 |
|------------|:------------------:|:-----------------:|:--------------:|:---------:|
| `supports_price` | YES | YES | YES | **필수** |
| `supports_market_cap` | YES | YES | YES | **필수** |
| `supports_volume` | YES | YES | YES | **필수** |
| `supports_spread` | NO | YES | NO | 선택 |
| `supports_ohlcv` | YES (via exchange) | YES | YES | **필수** |
| `supports_per` | NO | YES | YES | 시장별 |
| `supports_roe` | NO | YES | YES | 시장별 |
| `supports_tvl` | YES (DeFiLlama) | NO | NO | 시장별 |
| `supports_active_addresses` | YES (limited) | NO | NO | 선택 |
| `freshness_granularity` | 1min (price), 24h (fundamental) | 실시간 | 15min delay | — |
| `rate_limit` | 10-50 req/min (free) | 제한적 | 파일 기반 | — |
| `auth_required` | NO (free tier) | YES (API key) | NO | — |
| `symbol_namespace` | `coingecko_id` (e.g. "solana") | ticker (e.g. "AAPL") | 종목코드 6자리 | — |

### Capability Matrix Protocol 계약

```python
@dataclass(frozen=True)
class ProviderCapability:
    """Stage 3B-1: 구현체가 선언해야 하는 능력 명세."""
    supports_price: bool = False
    supports_market_cap: bool = False
    supports_volume: bool = False
    supports_spread: bool = False
    supports_ohlcv: bool = False
    supports_per: bool = False
    supports_roe: bool = False
    supports_tvl: bool = False
    supports_active_addresses: bool = False
    freshness_seconds: int = 3600  # default 1h
    rate_limit_per_minute: int = 10
    auth_required: bool = False
```

### Symbol Normalization Contract

| 시장 | 입력 형태 | 정규화 결과 | 함수 |
|------|-----------|------------|------|
| CRYPTO | `"sol/usdt"`, `"SOL/USDT"`, `" BTC/USDT "` | `"SOL/USDT"` | `canonicalize_symbol()` |
| US_STOCK | `"aapl"`, `"NASDAQ:NVDA"` | `"AAPL"`, `"NVDA"` | `canonicalize_symbol()` |
| KR_STOCK | `"5930"`, `"KRX:035420"` | `"005930"`, `"035420"` | `canonicalize_symbol()` |

> 기존 `canonicalize_symbol()` (asset.py)이 이미 구현됨. DataProvider 구현체는 이 함수를 반드시 사용.

### Symbol Namespace Mapping Contract

| 내부 정규형 | CoinGecko ID | KIS Ticker | KRX 코드 |
|------------|:------------:|:----------:|:--------:|
| `"SOL/USDT"` | `"solana"` | N/A | N/A |
| `"AAPL"` | N/A | `"AAPL"` | N/A |
| `"005930"` | N/A | N/A | `"005930"` |

> namespace 변환은 **구현체 내부 책임**. ABC 인터페이스는 내부 정규형만 받음.

### Partial Data Policy

| 필드 | 없을 때 | 동작 |
|------|---------|------|
| `price_usd` | None | MarketDataSnapshot quality → DEGRADED |
| `market_cap_usd` | None | Stage 2 liquidity → FAIL (fail-closed) |
| `avg_daily_volume_usd` | None | Stage 2 liquidity → FAIL |
| `atr_pct` | None | Stage 3 technical → FAIL |
| `adx` | None | Stage 3 technical → FAIL |
| `per` (stocks) | None | Stage 4 fundamental → FAIL |
| `tvl_usd` (crypto) | None | Stage 4 fundamental → FAIL |
| `available_bars` | None | Stage 5 backtest → FAIL |

> **원칙: 데이터 없음 = 해당 단계 FAIL.** 이는 SymbolScreener의 기존 동작과 일치.

### Stale Data Policy

| freshness | 동작 |
|-----------|------|
| < 1시간 | DataQuality.HIGH |
| 1~24시간 | DataQuality.DEGRADED — 스크리닝 실행 가능하나 경고 기록 |
| 24~72시간 | DataQuality.STALE — 스크리닝 실행 가능하나 결과 신뢰도 표시 |
| > 72시간 | DataQuality.UNAVAILABLE — 해당 필드 None 처리 → Stage FAIL |

---

## Section C: Failure Mode Matrix

| # | Failure Mode | 원인 | 감지 방법 | 정책 | 심각도 |
|:-:|-------------|------|----------|------|:------:|
| F1 | **Provider Timeout** | 네트워크 지연, API 서버 다운 | health_check() False | DataQuality.UNAVAILABLE → Stage FAIL | HIGH |
| F2 | **Rate Limit** | 요청 초과 | HTTP 429 응답 | 재시도 금지, UNAVAILABLE 반환 | MEDIUM |
| F3 | **Partial Response** | API가 일부 필드만 반환 | None 필드 카운트 | DEGRADED + 누락 필드별 Stage FAIL | MEDIUM |
| F4 | **Stale Data** | 캐시된 구 데이터 | timestamp 비교 | Stale Data Policy 적용 | LOW |
| F5 | **Invalid Symbol** | namespace 불일치 | canonicalize_symbol() 실패 | 해당 심볼 스크리닝 스킵 | LOW |
| F6 | **Auth Failure** | API key 만료/무효 | HTTP 401/403 | UNAVAILABLE + 경고 로그 | HIGH |
| F7 | **Data Inconsistency** | 소스 간 가격 불일치 | 기준 없음 (단일 소스) | N/A (단일 소스 정책) | LOW |
| F8 | **Provider Complete Outage** | 전체 API 불가 | 모든 health_check() False | 스크리닝 전체 중단, CORE 유지 | **CRITICAL** |
| F9 | **Cascading Failure** | Provider 실패 → 대량 FAIL → CORE 축소 | demote 카운트 > threshold | process_expired_ttl max_count=10 적용 | **CRITICAL** |

### Fail-Closed 전략 (Failure Mode별)

| Failure | 행동 | 근거 |
|---------|------|------|
| F1 Timeout | **CORE 유지** — 스크리닝 스킵 | 데이터 없음 ≠ 부적격 |
| F2 Rate Limit | **CORE 유지** — 재시도 안 함 | 다음 주기에 재시도 |
| F3 Partial | **해당 Stage FAIL** — 나머지 Stage 정상 진행 | 부분 데이터는 판단 불가 |
| F4 Stale | **정책별 분기** — 72h 초과 시 UNAVAILABLE | 시간 기반 열화 |
| F5 Invalid Symbol | **스킵** — 해당 심볼만 제외 | 다른 심볼에 영향 없음 |
| F6 Auth | **UNAVAILABLE** — 전체 provider 비활성 | 복구 전까지 미사용 |
| F8 Complete Outage | **전체 스크리닝 중단** — CORE pool 보존 | 가장 안전한 기본값 |
| F9 Cascading | **max_count=10 cap 유지** — 대량 강등 방지 | Stage 2B 패턴 |

---

## Section D: SectorRotator Reason Code

### 허용 범위

| 용도 | 허용 여부 |
|------|:---------:|
| 대시보드 표시 | ✅ |
| 감사 로그 기록 | ✅ |
| SymbolStatusAudit context 필드 | ✅ |
| 설명용 tooltip/annotation | ✅ |

### 금지 범위

| 용도 | 허용 여부 | 사유 |
|------|:---------:|------|
| runtime 분기 조건 | ❌ | 실행 경로 오염 |
| qualification 점수 변경 | ❌ | Phase 4 경계 침범 |
| screen_and_update() 내 조건문 | ❌ | FROZEN |
| beat/task 트리거 | ❌ | Stage 3B 금지 |
| Symbol.status 변경 근거 | ❌ | 수동 경로만 허용 |

### Reason Code 정의

```python
class RotationReasonCode(str, Enum):
    """SectorRotator 가중치 변경 사유 — 설명용 전용."""
    REGIME_TRENDING_UP = "regime_trending_up"
    REGIME_TRENDING_DOWN = "regime_trending_down"
    REGIME_RANGING = "regime_ranging"
    REGIME_HIGH_VOL = "regime_high_vol"
    REGIME_CRISIS = "regime_crisis"
    REGIME_UNKNOWN = "regime_unknown"
    SECTOR_OVERWEIGHT = "sector_overweight"
    SECTOR_UNDERWEIGHT = "sector_underweight"
    SECTOR_NEUTRAL = "sector_neutral"
```

### 통합 지점

`SectorWeight` dataclass에 `reason: RotationReasonCode` 필드 추가:

```python
@dataclass(frozen=True)
class SectorWeight:
    sector: AssetSector
    weight: float
    regime: str
    reason: RotationReasonCode  # Stage 3B-1 추가
```

---

## Section E: Stage 3B 범위 정의

### 3B-1 범위 (본 설계 검토 대상)

| 허용 | 파일 | 작업 |
|------|------|------|
| Purity Guard 테스트 | `tests/test_purity_guard.py` (신규) | 금지 패턴 자동 검사 |
| ProviderCapability 계약 | `data_provider.py` 확장 | frozen dataclass 추가 |
| RotationReasonCode | `sector_rotator.py` 확장 | enum + SectorWeight 필드 추가 |
| Failure Mode 테스트 | `tests/test_failure_modes.py` (신규) | empty/partial/stale/timeout 계약 |
| Capability Matrix 테스트 | `tests/test_data_provider.py` 확장 | ProviderCapability 계약 검증 |

| 금지 | 사유 |
|------|------|
| DataProvider 구현체 | 3B-2 |
| adapter stub (테스트 파일 외) | 3B-2 |
| beat/task 등록 | Stage 3B 전체 금지 |
| DB write | Stage 3B 전체 금지 |
| screen_and_update() 수정 | FROZEN |
| qualify_and_record() 수정 | FROZEN |
| 외부 API 실연결 | Stage 3B 전체 금지 |

### 3B-2 범위 (3B-1 봉인 후 별도 심사)

| 허용 후보 | 파일 | 위험 |
|-----------|------|:----:|
| DataProvider adapter stub | `tests/` 내 fixture only | LOW |
| In-memory fake provider | `tests/` 내 fixture only | LOW |
| Symbol namespace mapper | `data_provider.py` 확장 | MEDIUM |
| read-only 통합 테스트 | `tests/` | MEDIUM |

### GREEN / RED / AMBER (3B-1)

#### GREEN

| 파일 | 작업 |
|------|------|
| `tests/test_purity_guard.py` | **신규** |
| `tests/test_failure_modes.py` | **신규** |
| `tests/test_data_provider.py` | **확장** (ProviderCapability 테스트) |
| `tests/test_sector_rotator.py` | **확장** (reason code 테스트) |
| `app/services/data_provider.py` | **확장** (ProviderCapability dataclass) |
| `app/services/sector_rotator.py` | **확장** (RotationReasonCode enum + SectorWeight.reason) |

#### RED

| 파일 | 사유 |
|------|------|
| `app/services/asset_service.py` | FROZEN (screen_and_update, qualify_and_record) |
| `app/services/symbol_screener.py` | 미접촉 |
| `app/services/backtest_qualification.py` | Phase 4 |
| `workers/*` | task/beat 금지 |
| `exchanges/*` | 브로커 금지 |
| `app/services/runtime_*` | Phase 5 |
| `app/services/injection_gateway.py` | Stage 1 SEALED |
| `app/services/registry_service.py` | Stage 1 SEALED |

#### AMBER

| 파일 | 조건 |
|------|------|
| `app/models/asset.py` | 접촉 불요 (3B-1에서 모델 변경 없음) |

---

# (5) 실행방법

## Test Plan

### 3B-1 전용 테스트 계획

| 테스트 파일 | 대상 | 예상 수 |
|------------|------|:-------:|
| `test_purity_guard.py` (신규) | 금지 import/async/side-effect 패턴 검사 | ~20 |
| `test_failure_modes.py` (신규) | DataQuality 정책, partial/stale/timeout 계약 | ~15 |
| `test_data_provider.py` (확장) | ProviderCapability 계약, capability 필수 필드 | ~8 |
| `test_sector_rotator.py` (확장) | RotationReasonCode, SectorWeight.reason | ~7 |
| **예상 합계** | | **~50** |

### 회귀 보호 계획

| 측정 | 현재 | 3B-1 후 예상 |
|------|:----:|:-----------:|
| 전체 테스트 | 4927 | ~4977 (+50) |
| 실패 허용 | 0 | **0** |
| Purity Guard | 0 | ~20 (신규 경계 보호) |

### 봉인 조건 (3B-1)

| # | 조건 |
|:-:|------|
| 1 | Purity Guard 테스트 PASS (금지 패턴 전수 검사) |
| 2 | Failure Mode 계약 테스트 PASS |
| 3 | ProviderCapability 계약 테스트 PASS |
| 4 | RotationReasonCode 테스트 PASS |
| 5 | RED 파일 미접촉 |
| 6 | screen_and_update() FROZEN 유지 |
| 7 | qualify_and_record() FROZEN 유지 |
| 8 | 외부 API 실호출 0건 |
| 9 | DB write 0건 |
| 10 | 전체 회귀 PASS |
| 11 | A 판정 |

---

## A 심사 8항목 충족 계획

| # | 심사 항목 | 충족 방법 |
|:-:|----------|----------|
| 1 | Pure 파일 오염 방지 | `test_purity_guard.py` — 금지 import/async/side-effect 10+3+6 패턴 검사 |
| 2 | 구현체 분리 | DataProvider ABC + ProviderCapability 계약, 구현체는 3B-2 |
| 3 | Read-only 보장 | write path 0 — Purity Guard에서 db.add/flush/commit 패턴 차단 |
| 4 | Runtime 분리 | screen/qualify FROZEN, Purity Guard에서 regime_detector import 차단 |
| 5 | Failure contract | `test_failure_modes.py` — F1~F9 전부 계약 테스트 |
| 6 | Symbol contract | canonicalize_symbol() 기존 함수 + namespace mapping 계약 |
| 7 | Capability matrix | ProviderCapability frozen dataclass + 필수 필드 검증 |
| 8 | 회귀 전략 | 기존 4927 유지 + 신규 ~50 추가, 0 fail 허용 |

---

# (6) 더 좋은 아이디어

## 아이디어 1 — Purity Guard를 conftest.py fixture로도 제공

`test_purity_guard.py`를 독립 테스트 파일로 두되, `conftest.py`에도 session-scope fixture로 등록하면, **어떤 테스트 파일을 실행해도** 항상 Purity Guard가 먼저 통과해야 함.

## 아이디어 2 — DataProvider에 `supported_markets()` 메서드 추가

```python
@abstractmethod
def supported_markets(self) -> list[AssetClass]:
    """Return asset classes this provider covers."""
    ...
```

이렇게 하면 구현체가 "CRYPTO만 지원"인지 "US_STOCK+KR_STOCK"인지를 런타임에 선언하여, 잘못된 시장 요청을 계약 수준에서 거부 가능.

## 아이디어 3 — Failure Mode를 "회복 불가 / 일시적 / 무시 가능"으로 3분류

| 등급 | Failure | 행동 |
|------|---------|------|
| **회복 불가** | F6 Auth, F8 Outage | provider 비활성, 수동 복구 필요 |
| **일시적** | F1 Timeout, F2 Rate Limit | 다음 주기에 자동 재시도 |
| **무시 가능** | F4 Stale (< 24h), F7 Inconsistency | 경고 로그만, 스크리닝 진행 |

이 분류가 있으면 Stage 3B-2에서 adapter stub의 에러 시뮬레이션이 더 정확해짐.

---

## 결론

> **Stage 3B-1 limited scope approval requested.**
>
> 범위: Purity Guard + Capability Matrix + Failure Mode Matrix + Reason Code
> CRITICAL 0건, 외부 연결 0건, DB write 0건, FROZEN 유지.
> 구현체 연결은 3B-2로 분리.
> A 승인 전까지 구현 착수하지 않습니다.

---

```
CR-048 Stage 3B Design Review Package v1.0
Document ID: GOV-L3-STAGE3B-DESIGN-001
Date: 2026-04-04
Authority: A
Status: SUBMITTED (A 설계 심사 대기)
Scope: 3B-1 (contracts + guards), 3B-2 (adapter stubs, separate review)
CRITICAL items: 0
External connections: 0
DB write: 0
screen_and_update(): FROZEN
qualify_and_record(): FROZEN
Implementation: NOT YET REQUESTED
```
