# CR-048 RI-2A-1 Read-through Shadow Comparison 설계/계약 패키지

**문서 ID:** RI2A1-DESIGN-001
**작성일:** 2026-04-03
**전제 기준선:** v2.0 (5299/5299 PASS, RI-1 SEALED, RI-1A ACCEPT)
**전제 결정:**
- RI-2A Scope Review: CONDITIONAL ACCEPT
- RI-2A-1 (read-through 비교): **GO**
- RI-2A-2 (observation log + beat): DEFERRED
- RI-2B (bounded write): DEFERRED
**Authority:** A

---

## 1. RI-2A-1 목표

### 한 문장 정의

> **RI-2A-1 = "실시간 데이터 + DB 기존 결과를 입력으로 shadow pipeline을 실행하고, in-memory에서 비교한 뒤, 결과를 반환만 하고 아무것도 쓰지 않는다."**

### RI-2A-1이 하는 것

| 행위 | 허용 |
|------|:----:|
| 실시간 MarketDataSnapshot / BacktestReadiness 입력 | O |
| run_shadow_pipeline() 호출 (RI-1 SEALED pure) | O |
| DB에서 기존 screening_results SELECT | O |
| DB에서 기존 qualification_results SELECT | O |
| in-memory verdict 비교 | O |
| in-memory reason-level 비교 | O |
| ComparisonVerdict 반환 (caller에게) | O |

### RI-2A-1이 하지 않는 것

| 행위 | 금지 |
|------|:----:|
| DB INSERT (어떤 테이블이든) | **X** |
| DB UPDATE (어떤 테이블이든) | **X** |
| DB DELETE | **X** |
| Symbol.status 전이 | **X** |
| Celery beat task 등록 | **X** |
| 파일 I/O (로그 파일 제외) | **X** |
| screen_and_update() 호출 | **X** |
| qualify_and_record() 호출 | **X** |
| FROZEN 함수 수정 | **X** |
| RED 파일 접촉 | **X** |

### RI-1 대비 변경점

| 항목 | RI-1 | RI-2A-1 |
|------|:----:|:-------:|
| 입력 소스 | curated batch (수동) | **실시간 데이터 (caller 제공)** |
| 기존 결과 소스 | ShadowComparisonInput (수동 주입) | **DB SELECT (read-through)** |
| reason-level 비교 | 없음 | **있음** |
| DB 접촉 | 0 | **SELECT only** |
| DB write | 0 | **0** |
| 결과 저장 | JSON 파일 (스크립트) | **in-memory 반환만** |

---

## 2. 입력 소스 / 비교 대상 정의

### 2.1 Shadow Pipeline 입력

| 입력 | 타입 | 소스 | 비고 |
|------|------|------|------|
| market | `MarketDataSnapshot` | caller 제공 | data collection 결과 또는 테스트 fixture |
| backtest | `BacktestReadiness` | caller 제공 | 동일 |
| asset_class | `AssetClass` | caller 제공 | CRYPTO / US_STOCK / KR_STOCK |
| sector | `AssetSector` | caller 제공 | LAYER1, TECH 등 |
| fundamental | `FundamentalSnapshot | None` | caller 제공 (optional) | — |
| metadata | `SymbolMetadata | None` | caller 제공 (optional) | — |
| screening_thresholds | `ScreeningThresholds | None` | caller 제공 (optional) | None → default |
| qualification_thresholds | `QualificationThresholds | None` | caller 제공 (optional) | None → default |

**RI-2A-1 자체는 DB에서 입력을 조회하지 않습니다.**
입력은 caller가 제공합니다. DB read-through는 **비교 대상(기존 결과) 조회에만** 사용됩니다.

### 2.2 비교 대상 (DB read-through)

| 비교 대상 | 테이블 | 조회 쿼리 | 필드 |
|-----------|--------|-----------|------|
| 기존 screening | `screening_results` | `SELECT * WHERE symbol = ? ORDER BY screened_at DESC LIMIT 1` | `all_passed`, `stage1_exclusion` ~ `stage5_backtest`, `stage_reason_code` |
| 기존 qualification | `qualification_results` | `SELECT * WHERE symbol = ? ORDER BY evaluated_at DESC LIMIT 1` | `all_passed`, `check_*` (7개), `disqualify_reason`, `failed_checks` |

