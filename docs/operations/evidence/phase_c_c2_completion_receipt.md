# Phase C C-2 — Completion Receipt

**완료일:** 2026-04-10
**판정:** ASYMMETRIC (BTC=PASS / SOL=INFORMATIVE_FAIL)
**범위:** S-3 Density Uplift 실험 (FW2 10%→15%, shadow/paper only)
**scope 위반:** 0건
**canonical_run_id:** `bihlkm8s6`
**superseded_run_id:** `bgbkdmd64` (segments dict 접근 오류로 중단, 본 run에 의해 대체됨)

---

## Completion Header

| 항목 | 값 |
|------|---|
| `sol_density_pass` | **false** (FW2 trades 5→8, min_trades=10 미달) |
| `btc_density_pass` | **true** (FW2 trades 8→12, min_trades=10 충족) |
| `sol_quality_hold` | **true** (Train Δ=0.0000, FW1 Δ=0.0000) |
| `btc_quality_hold` | **true** (Train Δ=0.0000, FW1 Δ=0.0000) |
| `scope_violation` | **0건** |
| `b1_core_modified` | **false** |
| `smc_wt_logic_modified` | **false** |
| `live_deployed` | **false** |
| `auto_advance` | **false** |
| `s3_global_adoption` | **금지** (lane-specific candidate로 재분류) |

---

## Run 증거 체인

| 필드 | 값 |
|------|---|
| `failed_run_id` | `bgbkdmd64` |
| `failure_reason` | `AttributeError: 'str' object has no attribute 'segment_name'` (segments dict 순회 오류) |
| `superseded_by` | `bihlkm8s6` |
| `canonical_run_id` | `bihlkm8s6` |
| `canonical_exit_code` | 0 |
| `canonical_log` | `phase_c_c2_s3_experiment_log.json` |

**규칙**: 본 receipt의 모든 수치는 canonical run (`bihlkm8s6`) 기준이다. Failed run의 부분 결과는 참조하지 않는다.

---

## Deliverable 1: 변경 범위 증빙

| 항목 | Baseline | S-3 | 변경 |
|------|----------|-----|------|
| train_ratio | 0.60 | 0.60 | 미변경 |
| forward1_ratio | 0.20 | 0.20 | 미변경 |
| forward2_ratio | 0.10 | 0.15 | **+0.05** |
| holdout_ratio | 0.10 | 0.05 | **-0.05** |

**B-1 core 수정:** 없음 (FullCycleConfig 인스턴스 값만 변경, dataclass 미수정)
**Protected symbol 수정:** 없음 (FullCycleConfig / SegmentResult / FullCycleResult / SegmentSplitter)
**SMC/WT 로직 수정:** 없음
**BacktestingEngine occupancy rule 수정:** 없음

---

## Deliverable 2: Before/After Density 비교표

### SOL/USDT:USDT

| Segment | Bars (B→S3) | Trades (B→S3) | Fitness (B→S3) | Uplift | min_trades (B→S3) | Fitness Δ |
|---------|-------------|---------------|----------------|--------|--------------------|-----------|
| train | 5760→5760 | 46→46 | 0.4158→0.4158 | +0 (+0.0%) | OK→OK | +0.0000 |
| forward_1 | 1920→1920 | 19→19 | 0.3435→0.3435 | +0 (+0.0%) | OK→OK | +0.0000 |
| forward_2 | 960→1440 | 5→8 | 0.0000→0.0000 | **+3 (+60.0%)** | MISS→MISS | +0.0000 |
| holdout | 960→480 | 8→4 | 0.0000→0.0000 | -4 (-50.0%) | MISS→MISS | +0.0000 |

**Verdict:** FAIL → FAIL
**Overall fitness:** 0.2865 → 0.2865
**RDS:** 0.2740 → 0.2740
**Density PASS:** false
**Quality hold:** true
**Step verdict:** **INFORMATIVE_FAIL**

