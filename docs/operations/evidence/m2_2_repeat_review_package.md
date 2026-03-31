# M2-2 Repeat — Review Package

Effective: 2026-03-31
Status: **HOLD — A 판정 2026-03-31**
Author: B (Implementer)
Reviewer: A (Designer)
Scope: M2-2 동일 파라미터 반복 실행, 재현성 검증
Related: M2-2 Baseline Card (SEALED), baseline-m2-2-first-microlive-sealed tag

---

> **현재 실행 금지.** Mode 1 read-only 가드 활성 상태. 새 Execution Authorization 없이는 GO 불가.

---

## (1) 해석 및 요약

### A 판정: HOLD (2026-03-31)

M2-2 Repeat는 기준선과 동일 파라미터 재실행으로, NO-GO가 아닌 **HOLD** 상태다.
시스템이 정상적으로 read-only 상태를 유지하고 있으며, 이 상태 자체가 HOLD의 근거다.

### HOLD 사유 — Dashboard /ops-safety-summary 기준

| 항목 | 현재값 | 의미 |
|------|--------|------|
| preflight | `NOT_READY` | 실행 준비 미충족 |
| gate | `CLOSED` | 실행 경계 닫힘 |
| approval | `REJECTED` | 승인 상태 아님 |
| all_clear | `false` | 즉시 진행 불가 |
| safety_note | `Read-only. No execution authority.` | 실행 권한 없음 |
| lockdown | `false` | 봉쇄는 아님, 권한도 없음 |
| policy | `DRIFT` | 실행 승인 상태와 다름 |

### 판정 의미

- **NO-GO는 아님** — Repeat 자체가 부적절하다는 판정이 아님
- **GO도 아님** — 현재 권한/가드 상태가 실행 승인 상태가 아님
- **HOLD** — 새 REVIEW + 새 Execution Authorization 절차 전까지 유지

---

## (2) 장점 / 단점

### 장점

- 가드가 정상 작동 중 — Mode 1 설계대로 닫혀 있음
- Dashboard가 실행 권한 부재를 정확히 표시
- 망가져서 못 하는 상태가 아니라, **통제상 안 하는 상태**
- HOLD 초안이 준비되어 있으므로, GO 조건 충족 시 즉시 전환 가능

### 단점

- 초안만으로는 GO 불가 — 별도 승인 절차 필요
- DRIFT 상태에서 Repeat를 밀어붙이면 baseline 거버넌스를 스스로 깨는 결과

---

## (3) 이유 / 근거

### Repeat의 목적 정의

M2-2 Repeat는 두 가지 검증 중 하나를 목적으로 한다:

| 목적 | 설명 | 검증 대상 |
|------|------|-----------|
| **재현성 검증** | 동일 조건에서 동일 결과가 나오는지 | 파이프라인 결정론성 |
| **운영 편차 검증** | 시간 경과 후 환경 변화에도 정상인지 | 환경 안정성 |

→ A가 GO 시점에 어느 목적인지 명시 필요.

### Baseline Diff Checklist

#### 코드 차이

| 항목 | 기준선 (tag: baseline-m2-2-first-microlive-sealed) | 현재 | 차이 |
|------|----------------------------------------------|------|------|
| exchanges/binance.py | CR-036+037 적용 | 동일 | 없음 |
| app/services/order_executor.py | CR-036 적용 | 동일 | 없음 |
| 15 guard chain | 4+5+6 = 15 | 동일 | 없음 |
| app/core/database.py | CR-035 pool defense | 동일 | 없음 |
| app/main.py | CR-035 shutdown dispose | 동일 | 없음 |

#### 실행 경로 차이

동일 경로:
```
ActionLedger(4) → ExecutionLedger(5) → SubmitLedger(6) → OrderExecutor(dry_run=False)
```

#### 승인 범위 차이

기준선 승인 범위와 동일. 확대 없음.

#### 환경 차이 (GO 시점 확인 필요)

| 항목 | 기준선 (2026-03-31) | GO 시점 | 차이 |
|------|---------------------|---------|------|
| BTC/USDT 가격 | ~66,292 USDT | TBD | 변동 가능 |
| 최소 주문 단위 | 0.00015 BTC | TBD | 확인 필요 |
| Binance API 상태 | 정상 | TBD | 확인 필요 |
| USDT 잔고 | ≥ 10 USDT | TBD | 확인 필요 |

---

## (4) 실현·구현 대책

