# Current Governance Baseline

> **Guarded Release ACTIVE · Gate LOCKED · Stage 1~4B L3 SEALED · RI-1 SEALED · RI-2A-1 SEALED · RI-2A-2a SEALED · RI-2A-2b SEALED · RI-2B-1 SEALED · RI-2B-2a SEALED · 5456/5456 PASS**

**Last Updated:** 2026-04-04
**Authority:** A
**Status:** Sealed (v2.5 — RI-2A-2b Shadow Observation Automation + Retention 완료, DRY_SCHEDULE=True, beat COMMENTED, purge NOT IMPLEMENTED)

---

## Operational Mode

| Item | Value |
|------|-------|
| operational_mode | **GUARDED_RELEASE** |
| exchange_mode | **DATA_ONLY** |
| Gate | **LOCKED** |

---

## Allowed Scope

| Level | Scope | Status |
|-------|-------|--------|
| L0 | Documents, design cards | **Allowed** |
| L1 | Tests (contract, unit, regression) | **Allowed** |
| L2 | Read-only API, observatory endpoints | **Allowed** |
| L3 | Model skeleton (4 models + Alembic) | **Allowed (Sealed)** |
| L3 | Stage 1: Gateway validation + Registry CRUD + Registry API | **Allowed (Sealed)** |
| L3 | Stage 2A: Asset validators + constitution constants + audit model + schema | **Allowed (Sealed)** |
| L3 | Stage 2B: Asset service broker guard + transition validator + audit recording + TTL manual | **Allowed (Sealed)** |
| L3 | Stage 3A: SectorRotator pure logic + DataProvider ABC/Protocol interface | **Allowed (Sealed)** |
| L3 | Stage 3B-1: Contract strengthening (enums, dataclasses, pure functions, purity guard) | **Allowed (Sealed)** |
| L3 | Stage 3B-2: Pure transform + provider stubs + golden set fixtures + tests | **Allowed (Sealed)** |
| L3 | Stage 4A: Screening qualification pipeline + qualification fixtures + purity guard 8th zone | **Allowed (Sealed)** |
| L3 | Stage 4B: universe_manager.py enrolled as 9th Pure Zone + purity guard tests | **Allowed (Sealed)** |
| L3 | RI-1: pipeline_shadow_runner.py read-only shadow + 10th Pure Zone + purity guard | **Allowed (Sealed)** |
| L3 | RI-2A-1: shadow_readthrough.py read-through comparison (SELECT only, DB write 0) | **Allowed (Sealed)** |
| L3 | RI-2A-2a: shadow_observation_log append-only INSERT (business write 0, manual trigger only) | **Allowed (Sealed)** |
| L3 | RI-2B-1: shadow_write_receipt append-only INSERT (dry_run=True, business write 0, receipt-only) | **Allowed (Sealed)** |
| L3 | RI-2B-2a: execute_bounded_write + rollback_bounded_write code/contract (EXECUTION_ENABLED=False, business write 불가) | **Allowed (Sealed)** |
| L3 | RI-2A-2b: shadow_observation_tasks dry-schedule + retention planner (DRY_SCHEDULE=True, beat COMMENTED, purge NOT IMPLEMENTED) | **Allowed (Sealed)** |

## Blocked Scope

| Level | Scope | Status |
|-------|-------|--------|
| L3 | Promotion state transition **execution** | **Blocked** |
| L3 | RuntimeStrategyLoader implementation | **Blocked** |
| L3 | Feature Cache implementation | **Blocked** |
| L3 | KIS_US adapter | **Blocked** |
| L3 | Asset Service extension (Stage 2B) | **Allowed (Sealed)** |
| L3 | SymbolScreener pipeline activation / SectorRotator runtime integration (Stage 3B-2+) | **Blocked** |
| L3 | Hard delete API | **Blocked** |
| L3 | Execute / Activate runtime / Broker connect | **Blocked** |
| L3 | Task dispatch / Beat registration | **Blocked** |
| L4 | beat schedule changes | **Blocked** |
| L4 | exchange_mode changes | **Blocked** |
| L4 | blocked API release | **Blocked** |
| L4 | live order path activation | **Blocked** |

---

## Prohibitions (7)

1. CR-049 Phase 3 implementation
2. SEALED PASS scope reopening
3. DATA_ONLY contract violation
4. ETH operational path (CR-046)
5. L3 changes without A approval
6. L4 changes without separate CR
7. Unauthorized Gate opening

---

## Sealed Deliverables

### Phase 0 — Constitution (L0, ACCEPTED)

| Document | Version |
|----------|---------|
| `injection_constitution.md` | v2.0 |
| `broker_matrix.md` | v2.0 |
| `exclusion_baseline.md` | v2.0 |

