# M2-2 Execution Preparation — Micro-Live 단일 주문

Effective: 2026-03-31
Status: **SEALED — PASS** (2026-03-31, order 59922222570 FILLED, 9.94 USDT)
Additional Live Execution: CR-037 SEALED로 HOLD 해제 (2026-03-31). 단, 자동 승인 아님 — 이후 live는 별도 REVIEW/승인 필요.
Author: B (Implementer)
Reviewer: A (Designer)
Scope: M2-2 실행 파라미터 고정 및 사전 점검

---

## 실행 파라미터 (A 승인 경계)

| 항목 | 값 | 비고 |
|------|-----|------|
| **target_symbol** | **BTC/USDT** | A 지정 종목 |
| **max_notional** | **~10 USDT** | Binance 최소 주문 단위 |
| exchange | binance | mainnet |
| side | buy | market buy |
| order_type | market | 즉시 체결 |
| 주문 수 | 1건 | 초과 금지 |
| 종목 수 | 1종목 | 초과 금지 |
| 시간 윈도우 | 60초 | 실행 시작~종료 |
| dry_run | **false** | 이 실행에 한정 |

---

## 실행 경로

```
ActionLedger.propose_and_guard()     — 4 guard
  → ActionLedger.record_receipt()
    → ExecutionLedger.propose_and_guard() — 5 guard
      → ExecutionLedger.record_receipt()
        → SubmitLedger.propose_and_guard()  — 6 guard
          → SubmitLedger.record_receipt()
            → OrderExecutor.execute_order(dry_run=False)
              → ExchangeFactory.create("binance")
                → exchange.create_order("BTC/USDT", "market", "buy", amount)
```

---

## 사전 점검 체크리스트

| # | 항목 | 상태 | 비고 |
|---|------|------|------|
| 1 | BINANCE_TESTNET 환경변수 확인 | 대기 | 실행 직전 false 전환 |
| 2 | Binance API key trading 권한 확인 | 대기 | spot trading enabled |
| 3 | USDT 잔고 확인 (≥ 10 USDT) | 대기 | |
| 4 | 서버 미기동 확인 (포트 8000 free) | 대기 | |
| 5 | PostgreSQL 기동 확인 | 대기 | |
| 6 | 기존 stale 프로세스 없음 확인 | 대기 | |

---

## 실행 후 제출 항목 (A 요구)

1. 헌법 조항 대조 검수본
2. Evidence lineage (AP-* → EP-* → SP-* → OX-* → exchange order_id)
3. Side-effect 검증 (정확히 1건, 최소금액)
4. Guard/abort 동작 여부
5. 동일 경계 재실행 가능 여부

---

## 금지 사항

- 다건 실행
- 다종목 실행
- 금액 확대
- 윈도우 확대
- 가드 완화
- write/execution path 추가 개방
- testnet/mainnet 운영 기본값 재설정

---

## 복귀 절차

실행 완료 즉시:
1. BINANCE_TESTNET=true 복원
2. dry_run=True 기본값 확인
3. 운영 상태 오염 없음 확인
4. Post-Run Review 제출
