# CR-048 RI-2B-2c Session 2 — Combined Final Document (v1)

**Status:** PARTIAL-COMPLETE / NOT-CLOSED (superseded by Amendment Sheets v1 and v2 for entry-gate / persistence-snapshot / controlling-spec semantics)
**Issued:** 2026-04-06
**Session scope:** Option A2 remediation, Path L compat lint gate, aiosqlite integration tests, Session 2 receipt
**Governance parent:** A's formal GO ruling with 3-axis entry gate

---

## Part A — Session 2 Receipt (PARTIAL-COMPLETE)

### Axis status snapshot

| Axis | Description | Status |
|------|-------------|--------|
| 1 | Option A2 remediation (`select(...).with_for_update()` ORM construct in `app/services/shadow_write_service.py`) | **GREEN** |
| 2 | Path L compat lint gate (`scripts/cr048_path_l_compat_lint.py`) | **GREEN** |
| 3 | aiosqlite integration tests (`tests/test_cr048_ri2b2c_path_l_compat.py`) | **BLOCKED** |

**Overall Session 2 verdict:** PARTIAL-COMPLETE / NOT-CLOSED. Axes 1 and 2 are GREEN. Axis 3 is BLOCKED pending a separate Harness Repair session.

### Axis 1 — Option A2 remediation

`app/services/shadow_write_service.py` Step 6 SELECT was switched from raw
`text("SELECT ... FOR UPDATE")` to the SQLAlchemy 2.x dialect-aware ORM
construct:

```python
stmt = (
    select(Symbol.qualification_status)
    .where(Symbol.symbol == target_symbol)
    .with_for_update()
)
```

- On PostgreSQL (Path P): SQLAlchemy emits `FOR UPDATE`.
- On SQLite (Path L): SQLAlchemy silently drops the row-lock hint (SQLite
  serializes writers per database file; a row lock is meaningless).
- **Semantic equivalence with the pre-A2 raw SQL path is preserved on Postgres.**
- **The "near FOR syntax error" on aiosqlite is eliminated by design.**

The two dialect compile tests in `tests/test_cr048_ri2b2c_path_l_compat.py`
pass in isolation and confirm both behaviors.

### Axis 2 — Path L compat lint gate

`scripts/cr048_path_l_compat_lint.py` scans `app/**/*.py` via AST walk for
10 forbidden Postgres-only SQL patterns:

- `FOR UPDATE`
- `FOR SHARE`
- `DISTINCT ON`
- `LATERAL`
- `NULLS FIRST`
- `NULLS LAST`
- `GENERATED ALWAYS`
- `jsonb`
- `JSONB`
- `unnest(`
- `ARRAY[`

Result on current `HEAD`: **0 enforced violations**.

### Axis 3 — aiosqlite integration tests (BLOCKED)

**Blocking mechanism:** test harness pollution via module-level
`sys.modules["app.core.database"].Base = _fake_base` in
`tests/test_advanced_runner.py` (and ~60 peer files).

**Decisive evidence** (captured in diagnostic run `buztaj1a5.output`):

```
[CR048-DIAG] Symbol type=<class 'type'> has __table__=False module='app.models.asset' id=2955935436768
[CR048-DIAG] Symbol __bases__=(<class 'tests.test_advanced_runner.FakeBase'>,)
```

**Root cause chain:**

1. pytest collection is alphabetical at the test-file level.
2. `tests/test_advanced_runner.py` is collected before
   `tests/test_cr048_ri2b2c_path_l_compat.py`.
3. At module load time, `test_advanced_runner.py` executes
   `sys.modules["app.core.database"].Base = _fake_base` where `_fake_base`
   is `type("FakeBase", (), {...})` — a **plain** type, not a
   `DeclarativeMeta`.
4. `app.models.asset` has not yet been first-imported, so when it is later
   imported (by `test_cr048_ri2b2c_path_l_compat.py`), `Symbol` is declared
   as `class Symbol(FakeBase)` — no `DeclarativeMeta`, no `__table__`,
   no `metadata`.
5. Every subsequent ORM construct against `Symbol` explodes at
   `.compile()` or `create_all()` or `session.execute()` time.

**Why the pollution cannot be fixed within `test_cr048_ri2b2c_path_l_compat.py` alone:**

- `importlib.reload(app.models.asset)` creates a second `Symbol` class
  against a second `MetaData`, causing `create_all` to run against one
  metadata while the test queries through the other — symptom:
  `OperationalError: no such table: symbols`.
