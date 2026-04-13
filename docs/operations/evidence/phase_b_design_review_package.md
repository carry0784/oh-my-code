# Phase B Replay Engine — 설계 검토 패키지 (Gate 2)

**문서 유형:** 설계 검토 패키지 (DESIGN REVIEW ONLY)
**작성일:** 2026-04-10
**상태:** REVIEW_PASSED (CONDITIONAL_PASS → 3건 해소 완료 → PASS)
**근거 문서:** `phase_b_replay_engine_design_lock.md`, `cr046_phase_b_gate_dashboard.md`
**검토 대상 Gate:** Gate 2 — `PHASE_B_DESIGN_REVIEW_PASS`

---

> **설계 GO / 구현 GO 분리 선언**
>
> 본 문서는 **설계 검토 전용**이다. 이 문서가 ACCEPT 판정을 받더라도 그것은 Gate 2 충족을 의미할 뿐이며, Phase B 구현 착수(`PHASE_B_IMPLEMENTATION_GO = true`)는 아래 3-gate 전체 충족 후 **별도 구현 GO 선언**이 있을 때만 허용된다.
>
> ```
> B_ENTRY_CONDITION_1 = CR046_24BAR_FINAL_PASS                   (Gate 1 — MET)
> B_ENTRY_CONDITION_2 = PHASE_B_DESIGN_REVIEW_PASS               (Gate 2 — 본 문서 검토 대상)
> B_ENTRY_CONDITION_3 = OHLCV_400D_INGESTION_PATH_VERIFIED       (Gate 3 — NOT MET)
> ```
>
> Gate 1, 2, 3 **모두 MET**일 때에만 구현 착수가 허용된다.

---

## 목차

1. 목적 및 범위
2. 입력 데이터 명세
3. Train / Forward / Holdout 분할 규칙
4. Data Leakage 방지 규칙 (DL-001~006)
5. Batch Regime 규칙 (BR-001~004)
6. FullCycleBacktester 인터페이스
7. 실패 방식 명세 (Failure Mode Spec)
8. 금지영역 정의
9. Shadow → Paper → Live 적용 순서
10. 검토 체크리스트

---

## 1. 목적 및 범위

### 1.1 Phase B Replay Engine이 하는 일

Phase B Replay Engine은 **400일(9,600개 1H 캔들)의 과거 OHLCV 데이터를 4개 구간(Train / Forward-1 / Forward-2 / Holdout)으로 분할하고, 각 구간별로 독립적인 백테스트를 순차 실행한 뒤, 전략의 일반화 능력을 정량적으로 평가**하는 오케스트레이션 레이어다.

주요 기능:

- `HistoryDataManager.get_replay_candles()`를 통해 봉인된 데이터 평면에서 재현 가능한 입력 획득
- 400일 데이터를 60%/20%/10%/10% 비율로 시간 순서 기준 분할
- 각 구간에 대해 기존 `BacktestingEngine`을 순차 실행 (캡슐화, 수정 없음)
- 구간별 fitness, 레짐 분포, Walk-Forward 효율 산출
- Regime Diversity Score(RDS)로 레짐 편향 탐지
- 최종 PASS/FAIL 판정을 `FullCycleResult.verdict` 필드에 기록

### 1.2 Phase B Replay Engine이 하지 않는 일

| 범위 밖 항목 | 이유 |
|-------------|------|
| 실시간 전략 on/off 자동 제어 | Execution 영역 침범 금지 |
| Paper trading receipt 생성 및 참조 | Observation 체인 간섭 금지 |
| 전략 파라미터 자동 업데이트 | Decision 영역 침범 금지 |
| API endpoint 또는 Celery task 등록 | 실시간 경로 연결 금지 |
| Gate 조건 자동 승격 | 인간 검토 우회 금지 |
| `BacktestingEngine` 등 기존 모듈 수정 | Phase A 봉인 유지 |
| 실시간 시세 데이터 혼합 | 결정론적 재현 보장 필요 |
| Holdout 구간 다회 실행 (peek) | Data leakage 방지 |

### 1.3 전제 조건

- Phase A ACCEPTED (OhlcvHistory 모델, HistoryDataManager, detect_batch() 구현 완료)
- Gate 1 MET: CR-046 C1-A 24/24 SEALED_PASS (2026-04-09)
- 대상 심볼: SOL/USDT (1순위), BTC/USDT (2순위, 지연 가드 필수)

---

## 2. 입력 데이터 명세

### 2.1 OhlcvHistory 모델 컬럼 명세

Phase B Replay Engine의 모든 입력은 `ohlcv_history` 테이블에서 조회된다.

