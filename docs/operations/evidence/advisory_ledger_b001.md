# Advisory Ledger — B-001

## Ledger Metadata

| Field | Value |
|---|---|
| ledger_id | `ADV-LEDGER-B001` |
| issued_at | 2026-04-14T00:15:00Z |
| baseline_ref | `11cd437` (Phase A closure) |
| source_document | `docs/operations/evidence/step7_security_audit.md` |
| total_advisories | 7 |
| production_authorized | **FALSE** |
| p3_non_interference | **TRUE** |

---

## Advisory Entries

### A1 — Secret Key Validation

| Field | Value |
|---|---|
| advisory_id | `ADV-A1-SECRET-KEY` |
| category | Security / Configuration |
| severity | **Medium** |
| blast_radius | Production startup only. No runtime impact if env var is set correctly. |
| affected_component | `app/core/config.py` — `Settings.validate_production()` |
| exploitability | Low. Requires production deployment with default secret key unchanged. Internal system, no external auth surface. |
| mitigation | Add startup assertion: `assert settings.secret_key != "change-me-in-production"` in production entry point. `validate_production()` already checks this but does not hard-fail the process. |
| merge_block | **NO** — Does not affect code correctness or test integrity. |
| production_block | **YES** — Must be resolved before any production deployment. Default secret key in production is a critical misconfiguration. |
| owner | Infrastructure / DevOps |
| status | **RESOLVED** |
| resolved_at | 2026-04-14T01:30:00Z |
| resolution | Added `RuntimeError` fail-fast in `app/main.py` lifespan: startup aborts if `secret_key` is `"change-me-in-production"` or empty when `app_env == "production"`. |
| evidence_link | `docs/operations/evidence/step7_security_audit.md` §A1 |

---

### A2 — Rate Limiting

| Field | Value |
|---|---|
| advisory_id | `ADV-A2-RATE-LIMIT` |
| category | Security / API Protection |
| severity | **Medium** |
| blast_radius | All public-facing API endpoints. Internal trading system reduces exposure but does not eliminate risk if network-exposed. |
| affected_component | `app/main.py` — FastAPI middleware stack |
| exploitability | Medium. Without rate limiting, a compromised internal client or misconfigured scheduler could overwhelm the API. |
| mitigation | Add `slowapi` or custom rate-limiting middleware. Priority: `/api/v1/orders`, `/api/v1/signals` endpoints. |
| merge_block | **NO** — Rate limiting is additive; absence does not break existing functionality. |
| production_block | **CONDITIONAL** — Required if API is network-exposed. Not required if API is strictly localhost/pod-internal. |
| owner | Backend / API |
| status | OPEN |
| evidence_link | `docs/operations/evidence/step7_security_audit.md` §A2 |

---

### A3 — SQL Injection Surface

| Field | Value |
|---|---|
| advisory_id | `ADV-A3-SQL-INJECTION` |
| category | Security / Data Access |
| severity | **Low** |
| blast_radius | Database query layer. All queries use SQLAlchemy ORM with parameterized statements. |
| affected_component | All `app/services/*.py` using SQLAlchemy; `text()` calls verified safe. |
| exploitability | Very Low. SQLAlchemy ORM prevents injection by default. No user-supplied raw SQL paths exist. |
| mitigation | Periodic audit of any new `text()` or `execute()` calls. Add to code review checklist. |
| merge_block | **NO** — Current state is safe. |
| production_block | **NO** — ORM usage is already the correct pattern. |
| owner | Backend / Code Review |
| status | ACCEPTED_RISK |
| evidence_link | `docs/operations/evidence/step7_security_audit.md` §A3 |

---

### A4 — Dependency Audit

| Field | Value |
|---|---|
| advisory_id | `ADV-A4-DEP-AUDIT` |
| category | Security / Supply Chain |
| severity | **Medium** |
| blast_radius | All runtime dependencies. A vulnerable dependency could affect any component. |
| affected_component | `requirements.txt`, `pyproject.toml`, CI pipeline |
| exploitability | Variable. Depends on specific CVEs in dependencies. No known active vulnerabilities at time of audit. |
| mitigation | Add `pip-audit` or `safety` check to CI pipeline. Run as advisory (non-blocking) initially, promote to blocking after baseline established. |
| merge_block | **NO** — Absence of audit tooling does not affect code correctness. |
| production_block | **CONDITIONAL** — Recommended before production. Not a hard blocker if dependencies are manually reviewed. |
| owner | Infrastructure / CI |
| status | OPEN |
| evidence_link | `docs/operations/evidence/step7_security_audit.md` §A4 |