### 2.3 비교 결과 (반환값)

```python
@dataclass(frozen=True)
class ReadthroughComparisonResult:
    """RI-2A-1 comparison result. In-memory only, no persistence."""

    symbol: str
    shadow_result: ShadowRunResult              # shadow pipeline 출력
    comparison_verdict: ComparisonVerdict        # verdict-level 비교 결과
    reason_comparison: ReasonComparisonDetail | None  # reason-level 비교 (신규)
    existing_source: ExistingResultSource        # 기존 결과 출처 정보
```

---

## 3. Read-through 조회 경로

### 3.1 조회 함수 계약

```python
async def fetch_existing_for_comparison(
    db: AsyncSession,
    symbol: str,
) -> ShadowComparisonInput:
    """DB에서 기존 screening/qualification 결과를 읽어 비교 입력을 구성.

    Contract:
      - SELECT only (INSERT/UPDATE/DELETE 금지)
      - 기존 결과 없으면 existing_screening_passed=None 반환
      - 예외 발생 시 ShadowComparisonInput(None, None, None) 반환 (fail-closed)
    """
```

### 3.2 조회 경로 상세

```
fetch_existing_for_comparison(db, symbol="SOL/USDT")
  │
  ├─ SELECT screening_results
  │   WHERE symbol = 'SOL/USDT'
  │   ORDER BY screened_at DESC
  │   LIMIT 1
  │   → row가 있으면: existing_screening_passed = row.all_passed
  │   → row가 없으면: existing_screening_passed = None
  │
  ├─ SELECT qualification_results
  │   WHERE symbol = 'SOL/USDT'
  │   ORDER BY evaluated_at DESC
  │   LIMIT 1
  │   → row가 있으면: existing_qualification_passed = row.all_passed
  │   → row가 없으면: existing_qualification_passed = None
  │
  └─ return ShadowComparisonInput(
         existing_screening_passed=...,
         existing_qualification_passed=...,
         existing_screening_fail_reasons=...,   # 신규 필드
         existing_qualification_fail_reasons=..., # 신규 필드
     )
```

### 3.3 fail reason 추출 경로

| DB 필드 | 추출 방법 | 산출값 |
|---------|-----------|--------|
| `screening_results.stage1_exclusion` ~ `stage5_backtest` | False인 stage 이름 수집 | `{"stage2_liquidity", "stage3_technical"}` |
| `screening_results.stage_reason_code` | 직접 복사 | `"LOW_VOLUME"` |
| `qualification_results.failed_checks` | JSON parse | `["data_quality", "performance"]` |
| `qualification_results.disqualify_reason` | 직접 복사 | `"INSUFFICIENT_BARS"` |

---

## 4. Reason-level Comparison 규칙

### 4.1 ComparisonVerdict 확장

현재 ComparisonVerdict:
```python
class ComparisonVerdict(str, Enum):
    MATCH = "match"
    VERDICT_MISMATCH = "verdict_mismatch"
    REASON_MISMATCH = "reason_mismatch"
    INSUFFICIENT_EXISTING_DATA = "insufficient_existing_data"
```

RI-2A-1 확장 (A 지시: INSUFFICIENT 2종 분리):
```python
class ComparisonVerdict(str, Enum):
    MATCH = "match"
    VERDICT_MISMATCH = "verdict_mismatch"
    REASON_MISMATCH = "reason_mismatch"
    INSUFFICIENT_STRUCTURAL = "insufficient_structural"      # shadow DATA_REJECTED
    INSUFFICIENT_OPERATIONAL = "insufficient_operational"    # 기존 결과 없음
```

**기존 `INSUFFICIENT_EXISTING_DATA`는 2종으로 분리됩니다.**
하위 호환: 기존 테스트에서 `INSUFFICIENT_EXISTING_DATA`를 참조하는 곳은 적절한 신규 값으로 매핑합니다.

