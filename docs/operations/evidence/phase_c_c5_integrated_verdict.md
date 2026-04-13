# Phase C C-5 — Integrated Verdict

**작성일:** 2026-04-10
**범위:** C-1~C-4 종합 verdict + track별 상태 + 독립 미해결 병목 ledger
**Overall Phase C:** diagnostic success / remediation pending
**selection_reason:** chain_closure_priority

---

## 1. Phase C 체인 요약

Phase C는 FullCycle 전략의 multi-track 병목 진단을 목표로 한 4단계 진단 체인이다.

| Step | Track | 판정 | 핵심 발견 |
|------|-------|------|----------|
| **C-1** | S-track | CLOSED (SUCCESS) | 4대 병목 구조 식별: fire rate ~4%, occupancy ~28%, scarcity FW2, regime 편중 |
| **C-2** | S-track | SEALED (ASYMMETRIC) | S-3 density uplift: BTC=conditional keep (FW2 fitness 0→0.90), SOL=reject (min_trades 미달) |
| **C-3** | R-track | CLOSED (MAINTAINED_FAIL) | Regime 편중은 시장 구조적 특성 (ranging 85-96%). RDS 0.55 달성 불가 |
| **C-4** | W-track | CLOSED (INFORMATIVE_FAIL) | Cliff = scarcity penalty (100% correlation). 독립 W-track 결함 아님 |

---

## 2. Track별 상태 총괄

### 2.1 S-track (Trade Density / Signal Scarcity)

| 항목 | 값 |
|------|---|
| `track_status` | **unresolved_root_cause** |
| `propagated_failure` | **no** (원인 자체) |
| `independent_problem` | **yes** |
| `severity` | **primary** — Phase C에서 식별된 1차 병목 |
| `affected_assets` | SOL + BTC (SOL이 더 심각) |

**요약:** SMC fire rate ~4%가 전체 병목의 root cause이다. 이로 인해 forward 세그먼트에서 trade density가 부족하고, WF OOS window에서 min_trades 미달이 발생하며, fitness = 0 penalty가 적용되어 WF efficiency가 음수가 된다.

**S-3 실험 결과:**
- BTC: S-3 ratio(FW2 15%)로 FW2 trades 8→12, fitness 0→0.90 → **conditional keep (BTC lane only)**
- SOL: S-3 ratio로 FW2 trades 5→8 → min_trades 미달 지속 → **reject**

**후속 필요:** SOL S-1 root-cause follow-up (보조 신호원)

### 2.2 R-track (Regime Diversity)

| 항목 | 값 |
|------|---|
| `track_status` | **maintained_fail** |
| `propagated_failure` | **no** (독립 구조적 한계) |
| `independent_problem` | **yes (but structurally unresolvable)** |
| `closure_scope` | current_environment_only |
| `permanent_truth` | **false** |
| `reopen_trigger_required` | true |

**요약:** 암호화폐 1H 시장은 구조적으로 ranging 편중(SOL 84.5%, BTC 96.1%)이다. RDS 0.55는 현 환경에서 달성 불가. 이것은 RegimeDetector의 문제가 아니라 시장의 특성이다.

**R-track 재개방 트리거:**
1. dominant regime share ≤ 70%
2. effective regime count 증가 (SOL≥4, BTC≥2)
3. RegimeDetector 정의/파라미터 변경 (별도 sub-GO 필요)
4. 데이터 창 변경 (다른 시장 국면으로 전환)

### 2.3 W-track (Forward Stability / WF Efficiency)

| 항목 | 값 |
|------|---|
| `track_status` | **informative_fail** |
| `propagated_failure` | **yes** (S-track scarcity의 전파 효과) |
| `independent_problem` | **no** |
| `resolution_dependency` | S-track |

**요약:** WF efficiency 음수(-1.45 SOL, -0.49 BTC)와 FW2 cliff는 전략 일반화 실패가 아니다. OOS window 전체에서 trades < min_trades이며, cliff의 100%가 scarcity penalty와 상관한다. BTC FW1 fitness=0.8787로 전략 일반화 능력은 존재한다.

