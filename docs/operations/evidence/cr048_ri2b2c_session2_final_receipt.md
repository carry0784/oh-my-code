# CR-048 RI-2B-2c Session 2 — Final Receipt (Harness Repair amended v2)

**controlling_spec** = CR-048 RI-2B-2c Session 2 Amendment Sheet v2
**session_type** = Harness Repair (state-change, authorized)
**issued** = 2026-04-06
**session_outcome** = SESSION 2 CLOSED, axis 3 GREEN (subject to CI + merge)

---

## Governance declaration

- **controlling_spec** = `docs/operations/evidence/cr048_ri2b2c_session2_amendment_v2.md`
- **supersedes** = Part D original + Part D amendment v1
- **latest-wins** rule applied at every conflict point.
- **Entry gates (held at T0):**
  - `malware_classification = negative`
  - `controlling_spec = CR-048 RI-2B-2c Session 2 Amendment Sheet v2`
  - `artifacts_persisted_in_working_tree = true`
- **Target exit states:**
  - `artifacts_persisted_in_branch_history = true` — held at T2
  - `artifacts_persisted_in_main = false` — by design (Session 2 does not merge to main as part of axis 3 closure; merge is Phase 5a responsibility)
  - `test_harness_pollution = false` — held from T1 forward

---

## preflight results (hard gates before any edit)

### preflight_1 (import-safety)

```bash
python -c "import app.models.asset; print('OK')"
```

**Verbatim output:**
```
OK
```
**Exit code:** 0
**Verdict:** PASS

### preflight_2 (atomicity)

Pair-constraint satisfied: Option P applied to `tests/conftest.py`
**and** `_ensure_real_symbol()` removed from
`tests/test_cr048_ri2b2c_path_l_compat.py` **in the same session**.
Neither was applied alone. **Verdict:** PASS.

---

## Option P — exact diff summary

### `tests/conftest.py` (modified)

- 1 statement added (the Option P core): `import app.models.asset  # noqa: F401`
- Surrounding comment block added (documentation only, not statement-governed)
- Insertion point: between the top-level imports and the `from app.main import app` line
- Net change: **24 insertions, 0 deletions**

Normative single-statement form:
```python
import app.models.asset  # noqa: F401
```

### `tests/test_cr048_ri2b2c_path_l_compat.py` (helper removal + plain imports)

- `import importlib` removed
- `import sys` removed
- `from sqlalchemy.orm import DeclarativeBase, configure_mappers` removed
- `_ensure_real_symbol()` function removed (~83 lines including docstring)
- Tuple-assignment line `Base, Symbol, AssetClass, AssetSector = _ensure_real_symbol()` removed
- `configure_mappers()` top-level call removed
- `from app.models.asset import Symbol, AssetClass, AssetSector` added
- `_REAL_METADATA = Symbol.__table__.metadata` preserved (still works because
  `Symbol.__table__` now exists via plain import under Option P)
- Module docstring preserved unchanged

---

## Regression result (full suite)

```
4219 passed, 11 failed, 1231 skipped in 241.58s (0:04:01)
```

### Path-L compat test axis (NEW — previously BLOCKED)

```
tests/test_cr048_ri2b2c_path_l_compat.py::test_with_for_update_compiles_to_for_update_on_postgres PASSED
tests/test_cr048_ri2b2c_path_l_compat.py::test_with_for_update_drops_for_update_on_sqlite         PASSED
tests/test_cr048_ri2b2c_path_l_compat.py::test_step6_query_executes_on_aiosqlite_without_syntax_error PASSED
tests/test_cr048_ri2b2c_path_l_compat.py::test_step6_query_returns_none_for_missing_symbol        PASSED
tests/test_cr048_ri2b2c_path_l_compat.py::test_step6_query_reflects_updated_qualification_status  PASSED

5 passed in 0.20s
```

### Pre-existing unrelated failures (11, out-of-scope)

All in `tests/test_restart_drill.py`. Root cause: the test file expects
CR-048+ lifecycle features (`_startup_fingerprint`, `_on_beat_init`,
`exchange_mode_initialized` event) that are not yet landed on main.

- `ImportError: cannot import name '_startup_fingerprint' from 'workers.celery_app'` (3 tests)
- `ImportError: cannot import name '_on_beat_init' from 'workers.celery_app'` (1 test)
- `ValueError: substring not found` searching for `exchange_mode_initialized` in `app.main.lifespan` source (2 tests)
- `AssertionError: Missing required startup event: exchange_mode_initialized` (1 test)
- Related `baseline_check_after_restart` / `status_operational_mode_after_restart` / `governance_state_after_restart` / `beat_schedule_reload_no_forbidden` / `beat_active_count_stable` / `beat_all_dry_run` failures (4 tests)

