# Shadow Run v2 — Day 0 Baseline Seal

Date: 2026-04-01
Baseline Commit: `6beb906`
CR: CR-045 (CG-2B Exercisability Recovery Package)
Previous Baseline: `d813758` (v1, 7-day shadow CG-2A Proven / CG-2B Not Proven)

---

## 기준선 변경 사유

7일 Shadow Run v1에서 CG-2A는 Proven, CG-2B는 Not Proven으로 종료됨.
근본 원인: `200바 x SMA only x min_trades=10` 조합의 거래 횟수 부족.
CR-045를 통해 exercisability를 복구하여 재Shadow에서 CG-2B 실증 기회를 확보함.

---

## v1 → v2 변경 요약

| 항목 | v1 (`d813758`) | v2 (`6beb906`) | 변경 근거 |
|------|---------------|---------------|-----------|
| n_islands | 3 | **5** | 기본값 복원 |
| population_per_island | 6 | **10** | 기본값 복원 |
| max_generations | 3 | **10** | 수렴 기회 확대 |
| lookback | 50 | **30** | 빠른 첫 신호 |
| OHLCV limit | 200 | **500** | 관측 창 확대 |
| 전략 유형 | SMA only | **SMA + RSI** | 전략 다양성 |
| strategy_type gene | 없음 | **추가** (0=SMA, 1=RSI) | 진화가 전략 선택 |

---

## 불변 항목 (v1 = v2)

| 항목 | 값 | 확인 |
|------|-----|------|
| dry_run | True (HARDCODED) | ✅ |
| PENDING_OPERATOR | 유지 | ✅ |
| min_trades | 10 | ✅ |
| fitness > 0 조건 | 유지 | ✅ |
| GovernanceGate | 불변 | ✅ |
| execution path | 불변 | ✅ |
| reconciliation 4항목 | 불변 | ✅ |
| health monitor | 불변 | ✅ |

---

## 테스트 결과

| 범위 | 결과 |
|------|------|
| CR-045 신규 (10건) | 10/10 PASS |
| 기존 회귀 (3478건) | 3478/3478 PASS |
| 총계 | **3488/3488 PASS** |
| Pre-existing flaky (2건) | CR-045 무관, 제외 |

---

## 봉인 대상 파일

| # | 파일 | 변경 유형 |
|---|------|-----------|
| 1 | `strategies/rsi_strategy.py` | NEW |
| 2 | `app/services/strategy_genome.py` | EDIT |
| 3 | `app/services/strategy_runner.py` | EDIT |
| 4 | `scripts/shadow_run_cycle.py` | EDIT |
| 5 | `tests/test_strategy_genome.py` | EDIT |
| 6 | `tests/test_strategy_runner.py` | EDIT |
| 7 | `docs/operations/evidence/cr045_shadow_redesign_package.md` | EDIT |

---

## Day 0 역할 선언

> Day 0는 구조 준비도(readiness)와 경로 실행 가능성(exercisability) preflight이다.
> Day 0는 live 성공 선별 gate가 아니며, Day 0의 결과는 재Shadow 7일 evidence의 일부로 계산하지 않는다.

---

## Day 0 Preflight 기준 (PRE-1~6)

| # | 항목 | 합격 기준 |
|---|------|-----------|
| PRE-1 | RSI 전략 클래스 로드 가능 | import 오류 없음 |
| PRE-2 | genome→strategy 분기 정상 | SMA/RSI 양쪽 BaseStrategy 인스턴스 |
| PRE-3 | 진화 루프 완주 가능 | status=OK |
| PRE-4 | 변경 파라미터 적용 확인 | 설정값 일치 |
| PRE-5 | 전체 테스트 통과 | 0 failures |
| PRE-6 | 금지 범위 미침범 | grep/AST 확인 |

---

## 재Shadow 추가 기록 필드 (A 지시)

다음 Shadow 일일 표에 아래 필드를 고정 추가:

- `trade_count_by_strategy`
- `candidate_generation_by_strategy`
- `fitness_by_strategy`
- `registry_entries_by_strategy`

---

## Day 0 결과 제출 형식

```
Readiness:       PASS / FAIL
Exercisability:  PASS / FAIL
Shadow Start Recommendation: GO / HOLD
```

---

## 서명

```
Shadow Run v2 — Day 0 Baseline Seal
Baseline Commit: 6beb906
CR: CR-045 (CG-2B Exercisability Recovery Package)
Previous Baseline: d813758
Safety: All CG-2A safeguards unchanged

Prepared by: B (Implementer)
Approval: A (Decision Authority) — CR-045 GO 2026-04-01
Date: 2026-04-01
```
