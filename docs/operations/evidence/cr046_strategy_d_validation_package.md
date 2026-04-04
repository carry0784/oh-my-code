# CR-046: Strategy D Validation Package

**CG-2B Candidate Seed #1: SMC + WaveTrend + Supertrend (2/3 Consensus)**

Date: 2026-04-01
Status: **PROPOSED**
Prerequisite: 6-Indicator Backtest Results (`indicator_backtest_results.json`)
Scope: Out-of-sample / no-repaint / multi-regime validation of Strategy D
Relation to CR-045: **Independent** -- CR-045 sealed baseline is NOT modified

---

## 1. Background

6-indicator backtest (2025-10-03 ~ 2026-04-01, BTC/USDT 1H, 4320 bars) produced:

| Strategy | Return | Sharpe | WinR | MDD | PF | Trades |
|----------|--------|--------|------|-----|------|--------|
| Buy & Hold | -43.11% | -- | -- | -- | -- | -- |
| **Strategy D** | **+64.32%** | **4.71** | **53.6%** | **14.41%** | **1.92** | **56** |

Strategy D = SMC + WaveTrend + Supertrend, 2/3 consensus voting.

**A's decision**: In-sample performance is impressive but insufficient for operational deployment. Strategy D is approved as **priority-1 candidate for validation**, NOT for immediate integration.

---

## 2. Why Validation is Required Before Deployment

### 2A. Selection Bias Risk

The Top 3 indicators were **chosen from the same dataset** used to measure performance. This is a textbook look-ahead selection bias:

```
6 indicators tested on Period X
    --> Rank by Sharpe on Period X
        --> Top 3 selected on Period X
            --> Composite tested on Period X
                --> Performance measured on Period X   <-- SAME DATA
```

**Impact**: Sharpe 4.71 may be partially or wholly attributable to overfitting.

### 2B. SMC Repaint / Look-Ahead Risk

Smart Money Concepts relies on swing point detection:

```
swing_high[i] = high[i] == max(high[i-L : i+L+1])
```

This requires `L` future bars to confirm a swing point. If not properly lagged, the strategy effectively "sees the future":

- BOS/CHoCH signals may appear at bar `i` but actually require information up to bar `i+L`
- In live execution, these signals would not exist until `L` bars later
- This inflates win rate and return in backtesting

### 2C. Single-Asset / Single-Regime Dependency

- **Asset**: BTC/USDT only
- **Regime**: Strong downtrend (-43.11%)
- **Timeframe**: 1H only

A strategy that works in one regime on one asset may fail catastrophically in others.

### 2D. Execution Realism Gap

Current backtest includes:
- [x] Taker fee (0.075%)

Current backtest does NOT include:
- [ ] Spread / slippage
- [ ] Funding rate (for shorts held > 8h)
- [ ] Order book depth impact
- [ ] Execution latency
- [ ] Partial fills

---

## 3. Validation Plan

### Phase 1: No-Lookahead / No-Repaint Verification

| # | Check | Method | Pass Criteria |
|---|-------|--------|---------------|
| 1.1 | SMC swing detection lag | Code audit: verify all swing points use only `[i-L:]` (no future data) | No `[i+k]` for k > 0 in signal generation |
| 1.2 | Signal timestamp integrity | For each signal at bar `i`, verify all inputs are from bars <= `i` | 100% signals use only past/current data |
| 1.3 | Repaint test | Run on historical data, record signals. Re-run on same data extended by 100 bars. Compare. | 0 signal changes in overlapping period |
| 1.4 | Bar-close-only execution | Verify all entries/exits use close price of signal bar (not intra-bar) | All trade prices == bar close |

### Phase 2: Out-of-Sample / Walk-Forward

| # | Test | Method | Pass Criteria |
|---|------|--------|---------------|
| 2.1 | Temporal OOS split | Train: Oct 2025 - Jan 2026 (4 months), Test: Feb - Apr 2026 (2 months). Selection + weights from train only. | OOS Sharpe > 0.5, OOS Return > 0% |
| 2.2 | Walk-forward (3 windows) | 3-month train / 1-month test, rolling. Average OOS metrics. | Mean OOS Sharpe > 0.3 |
| 2.3 | Purged cross-validation | 5-fold purged CV with 48h embargo between folds | Mean CV Sharpe > 0.3 |
| 2.4 | Selection stability | In each fold: re-rank indicators, check if Top 3 remains {SMC, WaveTrend, Supertrend} | Top 3 stable in >= 3/5 folds |

### Phase 3: Multi-Asset / Multi-Regime

| # | Test | Method | Pass Criteria |
|---|------|--------|---------------|
| 3.1 | ETH/USDT backtest | Same strategy, same period, ETH | Sharpe > 0, PF > 1.0 |
| 3.2 | SOL/USDT backtest | Same strategy, same period, SOL | Sharpe > 0, PF > 1.0 |
| 3.3 | Bull regime test | Identify 3-month uptrend period, test Strategy D | Return > Buy & Hold |
| 3.4 | Sideways regime test | Identify 3-month range period, test Strategy D | MDD < 20%, no catastrophic loss |
| 3.5 | Flash crash resilience | Test on May 2024 or similar crash event if data available | No account-destroying drawdown |

