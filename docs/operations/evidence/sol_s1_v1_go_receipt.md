# Phase C Post-Closure — SOL S-1 V-1 Backtest GO Receipt

**발행일:** 2026-04-10
**판정:** GO (V-1 Backtest, Candidate 1 only)
**근거:** SOL S-1 Root-Cause Analysis 완료 + 사용자 V-1 GO 선택
**selection_reason:** lowest_blast_radius_rootcause_test

---

## GO 선언문 (원문)

```
PHASE C POST-CLOSURE — SOL S-1 V-1 BACKTEST GO

승인 범위:
- 다음 단계는 SOL S-1 Candidate 1 (Consensus window 확장) V-1 backtest only로 제한한다.
- 목적은 same-bar consensus 제약 완화가 SOL fire rate 병목을 실제로 줄이는지 검증하는 것이다.
- auto_advance_allowed = false 유지.
- Candidate 2(position sizing 분할), Candidate 3(SMC sensitivity 조정)은 본 GO 범위에 포함하지 않는다.

전제 상태:
- Phase C = CLOSED
- independent unresolved bottlenecks = fire rate + occupancy
- SOL S-3 = reject
- Candidate 1 = B-1 non-invasive highest priority

허용 작업:
1. baseline(same-bar) 대비 ±N bar consensus window backtest
2. N ∈ {1,2,3} 범위의 제한 비교
3. fire_rate / consensus_rate / trade_count / min_trades / fitness / occupancy_block_rate 기록
4. V-1 completion receipt 작성

금지 작업:
- Candidate 2 착수
- Candidate 3 착수
- BTC lane 변경
- live/shadow/paper 조기 착수
- 별도 GO 없는 V-2 진입
- auto advance

권고 판정 기준:
- PASS: fire_rate ≥ 1.5× baseline AND fitness ≥ 0.80× baseline AND occupancy block 악화 제한
- INFORMATIVE_FAIL: uplift는 있으나 품질/안정성 애매
- BLOCK: fitness 급락 또는 false-consensus 급증

selection_reason:
- lowest_blast_radius_rootcause_test
```

---

## 비교군 고정

| Config | Consensus Window | 설명 |
|--------|-----------------|------|
| **Baseline** | N=0 (same-bar) | 현재 전략 그대로 |
| **Test A** | N=1 (±1 bar) | 1-bar 지연 허용 |
| **Test B** | N=2 (±2 bar) | 2-bar 지연 허용 |
| **Test C** | N=3 (±3 bar) | 3-bar 지연 허용 |

## 필수 측정 항목

| 항목 | 이유 |
|------|------|
| consensus_rate | 병목 해소 여부 |
| fire_rate_uplift | 목표 지표 |
| trade_count | 실질 개선 |
| min_trades 충족 여부 | binary penalty 해소 |
| fitness | 품질 유지 |
| occupancy_block_rate | 2차 병목 악화 감시 |
| delayed_consensus_ledger | delay 분포 |
| newly_unblocked_trades | window 확장으로 해방된 trade |
| reblocked_by_occupancy | fire rate 상승 후 재차단 |

## Candidate 1 종료 조건

아래 중 하나라도 충족 시 후보 1 체인 중단:
- fitness < 0.80 × baseline
- delayed-consensus 비중만 늘고 실제 trade 증가 미미
- occupancy block rate 급증 (> 1.5× baseline block rate)
- OOS window 편차 과도

## 봉인

- 본 receipt는 V-1 Backtest 한정 GO 증거이다
- Candidate 1 (Consensus window 확장) only
- SOL only, N∈{1,2,3} 제한
- Candidate 2, 3은 HOLD 상태이다
- 전략 코드 직접 수정은 불포함 (subclass로 검증)
- B-1 core 미침범
