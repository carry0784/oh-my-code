# CR-048 단계적 L3 범위 확장 제안서

**문서 ID:** GOV-L3-PROPOSAL-001
**작성일:** 2026-04-04
**Authority:** A (Decision Authority)
**CR:** CR-048
**변경 등급:** L0 (제안 문서 — 승인 자체를 선반영하지 않음)
**전제:** Gate LOCKED 유지

> **본 문서는 제안서입니다. A 승인 전까지 어떤 L3 범위 확장도 실행되지 않습니다.**

---

## 1. 해석 및 요약

### 목적

현재 Limited L3(model skeleton only) 상태에서, CR-048 Phase 1~3 구현을 위해 L3 범위를 **단계적으로** 확장하는 로드맵을 제안합니다.

### 현재 기준선

| 항목 | 값 |
|------|-----|
| Gate | LOCKED |
| 허용 범위 | L0/L1/L2 + Limited L3(model skeleton) |
| 회귀 기준선 | 4593/4593 PASS |
| 예외 | EX-001, EX-002 종결 |
| 설계 문서 | 10건 (Phase 0: 3, Phase 1: 4, Phase 2: 1, Phase 3A: 1, Traceability: 1) |

### 제안 개요

L3를 한 번에 개방하지 않고 **3단계(Stage)로 분리하여 순차 개방**합니다.
각 Stage는 **선행 Stage 봉인 후에만** 다음 Stage를 검토합니다.

```
Stage 1: Phase 1 서비스 (Injection Gateway + Registry CRUD) ✅ COMPLETED/SEALED
    ↓ 봉인 완료 (2026-04-04, 4709/4709 PASS)
Stage 2A: Phase 2 정적 계층 (model/schema/validators — runtime 비연결) ← 다음 판정 지점
    ↓ 봉인 후
Stage 2B: Phase 2 서비스 계층 (asset_service 확장 — runtime-adjacent)
    ↓ 봉인 후
Stage 3: Phase 3A 서비스 (SymbolScreener + Sector Rotator + TTL)
```

---

## 2. 장점 / 단점

### 장점

| 장점 | 설명 |
|------|------|
| **점진적 리스크** | 한 번에 전체 L3를 열지 않으므로, 각 Stage에서 문제 발견 시 조기 중단 가능 |
| **중간 봉인** | 각 Stage 완료 시 회귀 기준선 + 금지 범위 재확인 |
| **설계 선행** | 각 Stage 진입 전에 설계 카드 + 계약 테스트가 이미 확정되어 있음 |
| **예외 방지** | 범위가 명확하므로 EX류 사후 예외 발생 가능성 감소 |
| **A 통제 유지** | 각 Stage 전환 시 A 판정 필요 |

### 단점

| 단점 | 완화 방안 |
|------|-----------|
| 진행 속도 느림 | 의도적 설계 — 속도보다 안전 우선 |
| Stage 간 의존성 | 명확한 의존 체인으로 관리 (아래 참조) |
| A 판정 빈도 증가 | 각 Stage 제출물을 명확히 하여 판정 효율 제고 |

---

## 3. 이유 / 근거

### 근거 1 — 한 번에 열면 범위 이탈 위험

Limited L3 배치에서도 `runtime_strategy_loader.py` 변경이 발생(EX-002).
더 넓은 범위를 한 번에 열면 cascading effect가 더 넓어짐.
단계적 개방으로 각 Stage의 blast radius를 제한.

### 근거 2 — 설계 카드가 이미 선행 완료

| Stage | 설계 카드 | 상태 |
|-------|----------|------|
| Stage 1 | design_indicator_registry.md, design_feature_pack.md, design_strategy_registry.md, design_promotion_state.md | **확정** |
| Stage 2 | design_asset_registry.md | **작성 완료** (본 배치) |
| Stage 3 | design_screening_engine.md | **작성 완료** (본 배치) |

즉, 모든 Stage의 "무엇을 만들 것인가"가 이미 문서화되어 있음.
L3 승인은 "만들어도 되는가"에 대한 판정만 필요.

### 근거 3 — Phase 의존 체인이 순차적

```
Phase 1 (Registry) → Phase 2 (Asset) → Phase 3A (Screening)
                                            ↓
                                       Phase 4 (Qualification)
```

