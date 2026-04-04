# Broker/Market Matrix (브로커/시장 매트릭스)

**문서 ID:** CONST-002
**작성일:** 2026-04-02 (v1.0) → 2026-04-04 (v2.0)
**Authority:** A (Decision Authority)
**CR:** CR-048 (K-Dexter Integrated Ops Server v2.3)
**Status:** **ACTIVE**
**변경 등급:** L0 (문서)

---

## 1. 해석 및 요약

### 목적

시장별 허용/금지 브로커를 명시하고, 거래 시간과 전략-자산 매핑 규칙을 정의한다.
Injection Gateway는 이 매트릭스를 기준으로 금지 브로커를 사용하는 Strategy 등록을 물리적으로 차단한다.

### 현재 브로커 현황

| 상태 | 브로커 | 수 |
|------|--------|----|
| **허용** | Binance, Bitget, UpBit, KIS_US, KIS_KR, Kiwoom_KR | 6 |
| **금지** | Alpaca, Kiwoom_US | 2 |
| **신규** | KIS_US (해외주식 전용) | 1 |

### 허용 브로커 매트릭스

| 자산 클래스 | 코드 | 허용 브로커 | 어댑터 | 상태 |
|------------|------|------------|--------|------|
| CRYPTO | `CRYPTO` | Binance | `exchanges/binance.py` | 기존 완료 |
| CRYPTO | `CRYPTO` | Bitget | `exchanges/bitget.py` | 기존 완료 |
| CRYPTO | `CRYPTO` | UpBit | `exchanges/upbit.py` | 기존 완료 |
| US_STOCK | `US_STOCK` | **KIS_US** | `exchanges/kis_us.py` | **신규** |
| KR_STOCK | `KR_STOCK` | KIS_KR | `exchanges/kis.py` | 기존 완료 (primary) |
| KR_STOCK | `KR_STOCK` | Kiwoom_KR | `exchanges/kiwoom.py` | 기존 완료 (optional) |

### 금지 브로커 (FORBIDDEN)

| 브로커 | 코드 | 금지 사유 | 차단 시점 |
|--------|------|-----------|-----------|
| ~~Alpaca~~ | `ALPACA` | 제거됨 — 미국 법규 리스크, 유지보수 비용 | Injection Gateway 등록 단계 |
| ~~Kiwoom_US~~ | `KIWOOM_US` | 주문/포지션/데이터 전체 금지 — API 불안정, 미국주식은 KIS_US 단일화 | Injection Gateway 등록 단계 |
| 기타 미승인 | — | 미등록 브로커 자동 거부 | Injection Gateway 등록 단계 |

---

## 2. 장점 / 단점

### 매트릭스 채택 시 장점

| 장점 | 설명 |
|------|------|
| **단일 진실 원천** | 허용/금지 브로커가 한 문서에 명시되어 코드와 문서의 불일치 방지 |
| **물리적 차단** | Injection Gateway가 매트릭스를 참조하여 금지 브로커 등록 자체를 거부 |
| **KIS_US 단일화** | 미국주식 경로를 KIS_US로 통일하여 복잡도 감소 |
| **기존 어댑터 재사용** | 6개 중 5개가 기존 완료, 신규는 KIS_US 1건만 |
| **거래 시간 명시** | TradingHoursGuard가 정확한 시간 외 주문을 차단 |

### 매트릭스 채택 시 단점/리스크

| 단점 | 완화 방안 |
|------|-----------|
| KIS_US 단일 의존 | KIS API 장애 시 미국주식 전체 차단 → Circuit Breaker + Safe Mode로 대응 |
| Kiwoom_KR optional | primary가 아니므로 통합 테스트 우선순위 낮음 → KIS_KR 장애 시 fallback으로 활용 가능 |
| 금지 브로커 해제 절차 복잡 | 의도적 설계 — 경솔한 해제 방지 |

### 매트릭스 미채택 시 리스크

| 리스크 | 심각도 |
|--------|--------|
| 금지 브로커 우회 등록 | **높음** |
| 자산 클래스-브로커 불일치 (예: CRYPTO 전략이 KIS_KR로 라우팅) | **높음** |
| 거래 시간 외 주문 시도 | **중간** |

---

## 3. 이유 / 근거

### 근거 1 — CLAUDE.md 금지 사항 반영

CLAUDE.md에 명시된 금지 사항:
- ETH: 운영 경로 금지 (CR-046)
- Alpaca: 제거
- Kiwoom_US: 금지

→ 이 금지 사항을 코드 레벨에서 강제하려면 매트릭스 + Injection Gateway 연동 필수.

### 근거 2 — KIS_US 분리의 기술적 필요성

