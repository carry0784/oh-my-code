# CR-048 Stage 3B Purity Guard Spec

**문서 ID:** GOV-L3-STAGE3B-PURITY-001
**작성일:** 2026-04-03
**Authority:** A (Decision Authority)
**CR:** CR-048
**전제:** Boundary Contract Spec (GOV-L3-STAGE3B-CONTRACT-001)
**목적:** Pure Zone 오염 방지를 위한 자동 검증 규격 정의

> 이 문서는 검증 규격만 포함한다. 테스트 코드 구현 지침 없음.

---

## 1. Purity Guard 개요

### 1-1. 목적

Pure Zone 6개 파일이 외부 상태(DB, 네트워크, 파일, 캐시, 환경변수, Celery, async 실행)에 오염되지 않았음을 **자동으로 검증**하는 테스트 규격.

### 1-2. 검증 방법론

| 방법 | 적용 범위 | 설명 |
|------|-----------|------|
| **AST 정적 분석** | import, 함수 정의, 데코레이터 | 소스 코드 파싱 후 금지 패턴 탐지 |
| **문자열 검색** | 특정 키워드 | 소스 텍스트에서 금지 문자열 탐지 |
| **Module 인트로스펙션** | 런타임 속성 | 모듈 로드 후 속성 검사 |

### 1-3. 대상 파일

| # | 파일 | 현재 Purity Proof | Stage 3B 강화 |
|:-:|------|:------------------:|:------------:|
| 1 | `sector_rotator.py` | ✅ 9 tests | + G1-G10 강화 |
| 2 | `data_provider.py` | ✅ 7 tests | + G1-G10 강화 |
| 3 | `symbol_screener.py` | ❌ 없음 | 신규 추가 |
| 4 | `backtest_qualification.py` | ❌ 없음 | 신규 추가 |
| 5 | `asset_validators.py` | ❌ 없음 | 신규 추가 |
| 6 | `constitution.py` | ❌ 없음 | 신규 추가 |

---

## 2. 금지 패턴 규격 (32종)

### 2-1. 금지 Import (16종)

| ID | 패턴 | 검증 방법 | 대상 파일 | 심각도 |
|:--:|------|-----------|-----------|:------:|
| P1 | `import asyncio` | AST ImportFrom | 전체 (data_provider 제외) | HIGH |
| P2 | `from sqlalchemy` | AST ImportFrom | 전체 | HIGH |
| P3 | `from sqlalchemy.ext.asyncio import AsyncSession` | AST ImportFrom | 전체 | HIGH |
| P4 | `import httpx` | AST Import | 전체 | HIGH |
| P5 | `import requests` / `from requests` | AST Import/ImportFrom | 전체 | HIGH |
| P6 | `import aiohttp` / `from aiohttp` | AST Import/ImportFrom | 전체 | HIGH |
| P7 | `from celery` / `import celery` | AST Import/ImportFrom | 전체 | HIGH |
| P8 | `import redis` / `from redis` | AST Import/ImportFrom | 전체 | MED |
| P9 | `import os` | AST Import | 전체 | MED |
| P10 | `from dotenv` | AST ImportFrom | 전체 | MED |
| P11 | `import socket` | AST Import | 전체 | MED |
| P12 | `import urllib` / `from urllib` | AST Import/ImportFrom | 전체 | MED |
| P13 | `import subprocess` | AST Import | 전체 | MED |
| P14 | `import shutil` | AST Import | 전체 | LOW |
| P15 | `import tempfile` | AST Import | 전체 | LOW |
| P16 | `from app.services.regime_detector` | AST ImportFrom | 전체 | HIGH |

#### P1 예외: data_provider.py

`data_provider.py`는 ABC 메서드 선언에 `async def`를 사용하지만, `asyncio` import는 불필요.
ABC 메서드 선언의 `async def`는 **PZ-08 예외 규칙**에 따라 허용 (body가 `...` 또는 docstring만일 때).

### 2-2. 금지 Async 패턴 (3종)

| ID | 패턴 | 검증 방법 | 대상 파일 | 심각도 |
|:--:|------|-----------|-----------|:------:|
| A1 | `async def` (non-ABC) | AST AsyncFunctionDef | sector_rotator, screener, qualifier, validators, constitution | HIGH |
| A2 | `await` 키워드 | AST Await | 전체 (data_provider ABC body 제외) | HIGH |
| A3 | `asyncio.run()` / `asyncio.get_event_loop()` | AST Call + Attribute | 전체 | HIGH |

#### A1 예외: data_provider.py

