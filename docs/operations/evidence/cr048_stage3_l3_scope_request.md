# CR-048 Stage 3 L3 범위 요청서

**문서 ID:** GOV-L3-STAGE3-REQUEST-001
**작성일:** 2026-04-04
**Authority:** A (Decision Authority)
**CR:** CR-048
**전제:** Stage 2B L3 SEALED (4844/4844 PASS)
**변경 등급:** L0 (요청 문서 — 승인 전 구현 금지)

> **Stage 3 limited scope approval requested.**
> 본 문서는 심사 패키지입니다. A 승인 전까지 어떤 Stage 3 구현도 실행되지 않습니다.

---

## 1. 현재 기준선

| 항목 | 값 |
|------|-----|
| Gate | **LOCKED** |
| 운영 모드 | GUARDED_RELEASE |
| 회귀 기준선 | **4844/4844 PASS** |
| Stage 1 L3 | SEALED |
| Stage 2A L3 | SEALED |
| Stage 2B L3 | SEALED |
| 예외 | EX-001, EX-002 종결. 신규 0건. |

---

## 2. Stage 3 대상 현황 분석

### 이미 구현 완료된 컴포넌트

| 컴포넌트 | 파일 | 라인 | 상태 | Runtime Reach |
|----------|------|:----:|:----:|:-------------:|
| SymbolScreener (5-stage engine) | `symbol_screener.py` | 313 | **구현 완료** | NO — stateless, I/O 없음 |
| ScreeningInput / ScreeningOutput | `symbol_screener.py` | — | **구현 완료** | NO — dataclass |
| screen_and_update() | `asset_service.py` L347-409 | 63 | **FROZEN** | YES — 이미 통합 완료 |
| qualify_and_record() | `asset_service.py` L413-482 | 70 | **FROZEN** | YES — Phase 4 경계 |
| ScreeningResult 모델 | `asset.py` | — | **구현 완료** | NO — ORM |
| 스크리너 테스트 | `test_symbol_screener.py` | 710 | **구현 완료** | N/A |

### 미구현 — Stage 3 신규 구현 후보

| 컴포넌트 | 파일 | 위험 | 사유 |
|----------|------|:----:|------|
| SectorRotator | `sector_rotator.py` | HIGH | regime 연결, 섹터 가중치 |
| DataProvider | `data_provider.py` | **CRITICAL** | 외부 API (CoinGecko, KIS, KRX) |
| Screening Celery Task | `screening_tasks.py` | **CRITICAL** | 자동 실행 경로 |
| Beat Schedule 등록 | `celery_app.py` | **CRITICAL** (L4) | 자동 트리거 |

---

## 3. 위험 분석 — Stage 3 CRITICAL 항목 3건

| # | CRITICAL 항목 | 영향 | 완화 가능 여부 |
|:-:|--------------|------|:-------------:|
| C1 | **Beat schedule 등록** — L4 변경, 자동 실행 경로 개방 | Symbol.status 자동 변경 → CORE pool 자동 축소 | Stage 3에서 제외 → Stage 4로 연기 |
| C2 | **외부 API 호출** (DataProvider) — 네트워크 의존, 실패 시 cascading | screening 불가 → 상태 동결/WATCH 강제 | 읽기전용 + rate limit + fallback |
| C3 | **Symbol.status 자동 변경** — 수동→자동 전환 | CORE pool 자동 축소 가능 | 수동 트리거만 허용 (Stage 2B 패턴) |

---

## 4. 범위 제안 — Stage 3를 3A/3B로 분리

Delta 분석 결과, CRITICAL 3건을 한 번에 열면 blast radius가 Stage 2B 대비 3~5배 확대됩니다. Stage 2→2A/2B 분리와 동일한 패턴으로 **Stage 3A (순수 로직 + 수동 호출)** / **Stage 3B (자동화 + 외부 연결)**를 제안합니다.

### 분리 기준 (Litmus Test)

> **"이 변경이 Celery beat 또는 외부 네트워크 호출을 필요로 하는가?"**
> - NO → Stage 3A
> - YES → Stage 3B

### Stage 3A 범위 (본 요청)

| 허용 | 파일 | 유형 | Runtime Reach |
|------|------|:----:|:-------------:|
| SectorRotator 순수 로직 | `sector_rotator.py` (신규) | L3 | **NO** — 입력→출력, I/O 없음 |
| DataProvider **인터페이스만** | `data_provider.py` (신규) | L3 | **NO** — ABC/Protocol, 구현체 없음 |
| screen_and_update() FROZEN 해제 **제한적** | `asset_service.py` | L3 | **YES** — SectorRotator 가중치 반영만 |
| 전용 테스트 | `tests/test_sector_rotator.py` (신규) | L1 | N/A |
| 전용 테스트 | `tests/test_data_provider.py` (신규) | L1 | N/A |

