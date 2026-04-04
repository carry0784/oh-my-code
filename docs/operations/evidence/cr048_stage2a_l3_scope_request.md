# CR-048 Stage 2A L3 범위 요청서

**문서 ID:** GOV-L3-STAGE2A-001
**작성일:** 2026-04-04
**Authority:** A (Decision Authority)
**CR:** CR-048
**변경 등급:** L3 (서비스 로직 — control-plane / static metadata)
**전제:** Stage 1 L3 SEALED (A 승인 2026-04-04, 4709/4709 PASS)
**참조:** `cr048_staged_l3_expansion_proposal.md` Stage 2, A 판정 2A/2B 분리 지시

> **본 문서는 Stage 2A L3 범위 요청서입니다. A 승인 전까지 구현 착수는 금지됩니다.**

---

## 1. Stage 2 분리 배경

A 판정: 기존 Stage 2 제출본(GOV-L3-STAGE2-001)은 **조건부 반려 / 축소 재상신** 결정.

반려 이유 3축:

| # | 이유 | 위험 |
|:--:|------|------|
| 1 | `asset_service.py`에 `symbol_screener`, `backtest_qualification` import 존재 | Stage 3/Phase 4 연쇄 로드 |
| 2 | `Symbol.status` 변경이 Data Plane에 간접 영향 | runtime 종목 풀 변경 가능 |
| 3 | TTL 자동 만료가 런타임 종목 풀에 직접 영향 | CORE→WATCH 자동 강등 |

분리 기준: **"이 변경이 `symbols` 테이블의 `status` 컬럼을 runtime에서 바꿀 수 있는 코드 경로에 도달하는가?"**

- **도달 불가** → Stage 2A (본 문서)
- **도달 가능** → Stage 2B (별도 요청서)

---

## 2. Stage 2A 성격 정의

| 항목 | Stage 2A |
|------|----------|
| 성격 | **정적 모델/스키마/메타데이터 정렬 + 순수 검증 함수** |
| runtime 연결 | **없음** |
| Symbol.status | **enum/상태 정의 가능, 실제 data plane read path 영향 없음** |
| TTL | **계산식 정의 가능, 자동 만료 실행 금지** |
| DB write | **DDL(migration)만, DML(status 변경 실행)은 금지** |
| `asset_service.py` | **RED — 미접촉** |
| `symbol_screener` | **RED — 미접촉** |
| `backtest_qualification` | **RED — 미접촉** |

### 핵심 원칙

Stage 2A의 모든 코드는 **`asset_service.py`를 import하지 않는다.**
`asset_service.py`는 `symbol_screener`와 `backtest_qualification`을 import하므로,
이 파일을 import하는 것 자체가 Stage 3/Phase 4 모듈의 연쇄 로드를 유발한다.
따라서 Stage 2A는 **model/enum/schema/constitution 직접 import만 허용**한다.

---

## 3. Stage 1 vs Stage 2A 차이점

| 항목 | Stage 1 | Stage 2A |
|------|---------|----------|
| **대상** | Gateway validation + Registry CRUD | **Asset model 정렬 + 순수 검증 함수** |
| **서비스 파일** | injection_gateway.py, registry_service.py | **asset_validators.py (신규)** |
| **기존 서비스 수정** | injection_gateway.py 확장 | **없음** |
| **모델/DB 변경** | 없음 | **가능** (migration 별도 명시) |
| **write 유형** | metadata create/retire | **DDL만** (DML status 변경 없음) |
| **Data Plane 영향** | 없음 | **없음** (순수 함수/스키마/상수만) |
| **기존 asset_service.py** | 미접촉 | **미접촉 (RED)** |
| **API 엔드포인트** | 16개 (9 GET + 7 POST) | **없음** (또는 validation-only GET) |

### Stage 2A 신규 리스크 5개

| # | 리스크 | 완화 방안 |
|:--:|--------|-----------|
| 1 | **constitution.py 상수 추가 시 기존 Gateway 동작 변경** | 신규 상수만, 기존 FORBIDDEN_BROKERS/SECTORS 수정 금지 |
| 2 | **asset.py enum 추가 시 Alembic migration 필요** | nullable column + ADD ONLY, 기존 column 수정 금지 |
| 3 | **asset_schema.py validator 강화 시 기존 API 호환성 깨짐** | 기존 필드 validator는 수정 금지, 신규 필드만 validator 추가 |
| 4 | **asset_validators.py에서 constitution import 경유로 부작용** | constitution.py는 순수 상수 파일 — 부작용 없음 확인 |
| 5 | **migration down 실패 시 롤백 불가** | migration은 ADD COLUMN/ADD ENUM VALUE만, DROP 연산 없음 |

