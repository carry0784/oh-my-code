# CR-048 Stage 3B-2 Symbol Namespace Contract

**문서 ID:** DESIGN-STAGE3B2-004
**작성일:** 2026-04-03
**CR:** CR-048
**변경 등급:** L0 (설계 문서)

---

## 1. 목적

symbol normalization의 표준 사례를 **시장별 golden set**으로 고정하고, normalize_symbol()의 계약 경계를 명확히 한다.

---

## 2. 내부 정규형 (Canonical Format)

| Asset Class | 정규형 | 패턴 | 예시 |
|-------------|--------|------|------|
| **CRYPTO** | `{BASE}/{QUOTE}` (대문자, slash 구분) | `[A-Z]+/[A-Z]+` | `BTC/USDT`, `SOL/USDT`, `ETH/USDT` |
| **US_STOCK** | `{TICKER}` (대문자 알파벳) | `[A-Z]+` | `AAPL`, `NVDA`, `MSFT` |
| **KR_STOCK** | `{6-DIGIT}` (숫자 6자리) | `[0-9]{6}` | `005930`, `000660`, `035420` |

---

## 3. Golden Set (시장별 표준 사례표)

### 3.1 CRYPTO

| 입력 (raw) | asset_class | 정규화 결과 | 사유 |
|------------|:-----------:|:-----------:|------|
| `BTC/USDT` | CRYPTO | `BTC/USDT` | 정규형 통과 |
| `btc/usdt` | CRYPTO | `BTC/USDT` | 소문자 → 대문자 정규화 |
| `SOL/USDT` | CRYPTO | `SOL/USDT` | 정규형 통과 |
| `sol/usdt` | CRYPTO | `SOL/USDT` | 소문자 → 대문자 정규화 |
| `BTCUSDT` | CRYPTO | **None** | slash 없음 → F7 NAMESPACE_ERROR |
| `KRW-BTC` | CRYPTO | **None** | dash 구분자 → F7 (UpBit 형식, 정규형 아님) |
| `btc_usdt` | CRYPTO | **None** | underscore → F7 |
| ` ` (공백) | CRYPTO | **None** | 빈 문자열 → F7 |
| `BTC/USDT ` | CRYPTO | `BTC/USDT` | trailing space → strip 후 정규화 |

### 3.2 US_STOCK

| 입력 (raw) | asset_class | 정규화 결과 | 사유 |
|------------|:-----------:|:-----------:|------|
| `AAPL` | US_STOCK | `AAPL` | 정규형 통과 |
| `aapl` | US_STOCK | `AAPL` | 소문자 → 대문자 |
| `NVDA` | US_STOCK | `NVDA` | 정규형 통과 |
| `MSFT` | US_STOCK | `MSFT` | 정규형 통과 |
| `BRK.B` | US_STOCK | **None** | 점 포함 → isalpha() 실패 |
| `005930` | US_STOCK | **None** | 숫자 → isalpha() 실패 |
| `AAPL1` | US_STOCK | **None** | 숫자 혼합 → isalpha() 실패 |

### 3.3 KR_STOCK

| 입력 (raw) | asset_class | 정규화 결과 | 사유 |
|------------|:-----------:|:-----------:|------|
| `005930` | KR_STOCK | `005930` | 정규형 통과 (삼성전자) |
| `000660` | KR_STOCK | `000660` | 정규형 통과 (SK하이닉스) |
| `035420` | KR_STOCK | `035420` | 정규형 통과 (네이버) |
| `12345` | KR_STOCK | **None** | 5자리 → 길이 불일치 |
| `0059301` | KR_STOCK | **None** | 7자리 → 길이 불일치 |
| `00593A` | KR_STOCK | **None** | 알파벳 포함 → isdigit() 실패 |
| `005930.KS` | KR_STOCK | **None** | 접미사 포함 → isdigit() 실패 |

### 3.4 Unknown Asset Class

| 입력 (raw) | asset_class | 정규화 결과 | 사유 |
|------------|:-----------:|:-----------:|------|
| `XYZ` | UNKNOWN | **None** | 미지원 자산 클래스 |
| `BTC/USDT` | FUTURE | **None** | 미지원 자산 클래스 |

---

## 4. 외부 형식 변환 필요 사례 (3B-2 범위 외, 참고용)

Stage 3B-2에서는 **정규형만 처리**한다. 아래 외부 형식은 향후 provider adapter 구현 시 처리.

| 거래소 | 원본 형식 | 정규형 | 변환 필요 |
|--------|-----------|--------|:---------:|
| Binance | `BTCUSDT` | `BTC/USDT` | YES (3B-3+) |
| UpBit | `KRW-BTC` | `BTC/USDT` | YES (3B-3+) |
| Yahoo Finance | `005930.KS` | `005930` | YES (3B-3+) |
| KIS | `005930` | `005930` | NO (이미 정규형) |

**규칙:** Stage 3B-2 stub은 정규형만 fixture에 사용. 외부 형식 변환은 3B-2 범위 밖.

---

## 5. normalize_symbol 확장 금지 항목

| 금지 | 사유 |
|------|------|
| 거래소별 형식 변환 로직 추가 | Provider 냄새가 pure layer에 침투 |
| 정규표현식 기반 패턴 매칭 추가 | 복잡도 증가, 현재 isalpha/isdigit/slash 검사로 충분 |
| asset_class 목록 확장 | Stage 3B-2 범위 외 (FUTURE, OPTION 등) |
| normalize_symbol 시그니처 변경 | Stage 3B-1 SEALED 계약 |

---

## 6. Fixture에서의 Golden Set 사용

```python
# tests/fixtures/screening_fixtures.py

# Golden set symbols (정규형만)
GOLDEN_SYMBOLS = {
    "CRYPTO": ["BTC/USDT", "SOL/USDT", "ETH/USDT", "UNI/USDT"],
    "US_STOCK": ["AAPL", "NVDA", "MSFT", "JPM"],
    "KR_STOCK": ["005930", "000660", "035420", "105560"],
}

# Namespace error symbols (F7 trigger)
F7_ERROR_SYMBOLS = {
    "CRYPTO": ["BTCUSDT", "KRW-BTC", "", "btc_usdt"],
    "US_STOCK": ["BRK.B", "005930", "AAPL1"],
    "KR_STOCK": ["12345", "00593A", "005930.KS"],
}
```

---

```
CR-048 Stage 3B-2 Symbol Namespace Contract v1.0
Document ID: DESIGN-STAGE3B2-004
Date: 2026-04-03
Status: SUBMITTED
```
