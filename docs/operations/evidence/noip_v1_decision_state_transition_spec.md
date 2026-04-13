# NOIP v1 — Decision 상태 전이표 운영 명세서

**작성일:** 2026-04-09
**상태:** DESIGN_LOCKED
**계층:** Decision (3차 보조 주입)

---

## 1. 목적

Interpretation 결과를 실제 **진입 가능 / 금지 / 보류** 상태로 변환한다.
상태 전이는 결정론적(deterministic)이며, 모든 전이에 사유가 기록된다.

---

## 2. 상태 정의

| 상태 | 코드 | 의미 | 체류 가능 시간 |
|------|------|------|---------------|
| **IDLE** | `D_IDLE` | 관측 대기, 아무 이벤트 없음 | 무제한 |
| **WATCH** | `D_WATCH` | 관측 이벤트 감지, 추적 시작 | 최대 10 bars |
| **READY** | `D_READY` | 해석 점수 기준 충족, 진입 대기 | 최대 5 bars |
| **EXECUTABLE** | `D_EXECUTABLE` | 모든 조건 통과, 실행 가능 | 최대 3 bars (Setup Expiry) |
| **BLOCKED** | `D_BLOCKED` | 진입 금지 조건 활성 | 조건 해제까지 |
| **COOLDOWN** | `D_COOLDOWN` | 진입 완료/기회 상실 후 휴지 | 고정 N bars |
| **REVIEW** | `D_REVIEW` | 결과 확정, 학습 로그 기록 중 | 1 bar |

---

## 3. 상태 전이 규칙

### 3.1 전이 매트릭스

```
FROM \ TO     IDLE    WATCH   READY   EXEC    BLOCKED  COOLDOWN  REVIEW
─────────────────────────────────────────────────────────────────────────
IDLE           -      T01      -       -        -        -         -
WATCH         T02      -      T03      -       T04       -         -
READY         T05      -       -      T06      T07       -         -
EXECUTABLE    T08      -       -       -       T09      T10        -
BLOCKED       T11      -       -       -        -        -         -
COOLDOWN       -       -       -       -        -        -        T12
REVIEW        T13      -       -       -        -        -         -
```

### 3.2 전이 조건 상세

| 코드 | FROM → TO | 조건 | 사유 |
|------|-----------|------|------|
| **T01** | IDLE → WATCH | `len(events) >= 1` AND `data_quality_score >= 60` | 최소 1개 관측 이벤트 발생 |
| **T02** | WATCH → IDLE | `watch_bars > 10` OR `all scores < 30` | 타임아웃 또는 신호 소멸 |
| **T03** | WATCH → READY | `interp_state in (ABSORPTION, EXHAUSTION, ACCEPTANCE, REJECTION, SWEEP_REVERSAL)` AND `confidence >= CONF_MIN` | 해석 점수 기준 도달 |
| **T04** | WATCH → BLOCKED | `interp_state in (CONFLICTED, INVALID)` OR `EV_DATA_QUALITY_FAIL` | 해석 불가 또는 데이터 실패 |
| **T05** | READY → IDLE | `ready_bars > 5` OR `confidence dropped below CONF_MIN` | 타임아웃 또는 확신 하락 |
| **T06** | READY → EXECUTABLE | Constitution PASS AND Risk Budget PASS AND Execution Friction PASS | 전 조건 통과 |
| **T07** | READY → BLOCKED | Constitution FAIL OR Risk Budget FAIL OR `S_ncf > CONFLICT_MAX` | 상위 제한 활성 |
| **T08** | EXECUTABLE → IDLE | `exec_bars > 3` (Setup Expiry) | 실행 윈도우 만료 |
| **T09** | EXECUTABLE → BLOCKED | `S_efr > FRICTION_MAX` OR `spread_bps > T_sw * 2` OR kill_switch | 실행 환경 악화 |
| **T10** | EXECUTABLE → COOLDOWN | 주문 체결 완료 OR 부분 체결 후 취소 | 실행 완료 |
| **T11** | BLOCKED → IDLE | 차단 조건 해제 AND `blocked_bars > 3` | 안전 확인 후 복귀 |
| **T12** | COOLDOWN → REVIEW | `cooldown_bars >= COOLDOWN_LENGTH` | 휴지 기간 완료 |
| **T13** | REVIEW → IDLE | 학습 로그 기록 완료 | 사이클 종료 |

---

## 4. 의사결정 점수

### 4.1 진입 점수 (Entry Score)

