# NOIP v1 — Interpretation 점수 공식 운영 명세서

**작성일:** 2026-04-09
**상태:** DESIGN_LOCKED
**계층:** Interpretation (2차 핵심 주입)

---

## 1. 목적

Observation에서 수집된 raw 필드와 이벤트를 **의미 있는 시장 해석 점수**로 변환한다.
Decision 계층에 넘길 setup_type, confidence, conflict를 산출한다.

---

## 2. 핵심 해석 점수 정의

### 2.1 점수 목록

| 점수명 | 기호 | 범위 | 의미 |
|--------|------|------|------|
| `int.absorption_score` | S_abs | 0~100 | 강한 체결 대비 가격 전진 부재 |
| `int.exhaustion_score` | S_exh | 0~100 | 추세 방향 체결 지속 + 확장 실패 |
| `int.acceptance_score` | S_acc | 0~100 | 가치영역 이탈 후 유지 |
| `int.rejection_score` | S_rej | 0~100 | 이탈 직후 복귀 (failed breakout) |
| `int.sweep_reversal_score` | S_swr | 0~100 | 유동성 sweep 후 즉시 복귀 |
| `int.narrative_alignment_score` | S_nal | 0~100 | 뉴스/서사 방향과 오더플로우 일치 |
| `int.narrative_conflict_score` | S_ncf | 0~100 | 뉴스/서사 방향과 오더플로우 충돌 |
| `int.execution_friction_score` | S_efr | 0~100 | 실행 환경 마찰 (spread/latency/depth) |
| `int.trap_risk_score` | S_trp | 0~100 | 함정 (spoof/false signal) 위험 |
| `int.regime_confidence` | S_rgm | 0~100 | 현재 레짐 판별 확신도 |

---

## 3. 점수 산출 공식 (초안)

### 3.1 Absorption Score

```
S_abs = w1 * clamp(|delta_n| / T_ds, 0, 1) * 100
      + w2 * clamp(volume_spike_z / T_vz, 0, 1) * 100
      - w3 * clamp(|price_change_pct| / 0.5, 0, 1) * 100

where:
  w1 = 0.40  (delta 강도)
  w2 = 0.30  (거래량 급증)
  w3 = 0.30  (가격 전진 → 전진 클수록 absorption 아님)
  
  price_change_pct = (close - open) / open * 100
  
  S_abs = max(0, S_abs)
```

**해석:** 체결은 강한데 가격이 안 움직이면 → 누군가 반대편에서 흡수 중

### 3.2 Exhaustion Score

```
S_exh = w1 * clamp(|delta_n| / T_ds, 0, 1) * 100
      + w2 * (1 if range_extension_fail else 0) * 100
      + w3 * tail_ratio * 100

where:
  w1 = 0.30  (체결 지속성)
  w2 = 0.35  (range 확장 실패)
  w3 = 0.35  (캔들 꼬리 비율)
  
  tail_ratio = max(upper_tail, lower_tail) / candle_range
  upper_tail = high - max(open, close)
  lower_tail = min(open, close) - low
  candle_range = max(high - low, 0.0001)
```

**해석:** 한 방향 체결이 계속되지만 가격 확장이 실패하고 꼬리가 길면 → 고갈

### 3.3 Acceptance Score

```
S_acc = w1 * (1 if value_area_break_sustained else 0) * 100
      + w2 * clamp(bars_outside_va / T_var, 0, 1) * 100
      + w3 * directional_delta_consistency * 100

where:
  w1 = 0.40  (VA 이탈 유지 여부)
  w2 = 0.30  (이탈 후 유지 bar 수)
  w3 = 0.30  (체결 방향 일관성)
  
  value_area_break_sustained = (position changed) AND (no return within T_var bars)
  directional_delta_consistency = sign(delta_n) == sign(price direction) for N bars
```

**해석:** 가치영역 이탈 후 돌아오지 않고 체결도 같은 방향이면 → 수용

### 3.4 Rejection Score

