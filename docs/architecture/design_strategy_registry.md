# Strategy Registry 설계 카드

**문서 ID:** DESIGN-P1-003
**작성일:** 2026-04-04
**Authority:** A (Decision Authority)
**CR:** CR-048 Phase 1 (Control Plane — Registry)
**Status:** **DESIGN_ONLY**
**변경 등급:** L0 (설계 문서)

---

## 1. 해석 및 요약

### 목적

전략(Strategy)의 메타데이터, 의존성, 시장 매트릭스, 승격 상태를 관리하는 레지스트리.
4대 분리 객체의 최상위 단위이며, 실행면(Data Plane)의 진입점.

### Strategy 정의

| 속성 | 설명 | 예시 |
|------|------|------|
| **id** | 고유 식별자 | `strat_momentum_kis_us_v2.1.4` |
| **name** | 표시 이름 | `momentum_kis_us` |
| **version** | 시맨틱 버전 | `2.1.4` |
| **feature_pack_id** | 의존 Feature Pack | `fp_trend_v1.0.0` |
| **asset_classes** | 적용 자산 클래스 | `[US_STOCK]` |
| **exchanges** | 허용 브로커 | `[KIS_US]` |
| **sectors** | 허용 섹터 | `[TECH, HEALTHCARE]` |
| **timeframes** | 적용 타임프레임 | `[1h, 4h]` |
| **regimes** | 적용 regime | `[TRENDING_UP]` |
| **max_symbols** | 최대 종목 수 | `10` |
| **signal_logic** | 신호 생성 방식 설명 | `Feature Pack 출력 기반 룰` |
| **code_path** | 전략 코드 위치 | `strategies/momentum_strategy.py` |
| **checksum** | 코드 해시 (SHA-256) | `c4d1...` |
| **promotion_state** | 현재 승격 상태 | `REGISTERED` |
| **champion_version** | Champion 버전 (있을 경우) | `v2.1.3` |
| **status** | 등록 상태 | `ACTIVE`, `DEPRECATED`, `BLOCKED` |

### 핵심 규칙

| 규칙 | 내용 |
|------|------|
| Live 버전 고정 | `strategy_v2.1.4` 시맨틱 버전 필수 |
| 실전 전략 직접 수정 금지 | 수정 = 새 버전 발행 |
| 금지 브로커/섹터 등록 불가 | Injection Gateway에서 차단 |
| Feature Pack 의존성 필수 | FP 없이 전략 등록 불가 |
| 자산 클래스-브로커 호환 | Strategy의 exchange가 ALLOWED_BROKERS에 포함 필수 |
| 시장 매트릭스 강제 | StrategyMarketMatrix로 자산-브로커-섹터-타임프레임 연결 |

---

## 2. 장점 / 단점

### 장점

| 장점 | 설명 |
|------|------|
| **전략 생애 완전 추적** | 등록 → 백테스트 → Paper → Live → Retired 전 과정 기록 |
| **다전략 관리** | 시장별 max 5, 종목당 max 3 등 노출 상한 강제 |
| **Champion/Challenger** | 같은 시장에서 현행 vs 후보 전략 비교 |
| **금지 경로 물리 차단** | 등록 단계에서 금지 브로커/섹터 사전 차단 |
| **런타임 무결성** | Strategy Bundle checksum으로 실행 중 변조 감지 |

### 단점

| 단점 | 완화 방안 |
|------|-----------|
| 승격 절차가 길다 | Fast-Track 경로 (A 승인 시, 주입 헌법 6.1절) |
| 전략 수정마다 새 버전 | 자동 버전 increment + 이전 버전 보관 |
| Feature Pack 의존성 관리 | FP 상태 변경 시 연관 Strategy에 자동 알림 |

---

## 3. 이유 / 근거

### 근거 1 — CR-046 교훈

