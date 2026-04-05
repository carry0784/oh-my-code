# Session Operating Runbook (v1)

**Created**: 2026-04-05
**Source session**: AELP v1 / Plan B / Item Q-2
**Parent plan**: `autonomous_execution_loop_plan.md` → `continuous_progress_plan_v1.md`
**Status**: RUNBOOK — operational procedure document, not a policy change.
**Purpose**: Codify the repeatable per-session workflow so that any operator (including an autonomous agent) can pick up, execute, and close a session without rediscovering rules.

---

## 1. Scope and audience

### 1.1 Who this is for
- Human operator starting a new Claude Code session on this repository
- Autonomous agent operating under AELP v1
- Reviewer auditing whether a session followed the rules

### 1.2 What this runbook is NOT
- **NOT** a change to the principles defined in `continuous_progress_plan_v1.md`
- **NOT** a replacement for `next_session_prompts.md`
- **NOT** authorization to bypass Track A HOLDs

---

## 2. Core principles (inherited, do not redefine)

Derived from `continuous_progress_plan_v1.md` §3 (authoritative source):

| # | Principle | Short form |
|:---:|---|---|
| P1 | One session, one primary task | Do not mix Track A + Track B in one PR |
| P2 | Blocked → PASS to next unblocked item | Never force-unblock |
| P3 | One PR, one purpose | No drive-by edits |
| P4 | Receipt chain integrity | 3-pattern naming enforced |
| P5 | Evidence body preservation | Sealed files are immutable |
| P6 | Forward / cleanup tag on every PR | Metadata discipline |
| P7 | Approval chain integrity | Receipts require explicit approver |
| P8 | Completed branch never re-candidate | Merged = done |

> AELP mode (autonomous execution) supersedes P2's "blocked → session end" narrow reading: under AELP, PASS auto-advances within the session without waiting for A's instruction. All other principles remain unchanged.

---

## 3. Pre-session check (60 seconds)

Run these in order before picking any work item:

```bash
# 1. Sync main and confirm clean state
git checkout main
git pull
git status

# 2. Check open PRs and recent merges
gh pr list --state open
gh pr list --state merged --limit 10

# 3. Verify governance chain head
# (Expect: cr048_ri2b2b_implementation_go_receipt.md with A signature)

# 4. Check CI baseline
gh run list --limit 5
```

**Abort pre-session if**:
- ❌ `.env` or secret file shows in `git status`
- ❌ Recent merge conflicts unresolved
- ❌ CI red on main (investigate before picking new work)
- ❌ Uncommitted changes in tracked files that you did not make

---

## 4. Task selection rule

### 4.1 Priority order

1. **Track A (HOLD chain)** — only if A has issued a new GO receipt AND the next step is in scope
2. **AELP Plan A** — items B-1 through B-5 from `continuous_progress_plan_v1.md` §4
3. **AELP Plan B** — items Q-1 through Q-3 (quality fallback)
4. **AELP Plan C** — verification + completion receipt (runs only after A+B done)
5. **STANDBY** — if all items above are complete or blocked

### 4.2 Skip rules (PASS trigger)

Skip and move to the next item if:
- Item requires a merged upstream dependency that is not yet merged
- Item requires credentials / collaborator / Track A unlock
- Item touches a sealed file (`c04_*`, `m2_*`, `cg2a_*`, sealed CR-046 phases, etc.)
- CI has failed 3 consecutive times on the same item (record failure, stop AELP loop)

---

## 5. Branch and commit workflow

### 5.1 Branch naming

| Type | Pattern | Example |
|---|---|---|
| AELP Plan A (quality infra) | `docs/bN-<short>` | `docs/b1-coverage-baseline` |
| AELP Plan A (workflow change) | `ci/bN-<short>` | `ci/b2-concurrency` |
| AELP Plan B (navigation / doc) | `docs/qN-<short>` | `docs/q1-evidence-index` |
| AELP Plan C (verification) | `docs/aelp-completion` | `docs/aelp-completion` |
| Track A unlock (when authorized) | `track-a/ri<N>-<step>` | `track-a/ri2b2b-activation` |

### 5.2 Commit message template

```
<type>: <imperative short summary>

<body describing WHY not WHAT>
<reference to AELP item / plan section>

<optional: scope boundary statement>

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

Types: `docs`, `ci`, `fix`, `feat`, `refactor`, `test`, `chore`.

### 5.3 PR title and body

- Title: ≤70 chars, same format as commit subject
- Body sections: Summary, Scope, Does NOT, Track A impact, Test plan
- Always include the "Does NOT" block (makes scope discipline auditable)

---

## 6. CI / merge flow

```bash
# 1. Create PR
gh pr create --title "..." --body "..."

# 2. Wait for all 3 checks (lint / test / build)
sleep 5
gh pr checks <PR_NUM> --watch

# 3. On all-green, squash merge with branch delete
gh pr merge <PR_NUM> --squash --delete-branch

