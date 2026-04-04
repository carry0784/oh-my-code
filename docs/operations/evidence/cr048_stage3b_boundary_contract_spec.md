# CR-048 Stage 3B Boundary Contract Spec

**문서 ID:** GOV-L3-STAGE3B-CONTRACT-001
**작성일:** 2026-04-03
**Authority:** A (Decision Authority)
**CR:** CR-048
**전제:** Stage 3B Boundary Inventory ACCEPTED (GOV-L3-STAGE3B-BOUNDARY-001)
**목적:** Pure Zone / 오염선 / FROZEN 경계 / 허용·금지 접촉면 명문화

> 이 문서는 설계 계약만 포함한다. 구현 지침 없음.

---

## 1. Pure Zone 정의

Pure Zone은 외부 상태(DB, 네트워크, 파일, 캐시, 환경변수)에 대한 의존이 0인 코드 영역이다.

### 1-1. Pure Zone 파일 목록 (6개)

| # | 파일 | 역할 | 순수성 근거 |
|:-:|------|------|------------|
| 1 | `app/services/sector_rotator.py` | Regime→Sector 가중치 계산 | sync, stdlib only, I/O 0 |
| 2 | `app/services/data_provider.py` | DataProvider ABC/Protocol 정의 | ABC only, 구현 0 |
| 3 | `app/services/symbol_screener.py` | 5단계 스크리닝 계산 | sync, stateless, I/O 0 |
| 4 | `app/services/backtest_qualification.py` | 7단계 백테스트 검증 | sync, stateless, I/O 0 |
| 5 | `app/services/asset_validators.py` | 7 pure 검증 함수 | sync, stateless, I/O 0 |
| 6 | `app/core/constitution.py` | 상수/정책 정의 | 값 정의만, 로직 0 |

### 1-2. Pure Zone 불변 규칙

| 규칙 | 설명 |
|------|------|
| **PZ-01** | Pure Zone 파일은 `async def`를 포함할 수 없다 (ABC 선언 제외) |
| **PZ-02** | Pure Zone 파일은 DB session, engine, connection을 import할 수 없다 |
| **PZ-03** | Pure Zone 파일은 네트워크 라이브러리를 import할 수 없다 |
| **PZ-04** | Pure Zone 파일은 파일 I/O를 수행할 수 없다 |
| **PZ-05** | Pure Zone 파일은 환경변수를 읽을 수 없다 |
| **PZ-06** | Pure Zone 파일은 Celery task/beat를 등록할 수 없다 |
| **PZ-07** | Pure Zone 파일은 다른 Pure Zone 파일 또는 stdlib만 import할 수 있다 |
| **PZ-08** | `data_provider.py`의 ABC 메서드는 `async def` + `...` (body 없음)만 허용 — 예외적 async 선언 |

---

## 2. 오염선 정의

오염선(Contamination Boundary)은 Pure Zone과 Runtime Zone 사이의 경계이다.

### 2-1. 오염선 위치

```
Pure Zone                      Contamination Line              Runtime Zone
─────────────────────── ══════════════════════════ ──────────────────────────
sector_rotator.py               │                    asset_service.py
data_provider.py                │                      L333: 첫 DB INSERT
symbol_screener.py              │                      L348: screen_and_update()
backtest_qualification.py       │                      L414: qualify_and_record()
asset_validators.py             │                    workers/tasks/*
constitution.py                 │                    exchanges/*
```

### 2-2. 오염선 통과 규칙

| 규칙 | 설명 |
|------|------|
| **CL-01** | Pure Zone → Runtime Zone 방향 호출은 **금지** (Pure가 Runtime을 import하면 안 됨) |
| **CL-02** | Runtime Zone → Pure Zone 방향 호출은 **허용** (Runtime이 Pure 함수를 호출할 수 있음) |
| **CL-03** | 오염선 통과 시 데이터는 **frozen dataclass 또는 primitive type**으로만 전달 |
| **CL-04** | DB session, connection 객체는 오염선을 통과할 수 없다 |
| **CL-05** | Pure Zone 함수의 반환값을 Runtime Zone에서 DB에 저장하는 것은 **허용** (현재 screen_and_update 패턴) |

---

## 3. FROZEN 경계

FROZEN 함수는 어떤 Stage에서도 수정이 금지된 함수이다.

### 3-1. FROZEN 함수 목록

| 함수 | 파일 | 라인 | 상태 | FROZEN 이후 |
|------|------|------|:----:|:-----------:|
| `screen_and_update()` | asset_service.py | L348-410 | **FROZEN** | Stage 2B부터 |
| `qualify_and_record()` | asset_service.py | L414-483 | **FROZEN** | Stage 2B부터 |

### 3-2. FROZEN 불변 규칙

| 규칙 | 설명 |
|------|------|
| **FR-01** | FROZEN 함수의 시그니처(매개변수, 반환 타입)를 변경할 수 없다 |
| **FR-02** | FROZEN 함수의 내부 로직을 변경할 수 없다 |
| **FR-03** | FROZEN 함수가 호출하는 함수의 시그니처를 변경할 수 없다 |
| **FR-04** | FROZEN 함수에 새 import를 추가할 수 없다 |
| **FR-05** | FROZEN 함수의 호출 순서(DB read → pure call → DB write)를 변경할 수 없다 |

---

## 4. Allowed Touch Matrix (T1-T7)

Stage 3B-1에서 접촉이 허용되는 항목. 전부 **추가만 허용, 수정/삭제 금지**.