### Phase 4: Execution Realism

| # | Test | Method | Pass Criteria |
|---|------|--------|---------------|
| 4.1 | Spread + slippage | Add 0.05% slippage per trade | Sharpe still > 0.5 |
| 4.2 | Funding rate impact | Deduct average funding (-0.01% per 8h for shorts) | Return reduction < 30% of original |
| 4.3 | Latency simulation | Delay entry by 1 bar (execute on next bar's open) | Sharpe still > 0 |
| 4.4 | Realistic fee tier | Use 0.1% taker (non-VIP Binance) | PF still > 1.0 |

### Phase 5: CG-2B Exercisability Assessment

| # | Test | Method | Pass Criteria |
|---|------|--------|---------------|
| 5.1 | trade_count_by_signal_family | Count signals per indicator in composite | Each indicator contributes >= 10% of signals |
| 5.2 | candidate_generation_rate | Simulate monthly candidate generation | >= 5 candidates/month |
| 5.3 | governance_exercisability_rate | Simulate governance gate decisions | >= 1 decision/week |
| 5.4 | fitness distribution | Calculate fitness distribution of generated candidates | > 20% of candidates have fitness > 0 |

---

## 4. Strategy D Signal Definitions

### 4A. SMC (Smart Money Concepts)

```
Signal Type: Structure break detection (BOS / CHoCH)
Swing Detection: Pivot high/low with lookback L=5 bars (confirmed, no future data)
BOS (Bullish): Close > last confirmed swing high, current trend already bullish
CHoCH (Bullish): Close > last confirmed swing high, current trend was bearish (reversal)
BOS (Bearish): Close < last confirmed swing low, current trend already bearish
CHoCH (Bearish): Close < last confirmed swing low, current trend was bullish (reversal)
Signal: +1 for bullish BOS/CHoCH, -1 for bearish BOS/CHoCH
```

### 4B. WaveTrend [LazyBear]

```
Params: Channel Length=10, Average Length=21, OB=60, OS=-60
ap = HLC3
esa = EMA(ap, 10)
d = EMA(|ap - esa|, 10)
ci = (ap - esa) / (0.015 * d)
wt1 = EMA(ci, 21)
wt2 = SMA(wt1, 4)
Signal: +1 when wt1 crosses above wt2, -1 when wt1 crosses below wt2
Strong signal: cross in OB/OS zone
```

### 4C. Supertrend

```
Params: ATR Period=10, Multiplier=3.0
up = HL2 - 3.0 * ATR(10)
dn = HL2 + 3.0 * ATR(10)
trend = +1 if close > dn(prev), -1 if close < up(prev)
Signal: +1 on trend flip to bullish, -1 on trend flip to bearish
```

### 4D. Composite (Strategy D)

```
weighted_score = SMC_signal * 1.0 + WaveTrend_signal * 1.0 + Supertrend_signal * 1.0
BUY:  weighted_score >= 2   (2 of 3 agree bullish)
SELL: weighted_score <= -2  (2 of 3 agree bearish)
HOLD: otherwise

Risk Management:
  Stop Loss:    -2%
  Take Profit:  +4%
```

---

## 5. Prohibited Scope

| Prohibition | Compliance |
|-------------|------------|
| CR-045 sealed baseline modification | NOT MODIFIED -- CR-046 is independent |
| Immediate operational deployment | NOT DEPLOYED -- validation first |
| Approval based on return alone | NOT DONE -- multi-phase validation required |
| Threshold manipulation | NOT DONE -- min_trades, fitness>0 unchanged |
| dry_run bypass | NOT APPLICABLE -- no execution path |
| PENDING_OPERATOR bypass | NOT APPLICABLE -- no execution path |
| Schema/Alembic changes | NONE |

---

## 6. State Transition Impact

| Transition | Impact |
|------------|--------|
| CANDIDATE -> VALIDATED | No impact -- CR-046 adds a new validation path, does not modify existing |
| VALIDATED -> PAPER_TRADING | No impact |
| PAPER_TRADING -> PROMOTED | No impact |
| Governance gates | No impact -- Strategy D would go through same gates |
| Health monitor | No impact |

---

## 7. Log / Audit Impact

| Item | Impact |
|------|--------|
| shadow_run_cycle.py | NOT MODIFIED by CR-046 |
| day_NN.json | NOT MODIFIED |
| New audit fields (future) | `trade_count_by_signal_family`, `candidate_generation_rate`, `governance_exercisability_rate` |
| indicator_backtest_results.json | Already generated -- read-only reference |

---

## 8. Acceptance Criteria for Shadow Promotion

Strategy D may be promoted to shadow candidate ONLY when ALL of the following are met:

| # | Criterion | Threshold |
|---|-----------|-----------|
| AC-1 | No-lookahead verification | 0 violations |
| AC-2 | No-repaint verification | 0 signal changes |
| AC-3 | OOS Sharpe (temporal split) | > 0.5 |
| AC-4 | Walk-forward mean Sharpe | > 0.3 |
| AC-5 | Selection stability | Top 3 stable in >= 3/5 folds |
| AC-6 | Multi-asset Sharpe (ETH or SOL) | > 0 |
| AC-7 | Slippage-adjusted Sharpe | > 0.5 |
| AC-8 | Latency-adjusted Sharpe | > 0 |
| AC-9 | Candidate generation rate | >= 5/month |
| AC-10 | Governance exercisability | >= 1 decision/week |

**All 10 criteria must pass.** Partial pass = HOLD.

---

## 9. Unresolved Risks

| # | Risk | Severity | Mitigation |
|---|------|----------|------------|
| 1 | Selection bias inflates Sharpe 4.71 | **High** | OOS + walk-forward will reveal true performance |
| 2 | SMC repaint in current implementation | **High** | Phase 1 code audit. If repaint found, re-implement with strict lag |
| 3 | Downtrend-only performance | Medium | Multi-regime test (Phase 3). If bull/sideways fails, strategy is regime-conditional |
| 4 | BTC-only performance | Medium | ETH/SOL tests. If fails, strategy is asset-specific |
| 5 | Execution gap degrades returns | Medium | Phase 4 realism tests. If Sharpe drops below 0.5, recalibrate |
| 6 | Strategy D may not survive integration into evolution framework | Low | Phase 5 exercisability test |
| 7 | CR-046 delays CR-045 reShadow | Low | CR-046 is independent. reShadow continues on its own timeline |

---

## 10. In-Sample vs Post-Selection Comparison (A directive)

A explicitly requested comparison of pre-selection vs post-selection performance:

| Metric | Pre-Selection (all 6) | Post-Selection (Top 3) | Delta |
|--------|----------------------|----------------------|-------|
| Best individual Sharpe | 1.74 (SMC) | 1.74 (SMC) | 0 |
| Composite Sharpe | -1.94 (2/6 equal) | 4.71 (2/3 Top 3) | +6.65 |
| Composite Return | -40.30% | +64.32% | +104.62% |
| Composite MDD | 49.80% | 14.41% | -35.39% |

**The delta is enormous.** This strongly suggests selection bias is a major contributor. The +6.65 Sharpe improvement from selection alone is a red flag that must be resolved by OOS testing.

---

## 11. Implementation File List

| # | File | Type | Content |
|---|------|------|---------|
| 1 | `scripts/indicator_backtest.py` | EXISTS | 6-indicator backtest (already committed) |
| 2 | `scripts/strategy_d_oos_validator.py` | **NEW (Phase 2)** | Walk-forward + purged CV |
| 3 | `scripts/strategy_d_repaint_checker.py` | **NEW (Phase 1)** | No-lookahead / no-repaint audit |
| 4 | `scripts/strategy_d_multi_asset.py` | **NEW (Phase 3)** | ETH/SOL/multi-regime tests |
| 5 | `scripts/strategy_d_execution_sim.py` | **NEW (Phase 4)** | Slippage/funding/latency simulation |
| 6 | `docs/operations/evidence/cr046_strategy_d_validation_package.md` | **THIS FILE** | Package document |
| 7 | `docs/operations/evidence/cr046_validation_results.md` | **NEW (after execution)** | Results report |

---

## 12. Timeline

| Phase | Duration | Dependency |
|-------|----------|------------|
| Phase 1: No-repaint | 1 day | None |
| Phase 2: OOS / WF | 2 days | Phase 1 pass |
| Phase 3: Multi-asset | 1 day | Phase 1 pass |
| Phase 4: Execution | 1 day | Phase 2 pass |
| Phase 5: CG-2B | 1 day | Phase 2 pass |
| Results compilation | 1 day | All phases |
| **Total** | **~7 days** | Sequential, some parallel |

---

## CR-046 Constitutional Cross-Check

| Requirement | Implementation | Status |
|-------------|---------------|--------|
| CR-045 baseline unchanged | CR-046 is fully independent | OK |
| No immediate deployment | Validation-first approach | OK |
| No return-only approval | 10-criterion acceptance board | OK |
| Selection bias addressed | OOS + walk-forward + fold stability | OK |
| Repaint risk addressed | Phase 1 dedicated audit | OK |
| Multi-regime addressed | Phase 3 multi-asset/regime tests | OK |
| Execution realism addressed | Phase 4 slippage/funding/latency | OK |
| CG-2B exercisability assessed | Phase 5 candidate/governance rates | OK |
| Threshold manipulation forbidden | min_trades, fitness>0 unchanged | OK |
| dry_run=True maintained | No execution path in CR-046 | OK |

---

## Signature

```
CR-046: Strategy D Validation Package
Alias: CG-2B Candidate Seed #1 Validation
Status: PROPOSED
Purpose: Validate SMC+WaveTrend+Supertrend composite before operational deployment
Safety: CR-045 baseline untouched, no execution path, validation only

Prepared by: B (Implementer)
Approval required: A (Decision Authority)
Date: 2026-04-01
```
