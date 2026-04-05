# CR-048 RI-2B-2c Session 2 — Amendment Sheet v1

**Amends:** `cr048_ri2b2c_session2_combined_final.md`
**Issued:** 2026-04-06
**Supersedes conflicts with:** Part D original (v1 combined final)
**Latest-wins rule:** any conflict between this sheet and v1 combined final is resolved in favor of this sheet.

---

## Amendment 1 — Split Entry Gates from Target Exit States

**Original defect:** v1 combined final Part D used the single phrase
"entry gate" for what are actually **two distinct kinds of conditions**:

1. Conditions that must hold **at session entry** (preconditions that
   cannot be created _during_ the session).
2. States that the session must **drive toward and hold at exit**
   (postconditions / target terminal states).

Conflating them makes it impossible to re-run the Harness Repair session
under the same GO — a post-commit artifact cannot be a precondition for
its own creation.

**Correction:** every Harness Repair session opener must distinguish:

```
Entry gates (hold-at-entry):
    - malware_classification = negative
    - controlling_spec = Amendment Sheet v2
    - artifacts_persisted_in_working_tree = true

Target exit states (hold-at-exit):
    - artifacts_persisted_in_branch_history = true
    - artifacts_persisted_in_main = false
    - test_harness_pollution = false
```

**Rationale:** `artifacts_persisted_in_branch_history = true` requires a
commit to exist; that commit is produced **inside** the session.
Therefore it is a target exit state, not an entry gate. Same for
`test_harness_pollution = false` — that is the desired terminal state
after Option P + helper removal, not a precondition.

---

## Amendment 2 — Replace "3-line fix" with "1-statement fix"

**Original defect:** v1 combined final Part B described Option P as a
"3-line fix" referring to (comment block + import line + noqa marker).
This overcounted lines and created ambiguity about whether the comment
block was optional.

**Correction:** the normative description is:

> Option P = **one statement** (`import app.models.asset  # noqa: F401`)
> added to `tests/conftest.py` at plugin-load time. Any surrounding
> explanatory comment block is documentation only and not governed by
> the 1-statement count.

**Rationale:** the governance-relevant change is exactly one import
statement. Lint gates and diff reviewers must count statements, not
lines, to verify scope compliance.

---

## Amendment 3 — Hard Preflights Added

**Original defect:** v1 combined final Part D authorized Option P
without preflight verification. This would have allowed a Harness Repair
session to apply Option P against a broken `app.models.asset` module,
producing a Type 2 failure (Option P "applied" but import still fails,
masking the real bug and wasting a commit).

**Correction:** two hard preflights are now mandatory before any edit.

### preflight_1 (import-safety)

```bash
python -c "import app.models.asset; print('OK')"
```

Run in a **fresh** Python interpreter. Must print `OK` and exit 0. If it
fails, the session STOPS and escalates as an import-safety failure. No
edits to `tests/conftest.py` are permitted under a failed preflight_1.

### preflight_2 (atomicity)

If preflight_1 PASSES and Option P is applied to `tests/conftest.py`,
`tests/test_cr048_ri2b2c_path_l_compat.py` **must be edited in the
same session** to remove `_ensure_real_symbol()` and restore plain
imports:

```python
from app.models.asset import Symbol, AssetClass, AssetSector
```

**Option P applied alone = broken.** The helper's `importlib.reload`
against the newly-DeclarativeBase-backed Symbol would bifurcate metadata
(two Symbol classes with two MetaData instances), producing
`OperationalError: no such table: symbols` downstream.

Helper removal is mandatory and atomic with Option P.

---

## Amendment 4 — Track Separation (Banned-Pattern Lint)

**Original defect:** v1 combined final Part C described the banned-pattern
lint gate (`scripts/cr048_path_l_compat_lint.py`) as optionally bundled
with the Harness Repair session. Bundling is forbidden.

**Correction:** the banned-pattern lint track is **strictly separate**
from the Harness Repair track. Specifically:

- The Harness Repair session's commit must **not** modify
  `scripts/cr048_path_l_compat_lint.py`.
- The Harness Repair session's commit must **not** add new banned
  patterns or lint rules.
- Any banned-pattern extensions are filed as a separate future track
  under its own GO.

**Rationale:** bundling unrelated concerns into a single commit
obstructs revert operations. If axis 3 has to be rolled back, only the
test harness changes should revert — the banned-pattern gate is already
GREEN and must remain so independently.

---

## Summary of corrections

| # | Area | Before | After |
|---|------|--------|-------|
| 1 | Entry gate semantics | Single "entry gate" phrase | Split into entry gates vs target exit states |
| 2 | Option P scope | "3-line fix" | "1-statement fix" |
| 3 | Session entry safety | No preflight | preflight_1 + preflight_2 as hard gates |
| 4 | Track boundaries | Bundled banned-pattern lint option | Strict track separation |

**Net effect on Harness Repair session design:** adds two hard gates
before any edit, sharpens scope to exactly one statement, and prevents
unrelated track bundling.
