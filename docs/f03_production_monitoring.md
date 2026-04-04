# F-03: Production Monitoring Rules

**Card**: F-03
**Type**: Operational Rule (no code change)
**Date**: 2026-03-25
**Phase**: prod

---

## 1. Fundamental Monitoring Principles

Production must always be:

- **Observable** — every critical state is visible
- **Auditable** — every change produces verifiable evidence
- **Stoppable** — immediate shutdown is always available

---

## 2. Health Check Rules

| Check | Endpoint | Frequency | Action on Failure |
|-------|----------|-----------|-------------------|
| Liveness | `GET /health` | Every 60s | Restart application |
| Startup | `GET /startup` | On boot | Wait, then investigate |
| Status | `GET /status` | Every 5 min | Check `degraded_reasons` |
| Dashboard | `GET /dashboard` | Every 30 min | Check template/static |

### Escalation

- 1 failed health check → retry in 30s
- 3 consecutive failures → restart application
- Restart fails → invoke rollback (D-05)

---

## 3. Log Rules

| Rule | Requirement |
|------|-------------|
| Log destination | File (`LOG_FILE_PATH`) + stdout |
| Log level | INFO minimum in production |
| Log rotation | Recommended: daily or size-based |
| Log preservation | Never delete active logs |
| Log review | Operator reviews ERROR entries at least daily |
| Log evidence | Logs must survive restart |

### Forbidden

- Disabling file logging in production
- Setting log level to DEBUG in production without card
- Deleting log files while system is running
- Redirecting logs to `/dev/null`

---

## 4. Receipt Rules

| Rule | Requirement |
|------|-------------|
| Receipt storage | JSONL file (`RECEIPT_FILE_PATH`) |
| Receipt durability | Must survive restart |
| Receipt review | Operator reviews delivery outcomes weekly |
| Receipt preservation | Never delete receipt files |

---

## 5. Evidence Rules

| Rule | Requirement |
|------|-------------|
| Evidence storage | SQLite (`EVIDENCE_DB_PATH`) |
| Evidence durability | DURABLE mode required |
| Evidence backup | Recommended: daily backup |
| Evidence preservation | Never delete evidence database |
| Evidence integrity | SQLite integrity check monthly |

---

## 6. Audit Interval

| Audit Type | Frequency | Command |
|------------|-----------|---------|
| Constitution audit (A-01) | Weekly | `pytest tests/test_a01_constitution_audit.py -q` |
| Boundary lock (C-40) | Weekly | `pytest tests/test_c40_execution_boundary_lock.py -q` |
| Production integrity (F-02) | Weekly | `pytest tests/test_f02_production_integrity.py -q` |
| Full regression | Before any change | `pytest -q` |
| Full audit suite | Monthly | `pytest tests/test_a01* tests/test_c40* tests/test_f02* -q` |

### Audit Failure Escalation

- Any audit failure → **freeze all changes**
- Create repair card
- Investigate root cause
- Restore integrity before resuming operations

---

## 7. Regression Interval

| Trigger | Action |
|---------|--------|
| Before any code change | Full `pytest -q` |
| After any config change | Full `pytest -q` |
| After any restart | Verify test count unchanged |
| Weekly baseline check | Full `pytest -q`, compare count |

### Baseline Rule

- Current baseline: **1673+ tests**
- Test count must **never decrease**
- Decrease = potential seal or contract removal = immediate investigation

---

## 8. Alert Rules

| Condition | Severity | Action |
|-----------|:--------:|--------|
| Health endpoint 503 | **HIGH** | Investigate within 5 minutes |
| Governance gate not initialized | **CRITICAL** | Immediate stop |
| Evidence store unavailable | **CRITICAL** | Immediate stop |
| Config drift detected (F-02 fail) | **CRITICAL** | Freeze changes, investigate |
| Audit failure | **HIGH** | Freeze changes, create repair card |
| Regression failure | **HIGH** | Revert last change, investigate |
| Persistence file missing | **HIGH** | Check disk, restore from backup |
| Log file not growing | **MEDIUM** | Verify log configuration |

---

## 9. Stop Rules

Immediate production stop is required when:

1. Governance gate is broken or disabled
2. Evidence store is unavailable or corrupted
3. Configuration drift detected (wrong APP_ENV)
4. Illegal execution path detected
5. Audit critical failure
6. Security breach suspected
7. Unplanned testnet flag change

**Any operator may invoke immediate stop. No approval required.**

Reference: D-05 (`prod_rollback_override_procedure.md`) Section 2.

---

## 10. Rollback Triggers

Rollback is triggered when:

| Trigger | Rollback Scope |
|---------|---------------|
| Stop condition activated | Full rollback per D-05 |
| Failed deployment | Revert to previous known-good state |
| Regression failure after change | Revert change, run regression |
| Audit failure after change | Revert change, run audit |
| Operator decision | Document reason, preserve evidence |

---

## 11. Monitoring Summary

```
Production must always be observable.
Production must always be auditable.
Production must always be stoppable.
No silent state. No silent change. No silent failure.
```

---

*Defined by Card F-03. These rules are binding in production phase.*
