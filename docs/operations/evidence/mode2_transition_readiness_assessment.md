# Mode 2 Transition Readiness Assessment

Date: 2026-05-14
Author: B (Implementer)
Reviewer: A (Designer)
Status: **사전 판정 제출**

---

## 1. Mode 2 사전 판정표

### 1.1 실행 경로 존재 확인

| # | 컴포넌트 | 파일 | 구현 상태 | 비고 |
|---|----------|------|-----------|------|
| 1 | **AgentOrchestrator** | `app/agents/orchestrator.py` | ✅ 존재 | Signal→Risk→Submit→Execute 체인 |
| 2 | **SubmitLedger** | `app/services/submit_ledger.py` | ✅ 존재 | propose_and_guard(), record_receipt() |
| 3 | **OrderExecutor** | `app/services/order_executor.py` | ✅ 존재 | execute_order(dry_run=True 기본) |
| 4 | **TCL DispatchRouter** | `src/kdexter/tcl/commands.py` | ✅ 존재 | DRY_RUN/LIVE mode, idempotency, RISK.CHECK |
| 5 | **Exchange Adapter (Binance)** | `src/kdexter/tcl/adapters/` + `app/exchanges/binance.py` | ✅ 존재 | CCXT 기반, testnet toggle |
| 6 | **E-02 Activation** | `app/core/executor_activation.py` | ✅ 존재 | 12개 검증 항목, activation_approval 필수 |
| 7 | **E-03 Micro Executor** | `app/core/micro_executor.py` | ✅ 존재 | 1회성 소비, dispatch guard |

### 1.2 안전 장치 확인

| # | 안전 장치 | 구현 위치 | 상태 | 비고 |
|---|-----------|-----------|------|------|
| 1 | **dry_run default=True** | orchestrator.py:322 | ✅ | `dry_run=task.context.get("dry_run", True)` |
| 2 | **binance_testnet default=True** | config.py:25 | ✅ | `binance_testnet: bool = True` |
| 3 | **LIVE gate** | commands.py:240 | ✅ | `_live_authorized=False` 기본, authorize_live() 필요 |
| 4 | **Idempotency** | commands.py:223-227 | ✅ | idempotency_key 기반 중복 실행 방지 |
| 5 | **RISK.CHECK** | commands.py:249-261 | ✅ | buy/sell 전 자동 리스크 체크 |
| 6 | **Activation 1회 소비** | micro_executor.py:43-86 | ✅ | _consumed_activations + evidence store |
| 7 | **Dispatch window** | micro_executor.py:35 | ✅ | 60초 기본, 만료 시 거부 |
| 8 | **Security LOCKDOWN** | 전 pipeline | ✅ | LOCKDOWN 시 실행 차단 |
| 9 | **kill_switch** | dashboard.py:3113-3126 | ✅ | LOCKDOWN/QUARANTINED → kill_switch=True |
| 10 | **NO_EXECUTION scope 기본** | executor_activation.py:53 | ✅ | execution_scope="NO_EXECUTION" 기본 |

### 1.3 Dashboard 상태 원인 분석

| Dashboard 표시 | 직접 원인 | 정상 여부 |
|----------------|-----------|-----------|
| **E-02: NOT_ACTIVATED** | `activation_approval=None`, `execution_scope="NO_EXECUTION"` | ✅ Mode 1 정상 — activation approval이 없으므로 차단됨 |
| **STATUS: UNKNOWN** | `ai_assist_source.py` status_word 초기값 "UNKNOWN", security_ctx 접근 실패 또는 조건 미충족 | ⬜ Mode 1 cold-start 특성 |
| **SYSTEM HEALTHY: X** | `system_healthy = state_val == "NORMAL"` — security_ctx가 NORMAL이 아니거나 접근 실패 | ⬜ 확인 필요 — security_ctx.current 값 |
| **TRADING AUTH: X** | `trading_authorized = system_healthy AND gate_decision == "OPEN"` — system_healthy가 False이면 X | ⬜ system_healthy 종속 |
| **freshness unknown** | 실시간 호가 미수집 (Mode 1에서 market feed = STALE) | ✅ Mode 1 정상 — live quote 없음 |

