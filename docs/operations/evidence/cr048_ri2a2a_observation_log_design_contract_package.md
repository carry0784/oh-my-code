# CR-048 RI-2A-2a 설계/계약 패키지

**문서 ID:** RI2A2A-DESIGN-001
**작성일:** 2026-04-03
**전제 기준선:** v2.1 (5330/5330 PASS, RI-2A-1 SEALED)
**전제 문서:**
- RI2A2-SCOPE-001 (RI-2A-2 범위 심사 — ACCEPT, 2a만 채택)
- RI2A1-SEALED (RI-2A-1 봉인 증빙)
**Authority:** A

---

## 1. Observation Table Schema

### 1.1 테이블 정의

```python
class ShadowObservationLog(Base):
    """Shadow observation record. Append-only. Not a business decision source."""

    __tablename__ = "shadow_observation_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ── 관찰 대상 ──
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    asset_class: Mapped[str] = mapped_column(String(16), nullable=False)
    asset_sector: Mapped[str] = mapped_column(String(32), nullable=False)

    # ── Shadow 결과 ──
    shadow_verdict: Mapped[str] = mapped_column(String(32), nullable=False)
    # qualified / screen_failed / qualify_failed / data_rejected
    shadow_screening_passed: Mapped[bool | None] = mapped_column(nullable=True)
    shadow_qualification_passed: Mapped[bool | None] = mapped_column(nullable=True)

    # ── 비교 결과 ──
    comparison_verdict: Mapped[str] = mapped_column(String(32), nullable=False)
    # match / verdict_mismatch / reason_mismatch / insufficient_structural / insufficient_operational
    existing_screening_passed: Mapped[bool | None] = mapped_column(nullable=True)
    existing_qualification_passed: Mapped[bool | None] = mapped_column(nullable=True)

    # ── Reason-level ──
    reason_comparison_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ReasonComparisonDetail serialized as JSON

    # ── Read-through metadata ──
    readthrough_failure_code: Mapped[str | None] = mapped_column(String(48), nullable=True)
    existing_screening_result_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    existing_qualification_result_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # ── 재현성 ──
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

    # ── 시각 ──
    shadow_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
```

### 1.2 인덱스

| 인덱스 | 컬럼 | 용도 |
|--------|------|------|
| `ix_shadow_obs_symbol` | (symbol) | symbol별 조회 |
| `ix_shadow_obs_created_at` | (created_at) | 시계열 집계, retention purge |
| `ix_shadow_obs_verdict` | (comparison_verdict, created_at) | verdict별 집계 |

### 1.3 테이블 특성

| 특성 | 값 |
|------|-----|
| FK | **없음** (기존 테이블과 완전 독립) |
| UNIQUE 제약 | **없음** (append-only, 중복 허용) |
| UPDATE 트리거 | **없음** |
| CASCADE | **없음** |
| business_impact | **false** — 이 테이블은 운영 의사결정의 소스가 아님 |

---

## 2. Append-only Contract

### 2.1 허용 DML

| DML | 허용 | 조건 |
|-----|:----:|------|
| INSERT | **O** | `record_shadow_observation()` 단일 경로만 |
| SELECT | **O** | 집계/조회 (읽기 전용) |
| UPDATE | **X** | 영구 금지 — 기록은 수정 불가 |
| DELETE | **X** | purge 전용 batch만 허용 (RI-2A-2a에서는 미구현) |

### 2.2 코드 수준 보장

| 보장 수단 | 상세 |
|-----------|------|
| 모델 | `ShadowObservationLog`에 UPDATE/DELETE 메서드 미구현 |
| 서비스 | `ShadowObservationService`에 `record_observation()` 1개 메서드만 노출 |
| 서비스 | `update_*`, `delete_*`, `modify_*` 메서드 없음 |
| 테스트 | mock DB에서 `db.merge()`, `db.delete()`, `db.execute(UPDATE/DELETE)` 호출 0회 검증 |
| 테스트 | `db.add()` + `db.flush()` 만 허용, 그 외 write 메서드 0회 검증 |

### 2.3 append-only 위반 감지

서비스에 write 금지 패턴이 등장하면 테스트가 실패합니다:
- `hasattr(service, 'update')` → False
- `hasattr(service, 'delete')` → False
- `grep -c "UPDATE\|DELETE\|merge\|remove" shadow_observation_service.py` → 0 (docstring 제외)

---

## 3. Insert Contract

### 3.1 입력 소스

`record_shadow_observation()`의 입력은 RI-2A-1에서 이미 생성된 객체입니다:

| 입력 | 타입 | 출처 |
|------|------|------|
| `shadow_result` | `ShadowRunResult` | `run_shadow_pipeline()` (RI-1 SEALED) |
| `readthrough_result` | `ReadthroughComparisonResult` | `run_readthrough_comparison()` (RI-2A-1 SEALED) |