```
entry_score = interp_confidence
  * direction_consistency_bonus
  * regime_alignment_bonus
  - conflict_penalty
  - friction_penalty

where:
  interp_confidence = InterpretationResult.confidence
  
  direction_consistency_bonus:
    = 1.10 if setup_direction == smc_trend direction
    = 1.00 if smc_trend == 0 (neutral)
    = 0.85 if setup_direction != smc_trend direction
  
  regime_alignment_bonus:
    = 1.10 if regime is favorable for setup_type
    = 1.00 if regime is neutral
    = 0.80 if regime is unfavorable
  
  conflict_penalty = S_ncf / 200  (max 0.5)
  friction_penalty = S_efr / 300  (max 0.33)
```

### 4.2 차단 점수 (Block Score)

```
block_score = max(
    S_ncf / 100,
    S_efr / 100,
    S_trp / 100,
    (1 - data_quality_score / 100),
)

BLOCKED if block_score > BLOCK_THRESHOLD (default: 0.7)
```

### 4.3 사이즈 팩터 (Size Factor)

```
size_factor = base_size
  * confidence_scale
  * volatility_scale
  * consecutive_loss_scale

where:
  base_size = max_position_size_usd (from config)
  
  confidence_scale:
    = 1.0 if entry_score >= 0.7
    = 0.7 if entry_score >= 0.5
    = 0.5 if entry_score >= 0.3
    = 0.0 if entry_score < 0.3 (no entry)
  
  volatility_scale:
    = 1.0 if atr_pct < 2%
    = 0.7 if atr_pct < 5%
    = 0.5 if atr_pct < 8%
    = 0.0 if atr_pct >= 8% (no entry)
  
  consecutive_loss_scale:
    = 1.0 if recent_consecutive_losses == 0
    = 0.7 if recent_consecutive_losses == 1
    = 0.5 if recent_consecutive_losses == 2
    = 0.0 if recent_consecutive_losses >= 3 (forced cooldown)
```

---

## 5. 진입 허용 조건 (AND 결합)

| # | 조건 | 임계값 | 위반 시 |
|---|------|--------|---------|
| E1 | `interp_state` ∈ 유효 setup 상태 | 5종 중 1개 | → BLOCKED |
| E2 | `entry_score >= ENTRY_MIN` | 0.30 | → stay READY |
| E3 | `S_ncf < CONFLICT_MAX` | 60 | → BLOCKED |
| E4 | `spread_bps < T_sw` | 15 bps | → BLOCKED |
| E5 | `data_quality_score >= 60` | 60 | → BLOCKED |
| E6 | `consecutive_losses < 3` | 3 | → forced COOLDOWN |
| E7 | `macro_event_proximity >= 15` | 15분 | → BLOCKED |
| E8 | `size_factor > 0` | >0 | → no entry |
| E9 | Constitution pass | - | → BLOCKED |
| E10 | Risk budget available | - | → BLOCKED |

---

## 6. 진입 금지 조건 (OR 결합 — 1개라도 해당 시 BLOCKED)

| # | 조건 | 즉시 BLOCKED |
|---|------|-------------|
| B1 | `macro_event_proximity < 15` | 거시 이벤트 직전 |
| B2 | `news_shock_flag == True` AND `S_ncf > 50` | 뉴스 급변 + 충돌 |
| B3 | `spread_bps > T_sw * 2` (30 bps) | 스프레드 극확대 |
| B4 | `data_quality_score < 40` | 데이터 심각 불량 |
| B5 | `S_trp > 80` | 함정 위험 극대 |
| B6 | `kill_switch active` | 거버넌스 긴급 정지 |
| B7 | `session_phase == PRE_OPEN` AND market != crypto | 장전 |
| B8 | `consecutive_losses >= 3` | 연속 손실 3회 |

---

## 7. COOLDOWN 규칙

| 조건 | COOLDOWN_LENGTH | 이유 |
|------|----------------|------|
| 정상 진입 후 | 3 bars | 동일 setup 재진입 방지 |
| 손실 청산 후 | 5 bars | 복수 매매 방지 |
| 연속 손실 3회 | 10 bars | 강제 냉각 |
| 이벤트 충격 후 | 5 bars | 급변 구간 회피 |

---

## 8. Setup Expiry Clock

EXECUTABLE 상태 진입 후 **최대 3 bars** 내 실행되지 않으면 자동 IDLE 복귀.

```
if exec_bars > SETUP_EXPIRY_BARS (default: 3):
    transition → IDLE
    reason = "SETUP_EXPIRED"
    log setup_type, direction, entry_score, expiry_bar_ts
```

---

## 9. Decision 출력 구조

