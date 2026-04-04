# CR-048 Stage 3B-2 Fixture Strategy

**문서 ID:** DESIGN-STAGE3B2-005
**작성일:** 2026-04-03
**CR:** CR-048
**변경 등급:** L0 (설계 문서)

---

## 1. 목적

Golden set fixture를 설계하여, stub 테스트가 **정상 경로 + 실패 모드 전체**를 커버하도록 한다.

A 추가 제안 반영: fixture에 **capability 부족 상황**을 의도적으로 포함.

---

## 2. Fixture 분류 체계

| 분류 | 목적 | 수량 |
|------|------|:----:|
| **Normal** | 시장별 정상 데이터 (CORE 후보) | 4종 |
| **Failure** | F1-F9 failure mode 재현 | 9종 |
| **Edge** | 경계값 + partial/stale usable | 4종 |
| **Capability** | provider capability 부족 시나리오 | 3종 |
| **합계** | | **20종** |

---

## 3. Normal Fixture (시장별 4종)

### 3.1 BTC/USDT (CRYPTO, LAYER1)

```python
FIXTURE_BTC_MARKET = MarketDataSnapshot(
    symbol="BTC/USDT",
    timestamp=datetime(2026, 4, 3, 12, 0, 0, tzinfo=timezone.utc),
    price_usd=68000.0,
    market_cap_usd=1_340_000_000_000,
    avg_daily_volume_usd=35_000_000_000,
    spread_pct=0.01,
    atr_pct=3.2,
    adx=28.0,
    price_vs_200ma=1.08,
    quality=DataQuality.HIGH,
)

FIXTURE_BTC_BACKTEST = BacktestReadiness(
    symbol="BTC/USDT",
    available_bars=2000,
    sharpe_ratio=0.85,
    missing_data_pct=0.3,
    quality=DataQuality.HIGH,
)

FIXTURE_BTC_METADATA = SymbolMetadata(
    symbol="BTC/USDT", market="crypto",
    listing_age_days=5000, is_active=True,
    metadata_origin="coingecko",
)
```

### 3.2 SOL/USDT (CRYPTO, LAYER1)

```python
FIXTURE_SOL_MARKET = MarketDataSnapshot(
    symbol="SOL/USDT",
    timestamp=datetime(2026, 4, 3, 12, 0, 0, tzinfo=timezone.utc),
    price_usd=145.0,
    market_cap_usd=65_000_000_000,
    avg_daily_volume_usd=3_500_000_000,
    spread_pct=0.03,
    atr_pct=5.5,
    adx=22.0,
    price_vs_200ma=1.15,
    quality=DataQuality.HIGH,
)
# backtest, metadata 유사 구조
```

### 3.3 AAPL (US_STOCK, TECH)

```python
FIXTURE_AAPL_MARKET = MarketDataSnapshot(
    symbol="AAPL",
    timestamp=datetime(2026, 4, 3, 16, 0, 0, tzinfo=timezone.utc),
    price_usd=195.0,
    market_cap_usd=3_000_000_000_000,
    avg_daily_volume_usd=8_000_000_000,
    spread_pct=0.005,
    atr_pct=1.8,
    adx=20.0,
    price_vs_200ma=1.02,
    quality=DataQuality.HIGH,
)

FIXTURE_AAPL_FUNDAMENTAL = FundamentalSnapshot(
    symbol="AAPL",
    per=28.5, roe=45.0,
    revenue_growth_pct=8.2, operating_margin_pct=30.0,
    quality=DataQuality.HIGH,
)
```

### 3.4 005930 (KR_STOCK, SEMICONDUCTOR)

```python
FIXTURE_005930_MARKET = MarketDataSnapshot(
    symbol="005930",
    timestamp=datetime(2026, 4, 3, 6, 30, 0, tzinfo=timezone.utc),
    price_usd=55.0,
    market_cap_usd=330_000_000_000,
    avg_daily_volume_usd=1_500_000_000,
    spread_pct=0.02,
    atr_pct=2.0,
    adx=18.0,
    price_vs_200ma=0.95,
    quality=DataQuality.HIGH,
)
```

---

## 4. Failure Fixture (F1-F9)

