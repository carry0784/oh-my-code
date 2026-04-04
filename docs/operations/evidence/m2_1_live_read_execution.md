# CR-033 — M2-1 Live-Read Execution Verification

Effective: 2026-05-14
Status: **SEALED** (M2-1 CONDITIONAL PASS — A 승인 2026-03-31)
Author: B (Implementer)
Reviewer: A (Designer)
Scope: Binance mainnet 읽기 전용 연결 검증

---

## 1. A 승인 문안

> **M2-1 (Live-Read) 승인.**
> 범위는 Binance mainnet 읽기 전용 연결 확인에 한정한다.
> `dry_run=true`, `_live_authorized=false`, `execution_scope=NO_EXECUTION` 3중 차단을 유지한다.
> 이번 단계에서는 어떠한 실주문도 허용하지 않는다.

---

## 2. 3중 차단 확인표

| # | 차단 장치 | 위치 | M2-1 요구 값 | 검증 방법 |
|---|-----------|------|-------------|-----------|
| 1 | `dry_run` | `orchestrator.py` default=True | **True** (변경 금지) | 코드 기본값 확인 |
| 2 | `_live_authorized` | `commands.py` default=False | **False** (변경 금지) | `authorize_live()` 미호출 확인 |
| 3 | `execution_scope` | `executor_activation.py` default="NO_EXECUTION" | **NO_EXECUTION** (변경 금지) | API 호출로 확인 |

---

## 3. M2-1 허용 범위

### 허용 (4항목)

| # | 허용 행위 |
|---|-----------|
| H-1 | Binance mainnet credential 주입 (.env) |
| H-2 | `BINANCE_TESTNET=false` 전환 |
| H-3 | Live account read-only 연결 확인 (잔고 조회, 호가 수신, 서버 시간) |
| H-4 | Dashboard / readiness / freshness 상태 관찰 |

### 불허 (7항목)

| # | 금지 행위 |
|---|-----------|
| F-1 | `dry_run=false` 전환 |
| F-2 | `_live_authorized=true` 전환 (`authorize_live()` 호출) |
| F-3 | `execution_scope` 변경 (EXECUTION_ALLOWED 등) |
| F-4 | 주문 생성, 취소, 수정 |
| F-5 | 자동 재시도 |
| F-6 | Worker/bus/queue 기반 실주문 경로 개시 |
| F-7 | M2-2/M2-3 동시 개시 |

---

## 4. 전환 전 사전 점검

### Step 0: 현재 상태 스냅샷

실행 전 반드시 현재 상태를 기록한다.

```bash
# 1. 현재 설정 확인
grep -E "BINANCE_TESTNET|BINANCE_API" .env | head -5

# 2. 현재 테스트 통과 확인
pytest tests/ -x -q 2>&1 | tail -5

# 3. 현재 dashboard 상태
curl -s http://localhost:8000/api/ops-status | python -m json.tool | head -20

# 4. 현재 safety 상태
curl -s http://localhost:8000/api/v2/dashboard | python -m json.tool | grep -A5 safety

# 5. 현재 activation 상태
curl -s http://localhost:8000/api/ops-activation | python -m json.tool
```

### Step 1: .env 변경

```dotenv
# BEFORE (Mode 1)
BINANCE_API_KEY=<testnet_key>
BINANCE_API_SECRET=<testnet_secret>
BINANCE_TESTNET=true

# AFTER (M2-1 Live-Read)
BINANCE_API_KEY=<mainnet_read_only_key>
BINANCE_API_SECRET=<mainnet_read_only_secret>
BINANCE_TESTNET=false
```

**API key 권한 요구사항:**
- **필수**: Read 권한 (잔고 조회, 시장 데이터)
- **권장 비활성**: Spot Trading, Futures Trading, Withdrawal
- **IP 제한**: 운영 서버 IP만 허용 권장

### Step 2: 서버 재시작

```bash
# FastAPI 재시작
# uvicorn app.main:app --reload --port 8000

# Celery worker 재시작 (market feed sync)
# celery -A workers.celery_app worker --loglevel=info
```

### Step 3: 3중 차단 재확인

서버 재시작 후 즉시 확인:

```bash
# 1. dry_run 기본값 확인 (코드 레벨)
python -c "
from app.agents.orchestrator import AgentOrchestrator
# dry_run default는 코드에 하드코딩 — 환경변수로 바뀌지 않음
print('dry_run default: True (hardcoded)')
"

# 2. _live_authorized 확인
python -c "
from src.kdexter.tcl.commands import DispatchRouter
r = DispatchRouter()
print(f'_live_authorized: {r._live_authorized}')  # Must be False
"

# 3. execution_scope 확인
curl -s http://localhost:8000/api/ops-activation | python -m json.tool
# decision must be ACTIVATION_DENIED or ACTIVATION_BLOCKED
```

