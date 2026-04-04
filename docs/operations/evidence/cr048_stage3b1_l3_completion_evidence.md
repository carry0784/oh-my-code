# CR-048 Stage 3B-1 L3 Completion Evidence

**문서 ID:** EVIDENCE-STAGE3B1-001
**작성일:** 2026-04-03
**Authority:** A (Decision Authority)
**CR:** CR-048
**Stage:** Stage 3B-1 (Phase 3B Screening Pipeline — Contract Strengthening)
**판정:** SEALED
**회귀 기준선:** 5075/5075 PASS (10 warnings, all pre-existing)

---

## 1. Stage 3B-1 개요

### 범위

Stage 3A에서 생성된 Pure Zone 6개 파일에 대해 **계약 강화 전용** 확장:
- 새 enum, frozen dataclass, pure function 추가
- 기존 Stage 3A 계약 무변경
- Runtime 비접촉
- GREEN zone only (Pure Zone 내부)

### 선행 설계 문서 (6건, A ACCEPTED)

| 문서 | 용도 |
|------|------|
| `cr048_stage3b_boundary_inventory.md` | Pure Zone 지도, 4-tier 분류, 오염 패턴 |
| `cr048_stage3b_boundary_contract_spec.md` | PZ/CL/FR 규칙, T1-T7 허용, X1-X15 금지 |
| `cr048_stage3b_failure_mode_matrix.md` | F1-F9, stale/partial 정책, 보완 §8-§11 |
| `cr048_stage3b_dataprovider_capability_matrix.md` | 20-field ProviderCapability, namespace, 합성 규칙 |
| `cr048_stage3b_purity_guard_spec.md` | 32 forbidden 패턴, 6 대상 파일, ~70 테스트 |
| `cr048_stage3b_test_plan.md` | ~128 테스트, 회귀 보호, 봉인 조건 |

---

## 2. 변경 파일 목록

### 구현 파일 (2건 수정, 0건 신규)

| 파일 | 작업 | 유형 |
|------|------|:----:|
| `app/services/sector_rotator.py` | +RotationReasonCode enum, +SectorWeight.reason field, +_derive_reason() pure helper | 확장 |
| `app/services/data_provider.py` | +DataQualityDecision enum, +SymbolMetadata dataclass, +ProviderCapability dataclass (20 fields), +check_stale(), +check_partial(), +normalize_symbol(), +compute_listing_age(), +is_screening_capable(), +FailureModeRecovery enum, +FAILURE_MODE_RECOVERY dict, +STALE_LIMITS constants | 확장 |

### 테스트 파일 (3건 신규, 2건 확장)

| 파일 | 테스트 수 | 유형 |
|------|:---------:|:----:|
| `tests/test_purity_guard.py` | 67 | **신규** |
| `tests/test_failure_modes.py` | 39 | **신규** |
| `tests/test_provider_capability.py` | 25 | **신규** |
| `tests/test_sector_rotator.py` | +8 (총 48→56) | 확장 |
| `tests/test_data_provider.py` | +5 (총 35→40) | 확장 |

### 신규 테스트 합계: 148건 (67 + 39 + 25 + 8 + 5 + 기존 Stage 3A 4건 확인)

---

## 3. Stage 3B-1 특성

| Property | Value |
|----------|:-----:|
| Runtime Touch Points | **0** |
| Pure Logic Only | **YES** (both modified files) |
| External Connections | **0** |
| DB/Session Access | **0** |
| Network Access | **0** |
| Celery/beat | **NONE** |
| Side-effects | **0** |
| screen_and_update() | **FROZEN** |
| qualify_and_record() | **FROZEN** |
| asset_service.py | **UNTOUCHED** |
| RegimeDetector import | **NONE** (CR-046 compliant) |
| Async functions added | **0** |
| RED/AMBER file contact | **0** |
| Exceptions | **0** |

---

## 4. 핵심 계약 추가 사항

### 4.1 RotationReasonCode (sector_rotator.py)

