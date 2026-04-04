# L-03: Emergency Override Law

**Card**: L-03
**Type**: Operational Law
**Date**: 2026-03-25
**Authority**: Under Constitution (C-46) and Law Freeze (L-01)

---

## 1. Emergency Definition

An emergency exists **only** when one or more of the following conditions are true:

| Condition | Example |
|-----------|---------|
| **Financial harm in progress** | Unintended order execution, position exposure |
| **Data integrity breach** | Database corruption, state machine inconsistency |
| **Security breach** | Unauthorized access, credential exposure |
| **Critical invariant broken** | SSOT bypassed, sealed layer corrupted |
| **System safety failure** | Fail-closed mechanism itself failing |

The following are **not** emergencies:

- Feature deadline pressure
- Performance degradation
- Test flakiness
- Operator inconvenience
- Notification delivery delay

---

## 2. Emergency Override Tiers

### Tier 1: Operator Lock (lowest risk)

- Disable auto-retry via gate (`gate.set_enabled(False)`)
- Set maintenance mode (`gate.set_maintenance(True)`)
- No code change required
- No constitutional review required
- Must be logged

### Tier 2: Configuration Override (medium risk)

- Change environment variables
- Disable webhook URLs
- Toggle testnet mode
- No code change
- Must be logged and audited within 24 hours

### Tier 3: Code Override (highest risk)

- Direct code modification without full card process
- Permitted only for Tier 1 emergency conditions
- Must be minimum change to restore safety
- Must be reversible
- Must be audited within 24 hours via A-series card

---

## 3. Override Protocol

### 3.1 Before Override

1. Confirm emergency condition exists (Section 1)
2. Determine override tier (Section 2)
3. Attempt lowest tier first
4. Document: what, when, why, who

### 3.2 During Override

1. Apply minimum change only
2. Do not expand scope
3. Do not fix unrelated issues
4. Do not refactor
5. Preserve reversibility

### 3.3 After Override

1. Log the override with timestamp and justification
2. Create audit card (A-series) within 24 hours
3. Run full regression
4. Verify all invariants restored
5. Determine if constitutional gap exists
6. If gap found, create amendment card

---

## 4. Override Limitations

Emergency override may **never**:

1. Permanently modify constitutional documents
2. Permanently disable governance gates
3. Create new execution paths outside SSOT
4. Permanently disable audit or logging
5. Override sealed subsystems without post-audit restoration
6. Establish precedent for future overrides
7. Be used retroactively to justify unauthorized changes

---

## 5. Override Evidence

Every override must produce:

| Evidence | Required |
|----------|:--------:|
| Timestamp | Yes |
| Operator identity | Yes |
| Emergency condition | Yes |
| Override tier | Yes |
| Changes made | Yes |
| Rollback plan | Yes |
| Post-override audit card number | Yes |

---

*Enacted by Card L-03.*
