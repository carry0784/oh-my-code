# Step 7 — Production Transition Checklist

## Pre-Deployment

### Infrastructure
- [ ] PostgreSQL provisioned (16+ with replication)
- [ ] Redis provisioned (7+ with authentication)
- [ ] Docker registry accessible (GHCR or private)
- [ ] K8s cluster provisioned (or Docker Compose host)
- [ ] PersistentVolume for `/app/data` (evidence DB, receipts)
- [ ] TLS certificates provisioned (Ingress or load balancer)

### Configuration
- [ ] `.env.production` created with all required variables
- [ ] `SECRET_KEY` set to unique random value (not default)
- [ ] `APP_ENV=production`
- [ ] `DEBUG=false`
- [ ] `GOVERNANCE_ENABLED=true`
- [ ] `BINANCE_TESTNET=false` (only when ready for live)
- [ ] `EXCHANGE_MODE=DATA_ONLY` initially (escalate via ops_state.json)
- [ ] Database URLs point to production PostgreSQL
- [ ] Redis URL points to production Redis with auth
- [ ] `LOG_FILE_PATH` set for persistent logging
- [ ] `EVIDENCE_DB_PATH` set for durable evidence
- [ ] `RECEIPT_FILE_PATH` set for durable receipts

### Secrets
- [ ] Docker secret for DB password created (`secrets/db_password.txt`)
- [ ] K8s Secret `kdexter-secrets` created with all sensitive values
- [ ] Exchange API keys configured (if applicable)
- [ ] LLM API keys configured (if applicable)
- [ ] No secrets committed to git (verify with `git log -p | grep -i "api_key\|password\|secret"`)

### Database
- [ ] `alembic upgrade head` executed on production DB
- [ ] All migrations verified (001 through 028)
- [ ] Database backup strategy in place
- [ ] Connection pool settings tuned for production load

## Deployment

### Build
- [ ] Docker image built successfully (`docker build -t kdexter/api .`)
- [ ] Image pushed to registry
- [ ] Image tag recorded for rollback reference

### Deploy
- [ ] K8s manifests applied: namespace, configmap, secrets, deployment, service
- [ ] OR docker-compose.prod.yml started
- [ ] Celery worker running
- [ ] Celery beat scheduler running
- [ ] Database migrations applied

### Verification
- [ ] `/health` returns `{"status": "healthy"}`
- [ ] `/ready` returns `{"ready": true}`
- [ ] `/startup` returns `{"started": true}`
- [ ] `/status` returns `{"overall_status": "healthy"}`
- [ ] Governance gate initialized (check startup logs)
- [ ] Evidence store in DURABLE mode (check startup logs)
- [ ] Receipt store in FILE_PERSISTED mode (check startup logs)

## Post-Deployment

### Monitoring
- [ ] Prometheus scraping `/metrics` endpoint
- [ ] Alert rules loaded (kdexter-health, kdexter-trading, kdexter-infra)
- [ ] Dashboard configured for key metrics
- [ ] Log aggregation active (structured JSON logs)

### Operational Readiness
- [ ] ops_state.json configured for production
- [ ] Operational mode verified (GUARDED_RELEASE initially)
- [ ] Exchange mode verified (DATA_ONLY initially)
- [ ] Celery beat schedule verified (all periodic tasks registered)
- [ ] Shadow task health confirmed (if PPF active)

### Rollback Plan
- [ ] Previous image tag documented
- [ ] `alembic downgrade` path verified for latest migration
- [ ] Docker Compose: `docker-compose.prod.yml down` + restart with previous image
- [ ] K8s: `kubectl rollout undo deployment/kdexter-api -n kdexter`

### Escalation Path
1. **DATA_ONLY → PAPER**: Set `EXCHANGE_MODE=PAPER` in ops_state.json, restart
2. **PAPER → LIVE**: Requires CR review, governance gate approval, operator sign-off
3. **Emergency stop**: Set `EXCHANGE_MODE=DATA_ONLY`, kill Celery workers

## Sign-Off

| Role | Name | Date | Approval |
|------|------|------|----------|
| Developer | | | [ ] |
| Operator | | | [ ] |
| Security | | | [ ] |

---

**This checklist must be completed and signed before production traffic is enabled.**