- 7개 enum 값: overweight_regime_aligned, underweight_regime_opposed, neutral_default, neutral_unlisted, reduced_high_vol, reduced_crisis, unknown_regime
- **사용 제약 (Usage Constraint):**
  - RotationReasonCode는 **설명 전용(explanation-only)** 필드
  - weight 계산에 영향 주지 않음 (reason은 weight 결정 후 파생)
  - screening/qualification 판단에 사용 금지
  - 대시보드 표시 및 감사 추적 전용
- SectorWeight.reason = None 기본값으로 **하위 호환성 유지**

### 4.2 DataQualityDecision (data_provider.py)

- 9개 enum 값: ok, partial_usable, partial_reject, stale_usable, stale_reject, insufficient_bars, missing_listing_age, symbol_namespace_error, provider_unavailable
- **사용 제약 (Usage Constraint):**
  - DataQualityDecision은 **입력 데이터 품질 판정 전용**
  - Qualification 판단 (백테스트 적격성) 또는 Runtime 거래 결정에 사용 금지
  - ScreeningInput 생성 시 reject 여부 판단에만 사용
  - reject 결정은 **fail-closed** (reject = 진입 불가)

### 4.3 Failure Mode Policy (F1-F9)

| 모드 | Fail Policy | Recovery |
|------|:-----------:|:--------:|
| F1 (empty response) | fail-closed | recoverable |
| F2 (partial mandatory) | fail-closed | non_recoverable |
| F3 (partial optional) | partial_usable | recoverable |
| F4 (stale price) | fail-closed | recoverable |
| F5 (insufficient bars) | fail-closed | non_recoverable |
| F6 (missing listing age) | **documented exception** | recoverable |
| F7 (symbol namespace) | fail-closed | non_recoverable |
| F8 (provider timeout) | fail-closed | recoverable |
| F9 (provider degraded) | stale_usable | recoverable |

**F6 예외 사유:** listing_age_days는 SymbolMetadata로 별도 공급 경로 확보. Stage 1 multi-check + Stages 2-5 follow-up + FROZEN 경로 보호로 다층 방어.

### 4.4 Stale Policy (System Constants SP-01~SP-05)

- Provider는 사실(timestamp)만 공급, 시스템이 stale 여부 결정
- STALE_LIMITS: 7개 (asset_class, data_type) → timedelta 매핑
- 미지원 조합: fail-closed (STALE_REJECT)

### 4.5 ProviderCapability (20 fields)

- 모든 supports_* 기본값 = False (fail-closed 기본)
- is_screening_capable(): volume + atr + adx + available_bars 4개 필수
- frozenset 기반 supported_asset_classes

### 4.6 SymbolMetadata (Option B)

- Stage 3A 기존 계약 무수정
- listing_age_days 공급 경로: SymbolMetadata.listing_age_days + compute_listing_age() 순수 함수
- frozen dataclass, 필수 필드 2개 (symbol, market)

---

## 5. Purity Guard 검증

### 32 Forbidden Patterns (6개 Pure Zone 파일 전수 검증)

| 카테고리 | 패턴 수 | 검증 |
|----------|:-------:|:----:|
| P (forbidden imports) | 16 | PASS |
| A (async patterns) | 3 | PASS |
| S (side-effects) | 9 | PASS |
| R (runtime deps) | 4 | PASS |
| **합계** | **32** | **ALL PASS** |

### 대상 파일 (6건)

| 파일 | Purity PASS |
|------|:-----------:|
| sector_rotator.py | YES |
| data_provider.py | YES |
| symbol_screener.py | YES |
| backtest_qualification.py | YES |
| asset_validators.py | YES |
| constitution.py | YES |

---

## 6. 회귀 결과

| Metric | Value |
|--------|:-----:|
| Total tests | **5075** |
| Passed | **5075** |
| Failed | **0** |
| Warnings | **10** (all pre-existing) |
| Test duration | ~173s |

### Stage 3B-1 신규 테스트 (5개 파일, 231건 단독 실행)