---

## 4. 파일 3분할 분류표

### GREEN (허용) — Stage 2A에서 변경 가능

| 파일 | 작업 | 등급 | 안전 근거 |
|------|------|:----:|-----------|
| `app/services/asset_validators.py` | **신규** — 순수 검증 함수 (broker policy, status transition, TTL 계산식) | L3 | I/O 없음, DB 미접촉, asset_service 미import |
| `app/models/asset.py` | enum 값 추가 / column 추가 (nullable) | L3 | 정적 스키마 정의, runtime 비연결 |
| `app/core/constitution.py` | 상수 추가 (BROKER_POLICY_RULES, TTL_DEFAULTS) | L0 | 순수 상수, 기존 값 수정 금지 |
| `app/schemas/asset_schema.py` | 신규 필드/validator 추가 | L2 | Pydantic 검증, DB 미접촉 |
| `alembic/versions/0XX_stage2a_*.py` | migration (ADD COLUMN/ADD ENUM VALUE) | L3 | DDL만, 기존 column 수정 없음 |
| `tests/test_asset_validators.py` | **신규** — 순수 함수 테스트 | L1 | unit test only |
| `tests/test_asset_model_stage2a.py` | **신규** — model/enum/schema 확장 테스트 | L1 | model 직접 import만 |

### RED (금지) — Stage 2A에서 절대 변경 불가

| 파일/범위 | 사유 |
|-----------|------|
| **`app/services/asset_service.py`** | **A 지시: RED 고정** — symbol_screener/backtest_qualification import 존재 |
| **`app/services/symbol_screener.py`** | **A 지시: RED 고정** — Stage 3 |
| **`app/services/backtest_qualification.py`** | **A 지시: RED 고정** — Phase 4 |
| `app/services/runtime_strategy_loader.py` | Data Plane — Phase 5 |
| `app/services/runtime_loader_service.py` | Data Plane — Phase 5 |
| `app/services/feature_cache.py` | Data Plane — Phase 5 |
| `app/services/paper_shadow_service.py` | Phase 4 |
| `app/services/injection_gateway.py` | Stage 1 SEALED |
| `app/services/registry_service.py` | Stage 1 SEALED |
| `app/api/routes/registry.py` | Stage 1 SEALED |
| `workers/tasks/*` | Celery task — Stage 2B/3 이상 |
| `exchanges/*` | 거래소 어댑터 |
| `app/services/regime_detector.py` | 수정 금지 |

### AMBER (회색지대) — 사전 예외 승인 시에만

| 파일 | 잠재적 필요성 | 예외 조건 |
|------|-------------|-----------|
| `app/models/qualification.py` | enum 값 추가 필요 시 | ADD 만 허용, 기존 값 변경 금지 |
| `tests/test_asset_registry.py` (기존) | 기존 테스트 호환 수정 필요 시 | assertion 정렬만, 로직 변경 금지 |
| `app/api/routes/` (asset endpoint) | validation-only GET 추가 시 | GET + read-only 검증만, write 금지 |

---

## 5. Capability Wall

### 허용 기능 (Stage 2A)

| Capability | 범위 | Data Plane 도달 | 비고 |
|------------|------|:---------------:|------|
| Broker-Policy 교차 검증 **함수** | `validate_broker_policy(exchanges, asset_class) -> violations` | **NO** | 순수 함수, DB 미접촉 |
| Status Transition 매트릭스 **검증 함수** | `validate_status_transition(current, target, override, sector) -> (ok, reason)` | **NO** | 순수 함수, 실제 전이 실행 없음 |
| TTL 계산식 **정의 함수** | `compute_candidate_ttl(score, asset_class) -> timedelta` | **NO** | 값 반환만, DB write 없음 |
| Symbol Canonicalization 강화 | `canonicalize_symbol()` 확장 | **NO** | 기존 순수 함수 |
| Constitution 상수 추가 | BROKER_POLICY_RULES, TTL_DEFAULTS 등 | **NO** | import만 발생 |
| Model enum/column 추가 | AssetSector, SymbolStatusReason 값 추가 | **NO** | DDL + nullable |
| Schema validator 추가 | Pydantic 입력 검증 강화 | **NO** | API 입력 단계만 |