- Re-executing `app.core.database` (Option I) fails with
  `ValueError: not enough values to unpack (expected 3, got 0)` because
  `app.core.config` is also stubbed and `DATABASE_URL` becomes a
  `MagicMock` that `create_async_engine` cannot parse
  (`u._instantiate_plugins(kwargs)` returns an empty tuple).
- Any in-test recovery races the first importer of `app.models.asset`,
  which was already polluted by the time the recovery code runs.

**Conclusion:** axis 3 cannot be closed inside the test file. It must be
closed at the conftest / plugin-phase boundary, before any polluter runs.

---

## Part B — Option P Specification (the only viable fix)

**Option P** = **one statement** added to `tests/conftest.py` at
plugin-load time (which runs before any test-file-level module body):

```python
# Eager import of app.models.asset at conftest plugin-load time.
#
# Why: ~60 test files module-level stub app.core.database.Base (see
# tests/test_advanced_runner.py) with a plain type(). If app.models.asset
# is first-imported AFTER any such stub, its Symbol class is declared
# against the stub instead of SQLAlchemy's DeclarativeBase, losing
# __table__ and metadata forever.
#
# conftest.py is loaded by pytest's plugin manager BEFORE any test file
# module body is executed, so importing app.models.asset here guarantees
# the real DeclarativeBase-backed Symbol class is registered in
# sys.modules first. Later sys.modules stubs then replace only the
# app.core.database.Base reference — Symbol's __bases__ already
# captures the real DeclarativeMeta.
import app.models.asset  # noqa: F401
```

**Paired atomic change:** `tests/test_cr048_ri2b2c_path_l_compat.py`
must have `_ensure_real_symbol()` removed and plain imports restored:

```python
from app.models.asset import Symbol, AssetClass, AssetSector
```

Option P applied alone = still broken (the helper's `importlib.reload`
would bifurcate metadata against the new DeclarativeBase-backed Symbol).

**Helper removal is mandatory and atomic with Option P.**

### Hard preflights (before any edit in the Harness Repair session)

**preflight_1:**

```bash
python -c "import app.models.asset; print('OK')"
```

Must print `OK` and exit 0 in a **fresh** Python interpreter. If it fails,
there is an import-safety failure inside `app.models.asset` itself that
must be resolved before Option P is viable (Option P only redirects
_when_ the import happens; it does not fix _what_ the import does).

**preflight_2:**

If preflight_1 PASSES and Option P is applied, the helper removal in the
path-L compat test is non-optional and must be completed in the same
session. Partial application is forbidden.

---

## Part C — Banned-Pattern Note (separate Track)

The Path L compat lint gate in `scripts/cr048_path_l_compat_lint.py`
already enforces the 10 banned SQL patterns across `app/**/*.py`.

**Scope note:** this gate is a **separate track** from the Harness Repair
session. It is already GREEN on current `HEAD` and must not be bundled
into the Harness Repair commit.

Future extension candidates (out of Session 2 scope):

- Extend gate to `workers/**/*.py` and `exchanges/**/*.py`.
- Add `ILIKE` if SOL/BTC deployment ever targets MySQL.
- Add `RETURNING` detection if Path L dialects without RETURNING support
  are ever introduced.

---

## Part D — Next Session Prompt (Harness Repair, original v1)

> **NOTE:** this original Part D wording is preserved here only for
> historical traceability. It has been **superseded** by Amendment
> Sheet v1 and Amendment Sheet v2. Any Harness Repair session must use
> the latest-wins amended wording, not this original text.

(Original prompt preserved for audit. See Amendment Sheet v1 / v2 for
governance-correct wording.)

---

## Frozen baseline chain

| Layer | Document | Role |
|-------|----------|------|
| 1 | `cr048_ri2b2c_session2_combined_final.md` (this file) | Initial receipt + Option P spec + Part D v1 |
| 2 | `cr048_ri2b2c_session2_amendment_v1.md` | 4 refinements: split entry gates / "1-statement" language / preflights / track separation |
| 3 | `cr048_ri2b2c_session2_amendment_v2.md` | 3 refinements: 4-timepoint snapshots / controlling_spec declaration / amendment persistence |

**Latest-wins rule:** in any conflict between v1 and a later amendment,
the latest amendment wins. Amendment Sheet v2 is the controlling spec
for the Harness Repair session.
