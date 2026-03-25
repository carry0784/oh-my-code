# C-04 Operator Checklist

**version**: 1.0
**date**: 2026-03-26

---

## Pre-Execution Checklist

Before clicking "Execute Manual Action", verify ALL of the following:

### System State
- [ ] Pipeline state = ALL_CLEAR
- [ ] Preflight decision = READY
- [ ] Gate decision = OPEN
- [ ] Ops score >= 0.7
- [ ] Trading authorized = true
- [ ] Lockdown = inactive (not LOCKDOWN/QUARANTINE)

### Approval State
- [ ] Approval decision = APPROVED
- [ ] Approval not expired
- [ ] Approval scope matches intended action
- [ ] Policy decision = MATCH

### Evidence Chain
- [ ] Preflight evidence ID = real (not fallback-*)
- [ ] Gate evidence ID = present
- [ ] Approval ID = present

### Operator Readiness
- [ ] I understand what this action will do
- [ ] I have reviewed the prerequisite matrix
- [ ] I confirm this is a manual, intentional action
- [ ] I am the authorized operator for this action

### C-04 Card State
- [ ] Met count shows 9/9
- [ ] Execute button is enabled (green)
- [ ] No BLOCKED badge visible
- [ ] No guard warning messages visible

---

## During Execution

1. Click "Execute Manual Action"
2. Review confirmation dialog
3. Verify chain status in confirmation
4. Click "Confirm & Execute" only if all conditions verified
5. Wait for synchronous response
6. Do NOT navigate away during execution

---

## Post-Execution Checklist

- [ ] Receipt ID displayed (RCP-*)
- [ ] Decision shows EXECUTED / REJECTED / FAILED
- [ ] If REJECTED: note block code and reason
- [ ] If FAILED: note error summary
- [ ] Verify receipt matches intended action
- [ ] Record receipt ID for audit trail

---

## Recovery Checklist (Rollback / Retry)

Before using Rollback or Retry:

- [ ] Original receipt ID is known
- [ ] 9-stage chain is still 9/9 PASS
- [ ] I understand rollback will reverse the action
- [ ] I understand retry will re-attempt with fresh chain validation
- [ ] Two-step confirmation will be required

---

## 실환경 연결 테스트

Before first production use, operator must verify:

| # | Check | How | Expected |
|---|-------|-----|----------|
| 1 | Dashboard loads | Navigate to /dashboard | 200 OK |
| 2 | Tab 3 renders | Click "운영 상태" tab | C-04 card visible |
| 3 | Chain data live | Check met count updates | Reflects real system state |
| 4 | Blocked state correct | Verify disabled buttons match chain state | Consistent |
| 5 | Safety summary endpoint | Check `/api/ops-safety-summary` | 200 OK with real data |
| 6 | Simulate works | Click Simulate when chain allows | SIMULATED receipt |
| 7 | Preview works | Click Preview | Action summary text |

---

## Forbidden Actions

NEVER do the following:

- Execute when any guard warning is visible
- Execute when met count < 9/9
- Execute without reading the confirmation dialog
- Execute multiple times without reviewing previous receipt
- Modify browser console/DOM to bypass disabled state
- Use API directly to bypass UI confirmation
- Execute during system maintenance or lockdown
- Execute without operator authorization

---

## Incident Response

If execution produces unexpected result:

1. Record receipt ID immediately
2. Do NOT retry automatically
3. Check C-08 Error Log for details
4. Check C-09 Audit Log for trace
5. Report to system administrator
6. Follow `c04_reclose_and_incident_policy.md`
