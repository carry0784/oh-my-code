# SOL S-1 V-2 — Candidate 1+2 Combined Verification Design

**작성일:** 2026-04-10
**범위:** Consensus window expansion + Position sizing 결합 backtest
**전제:** V-1 INFORMATIVE_FAIL (병목 전환: scarcity → occupancy)

---

## 1. V-2 목적

V-1에서 Candidate 1(consensus window 확장)이 fire rate와 fitness를 개선하지만 occupancy block rate를 48-73%로 폭증시킴을 확인했다. V-2는 **Candidate 2(position sizing 분할)를 결합하여 occupancy 병목을 완화**하고, 양쪽 개선이 동시에 작동하는지 검증한다.

---

## 2. Candidate 2 개입 위치

### 2.1 현재 구조

```
[Consensus Signal]
  → [Position Check: max_positions=1]
     → BLOCKED (position occupied)  ← occupancy 병목
     → ENTRY (position available)
        → SL 2% / TP 4%
        → 평균 ~4 bars 점유
```

### 2.2 Candidate 2 개입

```
[Consensus Signal]
  → [Position Check: max_positions=2]  ← 변경점
     → BLOCKED (2 positions occupied) ← 완화된 병목
     → ENTRY (slot available)
        → position_size_pct=1.0 (기존 2.0의 절반)  ← 변경점
        → SL 2% / TP 4% (유지)
```

**핵심 변경 2가지:**
1. `max_positions`: 1 → 2 (동시 포지션 2개 허용)
2. `position_size_pct`: 2.0 → 1.0 (각 포지션 크기 절반)

**총 시장 노출은 동일:** 2% × 1 = 1% × 2 = 2% max exposure

---

## 3. 비교군 설계

### 3.1 Config Matrix

| Config | Consensus Window | max_positions | position_size_pct | 설명 |
|--------|-----------------|---------------|-------------------|------|
| **A** | N=0 (baseline) | 1 | 2.0 | 현재 전략 그대로 |
| **B** | N=1 | 1 | 2.0 | V-1 best uplift (Candidate 1 only) |
| **C** | N=1 | 2 | 1.0 | **결합: Candidate 1 + 2** |
| **D** | N=2 | 2 | 1.0 | **결합: 더 넓은 window** |
| **E** | N=3 | 2 | 1.0 | **결합: 최대 window** |

### 3.2 비교 논리

- A vs B: V-1 재확인 (Candidate 1 단독 효과)
- B vs C: **Candidate 2 추가 효과** (동일 N에서 occupancy 완화)
- C vs D vs E: **결합 상태에서 N 확장 효과**

---

## 4. KPI 정의

### 4.1 Primary KPI: Executable Consensus Ratio (ECR)

```
ECR = executable_trades / consensus_signals × 100
```

| 상태 | 의미 |
|------|------|
| consensus_generated | window 내 SMC+WT 동시 발화 bar 수 |
| consensus_executable | 포지션 slot이 비어서 실제 진입 가능한 consensus |
| consensus_blocked | 포지션 점유로 차단된 consensus |
| **ECR** | **실행 가능 비율** |

**V-2 PASS 기준: ECR ≥ 60%** (baseline ECR = 86.7%)

### 4.2 Secondary KPIs

| KPI | 정의 | PASS 기준 |
|-----|------|----------|
| fire_rate_uplift | trades / baseline_trades | ≥ 1.5× |
| fitness_ratio | fitness / baseline_fitness | ≥ 0.80 |
| occupancy_block_rate | blocked / consensus × 100 | ≤ 40% |
| fw2_min_trades | FW2 segment trades ≥ 10 | true |
| holdout_min_trades | Holdout segment trades ≥ 10 | true |
| max_dd_ratio | max_dd / baseline_max_dd | ≤ 2.0 |
| win_rate_preservation | win_rate / baseline_win_rate | ≥ 0.80 |

---

## 5. Occupancy Block Reason Taxonomy

### 5.1 차단 코드

| Code | 의미 | 발생 조건 |
|------|------|----------|
| `BLOCK_MAX_POSITIONS` | 최대 동시 포지션 초과 | open_positions ≥ max_positions |
| `BLOCK_SAME_DIRECTION` | 동일 방향 중복 진입 | 기존 포지션과 같은 방향 consensus |
| `BLOCK_OPPOSITE_DIRECTION` | 반대 방향 진입 (헤지) | 기존 포지션과 반대 방향 consensus |

### 5.2 차단 추적 필드

V-2 스크립트에서 매 bar 기록:
```
{
  "bar": int,
  "consensus_dir": int,
  "open_positions": int,
  "block_code": str | None,
  "slots_used": int,
  "slots_available": int
}
```

---

## 6. 2축 상태 전이표

| 상태 | Scarcity | Occupancy | 의미 |
|------|----------|-----------|------|
| **S1** | High | Low | 신호 부족, 슬롯 여유 (baseline) |
| **S2** | Low | High | 신호 충분, 슬롯 부족 (V-1 Candidate 1) |
| **S3** | Low | Low | **목표 상태** (V-2 Candidate 1+2) |
| **S4** | High | High | 최악 (해당 없음) |

**V-2 목표: S1 → S3 직행 (S2를 거치지 않음)**

---

## 7. PASS/FAIL 판정 구조

### 7.1 PASS 조건 (모두 충족)

1. fire_rate_uplift ≥ 1.5×
2. fitness_ratio ≥ 0.80
3. ECR ≥ 60%
4. occupancy_block_rate ≤ 40%
5. FW2 + Holdout min_trades 충족
6. max_dd_ratio ≤ 2.0

### 7.2 INFORMATIVE_FAIL

- fire rate + fitness 달성, but ECR or block rate 미충족
- 또는 segment 불균형

### 7.3 BLOCK

- fitness < 0.80× baseline
- max_dd > 2.0× baseline
- win_rate < 0.80× baseline

---

## 8. 후보 1 + 2 결합 종료 조건

아래 중 하나라도 충족 시 결합 체인 중단:

1. fitness < 0.80 × baseline (모든 config에서)
2. max_dd > 2.5 × baseline
3. ECR < 40% (occupancy 완화 효과 없음)
4. FW2 + Holdout min_trades 미달 (모든 config에서)

---

## 9. 헌법 강화 조항

```
신호 확장 후보는 capacity 완화 후보와 분리 승인 금지.
signal uplift와 capacity uplift를 결합 검증 없이 단독 채택하지 않는다.
```

---

## 봉인

- V-2는 Candidate 1 + Candidate 2 결합 검증이다
- Executable Consensus Ratio (ECR)를 정식 KPI로 채택한다
- occupancy block reason taxonomy를 의무화한다
- 2축 상태 전이표 (scarcity × occupancy)를 운영 기준으로 사용한다
- 목표 상태는 S3 (Low scarcity / Low occupancy)이다
- 신호 확장 후보는 capacity 완화 후보와 분리 승인 금지한다
