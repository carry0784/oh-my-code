# Z-02: Operational Check Protocol

**Card**: Z-02
**Type**: Operational Rule (no code change)
**Date**: 2026-03-25
**Phase**: prod (frozen)

---

## Inspection Levels

| Level | Frequency | Scope | Returns |
|:-----:|-----------|-------|---------|
| 1 | **Daily** | Runtime health | OK / WARNING / FAIL |
| 2 | **Weekly** | Integrity review | INTACT / PARTIAL / BROKEN |
| 3 | **Monthly** | Governance audit | GOVERNED / DEGRADED / VIOLATED |

---

## Level 1 — Daily Check

Performed by operator every operational day.

| # | Check | Method | Expected |
|---|-------|--------|----------|
| 1 | APP_ENV = production | Config verify or startup log | production |
| 2 | Phase = prod | Governance snapshot | prod |
| 3 | `/health` | `GET /health` | 200 |
| 4 | `/status` | `GET /status` | 200, no CRITICAL |
| 5 | `/dashboard` | Browser | Loads |
| 6 | Log file growing | `ls -la logs/prod.log` | Size increased |
| 7 | Evidence DB present | `ls data/prod_evidence.db` | Exists |
| 8 | No crash/restart loop | Process uptime check | Stable |
| 9 | Monitoring active | F-03 rules followed | Active |

### Daily Result Classification

| Result | Condition |
|--------|-----------|
| **OK** | All 9 checks pass |
| **WARNING** | 1-2 non-critical checks fail (e.g., log size unchanged) |
| **FAIL** | Any endpoint fails, governance missing, or crash loop detected |

### Daily FAIL Action

1. Do not proceed with any changes
2. Log the failure with timestamp
3. Investigate root cause
4. If critical: invoke D-05 rollback procedure

---

## Level 2 — Weekly Integrity Review

Performed once per week.

| # | Check | Method | Expected |
|---|-------|--------|----------|
| 1 | Enforcement tests | `pytest tests/test_a01* tests/test_c40* tests/test_f02* -q` | 103 passed |
| 2 | Full regression | `pytest -q` | 1709+ passed, 0 failed |
| 3 | Boundary lock | C-40 tests pass | 25 passed |
| 4 | Freeze active | `f01_production_freeze.md` exists | Present |
| 5 | No doc drift | All 15 governance docs present | 15/15 |
| 6 | No config drift | APP_ENV=production, governance=true | Matched |
| 7 | Persistence durable | Evidence DB + receipt file + log file exist | All present |
| 8 | Monitoring rules present | `f03_production_monitoring.md` exists | Present |

### Weekly Result Classification

| Result | Condition |
|--------|-----------|
| **INTACT** | All 8 checks pass |
| **PARTIAL** | 1-2 non-critical checks fail |
| **BROKEN** | Any enforcement test fails, regression fails, or governance doc missing |

### Weekly BROKEN Action

1. Freeze all changes immediately
2. Run Z-01 full integrated inspection
3. Create incident report
4. Do not resume operations until INTACT restored

---

## Level 3 — Monthly Governance Audit

Performed once per month.

| # | Check | Method | Expected |
|---|-------|--------|----------|
| 1 | Constitution exists | File check | Present |
| 2 | Laws exist (5) | File check | 5/5 |
| 3 | Seals exist (5) | File check | 5/5 |
| 4 | Freeze exists | File check | Present |
| 5 | Monitoring exists | File check | Present |
| 6 | Audit tests exist | File check | A-01, C-40, F-02 |
| 7 | Integrity tests exist | File check | F-02 |
| 8 | No illegal execution path | C-40 tests | Pass |
| 9 | No unauthorized change | Git log review | No uncard changes |
| 10 | Phase unchanged | Config check | prod |

### Monthly Result Classification

| Result | Condition |
|--------|-----------|
| **GOVERNED** | All 10 checks pass |
| **DEGRADED** | 1-2 documents missing or test suite incomplete |
| **VIOLATED** | Unauthorized change detected, illegal path found, or phase changed |

### Monthly VIOLATED Action

1. Immediately invoke emergency procedure (L-03)
2. Stop all operations
3. Run Z-01 full inspection
4. Create incident report with evidence
5. Do not resume until GOVERNED restored

---

## Failure Rule

If any level returns FAIL / BROKEN / VIOLATED:

1. **Stop** all pending changes
2. **Log** the incident with timestamp and evidence
3. **Run** Z-01 full integrated inspection
4. **Do not** patch blindly — follow card protocol (L-02)
5. **Do not** bypass governance to "fix quickly"

---

## Allowed Actions

| Action | Allowed |
|--------|:-------:|
| Inspect | Yes |
| Monitor | Yes |
| Log | Yes |
| Audit | Yes |
| Operator action (restart, rollback) | Yes |
| Rollback per D-05 | Yes |
| Direct code change | **No** |
| Bypass law | **No** |
| Bypass seal | **No** |
| Bypass freeze | **No** |

---

## Final Rule

K-V3 is a live governed system. Operation must follow this protocol. Deviation from protocol without constitutional authority is a governance violation.

---

*Defined by Card Z-02.*
