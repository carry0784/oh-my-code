# F-01: Production Freeze

**Card**: F-01
**Type**: Freeze Declaration (no code change)
**Date**: 2026-03-25
**Phase**: prod
**Baseline**: 1673 passed, 0 failed

---

## 1. Freeze Declaration

The K-V3 system is in **production freeze** as of this card.

- **Phase**: prod
- **Baseline**: locked at 1673 passed, 0 failed
- **Governance**: active (constitution + laws + seals)
- **Change mode**: law-gated + elevated review required
- **APP_ENV**: production
- **is_production**: True

Production freeze means: the system is operational and no change may occur without following the full constitutional change procedure.

---

## 2. Allowed Changes

The following changes are permitted under production freeze:

| Change Type | Requirement |
|-------------|-------------|
| Law-approved change | L-series card with constitutional review |
| Card-defined change | Card number + scope + blast radius + review |
| Audit-passed change | A-01 + C-40 tests pass post-change |
| Operator-approved change | Explicit sign-off with receipt |
| Rollback/emergency | Per L-03 emergency override law |
| Bug fix | Card with regression evidence |

Every permitted change still requires the full procedure (Section 4).

---

## 3. Forbidden Changes

The following are **absolutely forbidden** under production freeze:

1. Direct code edit without card
2. Direct config edit without receipt
3. Runtime patch without card
4. Manual database edit
5. Manual log edit or deletion
6. Bypass audit (skip A-01 or C-40)
7. Bypass law (skip L-02 change protocol)
8. Bypass seal (modify sealed subsystem without constitutional card)
9. Bypass boundary (create new execution path outside SSOT)
10. Silent deployment
11. Undocumented restart
12. Testnet flag change without card
13. Governance disable attempt
14. Evidence or receipt deletion

Violation of any item triggers the violation rule (L-01 Section 9).

---

## 4. Required Procedure for Any Change

Every production change must complete all steps:

```
1. LAW REFERENCE    — identify applicable law (L-01~L-05)
2. CARD CREATION    — assign card number, declare scope
3. REVIEW           — constitutional comparison, forbidden scan
4. IMPLEMENTATION   — within declared scope only
5. AUDIT            — A-01 + C-40 tests pass
6. REGRESSION       — pytest -q → all pass, count not decreased
7. OPERATOR APPROVAL — explicit sign-off with receipt
```

Skipping any step invalidates the change.

---

## 5. Emergency Rule

Reference: L-03 (`law_emergency_override.md`)

- Override permitted only via L-03 law procedure
- Override must leave an evidence receipt
- Override must be audited within 24 hours (A-series card)
- Override does not establish precedent
- Override is the minimum change to restore safety

---

## 6. Rollback Rule

Reference: D-05 (`prod_rollback_override_procedure.md`)

- Rollback is always permitted (safety action)
- Rollback must be documented
- Rollback must preserve all evidence files
- Rollback must not delete logs, receipts, or evidence DB
- Post-rollback audit is required

---

## 7. Production Integrity Rule

- Production state is the source of truth
- No silent change is allowed
- No undocumented change is allowed
- No change may claim implicit authorization
- Every change must produce verifiable evidence
- Evidence must survive the change (no self-erasing changes)

---

## 8. Final Freeze Statement

**Production state is frozen.**
**All changes are law-gated.**
**All operations are audited.**
**No exception without constitutional authority.**

---

*Declared by Card F-01. Production freeze is now active.*
