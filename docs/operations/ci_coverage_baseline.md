# CI Coverage Baseline (Phase 2 fail-under proposal)

**Created**: 2026-04-05
**Source session**: AELP v1 / Plan A / Item A1 (B-1)
**Parent plan**: `autonomous_execution_loop_plan.md` → `continuous_progress_plan_v1.md` §4.1
**Status**: PROPOSAL ONLY — `--cov-fail-under` is **NOT** applied in this PR.
**Purpose**: Document the current `app/` coverage baseline and propose a conservative fail-under threshold for future Phase 2 CI enforcement.

---

## 1. Measurement Environment

| 항목 | 값 |
|---|---|
| Branch | `docs/b1-coverage-baseline` (based on `main` after AELP merge `65d19ba`) |
| Python | 3.14 (local), 3.11 (CI target) |
| pytest | 9.0.2 |
| pytest-cov | 7.1.0 |
| coverage.py | 7.13.5 |
| Command | `python -m pytest --cov=app --cov-report=term -q` |
| Measurement date | 2026-04-05 |

---

## 2. Summary Numbers (current baseline)

| 항목 | 값 |
|---|:---:|
| **Total statements** | **16,736** |
| **Missed statements** | **5,728** |
| **Coverage** | **66%** |
| Tests passed | 4,214 |
| Tests skipped | 1,231 |
| Tests failed (local env only) | 11 (all in `tests/test_restart_drill.py`) |

