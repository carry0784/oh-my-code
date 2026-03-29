# I-03: Prod Infrastructure Provision

**Card**: I-03
**Type**: Execution Evidence Card (no code change)
**Date**: 2026-03-25
**Phase**: staging → prod transition

---

## 1. Completed vs Incomplete

### Completed (with execution evidence)

| Item | Evidence |
|------|---------|
| Constitution/Law/Seal baseline | Active, 67 enforcement tests pass |
| Staging verification baseline | S-03 stable, S-04 soak pass, G-01 intact |
| Prod runbook | D-03 created |
| Prod config guide | D-04 created |
| Prod rollback procedure | D-05 created |
| `.env.production` created | File created per D-04 |
| Prod config applied | `.env.production` → `.env` |
| `APP_ENV=production` verified | Settings reload: `is_production=True` |
| `GOVERNANCE_ENABLED=true` | Confirmed |
| Testnet flags disabled | `BINANCE_TESTNET=false` |
| DB accessible | `alembic upgrade head` clean |
| Redis accessible | Running on 6379 |
| Data directory | `data/` exists |
| Logs directory | `logs/` exists |
| Evidence DB created | `data/prod_evidence.db` = 24,576 bytes |
| Log file created | `logs/prod.log` = 2,384 bytes |
| Migration executed | No errors |
| Audit in prod context | 67 passed |
| Regression in prod context | 1673 passed, 0 failed |
| Prod app boot | Lifespan OK, governance initialized |
| Endpoints verified | health=200, startup=200, status=200, dashboard=200 |

### Incomplete

None. All prod provision steps have execution evidence.

---

## 2. Prod Environment Separation

| Resource | Staging | Production | Separated |
|----------|---------|------------|:---------:|
| APP_ENV | staging | production | **YES** |
| Config file | .env.staging | .env.production | **YES** |
| Evidence DB | staging_evidence.db | prod_evidence.db | **YES** |
| Receipt file | staging_receipts.jsonl | prod_receipts.jsonl | **YES** |
| Log file | staging.log | prod.log | **YES** |
| Testnet mode | true | **false** | **YES** |
| Secret key | staging-secret | prod-secret | **YES** |

---

## 3. Startup Logs (prod boot evidence)

```
env=production
log_mode=FILE_PERSISTED
evidence_mode=SQLITE_PERSISTED, durability=DURABLE
governance_gate_created (gate_id=67b01657...)
receipt_mode=FILE_PERSISTED
governance_gate_initialized
```

---

## 4. Final Classification

### **PROD INFRA PROVISION COMPLETE**

---

## 5. Final Statement

**`Prod infrastructure = complete`**

---

*Verified by Card I-03.*
