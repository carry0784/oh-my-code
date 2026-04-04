# System Law Freeze

**Card**: L-01
**Type**: Operational Law (institutional, not feature)
**Date**: 2026-03-25
**Baseline at freeze**: 1631 passed, 0 failed
**Status**: FROZEN

---

## 1. Law Hierarchy

The K-V3 system is governed by a strict four-tier hierarchy. Each tier is subordinate to the tier above it. No tier may bypass, override, or contradict its superior.

```
CONSTITUTION  (supreme, immutable without amendment card)
     |
    LAW        (interprets constitution, restricts scope)
     |
    CARD       (implements under law, scoped and reviewed)
     |
    CODE       (obeys card, tested and regression-verified)
```

### 1.1 Binding Principle

- Constitution defines what the system **is**.
- Law defines what the system **may do**.
- Card defines what a specific change **will do**.
- Code implements what the card **approved**.

### 1.2 Supremacy Principle

No law may expand constitutional authority.
No card may violate law.
No code may exceed card scope.
Violation at any tier invalidates all tiers below it.

---

## 2. Law Scope

Law governs **permission and process**, not behavior logic.

### Law Governs

- Modification rules (what may be changed and how)
- Override rules (when exceptions are permitted)
- Audit rules (how compliance is verified)
- Deployment rules (how system transitions between phases)
- Operator rules (what operators may trigger)
- Emergency rules (how urgent situations are handled)
- Violation rules (what happens when rules are broken)

### Law Does Not Govern

- Runtime behavior logic (governed by code under card authority)
- Trading strategy (governed by engine under governance)
- Feature design (governed by card proposals)
- Algorithm implementation (governed by code review)

Law defines the **frame**. Cards fill the **content**.

---

## 3. Change Law

Every system change must satisfy the following requirements. A change that fails any requirement is invalid and must be rejected.

### 3.1 Mandatory Requirements

Every change must have:

1. **Card number** — A unique identifier (e.g., C-47, L-02, A-01)
2. **Scope declaration** — Explicit list of files and modules affected
3. **Blast radius** — Which subsystems, seals, or invariants are impacted
4. **Constitutional comparison** — Review against applicable seal documents
5. **Forbidden pattern scan** — Grep-verified absence of forbidden patterns
6. **Regression evidence** — Full `pytest -q` output showing all tests pass

### 3.2 Rejection Criteria

A change is automatically rejected if:

- Any mandatory requirement is missing
- Regression is not clean
- Sealed subsystem is modified without constitutional card
- Scope expands beyond card declaration
- Blast radius exceeds declared boundary
- Forbidden patterns are detected

### 3.3 Retroactive Authorization

A change cannot be approved after implementation by claiming it was implicitly allowed. All authorization must precede implementation.

### 3.4 Scope Freeze

Once a card's scope is declared and approved, it may not expand during implementation. If expanded scope is needed, a new card must be created.

---

## 4. Emergency Law

### 4.1 Emergency Definition

An emergency exists only when:

- System is in an unsafe state that risks data loss or financial harm
- A critical invariant is broken and cannot be deferred
- Operator lock is required to prevent ongoing damage
- Security breach requires immediate response

Operational inconvenience, feature urgency, and performance degradation are **not** emergencies.

### 4.2 Emergency Override Conditions

Emergency override is permitted only if **all** of the following are true:

1. The situation meets the emergency definition above
2. No standard card process can address it in time
3. The override is the minimum change needed to restore safety
4. An operator or authorized party initiates the override

### 4.3 Emergency Override Requirements

Every emergency override must:

1. **Be logged** — Record what was changed, when, why, and by whom
2. **Be reversible** — The override must be revertable to pre-override state
3. **Be minimal** — Only the minimum change to restore safety
4. **Be audited** — A post-emergency audit card must be created within 24 hours
5. **Not establish precedent** — Emergency actions do not authorize future similar actions

### 4.4 Emergency Limitations

Emergency override may **never**:

- Modify constitutional documents permanently
- Bypass governance layer permanently
- Create new execution paths outside SSOT
- Disable audit or logging permanently
- Override sealed subsystems without post-audit restoration

### 4.5 Post-Emergency Procedure

After an emergency override:

1. Create an audit card documenting the override
2. Verify all invariants are restored
3. Run full regression
4. Review whether the emergency exposed a constitutional gap
5. If gap found, create a constitutional amendment card

---

## 5. Audit Law

### 5.1 Audit Scope

Audit must verify compliance with:

- Constitution rules (all articles)
- Seal rules (all subsystem seals)
- SSOT rules (execution boundary)
- Boundary rules (layer isolation)
- Invariant rules (permanent conditions)
- Change rules (card process compliance)

### 5.2 Audit Triggers

Audit is required:

- Before any card receives GO
- After any emergency override
- At each phase transition (when phase system is implemented)
- On demand by operator

