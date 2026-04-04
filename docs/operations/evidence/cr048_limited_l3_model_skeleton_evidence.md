# CR-048 Limited L3 Model Skeleton Evidence

**Date:** 2026-04-04
**Authority:** A (APPROVED LIMITED L3 REVIEW GO)
**Scope:** Model skeleton 4 + Alembic migration 1 + Model unit tests
**Gate Status:** LOCKED (maintained)
**Final Status:** **ACCEPTED** (EX-002 사후 예외 승인으로 CONDITIONAL→FINAL ACCEPTED 승격, 2026-04-04)

---

## 1. File List (changed/created)

### Models (modified — skeleton columns only, no service logic)

| File | Action | Changes |
|------|--------|---------|
| `app/models/indicator_registry.py` | **MODIFIED** | +IndicatorCategory enum (5 values), +category/asset_classes/timeframes columns, IndicatorStatus values→UPPERCASE |
| `app/models/feature_pack.py` | **MODIFIED** | +description/asset_classes/timeframes/warmup_bars/champion_of columns, FeaturePackStatus values→UPPERCASE |
| `app/models/strategy_registry.py` | **MODIFIED** | +BACKTEST_FAIL state (10 total), AssetClass/PromotionStatus values→UPPERCASE, status Mapped[str] |
| `app/models/promotion_state.py` | **MODIFIED** | +evidence (Text, nullable), +approved_by (String(100), nullable) |

### Migration (new)

| File | Action | Changes |
|------|--------|---------|
| `alembic/versions/019_cr048_design_card_alignment.py` | **NEW** | ADD COLUMN: indicators(3), feature_packs(5), promotion_events(2). No table creation. |

### Tests (new)

| File | Action | Tests |
|------|--------|:-----:|
| `tests/test_cr048_model_skeletons.py` | **NEW** | 44 |

### Tests (modified — enum casing alignment)

| File | Action | Changes |
|------|--------|---------|
| `tests/test_registry.py` | **MODIFIED** | Enum assertions updated lowercase→UPPERCASE, PromotionStatus 9→10 states |
| `tests/test_asset_registry.py` | **MODIFIED** | AssetClass assertions updated lowercase→UPPERCASE |
| `tests/test_runtime_loader.py` | **MODIFIED** | strategy_status strings updated lowercase→UPPERCASE (37 occurrences), LOADABLE_STRATEGY_STATUSES test updated |
| `tests/test_universe_runner.py` | **MODIFIED** | Strategy status mock values updated lowercase→UPPERCASE |

### Runtime (modified — casing alignment)

| File | Action | Changes |
|------|--------|---------|
| `app/services/runtime_strategy_loader.py` | **MODIFIED** | LOADABLE_STRATEGY_STATUSES values→UPPERCASE |

---

## 2. Field / Relation / Constraint Summary

### New Columns

| Table | Column | Type | Nullable | Default | Purpose |
|-------|--------|------|:--------:|---------|---------|
| indicators | category | String(30) | Yes | — | CR-048 indicator category (5 values) |
| indicators | asset_classes | Text | Yes | — | JSON array of applicable asset classes |
| indicators | timeframes | Text | Yes | — | JSON array of applicable timeframes |
| feature_packs | description | Text | Yes | — | Human-readable description |
| feature_packs | asset_classes | Text | Yes | — | JSON array of applicable asset classes |
| feature_packs | timeframes | Text | Yes | — | JSON array of applicable timeframes |
| feature_packs | warmup_bars | Integer | No | 0 | Max warmup bars from indicators |
| feature_packs | champion_of | String(36) | Yes | — | Strategy ID for Champion/Challenger |
| promotion_events | evidence | Text | Yes | — | JSON evidence (backtest/paper results) |
| promotion_events | approved_by | String(100) | Yes | — | Approver identity |

### New Enum Values

| Enum | Added | Full Set |
|------|-------|----------|
| PromotionStatus | BACKTEST_FAIL | 10 states: DRAFT, REGISTERED, BACKTEST_PASS, BACKTEST_FAIL, PAPER_PASS, QUARANTINE, GUARDED_LIVE, LIVE, RETIRED, BLOCKED |
| IndicatorCategory | (new enum) | MOMENTUM, TREND, VOLATILITY, VOLUME, OSCILLATOR |

### Enum Casing Normalization (lowercase→UPPERCASE)

| Enum | Before | After |
|------|--------|-------|
| IndicatorStatus | active, deprecated, blocked | ACTIVE, DEPRECATED, BLOCKED |
| FeaturePackStatus | active, challenger, deprecated, blocked | ACTIVE, CHALLENGER, DEPRECATED, BLOCKED |
| PromotionStatus | draft, registered, ... | DRAFT, REGISTERED, ... |
| AssetClass | crypto, us_stock, kr_stock | CRYPTO, US_STOCK, KR_STOCK |

### New Index

| Table | Index | Column |
|-------|-------|--------|
| indicators | ix_indicators_category | category |

### Relations

No new FK constraints added (skeleton only). `champion_of` and `feature_pack_id` remain soft references (String(36)).

---

## 3. Alembic Migration Scope

**File:** `019_cr048_design_card_alignment.py`
**Revision:** `019_cr048_design_card` → revises `018_enum_contract_unification`