### Phase 1 — Design Cards (L0, ACCEPTED)

| Document | Version |
|----------|---------|
| `design_indicator_registry.md` | v1.0 |
| `design_feature_pack.md` | v1.0 |
| `design_strategy_registry.md` | v1.0 |
| `design_promotion_state.md` | v1.0 |

### Phase 2 — Design Card (L0, ACCEPTED)

| Document | Version |
|----------|---------|
| `design_asset_registry.md` | v1.0 |

### Phase 3A — Design Card (L0, ACCEPTED)

| Document | Version |
|----------|---------|
| `design_screening_engine.md` | v1.0 |

### Traceability (L0, ACCEPTED)

| Document | Version |
|----------|---------|
| `design_test_traceability.md` | v1.1 (34→58 items) |

### Contract Tests (L1, ACCEPTED)

| File | Tests |
|------|:-----:|
| `test_cr048_design_contracts.py` | 57 |
| `test_cr048_phase2_3a_contracts.py` | 30 |

### L3 Expansion Proposal (L0, ACCEPTED)

| Document | Version |
|----------|---------|
| `cr048_staged_l3_expansion_proposal.md` | v1.0 |

### Observatory API (L2, ACCEPTED)

| File | Endpoints | Tests |
|------|:---------:|:-----:|
| `cr048_observatory.py` | 5 GET | — |
| `test_cr048_observatory.py` | — | 48 |

### Model Skeletons (L3 Limited, SEALED)

| File | Changes |
|------|---------|
| `indicator_registry.py` | +IndicatorCategory enum, +category/asset_classes/timeframes |
| `feature_pack.py` | +description/asset_classes/timeframes/warmup_bars/champion_of |
| `strategy_registry.py` | +BACKTEST_FAIL, UPPERCASE enums |
| `promotion_state.py` | +evidence, +approved_by |
| `019_cr048_design_card_alignment.py` | Alembic: ADD COLUMN 10, CREATE INDEX 1 |
| `test_cr048_model_skeletons.py` | 44 tests |

### Stage 1 L3 — Control Plane Registry/Gateway (L3 Limited, SEALED)

| File | Work | Type |
|------|------|:----:|
| `injection_gateway.py` | 7-step validation (forbidden broker/sector, dependency, checksum, signature, market-matrix, FP status) | 확장 |
| `registry_service.py` | CRUD service (create/read/retire, no hard delete, no execute) | 신규 |
| `registry.py` | 16 endpoints (9 GET + 7 POST), RegistryService 경유 | 확장 |
| `registry_schema.py` | +PromotionEventResponse, RetireRequest, RegistryStatsResponse | 확장 |
| `test_injection_gateway_service.py` | Gateway 7-step + forbidden blocking (36 tests) | 신규 |
| `test_registry_service.py` | CRUD + append-only + no prohibited methods (28 tests) | 신규 |
| `test_registry_api.py` | API capability matrix + schema + error codes (22 tests) | 신규 |

#### Stage 1 API Capability Matrix

| Capability | Status |
|------------|:------:|
| Create (metadata) | **Allowed** |
| Read | **Allowed** |
| Soft Retire (DEPRECATED) | **Allowed** |
| Hard Delete | **Blocked** |
| Execute | **Blocked** |
| Promote (execution) | **Blocked** |
| Activate Runtime | **Blocked** |
| Task Dispatch | **Blocked** |
| Broker Connect | **Blocked** |

### Stage 2A L3 — Asset Static Layer (L3 Limited, SEALED)

| File | Work | Type |
|------|------|:----:|
| `asset_validators.py` | 7 pure functions (broker policy, status transition, TTL compute, sector, symbol data, constitution consistency) | 신규 |
| `asset.py` | +SymbolStatusAudit append-only model | 확장 |
| `constitution.py` | +BROKER_POLICY_RULES, +TTL_DEFAULTS, +TTL_MIN/MAX_HOURS, +STATUS_TRANSITION_RULES | 확장 |
| `asset_schema.py` | +6 response schemas (BrokerPolicy, StatusTransition, CandidateTTL, SymbolData, SymbolStatusAuditRead) | 확장 |
| `020_stage2a_asset_metadata.py` | CREATE TABLE symbol_status_audits (DDL only) | 신규 |
| `test_asset_validators.py` | 75 tests (broker/sector/transition/TTL/symbol/constitution) | 신규 |
| `test_asset_model_stage2a.py` | 28 tests (model/enum/schema/import safety) | 신규 |

#### Stage 2A Characteristics

| Property | Value |
|----------|:-----:|
| Runtime Reach | **ALL NO** |
| asset_service.py | **UNTOUCHED** |
| symbol_screener | **UNTOUCHED** |
| backtest_qualification | **UNTOUCHED** |
| DB DML | **0** |
| Exceptions | **0** |

