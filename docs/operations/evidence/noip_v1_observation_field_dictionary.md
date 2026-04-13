# NOIP v1 — Observation 필드 사전 운영 명세서

**작성일:** 2026-04-09
**상태:** DESIGN_LOCKED
**계층:** Observation (1차 핵심 주입)

---

## 1. 목적

시장 내부에서 유동성 회수, 흡수, 고갈, 수용/거부의 원재료를 수집한다.
Interpretation에 넘길 raw signal과 context를 정규화된 필드로 제공한다.

---

## 2. 관측 필드 사전

### 2.1 가격/구조 필드

| 필드명 | 타입 | 단위 | 설명 | 소스 |
|--------|------|------|------|------|
| `obs.price_close` | float | USD | 현재 bar 종가 | OHLCV |
| `obs.price_high` | float | USD | 현재 bar 고가 | OHLCV |
| `obs.price_low` | float | USD | 현재 bar 저가 | OHLCV |
| `obs.prior_swing_high` | float | USD | 직전 확정 swing high | 계산 (SMC L=5) |
| `obs.prior_swing_low` | float | USD | 직전 확정 swing low | 계산 (SMC L=5) |
| `obs.prior_high_swept` | bool | - | 이전 고점 돌파 후 복귀 여부 | 계산 |
| `obs.prior_low_swept` | bool | - | 이전 저점 이탈 후 복귀 여부 | 계산 |
| `obs.range_extension_fail` | bool | - | range 확장 후 유지 실패 | 계산 |
| `obs.vwap_distance` | float | % | 현재가 vs VWAP 거리 | 계산 |
| `obs.value_area_position` | enum | - | ABOVE / INSIDE / BELOW | 계산 |
| `obs.poc_distance` | float | % | 현재가 vs POC 거리 | 계산 |

### 2.2 체결/오더플로우 필드

| 필드명 | 타입 | 단위 | 설명 | 소스 |
|--------|------|------|------|------|
| `obs.aggressor_buy_vol` | float | 단위통화 | 매수 주도 체결량 | 거래소 trades |
| `obs.aggressor_sell_vol` | float | 단위통화 | 매도 주도 체결량 | 거래소 trades |
| `obs.delta_n` | float | 정규화 | (buy - sell) / total | 계산 |
| `obs.delta_accel` | float | 변화율 | delta_n의 1-bar 변화율 | 계산 |
| `obs.volume_spike_z` | float | z-score | 현재 거래량 vs 20-bar 평균 | 계산 |

### 2.3 호가/미시구조 필드

| 필드명 | 타입 | 단위 | 설명 | 소스 |
|--------|------|------|------|------|
| `obs.spread_bps` | float | bps | bid-ask spread | 거래소 ticker |
| `obs.depth_imbalance_n` | float | 정규화 | (bid_depth - ask_depth) / total | 거래소 orderbook |
| `obs.funding_rate` | float | % | 펀딩비 (선물) | 거래소 API |
| `obs.open_interest_chg` | float | % | 미결제약정 변화율 | 거래소 API |

### 2.4 서사/맥락 필드

| 필드명 | 타입 | 단위 | 설명 | 소스 |
|--------|------|------|------|------|
| `obs.news_proximity_min` | int | 분 | 가장 가까운 주요 뉴스까지 시간 | 뉴스 피드 |
| `obs.news_polarity` | float | -1~+1 | 뉴스 감성 방향 | NLP |
| `obs.news_shock_flag` | bool | - | 급변 뉴스 감지 여부 | NLP |
| `obs.theme_heat_score` | float | 0~100 | 섹터/테마 관심도 | 집계 |
| `obs.macro_event_proximity` | int | 분 | FOMC/CPI 등 거시 이벤트 거리 | 이벤트 캘린더 |
| `obs.session_phase` | enum | - | PRE_OPEN / OPEN / MID / CLOSE / AFTER | 시간 계산 |

### 2.5 품질 필드

| 필드명 | 타입 | 단위 | 설명 | 소스 |
|--------|------|------|------|------|
| `obs.data_quality_score` | float | 0~100 | 종합 데이터 품질 | 계산 |
| `obs.timestamp_sync_ok` | bool | - | 데이터 소스 간 시간 정합 | 검증 |
| `obs.missing_ratio` | float | 0~1 | 결측 필드 비율 | 검증 |
| `obs.stale_flag` | bool | - | 데이터 갱신 지연 여부 | 검증 |
| `obs.spread_outlier_flag` | bool | - | 스프레드 이상치 여부 | 검증 |

---

## 3. 관측 이벤트 목록

