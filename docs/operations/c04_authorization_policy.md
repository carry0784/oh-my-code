# C-04 Authorization Policy

**version**: 1.0
**date**: 2026-03-26
**scope**: C-04 Manual Action production execution authorization

---

## Core Principle

C-04 completion does not grant unconditional production execution authority. Every execution requires explicit, traceable, condition-verified authorization.

---

## 1. Authorization Chain

Production execution requires ALL of the following:

| # | Requirement | Source |
|---|-------------|--------|
| 1 | 9-stage chain = 9/9 PASS | Runtime validation |
| 2 | Operator identity verified | Authentication system |
| 3 | Two-step confirmation completed | UI confirmation dialog |
| 4 | Server-side chain revalidation | Endpoint `_build_ops_safety_summary()` |
| 5 | Receipt generated | `ManualActionReceipt` |
| 6 | Audit recorded | `audit_id` on every attempt |
| 7 | Operating Constitution compliance | `docs/operations/operating_constitution.md` |

Missing any one = execution REJECTED.

---

## 2. 9-Stage Chain Requirements

| Stage | Condition | Fail = |
|-------|-----------|--------|
| Pipeline | ALL_CLEAR | PIPELINE_NOT_READY |
| Preflight | READY | PREFLIGHT_NOT_READY |
| Gate | OPEN | GATE_CLOSED |
| Approval | APPROVED | APPROVAL_REQUIRED |
| Policy | MATCH | POLICY_BLOCKED |
| Risk | ops_score >= 0.7 | RISK_NOT_OK |
| Auth | trading_authorized = true | AUTH_NOT_OK |
| Scope | lockdown != LOCKDOWN/QUARANTINE | SCOPE_NOT_OK |
| Evidence | non-null, non-fallback | EVIDENCE_MISSING |

---

## 3. Authorization Levels

| Level | Scope | Authority |
|-------|-------|-----------|
| **Level 0** | View only | Read dashboard, no action |
| **Level 1** | Simulate/Preview | Simulation + preview (read-only chain check) |
| **Level 2** | Execute | Full chain-gated manual execution |
| **Level 3** | Recovery | Manual rollback/retry (requires original receipt) |

Each level requires the previous level's conditions plus additional verification.

---

## 4. Forbidden Under All Authorization Levels

- Automatic execution
- Background execution
- Queue/worker/bus-triggered execution
- Execution without 9-stage chain satisfaction
- Execution without receipt
- Execution without audit
- Execution with optimistic state
- Execution with cached/stale chain data
- Execution bypassing two-step confirmation

---

## 5. Authorization Revocation

Authorization is immediately revoked when:

- Any chain stage falls below threshold
- Operator session expires
- Lockdown/quarantine activated
- Evidence chain broken (fallback-* detected)
- Manual override by system administrator
- Incident declared

---

## 6. 실운영 승인 테스트

Production authorization requires passing the following pre-production tests:

| # | Test | Method | Pass Criteria |
|---|------|--------|---------------|
| 1 | Chain validation accuracy | Compare handler output vs actual system state | 9/9 alignment |
| 2 | Receipt generation | Execute with 9/9 → verify receipt fields | All fields non-empty |
| 3 | Audit generation | Execute with 9/9 → verify audit_id | AUD-* present |
| 4 | Rejection on partial chain | Execute with 8/9 → verify REJECTED | Block code matches |
| 5 | Re-close after condition drop | Execute → drop 1 condition → verify re-blocked | REJECTED |
| 6 | Two-step confirmation flow | Click execute → confirm dialog → verify POST only after confirm | No POST before confirm |
| 7 | Server-side revalidation | Modify chain between client check and server call → verify server rejects | REJECTED |

All 7 tests must PASS before production authorization is granted.