| 컬럼 | 타입 | Nullable | 설명 |
|------|------|----------|------|
| `id` | String(36) | No | UUID PK |
| `exchange` | String(50) | No | 거래소 식별자 (예: `binance`) |
| `symbol` | String(20) | No | 심볼 (예: `SOL/USDT`) |
| `timeframe` | String(10) | No | 타임프레임 (예: `1h`) |
| `open_time` | BigInteger | No | 캔들 시작 Unix ms timestamp, (exchange+symbol+timeframe+open_time) 유니크 제약 |
| `open` | Float | No | 시가 |
| `high` | Float | No | 고가 |
| `low` | Float | No | 저가 |
| `close` | Float | No | 종가 |
| `volume` | Float | No | 거래량 |
| `event_week_flag` | Boolean | No | 주요 이벤트 주간 여부 (default: false) |
| `macro_event_type` | String(50) | Yes | 이벤트 유형 (FOMC, CPI, NFP, HALVING 등) |
| `high_volatility_flag` | Boolean | No | 고변동성 구간 여부 (default: false) |
| `ingested_at` | DateTime | No | 적재 시각 (UTC) |

**유니크 제약:** `uq_ohlcv_canonical_slot` — (exchange, symbol, timeframe, open_time)

**복합 인덱스:** `ix_ohlcv_lookup` — (exchange, symbol, timeframe, open_time)

### 2.2 Replay 입력 스키마

```
입력 경로: HistoryDataManager.get_replay_candles(
    session,
    exchange, symbol, timeframe,
    start_ts, end_ts
) -> list[list]

반환 형식: [[timestamp_ms, open, high, low, close, volume], ...]
정렬 보장: open_time ASC (DB 레벨 보장)
호환 대상: BacktestingEngine.run(strategy, ohlcv, lookback)
```

### 2.3 데이터 커버리지 요구 사항

| 항목 | 기준값 | 미달 시 동작 |
|------|--------|-------------|
| 전체 구간 커버리지 | >= 95% | FAIL — 실행 중단 |
| 단일 구간 최소 바 수 | Holdout >= 960bars (40d x 24h) | FAIL — 구간 실행 불가 |
| 누락 바 연속 허용 범위 | <= 5개 연속 gap | WARN — 로그 기록 후 계속 |

### 2.4 이벤트 메타데이터 활용 규칙

- `event_week_flag`, `high_volatility_flag`는 레짐 분석 보조 지표로만 사용
- 이벤트 메타데이터가 없는 캔들도 백테스트 실행에서 제외하지 않음
- 이벤트 메타데이터 기반 자동 필터링 또는 가중치 조정 금지 (분석/보고서 목적만 허용)

---

## 3. Train / Forward / Holdout 분할 규칙

### 3.1 분할 구조

400일 (9,600개 1H 캔들) 기준 4-구간 분할:

```
+---------------------------------------------------------+
|  Train (240d)  | Forward-1 (80d) | FW-2 (40d) | Holdout |
|   5,760 bars   |    1,920 bars   |   960 bars | 960 bars|
|     60%        |      20%        |    10%     |   10%   |
+---------------------------------------------------------+
  t=0           t=240d            t=320d      t=360d   t=400d
```

### 3.2 구간별 상세 명세

| 구간 | 일수 | 바 수 (1H) | 비율 | 목적 | 데이터 접근 허용 조건 |
|------|------|-----------|------|------|-------------------|
| Train | 240 | 5,760 | 60% | 전략 파라미터 최적화 + Walk-Forward | 무조건 허용 |
| Forward-1 | 80 | 1,920 | 20% | 1차 전진검증 (일반화 확인) | Train 구간 실행 완료 후에만 |
| Forward-2 | 40 | 960 | 10% | 2차 전진검증 (안정성 재확인) | Forward-1 통과 후에만 |
| Holdout | 40 | 960 | 10% | 최종 blind test (1회만) | Forward-2 통과 후에만 |

### 3.3 분할 구현 규칙

| 규칙 | 내용 |
|------|------|
| **시간 기준 분할** | open_time ASC 정렬 후 인덱스 슬라이싱 — 무작위 셔플 절대 금지 |
| **경계 정의** | 각 구간의 시작/끝은 candle `open_time` 기준 |
| **경계 바 귀속** | 경계 바는 앞 구간 소속 (inclusive left, exclusive right) |
| **겹침 금지** | 구간 간 timestamp 중복 발생 시 즉시 FAIL |
| **순차 실행** | Train → Forward-1 → Forward-2 → Holdout 순서로만 실행 |

### 3.4 PASS 조건 (구간별 fitness 임계값)

| 구간 | fitness 임계값 | Walk-Forward 조건 |
|------|--------------|-----------------|
| Train | >= 0.4 | efficiency_ratio >= 0.5, is_overfit == False |
| Forward-1 | >= 0.3 | — |
| Forward-2 | >= 0.25 | — |
| Holdout | 참고용 (판정 기준 아님, 1회 실행만) | — |

---

## 4. Data Leakage 방지 규칙 (DL-001~006)

