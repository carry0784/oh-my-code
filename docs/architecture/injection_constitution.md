# Injection Constitution (주입 헌법)

**문서 ID:** CONST-001
**작성일:** 2026-04-02 (v1.0) → 2026-04-04 (v2.0)
**Authority:** A (Decision Authority)
**CR:** CR-048 (K-Dexter Integrated Ops Server v2.3)
**Status:** **ACTIVE**
**변경 등급:** L0 (문서)

---

## 1. 해석 및 요약

### 목적

모든 전략·지표·종목·뉴스 주입에 대한 **최상위 통제 규칙**.
이 헌법은 Phase 1~9 전체의 기준선이며, 코드 이전에 먼저 확정한다.
헌법 위반은 Injection Gateway에서 즉시 차단되며, 우회 경로는 존재하지 않는다.

### 핵심 원칙 요약

| 원칙 | 내용 |
|------|------|
| 등록 ≠ 활성화 | BACKTEST → PAPER → GUARDED_LIVE → LIVE 순서 필수 |
| 지표 단독 실전 불가 | Feature Pack에 포함되어 Strategy에 사용될 때만 |
| Live 버전 고정 | `strategy_v2.1.4` 형태 정확한 시맨틱 버전 |
| 실전 전략 직접 수정 금지 | 수정 = 새 버전 발행 |
| 항상 롤백 가능 | 문제 시 이전 Champion으로 즉시 복귀 |
| Champion/Challenger | Challenger 우위 시에만 승격 |
| **LLM 본선 제외** | LLM은 Audit/Review 채널로만. 실행 판단 금지 |
| **금지 경로 등록 차단** | 금지 브로커/섹터는 Injection Gateway에서 차단 |
| **Candidate TTL** | 24~48h 만료, regime 전환 시 즉시 재심사 |
| **AI → 실주문 영구 금지** | AI는 제안만, 실주문은 Rule Engine + GovernanceGate + OrderExecutor만 |

### 4대 분리 객체

| 객체 | 정의 | 예시 |
|------|------|------|
| **Indicator** | 계산식 (단일 지표) | RSI, ADX, ATR, WaveTrend, VWAP |
| **Feature Pack** | 전략이 쓰는 지표 묶음 | trend_pack_v1 = EMA200+ADX+ATR |
| **Strategy** | Feature Pack → 신호 생성 로직 | momentum_kis_us_v2, smc_wavetrend_crypto_v3 |
| **Promotion State** | 전략 생애 상태 (7단계) | DRAFT → REGISTERED → ... → LIVE → RETIRED/BLOCKED |

### Strategy Bank (7 상태)

| Bank | 상태 | 설명 |
|------|------|------|
| Research | DRAFT, REGISTERED | 연구 중 |
| Qualified | BACKTEST_PASS | 백테스트 통과 |
| Paper | PAPER_PASS | Paper Shadow 통과 |
| **Quarantine** | QUARANTINE | 이상 징후 격리 |
| Live | GUARDED_LIVE, LIVE | 실전 운영 |
| Retired | RETIRED | 정상 은퇴 |
| Blocked | BLOCKED | 영구 차단 |

---

## 2. 장점 / 단점

### 헌법 채택 시 장점

| 장점 | 설명 |
|------|------|
| **전략 품질 보장** | 9단계 백테스트 + 2주 Paper Shadow로 미검증 전략의 실전 진입 원천 차단 |
| **사고 복구력** | 항상 롤백 가능 원칙으로 Champion 즉시 복귀 가능 |
| **AI 안전성** | LLM 본선 제외 + AI→실주문 영구 금지로 AI 오판에 의한 손실 차단 |
| **금지 경로 물리 차단** | Injection Gateway에서 금지 브로커/섹터 등록 자체를 거부 |
| **버전 추적** | 시맨틱 버전 + 체크섬으로 실전 전략의 무결성 완전 보장 |
| **격리 체계** | Quarantine Bank으로 이상 전략 즉시 격리, 전파 방지 |

