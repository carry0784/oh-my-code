# CR-046 SOL C1-A — 진단 필드 설계서

**상태:** DESIGN LOCKED — 4개 잠금 항목 반영 완료 — A 승인 대기
**일시:** 2026-04-08
**선행 근거:** C1-B replay (`cr046_sol_c1b_replay_result.md`, evidence grade: observed_from_replay)

---

## 설계 원칙

1. **판단 계약 / 진단 계약 분리:** `analyze(): None | signal_dict` 계약은 변경하지 않는다. 진단 수집은 receipt builder(task layer)에서 별도 수행한다.
2. **append-only:** 기존 receipt 스키마의 기존 필드를 삭제/이름변경하지 않는다. 신규 필드만 추가한다.
3. **diagnostic_only:** 진단 필드는 자동 튜닝/파라미터 조정의 입력으로 직결 금지. `diagnostic_only=true` 메타 태그를 data JSON에 포함한다.
4. **SMC 중심 우선순위:** C1-B에서 SMC가 1차 병목(96.2% ZERO)으로 확정되었으므로, SMC 관련 필드가 1순위.
5. **BTC task 동기 수정 필수:** SOL과 BTC paper tasks의 receipt builder가 동일 구조를 사용하므로 양쪽 동시 적용.

---

## 표본 경계 (canonical denominator)

- **receipt 기준:** 24 bars (beat dispatch `:50:17` 기준)
- **replay 기준:** 26 bars (OHLCV bar 경계, 전후 1 bar 확장 포함)
- **canonical:** receipt 기준 24 bars. 비교 시 이 기준 사용.
- 상세: `cr046_sol_c1b_replay_result.md` "표본 경계 정의" 참조.

---

## 필드 설계

### 전략 반환 구조 변경

`analyze()` 계약(`None | signal_dict`)은 유지한다. 대신, 전략 내부에서 진단값을 **별도 메서드**로 노출한다.

```
# 기존 계약 유지
signal_result = strategy.analyze(ohlcv_list)  # None | signal_dict

# 신규: 진단 스냅샷 (항상 반환, signal 유무 무관)
diag = strategy.last_diagnostic()  # dict, analyze() 호출 후 즉시 사용 가능
```

`last_diagnostic()`은 analyze() 내부에서 계산된 중간값을 캐싱하여 반환한다. analyze() 계약에 영향 없음. BaseStrategy에 기본 구현(`return {}`)을 두고 SMCWaveTrendStrategy에서 override.

### 우선순위 1 — SMC 관련 (1차 병목)

| 필드명 | 타입 | 출처 | 설명 |
|--------|------|------|------|
| `smc_sig_raw` | int | `calc_smc_pure_causal()` signals[last_idx] | SMC signal (-1, 0, 1). **96.2% ZERO 확인됨** |
| `smc_trend_raw` | int | `calc_smc_pure_causal()` trend[last_idx] | 현재 SMC trend 방향 (-1, 0, 1) |
| `close_price` | float | ohlcv_list[-1][4] | 현재 bar close. swing level 대비 위치 판단용 |

### 우선순위 2 — WT 관련 (2차 병목)

| 필드명 | 타입 | 출처 | 설명 |
|--------|------|------|------|
| `wt_sig_raw` | int | `calc_wavetrend()` signals[last_idx] | WT signal (-1, 0, 1). **84.6% ZERO 확인됨** |
| `wt1_val` | float | `calc_wavetrend()` wt1[last_idx] | WT1 값 |
| `wt2_val` | float | `calc_wavetrend()` wt2[last_idx] | WT2 값 |
| `wt_cross_distance` | float | `abs(wt1 - wt2)` | cross까지의 거리. 근접도 추적용 |

### 우선순위 3 — 분류 / 메타

| 필드명 | 타입 | 출처 | 설명 |
|--------|------|------|------|
| `skip_reason_codes` | list[str] | consensus 판정 로직 | `[SMC_ZERO]`, `[WT_ZERO]`, `[SMC_ZERO, WT_ZERO]`, `[DIRECTION_MISMATCH]` |
| `near_miss_type` | str\|null | skip_reason_codes 기반 | `SMC_ONLY` / `WT_ONLY` / `DIR_MISMATCH` / null (both zero or consensus pass) |
| `diagnostic_only` | bool | 고정 | 항상 true. 자가진화 엔진 오연결 방지 |
| `diagnostic_version` | int | 고정 | 1 (초기). 향후 필드 추가 시 버전 증가. receipt 해석 버전 구분용 |
| `diagnostic_populated` | bool | 진단값 수집 성공 여부 | true: 진단값 정상 수집됨. false: 수집 실패/부분 누락 (기본값과 구분) |