### 4.1 규칙 상세

| 규칙 ID | 규칙 내용 | 위반 시 결과 | 탐지 방법 |
|---------|----------|------------|---------|
| **DL-001** | Train 구간 데이터는 Forward/Holdout 구간에 포함 불가 | FAIL — 전체 실행 중단 | `_split_segments()`에서 timestamp overlap 검사 |
| **DL-002** | Forward-1 결과로 Train 파라미터 재조정 금지 | FAIL — 결과 무효 처리 | Train 파라미터는 Train 실행 전에 고정, 이후 변경 불가 |
| **DL-003** | Holdout은 최종 1회만 실행 (peek 금지) | FAIL — 결과 무효 처리 | `FullCycleResult.holdout_executed` 플래그로 단일 실행 보장 |
| **DL-004** | 미래 데이터(구간 외 timestamp) 참조 금지 | FAIL — 전체 실행 중단 | 각 구간 실행 시 ohlcv 범위가 start_ts/end_ts 내로 제한됨을 검증 |
| **DL-005** | lookback 윈도우가 구간 경계를 넘을 경우, 해당 bar 제외 | WARN — 로그 기록 후 계속 | `lookback` 바 수만큼 각 구간 앞단 스킵 |
| **DL-006** | 전략의 `analyze()`에 전달되는 ohlcv는 해당 구간 내로 제한 | FAIL — 전체 실행 중단 | BacktestingEngine 호출 전 ohlcv 슬라이스 범위 검증 |

### 4.2 Leakage 체크 결과 기록

`FullCycleResult.data_leakage_check` 필드:
- `True`: 모든 DL 규칙 통과
- `False`: 하나라도 위반 시 → 전체 verdict = FAIL 확정

---

## 5. Batch Regime 규칙 (BR-001~004)

### 5.1 규칙 상세

| 규칙 ID | 규칙 내용 | 위반 시 결과 |
|---------|----------|------------|
| **BR-001** | `detect_batch()` 결과는 분석/보고서용으로만 사용 | 실시간 경로 연결 금지 |
| **BR-002** | batch regime 판정이 실시간 전략 on/off에 자동 반영 금지 | Execution 영역 침범 |
| **BR-003** | batch regime → execution gate 자동 연결 금지 | 인간 검토 없는 자동 승격 금지 |
| **BR-004** | `regime_evolution.py`의 기존 `partition_data_by_regime()`과 별개 경로 유지 | 두 경로 혼용 금지 |

### 5.2 batch regime 판정 사용 범위

| 허용 | 금지 |
|------|------|
| SegmentResult.regime_distribution 필드에 기록 | 실시간 RegimeDetector 상태 변경 |
| RDS 산출에 활용 | paper_trading_receipts에 전달 |
| 분석 보고서 생성 | Celery task 트리거 |
| 레짐 다양성 평가 (RDS >= 0.55 판정) | 자동 전략 파라미터 변경 |

### 5.3 Regime Diversity Score (RDS) 산출 공식

```
regime_proportions = [count_per_regime / total_valid_bars for each regime]
HHI = sum(p^2 for p in regime_proportions)
RDS = 1 - HHI

임계값: RDS >= 0.55 (PASS)
```

| 예시 | RDS | 판정 |
|------|-----|------|
| 5개 레짐 균등 분포 (각 20%) | 0.80 | PASS |
| 2개 레짐 50/50 분포 | 0.50 | FAIL |
| 1개 레짐 100% 지배 | 0.00 | FAIL |

---

## 6. FullCycleBacktester 인터페이스

### 6.1 구성 요소 관계도

```
FullCycleBacktester
  +-- HistoryDataManager       (Phase A 구현 완료 — 데이터 조회)
  +-- BacktestingEngine        (기존 모듈 — 구간별 백테스트 실행, 미수정)
  +-- PerformanceCalculator    (기존 모듈 — 성능 산출, 미수정)
  +-- RegimeDetector           (Phase A 확장 완료 — detect_batch() 사용)
  +-- WalkForwardValidator     (기존 모듈 — Train 구간 WF 검증, 미수정)
  +-- FitnessFunction          (기존 모듈 — fitness 평가, 미수정)
```

### 6.2 FullCycleConfig 데이터클래스

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `exchange` | str | `"binance"` | 거래소 식별자 |
| `symbol` | str | `"SOL/USDT"` | 대상 심볼 |
| `timeframe` | str | `"1h"` | 타임프레임 |
| `train_ratio` | float | `0.60` | Train 구간 비율 (240d) |
| `forward1_ratio` | float | `0.20` | Forward-1 구간 비율 (80d) |
| `forward2_ratio` | float | `0.10` | Forward-2 구간 비율 (40d) |
| `holdout_ratio` | float | `0.10` | Holdout 구간 비율 (40d) |
| `lookback` | int | `50` | 전략 lookback 바 수 |
| `backtest_config` | BacktestConfig | `BacktestConfig()` | 구간별 BacktestingEngine 설정 |

