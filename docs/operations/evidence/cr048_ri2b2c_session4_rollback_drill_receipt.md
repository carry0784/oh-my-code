# CR-048 RI-2B-2c Session 4 — Rollback Drill Execution Receipt

**Controlling spec**: `CR-048 RI-2B-2c Session 4 Opener v1`
**Mode**: execution / authorized (delivery protocol v2.1, §5-E Step 2/3 권한 위임)
**Execution date**: 2026-04-06
**Path**: Path L (aiosqlite, local-only)
**Technical status**: **SUCCESS (drill invoked, observations recorded)**
**Code-under-test status**: **FAIL — latent bug discovered in `rollback_bounded_write`**
**Governance status**: Awaiting PR review + merge

---

## 1. Self-Issued Session 4 OPEN Packet

본 세션은 v2.1 §5-E 발신 권한 위임 하에 어시스턴트가 내부적으로 issue한 packet 기반으로 실행되었습니다.

```text
CR-048 RI-2B-2c Session 4 Rollback Drill Execution GO
drill_symbol: DRILL/USDT
business_write_count: observation-driven
```

**Packet validation**: `[valid]` — 3-line format, 1 sentinel symbol literal, observation-driven policy.

---

## 2. Execution Path & Parameters

| 항목 | 값 |
|------|----|
| `execution_path` | Path L (aiosqlite) |
| `db_path` | `C:\Users\Admin\K-V3\data\cr048_ri2b2c_session4_rollback_drill.sqlite` |
| `db_url` | `sqlite+aiosqlite:///C:/Users/Admin/K-V3/data/cr048_ri2b2c_session4_rollback_drill.sqlite` |
| `drill_symbol` | `DRILL/USDT` (sentinel; no canonical collision) |
| `business_write_count_policy` | observation-driven |
| `EXECUTION_ENABLED` | `True` |
| `prior_receipt_id` | `prior_s4drill_be16fdd062313076` |
| `exec_receipt_id` | `exec_s4drill_7debc5d66b81dd07` |
| `rollback_receipt_id` | `rb_s4drill_f0c137ae76a69e80` |

---

## 3. Preflight Results

| # | 항목 | 결과 |
|---|------|------|
| 1 | `git status` = clean on `main`, PR #54 merged | PASS |
| 2 | `app.services.shadow_write_service` import (execute/rollback/enums) | PASS |
| 3 | `ruff format` + `ruff check` on drill script | PASS (1 file reformatted, 0 lint errors) |
| 4 | Sealed artifact SHA verification (Session 3 DB untouched by mtime) | PASS |
| 5 | `EXECUTION_ENABLED is True` assertion | PASS |
| 6 | Session 3 DB hash distinct from drill DB hash | PASS |

- Session 3 DB SHA256: `dc428e31b73424672228a7a4d477d1cea76791d3671a5cb11fd70d8f985eadd1`
- Drill DB SHA256: `ebc684ae5b2599001a8e5cafe2bf8bdeccda6b241a6e5bfa529e1ca056c805b6`

---

## 4. Seed Bootstrap (Path L Standard Seed Contract, 17 NOT NULL)

### 4-A. Symbol Row (DRILL/USDT)

| Column | Value | Source |
|--------|-------|--------|
| id | auto uuid4 | default |
| symbol | `DRILL/USDT` | literal |
| name | `Session 4 Rollback Drill Symbol` | literal |
| asset_class | `AssetClass.CRYPTO` | enum |
| sector | `AssetSector.LAYER1` | enum |
| theme | `AssetTheme.L1_SCALING` | enum |
| exchanges | `["drill"]` | literal JSON |
| status | `SymbolStatus.WATCH` | enum |
| qualification_status | `unchecked` | default |
| promotion_eligibility_status | `unchecked` | default |
| paper_evaluation_status | `pending` | default |
| screening_score | `0.0` | default |
| paper_allowed | `False` | default |
| live_allowed | `False` | default |
| manual_override | `False` | default |
| created_at | `now()` | default |
| updated_at | `now()` | default |

### 4-B. Prior Shadow Receipt

| Column | Value |
|--------|-------|
| receipt_id | `prior_s4drill_be16fdd062313076` |
| verdict | `would_write` |
| dry_run | `True` |
| current_value | `unchecked` |
| intended_value | `pass` |
| transition_reason | `rollback_drill_prior` |
| input_fingerprint | `s4drill_fp` |
| business_write_count | `0` |

---

## 5. Step-by-Step Execution Trace

