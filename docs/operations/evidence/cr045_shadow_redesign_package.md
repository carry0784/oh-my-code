# CR-045: Shadow Run CG-2B 확보용 재설계 패키지

Date: 2026-04-01
Status: **PROPOSED**
Prerequisite: Shadow 7-Day Final Verdict (EXTEND, `shadow_7day_final_verdict.md`)
Scope: Phase 5 서비스 shadow 파라미터 + 전략 다양성 개선 (실행 경로 불변)

---

## 1. 변경 목적

7일 Shadow Run에서 CG-2B(전략 후보/거버넌스 경로 실증)가 미증명으로 종료됨.
근본 원인을 해소하여 재Shadow에서 CG-2B 실증을 확보하는 것이 목적.

**이것은 "성능 개선"이 아니라 "실증 가능성 확보"다.**

---

## 2. 7일 Shadow 병목 분석

### 근본 원인 체인

```
5분봉 200바 → SMA 전략 → 대부분 0~2 trades 발생
    → min_trades=10 미만
        → fitness_function이 penalty 적용 → fitness = 0.0 강제
            → advanced_runner의 `if fitness > 0` 조건 불통과
                → registry.register() 미호출
                    → registry_size = 0
                        → governance_decisions = 0
                            → CG-2B NOT PROVEN
```

### 수치 증거

| 항목 | Shadow 설정 | 기본 설정 | 비고 |
|------|------------|---------|------|
| n_islands | 3 | 5 | shadow가 40% 작음 |
| population_per_island | 6 | 10 | shadow가 40% 작음 |
| max_generations | 3 | 20 | shadow가 **85% 작음** |
| lookback | 50 | 50 | 동일 |
| 전략 유형 | SMA only | SMA only | 단일군 |
| 5분봉 200바 → 예상 trades | 0~2 | — | min_trades=10 미달 |

### 핵심: min_trades=10 vs 실제 trades=0~2

이것이 **가장 직접적인 병목**. 5분봉 200바(≈16.7시간)에서 SMA 크로스오버가 10회 이상 거래할 수 있는 파라미터 범위가 극히 좁음.

---

## 3. 변경 범위표

### 3A. shadow_run_cycle.py 파라미터 조정

| 항목 | 현재 | 변경 | 근거 |
|------|------|------|------|
| n_islands | 3 | **5** (기본값 복원) | 탐색 다양성 확보 |
| population_per_island | 6 | **10** (기본값 복원) | 인구 크기 확보 |
| max_generations | 3 | **10** | 수렴 기회 확대 (기본 20의 50%) |
| lookback | 50 | **30** | 더 빠른 첫 신호 → trades 증가 |
| OHLCV limit | 200 | **500** | 더 긴 관측 창 → trades 기회 증가 |
| seed | 42 + day | 42 + day | 유지 |

### 3B. 전략 다양성 확장 (strategy_runner.py)

| 항목 | 현재 | 변경 | 근거 |
|------|------|------|------|
| 전략 유형 | SimpleMAStrategy only | **SimpleMAStrategy + RSICrossStrategy** | 2군 이상 → 레짐 다양성 |
| `_genome_to_strategy` | 항상 SMA 반환 | genome의 `strategy_type` gene으로 분기 | 진화가 전략 유형 선택 |

### 3C. genome 확장 (strategy_genome.py)

| 항목 | 현재 | 변경 | 근거 |
|------|------|------|------|
| Gene 목록 | fast_period, slow_period | + `strategy_type`, `rsi_period`, `rsi_overbought`, `rsi_oversold` | RSI 전략용 파라미터 |

### 3D. 신규 전략 클래스

| 파일 | 내용 |
|------|------|
| `strategies/rsi_strategy.py` | RSICrossStrategy: RSI overbought/oversold 크로스 전략 |

---

## 4. 금지 범위 확인표

