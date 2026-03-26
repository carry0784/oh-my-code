# I-01: Staging Infrastructure Provision Specification

**Card**: I-01
**Type**: Infrastructure Documentation (no code change)
**Date**: 2026-03-25
**Baseline**: 1673 passed, 0 failed

---

## 1. Purpose

This document defines the infrastructure requirements for the K-V3 staging environment. It ensures:

- Dev and staging environments are fully separated
- Staging runtime is reproducible
- Phase transition (P-02) has a verifiable infrastructure baseline
- No staging operation begins without documented infrastructure

This document does not implement infrastructure. It specifies what must exist before P-02 can proceed.

---

## 2. Environment Separation

### 2.1 Separation Matrix

| Resource | Dev | Staging | Shared |
|----------|-----|---------|:------:|
| Configuration file | `.env` (local) | `.env.staging` | No |
| Secrets | dev-only keys | staging-only keys | No |
| Database | `trading` (local) | `trading_staging` (staging host) | No |
| Redis | localhost:6379 | staging-host:6379 | No |
| Exchange keys | testnet/sandbox | testnet/sandbox (separate keys) | No |
| Log files | stdout only | `./logs/staging.log` | No |
| Evidence store | in-memory | `./data/staging_evidence.db` | No |
| Receipt store | in-memory | `./data/staging_receipts.jsonl` | No |
| Notification files | none | `./data/staging_notifications.jsonl` | No |

### 2.2 Separation Rules

1. **No shared secrets** between dev and staging
2. **No shared database** between dev and staging
3. **No shared log files** between dev and staging
4. **No shared data directories** between dev and staging
5. **Configuration files must be named differently** (`.env` vs `.env.staging`)
6. `.env.staging` must **never** be committed to version control

### 2.3 Runtime Flags

| Flag | Dev | Staging |
|------|-----|---------|
| `APP_ENV` | development | staging |
| `DEBUG` | true | **false** |
| `GOVERNANCE_ENABLED` | true | **true** (mandatory) |
| `BINANCE_TESTNET` | true | **true** (mandatory in staging) |
| `OKX_SANDBOX` | true | **true** (mandatory in staging) |
| `BITGET_SANDBOX` | true | **true** (mandatory in staging) |
| `KIS_DEMO` | true | **true** (mandatory in staging) |
| `KIWOOM_DEMO` | true | **true** (mandatory in staging) |

---

## 3. Required Runtime Components

### 3.1 Language and Runtime

| Component | Requirement |
|-----------|-------------|
| Python | 3.12+ (match dev version exactly) |
| pip | Latest stable |
| venv/virtualenv | Isolated environment required |

### 3.2 Infrastructure Services

| Service | Version | Port | Purpose |
|---------|---------|------|---------|
| PostgreSQL | 16+ | 5432 | Primary database |
| Redis | 7+ | 6379 | Cache, Celery broker |

### 3.3 Application Components

| Component | Required | Command |
|-----------|:--------:|---------|
| FastAPI server | Yes | `uvicorn app.main:app --port 8000` |
| Celery worker | Yes | `celery -A workers.celery_app worker` |
| Celery beat | Yes | `celery -A workers.celery_app beat` |

### 3.4 Data Storage

| Path | Purpose | Required |
|------|---------|:--------:|
| `./data/` | Evidence DB, receipts, notifications | Yes |
| `./logs/` | Application logs | Yes |

### 3.5 Network Access

| Direction | Target | Purpose | Required |
|-----------|--------|---------|:--------:|
| Outbound | Exchange testnet APIs | Order submission, market data | Yes |
| Outbound | Webhook URLs | Notification delivery | Optional |
| Outbound | Slack API | Slack notifications | Optional |
| Inbound | Port 8000 | API and dashboard access | Yes |
| Inbound | Port 5555 | Flower monitoring | Optional |

---

## 4. Dependency Pin Policy

### 4.1 Rules

1. `requirements.txt` must contain **pinned versions** (e.g., `fastapi==0.104.1`)
2. **No floating versions** (e.g., `fastapi>=0.104` is forbidden)
3. **No implicit upgrades** during staging deployment
4. Staging must install from the **same `requirements.txt`** as dev
5. `pip install -r requirements.txt` must produce identical results on dev and staging

### 4.2 Verification

```bash
# Generate lock from dev environment
pip freeze > requirements.lock

# Compare against requirements.txt
diff <(sort requirements.txt) <(sort requirements.lock)

# Install in staging from same file
pip install -r requirements.txt --no-deps
```

### 4.3 Update Policy

- Dependency updates require a C-series card
- Updates must be tested in dev before staging
- Full regression must pass after any dependency change

---

## 5. Configuration Rules

### 5.1 Configuration Source

| Priority | Source | Purpose |
|:--------:|--------|---------|
| 1 | Environment variables | Runtime overrides |
| 2 | `.env.staging` file | Staging defaults |
| 3 | `app/core/config.py` defaults | Fallback values |