| ID | 대상 파일 | 허용 범위 | 조건 | 비파괴 증명 |
|:--:|-----------|-----------|------|------------|
| **T1** | `sector_rotator.py` | `RotationReasonCode` enum 추가, `SectorWeight.reason` 필드 추가 | frozen dataclass 확장, 기존 API 하위 호환 | reason=None 기본값 → 기존 호출 무변경 |
| **T2** | `data_provider.py` | `ProviderCapability` frozen dataclass 추가 | 신규 타입, 기존 ABC/dataclass 비수정 | 신규 정의만, 기존 참조 없음 |
| **T3** | `data_provider.py` | `DataQualityPolicy` pure 함수 추가 | stale/partial 판정 함수, 기존 코드 비수정 | 기존 import path 무영향 |
| **T4** | `tests/test_sector_rotator.py` | Purity Guard 테스트 추가 | 기존 48 tests 비수정, 신규 테스트 class 추가만 | 기존 PASS 유지 |
| **T5** | `tests/test_data_provider.py` | Purity Guard 테스트 추가 | 기존 35 tests 비수정, 신규 테스트 class 추가만 | 기존 PASS 유지 |
| **T6** | 신규 `tests/test_purity_guard.py` | 통합 Purity Guard 테스트 | 신규 파일, Pure Zone 6개 파일 대상 | 읽기 전용 검사 |
| **T7** | 신규 `tests/test_failure_modes.py` | Failure Mode 계약 테스트 | 신규 파일, DataQuality 정책 검증 | Pure 함수 호출만 |

### T1 하위 호환 보장 설계

```
# 기존 (Stage 3A)
@dataclass(frozen=True)
class SectorWeight:
    sector: AssetSector
    weight: float
    regime: str

# Stage 3B-1 확장
@dataclass(frozen=True)
class SectorWeight:
    sector: AssetSector
    weight: float
    regime: str
    reason: RotationReasonCode | None = None  # ← 기본값 None, 기존 호출 무변경
```

기존 `SectorWeight(sector=..., weight=..., regime=...)` 호출은 `reason=None`으로 동작 → **하위 호환 보장**.

---

## 5. Prohibited Touch Matrix (X1-X15)

| ID | 대상 | 등급 | 금지 사유 | 위반 시 |
|:--:|------|:----:|-----------|---------|
| **X1** | `screen_and_update()` | 🔴 | FROZEN | 즉시 중단 + 롤백 |
| **X2** | `qualify_and_record()` | 🔴 | FROZEN | 즉시 중단 + 롤백 |
| **X3** | `asset_service.py` 전체 | 🟠 | AMBER, Stage 2B 봉인 | A 별도 승인 필요 |
| **X4** | `symbol_screener.py` 로직 수정 | 🟢→🟠 | Screening core, 계산 변경 금지 | 수정 금지, 읽기만 |
| **X5** | `backtest_qualification.py` 로직 수정 | 🟢→🟠 | Qualification core, 계산 변경 금지 | 수정 금지, 읽기만 |
| **X6** | `workers/celery_app.py` | 🔴 | Beat/task 등록 금지 | 접촉 금지 |
| **X7** | `workers/tasks/*` 생성/수정 | 🔴 | Task 생성/수정 금지 | 접촉 금지 |
| **X8** | `exchanges/*` | 🔴 | 브로커 어댑터 금지 | 접촉 금지 |
| **X9** | `injection_gateway.py` | 🔴 | Stage 1 봉인 | 접촉 금지 |
| **X10** | `registry_service.py` | 🔴 | Stage 1 봉인 | 접촉 금지 |
| **X11** | `registry.py` (API) | 🔴 | Stage 1 봉인 | 접촉 금지 |
| **X12** | `runtime_strategy_loader.py` | 🔴 | Runtime 실행 금지 | 접촉 금지 |
| **X13** | `feature_cache.py` | 🔴 | 캐시 구현 금지 | 접촉 금지 |
| **X14** | `asset_validators.py` 로직 수정 | 🟡 | Stage 2A 봉인 | 수정 금지 |
| **X15** | `constitution.py` 상수 수정 | 🟡 | Stage 2A 봉인 | 수정 금지 |

---

## 6. Stage 3B-1 / 3B-2 경계 규약

### 3B-1 범위 (계약 강화)

| 허용 | 금지 |
|------|------|
| frozen dataclass 추가 | 외부 API 호출 |
| pure enum 추가 | DB session 사용 |
| pure 함수 추가 | async 구현 |
| Purity Guard 테스트 | Celery task 등록 |
| Failure Mode 테스트 | FROZEN 함수 수정 |
| 계약/정책 정의 | screening 로직 변경 |

### 3B-2 범위 (read-only adapter stub)

| 허용 | 금지 |
|------|------|
| Stub/fixture adapter | 실 API 연결 |
| ScreeningInput 변환 규약 테스트 | DB write |
| DataQuality→ScreeningInput 매핑 테스트 | beat/task 등록 |
| 단위 테스트 | FROZEN 함수 수정 |

---

```
CR-048 Stage 3B Boundary Contract Spec v1.0
Document ID: GOV-L3-STAGE3B-CONTRACT-001
Date: 2026-04-03
Authority: A
Status: SUBMITTED
Pure Zone: 6 files, 8 rules (PZ-01~PZ-08)
Contamination Line: 5 rules (CL-01~CL-05)
FROZEN: 2 functions, 5 rules (FR-01~FR-05)
Allowed Touch: 7 items (T1-T7)
Prohibited Touch: 15 items (X1-X15)
```