**제약:** `train_ratio + forward1_ratio + forward2_ratio + holdout_ratio == 1.0` 검증 필수

### 6.3 SegmentResult 데이터클래스

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `segment_name` | str | — | `"train"` / `"forward_1"` / `"forward_2"` / `"holdout"` |
| `start_ts` | int | `0` | 구간 시작 Unix ms timestamp |
| `end_ts` | int | `0` | 구간 종료 Unix ms timestamp |
| `bars` | int | `0` | 실제 실행된 바 수 |
| `backtest` | BacktestResult | `BacktestResult()` | BacktestingEngine 결과 |
| `fitness` | FitnessBreakdown | `FitnessBreakdown()` | FitnessFunction 평가 결과 |
| `regime_distribution` | dict[str, float] | `{}` | 레짐별 비율 (예: `{"bear_strong": 0.4, "sideways": 0.3, ...}`) |

### 6.4 FullCycleResult 데이터클래스

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `config` | FullCycleConfig | `FullCycleConfig()` | 실행에 사용된 설정 |
| `segments` | dict[str, SegmentResult] | `{}` | 구간명 → SegmentResult 매핑 |
| `walk_forward` | WalkForwardResult or None | `None` | Train 구간 Walk-Forward 결과 |
| `regime_diversity_score` | float | `0.0` | RDS (0.0~1.0) |
| `overall_fitness` | float | `0.0` | 전체 가중 fitness 점수 |
| `holdout_executed` | bool | `False` | Holdout 구간 실행 여부 (DL-003 단일 실행 강제용) |
| `data_leakage_check` | bool | `True` | DL 규칙 전체 통과 여부 |
| `verdict` | str | `"PENDING"` | `"PASS"` / `"FAIL"` / `"PENDING"` |

### 6.4.1 overall_fitness 산출 공식

```
overall_fitness = (
    w_train * fitness(Train)
  + w_fw1   * fitness(Forward-1)
  + w_fw2   * fitness(Forward-2)
) / (w_train + w_fw1 + w_fw2)

where:
  w_train = 0.40  (최적화 구간 — 기본 기여)
  w_fw1   = 0.35  (1차 전진검증 — 일반화 기여)
  w_fw2   = 0.25  (2차 전진검증 — 안정성 기여)

규칙:
  - Holdout fitness는 overall_fitness에 포함하지 않음 (blind test 목적 보존)
  - 구간 FAIL(fitness 미달) 시 해당 구간 가중치는 0으로 처리, 총 가중치 재정규화
  - 모든 구간 FAIL 시 overall_fitness = 0.0
```

### 6.5 FullCycleBacktester 메서드 시그니처

```
class FullCycleBacktester:
    """400일 4-구간 백테스트 사이클 오케스트레이터.

    설계 제약:
      - BacktestingEngine을 캡슐화 (대체 아님)
      - 실시간/실행 경로 연결 없음
      - 자동 승격 또는 gate 활성화 없음
      - 결과는 분석/판정용 전용
    """

    def __init__(self, config: FullCycleConfig | None = None): ...

    async def run(
        self,
        session: AsyncSession,
        strategy: BaseStrategy,
    ) -> FullCycleResult:
        """400일 전체 백테스트 사이클 실행.

        실행 순서:
          1. HistoryDataManager로부터 replay 캔들 로드
          2. 데이터 커버리지 검증 (>= 95% 필수)
          3. 4개 구간으로 시간 순 분할
          4. 각 구간별 BacktestingEngine 순차 실행
          5. 구간별 레짐 분포 산출
          6. 구간별 fitness 산출
          7. Train 구간 Walk-Forward 검증 실행
          8. RDS 산출
          9. 전체 verdict 결정
        """
        ...

    def _split_segments(
        self, ohlcv: list[list]
    ) -> dict[str, list[list]]:
        """OHLCV를 train/forward1/forward2/holdout으로 분할.

        DL 검증:
          - 구간 간 timestamp 중복 없음
          - 경계 바는 앞 구간 소속
        """
        ...

    def _compute_regime_diversity(
        self, regime_results: list[BatchRegimeResult]
    ) -> float:
        """RDS = 1 - HHI(regime_proportions). 임계값: >= 0.55."""
        ...

    def _compute_verdict(
        self, result: FullCycleResult
    ) -> str:
        """PASS/FAIL 판정.

        PASS 조건 (모두 충족 필요):
          - Train fitness >= 0.4
          - Forward-1 fitness >= 0.3
          - Forward-2 fitness >= 0.25
          - Walk-Forward efficiency_ratio >= 0.5
          - Walk-Forward is_overfit == False
          - RDS >= 0.55
          - data_leakage_check == True
        """
        ...
```