CR-046에서 전략 실패(Track B, Track C-v2)의 근본 원인:
- 체계적인 9단계 검증 없이 Paper 단계 진입
- 자산별 적합성(ETH 부적합)을 사전 검증하지 못함

→ Strategy Registry + StrategyMarketMatrix로 자산-전략 호환성 사전 검증 강제.

### 근거 2 — 다전략 실행의 전제

Phase 5(다전략 Runtime)와 Phase 6(다종목 실행)은:
- 어떤 전략이 승인 상태인지 (GUARDED_LIVE or LIVE)
- 어떤 자산/브로커에 매핑되는지
- Feature Pack 의존성이 충족되는지

→ Strategy Registry가 없으면 RuntimeStrategyLoader가 작동 불가.

### 근거 3 — 앙상블 집계

같은 종목에 2+ 전략이 적용될 때:
```
Strategy A: LONG (score: 0.7)
Strategy B: SHORT (score: 0.3)
weighted_vote → net_score: 0.4 < 0.6 → abstain
```
→ StrategyRouter가 전략별 가중치와 신호를 집계하려면 등록된 메타데이터 필수.

---

## 4. 실현 / 구현 대책

### 4.1 DB 모델 (설계만)

```python
class StrategyRegistry(Base):
    __tablename__ = "strategy_registry"

    id: str                         # "strat_momentum_kis_us_v2.1.4"
    name: str                       # "momentum_kis_us"
    version: str                    # "2.1.4"
    description: str
    feature_pack_id: str            # FK → FeaturePackRegistry.id
    signal_logic_description: str
    code_path: str
    checksum: str                   # SHA-256
    promotion_state: PromotionState # FK/enum
    champion_version: str | None
    status: str                     # ACTIVE, DEPRECATED, BLOCKED
    created_by: str
    created_at: datetime
    updated_at: datetime

class StrategyMarketMatrix(Base):
    __tablename__ = "strategy_market_matrix"

    id: int                         # PK
    strategy_id: str                # FK → StrategyRegistry.id
    asset_class: str                # CRYPTO, US_STOCK, KR_STOCK
    exchange: str                   # BINANCE, KIS_US 등
    sectors: list[str]              # [TECH, SEMICONDUCTOR, ...]
    timeframes: list[str]           # [1h, 4h, ...]
    regimes: list[str]              # [TRENDING_UP, RANGING, ...]
    max_symbols: int
```

### 4.2 Injection Gateway 전략 등록 검증

| 순서 | 검증 | 실패 시 |
|------|------|---------|
| 1 | `exchange in FORBIDDEN_BROKERS` | 즉시 거부 |
| 2 | `exchange not in ALLOWED_BROKERS[asset_class]` | 거부 |
| 3 | `sector in FORBIDDEN_SECTORS` | 즉시 거부 |
| 4 | `feature_pack_id` 존재 + ACTIVE | 거부 (`MISSING_DEPENDENCY`) |
| 5 | FP의 `asset_classes`가 전략의 `asset_classes` 포함 | 거부 |
| 6 | 코드 checksum 검증 | 거부 (`VERSION_MISMATCH`) |
| 7 | 동일 name+version 중복 등록 | 거부 |

### 4.3 API 엔드포인트 (설계만)

| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| `GET` | `/api/v1/registry/strategies` | 전체 조회 (Bank별 필터 가능) | Viewer+ |
| `GET` | `/api/v1/registry/strategies/{id}` | 단건 조회 (메타+매트릭스+FP) | Viewer+ |
| `POST` | `/api/v1/registry/strategies` | 신규 등록 | Operator+ |
| `PATCH` | `/api/v1/registry/strategies/{id}/status` | 상태 변경 | Approver+ |
| `GET` | `/api/v1/registry/strategies/{id}/matrix` | 시장 매트릭스 조회 | Viewer+ |
| `GET` | `/api/v1/registry/bank/{bank}` | Bank별 전략 목록 | Viewer+ |

### 4.4 전략-자산 매핑 초기 계획