| 금지 유지 | 사유 |
|-----------|------|
| `screening_tasks.py` 신규 생성 | Stage 3B |
| `celery_app.py` beat 등록 | Stage 3B (L4) |
| DataProvider 구현체 (외부 API 호출) | Stage 3B |
| Symbol.status 자동 변경 | Stage 3B |
| qualify_and_record() 수정 | Phase 4 |
| RuntimeStrategyLoader | Phase 5 |

### Stage 3B 범위 (별도 심사)

| 허용 후보 | 파일 | 위험 |
|-----------|------|:----:|
| DataProvider 구현체 | `data_provider.py` | CRITICAL |
| Screening Celery Task | `screening_tasks.py` | CRITICAL |
| Beat Schedule 등록 | `celery_app.py` | CRITICAL (L4) |
| Symbol.status 자동 변경 허용 | `asset_service.py` | CRITICAL |

---

## 5. Stage 3A GREEN / RED / AMBER 파일 분류

### GREEN (수정/생성 허용)

| 파일 | 작업 | 사유 |
|------|------|------|
| `app/services/sector_rotator.py` | **신규** | 순수 계산 로직, I/O 없음 |
| `app/services/data_provider.py` | **신규** (인터페이스만) | ABC/Protocol 정의, 구현체 없음 |
| `tests/test_sector_rotator.py` | **신규** | L1 테스트 |
| `tests/test_data_provider.py` | **신규** | L1 인터페이스 계약 테스트 |

### AMBER (조건부 접촉)

| 파일 | 조건 |
|------|------|
| `app/services/asset_service.py` | screen_and_update()에 SectorRotator 가중치 반영만. FROZEN 해제 시 A 판정 별도 필요 |
| `tests/test_symbol_screener.py` | assertion 정렬만 (Stage 2B 패턴) |
| `tests/test_asset_registry.py` | assertion 정렬만 |

### RED (접촉 금지)

| 파일 | 사유 |
|------|------|
| `workers/tasks/screening_tasks.py` | Stage 3B |
| `workers/celery_app.py` | L4 — beat 등록 금지 |
| `app/services/symbol_screener.py` | 이미 완료, 수정 불요 |
| `app/services/backtest_qualification.py` | Phase 4 |
| `app/services/runtime_strategy_loader.py` | Phase 5 |
| `app/services/runtime_loader_service.py` | Phase 5 |
| `app/services/feature_cache.py` | Phase 5 |
| `app/services/injection_gateway.py` | Stage 1 SEALED |
| `app/services/registry_service.py` | Stage 1 SEALED |
| `app/api/routes/registry.py` | Stage 1 SEALED |
| `exchanges/*` | 브로커 금지 |

---

## 6. Runtime/Data Plane 영향표

### Stage 3A에서 NO→YES 전환 항목

| 항목 | Stage 2B | Stage 3A 제안 | 변화 |
|------|:--------:|:------------:|:----:|
| SectorRotator 호출 | NO | **YES** (순수 로직) | LOW — I/O 없음 |
| DataProvider 인터페이스 | NO | **YES** (ABC만) | NONE — 구현체 없음 |
| screen_and_update() 수정 | **FROZEN** | **조건부 해제** | MEDIUM — A 별도 판정 |
| 외부 API 호출 | NO | **NO** (Stage 3B) | NONE |
| Celery task | NO | **NO** (Stage 3B) | NONE |
| Beat schedule | NO | **NO** (Stage 3B) | NONE |
| Symbol.status 자동 변경 | 수동만 | **수동만** (Stage 3B까지) | NONE |

### 직접 영향 파일 / 간접 영향 파일

| 유형 | 파일 | 영향 |
|------|------|------|
| **직접** | `sector_rotator.py` | 신규 생성, 순수 로직 |
| **직접** | `data_provider.py` | 신규 생성, ABC만 |
| **조건부 직접** | `asset_service.py` | screen_and_update() FROZEN 해제 여부에 따라 |
| **간접** | `symbol_screener.py` | SectorRotator 출력을 ScreeningInput에 반영 시 |
| **간접** | `test_symbol_screener.py` | SectorRotator 통합 시 assertion 정렬 가능 |

---

## 7. Capability Wall