### 4.2 비교 흐름

```
Input: shadow_result, existing (from DB read-through)

Step 1: INSUFFICIENT 판정
  if existing.existing_screening_passed is None:
      → INSUFFICIENT_OPERATIONAL
  if shadow.verdict == DATA_REJECTED:
      → INSUFFICIENT_STRUCTURAL

Step 2: Verdict 비교
  shadow_screen_passed = verdict in (QUALIFIED, QUALIFY_FAILED)
  shadow_qual_passed = verdict == QUALIFIED
  if shadow_screen_passed != existing.screening_passed:
      → VERDICT_MISMATCH
  if existing.qual_passed is not None and shadow_qual_passed != existing.qual_passed:
      → VERDICT_MISMATCH

Step 3: Reason 비교 (verdict 일치 + 둘 다 fail인 경우만)
  if shadow_screen_passed == False and existing.screening_passed == False:
      shadow_fail_stages = {failed stages from ScreeningOutput}
      existing_fail_stages = {failed stages from DB}
      if shadow_fail_stages != existing_fail_stages:
          → REASON_MISMATCH

  if shadow_qual_passed == False and existing.qual_passed == False:
      shadow_fail_checks = {failed checks from QualificationOutput}
      existing_fail_checks = {failed checks from DB}
      if shadow_fail_checks != existing_fail_checks:
          → REASON_MISMATCH

Step 4: 전부 통과
  → MATCH
```

### 4.3 ReasonComparisonDetail 구조

```python
@dataclass(frozen=True)
class ReasonComparisonDetail:
    """Reason-level comparison breakdown. Audit-only, does not influence verdict."""

    screening_reasons_match: bool | None     # None = 비교 불가 (둘 다 pass이거나 insufficient)
    shadow_screening_fail_stages: frozenset[str] | None
    existing_screening_fail_stages: frozenset[str] | None
    qualification_reasons_match: bool | None
    shadow_qualification_fail_checks: frozenset[str] | None
    existing_qualification_fail_checks: frozenset[str] | None
```

### 4.4 verdict와 reason 지표 분리

A 지시에 따라 두 지표를 혼합하지 않습니다.

| 지표 | 계산 | 분모 |
|------|------|------|
| **verdict 일치율** | MATCH / (MATCH + VERDICT_MISMATCH + REASON_MISMATCH) | verdict 비교 가능 건 |
| **reason 일치율** | (MATCH where reason도 일치) / (같은 verdict fail 건) | reason 비교 가능 건 |

reason 일치율은 verdict 일치율의 **하위 지표**이며, verdict가 다르면 reason 비교 자체가 불가합니다.

---

## 5. DB Write 0 보장 방식

### 5.1 기술적 보장

| 보장 방법 | 상세 |
|-----------|------|
| **read-only session** | `fetch_existing_for_comparison`은 별도 read-only session 또는 `db.execute(select(...))` 만 사용 |
| **no `db.add()` 호출** | 함수 내 `db.add()`, `db.flush()`, `db.commit()` 호출 0회 |
| **no model instantiation for write** | ScreeningResult, QualificationResult, Symbol 등 INSERT용 인스턴스 생성 0 |
| **테스트 검증** | mock session에서 `add`, `flush`, `commit` 호출 0회 assert |

### 5.2 코드 수준 계약

```python
# 금지 패턴 (테스트에서 검증):
db.add(...)          # 금지
db.flush()           # 금지
db.commit()          # 금지
db.delete(...)       # 금지
db.execute(insert...) # 금지
db.execute(update...) # 금지
db.execute(delete...) # 금지

# 허용 패턴:
db.execute(select(...))  # 허용 (read-only)
```

### 5.3 purity guard 확장

`compare_shadow_to_existing()` 확장 부분은 여전히 **pure function**입니다.
DB 접촉은 `fetch_existing_for_comparison()`에만 격리되며,
비교 로직 자체는 in-memory pure입니다.

```
fetch_existing_for_comparison()  ← async, DB SELECT (격리)
    ↓ ShadowComparisonInput
compare_shadow_to_existing()     ← pure, no DB (기존 + 확장)
    ↓ ComparisonVerdict + ReasonComparisonDetail
```

