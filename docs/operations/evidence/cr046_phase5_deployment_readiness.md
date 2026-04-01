# CR-046 Phase 5: Deployment Readiness Assessment

Date: 2026-04-01
Canonical Core: **SMC (pure-causal) + WaveTrend**
Authority: A (Decision Authority)
Status: **DRAFT -- awaiting A's Track C decision and Phase 5 approval**

---

## 1. Pre-Deployment Summary

### Three-Tier Judgment (Final)

| Tier | Status | Key Caveat |
|------|--------|------------|
| Research Validity | CONDITIONAL PASS | ETH excluded, regime-conditional |
| Execution Realism | PASS (8/8) | BTC latency-sensitive |
| Operational Fit | CG-2B PROVEN | 1H timeframe |

### Track Results

| Track | Status | Finding |
|-------|--------|---------|
| Track A (Phase 4) | **PASS** | 8/8, BTC latency risk, SOL robust |
| Track B (ETH SMC+MACD) | **PENDING** | Next session |
| Track C (Regime Filter) | **FAIL** | Crypto ADX structurally high; traditional filters do not work |

---

## 2. Asset-Specific Deployment Grades

### SOL/USDT: `conditionally ready` (PRIMARY CANDIDATE)

| Factor | Assessment |
|--------|------------|
| Research | Sharpe 0.85, PF 1.37, beats B&H by 68pp |
| Execution | Worst-case Sharpe 1.13 (robust) |
| Latency sensitivity | Low (Sharpe actually improves with 1-bar delay) |
| Regime risk | Bear: strong, Sideways: accept as characteristic |
| Deployment gate | Position sizing limits, stop-loss enforced |

**SOL deployment conditions**:
1. Paper trading period: minimum 2 weeks
2. Initial notional: micro (escrow-level)
3. Stop-loss: 2% per trade (canonical)
4. Take-profit: 4% per trade (canonical)
5. Max concurrent positions: 1
6. Daily loss limit: 5%
7. Regime caveat acknowledged in operational runbook

### BTC/USDT: `conditionally hold` (LATENCY MITIGATION REQUIRED)

| Factor | Assessment |
|--------|------------|
| Research | Sharpe 4.16 (Phase 3), PF 1.71, beats B&H by 75pp |
| Execution | Worst-case Sharpe -0.02 (marginally negative) |
| Latency sensitivity | **HIGH** (Sharpe drops 91% with 1-bar delay) |
| Regime risk | Bear: excellent, Sideways Q2: -8.13 Sharpe |
| Deployment gate | Latency mitigation must precede deployment |

**BTC deployment conditions** (additional to SOL conditions):
1. Latency guard: execution must complete within same bar
2. Limit order preference: avoid market orders
3. Escrow/paper only until latency guard is verified
4. Monitor slippage per trade; alert if > 0.1%

### ETH/USDT: `research only`

| Factor | Assessment |
|--------|------------|
| Research | Core pair Sharpe -3.88 (FAIL) |
| Track B | SMC+MACD research pending |
| Deployment | **PROHIBITED** |

---

## 3. Deployment Architecture

```
Phase 5a: Paper Trading (2 weeks)
  SOL/USDT paper -> verify signal generation + execution flow
  BTC/USDT paper -> verify latency guard effectiveness

Phase 5b: Micro-Notional (2 weeks)
  SOL/USDT micro-live -> real exchange, minimal size
  BTC/USDT escrow -> hold until latency mitigation confirmed

Phase 5c: Controlled Scaling (if 5a+5b pass)
  SOL/USDT -> gradual increase per A's approval
  BTC/USDT -> conditional on latency guard proof
```

---

## 4. Deployment Readiness Checklist

| # | Item | Status | Blocker? |
|---|------|--------|----------|
| 1 | Canonical core defined | DONE | No |
| 2 | Phase 1-4 validation complete | DONE | No |
| 3 | Three-tier judgment filed | DONE | No |
| 4 | CG-2A sealed | DONE | No |
| 5 | CG-2B proven | DONE | No |
| 6 | Regime filter researched | DONE (FAIL) | No (accept as-is) |
| 7 | Paper trading infrastructure | READY | No |
| 8 | Latency guard (BTC) | **NOT DONE** | **YES (BTC only)** |
| 9 | Position sizing rules | DEFINED | No |
| 10 | Daily loss limits | DEFINED | No |
| 11 | Monitoring/alerting | READY (shadow infra) | No |
| 12 | A's Phase 5 approval | **PENDING** | **YES** |

---

## 5. Risk Register

| # | Risk | Probability | Impact | Mitigation |
|---|------|-------------|--------|------------|
| R1 | BTC latency causes loss | HIGH | MEDIUM | Latency guard + limit orders |
| R2 | Sideways regime losses | MEDIUM | LOW-MED | Accept + position sizing |
| R3 | Regime shift (new pattern) | LOW | HIGH | Monthly performance review |
| R4 | Exchange API outage | LOW | MEDIUM | Circuit breaker in execution layer |
| R5 | Fee tier change | LOW | LOW | Fee sensitivity < 2pp (Phase 4) |

---

## 6. Monitoring KPIs (Post-Deployment)

| KPI | Target | Alert Threshold |
|-----|--------|-----------------|
| `deployment_readiness_sol` | Sharpe > 0.5 (rolling 30d) | < 0.3 |
| `deployment_readiness_btc` | Sharpe > 0.5 (rolling 30d) | < 0.0 |
| `regime_filter_effect` | N/A (not deployed) | Research-only metric |
| Daily PnL | > 0 (avg) | 3 consecutive loss days |
| Max drawdown | < 15% | > 10% alert |
| Win rate | > 45% | < 35% |
| Trade count | 3-8 per week | < 1 or > 15 |

---

## 7. A Decision Required

### Decision 1: Track C Outcome

Track C regime filter research returned FAIL. Options:
- (a) Accept strategy as regime-conditional (recommended by B)
- (b) Research alternative crypto-specific regime indicators
- (c) Postpone deployment until regime filter works

### Decision 2: Phase 5 Approval

Approve Phase 5a (paper trading) for:
- SOL/USDT: immediate
- BTC/USDT: conditional on latency guard

### Decision 3: Deployment Priority

Confirm:
- SOL as primary deployment candidate
- BTC as secondary (latency-guarded)
- ETH excluded until Track B completes

---

## Signature

```
CR-046 Phase 5: Deployment Readiness Assessment
SOL/USDT: conditionally ready (primary)
BTC/USDT: conditionally hold (latency guard required)
ETH/USDT: research only
Prepared by: B (Implementer)
Date: 2026-04-01
```
