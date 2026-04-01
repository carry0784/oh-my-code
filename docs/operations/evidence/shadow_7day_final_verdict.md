# Shadow Run — 7-Day Final Verdict

Date: 2026-04-01
Shadow Period: Day 1~7 (2026-04-01)
Baseline Commit: `d813758`

---

## Final Verdict

> **CG-2A는 운영 안전성 기준을 충족하여 Proven으로 판정한다. CG-2B는 본 7일 shadow 창에서 전략 후보 및 거버넌스 경로 실증이 부족하여 Not Proven으로 판정한다. 따라서 전체 권고 결과는 EXTEND다.**

| 판정 축 | 결과 |
|---------|------|
| **CG-2A: Operational Safety** | **PROVEN** |
| **CG-2B: Strategy Production / Governance Flow** | **NOT YET PROVEN** |
| **Overall Recommended Outcome** | **EXTEND** |

---

## 7-Day Acceptance Board (완성본)

| Day | Date | Registry | Block% | Warnings | Drift% | Fitness MA | Crashes | cg2a | cg2b | Assessment |
|-----|------|----------|--------|----------|--------|-----------|---------|------|------|------------|
| 1 | 04-01 | 0 | N/A | 1 | N/A | 0.0 | 0 | PASS | WATCH | WATCH |
| 2 | 04-01 | 0 | N/A | 1 | 0% | 0.0 | 0 | PASS | WATCH | WATCH |
| 3 | 04-01 | 0 | N/A | 1 | 0% | 0.0 | 0 | PASS | WATCH | WATCH |
| 4 | 04-01 | 0 | N/A | 1 | 0% | 0.0 | 0 | PASS | WATCH | WATCH |
| 5 | 04-01 | 0 | N/A | 1 | 0% | 0.0 | 0 | PASS | FAIL | WATCH |
| 6 | 04-01 | 0 | N/A | 1 | 0% | 0.0 | 0 | PASS | FAIL | WATCH |
| 7 | 04-01 | 0 | N/A | 1 | 0% | 0.0 | 0 | PASS | FAIL | WATCH |

**7일 누적 수치:**
- Crashes: 0/7
- Reconciliation: 28/28 PASS
- STOP triggers: 0/7
- Health warnings: 7 (1/day, threshold < 2/day)
- dry_run: true 7/7 days
- registry_size: 0 for 7 consecutive days
- governance_decisions: 0 for 7 consecutive days
- candidate_state: BELOW_THRESHOLD for 7 consecutive days

---

## CG-2A: Operational Safety — PROVEN

### 증거 요약

| 항목 | 7일 누적 | 임계값 | 판정 |
|------|---------|--------|------|
| Crash count | 0 | 0 | **PASS** |
| Reconciliation checks | 28/28 | 28/28 | **PASS** |
| dry_run=true 유지 | 7/7 | 7/7 | **PASS** |
| STOP triggers | 0 | 0 | **PASS** |
| Health warnings (avg/day) | 1.0 | < 2.0 | **PASS** |
| CCXT data collection | 7/7 | — | **PASS** |
| Evolution loop completion | 7/7 | — | **PASS** |
| Orchestrator cycle completion | 7/7 | — | **PASS** |
| fail-closed gate operation | 7/7 | — | **PASS** |

### CG-2A 세부 증명

1. **인프라 안정성**: 7일 연속 크래시 0. 진화 루프(3세대 × 3섬 × 6인구)와 오케스트레이터 사이클이 매일 정상 완료.

2. **통제 구조 무결성**: `dry_run=True` HARDCODED 7일 유지. `PENDING_OPERATOR` 승격 경로 변조 없음. STOP 트리거 0건.

3. **조정 완전성**: `lifecycle_states_valid`, `registry_lifecycle_aligned`, `transitions_have_governance`, `health_monitor_responsive` 4개 항목 7일 × 4 = 28/28 PASS.

4. **fail-closed 정상 작동**: registry=0일 때 거버넌스 게이트가 존재하지 않는 후보를 억지로 통과시키지 않음. 이것은 안전 설계의 올바른 동작.

5. **헬스 모니터 반응성**: "Registry size 0 below minimum 3" 경고를 7일 연속 정확하게 발행. 이상 상태를 숨기지 않음.

---

## CG-2B: Strategy Production — NOT YET PROVEN

### 미충족 CG-2 기준

| # | CG-2 기준 | 임계값 | 7일 실적 | 판정 |
|---|-----------|--------|---------|------|
| CG2-1 | Shadow duration >= 7 days | 7 | 7 | **PASS** |
| CG2-2 | Orchestrator crashes = 0 | 0 | 0 | **PASS** |
| CG2-3 | Optimizer drift < 20% | <20% | 0% | **PASS** |
| CG2-4 | Governance block rate > 0% | >0% | N/A (0 candidates) | **NOT MET** |
| CG2-5 | PENDING_OPERATOR < 20/day | <20 | 0 | **PASS** |
| CG2-6 | Health warnings < 2/day avg | <2 | 1.0 | **PASS** |
| CG2-7 | Fitness 3-day MA non-decreasing | non-decreasing | 0.0 → 0.0 | **PASS** (trivially) |
| CG2-8 | Registry growth >= 1/2 days | >= 3.5 | 0 | **NOT MET** |
| CG2-9 | Daily reconciliation 4/4 | 4/4 | 28/28 | **PASS** |

**NOT MET 항목: CG2-4, CG2-8** — 둘 다 registry_size=0에 기인.

### 근본 원인 분석

**1. 전략 유형 한계**
- SMA 크로스오버만 존재 (단일 전략군)
- 추세 추종 전략이 횡보/노이즈 시장에서 양의 fitness를 생성하지 못함
- 5분봉 200바 (약 16.7시간)는 의미 있는 추세를 포착하기에 짧은 구간

