# Indicator Registry 설계 카드

**문서 ID:** DESIGN-P1-001
**작성일:** 2026-04-04
**Authority:** A (Decision Authority)
**CR:** CR-048 Phase 1 (Control Plane — Registry)
**Status:** **DESIGN_ONLY**
**변경 등급:** L0 (설계 문서)

---

## 1. 해석 및 요약

### 목적

단일 지표(Indicator)의 메타데이터, 버전, 입출력 스키마를 관리하는 레지스트리.
4대 분리 객체 중 가장 하위 단위이며, Feature Pack의 구성 요소.

### Indicator 정의

| 속성 | 설명 | 예시 |
|------|------|------|
| **id** | 고유 식별자 | `ind_rsi_v1.0.0` |
| **name** | 표시 이름 | `RSI` |
| **version** | 시맨틱 버전 | `1.0.0` |
| **category** | 지표 분류 | `MOMENTUM`, `TREND`, `VOLATILITY`, `VOLUME`, `OSCILLATOR` |
| **inputs** | 입력 스키마 (필요 데이터) | `{close: float[], period: int}` |
| **outputs** | 출력 스키마 | `{rsi: float}` |
| **asset_classes** | 적용 가능 자산 클래스 | `[CRYPTO, US_STOCK, KR_STOCK]` |
| **timeframes** | 적용 가능 타임프레임 | `[1m, 5m, 15m, 1h, 4h, 1d]` |
| **warmup_bars** | 최소 필요 bar 수 | `14` (RSI 기본) |
| **checksum** | 코드 해시 (SHA-256) | `a3f2...` |
| **status** | 등록 상태 | `ACTIVE`, `DEPRECATED`, `BLOCKED` |
| **created_by** | 등록자 | `operator_id` |
| **created_at** | 등록 시각 | `2026-04-04T10:00:00Z` |

### 핵심 규칙

| 규칙 | 내용 |
|------|------|
| 지표 단독 실전 불가 | Feature Pack에 포함되어 Strategy에 사용될 때만 |
| 버전 불변 | 등록된 버전의 코드 수정 금지 → 새 버전 발행 |
| 체크섬 검증 | load 시 코드 해시가 등록된 checksum과 일치해야 함 |
| 하위 호환 | minor/patch 버전 업은 기존 Feature Pack과 호환 보장 |
| major 버전 업 | 기존 Feature Pack 참조 변경 필요 → 새 FP 버전 |

---

## 2. 장점 / 단점

### 장점

| 장점 | 설명 |
|------|------|
| **재사용성** | 같은 지표를 여러 Feature Pack에서 공유 |
| **버전 관리** | 지표 수정 이력 완전 추적 |
| **무결성 보장** | checksum으로 런타임 코드 변조 감지 |
| **의존성 명시** | Feature Pack이 어떤 지표 버전을 사용하는지 정확히 알 수 있음 |

### 단점

| 단점 | 완화 방안 |
|------|-----------|
| 관리 오버헤드 | 지표 수가 적은 초기에는 과도할 수 있음 → 점진적 등록 |
| 버전 폭발 | minor fix도 새 버전 → 체크섬 기반 자동 비교로 중복 방지 |

---

## 3. 이유 / 근거

### 근거 1 — 기존 IndicatorCalculator와의 관계

현재 `app/services/indicators/indicator_calculator.py`에 RSI, MACD, BB, ATR, OBV, SMA, EMA가 구현되어 있음 (CR-038).
이 코드를 Indicator Registry에 등록하여 메타데이터 + 버전 관리를 추가.

### 근거 2 — Feature Cache 효율

Feature Cache는 `symbol × timeframe × bar_ts → { rsi: 65.2, adx: 28.1, ... }` 형태.
Indicator Registry에 warmup_bars, inputs/outputs가 명시되어야 Feature Cache가 정확히 계산할 수 있음.

### 근거 3 — Backtest Qualification 연동

9단계 중 1단계(데이터 호환성 검사)와 2단계(Warmup 검사)가 Indicator의 inputs/warmup_bars에 의존.

---

## 4. 실현 / 구현 대책

### 4.1 DB 모델 (설계만, 구현 미착수)