### 3.2 필드 매핑

| observation 필드 | 소스 | 변환 |
|-----------------|------|------|
| symbol | shadow_result.symbol | 직접 |
| asset_class | 호출자 제공 | 직접 |
| asset_sector | 호출자 제공 | 직접 |
| shadow_verdict | shadow_result.pipeline_output.verdict.value | enum → str |
| shadow_screening_passed | shadow_result.pipeline_output.screening_passed | 직접 |
| shadow_qualification_passed | shadow_result.pipeline_output.qualification_passed | 직접 |
| comparison_verdict | readthrough_result.comparison_verdict.value | enum → str |
| existing_screening_passed | readthrough_result에서 추출 | 직접 |
| existing_qualification_passed | readthrough_result에서 추출 | 직접 |
| reason_comparison_json | readthrough_result.reason_comparison | dataclass → JSON |
| readthrough_failure_code | readthrough_result.existing_source.failure_code | enum → str or None |
| existing_screening_result_id | readthrough_result.existing_source.screening_result_id | 직접 |
| existing_qualification_result_id | readthrough_result.existing_source.qualification_result_id | 직접 |
| input_fingerprint | shadow_result.input_fingerprint | 직접 |
| shadow_timestamp | shadow_result.shadow_timestamp | 직접 |
| created_at | DB server_default (now()) | 자동 |

### 3.3 Insert 함수 시그니처

```python
async def record_shadow_observation(
    db: AsyncSession,
    shadow_result: ShadowRunResult,
    readthrough_result: ReadthroughComparisonResult,
    asset_class: AssetClass,
    asset_sector: AssetSector,
) -> ShadowObservationLog | None:
    """Record one shadow observation. Append-only INSERT.

    Returns:
        ShadowObservationLog on success, None on failure.
        INSERT failure does NOT raise — logged and swallowed.
    """
```

### 3.4 Insert 실패 처리

```python
try:
    row = ShadowObservationLog(...)
    db.add(row)
    await db.flush()
    return row
except Exception:
    logger.exception("shadow observation INSERT failed for %s", symbol)
    return None  # 실패 시 None 반환, 예외 전파 안 함
```

**핵심:** INSERT 실패는 **절대** 호출자에게 예외를 전파하지 않습니다.

---

## 4. Duplicate Handling Rule

### 4.1 중복 정의

"동일 symbol + 유사 시각에 동일 input_fingerprint로 기록된 2+ 행"

### 4.2 중복 정책: **허용 (append-only 원칙 유지)**

| 선택지 | 채택 | 이유 |
|--------|:----:|------|
| UNIQUE 제약으로 차단 | **X** | INSERT 실패 → 에러 처리 복잡화, append-only 원칙 위반 가능 |
| upsert (ON CONFLICT UPDATE) | **X** | UPDATE 금지 위반 |
| **중복 허용 + 집계 시 dedup** | **O** | append-only 보장, INSERT 실패 없음, 집계에서 처리 |

### 4.3 Dedup 키 (집계 시)

집계 쿼리에서 중복 제거 시 사용:
```sql
-- 같은 symbol + fingerprint + shadow_timestamp 조합에서 가장 먼저 기록된 행만
ROW_NUMBER() OVER (
    PARTITION BY symbol, input_fingerprint, shadow_timestamp
    ORDER BY created_at ASC
) = 1
```

### 4.4 중복 발생 빈도 예상

수동 트리거에서는 중복 가능성이 매우 낮습니다.
같은 입력을 의도적으로 2번 실행하지 않는 한 발생하지 않습니다.
beat (RI-2A-2b)에서는 task 재시도로 발생 가능 — 그때 재검토.

---

## 5. Idempotency / Uniqueness Rule

### 5.1 Idempotency 전략: **Non-idempotent (append-only)**

| 전략 | 채택 | 이유 |
|------|:----:|------|
| Idempotent (같은 입력 → 같은 결과, 1행만) | **X** | UNIQUE 제약 또는 upsert 필요 → append-only 위반 |
| **Non-idempotent (같은 입력 → 추가 행)** | **O** | append-only 원칙 유지, 중복은 집계 시 처리 |

### 5.2 Uniqueness

- 테이블에 UNIQUE 제약 **없음**
- PK는 auto-increment `id`만
- 행 식별은 `(symbol, input_fingerprint, shadow_timestamp)` 조합으로 **논리적** 식별 (물리 제약 아님)

### 5.3 재실행 안전성

| 시나리오 | 결과 | 영향 |
|----------|------|:----:|
| 같은 symbol로 2번 호출 | 2행 INSERT | **0** (집계 시 dedup) |
| 다른 symbol로 1번씩 | 각 1행 INSERT | **0** |
| 10,000건 batch | 10,000행 INSERT | **0** (retention으로 관리) |

---

