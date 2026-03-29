# D-04: Production Configuration Guide

**Card**: D-04
**Type**: Documentation (no code change)
**Date**: 2026-03-25

---

## 1. Purpose

This document defines production configuration requirements and separation rules. Production configuration is the most sensitive tier — misconfiguration can cause real financial loss.

---

## 2. Environment Separation

### 2.1 Three-Environment Matrix

| Resource | Dev | Staging | Production |
|----------|-----|---------|------------|
| Config file | `.env` (local) | `.env.staging` | `.env.production` |
| APP_ENV | development | staging | **production** |
| Database | trading (local) | trading_staging | **trading_prod** |
| Exchange mode | testnet | testnet | **LIVE** |
| Exchange keys | test keys | test keys | **REAL keys** |
| Secrets | dev-only | staging-only | **prod-only** |
| Evidence store | in-memory | SQLite | **SQLite (backed up)** |
| Receipt store | in-memory | JSONL | **JSONL (backed up)** |
| Logs | stdout | file | **file (rotated, preserved)** |

### 2.2 Strict Separation Rules

1. **No shared secrets** across any environment
2. **No shared database** across any environment
3. **No shared exchange keys** across any environment
4. **No config file reuse** across environments
5. `.env.production` must **NEVER** be committed to version control
6. Production credentials must be stored in secure vault, not in files

---

## 3. Required Production Variables

```env
# ── App ──────────────────────────────────────────────
APP_ENV=production
DEBUG=false
SECRET_KEY=<cryptographically-random-production-secret>

# ── Database ─────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://<prod-user>:<prod-pass>@<prod-host>:5432/trading_prod
DATABASE_URL_SYNC=postgresql://<prod-user>:<prod-pass>@<prod-host>:5432/trading_prod

# ── Redis ────────────────────────────────────────────
REDIS_URL=redis://<prod-host>:6379/0
CELERY_BROKER_URL=redis://<prod-host>:6379/1
CELERY_RESULT_BACKEND=redis://<prod-host>:6379/2

# ── Exchanges (PRODUCTION — REAL MONEY) ──────────────
BINANCE_API_KEY=<production-key>
BINANCE_API_SECRET=<production-secret>
BINANCE_TESTNET=false          # ⚠️ REAL TRADING

# (repeat for each exchange in use)

# ── Governance ───────────────────────────────────────
GOVERNANCE_ENABLED=true        # MANDATORY in production
EVIDENCE_DB_PATH=./data/prod_evidence.db

# ── Notification ─────────────────────────────────────
RECEIPT_FILE_PATH=./data/prod_receipts.jsonl
NOTIFIER_WEBHOOK_URL=<production-webhook>
NOTIFIER_FILE_PATH=./data/prod_notifications.jsonl
NOTIFIER_SLACK_URL=<production-slack-webhook>

# ── Logging ──────────────────────────────────────────
LOG_FILE_PATH=./logs/prod.log
LOG_LEVEL=INFO

# ── Trading ──────────────────────────────────────────
DEFAULT_EXCHANGE=binance
MAX_POSITION_SIZE_USD=<production-limit>
RISK_LIMIT_PERCENT=<production-risk-limit>
```

---

## 4. Source Priority

| Priority | Source | Notes |
|:--------:|--------|-------|
| 1 | Environment variables | Runtime overrides (highest) |
| 2 | `.env.production` file | Production defaults |
| 3 | `app/core/config.py` defaults | Fallback (dev-oriented) |

### 4.1 Forbidden Fallback

- Production must **never** fall back to `config.py` defaults for critical settings
- `APP_ENV`, `GOVERNANCE_ENABLED`, exchange testnet flags must be explicitly set
- If `.env.production` is missing, the system must refuse to start (governance fail-fast)

---

## 5. Forbidden Configuration Patterns

1. **Floating env source**: Config from unknown origin
2. **Mixed environment secrets**: Staging keys in prod, or vice versa
3. **Temporary overrides**: "Just for now" config changes without card
4. **Manual hot edit**: Editing `.env` on running server without card
5. **Testnet flags in prod**: `BINANCE_TESTNET=true` in production is invalid
6. **Governance disabled**: `GOVERNANCE_ENABLED=false` causes fail-fast in production
7. **Debug enabled**: `DEBUG=true` in production is forbidden
8. **Default secret key**: `change-me-in-production` must be replaced

---

## 6. Verification Checklist

Before production activation, verify:

| # | Check | Evidence |
|---|-------|---------|
| 1 | `APP_ENV=production` | Settings reload output |
| 2 | `DEBUG=false` | Settings reload output |
| 3 | `GOVERNANCE_ENABLED=true` | Settings reload output |
| 4 | All testnet flags `false` | Settings reload output |
| 5 | Production DB accessible | `alembic current` |
| 6 | Production Redis accessible | `redis-cli ping` |
| 7 | `data/` directory exists | `ls data/` |
| 8 | `logs/` directory exists | `ls logs/` |
| 9 | Evidence DB path set | Settings reload output |
| 10 | Receipt file path set | Settings reload output |
| 11 | Log file path set | Settings reload output |
| 12 | Secret key not default | Settings reload output |
| 13 | Exchange keys are production | Manual verification (not logged) |

---

## 7. Relation to Prod Activation

Production activation is forbidden without:
- This configuration guide being followed
- Configuration verification checklist being completed
- `APP_ENV=production` evidence attached

---

*Documented by Card D-04.*
