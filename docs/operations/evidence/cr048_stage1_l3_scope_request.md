# CR-048 Stage 1 L3 범위 요청서

**문서 ID:** GOV-L3-STAGE1-001
**작성일:** 2026-04-04
**Authority:** A (Decision Authority)
**CR:** CR-048
**변경 등급:** L3 (서비스 로직)
**전제:** Phase 2+3A 설계 기준선 고정 완료 (A 승인 2026-04-04)
**참조:** `cr048_staged_l3_expansion_proposal.md` Stage 1

> **본 문서는 Stage 1 L3 범위 요청서입니다. A 승인 전까지 아래 파일 변경은 실행되지 않습니다.**

---

## 1. 해석 및 요약

### 목적

Phase 1 Control Plane 서비스를 완결하기 위한 L3 범위 요청.
현재 **모델 스켈레톤(L3 Limited)**만 존재하는 4개 Registry 모델에 대해,
검증 로직(Injection Gateway)과 CRUD 서비스(Registry Service)를 구현하여
**"등록 요청 → 검증 → 저장 → 조회"** 경로를 완성합니다.

### 현재 상태

| 항목 | 값 |
|------|-----|
| Gate | LOCKED |
| 회귀 기준선 | 4623/4623 PASS |
| 허용 범위 | L0/L1/L2 + Limited L3(model skeleton) |
| 설계 기준선 | Phase 0~3A 설계 카드 전부 고정 |
| 예외 | EX-001, EX-002 종결 |

### 요청 개요

| 항목 | 내용 |
|------|------|
| 대상 Phase | Phase 1 (Control Plane Registry) |
| 대상 Stage | Stage 1 (L3 확장 제안서 기준) |
| 변경 등급 | L3 (서비스 로직) |
| 변경 파일 수 | 최대 7개 (서비스 3 + API 1 + 테스트 3) |
| 모델 변경 | 없음 (기존 스켈레톤 유지) |
| DB 스키마 변경 | 없음 |

---

## 2. 장점 / 단점

### 장점

| 장점 | 설명 |
|------|------|
| **설계 선행 완료** | 4개 설계 카드 + 58항목 추적표 + 57건 계약 테스트가 이미 고정 |
| **blast radius 최소** | Registry 서비스는 Data Plane(실행면)과 완전 분리 |
| **기존 코드 활용** | injection_gateway.py, registry.py 이미 존재 — 확장만 |
| **금지 경로 차단 강화** | Gateway 검증 로직이 실제로 작동하게 됨 |

### 단점

| 단점 | 완화 방안 |
|------|-----------|
| write API 개방 | Registry 등록/조회에 한정, 주문/실행 경로와 무관 |
| 서비스 로직 추가 | 순수 검증+CRUD, 외부 API 호출 없음 |
| 테스트 범위 증가 | 서비스 단위 테스트로 커버, 회귀 유지 |

---

## 3. 이유 / 근거

### 근거 1 — 모델만으로는 의미 없음

현재 4개 모델(Indicator, FeaturePack, Strategy, PromotionEvent)은 스켈레톤만 있고,
이를 생성/검증/조회하는 서비스가 없어 실제 사용 불가.
Gateway 검증 함수도 존재하지만, 서비스 레이어에서 호출하는 CRUD가 없으면
금지 브로커/섹터 차단이 코드 수준에서 강제되지 않음.

### 근거 2 — Phase 2 의존

Phase 2(Asset Service 확장)는 Phase 1 Registry가 완성되어야
전략-종목 매핑, 자산-브로커 교차 검증 등을 구현 가능.
Stage 1이 없으면 Stage 2도 시작 불가.

### 근거 3 — 파일 분류가 명확

Stage 1에서 변경할 파일이 정확히 식별되어 있고,
Data Plane(runtime_strategy_loader, feature_cache, order_executor 등)과
완전히 분리되어 cascading effect가 없음.

---

## 4. 실현 / 구현 대책

### 파일 3분할 분류표

#### 허용 (GREEN) — Stage 1에서 변경 가능

| 파일 | 작업 | 등급 | 근거 |
|------|------|:----:|------|
| `app/services/injection_gateway.py` | 6단계 검증 로직 확장 | L3 | 설계 카드 §S-01 Gateway 7단계 |
| `app/services/registry_service.py` | 신규 — Registry CRUD 서비스 | L3 | 설계 카드 4개 모델의 생성/조회 |
| `app/api/routes/registry.py` | 기존 write API 확장 (POST/GET) | L3 | 등록+조회 엔드포인트 |
| `tests/test_injection_gateway_service.py` | 신규 — Gateway 서비스 테스트 | L1 | Gateway 6단계 검증 + 금지 차단 |
| `tests/test_registry_service.py` | 신규 — Registry CRUD 테스트 | L1 | CRUD 정상/실패/경계 |
| `tests/test_registry_api.py` | 신규 — API 통합 테스트 | L1 | 엔드포인트 응답/에러 |
| `app/schemas/registry_schema.py` | 기존 스키마 확장 (등록 요청/응답) | L2 | Pydantic 검증 |