### 5.2 Staging Overrides

All staging-specific values are defined in D-02 (`staging_configuration_guide.md`). This document does not duplicate those values but requires that document to be followed.

### 5.3 Forbidden Actions

1. **Never edit `app/core/config.py` defaults** to accommodate staging
2. **Never hardcode staging values** in production code
3. **Never commit `.env.staging`** to version control
4. **Never use dev `.env`** in staging environment
5. **Never disable governance** in staging (`GOVERNANCE_ENABLED=true` mandatory)

---

## 6. Startup Procedure (Staging)

### 6.1 First-Time Setup

```
Step 1: Clone repository
Step 2: Create virtual environment
Step 3: pip install -r requirements.txt
Step 4: Copy .env.staging to .env
Step 5: Create data directories (mkdir -p data logs)
Step 6: Start infrastructure (docker-compose up -d)
Step 7: Run database migrations (alembic upgrade head)
Step 8: Run audit (pytest tests/test_a01_constitution_audit.py -v)
Step 9: Run full regression (pytest -q)
Step 10: Start application (uvicorn app.main:app --port 8000)
Step 11: Verify health endpoints (/health, /ready, /startup)
Step 12: Verify dashboard loads (/dashboard)
```

### 6.2 Regular Startup

```
Step 1: Activate virtual environment
Step 2: Verify .env is staging config (APP_ENV=staging)
Step 3: Start infrastructure (docker-compose up -d)
Step 4: Start application
Step 5: Verify health endpoints
```

### 6.3 Pre-Startup Audit

Before every staging startup, verify:

```bash
# Constitution audit
pytest tests/test_a01_constitution_audit.py -q

# Boundary lock
pytest tests/test_c40_execution_boundary_lock.py -q

# Full regression
pytest -q
```

All must pass before staging operation begins.

---

## 7. Verification Checklist

Before staging is considered provisioned, verify:

| # | Item | How to Verify |
|---|------|--------------|
| 1 | Constitution active | `docs/system_final_constitution.md` exists |
| 2 | Laws frozen | `docs/system_law_freeze.md` exists |
| 3 | All seals present | 5 seal documents in `docs/` |
| 4 | A-01 audit passes | `pytest tests/test_a01_constitution_audit.py` → all pass |
| 5 | C-40 boundary passes | `pytest tests/test_c40_execution_boundary_lock.py` → all pass |
| 6 | Full regression clean | `pytest -q` → 0 failures |
| 7 | Runbook present | `docs/operational_runbook.md` exists |
| 8 | Config guide present | `docs/staging_configuration_guide.md` exists |
| 9 | Dependencies documented | `requirements.txt` with pinned versions |
| 10 | `.env.staging` prepared | File exists with staging values (not committed) |
| 11 | Data directories created | `data/` and `logs/` exist with write permissions |
| 12 | Database accessible | `alembic current` succeeds |
| 13 | Redis accessible | `redis-cli ping` returns PONG |
| 14 | Health endpoint OK | `GET /health` → 200 |
| 15 | Readiness endpoint OK | `GET /ready` → 200 |
| 16 | Governance active | Startup log shows `governance_gate_initialized` |

---

## 8. Forbidden Actions

The following actions are forbidden in the staging infrastructure context:

1. **Running staging without prior audit** (A-01 must pass)
2. **Running staging with dev configuration** (`.env` must be staging)
3. **Editing code without a card** (L-02 change protocol applies)
4. **Changing law without a law card** (L-series required)
5. **Changing seal without a seal card** (constitutional card required)
6. **Disabling governance in staging** (GOVERNANCE_ENABLED must be true)
7. **Using production exchange keys in staging** (testnet/sandbox only)
8. **Sharing secrets between environments** (separate keys required)
9. **Skipping regression before staging operation** (full test required)
10. **Deploying uncommitted or unreviewed code** (card process required)

---

## 9. Relation to P-02

This document (I-01) is a **prerequisite** for P-02 (Phase Transition Card).

- P-02 cannot be approved until this specification is followed
- P-02 must verify all items in Section 7
- P-02 must confirm infrastructure separation per Section 2
- No phase transition occurs without infrastructure provision

### Dependency Chain

```
D-01 (Runbook) + D-02 (Config Guide) → S-02 (Approval)
  → I-01 (Infra Spec) → P-02 (Phase Transition)
```

---

## 10. No Behavior Change Declaration

This document is **documentation only**.

- **No runtime code was changed** by this card
- **No production behavior was modified** by this card
- **No tests were added or modified** by this card
- **No seals, laws, or constitution were altered** by this card
- **No configuration defaults were changed** by this card

This card specifies infrastructure requirements. It does not implement them.

---

*Specified by Card I-01. Infrastructure provisioning is an operational action, not a code action.*
