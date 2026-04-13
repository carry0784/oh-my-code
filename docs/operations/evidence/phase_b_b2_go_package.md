# Phase B B-2 — GO Package

**작성일:** 2026-04-10
**상태:** REVIEW_PENDING (사용자 GO 선언 대기)
**전제:** B-1 CLOSED_DONE, 회귀 기준선 고정

---

## 1. 목적

B-1에서 구현된 데이터클래스/분할기/누수검증 기반 위에 **평가 오케스트레이터 계층**만 추가한다.

- **입력:** SegmentSplitter.split() 결과 (4-segment candles)
- **처리:** 순차 백테스트 → 피트니스 → 레짐 다양성 → walk-forward → 판정
- **출력:** FullCycleResult (verdict = PASS / FAIL)

B-2는 **B-1 코어를 건드리지 않고 그 위에 평가 레이어만 얹는** bounded scope이다.

---

## 2. 변경 범위

### 2.1 변경 파일

| 파일 | 작업 유형 | 변경 내용 | 제한 |
|------|----------|-----------|------|
| `app/services/full_cycle_backtester.py` | **APPEND ONLY** | `FullCycleBacktester` 클래스 추가 | B-1 코어(dataclass + SegmentSplitter) 수정 금지 |

### 2.2 B-1 동결 영역 (FROZEN — 수정 절대 금지)

`full_cycle_backtester.py` 내에서 아래 구성요소는 B-2에서 **읽기 전용**:

| 동결 대상 | 라인 범위 (approx) |
|-----------|-------------------|
| 상수 (DEFAULT_*_RATIO, W_*, SEGMENT_NAMES, MIN_SEGMENT_BARS) | ~40-55 |
| `FullCycleConfig` dataclass | ~60-100 |
| `SegmentResult` dataclass | ~103-125 |
| `FullCycleResult` dataclass | ~128-170 |
| `SegmentSplitter` class (전체) | ~175-310 |

### 2.3 비변경 파일 (Phase A Sealed)

| 파일 | 이유 |
|------|------|
| `app/services/backtesting_engine.py` | 시그니처 불변 |
| `app/services/history_data_manager.py` | Phase A 봉인 |
| `app/services/fitness_function.py` | 가중치/공식 불변 |
| `app/services/walk_forward_validator.py` | WF 검증 불변 |
| `app/services/regime_detector.py` | 레짐 감지 불변 |
| `app/models/ohlcv_history.py` | 스키마 봉인 |
| `strategies/*.py` | 전략 불변 |
| alembic migrations | 마이그레이션 없음 |
| API routes / Celery tasks | 없음 |

---

## 3. 구현 명세

### 3.1 FullCycleBacktester 클래스

```python
class FullCycleBacktester:
    """400-day 4-segment full-cycle orchestrator.
    
    Composes existing modules — does NOT modify them.
    """
    
    def __init__(self, config: FullCycleConfig | None = None):
        # Compose dependencies (all as-is)
        self.config = config or FullCycleConfig()
        self._engine = BacktestingEngine(config.backtest_config)
        self._fitness = FitnessFunction()
        self._regime = RegimeDetector()
        self._wf = WalkForwardValidator(config=config.backtest_config)
    
    async def run(
        self,
        session: AsyncSession,
        strategy: BaseStrategy,
    ) -> FullCycleResult:
        """Execute full 4-segment cycle.
        
        Sequence:
          1. Load replay candles (HistoryDataManager)
          2. Validate coverage (>= 95%)
          3. Split into 4 segments (SegmentSplitter)
          4. Validate no leakage (DL-001~006)
          5. Run BacktestingEngine on each segment
          6. Compute fitness per segment
          7. Compute regime distribution per segment
          8. Run walk-forward on train segment
          9. Compute regime diversity score
         10. Compute overall_fitness
         11. Compute verdict
        """
```

### 3.2 내부 메서드

| 메서드 | 역할 | 호출 대상 |
|--------|------|-----------|
| `run()` | 전체 오케스트레이션 | 아래 모든 것 조합 |
| `_run_segment()` | 단일 세그먼트 백테스트 + 피트니스 | `BacktestingEngine.run()`, `FitnessFunction.evaluate()` |
| `_compute_regime_diversity()` | 레짐 다양성 점수 | `RegimeDetector.detect_batch()` |
| `_compute_overall_fitness()` | 가중 피트니스 | W_TRAIN/W_FORWARD1/W_FORWARD2 |
| `_compute_verdict()` | 7개 조건 PASS/FAIL 판정 | 순수 계산 |

### 3.3 의존성 호출 규약 (AS-IS, 변경 없음)

