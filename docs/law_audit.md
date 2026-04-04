# L-04: Audit Law

**Card**: L-04
**Type**: Operational Law
**Date**: 2026-03-25
**Authority**: Under Constitution (C-46) and Law Freeze (L-01)

---

## 1. Audit Purpose

Audit exists to **verify constitutional compliance** across all system layers. Audit is not optional. Audit results are binding.

---

## 2. Audit Types

| Type | Trigger | Scope | Card Series |
|------|---------|-------|:-----------:|
| **Card Audit** | Every card submission | Card scope only | Built into card |
| **Full Audit** | On demand, phase transition, post-emergency | Entire system | A-series |
| **Layer Audit** | Seal modification proposal | Target layer | A-series |
| **Emergency Audit** | After emergency override | Override scope + blast radius | A-series |

---

## 3. Card Audit Requirements

Every card must include the following audit evidence in its submission:

1. **Modified files list** — exhaustive
2. **Constitutional comparison** — against applicable seals
3. **Forbidden pattern scan** — grep evidence
4. **Regression results** — `pytest -q` output
5. **Scope compliance** — no undeclared changes

Missing any item = automatic NO-GO.

---

## 4. Full Audit Checklist

A full audit (A-series card) must verify:

### 4.1 Constitution Compliance

- [ ] All articles of `system_final_constitution.md` are satisfied
- [ ] Layer hierarchy is preserved
- [ ] State ownership rules are preserved
- [ ] Fail-closed doctrine is maintained

### 4.2 Seal Compliance

- [ ] Retry layer seal invariants hold
- [ ] Notification layer seal invariants hold
- [ ] Execution layer seal invariants hold
- [ ] Engine layer seal invariants hold
- [ ] Governance layer seal invariants hold

### 4.3 Boundary Compliance

- [ ] C-40 execution boundary lock tests pass
- [ ] Card B sealed tests pass (57)
- [ ] No forbidden patterns in `app/`
- [ ] No cross-layer violations

### 4.4 Law Compliance

- [ ] Change protocol followed (L-02)
- [ ] No unauthorized emergency overrides (L-03)
- [ ] Audit evidence complete (L-04)

### 4.5 Regression

- [ ] Full regression clean
- [ ] Test count has not decreased
- [ ] No sealed tests modified

---

## 5. Audit Evidence Standards

| Evidence | Standard |
|----------|----------|
| Pattern scan | Automated grep, not manual review |
| Boundary test | Automated pytest, not manual check |
| Regression | Full `pytest -q`, not partial |
| Comparison | Explicit item-by-item, not summary |
| Scope check | File diff, not verbal claim |

Subjective judgment alone is insufficient. Audits must be reproducible.

---

## 6. Audit Failure Consequences

| Severity | Condition | Consequence |
|----------|-----------|-------------|
| **Critical** | SSOT bypass, sealed layer violation | System freeze until repaired |
| **High** | Missing audit evidence, scope violation | Card NO-GO, repair required |
| **Medium** | Incomplete pattern scan | Card blocked until scan complete |
| **Low** | Documentation gap | Card may proceed with documentation fix |

---

## 7. Audit Independence

- Audit tests must be automated where possible
- Audit results must not depend on the implementer's self-assessment alone
- C-40 boundary lock tests provide automated structural audit
- Future A-series cards should expand automated audit coverage

---

*Enacted by Card L-04.*
