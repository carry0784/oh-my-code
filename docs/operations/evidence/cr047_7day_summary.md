# CR-047: 1H Timeframe CG-2B Re-verification -- 7-Day Summary

CR: CR-047 (1H 시간봉 기반 CG-2B 재검증)
Plan: A (1H signal / 1H evaluation)
Baseline: `c2a3242`
Period: 2026-04-01 (Day 1~7)

---

## 7-Day Acceptance Board

| Day | Registry | Best Fit | Gov Dec | Healthy | SMA/RSI | CG-2B-1 | CG-2B-2 | Assessment |
|-----|----------|----------|---------|---------|---------|---------|---------|------------|
| 1 | **8** | 0.884 | 4 | true | 5/70 | **proven** | **proven** | **PASS** |
| 2 | **10** | 0.423 | 4 | true | 33/42 | **proven** | **proven** | **PASS** |
| 3 | **5** | 0.884 | 4 | true | 7/68 | **proven** | **proven** | **PASS** |
| 4 | **5** | 0.857 | 4 | true | 65/10 | **proven** | **proven** | **PASS** |
| 5 | **8** | 0.423 | 4 | true | 47/28 | **proven** | **proven** | **PASS** |
| 6 | **6** | 0.884 | 4 | true | 65/10 | **proven** | **proven** | **PASS** |
| 7 | **10** | 0.857 | 4 | true | 60/15 | **proven** | **proven** | **PASS** |

---

## CR-045 (5m) vs CR-047 (1H) 비교

| 항목 | CR-045 (5m) 7일 | CR-047 (1H) 7일 | 변화 |
|------|----------------|-----------------|------|
| registry_size range | 0 (전체) | **5~10** | 0 -> 5~10 |
| best_fitness range | 0.0 (전체) | **0.42~0.88** | 0 -> 양수 |
| governance_decisions | 0 (전체) | **4/day** | 0 -> 28 total |
| is_healthy | false (전체) | **true (전체)** | false -> true |
| CG-2B-1 | not_proven | **7/7 proven** | 개방 |
| CG-2B-2 | not_proven | **7/7 proven** | 개방 |
| day_assessment | WATCH (전체) | **PASS (전체)** | WATCH -> PASS |

---

## CG-2B-1: Candidate Generation -- 7/7 PROVEN

| 항목 | 결과 |
|------|------|
| registry_size 최소 | 5 |
| registry_size 최대 | 10 |
| registry_size 평균 | 7.4 |
| best_fitness 범위 | 0.42 ~ 0.88 |
| candidate_generation_rate_1h | 5~10/day |

**판정: PROVEN**
1H 시간봉에서 SMA/RSI 모두 min_trades >= 10을 충족하는 후보를 매일 생성.

---

## CG-2B-2: Governance Exercisability -- 7/7 PROVEN

| 항목 | 결과 |
|------|------|
| governance_decisions/day | 4 (매일 동일) |
| 7일 총 decisions | 28 |
| auto_approved | 4/day |
| pending_operator | 0/day |
| transitions | 4/day (candidate->validated->paper_trading) |
| governance_exercisability_rate_1h | 4/day |

**판정: PROVEN**
거버넌스 게이트가 매일 4건의 판정을 수행. 후보 -> 검증 -> 페이퍼트레이딩 전이 경로 완전 개방.

---

## Strategy Type Gene 분석

| Day | SMA | RSI | 우세 |
|-----|-----|-----|------|
| 1 | 5 | 70 | RSI (93%) |
| 2 | 33 | 42 | RSI (56%) |
| 3 | 7 | 68 | RSI (91%) |
| 4 | 65 | 10 | SMA (87%) |
| 5 | 47 | 28 | SMA (63%) |
| 6 | 65 | 10 | SMA (87%) |
| 7 | 60 | 15 | SMA (80%) |

**관찰**:
- Day 1~3: RSI 우세 (1H에서 RSI가 더 많은 crossover 생성)
- Day 4~7: SMA 우세 (진화가 SMA 파라미터를 최적화하면서 수렴)
- 양방향 탐색 후 수렴 패턴 관찰 = 자연스러운 진화 동작

---

## 안전장치 불변 확인

| 항목 | 상태 |
|------|------|
| dry_run=True | 7/7 HARDCODED |
| PENDING_OPERATOR | 유지 (auto_approve 경로만 사용) |
| min_trades=10 | 유지 (하향 안 함) |
| reconciliation | 7/7 PASS (28/28 개별 체크) |
| crashes | 0 |
| STOP triggers | 0 |
| live write path | 없음 |

---

## 종합 판정

```
CR-047 7-Day Assessment: PASS

CG-2A: SEALED (이전 CR-045에서 확정)
CG-2B-1 (Candidate Generation): 7/7 PROVEN
CG-2B-2 (Governance Exercisability): 7/7 PROVEN

1H 시간봉 전환으로 CG-2B 전체가 개방됨.
5m에서 관측 불가능했던 후보 생성 + 거버넌스 행사가
1H에서는 매일 안정적으로 발생.

핵심 전환점:
- 5m: 500바 = 41.7시간 -> trades 부족 -> fitness=0
- 1H: 500바 = 20.8일 -> trades 충분 -> fitness=0.42~0.88 -> registry=5~10

기준(min_trades=10)은 유지하면서 관측 구조를 바꾸는 것이 정답이었음.
```

---

## Signature

```
CR-047: 1H Timeframe CG-2B Re-verification
Plan A: 1H signal / 1H evaluation
Result: 7/7 PASS, CG-2B-1 PROVEN, CG-2B-2 PROVEN
Prepared by: B (Implementer)
Date: 2026-04-01
```