`data_provider.py`의 `async def`는 ABC 메서드 선언이므로 허용.
**검증 기준:** `async def`가 존재하되, body가 `...` / `pass` / docstring만인 경우 허용.

### 2-3. 금지 Side-effect 패턴 (9종)

| ID | 패턴 | 검증 방법 | 대상 파일 | 심각도 |
|:--:|------|-----------|-----------|:------:|
| S1 | `open(` | 문자열 검색 | 전체 | MED |
| S2 | `Path(` + read/write 메서드 | AST Call + Attribute | 전체 | MED |
| S3 | `os.environ` / `os.getenv` | AST Attribute | 전체 | MED |
| S4 | `json.load(` / `json.dump(` (파일 핸들) | AST Call | 전체 | MED |
| S5 | `.add(` / `.flush(` / `.commit(` (session) | 문자열 검색 (context 확인) | 전체 | HIGH |
| S6 | `.execute(` (SQL) | 문자열 검색 (context 확인) | 전체 | HIGH |
| S7 | `@app.task` | AST decorator | 전체 | HIGH |
| S8 | `@shared_task` / `@celery_app.task` | AST decorator | 전체 | HIGH |
| S9 | `beat_schedule` | 문자열 검색 | 전체 | HIGH |

#### S5/S6 오탐 방지

`session.add()` / `session.flush()` / `session.execute()`는 DB operation이지만,
Pure Zone 파일에 `session`이라는 변수 자체가 없어야 하므로, import 검사(P2/P3)가 1차 방어선.
S5/S6는 2차 방어선 (만약 session이 매개변수로 전달되는 경우까지 포착).

### 2-4. 금지 Runtime 의존 패턴 (4종)

| ID | 패턴 | 검증 방법 | 대상 파일 | 심각도 |
|:--:|------|-----------|-----------|:------:|
| R1 | `from app.services.asset_service` | AST ImportFrom | 전체 Pure Zone | HIGH |
| R2 | `from app.services.registry_service` | AST ImportFrom | 전체 Pure Zone | HIGH |
| R3 | `from app.services.injection_gateway` | AST ImportFrom | 전체 Pure Zone | HIGH |
| R4 | `from app.services.runtime_strategy_loader` | AST ImportFrom | 전체 Pure Zone | HIGH |

---

## 3. 허용 Import 규격

Pure Zone 파일이 import할 수 있는 모듈 화이트리스트.

### 3-1. 허용 stdlib

| 모듈 | 용도 |
|------|------|
| `dataclasses` | frozen dataclass 정의 |
| `enum` | Enum 정의 |
| `datetime` | 시각/날짜 타입 |
| `typing` | 타입 힌트 |
| `abc` | ABC/abstractmethod (data_provider만) |
| `logging` | 로거 (side-effect 논의: §3-2) |
| `json` | JSON 직렬화 (메모리 내 변환만, 파일 I/O 금지) |
| `math` | 수학 함수 |
| `collections` | 데이터 구조 |
| `functools` | 데코레이터 |
| `re` | 정규식 |

### 3-2. logging 허용 조건

| 조건 | 허용 |
|------|:----:|
| `logging.getLogger(__name__)` | ✅ |
| `logger.info/warning/error()` | ✅ |
| `logging.FileHandler` | ❌ (파일 I/O) |
| `logging.SocketHandler` | ❌ (네트워크) |

**logging은 "경미한 side-effect"이나, 파일/네트워크 핸들러 없이 stdout/stderr만 사용하면 허용.**

### 3-3. 허용 내부 모듈

| Pure Zone 파일 | import 허용 대상 |
|---------------|-----------------|
| `sector_rotator.py` | `app.models.asset` (enum/상수만) |
| `data_provider.py` | 없음 (self-contained) |
| `symbol_screener.py` | `app.models.asset` (enum/상수만) |
| `backtest_qualification.py` | `app.models.qualification` (enum/상수만) |
| `asset_validators.py` | `app.models.asset`, `app.core.constitution` (상수만) |
| `constitution.py` | `app.models.asset` (enum만) |

**규칙:** Pure Zone 파일은 다른 Pure Zone 파일 또는 모델(enum/상수만) import 가능. 서비스 계층 import 금지.

---

## 4. Purity Guard 테스트 구조

### 4-1. test_purity_guard.py (통합)

