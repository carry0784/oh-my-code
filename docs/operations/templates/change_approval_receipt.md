# Change Approval Receipt -- [CHANGE-ID]

> **Status**: PENDING / APPROVED / APPLIED / REJECTED
> **Date**: YYYY-MM-DD
> **Requester**: (who requested the change)
> **Approver**: (who approved)

---

## 0. Evolution Proposal Linkage

| Field | Value |
|-------|-------|
| Linked Proposal ID | (e.g. `EVO-20260330081903` or `N/A` if not from Evolution) |
| Proposal Status | PROPOSED / APPROVED / APPLIED / N/A |
| Origin | EVOLUTION / MANUAL / INCIDENT / MAINTENANCE |

> If this change originated from an Evolution proposal, record the `proposal_id` here.
> After applying, run `python scripts/evolution_loop.py apply <proposal_id> --commit <hash>` to sync status.

---

## 1. Change Purpose (1 sentence)

> (What this change does and why it is needed)

---

## 2. Affected Files

| File | Change Type | Protected? |
|------|------------|------------|
| `path/to/file.py` | MODIFY / DELETE / NEW | YES / NO |

---

## 3. Seal Rule Impact

| Rule | Contacted? | Detail |
|------|-----------|--------|
| P-01 (Order execution ban) | NO | |
| P-02 (Evolution proposal-only) | NO | |
| P-03 (GovernanceGate bypass ban) | NO | |
| P-04 (CostController required) | NO | |
| P-05 (PatternMemory learning-only) | NO | |
| P-06 (AutoFix scope limits) | NO | |
| Ops Rules (skill_loop_ops_rules.md) | NO | |
| Boundary Seal (boundary_seal) | NO | |

---

## 4. Revalidation Results

| Check | Result | Detail |
|-------|--------|--------|
| `pytest test_agent_governance.py` | PASS / FAIL | __/29 |
| `pytest test_4state_regression.py` | PASS / FAIL | __/14 |
| `pytest test_governance_monitor.py` | PASS / FAIL | __/11 |
| `inject_failure.py --mode scenario-all` | PASS / FAIL | __/4 |
| **Total** | | __/58 |

---

## 5. Approval Decision

- [ ] All tests pass
- [ ] No seal rule violation
- [ ] Governance review completed
- [ ] Change is necessary and minimal

**Decision**: APPROVED / REJECTED
**Reason**: (1 sentence)

---

## 6. Applied

> **Applied At**: YYYY-MM-DDTHH:MM:SSZ
> **Commit**: `(hash)`
> **Verified After Apply**: YES / NO

---

## 7. Force Override Record

> Complete this section ONLY if `--force` was used during `apply`.

| Field | Value |
|-------|-------|
| Forced Apply Used | YES / NO |
| Force Reason | (Why guard checks could not be satisfied normally) |
| Which Guards Failed | RECEIPT / TESTS / GOVERNANCE / COMMIT |
| Additional Reviewer | (Name of second reviewer who confirmed the force) |
| Post-Force Revalidation | (Date + result of full revalidation after forced apply) |

> **Rule**: Every forced apply MUST have this section filled.
> Unfilled force records are treated as governance violations.

---

> Template version: 1.2 (2026-03-30)
> Source: skill_loop_boundary_seal_2026-03-30.md
> Changes:
> - 1.0: Initial template
> - 1.1: Added Evolution Proposal Linkage (Section 0)
> - 1.2: Added Force Override Record (Section 7)
