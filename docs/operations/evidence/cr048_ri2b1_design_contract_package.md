# CR-048 RI-2B-1 설계/계약 패키지

**Stage**: RI-2B-1 (Receipt-only Shadow Write)
**Status**: DESIGN CONTRACT 제출
**Date**: 2026-04-04
**Authority**: A
**선행 조건**: RI-2B Scope Review ACCEPT (v3)
**Baseline**: v2.2 (5354/5354 PASS)

---

## 1. 설계 목적

> 실제 운영 상태를 변경하지 않고, **"만약 write 했다면 무엇이 바뀌었을지"를 receipt로 기록**하는 shadow evidence 계층.

RI-2B-1은 write-path의 **문법·계약·idempotency·금지선**을 dry-run 모드에서 먼저 검증하는 단계이며, business table 상태 변경은 0.

---

## 2. 스키마 계약

### shadow_write_receipt 테이블 (18필드)

| 필드 | 타입 | nullable | 설명 |
|------|------|:--------:|------|
| id | Integer (PK, auto) | N | |
| receipt_id | String(64) | N | Row identity (UUID) |
| dedupe_key | String(128) | N | Semantic idempotency key (SHA-256 hex) |
| symbol | String(32) | N | 대상 종목 |
| target_table | String(48) | N | 의도 대상 테이블명 |
| target_field | String(48) | N | 의도 대상 필드명 |
| current_value | String(128) | Y | 현재 값 (변경 전) |
| intended_value | String(128) | N | 의도 값 (변경 후) |
| would_change_summary | String(256) | N | 사람 가독 요약 |
| transition_reason | String(128) | N | 사유 코드 |
| block_reason_code | String(64) | Y | BLOCKED 시 구조화된 사유 코드 |
| shadow_observation_id | Integer | Y | 연결 shadow_observation_log.id (참조값, FK 아님) |
| input_fingerprint | String(64) | N | 재현성 키 |
| dry_run | Boolean | N | **항상 True** |
| executed | Boolean | N | **항상 False** |
| business_write_count | Integer | N | **항상 0** |
| verdict | String(32) | N | WOULD_WRITE / WOULD_SKIP / BLOCKED |
| created_at | DateTime(tz) | N (server_default) | |

**FK: 0. UNIQUE: 2 (receipt_id, dedupe_key). CASCADE: 0.**

### 인덱스 (4개)

| 인덱스 | 컬럼 | 용도 |
|--------|------|------|
| uq_receipt_id | (receipt_id) | Row identity UNIQUE |
| uq_dedupe_key | (dedupe_key) | Semantic idempotency UNIQUE |
| ix_swr_symbol | (symbol) | 종목별 조회 |
| ix_swr_created_at | (created_at) | 시간순 조회 |

---

## 3. Dedupe Key 계약 (고정)

### 입력요소 (7개, 순서 고정)

| # | 필드 | 예시 | None 처리 |
|---|------|------|-----------|
| 1 | symbol | `"SOL/USDT"` | 불허 (required) |
| 2 | target_table | `"symbols"` | 불허 |
| 3 | target_field | `"qualification_status"` | 불허 |
| 4 | current_value | `"unchecked"` | `"NULL"` |
| 5 | intended_value | `"pass"` | 불허 |
| 6 | input_fingerprint | `"a3f8..."` | 불허 |
| 7 | dry_run | `"true"` | 불허 (항상 `"true"`) |

**구분자**: `|` (pipe). **인코딩**: UTF-8. **해시**: SHA-256 hex lowercase.

```python
def compute_dedupe_key(symbol, target_table, target_field, current_value, intended_value, input_fingerprint, dry_run=True):
    raw = "|".join([
        symbol, target_table, target_field,
        current_value if current_value is not None else "NULL",
        intended_value, input_fingerprint,
        str(dry_run).lower(),
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
```

> 입력요소 추가/제거/순서 변경은 스키마 버전 변경으로 간주하며, 별도 A 심사 필수.

---

## 4. Verdict 결정표 (7단계, 순서 고정)

| Step | 조건 | verdict | block_reason_code |
|:----:|------|---------|-------------------|
| 1 | target_table/field가 허용 목록 밖 | `BLOCKED` | `OUT_OF_SCOPE` |
| 2 | target_table/field가 금지 목록 | `BLOCKED` | `FORBIDDEN_TARGET` |
| 3 | shadow_result 또는 readthrough_result가 None | `BLOCKED` | `INPUT_INVALID` |
| 4 | current_value == intended_value | `WOULD_SKIP` | — |
| 5 | current_value가 전이 사전조건 미충족 | `BLOCKED` | `PRECONDITION_FAILED` |
| 6 | shadow qualification verdict가 전이 조건 미충족 | `WOULD_SKIP` | — |
| 7 | 모든 검사 통과 + dry_run=True | `WOULD_WRITE` | — |

