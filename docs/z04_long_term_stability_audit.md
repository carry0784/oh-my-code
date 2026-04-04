# Z-04: Long-Term Stability Audit

**Card**: Z-04
**Type**: Operational Rule (no code change)
**Date**: 2026-03-25
**Phase**: prod (frozen)

---

## Purpose

A single point-in-time inspection (Z-01) proves the system is intact now. Long-term stability requires evidence that the system remains intact over time without drift, degradation, or silent change.

---

## Stability Windows

| Window | Duration | Purpose |
|--------|----------|---------|
| **7-day** | 1 week | Short-term operational stability |
| **30-day** | 1 month | Medium-term governance stability |
| **90-day** | 3 months | Long-term institutional stability |

---

## 7-Day Stability Check

After 7 days of production operation, verify:

| # | Check | Method |
|---|-------|--------|
| 1 | No unplanned restart | Process uptime log |
| 2 | No persistence loss | Evidence DB + receipt file sizes stable or growing |
| 3 | No config change | APP_ENV still production |
| 4 | No governance change | 15 governance docs still present |
| 5 | No phase change | Phase still prod |
| 6 | No enforcement drift | 103 enforcement tests pass |
| 7 | No regression drift | 1709+ tests pass |
| 8 | Daily checks all OK | 7 daily check logs |

### 7-Day Result

| Result | Condition |
|--------|-----------|
| **STABLE** | All 8 checks pass |
| **UNSTABLE** | Any restart loop, persistence loss, or enforcement failure |
| **DRIFT** | Config changed, governance doc missing, or phase changed |

---

## 30-Day Stability Check

After 30 days, verify everything in 7-day plus:

| # | Additional Check | Method |
|---|-----------------|--------|
| 1 | No unauthorized code change | `git log` review — all changes have card numbers |
| 2 | No illegal execution path | C-40 tests pass |
| 3 | No seal modification | 5 seal docs unchanged |
| 4 | No law modification | 5 law docs unchanged |
| 5 | Evidence DB growing normally | Size trend (no plateau = writes occurring, no explosion = no flood) |
| 6 | Log rotation working | Log file size manageable |
| 7 | Monthly governance audit passed | Z-02 Level 3 result = GOVERNED |

### 30-Day Result

| Result | Condition |
|--------|-----------|
| **STABLE** | All checks pass, governance audit = GOVERNED |
| **UNSTABLE** | Enforcement failure, persistence anomaly, or audit failure |
| **DRIFT** | Unauthorized change, missing doc, or governance DEGRADED/VIOLATED |

---

## 90-Day Stability Check

After 90 days, verify everything in 30-day plus:

| # | Additional Check | Method |
|---|-----------------|--------|
| 1 | Constitution unchanged | File hash or content comparison |
| 2 | No structural system change | Architecture unchanged |
| 3 | Enforcement test count stable | Still 103+ enforcement tests |
| 4 | Regression test count stable | Still 1709+ total tests |
| 5 | No emergency override without audit | All L-03 overrides have A-series cards |
| 6 | No rollback without documentation | All D-05 rollbacks documented |
| 7 | System operated within governance | No VIOLATED audit result in 90 days |

### 90-Day Result

| Result | Condition |
|--------|-----------|
| **STABLE** | System operated within governance for 90 days |
| **UNSTABLE** | Multiple incidents, repeated enforcement failures |
| **DRIFT** | Gradual unauthorized changes, governance erosion |

---

## Stability Record

Each stability check must produce a record:

| Field | Required |
|-------|:--------:|
| Check date | Yes |
| Window (7/30/90) | Yes |
| Result (STABLE/UNSTABLE/DRIFT) | Yes |
| Evidence summary | Yes |
| Anomalies found | Yes (or "none") |
| Operator who performed check | Yes |

---

## Failure Response

| Result | Action |
|--------|--------|
| STABLE | Continue normal operation |
| UNSTABLE | Run Z-01 full inspection, investigate cause |
| DRIFT | Invoke Z-01, identify drift source, create remediation card |

---

## Final Rule

Long-term stability is not assumed. It is proven by repeated evidence over time. A system that was intact on day 1 may drift by day 30. Only continuous verification produces confidence.

---

*Defined by Card Z-04. Long-term stability requires long-term evidence.*
