# Phase B — Implementation GO Package

**작성일:** 2026-04-10
**상태:** REVIEW_PENDING (GO 선언 전)
**전제:** 3-gate ALL MET (`IMPLEMENTATION_ELIGIBLE_NOT_AUTHORIZED`)

---

## 1. 목적

Phase B Replay Engine — 400일 4-Segment FullCycleBacktester를 구현한다.

- **입력:** `HistoryDataManager.get_replay_candles()` → 9,600 candles/symbol
- **처리:** 4-segment 분할 → 순차 백테스트 → regime diversity → walk-forward → verdict
- **출력:** `FullCycleResult` (PASS / FAIL / PENDING)

Phase B는 **오케스트레이터 전용**이다. 기존 모듈을 변경하지 않는다.

---

## 2. 변경 범위 (Scope)

### 2.1 신규 파일 (NEW)

| # | 파일 | 유형 | 예상 규모 | 내용 |
|---|------|------|-----------|------|
| 1 | `app/services/full_cycle_backtester.py` | NEW | ~350 lines | FullCycleConfig, SegmentResult, FullCycleResult, FullCycleBacktester |
| 2 | `scripts/phase_b_full_cycle_smoke.py` | NEW | ~200 lines | Smoke 테스트 스크립트 (SOL/BTC 대상) |

### 2.2 변경 파일 (MODIFY)

**없음.** Phase B는 기존 모듈 시그니처를 변경하지 않는다.

### 2.3 비변경 범위 (Out of Scope) — 절대 금지

| 금지 대상 | 이유 |
|-----------|------|
| `app/services/backtesting_engine.py` | Phase A 봉인, 시그니처 불변 |
| `app/services/history_data_manager.py` | Phase A 봉인 (V-005 로깅 수정 제외, 이미 완료) |
| `app/models/ohlcv_history.py` | Phase A 스키마 봉인 |
| `strategies/smc_wavetrend_strategy.py` | 전략 로직 불변 |
| `app/services/performance_calculator.py` | 메트릭 계산 불변 |
| `app/services/fitness_function.py` | 피트니스 가중치 불변 |
| `app/services/walk_forward_validator.py` | WF 검증 불변 |
| `app/services/regime_detector.py` | 레짐 감지 불변 (detect_batch 사용만) |
| 모든 alembic migration | 신규 마이그레이션 없음 |
| 모든 API route | Phase B에 엔드포인트 없음 |
| 모든 Celery task | Phase B에 자동 실행 없음 |
| `paper_trading_receipts` 테이블 | 관측 체인 간섭 금지 |

---

## 3. 영향 분석 (Blast Radius)

### 3.1 의존성 그래프

```
FullCycleBacktester (NEW)
  ├── HistoryDataManager.get_replay_candles()     [READ ONLY]
  ├── BacktestingEngine.run()                     [AS-IS]
  ├── PerformanceCalculator.calculate()           [AS-IS]
  ├── RegimeDetector.detect_batch()               [AS-IS]
  ├── WalkForwardValidator.validate()             [AS-IS]
  └── FitnessFunction.evaluate()                  [AS-IS]
```

### 3.2 Blast Radius 표

| 계층 | 영향 | 수준 |
|------|------|------|
| Data (DB) | 읽기 전용 (ohlcv_history SELECT) | NONE |
| Service | 신규 파일 1개 추가, 기존 불변 | LOW |
| Strategy | 전략 코드 변경 없음 | NONE |
| API | 엔드포인트 없음 | NONE |
| Worker | Celery 태스크 없음 | NONE |
| Live Trading | 연결점 없음 | NONE |
| Model/Migration | 변경 없음 | NONE |

### 3.3 롤백 가능성

- **단순 파일 삭제로 완전 롤백 가능**
- 신규 파일 2개만 삭제하면 Phase A 상태로 복원
- DB 변경 없음, 마이그레이션 없음
- 기존 모듈 시그니처 불변

---

## 4. 구현 분해 (Bounded Scopes)

### Phase B-1: 데이터클래스 + 분할 로직

**범위:**
- `FullCycleConfig` dataclass
- `SegmentResult` dataclass
- `FullCycleResult` dataclass
- `_split_segments()` 메서드 (DL-001~006 준수)

