# Phase C — Strategy Improvement GO Package

**작성일:** 2026-04-10
**상태:** REVIEW_PENDING (사용자 GO 선언 대기)
**전제:** Phase B CLOSED (MAINTAINED_FAIL), Closure Snapshot 봉인

---

## 1. 입력 헌법 (Phase B Failure Signature)

Phase B B-3 진단에서 봉인된 cross-asset 공통 실패 서명을 본 체인의 입력 헌법으로 사용한다.

```
공통 서명: scarcity=severe | regime=severe_bias | stability=cliff | verdict=FAIL
```

| 차원 | SOL | BTC | 등급 |
|------|-----|-----|------|
| F-1 Scarcity | FW2=5 trades | FW2=8 trades | severe |
| F-2 Regime | RDS=0.274 (ranging 84.5%) | RDS=0.076 (ranging 96.1%) | severe_bias |
| F-3 Stability | cliff (FW2 -100%) | cliff (FW2 -100%) | cliff |

| 지표 | SOL | BTC |
|------|-----|-----|
| verdict | FAIL (4/7) | FAIL (4/7) |
| overall_fitness | 0.2865 | 0.4857 |
| train fitness | 0.4158 | 0.4522 |
| WF efficiency | -0.4959 | -2.9074 |

### 구조적 한계 (B-3에서 확인)

| # | 한계 | 해소 가능성 |
|---|------|-------------|
| 1 | SMC+WT 2/2 consensus → 960-bar 구간에서 신호 희소 | 전략 핵심 변경 없이는 불가 |
| 2 | 암호화폐 1H 시장의 구조적 ranging 편중 | 시장 특성, 코드로 해소 불가 |
| 3 | min_trades 미달 → fitness 0.0 penalty | 신호 밀도 개선 또는 세그먼트 확대 필요 |
| 4 | WF efficiency 음수 (OOS < IS) | 전략 일반화 능력 개선 필요 |

---

## 2. 목표

Phase B의 오케스트레이터(B-1/B-2)는 정상이며, 문제는 전략 성과에 있다.
본 체인의 목표는 **전략 성과 개선**이며, 3-track 실험 구조로 접근한다.

### 2.1 기본 원칙

- 각 트랙은 **독립 실행/독립 평가** 가능해야 한다
- 복수 트랙 동시 적용 시 효과 분리가 불가하므로, **순차 실행** 원칙
- 모든 실험은 **SOL + BTC 2자산 동시 검증** (단일 자산 착시 방지)
- verdict threshold 완화는 **금지** (기준은 B-2에서 봉인)
- MAINTAINED_FAIL이 여전히 합법적 종료 조건

### 2.2 3-Track 실험 목표

| Track | 코드 | 목표 | B-3 기준값 | 개선 PASS 기준 | 합법적 종료 |
|-------|------|------|-----------|---------------|-------------|
| S-track | Scarcity 완화 | FW2 trades >= min_trades(10) | SOL 5 / BTC 8 | 양쪽 모두 >= 10 | MAINTAINED_FAIL (신호 밀도 개선 불가 확인) |
| R-track | Regime Diversity 개선 | RDS >= 0.55 | SOL 0.274 / BTC 0.076 | 양쪽 모두 >= 0.55 | MAINTAINED_FAIL (시장 구조적 ranging 편중 재확인) |
| W-track | Forward Stability 개선 | WF efficiency >= 0.5 | SOL -0.50 / BTC -2.91 | 양쪽 모두 >= 0.5 | MAINTAINED_FAIL (S/R 후에도 미해소 확인) |

**주의:** "구조적 불가 확인"은 PASS가 아니라 **MAINTAINED_FAIL**이다. 개선 성공(PASS)과 합법적 진단 종료(MAINTAINED_FAIL)를 혼동하면 안 된다.

### 2.3 Track 간 의존성

```
S-track (scarcity) ← 독립 실행 가능, 최우선
R-track (regime)   ← 독립 실행 가능, S-track 이후 권장
W-track (stability) ← S/R 결과에 종속적 (scarcity 해소 시 자동 개선 가능)
```

