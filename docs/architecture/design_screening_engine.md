# Screening Engine 설계 카드

**문서 ID:** DESIGN-P3-001
**작성일:** 2026-04-04
**Authority:** A (Decision Authority)
**CR:** CR-048 Phase 3A (Screening Engine)
**Status:** **DESIGN_ONLY**
**변경 등급:** L0 (설계 문서)

---

## 1. 해석 및 요약

### 목적

종목을 5단계 파이프라인으로 평가하여 CORE/WATCH/EXCLUDED 상태를 결정하는 엔진.
Asset Registry(Phase 2)가 "종목의 상태를 관리"한다면,
Screening Engine은 "종목이 어떤 상태에 있어야 하는지를 판정"한다.

### 5단계 스크리닝 파이프라인

| 단계 | 이름 | 입력 | 판정 기준 | FAIL 시 |
|:----:|------|------|-----------|---------|
| **1** | Exclusion Filter | 종목 메타 | Exclusion Baseline 7섹터 해당 여부 | → **EXCLUDED** (즉시 종료) |
| **2** | Liquidity/Execution Quality | 시장 데이터 | 거래량, 시총, 스프레드 | → **WATCH** |
| **3** | Technical Structure | OHLCV | ATR 1~20%, ADX>15, 200MA 위치 | → **WATCH** |
| **4** | Fundamental/On-chain | 재무/체인 데이터 | PER<100/ROE>5% (주식), TVL (DeFi) | → **WATCH** |
| **5** | Backtest Qualification | 과거 데이터 | 500bars+, Sharpe>0, 결측<5% | → **WATCH** |

**5단계 전부 PASS → CORE (적격), Candidate TTL=48h 설정**

### 단계별 세부 기준

#### Stage 1: Exclusion Filter

| 기준 | 값 | 대상 시장 |
|------|-----|-----------|
| MEME 코인 | DOGE, SHIB, PEPE, WIF 등 | CRYPTO |
| 저유동성 신생 토큰 | 시총 < $50M AND 상장 < 6개월 | CRYPTO |
| GameFi | AXS, IMX 등 | CRYPTO |
| 고밸류 순수 SW | PER > 80, 매출 성장만 | US_STOCK |
| 약한 소비 베타 | 소비재 소형주 | US_STOCK |
| 유가 민감 업종 | 정유, 화학 | KR_STOCK |
| 저유동성 단기 테마 | 일거래량 < 5억원 | KR_STOCK |

**Stage 1 FAIL → EXCLUDED (절대적). 이후 단계 평가하지 않음.**

#### Stage 2: Liquidity/Execution Quality

| 기준 | CRYPTO | US_STOCK | KR_STOCK |
|------|--------|----------|----------|
| 일평균 거래량 | > $10M | > $5M | > 5억원 |
| 시총 | > $50M | > $1B | > 1조원 |
| 스프레드 | < 0.5% | < 0.3% | < 0.5% |

#### Stage 3: Technical Structure

| 기준 | 조건 | 이유 |
|------|------|------|
| ATR (14) | 1% ~ 20% (일간) | 극단적 변동성/무변동 제외 |
| ADX (14) | > 15 | 최소한의 추세성 확보 |
| 200MA | 가격이 200MA ±50% 이내 | 극단적 괴리 종목 제외 |

#### Stage 4: Fundamental/On-chain

| 기준 | CRYPTO | US_STOCK | KR_STOCK |
|------|--------|----------|----------|
| 핵심 지표 | TVL > $10M (DeFi) | PER < 100, ROE > 5% | PER < 100, ROE > 5% |
| 보조 지표 | 활성 주소 추세 | 매출 성장률 > 0 | 영업이익률 > 0 |
| 데이터 소스 | CoinGecko, DeFiLlama | KIS API | KIS API, KRX |

#### Stage 5: Backtest Qualification

| 기준 | 값 | 이유 |
|------|-----|------|
| 최소 데이터 | 500 bars | 통계적 유의성 |
| Sharpe Ratio | > 0 | 최소한 양의 기대값 |
| 결측률 | < 5% | 데이터 품질 |
| 연속 결측 | < 10 bars | 데이터 연속성 |

### Candidate TTL

| 항목 | 값 |
|------|-----|
| 기본 TTL | **48시간** |
| Regime 전환 시 | **즉시 만료** → 재심사 필요 |
| 만료 후 행동 | CORE → WATCH 강등, 해당 종목 analyze 거부, 재심사 enqueue |
| 갱신 조건 | 재심사 5단계 전부 PASS |

### 섹터 로테이션