| Capability | Stage 3A | Stage 3B | Phase 4+ |
|------------|:--------:|:--------:|:--------:|
| SectorRotator 순수 계산 | **허용** | — | — |
| DataProvider ABC 정의 | **허용** | — | — |
| DataProvider 구현 (외부 호출) | ❌ | **후보** | — |
| Screening Celery Task | ❌ | **후보** | — |
| Beat Schedule 변경 | ❌ | **후보** (L4) | — |
| screen_and_update() 수정 | **조건부** | — | — |
| qualify_and_record() 수정 | ❌ | ❌ | **Phase 4** |
| Symbol.status 자동 변경 | ❌ | **후보** | — |
| Execute / Promote | ❌ | ❌ | ❌ |
| Activate Runtime | ❌ | ❌ | ❌ |
| Broker Connect | ❌ | ❌ | ❌ |
| Hard Delete | ❌ | ❌ | ❌ |
| Bulk Processing (무제한) | ❌ | ❌ | ❌ |

---

## 8. 제어 경계

### Fail-Closed 전략

| 시나리오 | 행동 |
|----------|------|
| SectorRotator 입력 누락 | 기본 가중치 반환 (equal weight), 에러 아님 |
| DataProvider ABC 미구현 호출 | NotImplementedError (구현체 없으므로 실제 호출 불가) |
| screen_and_update() SectorRotator 실패 | 가중치 무시, 기존 screening 결과만 반영 |

### Rollback 조건

| # | 트리거 | 롤백 행동 |
|:-:|--------|----------|
| 1 | 회귀 테스트 실패 | Stage 3A 코드 전체 revert |
| 2 | screen_and_update() 수정으로 기존 테스트 파괴 | 수정 revert, FROZEN 복원 |
| 3 | SectorRotator → regime 경로 연결 시도 | 즉시 중단 (CR-046 금지) |
| 4 | DataProvider 구현체 추가 시도 | 즉시 중단 (Stage 3B) |
| 5 | A 중단 지시 | 즉시 중단 |

### Kill Switch / 즉시 중단 조건 (5개)

| # | 조건 |
|:-:|------|
| 1 | `screening_tasks.py` 생성 시도 |
| 2 | `celery_app.py` beat 등록 시도 |
| 3 | 외부 API 실호출 코드 작성 시도 |
| 4 | qualify_and_record() 수정 시도 |
| 5 | RED 파일 접촉 |

---

## 9. 운영 제한

| 항목 | Stage 3A 제한 |
|------|:------------:|
| 최대 처리 건수 | N/A (순수 로직, 호출 상한 없음) |
| 수동/자동 여부 | **수동만** (Stage 3B까지 자동 금지) |
| 배치 상한 | N/A (Celery task 없음) |
| 스케줄러 허용 여부 | **NO** (beat 금지) |
| 외부 연결 여부 | **NO** (ABC만, 구현체 없음) |
| 감사 로그 | SymbolStatusAudit 기존 패턴 유지 (append-only) |

---

## 10. 검증 계획

### 전용 테스트 계획

| 테스트 파일 | 대상 | 예상 수 |
|------------|------|:-------:|
| `test_sector_rotator.py` | SectorRotator 순수 로직, 가중치 계산, 입력 누락 fallback | ~25 |
| `test_data_provider.py` | ABC 계약, NotImplementedError, 인터페이스 일치 | ~10 |
| (조건부) `test_screen_and_update_integration.py` | SectorRotator + SymbolScreener 통합 | ~15 |
| **예상 합계** | | **~50** |

### 회귀 계획

| 측정 | 현재 | Stage 3A 후 예상 |
|------|:----:|:---------------:|
| 전체 테스트 | 4844 | ~4894 (+50) |
| 실패 허용 | 0 | **0** |

### 봉인 조건

| # | 조건 |
|:-:|------|
| 1 | SectorRotator 순수 로직 테스트 PASS |
| 2 | DataProvider ABC 계약 테스트 PASS |
| 3 | (조건부) screen_and_update 통합 테스트 PASS |
| 4 | RED 파일 미접촉 확인 |
| 5 | 외부 API 실호출 코드 0건 확인 |
| 6 | Celery task / beat 등록 0건 확인 |
| 7 | 기존 테스트 유지 (4844건) |
| 8 | 전체 회귀 PASS |
| 9 | A 판정 |

---

## 11. Runtime Touch Budget vs Blast Radius