**인과 체인:**
```
S-track fire rate ~4% (root cause)
  → forward 세그먼트 trade density 부족
    → OOS window / FW2 min_trades 미달
      → fitness = 0.0 (binary penalty)
        → WF efficiency 음수 (인위적 왜곡)
          → W-track FAIL (scarcity artifact)
```

**W-track 재검증 트리거:**
1. SOL S-1 follow-up 완료 후
2. BTC S-3 ratio 적용 후 FW2 min_trades 충족 확인
3. Global trade density 2× 이상 증가

---

## 3. 독립 미해결 병목 Ledger

Phase C 진단 결과, **실질적 독립 미해결 병목은 2개**로 축소되었다.

| # | 병목 | 영향 자산 | 해결 가능성 | 독립성 | track | 후속 후보 |
|---|------|-----------|------------|--------|-------|----------|
| **1** | **SMC fire rate ~4%** | SOL+BTC | **가능** | **독립 root cause** | S-track | SOL S-1 (보조 신호원) |
| **2** | **Position occupancy block ~28%** | SOL+BTC | **가능** | **독립 2차 병목** | S-track | 별도 분석 |

### 종료된 병목

| # | 병목 | 종료 사유 | 독립성 | track |
|---|------|----------|--------|-------|
| 3 | RDS < 0.55 (regime 편중) | **구조적 불가** — 현 환경 market structure | 독립이지만 해결 불가 | R-track |
| 4 | WF efficiency < 0.5 (cliff) | **S-track 전파** — scarcity penalty artifact | **비독립** (전파 실패) | W-track |

### 병목 계층 구조

```
[독립 미해결]
  #1 fire rate ~4% ──────────────── 해결 가능, SOL S-1 priority
  #2 occupancy block ~28% ──────── 해결 가능, 별도 분석

[종료 - 구조적 불가]
  #3 RDS < 0.55 ────────────────── MAINTAINED_FAIL (market structure)

[종료 - 전파 효과]
  #4 WF efficiency < 0.5 ───────── INFORMATIVE_FAIL (propagated from #1)
       ↑
       S-track scarcity의 전파
```

---

## 4. Verdict System 관련 메모

### 4.1 현행 7개 조건 중 구조적 영향

| 조건 | 현 상태 | 구조적 영향 |
|------|---------|------------|
| overall fitness ≥ threshold | 미정 | S-track 의존 |
| train fitness ≥ threshold | SOL 0.44, BTC 0.46 | 중간 |
| forward fitness ≥ threshold | FW2 = 0 (penalty) | **S-track 전파** |
| WF efficiency ≥ 0.5 | FAIL | **S-track 전파** |
| WF consistency ≥ threshold | 0.2 | **S-track 전파** |
| RDS ≥ 0.55 | FAIL | **구조적 불가** |
| WF overfit = false | SOL=false, BTC=true | **S-track 전파** |

**관찰:** 7개 조건 중 **최소 3-4개가 S-track scarcity의 전파 효과**이며, **1개가 구조적 불가**이다. 따라서 현행 verdict system에서 PASS는 S-track 해결 없이 불가능하다.

### 4.2 평가 기준 재검토 후보 (수정 아님, 기록만)

| 항목 | 현재 기준 | 재검토 사유 | 재검토 시기 |
|------|----------|-----------|-----------|
| `min_trades` | 10 | Binary penalty가 cliff를 과장. BTC FW2 8t → fitness 0이지만 FW1 12t → fitness 0.88 | S-track 해결 후 |
| `RDS threshold` | 0.55 | 현 암호화폐 1H 환경에서 달성 불가 | 별도 GO 필요 |
| `WF n_windows` | 5 | Window당 bars 감소 → scarcity 심화 | S-track 해결 후 |

**이 항목들은 C-5 scope에서 수정하지 않는다. 향후 별도 GO가 필요하다.**

---

## 5. 후속 체인 권고

### 5.1 즉시 후속 (C-5 종료 후)