```python
# BacktestingEngine — 동기, 세그먼트별 1회
engine = BacktestingEngine(config.backtest_config)
result: BacktestResult = engine.run(strategy, segment_candles, lookback)

# FitnessFunction — 동기, 세그먼트별 1회  
fitness = FitnessFunction()
breakdown: FitnessBreakdown = fitness.evaluate(result.performance)

# RegimeDetector — 동기, 전체 candles 대상 1회
detector = RegimeDetector()
batch: list[BatchRegimeResult] = detector.detect_batch(all_candles)

# WalkForwardValidator — 동기, train segment 대상 1회
wf = WalkForwardValidator(config=config.backtest_config)
wf_result: WalkForwardResult = wf.validate(strategy, train_candles, lookback)
```

### 3.4 판정 조건 (PASS = 7개 전체 충족)

| # | 조건 | 임계값 |
|---|------|--------|
| 1 | Train fitness | >= 0.4 |
| 2 | Forward-1 fitness | >= 0.3 |
| 3 | Forward-2 fitness | >= 0.25 |
| 4 | WF efficiency_ratio | >= 0.5 |
| 5 | WF is_overfit | == False |
| 6 | Regime Diversity Score | >= 0.55 |
| 7 | Data leakage check | == True |

### 3.5 overall_fitness 공식

```
overall_fitness = (W_TRAIN * f(Train) + W_FORWARD1 * f(FW1) + W_FORWARD2 * f(FW2))
                  / (W_TRAIN + W_FORWARD1 + W_FORWARD2)

W_TRAIN = 0.40, W_FORWARD1 = 0.35, W_FORWARD2 = 0.25
Holdout: 별도 기록, overall_fitness에서 제외 (blind test)
```

### 3.6 Regime Diversity Score (RDS)

```
regime_proportions = [count_per_regime / total_valid_bars for each regime]
HHI = sum(p^2 for p in regime_proportions)
RDS = 1 - HHI

Threshold: RDS >= 0.55
```

---

## 4. DL/BR 규칙 준수

### B-2에서 추가로 검증할 DL 규칙

| Rule | 설명 | B-2 검증 방법 |
|------|------|-------------|
| DL-002 | Forward-1 결과로 Train 파라미터 재조정 금지 | strategy 인스턴스 train 후 재생성 안함 (단일 인스턴스 전달) |
| DL-003 | Holdout 정확히 1회 실행 | `holdout_executed` 플래그 1회 set |

### BR 규칙 준수

| Rule | 방법 |
|------|------|
| BR-001 | detect_batch() 결과는 분석/보고 전용 |
| BR-002 | batch regime verdict가 live on/off에 반영 안됨 (연결점 없음) |
| BR-003 | batch regime → execution gate 자동 연결 없음 |
| BR-004 | regime_evolution.py의 partition_data_by_regime()과 분리 |

---

## 5. 실패/중단 조건

### 즉시 중단 (ABORT)

| 코드 | 조건 |
|------|------|
| `ABORT_B1_CORE_MODIFIED` | B-1 동결 영역 변경 감지 |
| `ABORT_REGRESSION` | B-1 회귀 기준선 위반 (leakage, determinism) |
| `ABORT_SIGNATURE_BREAK` | 기존 모듈 시그니처 변경 필요 발견 |
| `ABORT_NONDETERMINISTIC` | 동일 입력 2회 실행 결과 불일치 |

### 경고 (WARN)

| 코드 | 조건 |
|------|------|
| `WARN_ALL_FAIL` | 모든 세그먼트 verdict = FAIL (전략 문제, 오케스트레이터 문제 아님) |
| `WARN_ZERO_TRADES` | 특정 세그먼트에서 거래 0건 |

---

## 6. 예상 산출물

| 산출물 | 유형 |
|--------|------|
| `FullCycleBacktester` class (~230 lines) | 코드 (append to existing file) |
| B-2 검증 실행 로그 | 콘솔 출력 |
| `phase_b_b2_completion_receipt.md` | 증거 |

---

## 7. 검증 계획

### B-2 완료 조건

1. `FullCycleBacktester.run()` 정상 실행 (SOL/USDT:USDT)
2. 4-segment 순차 백테스트 완료 (no crash)
3. fitness 계산 완료 (4 segments)
4. regime diversity score 계산 완료
5. walk-forward 실행 완료
6. overall_fitness 계산 완료
7. verdict 산출 (PASS or FAIL — 결과 무관, 판정 로직 동작 확인)
8. DL-002/003 준수 확인
9. B-1 회귀 기준선 유지 확인

### 회귀 검증

B-2 완료 후 아래를 재확인:

- B-1 SegmentSplitter.split() 결과 동일 (regression)
- validate_no_leakage() 결과 동일
- B-1 코어 코드 변경 없음

---

## 8. 봉인

- 본 패키지는 B-2 한정 GO를 위한 범위 정의이다
- 사용자 GO 선언 없이 B-2 착수는 금지이다
- B-2 완료가 B-3 자동 전이를 의미하지 않는다
- B-1 동결 영역 수정은 어떤 경우에도 금지이다