### Stage 2B L3 — Asset Service Limited Extension (L3 Limited, SEALED)

| File | Work | Type |
|------|------|:----:|
| `asset_service.py` | +broker guard in register_symbol, +validator in transition_status, +audit recording, +process_expired_ttl(max_count=10) | 수정 |
| `test_asset_service_phase2b.py` | 32 tests (broker/transition/TTL/audit/frozen/fail-closed) | 신규 |
| `test_asset_registry.py` | assertion regex 정렬 3건 + 테스트명 1건 | 정렬 |

#### Stage 2B Characteristics

| Property | Value |
|----------|:-----:|
| Runtime Touch Points | **5** (all fail-closed) |
| screen_and_update() | **FROZEN** |
| qualify_and_record() | **FROZEN** |
| symbol_screener import | **UNCHANGED** |
| backtest_qualification import | **UNCHANGED** |
| TTL execution | **Manual only, max 10** |
| Celery/beat | **NONE** |
| Active read path impact | **1** (list_core_symbols) |
| Exceptions | **0** |

### Stage 3A L3 — Screening Pure Logic + Interface (L3 Limited, SEALED)

| File | Work | Type |
|------|------|:----:|
| `sector_rotator.py` | SectorRotator — regime→sector weight 순수 계산 (6 regime, 12 sector) | 신규 |
| `data_provider.py` | DataProvider — 4 ABC (MarketData, Fundamental, Backtest, Composite) + 4 data contracts | 신규 |
| `test_sector_rotator.py` | 48 tests (weight/rotation/score/design contract/purity proof) | 신규 |
| `test_data_provider.py` | 35 tests (quality/contracts/ABC/method/purity proof) | 신규 |

#### Stage 3A Characteristics

| Property | Value |
|----------|:-----:|
| Runtime Touch Points | **0** |
| Pure Logic | **YES** (both files) |
| External Connections | **0** |
| DB/Session Access | **0** |
| Network Access | **0** |
| Celery/beat | **NONE** |
| Side-effects | **0** |
| screen_and_update() | **FROZEN** |
| qualify_and_record() | **FROZEN** |
| asset_service.py | **UNTOUCHED** |
| RegimeDetector import | **NONE** (CR-046 compliant) |
| Exceptions | **0** |

### Stage 3B-1 L3 — Contract Strengthening (L3 Limited, SEALED)

| File | Work | Type |
|------|------|:----:|
| `sector_rotator.py` | +RotationReasonCode enum (7 values), +SectorWeight.reason field, +_derive_reason() pure helper | 확장 |
| `data_provider.py` | +DataQualityDecision enum (9 values), +SymbolMetadata dataclass, +ProviderCapability dataclass (20 fields), +check_stale/check_partial/normalize_symbol/compute_listing_age/is_screening_capable pure functions, +FailureModeRecovery enum, +STALE_LIMITS constants | 확장 |
| `test_purity_guard.py` | 67 tests (32 forbidden patterns × 6 Pure Zone files) | 신규 |
| `test_failure_modes.py` | 39 tests (F1-F9, stale/partial/namespace/recovery) | 신규 |
| `test_provider_capability.py` | 25 tests (capability/screening/metadata/listing_age) | 신규 |
| `test_sector_rotator.py` | +8 tests (RotationReasonCode + backward compat) | 확장 |
| `test_data_provider.py` | +5 tests (ProviderCapability + SymbolMetadata purity) | 확장 |

#### Stage 3B-1 Characteristics

| Property | Value |
|----------|:-----:|
| Runtime Touch Points | **0** |
| Pure Logic Only | **YES** |
| External Connections | **0** |
| DB/Session Access | **0** |
| Network Access | **0** |
| Celery/beat | **NONE** |
| Side-effects | **0** |
| screen_and_update() | **FROZEN** |
| qualify_and_record() | **FROZEN** |
| asset_service.py | **UNTOUCHED** |
| RegimeDetector import | **NONE** (CR-046 compliant) |
| RED/AMBER file contact | **0** |
| Async functions added | **0** |
| Exceptions | **0** |

#### Stage 3B-1 Usage Constraints

| Constraint | Description |
|------------|-------------|
| RotationReasonCode | **Explanation-only** — weight 계산에 영향 금지, screening/qualification 판단에 사용 금지 |
| DataQualityDecision | **Input quality judgment only** — qualification/runtime trade 판단에 사용 금지 |
| F6 (missing_listing_age) | Documented exception — fail-open, 다층 방어 조건 하에서만 허용 |

### Stage 3B-2 L3 — Pure Transform + Provider Stubs (L3 Limited, SEALED)