### 6.6 기존 모듈 수정 여부

| 기존 모듈 | Phase B에서의 역할 | 수정 여부 |
|-----------|-------------------|----------|
| `BacktestingEngine` | 구간별 백테스트 실행기 | **미수정** (캡슐화) |
| `PerformanceCalculator` | 성능 산출 | **미수정** |
| `FitnessFunction` | fitness 평가 | **미수정** |
| `WalkForwardValidator` | Train 구간 WF 검증 | **미수정** |
| `RegimeDetector` | `detect_batch()` 사용 | **Phase A 완료** |
| `HistoryDataManager` | replay 캔들 조회 | **Phase A 완료** |

---

## 7. 실패 방식 명세 (Failure Mode Spec)

### 7.1 실패 방식 목록

| FM ID | 실패 명칭 | 심각도 | 탐지 방법 | 완화 조치 |
|-------|----------|--------|---------|---------|
| FM-001 | 데이터 충분성 부족 | CRITICAL | 커버리지 < 95% | 실행 중단, 데이터 재적재 후 재시도 |
| FM-002 | 해석 점수 과적합 | HIGH | Train-Forward 지표 드리프트 > 임계 | 전략 파라미터 재검토, Holdout 실행 금지 |
| FM-003 | 상태 전이 과민 반응 | HIGH | 구간 내 레짐 전환 빈도 이상 | RDS 재산출, 레짐 탐지 임계값 재검토 |
| FM-004 | 실행 차단 규칙 미비 | MEDIUM | `block_score`가 어떤 구간에서도 발동 안 됨 | 전략 신호 분포 점검, block 조건 검토 |
| FM-005 | 학습 루프 노이즈 강화 | HIGH | Forward 구간 fitness < Train 구간의 50% | 전략 과적합 의심, Walk-Forward is_overfit 재확인 |
| FM-006 | 레짐 다양성 부족 | MEDIUM | RDS < 0.55 | 데이터 기간 조정 또는 레짐 분류 기준 재검토 |
| FM-007 | Lookback 경계 침식 | MEDIUM | 구간 유효 바 < 구간 총 바 * 0.90 | lookback 크기 재검토, 구간 최소 바 수 상향 |
| FM-008 | 결정론적 재현 위반 | HIGH | 동일 입력 2회 실행 → 결과 불일치 | random seed 고정 검증, 부동소수점 순서 보장 |

### 7.2 실패 방식 상세

#### FM-001: 데이터 충분성 부족

- **탐지 방법:** `HistoryDataManager.get_replay_candles()` 반환 후 실제 바 수 / 예상 바 수 비율 계산. 커버리지 < 95%이면 즉시 FAIL.
- **심각도:** CRITICAL — 이 상태에서 백테스트 결과는 신뢰 불가
- **완화 조치:** 실행 중단 후 `OHLCV_400D_INGESTION_PATH_VERIFIED`(Gate 3) 재검증, 데이터 재적재 후 재시도. 단일 구간 gap이 5개 연속을 초과하는 경우도 해당.

#### FM-002: 해석 점수 과적합 (Train-Forward 지표 드리프트)

- **탐지 방법:** `fitness(Forward-1) < fitness(Train) * 0.75` 이면 드리프트 과다. Walk-Forward `efficiency_ratio < 0.5` 또는 `is_overfit == True`와 조합 확인.
- **심각도:** HIGH — 전략이 Train 구간에만 특화된 것으로 판단
- **완화 조치:** Forward-2 및 Holdout 실행 중단, 전략 파라미터 재검토 후 처음부터 재실행. Forward-1 결과로 Train 파라미터를 재조정하는 것은 DL-002 위반이므로 금지.

#### FM-003: 상태 전이 과민 반응

- **탐지 방법:** 단일 구간(특히 Forward 구간) 내 레짐 전환 빈도가 Train 구간 대비 2배 이상인 경우. `regime_distribution` 엔트로피 급증 탐지.
- **심각도:** HIGH — 레짐 탐지기 자체의 신뢰도 문제
- **완화 조치:** `detect_batch()` 임계값 파라미터 재검토 (Phase A 범위). Phase B에서 임계값 직접 수정 불가 — Phase A 재검토 요청 필요.

#### FM-004: 실행 차단 규칙 미비

- **탐지 방법:** 전략의 `block_score` 또는 이에 상응하는 신호 필터가 Train/Forward 전 구간에서 단 한 번도 발동되지 않은 경우.
- **심각도:** MEDIUM — 과도한 신호 생성 또는 필터 로직 결함 가능성
- **완화 조치:** 신호 분포 히스토그램 점검, block 조건의 임계값과 조건부 로직 재검토. Phase B 결과 보고서에 기록 후 별도 검토.

#### FM-005: 학습 루프 노이즈 강화

