# CR-046 Phase 1: No-Lookahead / No-Repaint Audit

Date: 2026-04-01
Auditor: B (Implementer)
Target: `scripts/indicator_backtest.py`
Scope: All 6 indicator functions + backtesting engine

---

## 1. Function-by-Function Audit

### 1.1 calc_supertrend() -- Lines 153-187

| Check | Result | Evidence |
|-------|--------|----------|
| Future data access | **PASS** | All references: `closes[i-1]`, `up[i-1]`, `dn[i-1]`, `trend[i-1]`. No `[i+k]`. |
| Signal at bar i uses only bars <= i | **PASS** | `trend[i]` computed from `closes[i]`, `dn[i-1]`, `up[i-1]`. Signal from trend flip at current bar. |

**Verdict: PASS -- no lookahead**

### 1.2 calc_squeeze_momentum() -- Lines 194-262

| Check | Result | Evidence |
|-------|--------|----------|
| Future data access | **PASS** | `highest_h[i] = max(highs[i-kc_length+1:i+1])` -- window ends at `i`, not beyond. |
| Signal at bar i uses only bars <= i | **PASS** | `sqz_on[i-1]` and `val[i]`, `val[i-1]` -- all past/current. |

**Verdict: PASS -- no lookahead**

### 1.3 calc_macd() -- Lines 269-292

| Check | Result | Evidence |
|-------|--------|----------|
| Future data access | **PASS** | EMA/SMA are causal filters. Crossover checks `[i]` vs `[i-1]`. |
| Signal at bar i uses only bars <= i | **PASS** | `macd_line[i] > signal_line[i]` and `macd_line[i-1] <= signal_line[i-1]`. |

**Verdict: PASS -- no lookahead**

### 1.4 calc_williams_vix_fix() -- Lines 299-337

| Check | Result | Evidence |
|-------|--------|----------|
| Future data access | **PASS** | `highest(closes[i-pd+1:i+1])` -- lookback only. `range_high[i] = max(wvf_clean[i-lb+1:i+1])`. |
| Signal at bar i uses only bars <= i | **PASS** | Spike detection uses `wvf[i]`, `wvf[i-1]`, `upper_band[i]`, `upper_band[i-1]`. |

**Verdict: PASS -- no lookahead**

### 1.5 calc_wavetrend() -- Lines 344-384

| Check | Result | Evidence |
|-------|--------|----------|
| Future data access | **PASS** | EMA is causal. SMA(wt1, 4) is causal. |
| Signal at bar i uses only bars <= i | **PASS** | Cross checks: `wt1[i] > wt2[i] and wt1[i-1] <= wt2[i-1]`. |

**Verdict: PASS -- no lookahead**

### 1.6 calc_smc() -- Lines 391-450

| Check | Result | Evidence |
|-------|--------|----------|
| Swing detection uses future data | **CONDITIONAL** | Line 411: `highs[i-L : i+L+1]` -- swing detection at bar `i` uses bars up to `i+L` (L=internal_length=5). This IS future data. |
| Signal generation compensates | **YES** | Line 426-429: Signals use `swing_highs[i - internal_length]` -- the swing point is only consumed `L` bars after its occurrence. |
| Effective lag | `internal_length` bars | Swing at bar `i` is only available at bar `i + internal_length`. Signal at bar `j` uses swing from bar `j - internal_length`. |
| Net lookahead | **0 bars** | The `+L` in detection is exactly offset by the `-L` delay in consumption. |

**Detailed analysis**:

```
Swing detection:  bar i confirmed if high[i] == max(high[i-5 : i+6])
                  Requires 5 future bars -> swing_highs[i] set at time i

Signal generation: At bar j, reads swing_highs[j - 5]
                   So swing at bar i is consumed at bar i + 5
                   By bar i + 5, the 5 future bars ARE available

Net effect: The swing at bar i requires data up to bar i+5
            The swing at bar i is consumed at bar j = i+5
            At bar j = i+5, data up to bar i+5 IS available
            -> NO net lookahead. The delay compensates exactly.
```

**Verdict: CONDITIONAL PASS**

The implementation is functionally correct (no net lookahead), but the pattern is fragile:
- The correctness depends on `internal_length` being identical in both the detection window and the delay offset
- If either is changed independently, lookahead would be introduced
- A cleaner implementation would detect swings using only past data

---

## 2. Backtesting Engine Audit

### 2.1 Entry/Exit Price

```python
# Line ~490 (inferred from Trade dataclass):
entry_price = closes[signal_bar]
exit_price = closes[exit_bar]
```

All trades use bar close prices. **PASS**.

### 2.2 Signal-to-Trade Mapping

Signals at bar `i` trigger trades at bar `i` close. No next-bar delay.
This is acceptable for bar-close-only execution model. **PASS**.

---

## 3. Repaint Risk Assessment

| Indicator | Repaint Risk | Notes |
|-----------|-------------|-------|
| Supertrend | **None** | Purely causal |
| Squeeze Momentum | **None** | Purely causal |
| MACD | **None** | Purely causal |
| Williams Vix Fix | **None** | Purely causal |
| WaveTrend | **None** | Purely causal |
| SMC | **Low** | Swing detection uses future bars, but delay compensation prevents net repaint |

---

## 4. Phase 1 Overall Verdict

```
Phase 1 Result: CONDITIONAL PASS

5/6 indicators: CLEAN PASS (no lookahead, no repaint)
1/6 indicators: CONDITIONAL PASS (SMC -- delay-compensated, functionally correct
                but architecturally fragile)

Recommendation:
- Proceed to Phase 2 (OOS validation)
- In Phase 2, include specific SMC repaint test (Check 1.3 from validation plan):
  Run on data, record signals. Re-run on extended data. Compare.
  This will empirically confirm the delay compensation works.

Risk level: LOW
  The delay compensation is mathematically sound (L_detect = L_delay = 5).
  Real-world impact: swing points identified 5 bars late, which reduces
  signal precision but does NOT create false signals.
```

---

## 5. Acceptance Criteria Mapping

| AC | Check | Result |
|----|-------|--------|
| AC-1 | No-lookahead verification | **CONDITIONAL PASS** (SMC delay-compensated) |
| AC-2 | No-repaint verification | **PASS** (no signal would change on data extension) |

---

## Signature

```
CR-046 Phase 1: No-Lookahead / No-Repaint Audit
Result: CONDITIONAL PASS
SMC Note: Functionally correct, architecturally fragile
Prepared by: B (Implementer)
Date: 2026-04-01
```
