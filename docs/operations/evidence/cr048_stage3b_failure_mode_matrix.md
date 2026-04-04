# CR-048 Stage 3B Failure Mode Matrix

**문서 ID:** GOV-L3-STAGE3B-FAILMODE-001
**작성일:** 2026-04-03
**Authority:** A (Decision Authority)
**CR:** CR-048
**전제:** Boundary Contract Spec (GOV-L3-STAGE3B-CONTRACT-001)
**목적:** DataProvider → ScreeningInput 변환 시 발생 가능한 장애 모드와 fail-closed 정책 정의

> 이 문서는 장애 모드 분류와 정책만 포함한다. 구현 지침 없음.

---

## 1. DataQualityDecision Enum 정의

DataProvider 출력을 ScreeningInput으로 변환할 때 내리는 판정.

| 값 | 의미 | ScreeningInput 변환 |
|----|------|:-------------------:|
| `OK` | 데이터 정상, 변환 진행 | 정상 매핑 |
| `PARTIAL_USABLE` | 일부 필드 누락, 필수 필드 충족 | 누락 필드 = None 전달 |
| `PARTIAL_REJECT` | 필수 필드 누락, 변환 불가 | **변환 거부** |
| `STALE_USABLE` | 데이터 오래됨, 허용 범위 내 | 정상 매핑 + stale 플래그 |
| `STALE_REJECT` | 데이터 오래됨, 허용 범위 초과 | **변환 거부** |
| `INSUFFICIENT_BARS` | 백테스트 히스토리 부족 | **Stage 5 FAIL 전달** |
| `MISSING_LISTING_AGE` | listing_age_days 정보 부재 | **Stage 1 skip (보수적)** |
| `SYMBOL_NAMESPACE_ERROR` | 심볼 형식 불일치 | **변환 거부** |
| `PROVIDER_UNAVAILABLE` | Provider 자체 불통 | **변환 거부** |

---

## 2. Failure Mode 상세 (F1-F9)

### F1: EMPTY — 데이터 완전 부재

| 항목 | 값 |
|------|-----|
| **조건** | DataProvider가 모든 필드를 None/빈값으로 반환 |
| **DataQuality** | `UNAVAILABLE` |
| **Decision** | `PROVIDER_UNAVAILABLE` |
| **ScreeningInput 변환** | 거부 — ScreeningInput 생성하지 않음 |
| **Screener 도달** | 도달하지 않음 |
| **Fail-closed** | ✅ 보수적 거부, 종목은 현재 상태 유지 |
| **심각도** | HIGH |

### F2: PARTIAL — 필수 필드 누락

| 항목 | 값 |
|------|-----|
| **조건** | 필수 4개 필드 중 1개 이상 None (volume, atr, adx, available_bars) |
| **DataQuality** | `DEGRADED` |
| **Decision** | `PARTIAL_REJECT` |
| **ScreeningInput 변환** | 거부 — 필수 필드 미충족 |
| **Screener 도달** | 도달하지 않음 |
| **Fail-closed** | ✅ 필수 필드 없이 screening 시도하지 않음 |
| **심각도** | HIGH |

### F3: PARTIAL_OPTIONAL — 선택 필드만 누락

| 항목 | 값 |
|------|-----|
| **조건** | 필수 4개 충족, 선택 필드 일부 None (spread, per, roe, tvl 등) |
| **DataQuality** | `DEGRADED` |
| **Decision** | `PARTIAL_USABLE` |
| **ScreeningInput 변환** | 허용 — 누락 필드는 None으로 전달 |
| **Screener 도달** | ✅ screener가 None 필드를 skip 처리 (기존 동작) |
| **Fail-closed** | ✅ screener의 기존 None skip 메커니즘에 의존 |
| **심각도** | LOW |

### F4: STALE — 시세 데이터 오래됨

| 항목 | 값 |
|------|-----|
| **조건** | MarketDataSnapshot.timestamp가 현재 시각 대비 허용 한도 초과 |
| **stale 허용 한도** | 아래 §3 Stale Policy 참조 |
| **DataQuality** | `STALE` |
| **Decision** | `STALE_USABLE` 또는 `STALE_REJECT` (한도에 따라) |
| **ScreeningInput 변환** | USABLE: 허용 + stale 플래그 / REJECT: 거부 |
| **Fail-closed** | ✅ 한도 초과 시 변환 거부 |
| **심각도** | MEDIUM |

### F5: INSUFFICIENT_BARS — 히스토리 부족

