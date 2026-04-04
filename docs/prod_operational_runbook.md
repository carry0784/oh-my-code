# D-03: Production Operational Runbook

**Card**: D-03
**Type**: Documentation (no code change)
**Date**: 2026-03-25

---

## 1. Purpose

This runbook defines production operational procedures. Production is the strictest operational tier. All procedures in this document are mandatory — deviation requires emergency override (L-03).

---

## 2. Startup Procedure

### 2.1 Pre-Start Checks

Before starting the production system, verify:

| # | Check | Command / Action | Required Result |
|---|-------|-----------------|-----------------|
| 1 | `.env` is prod config | Verify `APP_ENV=production` | Confirmed |
| 2 | Governance enabled | Verify `GOVERNANCE_ENABLED=true` | Confirmed |
| 3 | Debug disabled | Verify `DEBUG=false` | Confirmed |
| 4 | Testnet disabled | Verify `BINANCE_TESTNET=false` | Confirmed |
| 5 | Persistence configured | Verify `EVIDENCE_DB_PATH`, `RECEIPT_FILE_PATH`, `LOG_FILE_PATH` set | Confirmed |
| 6 | Infrastructure running | `docker-compose ps` | All Up |
| 7 | DB accessible | `alembic current` | No error |
| 8 | Data directories exist | `ls data/ logs/` | Exist |
| 9 | Audit passes | `pytest tests/test_a01_constitution_audit.py -q` | All pass |
| 10 | Regression passes | `pytest -q` | All pass |

**If any pre-start check fails, do NOT start the application.**

### 2.2 App Startup Order

```
1. Infrastructure (docker-compose up -d)
2. Database migration (python -m alembic upgrade head)
3. Pre-start audit (pytest audit + regression)
4. Application (uvicorn app.main:app --port 8000)
5. Celery worker (celery -A workers.celery_app worker)
6. Celery beat (celery -A workers.celery_app beat)
7. Post-start verification (health/ready/startup endpoints)
```

### 2.3 Post-Start Verification

| Endpoint | Expected | Action if Fail |
|----------|----------|----------------|
| `GET /health` | 200 | Restart app |
| `GET /ready` | 200 | Check DB/Redis/Gate |
| `GET /startup` | 200 | Wait or restart |
| `GET /status` | 200 | Investigate degraded_reasons |
| Dashboard | Loads | Check template/static files |

---

## 3. Runtime Monitoring

### 3.1 Continuous Checks

| Check | Frequency | Method |
|-------|-----------|--------|
| Health endpoint | Every 60s | `GET /health` |
| Status/degraded | Every 5 min | `GET /status` |
| Dashboard visual | Operator discretion | Browser |
| Log review | Hourly | `tail logs/prod.log` |
| Persistence size | Daily | `ls -la data/` |

### 3.2 Governance Checks

| Check | Frequency | Method |
|-------|-----------|--------|
| Gate initialized | On startup | Startup log |
| Evidence durable | On startup | Startup log |
| Audit enforcement | Weekly | Run A-01 tests |

### 3.3 Incident Detection

Monitor for:
- Incident overlay showing CRITICAL or LOCKDOWN
- Degraded status with persistent reasons
- Quote feed STALE for extended period
- Venue DISCONNECTED
- Loop ceiling exceeded
- Retry queue growing

---

## 4. Failure Procedures

### 4.1 Endpoint Failure

```
1. Check application process alive
2. Check DB connection
3. Check Redis connection
4. Check governance gate status
5. If recoverable: restart app
6. If not recoverable: invoke rollback (D-05)
```

### 4.2 Persistence Failure

```
1. Check disk space
2. Check file permissions
3. Check SQLite integrity
4. If data corrupted: preserve corrupted files, switch to backup
5. Document incident
```

### 4.3 Governance Failure

```
1. IMMEDIATE: Stop accepting new operations
2. Check governance gate initialization log
3. Check evidence store status
4. If governance cannot be restored: invoke emergency override (L-03)
5. Do NOT continue production with broken governance
```

### 4.4 Audit Failure

```
1. Run full audit: pytest tests/test_a01_constitution_audit.py -v
2. Identify failing test
3. Do NOT deploy fixes without card
4. If critical boundary violation: invoke emergency stop
5. Create repair card
```

---

## 5. Rollback / Brake Procedure

See D-05 (`prod_rollback_override_procedure.md`) for detailed procedure.

### Quick Reference

| Condition | Action |
|-----------|--------|
| Governance broken | Immediate stop |
| Persistence broken | Immediate stop |
| Config mismatch | Immediate stop |
| Audit failure | Stop, investigate |
| Regression failure | Stop, repair card |
| Endpoint all failing | Restart, then escalate |

---

## 6. Operator Responsibilities

### 6.1 Authorization Matrix

| Action | Who May Perform |
|--------|----------------|
| Start production | Authorized operator with sign-off |
| Stop production | Any operator (safety action) |
| Approve changes | Reviewer with card authority |
| Invoke emergency override | Authorized operator (L-03 rules) |
| Record incident receipt | Operating operator |
| Rollback | Any operator (safety action) |

### 6.2 Operator Daily Checklist

| # | Check | Method |
|---|-------|--------|
| 1 | System health | `GET /health` → 200 |
| 2 | System readiness | `GET /ready` → 200 |
| 3 | Dashboard loads | Visit `/dashboard` |
| 4 | No critical incidents | Check incident overlay |
| 5 | Data freshness | Check freshness timeline |
| 6 | Venue connectivity | Check venue status |
| 7 | Retry queue | Check retry status |
| 8 | Log errors | Review recent ERROR entries |
| 9 | Persistence files | Verify files exist and grow |
| 10 | Governance gate | Verify gate initialized |

---

## 7. Forbidden Actions

1. No ad-hoc config edits without card
2. No direct code edits without card
3. No ungated restart (must verify pre-start checks)
4. No prod without operator sign-off
5. No prod without audit evidence
6. No testnet-to-production switch without explicit card
7. No credential changes without documentation
8. No persistence path changes without documentation
9. No log level changes without documentation
10. No silent incident (all incidents must be documented)

---

## 8. Relation to Phase Activation

Production activation is forbidden without this runbook being:
- Created
- Reviewed
- Referenced in the prod activation card

---

*Documented by Card D-03.*