| File | Work | Type |
|------|------|:----:|
| `screening_transform.py` | L1 pure transform: validate→build pipeline, ScreeningInputSource, TransformResult | 신규 |
| `tests/fixtures/screening_fixtures.py` | Golden set: 4 normal + 9 failure + 4 edge + 6 capability | 신규 |
| `tests/stubs/screening_stubs.py` | L2 sync stubs: StubMarket/Backtest/Fundamental/ScreeningDataProvider | 신규 |
| `test_screening_transform.py` | 65 tests (validate/build/pipeline/source/result/F1-F9) | 신규 |
| `test_screening_stubs.py` | 34 tests (stub behavior + SB purity + capability profiles) | 신규 |
| `test_purity_guard.py` | +12 tests (7th Pure Zone: screening_transform.py) | 확장 |

#### Stage 3B-2 Characteristics

| Property | Value |
|----------|:-----:|
| Runtime Touch Points | **0** |
| Pure Logic Only | **YES** |
| External Connections | **0** |
| DB/Session Access | **0** |
| Network Access | **0** |
| Celery/beat | **NONE** |
| Side-effects | **0** |
| screen_and_update() | **FROZEN** |
| qualify_and_record() | **FROZEN** |
| asset_service.py | **UNTOUCHED** |
| RegimeDetector import | **NONE** |
| RED/AMBER file contact | **0** |
| Exceptions | **0** |

#### Stage 3B-2 Usage Constraints

| Constraint | Description |
|------------|-------------|
| `screening_transform.py` | **Pure transform 전용** — provider-specific branch 3초과 시 분할 |
| `tests/stubs/screening_stubs.py` | **테스트 전용** — app/ 계층 import 금지, real proxy 전환 금지 |
| validate→build | **Fail-closed invariant** — reject 시 ScreeningInput 생성 차단 불변 |
| Stub / Fixture / Golden set | **Runtime/service 계층 역류 금지** |

### Stage 4A L3 — Screening Qualification Pipeline (L3 Limited, SEALED)

| File | Work | Type |
|------|------|:----:|
| `app/services/screening_qualification_pipeline.py` | Pure Zone #8: static composition pipe, fail-closed 5+1 point chain | 신규 |
| `tests/fixtures/qualification_fixtures.py` | 7 BacktestReadiness fixtures (golden set) | 신규 |
| `test_screening_qualification_pipeline.py` | 50 tests (12 classes) | 신규 |
| `test_purity_guard.py` | +12 tests (8th Pure Zone: screening_qualification_pipeline.py) | 확장 |

#### Stage 4A Characteristics

| Property | Value |
|----------|:-----:|
| Runtime Touch Points | **0** |
| Pure Logic Only | **YES** |
| External Connections | **0** |
| DB/Session Access | **0** |
| Network Access | **0** |
| Celery/beat | **NONE** |
| Side-effects | **0** |
| Composition style | **Static composition pipe** |
| Qualification chain | **Fail-closed 5+1 point chain** |
| Mapping | **Deterministic** |
| Dataclasses | **Frozen** |
| screen_and_update() | **FROZEN** |
| qualify_and_record() | **FROZEN** |
| asset_service.py | **UNTOUCHED** |
| RegimeDetector import | **NONE** |
| RED/AMBER file contact | **0** |
| Async functions added | **0** |
| Exceptions | **0** |

#### Stage 4A Usage Constraints

| Constraint | Description |
|------------|-------------|
| `screening_qualification_pipeline.py` | **Pure import/call only** — DB/async/network 접근 금지, orchestration 금지 |
| `tests/fixtures/qualification_fixtures.py` | **테스트 전용** — service/runtime 계층 역류 금지 |
| Fail-closed chain | **5+1 point chain 불변** — 중간 단계 우회 금지 |

### Stage 4B L3 — Pure Zone Registration (L3 Limited, SEALED)

| File | Work | Type |
|------|------|:----:|
| `test_purity_guard.py` | +12 tests (9th Pure Zone: universe_manager.py) | 확장 |
| `universe_manager.py` | **무수정** (0줄 변경) | — |

#### Stage 4B Characteristics

| Property | Value |
|----------|:-----:|
| Runtime Touch Points | **0** |
| Production code changes | **0** |
| Pure Zone files | **9** (8 → 9) |
| Purity guard tests | **105** (93 → 105) |
| New tests | **12** |
| FROZEN/RED file contact | **0** |
| Exceptions | **0** |
| New warnings | **0** |

#### Stage 4B Usage Constraints

| Constraint | Description |
|------------|-------------|
| `universe_manager.py` | **Pure Zone 등록 전용** — 운영 코드 0줄 변경, purity guard 테스트만 추가 |
| Extraction scope | **REJECTED** — 원래 Extraction 범위는 기각됨, Pure Zone Registration Only |

