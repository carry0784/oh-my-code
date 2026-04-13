# Phase B: Replay Engine 설계 잠금 문서

**작성일:** 2026-04-09
**전제 조건:** Phase A ACCEPTED, 24-bar 종결 대기 중
**구현 승인 상태:** DESIGN_ONLY (구현 GO는 24-bar 종결 + 재판정 후)

---

## 1. 데이터 평면 봉인 규칙

Phase A에서 구축한 데이터 평면(`ohlcv_history`, `HistoryDataManager`, `detect_batch()`)의 사용 규칙을 잠급니다.

### 1.1 Replay 입력 스키마

```
입력: HistoryDataManager.get_replay_candles()
  -> list[list]  # [timestamp_ms, open, high, low, close, volume]
  -> BacktestingEngine.run(strategy, ohlcv, lookback) 호환

분할 기준:
  - open_time ASC 정렬 (DB 보장)
  - 단일 (exchange, symbol, timeframe) 범위
  - start_ts / end_ts로 구간 선택
```

**잠금 사항:**
- replay 입력은 반드시 `get_replay_candles()` 반환값 그대로 사용
- 실시간 데이터와 혼합 금지
- 같은 입력 → 같은 결과 (deterministic replay)

### 1.2 Train / Forward / Holdout 분할 규칙

400일 (9,600 1h candles) 기준:

```
┌─────────────────────────────────────────────────────────────┐
│  Train (240d)  │  Forward-1 (80d) │  FW-2 (40d) │ Holdout  │
│   5,760 bars   │    1,920 bars     │   960 bars  │ 960 bars │
│     60%        │      20%          │    10%      │   10%    │
└─────────────────────────────────────────────────────────────┘
```

| 구간 | 일수 | 비율 | 목적 | 데이터 접근 |
|------|------|------|------|------------|
| Train | 240 | 60% | 전략 파라미터 최적화 | 자유 |
| Forward-1 | 80 | 20% | 1차 전진검증 | Train 완료 후에만 |
| Forward-2 | 40 | 10% | 2차 전진검증 (안정성) | Forward-1 통과 후에만 |
| Holdout | 40 | 10% | 최종 blind test | Forward-2 통과 후에만 |

**분할 규칙:**
- 분할은 시간 기준 (timestamp 순서) — 무작위 셔플 금지
- 각 구간 경계는 candle open_time 기준으로 정의
- 구간 간 겹침(overlap) 금지

### 1.3 데이터 누수 금지 규칙

| 규칙 ID | 규칙 | 위반 시 결과 |
|---------|------|-------------|
| DL-001 | Train 구간 데이터는 Forward/Holdout 구간에 포함 불가 | FAIL |
| DL-002 | Forward-1 결과로 Train 파라미터 재조정 금지 | FAIL |
| DL-003 | Holdout은 최종 1회만 실행 (peek 금지) | FAIL |
| DL-004 | 미래 데이터(구간 외 timestamp) 참조 금지 | FAIL |
| DL-005 | lookback 윈도우가 구간 경계를 넘을 경우, 해당 bar 제외 | WARN |
| DL-006 | 전략의 analyze()에 전달되는 ohlcv는 해당 구간 내로 제한 | FAIL |

### 1.4 Batch Regime 결과의 실시간 경로 미연결 규칙

| 규칙 ID | 규칙 |
|---------|------|
| BR-001 | `detect_batch()` 결과는 분석/보고서용으로만 사용 |
| BR-002 | batch regime 판정이 실시간 전략 on/off에 자동 반영 금지 |
| BR-003 | batch regime → execution gate 자동 연결 금지 |
| BR-004 | regime_evolution.py의 기존 `partition_data_by_regime()`과 별개 경로 유지 |

---

## 2. FullCycleBacktester 설계

### 2.1 역할

기존 `BacktestingEngine`(단일 OHLCV 구간 백테스트)을 캡슐화하고, 400일 4-구간 분할 리플레이를 오케스트레이션합니다.

```
FullCycleBacktester
  ├── HistoryDataManager       (데이터 조회)
  ├── BacktestingEngine        (구간별 백테스트 실행)
  ├── PerformanceCalculator    (성능 산출)
  ├── RegimeDetector           (batch regime 판별)
  ├── WalkForwardValidator     (기존 WF 검증 재활용)
  └── FitnessFunction          (기존 fitness 평가 재활용)
```