Phase 2는 Phase 1의 Registry가 있어야 종목-전략 매핑 가능.
Phase 3A는 Phase 2의 Asset 모델이 있어야 스크리닝 대상 정의 가능.
따라서 순차 개방이 자연스러움.

---

## 4. 실현 / 구현 대책

### Stage 1: Phase 1 서비스 완결

**전제:** design_asset_registry.md + design_screening_engine.md A 승인 후

| 허용 | 파일 | 등급 |
|------|------|------|
| Injection Gateway 검증 로직 | `app/services/injection_gateway.py` 확장 | L3 |
| Registry CRUD 서비스 | `app/services/registry_service.py` (신규) | L3 |
| Registry write API | `app/api/routes/registry.py` 확장 | L3 |
| 서비스 단위 테스트 | `tests/test_injection_gateway_service.py` | L1 |

| 금지 유지 | 사유 |
|-----------|------|
| Promotion 상태 전이 실행 | Stage 1 범위 아님 |
| RuntimeStrategyLoader | Data Plane |
| Feature Cache | Data Plane |
| beat schedule 변경 | L4 |
| exchange_mode 변경 | L4 |
| KIS_US 어댑터 | Phase 3B |

**Stage 1 봉인 조건:** ✅ 전부 충족 (2026-04-04)
- Gateway 7단계 검증 테스트 PASS ✅
- Registry CRUD 테스트 PASS ✅
- 금지 브로커/섹터 등록 거부 테스트 PASS ✅
- 전체 회귀 PASS (4709/4709) ✅
- A 판정: ACCEPTED ✅
- 증빙: `cr048_stage1_l3_completion_evidence.md`

---

### Stage 2: Phase 2 서비스 확장

**전제:** Stage 1 봉인 완료

| 허용 | 파일 | 등급 |
|------|------|------|
| Symbol-Broker 교차 검증 | `app/services/asset_service.py` 확장 | L3 |
| TTL 만료 로직 (최소) | `app/services/asset_service.py` 확장 | L3 |
| 종목 상태 전이 감사 | `app/services/asset_service.py` 확장 | L3 |
| 서비스 단위 테스트 | `tests/test_asset_service_phase2.py` | L1 |

| 금지 유지 | 사유 |
|-----------|------|
| SymbolScreener 파이프라인 | Stage 3 |
| Celery screening task | Stage 3 |
| 외부 데이터 API 호출 | Stage 3 |
| Promotion 상태 전이 실행 | Phase 4 |
| RuntimeStrategyLoader | Data Plane |
| Feature Cache | Data Plane |
| beat schedule 변경 | L4 |
| exchange_mode 변경 | L4 |

**Stage 2 봉인 조건:** ✅ 전부 충족 (2026-04-04)
- Symbol-Broker 교차 검증 테스트 PASS ✅
- TTL 만료 로직 테스트 PASS (max 10, 수동, fail-closed) ✅
- EXCLUDED→CORE 직행 금지 테스트 PASS ✅
- screen_and_update/qualify_and_record FROZEN 유지 ✅
- 전체 회귀 PASS (4844/4844) ✅
- A 판정: ACCEPTED ✅
- 증빙: `cr048_stage2b_l3_completion_evidence.md`

---

### Stage 3: Phase 3A 스크리닝 엔진

**전제:** Stage 2 봉인 완료

| 허용 | 파일 | 등급 |
|------|------|------|
| SymbolScreener 5단계 | `app/services/symbol_screener.py` (신규) | L3 |
| SectorRotator | `app/services/sector_rotator.py` (신규) | L3 |
| DataProvider (읽기 전용) | `app/services/data_provider.py` (신규) | L3 |
| Screening Celery task | `workers/tasks/screening_tasks.py` (신규) | L3 |
| 서비스 단위 테스트 | `tests/test_symbol_screener.py` | L1 |

| 금지 유지 | 사유 |
|-----------|------|
| KIS_US 어댑터 | Phase 3B (별도 판정) |
| Backtest Qualification 9단계 | Phase 4 |
| Paper Shadow | Phase 4 |
| Promotion 상태 전이 실행 | Phase 4 |
| RuntimeStrategyLoader | Phase 5 |
| Feature Cache | Phase 5 |
| exchange_mode 변경 | L4 |