#### 금지 (RED) — Stage 1에서 변경 불가

| 파일/범위 | 사유 |
|-----------|------|
| `app/services/runtime_strategy_loader.py` | Data Plane — Phase 5 |
| `app/services/runtime_loader_service.py` | Data Plane — Phase 5 |
| `app/services/feature_cache.py` | Data Plane — Phase 5 |
| `app/services/asset_service.py` | Stage 2 범위 |
| `app/services/symbol_screener.py` (신규 금지) | Stage 3 범위 |
| `app/services/sector_rotator.py` (신규 금지) | Stage 3 범위 |
| `app/services/data_provider.py` (신규 금지) | Stage 3 범위 |
| `app/services/backtest_qualification.py` | Phase 4 |
| `app/services/paper_shadow_service.py` | Phase 4 |
| `app/services/promotion_gate.py` (신규 금지) | Phase 4 |
| `app/services/strategy_router.py` | Data Plane |
| `app/services/order_executor.py` | Data Plane — 주문 경로 |
| `workers/tasks/*` | Celery task — L4 |
| `exchanges/*` | 거래소 어댑터 — Phase 3B+ |
| `app/core/config.py` (exchange_mode) | L4 |
| `app/models/*` | 모델 변경 없음 (스켈레톤 확정) |
| `alembic/versions/*` | DB 스키마 변경 없음 |

#### 회색지대 (AMBER) — 사전 예외 승인 시에만 변경 가능

| 파일 | 잠재적 필요성 | 예외 조건 |
|------|-------------|-----------|
| `app/core/constitution.py` | Gateway가 새 상수를 참조해야 할 경우 | 상수 추가만 허용, 기존 값 변경 금지, 사전 보고 |
| `app/models/indicator_registry.py` | CRUD 중 컬럼 제약 추가 필요 시 | 제약(nullable, default) 조정만, 신규 컬럼 금지 |
| `app/models/feature_pack.py` | 동일 | 동일 |
| `app/models/strategy_registry.py` | 동일 | 동일 |
| `app/models/promotion_state.py` | 동일 | 동일 |
| `app/services/strategy_registry.py` (기존 서비스) | registry_service.py와 책임 분리 시 | 함수 이동만 허용, 로직 추가 금지 |

---

## 5. 실행방법

### Stage 1 구현 범위

| 단계 | 작업 | 파일 | 의존성 |
|:----:|------|------|--------|
| 1 | Registry CRUD 서비스 작성 | `registry_service.py` (신규) | 4개 모델 |
| 2 | Injection Gateway 검증 로직 확장 | `injection_gateway.py` 확장 | constitution.py |
| 3 | Registry 스키마 확장 | `registry_schema.py` 확장 | — |
| 4 | Registry API 엔드포인트 확장 | `registry.py` 확장 | 서비스+스키마 |
| 5 | Gateway 서비스 테스트 작성 | `test_injection_gateway_service.py` (신규) | — |
| 6 | Registry CRUD 테스트 작성 | `test_registry_service.py` (신규) | — |
| 7 | API 통합 테스트 작성 | `test_registry_api.py` (신규) | — |
| 8 | 전체 회귀 | — | 전체 |

### 구현 상세 — Injection Gateway 검증 항목

설계 카드 `design_strategy_registry.md` S-01 기준:

| # | 검증 단계 | 내용 | 실패 시 |
|:--:|-----------|------|---------|
| 1 | forbidden_broker 체크 | ALPACA, KIWOOM_US → 즉시 거부 | 400 + 사유 |
| 2 | forbidden_sector 체크 | 7개 금지 섹터 → 즉시 거부 | 400 + 사유 |
| 3 | dependency 검증 | 필요 지표/FP 존재 확인 | 400 + 누락 목록 |
| 4 | version checksum 검증 | manifest 체크섬 일치 | 400 + mismatch |
| 5 | manifest signature 검증 | 서명 유효성 | 400 + invalid |
| 6 | 시장 매트릭스 호환성 | asset_class ↔ broker 호환 | 400 + 불일치 |

### 구현 상세 — Registry CRUD

| 모델 | 생성(Create) | 조회(Read) | 수정(Update) | 삭제(Delete) |
|------|:----------:|:--------:|:----------:|:----------:|
| Indicator | O | O | 버전 발행만 | soft only |
| FeaturePack | O | O | 버전 발행만 | soft only |
| Strategy | O (Gateway 경유) | O | 버전 발행만 | soft only |
| PromotionEvent | O (기록 전용) | O | **금지** | **금지** |

