# M2-2 REVIEW 패키지 — Micro-Live 단일 주문 실행 검토

Effective: 2026-03-31
Status: **SEALED — PASS** (A 승인 2026-03-31, Binance order 59922222570 FILLED)
Author: B (Implementer)
Reviewer: A (Designer)
Scope: M2-2 실행 가능성 검토, GO/NO-GO 판정 자료

---

## (1) 해석 및 요약

### M2-2 목적 정의

M2-2(Micro-Live)는 **Binance mainnet에서 단 1건의 실제 주문을 실행**하여
전체 실행 파이프라인의 종단간(end-to-end) 무결성을 검증하는 단계이다.

```
검증 대상:
AgentOrchestrator → ActionLedger → SubmitLedger → OrderExecutor
→ MicroExecutor(E-03) → Exchange Adapter → Binance Mainnet
→ Fill 확인 → Evidence PRE+POST 쌍 생성 → 즉시 Mode 1 복귀
```

### M2-1과 M2-2의 경계

| 차원 | M2-1 (완료) | M2-2 (검토 중) |
|------|-------------|---------------|
| 성격 | Live-Read (읽기 전용) | Micro-Live (단건 실행) |
| dry_run | true (항상) | **false (이 단계에서만)** |
| _live_authorized | false (항상) | **true (authorize_live() 1회)** |
| execution_scope | NO_EXECUTION | **SPECIFIC_SYMBOL_ONLY** |
| 주문 수 | 0건 | **정확히 1건** |
| 종목 | 모든 종목 읽기 가능 | **A가 지정한 단일 종목만** |
| 금액 | N/A | **거래소 최소 단위 (약 10 USDT)** |
| write 행위 | API 권한으로 차단됨 | **허용, 감시 하에 실행** |
| evidence | N/A | **PRE+POST 쌍 필수** |
| 롤백 | 암묵적 (주문 없음) | **명시적: revoke_live() + dry_run=true** |

### M2-2가 검증하려는 정확한 대상

1. **실행 파이프라인 연결성**: 7개 컴포넌트가 실제로 연결되어 주문이 거래소에 도달하는지
2. **안전장치 작동**: 1건 초과 시 lockdown, 다른 종목 시 거부, evidence 누락 시 abort
3. **복귀 무결성**: 실행 후 즉시 Mode 1(dry_run=true)로 돌아가는지
4. **Evidence 완전성**: PRE(주문 전) + POST(주문 후) evidence 쌍이 append-only store에 기록되는지

---

## (2) 장점 / 단점

### M2-2 실행의 장점

- 전체 실행 파이프라인을 **단 1건, 최소 금액**으로 실증
- 성공 시 Mode 2 full(M2-3) 진입의 신뢰 기반 확보
- 5계층 안전장치(dry_run, authorize_live, execution_scope, max_order, lockdown)가 동시 작동
- 실패 시에도 최대 손실 = 약 10 USDT (거래소 최소 단위)

### M2-2 실행의 단점

- **실제 자금 이동**: 테스트넷이 아닌 메인넷에서 실제 주문 발생
- **API 키 권한 변경 필요**: 현재 read-only → trading 권한 필요 (M2-1에서 비활성화한 것을 다시 활성화)
- **일시적 dry_run=false**: 실행 중 시스템이 실행 가능 상태가 됨
- **롤백 실패 리스크**: 주문 자체는 취소 불가 (fill 후에는 포지션으로 남음)

---

## (3) 이유 / 근거

### 전제 조건 충족 상태

| # | 조건 | 상태 | 근거 |
|---|------|------|------|
| G-1 | CR-034 SEALED | SEALED | BL-TZ02 datetime fix |
| G-2 | CR-035 SEALED | SEALED | 커넥션 포화 방지 |
| G-3 | DB 쿼리 정상 (<1s) | 0.103s | CR-035 Phase A 계측 |
| G-4 | DataError 0건 | 0건 | CR-034 fix 효과 |
| G-5 | enforcement NORMAL | NORMAL | governance gate 정상 |
| G-6 | PG 커넥션 정상 | 6/100 | OBS-001 PASS |
| G-7 | 테스트 기준선 | 3171/0/0 | CR-035 Phase B 검증 |
| G-8 | M2-1 CONDITIONAL PASS | SEALED | live-read 완료 |
| G-9 | OBS-001 PASS | SEALED | 재기동 안정성 실증 |

**9/9 충족.**

### 실행 파이프라인 구현 상태

| 컴포넌트 | 파일 | 상태 |
|----------|------|------|
| ActionLedger | `app/agents/action_ledger.py` | 구현됨 |
| SubmitLedger | `app/services/submit_ledger.py` | 구현됨 (6 guards, fail-closed) |
| ExecutionLedger | `app/services/execution_ledger.py` | 구현됨 (5 guards) |
| OrderExecutor | `app/services/order_executor.py` | 구현됨 (dry_run=True default) |
| E-01 Precondition | `app/core/executor_design.py` | 구현됨 |
| E-02 Activation | `app/core/executor_activation.py` | 구현됨 |
| E-03 Dispatch Guard | `app/core/micro_executor.py` | 구현됨 |

