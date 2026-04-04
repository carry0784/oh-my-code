# reShadow v2 Run -- Day 3 일일 점검표

실행 시각: 2026-04-01T05:41:04Z (14:41 KST)
Market Regime 라벨: **Inactive Market Regime**
기준선: `0a9fff1` (CR-045 + island_model fix)
CR: CR-045 (CG-2B Exercisability Recovery Package)

---

## Config Fingerprint

```
bars=500, lookback=30, islands=5, pop=10, gen=10
strategy_types=[SMA, RSI], baseline=6beb906, cr=CR-045
```

---

## 체크리스트 요약

| 구분 | 항목 | Day 3 |
|------|------|-------|
| A | CCXT 500 bars | [x] YES |
| B | Evolution OK, gen=10 | [x] OK |
| B | registry_size | **0** |
| B | best_fitness | 0.0 |
| B | candidate_state | **BELOW_THRESHOLD** |
| C | Portfolio | SKIP (registry < 2) |
| D | Orchestrator OK, crash=0 | [x] OK |
| D | governance_decisions | **0** |
| D | block_rate | **N/A** (0 candidates) |
| D | is_healthy | **false** |
| E | Reconciliation 4/4 | [x] PASS |

---

## 전략별 요약

| 전략 | 게놈 수 | Best Fitness | Registry |
|------|--------|-------------|----------|
| **SMA** | 34 | 0.0 | 0 |
| **RSI** | 41 | 0.0 | 0 |

```json
"candidate_generation_by_strategy": {"SMA": 34, "RSI": 41}
"fitness_by_strategy":              {"SMA": 0.0, "RSI": 0.0}
"registry_entries_by_strategy":     {"SMA": 0, "RSI": 0}
```

### 3일간 strategy_type gene 추적

| Day | SMA | RSI | 우세 |
|-----|-----|-----|------|
| 1 | 31 | 44 | RSI (59%) |
| 2 | 44 | 31 | SMA (59%) |
| 3 | 34 | 41 | RSI (55%) |

진화가 매회 strategy gene을 교대 탐색하는 패턴 확인. 특정 전략에 수렴하지 않음 = 두 전략 모두 fitness=0.0이라 선택 압력 없음.

---

## CG-2 분리 판정

### CG-2A: 운영 회로 안정성 -- Day 3 PASS

| 항목 | Day 3 |
|------|-------|
| dry_run | True (HARDCODED) |
| crash | 0 |
| reconciliation | 4/4 PASS |
| CCXT data | 500 bars |
| Evolution loop | 10gen x 5islands OK |
| Orchestrator cycle | OK |

### CG-2B: 전략/거버넌스 -- Day 3 WATCH

| 항목 | Day 3 |
|------|-------|
| registry_size | 0 |
| governance_decisions | 0 |
| candidate_state | BELOW_THRESHOLD |
| cg2b_opening_signal | **no** |

---

## Day 판정

```
Day 3 Assessment: [ ] PASS  [x] WATCH  [ ] FAIL
overall_status = CG-2A_PASS__CG-2B_WATCH
Recommended Outcome = CONTINUE
```

---

## 7-Day Acceptance Board (v2)

| Day | Date | Registry | Block% | Warnings | Crashes | SMA/RSI | cg2a | cg2b | Assessment |
|-----|------|----------|--------|----------|---------|---------|------|------|------------|
| 1 | 04-01 | 0 | N/A | 1 | 0 | 31/44 | PASS | WATCH | WATCH |
| 2 | 04-01 | 0 | N/A | 1 | 0 | 44/31 | PASS | WATCH | WATCH |
| 3 | 04-01 | 0 | N/A | 1 | 0 | 34/41 | PASS | WATCH | WATCH |
| 4 | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| 5 | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| 6 | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| 7 | -- | -- | -- | -- | -- | -- | -- | -- | -- |

---

## JSON-체크리스트 교차 검증: 14/14 일치
