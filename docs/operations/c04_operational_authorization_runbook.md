# C-04 Operational Authorization Runbook

**version**: 1.0
**date**: 2026-03-26

---

## Purpose

Step-by-step procedure for authorizing, executing, and auditing C-04 Manual Action in production.

---

## Phase A: Pre-Authorization

### A1. System Health Check

```
1. Open /dashboard
2. Navigate to Tab 3 (운영 상태)
3. Verify:
   - System status: HEALTHY or DEGRADED (not UNHEALTHY)
   - Governance: NORMAL or ALLOWED
   - No active lockdown
   - No active incident
```

### A2. Chain Verification

```
1. Check C-04 card
2. Verify met count = 9/9
3. If < 9/9:
   - Read block code
   - Read guard messages
   - Resolve blocking conditions first
   - Do NOT proceed until 9/9
```

### A3. Approval Verification

```
1. Check C-02 Approval State
2. Verify: APPROVED (not REJECTED/expired)
3. Check approval scope matches intended action
4. Check approval ID is present
```

---

## Phase B: Execution

### B1. Simulate First

```
1. Click "Simulate" button
2. Read simulation result
3. Verify: SIMULATED (not REJECTED)
4. Note: "SIMULATED — not a guarantee"
5. If REJECTED: do NOT proceed to execute
```

### B2. Preview

```
1. Click "Preview" button
2. Read action summary
3. Verify: 9/9 conditions met
4. Note: "Preview does not guarantee execution"
```

### B3. Execute

```
1. Click "Execute Manual Action"
2. Read confirmation dialog carefully
3. Verify chain status in dialog
4. Click "Confirm & Execute"
5. Wait for response (synchronous)
6. Read result:
   - EXECUTED: action completed
   - REJECTED: chain failed (record block code)
   - FAILED: execution error (record error summary)
7. Record receipt ID
```

---

## Phase C: Post-Execution

### C1. Verify Receipt

```
1. Check displayed receipt ID (RCP-*)
2. Verify decision matches expectation
3. Check C-07 Action Log for entry
4. Check C-09 Audit Log for trace
```

### C2. Monitor

```
1. Refresh status (Phase 8 Refresh button)
2. Verify system state after action
3. Check for unexpected state changes
4. Check C-08 Error Log for issues
```

### C3. Document

```
1. Record receipt ID in operational log
2. Record timestamp
3. Record operator identity
4. Record decision and reason
5. File evidence per operating constitution
```

---

## Phase D: Recovery (If Needed)

### D1. Rollback

```
Prerequisites:
- Original receipt ID known
- 9-stage chain still 9/9
- Operator authorized

Steps:
1. Click "Rollback"
2. Confirm in dialog
3. Wait for response
4. Record rollback receipt ID
5. Verify reversal in system state
```

### D2. Retry

```
Prerequisites:
- Original receipt ID known
- 9-stage chain re-evaluated (fresh, not cached)
- Operator authorized

Steps:
1. Click "Retry"
2. Confirm in dialog
3. Wait for response
4. Record retry receipt ID
5. Verify result
```

---

## 운영 리허설 (Operational Rehearsal)

Before first production use, conduct a full rehearsal:

### Rehearsal Scenario 1: Blocked State

```
1. Open dashboard with chain < 9/9
2. Verify: Execute button disabled
3. Verify: All recovery buttons disabled
4. Verify: Guard messages visible
5. Verify: NO EXECUTION label visible
6. Attempt: Click execute → nothing happens
Expected: No execution, no receipt, no POST
```

### Rehearsal Scenario 2: Simulate in Blocked State

```
1. With chain partially met
2. Click Simulate (if enabled)
3. Expected: REJECTED with block code
4. Verify: simulation_note says "not a guarantee"
```

### Rehearsal Scenario 3: Allowed State (Controlled)

```
1. Ensure all 9 conditions met
2. Click Simulate → verify SIMULATED
3. Click Preview → verify action summary
4. Click Execute → confirm dialog
5. Cancel first (do NOT confirm)
6. Verify: no execution occurred
7. Click Execute again → Confirm
8. Record receipt ID
9. Verify: receipt shows EXECUTED
10. Check audit log
```

### Rehearsal Scenario 4: Re-Close

```
1. After successful execution
2. Intentionally reduce one condition (e.g., drop score below 0.7)
3. Verify: Execute button becomes disabled
4. Verify: Badge returns to BLOCKED
5. Attempt execute → nothing happens
```

### Rehearsal Scenario 5: Recovery

```
1. After successful execution in rehearsal
2. Click Rollback with original receipt ID
3. Verify: rollback receipt generated
4. Click Retry with original receipt ID
5. Verify: retry receipt generated
```

### Rehearsal Sign-Off

| Scenario | Operator | Date | Result |
|----------|----------|------|--------|
| 1. Blocked | _______ | _______ | PASS / FAIL |
| 2. Simulate | _______ | _______ | PASS / FAIL |
| 3. Allowed | _______ | _______ | PASS / FAIL |
| 4. Re-Close | _______ | _______ | PASS / FAIL |
| 5. Recovery | _______ | _______ | PASS / FAIL |

All 5 scenarios must PASS before production authorization.
