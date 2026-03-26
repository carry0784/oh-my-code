# Z-03: Incident Response Protocol

**Card**: Z-03
**Type**: Operational Rule (no code change)
**Date**: 2026-03-25
**Phase**: prod (frozen)

---

## Severity Levels

| Level | Name | Description | Example |
|:-----:|------|-------------|---------|
| **S1** | Runtime Error | Application error, recoverable | Endpoint 503, worker crash |
| **S2** | Persistence Error | Storage failure | Evidence DB locked, receipt write fail |
| **S3** | Execution Integrity Error | Boundary or SSOT violation | C-40 test failure, unauthorized sender call |
| **S4** | Governance Violation | Constitutional rule broken | Seal modified, law bypassed, unauthorized code change |
| **S5** | Unknown State | Cannot determine system state | Config unclear, phase ambiguous, mixed env |

---

## Response Actions

### S1 — Runtime Error

```
1. Check endpoint status
2. Review recent log entries
3. Restart application if needed
4. Verify /health returns 200 after restart
5. Log incident
```

**Allowed**: Restart, log review, operator action
**Forbidden**: Code change, config mutation

### S2 — Persistence Error

```
1. Check disk space and permissions
2. Verify evidence DB integrity
3. Verify receipt file writable
4. Verify log file writable
5. If corrupted: preserve corrupted files, do not delete
6. Restore from backup if available
7. Log incident with evidence
```

**Allowed**: File system check, backup restore, operator action
**Forbidden**: Code change, path modification without card

### S3 — Execution Integrity Error

```
1. STOP all operations immediately
2. Run C-40 boundary lock tests
3. Run F-02 production integrity tests
4. Identify the violation
5. Do NOT fix without card
6. Create repair card if needed
7. Log incident with full evidence
```

**Allowed**: Stop, audit, inspect
**Forbidden**: Direct fix, code change, boundary modification

### S4 — Governance Violation

```
1. STOP all operations immediately
2. Invoke emergency law (L-03)
3. Run full Z-01 inspection
4. Identify unauthorized change
5. Preserve all evidence
6. Create incident report
7. Do NOT resume without governance restoration
```

**Allowed**: Emergency stop, evidence preservation, L-03 override
**Forbidden**: Any change that further violates governance

### S5 — Unknown State

```
1. STOP system immediately
2. Do NOT attempt diagnosis while running
3. Preserve all files (logs, evidence, receipts, config)
4. Run Z-01 full inspection from outside
5. Classify actual state
6. Respond based on identified severity level
```

**Allowed**: Stop, preserve, inspect
**Forbidden**: Any action until state is classified

---

## Escalation Matrix

```
S1 → Operator handles → Log → Resume if OK
S2 → Operator handles → Audit → Resume if restored
S3 → Operator stops → Audit required → Card required → Resume after fix
S4 → Emergency stop → L-03 → Full inspection → Constitutional review
S5 → Emergency stop → Classify → Route to S1-S4 → Respond accordingly
```

---

## References

| Document | Purpose |
|----------|---------|
| L-03 `law_emergency_override.md` | Emergency override rules |
| D-05 `prod_rollback_override_procedure.md` | Rollback procedure |
| F-01 `f01_production_freeze.md` | Freeze rules |
| F-03 `f03_production_monitoring.md` | Monitoring rules |
| Z-01 `z01_full_integrated_system_inspection.md` | Full inspection procedure |

---

## Forbidden During Any Incident

1. Hot patch (direct code edit)
2. Direct code edit without card
3. Seal change
4. Law bypass
5. Constitution bypass
6. Evidence deletion
7. Log deletion
8. Silent recovery (recover without logging)
9. "It's fine now" without audit evidence

---

## Final Rule

Every incident must produce:
- Timestamp
- Severity classification
- Actions taken
- Evidence preserved
- Resolution status
- Post-incident audit reference (if S3+)

No incident may be silently resolved.

---

*Defined by Card Z-03.*