| 이벤트 코드 | 발동 조건 | 심각도 |
|-------------|----------|--------|
| `EV_SWEEP_HIGH` | `prior_high_swept == True` | INFO |
| `EV_SWEEP_LOW` | `prior_low_swept == True` | INFO |
| `EV_DELTA_SURGE` | `abs(delta_n) > DELTA_SURGE_THRESHOLD` | INFO |
| `EV_PRICE_STALL` | `delta_surge + price_change < STALL_THRESHOLD` | INFO |
| `EV_VALUE_AREA_BREAK` | `value_area_position changed from INSIDE` | INFO |
| `EV_VALUE_AREA_REJECT` | `value_area_position returned to INSIDE within N bars` | INFO |
| `EV_NEWS_NEAR` | `news_proximity_min < NEWS_PROXIMITY_THRESHOLD` | WARN |
| `EV_SPREAD_WIDEN` | `spread_bps > SPREAD_WIDEN_THRESHOLD` | WARN |
| `EV_DATA_QUALITY_FAIL` | `data_quality_score < QUALITY_MIN_THRESHOLD` | BLOCK |

---

## 4. 임계값 정의 (초안, Shadow 검증 후 조정)

| 파라미터 | 기호 | 초안 값 | 시장 | 비고 |
|----------|------|---------|------|------|
| `DELTA_SURGE_THRESHOLD` | T_ds | 0.30 | 크립토 | delta_n 절대값 |
| `STALL_THRESHOLD` | T_st | 0.10% | 크립토 | 가격 변화율 |
| `NEWS_PROXIMITY_THRESHOLD` | T_np | 30 | 공통 | 분 |
| `SPREAD_WIDEN_THRESHOLD` | T_sw | 15 | 크립토 | bps |
| `QUALITY_MIN_THRESHOLD` | T_qm | 60 | 공통 | 점수 |
| `VOLUME_SPIKE_Z_THRESHOLD` | T_vz | 2.0 | 크립토 | z-score |
| `SWEEP_RETURN_BARS` | T_sr | 3 | 크립토 | bar 수 |
| `VALUE_AREA_REJECT_BARS` | T_var | 5 | 크립토 | bar 수 |

---

## 5. 관측 출력 구조

```python
@dataclass
class ObservationSnapshot:
    """NOIP Observation 계층 1-bar 출력."""
    timestamp: int                          # bar open_time ms
    symbol: str
    exchange: str
    
    # 가격/구조
    price_close: float
    prior_swing_high: float | None
    prior_swing_low: float | None
    prior_high_swept: bool = False
    prior_low_swept: bool = False
    range_extension_fail: bool = False
    vwap_distance: float = 0.0
    value_area_position: str = "UNKNOWN"    # ABOVE/INSIDE/BELOW
    poc_distance: float = 0.0
    
    # 체결/오더플로우
    aggressor_buy_vol: float = 0.0
    aggressor_sell_vol: float = 0.0
    delta_n: float = 0.0
    delta_accel: float = 0.0
    volume_spike_z: float = 0.0
    
    # 호가/미시구조
    spread_bps: float = 0.0
    depth_imbalance_n: float = 0.0
    funding_rate: float | None = None
    open_interest_chg: float | None = None
    
    # 서사/맥락
    news_proximity_min: int = 9999
    news_polarity: float = 0.0
    news_shock_flag: bool = False
    theme_heat_score: float = 0.0
    macro_event_proximity: int = 9999
    session_phase: str = "UNKNOWN"
    
    # 품질
    data_quality_score: float = 0.0
    timestamp_sync_ok: bool = True
    missing_ratio: float = 0.0
    stale_flag: bool = False
    spread_outlier_flag: bool = False
    
    # 이벤트
    events: list[str] = field(default_factory=list)
```

---

## 6. 데이터 품질 게이트

### 품질 점수 산출

```
data_quality_score = 100
  - (missing_ratio * 40)
  - (20 if not timestamp_sync_ok)
  - (15 if stale_flag)
  - (15 if spread_outlier_flag)
  - (10 if volume_spike_z is NaN)
```

### 게이트 규칙

| 점수 범위 | 판정 | 후속 |
|-----------|------|------|
| >= 80 | QUALITY_HIGH | 정상 진행 |
| 60 ~ 79 | QUALITY_DEGRADED | 진행하되 confidence 감점 |
| < 60 | QUALITY_FAIL | EV_DATA_QUALITY_FAIL → BLOCKED |

---

## 7. 시장별 필드 가용성

| 필드 | 크립토 선물 | 미국주식 | 한국주식 |
|------|------------|---------|---------|
| aggressor_buy/sell_vol | O | O (TAQ) | X (추정만) |
| delta_n | O | O | 제한적 |
| depth_imbalance_n | O | X | X |
| funding_rate | O | X | X |
| open_interest_chg | O | O (옵션) | O (선물) |
| news_proximity | O | O | O |
| spread_bps | O | O | O |
| vwap_distance | O | O | O |
| value_area_position | O | O | O |

**규칙:** 가용하지 않은 필드는 `None` 또는 기본값 유지, missing_ratio에 반영.

---

## 8. 봉인

- 필드 사전 잠금일: 2026-04-09
- Shadow 검증 전 임계값은 초안
- 시장별 축약은 구현 시 확정
- 이 문서의 필드 추가/삭제는 Constitution 감사 대상
