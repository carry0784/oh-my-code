# CODEOWNERS Draft (Pre-activation for B2-2)

**Created**: 2026-04-05
**Source session**: AELP v1 / Plan A / Item A4 (B-4)
**Parent plan**: `autonomous_execution_loop_plan.md` → `continuous_progress_plan_v1.md` §4.4
**Status**: DRAFT — `.github/CODEOWNERS` is **NOT** created in this PR.
**Purpose**: Prepare a mapped ownership draft so that when B2-2 (Ruleset Phase 2 approvals=1) unlocks, a second PR can activate `.github/CODEOWNERS` in under 5 minutes.

---

## 1. Why this is DRAFT only

`.github/CODEOWNERS` is a **functional file** — GitHub reads it automatically and enforces review requirements against it. Creating it now (before B2-2 unlock + collaborator presence) causes **two immediate problems**:

1. **Dead-lock risk in single-operator environment**: The current repository has one active operator. A live CODEOWNERS assigning that same operator to every path would block the operator from self-merging their own PRs. See `next_session_prompts.md` BLOCK condition.
2. **Premature enforcement coupling**: CODEOWNERS enforcement ties to "Require review from Code Owners" ruleset checkbox. Enabling CODEOWNERS without that checkbox is meaningless; enabling both without a collaborator is dead-lock.

Therefore this document is a **preparation artifact** only. Activation trigger is B2-2.

---

## 2. Repository structure mapping

### 2.1 Top-level directories (current)

| Directory | Role | Governance sensitivity |
|---|---|:---:|
| `app/` | FastAPI application core (api, services, agents, models, schemas) | 🔴 critical |
| `workers/` | Celery background tasks (signal / order / market sync) | 🔴 critical |
| `exchanges/` | CCXT exchange wrappers (Binance, UpBit, Bitget, KIS, Kiwoom) | 🔴 critical |
| `strategies/` | Trading strategy implementations | 🔴 critical |
| `tests/` | pytest test suite | 🟡 high |
| `alembic/` | DB migrations | 🔴 critical |
| `docs/` | Operational documentation | 🟡 high |
| `docs/operations/evidence/` | Governance chain evidence / receipts | 🔴 critical (LOCK-sensitive) |
| `.github/` | CI workflows, issue templates, CODEOWNERS (future) | 🔴 critical |
| `scripts/` | Helper scripts | 🟢 normal |
| `src/` | `kdexter` package | 🟡 high |
| `data/` | Data files (gitignored usually) | 🟢 normal |
| `logs/` | Runtime log output | 🟢 normal |

### 2.2 Role definitions (placeholder — NOT mapped to actual GitHub accounts)

| Role symbol | Responsibility | Authority |
|---|---|---|
| `@role/platform-owner` | Overall architecture, governance chain | highest |
| `@role/trading-core` | `app/services`, `strategies/`, `exchanges/` | high |
| `@role/infra-ci` | `.github/`, `alembic/`, `requirements.txt`, `pyproject.toml` | high |
| `@role/docs-governance` | `docs/operations/evidence/`, receipt conventions | high |
| `@role/observability` | metrics, logging, runtime status | medium |
| `@role/security` | secret handling, env config, auth | high |

> These role symbols are **placeholders**. Real CODEOWNERS uses GitHub usernames or team handles (`@org/team`). Mapping role → real handle happens during B2-2 activation.

---

## 3. Proposed CODEOWNERS content (DRAFT, not yet a functional file)