# 4. Sync main
git checkout main
git pull
```

**Never**:
- `gh pr merge --admin` (bypass)
- `gh pr merge` without squash (keeps noisy history)
- Manual rebase on main without coordination
- Force push to main (protected branch; ruleset will block anyway)

---

## 7. PASS procedure

When an item cannot be executed (missing dependency, governance HOLD, sealed file conflict):

1. **Log** the reason in the session notes (one line)
2. **Leave** any partial branch un-pushed (no half-committed artifacts)
3. **Advance** the todo list to the next item
4. **Do not** create a placeholder commit
5. **Do not** mark the skipped item as completed — use a separate "skipped" state in notes

Example pass reason lines:
- `Q-2 PASS: upstream dependency PR #42 not yet merged`
- `B-5 PASS: cr046_sol_paper_rollout_plan.md is sealed and in scope of another session`
- `Track A PASS: no new GO receipt from A in this cycle`

---

## 8. Out-of-scope guard

Before any `git add`, verify:

| Guard | Command | Must be true |
|---|---|---|
| No Track A file touched | `git diff --name-only \| grep -E "shadow_write_service\\|cr048_ri2b2b"` | empty (unless explicit Track A work) |
| No sealed file touched | `git diff --name-only \| grep -E "^docs/operations/evidence/(c04_\\|cg2a_\\|cr046_phase[1-4]_\\|m2_)"` | empty |
| No `.env` staged | `git diff --cached --name-only \| grep "^\\.env"` | empty |
| No credentials staged | `git diff --cached \| grep -iE "api_key\\|secret\\|token" ` | empty (or only in docs referring to var names) |
| CI workflow unchanged unless in scope | `git diff --name-only \| grep "^\\.github/workflows"` | empty (unless CI item) |

If any guard trips, `git restore --staged` the offending file and re-verify.

---

## 9. Evidence file discipline

### 9.1 Create-only rules
- New evidence files go in `docs/operations/evidence/` with descriptive names
- Follow `receipt_naming_convention.md` for the 3-pattern receipt rule
- Include a footer block with plan ref, date, and scope boundary

### 9.2 Never modify
- Any file in §4 of `evidence_index.md` marked SEALED
- Receipts with an A signature already in place
- Sprint contract files from the 2026-03-30 batch
- C-04 Phase 1–10 sealed artifacts
- M2-2 baseline or post-run packages
- `cg2a_pass_seal.md`, `cr046_phase4_pass_seal.md`, `cr047_pass_seal.md`

### 9.3 Modification allowed
- `exception_register.md` — append only (with dated section)
- `CLAUDE.md` — state summary updates (with approval)
- `evidence_index.md` — this file's index (when new evidence added, append)

---

## 10. AELP-specific loop rules (autonomous mode)

When running under AELP v1 authority:

1. **Auto-advance**: after a PR merges green, immediately start the next item in the plan order
2. **Do not wait**: do not pause for A's confirmation between AELP items
3. **Record every merge**: note commit SHA for each merged AELP PR
4. **Stop conditions**:
   - Plan A + Plan B + Plan C complete → emit completion receipt and STANDBY
   - Any governance chain violation detected → STOP immediately, emit alert
   - 3 consecutive CI failures on the same item → STOP, emit diagnosis
5. **Exit artifact**: always write `aelp_<vN>_completion_receipt.md` on clean exit

---

## 11. Exit / STANDBY

A session ends in one of three states:

| State | Trigger | Action |
|---|---|---|
| COMPLETE | All plan items merged | Emit completion receipt → STANDBY |
| BLOCKED | All remaining items blocked | Emit skip log → STANDBY |
| ABORTED | Hard stop condition tripped | Emit diagnosis → STANDBY → notify A |

STANDBY means:
- No further tool calls until A's next instruction
- Working tree synced to main
- Todo list fully reconciled (no dangling `in_progress` items)
- Session summary sent to A (6-section format)

---

## 12. Session summary format (emit at end)

```
Session ID: <timestamp>
Plan ref  : AELP v<N> (or Track A RI-<N>)
Items merged: [list with SHA]
Items skipped: [list with reason]
Items failed: [list with CI error summary]
Next state: STANDBY | HOLD-WAITING | ALERT-REQUIRED
Governance chain head: <filename>
Track A status: UNCHANGED | UPDATED (<detail>)
```

---

## 13. What this PR does / does not do

### Does ✅
- Document the repeatable per-session procedure
- Codify pre-session checks, task selection, CI/merge flow, PASS procedure, out-of-scope guards, and exit states
- Reference the AELP and v1 plans as the authoritative sources
- Provide branch naming and commit templates

### Does NOT ❌
- Modify the principles in `continuous_progress_plan_v1.md`
- Modify AELP rules in `autonomous_execution_loop_plan.md`
- Create new authorities or unblock Track A
- Touch source code, workflows, or evidence files
- Alter `next_session_prompts.md`

---

## 14. References

| 문서 | 역할 |
|---|---|
| `docs/operations/continuous_progress_plan_v1.md` | Principles source (authoritative) |
| `docs/operations/autonomous_execution_loop_plan.md` | AELP loop rules source |
| `docs/operations/evidence/receipt_naming_convention.md` | Receipt 3-pattern spec |
| `docs/operations/evidence_index.md` | Evidence navigation |
| `docs/operations/next_session_prompts.md` | Session starter prompts |

---

## Footer

```
Session Operating Runbook v1
Plan ref         : AELP v1 / Plan B / Item Q-2
Created          : 2026-04-05
Sections         : 14 (scope / principles / pre-check / selection / branch /
                       CI / PASS / out-of-scope / evidence / AELP / exit /
                       summary / PR scope / references)
Content changes  : 0 outside this file
Track A impact   : none
```