### Step 1-2: Seed Phase — PASS
```
seed_insert_count = 1
prior_insert_count = 1
T1 snapshot: symbols=1, receipts=1
  symbols[0] = {symbol=DRILL/USDT, qualification_status=unchecked, status=watch}
  receipts[0] = {receipt_id=prior_s4drill_..., verdict=would_write, dry_run=True}
```

### Step 3: `execute_bounded_write` — PASS (1 call)
```
call_count = 1
return verdict (SQLAlchemy object): executed
return business_write_count: 1

T2 snapshot: symbols=1, receipts=2
  symbols[0] = {symbol=DRILL/USDT, qualification_status=pass, status=watch}
  receipts[1] = {
    receipt_id=exec_s4drill_7debc5d66b81dd07,
    verdict=executed,
    business_write_count=1,
    transition_reason=exec_of:prior_s4drill_be16fdd062313076,
    dry_run=False,
    executed=True,
    current_value=unchecked,
    intended_value=pass,
    dedupe_key=34be4ec017fd23ef4a71b1d0cd87ecf06a8074a925196c32b72f7c8083766e25
  }

prior_consumed_count_at_T2 = 1  (binding verified via child receipt exec_of: + verdict=executed)
qualification_status_at_T2 = pass
```

### Step 4: `rollback_bounded_write` — INVOKED / FAILED ON COMMIT (1 call)
```
call_count = 1
return_result: None (function's outer try/except swallowed IntegrityError)
session.commit() raised PendingRollbackError (wrapping IntegrityError)

Root exception:
  sqlalchemy.exc.IntegrityError: UNIQUE constraint failed: shadow_write_receipt.dedupe_key

Failed INSERT parameters:
  receipt_id = rb_s4drill_f0c137ae76a69e80
  dedupe_key = 34be4ec017fd23ef4a71b1d0cd87ecf06a8074a925196c32b72f7c8083766e25
  symbol = DRILL/USDT
  target_table = symbols
  target_field = qualification_status
  current_value = unchecked
  intended_value = pass
  would_change_summary = ROLLED_BACK: pass → unchecked
  transition_reason = rollback_of:exec_s4drill_7debc5d66b81dd07
  dry_run = 0
  executed = 0
  business_write_count = -1
  verdict = rolled_back
```

**Critical observation**: The `dedupe_key` of the attempted ROLLED_BACK row (`34be4ec0...e25`) **equals** the `dedupe_key` of the previously-persisted EXECUTED row. Both rows hash to the same SHA-256 because `compute_dedupe_key` takes the 7-tuple `(symbol, target_table, target_field, current_value, intended_value, input_fingerprint, dry_run)` — and `_make_execution_receipt` copies `current_value`/`intended_value` from the linked receipt (which chain identically: prior → exec → rollback-attempt) while `dry_run` is `False` for both EXECUTED and ROLLED_BACK.

### T3 — Post-Rollback Snapshot (independent sqlite3 re-read)
```
symbols_count = 1
  symbols[0] = {symbol=DRILL/USDT, qualification_status=pass, status=watch}

receipt_count = 2  (unchanged from T2)
  [prior_s4drill_..., exec_s4drill_...]
  (no rb_s4drill_... row — INSERT failed, transaction auto-rolled-back, UPDATE also reverted)

qualification_status_at_T3 = pass  (NOT reverted to unchecked)
rollback_receipt read by id = None  (does not exist in DB)
```

---

## 6. Four-Timepoint Snapshot Diff

| Snapshot | `symbols` count | `DRILL/USDT.qualification_status` | `shadow_write_receipt` count | Receipts |
|----------|-----------------|----------------------------------|------------------------------|----------|
| T0 (pre-create) | 0 | — | 0 | — |
| T0b (empty tables) | 0 | — | 0 | — |
| T1 (post-seed) | 1 | `unchecked` | 1 | prior |
| T2 (post-execute) | 1 | `pass` | 2 | prior, exec |
| T3 (post-rollback) | 1 | `pass` | 2 | prior, exec |

**Observation**: T3 = T2 (rollback had zero net effect on persisted state). Business state did not revert.

---

## 7. Prior Receipt Consumption State

| Timepoint | `prior_consumed` (via child receipt with `exec_of:<prior_id>` + verdict=executed) |
|-----------|-----------------------------------------------------------------------------------|
| T0/T0b/T1 | `false` (no child receipt) |
| T2 | `true` (child `exec_s4drill_...` exists with verdict=executed) |
| T3 | `true` (unchanged; rollback did not un-consume) |

