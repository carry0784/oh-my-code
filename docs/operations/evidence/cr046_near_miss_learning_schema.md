# CR-046 Near Miss Learning 스키마 설계

**상태:** SCHEMA_LOCKED
**잠금일:** 2026-04-09
**작성일:** 2026-04-10
**참조 소스:** `scripts/cr046_c1a_observation.py`, `strategies/smc_wavetrend_strategy.py`

---

## 1. 목적

near_miss (합의 불성립) 사례를 정형화하여 Learning 계층의 정식 자산으로 승격한다.

CR-046 24-bar 관측에서 수집되는 `near_miss_type` 필드는 현재 진단 목적에 한정되어 있다. 이 문서는 해당 데이터를 미래의 Learning 계층 입력으로 재사용하기 위한 스키마, 분류 기준, 집계 지표, 승격 조건을 설계 수준에서 확정한다.

구현은 이 문서의 범위 밖이다. 이 문서는 설계 잠금(design lock) 역할만 수행한다.

---

## 2. near_miss 유형 정의

`near_miss_type` 값은 `SMCWaveTrendStrategy._compute_near_miss_type()` 의 canonical 구현에서 도출된다. 아래 표는 그 분류 기준을 명시한다.

| 유형 | 조건 | 의미 |
|------|------|------|
| `SMC_ONLY` | `smc_sig != 0`, `wt_sig == 0` | SMC만 신호, WT 무반응 |
| `WT_ONLY` | `smc_sig == 0`, `wt_sig != 0` | WT만 신호, SMC 무반응 |
| `DIR_MISMATCH` | `smc_sig != 0`, `wt_sig != 0`, `smc_sig != wt_sig` | 양쪽 신호 방향 불일치 |
| `BOTH_ZERO` | `smc_sig == 0`, `wt_sig == 0` | 양쪽 모두 무신호 |

**주의:** `BOTH_ZERO` 는 관측 스크립트의 `_classify_bottleneck()` 에서 별도 처리되며, 전략 코드의 `_compute_near_miss_type()` 은 해당 케이스에 대해 `None` 을 반환한다. Learning 스키마에서는 `BOTH_ZERO` 를 명시적 유형으로 정의하여 집계 지표 산출에 포함한다.

---

## 3. 학습 로그 스키마

아래는 구현 코드가 아닌 설계 명세다. 실제 구현 시 이 스키마를 기준으로 한다.

```python
@dataclass
class NearMissRecord:
    # 식별
    timestamp: int          # bar open_time ms
    symbol: str
    exchange: str

    # 신호 원시값
    smc_sig_raw: int        # -1, 0, 1
    wt_sig_raw: int         # -1, 0, 1
    smc_trend_raw: int      # -1, 0, 1
    wt1_val: float | None
    wt2_val: float | None
    wt_cross_distance: float | None

    # 분류
    near_miss_type: str     # SMC_ONLY / WT_ONLY / DIR_MISMATCH / BOTH_ZERO
    blocked_by: str         # SMC_ZERO / WT_ZERO / DIRECTION_MISMATCH / BOTH_ZERO

    # 시장 맥락
    close_price: float
    regime_label: str | None        # BULL / BEAR / SIDEWAYS / UNKNOWN
    atr_pct: float | None           # ATR as % of price
    volume_spike_z: float | None    # volume z-score

    # 후행 검증 (N bars later)
    follow_through_bars: int = 5    # how many bars to check
    follow_through_direction: int | None = None  # actual price direction after N bars
    follow_through_pct: float | None = None      # price change % after N bars
    consensus_gap_score: float | None = None     # how close to consensus (0=far, 1=near)
```

### 필드 출처 대조

| 필드 | 출처 |
|------|------|
| `smc_sig_raw`, `wt_sig_raw`, `smc_trend_raw` | `strategies/smc_wavetrend_strategy.py` → `_build_diag()` |
| `wt1_val`, `wt2_val`, `wt_cross_distance` | `strategies/smc_wavetrend_strategy.py` → `_build_diag()` |
| `near_miss_type` | `strategies/smc_wavetrend_strategy.py` → `_compute_near_miss_type()` |
| `blocked_by` | `scripts/cr046_c1a_observation.py` → `_classify_bottleneck()` |
| `close_price` | `strategies/smc_wavetrend_strategy.py` → `_build_diag()` |
| `regime_label`, `atr_pct`, `volume_spike_z` | 외부 맥락 주입 (현재 미구현, 향후 확장 필드) |
| `follow_through_*` | 후처리 단계에서 산출 (bar 기록 시점에 미산출) |
| `consensus_gap_score` | 섹션 4 공식으로 산출 |

---

## 4. consensus_gap_score 산출 공식

`consensus_gap_score` 는 해당 bar가 합의에 얼마나 근접했는지를 나타내는 스칼라 값이다. 범위: `[0.0, 1.0]`. 값이 클수록 합의에 가까웠음을 의미한다.

```
if near_miss_type == BOTH_ZERO:
    consensus_gap_score = 0.0  (far from consensus)
elif near_miss_type == SMC_ONLY or WT_ONLY:
    consensus_gap_score = 0.5  (one side fired)
elif near_miss_type == DIR_MISMATCH:
    consensus_gap_score = 0.3  (both fired but wrong direction)

# Refine with WT cross distance
if wt_cross_distance is not None and wt_cross_distance < 5.0:
    consensus_gap_score += 0.2 * (1 - wt_cross_distance / 5.0)

consensus_gap_score = clamp(consensus_gap_score, 0, 1)
```