### 1.4 Mode 2 전환 시 정상화 예측

| 항목 | M2-1 (Live-Read) | M2-2 (Micro-Live) | M2-3 (Limited Live) |
|------|-------------------|--------------------|--------------------|
| TRADING AUTH | ⬜ system_healthy 종속 | ⬜ 동일 | ⬜ 동일 |
| SYSTEM HEALTHY | ✅ live credential → NORMAL 가능 | ✅ | ✅ |
| STATUS | ✅ HEALTHY/DEGRADED로 전환 예상 | ✅ | ✅ |
| freshness | ✅ live quote → 정상화 | ✅ | ✅ |
| E-02 Activation | ❌ NOT_ACTIVATED (dry_run) | ✅ activation_approval 부여 시 | ✅ |

---

## 2. 3단계 전환 계획

### M2-1: Live-Read Activation

**목적**: Live credential로 거래소 연결, 실시간 데이터 수신 확인. 주문 발생 0건.

| 항목 | 값 |
|------|-----|
| `binance_testnet` | **false** (live credential) |
| `dry_run` | **true** (주문 차단 유지) |
| `_live_authorized` | **false** (TCL LIVE gate 닫힘) |
| `execution_scope` | NO_EXECUTION |
| 실주문 가능 여부 | **불가** — 3중 차단 (dry_run + LIVE gate + NO_EXECUTION) |

#### 통과 기준

| # | 기준 | 판정 방법 | 필수 |
|---|------|-----------|------|
| 1 | 거래소 연결 성공 | dashboard 연결 상태 = connected | ✅ |
| 2 | 실시간 잔고/포지션 조회 | position_overview 정상 표시 | ✅ |
| 3 | freshness 정상화 | venue:binance → 시간 표시 (unknown 아님) | ✅ |
| 4 | SYSTEM HEALTHY = ✓ | dashboard Execution Readiness | ✅ |
| 5 | TRADING AUTH = 여전히 X | dry_run + NO_EXECUTION이므로 X 유지가 정상 | ✅ |
| 6 | Safety 7/7 유지 | 관찰 불변량 전부 True | ✅ |
| 7 | 실주문 0건 | 주문 이력 확인 | ✅ |
| 8 | 테스트 기준선 유지 | 3171/0/0 | ✅ |

#### 중단 조건

| 조건 | 행동 |
|------|------|
| 거래소 연결 실패 | 즉시 testnet으로 회귀 |
| 의도하지 않은 주문 발생 | **즉시 LOCKDOWN + testnet 회귀** |
| Safety invariant 위반 | 즉시 testnet 회귀 |
| API key 권한 오류 | credential 확인 후 재시도 (최대 3회) |

#### 필요 운영 파라미터

| 파라미터 | 변경 | 현재값 → 목표값 |
|----------|------|----------------|
| `BINANCE_TESTNET` | .env | `true` → `false` |
| `BINANCE_API_KEY` | .env | testnet key → **live key** |
| `BINANCE_API_SECRET` | .env | testnet secret → **live secret** |

---

### M2-2: Micro-Live

**목적**: 단일 거래소, 단일 심볼, 최소 금액, 정확히 1회 주문. 전체 lineage 검증.

| 항목 | 값 |
|------|-----|
| `binance_testnet` | **false** |
| `dry_run` | **false** (이 단계에서만 해제) |
| `_live_authorized` | **true** (TCL.authorize_live()) |
| `execution_scope` | SPECIFIC_SYMBOL_ONLY |
| `target_symbol` | A 지정 (예: BTC/USDT) |
| 주문 제한 | **1건, 최소 notional** |

#### 통과 기준