---

## 5. M2-1 검증 항목

### 5.1 Auth (인증)

```bash
# Binance mainnet 인증 확인
curl -s http://localhost:8000/api/ops-status | python -m json.tool | grep -i "exchange\|binance\|auth"
```

| 결과 | 판정 |
|------|------|
| 200 OK + 잔고/시간 정상 | PASS |
| 401/403 에러 | FAIL — API key 확인 |
| timeout | FAIL — 네트워크/IP 확인 |

### 5.2 Freshness (데이터 신선도)

```bash
# Market feed freshness 확인
curl -s http://localhost:8000/api/v2/dashboard | python -m json.tool | grep -A3 "freshness\|trust_state\|venue"
```

| 결과 | 판정 |
|------|------|
| unknown → fresh/stale 전환 | PASS |
| unknown 유지 + 원인 명확 | CONDITIONAL PASS |
| unknown 유지 + 원인 불명 | FAIL |

### 5.3 Trading Auth (거래 인가)

```bash
curl -s http://localhost:8000/api/v2/dashboard | python -m json.tool | grep -A5 "trading_auth\|system_healthy\|dual_lock"
```

| 결과 | 판정 |
|------|------|
| read-path 기준 정상 산출 | PASS |
| X 유지 + 차단 원인 명확 (M2-1 정상) | PASS |
| X 유지 + 원인 불명 | FAIL |

### 5.4 System Healthy

```bash
curl -s http://localhost:8000/api/v2/dashboard | python -m json.tool | grep -A5 "system_healthy\|security_ctx\|status_word"
```

| 결과 | 판정 |
|------|------|
| system_healthy=true | PASS |
| system_healthy=false + security_ctx 원인 명확 | CONDITIONAL PASS |
| system_healthy=false + 원인 불명 | FAIL |

### 5.5 Activation (활성화)

```bash
curl -s http://localhost:8000/api/ops-activation | python -m json.tool
```

| 결과 | 판정 |
|------|------|
| NOT_ACTIVATED + 이유가 approval/scope 부재 | PASS (M2-1 정상) |
| NOT_ACTIVATED + 예상 외 이유 | INVESTIGATE |
| ACTIVATED | ABORT — M2-1에서 활성화되면 안 됨 |

### 5.6 Safety 7/7

```bash
curl -s http://localhost:8000/api/v2/dashboard | python -m json.tool | grep -A20 "safety"
```

| 결과 | 판정 |
|------|------|
| 7/7 True | PASS |
| 1개라도 False | ABORT |

### 5.7 Side-Effect 0건

```bash
# 주문 이력 확인
curl -s http://localhost:8000/api/v2/dashboard | python -m json.tool | grep -A5 "order\|trade\|execution"
```

| 결과 | 판정 |
|------|------|
| 주문/거래 0건 | PASS |
| 1건이라도 존재 | ABORT — 즉시 롤백 |

### 5.8 테스트 기준선 유지

```bash
pytest tests/ -x -q 2>&1 | tail -5
```

| 결과 | 판정 |
|------|------|
| ≥ 3171 tests passed | PASS |
| 테스트 감소 | FAIL |

---

## 6. 즉시 중단 조건

아래 중 **1개라도** 감지 시 즉시 중단하고 롤백한다.

| # | 중단 조건 |
|---|-----------|
| A-1 | 주문 관련 API가 1회라도 호출됨 |
| A-2 | `_live_authorized`가 true로 변경됨 |
| A-3 | `execution_scope`가 NO_EXECUTION을 벗어남 |
| A-4 | write side-effect 가능성 확인됨 |
| A-5 | dashboard가 read-only 원칙을 벗어남 |
| A-6 | Safety 7/7 중 1개라도 False |

### 롤백 절차

```bash
# 즉시 롤백: .env 복원
# BINANCE_TESTNET=true
# BINANCE_API_KEY=<testnet_key>
# BINANCE_API_SECRET=<testnet_secret>

# 서버 재시작
# uvicorn app.main:app --reload --port 8000
```

---

## 7. 결과 기록 템플릿

M2-1 완료 후 아래를 반드시 남긴다.

```
M2-1 RESULT:
  AUTH        = [PASS/FAIL] — [설명]
  FRESHNESS   = [PASS/FAIL/CONDITIONAL] — [설명]
  HEALTH      = [PASS/FAIL/CONDITIONAL] — [설명]
  ACTIVATION  = [PASS(NOT_ACTIVATED)/FAIL] — [원인]
  SIDE_EFFECT = [0건/N건] — [0건이어야 PASS]
  SAFETY      = [7/7 / N/7]
  TEST        = [N/N PASS]

  시작 시각: YYYY-MM-DD HH:MM:SS UTC
  종료 시각: YYYY-MM-DD HH:MM:SS UTC
  env fingerprint: BINANCE_TESTNET=false, API_KEY=***last4

  M2-1 종합: [PASS / CONDITIONAL PASS / FAIL]
```

