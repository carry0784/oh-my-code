# M2-2 Baseline Diff Checklist

Effective: 2026-03-31
Status: **HOLD** (Repeat REVIEW 부속 문서)
Author: B (Implementer)
Reviewer: A (Designer)
Baseline Tag: `baseline-m2-2-first-microlive-sealed` → `8e26867`

---

> 이 문서는 M2-2 Repeat GO 시점에 기준선 대비 차이를 확인하기 위한 체크리스트다.
> 현재는 초안이며, GO 직전에 재확인 필수.

---

## 1. 실행 경로 코드 차이

**기준선 이후 실행 경로 코드 변경: 0건**

| 파일 | 기준선 상태 | 현재 | 차이 |
|------|-------------|------|------|
| `exchanges/binance.py` | CR-036+037 적용 (spot, params=params) | 동일 | **없음** |
| `app/services/order_executor.py` | CR-036 적용 (quantity, arg order) | 동일 | **없음** |
| `app/agents/action_ledger.py` | 4 guard chain | 동일 | **없음** |
| `app/services/execution_ledger.py` | 5 guard chain | 동일 | **없음** |
| `app/services/submit_ledger.py` | 6 guard chain | 동일 | **없음** |
| `scripts/m2_2_micro_live.py` | M2-2 실행 스크립트 | 동일 | **없음** |

---

## 2. 가드 상태 차이

| 가드 계층 | 기준선 | 현재 | 차이 |
|-----------|--------|------|------|
| ActionLedger | 4 checks (RISK, GOVERNANCE, SIZE, COST) | 동일 | **없음** |
| ExecutionLedger | 5 checks (AGENT, GOVERNANCE, COST, LOCKDOWN, SIZE) | 동일 | **없음** |
| SubmitLedger | 6 checks (EXEC, GOVERNANCE, COST, LOCKDOWN, EXCHANGE, SIZE) | 동일 | **없음** |
| 합계 | 15/15 | 15/15 | **없음** |

---

## 3. 승인 범위 차이

| 항목 | 기준선 | 현재 | 차이 |
|------|--------|------|------|
| 주문 수 | 1건 | 1건 | **없음** |
| 종목 수 | 1종목 (BTC/USDT) | 1종목 | **없음** |
| 금액 | ~10 USDT | ~10 USDT | **없음** |
| 시간 | 60초 | 60초 | **없음** |
| 거래소 | Binance spot | Binance spot | **없음** |

---

## 4. 인프라/환경 차이

**기준선 이후 인프라 변경:**

| 항목 | 기준선 (2026-03-31) | 현재 | 차이 |
|------|---------------------|------|------|
| `app/core/database.py` | CR-035 pool defense 적용 | 동일 | **없음** |
| `app/main.py` | CR-035 shutdown dispose 적용 | 동일 | **없음** |
| sync engine dispose | 5곳 적용 | 동일 | **없음** |
| `.env` BINANCE_TESTNET | true | true (확인 필요) | GO 시 재확인 |
| PostgreSQL | 16-alpine | 확인 필요 | GO 시 재확인 |
| Redis | 7-alpine | 확인 필요 | GO 시 재확인 |
| Python | 3.14 | 확인 필요 | GO 시 재확인 |

---

## 5. 테스트 차이

**기준선 이후 테스트 변경:**

| 항목 | 기준선 | 현재 | 차이 |
|------|--------|------|------|
| 전체 테스트 수 | 3176 | 3176 | **없음** |
| 실패 수 | 0 | 0 | **없음** |
| CR-036 전용 테스트 | 5/5 PASS | 동일 | **없음** |
| 신규 테스트 추가 | — | 23파일 (관측 서비스) | 실행 경로 무관 |

신규 테스트는 관측 서비스(observation) 전용이며, 실행 경로(execution path)와 무관.

---

## 6. 운영 스크립트 차이

| 파일 | 기준선 | 현재 | 차이 |
|------|--------|------|------|
| `scripts/m2_2_micro_live.py` | 기준선 실행 스크립트 | 동일 | **없음** |
| `scripts/m2_1_5_dryrun_test.py` | dry-run 검증 스크립트 | 동일 | **없음** |
| `scripts/start_server.sh` | CR-035 기동 가드 | 동일 | **없음** |
| 신규 스크립트 | — | autofix, evolution, governance, inject | 실행 경로 무관 |

---

## 7. 문서 차이

**기준선 이후 문서 변경: 97파일 추가 (실행 경로 변경 0건)**

| 카테고리 | 추가 수 | 실행 영향 |
|----------|---------|-----------|
| 거버넌스 증거 봉인 (evidence/) | 19파일 | 없음 |
| 운영 문서 (operations/) | 41파일 | 없음 |
| 관측 스키마/서비스 | 27파일 | 없음 |
| 관측 테스트 | 23파일 | 없음 |
| 기타 (constitution, scripts) | 추가분 | 없음 |

---

## 8. 종합 판정

### 기준선 대비 실행 경로 차이: **0건**

| 축 | 차이 수 | 실행 영향 |
|----|---------|-----------|
| 실행 경로 코드 | 0 | 없음 |
| 가드 체인 | 0 | 없음 |
| 승인 범위 | 0 | 없음 |
| 실행 스크립트 | 0 | 없음 |
| 인프라 코드 | 0 | 없음 |
| 환경 값 | TBD | GO 시 재확인 |

### 기준선 이후 추가분: 155파일 (+30,795줄)

전부 관측 서비스, 거버넌스 문서, 테스트 추가이며,
**실행 경로(execution path)에 영향을 주는 변경은 0건**이다.

---

## GO 시 재확인 항목

| # | 항목 | 확인 방법 |
|---|------|-----------|
| 1 | `git diff baseline-m2-2-first-microlive-sealed..HEAD -- exchanges/ app/services/order_executor.py` | 변경 0건 확인 |
| 2 | `python -m pytest tests/test_cr036_execution_contract.py -v` | 5/5 PASS |
| 3 | `python -m pytest tests/ -x -q` | 전체 PASS |
| 4 | `.env` BINANCE_TESTNET=true | 파일 직접 확인 |
| 5 | USDT 잔고 | Binance API 조회 |
| 6 | BTC/USDT 현재가 → 수량 계산 | ~10 USDT / 현재가 |

---

## 현재 실행 금지

이 문서는 diff 확인용 초안이며, 실행 승인 문서가 아니다.
새 REVIEW + 새 Execution Authorization 없이는 GO 불가.
