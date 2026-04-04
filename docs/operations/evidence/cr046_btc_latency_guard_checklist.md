# CR-046: BTC/USDT Latency Guard Operational Checklist

Date: 2026-04-01
Authority: A (Decision Authority)
Status: **APPROVED -- guarded paper trading only**

---

## Context

BTC/USDT is latency-sensitive (Phase 4: Sharpe drops 91% with 1-bar delay). This checklist defines mandatory guards for BTC paper trading.

---

## Pre-Trade Checklist (Every Trade)

| # | Check | Pass Condition | Fail Action |
|---|-------|----------------|-------------|
| 1 | Signal timing | Signal received within current bar | **SKIP trade** |
| 2 | Execution latency | Order placed within 5 seconds of signal | **SKIP trade** |
| 3 | Exchange connectivity | API response < 2 seconds | **SKIP trade** |
| 4 | Spread check | Bid-ask spread < 0.1% | **SKIP trade** |
| 5 | Daily loss check | Daily PnL > -5% | **HALT all trading** |
| 6 | Position check | No existing position | Close existing first |
| 7 | Kill-switch status | Not triggered | **NO trading** |

**Rule: If ANY check fails, the trade is SKIPPED. No exceptions.**

---

## Latency-Specific Guards

### Guard 1: Same-Bar Execution

```
Signal bar timestamp: T
Order must be placed before: T + 1H (next bar open)
If order placement > T + 55min: SKIP (too close to bar boundary)
```

### Guard 2: Execution Quality Monitor

| Metric | Acceptable | Alert | Halt |
|--------|------------|-------|------|
| Order fill time | < 5 sec | 5-30 sec | > 30 sec |
| Slippage per trade | < 0.1% | 0.1-0.2% | > 0.2% |
| Missed signals (skipped) | < 20% | 20-40% | > 40% |

### Guard 3: High-Latency Detection

If 3 consecutive trades have execution latency > 10 seconds:
1. Pause BTC trading
2. Log "HIGH_LATENCY_DETECTED"
3. Resume only after manual verification

---

## Daily Operations

### Morning Check (before first bar)

- [ ] Exchange API healthy
- [ ] Signal pipeline running
- [ ] Latency monitor active
- [ ] Kill-switch ready
- [ ] Previous day's results reviewed

### End-of-Day Review

- [ ] Count trades: expected 0-3 per day
- [ ] Count skipped signals: track skip rate
- [ ] Review latency distribution
- [ ] Review slippage per trade
- [ ] PnL within daily limit

---

## Weekly Review

| Metric | Target | Action if Failed |
|--------|--------|------------------|
| Skip rate | < 20% | Investigate connectivity |
| Avg execution latency | < 3 sec | Investigate infrastructure |
| Avg slippage | < 0.05% | Switch to limit orders |
| Sharpe (rolling) | > 0 | Report to A |
| Win rate | > 35% | Continue (within regime expectation) |

---

## Kill-Switch Triggers

| # | Trigger | Action | Reset |
|---|---------|--------|-------|
| K1 | Daily loss > 5% | Auto-halt | Next day, if A approves |
| K2 | Weekly loss > 10% | Auto-halt | Manual review + A approval |
| K3 | 3x consecutive high-latency | Pause BTC | Manual verification |
| K4 | Exchange API down > 30 min | Pause all | API recovery confirmed |
| K5 | A manual override | Immediate halt | A approval only |

---

## Escalation Path

```
Latency issue detected
  -> Log warning
  -> Skip trade
  -> If 3x consecutive: pause BTC
  -> If persists > 1 day: report to A
  -> A decides: continue / extend pause / halt indefinitely
```

---

## BTC vs SOL Guard Differences

| Guard | SOL | BTC |
|-------|-----|-----|
| Latency requirement | Standard (< 30 sec) | **Strict (< 5 sec)** |
| Skip rule | Optional | **Mandatory** |
| Slippage threshold | 0.2% | **0.1%** |
| High-latency detection | Not required | **Required (3x rule)** |
| Order type preference | Market OK | **Limit preferred** |

---

## Prohibited Actions

| Prohibition | Reason |
|-------------|--------|
| Disabling latency guard | A's ruling: guard is mandatory |
| Market orders without spread check | Latency risk |
| Ignoring skip signals | Each skip is a safety mechanism |
| Real capital without guard verification | Phase 5a is paper only |
| Treating BTC same as SOL for execution | Different latency profiles |

---

## Signature

```
CR-046 BTC/USDT Latency Guard Checklist
Mode: Guarded paper trading only
Guards: 7-point pre-trade, 3 latency-specific, kill-switch
Approved by: A (Decision Authority)
Date: 2026-04-01
```
