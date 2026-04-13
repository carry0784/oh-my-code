# Phase B B-3 — Completion Receipt

**완료일:** 2026-04-10
**판정:** MAINTAINED_FAIL (합법적 진단 종료)
**범위:** SOL + BTC cross-asset 전략 진단/관찰

---

## Completion Header

| 항목 | 값 |
|------|---|
| `sol_segments_complete` | **true** (train/fw1/fw2/holdout 4/4) |
| `btc_segments_complete` | **true** (train/fw1/fw2/holdout 4/4) |
| `cross_asset_compare_complete` | **true** (common + asset-specific 분리) |
| `terminal_status` | **MAINTAINED_FAIL** |

---

## B-3 종료 조건 판정

| 종료 유형 | 조건 | 충족 여부 |
|-----------|------|-----------|
| IMPROVED | 3 FAIL 원인 중 1개 이상 해소, 나머지 악화 없음 | **NO** — 진단 전용, 수정 미시행 |
| RESOLVED | 3 FAIL 원인 전체 해소, verdict=PASS 달성 | **NO** — 구조적 한계 확인 |
| **MAINTAINED_FAIL** | 개선 불가 확인, 구조적 한계 문서화 | **YES** — 2자산 동일 실패 서명 |

**적용 근거:** B-3는 진단/관찰 계층으로 제한되었으며, 전략 수정/threshold 완화/core 수정이 금지되었다. 진단 결과 3개 FAIL 원인이 모두 **구조적(시장 특성 + 전략 설계)**임이 cross-asset 비교로 확인되었다. MAINTAINED_FAIL은 B-3 GO 패키지에서 합법적 종료 조건으로 명시되었다.

---

## Cross-Asset 진단 요약표

| Track | SOL/USDT:USDT | BTC/USDT:USDT | 공통 병목 | 판정 |
|-------|---------------|---------------|-----------|------|
| F-1 Trade Scarcity | severe (FW2=5 trades) | severe (FW2=8 trades) | FW2 min_trades(10) 미달 | **MAINTAINED_FAIL** |
| F-2 WF Efficiency | -0.4959 (<0.5) | -2.9074 (<0.5) | OOS/IS 효율 구조적 부족 | **MAINTAINED_FAIL** |
| F-3 Regime Diversity | RDS=0.274 (ranging 84.5%) | RDS=0.076 (ranging 96.1%) | ranging 편중 (시장 구조) | **MAINTAINED_FAIL** |

---

## Failure Signature 비교

| 자산 | Failure Signature |
|------|-------------------|
| SOL/USDT:USDT | `scarcity=severe \| regime=severe_bias \| stability=cliff \| verdict=FAIL` |
| BTC/USDT:USDT | `scarcity=severe \| regime=severe_bias \| stability=cliff \| verdict=FAIL` |

**동일 서명**: 두 자산 모두 3차원(scarcity/regime/stability) 전부 동일 등급.
이는 FAIL 원인이 **특정 자산 고유 특성이 아닌 전략/시장 구조적 한계**임을 시사한다.

---

## Track별 상세 진단

### Track B-3A: Trade Scarcity

| 지표 | SOL | BTC |
|------|-----|-----|
| Total trades | 78 | 52 |
| Train trades | 46 | 24 |
| FW1 trades | 19 | 12 |
| FW2 trades | 5 (<10 MISS) | 8 (<10 MISS) |
| Holdout trades | 8 (<10 MISS) | 8 (<10 MISS) |
| FW2 density (per 100 bars) | 0.52 | 0.83 |
| Scarcity level | severe | severe |

**진단:** SMC+WaveTrend 2/2 consensus 조건이 960-bar 단기 구간에서 충분한 신호를 생성하지 못함. BTC가 SOL보다 FW2 밀도는 높으나 여전히 min_trades 미달. 이는 전략의 구조적 특성(높은 선별 기준)과 1H 타임프레임의 짧은 세그먼트가 결합된 결과.

### Track B-3B: Regime Diversity

| 지표 | SOL | BTC |
|------|-----|-----|
| Global RDS | 0.274 | 0.076 |
| Ranging % | 84.5% | 96.1% |
| Trending Down % | 7.9% | 1.8% |
| Trending Up % | 7.4% | 1.8% |
| Regime bias | severe_bias | severe_bias |

**진단:** 400일 기간의 1H 데이터에서 암호화폐 시장이 실제로 ranging 편중 상태임. BTC(96.1%)가 SOL(84.5%)보다 더 극심한 편중. RegimeDetector의 분류 기준이 아닌 **시장 자체의 특성**이 RDS 부족의 원인. RDS >= 0.55 기준은 현 시장 환경에서 달성 불가.

### Track B-3C: Forward Stability

| 지표 | SOL | BTC |
|------|-----|-----|
| Train fitness | 0.4158 | 0.4522 |
| FW1 fitness | 0.3435 | 0.8711 |
| FW2 fitness | 0.0000 | 0.0000 |
| Holdout fitness | 0.0000 | 0.0000 |
| FW1 degradation | -17.4% | +92.6% (비단조) |
| FW2 degradation | -100.0% | -100.0% |
| WF efficiency | -0.4959 | -2.9074 |
| WF consistency | 0.4 | 0.2 |
| Degradation profile | cliff | cliff |