### 5.3 Audit Evidence

Audit must produce:

- Forbidden pattern scan results
- Boundary lock test results (C-40)
- Full regression results
- Constitutional comparison review
- Seal document compliance check

### 5.4 Audit Failure

Audit failure results in:

- Immediate NO-GO for pending cards
- System freeze until audit passes
- Mandatory repair card before new feature cards

### 5.5 Audit Independence

Audit must be verifiable by automated tests. Audit results must not depend on subjective judgment alone. Where possible, audit is enforced by structural tests (e.g., C-40 boundary lock tests).

---

## 6. Phase Law (Placeholder)

### 6.1 Declaration

The system will adopt a phased deployment model in a future card. The phases are declared but not yet implemented:

| Phase | Description | Status |
|-------|-------------|--------|
| `dev` | Development and testing | **Current** |
| `staging` | Pre-production validation | Not yet defined |
| `prod` | Production operation | Not yet defined |

### 6.2 Phase Transition Rule

Phase transitions will require:

- Full regression clean
- Full audit pass
- Constitutional compliance verification
- Explicit GO from review process

### 6.3 Phase Implementation

Phase implementation details are deferred to a future card (recommended: P-01). This law only declares the phase structure. It does not implement phase logic.

---

## 7. Law Override Rule

### 7.1 Law Cannot Override Constitution

Law may only **restrict** constitutional authority, never **expand** it.

Example:
- Constitution allows sealed subsystem modification via constitutional card.
- Law may add additional requirements (e.g., audit before modification).
- Law may **not** permit modification without constitutional card.

### 7.2 Override Direction

```
Constitution can restrict Law    → Yes
Law can restrict Cards           → Yes
Cards can restrict Code          → Yes

Law can override Constitution    → No
Cards can override Law           → No
Code can override Cards          → No
```

### 7.3 Law Amendment

Law may be amended by a dedicated Law card (L-series) that:

- Declares the amendment scope
- Justifies the change against constitution
- Includes constitutional comparison
- Receives explicit GO

---

## 8. Law Conflict Rule

### 8.1 Conflict Resolution Order

When rules conflict, resolution follows the hierarchy:

1. **Constitution wins** over all
2. **Law wins** over Card and Code
3. **Card wins** over Code
4. **Code** is the lowest authority

### 8.2 Ambiguity Rule

When a rule is ambiguous:

- The more restrictive interpretation prevails
- If still ambiguous, the change is blocked until clarified by a Law or Constitution card
- "Probably allowed" is not sufficient; explicit authorization is required

### 8.3 Cross-Layer Conflict

When two sealed subsystems have conflicting rules:

- The constitution's layer hierarchy (Article 1) determines precedence
- Higher-authority layer's seal prevails
- Resolution must be documented in a dedicated card

---

## 9. Law Violation Rule

### 9.1 Violation Detection

A violation is detected when:

- A change is implemented without a card
- A card exceeds its declared scope
- A sealed subsystem is modified without constitutional card
- Forbidden patterns are found in code
- Regression fails after a change
- Boundary lock tests fail
- Audit produces non-compliance results

### 9.2 Violation Consequences

When a violation is detected:

1. **Change rejected** — The violating change must be reverted
2. **Card rejected** — The associated card receives NO-GO
3. **Merge rejected** — The code change must not be merged
4. **Repair required** — A repair card must be created to restore compliance
5. **Audit required** — A post-violation audit must verify restoration

### 9.3 Violation Precedence

Violation consequences apply regardless of:

- Test results (passing tests do not authorize violations)
- Feature importance
- Deadline pressure
- Operational convenience
- Prior informal approval

### 9.4 Non-Retaliation

Detecting and reporting violations is a protected action. The violation is the problem, not its detection.

---

## 10. Final Freeze Declaration

The system law layer is **frozen** as of Card L-01.

- **Future changes must follow law.** No change is valid without a card that satisfies all mandatory requirements.
- **No change allowed without card.** Cardless changes are constitutionally invalid.
- **No card allowed without law.** Cards must satisfy the Change Law (Section 3).
- **No law allowed against constitution.** Law may restrict but never expand constitutional authority.

### Governance Chain

```
Constitution (C-46) governs Law (L-01)
Law (L-01) governs Cards (C-series, L-series, A-series, P-series)
Cards govern Code
Code is tested and regression-verified
```

### Card Series Designation

| Series | Purpose | Authority |
|--------|---------|-----------|
| C-xx | Feature/implementation cards | Under Law |
| L-xx | Law cards | Under Constitution |
| A-xx | Audit cards | Under Law |
| P-xx | Phase cards | Under Law |

### Final Statement

The K-V3 system is governed by constitution and law.
No change, feature, refactor, or override may bypass this governance.
This law is frozen and may only be amended by an explicit L-series card.

---

*Frozen by Card L-01. This document is the operational law authority for the K-V3 system.*
