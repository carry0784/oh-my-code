# CR-046: SOL/USDT Paper Rollout Execution Plan

Date: 2026-04-01
Authority: A (Decision Authority)
Status: **APPROVED -- paper trading GO**

---

## 1. Scope

| Item | Value |
|------|-------|
| Asset | SOL/USDT |
| Composition | SMC (pure-causal, Version B) + WaveTrend |
| Consensus | 2/2 agreement required |
| Timeframe | 1H |
| Mode | Paper / dry_run only |
| Duration | 2 weeks minimum (Phase 5a) |

---

## 2. Paper Trading Parameters

| Parameter | Value | Source |
|-----------|-------|--------|
| Stop-loss | 2.0% per trade | Canonical |
| Take-profit | 4.0% per trade | Canonical |
| Fee assumption | 0.075% (VIP) / 0.1% (non-VIP) | Phase 4 |
| Slippage assumption | 0.05% | Phase 4 |
| Max concurrent positions | 1 | Conservative |
| Daily loss limit | 5.0% | Risk management |
| Weekly trade cap | 15 trades max | Anomaly guard |
| Notional | Paper (no real capital) | Phase 5a |

---

## 3. Entry/Exit Rules

### Entry

1. SMC (pure-causal) generates BOS/CHoCH signal (+1 or -1)
2. WaveTrend generates cross signal in same direction
3. Both signals agree within same bar -> entry signal
4. Position opened at bar close price
5. No entry if daily loss limit reached

### Exit

1. Stop-loss at -2.0% from entry
2. Take-profit at +4.0% from entry
3. Reverse signal from core pair (close + open reverse)
4. End-of-day forced close if daily loss > 4% (warning threshold)

---

## 4. Monitoring During Paper Phase

### Daily Checks

| # | Check | Action if Failed |
|---|-------|------------------|
| 1 | Signal generation active | Investigate signal pipeline |
| 2 | Trades executed (paper) | Verify execution engine |
| 3 | PnL within daily limit | Auto-pause if exceeded |
| 4 | No system errors | Fix before next bar |

### Weekly Review

| # | Metric | Target | Alert |
|---|--------|--------|-------|
| 1 | Rolling Sharpe | > 0.3 | < 0 for 1 week |
| 2 | Win rate | > 40% | < 30% |
| 3 | Trade count | 3-8 | < 1 or > 15 |
| 4 | Max drawdown | < 15% | > 10% |
| 5 | PF | > 1.0 | < 0.8 |

---

## 5. Phase 5a -> 5b Promotion Criteria

Paper -> micro-notional requires ALL:

| Criterion | Threshold |
|-----------|-----------|
| Paper duration | >= 2 weeks |
| Cumulative Sharpe | > 0 |
| Win rate | > 35% |
| Max drawdown | < 20% |
| No system failures | 0 critical errors |
| A explicit approval | Required |

---

## 6. Phase 5a Execution Checklist

- [ ] Verify SMC + WaveTrend signal pipeline operational
- [ ] Configure dry_run mode in execution engine
- [ ] Set SOL/USDT as active pair
- [ ] Set 1H timeframe
- [ ] Configure stop-loss 2.0% / take-profit 4.0%
- [ ] Configure daily loss limit 5.0%
- [ ] Enable paper trade logging
- [ ] Verify monitoring dashboard functional
- [ ] Start paper trading
- [ ] Daily check: signal generation + PnL
- [ ] Weekly review: Sharpe + win rate + trade count
- [ ] End of Week 2: compile Phase 5a results for A review

---

## 7. Kill-Switch Rules

| Trigger | Action |
|---------|--------|
| Daily loss > 5% | Auto-pause, resume next day |
| Weekly loss > 10% | Pause until manual review |
| 3 consecutive losing days | Alert A, continue with caution |
| System error in execution | Pause until fixed |
| A override | Immediate stop |

---

## 8. Prohibited Actions

| Prohibition | Reason |
|-------------|--------|
| Switching to live/real capital | Phase 5a is paper only |
| Changing canonical composition | Requires full CR cycle |
| Adding regime filter to signals | Track C v1 filter NOT adopted |
| Trading ETH/USDT | ETH excluded from deployment |
| Disabling dry_run without A approval | Safety |

---

## Signature

```
CR-046 SOL/USDT Paper Rollout Plan
Mode: Paper / dry_run only
Duration: 2 weeks minimum
Approved by: A (Decision Authority)
Date: 2026-04-01
```
