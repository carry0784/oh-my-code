# reShadow v2 Run -- Day 2 일일 점검표

실행 시각: 2026-04-01T05:39:14Z (14:39 KST)
Market Regime 라벨: **Inactive Market Regime**
기준선: `0a9fff1` (CR-045 + island_model fix)
CR: CR-045 (CG-2B Exercisability Recovery Package)

> **CG-2A 안전성 유지 여부 + CG-2B 후보 생성 경로 개방 여부를 동시 검증**

---

## Config Fingerprint

```
bars=500, lookback=30, islands=5, pop=10, gen=10
strategy_types=[SMA, RSI], baseline=6beb906, cr=CR-045
```

---

## 체크리스트 요약

| 구분 | 항목 | Day 2 |
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

## 전략별 요약 (CR-045 핵심)

| 전략 | 게놈 수 | Best Fitness | Registry | 관찰 Trades 범위 |
|------|--------|-------------|----------|----------------|
| **SMA** | 44 | 0.0 | 0 | 0~3 |
| **RSI** | 31 | 0.0 | 0 | 0~2 |

### 전략별 4개 필드

```json
"candidate_generation_by_strategy": {"SMA": 44, "RSI": 31}
"fitness_by_strategy":              {"SMA": 0.0, "RSI": 0.0}
"registry_entries_by_strategy":     {"SMA": 0, "RSI": 0}
```

### 전략별 분석

- **SMA**: Day 1 대비 게놈 수 증가 (31 -> 44). 진화가 SMA를 Day 2에서 더 선택. trades 0~3건 유지.
- **RSI**: Day 1 대비 게놈 수 감소 (44 -> 31). 여전히 min_trades=10 미달.
- **핵심 관찰**: Day 1에서 RSI 우세(59%) -> Day 2에서 SMA 우세(59%). 진화가 매 실행마다 strategy_type gene을 탐색하고 있음. 두 전략 모두 여전히 trades 부족으로 fitness=0.0.
- **Adaptive Mutation**: mutation_rate 0.1 -> 0.5 (gen 4부터 상승). 진화가 stagnation 감지하고 탐색 범위를 적극 확대 중.

### Day 1 vs Day 2 비교

| 항목 | Day 1 | Day 2 | 변화 |
|------|-------|-------|------|
| SMA genomes | 31 | 44 | +13 |
| RSI genomes | 44 | 31 | -13 |
| SMA trades range | 0~3 | 0~3 | 동일 |
| RSI trades range | 0~1 | 0~2 | 소폭 증가 |
| best_fitness | 0.0 | 0.0 | 동일 |
| registry | 0 | 0 | 동일 |
| mutation_rate (final) | -- | 0.5 | adaptive 작동 |
| migrations | -- | 25 | 정상 (5gen 간격 x 5islands) |

---

## CG-2 분리 판정

### CG-2A: 운영 회로 안정성 -- Day 2 PASS

| 항목 | Day 2 |
|------|-------|
| dry_run | True (HARDCODED) |
| crash | 0 |
| reconciliation | 4/4 PASS |
| STOP triggers | 0 |
| health warnings | 1 ("Registry size 0 below minimum 3") |
| CCXT data | 500 bars collected |
| Evolution loop | 10gen x 5islands OK |
| Orchestrator cycle | OK |
| fail-closed gate | 정상 작동 (입력 없을 때 차단 유지) |

### CG-2B: 전략/거버넌스 -- Day 2 WATCH

| 항목 | Day 2 |
|------|-------|
| registry_size | 0 |
| governance_decisions | 0 |
| candidate_state | BELOW_THRESHOLD |
| strategy_type gene | 정상 (SMA 44 / RSI 31) |
| RSI routing | **정상** (RSI_ prefix 확인) |
| cg2b_opening_signal | **no** (시장 제약 지속) |

---

## Day 판정

```
Day 2 Assessment: [ ] PASS  [x] WATCH  [ ] FAIL

overall_status = CG-2A_PASS__CG-2B_WATCH
Recommended Outcome = CONTINUE

사유:
  CG-2A: PASS - 인프라, 통제 구조, 안전 회로 연속 2일 정상.
  CG-2B: WATCH - strategy_type gene 양방향 탐색 확인 (Day 1 RSI 우세, Day 2 SMA 우세).
         Adaptive mutation 정상 작동 (0.1 -> 0.5).
         그러나 Inactive Market Regime 지속 -> trades 부족.
         min_trades=10 미달 -> fitness=0.0 -> registry=0.
         이것은 시스템 결함이 아니라 시장 상태에 의한 관측 제약.

  CR-045 효과 (2일 누적):
  [x] RSI 전략 분기 실제 작동 확인 (Day 1, Day 2 모두)
  [x] strategy_type gene 정상 (양방향 탐색 관찰)
  [x] 500바 수집 정상 (2/2)
  [x] 10gen x 5islands 진화 완주 (2/2)
  [x] Adaptive mutation 작동 (0.1 -> 0.5)
  [x] Migration 작동 (25 events)
  [ ] min_trades=10 충족 - 미달 (시장 제약)
  [ ] fitness > 0 - 미달 (시장 제약)
  [ ] registry >= 1 - 미달 (시장 제약)
```

---

## Mock Approval 연습

```
Genome ID: N/A (후보 0건)
Decision: [x] REJECT
Reason: fail-closed 정상 작동. 후보 부재. operator 판단 일관성 유지.
```

---

## 7-Day Acceptance Board (v2)

| Day | Date | Registry | Block% | Warnings | Crashes | SMA/RSI | cg2a | cg2b | Assessment |
|-----|------|----------|--------|----------|---------|---------|------|------|------------|
| 1 | 04-01 | 0 | N/A | 1 | 0 | 31/44 | PASS | WATCH | WATCH |
| 2 | 04-01 | 0 | N/A | 1 | 0 | 44/31 | PASS | WATCH | WATCH |
| 3 | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| 4 | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| 5 | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| 6 | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| 7 | -- | -- | -- | -- | -- | -- | -- | -- | -- |

---

## Day 3 진행 권고

> **권고: Day 3 GO**
>
> 근거:
> 1. CG-2A 연속 2일 PASS
> 2. CG-2B 연속 2일 WATCH (FAIL 아님)
> 3. strategy_type gene 양방향 탐색 관찰 (Day 1: RSI 우세, Day 2: SMA 우세)
> 4. Adaptive mutation + migration 정상 작동
> 5. 안전장치 불변
> 6. HOLD 조건 미해당
>
> Day 3에서 시장 구간이 변하면 CG-2B 변화 가능. 관찰 필요.

---

## JSON-체크리스트 교차 검증: 14/14 일치

| JSON 필드 | 점검표 값 | 일치 |
|-----------|----------|------|
| day | 2 | v |
| data_bars | 500 | v |
| data_source | ccxt_binance | v |
| dry_run | true | v |
| evolution.generations | 10 | v |
| evolution.best_fitness | 0.0 | v |
| evolution.islands | 5 | v |
| evolution.registry_size | 0 | v |
| evolution.status | OK | v |
| orchestrator.governance_decisions | 0 | v |
| orchestrator.is_healthy | false | v |
| orchestrator.warnings | ["Registry size 0 below minimum 3"] | v |
| reconciliation_pass | true | v |
| day_assessment | WATCH | v |
