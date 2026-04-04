# Shadow Run — Daily Log Template & 7-Day Acceptance Board

---

## Daily Log Template

```
=== Shadow Run Day [N] — [YYYY-MM-DD] ===

Process Status:
  Uptime since last restart: ___ hours
  Restarts today: ___

Evolution:
  Orchestrator cycles today: ___
  Strategies evolved: ___
  Registry size: ___ (delta: ___)
  Best fitness: ___

Governance:
  Decisions today: ___
  Auto-approved: ___
  PENDING_OPERATOR: ___
  Block rate: ___% (PENDING / total)

Lifecycle:
  New candidates: ___
  Validated: ___
  Paper trading active: ___
  Promoted: ___
  Demoted: ___
  Retired: ___
  Invalid transition attempts: ___

Paper Trading:
  Active sessions: ___
  Trades recorded today: ___
  Sessions closed: ___

Portfolio (if applicable):
  Optimizer method: ___
  Max weight: ___
  Weight drift: ___%
  Portfolio Sharpe: ___
  Portfolio drawdown: ___%

Health Monitor:
  is_healthy: ___
  Warnings: [list]
  Circuit breakers triggered: [list]

Reconciliation:
  [ ] All lifecycle records in valid states
  [ ] All registered genomes have lifecycle records
  [ ] All transitions have governance decisions
  [ ] Health monitor responsive (manual trigger test)

Stability Metrics:
  Optimizer output drift: ___% (threshold: <20%)
  PENDING_OPERATOR count: ___ (threshold: <20/day)
  Health warnings: ___ (threshold: <5/day)
  Fitness 3-day MA: ___ (direction: ___)

Day Assessment: PASS / FAIL / WATCH
Reason: ___
Operator Note: ___
```

---

## 7-Day Acceptance Board

| Day | Date | Cycles | Registry | Block Rate | Warnings | Drift | Fitness MA | Restarts | Assessment |
|-----|------|--------|----------|------------|----------|-------|-----------|----------|------------|
| 1 | — | — | — | — | — | — | — | — | — |
| 2 | — | — | — | — | — | — | — | — | — |
| 3 | — | — | — | — | — | — | — | — | — |
| 4 | — | — | — | — | — | — | — | — | — |
| 5 | — | — | — | — | — | — | — | — | — |
| 6 | — | — | — | — | — | — | — | — | — |
| 7 | — | — | — | — | — | — | — | — | — |

---

## Acceptance Criteria

### PASS (all must be true for 7 consecutive days):
- [ ] Optimizer output drift < 20% daily
- [ ] GovernanceGate block rate > 0% (proves gates work)
- [ ] PENDING_OPERATOR < 20 per day
- [ ] SystemHealth warnings < 2 per day average
- [ ] Fitness 3-day moving average non-decreasing
- [ ] Registry growth >= 1 entry per 2 days
- [ ] Orchestrator crash count = 0
- [ ] All 4 reconciliation checks pass daily

### FAIL (any one triggers):
- [ ] Optimizer drift > 40% in a single day
- [ ] Block rate = 100% for > 24 hours (nothing passes)
- [ ] PENDING_OPERATOR > 20 in a single day
- [ ] Health warnings > 5 in a single day
- [ ] Fitness monotonically decreasing for 3 days
- [ ] Registry 0 new entries after 7 days
- [ ] Orchestrator crash >= 1
- [ ] Any reconciliation check fails

### EXTEND (between PASS and FAIL):
- Acceptance thresholds met for 5/7 days → extend by 3 days
- Single non-critical warning spike → extend by 1 day

---

## Final Shadow Verdict

| Outcome | Criteria | Next Step |
|---------|----------|-----------|
| **SHADOW PROVEN** | 7/7 PASS days | Proceed to Operator Authorization |
| **SHADOW EXTENDED** | 5-6/7 PASS | Continue for 3 more days |
| **SHADOW FAILED** | Any FAIL trigger | HOLD — investigate root cause |

---

## Operator Approval Mock Exercise (Daily)

During shadow, operator performs 1 mock approval per day:

```
Mock Approval Day [N]:
  Genome ID: ___
  Current state: PAPER_TRADING
  Paper trades: ___
  Paper Sharpe: ___
  Paper win rate: ___
  Paper max DD: ___
  live_match_score: ___
  System healthy: ___

  Decision: APPROVE / HOLD / REJECT
  Reason: ___
```

This builds operational muscle memory before real approvals begin.
