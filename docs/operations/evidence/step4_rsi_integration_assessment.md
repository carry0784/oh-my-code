# RSI Strategy Operational Integration Assessment — Step 4 G3

## Strategy Identity

| Field | Value |
|-------|-------|
| Name | RSI_14_70_30 |
| Module | `strategies.rsi_strategy` |
| Class | RSICrossStrategy |
| Version | v1 |
| Origin | CR-045 |
| Consensus | 1/1 (single indicator) |

## Current Status

| Aspect | State |
|--------|-------|
| Code | Implemented, tracked |
| Catalog | Registered (EXPERIMENTAL) |
| Backtest | NOT STARTED |
| Paper | NOT STARTED |
| Production | FORBIDDEN |

## Regime Affinity Assessment

RSI crossover is designed for **ranging** and **high_volatility** markets where:

- Price oscillates between support/resistance levels
- Overbought/oversold extremes provide reliable mean-reversion signals
- Trending markets produce false signals (RSI stays OB/OS for extended periods)

**Catalog assignment:** `regime_affinity = ("ranging", "high_volatility")`

This complements the existing operational strategy (SMC+WT) which targets `trending_up` and `trending_down` regimes.

## Integration Decision

### Option A: Standalone Strategy (RECOMMENDED)

RSI runs as an independent strategy with its own signal path.
Regime-aware routing ensures it only activates in ranging/volatile regimes.

**Pros:**
- Clean separation from canonical SMC+WT
- Regime routing provides natural activation gate
- Easy to validate independently

**Cons:**
- 1/1 consensus (no second indicator confirmation)
- Lower confidence signals (0.6 vs 0.65 for consensus strategies)

### Option B: Ensemble Component

RSI acts as a third indicator in a multi-consensus framework.
Requires 2/3 or 3/3 consensus with other indicators.

**Pros:**
- Higher confidence through consensus
- Reduces false positives

**Cons:**
- Couples RSI to other strategies
- Harder to validate in isolation

### Verdict

**Option A (Standalone)** with regime routing gate.

RSI operates independently in ranging/high_volatility regimes only.
Validation path: backtest → paper → guarded_live, same as other strategies.

## Validation Requirements Before Promotion

1. [ ] Backtest on SOL/USDT 1H (400+ day, regime-filtered)
2. [ ] Backtest on BTC/USDT 1H (400+ day, regime-filtered)
3. [ ] Win rate > 50% in assigned regimes
4. [ ] Profit factor > 1.2 in assigned regimes
5. [ ] Paper trading minimum 14 days
6. [ ] No regime leakage (signals only in ranging/high_volatility)

## Track Assignment

**Track:** EXPERIMENTAL
**Promotion path:** EXPERIMENTAL → backtest PASS → paper PASS → OPERATIONAL
**Current gate:** Backtest NOT STARTED — no promotion eligible until backtest completes.