### RI-1 L3 — Pipeline Shadow Runner (L3 Limited, SEALED)

| File | Work | Type |
|------|------|:----:|
| `app/services/pipeline_shadow_runner.py` | Pure Zone #10: read-only shadow pipeline (transform→screen→qualify), comparison logic | 신규 |
| `tests/test_pipeline_shadow_runner.py` | 27 tests (7 classes: result/normal/reject/fail-closed/comparison/purity/evidence) | 신규 |
| `tests/test_purity_guard.py` | +12 tests (10th Pure Zone: pipeline_shadow_runner.py) | 확장 |

#### RI-1 Characteristics

| Property | Value |
|----------|:-----:|
| Runtime Touch Points | **0** |
| Production code changes | **0** |
| Pure Zone files | **10** (9 → 10) |
| Purity guard tests | **117** (105 → 117) |
| New tests | **39** (27 + 12) |
| DB write | **0** |
| State transition | **0** |
| FROZEN function call | **0** |
| FROZEN/RED file contact | **0** |
| asset_service import | **0** |
| Async functions added | **0** |
| Exceptions | **0** |
| New warnings | **0** |

#### RI-1 Usage Constraints

| Constraint | Description |
|------------|-------------|
| `pipeline_shadow_runner.py` | **Read-only shadow 전용** — DB write 금지, state transition 금지, runtime path 삽입 금지 |
| `compare_shadow_to_existing()` | **비교만 허용** — fetch 금지, DB 조회 금지, side-effect 금지 |
| RI-1 → RI-2 경계 | RI-1은 관찰 계층, RI-2는 bounded write — RI-2 진입 시 별도 범위 심사 필수 |
| 재개방 조건 | A 승인 필수, 별도 CR 또는 RI-2 범위 심사 통과 |

### RI-2A-1 L3 — Shadow Read-through Comparison (L3 Limited, SEALED)

| File | Work | Type |
|------|------|:----:|
| `app/services/pipeline_shadow_runner.py` | +INSUFFICIENT 2종 분리 (STRUCTURAL/OPERATIONAL), +ReasonComparisonDetail, +reason-level comparison | 확장 |
| `app/services/shadow_readthrough.py` | DB read-through: fetch_existing_for_comparison + run_readthrough_comparison | 신규 |
| `tests/test_pipeline_shadow_runner.py` | +10 tests (TestInsufficientSplit 4 + TestReasonLevelComparison 6) | 확장 |
| `tests/test_shadow_readthrough.py` | 21 tests (6 classes: extract/fetch/comparison/no-write) | 신규 |
| `scripts/ri1_shadow_observation.py` | INSUFFICIENT enum 참조 갱신 | 정렬 |
| `scripts/ri1a_threshold_alignment_remeasurement.py` | INSUFFICIENT enum 참조 갱신 | 정렬 |

#### RI-2A-1 Characteristics

| Property | Value |
|----------|:-----:|
| DB write | **0** |
| DB read | **2 SELECT** (bounded LIMIT 1) |
| Read targets | screening_results, qualification_results |
| State transition | **0** |
| New tables / migration | **0** |
| Celery/beat | **NONE** |
| FROZEN file contact | **0** |
| RED file contact | **0** |
| New tests | **31** (21 + 10) |
| Exceptions | **0** |
| New warnings | **0** |

#### RI-2A-1 Usage Constraints

| Constraint | Description |
|------------|-------------|
| `shadow_readthrough.py` | **Read-through only** — DB write 금지, 신규 테이블/마이그레이션 금지 |
| reason-level comparison | **비교용 전용** — 운영 반영 근거로 사용 금지 |
| ComparisonVerdict | **관찰 지표** — 자동 승격/차단 판단 근거 아님 |
| bounded query 계약 | read-through 쿼리는 LIMIT 1 bounded 고정 — 무제한 조회 금지 |
| RI-2A-1은 **무상태 비교 계층** | 운영 반영 계층 아님, RI-2A-2 진입은 별도 A 범위 심사 필수 |

### RI-2A-2a L3 — Shadow Observation Log (L3 Limited, SEALED)

| File | Work | Type |
|------|------|:----:|
| `app/models/shadow_observation.py` | ShadowObservationLog ORM (15 fields, FK 0, UNIQUE 0, 3 indexes) | 신규 |
| `app/services/shadow_observation_service.py` | record_shadow_observation() — INSERT only, failure → None | 신규 |
| `alembic/versions/021_shadow_observation_log.py` | CREATE TABLE shadow_observation_log + 3 indexes | 신규 |
| `tests/test_shadow_observation.py` | 24 tests (7 classes: model/record/append-only/failure/validation/duplicate/serialization) | 신규 |
| `app/models/__init__.py` | +ShadowObservationLog import | 수정 |