| Failure | Fixture 이름 | 핵심 특징 | 예상 결과 |
|:-------:|-------------|-----------|:---------:|
| **F1** | `FIXTURE_F1_EMPTY` | 모든 필드 None (빈 snapshot) | PARTIAL_REJECT |
| **F2** | `FIXTURE_F2_PARTIAL_MANDATORY` | volume=None, atr=None (mandatory 누락) | PARTIAL_REJECT |
| **F3** | `FIXTURE_F3_PARTIAL_OPTIONAL` | volume/atr/adx/bars 있지만 mcap/spread=None | PARTIAL_USABLE |
| **F4** | `FIXTURE_F4_STALE` | timestamp = 3시간 전 (CRYPTO) | STALE_REJECT |
| **F5** | `FIXTURE_F5_INSUFFICIENT_BARS` | available_bars=100 (< 500) | OK (stage 5 판단) |
| **F6** | `FIXTURE_F6_NO_LISTING_AGE` | metadata=None 또는 listing_age_days=None | MISSING_LISTING_AGE → OK |
| **F7** | `FIXTURE_F7_NAMESPACE_ERROR` | symbol="BTCUSDT" (slash 없음) | SYMBOL_NAMESPACE_ERROR |
| **F8** | `FIXTURE_F8_PROVIDER_TIMEOUT` | stub이 빈 snapshot 반환 (미등록 symbol) | PARTIAL_REJECT |
| **F9** | `FIXTURE_F9_QUALITY_CONFLICT` | quality=DEGRADED, 일부 필드 존재 | PARTIAL_USABLE |

---

## 5. Edge Fixture (경계값 4종)

| Fixture | 설명 | 예상 결과 |
|---------|------|:---------:|
| `FIXTURE_EDGE_STALE_USABLE` | timestamp = 50분 전 (CRYPTO price, limit 1h) | OK (아직 미도달) |
| `FIXTURE_EDGE_STALE_BOUNDARY` | timestamp = 정확히 1시간 전 | OK (<=) |
| `FIXTURE_EDGE_MIN_BARS` | available_bars=500 (정확히 최소) | OK (stage 5 pass) |
| `FIXTURE_EDGE_MAX_ATR` | atr_pct=20.0 (정확히 상한) | OK (stage 3 pass) |

---

## 6. Capability Fixture (A 추가 제안: 부족 상황 포함)

| Fixture | Capability Profile | 설명 | is_screening_capable |
|---------|-------------------|------|:--------------------:|
| `CAP_FULL_CRYPTO` | full_crypto | 모든 필수 + 대부분 optional 지원 | **YES** |
| `CAP_DEGRADED_NO_ADX` | degraded_crypto | adx 미지원 → mandatory 부족 | **NO** |
| `CAP_EMPTY` | empty | 아무것도 미지원 | **NO** |

---

## 7. Fixture 파일 구조

```python
# tests/fixtures/screening_fixtures.py

from datetime import datetime, timezone
from app.services.data_provider import (
    DataQuality, MarketDataSnapshot, FundamentalSnapshot,
    BacktestReadiness, SymbolMetadata, ProviderCapability,
)

# ── Normal Fixtures ──────────────────────────
FIXTURE_BTC_MARKET = MarketDataSnapshot(...)
FIXTURE_BTC_BACKTEST = BacktestReadiness(...)
FIXTURE_BTC_METADATA = SymbolMetadata(...)
# ... SOL, AAPL, 005930

# ── Failure Fixtures (F1-F9) ─────────────────
FIXTURE_F1_EMPTY_MARKET = MarketDataSnapshot(symbol="EMPTY/TEST")
FIXTURE_F1_EMPTY_BACKTEST = BacktestReadiness(symbol="EMPTY/TEST")
# ... F2-F9

# ── Edge Fixtures ────────────────────────────
FIXTURE_EDGE_STALE_USABLE_MARKET = MarketDataSnapshot(...)
# ... etc

# ── Capability Fixtures ──────────────────────
CAP_FULL_CRYPTO = ProviderCapability(
    provider_name="full_crypto",
    supported_asset_classes=frozenset({"CRYPTO"}),
    supports_volume=True, supports_atr=True,
    supports_adx=True, supports_available_bars=True,
    # ... all True
)
CAP_DEGRADED_NO_ADX = ProviderCapability(
    provider_name="degraded_no_adx",
    supports_volume=True, supports_atr=True,
    supports_adx=False, supports_available_bars=False,
)
CAP_EMPTY = ProviderCapability(provider_name="empty")

# ── Golden Set Symbols ───────────────────────
GOLDEN_SYMBOLS = {
    "CRYPTO": ["BTC/USDT", "SOL/USDT"],
    "US_STOCK": ["AAPL", "NVDA"],
    "KR_STOCK": ["005930", "000660"],
}
```

---

## 8. Fixture 완전성 검증표

| 검증 항목 | 커버 필요 | Fixture 수 |
|-----------|:---------:|:----------:|
| 시장별 정상 (CRYPTO, US, KR) | 3+ | 4 |
| F1-F9 failure mode 전체 | 9 | 9 |
| 경계값 (stale/bars/atr) | 3+ | 4 |
| Capability 부족 | 2+ | 3 |
| Namespace error (시장별) | 3+ | §4 F7 + §namespace golden set |
| **합계** | | **20+** |

---

```
CR-048 Stage 3B-2 Fixture Strategy v1.0
Document ID: DESIGN-STAGE3B2-005
Date: 2026-04-03
Status: SUBMITTED
```