> **Note on failures**: The 11 failures all come from `tests/test_restart_drill.py`, which is a drill/environment-dependent test file. Main branch CI has been consistently green (verified via recent merges #29~#35). These are local-environment-only failures (drill preconditions unmet in dev workstation) and do **not** indicate a regression.

---

## 3. Coverage Distribution Snapshot (selected modules)

### 3.1 High coverage (≥95%)

| Module | Stmts | Miss | Cov |
|---|:---:|:---:|:---:|
| `app/services/paper_trading_session_cr046.py` | 144 | 0 | 100% |
| `app/services/strategy_runner.py` | 87 | 0 | 100% |
| `app/services/strategy_tournament.py` | 95 | 0 | 100% |
| `app/services/system_health.py` | 40 | 0 | 100% |
| `app/services/retry_pressure_service.py` | 49 | 0 | 100% |
| `app/services/review_volume_service.py` | 55 | 0 | 100% |
| `app/services/screening_qualification_pipeline.py` | 59 | 0 | 100% |
| `app/services/screening_transform.py` | 45 | 0 | 100% |
| `app/services/strategy_genome.py` | 89 | 0 | 100% |
| `app/services/trend_observation_service.py` | 67 | 0 | 100% |
| `app/services/performance_metrics.py` | 134 | 3 | 98% |
| `app/services/watch_volume_service.py` | 55 | 1 | 98% |
| `app/services/strategy_lifecycle.py` | 70 | 2 | 97% |
| `app/services/sector_rotator.py` | 78 | 2 | 97% |
| `app/services/portfolio_constructor.py` | 72 | 3 | 96% |
| `app/services/portfolio_metrics.py` | 77 | 4 | 95% |
| `app/services/regime_detector.py` | 105 | 5 | 95% |

### 3.2 Moderate coverage (50–95%)

| Module | Stmts | Miss | Cov |
|---|:---:|:---:|:---:|
| `app/services/walk_forward_validator.py` | 69 | 4 | 94% |
| `app/services/pipeline_shadow_runner.py` | 107 | 10 | 91% |
| `app/services/sentiment_collector.py` | 86 | 8 | 91% |
| `app/services/portfolio_optimizer.py` | 111 | 14 | 87% |
| `app/services/symbol_screener.py` | 149 | 19 | 87% |
| `app/services/validation_pipeline.py` | 149 | 20 | 87% |
| `app/services/risk_budget_allocator.py` | 43 | 7 | 84% |
| `app/services/submit_ledger.py` | 243 | 43 | 82% |
| `app/services/regime_evolution.py` | 57 | 19 | 67% |
| `app/services/runtime_strategy_loader.py` | 73 | 29 | 60% |
| `app/services/runtime_bundle.py` | 54 | 24 | 56% |
| `app/services/promotion_gate.py` | 63 | 29 | 54% |
| `app/services/universe_manager.py` | 71 | 33 | 54% |
| `app/services/runtime_verifier.py` | 76 | 36 | 53% |

### 3.3 Low coverage (<50%) — improvement candidates

| Module | Stmts | Miss | Cov |
|---|:---:|:---:|:---:|
| `app/services/strategy_analyzer.py` | 83 | 42 | 49% |
| `app/services/strategy_router.py` | 44 | 23 | 48% |
| `app/services/trading_hours.py` | 92 | 49 | 47% |
| `app/services/signal_service.py` | 35 | 19 | 46% |
| `app/services/recovery_policy_engine.py` | 150 | 85 | 43% |
| `app/services/runtime_loader_service.py` | 82 | 55 | 33% |
| `app/services/shadow_observation_service.py` | 46 | 31 | 33% |
| `app/services/registry_service.py` | 153 | 109 | 29% |
| `app/services/shadow_readthrough.py` | 104 | 75 | 28% |
| `app/services/position_service.py` | 55 | 42 | 24% |
| `app/services/safe_mode_persistence.py` | 122 | 94 | 23% |
| `app/services/shadow_write_service.py` | 256 | 211 | 18% |
| `app/services/session_store_cr046.py` | 83 | 83 | 0% |

> **Important**: `shadow_write_service.py` at 18% is **expected** — it is gated by `EXECUTION_ENABLED=False` (Track A HOLD). Coverage cannot increase until B3' unlocks the flag and corresponding tests are enabled. This is **not** a regression.

> `session_store_cr046.py` at 0% is a CR-046 Phase 5a target. Coverage will grow once Phase 5a starts (Track A HOLD).

---

## 4. Fail-Under Proposal

### 4.1 Proposed threshold

**Proposal**: `--cov-fail-under=60`

### 4.2 Rationale

| 기준 | 값 | 근거 |
|---|:---:|---|
| Current measured | 66% | §2 |
| Safety margin | −6% | CI environment noise, skipped tests variation, future Track A unlock transient drops |
| Proposed floor | **60%** | 현재치의 90.9% 수준, 명백한 회귀만 차단 |
| Upper cap proposal | — | 본 PR에서 제안하지 않음 (별도 세션에서 조정) |

### 4.3 Why 60 and not 66

- **Skipped test variance**: 1,231 tests are currently skipped. Unskipping a subset (e.g., drill tests in dev containers) can temporarily shift the base.
- **Track A transient effects**: When B3' unlocks `EXECUTION_ENABLED`, `shadow_write_service.py` coverage will briefly dip before new tests are added.
- **CI environment differences**: Local Python 3.14 vs CI Python 3.11 may yield small deltas.
- **Conservative first bar**: A 6-point margin prevents false alarms while still catching meaningful regressions (>6%).

### 4.4 Review cycle

- **First review**: After 2 weeks of green CI with proposed floor, consider tightening to 62–63%.
- **Second review**: After B3' unlock + stabilization, reassess baseline and potentially raise to 68+.
- **Never automatic tightening**: Each bar raise requires an explicit PR with justification.

---

## 5. What this PR does / does not do

### Does ✅
- Measure current `app/` coverage from a clean main checkout
- Propose a conservative `--cov-fail-under` value
- Document the full module-level distribution
- Identify high-variance / expected-low modules

### Does NOT ❌
- Apply `--cov-fail-under` to `.github/workflows/ci.yml` (that is a separate PR, AELP Plan A Item A2 or later)
- Modify any source code
- Modify any test
- Modify any workflow
- Touch `shadow_write_service.py` or any Track A-gated module
- Unblock any Track A branch

---

## 6. Next Steps (future sessions, out of this PR)

1. **CI enforcement PR** (separate, future session): Add `--cov-fail-under=60` to `ci.yml` test job
2. **Low-coverage module audit** (separate session): Investigate modules at 0–30% and add targeted tests where safe
3. **Track A unlock preparation**: `shadow_write_service.py` coverage increase requires B3' unlock first
4. **Review after 2 weeks**: Tighten floor if green run stable

---

## 7. References

| 문서 | 역할 |
|---|---|
| `docs/operations/autonomous_execution_loop_plan.md` | Plan A parent |
| `docs/operations/continuous_progress_plan_v1.md` §4.1 | B-1 원본 명세 |
| `.github/workflows/ci.yml` | 대상 workflow (본 PR에서 미수정) |
| `requirements.txt` | `pytest-cov>=4.1.0` 포함 확인 |

---

## Footer

```
CI Coverage Baseline Document
Plan ref        : AELP v1 / Plan A / Item A1 (B-1)
Measured date   : 2026-04-05
Current coverage: 66% (16,736 stmts, 5,728 missed)
Proposed floor  : 60% (conservative, not yet enforced)
Enforcement PR  : deferred to future session
Source changes  : 0 (docs only)
Track A impact  : none
```