#### RI-2A-2a Characteristics

| Property | Value |
|----------|:-----:|
| DB write | **INSERT only** (shadow_observation_log) |
| Business table write | **0** |
| State transition | **0** |
| New tables | **1** (shadow_observation_log) |
| Celery/beat | **NONE** |
| Trigger method | **Manual only** |
| FROZEN file contact | **0** |
| RED file contact | **0** |
| New tests | **24** |
| Exceptions | **0** |
| New warnings | **0** |

#### RI-2A-2a Usage Constraints

| Constraint | Description |
|------------|-------------|
| `shadow_observation_service.py` | **Append-only INSERT 전용** — UPDATE/DELETE 영구 금지 |
| business_impact | **false** — observation log는 business decision source 아님 |
| observation 결과 | **운영 반영 금지** — 자동 승격/차단/promotion 판단 근거 아님 |
| beat / 자동 실행 | **금지** — manual trigger only (pytest / script) |
| 원본 row | **수정/삭제 금지** — dedup은 쿼리 시점에만 적용 |
| Dedupe key | `(symbol, input_fingerprint, shadow_timestamp)` — 집계용 |
| Retention/purge | **RI-2A-2b 범위** — RI-2A-2a에서 구현 금지 |
| RI-2A-2b 진입 | **별도 A 범위 심사 필수** |

### Totals

| Category | Count |
|----------|:-----:|
| Design documents | 10 (Phase 0: 3, Phase 1: 4, Phase 2: 1, Phase 3A: 1, Traceability: 1) |
| Governance documents | 4 (L3 expansion proposal, Stage 1 scope request, Stage 2A scope request, Stage 2B scope request) |
| New tests | 986 (57 + 48 + 44 + 30 + 86 + 103 + 32 + 83 + 148 + 111 + 62 + 12 + 39 + 31 + 24 + 43 + 33) |
| Observatory endpoints | 5 GET |
| Registry endpoints | 16 (9 GET + 7 POST) |
| Model files modified | 5 (4 Phase 1 + asset.py Stage 2A) |
| Service files | 12 (injection_gateway.py, registry_service.py, asset_validators.py, asset_service.py, sector_rotator.py, data_provider.py, screening_transform.py, screening_qualification_pipeline.py, pipeline_shadow_runner.py, shadow_readthrough.py, shadow_observation_service.py, shadow_write_service.py) |
| Purity guard files | 1 (test_purity_guard.py — 32 patterns × 10 files) |
| Purity guard tests | 117 (105 + 12 new) |
| Stub files | 1 (tests/stubs/screening_stubs.py — 4 sync providers) |
| Fixture files | 2 (tests/fixtures/screening_fixtures.py — 20 golden set, tests/fixtures/qualification_fixtures.py — 7 BacktestReadiness) |
| Test files | 191 |
| Alembic migrations | 4 (019 + 020 + 021 + 022) |

---

## Regression Baseline

| Metric | Value |
|--------|:-----:|
| Total tests | **5430** |
| Passed | **5430** |
| Failed | **0** |
| Warnings | **10** (pre-existing, Stage 2B AsyncMockMixin) |
| Test files | 195 |

---

## Exception Register

| ID | File | Decision | Status |
|----|------|----------|--------|
| EX-001 | `app/api/routes/ops.py` | APPROVED (retroactive) | **Closed** |
| EX-002 | `app/services/runtime_strategy_loader.py` | APPROVED (retroactive) | **Closed** |

**EX-003 불필요:** Stage 1 배치에서 `test_injection_gateway.py` 1건 assertion 수정은 7단계 순서 반영에 따른 L1 호환 정렬로, 별도 예외 불요 (A 판정).

**Stage 2A 예외:** 0건 발생. 신규 예외 추가 없음.

**Stage 2B 예외:** 0건 발생. `test_asset_registry.py` assertion 정렬 3건은 호환성 L1 정렬로 별도 예외 불요 (A 판정).

**Stage 3A 예외:** 0건 발생. 신규 예외 추가 없음. RED/AMBER 파일 접촉 0건.

**Stage 3B-1 예외:** 0건 발생. 신규 예외 추가 없음. RED/AMBER 파일 접촉 0건. 10 warnings 전부 Stage 2B 기원 (PRE-EXISTING, 관찰 항목).

**Stage 3B-2 예외:** 0건 발생. 신규 예외 추가 없음. RED/AMBER 파일 접촉 0건. 신규 경고 0건. OBS-001 유지 (10건, PRE-EXISTING).

