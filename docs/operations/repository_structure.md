# Repository Structure Map (K-V3)

**Created**: 2026-04-05
**Source session**: AELP v1 / Plan B / Item Q-3
**Parent plan**: `autonomous_execution_loop_plan.md` → `continuous_progress_plan_v1.md`
**Status**: STRUCTURE MAP — documentation of current layout, not a refactor.
**Purpose**: Provide a single reference for the K-V3 repository layout so that operators, reviewers, and autonomous agents can navigate, scope, and reason about changes without trial-and-error filesystem exploration.

---

## 1. Scope and caveat

### 1.1 What this document IS
- A snapshot of the current repository structure as of 2026-04-05
- A role / governance sensitivity annotation for each top-level path
- A reference for scoping decisions (which file belongs to which subsystem)

### 1.2 What this document is NOT
- **NOT** a proposed restructure
- **NOT** a justification for moving files
- **NOT** a replacement for `pyproject.toml` or `alembic.ini` definitions
- **NOT** a decision about the `app/` vs `src/kdexter/` dual-package question (that remains a future design review)

### 1.3 Dual-package caveat

The repository currently contains **two separate Python packages**:
- `app/` — FastAPI application core (NOT registered in `pyproject.toml`)
- `src/kdexter/` — `kdexter` package (REGISTERED in `pyproject.toml` via hatchling)

This is a **known structural asymmetry**, intentionally deferred as "별도 설계 검토" per the CI setup plan (`cozy-wishing-narwhal`). Unifying them is **out of scope** for all AELP v1 work.

---

## 2. Top-level tree

```
K-V3/
├── .github/                  # CI workflows + future CODEOWNERS
├── .claude/                  # Claude Code session state (gitignored mostly)
├── alembic/                  # DB migrations (24 version files)
├── app/                      # FastAPI application core — NOT in pyproject.toml
│   ├── agents/               # LLM agents (orchestrator, risk, signal validator)
│   ├── api/                  # HTTP layer
│   │   └── routes/           # 11 route modules
│   ├── core/                 # Config, database, logging
│   ├── exchanges/            # (exchange-related app helpers)
│   ├── models/               # 21 SQLAlchemy ORM models
│   ├── schemas/              # 39 Pydantic schemas
│   ├── services/             # 87 service modules (business logic)
│   ├── static/               # Static assets
│   ├── templates/            # Jinja templates
│   └── main.py               # FastAPI entry point
├── data/                     # Data files (gitignored)
├── docs/                     # Documentation
│   └── operations/           # Operational plans + evidence
│       └── evidence/         # 243 evidence files (immutable once sealed)
├── exchanges/                # CCXT wrappers (Binance, UpBit, Bitget, KIS, Kiwoom)
├── logs/                     # Runtime logs (gitignored)
├── scripts/                  # Helper scripts
├── src/                      # src-layout root
│   └── kdexter/              # `kdexter` package (REGISTERED in pyproject.toml)
│       ├── audit/
│       ├── config/
│       ├── engines/
│       ├── gates/
│       ├── governance/
│       ├── layers/
│       ├── ledger/
│       ├── loops/
│       ├── state_machine/
│       ├── strategy/
│       ├── tcl/
│       └── bootstrap.py
├── strategies/               # Trading strategy implementations
├── tests/                    # 197 test modules
├── workers/                  # Celery background tasks
│   └── tasks/                # 10 task modules
├── .env.example              # Env var template
├── .gitignore
├── CLAUDE.md                 # Project instructions for Claude Code
├── README.md                 # Repository readme
├── alembic.ini               # Alembic configuration
├── docker-compose.yml        # Postgres + Redis stack
├── pyproject.toml            # Python project metadata (registers `kdexter` only)
└── requirements.txt          # Runtime dependencies
```

---

## 3. Top-level path roles

| Path | Role | Governance sensitivity | Primary owners (role placeholder) |
|---|---|:---:|---|
| `app/` | FastAPI app core | 🔴 critical | trading-core, platform-owner |
| `app/api/routes/` | HTTP endpoints | 🔴 critical | trading-core |
| `app/services/` | Business logic (87 modules) | 🔴 critical | trading-core |
| `app/agents/` | LLM agents | 🔴 critical | trading-core |
| `app/models/` | ORM models (21 files) | 🔴 critical | trading-core |
| `app/schemas/` | Pydantic schemas (39 files) | 🟡 high | trading-core |
| `app/core/` | Config + DB + logging | 🔴 critical | security, platform-owner |
| `workers/` | Celery tasks (10 modules) | 🔴 critical | trading-core, observability |
| `exchanges/` | CCXT wrappers | 🔴 critical | trading-core, security |
| `strategies/` | Trading strategies | 🔴 critical | trading-core |
| `alembic/` | DB migrations (24 versions) | 🔴 critical | infra-ci, trading-core |
| `tests/` | pytest suite (197 files) | 🟡 high | trading-core |
| `docs/` | Operational docs | 🟡 high | docs-governance |
| `docs/operations/evidence/` | Governance evidence (243 files) | 🔴 critical | docs-governance, platform-owner |
| `.github/` | CI + future CODEOWNERS | 🔴 critical | infra-ci, platform-owner |
| `scripts/` | Helper scripts | 🟢 normal | infra-ci |
| `src/kdexter/` | `kdexter` package | 🟡 high | infra-ci, platform-owner |
| `data/` | Data files | 🟢 normal | - (mostly gitignored) |
| `logs/` | Runtime logs | 🟢 normal | - (gitignored) |

