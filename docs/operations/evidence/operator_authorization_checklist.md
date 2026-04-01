# Operator Authorization — 1-Page Checklist

**Purpose**: This is the single document an operator uses to approve or reject
a strategy promotion from PAPER_TRADING to PROMOTED.

---

## Pre-Conditions (ALL must be TRUE before reviewing)

| # | Check | Source | Status |
|---|-------|--------|--------|
| PC-1 | Kill-switch rehearsal completed (R-1~R-6) | killswitch_rehearsal_evidence.md | [ ] |
| PC-2 | Shadow run 7-day PASS | shadow_run_template.md | [ ] |
| PC-3 | R-04 accepted or resolved | r04_decision_memo.md | [ ] |
| PC-4 | System health is_healthy = True | SystemHealthReport | [ ] |
| PC-5 | No circuit breakers active | SystemHealthReport.warnings == [] | [ ] |

**If any PC fails: STOP — do not proceed to evaluation.**

---

## Strategy Evaluation (per genome)

| # | Criterion | Threshold | Actual | Pass? |
|---|-----------|-----------|--------|-------|
| E-1 | Paper trading trades | >= 20 | ___ | [ ] |
| E-2 | Paper trading duration | >= 168 hours (7 days) | ___ | [ ] |
| E-3 | Paper trading Sharpe | >= 0.5 | ___ | [ ] |
| E-4 | Paper trading win rate | >= 35% | ___ | [ ] |
| E-5 | Paper trading max drawdown | <= 20% | ___ | [ ] |
| E-6 | live_match_score | >= 0.65 | ___ | [ ] |
| E-7 | 5-stage validation status | PASSED | ___ | [ ] |
| E-8 | Previous demotions | < 2 | ___ | [ ] |
| E-9 | Portfolio drawdown (current) | < 15% | ___ | [ ] |
| E-10 | Governance queue | < 5 pending | ___ | [ ] |

---

## Decision Matrix

| All E-1~E-10 pass | Decision |
|-------------------|----------|
| YES | **APPROVE** — proceed to promotion |
| E-3 or E-4 or E-5 marginal (within 10%) | **HOLD** — extend paper trading 3 days |
| E-6 < 0.4 | **REJECT** — severe backtest-paper divergence |
| E-8 >= 2 | **REJECT** — pattern of poor real performance |
| Any E fails significantly | **HOLD** — investigate before re-evaluation |

---

## Post-Approval Actions

| # | Action | Owner | Deadline |
|---|--------|-------|----------|
| PA-1 | Confirm strategy in PROMOTED state | Operator | Immediate |
| PA-2 | Set portfolio weight <= initial allocation cap | System | Automatic |
| PA-3 | Verify health monitor still healthy | Operator | Within 1 hour |
| PA-4 | Schedule 72-hour probation review | Operator | +72 hours |
| PA-5 | Document approval in governance log | System | Automatic |

---

## Auto-Revocation Triggers (no operator action needed)

| Trigger | Action | Speed |
|---------|--------|-------|
| Strategy drawdown > risk_budget_pct | Auto-demote | Immediate |
| System health is_healthy = False | Auto-demote all | Immediate |
| Portfolio drawdown > max_dd_threshold | Auto-demote all | Immediate |

---

## Signature Block

```
Strategy Genome ID: _______________
Decision: APPROVE / HOLD / REJECT
Reason: _______________________________________________
Operator: _______________
Date: _______________
```

---

## Rejection/Hold Appeal

If rejected, the strategy may re-enter PAPER_TRADING (if not retired).
The operator documents the rejection reason and minimum conditions
for re-evaluation. No appeal bypasses the checklist above.