### 2.2 인터페이스 초안

```python
@dataclass
class FullCycleConfig:
    """400-day full cycle backtest configuration."""
    exchange: str = "binance"
    symbol: str = "SOL/USDT"
    timeframe: str = "1h"
    train_ratio: float = 0.60      # 240d
    forward1_ratio: float = 0.20   # 80d
    forward2_ratio: float = 0.10   # 40d
    holdout_ratio: float = 0.10    # 40d
    lookback: int = 50
    backtest_config: BacktestConfig = field(default_factory=BacktestConfig)

@dataclass
class SegmentResult:
    """Single segment backtest result."""
    segment_name: str             # "train", "forward_1", "forward_2", "holdout"
    start_ts: int = 0
    end_ts: int = 0
    bars: int = 0
    backtest: BacktestResult = field(default_factory=BacktestResult)
    fitness: FitnessBreakdown = field(default_factory=FitnessBreakdown)
    regime_distribution: dict[str, float] = field(default_factory=dict)

@dataclass
class FullCycleResult:
    """Complete 400-day backtest result."""
    config: FullCycleConfig = field(default_factory=FullCycleConfig)
    segments: dict[str, SegmentResult] = field(default_factory=dict)
    walk_forward: WalkForwardResult | None = None
    regime_diversity_score: float = 0.0     # 1 - HHI(regime_proportions)
    overall_fitness: float = 0.0
    data_leakage_check: bool = True
    verdict: str = "PENDING"                # PASS / FAIL / PENDING

class FullCycleBacktester:
    """Orchestrates 400-day 4-segment backtest cycle.
    
    Design constraints:
      - Capsulates BacktestingEngine (does not replace it)
      - No runtime/execution coupling
      - No auto-promotion or gate activation
      - Results are informational only
    """
    
    def __init__(self, config: FullCycleConfig | None = None): ...
    
    async def run(
        self,
        session: AsyncSession,
        strategy: BaseStrategy,
    ) -> FullCycleResult:
        """Execute full 400-day backtest cycle.
        
        Sequence:
          1. Load replay candles from HistoryDataManager
          2. Validate data coverage (>= 95% required)
          3. Split into 4 segments
          4. Run BacktestingEngine on each segment sequentially
          5. Compute regime distribution per segment
          6. Calculate fitness per segment
          7. Run walk-forward validation on train segment
          8. Compute overall verdict
        """
        ...
    
    def _split_segments(
        self, ohlcv: list[list]
    ) -> dict[str, list[list]]:
        """Split OHLCV into train/forward1/forward2/holdout.
        
        Data leakage check:
          - No timestamp overlap between segments
          - Boundary bars belong to earlier segment
        """
        ...
    
    def _compute_regime_diversity(
        self, regime_results: list[BatchRegimeResult]
    ) -> float:
        """Regime Diversity Score = 1 - HHI(regime_proportions).
        
        Threshold: >= 0.55 (enough regime variety).
        """
        ...
    
    def _compute_verdict(
        self, result: FullCycleResult
    ) -> str:
        """Determine overall PASS/FAIL.
        
        PASS conditions:
          - Train fitness >= 0.4
          - Forward-1 fitness >= 0.3
          - Forward-2 fitness >= 0.25
          - Walk-forward efficiency_ratio >= 0.5
          - Walk-forward is_overfit == False
          - Regime diversity >= 0.55
          - Data leakage check == True
        """
        ...
```

### 2.3 기존 모듈과의 관계

| 기존 모듈 | Phase B에서의 역할 | 수정 여부 |
|-----------|-------------------|----------|
| `BacktestingEngine` | 구간별 백테스트 실행기로 그대로 사용 | **미수정** (capsulate) |
| `PerformanceCalculator` | 성능 산출 그대로 사용 | **미수정** |
| `FitnessFunction` | fitness 평가 그대로 사용 | **미수정** |
| `WalkForwardValidator` | train 구간 WF 검증 그대로 사용 | **미수정** |
| `RegimeDetector` | `detect_batch()` (Phase A 확장) 사용 | **Phase A에서 이미 확장 완료** |
| `HistoryDataManager` | replay candle 조회 | **Phase A에서 이미 생성 완료** |

