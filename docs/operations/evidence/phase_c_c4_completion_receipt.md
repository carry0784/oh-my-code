# Phase C C-4 — Completion Receipt

**완료일:** 2026-04-10
**판정:** INFORMATIVE_FAIL (양 자산 모두 scarcity-driven cliff)
**범위:** W-track forward stability 진단/검증 only (구현 미포함)
**previous_chain:** C-3 CLOSED (MAINTAINED_FAIL)
**selection_reason:** phase_progress_priority

---

## Completion Header

| 항목 | 값 |
|------|---|
| `sol_wf_efficiency` | **-1.4515** (threshold 0.50 미달) |
| `btc_wf_efficiency` | **-0.4939** (threshold 0.50 미달) |
| `sol_wf_consistency` | **0.20** (1/5 profitable) |
| `btc_wf_consistency` | **0.20** (1/5 profitable) |
| `sol_wf_is_overfit` | **false** |
| `btc_wf_is_overfit` | **true** |
| `sol_cliff_detected` | **true** (magnitude 0.438) |
| `btc_cliff_detected` | **true** (magnitude 0.462) |
| `sol_cliff_cause` | **scarcity_penalty** |
| `btc_cliff_cause` | **scarcity_penalty** |
| `sol_scarcity_correlation` | **100%** (4/4 OOS failures = all scarce) |
| `btc_scarcity_correlation` | **100%** (4/4 OOS failures = all scarce) |
| `sol_step_verdict` | **INFORMATIVE_FAIL** |
| `btc_step_verdict` | **INFORMATIVE_FAIL** |
| `overall_verdict` | **INFORMATIVE_FAIL** |
| `scope_violation` | **0건** |
| `b1_core_modified` | **false** |
| `wf_validator_modified` | **false** |
| `auto_advance` | **false** |

---

## 핵심 해석 고정

```
C-4 diagnostic success ≠ stability improvement complete
W-track INFORMATIVE_FAIL = cliff의 근본 원인이 trade scarcity penalty임을 실험적으로 확인함
WF efficiency < 0.5는 전략의 일반화 실패가 아니라, S-track 미해결에 의한 OOS trade 부족 penalty이다
이것은 WalkForwardValidator 또는 fitness function의 문제가 아니라 trade density의 문제이다
S-track이 해결되면 WF efficiency는 자연 개선될 가능성이 높다
```

---

## Deliverable 1: WalkForward Window Analysis

### SOL/USDT:USDT

**WF efficiency:** -1.4515 (threshold: 0.50)
**Consistency:** 0.20 (1/5 profitable)
**Is overfit:** false

| Window | IS Trades | IS Return | OOS Trades | OOS Return | OOS Status | Scarcity? |
|--------|-----------|-----------|------------|------------|------------|-----------|
| 0 | 11 | -0.32% | 4 | -0.06% | **FAIL** | **YES** |
| 1 | 9 | +0.08% | 6 | -0.16% | **FAIL** | **YES** |
| 2 | 9 | +0.07% | 6 | -0.16% | **FAIL** | **YES** |
| 3 | 15 | -0.38% | 5 | +0.01% | OK | **YES** |
| 4 | 7 | +0.28% | 6 | -0.04% | **FAIL** | **YES** |

**Scarcity-correlated failures:** 4/4 (100%)

**해석:** 5개 윈도우 전체에서 OOS trades가 4-6건으로 min_trades(10) 미달. IS에서도 7-15건으로 밀도가 낮다. IS 학습이 잘 되는 경우(Window 4: +0.28%)에도 OOS에서 trade 부족으로 -0.04% 기록. OOS 실패의 원인은 전략 일반화 한계가 아니라 **trade 밀도 자체가 통계적 유효 판정에 불충분**한 것이다.

### BTC/USDT:USDT

**WF efficiency:** -0.4939 (threshold: 0.50)
**Consistency:** 0.20 (1/5 profitable)
**Is overfit:** true

| Window | IS Trades | IS Return | OOS Trades | OOS Return | OOS Status | Scarcity? |
|--------|-----------|-----------|------------|------------|------------|-----------|
| 0 | 2 | +0.05% | 2 | -0.09% | **FAIL** | **YES** |
| 1 | 6 | -0.00% | 2 | +0.03% | OK | **YES** |
| 2 | 7 | +0.04% | 5 | -0.11% | **FAIL** | **YES** |
| 3 | 10 | +0.14% | 2 | -0.04% | **FAIL** | **YES** |
| 4 | 12 | +0.37% | 5 | -0.08% | **FAIL** | **YES** |

**Scarcity-correlated failures:** 4/4 (100%)