**규칙:**
- Strategy 생성은 반드시 Injection Gateway 검증 통과 후에만
- PromotionEvent는 append-only (수정/삭제 불가)
- 모든 생성/수정은 감사 로그 기록
- Promotion 상태 전이 **실행**은 Stage 1 범위 아님 (기록만 허용)

### 봉인 조건

Stage 1 완료 시 아래를 모두 충족해야 봉인:

| # | 조건 | 검증 방법 |
|:--:|------|-----------|
| 1 | Gateway 6단계 검증 테스트 전부 PASS | `test_injection_gateway_service.py` |
| 2 | Registry CRUD 테스트 전부 PASS | `test_registry_service.py` |
| 3 | 금지 브로커 등록 시도 → 거부 테스트 PASS | ALPACA, KIWOOM_US 차단 |
| 4 | 금지 섹터 등록 시도 → 거부 테스트 PASS | 7개 섹터 차단 |
| 5 | 자산-브로커 호환 위반 → 거부 테스트 PASS | CRYPTO+KIS_US 등 |
| 6 | API 엔드포인트 테스트 PASS | `test_registry_api.py` |
| 7 | 기존 계약 테스트 유지 (57+30건) | regression |
| 8 | 전체 회귀 PASS (4623+α) | `pytest --tb=short -q` |
| 9 | **A 판정** | 제출 후 판정 |

### 중단 조건

| 조건 | 행동 |
|------|------|
| 회귀 실패 발생 | 즉시 중단, 원인 분석 |
| RED 파일 변경 필요 발견 | 즉시 중단, 사전 예외 요청 |
| AMBER 파일 변경 필요 | 작업 일시 중지, 사전 보고 후 승인 대기 |
| 설계-구현 불일치 발견 | 즉시 중단, 설계 카드 재검토 |
| Data Plane 영향 감지 | 즉시 중단, EX 리뷰 |
| A 중단 지시 | 즉시 중단 |

### 예외 승인 필요 지점

| 지점 | 예외 유형 | 처리 |
|------|-----------|------|
| constitution.py 상수 추가 필요 | 정책 변경 인접 | **사전 보고 + A 승인** |
| 모델 제약(nullable/default) 조정 필요 | 스키마 인접 | **사전 보고 + A 승인** |
| 기존 서비스 함수 이동 필요 | 책임 재분배 | **사전 보고** |
| 테스트에서 서비스 실호출 필요 | 통합 테스트 경계 | mock 우선, 실호출 시 사전 보고 |

---

## 6. 더 좋은 아이디어

### Promotion 상태 전이 "기록 전용" 모드

Stage 1에서 PromotionEvent를 생성할 수 있지만, **상태 전이를 실행하지는 않는** 모드를 제안합니다.

즉:
- `PromotionEvent.create(strategy_id, from_status, to_status, ...)` → 기록만
- 실제 `Strategy.promotion_status` 필드를 변경하는 로직은 **Stage 1에서 금지**
- Phase 4에서 Promotion Gate 서비스가 이를 담당

이렇게 하면 Stage 1에서 "누가 어떤 전이를 요청했는지"는 기록되지만,
실제 전이는 일어나지 않아 안전합니다.

### 테스트 격리 전략

Stage 1 서비스 테스트는 **DB 없이** 실행 가능하도록 설계합니다:
- 서비스 레이어: mock repository 패턴
- Gateway 검증: 순수 함수 + constitution 상수만 의존
- API 테스트: FastAPI TestClient + mock 서비스

이렇게 하면 기존 4623건 회귀에 영향 없이 신규 테스트를 추가할 수 있습니다.

---

## A에게 제출하는 항목 (L3 확장 제안서 §4 기준)

| # | 항목 | 내용 |
|:--:|------|------|
| 1 | 이전 Stage 봉인 증빙 | 설계 기준선 고정 완료 (A 승인 2026-04-04) |
| 2 | Stage 1 파일 목록 + 변경 범위 | GREEN 7파일, AMBER 6파일(조건부), RED 17+파일(금지) |
| 3 | 금지 범위 갱신표 | 본 문서 §4 RED 표 참조 |
| 4 | 예상 테스트 추가 수 | 40~60건 (Gateway 15~20 + CRUD 15~20 + API 10~20) |
| 5 | 회귀 기준선 현재 수치 | **4623/4623 PASS** |

---

```
CR-048 Stage 1 L3 Scope Request v1.0
Document ID: GOV-L3-STAGE1-001
Date: 2026-04-04
Authority: A
Status: REQUEST (A 승인 전까지 구현 착수 불가)
Gate: LOCKED (유지 전제)
Prerequisite: Phase 2+3A Design Baseline FIXED
```