### skip_reason_codes 정의

리스트형 단일 필드. 복수 코드 허용. `BOTH_ZERO` 코드는 제거 — `[SMC_ZERO, WT_ZERO]` 조합으로 표현.

| 코드 | 조건 |
|------|------|
| `SMC_ZERO` | `smc_sig == 0` |
| `WT_ZERO` | `wt_sig == 0` |
| `DIRECTION_MISMATCH` | `smc_sig != 0 and wt_sig != 0 and smc_sig != wt_sig` |
| `DATA_INSUFFICIENT` | `len(ohlcv) < min_bars` |

### near_miss_type 정의

| 값 | 조건 | C1-B 실측 |
|----|------|-----------|
| `SMC_ONLY` | smc_sig != 0 and wt_sig == 0 | 1건 (Bar 7) |
| `WT_ONLY` | smc_sig == 0 and wt_sig != 0 | 4건 (Bar 5, 17, 21, 25) |
| `DIR_MISMATCH` | smc_sig != 0 and wt_sig != 0 and smc_sig != wt_sig | 0건 |
| null | both zero or consensus pass | 21건 |

---

## Receipt data JSON 구조 (변경 후)

```json
{
  "action": "SKIP_SIGNAL_NONE",
  "bar_ts": 1775628000000,
  "signal": null,
  "symbol": "SOL/USDT",
  "strategy_version": "SMC_WaveTrend_1H_v2",
  "consensus_pass": false,
  "decision_source": "signal",
  "session_can_enter": false,
  "dry_run": true,
  "diagnostic_only": true,
  "diagnostic_version": 1,
  "diagnostic_populated": true,

  "smc_sig_raw": 0,
  "smc_trend_raw": 1,
  "wt_sig_raw": 0,
  "wt1_val": 25.65,
  "wt2_val": 24.82,
  "wt_cross_distance": 0.83,
  "close_price": 84.58,
  "skip_reason_codes": ["SMC_ZERO", "WT_ZERO"],
  "near_miss_type": null,

  "guard_pass": null,
  "guard_details": null,
  "halt_state": false,
  "block_reason": null,
  "entry_price": null,
  "expected_sl": null,
  "expected_tp": null,
  "receipt_id": "...",
  "session_id": "cr046_sol_paper_v1"
}
```

---

## 잠금 항목 (구현 GO 전 필수 확정)

### A. `last_diagnostic()` 상태 생명주기

| 시점 | 동작 | 상태 |
|------|------|------|
| `analyze()` 진입 직후 | `self._diag = {}` 초기화 | 이전 값 완전 소거 |
| `analyze()` 내부 — 지표 계산 완료 후 | smc_sig, wt_sig, wt1, wt2, smc_trend, close 값을 `self._diag`에 기록 | 중간값 캐싱 |
| `analyze()` 정상 종료 (None 반환) | `self._diag` 유지. skip_reason_codes, near_miss_type 생성 | 진단값 확정 |
| `analyze()` 정상 종료 (signal_dict 반환) | `self._diag` 유지. skip_reason_codes=[], near_miss_type=null | 진단값 확정 |
| `analyze()` 예외 발생 | `self._diag = {"diagnostic_populated": false}` | 부분/미정 상태 방지 |
| `last_diagnostic()` 호출 | `self._diag` 사본(copy) 반환 | 호출자가 원본 오염 불가 |
| 전략 객체 재사용 (다음 bar) | `analyze()` 진입 시 초기화되므로 stale 없음 | 안전 |

**불변식:** `last_diagnostic()`은 항상 직전 `analyze()` 호출의 결과를 반환한다. `analyze()`를 호출하지 않고 `last_diagnostic()`을 호출하면 `{}` (빈 dict)을 반환한다.

**동시성:** Celery solo-pool + `asyncio.run()` per task이므로 동일 전략 객체의 동시 호출은 발생하지 않는다. 전략 객체는 `create_fresh()` 패턴으로 task마다 새로 생성되므로 cross-task 오염 없음.

### B. `near_miss_type` canonical 생성 규칙

