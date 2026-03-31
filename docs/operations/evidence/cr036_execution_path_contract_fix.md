# CR-036: M2-2 Execution Path Contract Fix

Effective: 2026-03-31
Status: **SEALED** (A 승인 2026-03-31)
Author: B (Implementer)
Reviewer: A (Designer)
Scope: M2-2 실행 경로 결함 2건 수정
Related: M2-2 (BLOCKED), M2-1.5 (SEALED — PASS)

---

## (1) 해석 및 요약

### M2-2 blocker 2건 수정 완료

M2-2 GO 승인 직후, 실행 경로(`dry_run=False` 분기) 점검에서 2건의 결함을 발견했다.
A가 (C) 채택 — 별도 CR로 분리, 수정/검증 후 재판정.

| # | 문제 | 심각도 | 수정 |
|---|------|--------|------|
| 1 | `exchanges/binance.py` — `defaultType: "future"` | HIGH | `"future"` → `"spot"` |
| 2 | `OrderExecutor` → `Exchange` 호출 계약 불일치 | HIGH | `amount` → `quantity`, 인자 순서 정합화 |

### 왜 M2-2 blocker인가

- **문제 1**: 승인 범위는 spot BTC/USDT인데, 어댑터는 futures를 기본 실행. **상품군 위반**.
- **문제 2**: `create_order(amount=X)` 호출이 `create_order(quantity=X)` 시그니처에 바인딩 실패. **TypeError 발생** 또는 잘못된 바인딩.

두 문제 모두 `dry_run=True` 경로에서는 발현하지 않는다 (exchange 미호출).
따라서 M2-1.5 통과에도 불구하고, `dry_run=False` 경로는 미검증이었다.

---

## (2) 장점 / 단점

### 장점
- 수정이 최소 범위 (2파일, 각 1줄)
- 기존 파이프라인 구조 불변 (우회 없음)
- 전용 테스트 5건 추가로 재발 방지
- 전체 테스트 3176/0/0 PASS (회귀 없음)
- dry-run 재검증 10/10 PASS

### 단점
- M2-2 일정 1회 지연
- dry-run이 이 결함을 커버하지 못했다는 사실 자체가 테스트 갭

---

## (3) 이유 / 근거

### 문제 1: futures → spot

`exchanges/binance.py:20` 원래 값:
```python
"defaultType": "future"   # CCXT futures 모드
```

M2-2 승인 범위는 **spot BTC/USDT**이므로 futures 실행은 범위 위반:
- 마진/레버리지 요구
- 최소 주문 단위 상이
- 리스크 프로파일 다름
- 결제 메커니즘 다름

수정:
```python
"defaultType": "spot"
```

### 문제 2: create_order() 계약 불일치

`BaseExchange.create_order()` 시그니처:
```python
def create_order(self, symbol, side, order_type, quantity, price=None)
```

`OrderExecutor` 기존 호출:
```python
ex.create_order(symbol=symbol, order_type=order_type, side=side, amount=requested_size, price=price)
```

불일치 2건:
1. `amount` → `quantity` (키워드명)
2. `order_type, side` → `side, order_type` (순서)

수정 후:
```python
ex.create_order(symbol=symbol, side=side, order_type=order_type, quantity=requested_size, price=price)
```

### spot 경계 보장 근거

| 검증 | 결과 |
|------|------|
| `BinanceExchange.__init__` 소스에 `"defaultType": "spot"` | ✅ |
| `"defaultType": "future"` 소스에 없음 | ✅ |
| 테스트 `test_binance_adapter_spot_mode` PASS | ✅ |
| 테스트 `test_binance_adapter_no_futures` PASS | ✅ |

### create_order 계약 정합성 근거

| 검증 | 결과 |
|------|------|
| `OrderExecutor` 소스에 `quantity=requested_size` | ✅ |
| `OrderExecutor` 소스에 `amount=requested_size` 없음 | ✅ |
| 인자 순서: symbol < side < order_type < quantity | ✅ |
| 테스트 `test_order_executor_create_order_signature_match` PASS | ✅ |
| 테스트 `test_order_executor_create_order_arg_order` PASS | ✅ |