| 항목 | 값 |
|------|-----|
| **조건** | BacktestReadiness.available_bars < 500 또는 None |
| **DataQuality** | `DEGRADED` 또는 `UNAVAILABLE` |
| **Decision** | `INSUFFICIENT_BARS` |
| **ScreeningInput 변환** | 허용 — available_bars=None 또는 실제값 전달 |
| **Screener 도달** | ✅ Stage 5에서 FAIL 처리 (기존 동작) |
| **Fail-closed** | ✅ screener Stage 5가 기존 fail-closed로 처리 |
| **심각도** | LOW (screener가 이미 처리) |

### F6: MISSING_LISTING_AGE — 상장일 정보 부재

| 항목 | 값 |
|------|-----|
| **조건** | listing_age_days를 어떤 DataProvider도 제공하지 못함 |
| **DataQuality** | `DEGRADED` |
| **Decision** | `MISSING_LISTING_AGE` |
| **ScreeningInput 변환** | 허용 — listing_age_days=None 전달 |
| **Screener 도달** | ✅ Stage 1에서 listing age 체크 skip (기존 동작) |
| **Fail-closed** | ⚠️ skip은 보수적이지 않음 — 향후 정책 강화 후보 |
| **심각도** | MEDIUM (계약 공백) |

### F7: SYMBOL_NAMESPACE_ERROR — 심볼 형식 불일치

| 항목 | 값 |
|------|-----|
| **조건** | Provider가 반환한 symbol이 내부 namespace와 불일치 (예: "BTCUSDT" vs "BTC/USDT") |
| **DataQuality** | N/A (매핑 이전 에러) |
| **Decision** | `SYMBOL_NAMESPACE_ERROR` |
| **ScreeningInput 변환** | 거부 |
| **Screener 도달** | 도달하지 않음 |
| **Fail-closed** | ✅ namespace 불일치 종목 screening 방지 |
| **심각도** | HIGH |

### F8: PROVIDER_TIMEOUT — Provider 응답 지연

| 항목 | 값 |
|------|-----|
| **조건** | DataProvider 호출이 timeout 내 응답하지 않음 |
| **DataQuality** | `UNAVAILABLE` |
| **Decision** | `PROVIDER_UNAVAILABLE` |
| **ScreeningInput 변환** | 거부 |
| **Screener 도달** | 도달하지 않음 |
| **Fail-closed** | ✅ timeout 시 screening 시도하지 않음 |
| **심각도** | MEDIUM |

### F9: QUALITY_GRADE_CONFLICT — 복수 Provider 품질 불일치

| 항목 | 값 |
|------|-----|
| **조건** | MarketData는 HIGH인데 Fundamental은 STALE 등 불일치 |
| **DataQuality** | 개별 provider별 상이 |
| **Decision** | 최저 등급 채택 (pessimistic merge) |
| **ScreeningInput 변환** | 최저 등급 기준으로 F1-F4 재판정 |
| **Fail-closed** | ✅ 낙관적 합산 금지, 비관적 병합 |
| **심각도** | LOW |

---

## 3. Stale Policy (시간 기반 허용 한도)

### 3-1. 자산 클래스별 stale 허용 한도

| 자산 클래스 | 데이터 유형 | USABLE 한도 | REJECT 한도 | 근거 |
|------------|-----------|:-----------:|:-----------:|------|
| CRYPTO | 시세/거래량 | ≤ 1시간 | > 1시간 | 24/7 시장, 빠른 변동 |
| CRYPTO | 기본적분석 (TVL 등) | ≤ 24시간 | > 24시간 | 일 단위 갱신 |
| US_STOCK | 시세/거래량 | ≤ 4시간 | > 4시간 | 거래시간 외 지연 허용 |
| US_STOCK | 기본적분석 (PER/ROE) | ≤ 7일 | > 7일 | 분기 보고서 기반 |
| KR_STOCK | 시세/거래량 | ≤ 4시간 | > 4시간 | 거래시간 외 지연 허용 |
| KR_STOCK | 기본적분석 | ≤ 7일 | > 7일 | 분기 보고서 기반 |
| ALL | 백테스트 히스토리 | ≤ 30일 | > 30일 | 히스토리 데이터 안정적 |

### 3-2. Stale 판정 로직 (pure 함수)

```
is_stale(snapshot_timestamp, asset_class, data_type) → DataQualityDecision
  if snapshot_timestamp is None → STALE_REJECT
  age = now_utc - snapshot_timestamp
  if age ≤ USABLE_LIMIT[asset_class][data_type] → OK
  if age ≤ REJECT_LIMIT[asset_class][data_type] → STALE_USABLE
  else → STALE_REJECT
```