```python
# 정확히 이 로직으로만 생성. 해석 여지 없음.
def _compute_near_miss_type(smc_sig: int, wt_sig: int) -> str | None:
    if smc_sig != 0 and wt_sig == 0:
        return "SMC_ONLY"
    if smc_sig == 0 and wt_sig != 0:
        return "WT_ONLY"
    if smc_sig != 0 and wt_sig != 0 and smc_sig != wt_sig:
        return "DIR_MISMATCH"
    return None  # both zero or consensus pass
```

- 이 함수의 입력은 `smc_sig_raw`와 `wt_sig_raw`만 사용한다.
- 다른 조건(wt1/wt2 근접도, smc_trend 등)을 near_miss_type 판정에 사용하지 않는다.
- 변경 시 `diagnostic_version` 증가 필수.

### C. Receipt fallback 규칙

| 상황 | 동작 | receipt 생성 |
|------|------|-------------|
| 진단값 정상 수집 | 모든 진단 필드 기록, `diagnostic_populated=true` | 정상 |
| `last_diagnostic()` 빈 dict 반환 | 진단 필드 전부 null/기본값, `diagnostic_populated=false` | **정상 — receipt 생성 지속** |
| `analyze()` 예외 발생 | 기존 ERROR_FAIL_CLOSED 경로 유지, 진단 필드 미기록 | **정상 — 기존 에러 경로 보존** |
| 진단 필드 일부만 수집 | 수집된 필드만 기록, 나머지 null, `diagnostic_populated=false` | **정상** |

**핵심 불변식:** 진단값 수집 실패/부분 누락이 기존 receipt 생성 경로를 **절대 중단시키지 않는다**. 진단은 best-effort, receipt는 guaranteed.

### D. 6개 파일 exact scope lock

| # | 파일 경로 | 수정 목적 | 금지 변경 |
|---|----------|-----------|-----------|
| 1 | `strategies/base.py` | `last_diagnostic()` 기본 구현 추가 (`return {}`) | analyze() 시그니처 변경 금지 |
| 2 | `strategies/smc_wavetrend_strategy.py` | analyze() 내 `self._diag` 캐싱 + `last_diagnostic()` override | analyze() 반환값/계약 변경 금지, 지표 파라미터 변경 금지 |
| 3 | `workers/tasks/sol_paper_tasks.py` | analyze() 후 `strategy.last_diagnostic()` 수집 → receipt.data에 진단 필드 부착 | 기존 receipt 생성 경로 변경 금지, 진입/퇴출 로직 변경 금지 |
| 4 | `workers/tasks/btc_paper_tasks.py` | #3과 동일 (동기 수정) | #3과 동일 |
| 5 | `app/services/paper_trading_session_cr046.py` | PaperTradingReceipt에 optional 진단 필드 추가 (기본값 None) | 기존 필드 삭제/이름변경 금지 |
| 6 | `tests/` (신규: `test_diagnostic_fields.py`) | last_diagnostic() 반환값 검증, skip_reason_codes 정합성, near_miss_type canonical rule, fallback 테스트 | — |

**범위 밖 금지:** 위 6개 파일 외 수정 불가. `exchanges/`, `app/api/`, `app/models/`, `alembic/`, `docker-compose.yml` 등은 변경 대상 아님.

---

## 구현 대상 파일 목록

| 파일 | 변경 내용 | blast radius |
|------|----------|-------------|
| `strategies/smc_wavetrend_strategy.py` | `last_diagnostic()` 메서드 추가. analyze() 내부에서 중간값을 인스턴스 변수에 캐싱 | 낮음 — 기존 analyze() 반환값 변경 없음 |
| `strategies/base.py` | `last_diagnostic()` 기본 구현 (`return {}`) 추가 | 낮음 |
| `workers/tasks/sol_paper_tasks.py` | analyze() 호출 후 `strategy.last_diagnostic()`으로 진단값 수집, receipt.data에 부착 | 중간 — receipt builder 로직 확장 |
| `workers/tasks/btc_paper_tasks.py` | SOL과 동일 변경 (동기 수정 필수) | 중간 |
| `app/services/paper_trading_session_cr046.py` | PaperTradingReceipt dataclass에 신규 필드 추가 (optional, 기본값 None) | 낮음 — append-only |
| `tests/test_exchange_factory_isolation.py` | 변경 불필요 | 없음 |
| `tests/` (신규 or 기존) | last_diagnostic() 반환값 검증, skip_reason_codes 정합성 테스트 | 신규 테스트 추가 |