W-track은 S-track/R-track 완료 후 재측정으로 자연 해소 여부를 먼저 확인한다.
자연 해소가 안 되면 별도 실험을 설계한다.

---

## 3. S-track: Scarcity 완화

### 3.1 문제 분석

SMC+WaveTrend 2/2 consensus가 960-bar(40일) 구간에서 10회 이상 신호를 생성하지 못한다.
이는 전략의 선별 기준이 높아 짧은 구간에서 신호 밀도가 부족한 것이다.

### 3.2 허용 접근 방식

| # | 접근 | 설명 | 허용 여부 |
|---|------|------|-----------|
| S-1 | 보조 신호 추가 | SMC+WT 외 제3 신호원 추가로 consensus 다양화 | 허용 (신규 전략 파일) |
| S-2 | 타임프레임 확장 | 1H 외 4H/15m 멀티 타임프레임 신호 결합 | 허용 (연구 후 판단) |
| S-3 | 세그먼트 비율 조정 | FW2 비율을 10%→15% 등으로 확대해 bars 수 증가 | 허용 (FullCycleConfig 확장) |
| S-4 | consensus 완화 | 2/2 → 1/2로 낮추기 | **금지** (전략 핵심 훼손) |
| S-5 | min_trades 하향 | 10 → 5로 낮추기 | **금지** (threshold 완화) |

### 3.3 실행 방식

1. **진단 단계**: FW2 구간에서 SMC/WT 각각의 개별 신호 발생 빈도 분석
2. **설계 단계**: 유효한 접근 방식 선택 + 구현 범위 정의
3. **구현 단계**: 선택된 접근 방식 구현
4. **검증 단계**: SOL+BTC 양쪽에서 FW2 trades >= 10 확인

---

## 4. R-track: Regime Diversity 개선

### 4.1 문제 분석

RegimeDetector(K-Means k=5)가 암호화폐 1H 데이터의 84-96%를 ranging으로 분류한다.
이는 탐지기의 문제인지 시장 자체의 특성인지 구분이 필요하다.

### 4.2 허용 접근 방식 (Track C-v2 흡수)

| # | 접근 | 설명 | 허용 여부 |
|---|------|------|-----------|
| R-1 | 대안 regime 지표 연구 | realized vol, choppiness index, directional efficiency 등 | 허용 (연구+진단) |
| R-2 | RegimeDetector 파라미터 조정 | k값, 피처 벡터, 임계값 등 | **조건부 허용** (별도 sub-GO 필요) |
| R-3 | 멀티 타임프레임 regime | 1H + 4H/1D regime 결합 | 허용 (연구 후 판단) |
| R-4 | RDS 임계값 하향 | 0.55 → 0.40 등 | **금지** (threshold 완화) |
| R-5 | Regime 분류 자체 제거 | regime 무시하고 전체 구간 동일 처리 | **금지** (구조 훼손) |

### 4.3 실행 방식

1. **진단 단계**: 대안 지표(realized vol, choppiness, DER)로 동일 데이터 regime 재분류
2. **비교 단계**: 현재 K-Means vs 대안 지표의 ranging/trending 비율 비교
3. **판단 단계**: "시장 자체가 ranging인가" vs "탐지기가 과도하게 ranging으로 분류하는가" 결론
4. **구현 단계**: 유효한 개선안이 있으면 구현 (별도 sub-GO)

**핵심**: R-track의 합법적 종료에는 "시장 자체가 실제로 ranging 편중이라 RDS 0.55는 현 환경에서 달성 불가"라는 결론도 포함된다.

---

## 5. W-track: Forward Stability 개선

### 5.1 문제 분석

WF efficiency가 양 자산 모두 음수이며, FW2에서 cliff 패턴이 발생한다.
그러나 cliff의 근본 원인은 **trade scarcity에 의한 fitness 0.0 penalty**이므로,
S-track 완료 후 자연 해소 여부를 먼저 확인해야 한다.

### 5.2 실행 순서

