# M2-2 Post-Run Baseline Card

Effective: 2026-03-31
Status: **SEALED — BASELINE**
Author: B (Implementer)
Reviewer: A (Designer)
Scope: M2-2 micro-live 기준선 성공 사례 정리

---

## 1. 기준선 실행 결과

| 항목 | 값 |
|------|-----|
| 실행일 | 2026-03-31 |
| Binance Order ID | 59922222570 |
| Symbol | BTC/USDT (spot) |
| Side | buy (market) |
| Quantity | 0.00015 BTC |
| Price | 66,292.36 USDT |
| Notional | ~9.94 USDT |
| Status | FILLED |
| dry_run | False |

---

## 2. 파이프라인 기준선

### Lineage

```
Agent:     AP-20260331104214-726e54
Execution: EP-20260331104214-ea3602
Submit:    SP-20260331104214-2cb99e
Order:     OX-20260331104215-199714
Exchange:  59922222570
```

### Guard Checks: 15/15 PASS

- ActionLedger: 4/4 (RISK_APPROVED, GOVERNANCE_CLEAR, SIZE_BOUND, COST_BUDGET)
- ExecutionLedger: 5/5 (AGENT_RECEIPTED, GOVERNANCE_CLEAR, COST_WITHIN_BUDGET, LOCKDOWN_CHECK, SIZE_FINAL_CHECK)
- SubmitLedger: 6/6 (EXEC_RECEIPTED, GOVERNANCE_FINAL, COST_FINAL, LOCKDOWN_FINAL, EXCHANGE_ALLOWED, SIZE_SUBMIT_CHECK)

### Constitution Compliance: 10/10 PASS

---

## 3. 승인 경계 (재사용 기준)

| 항목 | 기준선 값 | 확대 시 필요 |
|------|----------|------------|
| 주문 수 | 1건 | 새 REVIEW |
| 종목 수 | 1종목 (BTC/USDT) | 새 REVIEW |
| 금액 | ~10 USDT | 새 REVIEW |
| 시간 | 60초 윈도우 | 새 REVIEW |
| 거래소 | Binance spot | 새 REVIEW |
| 가드 | 7계층 15 guard | 완화 금지 |

---

## 4. 봉인된 CR 체인

| CR | 내용 | 상태 |
|----|------|------|
| CR-033 | M2-1 Live-Read Verification | SEALED |
| CR-034 | Dashboard PostgreSQL datetime fix | SEALED |
| CR-035 | Connection saturation prevention | SEALED |
| CR-036 | Execution path contract fix (spot + signature) | SEALED |
| CR-037 | params keyword contract fix | SEALED |

---

## 5. 봉인된 관측/검증 체인

| 항목 | 결과 | 상태 |
|------|------|------|
| OBS-001 | 재기동 안정성 3회 PASS | SEALED |
| M2-1.5 | dry-run 관통 10/10 PASS | SEALED |
| M2-2 | micro-live FILLED | SEALED |

---

## 6. 이후 확장 시 필수 절차

M2-2 기준선을 넘는 모든 실행에는 아래가 필요하다.

1. **새 REVIEW 패키지** (범위/가드/차단/복귀 명시)
2. **A 승인** (GO/NO-GO 판정)
3. **pre-execution preflight** (dry-run 또는 contract check)
4. **post-run review** (체결/side-effect/lineage/constitution)

자동 확장 승인은 존재하지 않는다.

---

## 7. 운영 규칙 (이번 흐름에서 확립)

### M 계열 승인 표준 (3단계)

1. Review Package → A REVIEW
2. Pre-Go Dry-Run (또는 Contract Preflight) → A 확인
3. Final GO → 실행 → Post-Run Review → SEALED

### 실행 중 신규 결함 발견 시

1. 실행 결과 판정은 사실대로 분리
2. 기존 sealed CR에 소급 병합 금지
3. 신규 CR 발행
4. 해당 CR 봉인 전까지 필요한 범위만 최소 보류
5. 봉인 후 보류 사유만 해제

### Execution Contract Preflight (4항목)

1. 상품군 일치 (spot/futures/margin)
2. 호출 시그니처 일치 (executor ↔ adapter)
3. 승인 범위 일치 (review package ↔ adapter 설정)
4. CCXT 호출 계약 일치 (adapter ↔ CCXT positional/keyword)