## 6. Failure Matrix

| 실패 유형 | 발생 조건 | 운영 영향 | 처리 방식 | RI-2A-1 영향 |
|-----------|-----------|:---------:|-----------|:------------:|
| INSERT 실패 (DB 연결) | DB 연결 끊김 | **0** | `logger.exception()` + return None | **0** |
| INSERT 실패 (디스크 풀) | 저장 공간 부족 | **0** | 동일 | **0** |
| INSERT 실패 (타입 에러) | 필드 변환 실패 | **0** | 동일 | **0** |
| flush 실패 | transaction 충돌 | **0** | 동일 | **0** |
| shadow_result가 None | 호출자 실수 | **0** | 사전 검증 → return None | **0** |
| readthrough_result가 None | 호출자 실수 | **0** | 사전 검증 → return None | **0** |
| 스키마 drift | 마이그레이션 누락 | **0** | 테이블 독립 → 기존 테이블 영향 없음 | **0** |

**불변 원칙:** `record_shadow_observation()`은 어떤 경우에도:
- 예외를 전파하지 않음
- pipeline/readthrough 실행을 차단하지 않음
- 기존 테이블에 접촉하지 않음

---

## 7. Rollback Plan

| 시나리오 | 절차 | 비용 | 기준선 영향 |
|----------|------|:----:|:----------:|
| RI-2A-2a 전체 철회 | 1. 서비스/모델/테스트 파일 삭제 2. `alembic downgrade` (DROP TABLE) 3. `__init__.py` import 제거 | **TRIVIAL** | **0** |
| 관측 데이터만 삭제 | `TRUNCATE shadow_observation_log` | **TRIVIAL** | **0** |
| 스키마 수정 필요 | 신규 마이그레이션 (기존 테이블 영향 0) | **TRIVIAL** | **0** |

### RI-2A-1 복귀 보장

RI-2A-2a에 문제가 생겨도:
- `pipeline_shadow_runner.py` → 수정 0줄 → **영향 0**
- `shadow_readthrough.py` → 수정 0줄 → **영향 0**
- 기존 5330 tests → 신규 파일만 추가 → **영향 0**
- `shadow_observation_log`는 기존 테이블과 FK 0 → **DROP 가능**

---

## 8. Manual Trigger Flow

### 8.1 호출 흐름

```
호출자 (스크립트 / 테스트 / 향후 beat task)
    │
    │  ShadowRunResult + ReadthroughComparisonResult
    │  (RI-2A-1 경유로 이미 생성)
    v
record_shadow_observation(db, shadow_result, readthrough_result, asset_class, asset_sector)
    │
    ├─ 입력 검증 (shadow_result/readthrough_result None 체크)
    ├─ 필드 변환 (enum→str, dataclass→JSON)
    ├─ ShadowObservationLog 생성
    ├─ db.add(row) + db.flush()
    ├─ 성공 → return row
    └─ 실패 → logger.exception() + return None
```

### 8.2 수동 실행 스크립트 (참고용, 구현 범위에 포함하지 않음)

수동 검증 시 아래와 같은 흐름으로 호출합니다:

```python
# 개념적 흐름 (실제 구현은 별도)
shadow = run_shadow_pipeline(market, backtest, asset_class, sector)
readthrough = await run_readthrough_comparison(db, shadow)
observation = await record_shadow_observation(db, shadow, readthrough, asset_class, sector)
```

### 8.3 Manual trigger 경계

| 허용 | 금지 |
|------|------|
| pytest 내 호출 | beat 자동 실행 |
| 스크립트 수동 실행 | Celery task 등록 |
| 단건/배치 호출 | 주기적 자동 반복 |

---

## 9. Retention / Purge Stance

### 9.1 RI-2A-2a의 purge 정책

| 항목 | 결정 |
|------|------|
| purge 구현 | **RI-2A-2a에서 미구현** |
| purge 시점 | RI-2A-2b 또는 후속 단계에서 필요 시 추가 |
| 보존 기간 (문서상) | **90일 권장** (구현은 후속) |

### 9.2 미구현 이유

| # | 이유 |
|---|------|
| 1 | 수동 트리거에서는 대량 축적 가능성이 낮음 |
| 2 | purge는 DELETE — append-only 원칙과 별도 심사 대상 |
| 3 | 필요 시 수동 `TRUNCATE` 또는 `DELETE WHERE created_at < ?`로 대응 가능 |
| 4 | 자동 purge는 beat (RI-2A-2b) 범위와 연결 — 지금 열지 않음 |

### 9.3 축적량 예상

| 시나리오 | 일일 행 수 | 90일 총량 |
|----------|:----------:|:---------:|
| 수동 단건 (테스트) | ~10 | ~900 |
| 수동 배치 (20 symbols) | ~20 | ~1,800 |
| beat 5분 (RI-2A-2b, 참고) | ~5,760 | ~518,400 |