**Stage 3 봉인 조건:**
- 5단계 스크리닝 파이프라인 테스트 PASS
- Stage 1 FAIL → EXCLUDED 절대성 테스트 PASS
- Candidate TTL 만료 테스트 PASS
- 금지 섹터 = Exclusion Baseline 일치 테스트 PASS
- 전체 회귀 PASS
- A 판정

---

## 5. 실행방법

### 제안하는 타임라인

| 단계 | 선행 조건 | 내용 |
|------|-----------|------|
| **지금** | 없음 | 설계 카드 2건 + 계약 테스트 확장 (L0/L1) |
| **Stage 1 요청** | 설계 카드 A 승인 + 계약 테스트 PASS | Phase 1 서비스 L3 범위 요청 |
| **Stage 1 실행** | A 승인 | Injection Gateway + Registry CRUD |
| **Stage 1 봉인** | 회귀 PASS + A 판정 | Stage 1 기준선 봉인 |
| **Stage 2 요청** | Stage 1 봉인 | Phase 2 서비스 L3 범위 요청 |
| **Stage 2 실행** | A 승인 | Asset Service 확장 |
| **Stage 2 봉인** | 회귀 PASS + A 판정 | Stage 2 기준선 봉인 |
| **Stage 3 요청** | Stage 2 봉인 | Phase 3A 서비스 L3 범위 요청 |
| **Stage 3 실행** | A 승인 | SymbolScreener + TTL |
| **Stage 3 봉인** | 회귀 PASS + A 판정 | Phase 1~3A 완결 기준선 봉인 |

### 각 Stage 전환 시 A에게 제출할 것

1. 이전 Stage 봉인 증빙
2. 다음 Stage 파일 목록 + 변경 범위
3. 금지 범위 갱신표
4. 예상 테스트 추가 수
5. 회귀 기준선 현재 수치

---

## 6. 더 좋은 아이디어

### "파일 분류표" 제도화

A가 제안한 **모델 변경 동반 파일 분류표**를 각 Stage에 미리 적용:

| 파일 패턴 | Stage 1 | Stage 2 | Stage 3 |
|-----------|:-------:|:-------:|:-------:|
| `app/models/*` | 수정만 | 수정만 | 수정만 |
| `app/services/injection_gateway.py` | **허용** | 읽기만 | 읽기만 |
| `app/services/registry_service.py` | **허용** | 읽기만 | 읽기만 |
| `app/services/asset_service.py` | 금지 | **허용** | 읽기만 |
| `app/services/symbol_screener.py` | 금지 | 금지 | **허용** |
| `app/services/sector_rotator.py` | 금지 | 금지 | **허용** |
| `app/api/routes/registry.py` | **허용** | 읽기만 | 읽기만 |
| `workers/tasks/*` | 금지 | 금지 | **허용** |
| `app/services/runtime_*` | 금지 | 금지 | 금지 |
| `app/services/feature_cache.py` | 금지 | 금지 | 금지 |
| `exchanges/*` | 금지 | 금지 | 금지 |
| `tests/*` | **허용** | **허용** | **허용** |
| `docs/*` | **허용** | **허용** | **허용** |
| `alembic/*` | **허용** | **허용** | **허용** |

이 표가 각 Stage 승인 시점에 확정되면, EX류 사후 예외 없이 범위를 관리할 수 있습니다.

---

## Phase별 허용 범위표

| Phase | 허용 범위 | 비고 |
|-------|----------|------|
| Phase 1 서비스 | Gateway 검증 + Registry CRUD + write API | Stage 1 |
| Phase 2 서비스 | Asset Service 확장 + Symbol-Broker 검증 + TTL | Stage 2 |
| Phase 3A | SymbolScreener + SectorRotator + DataProvider + Celery task | Stage 3 |
| Phase 3B | KIS_US 어댑터 | **별도 판정** (외부 의존성) |
| Phase 4+ | Backtest/Paper/Promotion/Runtime | **별도 CR 또는 L4 판정** |

## Phase별 금지 범위표