기존 `exchanges/kis.py`는 한국주식 전용:
- API 엔드포인트 차이 (국내/해외)
- 인증 방식 차이 (토큰 타입, 시장 코드)
- 거래 시간 차이 (KST vs EST)
- 주문 API 파라미터 차이

→ 별도 어댑터 `exchanges/kis_us.py` 신규 생성이 올바른 접근.

### 근거 3 — Kiwoom_KR optional 유지

Kiwoom_KR은:
- 이미 구현 완료 (`exchanges/kiwoom.py`)
- KIS_KR의 fallback으로 활용 가능
- 그러나 primary가 아니므로 통합 테스트/모니터링 우선순위 낮음

→ optional로 유지하되, 제거하지 않음.

### 근거 4 — 거래소별 거래 시간 guard 필요성

| 거래소 | 시간 | 시간 외 주문 시 |
|--------|------|----------------|
| Binance, Bitget, UpBit | 24/7 | 해당 없음 |
| KIS_KR, Kiwoom_KR | KST 09:00-15:30 (평일) | TradingHoursGuard 차단 |
| KIS_US | EST 09:30-16:00 (평일) | TradingHoursGuard 차단 |

- 시간 외 주문은 거래소가 거부하거나 예기치 않은 체결이 발생할 수 있음
- TradingHoursGuard가 선제적으로 차단하여 불필요한 API 호출 방지

---

## 4. 실현 / 구현 대책

### 4.1 Strategy-Market Matrix (강제 매핑)

```python
class StrategyMarketMatrix:
    strategy_id: str
    asset_class: AssetClass      # CRYPTO, US_STOCK, KR_STOCK
    exchange: str                 # 허용 브로커만 (금지 브로커 등록 불가)
    sectors: list[AssetSector]   # 허용 섹터만 (EXCLUDED 섹터 등록 불가)
    timeframes: list[str]
    regimes: list[str]
    max_symbols: int
```

### 4.2 전략-자산 매핑 초기 계획

| 전략 | CRYPTO | US_STOCK | KR_STOCK | Regime |
|------|:------:|:--------:|:--------:|-------|
| SMC+WaveTrend | **O** | X | X | 추세 |
| RSI Cross | O | **O** | **O** | 전체 |
| Mean Reversion | X | **O** | **O** | 횡보 |
| Momentum | X | **O** | **O** | 상승 |

### 4.3 코드 상수 설계

```python
FORBIDDEN_BROKERS = frozenset({"ALPACA", "KIWOOM_US"})

ALLOWED_BROKERS = {
    "CRYPTO": frozenset({"BINANCE", "BITGET", "UPBIT"}),
    "US_STOCK": frozenset({"KIS_US"}),
    "KR_STOCK": frozenset({"KIS_KR", "KIWOOM_KR"}),
}

TRADING_HOURS = {
    "BINANCE": {"type": "24_7"},
    "BITGET": {"type": "24_7"},
    "UPBIT": {"type": "24_7"},
    "KIS_KR": {"type": "weekday", "tz": "Asia/Seoul", "open": "09:00", "close": "15:30"},
    "KIWOOM_KR": {"type": "weekday", "tz": "Asia/Seoul", "open": "09:00", "close": "15:30"},
    "KIS_US": {"type": "weekday", "tz": "US/Eastern", "open": "09:30", "close": "16:00"},
}
```

### 4.4 Injection Gateway 매트릭스 체크

| 체크 | 구현 |
|------|------|
| 금지 브로커 | `if exchange in FORBIDDEN_BROKERS: reject()` |
| 자산 클래스-브로커 호환 | `if exchange not in ALLOWED_BROKERS[asset_class]: reject()` |
| 거래 시간 | `TradingHoursGuard.is_market_open(exchange)` |

### 4.5 KIS_US 어댑터 설계 (Phase 3B)

| 메서드 | 설명 |
|--------|------|
| `create_order()` | 미국주식 주문 생성 |
| `cancel_order()` | 주문 취소 |
| `fetch_order()` | 주문 상태 조회 |
| `fetch_positions()` | 보유 포지션 조회 |
| `fetch_balance()` | 잔고 조회 |
| `fetch_ticker()` | 실시간 시세 |
| `fetch_ohlcv()` | OHLCV 데이터 |

기존 `exchanges/kis.py` (KR 전용) 유지, `exchanges/kis_us.py` 별도 생성.

### 4.6 허용/금지/승인 필요 정리