### 금지 기능 (Stage 2A)

| Capability | 이유 | 승인 단계 |
|------------|------|:---------:|
| Symbol.status **실제 변경** (DB UPDATE) | runtime pool 영향 | **2B** |
| TTL 자동 만료 **실행** (CORE→WATCH 강등) | runtime pool 축소 | **2B** |
| Symbol-Broker 교차 검증 **서비스 통합** (asset_service 호출) | asset_service.py RED | **2B** |
| 상태 전이 감사 이벤트 **DB 기록** | asset_service.py 경유 | **2B** |
| Regime 전환 시 TTL 일괄 만료 | runtime pool 전면 변경 | **2B** |
| SymbolScreener 파이프라인 | Stage 3 | **Stage 3** |
| BacktestQualifier 실행 | Phase 4 | **Phase 4** |
| Celery task 생성 | L4 | **Stage 3+** |
| beat schedule 변경 | L4 | **L4** |
| exchange_mode 변경 | L4 | **L4** |

---

## 6. Data Plane Impact Matrix

| 변경 항목 | 직접 영향 파일 | 간접 영향 파일 | 현재 runtime 도달 가능 | Fail-Closed | Rollback 가능 | 승인 단계 |
|-----------|---------------|---------------|:--------------------:|:-----------:|:-------------:|:---------:|
| **enum 값 추가** (AssetSector, SymbolStatusReason) | asset.py | 없음 (기존 코드는 새 값 무시) | **NO** | YES (unknown enum 무시) | YES (migration down) | **2A** |
| **Symbol column 추가** (nullable) | asset.py, migration | 없음 (nullable이면 기존 row 무영향) | **NO** | YES (nullable default) | YES (migration down) | **2A** |
| **constitution 상수 추가** | constitution.py | 없음 (import만) | **NO** | N/A | YES (code revert) | **2A** |
| **asset_validators.py 순수 함수** | 신규 파일 | 없음 (어디서도 호출하지 않으면) | **NO** | N/A | YES (파일 삭제) | **2A** |
| **Pydantic schema validator 추가** | asset_schema.py | API input 단계 | **NO** (status 변경 없음) | YES (reject-only) | YES (code revert) | **2A** |
| **asset_service.py 수정** | asset_service.py | runtime_loader, screener | **YES** | 구현 의존 | 조건부 | **2B** |
| **TTL 자동 만료 실행** | asset_service.py | runtime pool 축소 | **YES** | NO | NO (비가역) | **2B** |
| **Symbol.status DB UPDATE** | asset_service.py | runtime loader read path | **YES** | 구현 의존 | 조건부 | **2B** |
| **screen_and_update 변경** | asset_service.py | CORE/WATCH 판정 변경 | **YES** | 구현 의존 | 조건부 | **2B** |
| **qualify_and_record 변경** | asset_service.py | promotion gate 영향 | **YES** | 구현 의존 | 조건부 | **2B** |

---

## 7. asset_validators.py 설계 개요

### 원칙

- **순수 함수만** — `(input) -> (output)`, side-effect 없음
- **AsyncSession 금지** — DB 접근 없음
- **asset_service.py import 금지** — symbol_screener 연쇄 방지
- **constitution.py, asset.py (model enum) import만 허용**

### 함수 목록 (후보)

| 함수 | 입력 | 출력 | 용도 |
|------|------|------|------|
| `validate_broker_policy` | `exchanges: list[str], asset_class: str` | `list[str]` (위반 항목) | ALLOWED_BROKERS 대조 |
| `check_forbidden_brokers` | `exchanges: list[str]` | `list[str]` (금지 브로커) | FORBIDDEN_BROKERS 대조 |
| `validate_status_transition` | `current: str, target: str, manual_override: bool, sector: str` | `tuple[bool, str]` (가능여부, 거절사유) | 전이 매트릭스 검증 |
| `compute_candidate_ttl` | `score: float, asset_class: str` | `timedelta` | TTL 계산식 (DB write 없음) |
| `is_excluded_sector` | `sector: str` | `bool` | EXCLUDED_SECTORS 판정 |
| `validate_symbol_data` | `data: dict` | `list[str]` (오류 목록) | 등록 전 사전 검증 |

### 상태 전이 매트릭스 (정의만, 실행은 2B)

