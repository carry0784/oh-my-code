# C-04 Re-Close and Incident Policy

**version**: 1.0
**date**: 2026-03-26

---

## Core Rule

Any condition regression immediately returns C-04 to blocked state. No grace period. No optimistic hold. Fail-closed is instant.

---

## 1. Re-Close Rules

### Automatic Re-Close Triggers

C-04 automatically returns to BLOCKED when ANY of the following occur:

| # | Trigger | Block Code |
|---|---------|-----------|
| 1 | Pipeline state != ALL_CLEAR | PIPELINE_NOT_READY |
| 2 | Preflight != READY | PREFLIGHT_NOT_READY |
| 3 | Gate != OPEN | GATE_CLOSED |
| 4 | Approval != APPROVED or expired | APPROVAL_REQUIRED |
| 5 | Policy != MATCH | POLICY_BLOCKED |
| 6 | Ops score < 0.7 | RISK_NOT_OK |
| 7 | Trading unauthorized | AUTH_NOT_OK |
| 8 | Lockdown/quarantine active | SCOPE_NOT_OK |
| 9 | Evidence missing or fallback | EVIDENCE_MISSING |

### Re-Close Behavior

- Execute button: **immediately disabled**
- Recovery buttons: **immediately disabled**
- Badge: **returns to BLOCKED**
- Met count: **drops below 9/9**
- Block code: **displays first failing stage**
- Guard messages: **re-appear**
- Any in-flight UI state: **reset to blocked**

### Re-Close Does NOT

- Delete existing receipts
- Delete existing audit entries
- Modify previous execution results
- Trigger automatic rollback
- Trigger automatic retry

---

## 2. Incident Declaration Rules

### When to Declare Incident

| # | Condition | Action |
|---|-----------|--------|
| 1 | Execution returns FAILED | Declare investigation incident |
| 2 | Receipt shows RESULT_UNKNOWN | Declare investigation incident |
| 3 | Audit entry missing for executed action | Declare evidence incident |
| 4 | Receipt and system state contradict | Declare consistency incident |
| 5 | Unexpected state change after execution | Declare mutation incident |
| 6 | Multiple rapid failures | Declare stability incident |

### Incident Response Steps

```
1. STOP all execution attempts
2. Record current receipt IDs
3. Record current system state
4. Check C-08 Error Log
5. Check C-09 Audit Log
6. Do NOT retry until incident resolved
7. Do NOT rollback until incident analyzed
8. Notify system administrator
9. Document incident in operational log
```

---

## 3. Evidence Preservation Rules

### During Re-Close

- All existing receipts are preserved
- All existing audit entries are preserved
- All existing evidence linkages are preserved
- No automatic cleanup occurs
- Re-close itself is an observable state change (visible in UI)

### During Incident

- Receipt chain must remain traceable
- Audit chain must remain unbroken
- Evidence IDs must remain linked
- No manual deletion of evidence
- Investigation must produce its own audit trail

---

## 4. Recovery After Re-Close

### To Re-Enable Execution

1. Resolve the condition that caused re-close
2. Wait for chain to re-evaluate to 9/9
3. Re-verify all operator checklist items
4. Proceed through normal execution flow
5. Do NOT use cached or stale chain data

### Recovery After Incident

1. Complete incident investigation
2. Document root cause
3. Verify system state is clean
4. Re-verify all 9 chain conditions
5. Obtain fresh operator authorization
6. Conduct simulation before execution
7. Proceed only if simulation shows SIMULATED

---

## 5. Forbidden During Re-Close / Incident

| Forbidden | Reason |
|-----------|--------|
| Force-enable execute button | Bypass violation |
| Skip chain re-evaluation | Stale data risk |
| Auto-retry after failure | Manual-only rule |
| Auto-rollback after failure | Manual-only rule |
| Delete receipts/audit | Evidence destruction |
| Ignore RESULT_UNKNOWN | Investigation required |
| Override re-close via flag | Hidden state violation |
| Execute during lockdown | Constitutional violation |

---

## 6. Fail-Closed Guarantees

| Situation | Behavior |
|-----------|----------|
| Unknown chain state | BLOCKED |
| Missing evidence | BLOCKED |
| Stale data | BLOCKED |
| Server error | FAILED receipt + audit |
| Network error | No execution (client-side blocked) |
| Partial chain | BLOCKED |
| Expired approval | BLOCKED |
| Condition regression | Instant re-close |

---

## 7. Audit Trail Requirements

Every C-04 interaction must be traceable:

| Event | Receipt? | Audit? |
|-------|---------|--------|
| Execution success | Yes (RCP-*) | Yes (AUD-*) |
| Execution rejection | Yes | Yes |
| Execution failure | Yes | Yes |
| Simulation | Yes (RCP-SIM-*) | Yes (AUD-SIM-*) |
| Rollback | Yes (RCP-RB-*) | Yes (AUD-RB-*) |
| Retry | Yes (RCP-RT-*) | Yes (AUD-RT-*) |
| Re-close | Observable in UI | Chain state recorded |
| Incident | Operator documented | Investigation record |

No silent action. No unrecorded execution. No evidence gap.
