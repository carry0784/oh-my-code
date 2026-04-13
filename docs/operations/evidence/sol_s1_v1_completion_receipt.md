# SOL S-1 V-1 — Completion Receipt

**완료일:** 2026-04-10
**판정:** INFORMATIVE_FAIL (fire rate 달성, occupancy 병목 전환)
**범위:** Candidate 1 (Consensus window 확장) 단독 backtest
**previous_chain:** SOL S-1 Root-Cause Analysis
**selection_reason:** lowest_blast_radius_rootcause_test

---

## Completion Header

| 항목 | 값 |
|------|---|
| `candidate` | Candidate 1 (Consensus window expansion) |
| `configs_tested` | N=0 (baseline), N=1, N=2, N=3 |
| `fire_rate_uplift_achieved` | **true** (N=1: 1.93×, N=2: 2.70×, N=3: 3.11×) |
| `fitness_preserved` | **true** (N=3: 1.29× baseline) |
| `fw2_scarcity_resolved` | **true** (N=1부터 min_trades 전 세그먼트 충족) |
| `occupancy_guard_passed` | **false** (48-73% > 20% limit) |
| `overall_verdict` | **INFORMATIVE_FAIL** |
| `design_value` | **높음** — 후속 결합 검증 입력으로 승격 |
| `scope_violation` | **0건** |
| `b1_core_modified` | **false** |
| `auto_advance` | **false** |

---

## 핵심 해석 고정

```
V-1 INFORMATIVE_FAIL ≠ Candidate 1 폐기
V-1은 scarcity 해소 방향이 유효함을 확인하고, 병목이 occupancy로 전환됨을 드러낸 진단 성공이다
Candidate 1 단독 채택은 불가하지만, 설계 가치는 높으며 후속 결합 검증의 핵심 입력이다
신호 확장만으로는 운영 가능한 성과 증가에 도달하지 못한다 — capacity 관리 동반 필요
```

---

## 결과 요약

| Metric | N=0 | N=1 | N=2 | N=3 |
|--------|-----|-----|-----|-----|
| Trades | 81 | 156 | 219 | 252 |
| Fire rate uplift | 1.00× | **1.93×** | **2.70×** | **3.11×** |
| Fitness | 0.343 | 0.328 | 0.332 | **0.442** |
| Fitness ratio | 1.00 | 0.96 | 0.97 | **1.29** |
| Block rate | 13.3% | **48.2%** | **63.2%** | **73.1%** |
| FW2 trades | 5 | 17 | 27 | 30 |
| FW2 min_trades | **MISS** | OK | OK | OK |
| Holdout fitness | 0.000 | **0.899** | **0.898** | **0.894** |

---

## 병목 전환 확인

```
[V-1 이전]
  지배 병목 = scarcity (SMC sparsity × same-bar consensus)
  2차 병목 = occupancy (13.3%)

[V-1 이후 (Candidate 1 적용 시)]
  지배 병목 = occupancy (48-73%)     ← 전환됨
  해소 병목 = scarcity (1.93-3.11× 개선)
```

**상태 전이: scarcity-dominant → occupancy-dominant**

---

## 판정 실패 상세

| Config | Fire rate ≥ 1.5× | Fitness ≥ 0.80× | Block ≤ 20% | 판정 |
|--------|-----------------|-----------------|-------------|------|
| N=1 | 1.93× ✓ | 0.96 ✓ | 48.2% **✗** | FAIL |
| N=2 | 2.70× ✓ | 0.97 ✓ | 63.2% **✗** | FAIL |
| N=3 | 3.11× ✓ | 1.29 ✓ | 73.1% **✗** | FAIL |

**3개 config 모두 fire rate + fitness PASS, occupancy만 FAIL**

---

## 아이디어 반영 기록

| 아이디어 | 반영 | 시기 |
|----------|------|------|
| Executable Consensus Ratio KPI 승격 | V-2에서 정식 KPI로 채택 | 즉시 |
| scarcity × occupancy 2축 상태 전이 | V-2 설계서에 반영 | 즉시 |
| 신호 확장 + capacity 완화 분리 승인 금지 헌법 | V-2 GO에 명시 | 즉시 |
| occupancy 원인별 차단 코드 의무화 | V-2 스크립트에 구현 | 즉시 |

---

## 후속 경로

| 단계 | 명칭 | 상태 |
|------|------|------|
| **V-2** | Candidate 1 + Candidate 2 결합 검증 | **다음 GO 대상** |
| V-3 | Shadow 검증 | LOCKED (V-2 PASS 필요) |
| V-4 | Paper 검증 | LOCKED (V-3 PASS 필요) |

---

## Run 증거 체인

| 필드 | 값 |
|------|---|
| `canonical_run_id` | V-1 실행 (단일 성공) |
| `canonical_exit_code` | 0 |
| `failed_run_count` | 1 (PerformanceReport.get 수정 전) |
| `log_file` | `sol_s1_v1_backtest_log.json` |
| `script` | `scripts/sol_s1_v1_consensus_window_backtest.py` |

---

## 봉인

- V-1은 Candidate 1 (Consensus window 확장) 단독 backtest로 완료되었다
- **INFORMATIVE_FAIL**: fire rate + fitness 달성, occupancy 병목 전환
- Candidate 1 단독 채택은 불가하지만, 설계 가치는 높다
- 병목이 scarcity-dominant에서 occupancy-dominant로 전환됨을 확인하였다
- FW2/Holdout scarcity는 N=1부터 해소됨을 확인하였다
- 후속 V-2는 Candidate 1 + Candidate 2 결합 검증이다
- auto_advance는 금지이다