**SOL 해석:**
- FW2 구간 50% 확대(960→1440 bars)로 trades 60% 증가(5→8)
- 그러나 min_trades=10 미달 (8 trades)
- C-1 진단의 FW2 집중도 9.1% (기대치 이하) 예측과 일치
- **결론: SOL은 S-3만으로 density 문제 해결 불가**

### BTC/USDT:USDT

| Segment | Bars (B→S3) | Trades (B→S3) | Fitness (B→S3) | Uplift | min_trades (B→S3) | Fitness Δ |
|---------|-------------|---------------|----------------|--------|--------------------|-----------|
| train | 5760→5760 | 24→24 | 0.4522→0.4522 | +0 (+0.0%) | OK→OK | +0.0000 |
| forward_1 | 1920→1920 | 12→12 | 0.8711→0.8711 | +0 (+0.0%) | OK→OK | +0.0000 |
| forward_2 | 960→1440 | 8→12 | 0.0000→0.8977 | **+4 (+50.0%)** | MISS→**OK** | **+0.8977** |
| holdout | 960→480 | 8→5 | 0.0000→0.0000 | -3 (-37.5%) | MISS→MISS | +0.0000 |

**Verdict:** FAIL → FAIL (RDS + WF_EFFICIENCY 여전히 미달)
**Overall fitness:** 0.4857 → **0.7102** (+0.2245)
**RDS:** 0.0755 → 0.0755
**Density PASS:** **true**
**Quality hold:** true
**Step verdict:** **PASS**

**BTC 해석:**
- FW2 구간 50% 확대(960→1440 bars)로 trades 50% 증가(8→12), min_trades=10 충족
- FW2 fitness 0.00→0.90으로 극적 개선 (penalty 해제)
- overall_fitness 0.49→0.71로 상승 (+46%)
- C-1 진단의 FW2 집중도 17.2% (기대치 이상) 예측과 정확히 일치
- **결론: BTC는 S-3로 FW2 density 문제 해결됨. 그러나 RDS + WF_EFFICIENCY 미달은 별도 원인**

---

## Deliverable 3: Quality 유지 판정표

| Asset | Train Δ | FW1 Δ | Quality Hold | Density PASS | Step Verdict |
|-------|---------|-------|--------------|--------------|--------------|
| SOL/USDT:USDT | +0.0000 | +0.0000 | true | false | **INFORMATIVE_FAIL** |
| BTC/USDT:USDT | +0.0000 | +0.0000 | true | **true** | **PASS** |

**Quality 평가:**
- 양 자산 모두 Train/FW1 구간은 동일 데이터 범위이므로 fitness 변동 없음
- Quality degradation = 0 (두 자산 모두)
- S-3는 FW2/Holdout 경계만 이동하므로, Train/FW1에 대한 부작용 없음을 확인

---

## Deliverable 4: Cross-Asset 종합 판정

### 판정: **ASYMMETRIC** (BTC=PASS / SOL=INFORMATIVE_FAIL)

| 판정 항목 | 결과 |
|-----------|------|
| 양 자산 density uplift | BTC만 min_trades 충족 |
| 양 자산 quality hold | 양 자산 모두 충족 |
| scope 위반 | 0건 |
| B-1 core 무결성 | 유지 |

### 의미 분석

**S-3 (FW2 비율 확대)은 "저위험 density 보정책"으로서 설계 의도를 정확히 달성했다:**

1. **BTC**: FW2 집중도 17.2%인 BTC에서는 구간 확대가 즉각 효과 → min_trades 충족
2. **SOL**: FW2 집중도 9.1%인 SOL에서는 구간 확대만으로 불충분 → 근본 원인(SMC scarcity) 미해결
3. **C-1의 이원 우선순위 예측 정확**: 운영 우선순위(S-3 저위험)와 근본 우선순위(S-1 SMC scarcity)의 분리가 실험적으로 확인됨

### BTC에 대한 S-3 적용 여부