---

## 6. State Change 0 보장 방식

### 6.1 접촉 불가 상태

| 상태 | 테이블/필드 | RI-2A-1 |
|------|-----------|:--------:|
| Symbol.status | symbols.status | **SELECT만** |
| Symbol.qualification_status | symbols.qualification_status | **SELECT만** |
| Symbol.candidate_expire_at | symbols.candidate_expire_at | **SELECT만** |
| PromotionState.current_status | promotion_states.current_status | **접촉 금지** |

### 6.2 상태 전이 규칙 (불변)

RI-2A-1은 상태 전이를 **읽을 수만** 있습니다.

```
WATCH → CORE: RI-2A-1에서 불가 (RI-2B scope)
CORE → WATCH: RI-2A-1에서 불가
CORE → EXCLUDED: RI-2A-1에서 불가
어떤 전이든: RI-2A-1에서 불가
```

---

## 7. FROZEN 호출/수정 여부 명시

### 7.1 FROZEN 함수 접촉표

| FROZEN 함수 | 호출 | 수정 | 경유 경로 |
|-------------|:----:|:----:|-----------|
| `run_screening_qualification_pipeline()` | **O** | **X** | run_shadow_pipeline() 내부 |
| `transform_provider_to_screening()` | **O** | **X** | run_shadow_pipeline() 내부 |
| `SymbolScreener.screen()` | **간접** | **X** | pipeline 내부 |
| `BacktestQualifier.qualify()` | **간접** | **X** | pipeline 내부 |
| `UniverseManager.select()` | **X** | **X** | 미사용 |
| `screen_and_update()` | **X** | **X** | RI-2B scope |
| `qualify_and_record()` | **X** | **X** | RI-2B scope |

### 7.2 핵심 원칙

> **RI-2A-1은 FROZEN 함수를 호출하되, 수정하지 않는다.**
> 호출 경로는 RI-1에서 이미 검증된 `run_shadow_pipeline()` 내부 경로와 동일하다.
> RI-2A-1에서 추가되는 것은 "비교 입력의 소스 변경" (수동 → DB read-through)뿐이다.

### 7.3 수정 허용 파일

| 파일 | 수정 유형 | 변경 내용 |
|------|-----------|-----------|
| `app/services/pipeline_shadow_runner.py` | **확장** | ComparisonVerdict 2종 INSUFFICIENT 분리, reason-level 비교 추가 |
| `tests/test_pipeline_shadow_runner.py` | **확장** | reason-level 비교 테스트, INSUFFICIENT 분리 테스트 |

### 7.4 신규 파일 (RI-2A-1 범위)

| 파일 | 유형 | 설명 |
|------|------|------|
| `app/services/shadow_readthrough.py` | **신규** | `fetch_existing_for_comparison()` + `run_readthrough_comparison()` |
| `tests/test_shadow_readthrough.py` | **신규** | read-through 조회 + 비교 테스트 |

**총 신규/수정: 4파일.** 마이그레이션 없음. 모델 없음. Celery 없음.

---

## 8. Fail-closed 규칙

### 8.1 예외 처리

| 예외 상황 | 행동 | 반환값 |
|-----------|------|--------|
| `run_shadow_pipeline()` 예외 | 즉시 중단, 예외 전파 | caller에게 예외 |
| `fetch_existing_for_comparison()` DB 연결 실패 | INSUFFICIENT_OPERATIONAL 반환 | 비교 불가로 처리 |
| `fetch_existing_for_comparison()` 쿼리 오류 | INSUFFICIENT_OPERATIONAL 반환 | 비교 불가로 처리 |
| `compare_shadow_to_existing()` 예외 | 즉시 중단, 예외 전파 | caller에게 예외 |
| 기존 결과 JSON 파싱 실패 (failed_checks 등) | reason 비교 SKIP, verdict만 비교 | reason_comparison = None |

### 8.2 fail-closed 원칙

