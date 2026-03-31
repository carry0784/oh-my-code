# CR-037: create_market_order params Keyword Contract Fix

Effective: 2026-03-31
Status: **SEALED** (A 승인 2026-03-31)
Author: B (Implementer)
Reviewer: A (Designer)
Scope: BinanceExchange.create_order() CCXT 호출 계약 수정
Related: CR-036 (SEALED), M2-2 (SEALED — PASS)

---

## (1) 해석 및 요약

### 발견 경위

M2-2 micro-live 실행 중 OrderExecutor가 BinanceExchange.create_order()를 호출했을 때
`decimal.ConversionSyntax` 에러가 발생했다.

```
binance.py:6403, in create_order_request
    priceString = self.number_to_string(price)
decimal_to_precision.py:176
    d = decimal.Decimal(str(x))   # x = {} (params dict)
→ decimal.InvalidOperation: [<class 'decimal.ConversionSyntax'>]
```

### 원인

`exchanges/binance.py:37`에서 `params` dict를 위치 인자로 전달:

```python
# 버그 코드:
order = await self.client.create_market_order(symbol, side, quantity, params)

# CCXT 시그니처:
# create_market_order(symbol, side, amount, price=None, params={})
#                                           ↑ params가 여기에 바인딩
```

`params` (빈 dict `{}`)가 CCXT의 `price` 파라미터 위치에 들어가면서,
CCXT 내부에서 `Decimal(str({}))` → `ConversionSyntax` 발생.

### 수정

```python
# 수정 후:
order = await self.client.create_market_order(symbol, side, quantity, params=params)
```

`create_limit_order`도 동일 패턴 적용:
```python
order = await self.client.create_limit_order(symbol, side, quantity, price, params=params)
```

---

## (2) 장점 / 단점

### 장점
- 수정 최소 (1파일, 2줄)
- 기존 파이프라인 구조 불변
- M2-2 재실행으로 수정 효과 즉시 실증 (FILLED)
- CR-036과 범위 분리 완료

### 단점
- dry-run에서는 발현하지 않는 결함 (exchange 미호출)
- M2-1.5, CR-036 전용 테스트 모두 이 결함을 커버하지 못함
- 실행 중 발견이라는 점에서 사전 검증 갭 존재

---

## (3) 이유 / 근거

### CR-036과의 범위 분리

| 항목 | CR-036 | CR-037 |
|------|--------|--------|
| 대상 | OrderExecutor → Exchange 호출 | Exchange → CCXT 호출 |
| 결함 | `amount` vs `quantity`, 인자 순서 | `params` 위치 인자 → keyword |
| 계층 | OrderExecutor ↔ BaseExchange | BinanceExchange ↔ CCXT |
| 발견 시점 | M2-2 전 코드 리뷰 | M2-2 실행 중 |

두 결함은 서로 다른 호출 계층의 계약 불일치이므로 독립 CR이 맞다.

### 영향 범위

| 항목 | 영향 |
|------|------|
| `create_market_order` | 직접 영향 (market order 실패) |
| `create_limit_order` | 간접 영향 (params가 마지막 인자이므로 현재는 정상, 하지만 방어적 수정) |
| dry-run 경로 | 영향 없음 (exchange 미호출) |
| 다른 exchange 어댑터 | 확인 필요 (아래 참조) |

### 다른 어댑터 확인

| 어댑터 | 상태 | 비고 |
|--------|------|------|
| BinanceExchange | 수정 완료 | `params=params` |
| UpBitExchange | M2-2 범위 외 | 향후 확인 필요 |
| BitgetExchange | M2-2 범위 외 | 향후 확인 필요 |

---

## (4) 실현/구현 대책

### 변경 파일 목록

| # | 파일 | 변경 | 내용 |
|---|------|------|------|
| 1 | `exchanges/binance.py:37,39` | EDIT (2줄) | `params` → `params=params` (keyword) |

### 수정 전후

```python
# Before (L37):
order = await self.client.create_market_order(symbol, side, quantity, params)
# Before (L39):
order = await self.client.create_limit_order(symbol, side, quantity, price, params)

# After (L37):
order = await self.client.create_market_order(symbol, side, quantity, params=params)
# After (L39):
order = await self.client.create_limit_order(symbol, side, quantity, price, params=params)
```

### 테스트 결과

```
CR-036 전용 테스트: 5/5 PASS (기존 테스트 회귀 없음)
관련 테스트: 50/50 PASS (cr036 + order_executor + market_feed)
M2-2 재실행: FILLED (수정 효과 실증)
```

### M2-2 실행 결과와의 관계

- 첫 실행: `decimal.ConversionSyntax` 에러로 실패
- params=params 수정 후 재실행: **FILLED** (Binance order 59922222570)
- 실행 성공은 이 수정의 직접적 효과

---

## (5) 실행방법

### 검증 재현

```bash
cd C:/Users/Admin/K-V3

# 관련 테스트
python -m pytest tests/test_cr036_execution_contract.py tests/test_order_executor.py -v

# 소스 확인
grep -n "params=params" exchanges/binance.py
# → L37, L39 두 곳
```

---

## (6) 더 좋은 아이디어

### Execution Contract Preflight 확장 제안

CR-036에서 도입한 3항목 체크에 4번째를 추가:

1. 상품군 일치 (spot/futures/margin)
2. 호출 시그니처 일치 (executor ↔ adapter)
3. 승인 범위 일치 (review package ↔ adapter 설정)
4. **CCXT 호출 계약 일치 (adapter ↔ CCXT positional/keyword)**

### 운영 헌법 추가 규칙 제안

> **실행 중 신규 결함 발견 시: 실행 결과 판정과 코드 결함 처리를 분리한다.
> 실행 결과는 사실대로 판정하고, 코드 결함은 반드시 신규 CR로 분리한다.**

---

## 미해결 리스크

| # | 리스크 | 심각도 |
|---|--------|--------|
| R-1 | UpBit/Bitget 어댑터도 동일 패턴 가능 | LOW (M2-2 범위 외) |

---

## B의 봉인 권고

CR-037은 수정 완료, M2-2 실행으로 효과 실증, 테스트 회귀 없음.
A의 SEALED 판정을 요청합니다.