**규칙:** 이 함수는 반드시 Pure Zone에 배치 (I/O 없음, 시각은 매개변수로 전달).

---

## 4. Partial Data Policy (필드 기반 허용 정책)

### 4-1. 필수 필드 (4개) — None이면 PARTIAL_REJECT

| # | 필드 | Stage | 이유 |
|:-:|------|:-----:|------|
| 1 | `avg_daily_volume_usd` | 2 | 유동성 판단 불가 |
| 2 | `atr_pct` | 3 | 변동성 판단 불가 |
| 3 | `adx` | 3 | 추세 강도 판단 불가 |
| 4 | `available_bars` | 5 | 백테스트 가용성 판단 불가 |

### 4-2. 선택 필드 (8개) — None이면 해당 stage에서 skip

| # | 필드 | Stage | None 시 동작 |
|:-:|------|:-----:|:------------:|
| 1 | `market_cap_usd` | 1 | Stage 1 mcap 체크 skip |
| 2 | `listing_age_days` | 1 | Stage 1 age 체크 skip |
| 3 | `spread_pct` | 2 | Stage 2 spread 체크 skip |
| 4 | `price_vs_200ma` | 3 | Stage 3 MA 체크 skip |
| 5 | `per` | 4 | Stage 4 PER 체크 skip |
| 6 | `roe` | 4 | Stage 4 ROE 체크 skip |
| 7 | `tvl_usd` | 4 | Stage 4 TVL 체크 skip |
| 8 | `sharpe_ratio` | 5 | Stage 5 Sharpe 체크 skip |
| 9 | `missing_data_pct` | 5 | Stage 5 결측률 체크 skip |

### 4-3. Partial 판정 로직 (pure 함수)

```
check_partial(market: MarketDataSnapshot, fund: FundamentalSnapshot, bt: BacktestReadiness)
    → DataQualityDecision

  mandatory = [market.avg_daily_volume_usd, market.atr_pct, market.adx, bt.available_bars]
  if any(v is None for v in mandatory) → PARTIAL_REJECT
  if any optional is None → PARTIAL_USABLE
  else → OK
```

---

## 5. DataQuality → ScreeningInput 변환 규약

### 5-1. 변환 계층 구조

```
[MarketDataSnapshot]  ──┐
[FundamentalSnapshot] ──┤──→ [DataQualityDecision] ──→ [ScreeningInput] (또는 거부)
[BacktestReadiness]   ──┘
```

### 5-2. 변환 규칙

| # | 규칙 | 설명 |
|:-:|------|------|
| C1 | 변환 함수는 **pure function**이어야 한다 | DB, 네트워크, 캐시 접근 금지 |
| C2 | 변환 함수는 **DataQualityDecision을 먼저 산출**한다 | 판정 없이 매핑하지 않음 |
| C3 | Decision이 REJECT 계열이면 **ScreeningInput을 생성하지 않는다** | fail-closed |
| C4 | Decision이 USABLE 계열이면 **가용 필드만 매핑**한다 | None 필드 그대로 전달 |
| C5 | 복수 Provider의 Quality가 다르면 **최저 등급 채택** | pessimistic merge |
| C6 | listing_age_days는 **별도 소스**에서 채워야 한다 | DataProvider 계약에 없음 |
| C7 | symbol namespace는 **변환 전 정규화** 필수 | "BTCUSDT" → "BTC/USDT" 등 |

### 5-3. 변환 순서

```
1. Provider 호출 (Stage 3B-2 영역 — 여기서는 계약만 정의)
2. Symbol namespace 검증 → SYMBOL_NAMESPACE_ERROR 시 거부
3. Stale 판정 (timestamp 기반) → STALE_REJECT 시 거부
4. Partial 판정 (필수 필드 존재 확인) → PARTIAL_REJECT 시 거부
5. Quality grade 병합 (최저 등급 채택)
6. ScreeningInput 생성 (pure 매핑)
```

---

## 6. listing_age_days 공백 해소 전략

### 현재 상태

| 항목 | 값 |
|------|-----|
| ScreeningInput에 존재 | ✅ (Stage 1에서 사용) |
| DataProvider 계약에 존재 | ❌ |
| MarketDataSnapshot에 존재 | ❌ |
| FundamentalSnapshot에 존재 | ❌ |

### 해소 방안 (3안)