| 금지 조항 | 준수 여부 | 확인 방법 |
|-----------|----------|---------|
| dry_run 해제 금지 | ✅ 준수 | HARDCODED `DRY_RUN = True` 유지 |
| PENDING_OPERATOR 우회 금지 | ✅ 준수 | GovernanceGate 로직 불변 |
| live write path 개방 금지 | ✅ 준수 | 변경 대상에 execution path 없음 |
| CG-2A 안전장치 약화 금지 | ✅ 준수 | orchestrator/governance/health 코드 불변 |
| 임계값 왜곡 금지 | ✅ 준수 | min_trades=10 유지, fitness>0 조건 유지 |
| 기존 실행 경로 변경 금지 | ✅ 준수 | strategy_runner/_genome_to_strategy만 확장 |
| Schema/Alembic 변경 금지 | ✅ 준수 | DB 변경 없음 |

---

## 5. CG-2B 확보 논리

### 변경 전 (현 shadow): fitness=0.0이 불가피한 구조

```
200바 × SMA → 0~2 trades → min_trades=10 미달 → fitness=0.0 → registry=0
```

### 변경 후: fitness>0이 가능한 구조

```
500바 × (SMA + RSI) × 10pop × 10gen
    → RSI 전략: overbought/oversold 크로스 → trades 빈도 ↑
    → 500바(≈41.7시간): SMA도 더 많은 시그널 가능
    → min_trades=10 충족 기회 대폭 증가
        → fitness > 0 가능
            → registry >= 1
                → governance_decisions >= 1
                    → CG-2B 실증 가능
```

### 기대 효과 수치 추정

| 항목 | 현 shadow | 재설계 후 | 근거 |
|------|----------|---------|------|
| 바 수 | 200 | 500 | 2.5× 관측 창 |
| 예상 SMA trades | 0~2 | 2~8 | 더 긴 창 |
| 예상 RSI trades | — | 5~15 | RSI는 SMA보다 빈번 |
| min_trades 충족 확률 | ~0% | **50~80%** | RSI + 긴 창 조합 |
| registry >= 1 확률 | ~0% | **60~90%** | 10gen × 50pop 탐색 |

---

## 6. 상태 전이 영향

| 상태 전이 | 영향 | 확인 |
|-----------|------|------|
| CANDIDATE → VALIDATED | 불변 | 5-stage validation 코드 미변경 |
| VALIDATED → PAPER_TRADING | 불변 | lifecycle 코드 미변경 |
| PAPER_TRADING → PROMOTED | 불변 | PENDING_OPERATOR 유지 |
| PROMOTED → DEMOTED | 불변 | auto-approve (fail-closed) 유지 |
| 건강 모니터 회로차단 | 불변 | system_health 코드 미변경 |

---

## 7. 로그/Audit 영향

| 항목 | 영향 |
|------|------|
| shadow_run_cycle.py 출력 형식 | 불변 — 동일 JSON 구조 |
| day_NN.json 스키마 | 불변 |
| 체크리스트 템플릿 | 재사용 가능 |
| structlog 로그 | 불변 — 동일 이벤트명 |

---

## 8. 테스트 계획

| # | 테스트 | 검증 내용 |
|---|--------|---------|
| 1 | `pytest tests/test_strategy_runner.py -v` | genome→strategy 분기 정상 |
| 2 | `pytest tests/test_strategy_genome.py -v` | RSI gene 추가 후 mutation/crossover 정상 |
| 3 | `pytest tests/test_advanced_runner.py -v` | 변경된 설정으로 진화 정상 완료 |
| 4 | `pytest tests/test_fitness_function.py -v` | fitness 계산 불변 확인 |
| 5 | `pytest tests/ -x` | 전체 회귀 테스트 |
| 6 | `python scripts/shadow_run_cycle.py --day 0 --json` | 변경 설정으로 registry >= 1 발생 확인 |
| 7 | 실행 경로 오염 검사 | Phase 1-7 이외 코드에 새 import 없음 |

---

## 9. 새 Shadow Acceptance 기준

기존 CG-2 기준을 유지하되, 사전 점검 항목 추가:

### 사전 점검 (shadow 시작 전)

