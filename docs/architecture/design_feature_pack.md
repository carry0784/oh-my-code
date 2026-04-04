# Feature Pack 설계 카드

**문서 ID:** DESIGN-P1-002
**작성일:** 2026-04-04
**Authority:** A (Decision Authority)
**CR:** CR-048 Phase 1 (Control Plane — Registry)
**Status:** **DESIGN_ONLY**
**변경 등급:** L0 (설계 문서)

---

## 1. 해석 및 요약

### 목적

전략이 사용하는 지표 묶음(Feature Pack)을 관리하는 레지스트리.
Indicator → Feature Pack → Strategy 계층 구조에서 중간 계층.
같은 지표 조합을 여러 전략이 공유할 수 있고, Feature Cache의 계산 단위.

### Feature Pack 정의

| 속성 | 설명 | 예시 |
|------|------|------|
| **id** | 고유 식별자 | `fp_trend_v1.0.0` |
| **name** | 표시 이름 | `trend_pack_v1` |
| **version** | 시맨틱 버전 | `1.0.0` |
| **indicators** | 포함 지표 목록 (ID+버전) | `[ind_ema_v1.0.0, ind_adx_v1.0.0, ind_atr_v1.0.0]` |
| **parameters** | 지표별 파라미터 오버라이드 | `{ema: {period: 200}, adx: {period: 14}}` |
| **asset_classes** | 적용 가능 자산 클래스 | `[CRYPTO, US_STOCK]` |
| **timeframes** | 적용 가능 타임프레임 | `[1h, 4h, 1d]` |
| **warmup_bars** | max(포함 지표 warmup_bars) | `200` (EMA200 기준) |
| **checksum** | 지표 조합 + 파라미터 해시 | `b7e9...` |
| **status** | 등록 상태 | `ACTIVE`, `DEPRECATED`, `BLOCKED` |
| **champion_of** | Champion인 전략 ID (있을 경우) | `strat_momentum_v2` |

### 핵심 규칙

| 규칙 | 내용 |
|------|------|
| Feature Pack도 버전 불변 | 등록된 FP 수정 금지 → 새 버전 발행 |
| 지표 의존성 검증 | 포함된 Indicator가 모두 ACTIVE 상태여야 함 |
| Champion/Challenger 지원 | 같은 전략에서 FP v1(Champion) vs FP v2(Challenger) 비교 가능 |
| Feature Cache 단위 | FP에 포함된 지표를 symbol×timeframe별로 1회만 계산 |
| warmup_bars 자동 계산 | 포함 지표 중 최대 warmup_bars를 FP warmup_bars로 설정 |

---

## 2. 장점 / 단점

### 장점

| 장점 | 설명 |
|------|------|
| **계산 효율** | 같은 FP를 사용하는 다전략이 Feature Cache를 공유 |
| **A/B 테스트** | FP 레벨에서 Champion vs Challenger 비교 가능 |
| **구성 추적** | 전략이 어떤 지표 조합을 사용하는지 정확히 추적 |
| **독립 변경** | 지표 업그레이드 시 FP 새 버전만 발행, 전략 코드 변경 불필요 |

### 단점

| 단점 | 완화 방안 |
|------|-----------|
| 지표-FP-전략 3계층 관리 복잡 | 자동 의존성 검증으로 오류 방지 |
| FP가 많아지면 유사 조합 난립 | 유사도 검사 + 중복 경고 |

---

## 3. 이유 / 근거

### 근거 1 — Feature Cache 최적화

다전략 실행 시:
```
Strategy A: RSI + ADX + ATR
Strategy B: RSI + EMA + ATR
공통: RSI, ATR → 1회만 계산
```
Feature Pack 단위로 캐시하면 공통 지표 중복 계산 제거.

### 근거 2 — Champion/Challenger 비교

```
trend_pack_v1 (Champion): EMA200 + ADX14 + ATR14
trend_pack_v2 (Challenger): EMA200 + ADX14 + ATR14 + VWAP
```
같은 전략에서 FP만 교체하여 효과 비교 → 지표 레벨 최적화.

### 근거 3 — 런타임 무결성

Runtime Immutability Zone의 Feature Pack Bundle:
- FP 등록 시 checksum = hash(지표 ID 목록 + 파라미터 + 버전)
- 런타임 5분 주기로 checksum 검증
- 불일치 시 load 거부

---

## 4. 실현 / 구현 대책

### 4.1 DB 모델 (설계만)