| 체인 | 명칭 | 목적 | 선행 조건 |
|------|------|------|----------|
| **SOL S-1** | **Phase C Post-Closure — SOL S-1 Root-Cause Chain** | 보조 신호원 도입으로 fire rate 개선 | C-5 완료 + 별도 GO |

### 5.2 대기 (S-1 결과 후 판단)

| 체인 | 목적 | 트리거 |
|------|------|--------|
| Occupancy 분석 | Position occupancy block 28% 해소 | S-1 결과에 따라 |
| BTC S-3 적용 | S-3 ratio를 BTC에 공식 적용 | S-1 + occupancy 분석 후 |
| W-track 재검증 | S-track 해결 후 WF efficiency 재측정 | S-1 완료 후 자동 트리거 |

### 5.3 금지 (별도 트리거 필요)

| 체인 | 금지 사유 | 재개방 조건 |
|------|----------|-----------|
| R-track 재개방 | MAINTAINED_FAIL — 구조적 불가 | 4개 재개방 트리거 중 1개 충족 |
| RDS 기준 변경 | C-3/C-4 scope 외 | 별도 GO + 별도 근거 |
| min_trades 기준 변경 | W-3/W-4 금지 (C-4 GO) | 별도 GO + 별도 근거 |

---

## 6. Phase C 전체 증거 체인

| 산출물 | 경로 |
|--------|------|
| C-1 진단 | `phase_c_c1_completion_receipt.md` |
| C-2 GO | `phase_c_c2_go_receipt.md` |
| C-2 실험 결과 | `phase_c_c2_s3_experiment_log.json` |
| C-2 완료 | `phase_c_c2_completion_receipt.md` |
| C-3 GO | `phase_c_c3_go_receipt.md` |
| C-3 진단 결과 | `phase_c_c3_rtrack_diagnosis_log.json` |
| C-3 완료 | `phase_c_c3_completion_receipt.md` |
| C-4 GO | `phase_c_c4_go_receipt.md` |
| C-4 진단 결과 | `phase_c_c4_wtrack_diagnosis_log.json` |
| C-4 완료 | `phase_c_c4_completion_receipt.md` |
| C-5 GO | `phase_c_c5_go_receipt.md` |
| **C-5 종합 verdict** | **`phase_c_c5_integrated_verdict.md`** (본 문서) |
| C-5 완료 | `phase_c_c5_completion_receipt.md` |
| C-5 JSON | `phase_c_c5_summary_log.json` |

---

## 7. 종합 판정

```
Phase C Overall = DIAGNOSTIC SUCCESS / REMEDIATION PENDING

Phase C는 전략의 multi-track 병목을 성공적으로 진단하고,
4대 병목을 2개의 독립 미해결 병목과 2개의 종료 병목으로 분류하였다.
이것은 진단 체인으로서 완전한 성공이다.
단, 진단 성공 ≠ 문제 해결 완료이다.
실질적 개선은 후속 SOL S-1 Root-Cause Chain에서 시작된다.
```

---

## 봉인

- Phase C는 C-1~C-4의 4단계 진단 체인으로 완결되었다
- **Overall Phase C = diagnostic success / remediation pending**
- 독립 미해결 병목은 **fire rate (#1)** 과 **occupancy (#2)** 두 개이다
- R-track은 **MAINTAINED_FAIL** (current-environment bounded)이다
- W-track은 **INFORMATIVE_FAIL** (S-track scarcity propagation)이다
- W-track cliff의 100%는 scarcity penalty와 상관하며 독립 결함이 아니다
- BTC FW1 fitness=0.8787로 전략 일반화 능력은 부분 증명되었다
- verdict system 7개 조건 중 3-4개가 S-track 전파, 1개가 구조적 불가이다
- 평가 기준 재검토는 본 문서에 기록만 하며 수정하지 않는다
- 후속 체인은 **Phase C Post-Closure — SOL S-1 Root-Cause Chain**이 유일한 즉시 후보이다
- SOL S-1 follow-up은 C-5 완료 + 별도 GO가 필요하다
- auto_advance는 금지이다
