# Phase C C-1 — Completion Receipt

**완료일:** 2026-04-10
**판정:** SUCCESS
**범위:** S-track Scarcity 진단 + 설계 (구현 미포함)

---

## Completion Header

| 항목 | 값 |
|------|---|
| `sol_diagnosis_complete` | **true** |
| `btc_diagnosis_complete` | **true** |
| `deliverable_1_cause_table` | **LOCKED** |
| `deliverable_2_density_table` | **LOCKED** |
| `deliverable_3_candidates` | **LOCKED** |
| `primary_bottleneck` | **SMC_SCARCITY** |
| `secondary_bottleneck` | **POSITION_OCCUPANCY_BLOCK** |
| `c2_unlock_recommendation` | S-3 shadow/paper only, 별도 GO 필요 |

---

## 1차 병목: SMC Scarcity

| 지표 | SOL | BTC | 해석 |
|------|-----|-----|------|
| SMC fire rate | 4.1% (395/9550) | 3.7% (354/9550) | **1차 병목 — consensus 상한 제한** |
| WT fire rate | 14.8% (1417/9550) | 14.6% (1397/9550) | SMC의 ~3.7배, 상대적으로 충분 |
| Consensus rate | 0.8% (77/9550) | 0.7% (64/9550) | 전체의 1% 미만 |
| Consensus gap (near-miss) | 17.4% (1658) | 17.0% (1623) | 미실현 기회 ~17% |
| Both zero | 81.8% (7815) | 82.3% (7863) | 신호 자체 없는 구간 |

**결론**: WT는 ~15%로 충분히 활성적이나, SMC가 ~4%만 fire하여 consensus의 **upper bound가 ~4%**로 제한됨. 실제 consensus는 ~0.8%로, SMC fire 중에서도 WT와 방향이 맞는 경우만 통과.

---

## 2차 병목: Position Occupancy Block

| 지표 | SOL FW2 | BTC FW2 |
|------|---------|---------|
| Consensus | 7 | 11 |
| B3 trades | 5 | 8 |
| **Consensus-to-trade 손실** | **28.6%** (2/7) | **27.3%** (3/11) |

**결론**: consensus가 발생해도 약 1/4 이상은 기존 포지션이 열려있어 신규 진입이 차단됨. 이는 SMC scarcity와 독립적인 2차 병목.

### 병목 구조

```
전체 9550 bars
├── Both Zero: ~82% (신호 자체 없음)
├── Near-miss (gap): ~17% (한쪽만 fire → consensus 실패)
│   ├── WT only: ~14% (SMC 미발화)
│   ├── SMC only: ~3% (WT 미발화)
│   └── Direction mismatch: ~0.5%
├── Consensus PASS: ~0.8% (양쪽 fire + 같은 방향)
│   ├── Trade 실현: ~0.6%
│   └── Position occupancy block: ~0.2%
└── 결과: FW2에서 5~8 trades (min_trades=10 미달)
```

---

## SMC-to-Consensus 전환율

| 자산 | SMC fire | Consensus | 전환율 |
|------|----------|-----------|--------|
| SOL | 395 | 77 | 19.5% |
| BTC | 354 | 64 | 18.1% |

**해석**: SMC가 fire해도 ~80%는 WT 미발화 또는 방향 불일치로 consensus 불성립.

---

## FW2 집중도 지수

| 자산 | FW2 Consensus | Global Consensus | FW2 비율 (bars) | FW2 집중도 |
|------|---------------|------------------|----------------|-----------|
| SOL | 7 | 77 | 10.1% (960/9550) | 9.1% (기대치 이하) |
| BTC | 11 | 64 | 10.1% (960/9550) | 17.2% (기대치 이상) |

**해석**: SOL은 FW2가 전체보다 특별히 좋은 구간이 아님. BTC는 FW2 집중도가 높아 비율 확대 효과가 더 클 수 있음. **S-3는 BTC에는 유효하나 SOL 공통 해결책으로 단정하기 이름.**

---

## 후보안 재분류 (이원 우선순위)

### 운영 우선순위 (저위험 → 고위험)

| 순위 | 후보 | 분류 | 이유 |
|------|------|------|------|
| 1 | **S-3 (FW2 비율 확대)** | 저위험 density 보정 | 전략 미변경, blast radius 최소, 즉시 검증 가능 |
| 2 | S-1 (보조 신호원) | 중위험 구조 개선 | 신규 전략 파일 추가, 검증 비용 높음 |
| 3 | S-2 (멀티 TF) | 고위험 구조 확장 | Phase A 봉인 충돌 위험 |

### 근본 개선 우선순위 (원인 직결도)

| 순위 | 후보 | 분류 | 이유 |
|------|------|------|------|
| 1 | **S-1 (보조 신호원)** | 근본 원인 완화 | SMC scarcity를 직접 우회/보완 |
| 2 | S-2 (멀티 TF) | 구조적 확장 | 상위 TF 확인으로 consensus 기회 확대 |
| 3 | S-3 (FW2 비율 확대) | 표본 보정 | 밀도 자체를 개선하지 않음, 구간 확대만 |

