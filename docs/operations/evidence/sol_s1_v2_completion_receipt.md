# SOL S-1 V-2 — Completion Receipt

**완료일:** 2026-04-10
**판정:** PASS (C1C2_N2 — 모든 기준 충족)
**범위:** Candidate 1 + Candidate 2 결합 검증 backtest
**previous_chain:** SOL S-1 V-1 (INFORMATIVE_FAIL — scarcity → occupancy 병목 전환)
**selection_reason:** combined_capacity_uplift_after_bottleneck_shift

---

## Completion Header

| 항목 | 값 |
|------|---|
| `candidate` | Candidate 1+2 (Consensus window N=2 + Position sizing max_positions=2, size=1%) |
| `configs_tested` | A (baseline), B (C1_N1), C (C1C2_N1), D (C1C2_N2), E (C1C2_N3) |
| `fire_rate_uplift_achieved` | **true** (C1C2_N2: 4.37×, C1C2_N1: 2.96×, C1C2_N3: 5.35×) |
| `fitness_preserved` | **true** (C1C2_N2: 0.98× baseline) |
| `ecr_threshold_met` | **true** (C1C2_N2: 64.3% ≥ 60%) |
| `occupancy_block_resolved` | **true** (C1C2_N2: 35.7% ≤ 40%) |
| `fw2_min_trades_met` | **true** (C1C2_N2: 42 trades) |
| `holdout_min_trades_met` | **true** (C1C2_N2: 33 trades) |
| `max_dd_ratio` | 1.61× (≤ 2.0) |
| `win_rate_preservation` | 0.98× (≥ 0.80) |
| `overall_verdict` | **PASS** |
| `scope_violation` | **0건** |
| `b1_core_modified` | **false** |
| `auto_advance` | **false** |

---

## 핵심 해석 고정

```
V-2 PASS = Candidate 1+2 결합이 2축 동시 해소를 달성함을 확인
scarcity(fire rate 4.37×) + occupancy(ECR 64.3%, block 35.7%) 양축 동시 개선
목표 상태 S3 (Low scarcity / Low occupancy) 도달: C1C2_N1, C1C2_N2
단, fitness 절대 수준은 낮으며 (0.4428), 수익성 개선은 아직 미달
PASS는 "구조적 병목 해소"를 의미하며, "수익성 달성"을 의미하지 않음
```

---

## 결과 요약 — Best Config (C1C2_N2)

| Metric | Baseline (A) | Best (C1C2_N2) | 비율 | PASS 기준 | 판정 |
|--------|-------------|----------------|------|----------|------|
| Trades | 78 | 341 | 4.37× | ≥ 1.5× | ✓ |
| Fitness | 0.452 | 0.443 | 0.98× | ≥ 0.80× | ✓ |
| ECR | 86.7% | 64.3% | — | ≥ 60% | ✓ |
| Block rate | 13.3% | 35.7% | — | ≤ 40% | ✓ |
| FW2 trades | 7 | 42 | — | ≥ 10 | ✓ |
| Holdout trades | 8 | 33 | — | ≥ 10 | ✓ |
| Max DD | 0.93% | 1.50% | 1.61× | ≤ 2.0× | ✓ |
| Win rate | 0.308 | 0.302 | 0.98× | ≥ 0.80× | ✓ |

**6/6 Primary PASS + 2/2 Secondary PASS = FULL PASS**

---

## 전체 Config 비교

| Config | Trades | Fire↑ | Fitness | Fit↑ | ECR | Block% | State | 판정 |
|--------|--------|-------|---------|------|-----|--------|-------|------|
| A (baseline) | 78 | 1.00× | 0.452 | 1.00 | 86.7% | 13.3% | S1 | — |
| B (C1_N1) | 142 | 1.82× | 0.437 | 0.97 | 51.8% | 48.2% | S2 | ECR FAIL |
| C (C1C2_N1) | 231 | 2.96× | 0.450 | 1.00 | 84.3% | 15.7% | **S3** | **PASS** |
| D (C1C2_N2) | 341 | 4.37× | 0.443 | 0.98 | 64.3% | 35.7% | **S3** | **PASS** |
| E (C1C2_N3) | 417 | 5.35× | 0.452 | 1.00 | 50.8% | 49.2% | S2 | ECR FAIL |

---

## 2축 상태 전이 확인

```
[V-1 이전 (Baseline)]
  State = S1 (High scarcity / Low occupancy)

[V-1 이후 (Candidate 1 only)]
  State = S2 (Low scarcity / High occupancy)  ← bottleneck shift

[V-2 이후 (Candidate 1+2 결합)]
  C1C2_N1 → State = S3 (Low scarcity / Low occupancy)  ← 목표 도달
  C1C2_N2 → State = S3 (Low scarcity / Low occupancy)  ← 목표 도달, 최대 fire rate
  C1C2_N3 → State = S2 (Low scarcity / High occupancy)  ← N3에서 재포화
```

**S1 → S3 직행 달성 (S2를 거치지 않음) — C1C2_N1, C1C2_N2**

---

## Block Reason Taxonomy (Best: C1C2_N2)

| Block Code | Count | Ratio | 설명 |
|-----------|-------|-------|------|
| BLOCK_MAX_POSITIONS | 19 | 10.1% | 2개 slot 모두 점유 |
| BLOCK_SAME_DIRECTION | 134 | 70.9% | 동일 방향 중복 진입 차단 |
| BLOCK_OPPOSITE_DIRECTION | 36 | 19.0% | 반대 방향 진입 차단 |
| **Total** | **189** | **100%** | — |