> Governance sensitivity scale: 🔴 critical (review required) / 🟡 high (review recommended) / 🟢 normal (standard PR review).

---

## 4. Subsystem descriptions

### 4.1 `app/` — FastAPI application core

Contains the live application. NOT registered in `pyproject.toml`; imports work via `PYTHONPATH=.` convention.

- **`app/main.py`**: FastAPI app factory, lifespan hooks
- **`app/core/`**: `config.py` (pydantic-settings), `database.py` (async SQLAlchemy), logging
- **`app/api/routes/`**: 11 modules — `orders.py`, `signals.py`, `positions.py`, `agents.py`, `ops.py`, `dashboard.py`, `market_state.py`, `registry.py`, `operator_retry.py`, `cr048_observatory.py`
- **`app/services/`**: 87 modules — largest subsystem; examples include `paper_trading_session_cr046.py`, `shadow_write_service.py` (Track A gated), `strategy_runner.py`, `performance_metrics.py`
- **`app/agents/`**: LLM agent layer — `orchestrator.py`, `signal_validator.py`, `risk_manager.py`, `governance_gate.py`, `action_ledger.py`
- **`app/models/`**: 21 ORM models incl. `order`, `signal`, `position`, `trade`, `paper_session`, `shadow_write_receipt`, `strategy_registry`
- **`app/schemas/`**: 39 Pydantic request/response schemas

### 4.2 `workers/` — Celery background tasks

- `celery_app.py`: Celery factory
- `tasks/`: 10 modules — `check_tasks.py`, `cycle_runner_tasks.py`, `data_collection_tasks.py`, `governance_monitor_tasks.py`, `market_tasks.py`, `order_tasks.py`, `shadow_observation_tasks.py`, `signal_tasks.py`, `snapshot_tasks.py`, `sol_paper_tasks.py` (CR-046)

### 4.3 `exchanges/` — CCXT wrappers

- `base.py`, `factory.py` (`ExchangeFactory.create("binance")`)
- Concrete: `binance.py`, `upbit.py`, `bitget.py`, `kis.py`, `kiwoom.py`
- Default testnet mode via `BINANCE_TESTNET=true`

### 4.4 `strategies/` — Trading strategies

- `base.py`: strategy interface
- `example_strategy.py`, `rsi_strategy.py`, `smc_wavetrend_strategy.py` (canonical CR-046)

### 4.5 `alembic/` — Migrations

- `env.py` (async-capable)
- `versions/`: 24 migration files
- Run via `alembic upgrade head`

### 4.6 `tests/` — pytest suite

- 197 test modules
- Current baseline: 4,214 pass / 1,231 skip, 66% coverage (per `ci_coverage_baseline.md`)
- `conftest.py` handles DB bootstrap with SQLite (via `aiosqlite`)

### 4.7 `src/kdexter/` — Secondary Python package

- REGISTERED in `pyproject.toml` via hatchling
- `__init__.py` exposes `__version__ = "0.1.0"`
- Subpackages: `audit`, `config`, `engines`, `gates`, `governance`, `layers`, `ledger`, `loops`, `state_machine`, `strategy`, `tcl`, `bootstrap.py`
- Purpose: alternative / parallel framework; actual runtime entry is `app.main` (FastAPI), not `kdexter`
- **Build job in CI verifies `import kdexter` works** as a packaging smoke test

### 4.8 `docs/operations/` — Operational docs

- `autonomous_execution_loop_plan.md`, `continuous_progress_plan_v1.md`, `session_operating_runbook.md`, `evidence_index.md`, `codeowners_draft.md`, `sha_pinning_inventory.md`, `ci_coverage_baseline.md`, `next_session_prompts.md`, `repository_structure.md` (this file)
- `evidence/`: 243 files — see `evidence_index.md`
- Various runbooks and receipts in top-level `docs/operations/`

### 4.9 `.github/` — CI + metadata