| Operation | Count |
|-----------|:-----:|
| ADD COLUMN | 10 |
| CREATE INDEX | 1 |
| CREATE TABLE | **0** |
| ALTER TABLE | **0** |
| DROP | **0** |

**Note:** Enum value case migration (lowercase→UPPERCASE) is ORM-level only. Existing DB rows retain lowercase values. New rows will use UPPERCASE. A future data-migration can normalize if needed.

---

## 4. Prohibition Non-Violation Confirmation

| Prohibition | Status | Evidence |
|-------------|:------:|---------|
| Injection Gateway 실행 로직 | **NOT TOUCHED** | No changes to `app/services/injection_gateway.py` |
| Promotion 상태 전이 실행 로직 | **NOT TOUCHED** | No transition logic added |
| RuntimeStrategyLoader 구현 | **CASING ONLY** | Only `LOADABLE_STRATEGY_STATUSES` values updated lowercase→UPPERCASE |
| Feature Cache 구현 | **NOT TOUCHED** | No changes to cache logic |
| write API (POST/PUT/PATCH/DELETE) | **NOT TOUCHED** | No new endpoints |
| beat schedule 변경 | **NOT TOUCHED** | No changes to beat config |
| exchange_mode 변경 | **NOT TOUCHED** | DATA_ONLY maintained |
| KIS_US 어댑터 | **NOT TOUCHED** | No new adapter |
| 서비스 로직 신규 생성 | **NOT TOUCHED** | No service files created/modified (except casing fix) |
| DB INSERT/UPDATE/DELETE 경로 | **NOT TOUCHED** | No write paths added |

---

## 5. Model Test Results

```
tests/test_cr048_model_skeletons.py — 44 passed in 0.08s

  TestIndicatorModel:       9 tests PASS
  TestFeaturePackModel:    10 tests PASS
  TestStrategyModel:       10 tests PASS
  TestPromotionEventModel:  7 tests PASS
  TestCrossModelConsistency: 8 tests PASS
```

### Test Coverage

| Category | Tests | Status |
|----------|:-----:|:------:|
| Table names | 4 | PASS |
| Enum values match design | 7 | PASS |
| Enum UPPERCASE enforcement | 4 | PASS |
| Required columns present | 4 | PASS |
| New columns exist | 8 | PASS |
| Nullable/unique constraints | 4 | PASS |
| Cross-model consistency | 8 | PASS |
| BACKTEST_FAIL state existence | 1 | PASS |
| Champion/Challenger support | 2 | PASS |
| Append-only audit trail | 1 | PASS |
| PK structure | 1 | PASS |

---

## 6. Full Regression Results

```
4593 passed in 173.68s (0:02:53)
0 failed
0 errors
```

| Metric | Before | After | Delta |
|--------|:------:|:-----:|:-----:|
| Total tests | 4549 | 4593 | **+44** |
| Failures | 0 | 0 | 0 |
| Test files | 174 | 175 | +1 |

### Existing Test Updates (enum casing)

| File | Tests Modified | Reason |
|------|:--------------:|--------|
| test_registry.py | 6 | Enum values lowercase→UPPERCASE |
| test_asset_registry.py | 1 | AssetClass values lowercase→UPPERCASE |
| test_runtime_loader.py | 38 | strategy_status strings + LOADABLE set |
| test_universe_runner.py | 2 | Strategy mock status values |

All modifications are casing-only — no logic changes.

---

## 7. Gate Status Confirmation

| Item | Status |
|------|--------|
| Gate | **LOCKED** |
| operational_mode | GUARDED_RELEASE |
| exchange_mode | DATA_ONLY |
| L3 scope | Model skeleton only (as approved) |
| L4 | **BLOCKED** |
| Prohibitions | 7건 유지 |
| GR-RULE-01~03 | 적용 중 |

---

## Design Card Alignment Summary

| Model | Design Card | Alignment |
|-------|------------|:---------:|
| Indicator | design_indicator_registry.md v1.0 | **ALIGNED** |
| FeaturePack | design_feature_pack.md v1.0 | **ALIGNED** |
| Strategy (PromotionStatus) | design_strategy_registry.md v1.0 + design_promotion_state.md v1.0 | **ALIGNED** |
| PromotionEvent | design_promotion_state.md v1.0 | **ALIGNED** |

---

## 8. EX-002 Exception Resolution

| Item | Result |
|------|--------|
| Exception ID | EX-002 |
| File | `app/services/runtime_strategy_loader.py` |
| Change | `LOADABLE_STRATEGY_STATUSES` frozenset 문자열 3개 lowercase→UPPERCASE |
| Lines | 56-58 (3 lines) |
| A Decision | **APPROVED** — retroactive exception, one-time only |
| Batch Status | CONDITIONAL ACCEPT → **FINAL ACCEPTED** |
| Exception Register | `docs/operations/evidence/exception_register.md` EX-002 등록 완료 |
| Exception Report | `docs/operations/evidence/EX-002_runtime_strategy_loader_casing.md` |

---

```
CR-048 Limited L3 Model Skeleton Evidence v1.1 (FINAL ACCEPTED)
Authority: A
Date: 2026-04-04
Scope: Model skeleton 4 + Migration 1 + Tests 44
Regression: 4593/4593 PASS
Gate: LOCKED
```