**지배적 차단 원인: SAME_DIRECTION (70.9%)** — 동일 방향 consensus가 연속 발화 시 기존 포지션과 중복

---

## B vs C 비교 — Candidate 2 추가 효과

| Metric | B (C1 only) | C (C1+C2) | 변화 |
|--------|------------|-----------|------|
| Trades | 142 | 231 | +62.7% |
| ECR | 51.8% | 84.3% | +32.5pp |
| Block rate | 48.2% | 15.7% | -32.5pp |
| Fitness | 0.437 | 0.450 | +0.013 |
| Max DD | 1.46% | 0.95% | -0.51pp |

**동일 N=1에서 Candidate 2 추가 시: ECR +32.5pp, block rate -32.5pp, DD 개선**

---

## Segment 안정성 (Best: C1C2_N2)

| Segment | Trades | Fitness | min_trades | Return |
|---------|--------|---------|-----------|--------|
| train | 196 | 0.446 | OK | -0.85% |
| forward_1 | 70 | 0.436 | OK | -0.42% |
| forward_2 | 42 | 0.510 | OK | +0.20% |
| holdout | 33 | 0.440 | OK | -0.21% |

**4/4 segment min_trades 충족, fitness 0.436-0.510 범위, 세그먼트 간 안정적**

---

## PASS 조건 판정 상세

| # | 조건 | 기준 | 실측 | 판정 |
|---|------|------|------|------|
| 1 | fire_rate_uplift | ≥ 1.5× | 4.37× | ✓ PASS |
| 2 | fitness_ratio | ≥ 0.80 | 0.98 | ✓ PASS |
| 3 | ECR | ≥ 60% | 64.3% | ✓ PASS |
| 4 | occupancy_block_rate | ≤ 40% | 35.7% | ✓ PASS |
| 5 | FW2 + Holdout min_trades | ≥ 10 each | 42, 33 | ✓ PASS |
| 6 | max_dd_ratio | ≤ 2.0 | 1.61 | ✓ PASS |

---

## 헌법 검증

```
"신호 확장 후보는 capacity 완화 후보와 분리 승인 금지"
→ V-2는 Candidate 1 (신호 확장) + Candidate 2 (capacity 완화) 결합으로 검증
→ 헌법 준수 확인
```

---

## 경계 관찰 사항

1. **ECR은 64.3%로 PASS이나 마진은 4.3pp** — N=3으로 확장하면 50.8%로 FAIL 전환
2. **Block의 70.9%가 SAME_DIRECTION** — 동일 방향 연속 consensus의 구조적 특성
3. **수익률은 전 config 마이너스** — 구조적 병목 해소 ≠ 수익성 달성
4. **Fitness 절대값 0.44 수준** — penalty 없이 consistency 지배, return 기여 미미
5. **C1C2_N1도 PASS** — ECR 84.3%, block 15.7%로 N1이 더 여유, but fire rate 2.96× vs 4.37×

---

## 후속 경로

| 단계 | 명칭 | 상태 |
|------|------|------|
| V-1 | Candidate 1 단독 | CLOSED (INFORMATIVE_FAIL) |
| **V-2** | **Candidate 1+2 결합** | **CLOSED (PASS)** |
| **V-3** | Shadow 검증 | **UNLOCKED (V-2 PASS로 해제)** |
| V-4 | Paper 검증 | LOCKED (V-3 PASS 필요) |

---

## Run 증거 체인

| 필드 | 값 |
|------|---|
| `canonical_run_id` | V-2 실행 (단일 성공) |
| `canonical_exit_code` | 0 |
| `failed_run_count` | 0 |
| `log_file` | `sol_s1_v2_backtest_log.json` |
| `script` | `scripts/sol_s1_v2_combined_backtest.py` |

---

## Best Config 잠금

```
best_config: C1C2_N2
consensus_window: N=2
max_positions: 2
position_size_pct: 1.0%
SL: 2% / TP: 4% (유지)
총 시장 노출: 2% max (1% × 2 slots)
```

---

## 아이디어 반영 기록

| 아이디어 | 반영 | 시기 |
|----------|------|------|
| ECR 기반 상태 전이 (Green/Yellow/Red) 도입 | V-3 설계서에서 구현 | V-3 설계 시 |
| SAME_DIRECTION을 독립 병목으로 승격 | V-3 관측 필드 분리 | V-3 설계 시 |
| N2 주력 / N1 안전판 이중 운영 설계 | V-3 shadow 구조에 반영 | V-3 설계 시 |
| 수익성 트랙 분리 고정 | 별도 트랙으로 분리, 본 체인에 혼입 금지 | 즉시 |

---

## 봉인

- V-2는 Candidate 1 + Candidate 2 결합 검증으로 **PASS** 판정이다
- Best config = C1C2_N2 (N=2, max_positions=2, size=1%)
- 6/6 Primary + 2/2 Secondary 모든 기준 충족
- 2축 상태 전이 S1 → S3 달성 (C1C2_N1, C1C2_N2)
- Candidate 2의 occupancy 완화 효과 확인 (B→C: ECR +32.5pp)
- ECR 마진 4.3pp — N=3 확장은 FAIL (design boundary 확인)
- 수익률 개선은 미달 — 구조적 병목 해소 ≠ 수익성 달성
- V-3 Shadow 검증이 UNLOCKED 되었다
- auto_advance는 금지이다
