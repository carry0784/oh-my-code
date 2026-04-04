# Z-06: Drift Detection Rule

**Card**: Z-06
**Type**: Operational Rule (no code change)
**Date**: 2026-03-25
**Baseline**: Z-05 snapshot (SNAP-2026-03-25-PROD-FINAL)

---

## Drift Dimensions

Every drift check compares current state against Z-05 snapshot across these dimensions:

| # | Dimension | Snapshot Value | How to Check |
|---|-----------|---------------|--------------|
| 1 | Phase | prod | Config verify |
| 2 | APP_ENV | production | Settings reload |
| 3 | Governance docs | 15 present | File count |
| 4 | Law docs | 5 present | File count |
| 5 | Seal docs | 5 present | File count |
| 6 | Enforcement tests | 103 | `pytest` count |
| 7 | Regression tests | 1709 | `pytest -q` count |
| 8 | Execution SSOT | 1 definition | C-40 tests |
| 9 | Persistence mode | durable (3 paths set) | Config verify |
| 10 | Monitoring rules | F-03 present | File check |
| 11 | Freeze | F-01 active | File check |
| 12 | Test failures | 0 | `pytest -q` result |

---

## Drift Classification

| Level | Definition | Trigger |
|-------|-----------|---------|
| **NO_DRIFT** | All dimensions match snapshot | 12/12 match |
| **MINOR_DRIFT** | Non-critical documentary difference | 1-2 docs missing but no enforcement/runtime impact |
| **MAJOR_DRIFT** | Enforcement or config mismatch | Test count decreased, config changed, persistence mode changed |
| **CRITICAL_DRIFT** | Governance or execution boundary violated | Phase changed, SSOT bypassed, seal modified, law violated |

---

## Response Rules

| Level | Action |
|-------|--------|
| **NO_DRIFT** | Continue normal operation |
| **MINOR_DRIFT** | Log finding, restore missing doc, verify at next weekly check |
| **MAJOR_DRIFT** | Stop changes, run Z-01 full inspection, create remediation card |
| **CRITICAL_DRIFT** | Emergency stop, invoke L-03, run Z-01, preserve evidence, incident report |

---

## Drift Check Procedure

```
1. Load Z-05 snapshot values
2. Collect current values for all 12 dimensions
3. Compare each dimension
4. Classify overall drift level
5. Execute response per level
6. Record drift check result with timestamp
```

---

## Drift Check Record

Each drift check must produce:

| Field | Required |
|-------|:--------:|
| Check date | Yes |
| Snapshot reference | Z-05 |
| Dimensions checked | 12 |
| Dimensions matched | Count |
| Drift level | NO/MINOR/MAJOR/CRITICAL |
| Anomalies | List or "none" |
| Operator | Yes |

---

*Defined by Card Z-06. Drift is measured, not assumed.*