| # | 항목 | 임계값 |
|---|------|--------|
| PRE-1 | Day 0 테스트 실행에서 registry >= 1 | 필수 |
| PRE-2 | Day 0 테스트 실행에서 governance_decisions >= 1 | 필수 |
| PRE-3 | candidate_generation_probability | > 50% (Day 0 기준) |
| PRE-4 | governance_exercisability | > 0% (Day 0 기준) |

### CG-2 기준 (기존 유지)

| # | 기준 | 임계값 |
|---|------|--------|
| CG2-1 | Shadow >= 7일 | 7 |
| CG2-2 | 크래시 = 0 | 0 |
| CG2-3 | Optimizer drift < 20% | <20% |
| CG2-4 | Governance block rate > 0% | >0% |
| CG2-5 | PENDING_OPERATOR < 20/day | <20 |
| CG2-6 | Health warnings < 2/day avg | <2 |
| CG2-7 | Fitness 3-day MA non-decreasing | 비감소 |
| CG2-8 | Registry growth >= 1/2 days | >= 3.5 |
| CG2-9 | Daily reconciliation 4/4 | 4/4 |

---

## 10. 새 기준선 봉인 계획

1. CR-045 구현 완료
2. 전체 테스트 통과 확인
3. Day 0 사전 점검 통과 확인
4. 새 기준선 커밋 고정
5. `shadow_day0_baseline_v2.md` 발행
6. A 승인 후 재Shadow 시작

---

## 11. 변경 파일 목록

| # | 파일 | 변경 유형 | 내용 |
|---|------|-----------|------|
| 1 | `strategies/rsi_strategy.py` | **NEW** | RSICrossStrategy 클래스 |
| 2 | `app/services/strategy_genome.py` | EDIT | strategy_type, RSI 관련 gene 추가 |
| 3 | `app/services/strategy_runner.py` | EDIT | `_genome_to_strategy` RSI 분기 추가 |
| 4 | `scripts/shadow_run_cycle.py` | EDIT | 파라미터 조정 (5/10/10/30/500) |
| 5 | `tests/test_strategy_genome.py` | EDIT | RSI gene 테스트 추가 |
| 6 | `tests/test_strategy_runner.py` | EDIT | RSI 분기 테스트 추가 |

**총 6파일 (코드 4, 테스트 2)**

---

## 12. 미해결 리스크

| # | 리스크 | 심각도 | 대응 |
|---|--------|--------|------|
| 1 | RSI 전략도 현 시장에서 trades < 10일 수 있음 | 중간 | 500바 + RSI 조합으로 확률 크게 상승. Day 0 사전 점검으로 확인 |
| 2 | 전략군 확장이 fitness 임계값을 trivially 통과하게 만들 수 있음 | 낮음 | min_trades=10, fitness>0 조건 유지. 임계값 왜곡 금지 |
| 3 | 새 CR이 기존 sealed 코드에 영향 줄 수 있음 | 낮음 | 변경 대상이 Phase 5 서비스 + shadow 스크립트로 한정. 실행 경로 불변 |
| 4 | 재Shadow도 7일 소요 | 수용 | CG-2B 없이 CG-2 통과 불가. 필요한 비용 |

---

## CR-045 헌법 조항 대조 검수

| 요구 조항 | 반영 문장 | 상태 |
|-----------|---------|------|
| dry_run=True 유지 | HARDCODED 불변 | ✅ |
| PENDING_OPERATOR 유지 | GovernanceGate 코드 불변 | ✅ |
| live write path 금지 | execution path 변경 0건 | ✅ |
| 안전장치 약화 금지 | orchestrator/governance/health 불변 | ✅ |
| 임계값 왜곡 금지 | min_trades=10 유지, fitness>0 유지 | ✅ |
| 변경은 CR 통해서만 | CR-045 제출 | ✅ |

---

## 서명

```
CR-045: Shadow Run CG-2B Redesign Package
Status: PROPOSED
Purpose: CG-2B evidence acquisition via strategy diversification
Safety: All CG-2A safeguards unchanged

Prepared by: B (Implementer)
Approval required: A (Decision Authority)
Date: 2026-04-01
```
