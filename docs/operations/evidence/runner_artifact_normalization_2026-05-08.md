# Runner Artifact Normalization Memo

Date: 2026-05-08
Status: **CLOSED — CONTROLLED (operational standard)**
Author: B (Implementer)
CR-ID: CR-015 (diagnosis) → CR-017 (closure)
Category: L2 (test runner, no test relaxation)

---

## 1. Problem Statement

When running all 20 observation + governance test files in a single
`pytest` invocation, a collection error occurs:

```
ERROR collecting tests/test_agent_governance.py
ModuleNotFoundError: No module named 'kdexter.engines'; 'kdexter' is not a package
```

First observed: Day 9 of Phase H pilot (2026-04-08)
Reproduced: 2026-05-08 (consistent)

---

## 2. Root Cause Analysis

### Category: Import namespace collision

The error chain:
1. `test_agent_governance.py` imports `app.agents.governance_gate`
2. `governance_gate.py` imports `from kdexter.engines.cost_controller import CostController`
3. When observation test files are collected FIRST, Python's import system
   encounters a local `kdexter` name (likely a namespace conflict with the
   project root or a cached module path) that shadows the actual `kdexter`
   package
4. The shadowed `kdexter` has no `engines` submodule, causing the ImportError

### Why it only occurs in combined runs

- **Observation tests (520)**: Use `_STUB_MODULES` with `MagicMock()` to
  stub out `app.exchanges.*` and other heavy imports. This stubs module
  entries in `sys.modules` early in the collection phase.
- **Governance tests (312)**: Import real `app.agents.governance_gate`
  which depends on the real `kdexter` package.
- **Combined**: The `sys.modules` stubs from observation test setup
  interfere with the real import path for `kdexter.engines`.

### Evidence

| Run | Result |
|-----|--------|
| 20 files combined | ERROR (collection failure on test_agent_governance.py) |
| 16 observation files only | 520 PASS |
| 4 governance files only | 312 PASS |
| Total via split execution | 832 PASS, 0 FAIL |

---

## 3. Verdict

| Dimension | Assessment |
|-----------|-----------|
| Root cause | `sys.modules` stub pollution from `_STUB_MODULES` pattern |
| Is it a code defect? | No — test isolation artifact |
| Is it a safety issue? | No — does not affect runtime or test correctness |
| Operational impact | None — split execution produces identical results |
| Fix priority | Low — cosmetic test runner convenience |

---

## 4. Workaround (Current)

Run observation and governance test suites as two separate invocations:

```bash
# Suite 1: Observation (520 tests)
python -m pytest tests/test_four_tier_board.py tests/test_observation_summary.py \
  tests/test_decision_card.py tests/test_observation_summary_schema.py \
  tests/test_decision_schema_typing.py tests/test_stale_contract.py \
  tests/test_threshold_calibration.py tests/test_4state_regression.py \
  tests/test_cleanup_simulation.py tests/test_cleanup_policy.py \
  tests/test_orphan_detection.py tests/test_order_executor.py \
  tests/test_submit_ledger.py tests/test_execution_ledger.py \
  tests/test_agent_action_ledger.py tests/test_operator_decision.py \
  --tb=no -q

# Suite 2: Governance (312 tests)
python -m pytest tests/test_agent_governance.py tests/test_ops_checks.py \
  tests/test_market_feed.py tests/test_dashboard.py --tb=no -q
```

This workaround has been in continuous use since Day 9 through Day 30
without any issues.

---

## 5. Fix Options (Future, if desired)

| Option | Effort | Risk | Recommendation |
|--------|--------|------|----------------|
| A. Move `_STUB_MODULES` to `conftest.py` with proper teardown | Medium | Low | Preferred — centralizes stubs |
| B. Use `pytest-forked` for process isolation | Low | Medium | Adds dependency |
| C. Refactor governance_gate imports to be lazy | Medium | Low | Over-engineering |
| D. Keep split execution | None | None | Acceptable indefinitely |

**Recommended**: Option D (keep split) for now. Option A if CI/CD requires
single-command execution in the future.

---

## 6. Operational Impact Assessment

| Question | Answer |
|----------|--------|
| Does this affect test correctness? | No |
| Does this mask any real failures? | No — split runs are functionally identical |
| Does this affect the 832/0/0 baseline? | No |
| Does this affect governance compliance? | No |
| Should this block any other work? | No |
| Should this be tracked as a defect? | No — tracked as known artifact (RA-001) |

---

## 7. Operational Standard (CR-017 Closure)

Effective: 2026-05-08
Approved by: A (Designer/Inspector)

### 7.1 Mandatory Split Execution Rule

The 832-test baseline MUST be executed as two separate invocations.
Single-invocation execution is a **known-broken configuration** and
MUST NOT be used for compliance verification.

**Standard execution commands:**

```bash
# Suite 1: Observation (520 tests)
python -m pytest tests/test_four_tier_board.py tests/test_observation_summary.py \
  tests/test_decision_card.py tests/test_observation_summary_schema.py \
  tests/test_decision_schema_typing.py tests/test_stale_contract.py \
  tests/test_threshold_calibration.py tests/test_4state_regression.py \
  tests/test_cleanup_simulation.py tests/test_cleanup_policy.py \
  tests/test_orphan_detection.py tests/test_order_executor.py \
  tests/test_submit_ledger.py tests/test_execution_ledger.py \
  tests/test_agent_action_ledger.py tests/test_operator_decision.py \
  --tb=no -q

# Suite 2: Governance (312 tests)
python -m pytest tests/test_agent_governance.py tests/test_ops_checks.py \
  tests/test_market_feed.py tests/test_dashboard.py --tb=no -q

# Expected combined: 832 passed, 0 failed
```

### 7.2 Reproduction Conditions

| Condition | Detail |
|-----------|--------|
| Trigger | Running all 20 test files in single pytest invocation |
| Root cause | `_STUB_MODULES` in observation tests pollute `sys.modules` |
| Affected module | `kdexter.engines.cost_controller` (via `governance_gate.py`) |
| Error type | `ModuleNotFoundError` during collection phase |
| Workaround | Split into 2 invocations (observation + governance) |

### 7.3 Prohibitions

| Prohibited | Reason |
|------------|--------|
| Using single-invocation result as compliance evidence | Known to produce false collection errors |
| Treating the collection error as a test failure | It is a runner artifact, not a code defect |
| Relaxing any test to "fix" the collection issue | RA-001 is not a test problem |
| Adding pytest-forked without L2 review | Adds external dependency |

### 7.4 Future Resolution Path

If CI/CD automation requires single-command execution in the future:

1. Register as CR (Category B, L2)
2. Preferred fix: Move `_STUB_MODULES` to `conftest.py` with `yield` teardown
3. Verify 832/0/0 baseline is maintained after change
4. Update this document with resolution evidence

### 7.5 Known Artifact Registry Entry

| ID | Description | Severity | Status | Standard |
|----|-------------|----------|--------|----------|
| RA-001 | pytest collection error on combined 20-file invocation | Low | CONTROLLED | Split execution mandatory |
| FP-001 | Red line 1 grep matches "NEVER True" comment | Low | CONTROLLED | Manual verification on weekly check |

**RA-001 status: DIAGNOSED → CONTROLLED → CLOSED (operational standard established).**