| Regime | 가중 섹터 | 감소 섹터 |
|--------|-----------|-----------|
| TRENDING_UP | Layer1, Tech, 반도체 | — |
| TRENDING_DOWN | Infra, Energy, 금융 | Layer1, Tech |
| RANGING | DeFi, IT | — |
| HIGH_VOL/CRISIS | 전체 exposure 축소 | 전체 |

Regime 전환 시 → Candidate TTL 즉시 만료 → 재심사 trigger.

### 스크리닝 실행 주기

| 주기 | 작업 |
|------|------|
| **1시간** | CORE/WATCH 종목 Stage 2~3 재평가 (빠른 변화 감지) |
| **1일** | 전체 종목 Stage 1~5 전수 재평가 |
| **Regime 전환** | CORE 종목 즉시 Stage 2~5 재평가 (TTL 즉시 만료) |
| **수동 요청** | Operator가 특정 종목/자산 클래스 재심사 enqueue |

---

## 2. 장점 / 단점

### 장점

| 장점 | 설명 |
|------|------|
| **계층적 필터링** | 1단계에서 대량 제거 → 후속 단계 연산 부하 감소 |
| **절대적 EXCLUDED** | Stage 1 FAIL은 무조건 EXCLUDED — 이후 단계에서 뒤집힐 수 없음 |
| **시장별 맞춤 기준** | CRYPTO/US_STOCK/KR_STOCK 각각 다른 임계값 |
| **감사 추적** | ScreeningResult가 모든 단계 결과를 append-only 기록 |
| **Candidate TTL** | stale 후보 자동 만료로 시장 변화에 빠르게 대응 |
| **Regime 연동** | 시장 체제 전환 시 즉시 재심사 |

### 단점

| 단점 | 완화 방안 |
|------|-----------|
| Stage 4 데이터 소스 의존 | 무료 API(CoinGecko, KRX) 우선, 유료 API는 점진 도입 |
| Stage 5 Sharpe>0 기준이 낮음 | 초기 진입 장벽을 낮게 유지 → Backtest Qualification(Phase 4)에서 강화 |
| 시장별 기준 관리 복잡 | 설정 파일화하여 A 승인 하에 조정 가능 |

---

## 3. 이유 / 근거

### 근거 1 — 단계적 필터링의 효율성

1000 종목 기준 예상 통과율:

| 단계 | 통과율 | 잔여 종목 |
|:----:|:------:|:---------:|
| Stage 1 | 70% | 700 |
| Stage 2 | 50% | 350 |
| Stage 3 | 60% | 210 |
| Stage 4 | 70% | 147 |
| Stage 5 | 80% | ~120 |

→ 최종 CORE: 약 12%. 노출 상한(시장별 max 20종목)과 부합.

### 근거 2 — Exclusion Filter의 절대성

Stage 1은 Exclusion Baseline(CONST-003)의 코드 레벨 강제.
이 단계의 판정은 **절대적**이어야 하며, 이후 단계에서 뒤집히면 안 됨.

이유:
- Meme/GameFi는 기술적 분석 자체가 무의미
- 저유동성 종목은 백테스트 결과가 체결 불가
- Stage 1을 통과하지 않으면 Stage 2~5 연산 자체가 낭비

### 근거 3 — Candidate TTL의 필요성

| 시나리오 | TTL 없을 때 | TTL 있을 때 |
|----------|------------|------------|
| Regime 전환 | 구 CORE 종목이 부적합한 상태로 운용 지속 | 즉시 만료 → 재심사 |
| 급격한 유동성 변화 | 유동성 고갈 종목에 주문 시도 | 48시간 후 자동 재평가 |
| 데이터 품질 저하 | 결측 누적 종목 계속 운용 | 재심사에서 Stage 5 FAIL |

### 근거 4 — 기존 재사용 가능 컴포넌트

| 컴포넌트 | 파일 | Phase 3A 활용 |
|----------|------|--------------|
| IndicatorCalculator | `app/services/indicators/` | Stage 3의 ATR, ADX, SMA 계산 |
| MarketDataCollector | `workers/tasks/data_collection_tasks.py` | Stage 2 데이터 수집 |
| RegimeDetector | `app/services/regime_detector.py` | Regime 전환 감지 → TTL 만료 trigger |
| BacktestingEngine | `app/services/backtesting/` | Stage 5 Sharpe 계산 |

---

## 4. 실현 / 구현 대책

### Phase 3A 구현 대상 (L3 승인 필요)

| 파일 | 작업 | 등급 |
|------|------|------|
| `app/services/symbol_screener.py` | 5단계 스크리닝 파이프라인 | L3 |
| `app/services/sector_rotator.py` | Regime별 섹터 가중치 | L3 |
| `app/services/data_provider.py` | CoinGecko, KRX, KIS 데이터 조회 | L3 |
| `workers/tasks/screening_tasks.py` | Celery 스크리닝 task | L3 |