```python
class FeaturePackRegistry(Base):
    __tablename__ = "feature_pack_registry"

    id: str                    # "fp_trend_v1.0.0"
    name: str                  # "trend_pack_v1"
    version: str               # "1.0.0"
    description: str
    indicators: list[dict]     # [{id: "ind_ema_v1.0.0", params: {period: 200}}, ...]
    asset_classes: list[str]
    timeframes: list[str]
    warmup_bars: int           # auto-calculated
    checksum: str              # SHA-256
    status: str                # ACTIVE, DEPRECATED, BLOCKED
    champion_of: str | None    # strategy_id
    created_by: str
    created_at: datetime
    updated_at: datetime
```

### 4.2 Pydantic 스키마 (설계만)

```python
class FeaturePackIndicator(BaseModel):
    indicator_id: str           # "ind_rsi_v1.0.0"
    parameter_overrides: dict = {}

class FeaturePackCreate(BaseModel):
    name: str
    version: str
    description: str
    indicators: list[FeaturePackIndicator]  # 1개 이상
    asset_classes: list[AssetClass]
    timeframes: list[str]

class FeaturePackResponse(FeaturePackCreate):
    id: str
    warmup_bars: int
    checksum: str
    status: str
    champion_of: str | None
    created_at: datetime
```

### 4.3 API 엔드포인트 (설계만)

| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| `GET` | `/api/v1/registry/feature-packs` | 전체 조회 | Viewer+ |
| `GET` | `/api/v1/registry/feature-packs/{id}` | 단건 조회 | Viewer+ |
| `POST` | `/api/v1/registry/feature-packs` | 신규 등록 | Operator+ |
| `PATCH` | `/api/v1/registry/feature-packs/{id}/status` | 상태 변경 | Approver+ |
| `GET` | `/api/v1/registry/feature-packs/{id}/indicators` | 포함 지표 목록 | Viewer+ |

### 4.4 의존성 검증 로직 (설계만)

등록 시 체크:
1. 모든 `indicator_id`가 IndicatorRegistry에 존재
2. 모든 지표가 `ACTIVE` 상태
3. 지표의 `asset_classes`가 FP의 `asset_classes`를 포함
4. 지표의 `timeframes`가 FP의 `timeframes`를 포함
5. 동일 이름+버전 중복 등록 거부
6. checksum 자동 생성

### 4.5 초기 Feature Pack 후보

| FP 이름 | 포함 지표 | 대상 전략 |
|---------|-----------|-----------|
| `trend_pack_v1` | EMA200 + ADX14 + ATR14 | Momentum |
| `oscillator_pack_v1` | RSI14 + MACD + WaveTrend | SMC+WaveTrend |
| `mean_rev_pack_v1` | BB20 + RSI14 + ATR14 | Mean Reversion |
| `volume_pack_v1` | OBV + VWAP | 보조 (여러 전략에서 공유) |

---

## 5. 실행방법

| 단계 | 작업 | 등급 |
|------|------|------|
| 1 | 본 설계 카드 A 승인 | L0 |
| 2 | IndicatorRegistry 구현 완료 (선행) | L3 |
| 3 | FeaturePackRegistry 모델 구현 | L3 |
| 4 | 의존성 검증 로직 구현 | L3 |
| 5 | API 엔드포인트 구현 | L3 |
| 6 | 단위 테스트 (`test_feature_pack.py`) | L1 |
| 7 | Feature Cache 연동 (Phase 5) | L3 |

---

## 6. 더 좋은 아이디어

### 6.1 FP 유사도 검사

새 FP 등록 시 기존 FP와 지표 조합이 80%+ 겹치면 경고:
```
Warning: fp_trend_v1.0.1 is 85% similar to fp_trend_v1.0.0
Consider versioning instead of new pack.
```

### 6.2 FP 성능 벤치마크

```
fp_trend_v1: 계산 시간 12ms/bar, 메모리 2.3MB
fp_oscillator_v1: 계산 시간 8ms/bar, 메모리 1.8MB
```
→ 리소스 사용량 기반 FP 최적화 가이드.

---

## L3 구현 선행조건 체크리스트

| # | 조건 | 충족 여부 |
|---|------|:---------:|
| 1 | Phase 0 문서 3종 A 승인 | ⬜ |
| 2 | Indicator Registry 설계 카드 A 승인 | ⬜ |
| 3 | 본 설계 카드 A 승인 | ⬜ |
| 4 | IndicatorRegistry 구현 완료 | ⬜ |
| 5 | Gate LOCKED 해제 또는 L3 개별 A 승인 | ⬜ |
| 6 | 전체 회귀 테스트 PASS | ⬜ |

**0/6 충족. 구현 착수 불가.**

---

```
Feature Pack Design Card v1.0
Authority: A
Date: 2026-04-04
CR: CR-048 Phase 1
```