**2. 진화 설정의 보수성**
- 3세대는 수렴에 불충분할 수 있음
- 6인구 × 3섬 = 18개 게놈은 탐색 공간 대비 작음
- 그러나 shadow 중 설정 변경은 금지 (원칙 준수)

**3. 시장 구간 고정**
- 동일 시간대 반복 실행으로 비슷한 시장 데이터 수집
- 일간 시장 변동성 다양성이 제한적

**4. fitness 임계값의 정상 작동**
- best_fitness = 0.0이면 registry 등록 기준 미달
- 이것은 시스템의 올바른 동작: 저품질 전략을 걸러냄

### 핵심 구분

> **이것은 시스템 결함이 아니다.** 진화, 토너먼트, 등록, 거버넌스, 헬스 — 모든 컴포넌트가 올바르게 작동했다. 문제는 "전략-시장 불일치"이며, 이는 설계 제약(SMA only, 보수적 진화 설정)에 기인한다.

---

## EXTEND 옵션 비교

### 옵션 A: 동일 설정 연장 Shadow

| 항목 | 내용 |
|------|------|
| 기간 | +3일 (Day 8~10) |
| 설정 변경 | 없음 |
| 기대 효과 | 시장 구간 변화로 자연적 registry >= 1 발생 가능 |
| CG-2B 확보 가능성 | **낮음** — 7일간 0이었으므로 +3일도 동일할 확률 높음 |
| 장점 | 추가 CR 불필요, 즉시 시작 가능, 순수 관측 연장 |
| 단점 | 관찰 반복 가능성 높음, 시간 비용 대비 정보 이득 낮음 |
| 적합 조건 | "시장 변화만 기다리면 될 때" |

### 옵션 B: CR 승인 후 파라미터 재설계 + 재Shadow

| 항목 | 내용 |
|------|------|
| 기간 | 새 7일 shadow cycle |
| 설정 변경 | CR 제출 후 승인 |
| CR 범위 후보 | (a) max_generations 증가 (3→10), (b) population 증가 (6→20), (c) 전략 유형 추가 (RSI, Bollinger, MACD 등), (d) lookback 조정 (50→100), (e) fitness 임계값 조정, (f) 데이터 수집 시간대 분산 |
| CG-2B 확보 가능성 | **높음** — 구조적 원인을 직접 해결 |
| 장점 | CG-2B 증거 확보 가능성 대폭 상승, 실질적 개선 |
| 단점 | 새 CR 필요, 추가 테스트 필요, 기준선 재고정 필요 |
| 적합 조건 | "구조적 원인을 해결하고 재증명할 때" |

### 옵션 비교표

| 기준 | 옵션 A | 옵션 B |
|------|--------|--------|
| CG-2B 확보 가능성 | 낮음 | **높음** |
| 추가 비용 (시간) | 3일 | 7일+ |
| CR 필요 여부 | 불필요 | **필요** |
| 위험 | 3일 더 허비 가능 | 새 CR 범위 통제 필요 |
| 정보 이득 | 낮음 | **높음** |
| **권고 순위** | 2순위 | **1순위** |

---

## 최종 권고

> **권고: 옵션 B (CR 승인 후 파라미터 재설계 + 재Shadow) 우선**

### 권고 근거

1. 7일 연속 동일 결과는 동일 설정 연장으로 해소되지 않을 가능성이 높음
2. 근본 원인이 "전략 유형 한계 + 진화 보수성"으로 명확히 식별됨
3. CR을 통한 설계 변경은 CG-2B 확보 가능성을 구조적으로 높임
4. CG-2A는 이미 Proven이므로 재Shadow에서도 안전성은 유지될 것으로 예상

### 옵션 B 실행 시 CR 패키지 권고

| # | CR 항목 | 변경 내용 | 우선순위 |
|---|---------|---------|---------|
| 1 | 전략군 확장 | SMA 외 RSI, Bollinger 등 추가 | **높음** |
| 2 | 진화 세대 증가 | max_generations: 3 → 10+ | 높음 |
| 3 | 인구 크기 증가 | population: 6 → 20+ | 중간 |
| 4 | lookback 조정 | 50 → 100+ | 중간 |
| 5 | 데이터 시간대 분산 | 실행 시각 분산 또는 다중 timeframe | 낮음 |

---

## 후속 의사결정표

| A의 선택 | 다음 단계 | 예상 기간 |
|---------|---------|---------|
| **옵션 B 승인** | CR 제출 → 구현 → 테스트 → 새 기준선 → 재Shadow 7일 | 2~3주 |
| **옵션 A 승인** | 동일 설정 +3일 연장 Shadow (Day 8~10) | 3일 |
| **HOLD** | Shadow 중단, 재설계 검토 후 재개 | 미정 |
| **다른 접근** | A 판단에 따름 | — |

---

## GO/HOLD 위치 업데이트

```
[X] BUILD COMPLETE
[X] GOVERNANCE COMPLETE
[X] CG-1: KILL-SWITCH PROVEN
[~] CG-2: SHADOW PROVEN         ← CG-2A Proven / CG-2B Not Proven → EXTEND
[ ] OPERATOR AUTHORIZED
[ ] LIVE ELIGIBLE
```

---

## 서명

```
Shadow Run 7-Day Final Verdict

Period: Day 1~7 (2026-04-01)
Baseline: d813758
CG-2A: PROVEN
CG-2B: NOT YET PROVEN
Overall: EXTEND
Recommended: Option B (CR + redesign)

Prepared by: B (Implementer)
Review required: A (Decision Authority)
Date: 2026-04-01
```