**7/7 컴포넌트 구현 완료.**

### 안전장치 구현 상태

| # | 안전장치 | 메커니즘 | 상태 |
|---|---------|----------|------|
| S-1 | dry_run | OrderExecutor(dry_run=True) default | 구현됨 |
| S-2 | _live_authorized | authorize_live() / revoke_live() | 구현됨 |
| S-3 | execution_scope | SPECIFIC_SYMBOL_ONLY enum | 구현됨 |
| S-4 | Lockdown | operator_approval + execution_policy | 구현됨 |
| S-5 | Evidence | PRE+POST append-only | 구현됨 |
| S-6 | SubmitLedger guards | 6단계 fail-closed | 구현됨 |
| S-7 | ExecutionLedger guards | 5단계 receipt-enforced | 구현됨 |

**7/7 안전장치 구현 완료.**

---

## (4) 실현/구현 대책

### 허용 범위

| 항목 | 허용 |
|------|------|
| dry_run | false (M2-2 실행 중에만) |
| _live_authorized | true (authorize_live() 1회) |
| execution_scope | SPECIFIC_SYMBOL_ONLY |
| 대상 종목 | A가 지정 (예: BTC/USDT) |
| 최대 금액 | 거래소 최소 단위 (약 10 USDT) |
| 최대 주문 수 | 1건 |
| 주문 유형 | MARKET (즉시 체결) |
| 실행 후 | 즉시 dry_run=true + revoke_live() |

### 금지 범위

| 항목 | 금지 |
|------|------|
| 2건 이상 주문 | 절대 금지 |
| 지정 종목 외 주문 | 절대 금지 |
| dry_run=false 상시화 | 절대 금지 |
| BINANCE_TESTNET=false 상시화 | 금지 (M2-2 실행 중에만) |
| 자동 재시도(retry) | 금지 |
| 포지션 확대 | 금지 (1건 체결 후 즉시 복귀) |
| CR-033/034/035 재논쟁 | 금지 |
| write/execution path 확대 | 금지 |

### Side-Effect 0 보장 장치

| 계층 | 장치 | 효과 |
|------|------|------|
| 1 | dry_run=True (기본값) | 실행 불가 상태 기본 |
| 2 | authorize_live() 1회 소모 | 2번째 호출 무효 |
| 3 | SPECIFIC_SYMBOL_ONLY | 다른 종목 거부 |
| 4 | max_order_count=1 (idempotency) | 중복 실행 방지 |
| 5 | SubmitLedger 6-guard | 조건 미충족 시 fail-closed |
| 6 | ExecutionLedger 5-guard | receipt 없으면 전이 불가 |
| 7 | Lockdown trigger | 이상 탐지 시 즉시 전체 차단 |

**1건 체결 후 시스템은 자동으로 실행 불가 상태로 복귀한다.**

### Write 차단 확인 방법

M2-2 실행 전:
1. `dry_run=True` 확인 (OrderExecutor 기본값)
2. `_live_authorized=False` 확인
3. `execution_scope=NO_EXECUTION` 확인

M2-2 실행 중:
1. `authorize_live()` 호출 → `_live_authorized=True` (1회만)
2. `execution_scope=SPECIFIC_SYMBOL_ONLY` 전환
3. `dry_run=False` 전환

M2-2 실행 후:
1. `revoke_live()` → `_live_authorized=False`
2. `dry_run=True` 복원
3. `execution_scope=NO_EXECUTION` 복원
4. BINANCE_TESTNET=true 복원

### 즉시 중단 조건

| # | 조건 | 행동 |
|---|------|------|
| A-1 | 2건 이상 주문 시도 | 즉시 LOCKDOWN |
| A-2 | 지정 외 종목 주문 시도 | 즉시 LOCKDOWN |
| A-3 | 자동 재시도 탐지 | 즉시 LOCKDOWN |
| A-4 | 일일 손실 > max_notional 50% | 즉시 LOCKDOWN |
| A-5 | Evidence PRE+POST 쌍 불완전 | 즉시 ABORT |
| A-6 | 60초 실행 윈도우 초과 | 자동 만료, revoke |
| A-7 | 서버 프로세스 이상 | 즉시 중단, dry_run=true |

### 롤백 절차

```
단계 1: dry_run=True 즉시 복원
단계 2: revoke_live() 호출
단계 3: execution_scope=NO_EXECUTION 복원
단계 4: BINANCE_TESTNET=true 복원 (.env)
단계 5: 서버 재시작 (clean state)
단계 6: /startup + /status 정상 확인
단계 7: pg_stat_activity 기준선 확인
```

**주문 자체는 취소 불가** (market order 즉시 체결). 체결된 포지션은 별도 청산 필요.

---

## (5) 실행방법

### 성공 기준