```
S_rej = w1 * (1 if value_area_return else 0) * 100
      + w2 * (1 if range_extension_fail else 0) * 100
      + w3 * counter_delta_strength * 100

where:
  w1 = 0.40  (VA 복귀 여부)
  w2 = 0.30  (확장 실패)
  w3 = 0.30  (반대 방향 체결 강도)
  
  value_area_return = broke out then returned to INSIDE within T_var bars
  counter_delta_strength = clamp(|delta_n in opposite direction| / T_ds, 0, 1)
```

**해석:** 이탈했다가 바로 복귀 + 반대 체결 강하면 → 거부 (failed breakout)

### 3.5 Sweep Reversal Score

```
S_swr = w1 * (1 if prior_high_swept or prior_low_swept else 0) * 100
      + w2 * (1 if price_returned_within_T_sr else 0) * 100
      + w3 * reversal_delta_strength * 100

where:
  w1 = 0.35  (sweep 발생)
  w2 = 0.35  (빠른 복귀)
  w3 = 0.30  (복귀 방향 체결)
```

**해석:** 고점/저점 돌파 후 즉시 복귀 + 반대 체결 강하면 → sweep reversal

### 3.6 Narrative Alignment Score

```
S_nal = w1 * clamp(news_polarity_match, 0, 1) * 100
      + w2 * (1 - clamp(news_proximity_min / 60, 0, 1)) * 100
      + w3 * theme_heat_factor * 100

where:
  w1 = 0.40  (뉴스 감성과 오더플로우 방향 일치)
  w2 = 0.30  (뉴스 근접성)
  w3 = 0.30  (테마 열기)
  
  news_polarity_match:
    = 1.0 if sign(news_polarity) == sign(delta_n) and both nonzero
    = 0.5 if either is zero (neutral)
    = 0.0 if signs conflict
  
  theme_heat_factor = clamp(theme_heat_score / 80, 0, 1)
```

### 3.7 Narrative Conflict Score

```
S_ncf = w1 * clamp(news_polarity_conflict, 0, 1) * 100
      + w2 * (1 if news_shock_flag else 0) * 100
      + w3 * (1 if macro_event_proximity < 30 else 0) * 100

where:
  w1 = 0.40  (뉴스 vs 오더플로우 방향 충돌)
  w2 = 0.30  (뉴스 급변)
  w3 = 0.30  (거시 이벤트 근접)
  
  news_polarity_conflict:
    = 1.0 if sign(news_polarity) != sign(delta_n) and both nonzero
    = 0.0 otherwise
```

### 3.8 Execution Friction Score

```
S_efr = w1 * clamp(spread_bps / T_sw, 0, 1) * 100
      + w2 * clamp(abs(depth_imbalance_n) * 2, 0, 1) * 100
      + w3 * (1 if stale_flag else 0) * 100

where:
  w1 = 0.40  (스프레드)
  w2 = 0.30  (호가 비대칭)
  w3 = 0.30  (데이터 지연)
```

### 3.9 Trap Risk Score

```
S_trp = w1 * (1 if depth_imbalance_n > 0.7 and delta_n_opposite else 0) * 100
      + w2 * spoof_indicator * 100
      + w3 * consecutive_false_breakout_count / 3 * 100

where:
  w1 = 0.35  (호가 쏠림 vs 실제 체결 불일치)
  w2 = 0.35  (스푸핑 후보)
  w3 = 0.30  (연속 failed breakout)
  
  spoof_indicator = rapid depth disappearance after aggressive fill
```

### 3.10 Regime Confidence

```
S_rgm = RegimeDetector.detect() confidence * 100
        (기존 regime_detector.py의 cluster confidence 재활용)
```

---

## 4. 해석 상태 분류

| 해석 상태 | 발동 조건 | 방향 |
|-----------|----------|------|
| `INTERP_ABSORPTION` | S_abs >= 60 AND S_exh < 40 | delta_n 반대 방향 |
| `INTERP_EXHAUSTION` | S_exh >= 60 AND S_abs < 40 | delta_n 반대 방향 |
| `INTERP_ACCEPTANCE` | S_acc >= 60 AND S_rej < 30 | VA 이탈 방향 |
| `INTERP_REJECTION` | S_rej >= 60 AND S_acc < 30 | VA 복귀 방향 |
| `INTERP_SWEEP_REVERSAL` | S_swr >= 65 | sweep 반대 방향 |
| `INTERP_CONFLICTED` | S_ncf >= 60 OR (max_score - 2nd_score < 10) | 없음 (BLOCKED) |
| `INTERP_NEUTRAL` | 모든 점수 < 40 | 없음 |
| `INTERP_INVALID` | data_quality_score < 60 | 없음 (BLOCKED) |