| 테스트 클래스 | 대상 | 검증 항목 | 예상 테스트 수 |
|-------------|------|-----------|:-------------:|
| `TestSectorRotatorPurity` | sector_rotator.py | P1-P16, A1-A3, S1-S9, R1-R4 | ~12 |
| `TestDataProviderPurity` | data_provider.py | P1-P16, A1-A3(예외), S1-S9, R1-R4 | ~12 |
| `TestSymbolScreenerPurity` | symbol_screener.py | P1-P16, A1-A3, S1-S9, R1-R4 | ~12 |
| `TestBacktestQualifierPurity` | backtest_qualification.py | P1-P16, A1-A3, S1-S9, R1-R4 | ~12 |
| `TestAssetValidatorsPurity` | asset_validators.py | P1-P16, A1-A3, S1-S9, R1-R4 | ~12 |
| `TestConstitutionPurity` | constitution.py | P1-P16, A1-A3, S1-S9, R1-R4 | ~10 |

**예상 총 테스트: ~70**

### 4-2. 기존 Purity Proof와의 관계

| 기존 테스트 | 위치 | 유지 |
|------------|------|:----:|
| `TestInterfacePurityProof` (sector_rotator) | test_sector_rotator.py | ✅ 유지 |
| `TestInterfacePurityProof` (data_provider) | test_data_provider.py | ✅ 유지 |

**기존 테스트는 유지. test_purity_guard.py는 6개 파일 통합 검사로 커버리지 확장.**

### 4-3. 검증 유틸리티 함수 (test 내부)

테스트 코드 내 재사용 가능한 검증 함수 (테스트 파일 내부에만 존재, 프로덕션 코드에 포함 안 됨).

| 함수 | 용도 |
|------|------|
| `_parse_source(file_path)` | AST 파싱 + 소스 텍스트 반환 |
| `_collect_imports(tree)` | AST에서 모든 import 추출 |
| `_has_forbidden_import(imports, forbidden_list)` | 금지 import 존재 여부 |
| `_collect_async_defs(tree)` | async def 함수 목록 추출 |
| `_collect_decorators(tree)` | 데코레이터 목록 추출 |
| `_has_forbidden_string(source, pattern)` | 소스 텍스트에서 금지 패턴 검색 |

---

## 5. Purity Guard 실행 정책

### 5-1. 실행 시점

| 시점 | 필수 여부 |
|------|:---------:|
| 매 Stage 회귀 테스트 실행 시 | **필수** |
| 신규 파일 추가 시 (Pure Zone 내) | **필수** |
| 기존 Pure Zone 파일 수정 시 | **필수** |
| CI/CD 파이프라인 | **권장** |

### 5-2. 실패 시 행동

| 등급 | 실패 시 |
|------|---------|
| HIGH | **즉시 중단 + 커밋 금지** |
| MED | **경고 + A 검토 요청** |
| LOW | **경고 기록** |

### 5-3. 새 Pure Zone 파일 추가 시

새 파일이 Pure Zone에 추가되면:
1. test_purity_guard.py에 해당 파일 테스트 클래스 추가 **필수**
2. 허용 import 목록(§3-3) 업데이트 **필수**
3. Boundary Contract Spec 업데이트 **필수**

---

## 6. Stage 3A 기존 Purity Proof 누락 보강 항목

Boundary Inventory §1-3에서 식별된 누락 항목(G1-G10)의 보강 계획.

| ID | 누락된 검증 | 대상 파일 | Purity Guard에서 커버 | 금지 패턴 ID |
|:--:|------------|-----------|:-------------------:|:-----------:|
| G1 | aiohttp import | sector_rotator.py | ✅ | P6 |
| G2 | open()/Path() | sector_rotator.py | ✅ | S1, S2 |
| G3 | os.environ | sector_rotator.py | ✅ | S3 |
| G4 | json.load/dump (파일) | 양쪽 | ✅ | S4 |
| G5 | logging handler | 양쪽 | ✅ (handler 유형 검사) | §3-2 |
| G6 | @task decorator | 양쪽 | ✅ | S7, S8 |
| G7 | Session/engine/connection | 양쪽 | ✅ | P2, P3 |
| G8 | redis/celery import | sector_rotator.py | ✅ | P7, P8 |
| G9 | socket/urllib | 양쪽 | ✅ | P11, P12 |
| G10 | subprocess/Popen | 양쪽 | ✅ | P13 |

**G1-G10 전부 Purity Guard 통합 테스트에서 커버.**

---

```
CR-048 Stage 3B Purity Guard Spec v1.0
Document ID: GOV-L3-STAGE3B-PURITY-001
Date: 2026-04-03
Authority: A
Status: SUBMITTED
Forbidden Patterns: 32 (P16 + A3 + S9 + R4)
Target Files: 6 (Pure Zone 전체)
Expected Tests: ~70
Existing Purity Proof: 유지 (16 tests in 2 files)
Gaps Covered: G1-G10 전부
Execution: 매 회귀 시 필수
```
