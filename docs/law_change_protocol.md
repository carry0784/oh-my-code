# L-02: Change Protocol Law

**Card**: L-02
**Type**: Operational Law
**Date**: 2026-03-25
**Authority**: Under Constitution (C-46) and Law Freeze (L-01)

---

## 1. Scope

This law defines the mandatory protocol for every system change. No change to code, configuration, documentation, or infrastructure is valid unless it follows this protocol.

---

## 2. Card Lifecycle

Every change follows this lifecycle:

```
PROPOSE → SCOPE → REVIEW → IMPLEMENT → VERIFY → SEAL
```

### 2.1 PROPOSE

- Declare card number and series (C/L/A/P)
- State purpose in one sentence
- Identify target layer and subsystem

### 2.2 SCOPE

- List allowed files (exhaustive)
- List forbidden files (exhaustive)
- Declare blast radius (which seals/invariants affected)
- Scope freeze: once declared, no expansion without new card

### 2.3 REVIEW

- Constitutional comparison against applicable seals
- Forbidden pattern scan
- Verify scope does not violate sealed subsystems
- Confirm no production behavior change (for law/audit/phase cards)

### 2.4 IMPLEMENT

- Work within declared scope only
- No scope creep
- No opportunistic refactoring
- No undeclared changes

### 2.5 VERIFY

- Run targeted tests
- Run full regression (`pytest -q`)
- Confirm 0 failures
- Confirm no sealed test modification

### 2.6 SEAL

- Submit modified files list
- Submit constitutional comparison review
- Submit test results
- Receive GO / NO-GO

---

## 3. Card Series Rules

| Series | Purpose | Creates Code | Creates Docs | Creates Tests |
|--------|---------|:---:|:---:|:---:|
| C-xx | Feature/implementation | Yes | Optional | Yes |
| L-xx | Law definition | No | Yes | No |
| A-xx | Audit/verification | No | Optional | Yes |
| P-xx | Phase/deployment | No | Yes | Optional |

### 3.1 Series Authority

- L-series cards are subordinate to Constitution only
- C-series cards are subordinate to Law and Constitution
- A-series cards enforce Law and Constitution
- P-series cards define operational phases under Law

---

## 4. Mandatory Submission Format

Every card must submit:

```
## 1) Modified files
| File | Action | Reason |

## 2) Constitutional comparison review
| Item | Content |

## 3) Test results
- New tests:
- Regression:

## 4) Final decision: GO / NO-GO
```

Submissions missing any section are automatically NO-GO.

---

## 5. Single-Card Rule

- One card = one task
- Mixed work forbidden
- Scope expansion forbidden
- If additional work discovered, create a new card

---

## 6. Baseline Rule

- Start only from clean baseline
- If regression not clean, create repair card first
- Never implement on dirty baseline
- Baseline test count must not decrease

---

## 7. Sealed Subsystem Change Rule

Changing a sealed subsystem requires:

1. Constitutional card (not regular feature card)
2. Seal document comparison
3. All lock tests pass unmodified
4. Blast radius declaration covering all downstream effects
5. Explicit GO with constitutional authority

---

*Enacted by Card L-02.*