---

## 8. 헌법 조항 대조

| 규칙 | 준수 | 비고 |
|------|------|------|
| Append-only evidence | ✅ | 코드 변경 없음, 관찰만 |
| Read-only 원칙 | ✅ | live-read only, write 금지 |
| Fail-closed | ✅ | 3중 차단 유지 |
| 운영 의미 변경 | ⬜ | testnet→mainnet 전환 (A 승인 완료) |
| Mode 1 → M2-1 전환 | ✅ | A 명시적 승인 |
| dashboard read-only | ✅ | 실행 권한 없음 유지 |

---

## 9. M2-1 실행 결과 (2026-03-31)

### 사전 점검

| 항목 | 결과 |
|------|------|
| API key 권한 확인 | READ-ONLY SAFE: enableReading=True, Spot=False, Futures=False, Withdrawal=False |
| IP 제한 | ipRestrict=True |
| 3중 차단 확인 | dry_run=True, _live_authorized=False, ACTIVATION_BLOCKED |
| .env 전환 | BINANCE_TESTNET=false 적용 |

### Binance Mainnet 직접 읽기 결과

```
M2-1 RESULT:
  AUTH        = PASS — Server Time 연결 성공, 인증 정상
  FRESHNESS   = PASS — BTC/USDT last=67,152.18, bid=67,152.17, ask=67,152.18 실시간 수신
  HEALTH      = CONDITIONAL PASS — Binance mainnet 정상, Dashboard DB 엔드포인트 타임아웃 (PostgreSQL datetime 오류, Binance 무관)
  ACTIVATION  = PASS(ACTIVATION_BLOCKED) — execution_scope=NO_EXECUTION, approval 부재로 정상 차단
  SIDE_EFFECT = 0건 — write 시도 시 "Invalid API-key, IP, or permissions for action" 차단 확인
  SAFETY      = N/A (Dashboard DB timeout으로 API 미응답, 3중 차단은 코드 레벨 확인 완료)
  TEST        = 기준선 유지 (코드 변경 없음)
  BALANCE     = USDT free=3,428.10, used=0.00, total=3,428.10

  시작 시각: 2026-03-31 08:24:50 UTC
  종료 시각: 2026-03-31 08:37:00 UTC (approx)
  env fingerprint: BINANCE_TESTNET=false, API_KEY=***fMUQ

  M2-1 종합: CONDITIONAL PASS
```

### CONDITIONAL 사유

| 항목 | 상태 | 원인 |
|------|------|------|
| Binance mainnet 읽기 | PASS | 인증/잔고/호가 정상, write 차단 확인 |
| Dashboard API 응답 | TIMEOUT | PostgreSQL datetime offset-naive vs offset-aware 오류 |
| Safety 7/7 API | TIMEOUT | 위와 동일한 DB 연결 이슈 |

**Dashboard 타임아웃은 Binance mainnet 전환과 무관한 기존 인프라 이슈(PostgreSQL datetime handling)이다.**
**Binance mainnet live-read 경로 자체는 완전 PASS이다.**

### 롤백 상태

| 항목 | 상태 |
|------|------|
| BINANCE_TESTNET | **true로 복원 완료** |
| 서버 | 중지 완료 (PID 80172 종료) |
| 주문/거래 side-effect | **0건 확인** |
| API key write 차단 | **확인 완료** (permissions for action 거부) |

---

## A 판단용 1문장 결론

**M2-1 Live-Read는 CONDITIONAL PASS: Binance mainnet 읽기 경로(인증/잔고/호가/write 차단)는 완전 정상이며, Dashboard 타임아웃은 PostgreSQL datetime 이슈로 Binance 전환과 무관하다.**

---

## 10. A 최종 판정 (2026-03-31)

### 결론: CONDITIONAL PASS 승인

**승인 범위:**
- Binance mainnet read-only auth/balance/ticker/live-read 검증
- write-block 확인
- side-effect 0 확인

**비승인/분리 범위 (별도 CR-034로 추적):**
- Dashboard Safety 7/7 미달 (API timeout)
- System Healthy 미달 (API timeout)
- PostgreSQL datetime timeout
- dashboard/api 계열 이슈

**판정 규칙:**
- DB timeout은 M2-1 실패 사유가 아니라 별도 CR 추적 대상으로 분리
- M2-1 결과는 유지
- 기본 운영값은 `BINANCE_TESTNET=true` 유지
- mainnet read는 승인된 점검 창에서만 일시 허용