### 헌법 채택 시 단점/리스크

| 단점 | 완화 방안 |
|------|-----------|
| 승격 절차가 길다 (최소 6주+) | Paper Shadow 2주 + Guarded 4주는 최소 기간이며, 시장 기회를 놓칠 수 있음 → 별도 Fast-Track CR로 단축 가능 (A 승인 필수) |
| 규칙 복잡도 | 자동화된 Injection Gateway가 규칙을 강제하므로 운영자 부담 최소화 |
| 새 지표 실전 반영 지연 | Feature Pack 단위로 묶어야 하므로 단일 지표 테스트가 느림 → Research Bank에서 자유 실험 가능 |

### 헌법 미채택 시 리스크

| 리스크 | 심각도 |
|--------|--------|
| 미검증 전략 실전 투입 | **치명적** |
| AI 오판에 의한 실주문 | **치명적** |
| 금지 브로커 우회 | **높음** |
| 버전 불일치로 인한 런타임 오류 | **높음** |
| 롤백 불가 상황 | **높음** |

---

## 3. 이유 / 근거

### 근거 1 — CR-046 실패 교훈

CR-046에서 Track B(ETH SMC+MACD)와 Track C-v2(regime filter)가 NO-GO SEALED된 핵심 원인:
- Track B: `CV_INSTABILITY` — 시간에 따른 승률 붕괴 (55%→25%)
- Track C-v2: `CROSS_ASSET_NON_GENERALIZABLE` — 특정 자산에만 유효한 필터

→ 9단계 Backtest Qualification이 있었다면 Phase 3(미래데이터 누수 검사)과 Phase 9(시장별 적합성 검증)에서 조기 발견 가능.

### 근거 2 — LLM 본선 제외 원칙

현행 `SignalValidatorAgent` / `RiskManagerAgent`는 LLM 기반이나:
- LLM 응답은 비결정적(non-deterministic)
- 같은 입력에 다른 출력 가능 → 재현성 없음
- 실행 판단에 사용 시 감사 불가

→ LLM은 Audit/Commentary Layer로만 한정. 실행 판단은 Rule Engine + GovernanceGate만.

### 근거 3 — 금지 경로의 물리적 차단 필요성

- CLAUDE.md에 명시: ETH 운영 경로 금지, Alpaca 제거, Kiwoom_US 금지
- 문서 금지만으로는 코드 레벨 우회 가능
- Injection Gateway에서 `FORBIDDEN_BROKERS`, `FORBIDDEN_SECTORS` 체크를 강제해야 물리적 차단 보장

### 근거 4 — Candidate TTL의 필요성

- 시장 환경은 regime 단위로 변함 (TRENDING → RANGING → HIGH_VOL)
- regime 전환 시 기존 후보군의 적합성이 변함
- TTL 48h + regime 전환 즉시 재심사로 stale candidate 방지

---

## 4. 실현 / 구현 대책

### 4.1 승격 경로 (Promotion Gate)

```
REGISTERED → [9단계 Backtest PASS] → BACKTEST_PASS
BACKTEST_PASS → [Paper Shadow 2주 PASS] → PAPER_PASS
PAPER_PASS → [A 승인] → GUARDED_LIVE (자본 50%, 종목 50%)
GUARDED_LIVE → [4주 안정] → LIVE
이상 징후 → QUARANTINE (격리, 거래 중단, 진단)
QUARANTINE → 복구 가능 시 GUARDED_LIVE, 불가 시 BLOCKED
LIVE → 성과 장기 하락 → RETIRED
문제 발생 → 즉시 이전 Champion으로 롤백
```

### 4.2 Backtest Qualification 9단계