### Phase 3A가 아닌 항목

| 항목 | 실제 Phase | 이유 |
|------|-----------|------|
| KIS_US 어댑터 | Phase 3B | 별도 브로커 구현 |
| Backtest Qualification 9단계 | Phase 4 | 더 엄격한 검증 파이프라인 |
| Paper Shadow | Phase 4 | Champion/Challenger 비교 |

---

## 5. 실행방법

### 현재 단계 (L0/L1)

1. 본 설계 카드 확정
2. 계약 테스트 작성 (5단계 구조, 기준값, TTL 상수)
3. design_test_traceability.md 확장

### 다음 단계 (L3 승인 후)

1. SymbolScreener 5단계 파이프라인 구현
2. Celery screening task 등록
3. TTL 만료 + Regime 연동 로직
4. 통합 테스트

---

## 6. 더 좋은 아이디어

### Screening Score 정규화

현재 screening_score는 0.0~1.0 범위이지만, 각 단계 가중치가 미정의.
다음과 같은 가중 방식을 제안:

| 단계 | 가중치 | 이유 |
|:----:|:------:|------|
| Stage 1 | Pass/Fail (이진) | 절대적 필터 |
| Stage 2 | 30% | 유동성이 체결 가능성의 핵심 |
| Stage 3 | 25% | 기술적 적합성 |
| Stage 4 | 20% | 기초 체력 |
| Stage 5 | 25% | 전략 적합성 |

`screening_score = 0.3*S2 + 0.25*S3 + 0.20*S4 + 0.25*S5` (Stage 1 PASS 시에만)

이 방식은 Phase 3A 구현 시 파라미터화하여 A 승인 하에 조정 가능.

---

## L3 선행조건 체크리스트

| # | 조건 | 충족 여부 |
|---|------|:---------:|
| 1 | 본 설계 카드 A 승인 | |
| 2 | design_asset_registry.md 확정 | |
| 3 | 계약 테스트 PASS | |
| 4 | design_test_traceability.md Phase 3A 항목 반영 | |
| 5 | exclusion_baseline.md 7섹터와 Stage 1 기준 일치 확인 | |
| 6 | 기존 IndicatorCalculator 호환성 확인 (ATR, ADX, SMA) | |
| 7 | 기존 RegimeDetector와 TTL 연동 인터페이스 정의 | |
| 8 | L3 범위 확장 제안서 A 승인 | |

## 구현 착수 불가 항목

| 항목 | 사유 |
|------|------|
| SymbolScreener 파이프라인 | L3 서비스 로직 |
| Celery screening task | L3 실행 로직 |
| data_provider.py (외부 API 호출) | L3 외부 의존성 |
| sector_rotator.py | L3 서비스 로직 |
| TTL 자동 만료 로직 | L3 실행 로직 |
| Regime 전환 연동 | L3 실행 로직 |

## 문서-테스트 추적 항목 (Phase 3A)

| # | 계약 항목 | 테스트 ID |
|---|----------|-----------|
| SC-01 | 5단계 파이프라인 순서 | `test_screening_five_stages_order` |
| SC-02 | Stage 1 FAIL → EXCLUDED (절대적) | `test_stage1_fail_always_excluded` |
| SC-03 | Stage 2~5 FAIL → WATCH | `test_stage2_to_5_fail_is_watch` |
| SC-04 | 5단계 전부 PASS → CORE | `test_all_stages_pass_is_core` |
| SC-05 | Candidate TTL 48시간 | `test_candidate_ttl_48h` |
| SC-06 | Regime 전환 시 TTL 즉시 만료 | `test_regime_change_expires_ttl` |
| SC-07 | Stage 1 금지 섹터 = Exclusion Baseline 7개 | `test_stage1_matches_exclusion_baseline` |
| SC-08 | Stage 2 유동성 기준 시장별 분리 | `test_stage2_thresholds_per_market` |
| SC-09 | Stage 3 ATR/ADX/MA 기준값 | `test_stage3_technical_thresholds` |
| SC-10 | Stage 5 최소 500bars | `test_stage5_min_bars_500` |
| SC-11 | ScreeningResult append-only | `test_screening_result_append_only` |
| SC-12 | 스크리닝 실행 주기 정의 | `test_screening_schedule_defined` |

---

```
Design Card: Screening Engine v1.0
Document ID: DESIGN-P3-001
Date: 2026-04-04
CR: CR-048 Phase 3A
Status: DESIGN_ONLY
```
