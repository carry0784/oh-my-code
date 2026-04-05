# CR-048 RI-2B-2c — Path L Compatibility Remediation Plan (v2)

**Document type**: Planning evidence (persisted to disk)
**Created**: 2026-04-05
**Author session**: Post-`ab8d81e` STANDBY planning under A's explicit "더 나은 계획서" directive
**Parent problem**: B3'' Path L first bounded CAS write session returned BLOCKED (`execute_bounded_write` Step 6 uses `SELECT … FOR UPDATE`, rejected by SQLite)
**Supersedes**: inline plan v1 (same session, 4 self-declared limitations in §9)
**Status**: PLAN ONLY — no code/DB/sealed-file changes performed while producing this document
**Current main HEAD**: `ab8d81e`
**Current Track A chain head**: `d999aed` (implementation_go, unchanged)
**Activation signature**: `ab8d81e` (P4.shadow_receipt_id = `prior_68d980c176d24a0c9dc6ead35307bbad`, unchanged)

---

## 0. Reader-facing summary (TL;DR)

The B3'' Path L execution session correctly halted on a structural incompatibility: one line of sealed code (`shadow_write_service.py:568`) emits `SELECT … FOR UPDATE`, which SQLite does not parse. This document is a **complete, persisted, empirically grounded remediation plan** that eliminates the four honest limitations of the earlier inline draft by:

1. **Persisting to disk** at `docs/operations/evidence/cr048_ri2b2c_path_l_compat_plan.md`.
2. **Specifying the exact before/after diff** for the recommended fix (Option A2).
3. **Enumerating all Postgres-specific SQL** in `app/services/` via full grep (result: exactly one occurrence — line 568).
4. **Specifying the complete 17-column Symbol bootstrap fixture** with concrete values.

The recommended remediation path is a new, independent 3-pattern governance chain (`CR-048 RI-2B-2c`) that is a sibling of — not an amendment to — the currently-closed `ab8d81e` activation signature chain. The existing activation signature remains valid without re-signing because it binds intent/parameters, not code body.

---

## 1. Completion status of the parent problem

### 1.1 Verdict
**B3'' first bounded CAS write under Path L — NOT COMPLETED.**

### 1.2 Per-item status matrix (updated with line-number citations)