| 측정 항목 | Stage 2B (봉인) | Stage 3A (제안) | 변화 |
|-----------|:--------------:|:--------------:|:----:|
| 변경 함수 수 | 3 | +1~2 (rotator + 조건부 screen_and_update) | **소폭 증가** |
| 신규 side-effect 수 | 0 | **0** (순수 로직만) | **동일** |
| 영향 read path 수 | 1 | +0~1 (rotator 가중치 → screening 입력) | **소폭 증가** |
| Batch 상한 | 10 | N/A (수동 호출) | **동일** |
| 외부 연결 | 0 | **0** (ABC만) | **동일** |
| Rollback 난이도 | LOW | **LOW** (순수 로직 삭제) | **동일** |
| Fail-closed 가능 여부 | 전부 YES | **전부 YES** | **동일** |

### Stage 3A vs Stage 3 전체 비교

| 측정 항목 | Stage 3A (본 제안) | Stage 3 전체 | 축소율 |
|-----------|:-----------------:|:-----------:|:------:|
| CRITICAL 항목 | **0** | 3 | 100% 제거 |
| 외부 연결 | **0** | 2~3 | 100% 제거 |
| Beat 변경 | **0** | 1+ (L4) | 100% 제거 |
| 자동 실행 | **NO** | YES | 100% 제거 |
| 신규 side-effect | **0** | 3 | 100% 제거 |

---

## 12. screen_and_update() FROZEN 해제 분석

### 현재 상태

`screen_and_update()`는 Stage 2B에서 **FROZEN** (0줄 수정). 이 함수는 이미 SymbolScreener를 호출하는 완전한 통합 코드.

### Stage 3A에서 수정이 필요한 경우

SectorRotator 가중치를 screening에 반영하려면 `screen_and_update()` 내부에서 rotator 호출이 필요할 수 있음.

### 선택지

| 선택지 | 설명 | 위험 |
|--------|------|:----:|
| **A. FROZEN 유지** | SectorRotator를 screen_and_update() 외부에서만 사용. 통합은 Stage 3B | LOW |
| **B. 제한적 해제** | screen_and_update()에 SectorRotator 호출 1줄 삽입. 나머지 미수정 | MEDIUM |
| **C. 완전 해제** | 함수 재작성. SectorRotator + DataProvider 통합 | HIGH |

### 제안

**선택지 A (FROZEN 유지)**를 기본으로 제안합니다.
- SectorRotator는 독립 순수 함수로 구현
- screen_and_update() 통합은 Stage 3B에서 심사
- Stage 3A의 blast radius를 Stage 2B와 동등하게 유지

**선택지 B가 필요한 경우**, A에게 별도 판정을 요청합니다.

---

## 13. CR-046 충돌 검토

| CR-046 금지 | Stage 3A 계획 | 충돌 |
|-------------|:------------:|:----:|
| RegimeDetector 수정 금지 | SectorRotator는 RegimeDetector를 **사용하지 않음** (독립 입력) | ❌ 없음 |
| Regime filter signal pipeline 연결 금지 | SectorRotator는 signal pipeline **무관** | ❌ 없음 |
| ETH 운영 경로 금지 | Stage 3A는 운영 경로 아님 (순수 로직) | ❌ 없음 |
| BTC Session 2 금지 | Stage 3A는 session 무관 | ❌ 없음 |

**SectorRotator 입력:** regime 데이터를 **파라미터로 받는 순수 함수**. RegimeDetector를 import하거나 호출하지 않음. CR-046 금지와 충돌 없음.

---

## 14. 요청 정리

### 본 요청의 범위

**Stage 3A Limited L3 — 순수 로직 + 인터페이스 정의**

- SectorRotator 순수 계산 로직 (I/O 없음)
- DataProvider ABC/Protocol (구현체 없음)
- 전용 테스트 (~50건)
- screen_and_update() **FROZEN 유지** (선택지 A)

### 명시적으로 포함하지 않는 것

- DataProvider 구현체 (외부 API) → Stage 3B
- Screening Celery Task → Stage 3B
- Beat Schedule 변경 → Stage 3B (L4)
- Symbol.status 자동 변경 → Stage 3B
- qualify_and_record() 수정 → Phase 4

### 결론

> **Stage 3A limited scope approval requested.**
> CRITICAL 0건, 외부 연결 0건, 자동 실행 0건.
> Blast radius는 Stage 2B와 동등 수준.
> A 승인 전까지 구현 착수하지 않습니다.

---

```
CR-048 Stage 3 L3 Scope Request v1.0
Document ID: GOV-L3-STAGE3-REQUEST-001
Date: 2026-04-04
Authority: A
Status: SUBMITTED (A 심사 대기)
Scope: Stage 3A (pure logic + ABC interface)
CRITICAL items: 0 (all deferred to Stage 3B)
External connections: 0
Beat/scheduler: NO
screen_and_update(): FROZEN (선택지 A)
Implementation: NOT YET REQUESTED
```