**검증:**
- 분할 결과 timestamp 겹침 없음
- 경계 bar가 선행 세그먼트에 귀속
- lookback 경계 침범 bar 제외 (DL-005)

**예상:** ~120 lines

---

### Phase B-2: 오케스트레이터 + 레짐 + 판정

**범위:**
- `FullCycleBacktester.__init__()` + `run()`
- 4-segment 순차 실행 (BacktestingEngine.run × 4)
- `_compute_regime_diversity()` (RDS = 1 - HHI)
- `_compute_verdict()` (7개 PASS 조건)
- `overall_fitness` 계산 (w_train=0.40, w_fw1=0.35, w_fw2=0.25)

**검증:**
- Train → FW1 → FW2 → Holdout 순서 보장
- Holdout은 overall_fitness에서 제외
- 동일 입력 → 동일 결과 (결정론적 재현)

**예상:** ~230 lines

---

### Phase B-3: Smoke 테스트 + 준수 감사

**범위:**
- `scripts/phase_b_full_cycle_smoke.py`
- SOL/USDT 1종 대상 full cycle 실행
- 결과 JSON 로그 출력
- DL 규칙 위반 검사 자동화
- BR 규칙 준수 확인

**검증:**
- Smoke PASS (no crash, no leakage, deterministic)
- 2회 동일 실행 시 동일 결과 (결정론 검증)

**예상:** ~200 lines

---

## 5. Shadow-First 실행 계획

### 5.1 단계 정의

| 단계 | 이름 | 조건 | 산출물 |
|------|------|------|--------|
| S-0 | Smoke | 구현 완료 | smoke_pass.json |
| S-1 | Shadow (SOL) | Smoke PASS | shadow_sol_result.json |
| S-2 | Shadow (BTC) | S-1 no regression | shadow_btc_result.json |
| S-3 | Determinism Check | S-1 + S-2 PASS | determinism_receipt.md |
| S-4 | Shadow 판정 | S-3 PASS | shadow_verdict_receipt.md |

### 5.2 Shadow 기준선 (Baseline Metrics)

Phase B Shadow에서 관찰할 지표:

| 지표 | 기준 | 실패 조건 |
|------|------|-----------|
| Train fitness | >= 0.4 | < 0.4 → FAIL |
| Forward-1 fitness | >= 0.3 | < 0.3 → FAIL |
| Forward-2 fitness | >= 0.25 | < 0.25 → FAIL |
| WF efficiency_ratio | >= 0.5 | < 0.5 → FAIL |
| WF is_overfit | False | True → FAIL |
| Regime Diversity Score | >= 0.55 | < 0.55 → FAIL |
| Data leakage check | True | False → FAIL |

### 5.3 Regression 금지 항목

| 항목 | 설명 |
|------|------|
| Phase A smoke | `phase_a_replay_smoke.py` PASS 유지 |
| Gate 3 coverage | 100% 유지 (데이터 오염 없음) |
| 기존 모듈 시그니처 | 변경 시 즉시 중단 |
| 결정론적 재현 | 2회 실행 결과 불일치 시 즉시 중단 |

### 5.4 금지 전이

| 전이 | 상태 |
|------|------|
| Shadow → Paper | **금지** (Phase B 범위 밖) |
| Shadow → Live | **절대 금지** |
| Auto-promote via FullCycleResult | **금지** |

Phase B는 **오프라인 백테스트** 전용이다. Shadow 결과가 어떠하든 자동으로 Paper/Live 전이하지 않는다.

---

## 6. 실패/중단/복구 조건

### 6.1 즉시 중단 (ABORT)

| 코드 | 조건 | 조치 |
|------|------|------|
| `ABORT_SIGNATURE_BREAK` | 기존 모듈 시그니처 변경 필요 발견 | 구현 중단, 설계 재검토 |
| `ABORT_DATA_POLLUTION` | ohlcv_history에 의도치 않은 write 발생 | 구현 중단, 데이터 복구 |
| `ABORT_LEAKAGE_DETECTED` | DL-001~006 위반 감지 | 해당 세그먼트 결과 폐기 |
| `ABORT_NONDETERMINISTIC` | 동일 입력 2회 실행 결과 불일치 | 구현 중단, 원인 분석 |
| `ABORT_SCOPE_CREEP` | 비범위 파일 수정 시도 | 해당 변경 폐기 |