- **탐지 방법:** `fitness(Forward-2) < fitness(Forward-1) * 0.80` 이거나, fitness 추이가 Train → Forward-1 → Forward-2 구간에서 단조 감소하는 경우.
- **심각도:** HIGH — 전략이 시간 경과에 따라 성능이 지속 하락하는 구조적 문제
- **완화 조치:** Holdout 실행 금지, 전략의 신호 생성 로직 및 파라미터 민감도 재분석 필요. 노이즈 강화 패턴은 과적합과 구분하여 보고.

#### FM-006: 레짐 다양성 부족

- **탐지 방법:** `regime_diversity_score < 0.55` (RDS = 1 - HHI < 0.55). 단일 레짐이 전체 바의 70% 이상을 차지하는 경우.
- **심각도:** MEDIUM — 특정 시장 상태에 편향된 백테스트 결과로 신뢰도 제한
- **완화 조치:** 400일 데이터 기간 조정 (시작점 변경), 레짐 분류 기준 재검토. RDS FAIL이 확정되면 `FullCycleResult.verdict = FAIL` 처리.

#### FM-007: Lookback 경계 침식

- **탐지 방법:** 각 구간에서 DL-005에 의해 lookback(=50) 바가 스킵된 후, 유효 바 수가 구간 총 바 수의 90% 미만으로 떨어지는 경우. 특히 Forward-2/Holdout(960 bar) 구간에서 ~5.2% 손실 발생 가능.
- **심각도:** MEDIUM — 유효 바 수 부족으로 통계적 신뢰도가 제한될 수 있음
- **완화 조치:** lookback 크기 대비 구간 최소 바 수 검증 로직 추가. 유효 바 수가 구간 임계 미만이면 WARN 로그 기록 후 보고서에 명시.

#### FM-008: 결정론적 재현 위반

- **탐지 방법:** 동일 입력(동일 OHLCV, 동일 config)으로 `FullCycleBacktester.run()`을 2회 실행하여 `FullCycleResult`의 verdict, overall_fitness, segments별 fitness가 동일한지 검증.
- **심각도:** HIGH — 재현 불가능한 백테스트는 모든 판정의 신뢰 기반을 훼손
- **완화 조치:** 전략 내 random seed 고정 확인, numpy 연산 순서 보장, 부동소수점 비결정성 탐지. 2회 실행 결과 불일치 시 verdict = FAIL 강제.

---

## 8. 금지영역 정의

Phase B 구현 범위에서 절대 포함되어서는 안 되는 항목:

| # | 금지 사항 | 위반 분류 | 이유 |
|---|----------|----------|------|
| 1 | `FullCycleResult`를 근거로 전략 자동 승격 처리 | Decision 영역 침범 | 인간 검토 없는 자동 전략 전환 금지 |
| 2 | Phase B 결과를 API endpoint에 직접 노출 | 실시간 경로 연결 | 백테스트 결과가 실행 경로에 개입 금지 |
| 3 | Celery task 등록 또는 스케줄 연동 | 자동 실행 경로 | 백테스트 자동 반복 실행 금지 |
| 4 | `paper_trading_receipts` 테이블 참조 또는 기록 | Observation 체인 간섭 | Phase B는 Observation 체인과 독립 |
| 5 | `BacktestingEngine`, `FitnessFunction` 등 기존 모듈의 메서드 시그니처 변경 | 하위 호환성 파괴 | Phase A 봉인 유지 |
| 6 | `FitnessFunction` 가중치 변경 | Decision 의미 변경 | 가중치는 별도 CR 없이 변경 불가 |
| 7 | `OhlcvHistory` 스키마 변경 | Phase A 봉인 위반 | 모델은 Phase A에서 확정 완료 |
| 8 | batch regime 결과를 실시간 RegimeDetector 상태에 반영 | BR-002 위반 | 분석 경로와 실행 경로 분리 원칙 |
| 9 | Holdout 구간 다회 실행 또는 중간 peek | DL-003 위반 | 최종 blind test 무결성 보장 |
| 10 | 실시간 시세 데이터와 `get_replay_candles()` 결과 혼합 | 결정론적 재현 위반 | 동일 입력 → 동일 결과 보장 |
| 11 | Forward 결과를 Train 파라미터 재조정에 활용 | DL-002 위반 | 미래 정보 역방향 누수 |
| 12 | Gate 조건 자동 업데이트 또는 승격 | 거버넌스 우회 | 3-gate는 인간 검토 후 수동 확정 |

---

## 9. Shadow → Paper → Live 적용 순서

Phase B Replay Engine의 결과는 **정보 제공 전용**이며, 실제 적용은 아래 단계적 순서를 따른다.

### 9.1 단계별 구조

```
[Phase B 실행] --> [Shadow 검증] --> [Paper 거래] --> [Live 거래]
                    (분석 전용)       (모의 실행)      (실제 자본)
```

### 9.2 Shadow 단계 (현재 단계)