| 안 | 방법 | 장점 | 단점 |
|----|------|------|------|
| **A** | MarketDataSnapshot에 `listing_date` 필드 추가 | 깔끔 | 기존 frozen dataclass 수정 |
| **B** | 별도 `SymbolMetadataSnapshot` frozen dataclass 신설 | 기존 계약 비수정 | 타입 1개 증가 |
| **C** | listing_age_days를 registry metadata에서 가져오기 | DataProvider 범위 외 | 변환 함수가 2개 소스 필요 |

### Stage 3B-1 결정

**안 B 채택 (권고)**
- 기존 Stage 3A frozen dataclass를 수정하지 않음
- 신규 `SymbolMetadata` frozen dataclass로 listing_date, exchange_list 등 정적 메타 분리
- 변환 함수가 (MarketData, Fundamental, Backtest, Metadata) → ScreeningInput 으로 확장

**단, 이 결정은 A 판정 대상. 확정이 아닌 권고.**

---

## 7. Failure Mode 요약표

| ID | 모드 | Decision | Screener 도달 | Fail-closed | 심각도 |
|:--:|------|----------|:-------------:|:-----------:|:------:|
| F1 | EMPTY | PROVIDER_UNAVAILABLE | ❌ | ✅ | HIGH |
| F2 | PARTIAL (필수) | PARTIAL_REJECT | ❌ | ✅ | HIGH |
| F3 | PARTIAL (선택) | PARTIAL_USABLE | ✅ | ✅ | LOW |
| F4 | STALE | STALE_USABLE/REJECT | 조건부 | ✅ | MEDIUM |
| F5 | INSUFFICIENT_BARS | INSUFFICIENT_BARS | ✅ | ✅ | LOW |
| F6 | MISSING_LISTING_AGE | MISSING_LISTING_AGE | ✅ | ⚠️ | MEDIUM |
| F7 | SYMBOL_NAMESPACE | SYMBOL_NAMESPACE_ERROR | ❌ | ✅ | HIGH |
| F8 | PROVIDER_TIMEOUT | PROVIDER_UNAVAILABLE | ❌ | ✅ | MEDIUM |
| F9 | QUALITY_CONFLICT | pessimistic merge | 조건부 | ✅ | LOW |

**전체 9개 모드 중 fail-closed: 8/9 (F6 제외 — 아래 §8 참조)**

---

## 8. F6 Fail-closed 예외 상세 (A-1 보완)

### 8-1. 예외 식별

| 항목 | 값 |
|------|-----|
| **예외 Failure Mode** | F6: MISSING_LISTING_AGE |
| **현재 동작** | listing_age_days=None → Stage 1 age 체크 **skip** (통과) |
| **fail-closed가 아닌 이유** | skip은 "통과 허용"이므로, 상장 직후 데이터 부족 종목이 Stage 1을 우회할 수 있음 |

### 8-2. 통제 조건

| # | 통제 | 설명 |
|:-:|------|------|
| 1 | **Stage 1 다중 방어** | listing_age skip이어도, sector 제외(EXCLUDED_SECTORS)와 market_cap 체크가 별도로 존재 → 신생 저시총 종목은 이중 차단 |
| 2 | **Stage 2-5 후속 필터** | listing_age를 통과해도 volume/atr/adx/bars 필수 필드에서 재검증 → 데이터 부족 종목은 후속 stage에서 FAIL |
| 3 | **write path 도달 불가** | screening 결과는 `screen_and_update()` (FROZEN)을 거쳐야 DB에 반영 → F6 단독으로 write path에 직접 도달하지 않음 |
| 4 | **SymbolMetadata 도입 후 강화** | SymbolMetadata.listing_date가 채워지면 F6은 자동으로 해소 → 과도기 허용 |

### 8-3. 허용 범위

| 허용 | 금지 |
|------|------|
| listing_age 없이 Stage 1 age 체크 skip | listing_age 없이 CORE 상태 직접 부여 |
| 후속 Stage에서 정상 필터링 | screening 우회하여 write path 직접 진입 |
| SymbolMetadata 도입 전 과도기 운영 | 영구적 skip 허용 |

### 8-4. Fallback 결과

listing_age_days=None이면:
- Stage 1 age 체크만 skip
- 나머지 4단계는 정상 수행
- 최종 ScreeningOutput에 `listing_age_unknown=True` 플래그 기록 (추적용)
- **runtime/write path로 절대 이어지지 않음** — screening 결과는 read-only dataclass이며, write는 FROZEN screen_and_update()만 담당

---

## 9. Stale 한도: 시스템 정책값 고정 원칙 (A-2 보완)

