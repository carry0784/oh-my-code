# D-02: Staging Configuration Guide

**Card**: D-02
**Type**: Documentation (no code change)
**Date**: 2026-03-25

---

## 1. Purpose

This document defines the configuration differences between `dev` and `staging` environments. Staging mirrors production intent while using sandbox/testnet endpoints.

---

## 2. Environment Variables: Staging

Create `.env.staging` with the following configuration:

```env
# ── App ──────────────────────────────────────────────
APP_ENV=staging
DEBUG=false
SECRET_KEY=<generate-unique-staging-secret>

# ── Database ─────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://postgres:<staging-password>@<staging-host>:5432/trading_staging
DATABASE_URL_SYNC=postgresql://postgres:<staging-password>@<staging-host>:5432/trading_staging

# ── Redis ────────────────────────────────────────────
REDIS_URL=redis://<staging-host>:6379/0
CELERY_BROKER_URL=redis://<staging-host>:6379/1
CELERY_RESULT_BACKEND=redis://<staging-host>:6379/2

# ── Exchanges (TESTNET/SANDBOX ONLY) ─────────────────
BINANCE_API_KEY=<staging-testnet-key>
BINANCE_API_SECRET=<staging-testnet-secret>
BINANCE_TESTNET=true

OKX_API_KEY=<staging-sandbox-key>
OKX_API_SECRET=<staging-sandbox-secret>
OKX_PASSPHRASE=<staging-sandbox-passphrase>
OKX_SANDBOX=true

BITGET_API_KEY=<staging-sandbox-key>
BITGET_API_SECRET=<staging-sandbox-secret>
BITGET_PASSPHRASE=<staging-sandbox-passphrase>
BITGET_SANDBOX=true

KIS_APP_KEY=<staging-demo-key>
KIS_APP_SECRET=<staging-demo-secret>
KIS_ACCOUNT_NO=<staging-demo-account>
KIS_DEMO=true

KIWOOM_APP_KEY=<staging-demo-key>
KIWOOM_APP_SECRET=<staging-demo-secret>
KIWOOM_ACCOUNT_NO=<staging-demo-account>
KIWOOM_DEMO=true

# ── LLM ──────────────────────────────────────────────
ANTHROPIC_API_KEY=<staging-api-key>

# ── Governance ───────────────────────────────────────
GOVERNANCE_ENABLED=true
EVIDENCE_DB_PATH=./data/staging_evidence.db

# ── Notification ─────────────────────────────────────
RECEIPT_FILE_PATH=./data/staging_receipts.jsonl
NOTIFIER_WEBHOOK_URL=<staging-discord-webhook>
NOTIFIER_FILE_PATH=./data/staging_notifications.jsonl
NOTIFIER_SLACK_URL=<staging-slack-webhook>

# ── Logging ──────────────────────────────────────────
LOG_FILE_PATH=./logs/staging.log
LOG_LEVEL=INFO

# ── Trading ──────────────────────────────────────────
DEFAULT_EXCHANGE=binance
MAX_POSITION_SIZE_USD=100.0
RISK_LIMIT_PERCENT=1.0
```

---

## 3. Dev vs Staging Comparison

| Setting | Dev | Staging | Reason |
|---------|-----|---------|--------|
| `APP_ENV` | development | staging | Phase identification |
| `DEBUG` | true | false | No debug in staging |
| `SECRET_KEY` | change-me | unique generated | Security |
| `DATABASE_URL` | localhost | staging host | Separate DB |
| `BINANCE_TESTNET` | true | **true** | Staging uses testnet |
| `GOVERNANCE_ENABLED` | true | **true** | Mandatory |
| `EVIDENCE_DB_PATH` | (empty) | file path | Durable evidence |
| `RECEIPT_FILE_PATH` | (empty) | file path | Durable receipts |
| `LOG_FILE_PATH` | (empty) | file path | Persistent logs |
| `MAX_POSITION_SIZE_USD` | 1000 | 100 | Reduced staging risk |
| `RISK_LIMIT_PERCENT` | 2.0 | 1.0 | Tighter staging limit |

### Critical Staging Rules

1. **All exchange testnet/sandbox flags MUST remain `true`** in staging
2. **`GOVERNANCE_ENABLED` MUST be `true`** in staging
3. **`DEBUG` MUST be `false`** in staging
4. **Evidence and receipt persistence MUST be enabled** in staging

---

## 4. Staging vs Production Comparison

| Setting | Staging | Production | Change Required |
|---------|---------|------------|:---------------:|
| `APP_ENV` | staging | production | Yes |
| `BINANCE_TESTNET` | true | **false** | Yes |
| `OKX_SANDBOX` | true | **false** | Yes |
| `BITGET_SANDBOX` | true | **false** | Yes |
| `KIS_DEMO` | true | **false** | Yes |
| `KIWOOM_DEMO` | true | **false** | Yes |
| `MAX_POSITION_SIZE_USD` | 100 | per-strategy | Yes |
| `RISK_LIMIT_PERCENT` | 1.0 | per-strategy | Yes |
| Exchange API keys | testnet keys | **production keys** | Yes |
| Database | staging DB | **production DB** | Yes |

### Production Transition Warnings

- Changing testnet flags to `false` enables **real trading with real money**
- Production API keys must **never** be committed to version control
- Production database must be separately provisioned and backed up

---

## 5. Infrastructure: Staging

### 5.1 Docker Compose (staging override)

```yaml
# docker-compose.staging.yml
version: '3.8'
services:
  postgres:
    environment:
      POSTGRES_DB: trading_staging
      POSTGRES_PASSWORD: <staging-password>
  redis:
    command: redis-server --requirepass <staging-redis-password>
```

### 5.2 Data Directories

```bash
# Create staging data directories
mkdir -p data logs

# Verify write permissions
touch data/staging_evidence.db
touch data/staging_receipts.jsonl
touch data/staging_notifications.jsonl
touch logs/staging.log
```

---

## 6. Staging Startup Checklist

| # | Step | Command/Action | Verify |
|---|------|---------------|--------|
| 1 | Copy env file | `cp .env.staging .env` | File exists |
| 2 | Start infrastructure | `docker-compose up -d` | All services Up |
| 3 | Create data dirs | `mkdir -p data logs` | Dirs exist |
| 4 | Run migrations | `alembic upgrade head` | No errors |
| 5 | Start app | `uvicorn app.main:app --port 8000` | Startup logs clean |
| 6 | Check health | `GET /health` | 200 |
| 7 | Check readiness | `GET /ready` | 200 |
| 8 | Check governance | Startup log shows `governance_gate_initialized` | Present |
| 9 | Check evidence | Startup log shows `evidence_mode=SQLITE_PERSISTED` | Present |
| 10 | Check receipts | Startup log shows `receipt_mode=FILE_PERSISTED` | Present |
| 11 | Load dashboard | Visit `/dashboard` | Renders |
| 12 | Test notification | `POST /api/operator/retry-pass` | Returns JSON |

---

## 7. Staging Security Rules

1. **No production credentials** in staging environment
2. **No real trading** in staging (all testnet/sandbox)
3. **Staging secrets** must be different from production
4. **`.env.staging`** must not be committed to version control
5. **Staging database** must be separate from production

---

*Documented by Card D-02.*