### 산출 근거

- `BOTH_ZERO`: 두 지표 모두 무신호이므로 합의 가능성이 가장 낮다 → `0.0` 기준점.
- `SMC_ONLY` / `WT_ONLY`: 한 쪽만 발화했으므로 절반의 합의 조건을 충족한다 → `0.5` 기준점.
- `DIR_MISMATCH`: 양쪽이 발화했으나 방향이 반대이므로 `SMC_ONLY`/`WT_ONLY` 보다 낮은 점수 → `0.3` 기준점.
- `wt_cross_distance` 보정: WT 크로스 거리가 작을수록 WT 신호 발화에 근접했음을 의미. `< 5.0` 임계값은 `wt1_val`/`wt2_val` 의 실측 분포에 기반하여 향후 재조정 가능.

---

## 5. follow_through 검증 규칙

`follow_through` 는 near_miss bar 이후 N bars 동안의 실제 가격 움직임을 기록한다. 목적은 "만약 합의가 성립했다면 수익이었을까?" 에 대한 역사적 검증이다.

### 기본 파라미터

- `follow_through_bars = 5` (기본값): bar 기록 시점 기준 +5 bars 후의 close_price 기준
- `follow_through_pct`: `(close_t+N - close_t) / close_t * 100`
- `follow_through_direction`: `+1` (상승), `-1` (하락), `0` (중립)

### 판정 기준

| 판정 | 조건 | 해석 |
|------|------|------|
| `healthy_block` | near_miss 후 가격이 신호 반대 방향 이동 | 차단이 올바름 — 손실을 회피했음 |
| `false_block` | near_miss 후 가격이 신호 방향 이동 | 차단이 기회 손실 — 수익을 놓쳤음 |
| `neutral` | 변화 미미 (`abs(follow_through_pct) < 0.3%`) | 판단 불가 — 가격 고착 구간 |

### 방향 매핑

near_miss bar의 신호 방향은 `smc_sig_raw` 또는 `wt_sig_raw` 중 0이 아닌 값을 기준으로 한다. `DIR_MISMATCH` 케이스는 `smc_sig_raw` 를 우선 기준으로 사용한다. `BOTH_ZERO` 케이스는 신호 방향이 없으므로 `follow_through_direction` 을 `null` 로 기록하고 `healthy_block`/`false_block` 판정을 생략한다.

---

## 6. 집계 지표

최소 관측 창 완료 후 아래 집계 지표를 산출한다.

| 지표 | 산출식 | 설명 |
|------|--------|------|
| `near_miss_rate` | `near_miss bars / total bars` | 전체 bars 중 합의 불성립 비율 |
| `healthy_block_rate` | `healthy_blocks / total near_miss` | 차단이 올바른 비율 |
| `false_block_rate` | `false_blocks / total near_miss` | 기회 손실 비율 |
| `consensus_gap_distribution` | `consensus_gap_score` 히스토그램 | 합의 근접도 분포 (bin: 0.1 단위) |
| `regime_breakdown` | `near_miss count per regime_label` | 레짐별 near_miss 발생 빈도 |

### 해석 지침

- `false_block_rate > 0.4`: Learning 계층 재조정 신호 — 합의 기준이 지나치게 엄격할 가능성
- `healthy_block_rate > 0.6`: 현재 합의 기준의 유효성 확인
- `regime_breakdown` 에서 특정 레짐 집중: 레짐 조건부 완화 실험의 근거

---

## 7. 승격 기준

near_miss 데이터가 Learning 계층의 정식 자산으로 승격되려면 아래 조건을 모두 충족해야 한다.

| 조건 | 세부 기준 |
|------|-----------|
| 최소 수량 | near_miss 레코드 100건 이상 수집 |
| 후행 검증 | `follow_through_pct`, `follow_through_direction` 필드가 채워진 레코드 포함 |
| 레짐 매핑 | `regime_label` 이 `UNKNOWN` 이 아닌 레코드가 전체의 50% 이상 |
| 집계 산출 | 섹션 6의 집계 지표를 1회 이상 산출하고 문서화 |

승격 후에는 별도 Learning 계층 설계 문서(미작성)에서 해당 자산을 참조한다.

---

## 8. 봉인

- **스키마 잠금일:** 2026-04-09
- **이 문서의 역할:** 설계 잠금 전용. 구현 코드를 포함하지 않는다.
- **필드 추가:** 허용 (확장 방향). `NearMissRecord` 에 새 필드를 추가할 때는 기본값을 `None` 으로 설정하여 기존 레코드와의 호환성을 유지한다.
- **필드 삭제 / 의미 변경:** Constitution 감사 대상. `near_miss_type`, `consensus_gap_score`, `follow_through_*` 의 의미를 변경하려면 별도 CR을 통해 승인받아야 한다.
- **canonical 구현 참조:** `strategies/smc_wavetrend_strategy.py` → `_compute_near_miss_type()`, `_compute_skip_reason_codes()`, `_build_diag()` 가 이 스키마의 primary source이다. 해당 함수들의 변경은 이 스키마에 대한 breaking change로 간주한다.