```codeowners
# CODEOWNERS — DRAFT (not yet activated)
# Activation trigger: B2-2 Ruleset Phase 2 + collaborator presence
# Policy: most-specific path wins; last match for a path determines ownership.

# ============================================================
# Default catch-all
# ============================================================
*                                      @role/platform-owner

# ============================================================
# Application core
# ============================================================
/app/                                  @role/trading-core @role/platform-owner
/app/api/                              @role/trading-core
/app/services/                         @role/trading-core
/app/agents/                           @role/trading-core
/app/models/                           @role/trading-core
/app/schemas/                          @role/trading-core
/app/core/config.py                    @role/security @role/platform-owner

# ============================================================
# Workers (Celery, scheduled tasks)
# ============================================================
/workers/                              @role/trading-core @role/observability

# ============================================================
# Exchange integrations
# ============================================================
/exchanges/                            @role/trading-core @role/security

# ============================================================
# Strategies
# ============================================================
/strategies/                           @role/trading-core

# ============================================================
# Database migrations
# ============================================================
/alembic/                              @role/infra-ci @role/trading-core

# ============================================================
# Tests
# ============================================================
/tests/                                @role/trading-core

# ============================================================
# CI / Infra / Meta
# ============================================================
/.github/                              @role/infra-ci @role/platform-owner
/.github/workflows/                    @role/infra-ci
/requirements.txt                      @role/infra-ci
/pyproject.toml                        @role/infra-ci
/docker-compose.yml                    @role/infra-ci
/alembic.ini                           @role/infra-ci

# ============================================================
# Documentation
# ============================================================
/docs/                                 @role/docs-governance
/docs/operations/                      @role/docs-governance @role/platform-owner
/docs/operations/evidence/             @role/docs-governance @role/platform-owner
/CLAUDE.md                             @role/platform-owner
/README.md                             @role/docs-governance

# ============================================================
# Source layout (kdexter package)
# ============================================================
/src/                                  @role/infra-ci @role/platform-owner

# ============================================================
# Environment / secrets (review by security role)
# ============================================================
/.env*                                 @role/security @role/platform-owner
```

---

## 4. Activation procedure (for future B2-2 PR)

When B2-2 unlocks (collaborator confirmed + ruleset approvals=1 enabled):

1. **Replace placeholder roles with real GitHub handles**
   - Example: `@role/platform-owner` → `@carry0784` (or `@carry0784/core`)
   - Keep a 1-to-1 mapping table in the activation PR body
2. **Create `.github/CODEOWNERS`** from the above draft with real handles
3. **Verify syntax** via `gh codeowners list` (or GitHub UI) before merge
4. **Enable "Require review from Code Owners"** in the main ruleset
5. **Test with a throwaway PR** to confirm ownership matching works
6. **Record activation receipt** as `docs/operations/evidence/b4_codeowners_activation_receipt.md`

---

## 5. Risks to avoid during activation

| Risk | Mitigation |
|---|---|
| Activating CODEOWNERS before collaborator exists | **Wait for B2-2 unlock** (no collaborator = dead-lock) |
| Single owner catching every path | Use multiple role handles per path |
| Stale role mapping | Review mapping table every quarter |
| Secret file paths under wrong role | `.env*` under `@role/security` explicitly |
| `/.github/CODEOWNERS` self-ownership missing | Always assign `@role/platform-owner` to `.github/` |
| Bypass list self-addition | **Never add self to ruleset bypass list** (per PR-B spec) |

---

## 6. What this PR does / does not do

### Does ✅
- Map the current repository structure to logical ownership roles
- Provide a paste-ready CODEOWNERS draft (with placeholder roles)
- Document the activation procedure
- List risks and mitigations

### Does NOT ❌
- Create `.github/CODEOWNERS` (functional file)
- Map any placeholder role to a real GitHub account
- Enable "Require review from Code Owners" ruleset
- Add any bypass entries
- Modify any existing workflow or source code
- Unblock B2-2 (still needs collaborator)

---

## 7. References

| 문서 | 역할 |
|---|---|
| `docs/operations/autonomous_execution_loop_plan.md` | Plan A parent |
| `docs/operations/continuous_progress_plan_v1.md` §4.4 | B-4 원본 명세 |
| `docs/operations/next_session_prompts.md` | PR-B BLOCK 조건 / 협업자 요건 |
| GitHub CODEOWNERS 공식 문서 | 문법 레퍼런스 |

---

## Footer

```
CODEOWNERS Draft Document
Plan ref        : AELP v1 / Plan A / Item A4 (B-4)
Created         : 2026-04-05
Functional file : NOT YET CREATED (activation trigger = B2-2 unlock)
Placeholder roles: 6 (to be mapped to real handles at activation)
Path rules      : 19 (catch-all + 18 specific)
Next PR         : activation PR (blocked by B2-2 / collaborator)
Track A impact  : none
```