| 항목 | 내용 |
|------|------|
| **목적** | Phase B 결과의 통계적 유의성 및 재현 가능성 확인 |
| **진입 조건** | 3-gate 전체 MET (`PHASE_B_IMPLEMENTATION_GO = true`) + 구현 GO 선언 |
| **실행 범위** | `FullCycleBacktester.run()` 결과 생성 및 분석 리포트 출력 |
| **금지 사항** | 실제 주문 제출, paper 환경 연결, 실시간 데이터 사용 |
| **종료 조건** | `FullCycleResult.verdict == PASS` + 분석 리포트 검토 완료 |
| **결과물** | `FullCycleResult` JSON 출력, Regime 분포 분석 보고서 |

### 9.3 Paper 단계

| 항목 | 내용 |
|------|------|
| **목적** | Shadow에서 검증된 전략 파라미터의 실시간 시장 적용 타당성 확인 |
| **진입 조건** | Shadow 단계 verdict == PASS + **별도 Paper 착수 승인** |
| **실행 범위** | SOL/USDT paper 환경에서 전략 신호 생성 및 모의 주문 실행 |
| **제한 사항** | BTC/USDT는 지연 가드(`cr046_btc_latency_guard_checklist.md`) 통과 필수 |
| **종료 조건** | Paper 기간 동안 무회귀 확인 + 슬리피지/실행 품질 기준 충족 |
| **결과물** | paper_trading_receipts 기록, 실행 품질 분석 보고서 |

### 9.4 Live 단계

| 항목 | 내용 |
|------|------|
| **목적** | 실제 자본을 투입한 제한적 실전 운영 |
| **진입 조건** | Paper 단계 완료 + **별도 Live 착수 승인** + 운영 준비도 검토 (`cr046_deployment_readiness_table.md`) |
| **실행 범위** | SOL/USDT 소규모 포지션, 킬스위치 및 포지션 사이즈 제한 활성화 |
| **제한 사항** | ETH/USDT는 연구 전용 — Live 금지 |
| **종료 조건** | Live 안정성 확인 + 별도 확장 승인 |

### 9.5 단계 간 이행 금지 사항

- Shadow → Paper 전환 시 자동 이행 금지 (인간 승인 필수)
- Paper → Live 전환 시 자동 이행 금지 (별도 CR 및 배포 준비도 검토 필수)
- Phase B 결과만으로 Paper 또는 Live 진입 금지
- 레짐 결과가 FAIL인 전략은 어떤 단계로도 진입 불가

---

## 10. 검토 체크리스트

본 문서의 Gate 2 (`PHASE_B_DESIGN_REVIEW_PASS`) 충족 여부를 판단하는 검토자 체크리스트:

### 목적 및 범위 (섹션 1)

- [ ] 1. Phase B Replay Engine의 기능적 목적이 명확하게 기술되어 있는가?
- [ ] 2. Phase B가 하지 않는 일(금지 범위)이 구체적으로 열거되어 있는가?
- [ ] 3. 실시간 실행 경로와의 분리가 명시되어 있는가?

### 입력 데이터 명세 (섹션 2)

- [ ] 4. OhlcvHistory 모델의 모든 컬럼이 명세되어 있는가?
- [ ] 5. 유니크 제약 (`uq_ohlcv_canonical_slot`)이 기술되어 있는가?
- [ ] 6. `get_replay_candles()` 반환 형식 및 정렬 보장이 명시되어 있는가?
- [ ] 7. 데이터 커버리지 요구 사항(>= 95%) 및 미달 시 동작이 정의되어 있는가?
- [ ] 8. 이벤트 메타데이터 활용 범위가 분석 목적으로 제한되어 있는가?

### Train/Forward/Holdout 분할 규칙 (섹션 3)

- [ ] 9. 240d/80d/40d/40d 분할 구조가 다이어그램 또는 표로 명시되어 있는가?
- [ ] 10. 시간 기준 분할 원칙과 무작위 셔플 금지가 명시되어 있는가?
- [ ] 11. 각 구간의 접근 허용 조건(순차 실행)이 명시되어 있는가?
- [ ] 12. 구간별 fitness 임계값이 정의되어 있는가?
- [ ] 13. 경계 바 귀속 규칙이 명시되어 있는가?

### Data Leakage 방지 규칙 (섹션 4)

- [ ] 14. DL-001 (Train 데이터 Forward/Holdout 포함 불가)이 기술되어 있는가?
- [ ] 15. DL-002 (Forward 결과로 Train 재조정 금지)가 기술되어 있는가?
- [ ] 16. DL-003 (Holdout 1회 실행 제한)이 기술되어 있는가?
- [ ] 17. DL-004 (미래 데이터 참조 금지)가 기술되어 있는가?
- [ ] 18. DL-005 (lookback 경계 초과 bar 제외)가 기술되어 있는가?
- [ ] 19. DL-006 (analyze() 입력 범위 제한)이 기술되어 있는가?
- [ ] 20. `data_leakage_check` 필드를 통한 결과 기록 방법이 명시되어 있는가?