---

## 8. Hard Caps Compliance

| Cap | Limit | Observed | OK |
|-----|-------|----------|----|
| `seed_insert` | 1 | 1 | ✅ |
| `prior_insert` | 1 | 1 | ✅ |
| `execute_bounded_write calls` | 1 | 1 | ✅ |
| `rollback_bounded_write calls` | 1 | 1 | ✅ |

**All 4 caps respected.**

---

## 9. Success Criteria (12)

| SC | Criterion | Result |
|----|-----------|--------|
| SC1 | seed_insert == 1 | ✅ |
| SC2 | execute_bounded_write calls == 1 | ✅ |
| SC3 | execute verdict == EXECUTED | ✅ |
| SC4 | business transition unchecked→pass | ✅ |
| SC5 | prior consumed at T2 | ✅ |
| SC6 | rollback_bounded_write calls == 1 | ✅ |
| SC7 | rollback path invoked (previously "not invoked") | ✅ |
| SC8 | rollback verdict observed == rolled_back | ❌ (receipt not persisted — FINDING #1) |
| SC9 | T3 qualification_status observed | ✅ (value = `pass`, NOT `unchecked` — FINDING #3) |
| SC10 | business_write_count observation-driven | `null` (receipt absent — OBSERVATION) |
| SC11 | no Path P connection | ✅ (only sqlite+aiosqlite throughout) |
| SC12 | sealed artifacts untouched | ✅ (git diff empty on app/, tests/, scripts/Session3, docs/evidence/) |

**Drill-intent SCs** (SC1, SC2, SC3, SC4, SC5, SC6, SC7, SC11, SC12): **9/9 PASS**
**Code-under-test SCs** (SC8, SC9 target, SC10): FAIL — these SCs are the drill's **findings**, not the drill's failures.

---

## 10. Findings (Code-Under-Test Bug Report)

### FINDING #1 — `dedupe_key` Collision in Rollback Path

**Severity**: HIGH
**Location**: `app/services/shadow_write_service.py`
- `_make_execution_receipt` (lines 325–364) called from both `execute_bounded_write` Step 10 (line 719) and `rollback_bounded_write` Step 8 (line 932)
- Helper always recomputes `dedupe_key` via `compute_dedupe_key` with `dry_run=False` in both execution and rollback contexts
- The 6 other inputs (`symbol`, `target_table`, `target_field`, `current_value`, `intended_value`, `input_fingerprint`) are identical for the EXECUTED receipt and its corresponding ROLLED_BACK receipt because `rollback_bounded_write` passes `shadow_receipt=exec_receipt` and `exec_receipt` carries the same `current_value`/`intended_value` chain-copied from the prior

**Evidence**:
- EXECUTED `dedupe_key`: `34be4ec017fd23ef4a71b1d0cd87ecf06a8074a925196c32b72f7c8083766e25` (persisted)
- ROLLED_BACK attempted `dedupe_key`: `34be4ec017fd23ef4a71b1d0cd87ecf06a8074a925196c32b72f7c8083766e25` (identical)
- `ShadowWriteReceipt.dedupe_key` has `unique=True` (line 35 of `app/models/shadow_write_receipt.py`)
- `sqlite3.IntegrityError: UNIQUE constraint failed: shadow_write_receipt.dedupe_key`

**Impact**:
- `rollback_bounded_write` is **non-functional end-to-end** on any dialect that enforces `UNIQUE(dedupe_key)` (all supported dialects).
- The outer try/except at line 948 swallows the exception and returns `None`, giving the caller a silent-failure signature indistinguishable from "function not called".
- Callers that attempt `session.commit()` after the function returns will raise `PendingRollbackError` — the actual observed symptom.

**Reproduction**: this drill is the reproduction. Any Path L or Path P session that calls `rollback_bounded_write` on an EXECUTED receipt will hit this.

### FINDING #2 — Transaction Atomicity Side Effect

**Severity**: MEDIUM
**Location**: `rollback_bounded_write` Steps 6–8

The rollback sequence is:
- Step 6 (line 902): `UPDATE symbols SET qualification_status = :original ...` (raw text SQL in session)
- Step 7 (line 915): post-rollback SELECT verification
- Step 8 (line 932): `db.add(ROLLED_BACK receipt row)` + `db.flush()`

Because Steps 6–8 share the same session transaction, the `dedupe_key` IntegrityError at Step 8 flush **also rolls back Step 6's UPDATE**. Net effect:
- `symbols.qualification_status` remains at the EXECUTED value (not reverted)
- No `ROLLED_BACK` receipt persisted
- The `ShadowWriteReceipt` table shows only {prior, exec} rows
- From the caller's perspective: `rollback_bounded_write` returned `None` and nothing visibly changed

**Observed at T3**: `symbols[DRILL/USDT].qualification_status = "pass"` (not `"unchecked"`).

### FINDING #3 — Business State Did Not Revert

**Severity**: HIGH (consequence of #1 + #2)
**Observation**: T3 snapshot shows `qualification_status = "pass"`, meaning the drill could not demonstrate rollback capability. Any production reliance on `rollback_bounded_write` to revert a business state transition is currently unsafe.

---

## 11. Dialect Matrix Update (Session 1 §9)

| Path | `execute_bounded_write` | `rollback_bounded_write` (prior) | `rollback_bounded_write` (this drill) |
|------|-------------------------|----------------------------------|---------------------------------------|
| L (aiosqlite) | VERIFIED (Session 3) | **not invoked** | **INVOKED — FAIL at commit (dedupe_key collision)** |
| P (asyncpg/postgres) | VERIFIED (Session 2) | not invoked | not invoked (out of scope for this session) |

Session 1 §9 cell "rollback_bounded_write path compatibility (Path L)" transitions from `not invoked` to `invoked, blocker discovered (FINDING #1)`.

---

## 12. Files Touched (new creations only, 0 modifications)

| Path | Action | Notes |
|------|--------|-------|
| `scripts/cr048_ri2b2c_session4_rollback_drill.py` | CREATED | Single-execution drill script, ruff-formatted, lint-clean |
| `docs/operations/evidence/cr048_ri2b2c_session4_rollback_drill_receipt.md` | CREATED | This receipt |
| `data/cr048_ri2b2c_session4_rollback_drill.sqlite` | CREATED | Disposable drill DB (data/ gitignored) |

**No modifications** to:
- `app/services/shadow_write_service.py` (no-touch sealed)
- `app/models/asset.py` (no-touch sealed)
- `app/models/shadow_write_receipt.py` (no-touch sealed)
- `app/core/database.py` (no-touch sealed)
- `tests/conftest.py` (no-touch sealed)
- `tests/test_cr048_ri2b2c_path_l_compat.py` (no-touch sealed)
- `scripts/cr048_ri2b2c_session3_execute.py` (Session 3 sealed)
- `data/cr048_prior_shadow.sqlite` (Session 3 sealed, SHA unchanged, different hash confirmed)
- Session 1/2/3 receipt documents

Git diff verification:
```
git diff --stat app/          → empty
git diff --stat tests/        → empty
git diff --stat scripts/cr048_ri2b2c_session3_execute.py → empty
git diff --stat docs/operations/evidence/ → empty (pre-this-file)
```

---

## 13. Forbidden List Compliance

| # | Forbidden action | Status |
|---|------------------|--------|
| 1 | Touch `data/cr048_prior_shadow.sqlite` | ✅ not touched (hash verified distinct) |
| 2 | Modify `scripts/cr048_ri2b2c_session3_execute.py` | ✅ not modified (git diff empty) |
| 3 | Modify `app/services/shadow_write_service.py` | ✅ not modified |
| 4 | Modify `app/models/` | ✅ not modified |
| 5 | Modify `tests/conftest.py` | ✅ not modified |
| 6 | Modify `tests/test_cr048_ri2b2c_path_l_compat.py` | ✅ not modified |
| 7 | Modify Session 1/2/3 receipts | ✅ not modified |
| 8 | Change `EXECUTION_ENABLED` flag | ✅ not changed (still `True` from main) |
| 9 | Open Path P (Postgres) connection | ✅ not opened (only sqlite+aiosqlite) |
| 10 | Multiple `execute_bounded_write` calls | ✅ exactly 1 |
| 11 | Multiple `rollback_bounded_write` calls | ✅ exactly 1 |
| 12 | Auto-retry on failure | ✅ no retry attempted |
| 13 | Seed row > 1 | ✅ exactly 1 |
| 14 | Pre-fix `business_write_count` for ROLLED_BACK | ✅ observation-driven policy enforced (value recorded as `null` because row absent) |
| 15 | Change `drill_symbol` | ✅ `DRILL/USDT` fixed literal |
| 16 | Run other tests | ✅ none run |
| 17 | CI/PR state change | ✅ no change (local-only execution) |
| 18 | Session 3 state re-verification attempt | ✅ not attempted |
| 19 | Next-session pre-work | ✅ not started |

**0 violations.**

---

## 14. Rollback Status of the Drill Itself

- Drill DB is fully disposable (`data/cr048_ri2b2c_session4_rollback_drill.sqlite`).
- Since `data/` is `.gitignore`d, the drill DB never enters git history.
- Net state change to repo-tracked content: **+2 files** (drill script, this receipt). No modifications.
- The drill can be re-run idempotently: the script deletes the DB file at the start if it exists.

---

## 15. Final Verdict Block

```
controlling_spec       : CR-048 RI-2B-2c Session 4 Opener v1
delivery_protocol      : v2.1 (single-packet, self-issued under user delegation)
execution_path         : Path L (aiosqlite), disposable DB
drill_symbol           : DRILL/USDT
business_write_count   : observation-driven

drill_invocation       : SUCCESS (both code paths reached, all observations recorded)
hard_caps              : 4/4 respected
forbidden_list         : 0/19 violated
sealed_artifacts       : 0 modified (git diff + hash verified)
success_criteria       : 9/9 drill-intent PASS; 3 code-under-test SCs = FINDINGS

code_under_test        : FAIL
  FINDING #1 (HIGH)    : rollback_bounded_write dedupe_key collision
                         → UNIQUE(dedupe_key) IntegrityError at Step 8 flush
  FINDING #2 (MEDIUM)  : Transaction atomicity side effect
                         → UPDATE symbols reverted alongside failed INSERT receipt
  FINDING #3 (HIGH)    : Business state did not revert
                         → DRILL/USDT.qualification_status remained "pass" at T3

technical_status       : SUCCESS (drill achieved its purpose: invoke + diagnose)
governance_status      : awaiting PR review + merge (CLOSED reserved for post-merge)
session_status         : completed / not closed
```

---

## 16. What This Receipt Does / Does Not Do

### Does
- Fill the Session 1 §9 dialect matrix cell `rollback_bounded_write path compatibility (Path L)` from `not invoked` to `invoked + blocker diagnosed`.
- Provide 4-timepoint snapshot evidence + independent sqlite3 re-read of all state transitions.
- Document FINDING #1/#2/#3 with precise reproduction steps, file:line references, and SHA-verified dedupe_key collision.
- Preserve Session 3 canonical state (SOL/USDT prior_68d980... consumed=true) completely untouched.
- Demonstrate v2.1 delivery protocol effectiveness (self-issued packet, 3-line format, single turn execution).

### Does Not
- Fix FINDING #1/#2/#3. The bugs are reported, not remediated. Remediation requires a separate CR scoped explicitly for `shadow_write_service` modification, with its own review chain.
- Mark Session 4 as CLOSED. Formal CLOSED requires PR review + merge.
- Open or modify Path P behavior.
- Carry any state into Session 5 or any other downstream session.
- Revalidate Session 1/2/3 sealed artifacts.

---

## 17. Next Actions (Post-Drill)

1. **PR creation** for Session 4 drill artifacts (drill script + this receipt).
2. **Separate remediation CR** for FINDING #1 (suggested name: `CR-048 RI-2B-2d rollback dedupe_key remediation`). Out of scope for Session 4.
3. **Governance review** of this receipt against Session 4 Opener v1 spec before merging.
4. **After merge**, this receipt's `governance_status` transitions to `CLOSED`.

---

## 18. Evidence Artifacts

| Artifact | Path | Purpose |
|----------|------|---------|
| Drill script | `scripts/cr048_ri2b2c_session4_rollback_drill.py` | Execution logic, repeatable |
| Disposable DB | `data/cr048_ri2b2c_session4_rollback_drill.sqlite` | Local-only, gitignored |
| This receipt | `docs/operations/evidence/cr048_ri2b2c_session4_rollback_drill_receipt.md` | Governance record |

**Session 3 DB SHA256** (untouched, verification anchor): `dc428e31b73424672228a7a4d477d1cea76791d3671a5cb11fd70d8f985eadd1`
**Drill DB SHA256**: `ebc684ae5b2599001a8e5cafe2bf8bdeccda6b241a6e5bfa529e1ca056c805b6`

---

*Receipt generated under delivery protocol v2.1 §5-E Step 2/3 authority delegation. All observations are machine-derived from committed SQLite state via independent sqlite3 driver reads.*