| 단계 | 검증 내용 | 실패 시 |
|------|-----------|---------|
| 1 | 데이터 호환성 검사 | 등록 거부 |
| 2 | Warmup 검사 | 등록 거부 |
| 3 | **미래데이터 누수 검사** (causality test) | 등록 거부 |
| 4 | 결측/정렬 검사 | 등록 거부 |
| 5 | 단일 종목 백테스트 | BACKTEST_FAIL |
| 6 | 다종목 백테스트 | BACKTEST_FAIL |
| 7 | OOS / Walk-Forward 검증 | BACKTEST_FAIL |
| 8 | 비용 반영 (수수료, 슬리피지) | BACKTEST_FAIL |
| 9 | 시장별 적합성 검증 | BACKTEST_FAIL |

### 4.3 Paper Shadow 평가 기준

| 기준 | 조건 |
|------|------|
| Sharpe | Challenger > Champion × 1.1 |
| MaxDD | Challenger < Champion × 1.2 |
| Turnover | 합리적 범위 (과매매 아님) |
| Slippage sensitivity | 실행 가능 수준 |
| Exposure stability | 급격한 노출 변동 없음 |
| Regime robustness | 다 regime에서 안정 |
| Cross-symbol concentration | 특정 종목 과집중 없음 |

Paper Shadow 최소 기간: **2주**

### 4.4 운영자 승인 레벨

| 위험도 | 작업 | 승인 방식 |
|--------|------|-----------|
| **저위험** | watchlist 재심사, 뉴스 태깅, 내부 로그 조회 | 자동 승인 |
| **중위험** | 백테스트 job 생성, paper candidate 등록, 스크리닝 재실행 | Operator 검토 후 승인 |
| **고위험** | Guarded Live 승격, Live 활성화, Champion 교체, 롤백 실행 | **A 승인 필수** |

### 4.5 노출 상한

| 항목 | 상한 |
|------|------|
| 시장별 Active 전략 | max 5 |
| 종목당 동시 전략 | max 3 |
| 전략×종목 동시 실행 | max 30 (전체) |
| 시장별 총 종목 | max 20 |
| 테마별 종목 | max 5 |
| 단일 종목 자본 비중 | max 10% |
| 단일 테마 자본 비중 | max 25% |
| 단일 시장 자본 비중 | max 50% |

### 4.6 Injection Gateway 검증 항목

| 순서 | 검증 | 실패 시 |
|------|------|---------|
| 1 | forbidden_broker 체크 | 즉시 거부 + `FORBIDDEN_BROKER` 코드 |
| 2 | forbidden_sector 체크 | 즉시 거부 + `FORBIDDEN_SECTOR` 코드 |
| 3 | dependency 검증 (필요 지표 존재 확인) | 거부 + `MISSING_DEPENDENCY` 코드 |
| 4 | version checksum 검증 | 거부 + `VERSION_MISMATCH` 코드 |
| 5 | manifest signature 검증 | 거부 |
| 6 | 시장 매트릭스 호환성 검증 | 거부 |

### 4.7 Runtime Immutability Zone

런타임에서 변경 불가한 4개 체크섬 묶음:

| 묶음 | 포함 항목 | 검증 시점 |
|------|-----------|-----------|
| **Strategy Bundle** | 전략 코드 + 파라미터 + 버전 | load 시, 5분 주기 |
| **Feature Pack Bundle** | 지표 조합 + 가중치 + 버전 | load 시, 5분 주기 |
| **Broker Policy Bundle** | 허용/금지 브로커 + 거래 시간 | load 시, 설정 변경 시 |
| **Risk Limit Bundle** | 노출 상한 + 비중 상한 | load 시, 설정 변경 시 |

불일치 감지 시: load 거부 + SM-3 진입 후보.

---

## 5. 실행방법

### Phase별 구현 순서