### Batch Regime 규칙 (섹션 5)

- [ ] 21. BR-001 (detect_batch() 결과는 분석 목적만)이 기술되어 있는가?
- [ ] 22. BR-002 (실시간 on/off 자동 반영 금지)가 기술되어 있는가?
- [ ] 23. BR-003 (execution gate 자동 연결 금지)이 기술되어 있는가?
- [ ] 24. BR-004 (partition_data_by_regime()과 별개 경로 유지)가 기술되어 있는가?
- [ ] 25. RDS 산출 공식 및 임계값(>= 0.55)이 명시되어 있는가?

### FullCycleBacktester 인터페이스 (섹션 6)

- [ ] 26. FullCycleConfig 데이터클래스의 모든 필드가 정의되어 있는가?
- [ ] 27. SegmentResult 데이터클래스의 모든 필드가 정의되어 있는가?
- [ ] 28. FullCycleResult 데이터클래스의 모든 필드가 정의되어 있는가?
- [ ] 29. `run()`, `_split_segments()`, `_compute_regime_diversity()`, `_compute_verdict()` 시그니처가 명시되어 있는가?
- [ ] 30. PASS 조건 7개 항목이 `_compute_verdict()` 명세에 포함되어 있는가?
- [ ] 31. 기존 모듈의 수정 여부(미수정)가 확인되어 있는가?

### 실패 방식 명세 (섹션 7)

- [ ] 32. FM-001 (데이터 충분성 부족)의 탐지 방법, 완화 조치, 심각도가 기술되어 있는가?
- [ ] 33. FM-002 (해석 점수 과적합)의 탐지 방법, 완화 조치, 심각도가 기술되어 있는가?
- [ ] 34. FM-003 (상태 전이 과민 반응)의 탐지 방법, 완화 조치, 심각도가 기술되어 있는가?
- [ ] 35. FM-004 (실행 차단 규칙 미비)의 탐지 방법, 완화 조치, 심각도가 기술되어 있는가?
- [ ] 36. FM-005 (학습 루프 노이즈 강화)의 탐지 방법, 완화 조치, 심각도가 기술되어 있는가?
- [ ] 37. FM-006 (레짐 다양성 부족)의 탐지 방법, 완화 조치, 심각도가 기술되어 있는가?

### 금지영역 정의 (섹션 8)

- [ ] 38. 자동 전략 승격 금지가 명시되어 있는가?
- [ ] 39. API endpoint 등록 금지가 명시되어 있는가?
- [ ] 40. Celery task 등록 금지가 명시되어 있는가?
- [ ] 41. paper_trading_receipts 참조 금지가 명시되어 있는가?
- [ ] 42. 기존 모듈 시그니처 변경 금지가 명시되어 있는가?
- [ ] 43. OhlcvHistory 스키마 변경 금지가 명시되어 있는가?
- [ ] 44. Holdout 다회 실행 금지가 명시되어 있는가?

### Shadow → Paper → Live 적용 순서 (섹션 9)

- [ ] 45. Shadow 단계의 진입/종료 조건이 정의되어 있는가?
- [ ] 46. Paper 단계의 진입/종료 조건이 정의되어 있는가?
- [ ] 47. Live 단계의 진입 조건 및 제한 사항이 정의되어 있는가?
- [ ] 48. 단계 간 자동 이행 금지 및 인간 승인 필요성이 명시되어 있는가?
- [ ] 49. ETH/USDT Live 금지가 명시되어 있는가?

### 설계 GO / 구현 GO 분리 (문서 상단)

- [ ] 50. 본 문서가 설계 검토 전용임이 명시되어 있는가?
- [ ] 51. 3-gate 전체 MET 후 별도 구현 GO 선언 필요성이 명시되어 있는가?
- [ ] 52. 현재 Gate 상태 (Gate 1 MET, Gate 2/3 NOT MET)가 기술되어 있는가?

---

## 변경 이력

| 일시 | 버전 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 2026-04-10 | v1.0 | 최초 작성 — Gate 2 설계 검토 패키지 | carry0784 |
| 2026-04-10 | v1.1 | Gate 2 감사 3건 해소: C-1 holdout_executed 필드 추가, C-2 FM-001 임계값 95% 통일, C-3 overall_fitness 산출 공식 추가. FM-007/008 추가. | carry0784 |

---

*본 문서는 `phase_b_replay_engine_design_lock.md` 및 `cr046_phase_b_gate_dashboard.md`를 근거로 작성되었으며, Gate 2 (`PHASE_B_DESIGN_REVIEW_PASS`) 충족 여부 판정을 위한 공식 검토 자료로 사용된다.*
