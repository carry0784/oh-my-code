# Phase C C-3 — Completion Receipt

**완료일:** 2026-04-10
**판정:** MAINTAINED_FAIL (양 자산 모두 구조적 regime 편중)
**범위:** R-track regime diversity 진단 (구현 미포함)
**previous_chain:** C-2 SEALED (ASYMMETRIC)
**selection_reason:** phase_progress_priority

---

## Completion Header

| 항목 | 값 |
|------|---|
| `sol_rds` | **0.2740** (threshold 0.55 미달) |
| `btc_rds` | **0.0755** (threshold 0.55 미달) |
| `sol_dominant_regime` | **ranging 84.5%** |
| `btc_dominant_regime` | **ranging 96.1%** |
| `sol_effective_regime_count` | **3** |
| `btc_effective_regime_count` | **1** |
| `sol_rds_pass` | **false** |
| `btc_rds_pass` | **false** |
| `sol_step_verdict` | **MAINTAINED_FAIL** |
| `btc_step_verdict` | **MAINTAINED_FAIL** |
| `overall_verdict` | **MAINTAINED_FAIL** |
| `scope_violation` | **0건** |
| `b1_core_modified` | **false** |
| `regime_detector_modified` | **false** |
| `auto_advance` | **false** |

---

## 핵심 해석 고정

```
C-3 diagnostic success ≠ regime improvement complete
R-track MAINTAINED_FAIL = 시장 자체의 구조적 ranging 편중이 실험적으로 재확인됨
RDS 0.55는 현 암호화폐 1H 환경에서 달성 불가
이것은 탐지기의 문제가 아니라 시장의 특성이다
```

---

## Deliverable 1: Global Regime Distribution

### SOL/USDT:USDT

| Regime | Bars | Share | Trades | Trade Share |
|--------|------|-------|--------|-------------|
| ranging | 8114 | 84.5% | 80 | 98.8% |
| trending_down | 754 | 7.8% | 1 | 1.2% |
| trending_up | 706 | 7.3% | 0 | 0.0% |
| unknown | 26 | 0.3% | 0 | 0.0% |

**RDS:** 0.2740 (threshold: 0.55) **FAIL**
**Dominant regime:** ranging (84.5%)
**Effective regime count:** 3 (trending_up, trending_down, ranging이 각 5% 이상)
**Blank zones:** trending_up, unknown (bars는 존재하나 trades 0건)

### BTC/USDT:USDT

| Regime | Bars | Share | Trades | Trade Share |
|--------|------|-------|--------|-------------|
| ranging | 9227 | 96.1% | 53 | 100.0% |
| trending_up | 175 | 1.8% | 0 | 0.0% |
| trending_down | 172 | 1.8% | 0 | 0.0% |
| unknown | 26 | 0.3% | 0 | 0.0% |

**RDS:** 0.0755 (threshold: 0.55) **FAIL**
**Dominant regime:** ranging (96.1%)
**Effective regime count:** 1 (ranging만 5% 이상)
**Blank zones:** trending_up, trending_down, unknown (모든 비-ranging regime에서 trades 0건)

---

## Deliverable 2: Per-Segment Regime Profile

### SOL/USDT:USDT

| Segment | Bars | Dominant | Dom Share | Eff Regimes | RDS |
|---------|------|----------|-----------|-------------|-----|
| train | 5760 | ranging | 84.4% | 3 | 0.2760 |
| forward_1 | 1920 | ranging | 85.8% | 3 | 0.2532 |
| forward_2 | 960 | ranging | 80.9% | 3 | 0.3265 |
| holdout | 960 | ranging | 86.2% | 3 | 0.2482 |

**해석:** 전 세그먼트에서 ranging 80-86%, RDS 0.25-0.33 범위. 특정 세그먼트가 아니라 **전체 데이터의 구조적 특성**.

### BTC/USDT:USDT

| Segment | Bars | Dominant | Dom Share | Eff Regimes | RDS |
|---------|------|----------|-----------|-------------|-----|
| train | 5760 | ranging | 97.2% | 1 | 0.0548 |
| forward_1 | 1920 | ranging | 96.3% | 1 | 0.0719 |
| forward_2 | 960 | ranging | 91.7% | 1 | 0.1562 |
| holdout | 960 | ranging | 93.7% | 1 | 0.1207 |

**해석:** 전 세그먼트에서 ranging 92-97%, RDS 0.05-0.16 범위. SOL보다 훨씬 심한 ranging 편중. **사실상 단일 regime 환경**.