BTC에 S-3 비율을 적용할지 여부는 C-2 scope 밖이며, 별도 판단 필요:
- S-3는 FW2 density만 해결하며, RDS(0.0755) + WF_EFFICIENCY(-2.91) 미달은 별도 원인
- S-3 적용이 이 두 지표를 악화시키지는 않음 (quality hold = true)
- 그러나 S-3만으로 BTC verdict를 PASS로 전환하지는 못함

### SOL에 대한 후속 방향

SOL은 S-3로 해결 불가가 실험적으로 확인됨:
- FW2 trades: 5→8 (min_trades=10까지 2 trades 부족)
- 근본 원인: SMC fire rate ~4.1%에 의한 consensus 상한 제한
- 후속 후보: **S-1 (보조 신호원)** = 근본 개선 1순위

### 핵심 해석 고정

```
C-2는 "전략 성공"이 아니라 "비대칭 학습 성공"이다.
S-3 = density patch (lane-specific)
S-1 = root-cause candidate (SOL 우선)
C-2 성공 ≠ S-track 해결 완료
```

---

## S-3 재분류: Lane별 후보 장부

C-2 결과에 의해 S-3의 지위를 재분류한다.

| 분류 전 | 분류 후 |
|---------|--------|
| S-3 = 전 자산 공통 저위험 1순위 | S-3 = **BTC lane-specific conditional candidate** |

### Lane별 후보 장부

| Asset | 후보 | 지위 | shadow | paper | live | global | 근거 |
|-------|------|------|--------|-------|------|--------|------|
| BTC | S-3 (FW2 비율 확대) | **conditional keep** | OK | OK | **금지** | **금지** | FW2 trades 8→12, min_trades 충족, fitness 0→0.90 |
| SOL | S-3 (FW2 비율 확대) | **reject** | N/A | N/A | N/A | **금지** | FW2 trades 5→8, min_trades 미달, FW2 집중도 9.1% |
| SOL | S-1 (보조 신호원) | **priority candidate** | 별도GO | 별도GO | **금지** | **금지** | SMC scarcity 근본 원인 직접 완화, 근본 개선 1순위 유지 |
| 전체 | S-3 global default | **채택 금지** | N/A | N/A | N/A | **금지** | 자산 비대칭으로 공통 해법 불성립 |

### 금지 사항

- S-3를 전 자산 공통 default로 승격 금지
- SOL 미해결 상태를 무시한 "S-track 해결 완료" 선언 금지
- BTC S-3 PASS를 근거로 전체 S-track을 과대평가 금지

---

## C-1 예측 대비 실측 검증 (진단 정확도 추적)

| C-1 예측 항목 | 예측 | 실측 | 일치 |
|---------------|------|------|------|
| SOL FW2 집중도 9.1% → S-3 효과 제한적 | trades < 10 예상 | trades=8 (MISS) | **일치** |
| BTC FW2 집중도 17.2% → S-3 효과 유효 | trades ≥ 10 예상 | trades=12 (OK) | **일치** |
| S-3는 근본 해결책이 아닌 density 보정 | SOL 미해결 예상 | SOL INFORMATIVE_FAIL | **일치** |
| Quality degradation 없을 것 | Train/FW1 무변동 | Train/FW1 Δ=0.00 | **일치** |

**C-1 진단의 정확도: 4/4 (100%)**

### 진단 프레임 유효성 평가

C-1에서 수립한 진단 프레임(FW2 집중도, 이원 우선순위, quality hold 예측)이 C-2 실측에서 **100% 적중**했다. 이는 단순히 실험 하나가 끝난 것이 아니라, **진단 모델 자체가 운영 가능한 수준**임을 의미한다.