```
S-track 완료 → full-cycle 재실행 → WF efficiency 재측정
  ├─ WF >= 0.5 → W-track 자연 해소 (RESOLVED)
  └─ WF < 0.5  → W-track 별도 실험 설계 (별도 sub-GO)
```

### 5.3 별도 실험이 필요한 경우의 허용 접근

| # | 접근 | 허용 여부 |
|---|------|-----------|
| W-1 | WF window 수 조정 (n_windows) | **조건부 허용** (별도 sub-GO) |
| W-2 | Train/Forward 비율 조정 | **조건부 허용** (S-3와 연계) |
| W-3 | WF efficiency 임계값 하향 | **금지** |
| W-4 | WF overfit 판정 기준 완화 | **금지** |

---

## 6. Bounded Scope 분해

### 6.1 실행 순서

| Step | 내용 | 전제 | 자동 전진 |
|------|------|------|-----------|
| C-1 | S-track 진단 + 설계 | 사용자 GO | 불가 |
| C-2 | S-track 구현 + 검증 | C-1 완료 + 별도 GO | 불가 |
| C-3 | R-track 진단 + 비교 | C-2 완료 또는 별도 GO | 불가 |
| C-4 | W-track 재측정 | S/R 완료 후 | 불가 |
| C-5 | 종합 verdict 재실행 | C-1~C-4 완료 | 불가 |

### 6.3 C-1 필수 산출물

C-1 완료 시 아래 4건이 반드시 존재해야 한다.

| # | 산출물 | 내용 |
|---|--------|------|
| 1 | Scarcity 원인 분해표 | SMC/WT 개별 신호 빈도, consensus gap 분석, 구간별 신호 밀도 |
| 2 | SOL/BTC trade density 비교표 | 4-segment별 trades, density per 100 bars, min_trades miss 여부 |
| 3 | 개선 후보안 2~3개 | 각 후보의 접근/장단점/리스크/예상 효과 |
| 4 | `phase_c_c1_completion_receipt.md` | 진단 결론 + C-2 해금 가능 여부 판정 |

### 6.4 C-2 해금 조건

C-2는 아래 4개가 **전부 충족**되어야 열린다.

| # | 조건 |
|---|------|
| 1 | C-1 completion receipt 발행 완료 |
| 2 | 개선 후보 우선순위 확정 |
| 3 | 변경 파일/비변경 파일 목록 고정 |
| 4 | regression 기준선 고정 |

### 6.2 각 Step의 GO 규칙

- 각 Step은 **별도 GO 선언** 필요
- 자동 전진 금지 (`auto_advance_allowed = false`)
- 이전 Step 결과를 다음 Step 입력으로 사용

---

## 7. 변경 범위

### 7.1 허용 파일 (Step별로 다름, 각 GO에서 재정의)

| 유형 | 파일 | 조건 |
|------|------|------|
| NEW | `strategies/` 하위 신규 파일 | S-track 보조 신호용 (C-2 GO 시) |
| NEW | `scripts/phase_c_*.py` | 진단/실험 스크립트 |
| MODIFY | `app/services/full_cycle_backtester.py` | **APPEND ONLY** (line 457+ 이후, B-2 패턴 유지) |
| MODIFY | `app/services/regime_detector.py` | R-track sub-GO 시에만 허용 |

### 7.2 B-1 Core 봉인 대상 (라인번호 + 심볼 기반 이중 잠금)

아래 클래스/함수는 **어떤 경우에도 수정 금지**이다. 라인 drift가 발생해도 심볼명 기준으로 보호한다.

| 파일 | 심볼 | 유형 | 보호 기준 |
|------|------|------|-----------|
| `app/services/full_cycle_backtester.py` | `FullCycleConfig` | dataclass | 필드 추가/삭제/변경 금지 |
| `app/services/full_cycle_backtester.py` | `SegmentResult` | dataclass | 필드 추가/삭제/변경 금지 |
| `app/services/full_cycle_backtester.py` | `FullCycleResult` | dataclass | 필드 추가/삭제/변경 금지 |
| `app/services/full_cycle_backtester.py` | `SegmentSplitter` | class | split/validate 로직 변경 금지 |
| `app/services/full_cycle_backtester.py` | lines 1-455 (현재 기준) | zone | 이 영역 내 모든 코드 수정 금지 |