```python
# 설계 참조용 — 구현은 L3 승인 후
class IndicatorRegistry(Base):
    __tablename__ = "indicator_registry"

    id: str                    # "ind_rsi_v1.0.0"
    name: str                  # "RSI"
    version: str               # "1.0.0"
    category: IndicatorCategory  # MOMENTUM, TREND, VOLATILITY, VOLUME, OSCILLATOR
    description: str
    inputs_schema: dict        # JSON Schema
    outputs_schema: dict       # JSON Schema
    asset_classes: list[str]   # ["CRYPTO", "US_STOCK", "KR_STOCK"]
    timeframes: list[str]      # ["1m", "5m", ...]
    warmup_bars: int           # 최소 bar 수
    code_path: str             # "app/services/indicators/rsi.py"
    checksum: str              # SHA-256
    status: str                # ACTIVE, DEPRECATED, BLOCKED
    created_by: str
    created_at: datetime
    updated_at: datetime
```

### 4.2 Pydantic 스키마 (설계만)

```python
class IndicatorCreate(BaseModel):
    name: str
    version: str  # semver
    category: IndicatorCategory
    description: str
    inputs_schema: dict
    outputs_schema: dict
    asset_classes: list[AssetClass]
    timeframes: list[str]
    warmup_bars: int = Field(gt=0)
    code_path: str

class IndicatorResponse(IndicatorCreate):
    id: str
    checksum: str
    status: str
    created_at: datetime
```

### 4.3 API 엔드포인트 (설계만)

| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| `GET` | `/api/v1/registry/indicators` | 전체 조회 | Viewer+ |
| `GET` | `/api/v1/registry/indicators/{id}` | 단건 조회 | Viewer+ |
| `POST` | `/api/v1/registry/indicators` | 신규 등록 | Operator+ |
| `PATCH` | `/api/v1/registry/indicators/{id}/status` | 상태 변경 (DEPRECATED/BLOCKED) | Approver+ |

### 4.4 초기 등록 대상 (기존 CR-038 지표)

| 지표 | 카테고리 | warmup_bars | 비고 |
|------|----------|:-----------:|------|
| RSI | MOMENTUM | 14 | 기존 구현 완료 |
| MACD | MOMENTUM | 34 | 기존 구현 완료 |
| Bollinger Bands | VOLATILITY | 20 | 기존 구현 완료 |
| ATR | VOLATILITY | 14 | 기존 구현 완료 |
| OBV | VOLUME | 1 | 기존 구현 완료 |
| SMA | TREND | 200 (설정 가능) | 기존 구현 완료 |
| EMA | TREND | 200 (설정 가능) | 기존 구현 완료 |
| WaveTrend | OSCILLATOR | 21 | CR-046 구현 |
| ADX | TREND | 14 | 추가 필요 |
| VWAP | VOLUME | 1 | 추가 필요 |

---

## 5. 실행방법

| 단계 | 작업 | 등급 |
|------|------|------|
| 1 | 본 설계 카드 A 승인 | L0 |
| 2 | DB 마이그레이션 (004_control_plane_tables) | L3 |
| 3 | IndicatorRegistry 모델 구현 | L3 |
| 4 | Pydantic 스키마 구현 | L3 |
| 5 | API 엔드포인트 구현 | L3 |
| 6 | 기존 CR-038 지표 7개 초기 등록 | L3 |
| 7 | 단위 테스트 (`test_indicator_registry.py`) | L1 |

---

## 6. 더 좋은 아이디어

### 6.1 지표 성능 프로파일링

각 지표에 평균 계산 시간을 기록하여 Feature Cache 최적화에 활용:
- 느린 지표: 캐시 우선순위 높임
- 빠른 지표: 실시간 재계산 허용

### 6.2 지표 호환성 매트릭스

```
RSI + ADX: 호환 (같은 close 입력)
VWAP + OBV: 호환 (같은 volume 입력)
WaveTrend + MACD: 주의 (신호 중복 가능)
```
→ Feature Pack 구성 시 중복/충돌 경고.

---

## L3 구현 선행조건 체크리스트

| # | 조건 | 충족 여부 |
|---|------|:---------:|
| 1 | Phase 0 문서 3종 A 승인 | ⬜ |
| 2 | 본 설계 카드 A 승인 | ⬜ |
| 3 | Gate LOCKED 해제 또는 L3 개별 A 승인 | ⬜ |
| 4 | 전체 회귀 테스트 PASS | ⬜ |
| 5 | baseline-check 6/6 PASS | ⬜ |

**0/5 충족. 구현 착수 불가.**

---

```
Indicator Registry Design Card v1.0
Authority: A
Date: 2026-04-04
CR: CR-048 Phase 1
```