**핵심:** Phase B는 기존 모듈을 조합하는 오케스트레이터만 신규 생성. 기존 모듈 수정 없음.

---

## 3. Regime Diversity Score (RDS) 공식

```
regime_proportions = [count_per_regime / total_valid_bars for each regime]
HHI = sum(p^2 for p in regime_proportions)
RDS = 1 - HHI

임계값: RDS >= 0.55
의미: 단일 레짐이 지배적이지 않아야 백테스트 결과가 편향되지 않음
```

예시:
- 5개 레짐 균등 분포: RDS = 1 - 5*(0.2^2) = 0.80 (PASS)
- 1개 레짐 100%: RDS = 1 - 1.0 = 0.00 (FAIL)
- 2개 레짐 50/50: RDS = 1 - 2*(0.5^2) = 0.50 (FAIL, < 0.55)

---

## 4. Phase B 금지 범위

| 금지 사항 | 이유 |
|-----------|------|
| `FullCycleResult`로 자동 전략 승격 | Decision/Execution 영역 침범 |
| API endpoint 등록 | 실시간 경로 연결 |
| Celery task 등록 | 자동 실행 경로 |
| `paper_trading_receipts` 참조 | Observation 체인 간섭 |
| 기존 모듈 (`BacktestingEngine` 등) 메서드 시그니처 변경 | 하위 호환성 파괴 |
| `FitnessFunction` 가중치 변경 | Decision 의미 변경 |
| `OhlcvHistory` 스키마 변경 | Phase A 봉인 위반 |

---

## 5. Phase B 산출물 목록 (구현 시)

| # | 파일 | 유형 | 예상 Lines |
|---|------|------|-----------|
| 1 | `app/services/full_cycle_backtester.py` | 신규 | ~350 |
| 2 | `scripts/phase_b_full_cycle_smoke.py` | 신규 | ~200 |
| 3 | 이 설계 문서 정합성 대조 검수본 | 보고서 | - |

---

## 6. Phase B 구현 진입 조건 (3-gate)

Phase B 구현 GO를 위해 아래 **3개 모두** 충족 필요:

```
B_ENTRY_CONDITION_1 = CR046_24BAR_FINAL_PASS
B_ENTRY_CONDITION_2 = PHASE_B_DESIGN_REVIEW_PASS
B_ENTRY_CONDITION_3 = OHLCV_400D_INGESTION_PATH_VERIFIED
```

| 조건 | 설명 | 현재 상태 |
|------|------|----------|
| `B_ENTRY_CONDITION_1` | CR-046 24-bar 최종 PASS + `OBSERVATION_REGRESSION = no_regression_final` | **NOT MET** (IN_PROGRESS) |
| `B_ENTRY_CONDITION_2` | 이 설계 문서 리뷰 ACCEPT (누수 규칙 / 분할 규칙 / 금지 범위 확인) | **NOT MET** (리뷰 대기) |
| `B_ENTRY_CONDITION_3` | 400일 OHLCV 실제 적재 경로 검증 (pagination, 중복 정규화, 데이터 연속성) | **NOT MET** (미착수) |

**3개 모두 MET일 때만 `PHASE_B_IMPLEMENTATION_GO = true`로 전환.**
설계 문서만 보고 성급히 구현하지 않으며, 데이터 없는 엔진 구현을 방지한다.

---

## 7. 무회귀 상태 3단계 정의

| 상태 | 조건 | 의미 |
|------|------|------|
| `no_regression_smoke` | 3-bar smoke PASS | 최소 검증만 통과 |
| `no_regression_so_far` | smoke + 진행 중 24-bar 무이상 | 현재까지 이상 없음 |
| `no_regression_final` | 24-bar 완전 종결 PASS | 최종 확정 |

현재 상태: **`no_regression_so_far`**

---

## 봉인 서명

- 설계 잠금일: 2026-04-09
- Phase A 승인: ACCEPTED
- Phase B 구현: DESIGN_ONLY (GO 대기)
- Phase B 진입 3-gate: 2026-04-09 고정 (리뷰 반영)
- B_ENTRY_CONDITION_1: NOT MET
- B_ENTRY_CONDITION_2: NOT MET
- B_ENTRY_CONDITION_3: NOT MET
