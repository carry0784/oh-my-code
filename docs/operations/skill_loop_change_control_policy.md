# K-Dexter Skill Loop -- Change Control Policy

> **Status**: ACTIVE
> **Effective**: 2026-03-30
> **Scope**: All files within the Skill Loop boundary

---

## 1. General Principle

The Skill Loop is a **sealed operational core**. All changes are prohibited by default and require explicit approval through the procedures defined in this document.

---

## 2. Change Categories

| Category | Risk | Approval Level |
|----------|------|---------------|
| **Critical** (governance rules, BLOCK logic, grade thresholds) | HIGH | Governance review + full revalidation |
| **Standard** (autofix policy, cooldown tuning, Evolution templates) | MEDIUM | Change receipt + test revalidation |
| **Documentation** (ops rules updates, receipt template) | LOW | Change receipt + review |
| **Data** (grade_history reset, pattern cleanup) | MEDIUM | Change receipt + justification |

---

## 3. Standard Change Procedure

### Step 1: Identify

- Determine change category (Critical / Standard / Documentation / Data)
- Check if change touches sealed files (see Baseline Card)
- Check P-01~P-06 impact

### Step 2: Propose

If change originates from Evolution Loop:
```bash
python scripts/evolution_loop.py board   # review pending proposals
python scripts/evolution_loop.py approve <proposal_id>
```

If manual change:
- Document purpose in 1 sentence
- List affected files

### Step 3: Receipt

Create `docs/operations/evidence/change_receipt_YYYY-MM-DD_<id>.md` using template:
```
docs/operations/templates/change_approval_receipt.md
```

Fill all sections:
- Section 0: Evolution Proposal Linkage
- Section 1: Change Purpose
- Section 2: Affected Files
- Section 3: Seal Rule Impact (P-01~P-06)
- Section 4: Revalidation Results
- Section 5: Approval Decision

### Step 4: Implement

- Make changes in a branch
- Run revalidation:

```bash
pytest tests/test_agent_governance.py tests/test_4state_regression.py tests/test_governance_monitor.py -v
python scripts/inject_failure.py --mode scenario-all
```

- Record results in receipt Section 4

### Step 5: Apply

If from Evolution proposal:
```bash
python scripts/evolution_loop.py apply <proposal_id> --commit <hash>
```

Apply Guard will verify:
- Receipt exists
- Tests pass (GREEN/YELLOW)
- Governance not BLOCK
- Commit hash provided

### Step 6: Verify

- Confirm 54/54 tests pass
- Confirm 4/4 synthetic states pass
- Update receipt Section 6 (Applied)

---

## 4. Force Override Procedure

When Apply Guard fails but change is urgent:

### Step 1: Use --force

```bash
python scripts/evolution_loop.py apply <proposal_id> --commit <hash> --force
```

### Step 2: Fill Section 7

In the change receipt, complete ALL fields:

| Field | Required |
|-------|----------|
| Forced Apply Used | YES |
| Force Reason | (mandatory) |
| Which Guards Failed | (list all) |
| Additional Reviewer | (mandatory - name of second person) |
| Post-Force Revalidation | (date + full result within 24h) |

### Step 3: Post-Force Revalidation

Within 24 hours of forced apply:
- Run full test suite
- Run 4-state verification
- Record results in receipt
- If revalidation fails: rollback change

### Rule

> **Unfilled force records are treated as governance violations.**

---

## 5. Prohibited Changes (Always Denied)

These changes are NEVER approved regardless of procedure:

1. BLOCK override implementation
2. Apply Guard removal or weakening
3. GovernanceGate bypass
4. AutoFix policy weakening (DENY -> ALLOW without review)
5. Evolution auto-apply
6. Skill Loop order execution capability
7. Grade history manipulation
8. Regression test removal or weakening

---

## 6. Revalidation Requirements by Category

| Category | Tests Required | Synthetic 4-State | Receipt |
|----------|---------------|-------------------|---------|
| Critical | 54/54 | 4/4 | Full (all sections) |
| Standard | 54/54 | Recommended | Sections 0-5 |
| Documentation | N/A | N/A | Sections 0-2, 5 |
| Data | 54/54 | 4/4 | Full (all sections) |

---

## 7. Operational Rhythm

| Frequency | Action | Owner |
|-----------|--------|-------|
| Daily | Check evaluation-status dashboard | Operator |
| Weekly | Review evolution board, run synthetic verification | Operator |
| Pre-Release | Full revalidation (54 tests + 4-state) | Operator |
| On Change | Receipt + revalidation + evidence | Requester + Approver |

---

## 8. Escalation

| Situation | Action |
|-----------|--------|
| Test failure after change | Rollback immediately, investigate |
| BLOCK state after change | Halt all operations, human review |
| Force used without Section 7 | Governance violation, require audit |
| Repeated force usage (3+ in 7 days) | Suspend change authority, review process |

---

> Effective: 2026-03-30
> Applies to: All Skill Loop boundary files
> Review: Upon policy change request or quarterly