**진단:** FW2에서 fitness=0.0으로 급락하는 cliff 패턴이 두 자산 모두에서 확인. BTC의 FW1이 train보다 높은 비단조 패턴은 특이하나, FW2/holdout에서 동일하게 붕괴. cliff의 근본 원인은 trade scarcity(min_trades 미달 → fitness=0.0 penalty)이며, 순수 성과 열화보다 **거래 부족에 의한 판정 불가**가 핵심.

---

## Common vs Asset-Specific Failures

| 구분 | 내용 |
|------|------|
| **Common (교집합)** | `forward_2_FITNESS_LOW(0.0000<0.25)` |
| **SOL-specific** | `RDS_LOW(0.2740<0.55)`, `WF_EFFICIENCY_LOW(-0.4959<0.5)` |
| **BTC-specific** | `RDS_LOW(0.0755<0.55)`, `WF_EFFICIENCY_LOW(-2.9074<0.5)` |

**해석:** 3개 reason code가 모두 양쪽 자산에 존재하나, 수치 차이로 인해 정확한 문자열 매칭에서는 FW2만 공통으로 분류됨. 실질적으로는 **3개 원인 모두 cross-asset 공통 병목**.

---

## 구조적 한계 요약

| # | 한계 | 근거 | 해소 가능성 |
|---|------|------|-------------|
| 1 | 1H 타임프레임에서 SMC+WT 2/2 consensus의 신호 희소성 | FW2(960 bars=40일)에서 SOL 5회, BTC 8회 | 전략 핵심 변경 없이는 불가 |
| 2 | 암호화폐 시장의 구조적 ranging 편중 | SOL 84.5%, BTC 96.1% | 시장 특성, 코드로 해소 불가 |
| 3 | 단기 세그먼트에서 min_trades 미달로 인한 fitness 0.0 penalty | FW2/holdout 모두 <10 trades | min_trades 하향(금지) 또는 신호 밀도 개선 필요 |
| 4 | WF efficiency 음수 (OOS < IS) | SOL -0.50, BTC -2.91 | 전략 일반화 능력 개선 필요 |

---

## 수행 내역

| 항목 | 수행 여부 |
|------|-----------|
| SOL full-cycle 실행 (9,600 candles) | DONE |
| BTC full-cycle 실행 (9,600 candles) | DONE |
| 4-segment 분할 (train/fw1/fw2/holdout) | DONE (양쪽) |
| WF 5-window 검증 | DONE (양쪽) |
| Regime 분석 (global + per-segment) | DONE (양쪽) |
| Scarcity 진단 | DONE (양쪽) |
| Stability 진단 | DONE (양쪽) |
| Cross-asset 비교 | DONE |
| Failure signature 비교 | DONE |
| Diagnosis log 출력 | DONE (`phase_b_b3_diagnosis_log.json`) |

---

## 비변경 확인

| 파일 | 변경 여부 |
|------|----------|
| `app/services/full_cycle_backtester.py` | 미변경 (B-1/B-2 core 봉인 유지) |
| `app/services/backtesting_engine.py` | 미변경 |
| `app/services/fitness_function.py` | 미변경 |
| `app/services/walk_forward_validator.py` | 미변경 |
| `app/services/regime_detector.py` | 미변경 |
| `strategies/smc_wavetrend_strategy.py` | 미변경 |
| verdict thresholds | 미변경 |

---

## B-1 회귀 기준선 검증

| 기준 | 결과 |
|------|------|
| leakage_violations = 0 | 0 (유지) |
| determinism = true | true (유지) |
| existing_module_changes = 0 | 0 (유지) |
| B-1 core code | 미변경 |

---

## 상태 전이

```
B-3: IN_PROGRESS -> CLOSED (MAINTAINED_FAIL)
next_unlocked_step: NONE (유지)
auto_advance_allowed: false (유지)
```

---

## 후속 금지 조항

1. B-3 결과를 근거로 한 **자동 후속 구현 금지** — 별도 GO 필요
2. verdict=FAIL을 해소하기 위한 **threshold 완화 금지**
3. B-1/B-2 core **수정 금지** — 별도 변경 제어 필요
4. MAINTAINED_FAIL을 **실패로 취급 금지** — 합법적 진단 종료임
5. 전략 수정/개선은 **별도 GO 패키지 + 사용자 승인** 필요

---

## 봉인

- 본 receipt는 B-3 진단 계층의 최종 종료 증거이다
- MAINTAINED_FAIL은 성공적인 진단 종료이며, 실패가 아니다
- 3개 FAIL 원인이 모두 구조적(시장 특성 + 전략 설계)임이 2자산 비교로 확인되었다
- 후속 전략 개선은 별도 GO 패키지 + 사용자 승인 없이 착수 불가
- B-1/B-2 core 및 verdict thresholds는 여전히 봉인 상태이다
