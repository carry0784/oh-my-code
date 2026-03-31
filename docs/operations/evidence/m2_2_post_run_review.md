# M2-2 Post-Run Review

Effective: 2026-03-31
Status: **SEALED — PASS** (A 승인 2026-03-31)
Author: B (Implementer)
Reviewer: A (Designer)
Scope: M2-2 micro-live 단일 주문 실행 결과 검수

---

## (1) 해석 및 요약

### M2-2 FINAL VERDICT: PASS

Binance mainnet에서 BTC/USDT spot market buy 1건을 성공적으로 체결했다.

```
체결 결과:
  Order ID:     OX-20260331104215-199714
  Exchange ID:  59922222570
  Status:       FILLED
  Symbol:       BTC/USDT
  Side:         buy
  Type:         market
  Requested:    0.00015 BTC
  Executed:     0.00015 BTC
  Price:        66,292.36 USDT
  Notional:     ~9.94 USDT
  dry_run:      False
```

---

## (2) 실제 체결/미체결 결과

| 항목 | 결과 |
|------|------|
| 체결 여부 | **FILLED** |
| 체결 수량 | 0.00015 BTC (requested와 동일) |
| 체결 가격 | 66,292.36 USDT |
| 실제 비용 | ~9.94 USDT |
| 슬리피지 | 최소 (market order) |
| 체결 시간 | 2026-03-31 10:42:15 UTC |
| Binance Order ID | 59922222570 |

---

## (3) Side-Effect 결과

| 항목 | 결과 |
|------|------|
| Total orders | 1 |
| Live orders | 1 |
| Dry-run orders | 0 |
| Actual notional | ~9.94 USDT |
| Range violation | NO |
| .env 파일 변경 | NO (BINANCE_TESTNET=true 유지) |
| TESTNET 런타임 복원 | YES (true) |
| 다건 실행 | NO |
| 다종목 실행 | NO |
| 금액 초과 | NO (9.94 < 11.0 hard cap) |

**Side-effect: 정확히 1건, 최소금액, 승인 범위 내**

---

## (4) Evidence / Ledger / Receipt Lineage

### Full Lineage Trace

```
Agent:     AP-20260331104214-726e54
Execution: EP-20260331104214-ea3602
Submit:    SP-20260331104214-2cb99e
Order:     OX-20260331104215-199714
Exchange:  59922222570
```

### Board Summary (실행 후)

| Ledger | Total | Receipted | Blocked | Orphan |
|--------|-------|-----------|---------|--------|
| ActionLedger | 1 | 1 | 0 | 0 |
| ExecutionLedger | 1 | 1 | 0 | 0 |
| SubmitLedger | 1 | 1 | 0 | 0 |
| OrderExecutor | 1 | FILLED | - | - |

### Guard Check 전체 결과

#### ActionLedger (4 checks)

| Guard | 결과 |
|-------|------|
| RISK_APPROVED | PASS |
| GOVERNANCE_CLEAR | PASS |
| SIZE_BOUND | PASS |
| COST_BUDGET | PASS |

#### ExecutionLedger (5 checks)

| Guard | 결과 |
|-------|------|
| AGENT_RECEIPTED | PASS |
| GOVERNANCE_CLEAR | PASS |
| COST_WITHIN_BUDGET | PASS |
| LOCKDOWN_CHECK | PASS |
| SIZE_FINAL_CHECK | PASS |

#### SubmitLedger (6 checks)

| Guard | 결과 |
|-------|------|
| EXEC_RECEIPTED | PASS |
| GOVERNANCE_FINAL | PASS |
| COST_FINAL | PASS |
| LOCKDOWN_FINAL | PASS |
| EXCHANGE_ALLOWED | PASS |
| SIZE_SUBMIT_CHECK | PASS |

**15/15 guard check PASS**

---

## (5) 헌법 조항 대조 검수본

| 규칙 | 준수 | 비고 |
|------|------|------|
| 1건 제한 | PASS | live_orders = 1 |
| 1종목 제한 | PASS | BTC/USDT only |
| 최소금액 범위 | PASS | 9.94 USDT |
| 60초 윈도우 | PASS | 실행 총 ~4초 |
| spot 모드 | PASS | defaultType = spot |
| .env 미변경 | PASS | BINANCE_TESTNET=true 유지 |
| TESTNET 복원 | PASS | 런타임 true 복원 확인 |
| 파이프라인 우회 없음 | PASS | lineage 정합 확인 |
| 범위 확대 | PASS | 미시도 |
| 가드 완화 | PASS | 15/15 guard PASS |

**Constitution Compliance: 10/10 PASS**

---

## (6) 동일 경계 재실행 가능 여부

### 결론: 가능 (단, 새 승인 필요)

기술적으로는 동일 스크립트로 재실행 가능하다. 단:
- 현재 승인은 **1건 한정**이므로 추가 실행에는 새 승인 필요
- ActionLedger의 duplicate 차단 (60초 cooldown)이 동일 파라미터 재실행을 자동 방어
- 범위 확대(다건, 다종목, 금액)에는 별도 review/approval 필요

---

## (7) 실행 중 발견된 추가 버그

### 문제 3: `create_market_order` params 위치 인자 (CR-036 추가)

`exchanges/binance.py:37` 에서:
```python
# Before (버그):
order = await self.client.create_market_order(symbol, side, quantity, params)
# CCXT 시그니처: create_market_order(symbol, side, amount, price=None, params={})
# → params dict가 price 위치에 들어감 → decimal.ConversionSyntax

# After (수정):
order = await self.client.create_market_order(symbol, side, quantity, params=params)
```

이 버그는 M2-2 첫 실행 시 발견되어 즉시 수정 후 재실행에서 FILLED 확인.

---

## (8) T-0 Preflight 결과

| # | 항목 | 결과 |
|---|------|------|
| PF-1 | .env BINANCE_TESTNET=true | PASS |
| PF-2 | Runtime override false | PASS |
| PF-3 | target_symbol = BTC/USDT | PASS |
| PF-4 | price/qty/notional 범위 | PASS (9.94 USDT) |
| PF-5 | free USDT 충분 | PASS (3,428.10 USDT) |

**Preflight: 5/5 PASS**

---

## GO / HOLD 판정용 1문장 결론

**M2-2 micro-live 성공: Binance mainnet BTC/USDT spot market buy 0.00015 BTC @ 66,292.36 체결 (9.94 USDT), 15 guard PASS, constitution 10/10 PASS, side-effect 정확히 1건, 파이프라인 정합성 유지, .env 미변경, TESTNET 복원 완료.**
