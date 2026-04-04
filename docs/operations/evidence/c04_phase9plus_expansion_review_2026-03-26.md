# C-04 Phase 9+ Expansion Review — 2026-03-26

**evidence_id**: C04-PHASE9PLUS-REVIEW-2026-03-26
**baseline**: 2ac6afa (Step 4 freeze)

---

## Expansion Candidate Table

| # | Candidate | Expected Benefit | Guard Impact | SSOT Impact | UI Impact | Write Path | Verdict |
|---|-----------|-----------------|-------------|-------------|-----------|-----------|---------|
| 1 | SSOT Drift Sentinel test | Prevent score path divergence | None (test only) | Protects SSOT | None | None | **GO** |
| 2 | Operator identity binding | Real operator ID in receipts | None | None | Minor display | None | **GO** |
| 3 | Receipt history display | Show past receipts in C-07 | None | None | Read-only display | None | **GO** |
| 4 | Audit trail display | Show past audits in C-09 | None | None | Read-only display | None | **GO** |
| 5 | Snapshot freshness auto-refresh | Celery beat + periodic snapshot | None | Keeps SSOT fresh | None | None (existing task) | **CONDITIONAL** |
| 6 | Hourly check latency/warning fix | Resolve remaining 2 WARN items | None | None | None | None | **CONDITIONAL** |
| 7 | Re-close verification in UI | Show re-close transition live | None | None | Display only | None | **GO** |
| 8 | Multi-exchange sync | Connect additional exchanges | None | None | Display | None | **CONDITIONAL** |
| 9 | Execute with real trade dispatch | Actual order submission | **HIGH** — E-01 activation | None | Execution UI | **Yes** | **BLOCKED** |
| 10 | Auto-execution scheduler | Cron-based execute | **CRITICAL** — violates manual-only | None | None | Yes | **BLOCKED** |
| 11 | Score threshold adjustment | Change 0.7 threshold | Guard change | SSOT change | None | None | **BLOCKED** |
| 12 | New write endpoint | Additional POST routes | None | None | None | **Yes** | **BLOCKED** |
| 13 | UI-side score calculation | Client compute score | None | **SSOT drift** | Judgment layer | None | **BLOCKED** |

---

## Classification Summary

### GO (safe, no guard/SSOT/write impact)

1. **SSOT Drift Sentinel test** — test-only, protects alignment
2. **Operator identity binding** — enrich receipt with real operator
3. **Receipt history display** — read-only C-07 enhancement
4. **Audit trail display** — read-only C-09 enhancement
5. **Re-close verification in UI** — display state transition

### CONDITIONAL (requires specific conditions)

6. **Snapshot freshness auto-refresh** — requires Celery beat, no code change
7. **Hourly check remaining WARN fix** — requires measurement path for latency/warning
8. **Multi-exchange sync** — requires API keys + DNS fix for each exchange

### BLOCKED (violates constitutional boundaries)

9. Real trade dispatch — requires E-01 activation (separate approval)
10. Auto-execution scheduler — violates manual-only principle
11. Score threshold adjustment — changes Guard boundary
12. New write endpoint — write path expansion
13. UI-side score calculation — SSOT drift

---

## Recommended Next Actions (priority order)

1. **SSOT Drift Sentinel test** — highest value, zero risk
2. **Receipt/Audit history display** — improves operator visibility
3. **Celery beat start** — enables auto-refresh for SSOT freshness
4. **Operator identity binding** — receipt quality improvement

---

## Constitutional Compliance

| Rule | Status |
|------|--------|
| Guard invariance | All GO items preserve guard | **PASS** |
| SSOT invariance | No GO item introduces new calculation | **PASS** |
| UI read-only | All GO items are display/test only | **PASS** |
| Write path unchanged | No GO item adds POST | **PASS** |
| Simulate/execute boundary | Preserved | **PASS** |