```
tests/test_purity_guard.py        — 67 PASSED
tests/test_failure_modes.py       — 39 PASSED
tests/test_provider_capability.py — 25 PASSED
tests/test_sector_rotator.py      — 56 PASSED (48 기존 + 8 신규)
tests/test_data_provider.py       — 40 PASSED (35 기존 + 5 신규)
Total: 231 PASSED in 0.40s
```

---

## 7. Warnings 분류표

### 10건 전수 분류

| # | 소스 테스트 | 경고 위치 | 경고 유형 | 분류 |
|---|------------|-----------|-----------|------|
| 1 | test_asset_service_phase2b::TestRegisterSymbolBrokerValidation::test_allowed_broker_passes | asset_service.py:146 | RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited | **PRE-EXISTING** |
| 2 | test_asset_service_phase2b::TestRegisterSymbolBrokerValidation::test_us_stock_kis_us_passes | asset_service.py:146 | (동일) | **PRE-EXISTING** |
| 3 | test_asset_service_phase2b::TestRegisterSymbolBrokerValidation::test_excluded_sector_still_forces_excluded | asset_service.py:146 | (동일) | **PRE-EXISTING** |
| 4 | test_asset_service_phase2b::TestTransitionStatusWithAudit::test_core_to_watch_allowed | asset_service.py:251 | RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited | **PRE-EXISTING** |
| 5 | test_asset_service_phase2b::TestTransitionStatusWithAudit::test_excluded_to_watch_with_override_allowed | asset_service.py:251 | (동일) | **PRE-EXISTING** |
| 6 | test_asset_service_phase2b::TestTransitionStatusWithAudit::test_same_status_noop | asset_service.py:251 | (동일) | **PRE-EXISTING** |
| 7 | test_asset_service_phase2b::TestTransitionStatusWithAudit::test_audit_records_from_and_to_status | asset_service.py:251 | (동일) | **PRE-EXISTING** |
| 8 | test_asset_service_phase2b::TestProcessExpiredTTL::test_demotes_expired_core_to_watch | asset_service.py:251 | (동일) | **PRE-EXISTING** |
| 9 | test_asset_service_phase2b::TestProcessExpiredTTL::test_max_count_enforced | asset_service.py:251 | (동일) | **PRE-EXISTING** |
| 10 | test_asset_service_phase2b::TestRecordStatusAudit::test_audit_record_created | asset_service.py:251 | (동일) | **PRE-EXISTING** |

### 분류 결과

| 분류 | 건수 | 설명 |
|------|:----:|------|
| **PRE-EXISTING** (Stage 2B 기원) | **10** | AsyncMockMixin._execute_mock_call 미대기, Stage 2B async mock 패턴 |
| Stage 3B-1 신규 | **0** | 없음 |
| Stage 3B-1 관련 파일 | **0** | 없음 — 경고는 asset_service.py / test_asset_service_phase2b.py에서만 발생 |

### 판정

- 10건 전부 **Stage 2B SEALED 시점부터 존재**하는 AsyncMockMixin 패턴 경고
- Stage 3B-1은 asset_service.py를 **UNTOUCHED** — 경고 원인과 무관
- **관찰 항목(observation items)** 으로 분류, 봉인 차단 사유 아님

---

## 8. 예외 레지스터

| 항목 | 값 |
|------|-----|
| Stage 3B-1 신규 예외 | **0건** |
| RED/AMBER 파일 접촉 | **0건** |
| 범위 이탈 | **0건** |
| Stage 3A 계약 변경 | **0건** |
| FROZEN 함수 변경 | **0건** |

---

## 9. 봉인 상태

```
CR-048 Stage 3B-1 L3 Completion Evidence
Authority: A
Judgment: SEALED
Date: 2026-04-03
Regression: 5075/5075 PASS (10 warnings, pre-existing)
Gate: LOCKED
Stage 3B-1: COMPLETED/SEALED
Next Decision Point: Stage 3B-2 설계/스텁 패키지 제출 시점
```