**Stage 4A 예외:** 0건 발생. 신규 예외 추가 없음. RED/AMBER 파일 접촉 0건. 신규 경고 0건. OBS-001 유지 (10건, PRE-EXISTING).

**Stage 4B 예외:** 0건 발생. 신규 예외 추가 없음. RED/AMBER 파일 접촉 0건. 신규 경고 0건. OBS-001 유지 (10건, PRE-EXISTING). Clean run 5260/5260.

**RI-1 예외:** 0건 발생. 신규 경고 0건. OBS-001 유지 (10건, PRE-EXISTING). Clean run 5299/5299. FROZEN/RED 접촉 0건.

**RI-2A-1 예외:** 0건 발생. 신규 경고 0건. OBS-001 유지 (10건, PRE-EXISTING). Clean run 5330/5330. FROZEN/RED 접촉 0건. DB write 0. read-through SELECT only (2 tables, LIMIT 1 bounded).

**RI-2A-2a 예외:** 0건 발생. 신규 경고 0건. OBS-001 유지 (10건, PRE-EXISTING). Clean run 5354/5354. FROZEN/RED 접촉 0건. DB write = INSERT only (shadow_observation_log). business table write 0. manual trigger only.

**RI-2B-1 예외:** 0건 발생. 신규 경고 0건. OBS-001 유지 (10건, PRE-EXISTING). Clean run 5397/5397. FROZEN/RED 접촉 0건. DB write = INSERT only (shadow_write_receipt). business table write 0. dry_run=True forced. receipt-only.

**RI-2B-2a 예외:** 0건 발생. 신규 경고 0건. OBS-001 유지 (10건, PRE-EXISTING). Clean run 5430/5430. FROZEN/RED 접촉 0건. EXECUTION_ENABLED=False. business table write 불가. 기존 코드 수정 0줄. 모델/마이그레이션 변경 0.

**RI-2A-2b 예외:** 0건 발생. 신규 경고 0건. OBS-001 유지 (10건, PRE-EXISTING). Clean run 5456/5456. FROZEN/RED 접촉 0건. SEALED 서비스 수정 0줄. DRY_SCHEDULE=True 하드코딩. beat COMMENTED. purge NOT IMPLEMENTED. 초기 bind=True 실패 → 수정 후 4회 연속 PASS (superseded).

Full register: `docs/operations/evidence/exception_register.md`

---

## Governance Rules

| Rule | Description |
|------|-------------|
| GR-RULE-01 | Cascade change level analysis required |
| GR-RULE-02 | A approval required for L2+ changes |
| GR-RULE-03 | Classification table-based judgment |
| BL-EXMODE01 | exchange_mode lock |
| BL-OPS-RESTART01 | Operational restart protocol |

---

## Re-entry Conditions (4)

| Condition | Trigger |
|-----------|---------|
| drift | Baseline 6-item drift detected |
| regression | Test failure count > 0 |
| forbidden | Prohibited scope violation |
| write_path | Unauthorized write path detected |

---

## Evidence Documents

