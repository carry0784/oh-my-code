# L-05: Phase Law

**Card**: L-05
**Type**: Operational Law
**Date**: 2026-03-25
**Authority**: Under Constitution (C-46) and Law Freeze (L-01)

---

## 1. Phase Definition

The system operates in one of three phases at any time:

| Phase | Code | Description |
|-------|------|-------------|
| **Development** | `dev` | Active implementation, testing, iteration |
| **Staging** | `staging` | Pre-production validation, integration testing |
| **Production** | `prod` | Live operation with real resources |

---

## 2. Current Phase

**Current phase: `dev`**

The system remains in `dev` until an explicit phase transition card (P-series) moves it to `staging`.

---

## 3. Phase Transition Rules

### 3.1 dev → staging

Required:

1. Full regression clean
2. Full constitution audit (A-series card) passed
3. All sealed subsystems verified
4. All law documents finalized
5. Deployment configuration documented
6. Explicit GO from review process

### 3.2 staging → prod

Required:

1. Full regression clean in staging environment
2. Integration test suite passed
3. Full audit passed in staging
4. Operational runbook complete
5. Emergency procedures tested
6. Monitoring and alerting verified
7. Explicit GO from review process

### 3.3 prod → dev (rollback)

Permitted only under:

1. Emergency override (L-03)
2. Critical failure in production
3. Must follow emergency protocol
4. Must create post-rollback audit card

---

## 4. Phase-Specific Rules

### 4.1 dev Phase

- Code changes follow card protocol (L-02)
- Testnet mode enabled by default
- All changes regression-verified
- Constitution and law are active and binding

### 4.2 staging Phase

- No new feature cards without staging validation
- Configuration must match production intent
- External integrations tested against sandboxes
- Performance baseline established

### 4.3 prod Phase

- Changes require elevated review
- Emergency override protocol active (L-03)
- Monitoring mandatory
- Audit trail mandatory
- No experimental changes

---

## 5. Phase Enforcement

- Phase is declared, not automatic
- Phase transitions require explicit P-series card
- Backward phase transitions require justification
- Phase cannot be skipped (dev → prod without staging is forbidden)

---

## 6. Implementation Deferral

Phase enforcement mechanisms (runtime checks, configuration guards, deployment automation) are deferred to P-01 implementation card. This law defines the rules. P-01 will implement them.

---

*Enacted by Card L-05.*