| 전략 | asset_class | exchange | sectors | regime |
|------|------------|----------|---------|--------|
| SMC+WaveTrend | CRYPTO | BINANCE, BITGET | LAYER1, DEFI | 추세 |
| RSI Cross | CRYPTO, US_STOCK, KR_STOCK | 전체 허용 | 전체 허용 | 전체 |
| Mean Reversion | US_STOCK, KR_STOCK | KIS_US, KIS_KR | TECH, FINANCE | 횡보 |
| Momentum | US_STOCK, KR_STOCK | KIS_US, KIS_KR | TECH, SEMI | 상승 |

### 4.5 RuntimeStrategyLoader 연동 (Phase 5)

```
loader.load(strategy_id)
  1. StrategyRegistry 조회 → promotion_state == GUARDED_LIVE or LIVE 확인
  2. StrategyMarketMatrix 조회 → 현재 시장 환경과 호환 확인
  3. FeaturePackRegistry 조회 → FP ACTIVE 확인
  4. checksum 검증 → 불일치 시 load 거부
  5. 전략 코드 load + Feature Cache 초기화
```

---

## 5. 실행방법

| 단계 | 작업 | 등급 |
|------|------|------|
| 1 | 본 설계 카드 A 승인 | L0 |
| 2 | Indicator + FeaturePack Registry 구현 완료 (선행) | L3 |
| 3 | StrategyRegistry 모델 구현 | L3 |
| 4 | StrategyMarketMatrix 모델 구현 | L3 |
| 5 | Injection Gateway 전략 검증 로직 구현 | L3 |
| 6 | API 엔드포인트 구현 | L3 |
| 7 | 단위 테스트 (`test_strategy_registry.py`, `test_injection_gateway.py`) | L1 |
| 8 | RuntimeStrategyLoader 연동 (Phase 5) | L3 |

---

## 6. 더 좋은 아이디어

### 6.1 전략 건전성 점수 (Strategy Health Score)

실전 운영 중 전략에 건전성 점수를 부여:

| 지표 | 가중치 |
|------|--------|
| 최근 30일 Sharpe | 30% |
| 최근 30일 MaxDD | 25% |
| Win Rate 안정성 (표준편차) | 20% |
| 슬리피지 대비 실질 수익 | 15% |
| Quarantine 이력 | 10% |

→ 건전성 < 40% 시 자동 Quarantine 후보 알림.

### 6.2 전략 은퇴 자동 추천

| 조건 | 추천 |
|------|------|
| 90일 연속 음수 수익 | RETIRED 추천 (A 승인 필요) |
| 건전성 점수 < 20% (60일 유지) | RETIRED 추천 |
| regime 적합성 3회 연속 불일치 | Quarantine + 재검증 |

### 6.3 전략 클론 기능

기존 전략을 기반으로 파라미터만 변경한 새 버전 생성:
```
strat_momentum_v2.1.4 → clone → strat_momentum_v2.2.0
  변경: FP v1 → FP v2, max_symbols 10 → 15
  나머지: 동일
```
→ Challenger 생성 효율화.

---

## L3 구현 선행조건 체크리스트

| # | 조건 | 충족 여부 |
|---|------|:---------:|
| 1 | Phase 0 문서 3종 A 승인 | ⬜ |
| 2 | Indicator Registry 설계 카드 A 승인 | ⬜ |
| 3 | Feature Pack 설계 카드 A 승인 | ⬜ |
| 4 | 본 설계 카드 A 승인 | ⬜ |
| 5 | Indicator + FeaturePack Registry 구현 완료 | ⬜ |
| 6 | Gate LOCKED 해제 또는 L3 개별 A 승인 | ⬜ |
| 7 | 전체 회귀 테스트 PASS | ⬜ |

**0/7 충족. 구현 착수 불가.**

---

```
Strategy Registry Design Card v1.0
Authority: A
Date: 2026-04-04
CR: CR-048 Phase 1
```
