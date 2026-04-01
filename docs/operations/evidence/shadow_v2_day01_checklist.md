# reShadow v2 Run -- Day 1 일일 점검표

실행 시각: 2026-04-01T04:17:53Z (13:17 KST)
Market Regime 라벨: **Inactive Market Regime**
기준선: `0a9fff1` (CR-045 + island_model fix)
CR: CR-045 (CG-2B Exercisability Recovery Package)

> **CG-2A 안전성 유지 여부 + CG-2B 후보 생성 경로 개방 여부를 동시 검증**

---

## Config Fingerprint

```
bars=500, lookback=30, islands=5, pop=10, gen=10
strategy_types=[SMA, RSI], baseline=0a9fff1, cr=CR-045
```

---

## 체크리스트 요약

| 구분 | 항목 | Day 1 |
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
| **SMA** | 31 | 0.0 | 0 | 0~3 |
| **RSI** | 44 | 0.0 | 0 | 0~1 |

### 전략별 4개 필드

```json
"candidate_generation_by_strategy": {"SMA": 31, "RSI": 44}
"fitness_by_strategy":              {"SMA": 0.0, "RSI": 0.0}
"registry_entries_by_strategy":     {"SMA": 0, "RSI": 0}
```

### 전략별 분석

- **SMA**: 500바로 확대 후 trades 0~3건 (v1 대비 소폭 증가). 여전히 min_trades=10 미달.
- **RSI**: 진화가 RSI 전략을 우선 선택(44/75 = 59%). 그러나 Inactive Market에서 RSI crossover도 0~1건. Overbought/oversold 경계를 넘는 변동성이 부족.
- **핵심 관찰**: 진화가 RSI를 SMA보다 더 많이 선택 → strategy_type gene이 정상 작동. 그러나 현 시장 구간에서는 두 전략 모두 min_trades=10 미달.

---

## CG-2 분리 판정

### CG-2A: 운영 회로 안정성 -- Day 1 PASS

| 항목 | Day 1 |
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

### CG-2B: 전략/거버넌스 -- Day 1 WATCH

| 항목 | Day 1 |
|------|-------|
| registry_size | 0 |
| governance_decisions | 0 |
| candidate_state | BELOW_THRESHOLD |
| strategy_type gene | 정상 (SMA 31 / RSI 44) |
| RSI routing | **정상** (island_model fix 후 RSI_ prefix 확인) |

---

## v1 vs v2 Day 1 비교

| 항목 | v1 Day 1 | v2 Day 1 | 변화 |
|------|---------|---------|------|
| bars | 200 | **500** | +300 |
| generations | 3 | **10** | +7 |
| islands | 3 | **5** | +2 |
| population | 18 (6x3) | **50 (10x5)** | +32 |
| strategy types | SMA only | **SMA + RSI** | +1 |
| RSI genomes | 0 | **44** | NEW |
| SMA trades range | 0~2 | **0~3** | 소폭 증가 |
| RSI trades range | -- | **0~1** | NEW (아직 부족) |
| mutations | 3gen | **10gen + adaptive** | 확대 |
| registry | 0 | 0 | 동일 |
| best_fitness | 0.0 | 0.0 | 동일 |

---

## Day 판정

```
Day 1 Assessment: [ ] PASS  [x] WATCH  [ ] FAIL

overall_status = CG-2A_PASS__CG-2B_WATCH
Recommended Outcome = CONTINUE

사유:
  CG-2A: PASS — 인프라, 통제 구조, 안전 회로 정상.
  CG-2B: WATCH — RSI 전략 분기 정상 작동 확인. 진화가 RSI를 59% 선택.
         그러나 Inactive Market Regime에서 두 전략 모두 trades 부족.
         min_trades=10 미달 → fitness=0.0 → registry=0.
         이것은 시스템 결함이 아니라 시장 상태에 의한 관측 제약.

  CR-045 효과:
  [x] RSI 전략 분기 실제 작동 확인 (RSI_ prefix 로그)
  [x] strategy_type gene 정상 (진화가 RSI 우선 선택)
  [x] 500바 수집 정상
  [x] 10gen x 5islands 진화 완주
  [ ] min_trades=10 충족 — 미달 (시장 제약)
  [ ] fitness > 0 — 미달 (시장 제약)
  [ ] registry >= 1 — 미달 (시장 제약)
```

---

## Day 1 발견 및 수정 사항

### island_model.py 중복 분기 발견 및 수정

Day 1 첫 실행에서 `island_model.py:196-204`에 별도의 `_genome_to_strategy`가 존재하여
RSI genome이 실제로는 SMA로 backtest되고 있었음을 발견.

- **원인**: CR-045 변경 파일 목록에서 `island_model.py` 누락
- **수정**: `island_model._genome_to_strategy`를 `StrategyRunner._genome_to_strategy`로 위임
- **커밋**: `0a9fff1`
- **검증**: 수정 후 Day 1 재실행 → RSI_ prefix 로그 정상 확인
- **영향**: 안전장치 불변 (strategy 선택 경로만 수정, execution path 불변)

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
| 2 | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| 3 | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| 4 | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| 5 | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| 6 | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| 7 | -- | -- | -- | -- | -- | -- | -- | -- | -- |

---

## Day 2 진행 권고

> **권고: Day 2 GO**
>
> 근거:
> 1. CG-2A PASS, CG-2B WATCH (FAIL 아님)
> 2. CR-045 구조 변경 정상 작동 확인 (RSI 분기, gene, 500바, 10gen)
> 3. island_model 수정으로 완전한 전략 다양성 확보
> 4. 안전장치 불변
> 5. HOLD 조건 미해당
>
> Day 2에서 시장 구간이 변하면 CG-2B 변화 가능. 관찰 필요.

---

## JSON-체크리스트 교차 검증: 14/14 일치 ✓

| JSON 필드 | 점검표 값 | 일치 |
|-----------|----------|------|
| day | 1 | ✓ |
| data_bars | 500 | ✓ |
| data_source | ccxt_binance | ✓ |
| dry_run | true | ✓ |
| evolution.generations | 10 | ✓ |
| evolution.best_fitness | 0.0 | ✓ |
| evolution.islands | 5 | ✓ |
| evolution.registry_size | 0 | ✓ |
| evolution.status | OK | ✓ |
| orchestrator.governance_decisions | 0 | ✓ |
| orchestrator.is_healthy | false | ✓ |
| orchestrator.warnings | ["Registry size 0 below minimum 3"] | ✓ |
| reconciliation_pass | true | ✓ |
| day_assessment | WATCH | ✓ |