---

## (4) 실현/구현 대책

### 변경 파일 목록

| # | 파일 | 변경 | 내용 |
|---|------|------|------|
| 1 | `exchanges/binance.py` | EDIT (1줄) | `"future"` → `"spot"` |
| 2 | `app/services/order_executor.py` | EDIT (2줄) | `amount` → `quantity`, 인자 순서 정합화 |
| 3 | `tests/test_cr036_execution_contract.py` | NEW (5 tests) | spot 모드, futures 차단, 시그니처, 인자 순서, lineage |

> **Note**: `create_market_order` params keyword 수정건은 CR-036 범위 외. CR-037로 분리 등록됨.

### 테스트 결과

```
CR-036 전용 테스트: 5/5 PASS
전체 테스트: 3176/0/0 PASS (기존 3171 + CR-036 5건)
dry-run 재검증: 10/10 PASS
```

### 금지사항 준수

| 금지 | 준수 |
|------|------|
| OrderExecutor 우회 금지 | ✅ 파이프라인 유지 |
| Schema/Alembic 변경 금지 | ✅ |
| Write/execution path 추가 개방 금지 | ✅ |
| 가드 완화 금지 | ✅ |

---

## (5) 실행방법

### 수정 검증 재현

```bash
cd C:/Users/Admin/K-V3

# CR-036 전용 테스트
python -m pytest tests/test_cr036_execution_contract.py -v

# 전체 테스트 회귀
python -m pytest tests/ -x -q

# dry-run 재검증
PYTHONPATH=. python scripts/m2_1_5_dryrun_test.py
```

### 코드 잔여 참조 확인

```bash
# futures 잔여 확인
grep -n "defaultType.*future" exchanges/binance.py
# → 0건 예상

# amount 잔여 확인
grep -n "amount=requested_size" app/services/order_executor.py
# → 0건 예상
```

---

## (6) 더 좋은 아이디어

### Execution Contract Preflight 고정 절차 제안

A가 권고한 3항목 체크를 M2 계열 승인 전 고정 절차로 추가:

1. **상품군 일치**: spot / futures / margin
2. **호출 시그니처 일치**: executor ↔ adapter ↔ base class
3. **승인 범위 일치**: review package ↔ 실제 adapter 설정

이 3항목은 `test_cr036_execution_contract.py`로 자동화되었으므로,
향후에는 `pytest tests/test_cr036_execution_contract.py`로 사전 검증 가능.

### dry-run 갭 분석

이번 건이 dry-run에서 발견되지 않은 이유:
- dry-run 경로(`[4] dry_run 모드`)는 exchange를 호출하지 않음
- 따라서 `create_order()` 시그니처와 `defaultType` 모두 미검증

향후 M2 계열에서는 dry-run 외에 **execution contract preflight**를 추가해야 한다.

---

## 미해결 리스크

| # | 리스크 | 심각도 | 비고 |
|---|--------|--------|------|
| R-1 | 다른 exchange 어댑터(upbit, bitget 등)도 동일 불일치 가능 | LOW | M2-2 범위는 binance만 |
| R-2 | spot 모드 전환으로 기존 futures 기능(fetch_positions 등) 동작 변경 | LOW | M2-2는 단일 market buy만 |

---

## M2-2 재판정 권고

### B의 의견

CR-036 수정 완료. 다음 근거로 M2-2 BLOCKED 해제를 권고합니다:

1. **spot 모드 확정**: `defaultType: "spot"` 소스 및 테스트 확인
2. **create_order 계약 정합**: 시그니처 + 인자 순서 일치, 테스트 확인
3. **기존 파이프라인 무변경**: 우회 없음, 구조 보존
4. **전체 테스트 3176/0/0**: 회귀 없음
5. **dry-run 재검증 10/10**: 파이프라인 정합성 유지
6. **execution contract preflight 테스트 자동화**: 재발 방지

### 상태 전이 제안

```
CR-036: REVIEW 대기 (A 판정 필요)
M2-2: BLOCKED → (A 판정에 따라) UNBLOCKED / GO 재승인
```