**Attribution analysis:** these 11 failures were recorded in the
prior-session diagnostic `ba4w8s8tj.output` at the same baseline with
**zero poison markers**, confirming they pre-date this session and were
not caused by Option P. `tests/test_restart_drill.py` is **not** in the
`_CR048_FORWARD_TEST_FILES` skip list in `tests/conftest.py`, and adding
it is out of scope for this session (GO file-list restriction).

**Axis 3 verdict: GREEN** (5/5 path-L compat PASS, 0 new failures introduced).

---

## 4-Timepoint persistence snapshots

Per Amendment 5 (Amendment Sheet v2). T0 is baseline; T1..T4 are transitions.

| Artifact | T0 pre-edit | T1 post-edit | T2 post-commit | T3 post-PR-open | T4 post-merge |
|----------|-------------|--------------|----------------|-----------------|---------------|
| `tests/conftest.py` | existing (no Option P) | **+24 insertions** (Option P applied) | included in this commit | included in this PR | **pending** |
| `tests/test_cr048_ri2b2c_path_l_compat.py` | untracked (from prior session) | `_ensure_real_symbol()` removed; plain imports restored | included in this commit (first tracked appearance) | included in this PR | **pending** |
| `docs/operations/evidence/cr048_ri2b2c_session2_combined_final.md` | absent | written (v1 combined final) | included in this commit | included in this PR | **pending** |
| `docs/operations/evidence/cr048_ri2b2c_session2_amendment_v1.md` | absent | written (Amendment v1) | included in this commit | included in this PR | **pending** |
| `docs/operations/evidence/cr048_ri2b2c_session2_amendment_v2.md` | absent | written (Amendment v2, controlling) | included in this commit | included in this PR | **pending** |
| `docs/operations/evidence/cr048_ri2b2c_session2_final_receipt.md` | absent | written (this file) | included in this commit | included in this PR | **pending** |

**T4 resolution path:** T4 (merge to main) is NOT part of Session 2 axis 3 closure.
Per Amendment Sheet v2 Operational Correction, `artifacts_persisted_in_main = false`
is the target exit state for this session — merge is deferred to a separate
governance step (PR review + Ruleset checks + explicit merge authorization).

---

## Files changed in the session commit (explicit paths)

1. `tests/conftest.py` — Option P (1 statement + comment block)
2. `tests/test_cr048_ri2b2c_path_l_compat.py` — helper removal + plain imports (first tracked)
3. `docs/operations/evidence/cr048_ri2b2c_session2_combined_final.md` — frozen baseline layer 1
4. `docs/operations/evidence/cr048_ri2b2c_session2_amendment_v1.md` — frozen baseline layer 2
5. `docs/operations/evidence/cr048_ri2b2c_session2_amendment_v2.md` — frozen baseline layer 3 (controlling)
6. `docs/operations/evidence/cr048_ri2b2c_session2_final_receipt.md` — this receipt

**Explicitly NOT included in this commit (out of scope per GO):**

- `app/services/shadow_write_service.py` — Option A2 remediation (axis 1, separate PR)
- `scripts/cr048_path_l_compat_lint.py` — banned-pattern lint gate (axis 2, separate PR per Amendment 4 track separation)
- `scripts/cr048_symbol_column_poison_bisect.py` — diagnostic artifact
- `_inline_diag.py`, `_poison_detector.py` — diagnostic artifacts
- `.claude/settings.local.json` — user-local settings
- `tests/test_advanced_runner.py` — explicit NO-MODIFY per GO (polluter is preserved as-is; Option P neutralizes pollution without touching the polluter)

---

## Rollback readiness

Per GO rollback conditions:

- **preflight_1 failure path:** not triggered (preflight_1 PASS).
- **Option P applied but axis 3 still BLOCKED path:** not triggered (axis 3 GREEN).
- **New unrelated failures path:** not triggered (0 new failures; 11 pre-existing are unchanged vs baseline).

Session terminates with no rollback required.

---

## Final state

- **Axis 1:** GREEN (Option A2 — held in working tree, separate PR)
- **Axis 2:** GREEN (lint gate — held in working tree, separate PR)
- **Axis 3:** GREEN (Option P + helper removal, this commit)
- **Session 2 verdict:** **CLOSED** — 3-of-3 axes GREEN (axes 1 and 2 held in working tree for separate PRs per governance track separation; axis 3 closed here)
- **Session 3 status:** unblocked pending axis 1 + axis 2 PR merges
