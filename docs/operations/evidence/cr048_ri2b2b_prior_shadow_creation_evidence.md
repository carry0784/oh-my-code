# CR-048 RI-2B-2b Prior Shadow Receipt Creation Evidence

**Created**: 2026-04-05
**Source session**: Prior-shadow creation session (one-off integration bring-up)
**Parent plan**: `docs/operations/evidence/cr048_ri2b2b_package.md` → `cr048_ri2b2b_implementation_go_receipt.md`
**Sibling of**: `cr048_ri2b2b_activation_go_receipt.md` (DRAFT, PR #47, `b645980`)
**Status**: EXECUTION EVIDENCE — one receipt created, append-only, captured for A's reference only.
**Purpose**: Record the generation of a single real `shadow_write_receipt.receipt_id` so that A can paste it into the `P4.shadow_receipt_id` signature slot of the activation GO receipt DRAFT when the signature session is held.

---

## 0. Chain relationship (critical scope note)

This document belongs to a **SIBLING** chain of the Track A governance sequence. It does NOT extend the chain head at `d999aed` (implementation GO receipt, A signed 2026-04-04).

```
Track A governance chain (unchanged head):
  package SEALED
  → acceptance ACCEPT
  → implementation_go SIGNED  ← d999aed (chain head, A signature)
  → B3' EXECUTED              ← 409ed2d (EXECUTION_ENABLED flipped True)
  → activation_go_receipt DRAFT STAGED ← b645980 (PR #47, UNSIGNED)
        ↳ BLOCKED on P4.shadow_receipt_id

Sibling chain (this document):
  prior-shadow creation session
  → one-off integration bring-up
  → evaluate_shadow_write() called exactly 1 time
  → shadow_write_receipt INSERT count = 1
  → receipt_id captured in §5 of this file
```

Running the script and merging this evidence PR does **not**:
- sign the activation DRAFT
- advance the Track A chain head
- unblock `execute_bounded_write()` (that is B3'', a separate downstream step)
- constitute an authorization for any business-table write

---

## 1. Authority citation

Authority for this session is A's explicit Korean-language instruction issued after the read-only search session returned 0 shadow_receipt_id candidates:

> "prior_shadow_receipt 생성 세션 GO"

With A's pre-specified scope:

> "통합 기동 → evaluate_shadow_write() 1회 실제 호출 → DB에 INSERT 1건 → 그 receipt_id를 산출물로 보고. 별도 receipt(가칭 `cr048_ri2b2b_prior_shadow_creation_evidence.md`)에 기록. 현 activation DRAFT와 **별도 체인**으로 취급."

Rough translation: "integration bring-up → 1 real call to `evaluate_shadow_write()` → 1 INSERT to DB → report that receipt_id as the deliverable. Record it in a separate receipt (tentative name `cr048_ri2b2b_prior_shadow_creation_evidence.md`). Treat as a separate chain from the current activation DRAFT."

---

## 2. Scope

### 2.1 In-scope (this PR)

- Create ONE new Python script at `scripts/cr048_create_prior_shadow_receipt.py`
- Use that script to issue exactly ONE call to
  `app.services.shadow_write_service.evaluate_shadow_write()`
- Write exactly ONE row to a fresh dedicated SQLite DB at
  `data/cr048_prior_shadow.sqlite` (gitignored)
- Capture the generated `receipt_id` and record it in this evidence file
- Perform post-run integrity checks (row count, forced proof fields,
  schema DDL)

### 2.2 Out-of-scope

- Modification of any sealed RI-2B-1 file (`shadow_write_service.py`,
  `shadow_write_receipt.py`, `022_shadow_write_receipt.py`,
  `test_shadow_write_receipt.py`)
- Modification of `cr048_ri2b2b_activation_go_receipt.md` DRAFT
- Any business-table write (symbols.qualification_status is unchanged)
- Any call to `execute_bounded_write()` / `rollback_bounded_write()`
- Any Track A chain advancement
- Running the script a second time or creating additional receipts
- Committing the `.sqlite` file (gitignored by `.gitignore` lines
  123, 125–127)

---

## 3. Inputs used

| Field | Value | Source |
|---|---|---|
| `symbol` | `SOL/USDT` | A's pre-specified SOL default |
| `target_table` | `symbols` | `evaluate_shadow_write` default; only member of `ALLOWED_TARGETS` |
| `target_field` | `qualification_status` | `evaluate_shadow_write` default |
| `current_qualification_status` | `unchecked` | Only legal source for `unchecked → pass` transition (see `ALLOWED_TRANSITIONS`) |
| `shadow_observation_id` | `None` | No prior observation row referenced |
| `receipt_id` | `prior_` + `uuid4().hex` | Prefixed to make the row trivially auditable |
| `shadow_result` | `run_shadow_pipeline(market, backtest, CRYPTO, LAYER1, now_utc)` | Real pipeline call, high-quality SOL/USDT fixture (price=150, mcap=50B, vol=500M, ADX=30, quality=HIGH) → yields `PipelineVerdict.QUALIFIED` |
| `readthrough_result` | `ReadthroughComparisonResult(symbol, shadow_result, MATCH, None, ExistingResultSource("sr-prior-001","qr-prior-001",None))` | Mirrors the `_make_readthrough` test fixture pattern |

All fixture values are synthetic. No production market data was fetched.

---

## 4. Script artifact

| Field | Value |
|---|---|
| Path | `scripts/cr048_create_prior_shadow_receipt.py` |
| sha256 | `8a6c81131b8349e204ca1e1594de1b5cce573abd9b023b60c3a424e3e50e55b2` |
| Lines | 275 |
| Entry point | `asyncio.run(_main())` |
| DB target (env-overridden before app import) | `sqlite+aiosqlite:///C:/Users/Admin/K-V3/data/cr048_prior_shadow.sqlite` |
| Schema bootstrap | `Base.metadata.create_all` (same as `tests/conftest.py:82`) |
| Dependencies introduced | 0 new pip packages (uses existing `aiosqlite`, `sqlalchemy[asyncio]`) |
| Sealed files touched | 0 |

The script deletes any pre-existing DB file at startup to guarantee a clean slate, imports `app.models.shadow_write_receipt.ShadowWriteReceipt` (which registers the sealed ORM class on `Base.metadata`), creates all tables, calls `evaluate_shadow_write()` exactly once, commits, and verifies the row via an independent `select(...)` query.

---

## 5. Captured receipt_id (deliverable)

**This is the value A should paste into `P4.shadow_receipt_id` of the activation GO receipt DRAFT at signature time.**

```
receipt_id: prior_68d980c176d24a0c9dc6ead35307bbad
```

Full row (from the script's structured report):

| Column | Value |
|---|---|
| `receipt_id` | `prior_68d980c176d24a0c9dc6ead35307bbad` |
| `dedupe_key` | `5d3990e8d87a91a1fdea05c5d069ca32a032ce834b575e9123f90f722033019a` |
| `symbol` | `SOL/USDT` |
| `target_table` | `symbols` |
| `target_field` | `qualification_status` |
| `current_value` | `unchecked` |
| `intended_value` | `pass` |
| `verdict` | `would_write` |
| `transition_reason` | `shadow_qualified` |
| `block_reason_code` | `None` |
| `would_change_summary` | `symbols.qualification_status: unchecked → pass` |
| `input_fingerprint` | `16134b1bd9548d89` |
| `shadow_observation_id` | `None` |
| `dry_run` | `True` ✅ forced |
| `executed` | `False` ✅ forced |
| `business_write_count` | `0` ✅ forced |
| `created_at` | `2026-04-05 08:24:04` (UTC) |

---

## 6. Execution log (verbatim stdout)

```
[setup] DB file         : C:\Users\Admin\K-V3\data\cr048_prior_shadow.sqlite
[setup] DATABASE_URL    : sqlite+aiosqlite:///C:/Users/Admin/K-V3/data/cr048_prior_shadow.sqlite
[setup] removed previous DB file
[setup] Base.metadata.create_all -> OK
[inputs] symbol         : SOL/USDT
[inputs] pipeline verdict: PipelineVerdict.QUALIFIED
[inputs] input_fingerprint: 16134b1bd9548d89
[inputs] comparison      : ComparisonVerdict.MATCH
[call]   receipt_id      : prior_68d980c176d24a0c9dc6ead35307bbad

================================================================
CR-048 RI-2B-2b PRIOR SHADOW RECEIPT — CREATION REPORT
================================================================
receipt_id           : prior_68d980c176d24a0c9dc6ead35307bbad
dedupe_key           : 5d3990e8d87a91a1fdea05c5d069ca32a032ce834b575e9123f90f722033019a
symbol               : SOL/USDT
target_table         : symbols
target_field         : qualification_status
current_value        : unchecked
intended_value       : pass
verdict              : would_write
transition_reason    : shadow_qualified
block_reason_code    : None
would_change_summary : symbols.qualification_status: unchecked → pass
input_fingerprint    : 16134b1bd9548d89
shadow_observation_id: None
dry_run              : True
executed             : False
business_write_count : 0
created_at           : 2026-04-05 08:24:04
total row count      : 1
================================================================
[verify] dry_run=True, executed=False, business_write_count=0 -> OK
[verify] total rows == 1 -> OK
[done]   exit 0
```

Exit code: `0`

---

## 7. Independent SQL verification

Ran directly after script exit, using the stdlib `sqlite3` module (not SQLAlchemy), to independently confirm the persisted state:

```
--- table names ---
shadow_write_receipt

--- row count ---
1

--- single row (all forced-proof columns) ---
('prior_68d980c176d24a0c9dc6ead35307bbad',
 '5d3990e8d87a91a1fdea05c5d069ca32a032ce834b575e9123f90f722033019a',
 'SOL/USDT',
 'would_write',
 'pass',
 1,   # dry_run
 0,   # executed
 0)   # business_write_count
```

Selected columns of the `CREATE TABLE` DDL confirm the RI-2B-1 sealed schema:

```sql
CREATE TABLE shadow_write_receipt (
  id INTEGER NOT NULL,
  receipt_id VARCHAR(64) NOT NULL,
  dedupe_key VARCHAR(128) NOT NULL,
  symbol VARCHAR(32) NOT NULL,
  target_table VARCHAR(48) NOT NULL,
  target_field VARCHAR(48) NOT NULL,
  current_value VARCHAR(128),
  intended_value VARCHAR(128) NOT NULL,
  would_change_summary VARCHAR(256) NOT NULL,
  transition_reason VARCHAR(128) NOT NULL,
  ...
```

---

## 8. Forced proof fields (RI-2B-1 contract)

The sealed RI-2B-1 function body at `app/services/shadow_write_service.py:245` unconditionally sets:

```python
row = ShadowWriteReceipt(
    ...
    dry_run=True,
    executed=False,
    business_write_count=0,
    ...
)
```

These fields are **not** function parameters; they cannot be overridden by any caller. The persisted row (§5, §7) confirms all three are present at the expected values.

Business-table writes performed by this session: **0**. `symbols.qualification_status` was NOT touched.

---

## 9. Append-only contract proof

| Claim | Evidence |
|---|---|
| INSERT count = 1 | Script report `total row count: 1`; independent SQL `SELECT COUNT(*) = 1` |
| UPDATE count = 0 | `shadow_write_service.py` contains no `UPDATE` statement (sealed RI-2B-1 source) |
| DELETE count = 0 | `shadow_write_service.py` contains no `DELETE` statement (sealed RI-2B-1 source) |
| No subsequent mutation | Script exits after a single `await session.commit()`; engine is disposed; no further code path touches the DB |
| Next-run impossibility without fresh receipt_id | `ShadowWriteReceipt.receipt_id` has UNIQUE constraint; re-running with the same prefix would require a new `uuid4().hex` |

---

## 10. FROZEN / RED / sealed file impact

Files in this PR:

| File | Status | Change |
|---|---|---|
| `scripts/cr048_create_prior_shadow_receipt.py` | NEW (sensitivity: normal) | create |
| `docs/operations/evidence/cr048_ri2b2b_prior_shadow_creation_evidence.md` | NEW (this file) | create |

Files **not** touched (verified via `git status` and `git diff --name-only`):

| Sealed / Track A file | Touched? |
|---|:---:|
| `app/services/shadow_write_service.py` (RI-2B-1 sealed) | ❌ |
| `app/models/shadow_write_receipt.py` (RI-2B-1 sealed) | ❌ |
| `alembic/versions/022_shadow_write_receipt.py` (RI-2B-1 sealed) | ❌ |
| `tests/test_shadow_write_receipt.py` (RI-2B-1 sealed) | ❌ |
| `docs/operations/evidence/cr048_ri2b2b_activation_go_receipt.md` (DRAFT, PR #47) | ❌ |
| `docs/operations/evidence/cr048_ri2b2b_implementation_go_receipt.md` (chain head, PR #34) | ❌ |
| `app/services/paper_trading_session_cr046.py` | ❌ |
| `app/services/session_store_cr046.py` | ❌ |
| Any `workers/`, `strategies/`, `exchanges/` file | ❌ |
| `pyproject.toml`, `requirements.txt` | ❌ |

---

## 11. Post-session state

| Aspect | State |
|---|---|
| Track A chain head | `d999aed` (unchanged) |
| `EXECUTION_ENABLED` | `True` (unchanged since B3') |
| Activation DRAFT signature | still BLANK (this PR does not sign it) |
| B3'' (first bounded CAS write) | still BLOCKED |
| `data/cr048_prior_shadow.sqlite` | exists locally, gitignored, contains 1 row |
| `shadow_write_receipt` row count in prod DB | **0 — not touched** (prod DB is Postgres; this session only wrote to a local SQLite file) |
| Prior-shadow receipt_id available for A | `prior_68d980c176d24a0c9dc6ead35307bbad` |
| Next state | STANDBY — awaiting A's decision to hold a signature session or supply a different `shadow_receipt_id` |

---

## 12. Reproducibility notes

Running the script a second time on the same machine will:

1. Delete `data/cr048_prior_shadow.sqlite`
2. Recreate the schema
3. Generate a **new** `receipt_id` (new `uuid4().hex`) — different from the one in §5
4. Produce a **new** `dedupe_key` only if any of the 7 dedupe inputs differ; because `now_utc` is a frozen constant, `input_fingerprint` is also frozen, so the `dedupe_key` will match the one in §5 if the inputs were preserved — but the `receipt_id` would differ, proving uniqueness enforcement on `receipt_id` rather than on `dedupe_key`.

Because A should use **exactly one** deterministic receipt_id for the signature, **do not re-run the script before signature**. The value in §5 is the canonical deliverable of this session.

---

## 13. What this PR does / does not do

### Does ✅
- Add a one-off prior-shadow creation script
- Capture and record one real `receipt_id` generated by the sealed RI-2B-1 function
- Verify the single-row, forced-proof, append-only contract empirically
- Preserve strict separation from the activation DRAFT chain

### Does NOT ❌
- Modify any sealed RI-2B-1 source file
- Modify the activation GO receipt DRAFT
- Sign any signature slot
- Advance the Track A governance chain head
- Run `execute_bounded_write()` or any bounded CAS write
- Write to any business table (symbols, orders, positions, trades)
- Fetch any real market data
- Create or modify any alembic migration
- Install or pin any new dependency
- Produce more than one receipt

---

## 14. References

| 문서 | 역할 |
|---|---|
| `docs/operations/evidence/cr048_ri2b1_completion_evidence.md` | RI-2B-1 SEALED reference (schema, forced proof contract) |
| `docs/operations/evidence/cr048_ri2b2a_completion_evidence.md` | RI-2B-2a SEALED reference (EXECUTION_ENABLED=False baseline) |
| `docs/operations/evidence/cr048_ri2b2b_implementation_go_receipt.md` | Track A chain head (A signed, `d999aed`) |
| `docs/operations/evidence/cr048_ri2b2b_activation_go_receipt.md` | Activation DRAFT (PR #47, `b645980`) — **sibling**, blocked on `P4.shadow_receipt_id` |
| `app/services/shadow_write_service.py` | Sealed RI-2B-1 implementation (`evaluate_shadow_write` at line 192) |
| `app/models/shadow_write_receipt.py` | Sealed RI-2B-1 ORM model |
| `scripts/cr048_create_prior_shadow_receipt.py` | One-off bring-up script (this PR) |
| `tests/test_shadow_write_receipt.py` | Sealed tests — source of the `_shadow_qualified` / `_make_readthrough` fixture pattern |

---

## Footer

```
CR-048 RI-2B-2b Prior Shadow Receipt Creation Evidence
Session type       : one-off integration bring-up (sibling chain)
Created            : 2026-04-05
Script             : scripts/cr048_create_prior_shadow_receipt.py
Script sha256      : 8a6c81131b8349e204ca1e1594de1b5cce573abd9b023b60c3a424e3e50e55b2
Calls to evaluate_shadow_write() : 1
INSERTs            : 1
UPDATEs            : 0
DELETEs            : 0
Business-table writes : 0
Track A chain head : d999aed (UNCHANGED)
Activation DRAFT   : b645980 (UNCHANGED)
receipt_id (deliverable) : prior_68d980c176d24a0c9dc6ead35307bbad
dedupe_key         : 5d3990e8d87a91a1fdea05c5d069ca32a032ce834b575e9123f90f722033019a
dry_run / executed / business_write_count : True / False / 0  (FORCED)
Next state         : STANDBY — receipt_id available for A's signature session
```
