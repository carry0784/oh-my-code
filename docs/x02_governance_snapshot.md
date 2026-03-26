# X-02: Governance Snapshot

**Card**: X-02
**Type**: State Record (no code change)
**Date**: 2026-03-25
**Snapshot time**: 2026-03-25T18:10:00+09:00

---

## Exact System State

| Field | Value |
|-------|-------|
| **Phase** | `prod` |
| **Freeze** | Active (F-01) |
| **APP_ENV** | `production` |
| **is_production** | `True` |
| **DEBUG** | `False` |
| **GOVERNANCE_ENABLED** | `True` |
| **BINANCE_TESTNET** | `False` |
| **OKX_SANDBOX** | `False` |
| **BITGET_SANDBOX** | `False` |
| **KIS_DEMO** | `False` |
| **KIWOOM_DEMO** | `False` |

## Constitution Version

| Document | Card | Status |
|----------|------|:------:|
| `system_final_constitution.md` | C-46 | Active |

## Law Version

| Law | Card | Status |
|-----|------|:------:|
| System Law Freeze | L-01 | Frozen |
| Change Protocol | L-02 | Frozen |
| Emergency Override | L-03 | Frozen |
| Audit Law | L-04 | Frozen |
| Phase Law | L-05 | Frozen |

## Seal List

| Seal | Card | Status |
|------|------|:------:|
| Retry Layer | C-41 | Sealed |
| Notification Layer | C-42 | Sealed |
| Execution Layer | C-43 | Sealed |
| Engine Layer | C-44 | Sealed |
| Governance Layer | C-45 | Sealed |

## Enforcement Tests

| Suite | Card | Tests |
|-------|------|:-----:|
| Constitution Audit | A-01 | 42 |
| Boundary Lock | C-40 | 25 |
| Production Integrity | F-02 | 36 |
| **Total** | | **103** |

## Regression Count

| Metric | Value |
|--------|:-----:|
| Total tests | 1709 |
| Passed | 1709 |
| Failed | 0 |

## Persistence Mode

| Store | Mode | Path |
|-------|------|------|
| Evidence | SQLITE_PERSISTED | `./data/prod_evidence.db` |
| Receipts | FILE_PERSISTED | `./data/prod_receipts.jsonl` |
| Logs | FILE_PERSISTED | `./logs/prod.log` |

## Change Mode

**Frozen + Law-gated + Elevated review**

## Monitoring Rule

Reference: F-03 (`f03_production_monitoring.md`)

## Rollback Rule

Reference: D-05 (`prod_rollback_override_procedure.md`)

## Card Registry

| Series | Range | Count | Purpose |
|--------|-------|:-----:|---------|
| Card B | — | 1 | Engine baseline (57 sealed tests) |
| C | C-01~C-46 | 46 | Implementation + Constitution |
| L | L-01~L-05 | 5 | Laws |
| A | A-01 | 1 | Audit |
| P | P-01~P-06 | 6 | Phase |
| D | D-01~D-05 | 5 | Documentation |
| S | S-01~S-04 | 4 | Staging review |
| I | I-01~I-03 | 3 | Infrastructure |
| O | O-01~O-03 | 3 | Operator sign-off |
| G | G-01 | 1 | Governance integrity |
| F | F-01~F-03 | 3 | Production freeze |
| X | X-01~X-03 | 3 | Completion |
| **Total** | | **81** | |

---

*Snapshot recorded by Card X-02. This is the exact state at project completion.*