| # | 기준 | 판정 방법 | 필수 |
|---|------|-----------|------|
| 1 | M2-1 전체 통과 | M2-1 판정표 8/8 | ✅ |
| 2 | A 재승인 | out-of-band 승인 문서 | ✅ |
| 3 | 주문 1건 정상 체결 | 거래소 주문 이력 확인 | ✅ |
| 4 | AP→EP→SP→OX lineage 완전 | SubmitLedger + OrderExecutor + Evidence 확인 | ✅ |
| 5 | Evidence bundle 생성 | PRE + POST evidence 쌍 확인 | ✅ |
| 6 | 주문 수 = 정확히 1 | 추가 주문 0건 확인 | ✅ |
| 7 | 실현 손익 기록 | position/trade 테이블 갱신 확인 | ✅ |
| 8 | 자동 재시도 없음 | 주문 후 추가 실행 시도 0건 | ✅ |
| 9 | Safety invariant 유지 | 주문 실행 중에도 7/7 | ✅ |
| 10 | 즉시 Mode 1 회귀 가능 | dry_run=true 복원 확인 | ✅ |

#### 중단 조건

| 조건 | 행동 |
|------|------|
| 주문 1건 초과 발생 | **즉시 LOCKDOWN + dry_run=true + revoke_live()** |
| 예상 외 심볼 주문 | **즉시 LOCKDOWN** |
| 체결 후 자동 재시도 발생 | 즉시 중단 |
| 일 손실 > 최소 notional의 50% | 즉시 중단 |
| Safety invariant 위반 | 즉시 Mode 1 회귀 |
| Evidence 누락 | 즉시 중단 + 조사 |

#### 필요 운영 파라미터

| 파라미터 | 설명 |
|----------|------|
| `target_symbol` | A 지정 (예: BTC/USDT) |
| `max_notional` | 최소 거래 가능 금액 (거래소 minimum) |
| `max_order_count` | **1** |
| `daily_loss_limit` | max_notional × 0.5 |
| `execution_scope` | SPECIFIC_SYMBOL_ONLY |

---

### M2-3: Limited Live

**목적**: 제한된 규모로 연속 운영. 규모/주문수/손실 상한 적용.

| 항목 | 값 |
|------|-----|
| `binance_testnet` | **false** |
| `dry_run` | **false** |
| `_live_authorized` | **true** |
| `execution_scope` | MICRO_LIVE_ONLY |
| 주문 제한 | 일 N건, 총 금액 상한 |

#### 통과 기준

| # | 기준 | 판정 방법 | 필수 |
|---|------|-----------|------|
| 1 | M2-2 전체 통과 | M2-2 판정표 10/10 | ✅ |
| 2 | A 재승인 | out-of-band 승인 문서 | ✅ |
| 3 | 7일 연속 운영 | 일간 체크 7/7 PASS | ✅ |
| 4 | 일 주문수 상한 미초과 | 매일 확인 | ✅ |
| 5 | 일 손실 한도 미초과 | 매일 확인 | ✅ |
| 6 | 전체 lineage 100% | orphan evidence 0건 | ✅ |
| 7 | 즉시 중단 테스트 | 수동 kill_switch 작동 확인 | ✅ |
| 8 | Safety 7/7 유지 | 7일간 전부 True | ✅ |

#### 중단 조건

| 조건 | 행동 |
|------|------|
| 일 손실 한도 초과 | 당일 실행 즉시 중단, 익일 A 판정 |
| 일 주문수 상한 초과 | 즉시 중단 |
| 연속 3건 손실 | 즉시 중단 + A 판정 |
| 누적 손실 > 총 상한 | **즉시 Mode 1 회귀** |
| Safety invariant 위반 | **즉시 Mode 1 회귀** |
| 이상 거래 패턴 | 즉시 중단 + 조사 |

#### 필요 운영 파라미터