수동 트리거 범위에서는 **retention 압박 없음**.

---

## 10. Test Plan

### 10.1 예상 신규 테스트

| 테스트 클래스 | 수 | 검증 대상 |
|-------------|:-:|-----------|
| **TestShadowObservationModel** | 4 | 모델 필드, 테이블명, import, nullable 검증 |
| **TestRecordObservation** | 5 | INSERT 정상, 필드 매핑, timestamp UTC, enum→str, JSON 직렬화 |
| **TestAppendOnlyGuarantee** | 4 | db.add만 허용, merge/delete/execute(UPDATE) 0회, 서비스에 update/delete 메서드 없음 |
| **TestInsertFailureIsolation** | 3 | INSERT 실패 시 예외 미전파, return None, pipeline/readthrough 무영향 |
| **TestInputValidation** | 3 | shadow_result=None → None, readthrough_result=None → None, 정상 입력 → row |
| **TestDuplicateAllowed** | 2 | 동일 입력 2회 → 2행, UNIQUE 제약 없음 |
| **TestReasonComparisonSerialization** | 3 | ReasonComparisonDetail → JSON → 역직렬화 정합, None 처리, frozenset 직렬화 |
| **총 예상** | **24** | |

### 10.2 기존 기준선 보호

| 보호 항목 | 방법 |
|-----------|------|
| 기존 5330 tests | 전체 회귀 PASS 필수 |
| pipeline_shadow_runner.py | **수정 0줄** (RI-2A-1 SEALED) |
| shadow_readthrough.py | **수정 0줄** (RI-2A-1 SEALED) |
| test_pipeline_shadow_runner.py | **수정 0줄** |
| test_shadow_readthrough.py | **수정 0줄** |
| FROZEN 함수 | 수정 0줄 |
| RED 파일 | 접촉 0건 |
| Pure Zone 10 files | purity guard 117 tests 유지 |

---

## 11. 파일 목록

### 신규 (4개)

| 파일 | 유형 |
|------|------|
| `app/models/shadow_observation.py` | 모델 |
| `app/services/shadow_observation_service.py` | 서비스 |
| `alembic/versions/0XX_shadow_observation_log.py` | 마이그레이션 |
| `tests/test_shadow_observation.py` | 테스트 |

### 수정 (1개)

| 파일 | 변경 |
|------|------|
| `app/models/__init__.py` | ShadowObservationLog import 추가 |

### 무수정 (봉인 유지)

| 파일 | 이유 |
|------|------|
| `pipeline_shadow_runner.py` | RI-2A-1 SEALED |
| `shadow_readthrough.py` | RI-2A-1 SEALED |
| `test_pipeline_shadow_runner.py` | 봉인 |
| `test_shadow_readthrough.py` | 봉인 |
| `exchanges/*` | RED |
| `workers/tasks/*` | RED (task 등록 없음) |

---

## 12. 완료 기준 (A 판정용)

| # | 기준 |
|---|------|
| 1 | Business table write 0 (screening_results, qualification_results, symbols 접촉 0) |
| 2 | shadow_observation_log INSERT only (append-only) |
| 3 | UPDATE/DELETE 호출 0 (모델+서비스+테스트 검증) |
| 4 | INSERT 실패 시 예외 미전파 (pipeline/readthrough 무영향) |
| 5 | RI-2A-1 코드 수정 0줄 |
| 6 | FROZEN 수정 0줄 |
| 7 | RED 접촉 0건 |
| 8 | beat / Celery task 등록 없음 |
| 9 | 신규 테스트 PASS |
| 10 | 전체 회귀 PASS |
| 11 | 신규 경고/예외 0 |

---

## A 판정 요청

| 판정 대상 | 선택지 |
|----------|--------|
| RI-2A-2a 설계/계약 | ACCEPT / 수정 요청 / 거부 |
| RI-2A-2a 구현 GO | 설계 승인 후 별도 GO 필요 |

---

```
CR-048 RI-2A-2a Design/Contract Package v1.0
Baseline: v2.1 (5330/5330 PASS, RI-2A-1 SEALED)
Scope: shadow_observation_log append-only INSERT, manual trigger
New table: shadow_observation_log (1, FK-free, independent)
DML: INSERT only (UPDATE/DELETE prohibited)
Business table write: ZERO
RI-2A-1 code modification: ZERO lines
FROZEN modification: ZERO lines
RED access: ZERO
Beat/Celery task: NONE
Duplicate policy: allowed (append-only, dedup at query time)
Retention: 90d recommended (purge deferred to RI-2A-2b)
Insert failure: swallowed, never propagates
Rollback cost: TRIVIAL
Estimated new tests: ~24
Estimated new files: 4 (model + service + migration + test)
Modified files: 1 (models/__init__.py import)
```