---

## Deliverable 3: Regime-Trade Cross-Reference

### SOL/USDT:USDT

| Regime | Trades | Share | Win Rate | Total Return |
|--------|--------|-------|----------|--------------|
| ranging | 80 | 98.8% | 31.2% | -34.03% |
| trending_down | 1 | 1.2% | 0.0% | -2.30% |
| trending_up | **0** | 0.0% | N/A | 0.00% |

**Trade concentration:** 80/81 (98.8%) in ranging
**Blank zone 상세:** trending_up에 706 bars가 있지만 trade 0건 — 이 구간에서 SMC+WT consensus가 발생하지 않거나, 발생하더라도 position occupancy로 차단됨

### BTC/USDT:USDT

| Regime | Trades | Share | Win Rate | Total Return |
|--------|--------|-------|----------|--------------|
| ranging | 53 | 100.0% | 41.5% | +11.74% |
| trending_up | **0** | 0.0% | N/A | 0.00% |
| trending_down | **0** | 0.0% | N/A | 0.00% |

**Trade concentration:** 53/53 (100.0%) in ranging
**Blank zone 상세:** trending 구간 자체가 극소(각 1.8%)하여 trade 기회가 구조적으로 부재

---

## Deliverable 4: Asset Regime Asymmetry

| Regime | SOL Share | BTC Share | Delta | Asymmetric? |
|--------|-----------|-----------|-------|-------------|
| ranging | 84.5% | 96.1% | **11.6%** | **YES** |
| trending_down | 7.8% | 1.8% | 6.1% | no |
| trending_up | 7.3% | 1.8% | 5.5% | no |
| unknown | 0.3% | 0.3% | 0.0% | no |

**SOL RDS:** 0.2740
**BTC RDS:** 0.0755
**RDS delta:** 0.1985

### 비대칭 해석

- BTC는 SOL보다 **12% 더 심하게 ranging 편중** (96% vs 85%)
- SOL은 trending 구간이 각 7-8%로 일정 수준 존재하나, BTC는 각 1.8%에 불과
- **RDS가 낮은 이유는 두 자산에서 동일하지만 (ranging 편중), 심각도가 다름**
- SOL의 RDS 0.27은 "낮지만 분포는 존재", BTC의 RDS 0.08은 "사실상 단일 regime"

---

## 구조적 판정: 탐지기 vs 시장

### 판정 질문: "RDS가 낮은 것은 RegimeDetector의 문제인가, 시장의 특성인가?"

| 근거 | 판정 |
|------|------|
| 양 자산에서 일관되게 ranging 80-96% | **시장 특성** (탐지기가 일방적으로 오분류할 확률 낮음) |
| 전 세그먼트에서 일관적 (train/FW1/FW2/holdout 모두 비슷) | **시장 특성** (데이터 특정 구간 문제 아님) |
| SOL과 BTC 간 편중도 차이 (85% vs 96%) | 시장별 구조 차이 반영, 탐지기 일관 작동 |
| trending 구간에서도 trade 0건 (특히 BTC) | 시장이 아니라 **전략(SMC+WT)**의 trending 구간 sensitivity 한계 가능성 |

**결론: 주요 원인은 시장의 구조적 ranging 편중이다.**
단, trending 구간에서 trade가 아예 없는 현상은 전략 특성도 기여하고 있을 수 있다.

---

## C-3 종료 후 재평가 질문 응답

### Q1: R-track이 구조적 불가인가?

**Yes.** 암호화폐 1H 시장은 구조적으로 ranging 편중이며, 현재 RegimeDetector(K-Means k=5) 기준으로 RDS 0.55 달성은 사실상 불가.

- SOL: ranging 84.5% → RDS 0.27 (달성까지 ranging을 ~42%로 낮춰야 하지만, 이는 시장 구조 자체 변경 필요)
- BTC: ranging 96.1% → RDS 0.08 (달성까지 ranging을 ~42%로 낮춰야 하지만, 사실상 불가)

### Q2: R-track 개선이 S-1보다 먼저 다룰 가치가 있는가?

**No.** R-track은 MAINTAINED_FAIL로 종료된다. 이 축에서 추가 투자는 정보 수익이 거의 없다. SOL root-cause(S-1)가 더 높은 개선 가능성을 가진다.

### Q3: R-track 진단 결과가 S-track 미해결보다 정보 수익이 큰가?

**Yes (진단으로서).** "RDS 0.55 불가"라는 결론 자체가 중요한 학습이다. 이것은 verdict 기준에서 RDS를 어떻게 취급해야 하는지에 대한 구조적 입력이 된다.

