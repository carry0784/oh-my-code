# CR-048 RI-2B-2c Session 2 — Amendment Sheet v2

**Amends:** `cr048_ri2b2c_session2_combined_final.md` + `cr048_ri2b2c_session2_amendment_v1.md`
**Issued:** 2026-04-06
**Status:** FROZEN BASELINE — controlling spec for the Harness Repair session
**Latest-wins rule:** any conflict between this sheet and earlier layers is resolved in favor of this sheet.

---

## Amendment 5 — 4-Timepoint Persistence Snapshots

**Original defect:** v1 combined final Part A and Amendment Sheet v1
described session receipts using a single "after" state. A single
snapshot cannot distinguish between:

- An artifact that exists only in the working tree (not yet committed).
- An artifact that is committed but unpushed.
- An artifact that is pushed to a branch but not merged.
- An artifact that is merged into `main`.

These are **four different persistence states**, each with distinct
governance properties (rollback difficulty, visibility, auditability).

**Correction:** every Session 2 final receipt must use a 4-timepoint
snapshot against a `pre-edit` baseline. The five state labels are:

| Timepoint | Label | Persistence state |
|-----------|-------|-------------------|
| T0 | `pre-edit` | Baseline — nothing changed yet |
| T1 | `post-edit` | Changes in working tree, not staged |
| T2 | `post-commit` | Committed to local branch HEAD |
| T3 | `post-PR-open` | Pushed to remote branch + PR opened |
| T4 | `post-merge` | Merged into `main` |

The "4-timepoint" name counts the four transitions **after** the T0
baseline. A session can legitimately terminate at any T1..T4. A
Harness Repair session that terminates at T3 is PARTIAL-CLOSED; only
T4 constitutes SESSION 2 FULLY CLOSED.

**Receipt table template:**

```
| Artifact | T0 pre-edit | T1 post-edit | T2 post-commit | T3 post-PR-open | T4 post-merge |
|----------|-------------|--------------|----------------|-----------------|---------------|
| tests/conftest.py         | unchanged | Option P added  | commit <sha>  | PR #<n>       | pending / <sha> |
| tests/test_cr048_...py    | present   | helper removed  | commit <sha>  | PR #<n>       | pending / <sha> |
| docs/.../amendment_v2.md  | absent    | written         | commit <sha>  | PR #<n>       | pending / <sha> |
```

---

## Amendment 6 — First-Line `controlling_spec` Declaration

**Original defect:** when multiple amendments stack, ambiguity can arise
about which layer governs a given rule. Amendment v1 established the
latest-wins rule, but did not require every subsequent session opener to
**explicitly declare** the controlling spec before any action.

**Correction:** every Harness Repair session (and any future Session 2
remediation session) must record its controlling spec as the **first
line** of the session log, in the literal form:

```
controlling_spec = CR-048 RI-2B-2c Session 2 Amendment Sheet v2
```

No preamble, no rephrasing, no summarization before this line. The
declaration must precede:

- any tool invocation,
- any file read,
- any acknowledgment of the GO.

**Rationale:** this enables a grep-style audit over session transcripts
to verify that every state-change session ran under a declared
controlling spec. Sessions without a first-line declaration are
treated as governance-invalid regardless of their outcome.

---

## Amendment 7 — Amendment Persistence as Separate Files

**Original defect:** v1 combined final and Amendment Sheet v1 existed
only as chat text, not as committed files. This creates a brittle chain
where losing chat context loses the controlling spec entirely. A session
cannot cite a spec that does not exist on disk.

**Correction:** before the Harness Repair session opens its main work,
it **must persist all three layers of the frozen baseline** as distinct
files under `docs/operations/evidence/`:

1. `cr048_ri2b2c_session2_combined_final.md` — v1 combined final
2. `cr048_ri2b2c_session2_amendment_v1.md` — Amendment Sheet v1
3. `cr048_ri2b2c_session2_amendment_v2.md` — Amendment Sheet v2 (this file)

Each file must be written as its own artifact (not concatenated).
Concatenation defeats the latest-wins audit: grep for "Amendment 5"
should return exactly one file.

**The Harness Repair session's final commit must include these three
files in the same commit as the test-harness edits**, because the
entry gate `artifacts_persisted_in_working_tree = true` requires them
to exist at T1 and the target exit state
`artifacts_persisted_in_branch_history = true` requires them at T2+.

---

## Summary of corrections

| # | Area | Correction |
|---|------|------------|
| 5 | Receipt snapshot | Single "after" → 4-timepoint (T0..T4) |
| 6 | Spec traceability | First-line `controlling_spec = ...` declaration required |
| 7 | Amendment persistence | Chat-only → committed evidence files |

## Frozen baseline stack (3 layers)

```
Layer 3: cr048_ri2b2c_session2_amendment_v2.md   (this file — CONTROLLING)
Layer 2: cr048_ri2b2c_session2_amendment_v1.md
Layer 1: cr048_ri2b2c_session2_combined_final.md
```

## Operational correction note (applied at Harness Repair session opening)

When the Harness Repair session opens with its Authorization block, the
block MUST list **entry gates** and **target exit states** separately
(per Amendment 1). The following assignment is governance-correct:

**Entry gates (must hold at T0):**

- `malware_classification = negative`
- `controlling_spec = CR-048 RI-2B-2c Session 2 Amendment Sheet v2`
- `artifacts_persisted_in_working_tree = true`

**Target exit states (must hold at T2..T4 as applicable):**

- `artifacts_persisted_in_branch_history = true` (T2)
- `artifacts_persisted_in_main = false` (T4 — Session 2 does NOT merge to main as part of axis 3 closure)
- `test_harness_pollution = false` (T1+ — observable from post-edit forward)

This is an operational correction applied at session opening time; it
does **not** constitute a new amendment (no Amendment v3 is required).
Amendment Sheet v2 is the final frozen baseline.