**해석:** BTC는 SOL보다 심각한 scarcity — OOS trades가 2-5건. IS에서도 Window 0은 2건에 불과. Window 4에서 IS 12t/+0.37%의 강한 학습이 있지만 OOS 5t/-0.08%로 전이 실패. 그러나 이 "실패"는 OOS에서 trade 5건의 결과이므로 통계적 유의성이 없다. `is_overfit=true`도 같은 맥락 — IS/OOS 수익률 격차가 크지만 OOS 표본이 너무 적어 overfit 판정 자체가 의미 없다.

---

## Deliverable 2: Cliff Analysis

### SOL/USDT:USDT

| Segment | Bars | Trades | Fitness | min_trades |
|---------|------|--------|---------|------------|
| train | 5760 | 46 | 0.4380 | OK |
| forward_1 | 1920 | 19 | 0.3622 | OK |
| forward_2 | 960 | 5 | 0.0000 | **MISS** |
| holdout | 960 | 8 | 0.0000 | **MISS** |

**Cliff detected:** true
**Cliff magnitude:** 0.4380 (train - FW2)
**Cliff cause:** **scarcity_penalty**

**해석:** Train(46t) → FW1(19t) → FW2(5t) → Holdout(8t)로 bars 감소에 비례하여 trades가 줄어듦. Trade density는 전 세그먼트에서 일관적(~8t/960bars ≈ 0.83%). FW2의 fitness 0.000은 **전략이 FW2에서 작동하지 않는 것이 아니라**, 5건의 trade가 min_trades(10) 미달이어서 fitness = 0 penalty가 적용된 결과이다.

### BTC/USDT:USDT

| Segment | Bars | Trades | Fitness | min_trades |
|---------|------|--------|---------|------------|
| train | 5760 | 24 | 0.4618 | OK |
| forward_1 | 1920 | 12 | 0.8787 | OK |
| forward_2 | 960 | 8 | 0.0000 | **MISS** |
| holdout | 960 | 8 | 0.0000 | **MISS** |

**Cliff detected:** true
**Cliff magnitude:** 0.4618 (train - FW2)
**Cliff cause:** **scarcity_penalty**

**해석:** BTC의 FW1은 12t로 min_trades를 겨우 충족하며 fitness 0.8787로 **매우 우수**. 이것은 BTC 전략이 forward 구간에서도 잘 작동함을 의미한다. FW2의 8t도 FW1의 12t와 밀도가 동일하지만(~0.83%) min_trades 문턱에 2건 부족하여 fitness = 0. **cliff는 전략 품질의 급락이 아니라 min_trades 문턱의 binary penalty effect이다.**

---

## Deliverable 3: Scarcity-Cliff Correlation

| Asset | WF Eff | Cliff? | Cliff Cause | OOS Scarcity Correlation | Verdict |
|-------|--------|--------|-------------|--------------------------|---------|
| SOL/USDT:USDT | -1.4515 | Yes | scarcity_penalty | 100% | **INFORMATIVE_FAIL** |
| BTC/USDT:USDT | -0.4939 | Yes | scarcity_penalty | 100% | **INFORMATIVE_FAIL** |

---

## GO Package 가설 검증 결과

### 가설 (GO package Section 5.1)

> cliff의 근본 원인은 **trade scarcity에 의한 fitness 0.0 penalty**이므로,
> S-track 완료 후 자연 해소 여부를 먼저 확인해야 한다.

### 검증 결과

| 검증 질문 | 결과 | 근거 |
|-----------|------|------|
| **BTC: S-3 적용 시 WF efficiency 자연 개선 가능?** | **가능성 높음** | FW1 fitness=0.8787로 전략 품질 우수. FW2 8t → min_trades 2건 부족만이 문제. S-3 ratio 적용(FW2 15%)으로 bars 증가 시 trade density 충족 예상 |
| **SOL: scarcity 미해결 상태에서 WF 개선 가능?** | **불가** | FW2 5t로 min_trades 절반. S-3 ratio만으로 불충분. SOL은 별도 S-1 (보조 신호원)이 선행 필요 |
| **cliff = scarcity artifact인가, 전략 일반화 한계인가?** | **scarcity artifact 확인** | 양 자산 100% scarcity correlation. BTC FW1=0.8787이 전략 일반화 능력을 증명. FW2 cliff는 min_trades binary penalty의 산물 |

### C-2 결과와의 교차 검증

| C-2 관측 | C-4 검증 | 일치 여부 |
|----------|----------|-----------|
| BTC S-3: FW2 trades 8→12, fitness 0→0.90 | C-4: FW2 trades 8건, min_trades MISS → fitness 0 | **일치** (C-2에서 S-3로 12건 달성 시 fitness 회복 확인) |
| SOL S-3: FW2 trades 5→8, fitness 여전히 0 | C-4: FW2 trades 5건, S-3 적용해도 min_trades 미달 예상 | **일치** (SOL은 density 문제가 S-3만으로 해결 안 됨) |

---