---

## 미해결 잔여 병목 (C-3 결과 반영)

| # | 병목 | 영향 자산 | 해결 가능성 | 후속 후보 |
|---|------|-----------|------------|-----------|
| 1 | SMC fire rate ~4% (1차 병목) | SOL+BTC | **가능** | S-1 (보조 신호원) |
| 2 | Position occupancy block ~28% | SOL+BTC | **가능** | 별도 분석 |
| 3 | RDS < 0.55 (regime 편중) | SOL+BTC | **구조적 불가** | MAINTAINED_FAIL 종료 |
| 4 | WF efficiency < 0.5 | SOL+BTC | **미정** | W-track (C-4) |

---

## Verdict 기준 재평가 권고

RDS가 구조적으로 달성 불가라면, 현재 verdict system의 7개 조건 중 1개(`RDS >= 0.55`)는 **현 환경에서 항상 FAIL**이다. 이것은 두 가지 선택지를 제시한다:

1. **RDS 기준 유지 + MAINTAINED_FAIL 수용**: verdict가 항상 이 조건에서 실패하지만, 다른 6개 조건만으로 전략 품질 판단
2. **RDS 기준 조정**: 별도 GO + 별도 근거가 필요 (R-4는 GO package에서 금지)

**이 선택은 C-3 scope 밖이며, 별도 판단이 필요하다.**

---

## R-track 면제 장부

| 필드 | 값 |
|------|---|
| `track_status` | maintained_fail |
| `closure_scope` | **current_environment_only** (현재 데이터 창·현재 detector 정의·현재 시장 구조 범위) |
| `reopen_trigger_required` | true |
| `permanent_truth` | **false** — 영구 법칙으로 봉인하지 않는다 |

### R-track 재개방 트리거

아래 중 하나가 충족되면 R-track 봉인을 재검토할 수 있다.

| # | 재개방 트리거 | 의미 |
|---|-----------|------|
| 1 | dominant regime share가 70% 이하로 하락 | 시장 구조 다변화 신호 |
| 2 | effective regime count 증가 (SOL≥4, BTC≥2) | blank zone 해소 조짐 |
| 3 | RegimeDetector 정의/파라미터 변경 | 관측 프레임 자체가 바뀐 경우 (별도 sub-GO 필요) |
| 4 | 데이터 창 변경 (다른 시장 국면으로 전환) | 관측 범위가 변한 경우 |

**재개방 절차**: 트리거 충족 확인 → 별도 explicit GO → 재진단 실행

---

## Run 증거 체인

| 필드 | 값 |
|------|---|
| `failed_run_id` | `bfy8xs8ak` |
| `failure_reason` | `AttributeError: 'TradeRecord' object has no attribute 'pnl_pct'` |
| `superseded_by` | `blyaioqjb` |
| `canonical_run_id` | `blyaioqjb` |
| `canonical_exit_code` | 0 |

---

## 상태 전이

```
C-3: GO -> CLOSED (MAINTAINED_FAIL: 양 자산 구조적 regime 편중)
active_path: NONE
held_path: SOL S-1 follow-up (재평가 대기)
next_unlocked_step: NONE (C-4 별도 GO 필요)
auto_advance_allowed: false
```

---

## 봉인

- C-3는 R-track regime diversity 진단으로 완료되었다
- **C-3 diagnostic success ≠ regime improvement complete** — 진단이 끝난 것이지 개선이 끝난 것이 아니다
- 양 자산 모두 **MAINTAINED_FAIL** — 시장의 구조적 ranging 편중이 원인이며, 탐지기 오류가 아니다
- SOL은 ranging 84.5%, BTC는 ranging 96.1%로, **RDS 0.55는 현 환경에서 달성 불가**
- BTC는 사실상 단일 regime 환경 (effective regime count = 1)
- SOL은 3개 regime이 존재하나 ranging이 압도적
- trade는 ranging 구간에 98-100% 집중되어 있다
- trending 구간에서 trade 0건은 전략(SMC+WT)의 trending sensitivity 한계도 기여할 수 있다
- RegimeDetector는 읽기 전용으로만 사용되었다 (수정 없음)
- B-1 core 이중 잠금(line + symbol)은 유지되었다
- Scope 위반은 0건이다
- C-4 이후 착수는 별도 explicit GO가 필요하다
- Verdict system의 RDS 기준 재평가는 C-3 scope 밖이다