| 파라미터 | 설명 | 권장 초기값 |
|----------|------|-------------|
| `daily_order_limit` | 일 최대 주문 수 | 5 |
| `daily_loss_limit` | 일 최대 손실 (USDT) | A 지정 |
| `total_loss_cap` | 누적 최대 손실 | A 지정 |
| `max_position_size` | 최대 포지션 규모 | A 지정 |
| `allowed_symbols` | 허용 심볼 목록 | A 지정 |
| `operating_hours` | 운영 시간대 | A 지정 또는 24h |

---

## 3. 단계 간 승격 규칙

```
Mode 1 (현재)
    │
    ▼  A 승인 + M2-1 통과 기준 8/8
M2-1: Live-Read
    │
    ▼  A 재승인 + M2-2 통과 기준 10/10
M2-2: Micro-Live (1회 주문)
    │
    ▼  A 재승인 + M2-3 통과 기준 8/8
M2-3: Limited Live
    │
    ▼  A 재승인 + 장기 운영 검증
Production
```

**자동 승격 없음. 모든 단계 전환은 A의 명시적 재승인 필요.**

**회귀는 즉시 가능. 승격만 승인 필요.**

---

## 4. A 최종 승인 문안 초안

### M2-1 승인 문안

```
A 판정:
- Mode 2 Phase 1 (M2-1: Live-Read Activation)을 승인한다.
- BINANCE_TESTNET=false 전환을 허가한다.
- dry_run=true, _live_authorized=false, execution_scope=NO_EXECUTION을 유지한다.
- 실주문은 0건이어야 한다.
- M2-1 통과 기준 8/8 충족 시 M2-2 검토를 개시할 수 있다.
- 이상 발생 시 즉시 testnet으로 회귀한다.
```

### M2-2 승인 문안

```
A 판정:
- Mode 2 Phase 2 (M2-2: Micro-Live)를 승인한다.
- dry_run=false, authorize_live()를 허가한다.
- target_symbol: [A 지정]
- max_notional: [A 지정]
- 주문 수: 정확히 1건
- 자동 재시도 금지
- 체결 후 즉시 dry_run=true로 복원한다.
- AP→EP→SP→OX lineage 완전 확인 후 M2-3 검토를 개시할 수 있다.
```

### M2-3 승인 문안

```
A 판정:
- Mode 2 Phase 3 (M2-3: Limited Live)를 승인한다.
- daily_order_limit: [A 지정]
- daily_loss_limit: [A 지정]
- total_loss_cap: [A 지정]
- allowed_symbols: [A 지정]
- 7일 연속 운영 후 Production 검토를 개시할 수 있다.
```

---

## 5. 사전 판정 결론

### 전환 가능성: **조건부 가능** ✅⚠️

| 항목 | 판정 |
|------|------|
| 실행 경로 구현 | ✅ 전 경로 존재 (AP→EP→SP→OX) |
| 안전 장치 | ✅ 10개 장치 모두 구현 |
| 3중 차단 (M2-1) | ✅ dry_run + LIVE gate + NO_EXECUTION |
| idempotency | ✅ idempotency_key 기반 |
| evidence/audit | ✅ append-only EvidenceStore |
| 단계별 분리 | ✅ M2-1/2/3 명확 분리 |

### 잔존 확인 사항

| # | 사항 | 확인 시점 |
|---|------|-----------|
| 1 | Live Binance API key/secret 준비 여부 | M2-1 직전 |
| 2 | Live Binance API key의 권한 범위 (read-only vs trade) | M2-1 직전 |
| 3 | SYSTEM HEALTHY = X의 정확한 원인 (security_ctx 값) | M2-1 실행 중 |
| 4 | M2-2 target_symbol 및 max_notional | A 지정 필요 |
| 5 | M2-3 daily_loss_limit, total_loss_cap | A 지정 필요 |

### A에게 드리는 최종 질문

**M2-1(Live-Read) 승인 여부를 판정해 주십시오.**
현재 시스템은 M2-1의 전제 조건을 충족하고 있으며, 3중 차단이 유지되므로 주문 발생 위험은 0입니다.