```
DB 조회 실패 → INSUFFICIENT (비교 포기, 결과 반환)
Shadow 실패 → 예외 전파 (caller가 처리)
비교 실패 → 예외 전파 (caller가 처리)

절대로:
  DB 조회 실패 → 기존 결과 추정 (X)
  Shadow 실패 → 기본값 반환 (X)
  비교 실패 → MATCH로 간주 (X)
```

### 8.3 fail-closed 테스트 계약

| 테스트 | 검증 |
|--------|------|
| DB 연결 실패 시 INSUFFICIENT_OPERATIONAL 반환 | mock session raise → assert INSUFFICIENT_OPERATIONAL |
| 기존 결과 없을 때 INSUFFICIENT_OPERATIONAL | mock empty result → assert INSUFFICIENT_OPERATIONAL |
| shadow DATA_REJECTED → INSUFFICIENT_STRUCTURAL | assert 분류 정확 |
| JSON 파싱 실패 시 reason=None, verdict만 비교 | corrupt JSON mock → assert verdict 비교는 정상 |

---

## 9. Rollback 방식

### 9.1 Rollback 비용: TRIVIAL

RI-2A-1은 **DB write 0, 신규 테이블 0, Celery task 0**이므로:

| Rollback 항목 | 비용 |
|-------------|:----:|
| `app/services/shadow_readthrough.py` 삭제 | TRIVIAL |
| `tests/test_shadow_readthrough.py` 삭제 | TRIVIAL |
| `pipeline_shadow_runner.py` ComparisonVerdict 변경 revert | TRIVIAL |
| `test_pipeline_shadow_runner.py` 확장 부분 revert | TRIVIAL |

### 9.2 기존 기준선에 미치는 영향

| 기준선 항목 | 영향 |
|-----------|:----:|
| 5299 기존 테스트 | **0** (신규 파일 추가만) |
| 117 purity tests | **0** (Pure Zone 무접촉) |
| 87 contract tests | **0** |
| DB 스키마 | **0** (마이그레이션 없음) |
| FROZEN 함수 | **0** (수정 0줄) |

### 9.3 RI-1 복귀 보장

RI-2A-1을 전량 철회해도:
- RI-1 shadow pipeline 완전 작동 (코드 무변경 부분)
- 기존 ComparisonVerdict.INSUFFICIENT_EXISTING_DATA 복원 가능
- 어떤 DB 상태도 변경되지 않았으므로 cleanup 불필요

---

## 10. 테스트 계획

### 10.1 신규 테스트

| 테스트 Class | 파일 | 예상 tests | 검증 대상 |
|-------------|------|:----------:|-----------|
| **TestFetchExistingForComparison** | `test_shadow_readthrough.py` | ~6 | DB read-through 정확성 |
| - 기존 screening 있음 → 정확한 ShadowComparisonInput | | | |
| - 기존 qualification 있음 → 정확한 반환 | | | |
| - 기존 결과 없음 → None 반환 | | | |
| - DB 연결 실패 → None 반환 (fail-closed) | | | |
| - fail reason 추출 정확성 (stage별 False → fail stage 집합) | | | |
| - failed_checks JSON 파싱 정확성 | | | |
| **TestReadthroughComparison** | `test_shadow_readthrough.py` | ~5 | 전체 흐름 |
| - shadow + read-through → MATCH | | | |
| - shadow + read-through → VERDICT_MISMATCH | | | |
| - shadow + read-through → REASON_MISMATCH | | | |
| - shadow + read-through → INSUFFICIENT_STRUCTURAL | | | |
| - shadow + read-through → INSUFFICIENT_OPERATIONAL | | | |
| **TestReadthroughNoWrite** | `test_shadow_readthrough.py` | ~3 | DB write 0 검증 |
| - mock session에서 add/flush/commit 호출 0회 | | | |
| - INSERT/UPDATE/DELETE execute 호출 0회 | | | |
| - symbols 테이블 변경 0 | | | |

### 10.2 확장 테스트