| 금지 항목 | Stage 1 | Stage 2 | Stage 3 | 비고 |
|-----------|:-------:|:-------:|:-------:|------|
| Promotion 상태 전이 실행 | X | X | X | Phase 4 |
| RuntimeStrategyLoader | X | X | X | Phase 5 |
| Feature Cache | X | X | X | Phase 5 |
| KIS_US 어댑터 | X | X | X | Phase 3B 별도 |
| beat schedule 변경 | X | X | X | L4 |
| exchange_mode 변경 | X | X | X | L4 |
| blocked API 해제 | X | X | X | L4 |
| 실주문 경로 활성화 | X | X | X | L4 |

## 재진입 조건 / 중단 조건

| 조건 | 행동 |
|------|------|
| 회귀 실패 발생 | 해당 Stage 즉시 중단, 원인 분석 |
| 금지 범위 위반 발견 | 해당 Stage 중단, EX 리뷰 또는 revert |
| 설계-구현 불일치 발견 | 해당 Stage 중단, 설계 카드 재검토 |
| drift 감지 | 해당 Stage 중단, baseline-check 재실행 |
| A 중단 지시 | 즉시 중단 |

## 예외 승인 필요 지점

| 지점 | 예외 유형 | 사전/사후 |
|------|-----------|-----------|
| Stage N에서 Stage N+1 파일 변경 필요 | 범위 이탈 | **사전 승인 필수** |
| `app/services/runtime_*` 변경 필요 | 런타임 인접 | **사전 승인 필수** |
| 금지 목록 파일 변경 필요 | 정책 변경 | **A 직접 판정** |
| 테스트에서 서비스 import 발생 (mock 아닌 실호출) | 통합 테스트 경계 | **Stage 판정 시 포함 여부 결정** |

---

```
CR-048 Staged L3 Expansion Proposal v1.7
Document ID: GOV-L3-PROPOSAL-001
Date: 2026-04-03
Authority: A
Status: ACTIVE (Stage 1~4B SEALED, RI-1 SEALED, RI-2A-1 SEALED, RI-2A-2a SEALED, RI-2A-2b SEALED, RI-2B-1 SEALED, RI-2B-2a SEALED, RI-2B-2b DEFERRED)
Gate: LOCKED (유지 전제)
Stage 1: COMPLETED/SEALED (2026-04-04, 4709/4709 PASS)
Stage 2 (원본): REJECTED (2A/2B 분리 지시)
Stage 2A: COMPLETED/SEALED (2026-04-04, 4812/4812 PASS)
Stage 2B: COMPLETED/SEALED (2026-04-04, 4844/4844 PASS)
Stage 3 (원본): SPLIT (3A/3B 분리)
Stage 3A: COMPLETED/SEALED (2026-04-04, 4927/4927 PASS)
Stage 3B-1: COMPLETED/SEALED (2026-04-03, 5075/5075 PASS, 10 warnings pre-existing)
Stage 3B-2: COMPLETED/SEALED (2026-04-03, 5186/5186 PASS, 10 warnings pre-existing)
Stage 3B: COMPLETED/SEALED (전체 봉인)
Stage 4A (Pipeline Composition): COMPLETED/SEALED (2026-04-03, 62 tests, 5248/5248 clean)
Stage 4B (Pure Zone Registration): COMPLETED/SEALED (2026-04-03, 12 tests, 5260/5260 clean)
RI-1 (Pipeline Shadow Runner): COMPLETED/SEALED (2026-04-03, 39 tests, 5299/5299 clean)
RI-2A-1 (Shadow Read-through): COMPLETED/SEALED (2026-04-03, 31 tests, 5330/5330 clean)
RI-2A-2a (Shadow Observation Log): COMPLETED/SEALED (2026-04-04, 24 tests, 5354/5354 clean)
RI-2B-1 (Shadow Write Receipt): COMPLETED/SEALED (2026-04-04, 43 tests, 5397/5397 clean)
RI-2B-2a (Real Bounded Write Code/Contract): COMPLETED/SEALED (2026-04-04, 33 tests, 5430/5430 clean, EXECUTION_ENABLED=False)
RI-2A-2b (Shadow Observation Automation + Retention): COMPLETED/SEALED (2026-04-04, 26 tests, 5456/5456 clean, DRY_SCHEDULE=True, beat COMMENTED, purge NOT IMPLEMENTED)
RI-2B-2b (Execution Enable): DEFERRED
Pure Zone: 10 files, 117 purity tests
Baseline: v2.5
```