---

## 호환성 검수 포인트

| # | 검수 항목 | 기대 결과 | 검증 방법 |
|---|----------|-----------|-----------|
| 1 | 기존 receipt reader가 신규 필드 무시 가능 | 기존 receipt에 신규 필드 없어도 에러 없음 | 기존 receipt 조회 테스트 |
| 2 | analyze() 반환값 변경 없음 | None \| signal_dict 계약 유지 | 기존 테스트 전수 통과 |
| 3 | BTC paper tasks 동기 수정 | SOL과 동일 diagnostic 필드 | BTC 테스트 통과 |
| 4 | PaperTradingReceipt 기존 필드 보존 | 기존 24-bar receipt와 호환 | schema 비교 |
| 5 | diagnostic_only=true 포함 | 모든 신규 receipt에 메타 태그 | receipt 조회 확인 |
| 6 | live path 영향 0 | 진단 필드가 진입/퇴출 로직에 영향 없음 | 코드 리뷰 |

---

## Evidence Grade 정의

| 등급 | 의미 | 사용처 |
|------|------|--------|
| `inferred_from_backtest` | Phase 3 백테스트 기반 추정 | 기대 빈도 기준선 |
| `observed_from_replay` | C1-B replay에서 1회성 확인 | SMC_ZERO 96.2%, WT_ZERO 84.6% |
| `observed_from_live_receipt` | 진단 필드 구현 후 live receipt에서 관측 | C1-A 구현 후 7일 관측 |

---

## 비채택 항목 (이번 구현 범위에서 제외)

| 항목 | 제외 이유 | 향후 경로 |
|------|----------|-----------|
| `volatility_filter_pass` | Track C v2 예약 필드, 현재 C1 범위 밖 | Track C v2 CR에서 추가 |
| `always-return-diagnostic` (analyze 계약 변경) | blast radius 큼, BTC 동기화 리스크 | EV-1 진화 후보로 유지 |
| `DIRECTION_MISMATCH` 경보 | C1-B에서 0% 확인, 현재 비우선 | 필드는 유지, 경보는 보류 |
| `audit_trace_id` (parent/root 관계) | 단일 receipt 단계에서 trace chain 불필요 | exit/entry 연결 시 추가 |
| `regime_snapshot` | 현재 regime 분류 로직 미존재 (Track C v1 FAIL) | Track C v2에서 설계 |
| `market_context_bucket` | regime_snapshot과 동일 의존성 | Track C v2에서 설계 |
| `signal_density_20` (rolling metric) | 진화 후보, 1차 관측 확장과 분리 | 7일 관측 후 필요성 재판단 |
| SMC 2차 분해 (NO_BREAKOUT/RANGE_LOCKED 등) | C1-A 1차 설계 범위 초과 | 후속 확장 후보 |

---

## 금지 사항 (구현 시 재확인)

1. analyze() 반환값 변경 금지 (계약 유지)
2. 진단 필드를 진입/퇴출 조건으로 사용 금지
3. 진단 필드를 자동 파라미터 조정 입력으로 사용 금지
4. 기존 receipt 필드 삭제/이름변경 금지
5. 2/2 consensus 완화 금지
6. 파라미터(internal_length, n1, n2) 변경 금지
7. dry_run=False 전환 금지
8. 6개 파일 외 수정 범위 확산 금지
9. **비채택 항목 재유입 금지:** `volatility_filter_pass`, `always-return-diagnostic`, `regime_snapshot`, `market_context_bucket`, `audit_trace_id parent/root`, `signal_density_20`, SMC 2차 분해를 이번 구현에 끼워 넣는 것 금지

---

## 다음 단계

| 순서 | 작업 | 선행 조건 |
|------|------|-----------|
| 1 | **본 설계서 A 승인** | — |
| 2 | 구현 GO 발행 | 설계서 승인 |
| 3 | SOL + BTC task 동시 구현 | GO |
| 4 | 테스트 (기존 전수 통과 + 신규 진단 필드 검증) | 구현 완료 |
| 5 | PR → CI green → merge | 테스트 통과 |
| 6 | worker/beat 재시작 | merge |
| 7 | 7일 관측 (168 bars) → smc_sig=0/wt_sig=0 비율 집계 | 재시작 |
| 8 | Phase 3 대조 리포트 | 관측 완료 |