### 7.3 절대 금지 파일

| 파일 | 이유 |
|------|------|
| `app/services/full_cycle_backtester.py` B-1 core (위 7.2 참조) | B-1 core 봉인 |
| `app/services/backtesting_engine.py` | Phase A 봉인 |
| `app/services/fitness_function.py` | 가중치/공식 불변 |
| `app/services/history_data_manager.py` | Phase A 봉인 |
| `app/models/ohlcv_history.py` | 스키마 봉인 |
| verdict thresholds (B-2 constants) | 기준 완화 금지 |

---

## 8. 검증 원칙

### 8.1 Cross-Asset 2자산 동시 검증

모든 실험은 SOL/USDT:USDT + BTC/USDT:USDT 양쪽에서 동시 실행한다.
단일 자산 결과로 전체 결론을 내리는 것은 금지한다.

### 8.2 B-1 회귀 기준선 유지

| 지표 | 기준값 | 위반 시 |
|------|--------|---------|
| `leakage_violations` | 0 | ABORT |
| `determinism` | true | ABORT |
| `existing_module_changes` | Phase B core 미변경 | ABORT |

### 8.3 개선 판정 기준

| 판정 | 조건 |
|------|------|
| IMPROVED | 3 FAIL 원인 중 1개 이상 해소, 나머지 악화 없음 |
| RESOLVED | verdict=PASS (7/7) 달성 |
| MAINTAINED_FAIL | 구조적 한계 재확인, 합법적 종료 |

---

## 9. Rollback 계획

| 조건 | 조치 |
|------|------|
| 회귀 기준선 위반 | 해당 Step 변경 전체 revert |
| 기존 PASS 조건 악화 | 변경 revert + 원인 분석 |
| B-1/B-2 core 오염 | 즉시 ABORT + git revert |

---

## 10. Receipt 체계

| Receipt | 시점 | 내용 |
|---------|------|------|
| `phase_c_go_receipt.md` | GO 선언 시 | Phase C 착수 승인 |
| `phase_c_c1_completion_receipt.md` | C-1 완료 | S-track 진단 결과 |
| `phase_c_c2_completion_receipt.md` | C-2 완료 | S-track 구현 검증 결과 |
| `phase_c_c3_completion_receipt.md` | C-3 완료 | R-track 진단/비교 결과 |
| `phase_c_c4_completion_receipt.md` | C-4 완료 | W-track 재측정 결과 |
| `phase_c_c5_completion_receipt.md` | C-5 완료 | 종합 verdict 재실행 결과 |
| `phase_c_closure_snapshot.md` | 종료 시 | 최종 상태 봉인 |

---

## 11. 종료 조건

| 종료 유형 | 조건 | 결과 |
|-----------|------|------|
| **FULL_PASS** | SOL+BTC 양쪽 verdict=PASS (7/7) | Phase C 성공 종료 |
| **PARTIAL_IMPROVED** | 1개 이상 FAIL 원인 해소, 나머지 악화 없음 | Phase C 부분 성공 |
| **MAINTAINED_FAIL** | 모든 접근 실패, 구조적 한계 재확인 | Phase C 합법적 FAIL 종료 |
| **ABORT** | 회귀 기준선 위반 또는 core 오염 | Phase C 비정상 종료 |

---

## 12. 봉인

- 본 패키지는 Phase C 범위 정의이며, **사용자 GO 없이 착수 금지**
- Phase B 체인은 재개방하지 않는다 (별도 체인)
- B-1/B-2 core 및 verdict thresholds 수정은 어떤 경우에도 금지
- MAINTAINED_FAIL은 여전히 합법적 종료 조건
- Track C-v2 (대안 regime 지표)는 R-track에 흡수
- 각 Step은 별도 GO 필요, 자동 전진 금지