| # | Milestone | Status | Evidence anchor |
|:---:|---|:---:|---|
| 1 | Activation signature §14 P1/P2/P4/P5 | ✅ DONE | `ab8d81e` (PR #49) |
| 2 | `EXECUTION_ENABLED = True` | ✅ DONE | `shadow_write_service.py:59`, flip `409ed2d` (PR #46) |
| 3 | Prior shadow receipt created | ✅ DONE | `c95f16b` (PR #48), `data/cr048_prior_shadow.sqlite` row `prior_68d9…7bbad` |
| 4 | Entry gate 5/5 PASS | ✅ DONE | Direct session report (intended_value / Path L / caps 1-1 / receipt_id / source) |
| 5 | `execute_bounded_write()` 1 call | ❌ NOT INVOKED | HC#1 "0 if blocked before execution" applied after root-cause detection |
| 6 | `symbols.SOL/USDT` bootstrap row | ❌ ABSENT | Local sqlite `symbols` table has 0 rows |
| 7 | CAS transition `unchecked → pass` | ❌ NOT ATTEMPTED | Dependent on (5)(6) |
| 8 | Post-write verification | ❌ NOT ATTEMPTED | Dependent on (5) |
| 9 | New execution receipt row | ❌ NOT INSERTED | Dependent on (5) |
| 10 | Final bounded report | ✅ DONE | Inline BLOCKED report in previous turn |

---

## 2. Primary blocker — empirically verified root cause

### 2.1 Exact offending line (sealed, not to be modified in this session)

`app/services/shadow_write_service.py`, line 568, inside `execute_bounded_write`, "Step 6 — real-time DB check (TOCTOU defense)":

```python
# Step 6: real-time DB check (TOCTOU defense)
db_stmt = text("SELECT qualification_status FROM symbols WHERE symbol = :symbol FOR UPDATE")
db_result = await db.execute(db_stmt, {"symbol": symbol})
db_row = db_result.fetchone()
current_db_value = db_row[0] if db_row else None
```

### 2.2 Reproducible empirical evidence

| # | Invocation | Environment | Result |
|:---:|---|---|---|
| E1 | `sqlite3.connect(':memory:').execute("SELECT x FROM t WHERE x=? FOR UPDATE", ('a',))` | Python 3.x stdlib sqlite3 + SQLite 3.50.4 | `sqlite3.OperationalError: near "FOR": syntax error` |
| E2 | SQLAlchemy `text("SELECT x FROM t WHERE x=:v FOR UPDATE")` on `sqlite+aiosqlite:///<tmp>` | SQLAlchemy 2.x + aiosqlite + SQLite 3.50.4 | `(sqlite3.OperationalError) near "FOR": syntax error [SQL: SELECT x FROM t WHERE x=? FOR UPDATE]` |

Both reproductions were performed in **sandbox/temporary databases** during the previous session. **Zero writes to `data/cr048_prior_shadow.sqlite`** occurred.

### 2.3 Why the sealed tests did not catch this

All execute/rollback tests in `tests/test_shadow_write_receipt.py` wire `db.execute` to `AsyncMock(side_effect=mock_execute)` (e.g. lines 1074, 1106, 1143, 1178, 1214, 1248, 1296, 1337, 1373 …). No test ever exercises `execute_bounded_write` against a real aiosqlite engine, so dialect-level incompatibilities are invisible to CI.

### 2.4 Why Path L is structurally impossible today (without a fix)

If `execute_bounded_write` were called on the Path L aiosqlite engine:
- Control reaches line 568.
- `await db.execute(db_stmt, {"symbol": symbol})` raises `sqlite3.OperationalError`.
- The outer `try/except Exception` (lines 385 / 729) catches it and returns `None`.
- No `shadow_write_receipt` row is emitted (no audit trail), no `symbols` row is modified.
- The 1 permitted call is consumed with zero auditable output.

Therefore the stop-before-invoking decision (HC#1 "0 if blocked before execution") strictly dominates the "call-and-swallow-exception" path.

---

## 3. Full Postgres-incompatibility audit (resolves limitation #3 of v1)

### 3.1 Scan scope and method

Tool: `Grep` over `app/services/` recursively.
Patterns: `FOR UPDATE`, `FOR SHARE`, `RETURNING`, `ON CONFLICT`, `DO UPDATE`, `LATERAL`, `DISTINCT ON`, `WITH RECURSIVE`, `NULLS FIRST`, `NULLS LAST`, `ILIKE`, `jsonb`, `JSONB`, `ARRAY\[`, `unnest(`, `GENERATED ALWAYS`, `::` cast, `text\(`.

### 3.2 Findings — every raw SQLAlchemy `text()` in `app/services/`

Raw `text(...)` SQL is localized **entirely** to `shadow_write_service.py`. Other `app/services/*.py` matches for the token `text(` are `Path.read_text` / `Path.write_text` (filesystem I/O, not SQLAlchemy).

| Line | Function | SQL fragment | Postgres-only? | SQLite compat |
|:---:|---|---|:---:|:---:|
| 568 | `execute_bounded_write` Step 6 | `SELECT qualification_status FROM symbols WHERE symbol = :symbol FOR UPDATE` | **YES** (`FOR UPDATE`) | ❌ |
| 628 | `execute_bounded_write` Step 8 | `UPDATE symbols SET qualification_status = :intended WHERE symbol = :symbol AND qualification_status = :expected` | NO | ✅ |
| 677 | `execute_bounded_write` Step 9 verify | `SELECT qualification_status FROM symbols WHERE symbol = :symbol` | NO | ✅ |
| 684 | `execute_bounded_write` Step 9 fallback rollback | `UPDATE symbols SET qualification_status = :original WHERE symbol = :symbol AND qualification_status = :intended` | NO | ✅ |
| 872 | `rollback_bounded_write` Step 5 | `SELECT qualification_status FROM symbols WHERE symbol = :symbol` | NO | ✅ |
| 896 | `rollback_bounded_write` Step 6 CAS | `UPDATE symbols SET qualification_status = :original WHERE symbol = :symbol AND qualification_status = :intended` | NO | ✅ |
| 910 | `rollback_bounded_write` Step 7 verify | `SELECT qualification_status FROM symbols WHERE symbol = :symbol` | NO | ✅ |

**Total raw `text()` SQL in `app/services/`**: **7 statements**.
**Postgres-only among them**: **exactly 1** (line 568).
**Other Postgres-specific constructs** (`RETURNING`, `ON CONFLICT`, `jsonb`, `LATERAL`, `::` cast, etc.) in `app/services/`: **0**.
**`.with_for_update()` usages** in `app/`: **0**.

### 3.3 Conclusion of the audit

The Path L (aiosqlite) incompatibility surface in `app/services/` is exactly **one line** (`shadow_write_service.py:568`). The rollback function and all other bounded-write steps are already SQLite-compatible. There is **no hidden second blocker** waiting downstream of Step 6.

### 3.4 Out-of-scope (acknowledged limits of this audit)

This audit did **not** scan:
- `app/core/`, `app/models/`, `app/api/`, `workers/`, `exchanges/`, `strategies/`
- Alembic migration bodies under `alembic/versions/`
- Raw `execute()` calls on the `AsyncConnection` using ORM query builders (SQLAlchemy ORM level is dialect-aware; only raw `text()` is at risk)

These scopes are irrelevant for `execute_bounded_write`'s path, but if Track A later expands to new write surfaces, a fresh audit should be performed.

---

## 4. Secondary prerequisite — `symbols` table is empty in the Path L store

### 4.1 Current state (read-only verified)

```
data/cr048_prior_shadow.sqlite
├─ shadow_write_receipt: 1 row (receipt_id=prior_68d9…7bbad, verdict=would_write, unconsumed, dry_run=1)
└─ symbols              : 0 rows
```

### 4.2 Implication

Even if the line-568 blocker were resolved, `execute_bounded_write` would still fail at Step 6 or Step 7 with `STALE_PRECONDITION` or at Step 8 with `CAS_MISMATCH` because the target row for `SOL/USDT` does not exist. A **bootstrap INSERT** of one `symbols` row in `unchecked` state is required prior to the retry call.

### 4.3 Why bootstrap is **not** "scope expansion"

- A bootstrap row is test-target initialization, not a bounded business write.
- It is inserted **before** the `execute_bounded_write` call and **without** going through `execute_bounded_write`.
- It does not consume, modify, or fabricate any `shadow_write_receipt` row.
- It is clearly auditable (1 INSERT, logged, pre-call, single row).
- It is analogous to CREATE TABLE in a test conftest — setup, not effect.

---

## 5. Option matrix — remediation strategies

### 5.1 Summary (scored)

| ID | Approach | Files touched | LoC diff | Postgres semantics preserved? | SQLite works? | Silent-workaround? | Recommendation |
|:---:|---|---|:---:|:---:|:---:|:---:|:---:|
| A1 | Delete `FOR UPDATE` from line 568 | 1 (`shadow_write_service.py`) | 1-line edit | Partial (CAS still guards atomicity, but row-level lock lost) | ✅ | NO | 🟢 Fallback |
| A2 | Replace raw `text(...FOR UPDATE)` with ORM `select(Symbol.qualification_status).where(...).with_for_update()` | 1 (`shadow_write_service.py`) + 1 new import line | 3-5 lines | **YES** (dialect-aware: Postgres locks, SQLite no-ops) | ✅ | NO | 🟢🟢 **Primary** |
| B | Inline dialect branch (`if engine.dialect.name == 'sqlite': …`) | 1 (service) | 8-12 lines | Partial | ✅ | NO | 🔴 Verbose, leaks infra into service |
| C | Skip Path L, go directly to Path P (Postgres) | 0 code / 1 docker-compose | 0 | N/A | N/A | NO | 🟡 Contradicts A's L-before-P governance |
| D | Test-side monkey-patch to strip `FOR UPDATE` | 1 test file | ~10 lines | Partial | ✅ | **YES** | 🔴 A-forbidden (silent compensation) |
| E | Engine-level `before_execute` event listener rewriting SQL | 1 (`app/core/database.py`) | ~15 lines | Partial | ✅ | **YES** (non-obvious runtime rewrite) | 🔴 A-forbidden |

### 5.2 Recommendation

**Option A2 (ORM `with_for_update()` replacement).**
Justification:
- Minimum touched surface (1 file, ~3-5 LoC).
- SQLAlchemy dialect-aware contract: Postgres emits `FOR UPDATE`, SQLite silently no-ops.
- Idiomatic 2.x SQLAlchemy (ORM-first), matches codebase's ORM orientation.
- Not a silent workaround — the change is explicit, diff-auditable, and typed.
- Preserves all existing semantics on Postgres; makes SQLite path structurally valid.

**Fallback**: Option A1 (delete `FOR UPDATE`) only if the review session judges A2 adds too many moving parts. A1 is 1-line, trivially reviewable, and the downstream CAS guard at line 628 independently prevents write corruption.

---

## 6. Exact diff specification for Option A2 (resolves limitation #2 of v1)

⚠️ **This diff is a specification only. No edits are applied by this plan document.** The edits are to be performed only inside a separate, A-authorized implementation session (CR-048 RI-2B-2c session 2).

### 6.1 File

`app/services/shadow_write_service.py`

### 6.2 Import addition (top of file, near line 22-26)

**Before** (current imports block 22-25):
```python
from app.models.shadow_write_receipt import ShadowWriteReceipt
from app.services.pipeline_shadow_runner import ShadowRunResult
from app.services.screening_qualification_pipeline import PipelineVerdict
from app.services.shadow_readthrough import ReadthroughComparisonResult
```

**After** (add one line):
```python
from app.models.asset import Symbol
from app.models.shadow_write_receipt import ShadowWriteReceipt
from app.services.pipeline_shadow_runner import ShadowRunResult
from app.services.screening_qualification_pipeline import PipelineVerdict
from app.services.shadow_readthrough import ReadthroughComparisonResult
```

### 6.3 Step 6 body replacement (line 567-571)

**Before** (current, sealed — read-only today):
```python
        # Step 6: real-time DB check (TOCTOU defense)
        db_stmt = text("SELECT qualification_status FROM symbols WHERE symbol = :symbol FOR UPDATE")
        db_result = await db.execute(db_stmt, {"symbol": symbol})
        db_row = db_result.fetchone()
        current_db_value = db_row[0] if db_row else None
```

**After** (target for session 2 only):
```python
        # Step 6: real-time DB check (TOCTOU defense)
        # Dialect-aware row lock:
        #   Postgres -> emits "SELECT ... FOR UPDATE" (row-level lock)
        #   SQLite   -> emits plain "SELECT ..."     (no-op, single-writer)
        db_stmt = (
            select(Symbol.qualification_status)
            .where(Symbol.symbol == symbol)
            .with_for_update()
        )
        db_result = await db.execute(db_stmt)
        db_row = db_result.fetchone()
        current_db_value = db_row[0] if db_row else None
```

### 6.4 Diff size summary

| Metric | Value |
|---|---|
| Files changed | 1 |
| Import lines added | 1 |
| Body lines removed | 2 |
| Body lines added | 7 |
| Net delta | +6 lines |
| Functions touched | 1 (`execute_bounded_write`) |
| Other steps modified | 0 |

### 6.5 Why this is not a semantics change on Postgres

SQLAlchemy 2.x's `.with_for_update()` on a `select(...)` statement rendered against the PostgreSQL dialect produces exactly the same wire-level SQL as the current raw `text("... FOR UPDATE")`: a locking SELECT. Verified by SQLAlchemy documentation and standard dialect behavior. No pool or isolation-level change needed.

### 6.6 Why this works on SQLite

SQLAlchemy's `sqlite` dialect is documented to silently drop `FOR UPDATE` because SQLite lacks fine-grained row locks — its concurrency model already serializes writers per database file. The ORM-level `.with_for_update()` is the sanctioned way to express the intent portably.

---

## 7. Complete 17-column bootstrap fixture (resolves limitation #4 of v1)

⚠️ **This fixture is a specification only.** It is executed only in session 3 (the B3'' retry session), not in session 1 (scope review) or session 2 (code fix).

### 7.1 Column enumeration (live `data/cr048_prior_shadow.sqlite` PRAGMA verified)

| # | Column | Type | NOT NULL | Enum? | Planned bootstrap value |
|:---:|---|---|:---:|:---:|---|
| 1 | `id` | VARCHAR(36) PK | ✅ | — | `str(uuid.uuid4())` (e.g. `"a2d4d6d6-0000-4000-8000-000000000001"`) |
| 2 | `symbol` | VARCHAR(40) unique | ✅ | — | `"SOL/USDT"` |
| 3 | `name` | VARCHAR(200) | ✅ | — | `"Solana / Tether USD"` |
| 4 | `asset_class` | VARCHAR(8) | ✅ | `AssetClass` | `"crypto"` |
| 5 | `sector` | VARCHAR(23) | ✅ | `AssetSector` | `"layer1"` |
| 6 | `theme` | VARCHAR(16) | ✅ | `AssetTheme` | `"l1_scaling"` (or `"none"`) |
| 7 | `exchanges` | TEXT (JSON array) | ✅ | — | `'["binance"]'` |
| 8 | `market_cap_usd` | FLOAT | ❌ | — | `50_000_000_000.0` (optional) |
| 9 | `avg_daily_volume` | FLOAT | ❌ | — | `500_000_000.0` (optional) |
| 10 | `status` | VARCHAR(8) | ✅ | `SymbolStatus` | `"watch"` |
| 11 | `status_reason_code` | VARCHAR(60) | ❌ | — | `None` |
| 12 | `exclusion_reason` | TEXT | ❌ | — | `None` |
| 13 | `screening_score` | FLOAT | ✅ | — | `0.0` |
| 14 | `qualification_status` | VARCHAR(20) | ✅ | — | `"unchecked"` ← **CAS target** |
| 15 | `promotion_eligibility_status` | VARCHAR(30) | ✅ | — | `"unchecked"` |
| 16 | `paper_evaluation_status` | VARCHAR(20) | ✅ | — | `"pending"` |
| 17 | `paper_pass_at` | DATETIME | ❌ | — | `None` |
| 18 | `regime_allow` | TEXT (JSON) | ❌ | — | `None` |
| 19 | `candidate_expire_at` | DATETIME | ❌ | — | `None` |
| 20 | `paper_allowed` | BOOLEAN | ✅ | — | `False` |
| 21 | `live_allowed` | BOOLEAN | ✅ | — | `False` |
| 22 | `manual_override` | BOOLEAN | ✅ | — | `False` |
| 23 | `override_by` | VARCHAR(100) | ❌ | — | `None` |
| 24 | `override_reason` | TEXT | ❌ | — | `None` |
| 25 | `override_at` | DATETIME | ❌ | — | `None` |
| 26 | `broker_policy` | VARCHAR(60) | ❌ | — | `None` |
| 27 | `created_at` | DATETIME | ✅ | — | `datetime.now(timezone.utc)` |
| 28 | `updated_at` | DATETIME | ✅ | — | `datetime.now(timezone.utc)` |

**Total columns in `symbols` table**: 28 (from PRAGMA).
**NOT NULL columns**: 17.
**Columns requiring explicit value in bootstrap**: at least the 17 NOT NULL; nullable columns default to `NULL`.

### 7.2 Planned ORM bootstrap snippet (session 3 reference — not executed now)

```python
# Session 3 bootstrap (run ONCE before execute_bounded_write)
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.asset import Symbol, AssetClass, AssetSector, AssetTheme, SymbolStatus

async def bootstrap_sol_usdt_unchecked(session: AsyncSession) -> Symbol:
    now = datetime.now(timezone.utc)
    row = Symbol(
        id=str(uuid4()),
        symbol="SOL/USDT",
        name="Solana / Tether USD",
        asset_class=AssetClass.CRYPTO,
        sector=AssetSector.LAYER1,
        theme=AssetTheme.L1_SCALING,
        exchanges='["binance"]',
        status=SymbolStatus.WATCH,
        screening_score=0.0,
        qualification_status="unchecked",          # ← CAS pre-state
        promotion_eligibility_status="unchecked",
        paper_evaluation_status="pending",
        paper_allowed=False,
        live_allowed=False,
        manual_override=False,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    await session.flush()
    return row
```

All NOT NULL fields are explicitly set; all nullable fields rely on model defaults (`None` or SQLAlchemy default-factory). The `theme` value is nominal — `"l1_scaling"` is most accurate for SOL; `"none"` is equally acceptable if the reviewer prefers minimalism.

### 7.3 Idempotency and safety

- The bootstrap function is called exactly once per session 3 invocation.
- It adds one row. If the script is re-run, the session-start logic will detect that the row already exists (`SELECT ... WHERE symbol = 'SOL/USDT'`) and skip the INSERT.
- It does NOT touch `shadow_write_receipt`.
- It does NOT call `execute_bounded_write`.

---

## 8. New 3-pattern governance chain — CR-048 RI-2B-2c

### 8.1 Relation to existing chains

```
existing:
  CR-048 RI-2B-2b chain head  : d999aed  (implementation_go, unchanged)
  B3' flag flip               : 409ed2d  (EXECUTION_ENABLED=True, unchanged)
  Activation signature merged : ab8d81e  (P4 slots signed, unchanged)
  Prior-shadow creation       : c95f16b  (sibling, unchanged)

new (proposed):
  CR-048 RI-2B-2c scope review         : SR (session 1)
  CR-048 RI-2B-2c implementation_go    : IG (session 2)
  CR-048 RI-2B-2b retry execution      : RX (session 3, reuses ab8d81e signature)

relationship : sibling of RI-2B-2b chain (does NOT advance d999aed)
```

### 8.2 Session 1 — Scope Review Acceptance

| Field | Value |
|---|---|
| Purpose | A formally accepts the scope (1 file, 1 function, ~6 LoC, +1 import) and approves moving to session 2 |
| Input | (a) this plan document, (b) previous BLOCKED report |
| Output | `docs/operations/evidence/cr048_ri2b2c_scope_review_acceptance_receipt.md` |
| Code edits | **0** |
| DB writes | **0** |
| New test files | **0** |
| Signatures needed | A directly signs §14-equivalent block (verdict / date / scope / rollback_authority) |
| Branch | `track-a/cr048-ri2b2c-scope-review` |
| Exit criterion | Merged PR containing only the scope review receipt file |

### 8.3 Session 2 — Implementation GO

| Field | Value |
|---|---|
| Purpose | Apply Option A2 diff, add aiosqlite E2E compat tests, emit implementation receipt |
| Input | Session 1 merged receipt |
| Output files | (a) `app/services/shadow_write_service.py` (modified — line 568 region, +1 import), (b) `tests/test_shadow_write_compat_aiosqlite.py` (new), (c) `docs/operations/evidence/cr048_ri2b2c_implementation_go_receipt.md` (new) |
| Code edits | Option A2 only. No other lines touched. |
| Test additions | ≥3 cases: success path, CAS mismatch, no-prior-receipt — all on real aiosqlite engine, no mocks |
| Pre-existing sealed tests | Must all still PASS |
| Signatures needed | A signs §14-equivalent block of implementation_go receipt |
| Branch | `track-a/cr048-ri2b2c-implementation` |
| Exit criterion | Merged PR + CI 3/3 green + receipt signed |

### 8.4 Session 3 — B3'' Retry Execution

| Field | Value |
|---|---|
| Purpose | Retry the originally-blocked B3'' Path L first bounded CAS write using the now-compatible service |
| Input | Main at session-2 merge SHA + unchanged `ab8d81e` activation signature |
| Signature reuse | **YES** — `ab8d81e`'s §14 remains valid (signature binds intent+parameters, not code bytes) |
| Pre-call bootstrap | Insert 1 `symbols` row (SOL/USDT, `unchecked`) via the §7.2 fixture |
| Execute call | `execute_bounded_write(...)` exactly **1** time |
| Hard constraints | The same 10 HCs from the original B3'' Path L GO |
| Output files | (a) `scripts/cr048_ri2b2c_b3pp_path_l_retry.py` (new), (b) `docs/operations/evidence/cr048_ri2b2c_b3pp_path_l_retry_evidence.md` (new) |
| Branch | `track-a/b3pp-path-l-retry` (or reuse empty `track-a/b3pp-path-l-first-write`) |
| Success outcome | 1 new execution receipt with `verdict=executed`, `executed=True`, `business_write_count=1`, `qualification_status=pass` for SOL/USDT |
| Exit criterion | Bounded report with Entry gate 5/5 PASS + execution success + post-verify PASS |

### 8.5 Interlocks

- Session 2 cannot start until session 1 is merged.
- Session 3 cannot start until session 2 is merged.
- Path P is not opened in any of the three sessions.
- A separate L→P promotion review session may follow session 3, but is out of scope for this plan.

---

## 9. Verification plan (per session)

### 9.1 Session 1 verification
- [ ] Scope document exactly matches this plan's recommendation (Option A2).
- [ ] No code edits in the PR.
- [ ] Exactly 1 new file added (`cr048_ri2b2c_scope_review_acceptance_receipt.md`).
- [ ] No sealed file touched.

### 9.2 Session 2 verification
- [ ] Diff in `shadow_write_service.py` matches §6.3 exactly (modulo whitespace/formatting).
- [ ] `ruff check .` and `ruff format --check .` PASS.
- [ ] All pre-existing sealed tests PASS.
- [ ] ≥3 new aiosqlite E2E tests PASS without mocks.
- [ ] CI `lint` / `test` / `build` all green.
- [ ] `tests/test_shadow_write_receipt.py` unchanged.
- [ ] No file outside (`app/services/shadow_write_service.py`, new test file, new receipt file) touched.

### 9.3 Session 3 verification
- [ ] Entry gate 5/5 PASS (identical to original B3'' GO).
- [ ] Bootstrap row INSERTed exactly once.
- [ ] `execute_bounded_write` called exactly once, returns non-None receipt with `verdict=executed`.
- [ ] `data/cr048_prior_shadow.sqlite` post-state: `symbols` has 1 row with `qualification_status='pass'`, `shadow_write_receipt` has 2 rows (1 prior + 1 execution).
- [ ] `business_write_count` across all receipts sums to exactly 1.
- [ ] No Postgres connection established.
- [ ] No rollback invoked (success path).
- [ ] Post-verify SELECT returns `'pass'`.

---

## 10. Risk matrix

| # | Risk | Likelihood | Impact | Mitigation |
|:---:|---|:---:|:---:|---|
| R1 | Scope creep during session 2 (other lines "piggy-backed") | Medium | High | Session 1 receipt caps scope to §6.3 diff exactly; session 2 PR diff must match |
| R2 | New aiosqlite E2E tests expose a second hidden incompat | Medium | Medium (positive if early) | Treat any additional finding as session 2 continuation if ≤5 LoC extra; otherwise stop and open session 2.5 |
| R3 | Existing signature (`ab8d81e`) interpreted as invalidated | Low | High | Session 1 receipt explicitly declares that signature binds intent+parameters, not code bytes |
| R4 | Silent compensation via monkey patch sneaks in | Very Low | Critical | Session 2 review checklist explicitly forbids monkey patch / engine event listener |
| R5 | Path P accidentally activated during session 3 | Low | High | Session 3 branch env pins `DATABASE_URL` to `sqlite+aiosqlite:///data/cr048_prior_shadow.sqlite` before any import |
| R6 | Bootstrap row inserted twice on re-run | Low | Medium | §7.3 idempotent guard (`SELECT WHERE symbol='SOL/USDT'` pre-check) |
| R7 | `theme` enum mismatch (`l1_scaling` vs `none`) | Low | Low | Either value is valid; session 3 script will use whichever the reviewer approved in session 1 |
| R8 | Re-running session 3 double-consumes prior receipt | Low | High | `execute_bounded_write` Step 4 (consumed check) already prevents this — test covers this case |
| R9 | `shadow_write_service.py` re-seal procedure forgotten | Medium | Medium | Session 2 receipt explicitly records new SHA as "RI-2B-2c seal point" and updates CLAUDE.md if applicable |

---

## 11. Governance and approval chain

### 11.1 Required A approvals
- **Session 1 GO**: explicit approval to accept the scope outlined in this plan (Option A2, sessions 1→2→3 structure).
- **Session 2 GO**: explicit approval to apply the Option A2 diff and add E2E tests.
- **Session 3 GO**: implicit via the unchanged `ab8d81e` signature, but A should still signal "retry authorized" to avoid ambiguity.

### 11.2 Sealed list update (post-session 2)
- `app/services/shadow_write_service.py` is re-sealed at the session-2 merge SHA.
- The new test file `tests/test_shadow_write_compat_aiosqlite.py` becomes sealed from its introduction.

### 11.3 Chain integrity
- `Track A d999aed` implementation_go chain head — **unchanged** throughout all three sessions.
- `ab8d81e` activation signature — **unchanged**.
- `RI-2B-2c` chain runs as an independent sibling.

### 11.4 No-touch list (all three sessions)
- `docs/operations/evidence/cr048_ri2b2b_activation_go_receipt.md`
- `docs/operations/evidence/cr048_ri2b2b_prior_shadow_creation_evidence.md`
- `scripts/cr048_create_prior_shadow_receipt.py`
- `tests/test_shadow_write_receipt.py`
- `data/cr048_prior_shadow.sqlite` (except the bootstrap INSERT in session 3, which only adds to `symbols`, not to `shadow_write_receipt`)
- `CLAUDE.md` / `EXECUTION_ENABLED` (stays `True`)

---

## 12. Success criteria (end-to-end)

### 12.1 Per-session success
- Session 1: scope receipt merged, A signed.
- Session 2: diff applied, E2E tests added, CI green, implementation receipt merged, A signed.
- Session 3: 1 `execute_bounded_write` success, 1 business write, 1 new execution receipt row, Path L structurally viable.

### 12.2 Program-level success
- `b3pp_first_bounded_cas_write_completed = TRUE`.
- `path_l_structurally_viable = TRUE`.
- L→P promotion judgment session may now proceed if A chooses.
- Exactly one new sealed point added (`RI-2B-2c` seal), no sealed point removed.

---

## 13. Explicit limitations that this v2 plan still carries (honest)

This plan eliminates all four limitations of v1 but is candid about residual constraints:

1. **Plan ≠ execution**: this document is still prose + code snippets; no code, DB, or git state has been altered by producing it.
2. **Session 1 may refine**: A or the reviewer may tighten wording or choose A1 over A2. The plan is a proposal, not an edict.
3. **External dependencies unchanged**: no `requirements.txt`, `pyproject.toml`, or infra change is needed. If session 2 introduces such a change, it is out of scope and must be extracted into its own session.
4. **Audit limited to `app/services/`**: `app/core/`, `app/models/`, `app/api/`, `workers/`, `exchanges/`, `strategies/`, and Alembic migrations were not scanned for Postgres-only SQL. The B3'' path does not touch those, but a future expansion would warrant a fresh scan.
5. **SOL/USDT `theme` choice**: `"l1_scaling"` is the nominal proposal; `"none"` is acceptable. Session 1 or session 3 can finalize.

---

## 14. Next immediate action

**Wait for A's explicit GO.** The valid next inputs are, in order of preference:

1. `CR-048 RI-2B-2c Scope Review Acceptance GO` (starts session 1 per this plan).
2. `Path L compatibility remediation planning GO` (if A wants yet another planning iteration rather than session 1).
3. An A-chosen alternative (Option A1, Option C, or a new variant).

Until then:
- **Claude action: none.**
- **Tool calls: 0.**
- **Branch state: main.**
- **Sealed files: untouched.**
- **STANDBY maintained.**

---

## 15. Appendix A — Empirical reproduction commands

These are exactly the commands that were run during the previous BLOCKED session, for future auditors to replay:

```bash
# E1 — stdlib sqlite3 direct
python -c "
import sqlite3
conn = sqlite3.connect(':memory:')
conn.execute('CREATE TABLE t(x TEXT)')
conn.execute(\"INSERT INTO t VALUES('a')\")
try:
    cur = conn.execute('SELECT x FROM t WHERE x=? FOR UPDATE', ('a',))
    print('OK', cur.fetchall())
except Exception as e:
    print('FAIL', type(e).__name__, e)
"

# E2 — SQLAlchemy text() via aiosqlite
python -c "
import asyncio, os, tempfile
async def main():
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    tmp = tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False); tmp.close()
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp.name}')
    async with engine.begin() as c:
        await c.execute(text('CREATE TABLE t(x TEXT)'))
        await c.execute(text(\"INSERT INTO t(x) VALUES('a')\"))
    async with engine.begin() as c:
        try:
            r = await c.execute(text('SELECT x FROM t WHERE x=:v FOR UPDATE'), {'v': 'a'})
            print('OK', r.fetchall())
        except Exception as e:
            print('FAIL', type(e).__name__, e)
    await engine.dispose()
    os.unlink(tmp.name)
asyncio.run(main())
"
```

Expected output (both commands): `FAIL OperationalError near "FOR": syntax error`.

---

## 16. Appendix B — Live state snapshot at plan-write time

```
git HEAD                        : ab8d81e (main)
Track A implementation_go head  : d999aed (unchanged)
B3' flag flip commit            : 409ed2d
activation DRAFT body commit    : b645980
activation signature merge      : ab8d81e
prior-shadow creation merge     : c95f16b
EXECUTION_ENABLED                : True  (shadow_write_service.py:59)
data/cr048_prior_shadow.sqlite  :
  shadow_write_receipt rows     : 1  (receipt_id=prior_68d980c176d24a0c9dc6ead35307bbad)
  symbols rows                  : 0
  other tables                  : present, empty
sealed files touched this session: 0
local branches                  : main (current), track-a/b3pp-path-l-first-write (empty bookmark)
working tree drift              : .claude/settings.local.json (pre-existing, not from this session)
```

---

## 17. Appendix C — Mapping from v1 limitations to v2 resolutions

| v1 §9 limitation | v2 resolution | v2 section |
|---|---|:---:|
| Plan is text-only, not persisted | Persisted to disk as this markdown file | (file path itself) |
| Option A2 exact diff not specified | Before/after code block with line numbers and import block | §6 |
| Hidden incompat scan incomplete | Full `app/services/` grep of 15+ Postgres-only token patterns | §3 |
| SOL/USDT bootstrap column details not specified | 28-column table + idempotent ORM snippet | §7 |

All four v1 limitations are eliminated by v2.

---

## Footer

```
Document ID        : cr048_ri2b2c_path_l_compat_plan_v2
Chain relationship : sibling of CR-048 RI-2B-2b (does NOT advance d999aed)
Authorship         : Claude, under A's explicit "더 나은 계획서" directive
Persistence        : disk (this file)
Execution          : none — plan only
Files created by producing this plan: 1 (this file)
Files modified by producing this plan: 0
Sealed files touched: 0
Code changes       : 0
DB changes         : 0
Git commits        : 0
Next valid action  : wait for A's GO (§14)
```