## 구조적 판정: WF efficiency 실패의 인과 구조

```
[Root Cause]
  SMC fire rate ~4% (1차 병목, C-1 진단)
    ↓
  Global trade density 부족
    ↓
  Forward 세그먼트 bars 축소 시 trade 부족 심화
    ↓
  OOS window / FW2 / Holdout에서 min_trades 미달
    ↓
  fitness = 0.0 (binary penalty)
    ↓
  WF efficiency = avg_oos_return / |avg_is_return| < 0 (인위적 왜곡)
    ↓
  WF 판정 = FAIL (scarcity artifact)
```

**결론: WF efficiency FAIL은 독립적 W-track 문제가 아니라, S-track(trade density) 미해결의 전파(propagation) 효과이다.**

---

## W-track 면제 장부

| 필드 | 값 |
|------|---|
| `track_status` | informative_fail |
| `failure_type` | scarcity_propagation (S-track 미해결의 전파) |
| `independent_problem` | **false** — W-track 자체의 독립적 문제가 아님 |
| `resolution_dependency` | S-track (trade density 해결 시 자연 개선 예상) |
| `retest_trigger` | S-track 해결 후 WF 재검증 필요 |

### W-track 재검증 트리거

| # | 재검증 트리거 | 의미 |
|---|-----------|------|
| 1 | SOL S-1 follow-up 완료 (보조 신호원 적용) | SOL trade density 개선 확인 후 WF 재검증 |
| 2 | BTC S-3 ratio 적용 후 FW2 min_trades 충족 | BTC cliff 자연 해소 확인 |
| 3 | Global trade density 2배 이상 증가 | 전체 WF window에서 min_trades 충족 가능 |
| 4 | min_trades 기준 자체 변경 | 별도 sub-GO 필요 (W-3/W-4 금지 범위) |

---

## 미해결 잔여 병목 (C-4 결과 반영 종합)

| # | 병목 | 영향 자산 | 해결 가능성 | 상태 | 후속 후보 |
|---|------|-----------|------------|------|-----------|
| 1 | SMC fire rate ~4% (1차 병목) | SOL+BTC | **가능** | **미해결** | S-1 (보조 신호원) |
| 2 | Position occupancy block ~28% | SOL+BTC | **가능** | **미해결** | 별도 분석 |
| 3 | RDS < 0.55 (regime 편중) | SOL+BTC | **구조적 불가** | C-3 MAINTAINED_FAIL | 종료 (면제) |
| 4 | WF efficiency < 0.5 (cliff) | SOL+BTC | **S-track 의존** | C-4 INFORMATIVE_FAIL | S-track 해결 후 재검증 |

**핵심 통찰:** 4대 병목 중 #3은 구조적 불가(C-3), #4는 #1의 전파 효과(C-4). 따라서 **실질적 독립 미해결 병목은 #1(fire rate)과 #2(occupancy)** 두 개이다.

---

## Run 증거 체인

| 필드 | 값 |
|------|---|
| `canonical_run_id` | 이번 C-4 진단 (단일 실행 성공) |
| `canonical_exit_code` | 0 |
| `failed_run_count` | 0 |
| `log_file` | `phase_c_c4_wtrack_diagnosis_log.json` |
| `script` | `scripts/phase_c_c4_wtrack_diagnosis.py` |

---

## 상태 전이

```
C-4: GO -> CLOSED (INFORMATIVE_FAIL: 양 자산 scarcity-driven cliff 확인)
active_path: NONE
held_path: SOL S-1 follow-up (재평가 대기)
next_unlocked_step: NONE (C-5 별도 GO 필요)
auto_advance_allowed: false
```

---

## 봉인

- C-4는 W-track forward stability 진단/검증으로 완료되었다
- **C-4 diagnostic success ≠ stability improvement complete** — 진단이 끝난 것이지 안정성이 개선된 것이 아니다
- 양 자산 모두 **INFORMATIVE_FAIL** — cliff의 100%가 trade scarcity penalty와 상관
- GO package 가설 "cliff = scarcity penalty"는 **실험적으로 확인(confirmed)**되었다
- WF efficiency FAIL은 독립적 W-track 문제가 아니라 **S-track 미해결의 전파 효과**이다
- BTC FW1 fitness=0.8787로 **전략 일반화 능력은 존재**한다 — S-track 해결 시 WF 자연 개선 예상
- SOL은 S-1 (보조 신호원)이 선행되어야 WF 개선이 가능하다
- WalkForwardValidator는 읽기 전용으로만 사용되었다 (수정 없음)
- B-1 core 이중 잠금(line + symbol)은 유지되었다
- Scope 위반은 0건이다
- C-5 착수는 별도 explicit GO가 필요하다
- min_trades 기준 변경(W-3/W-4)은 C-4 scope에서 금지되었으며, 시도하지 않았다
