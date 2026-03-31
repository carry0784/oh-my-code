# Post-Pilot Change Control: Freeze Exit Approval

Effective: 2026-05-08
Status: **ACTIVE**
Author: B (Implementer)
Approved by: A (Designer/Inspector)
Supersedes: Change Freeze Window (h_pilot_log.md §Change Freeze Window)

---

## 1. Purpose

The 30-day pilot change freeze (2026-03-31 to 2026-05-08) has ended with
a PASS result. This document formally lifts the freeze and establishes
the permitted change scope for the post-pilot period.

**The freeze lift is NOT a return to unrestricted development.**
All changes remain subject to D-3 change control and intake registry.

---

## 2. Freeze Exit Declaration

| Item | Value |
|------|-------|
| Freeze period | 2026-03-31 to 2026-05-08 |
| Freeze violations | 0 |
| Exit trigger | G-1 §8 Pilot PASS |
| Exit date | 2026-05-08 |
| Approved by | A (Designer/Inspector) |

---

## 3. Post-Pilot Change Levels

### L1 — Permitted (Category A/B, self-review)

Changes that do NOT affect the sealed observation system:

| Scope | Examples |
|-------|---------|
| Documentation | Typo fixes, formatting, new non-observation docs |
| Governance calendar | Schedule updates, status marking, backfill entries |
| Operational scripts | Check scripts, runner configs |
| Read-only tooling | Dashboard improvements (read-only), monitoring |
| Test additions | New tests that do not relax existing assertions |
| Evidence documents | Seal receipts, audit records, closure packs |

**Process**: B implements, logs in intake registry, self-review commit note.

### L2 — Conditional (Category B/C, requires registry + review)

Changes that touch code but do NOT alter the sealed observation layer:

| Scope | Examples | Condition |
|-------|---------|-----------|
| Exchange removal/cleanup | OKX references in docs (already done in code) | Verify 832/0/0 after |
| Test runner fixes | Collection artifact normalization | No test relaxation |
| Config cleanup | Dead config fields, env examples | No runtime behavior change |
| Infrastructure | Dependency updates, CI config | Verify 832/0/0 after |
| Observability additions | New metrics, logging (read-only) | No write paths |
| Governance tool changes | Grep patterns, verification scripts | Default to Category C |

**Process**: Register in intake registry BEFORE implementing. B implements
with self-review. Verify 832/0/0 baseline after. A reviews if Category C.

**Boundary classification rules (CR-022 + CR-025 calibration):**
- Changes touching validation surface (grep patterns, governance check
  procedures, red line verification tools): **default to Category C**
- Any board field addition/removal: **default to L3/C** (not L3/D unless
  field controls a safety invariant or red line — CR-025 #3 resolution)

### L3 — Prohibited (requires constitutional review)

Changes to the sealed observation system remain frozen:

| Scope | Reason |
|-------|--------|
| Execution paths (action_allowed, write paths) | Safety invariant |
| Decision safety fields | Constitutional protection |
| Prediction language in observation layer | Red line 4 |
| Imperative verbs in observation layer | Red line 5 |
| Board field additions/removals | Sealed at 24 fields |
| Schema modifications to observation cards | Sealed |
| Safety boolean default changes | Red line 7 |
| Observation-decision merge | Red line 8 |
| Alert triggers in observation layer | Red line 10 |
| BINANCE_TESTNET=false with active workers | Production gate required (separate CR) |

**Process**: D-3 Category D constitutional amendment. Requires A+B+C
unanimous review. Not expected during post-pilot stabilization.

**Exchange target rule**: Read-only activation (Mode 1) with a production
exchange target cannot pass the warm-start gate. Testnet is mandatory
for first activation. Production mode requires a separate gate approval.

---

## 4. Baseline Regression Rule

Every L2 change MUST include a regression check:

```bash
# Observation tests (520)
python -m pytest tests/test_four_tier_board.py tests/test_observation_summary.py \
  tests/test_decision_card.py tests/test_observation_summary_schema.py \
  tests/test_decision_schema_typing.py tests/test_stale_contract.py \
  tests/test_threshold_calibration.py tests/test_4state_regression.py \
  tests/test_cleanup_simulation.py tests/test_cleanup_policy.py \
  tests/test_orphan_detection.py tests/test_order_executor.py \
  tests/test_submit_ledger.py tests/test_execution_ledger.py \
  tests/test_agent_action_ledger.py tests/test_operator_decision.py \
  --tb=no -q

# Governance tests (312)
python -m pytest tests/test_agent_governance.py tests/test_ops_checks.py \
  tests/test_market_feed.py tests/test_dashboard.py --tb=no -q

# Expected: 832 passed, 0 failed, 0 warnings
```

If any test fails after an L2 change: **revert first, investigate second**.

---

## 5. Intake Registry Integration

All post-pilot changes follow the G-3 intake registry process:

1. Register change request (CR-ID) BEFORE implementation
2. Classify as L1/L2/L3 using this document
3. Implement (L1/L2 only; L3 requires constitutional review)
4. Run baseline regression (L2 required, L1 recommended)
5. Record outcome in registry

The next CR-ID is **CR-012**.

---

## 6. Weekly Governance Continuity

The G-2 governance sustainment loop continues post-pilot:

| Check | Frequency | Status |
|-------|-----------|--------|
| Governance test run | Weekly | Continues |
| Red line spot check | Weekly | Continues |
| Category drift review | Bi-weekly | Continues (backfill pending items first) |
| Full audit | Monthly | Continues |
| Constitution review | Quarterly | Next: 2026-06-30 |

---

## 7. Escalation

If any L3 change is attempted without constitutional review:

1. **Immediate**: Revert the change
2. **Log**: Record as exception event in pilot log successor
3. **Review**: A+B review within 24 hours
4. **Assess**: Determine if intentional violation or classification error