| Document | Location |
|----------|----------|
| Guarded Release exit evaluation | `evidence/guarded_release_exit_evaluation_2026-04-04.md` |
| L3 model skeleton evidence | `evidence/cr048_limited_l3_model_skeleton_evidence.md` |
| EX-001 exception note | `evidence/guarded_release_l2_exception_note_2026-04-04.md` |
| EX-002 exception report | `evidence/EX-002_runtime_strategy_loader_casing.md` |
| Exception register | `evidence/exception_register.md` |
| Phase 2+3A 설계 카드 | `docs/architecture/design_asset_registry.md`, `design_screening_engine.md` |
| L3 확장 제안서 | `evidence/cr048_staged_l3_expansion_proposal.md` |
| Stage 1 범위 요청서 | `evidence/cr048_stage1_l3_scope_request.md` |
| **Stage 1 완료 증빙** | **`evidence/cr048_stage1_l3_completion_evidence.md`** |
| Stage 2 범위 요청서 (원본, 반려) | `evidence/cr048_stage2_l3_scope_request.md` |
| Stage 2A 범위 요청서 | `evidence/cr048_stage2a_l3_scope_request.md` |
| Stage 2B 범위 요청서 | `evidence/cr048_stage2b_l3_scope_request.md` |
| Stage 2B 심사 패키지 | `evidence/cr048_stage2b_review_package.md` |
| Stage 2A→2B 경계 분석 | `evidence/cr048_stage2a_2b_boundary_delta.md` |
| **Stage 2A 완료 증빙** | **`evidence/cr048_stage2a_l3_completion_evidence.md`** |
| **Stage 2B 완료 증빙** | **`evidence/cr048_stage2b_l3_completion_evidence.md`** |
| Stage 3 범위 요청서 | `evidence/cr048_stage3_l3_scope_request.md` |
| Stage 2B→3 Runtime Delta | `evidence/cr048_stage2b_to_stage3_runtime_delta.md` |
| **Stage 3A 완료 증빙** | **`evidence/cr048_stage3a_l3_completion_evidence.md`** |
| Stage 3B-1 설계 문서 (6건) | `evidence/cr048_stage3b_boundary_*.md`, `cr048_stage3b_failure_mode_matrix.md`, `cr048_stage3b_dataprovider_capability_matrix.md`, `cr048_stage3b_purity_guard_spec.md`, `cr048_stage3b_test_plan.md` |
| **Stage 3B-1 완료 증빙** | **`evidence/cr048_stage3b1_l3_completion_evidence.md`** |
| Stage 3B-2 설계 문서 (6건) | `evidence/cr048_stage3b2_stub_scope_review.md`, `cr048_stage3b2_stub_contract.md`, `cr048_stage3b2_screening_input_transform_spec.md`, `cr048_stage3b2_symbol_namespace_contract.md`, `cr048_stage3b2_fixture_strategy.md`, `cr048_stage3b2_test_plan.md` |
| **Stage 3B-2 완료 증빙** | **`evidence/cr048_stage3b2_l3_completion_evidence.md`** |
| Stage 4B 범위 심사 | `evidence/cr048_stage4b_scope_review_package.md` |
| Runtime Integration 범위 심사 | `evidence/cr048_runtime_integration_scope_review_package.md` |
| RI-1 설계/계약 | `evidence/cr048_ri1_shadow_design_contract_package.md` |
| **RI-1 완료 증빙** | **`evidence/cr048_ri1_completion_evidence.md`** |
| RI-1A Threshold Alignment | `evidence/cr048_ri1a_threshold_alignment_remeasurement_package.md` |
| RI-2A Scope Review | `evidence/cr048_ri2a_scope_review_package.md` |
| RI-2A-1 Design/Contract | `evidence/cr048_ri2a1_readthrough_design_contract_package.md` |
| RI-2A-1 구현 완료 보고 | `evidence/cr048_ri2a1_implementation_completion_report.md` |
| **RI-2A-1 봉인 증빙** | **`evidence/cr048_ri2a1_completion_evidence.md`** |
| RI-2A-2 범위 심사 | `evidence/cr048_ri2a2_scope_review_package.md` |
| RI-2A-2a 설계/계약 | `evidence/cr048_ri2a2a_observation_log_design_contract_package.md` |
| RI-2A-2a 구현 완료 보고 | `evidence/cr048_ri2a2a_implementation_completion_report.md` |
| **RI-2A-2a 봉인 증빙** | **`evidence/cr048_ri2a2a_completion_evidence.md`** |

---

## Next Decision Points

1. **RI-2A-2b 봉인 완료. 다음: RI-2B-2b Scope Review (실행 활성화, DEFERRED)** ← 다음 판정 지점
2. Drift / regression anomaly
3. Guarded Release termination or Gate policy review

---

```
Current Governance Baseline v2.5
Authority: A
Sealed: 2026-04-04
Regression: 5456/5456 PASS (10 warnings, pre-existing)
Gate: LOCKED
Stage 1 L3: COMPLETED/SEALED
Stage 2A L3: COMPLETED/SEALED
Stage 2B L3: COMPLETED/SEALED
Stage 3A L3: COMPLETED/SEALED
Stage 3B-1 L3: COMPLETED/SEALED
Stage 3B-2 L3: COMPLETED/SEALED
Stage 3B L3: COMPLETED/SEALED
Stage 4A L3: COMPLETED/SEALED
Stage 4B L3: COMPLETED/SEALED
RI-1 L3: COMPLETED/SEALED
RI-2A-1 L3: COMPLETED/SEALED
RI-2A-2a L3: COMPLETED/SEALED
RI-2A-2b L3: COMPLETED/SEALED (DRY_SCHEDULE=True, beat COMMENTED, purge NOT IMPLEMENTED)
RI-2B-1 L3: COMPLETED/SEALED
RI-2B-2a L3: COMPLETED/SEALED (EXECUTION_ENABLED=False)
Pure Zone: 10 files
Purity Guard: 117 tests
Phase 2+3A Design Baseline: FIXED
RI-2B-2b: DEFERRED (execution_enabled=False→True 전환은 별도 A 승인 필요)
RI-2B-2a SEALED는 execution_enabled 값 변경·운영 실행·rollback 실행 권한을 의미하지 않는다.
RI-2A-2b SEALED는 beat uncomment·DRY_SCHEDULE False 전환·retention purge 실행 권한을 의미하지 않는다.
```
