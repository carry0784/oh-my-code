# SOL S-1 V-3 — Shadow Implementation Scope Lock GO

**발행일:** 2026-04-10
**chain:** Phase C Post-Closure — SOL S-1 Root-Cause Chain
**step:** V-3 pre-implementation scope lock
**previous_receipt:** `sol_s1_v3_go_receipt.md` (V-3 explicit GO)
**design_reference:** `sol_s1_v3_design.md`
**purpose:** 구현 착수 전 구현 경계 헌법화 (구현 오염 방지)

---

## 목적

V-3 설계와 explicit GO는 완료되었으나, 구현 단계에서 범위 오염이 발생할 수 있다. 본 receipt는 **구현 경계를 사전에 잠가** 구현자가 신규 모듈 경계를 넓히거나 기존 산출물을 변경하는 것을 원천 차단한다.

**핵심 원칙: 지금 필요한 것은 전략 로직이 아니라 구현 경계의 불변성이다.**

---

## Explicit Scope Lock GO — Verbatim

```text
V-3 SHADOW IMPLEMENTATION SCOPE LOCK GO

목적
V-3 shadow drift verification 구현 착수 전, 구현 범위와 산출물 경계를 잠근다.

허용
- 신규 V-3 shadow 전용 script/module 생성
- docs/operations/evidence/sol_s1_v3_*.md
- docs/operations/evidence/sol_s1_v3_*.json

금지
- 기존 V-1/V-2 scripts 수정
- sealed design 수정
- strategy parameter source 수정
- 공용 실행 엔진/기존 baseline 산출물 수정
- N1 shadow 실행 구현
- N3 비교/확장 구현
- 수익성 최적화 로직 추가

필수 evidence log fields
run_id
config_fingerprint
bars_observed
trades_count
ecr
block_rate
same_direction_ratio
same_direction_delta_pp
yellow_extension_count
invalid_run_count
final_state
receipt_completeness_pct
stop_reason
started_at
ended_at

허용 stop_reason enum
STOP_RED_ECR
STOP_RED_BLOCK_RATE
STOP_RED_SD_RATIO
STOP_INVALID_RUN
STOP_PASS_GREEN
STOP_YELLOW_EXTENSION_EXHAUSTED

종료 규칙
구현 완료 후 completion receipt 작성
STATE = STANDBY
다음 단계 = 별도 explicit GO 없이는 시작 금지
auto_advance = 금지
```

---

## 아이디어 3건 반영 조항 (리뷰 추가)

### 1. Evidence Log 추가 필수 필드 (아이디어 1)

기본 15개 필수 필드에 **추가 2개** 잠금:

| 필드 | 타입 | 설명 |
|------|------|------|
| `design_version` | str | 참조 설계 버전 (예: `sol_s1_v3_design.md@2026-04-10`) |
| `go_receipt_id` | str | 참조 GO receipt (예: `sol_s1_v3_go_receipt.md`) |

**총 필수 필드 = 16 + 2 = 18개** (GO 기본 16 + design_version + go_receipt_id)

### 2. Stop Reason Detail 필드 (아이디어 2)

기본 `stop_reason` enum에 **보조 필드** 추가:

| 필드 | 타입 | 제한 |
|------|------|------|
| `stop_reason_detail` | str | **최대 160자**, 단일 라인, 숫자/임계값/시점만 허용 |

**허용 예시:**
- `"ecr=54.3% < 55.0% threshold at bar 78"`
- `"block_rate=46.2% > 45.0% threshold, rolling window 3/3"`
- `"sd_delta=+16.4pp exceeds Red threshold"`
- `"invalid_data_missing at bar 42"`

**금지:**
- 자유 서술
- 다중 라인
- 해석/추론/의견
- 160자 초과

### 3. Completion Receipt 불변성 증거 필드 (아이디어 3)

completion receipt에 **무오염 증거 2줄** 강제:

| 필드 | 값 | 의미 |
|------|---|------|
| `baseline_mutation` | `false` (필수) | V-2 baseline 참조값 변경 없음 |
| `fallback_executed` | `false` (필수) | N1 fallback 자동 전환 없음 |

두 값이 `true`이면 V-3 자동 invalid 처리.

---

## 신규 생성 허용 파일명 패턴

```
scripts/sol_s1_v3_shadow_run.py           (실행 스크립트)
scripts/sol_s1_v3_shadow_*.py             (보조 모듈, 필요시)
docs/operations/evidence/sol_s1_v3_shadow_log.json
docs/operations/evidence/sol_s1_v3_completion_receipt.md
```

**파일명 패턴 제한:**
- `sol_s1_v3_*` prefix 필수
- shadow 외 이름 금지 (예: `sol_s1_v3_optimize_*` 불가)
- 기존 파일명과 충돌 금지

---

## 금지 파일 (Read-Only)

### Sealed Design / Baseline
- `docs/operations/evidence/sol_s1_v3_design.md` — 참조만
- `docs/operations/evidence/sol_s1_v3_go_receipt.md` — 참조만
- `docs/operations/evidence/sol_s1_v3_impl_scope_lock.md` — 본 문서
- `docs/operations/evidence/sol_s1_v2_*` — V-2 산출물 전체
- `docs/operations/evidence/sol_s1_v1_*` — V-1 산출물 전체
- `docs/operations/evidence/sol_s1_rootcause_*` — 루트 cause 문서