**금지선 우선 차단 원칙**: Step 1~3은 금지선/입력검증으로 반드시 선행 차단.
Step 4~6은 비즈니스 조건 평가. Step 7은 모든 검사 통과 시에만 도달.

> Step 순서 변경은 설계 변경으로 간주. 별도 A 심사 필수.

### Verdict → intended_value 매핑 (qualification_status 전용)

| shadow qualification 결과 | intended_value | verdict |
|--------------------------|----------------|---------|
| PipelineVerdict.QUALIFIED | `"pass"` | WOULD_WRITE (조건 충족 시) |
| PipelineVerdict.QUALIFY_FAILED | `"fail"` | WOULD_WRITE (조건 충족 시) |
| PipelineVerdict.SCREEN_FAILED | — | WOULD_SKIP (qualification 미도달) |
| PipelineVerdict.DATA_REJECTED | — | WOULD_SKIP (데이터 불충분) |

---

## 5. 허용/금지 의도 대상

### 허용 (whitelist, 고정)

| target_table | target_field | 허용 전이 |
|-------------|-------------|-----------|
| `symbols` | `qualification_status` | `unchecked → pass`, `unchecked → fail` |

**1개 테이블 × 1개 필드 × 2개 전이만.**

### 금지 (forbidden, 고정)

| target_table | target_field | 금지 사유 |
|-------------|-------------|-----------|
| `symbols` | `status` | 3상태 전이는 screening pipeline 전용 |
| `symbols` | `promotion_eligibility_status` | 승격 경로 변경은 RI-2B-2+ |
| `symbols` | `paper_evaluation_status` | paper 경로는 CR-046 frozen |
| `strategies` | `status` | 전략 승격은 Phase 4+ |
| `screening_results` | * | screening pipeline 전용 |
| `qualification_results` | * | qualification pipeline 전용 |
| `promotion_events` | * | promotion gate 전용 |

---

## 6. 서비스 계약

### Public API (1개 함수만)

```python
async def evaluate_shadow_write(
    db: AsyncSession,
    receipt_id: str,                    # UUID (호출자 생성)
    shadow_result: ShadowRunResult,     # RI-1 SEALED 출력
    readthrough_result: ReadthroughComparisonResult,  # RI-2A-1 SEALED 출력
    symbol: str,
    current_qualification_status: str,  # 현재 값 (호출자 조회)
) -> ShadowWriteReceipt | None:
```

### 계약

| 항목 | 규칙 |
|------|------|
| 반환 | ShadowWriteReceipt on success, None on failure |
| INSERT 대상 | shadow_write_receipt **1개 테이블만** |
| Business table write | **0** (symbols, strategies 등 무변경) |
| DB read | **0** (current_value는 호출자가 전달) |
| dry_run | **항상 True** (함수 내부에서 강제) |
| executed | **항상 False** |
| business_write_count | **항상 0** |
| Failure 처리 | try/except → logger.exception → return None |
| UPDATE/DELETE | **0** (메서드 없음) |

### 금지 메서드

서비스에 아래 이름을 포함한 public 메서드가 존재해서는 안 됨:
- `update`, `delete`, `remove`, `execute`, `apply`, `commit_write`

---

## 7. Idempotency 계약 (2계층)

### Layer 1 — Row Identity

| 항목 | 규칙 |
|------|------|
| receipt_id | 호출자가 생성하는 UUID |
| UNIQUE | receipt_id에 UNIQUE 인덱스 |
| 중복 시 | IntegrityError → 기존 receipt 조회 반환 |

### Layer 2 — Semantic Identity

| 항목 | 규칙 |
|------|------|
| dedupe_key | 7개 입력요소의 SHA-256 해시 |
| UNIQUE | dedupe_key에 UNIQUE 인덱스 |
| 중복 시 | IntegrityError → 기존 receipt 조회 반환 |

### 중복 처리 흐름

```
evaluate_shadow_write() 호출
  → dedupe_key 계산
  → INSERT 시도
  → IntegrityError 발생 (receipt_id 또는 dedupe_key 중복)
    → SELECT WHERE dedupe_key = ? LIMIT 1
    → 기존 receipt 반환
  → 정상 INSERT 시
    → 새 receipt 반환
```

---

## 8. Failure Isolation (RI-2A-2a 패턴 계승)

| 실패 유형 | 운영 영향 | 처리 |
|-----------|:---------:|------|
| db.flush() 실패 | 0 | return None, 예외 미전파 |
| db.add() 실패 | 0 | return None, 예외 미전파 |
| UNIQUE 위반 (중복) | 0 | 기존 receipt 반환 |
| shadow_result = None | 0 | BLOCKED (INPUT_INVALID) |
| readthrough_result = None | 0 | BLOCKED (INPUT_INVALID) |
| RuntimeError | 0 | return None, 예외 미전파 |