### 실행 파라미터 (기준선과 동일)

| 항목 | 값 | 기준선 대비 |
|------|-----|-----------|
| target_symbol | BTC/USDT | 동일 |
| max_notional | ~10 USDT | 동일 |
| exchange | binance | 동일 |
| side | buy | 동일 |
| order_type | market | 동일 |
| 주문 수 | 1건 | 동일 |
| 종목 수 | 1종목 | 동일 |
| 시간 윈도우 | 60초 | 동일 |
| dry_run | false | 동일 |

### GO 전 필요 조건

| # | 조건 | 상태 |
|---|------|------|
| 1 | 새 REVIEW 패키지 정식 확정 (이 문서) | HOLD |
| 2 | Baseline 대비 diff 체크 완료 | 초안 완료, GO 시 재확인 |
| 3 | 반복 실행 목적 명확화 (재현성/운영편차) | A 결정 대기 |
| 4 | 새 Execution Authorization | 미발행 |
| 5 | Read-only → 승인된 실행 창 일시 전환 절차 | 미개시 |
| 6 | 사전 점검 7항목 통과 | 대기 |

### 사전 점검 체크리스트 (GO 시 실행)

| # | 항목 | 상태 |
|---|------|------|
| 1 | BINANCE_TESTNET .env 확인 (true) | 대기 |
| 2 | Runtime override 준비 | 대기 |
| 3 | Binance API key spot trading 권한 | 대기 |
| 4 | USDT 잔고 ≥ 10 USDT | 대기 |
| 5 | 서버 미기동 확인 (포트 8000 free) | 대기 |
| 6 | PostgreSQL 기동 확인 | 대기 |
| 7 | 기존 stale 프로세스 없음 | 대기 |

---

## (5) 실행방법

### 성공 기준

| 항목 | 기준 |
|------|------|
| Order status | FILLED |
| Guard checks | 15/15 PASS |
| Constitution | 10/10 PASS |
| Side-effect | 정확히 1건, 최소금액 |
| Lineage | AP→EP→SP→OX→exchange 완전 |

### 실패 시 대응

| 상황 | 대응 |
|------|------|
| Guard 실패 | 즉시 중단, 원인 분석, 신규 CR |
| Exchange 거부 | 에러 기록, 파라미터 확인 |
| Timeout | 60초 윈도우 초과 시 자동 중단 |
| 신규 결함 | 실행 결과와 결함 분리, 신규 CR 발행 |

### 실행 후 제출 항목

1. Post-Run Review (기준선 대비 diff)
2. Evidence lineage 완전성
3. Side-effect 검증
4. Guard/abort 동작 기록
5. Constitution 대조 검수본

### 금지 사항

- 파라미터 변경 (금액/종목/시간/거래소)
- 가드 완화
- 다건/다종목 실행
- testnet/mainnet 기본값 재설정
- write/execution path 추가 개방

### 복귀 절차

실행 완료 즉시:
1. BINANCE_TESTNET=true 복원
2. dry_run=True 기본값 확인
3. 운영 상태 오염 없음 확인
4. Post-Run Review 제출

---

## (6) 더 좋은 아이디어

### M2-2 Repeat Readiness Card 제안

GO 시점에 이 문서 전체를 다시 읽는 대신, 3항목 Readiness Card로 좁히면 승인이 빨라진다:

| # | 항목 | 내용 |
|---|------|------|
| 1 | **왜 반복하는가** | 재현성 검증 / 운영 편차 검증 (A 선택) |
| 2 | **Baseline과 무엇이 다른가** | Diff Checklist 요약 (코드 0건, 환경 TBD) |
| 3 | **어떤 조건에서만 실행하는가** | GO 전 6조건 + 사전 점검 7항목 |

### 상태 전이 경로

```
현재: HOLD (read-only, no execution authority)
  ↓ A가 목적 결정 + Readiness Card 확인
  ↓ A가 새 Execution Authorization 발행
  ↓ 사전 점검 7/7 PASS
GO → 실행 → Post-Run Review → SEALED (또는 신규 CR)
  ↓ 즉시 복귀
Mode 1 steady-state 복원
```

---

## B의 HOLD 정리 완료 보고

M2-2 Repeat REVIEW 초안을 A 판정(HOLD)에 맞춰 정리 완료.
현재 실행 금지 상태 명시, GO 전 필요 조건 6항목 정리, Readiness Card 제안 포함.
A의 다음 지시를 대기합니다.