| 테스트 Class | 파일 | 예상 tests | 검증 대상 |
|-------------|------|:----------:|-----------|
| **TestReasonLevelComparison** | `test_pipeline_shadow_runner.py` | ~6 | reason-level 비교 |
| - 같은 fail stages → MATCH | | | |
| - 다른 fail stages → REASON_MISMATCH | | | |
| - 같은 fail checks → MATCH | | | |
| - 다른 fail checks → REASON_MISMATCH | | | |
| - 하나가 None → reason 비교 SKIP | | | |
| - JSON 파싱 실패 → reason 비교 SKIP | | | |
| **TestInsufficientSplit** | `test_pipeline_shadow_runner.py` | ~4 | INSUFFICIENT 2종 분리 |
| - DATA_REJECTED → INSUFFICIENT_STRUCTURAL | | | |
| - 기존 없음 → INSUFFICIENT_OPERATIONAL | | | |
| - 기존 INSUFFICIENT_EXISTING_DATA 참조 호환 | | | |
| - 두 종류 동시 조건 시 우선순위 | | | |

### 10.3 테스트 총합

| 구분 | 예상 tests |
|------|:----------:|
| 신규 (test_shadow_readthrough.py) | ~14 |
| 확장 (test_pipeline_shadow_runner.py) | ~10 |
| **총 RI-2A-1 예상** | **~24** |

### 10.4 기존 기준선 보호

| 보호 조치 | 방법 |
|-----------|------|
| 5299 기존 테스트 전체 회귀 | pytest 전체 실행 후 PASS 확인 |
| 117 purity tests 유지 | Pure Zone 10 files 무접촉 확인 |
| ComparisonVerdict 하위 호환 | 기존 INSUFFICIENT_EXISTING_DATA 참조 테스트 업데이트 |
| pipeline_shadow_runner.py 순수성 | compare_shadow_to_existing 확장 부분도 pure 유지 |

---

## 요약

### RI-2A-1 범위 최종 정리

```
RI-2A-1 = Read-through Shadow Comparison

입력:
  ├─ MarketDataSnapshot (caller 제공)
  ├─ BacktestReadiness (caller 제공)
  └─ AssetClass, AssetSector (caller 제공)

처리:
  ├─ run_shadow_pipeline() (RI-1 SEALED, pure, 수정 0줄)
  ├─ fetch_existing_for_comparison() (DB SELECT only, 신규)
  └─ compare_shadow_to_existing() (pure, 확장: reason-level + INSUFFICIENT 분리)

출력:
  └─ ReadthroughComparisonResult (in-memory, 반환만)

DB 행위:
  ├─ SELECT: screening_results, qualification_results (read-through)
  ├─ INSERT: 0
  ├─ UPDATE: 0
  └─ DELETE: 0

파일 변경:
  ├─ 신규: shadow_readthrough.py, test_shadow_readthrough.py (2파일)
  ├─ 확장: pipeline_shadow_runner.py, test_pipeline_shadow_runner.py (2파일)
  └─ 합계: 4파일, 마이그레이션 0, 모델 0, Celery 0

FROZEN 수정: 0줄
RED 접촉: 0
Rollback: TRIVIAL
예상 테스트: ~24
```

---

## A 판정 요청

| 판정 대상 | 선택지 |
|----------|--------|
| RI-2A-1 설계/계약 | **승인 / 수정 요청 / 거부** |
| ComparisonVerdict INSUFFICIENT 2종 분리 | 승인 여부 |
| reason-level comparison 규칙 | 승인 여부 |
| RI-2A-1 구현 GO | 설계 승인 시 별도 GO 판정 |

---

```
CR-048 RI-2A-1 Read-through Design Contract v1.0
Baseline: v2.0 (5299/5299 PASS, RI-1 SEALED, RI-1A ACCEPT)
Scope: read-through shadow comparison (DB SELECT + in-memory compare)
DB write: ZERO (any table)
DB SELECT: screening_results, qualification_results (read-only)
New tables: ZERO
New migrations: ZERO
Celery tasks: ZERO
FROZEN modification: ZERO lines
RED access: ZERO
Files changed: 4 (2 new, 2 extended)
Estimated tests: ~24
Rollback cost: TRIVIAL
```