| 행위 | 허용 여부 | 비고 |
|------|:---------:|------|
| 허용 브로커로 전략 등록 | ✅ | |
| 24/7 거래소 상시 주문 | ✅ | |
| 거래 시간 내 KIS_KR/US 주문 | ✅ | |
| 금지 브로커로 전략 등록 | ⛔ | Injection Gateway 차단 |
| 거래 시간 외 주문 | ⛔ | TradingHoursGuard 차단 |
| 금지 브로커 목록 삭제 | ⛔ | 추가만 가능 |
| 금지 브로커 해제 | ⛔ | **A 승인 + 별도 CR** |
| 매트릭스 자체 수정 | ⚠️ | **Admin 역할 + A 승인** |

---

## 5. 실행방법

### 구현 순서

| 단계 | 작업 | Phase | 등급 |
|------|------|-------|------|
| 1 | 본 매트릭스 A 승인 | Phase 0 | L0 |
| 2 | `FORBIDDEN_BROKERS`, `ALLOWED_BROKERS` 상수 정의 | Phase 1 | L3 |
| 3 | Injection Gateway에 매트릭스 체크 구현 | Phase 1 | L3 |
| 4 | `exchanges/kis_us.py` 어댑터 신규 생성 | Phase 3B | L3 |
| 5 | `exchanges/factory.py`에 kis_us 등록 | Phase 3B | L3 |
| 6 | TradingHoursGuard 구현 | Phase 6 | L3 |
| 7 | 통합 테스트 | Phase 7 | L1 |

### 거래소 최종 목록 (구현 상태)

| 이름 | 어댑터 | 상태 | 비고 |
|------|--------|------|------|
| binance | `exchanges/binance.py` | ✅ 기존 완료 | |
| bitget | `exchanges/bitget.py` | ✅ 기존 완료 | |
| upbit | `exchanges/upbit.py` | ✅ 기존 완료 | |
| kis_kr | `exchanges/kis.py` | ✅ 기존 완료 | |
| **kis_us** | `exchanges/kis_us.py` | ⬜ 신규 | Phase 3B |
| kiwoom_kr | `exchanges/kiwoom.py` | ✅ 기존 완료 | optional |
| ~~alpaca~~ | 제거 | ⛔ **FORBIDDEN** | |
| ~~kiwoom_us~~ | 금지 | ⛔ **FORBIDDEN** | |

---

## 6. 더 좋은 아이디어

### 6.1 브로커 건전성 등급제

허용 브로커에 대해 건전성 등급을 부여하여, 등급에 따라 자동 노출 조절:

| 등급 | 조건 | 노출 제한 |
|------|------|-----------|
| GREEN | 응답 지연 < 500ms, 24H 장애 0 | 제한 없음 |
| YELLOW | 응답 지연 500ms~2s 또는 24H 장애 1~2회 | 신규 진입 50% 제한 |
| RED | 응답 지연 > 2s 또는 24H 장애 3회+ | 신규 진입 금지, 기존 포지션 청산만 |

→ Phase 7 (모니터링) 또는 Phase 9 (Recovery)에서 구현 가능.

### 6.2 Pre-market / After-hours 지원 (미국주식)

KIS_US가 pre-market (04:00-09:30 EST) / after-hours (16:00-20:00 EST)를 지원하는 경우:
- TradingHoursGuard에 extended hours 모드 추가
- 단, extended hours는 유동성 낮으므로 별도 리스크 상한 적용
- A 승인 필요

### 6.3 브로커 장애 시 자동 전환 (KR_STOCK)

KIS_KR → Kiwoom_KR 자동 전환:
- KIS_KR RED 상태 시 Kiwoom_KR로 자동 라우팅
- 단, 주문 중복 방지 체크 필수
- Phase 9 (Recovery) 범위

---

## L3 구현 선행조건 체크리스트

Phase 1 / Phase 3B 구현(L3) 착수 전 아래 조건 **전부 충족** 필요:

| # | 조건 | 충족 여부 | 비고 |
|---|------|:---------:|------|
| 1 | 본 문서(브로커 매트릭스) A 승인 | ⬜ | |
| 2 | injection_constitution.md A 승인 | ⬜ | |
| 3 | exclusion_baseline.md A 승인 | ⬜ | |
| 4 | Phase 1 설계 카드 4종 A 승인 | ⬜ | |
| 5 | Gate LOCKED 해제 또는 L3 개별 A 승인 | ⬜ | 현재 Gate LOCKED |
| 6 | 전체 회귀 테스트 PASS | ⬜ | |
| 7 | baseline-check 6/6 PASS | ⬜ | |
| 8 | KIS_US API 접근 키 확보 | ⬜ | Phase 3B 전용 |

**0/8 충족. 구현 착수 불가.**

---

```
Broker/Market Matrix v2.0
Authority: A
Date: 2026-04-04
CR: CR-048
```