### 핵심 교정

**S-3는 "근본 해결책"이 아니라 "저위험 density 보정책"이다.**
S-3가 운영 1순위인 이유는 실행 안전성이지, 원인 해소력이 아니다.

---

## 후보별 상세 (리뷰 보강 반영)

### S-3: 세그먼트 비율 조정

| 항목 | 내용 |
|------|------|
| 접근 | FW2 10%→15%, Holdout 10%→5% |
| 예상 효과 | FW2 = 1440 bars, 동일 밀도에서 trades ~50% 증가 |
| 예상 실패 방식 | FW2 1440에서도 trades < 10 → 밀도 문제 확인 |
| 실패 감지 | FW2 trades 재측정 |
| rollback | config 값 복원으로 완전 rollback |
| 금지영역 충돌 | FullCycleConfig 필드 추가 금지 → 별도 config wrapper 필요 |
| **위상** | **저위험 실험 1순위 (근본 해결 아님)** |

### S-1: 보조 신호원 추가

| 항목 | 내용 |
|------|------|
| 접근 | SMC+WT 외 제3 지표로 consensus 다양화 (2-of-3) |
| 예상 효과 | SMC scarcity 우회로 consensus 기회 확대 |
| 예상 실패 방식 | 추가 지표도 ranging에서 희소 → 개선 미미 |
| 실패 감지 | 제3 지표 fire rate + consensus 재측정 |
| rollback | 신규 파일 삭제로 완전 rollback |
| 금지영역 충돌 | 없음 (신규 파일, B-1 core 미접촉) |
| **위상** | **근본 개선 1순위** |

### S-2: 멀티 타임프레임 (보류)

| 항목 | 내용 |
|------|------|
| 접근 | 4H TF에서 방향 확인 후 1H 단독 신호 승인 |
| 금지영역 충돌 | **history_data_manager 수정 → Phase A 봉인 충돌 가능** |
| **위상** | **보류 (봉인 충돌 해소 전 착수 금지)** |

---

## Near-miss 세분화

| 유형 | SOL | BTC | 해석 |
|------|-----|-----|------|
| WT only (SMC 미발화) | 1340 (14.0%) | 1310 (13.7%) | SMC scarcity의 직접 증거 |
| SMC only (WT 미발화) | 283 (3.0%) | 257 (2.7%) | WT 미응답 |
| Direction mismatch | 35 (0.4%) | 56 (0.6%) | 양쪽 fire했으나 방향 불일치 |
| **합계** | **1658 (17.4%)** | **1623 (17.0%)** | consensus 직전 탈락 |

---

## B-1 Core 보호 검증

| 심볼 | 상태 |
|------|------|
| `FullCycleConfig` | 미변경 |
| `SegmentResult` | 미변경 |
| `FullCycleResult` | 미변경 |
| `SegmentSplitter` | 미변경 |
| lines 1-455 (현재 기준) | 미변경 |

---

## C-2 해금 권고

| 항목 | 권고 |
|------|------|
| C-2 범위 | **S-3 shadow/paper only** |
| C-2 목적 | FW2 비율 확대 시 trade density uplift 검증 |
| C-2 금지 | live, multi-TF, core logic expansion, auto-advance |
| C-2 전제조건 1 | C-1 receipt 발행 완료 ✅ |
| C-2 전제조건 2 | 후보 우선순위 확정 ✅ (이원 우선순위) |
| C-2 전제조건 3 | 변경/비변경 파일 목록 → C-2 GO에서 정의 |
| C-2 전제조건 4 | regression 기준선 → C-2 GO에서 정의 |
| C-2 별도 GO | **필수** |

### 미해결 리스크

| # | 리스크 | 대책 |
|---|--------|------|
| 1 | S-3로 SOL FW2 trades >= 10 달성 불확실 (FW2 집중도 9.1%) | 실패 시 S-1 근본 개선으로 전환 |
| 2 | S-3는 quality degradation 미검증 | C-2에서 fitness 동시 측정 필요 |
| 3 | 2차 병목(position occupancy)은 S-3로 해결 불가 | 별도 분석 항목으로 유지 |

---

## 상태 전이

```
C-1: IN_PROGRESS -> CLOSED (SUCCESS)
next_unlocked_step: NONE (C-2 별도 GO 필요)
auto_advance_allowed: false
```

---

## 봉인

- C-1은 진단/설계 완료 상태이며, 구현은 수행하지 않았다
- 1차 병목(SMC scarcity)과 2차 병목(position occupancy block)이 확인되었다
- S-3는 저위험 실험 1순위이며, 근본 해결책이 아니다
- S-1이 근본 개선 1순위이나, C-2에서 즉시 착수하지 않는다
- C-2는 별도 GO 없이 착수 금지
- B-1 core 이중 잠금(line + symbol) 유지