| 진단 도구 | 예측력 | 운영 가능성 |
|-----------|--------|------------|
| FW2 집중도 지수 | **검증됨** (SOL 9.1% → MISS, BTC 17.2% → OK) |후보 효과 사전 판별에 사용 가능 |
| 이원 우선순위 분류 | **검증됨** (운영 vs 근본 분리 정확) | 후보 채택/폐기 기준으로 사용 가능 |
| Quality hold 예측 | **검증됨** (Train/FW1 무변동) | 부작용 사전 판별에 사용 가능 |

**권고**: 이 진단 프레임을 후속 실험(C-3, C-4)에서도 표준 진단 도구로 재사용한다.

---

## Holdout 축소 영향

| Asset | Holdout Bars (B→S3) | Holdout Trades (B→S3) |
|-------|--------------------|-----------------------|
| SOL | 960→480 | 8→4 |
| BTC | 960→480 | 8→5 |

Holdout은 blind test 구간으로 verdict에 직접 기여하지 않으나, 축소로 trades가 감소함.
이는 S-3의 trade-off: **FW2 density 확보 vs Holdout 검증력 축소**.

---

## 미해결 잔여 병목 (S-3 미해결)

| # | 병목 | 영향 자산 | S-3 해결 여부 | 후속 후보 |
|---|------|-----------|--------------|-----------|
| 1 | SMC fire rate ~4% (1차 병목) | SOL+BTC | 미해결 | S-1 (보조 신호원) |
| 2 | Position occupancy block ~28% (2차 병목) | SOL+BTC | 미해결 | 별도 분석 |
| 3 | RDS < 0.55 (regime 편중) | SOL+BTC | 미해결 | R-track (C-3) |
| 4 | WF efficiency < 0.5 (학습 불안정) | SOL+BTC | 미해결 | W-track (C-4) |

---

## 후속 GO 선택 결과

C-2 종료 시점에서 2개 선택지 중 사용자가 **C-3 only GO**를 선택했다.

| 선택지 | 상태 | 근거 |
|--------|------|------|
| **C-3 only GO** | **SELECTED** | phase_progress_priority — 동일 축 반복보다 다음 축(R-track) 진단의 정보 수익이 큼 |
| SOL S-1 follow-up GO | **HOLD** | C-3 완료 후 재평가 |

```
active_path = C-3 (R-track regime 진단)
held_path = SOL S-1 follow-up
selection_reason = phase_progress_priority
```

---

## 상태 전이

```
C-2: LIMITED_GO -> CLOSED (ASYMMETRIC: BTC=PASS / SOL=INFORMATIVE_FAIL)
next_unlocked_step: NONE (C-3 별도 GO 필요)
auto_advance_allowed: false
selected_go: C-3 only (R-track regime 진단) — ACTIVE
held_go: SOL S-1 follow-up — HOLD (C-3 완료 후 재평가)
selection_reason: phase_progress_priority
```

---

## 봉인

- C-2는 S-3 shadow/paper 범위 내에서 완료되었다
- **C-2 성공은 "S-track 해결 완료"를 의미하지 않는다** — 비대칭 학습 성공이다
- BTC에서 FW2 density uplift가 확인되었다 (trades 8→12, min_trades 충족)
- SOL에서 FW2 density uplift가 불충분했다 (trades 5→8, min_trades 미달)
- S-3는 global candidate에서 **BTC lane-specific conditional candidate로 재분류**되었다
- S-3를 전 자산 공통 default로 승격하는 것은 금지한다
- C-1의 이원 우선순위 예측이 100% 일치하여 진단 프레임의 운영 유효성이 확인되었다
- S-3는 저위험 density 보정(density patch)이며, 근본 해결책(root-cause fix)이 아님이 실험적으로 재확인되었다
- SOL root-cause 후속 후보는 S-1 (보조 신호원)이며, 별도 GO가 필요하다
- Quality degradation은 0건이다
- Scope 위반은 0건이다
- B-1 core 이중 잠금(line + symbol)은 유지되었다
- Canonical run은 `bihlkm8s6`이며, failed run `bgbkdmd64`는 참조하지 않는다
- C-3 이후 착수는 별도 explicit GO가 필요하다