| 순서 | Phase | 산출물 | 의존성 |
|------|-------|--------|--------|
| 1 | Phase 0 (본 문서) | 헌법 + 브로커 매트릭스 + 제외 기준선 | 없음 |
| 2 | Phase 1 | Registry 모델 (Indicator, FeaturePack, Strategy, PromotionState) | Phase 0 |
| 3 | Phase 2 | Asset Registry (Symbol 3상태) | Phase 1 |
| 4 | Phase 3A/3B | Screening Engine + KIS_US Adapter | Phase 2 (병렬 가능) |
| 5 | Phase 4 | Backtest Qualification + Paper Shadow | Phase 2+3 |
| 6 | Phase 5 | 다전략 Runtime + Feature Cache | Phase 4 |
| 7 | Phase 6 | 다종목 실행 파이프라인 | Phase 5 |
| 8 | Phase 7 | 실시간 운영 + 모니터링 | Phase 6 |
| 9 | Phase 8 | AI Injection Console | Phase 7 |
| 10 | Phase 9 | Autonomous Recovery | Phase 7+ |

### 허용/금지/승인 필요 정리

| 행위 | 허용 여부 | 비고 |
|------|:---------:|------|
| Research Bank에서 자유 실험 | ✅ | 실전 영향 없음 |
| 9단계 Backtest 자동 실행 | ✅ | Operator 승인 후 |
| Paper Shadow 자동 실행 | ✅ | Operator 승인 후 |
| Guarded Live 승격 | ⚠️ | **A 승인 필수** |
| Live 활성화 | ⚠️ | **A 승인 필수** |
| Champion 교체 | ⚠️ | **A 승인 필수** |
| AI → 실주문 직접 경로 | ⛔ | **영구 금지** |
| 금지 브로커 등록 | ⛔ | Injection Gateway 차단 |
| 금지 섹터 등록 | ⛔ | Injection Gateway 차단 |
| 실전 전략 직접 수정 | ⛔ | 새 버전 발행만 허용 |
| LLM 실행 판단 | ⛔ | Audit/Review만 |
| 금지 브로커 해제 | ⛔ | A 승인 + 별도 CR |
| 금지 섹터 해제 | ⛔ | A 승인 필수 |

---

## 6. 더 좋은 아이디어

### 6.1 Fast-Track 승격 경로

긴급 시장 기회 대응을 위한 단축 경로:
- Paper Shadow 2주 → 1주 단축 (A 승인 필수)
- Guarded Live 4주 → 2주 단축 (A 승인 필수 + 추가 모니터링 주기 2배)
- 단, 9단계 Backtest와 Quarantine 격리는 단축 불가

### 6.2 Feature Pack Champion/Challenger

전략뿐 아니라 Feature Pack 조합도 Challenger 비교 가능:
```
trend_pack_v1 (Champion) vs trend_pack_v2 (Challenger)
같은 전략, 다른 피처셋 → 효과 비교
```
→ 지표 수준에서의 A/B 테스트로 더 세밀한 최적화 가능.

### 6.3 헌법 개정 절차

헌법 자체 수정이 필요한 경우:
1. 개정 사유 문서화
2. 영향 범위 분석 (어떤 Phase가 영향받는지)
3. A 승인 필수
4. 별도 CR 등록
5. 기존 헌법 버전 보관 (v1 → v2)

---

## L3 구현 선행조건 체크리스트

Phase 1 구현(L3) 착수 전 아래 조건 **전부 충족** 필요:

| # | 조건 | 충족 여부 | 비고 |
|---|------|:---------:|------|
| 1 | 본 문서(주입 헌법) A 승인 | ⬜ | |
| 2 | broker_matrix.md A 승인 | ⬜ | |
| 3 | exclusion_baseline.md A 승인 | ⬜ | |
| 4 | Phase 1 설계 카드 4종 A 승인 | ⬜ | Indicator, FeaturePack, Strategy, PromotionState |
| 5 | Gate LOCKED 해제 또는 L3 개별 A 승인 | ⬜ | 현재 Gate LOCKED |
| 6 | 전체 회귀 테스트 PASS | ⬜ | |
| 7 | baseline-check 6/6 PASS | ⬜ | |
| 8 | 구현 범위·영향 문서화 (재진입 검토 템플릿) | ⬜ | |

**0/8 충족. 구현 착수 불가.**

---

```
Injection Constitution v2.0
Authority: A
Date: 2026-04-04
CR: CR-048
```