| # | 기준 | 조건 |
|---|------|------|
| P-1 | 주문 1건 체결 | fill 확인 |
| P-2 | 정확한 종목 | A 지정 종목과 일치 |
| P-3 | 금액 범위 | 거래소 최소 단위 이내 |
| P-4 | Evidence 완전 | PRE + POST 쌍 존재 |
| P-5 | 자동 재시도 없음 | 1건 후 추가 시도 0 |
| P-6 | Mode 1 복귀 | dry_run=true, _live_authorized=false |
| P-7 | 시스템 정상 | /startup 200, enforcement NORMAL |

**7/7 충족 = PASS**

### 실패 기준

| # | 기준 | 조건 |
|---|------|------|
| F-1 | 주문 실패 | fill 미확인 (timeout, reject) |
| F-2 | 2건 이상 실행 | lockdown 발동 |
| F-3 | 잘못된 종목 | 지정 외 종목 체결 |
| F-4 | Evidence 누락 | PRE 또는 POST 없음 |
| F-5 | 복귀 실패 | dry_run=true 미복원 |
| F-6 | LOCKDOWN 발동 | 안전장치 위반 탐지 |

**F-1~F-6 중 1건이라도 해당 = FAIL**

### 실행 순서 (A GO 판정 후)

```
[사전]
1. A가 target_symbol, max_notional 지정
2. Binance API 키 trading 권한 활성화 (임시)
3. BINANCE_TESTNET=false 설정 (임시)
4. 서버 시작 (bash scripts/start_server.sh)
5. /startup 200 확인

[실행]
6. authorize_live() 호출
7. execution_scope=SPECIFIC_SYMBOL_ONLY 설정
8. dry_run=False 설정
9. 단일 주문 실행 (target_symbol, min_qty, MARKET)
10. Fill 확인

[수거]
11. Evidence PRE+POST 확인
12. revoke_live()
13. dry_run=True 복원
14. execution_scope=NO_EXECUTION 복원
15. BINANCE_TESTNET=true 복원
16. API 키 trading 권한 비활성화
17. 서버 재시작 (clean state)
18. /startup 200 + enforcement NORMAL 확인
```

---

## (6) 더 좋은 아이디어

### M2-2 실행 전 추가 검증 후보

M2-2 실행 전에 한 단계 더 둘 수 있다:

**M2-1.5 (Dry-Run Pipeline 관통 테스트)**

dry_run=True 상태에서 전체 파이프라인을 관통시켜,
주문이 거래소에 도달하기 **직전까지** 모든 컴포넌트가 정상 작동하는지 확인.

이것은 실제 자금 이동 없이 파이프라인 연결성만 검증하는 것으로,
M2-2의 리스크를 더 줄일 수 있다.

**A가 판단할 사항**:
- M2-1.5를 추가할지, 아니면 바로 M2-2로 갈지
- 현재 테스트 3171개가 이미 파이프라인을 커버하고 있으므로 불필요할 수도 있음

---

## 헌법 조항 대조

| 규칙 | 준수 | 비고 |
|------|------|------|
| 자동 GO 전제 금지 | ✅ | REVIEW 패키지 제출만 |
| live execution 확대 금지 | ✅ | 1건/1종목/최소금액 고정 |
| testnet=false 상시화 금지 | ✅ | M2-2 중에만 임시 |
| write/execution path 개방 금지 | ✅ | 기존 코드 변경 없음 |
| CR-033/034/035 재논쟁 금지 | ✅ | 봉인 유지 |

## 미해결 리스크

| # | 리스크 | 심각도 | 대응 |
|---|--------|--------|------|
| R-1 | API 키 trading 권한 재활성화 필요 | MEDIUM | M2-2 직후 비활성화 |
| R-2 | Market order 체결 후 포지션 잔류 | LOW | 별도 청산 또는 방치(최소 금액) |
| R-3 | 60초 윈도우 내 네트워크 장애 | LOW | 자동 만료 → revoke |
| R-4 | Evidence store 기록 실패 | LOW | fail-closed → abort |

## GO / CONDITIONAL GO / HOLD / NO-GO 판정표

| 판정 | 조건 |
|------|------|
| **GO** | 9/9 전제조건 충족 + A가 target_symbol/max_notional 지정 + API 키 준비 |
| **CONDITIONAL GO** | 전제조건 충족하나 M2-1.5 dry-run 관통 테스트 1회 추가 후 GO |
| **HOLD** | 전제조건 충족하나 추가 안정화 기간 필요 (예: 7일 Mode 1 관찰) |
| **NO-GO** | 전제조건 미충족, 안전장치 미구현, 또는 A가 리스크 불수용 |

---

## A 판정용 1문장 결론

**M2-2 전제조건 9/9 충족, 실행 파이프라인 7/7 구현, 안전장치 7/7 구현, 1건/1종목/최소금액/60초 윈도우 경계 내에서 A의 GO 판정 시 실행 가능 — 단, 자동 GO가 아닌 A의 명시적 판정 필요.**