- `workflows/ci.yml`: 3 jobs (lint / test / build), concurrency cancel-in-progress enabled
- Future: `.github/CODEOWNERS` (draft only, activation blocked by B2-2)
- Future: `.github/dependabot.yml` (deferred per SHA pinning inventory)

---

## 5. Build and packaging facts

| Fact | Value | Source |
|---|---|---|
| Python version (runtime) | 3.11 | `ci.yml` |
| Build backend | hatchling | `pyproject.toml` |
| Registered package | `kdexter` (from `src/kdexter`) | `pyproject.toml` |
| Unregistered package | `app/` (runs via `PYTHONPATH=.`) | known asymmetry |
| DB | PostgreSQL (prod), SQLite via `aiosqlite` (tests) | `docker-compose.yml`, `conftest.py` |
| Queue | Redis broker, Celery worker + beat | `docker-compose.yml` |
| Tests | pytest 9.0.2 | `requirements.txt` |
| Coverage tool | pytest-cov 7.1.0 + coverage 7.13.5 | `requirements.txt` |
| Linter | ruff 0.15.9 (pinned in CI) | `ci.yml` |

---

## 6. Known asymmetries and deferred decisions

| # | Asymmetry | Deferred to | Reason |
|:---:|---|---|---|
| 1 | `app/` not in `pyproject.toml` | future design review | "kdexter vs app" unification needs scope analysis |
| 2 | `.github/CODEOWNERS` not activated | B2-2 unlock | dead-lock risk in single-operator environment |
| 3 | Dependabot not configured | post SHA-pin strategy PR | SHA pinning inventory only (B-3) |
| 4 | `--cov-fail-under` not enforced | future CI hardening PR | baseline-only (B-1) |
| 5 | SHA pins not applied | future supply-chain PR | inventory only (B-3) |
| 6 | Phase 5a paper session not started | A's explicit GO | preflight only (B-5) |

---

## 7. Scoping rules (applied for every PR)

When deciding whether a file is in-scope for a PR, consult this table:

| Target path | AELP Plan A/B/C (this cycle) | Track A (HOLD chain) |
|---|:---:|:---:|
| `docs/operations/*.md` (non-evidence) | ✅ | ✅ (only if plan change) |
| `docs/operations/evidence/*.md` (new file) | ✅ | ✅ |
| `docs/operations/evidence/*.md` (sealed file) | ❌ | ❌ |
| `.github/workflows/*.yml` | ✅ (AELP Plan A only) | ❌ |
| `app/services/shadow_write_service.py` | ❌ | ✅ (only on Track A unlock) |
| `app/services/paper_trading_session_cr046.py` | ❌ | ✅ (only on Phase 5a activation) |
| Any `app/` or `workers/` code | ❌ | ✅ (only by scope) |
| `tests/test_shadow_write_receipt.py` | ❌ | ✅ (only on Track A unlock) |
| `alembic/versions/*.py` | ❌ | ✅ (only on schema change approved) |
| `pyproject.toml`, `requirements.txt` | ❌ | ✅ (only on dependency change approved) |

---

## 8. What this PR does / does not do

### Does ✅
- Document current repository layout
- Annotate governance sensitivity per path
- List subsystem components and counts
- Record known asymmetries with deferral reasons
- Provide scoping rules table for future PRs

### Does NOT ❌
- Propose any restructure or unification
- Move, rename, or delete any file
- Modify `pyproject.toml`, `requirements.txt`, or any build config
- Touch Track A files
- Change `.github/workflows/ci.yml`

---

## 9. References

| 문서 | 역할 |
|---|---|
| `docs/operations/autonomous_execution_loop_plan.md` | AELP parent |
| `docs/operations/continuous_progress_plan_v1.md` | v1 source |
| `docs/operations/evidence_index.md` | Evidence navigation (Q-1) |
| `docs/operations/session_operating_runbook.md` | Session procedure (Q-2) |
| `docs/operations/codeowners_draft.md` | Role placeholder mapping |
| `docs/operations/ci_coverage_baseline.md` | Coverage baseline (B-1) |
| `docs/operations/sha_pinning_inventory.md` | SHA pinning inventory (B-3) |
| `pyproject.toml` | Package registration source of truth |
| `alembic.ini` | Migration source of truth |
| `docker-compose.yml` | Infra stack source of truth |

---

## Footer

```
Repository Structure Map
Plan ref         : AELP v1 / Plan B / Item Q-3
Created          : 2026-04-05
Top-level paths  : 18 annotated
Subsystems       : 9 described (app/, workers/, exchanges/, strategies/,
                   alembic/, tests/, src/kdexter/, docs/operations/, .github/)
Asymmetries      : 6 documented
Content changes  : 0 outside this file
Track A impact   : none
```
