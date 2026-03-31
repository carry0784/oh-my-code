# M2-2 Repeat Readiness Card

Effective: 2026-03-31
Status: **HOLD**
Author: B (Implementer)
Reviewer: A (Designer)

---

> **목적**: 재현성 검증 | **현재 상태**: HOLD | **GO 조건 충족**: 0/6 | **가장 큰 blocker**: Read-only / No execution authority

---

## 1. 왜 반복하는가

**목적: 재현성 검증 (A 결정 2026-03-31)**

M2-2 첫 micro-live (order 59922222570, FILLED, 9.94 USDT)가 **재현 가능한 결과**인지 확인한다.

| 검증 질문 | 기대 결과 |
|-----------|-----------|
| 동일 파이프라인에서 동일 결과가 나오는가? | FILLED |
| 15 guard가 동일하게 통과하는가? | 15/15 PASS |
| Constitution 10/10이 재현되는가? | 10/10 PASS |
| Lineage가 동일 구조로 생성되는가? | AP→EP→SP→OX→exchange |

**운영편차 검증은 별도 후속 후보로 분리** — 이 카드의 범위가 아님.

---

## 2. Baseline과 무엇이 같아야 하는가

### 반드시 동일해야 하는 항목

| 항목 | 기준선 값 | 변경 허용 |
|------|-----------|-----------|
| target_symbol | BTC/USDT | 불가 |
| max_notional | ~10 USDT | 불가 |
| exchange | binance (spot) | 불가 |
| side | buy (market) | 불가 |
| 주문 수 | 1건 | 불가 |
| 종목 수 | 1종목 | 불가 |
| 시간 윈도우 | 60초 | 불가 |
| Guard chain | 4+5+6 = 15 | 완화 금지 |
| 실행 경로 | ActionLedger→ExecutionLedger→SubmitLedger→OrderExecutor | 변경 금지 |
| 실행 스크립트 | scripts/m2_2_micro_live.py | 동일 |

### 변동 허용 항목 (환경 의존)

| 항목 | 기준선 값 | 변동 예상 |
|------|-----------|-----------|
| BTC/USDT 가격 | ~66,292 USDT | 시장 변동 |
| 체결 수량 | 0.00015 BTC | 가격 연동 조정 |
| Binance order ID | 59922222570 | 매 실행 신규 |
| Lineage ID | AP-/EP-/SP-/OX- 접두사 | 매 실행 신규 |
| 체결 시각 | 2026-03-31 | GO 시점 |

---

## 3. 어떤 조건에서만 다시 실행하는가

### GO 전 필수 조건 (6항목, 현재 0/6)

| # | 조건 | 현재 상태 | 필요 행위 |
|---|------|-----------|-----------|
| 1 | 새 REVIEW 패키지 정식 확정 | HOLD | A 승인 |
| 2 | Baseline diff 체크 완료 | 초안 완료 | GO 시 재확인 |
| 3 | 목적 확정 (재현성 검증) | ✅ A 결정 | — |
| 4 | 새 Execution Authorization | 미발행 | A 발행 |
| 5 | Read-only → 실행 창 일시 전환 | 미개시 | A 승인 |
| 6 | 사전 점검 7항목 PASS | 대기 | 실행 직전 |

### 사전 점검 7항목 (GO 후 실행 직전)

| # | 항목 |
|---|------|
| 1 | BINANCE_TESTNET .env = true 확인 |
| 2 | Runtime override 준비 |
| 3 | Binance API key spot trading 권한 |
| 4 | USDT 잔고 ≥ 10 USDT |
| 5 | 서버 미기동 확인 (포트 8000 free) |
| 6 | PostgreSQL 기동 확인 |
| 7 | 기존 stale 프로세스 없음 |

### 실행 후 즉시

1. BINANCE_TESTNET=true 복원
2. dry_run=True 기본값 확인
3. Post-Run Review 제출 (기준선 대비 diff)
4. Mode 1 steady-state 즉시 복귀

---

## 현재 실행 금지

이 Readiness Card는 준비 문서이며, 실행 승인 문서가 아니다.
새 REVIEW + 새 Execution Authorization 없이는 GO 불가.
