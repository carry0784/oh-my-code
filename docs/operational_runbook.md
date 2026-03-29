# D-01: Operational Runbook

**Card**: D-01
**Type**: Documentation (no code change)
**Date**: 2026-03-25

---

## 1. System Startup

### 1.1 Infrastructure

```bash
# Start PostgreSQL, Redis, Flower
docker-compose up -d

# Verify services
docker-compose ps
# Expected: postgres (5432), redis (6379), flower (5555) all Up
```

### 1.2 Database

```bash
# Run migrations
alembic upgrade head

# Verify migration status
alembic current
```

### 1.3 Application

```bash
# Start FastAPI server
uvicorn app.main:app --reload --port 8000

# Verify startup logs:
#   - "Starting trading system" with env, log_mode
#   - "evidence_store_initialized" with evidence_mode
#   - "receipt_store_initialized" with receipt_mode
#   - "governance_gate_initialized" (if governance enabled)
```

### 1.4 Background Workers

```bash
# Start Celery worker
celery -A workers.celery_app worker --loglevel=info

# Start Celery beat scheduler
celery -A workers.celery_app beat --loglevel=info
```

### 1.5 Post-Startup Verification

| Check | Endpoint | Expected |
|-------|----------|----------|
| Health | `GET /health` | 200 OK |
| Readiness | `GET /ready` | 200 OK (all checks pass) |
| Startup | `GET /startup` | 200 OK |
| Status | `GET /status` | overall_status present |
| Dashboard | `GET /dashboard` | HTML page loads |

---

## 2. System Shutdown

### 2.1 Graceful Shutdown

```bash
# Stop application (Ctrl+C or SIGTERM)
# Stop workers
celery -A workers.celery_app control shutdown

# Stop infrastructure
docker-compose down
```

### 2.2 Data Preservation

Before shutdown, verify:

- No pending orders in execution
- Receipt store flushed (if file-backed)
- Celery queue drained

---

## 3. Health Check Procedures

### 3.1 Probe Endpoints

| Probe | Endpoint | Purpose | Failure Action |
|-------|----------|---------|----------------|
| Liveness | `GET /health` | Process alive | Restart service |
| Readiness | `GET /ready` | Dependencies ready | Check DB/Redis/Gate |
| Startup | `GET /startup` | Init complete | Wait or restart |
| Status | `GET /status` | Degraded detection | Investigate degraded_reasons |

### 3.2 Dashboard Monitoring

Access `http://localhost:8000/dashboard` for:

- Loop ceiling monitor
- Quote feed status
- Venue connectivity
- Incident overlay (highest severity)
- Freshness timeline
- Source provenance
- Operator triage checklist
- Handoff receipt
- Incident chronology

### 3.3 Retry System Status

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/operator/retry-status` | GET | Pending retry count, queue summary |
| `/api/operator/retry-pass` | POST | Trigger manual retry pass |

---

## 4. Common Troubleshooting

### 4.1 Database Connection Failed

```
Symptom: /ready returns 503, DB check fails
Action:
  1. Verify PostgreSQL is running: docker-compose ps
  2. Check DATABASE_URL in .env
  3. Test connection: psql -h localhost -U postgres -d trading
  4. Restart if needed: docker-compose restart postgres
```

### 4.2 Governance Gate Disabled Warning

```
Symptom: "governance_gate_disabled" in logs
Action:
  1. Check GOVERNANCE_ENABLED in .env
  2. In production, this MUST be true (app will fail-fast if false)
  3. In dev/staging, warning is acceptable
```

### 4.3 Receipt Store in Memory-Only Mode

```
Symptom: receipt_mode="IN_MEMORY" in startup logs
Action:
  1. Set RECEIPT_FILE_PATH in .env for persistence
  2. Verify write permissions to target path
  3. Restart application
```

### 4.4 Webhook/Notification Delivery Failures

```
Symptom: Receipts show delivered=False for external channel
Action:
  1. Check NOTIFIER_WEBHOOK_URL in .env
  2. Verify webhook endpoint is reachable
  3. Check /api/operator/retry-status for pending retries
  4. Trigger manual retry: POST /api/operator/retry-pass
```

### 4.5 Exchange Connectivity Issues

```
Symptom: Venue status shows DISCONNECTED
Action:
  1. Verify exchange API keys in .env
  2. Check testnet/sandbox mode settings
  3. Verify network connectivity to exchange
  4. Check rate limiter status
```

---

## 5. Operator Daily Checklist

| # | Check | How |
|---|-------|-----|
| 1 | System health | `GET /health` → 200 |
| 2 | System readiness | `GET /ready` → 200 |
| 3 | Dashboard loads | Visit `/dashboard` |
| 4 | No critical incidents | Check incident overlay |
| 5 | Data freshness | Check freshness timeline (no STALE) |
| 6 | Venue connectivity | Check venue status (no DISCONNECTED) |
| 7 | Retry queue | `GET /api/operator/retry-status` → low pending count |
| 8 | Log errors | Review recent log output for ERROR level |

---

## 6. Configuration Reference

| Variable | Default | Purpose |
|----------|---------|---------|
| `APP_ENV` | development | Environment name |
| `DEBUG` | false | Debug mode |
| `DATABASE_URL` | postgresql+asyncpg://... | Async DB connection |
| `REDIS_URL` | redis://localhost:6379/0 | Redis connection |
| `GOVERNANCE_ENABLED` | true | Governance gate active |
| `EVIDENCE_DB_PATH` | (empty) | SQLite evidence path |
| `RECEIPT_FILE_PATH` | (empty) | JSONL receipt path |
| `NOTIFIER_WEBHOOK_URL` | (empty) | Discord/webhook URL |
| `NOTIFIER_FILE_PATH` | (empty) | File notifier path |
| `NOTIFIER_SLACK_URL` | (empty) | Slack webhook URL |
| `LOG_FILE_PATH` | (empty) | Log file path |
| `LOG_LEVEL` | INFO | Log level |
| `BINANCE_TESTNET` | true | Binance testnet mode |
| `BITGET_SANDBOX` | true | Bitget sandbox mode |
| `KIS_DEMO` | true | KIS demo mode |
| `KIWOOM_DEMO` | true | Kiwoom demo mode |
| `DEFAULT_EXCHANGE` | binance | Default exchange |
| `MAX_POSITION_SIZE_USD` | 1000.0 | Max position size |
| `RISK_LIMIT_PERCENT` | 2.0 | Risk limit percentage |

---

*Documented by Card D-01.*
