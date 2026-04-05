# SHA Pinning Inventory for CI Actions

**Created**: 2026-04-05
**Source session**: AELP v1 / Plan A / Item A3 (B-3)
**Parent plan**: `autonomous_execution_loop_plan.md` → `continuous_progress_plan_v1.md` §4.3
**Status**: INVENTORY ONLY — SHA pinning is **NOT** applied in this PR.
**Purpose**: Enumerate every GitHub Actions action referenced in this repository's workflows, capture the current tag-to-commit resolution, and prepare the ground for a future supply-chain hardening PR.

---

## 1. Why SHA pinning matters

Version tags (e.g. `@v4`, `@v5.0.0`) are **mutable references**. A malicious actor who gains write access to an action's repository — or even a well-intentioned maintainer pushing a breaking change — can alter what any tag points to. Pinning to a full 40-character commit SHA guarantees that CI executes the **exact byte sequence** that was audited, regardless of upstream tag movement.

Reference: GitHub security hardening guide, OpenSSF Scorecard "Pinned-Dependencies" check.

---

## 2. Current workflow inventory

| Workflow | Path | Jobs |
|---|---|---|
| CI | `.github/workflows/ci.yml` | lint / test / build |

Only one workflow file currently exists in this repository.

---

## 3. Action inventory

### 3.1 Actions referenced in `.github/workflows/ci.yml`

| # | Action | Current ref | Resolved SHA (at 2026-04-05) | Tag type | Release date |
|:---:|---|---|---|:---:|---|
| 1 | `actions/checkout` | `v5.0.0` | `08c6903cd8c0fde910a37f88322edcfb5dd907a8` | exact (v5.0.0) | 2025-08-11 |
| 2 | `actions/setup-python` | `v6.0.0` | `e797f83bcb11b83ae66e0230d6156d7c80228e7c` | exact (v6.0.0) | 2025-09-04 |
| 3 | `actions/cache` | `v5` | `668228422ae6a00e4ad889ee87cd7109ec5666a7` | **floating** (→ v5.0.4) | 2026-03-18 (v5.0.4) |

### 3.2 Observations

| # | Item | Risk | Note |
|:---:|---|:---:|---|
| 1 | `actions/cache@v5` | 🟡 medium | Uses floating major-version tag. Upstream can silently advance to v5.0.5, v5.1.0, etc. without this repo knowing. Pinning to exact SHA or `v5.0.4` would freeze this. |
| 2 | `actions/checkout@v5.0.0` | 🟢 low | Already pinned to exact version tag. SHA pin would add cryptographic integrity. |
| 3 | `actions/setup-python@v6.0.0` | 🟢 low | Already pinned to exact version tag. SHA pin would add cryptographic integrity. |
| 4 | Transitive actions | 🟠 unknown | GitHub-official actions may internally call other actions. Full dependency tree inspection is out of scope for this inventory. |

### 3.3 Verification commands (audit trail)

The inventory data above was produced by the following GitHub API calls:

```bash
gh api repos/actions/checkout/git/ref/tags/v5.0.0 --jq '.object.sha'
# => 08c6903cd8c0fde910a37f88322edcfb5dd907a8

gh api repos/actions/setup-python/git/ref/tags/v6.0.0 --jq '.object.sha'
# => e797f83bcb11b83ae66e0230d6156d7c80228e7c

gh api repos/actions/cache/git/ref/tags/v5 --jq '.object.sha'
# => 668228422ae6a00e4ad889ee87cd7109ec5666a7

gh api repos/actions/cache/git/ref/tags/v5.0.4 --jq '.object.sha'
# => 668228422ae6a00e4ad889ee87cd7109ec5666a7  (confirms v5 → v5.0.4)
```

All three tags at time of capture are lightweight tags pointing directly to commit objects (verified via `--jq '.object.type'` returning `"commit"`).

---

## 4. Proposed SHA pin syntax (for future enforcement PR)

Once a separate PR decides to enforce pinning, the `uses:` lines in `.github/workflows/ci.yml` would become:

```yaml
# Before (current)
- uses: actions/checkout@v5.0.0
- uses: actions/setup-python@v6.0.0
- uses: actions/cache@v5

# After (full SHA pin with version comment)
- uses: actions/checkout@08c6903cd8c0fde910a37f88322edcfb5dd907a8 # v5.0.0
- uses: actions/setup-python@e797f83bcb11b83ae66e0230d6156d7c80228e7c # v6.0.0
- uses: actions/cache@668228422ae6a00e4ad889ee87cd7109ec5666a7 # v5.0.4
```

The trailing `# version` comment is the GitHub-recommended convention so humans can still read which version is pinned.

---

## 5. Risk / Trade-off analysis

### 5.1 Benefits of pinning

| Benefit | Description |
|---|---|
| **Reproducibility** | CI result at time T is bit-exact reproducible at time T+N |
| **Supply-chain integrity** | Upstream tag repush cannot silently change behavior |
| **Audit trail** | `grep` across the repo gives exact version audit in seconds |
| **OpenSSF Scorecard** | "Pinned-Dependencies" check passes at full score |

### 5.2 Costs of pinning

| Cost | Description | Mitigation |
|---|---|---|
| Manual update overhead | Security patches require manual SHA bump | Use `dependabot` to auto-open PRs when upstream releases |
| `v5` → exact loses minor-version auto-updates | v5.0.4 → v5.0.5 bug fixes won't apply until explicit update | Same (dependabot) |
| Version comment discipline | Humans must keep `# v5.0.0` comment accurate | Enforced by code review |

### 5.3 Why this PR does NOT apply the pin yet

1. **Single action is floating** (`cache@v5`): applying pin without a strategy for future updates is risky
2. **Dependabot strategy undecided**: without automated update PRs, a pinned repo becomes stale
3. **Audit discipline setup**: project first needs a documented policy for when/how to bump pinned SHAs
4. **Scope discipline**: AELP Plan A Item A3 is defined as "inventory only, no apply"

---

## 6. Follow-up items (out of this PR, future sessions)

1. **Dependabot configuration PR**: Add `.github/dependabot.yml` with `github-actions` ecosystem
2. **SHA pinning enforcement PR** (separate): Replace the 3 `uses:` lines with SHA+comment form
3. **Policy document**: Add a 1-page runbook for "how to review and merge a dependabot action bump PR"
4. **Scorecard CI**: (optional, long-term) Add OpenSSF Scorecard workflow to continuously monitor pinning status
5. **Transitive audit** (optional): Inspect whether `actions/checkout`, `setup-python`, `cache` internally invoke other actions

---

## 7. What this PR does / does not do

### Does ✅
- Enumerate every action referenced in current workflow files
- Capture the tag → SHA resolution at measurement date
- Document the verification commands (reproducible audit trail)
- Propose the future pinning syntax
- Analyze trade-offs and list follow-ups

### Does NOT ❌
- Modify `.github/workflows/ci.yml` (no `uses:` line changes)
- Add dependabot configuration
- Add any SHA pin in any form
- Bump any action version
- Touch any source code, test, or other doc

---

## 8. References

| 문서 | 역할 |
|---|---|
| `docs/operations/autonomous_execution_loop_plan.md` | Plan A parent |
| `docs/operations/continuous_progress_plan_v1.md` §4.3 | B-3 원본 명세 |
| `.github/workflows/ci.yml` | 유일한 대상 workflow (본 PR에서 미수정) |
| GitHub security hardening guide | 상위 레퍼런스 |
| OpenSSF Scorecard Pinned-Dependencies check | 상위 레퍼런스 |

---

## Footer

```
SHA Pinning Inventory Document
Plan ref        : AELP v1 / Plan A / Item A3 (B-3)
Measured date   : 2026-04-05
Actions counted : 3 (checkout, setup-python, cache)
Floating tags   : 1 (cache@v5 → v5.0.4)
Pins applied    : 0 (inventory only)
Next PR         : dependabot config + actual pin (deferred)
Track A impact  : none
```