### Strategy Parameter Source
- `strategies/smc_wavetrend_strategy.py`
- `strategies/base_strategy.py` 및 관련 부모 클래스
- `app/core/config.py` 중 strategy 관련 파라미터

### 기존 V-1/V-2 Scripts
- `scripts/sol_s1_v1_consensus_window_backtest.py`
- `scripts/sol_s1_v2_combined_backtest.py`

### 공용 엔진
- `backtesting/engine.py`
- `backtesting/fitness.py`
- `backtesting/performance.py`

### 헌법/거버넌스
- `CLAUDE.md`
- 기타 거버넌스 문서

---

## Evidence Log 최종 필드 구조 (18 필수 + 3 선택)

### 필수 (18)

```json
{
  "run_id": "str",
  "config_fingerprint": "C1C2_N2_v3",
  "design_version": "sol_s1_v3_design.md@2026-04-10",
  "go_receipt_id": "sol_s1_v3_go_receipt.md",
  "bars_observed": "int",
  "trades_count": "int",
  "ecr": "float",
  "block_rate": "float",
  "same_direction_ratio": "float",
  "same_direction_delta_pp": "float",
  "yellow_extension_count": "int",
  "invalid_run_count": "int",
  "final_state": "GREEN|YELLOW|RED",
  "receipt_completeness_pct": "float",
  "stop_reason": "STOP_*",
  "stop_reason_detail": "str (<=160)",
  "started_at": "ISO8601",
  "ended_at": "ISO8601"
}
```

### 선택 (3)

```json
{
  "rolling_ecr_12": "float[]",
  "rolling_block_rate_12": "float[]",
  "rolling_sd_ratio_12": "float[]"
}
```

### 금지

- 수익 최적화 관련 exploratory field
- N3 관련 비교 field
- N1 shadow 실행 결과 field
- 자유 서술 주석 field

---

## Stop Reason Enum (최종 6개)

| Enum | 발동 조건 | 종류 |
|------|----------|------|
| `STOP_PASS_GREEN` | 기간 충족 + Green 상태 | 정상 완료 |
| `STOP_RED_ECR` | ECR < 55% | fail-closed |
| `STOP_RED_BLOCK_RATE` | block_rate > 45% | fail-closed |
| `STOP_RED_SD_RATIO` | SD_ratio > 85.9% | fail-closed |
| `STOP_INVALID_RUN` | invalid ≥ 1 | fail-closed |
| `STOP_YELLOW_EXTENSION_EXHAUSTED` | Yellow 연장 후 미복귀 | fail-closed |

enum 외 값 사용 금지. 새 enum 추가는 별도 explicit GO 필요.

---

## Completion Receipt 필수 필드 (종합)

V-3 GO receipt 4개 + Scope Lock 2개 = **총 6개 필수**:

```json
{
  "final_state": "GREEN|YELLOW|RED",
  "yellow_extension_count": "int",
  "same_direction_delta_pp": "float",
  "receipt_completeness_pct": "float",
  "baseline_mutation": "false",
  "fallback_executed": "false"
}
```

`baseline_mutation == true` 또는 `fallback_executed == true` 시 V-3 invalid.

---

## GO 발행 헌법 확인

```
✓ V-3 설계서 CLOSED / ACCEPT
✓ V-3 explicit GO 발행 완료
✓ 허용 파일 패턴 잠금
✓ 금지 파일 명시 (6 카테고리)
✓ 필수 evidence log field 18개 잠금
✓ stop_reason enum 6개 잠금
✓ stop_reason_detail 160자 제한
✓ completion receipt 필수 6개 필드
✓ baseline_mutation/fallback_executed 불변성 증거
✓ 신규 파일명 패턴 제한
✓ auto_advance 금지 유지
```

---

## Chain 상태 갱신

| 단계 | 상태 | 비고 |
|------|------|------|
| Root-Cause Analysis | CLOSED | COMPLETE |
| V-1 | CLOSED | INFORMATIVE_FAIL |
| V-2 | CLOSED | PASS (C1C2_N2) |
| V-3 설계서 | CLOSED | ACCEPT |
| V-3 GO 발행 | COMPLETE | `sol_s1_v3_go_receipt.md` |
| **V-3 구현 범위 잠금** | **COMPLETE** | **본 receipt** |
| V-3 구현 착수 | NOT STARTED | 별도 explicit GO 필요 |
| V-3 실행 | LOCKED | 구현 완료 필요 |
| V-4 | LOCKED | V-3 PASS + 추가 unlock 조건 |

---

## 봉인

- V-3 구현 범위가 본 receipt로 헌법화되었다
- 허용: `scripts/sol_s1_v3_shadow_*.py`, `docs/operations/evidence/sol_s1_v3_*.{md,json}`
- 금지: V-1/V-2 산출물, sealed design, strategy source, 공용 엔진, 헌법 문서
- evidence log 필수 필드는 18개이다 (기본 16 + design_version + go_receipt_id)
- stop_reason enum은 6개로 잠겨 있다
- stop_reason_detail은 최대 160자, 단일 라인, 숫자 중심이다
- completion receipt 필수 필드는 6개이다 (GO 4 + scope lock 2)
- baseline_mutation/fallback_executed 두 값은 반드시 false여야 한다
- 구현 착수는 본 receipt로 허가되지 않는다 — 별도 explicit GO 필요
- STATE = STANDBY
- auto_advance = 금지