```python
@dataclass
class DecisionOutput:
    """NOIP Decision 계층 출력."""
    timestamp: int
    symbol: str
    
    # 상태
    state: str = "D_IDLE"
    prev_state: str = "D_IDLE"
    transition_code: str | None = None    # T01~T13
    transition_reason: str = ""
    
    # 판정
    trade_allowed: bool = False
    side: str | None = None               # "LONG" / "SHORT"
    setup_type: str | None = None
    
    # 점수
    entry_score: float = 0.0
    block_score: float = 0.0
    conflict_penalty: float = 0.0
    
    # 사이즈
    size_factor: float = 0.0
    size_cap_usd: float = 0.0
    
    # 제한
    block_reason: str | None = None
    invalidation_condition: str | None = None
    
    # 컨텍스트
    confidence: float = 0.0
    expected_rr: float = 0.0
    cooldown_remaining: int = 0
    setup_expiry_remaining: int = 0
```

---

## 10. 전이 다이어그램

```
                    T01 (event detected)
          ┌─────────────────────────────┐
          │                             ▼
        IDLE ◄──── T02 (timeout) ──── WATCH
          ▲                             │
          │                    T03      │ T04
          │              (score met)    │ (invalid)
          │                    ▼        ▼
        T05 ◄────────────── READY ──► BLOCKED
       (timeout)              │          │
          ▲                   │ T06      │ T11
          │            (all pass)   (resolved)
          │                   ▼          │
        T08 ◄──────────── EXECUTABLE    │
       (expiry)               │          │
                              │ T10      │
                        (filled)    T09  │
                              ▼   (env) │
                          COOLDOWN      │
                              │          │
                              │ T12      │
                         (cooled)       │
                              ▼          │
                           REVIEW ───────┘
                              │
                              │ T13
                         (logged)
                              ▼
                            IDLE
```

---

## 11. 로그 필수 필드

모든 상태 전이 시 기록:

| 필드 | 타입 | 설명 |
|------|------|------|
| `log.timestamp` | int | 전이 시각 |
| `log.symbol` | str | 심볼 |
| `log.from_state` | str | 이전 상태 |
| `log.to_state` | str | 다음 상태 |
| `log.transition_code` | str | T01~T13 |
| `log.reason` | str | 전이 사유 |
| `log.entry_score` | float | 현재 진입 점수 |
| `log.block_score` | float | 현재 차단 점수 |
| `log.confidence` | float | 현재 확신도 |
| `log.setup_type` | str | 현재 setup (있으면) |
| `log.block_reason` | str | 차단 사유 (있으면) |
| `log.bars_in_state` | int | 현재 상태 체류 bar 수 |

---

## 12. Constitution 통과 검사

Decision이 READY → EXECUTABLE로 전이하기 전 반드시 확인:

| 헌법 조항 | 검사 내용 |
|-----------|----------|
| 조항 3 (단일 신호 금지) | `interp_state`가 유효 setup이고 점수 기반인지 |
| 조항 4 (설명 가능성) | `transition_reason` 비어있지 않은지 |
| 조항 5 (데이터 품질) | `data_quality_score >= 60` |
| 조항 7 (의도 추정 금지) | setup_type에 "intent" 기반 규칙 없는지 |
| 조항 10 (차단 우선) | `block_score < BLOCK_THRESHOLD` |

---

## 13. 임계값 요약

| 파라미터 | 기호 | 초안 값 | 비고 |
|----------|------|---------|------|
| `CONF_MIN` | 최소 confidence | 0.35 | WATCH→READY 진입 |
| `ENTRY_MIN` | 최소 entry_score | 0.30 | READY→EXECUTABLE |
| `BLOCK_THRESHOLD` | 차단 임계 | 0.70 | block_score 초과 시 |
| `CONFLICT_MAX` | 최대 conflict | 60 | S_ncf 초과 시 BLOCKED |
| `FRICTION_MAX` | 최대 friction | 70 | S_efr 초과 시 BLOCKED |
| `SETUP_EXPIRY_BARS` | 실행 만료 | 3 bars | EXECUTABLE 체류 한계 |
| `COOLDOWN_NORMAL` | 정상 냉각 | 3 bars | |
| `COOLDOWN_LOSS` | 손실 냉각 | 5 bars | |
| `COOLDOWN_STREAK` | 연속손실 냉각 | 10 bars | |
| `WATCH_TIMEOUT` | 감시 만료 | 10 bars | |
| `READY_TIMEOUT` | 준비 만료 | 5 bars | |

---

## 14. 봉인

- 상태 전이표 잠금일: 2026-04-09
- 임계값은 Shadow/Paper 검증 후 조정 가능 (Evolution 허용 범위)
- 상태 추가/삭제는 Constitution 감사 대상
- 전이 규칙(T01~T13) 추가/삭제는 Constitution 감사 대상
- BLOCKED 조건 추가는 허용 (안전 방향), 삭제는 Constitution 감사 대상