### 6.2 경고 (WARN)

| 코드 | 조건 | 조치 |
|------|------|------|
| `WARN_LOOKBACK_BOUNDARY` | DL-005 lookback 경계 bar 제외 | 로그 기록, 계속 |
| `WARN_LOW_DIVERSITY` | RDS < 0.55 but > 0.40 | 결과 기록, FAIL 판정 |
| `WARN_MARGINAL_FITNESS` | fitness가 임계값 ±0.05 이내 | 결과 기록, 주의 표시 |

### 6.3 복구 (Rollback)

```
1. 신규 파일 삭제: full_cycle_backtester.py, phase_b_full_cycle_smoke.py
2. DB 변경 없으므로 마이그레이션 롤백 불필요
3. Phase A 상태로 완전 복원 가능
```

---

## 7. Receipt 체계

### 7.1 구현 과정 Receipt

| Receipt | 시점 | 내용 |
|---------|------|------|
| `phase_b_implementation_go_receipt.md` | GO 선언 시 | 구현 착수 승인 증거 |
| `phase_b_b1_completion_receipt.md` | B-1 완료 시 | 데이터클래스 + 분할 검증 |
| `phase_b_b2_completion_receipt.md` | B-2 완료 시 | 오케스트레이터 + 판정 검증 |
| `phase_b_b3_smoke_receipt.md` | B-3 완료 시 | Smoke PASS 증거 |

### 7.2 Shadow 결과 Receipt

| Receipt | 시점 | 내용 |
|---------|------|------|
| `phase_b_shadow_sol_receipt.md` | S-1 완료 | SOL shadow 결과 + 기준선 비교 |
| `phase_b_shadow_btc_receipt.md` | S-2 완료 | BTC shadow 결과 + 기준선 비교 |
| `phase_b_determinism_receipt.md` | S-3 완료 | 결정론 2회 검증 증거 |
| `phase_b_shadow_verdict_receipt.md` | S-4 완료 | Phase B 최종 판정 |

---

## 8. 실행 순서 요약

```
[현재] IMPLEMENTATION_ELIGIBLE_NOT_AUTHORIZED
   │
   ▼  ← 본 문서 승인 (사용자 GO 선언)
[GO] IMPLEMENTATION_AUTHORIZED
   │
   ├── B-1: 데이터클래스 + 분할 ─── receipt → B-1 DONE
   ├── B-2: 오케스트레이터 + 판정 ─ receipt → B-2 DONE
   └── B-3: Smoke 테스트 ────────── receipt → B-3 DONE
   │
   ▼
[SMOKE] SMOKE_PASS
   │
   ├── S-1: Shadow SOL ──────────── receipt → S-1 DONE
   ├── S-2: Shadow BTC ──────────── receipt → S-2 DONE
   ├── S-3: Determinism Check ───── receipt → S-3 DONE
   └── S-4: Shadow 판정 ─────────── receipt → S-4 DONE
   │
   ▼
[VERDICT] PHASE_B_COMPLETE
```

---

## 9. 전이 규칙

```python
# 구현 착수 조건
IF (
    gate_1 == MET
    AND gate_2 == MET
    AND gate_3 == MET
    AND implementation_go_declared == True  # ← 사용자 명시적 선언
):
    PHASE_B_IMPLEMENTATION_GO = True

# 구현 완료 → Shadow 전이 조건
IF (
    b1_receipt == DONE
    AND b2_receipt == DONE
    AND b3_smoke_receipt == PASS
):
    PHASE_B_SHADOW_GO = True

# Shadow 판정 조건
IF (
    shadow_sol_pass == True
    AND shadow_btc_pass == True
    AND determinism_check == PASS
):
    PHASE_B_VERDICT = "PASS"  # or "FAIL"
```

---

## 10. 봉인

- 본 문서는 Phase B 구현 GO 패키지로, 승인 전까지 구현 착수 불가
- 사용자의 명시적 GO 선언이 본 문서의 승인을 의미한다
- GO 선언 없이 구현 코드 작성은 거버넌스 위반이다
- 본 문서 승인 시 `phase_b_implementation_go_receipt.md` 발행 필요