---

## 9. 파일 목록 (확정)

| 파일 | 작업 | 등급 |
|------|------|:----:|
| `app/models/shadow_write_receipt.py` | **신규** — ShadowWriteReceipt ORM | L3 |
| `app/services/shadow_write_service.py` | **신규** — evaluate_shadow_write() dry-run only | L3 |
| `alembic/versions/022_shadow_write_receipt.py` | **신규** — CREATE TABLE + 4 indexes | L3 |
| `tests/test_shadow_write_receipt.py` | **신규** — model + service + idempotency + forbidden + verdict tests | L1 |
| `app/models/__init__.py` | **수정** — ShadowWriteReceipt import 추가 | L3 |

**총 5개 파일** (신규 4, 수정 1).

### FROZEN 파일 (무접촉 필수)

| 파일 | 봉인 단계 |
|------|----------|
| `app/services/pipeline_shadow_runner.py` | RI-1 SEALED |
| `app/services/shadow_readthrough.py` | RI-2A-1 SEALED |
| `app/services/shadow_observation_service.py` | RI-2A-2a SEALED |
| `app/models/shadow_observation.py` | RI-2A-2a SEALED |

### RED 파일 (무접촉 필수)

| 파일 | 사유 |
|------|------|
| `exchanges/*` | 거래소 어댑터 |
| `workers/tasks/order_tasks.py` | 주문 경로 |
| `workers/tasks/market_tasks.py` | 시장 데이터 경로 |
| `app/services/multi_symbol_runner.py` | 실행 경로 |
| `app/services/asset_service.py` | RI-2B-1에서 변경 금지 |
| `app/models/asset.py` | RI-2B-1에서 변경 금지 |
| `workers/tasks/*` | task 등록 금지 |

---

## 10. 방화벽 선언

> **RI-2B-1은 shadow evidence 단계이며, symbols 포함 모든 business table 상태 변경은 금지된다.**
>
> **RI-2B-1 승인 범위는 shadow evidence append-only에 한정되며, 이를 근거로 RI-2B-2 real bounded write에 대한 승인 또는 착수 권한이 발생하지 않는다.**
>
> **본 문서의 승인 범위는 RI-2B-1 shadow evidence 설계 심사에 한정되며, 실행 권한·운영 write 권한·후속 단계 권한을 생성하지 않는다.**

---

## 11. 완료 기준 (13개)

| # | 기준 | 검증 방법 |
|---|------|-----------|
| 1 | Schema 구현 (18필드, FK 0, UNIQUE 2) | 모델 테스트 |
| 2 | Append-only (INSERT만, UPDATE/DELETE 0) | 메서드 부재 검증 |
| 3 | Verdict 7단계 결정표 순서 준수 | 단계별 verdict 테스트 |
| 4 | 금지선 우선 차단 (Step 1~3 선행) | OUT_OF_SCOPE/FORBIDDEN_TARGET/INPUT_INVALID 테스트 |
| 5 | dry_run=True / executed=False / business_write_count=0 고정 | 강제값 테스트 |
| 6 | Semantic dedupe (dedupe_key UNIQUE) | 중복 요청 → 1 row 테스트 |
| 7 | Idempotency (receipt_id UNIQUE + dedupe_key UNIQUE) | 2계층 중복 테스트 |
| 8 | Business table write 0 | symbols/strategies 무변경 테스트 |
| 9 | Forbidden target 차단 | 7개 금지 대상 거부 테스트 |
| 10 | Failure isolation (flush/add 실패 → None) | 예외 미전파 테스트 |
| 11 | FROZEN 수정 0줄 | 파일 접촉 검증 |
| 12 | RED 접촉 0건 | 파일 접촉 검증 |
| 13 | 전체 회귀 PASS | baseline 유지 |

---

## 12. 구현 완료 보고 형식

보고에 포함할 섹션:

1. 수정/생성 파일 목록
2. DDL / 스키마 요약
3. Append-only 검증표
4. Verdict 결정표 검증표
5. Idempotency 2계층 검증표
6. Failure isolation 검증표
7. FROZEN / RED 무접촉 증빙
8. Business table write 0 증빙
9. 전체 회귀 결과
10. 신규 경고/예외 여부
11. 완료 기준 13/13 대조표

---

## A 판정 요청

RI-2B-1 설계/계약 패키지를 제출합니다.

- **ACCEPT + GO** → RI-2B-1 구현 제한 승인
- **CONDITIONAL** → 지적 사항 반영 후 재제출
- **REJECT** → 설계 재검토