| From \ To | CORE | WATCH | EXCLUDED |
|-----------|:----:|:-----:|:--------:|
| **CORE** | — | TTL만료/Regime (2B) | manual/screening_fail (2B) |
| **WATCH** | screening_pass (2B) | — | manual/baseline (2B) |
| **EXCLUDED** | **금지** (excluded_sector) | manual_override 필수 (2B) | — |

Stage 2A에서는 이 매트릭스를 **코드로 정의하고 테스트**하되,
실제 DB `Symbol.status = new_status` 실행은 Stage 2B에서만 수행.

---

## 8. 중단 조건 / 봉인 조건

### 중단 조건

| 조건 | 행동 |
|------|------|
| 회귀 실패 발생 | 즉시 중단, 원인 분석 |
| RED 파일 변경 필요 발견 | 즉시 중단, 사전 예외 요청 |
| AMBER 파일 변경 필요 | 작업 일시 중지, 사전 보고 |
| `asset_service.py` import 필요 발견 | **즉시 중단** — Stage 2B 경계 |
| `from app.services.asset_service import` 발생 | **즉시 중단** — symbol_screener 연쇄 |
| migration이 기존 column 수정 필요 | 즉시 중단, 재설계 |
| A 중단 지시 | 즉시 중단 |

### 봉인 조건

| # | 조건 | 검증 방법 |
|:--:|------|-----------|
| 1 | asset_validators.py 전 함수 테스트 PASS | broker policy, transition matrix, TTL 계산 |
| 2 | constitution 상수 일관성 테스트 PASS | constitution ↔ model enum ↔ gateway 교차 검증 |
| 3 | migration up/down 성공 | Alembic upgrade + downgrade |
| 4 | schema validator 테스트 PASS | 기존 API 호환성 유지 확인 |
| 5 | asset_service.py **미변경** 확인 | `git diff` 기준 0 lines changed |
| 6 | symbol_screener / backtest_qualification **미접촉** 확인 | `git diff` 기준 0 lines |
| 7 | 기존 계약 테스트 유지 (57+30건) | regression |
| 8 | 전체 회귀 PASS (4709+a) | `pytest --tb=short -q` |
| 9 | **A 판정** | 제출 후 판정 |

---

## 9. 예외 승인 필요 지점

| 지점 | 예외 유형 | 처리 |
|------|-----------|------|
| constitution.py 기존 상수 **값** 변경 | 정책 변경 | **A 직접 판정** |
| qualification.py enum 추가 | AMBER | **사전 보고** |
| 기존 test_asset_registry.py assertion 수정 | AMBER | **사전 보고** |
| asset API endpoint GET 추가 | AMBER | **사전 보고** |

---

## A에게 제출하는 항목 (L3 확장 제안서 S4 기준)

| # | 항목 | 내용 |
|:--:|------|------|
| 1 | Stage 1 봉인 증빙 | SEALED (2026-04-04, `cr048_stage1_l3_completion_evidence.md`) |
| 2 | Stage 2A 파일 목록 + 변경 범위 | GREEN 7파일, AMBER 3파일(조건부), RED 16+파일(금지) |
| 3 | 금지 범위 갱신표 | 본 문서 S4 RED 표 + **asset_service.py RED 고정** |
| 4 | 예상 테스트 추가 수 | 25~40건 (broker-policy 8~12 + transition-matrix 9 + TTL 5~8 + model/schema 5~10) |
| 5 | 회귀 기준선 현재 수치 | **4709/4709 PASS** |
| 6 | Data Plane Impact Matrix | 본 문서 S6 — 모든 2A 항목 "runtime 도달 NO" |

---

**Stage 2A limited scope approval requested**

본 요청은 `asset_service.py`를 포함한 모든 runtime-adjacent 파일을 RED로 고정하며,
순수 함수/정적 정의/스키마/상수/테스트만 포함합니다.

---

```
CR-048 Stage 2A L3 Scope Request v1.0
Document ID: GOV-L3-STAGE2A-001
Date: 2026-04-04
Authority: A
Status: REQUEST (A 승인 전까지 구현 착수 불가)
Gate: LOCKED (유지 전제)
Prerequisite: Stage 1 SEALED
asset_service.py: RED (미접촉)
symbol_screener: RED (미접촉)
backtest_qualification: RED (미접촉)
Runtime 도달: 전 항목 NO
```