### 원칙

| 규칙 | 설명 |
|------|------|
| **SP-01** | Stale 임계값은 **시스템 정책 상수**로 고정한다 (constitution.py 또는 data_provider.py 상수) |
| **SP-02** | Provider는 사실(timestamp, data_age)만 제공하고, stale 여부를 판정하지 않는다 |
| **SP-03** | `is_stale()` 판정 함수는 시스템 정책 상수만 참조한다 |
| **SP-04** | Provider가 자체 freshness 기준을 갖고 있어도, 시스템 정책이 우선한다 |
| **SP-05** | 정책 상수 변경은 constitution 수정에 해당하며, A 승인 필요 |

### 구현 위치

```
STALE_LIMITS = {
    (AssetClass.CRYPTO, "price"):       timedelta(hours=1),
    (AssetClass.CRYPTO, "fundamental"): timedelta(hours=24),
    (AssetClass.US_STOCK, "price"):     timedelta(hours=4),
    (AssetClass.US_STOCK, "fundamental"): timedelta(days=7),
    (AssetClass.KR_STOCK, "price"):     timedelta(hours=4),
    (AssetClass.KR_STOCK, "fundamental"): timedelta(days=7),
    ("ALL", "backtest"):                timedelta(days=30),
}
```

**위치:** `data_provider.py` (Pure Zone, 상수 정의)

---

## 10. DataQualityDecision 허용 범위 (A-3 보완)

### 허용

| 용도 | 설명 |
|------|------|
| ScreeningInput 생성 가능/불가 판정 | 핵심 용도 |
| Fail-closed 이유 코드 | 왜 변환이 거부되었는지 |
| 감사/테스트 설명 코드 | 로깅, 추적, 증빙 |

### 금지

| 용도 | 이유 |
|------|------|
| Qualification 판정 직접 대체 | BacktestQualifier의 영역 침범 |
| Runtime trade 여부 직접 결정 | Data Plane 실행 판단은 별도 계층 |
| Provider별 임의 override | 시스템 정책 우선 원칙(SP-04) 위반 |
| Strategy 선택/라우팅 | Control Plane 영역 |

### 범위 경계

```
DataQualityDecision의 영향 범위:

  DataProvider 출력 → [DataQualityDecision] → ScreeningInput 생성 여부
                                                    │
                                                    ▼ (여기까지만)
                                              ScreeningInput
                                                    │
                                                    ▼ (이후는 기존 계층이 담당)
                                              SymbolScreener.screen()
                                              BacktestQualifier.qualify()
                                              AssetService.screen_and_update() [FROZEN]
```

---

## 11. SymbolMetadata 확정 (A-4 보완, 안 B 확정)

### 확정 필드

| # | 필드 | 타입 | 의미 | 기본값 |
|:-:|------|------|------|:------:|
| 1 | `symbol` | `str` | 종목 식별자 | 필수 |
| 2 | `market` | `str` | 시장 식별 (예: "crypto", "us_stock", "kr_stock") | 필수 |
| 3 | `listing_age_days` | `int \| None` | 상장 이후 일수 | `None` |
| 4 | `is_active` | `bool` | 현재 거래 가능 여부 | `True` |
| 5 | `as_of` | `datetime \| None` | 메타데이터 기준 시각 | `None` |
| 6 | `metadata_origin` | `str` | 데이터 출처 (예: "registry", "coingecko", "krx") | `"unknown"` |

### 규칙

| 규칙 | 설명 |
|------|------|
| **SM-01** | SymbolMetadata는 Pure Zone에 위치 (data_provider.py) |
| **SM-02** | frozen=True, 모든 필드 immutable |
| **SM-03** | runtime/service 계층 import 없음 |
| **SM-04** | metadata가 없는데 listing_age가 필수인 전략이면 fail-closed |
| **SM-05** | DataProvider 핵심 OHLCV 계약과 분리 |

---

```
CR-048 Stage 3B Failure Mode Matrix v1.1 (A-1~A-4 보완)
Document ID: GOV-L3-STAGE3B-FAILMODE-001
Document ID: GOV-L3-STAGE3B-FAILMODE-001
Date: 2026-04-03
Authority: A
Status: SUBMITTED
Failure Modes: 9 (F1-F9)
DataQualityDecision: 9 values
Fail-closed: 8/9 modes
Stale Policy: 3 asset classes × 3 data types
Partial Policy: 4 mandatory + 9 optional fields
listing_age_days: 해소 방안 B 권고 (A 판정 대기)
```
