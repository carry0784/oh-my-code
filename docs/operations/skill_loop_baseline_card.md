# K-Dexter Skill Loop -- Baseline Card

> **Frozen**: 2026-03-30
> **Baseline Commit**: `09bab26`

---

## System Metrics

| Metric | Value |
|--------|-------|
| Total tests | 54 |
| Test suites | 3 (governance 29, regression 14, monitor 11) |
| System validation checks | 9 |
| Governance rules | 8 (GC-01~08) |
| Boundary prohibitions | 6 (P-01~P-06) |
| AutoFix policy entries | 24 (8 types x 3 recurrences) |
| Protected files | 8 |
| Prohibited changes | 8 |
| CLI commands | 7 (run, list, board, approve, reject, apply, block) |
| Apply Guard checks | 4 (receipt, tests, governance, commit) |
| Cooldown window | 24 hours (per category) |
| Dashboard endpoints | 50+ |
| Constitution documents | 26 |
| K-Dexter engines | 18 |

---

## Grade System

| Grade | Risk Score | Meaning |
|-------|-----------|---------|
| GREEN | 0-2 | Normal operation |
| YELLOW | 3-7 | Warning, limited autofix |
| RED | 8+ | Manual intervention required |
| BLOCK | N/A | Governance violation, all halted |

---

## Risk Score Weights

| Item | Points |
|------|--------|
| test_failed | 1 |
| test_error | 2 |
| import_error | 3 |
| validation_fail | 2 |
| governance_violation | 5 |
| governance_warning | 2 |
| constitution_fail | 5 |
| live_path_touch | 3 |

## Recurrence Multipliers

| Level | Multiplier |
|-------|-----------|
| FIRST | x1.0 |
| REPEAT | x1.5 |
| PATTERN | x2.0 |

---

## AutoFix Policy

| Type | FIRST | REPEAT | PATTERN |
|------|-------|--------|---------|
| F-IMPORT | ALLOW | ALLOW | MANUAL |
| F-TEST | ALLOW | ALLOW | MANUAL |
| F-LINT | ALLOW | ALLOW | ALLOW |
| F-CONFIG | ALLOW | MANUAL | DENY |
| F-MIGRATION | MANUAL | DENY | DENY |
| F-ENDPOINT | ALLOW | MANUAL | DENY |
| F-GOVERNANCE | DENY | DENY | DENY |
| F-WORKER | ALLOW | MANUAL | DENY |

---

## Evolution Board States

```
PROPOSED --> APPROVED --> APPLIED
         \-> REJECTED
         \-> BLOCKED
```

---

## Key Files

| File | Role |
|------|------|
| `scripts/evaluate_results.py` | Risk score + grade evaluation |
| `scripts/autofix_loop.py` | Self-healing loop engine |
| `scripts/evolution_loop.py` | Proactive improvement proposals |
| `scripts/governance_check.py` | GC-01~08 rule enforcement |
| `scripts/validate_system.py` | 9-check system validation |
| `scripts/run_tests.py` | Scope-aware test runner |
| `scripts/inject_failure.py` | Synthetic failure injector |
| `tests/test_4state_regression.py` | 4-state regression guard |
| `tests/test_agent_governance.py` | 29-test governance guard |
| `tests/test_governance_monitor.py` | 11-test monitor guard |
| `docs/operations/skill_loop_ops_rules.md` | Operational rules (SEALED) |
| `docs/operations/templates/change_approval_receipt.md` | Change receipt template v1.2 |

---

## Seal Documents

| Document | Purpose |
|----------|---------|
| `skill_loop_seal_receipt_2026-03-30.md` | Component seal + test verification |
| `skill_loop_boundary_seal_2026-03-30.md` | Boundary prohibitions + operational controls |
| `skill_loop_final_seal_declaration.md` | Final seal declaration + mode transition |
| `skill_loop_baseline_card.md` | This card (frozen metrics reference) |
| `skill_loop_change_control_policy.md` | Change control procedures |

---

> Frozen: 2026-03-30 | Baseline: `09bab26` | Tests: 54/54 PASS