---

### A5 — Redis Authentication (Dev)

| Field | Value |
|---|---|
| advisory_id | `ADV-A5-REDIS-AUTH` |
| category | Security / Infrastructure |
| severity | **Low** |
| blast_radius | Development environment only. Production `docker-compose.prod.yml` already has `--requirepass`. |
| affected_component | `docker-compose.yml` (dev) — Redis service |
| exploitability | Very Low. Dev environment only; no external network exposure expected. |
| mitigation | Add `--requirepass` to dev Redis or document that dev Redis is intentionally open for local development. |
| merge_block | **NO** — Dev-only configuration. |
| production_block | **NO** — Production already has Redis auth. |
| owner | Infrastructure / DevOps |
| status | ACCEPTED_RISK |
| evidence_link | `docs/operations/evidence/step7_security_audit.md` §A5 |

---

### A6 — Log Sanitization

| Field | Value |
|---|---|
| advisory_id | `ADV-A6-LOG-SANITIZE` |
| category | Security / Observability |
| severity | **Low** |
| blast_radius | Log output paths. Risk of API keys or secrets appearing in error stack traces from exchange API calls. |
| affected_component | `exchanges/*.py` — error handling paths; structured logging throughout |
| exploitability | Low. Requires access to log storage. Internal system reduces exposure. |
| mitigation | Audit exchange API error handlers for secret leakage. Add log redaction for known secret field names (`api_key`, `api_secret`, `passphrase`). |
| merge_block | **NO** — Structured logging is already in place. |
| production_block | **CONDITIONAL** — Recommended audit before production log aggregation is enabled. |
| owner | Backend / Observability |
| status | OPEN |
| evidence_link | `docs/operations/evidence/step7_security_audit.md` §A6 |

---

### A7 — K8s Network Policy

| Field | Value |
|---|---|
| advisory_id | `ADV-A7-NETWORK-POLICY` |
| category | Security / Infrastructure |
| severity | **Medium** |
| blast_radius | All K8s pods in `kdexter` namespace. Without NetworkPolicy, any pod can communicate with any other pod. |
| affected_component | `k8s/` manifests — missing `NetworkPolicy` resource |
| exploitability | Medium. If one pod is compromised, lateral movement to other pods is unrestricted. |
| mitigation | Add `NetworkPolicy` manifests: allow API → DB, Worker → Redis/DB, Beat → Redis. Deny all other intra-namespace traffic. |
| merge_block | **NO** — K8s manifests are declarative; absence of NetworkPolicy does not break deployment. |
| production_block | **YES** — Required before production K8s deployment. Lateral movement restriction is a hard security requirement. |
| owner | Infrastructure / K8s |
| status | **RESOLVED** |
| resolved_at | 2026-04-14T01:45:00Z |
| resolution | Added `k8s/networkpolicy.yaml`: default-deny-all + 5 allow policies (API, Worker, Beat, Postgres, Redis). Flows restricted to API→DB/Redis, Worker→DB/Redis, Beat→Redis, Prometheus→API, Ingress→API. |
| evidence_link | `docs/operations/evidence/step7_security_audit.md` §A7 |

---

## Summary Matrix

| ID | Severity | merge_block | production_block | Status |
|---|---|---|---|---|
| A1 | Medium | NO | **YES** | **RESOLVED** |
| A2 | Medium | NO | CONDITIONAL | OPEN |
| A3 | Low | NO | NO | ACCEPTED_RISK |
| A4 | Medium | NO | CONDITIONAL | OPEN |
| A5 | Low | NO | NO | ACCEPTED_RISK |
| A6 | Low | NO | CONDITIONAL | OPEN |
| A7 | Medium | NO | **YES** | **RESOLVED** |

### Aggregate Judgment

- **merge_block = NO** for all 7 advisories. Phase A merges were correctly executed.
- **production_block = YES** for 2 advisories (A1, A7). Both RESOLVED (2026-04-14).
- **production_block = CONDITIONAL** for 3 advisories (A2, A4, A6). Resolution depends on deployment topology.
- **production_block = NO** for 2 advisories (A3, A5). Accepted risk, no action required.
- **production_authorized = FALSE** remains unchanged. This ledger does not grant authorization.

### Open Count

| Category | Count |
|---|---|
| OPEN | 3 |
| ACCEPTED_RISK | 2 |
| RESOLVED | 2 |
| Total | 7 |