**규칙:** 최고 점수 상태 1개만 채택. 2개 이상 동점(차이 < 10) → CONFLICTED.

---

## 5. Setup Type 목록

| setup_type | 설명 | 전형적 방향 |
|------------|------|------------|
| `ABSORPTION_LONG` | 하락 체결 흡수 후 반등 | LONG |
| `ABSORPTION_SHORT` | 상승 체결 흡수 후 하락 | SHORT |
| `EXHAUSTION_REVERSAL_LONG` | 하락 고갈 후 반등 | LONG |
| `EXHAUSTION_REVERSAL_SHORT` | 상승 고갈 후 하락 | SHORT |
| `ACCEPTANCE_BREAKOUT_LONG` | 상방 이탈 수용 | LONG |
| `ACCEPTANCE_BREAKOUT_SHORT` | 하방 이탈 수용 | SHORT |
| `REJECTION_FADE_LONG` | 하방 거부 후 반등 | LONG |
| `REJECTION_FADE_SHORT` | 상방 거부 후 하락 | SHORT |
| `SWEEP_REVERSAL_LONG` | 저점 sweep 후 반등 | LONG |
| `SWEEP_REVERSAL_SHORT` | 고점 sweep 후 하락 | SHORT |

---

## 6. 해석 출력 구조

```python
@dataclass
class InterpretationResult:
    """NOIP Interpretation 계층 출력."""
    timestamp: int
    symbol: str
    
    # 점수 벡터
    absorption_score: float = 0.0
    exhaustion_score: float = 0.0
    acceptance_score: float = 0.0
    rejection_score: float = 0.0
    sweep_reversal_score: float = 0.0
    narrative_alignment_score: float = 0.0
    narrative_conflict_score: float = 0.0
    execution_friction_score: float = 0.0
    trap_risk_score: float = 0.0
    regime_confidence: float = 0.0
    
    # 해석 결과
    interp_state: str = "INTERP_NEUTRAL"
    setup_type: str | None = None
    setup_direction: str | None = None   # "LONG" / "SHORT" / None
    confidence: float = 0.0              # 최고 점수 / 100
    
    # 충돌/무효
    conflict_reasons: list[str] = field(default_factory=list)
    invalid_reason: str | None = None
```

---

## 7. Confidence 합성 공식

```
raw_confidence = max_score / 100

adjusted_confidence = raw_confidence
  * (1 - narrative_conflict_penalty)
  * (1 - execution_friction_penalty)
  * (1 - trap_risk_penalty)
  * regime_bonus

where:
  narrative_conflict_penalty = clamp(S_ncf / 200, 0, 0.5)
  execution_friction_penalty = clamp(S_efr / 200, 0, 0.3)
  trap_risk_penalty = clamp(S_trp / 200, 0, 0.4)
  regime_bonus = 0.9 + 0.1 * clamp(S_rgm / 100, 0, 1)

final_confidence = clamp(adjusted_confidence, 0, 1)
```

---

## 8. 무효화 규칙

| 조건 | 결과 | 이유 |
|------|------|------|
| `data_quality_score < 60` | INTERP_INVALID | 데이터 품질 미달 |
| `spread_outlier_flag == True` | INTERP_INVALID | 실행 불가 시장 |
| `S_ncf > 80 AND S_nal < 20` | INTERP_CONFLICTED | 극심한 서사 충돌 |
| `S_trp > 80` | INTERP_CONFLICTED | 함정 위험 과도 |
| `missing_ratio > 0.3` | INTERP_INVALID | 결측 과다 |

---

## 9. 봉인

- 점수 공식 잠금일: 2026-04-09
- 가중치(w1~w3)는 Shadow 검증 후 조정 가능 (Evolution 허용 범위)
- 임계값은 시장별 차등 적용 가능
- setup_type 추가/삭제는 Constitution 감사 대상
- 점수 공식 구조(항목 수, 합성 방식) 변경은 Constitution 감사 대상
